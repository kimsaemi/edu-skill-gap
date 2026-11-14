#!/usr/bin/env python3
"""오프라인 추천 평가 장치
파일명: scripts/eval_offline.py

목적:
  기존 사람 판정 데이터(업무×과정 단위, 2인 판정 중 보수적 최소 판정 기준)를 정답 사전으로 활용하여,
  임의의 추천 결과 파일(Top 3)을 입력받아 다음을 평가합니다:
  (a) 판정 보유 항목의 적합률 (Strict: 적합 %, Lenient: 부분 적합 포함 %)
  (b) 판정 미보유 항목 비율 (판정 데이터 부재 비율 %)
  (c) 기본 추천(task_course_recommendations_90_reranked.csv) 대비 변경된 슬롯/강좌 수

주의사항:
  - 판정이 없는 항목을 적합이나 부적합으로 자의적으로 가정하지 않고 (a)와 (b)를 명확히 분리 표기합니다.
  - 본 장치는 개선안 탐색 및 '사전 걸러내기(Screening)' 용도이며, 여기서 점수가 높더라도
    새로운 홀드아웃 사람 평가 검증 전까지는 최종적인 개선 결론으로 간주할 수 없습니다.
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RECO = ROOT / "data" / "hr" / "output" / "recommendation"
DEFAULT_BASELINE = RECO / "task_course_recommendations_90_reranked.csv"


def build_ground_truth_dict():
    """1차, 2차, 홀드아웃 1차, 홀드아웃 2차의 사람 판정을 (task_id, course_uid) 단위로 통합

    판정 기준: 두 사람 중 낮은 판정 (적합 2 > 부분 적합 1 > 부적합 0)
    """
    r1 = pd.read_csv(RECO / "precision_eval_results.csv")
    r2 = pd.read_csv(RECO / "precision_eval_round2_results.csv")
    h1 = pd.read_csv(RECO / "precision_eval_holdout_results.csv")
    h2 = pd.read_csv(RECO / "precision_eval_holdout2_results.csv")
    k2 = pd.read_csv(RECO / "precision_eval_holdout2_key.csv")

    h2_m = h2.merge(k2[["item_id", "course_id"]], on="item_id", how="left")
    h2_m["course_uid"] = h2_m["course_id"]

    all_dfs = []
    for df in [r1, r2, h1, h2_m]:
        sub = df[["task_id", "course_uid", "judgment"]].dropna().copy()
        sub = sub[sub["judgment"].isin(["적합", "부분 적합", "부적합"])]
        all_dfs.append(sub)

    combined = pd.concat(all_dfs, ignore_index=True)
    rank_map = {"적합": 2, "부분 적합": 1, "부적합": 0}
    inv_map = {2: "적합", 1: "부분 적합", 0: "부적합"}

    combined["score"] = combined["judgment"].map(rank_map)

    # (task_id, course_uid)별 최소 점수 산출
    gt_df = (
        combined.groupby(["task_id", "course_uid"])
        .agg(min_score=("score", "min"), eval_count=("score", "count"))
        .reset_index()
    )
    gt_df["consensus_judgment"] = gt_df["min_score"].map(inv_map)

    gt_dict = {}
    for _, row in gt_df.iterrows():
        gt_dict[(row["task_id"], str(row["course_uid"]).strip())] = {
            "judgment": row["consensus_judgment"],
            "score": row["min_score"],
            "eval_count": row["eval_count"],
        }
    return gt_dict


def evaluate_recommendations(df_rec, df_baseline=None, gt_dict=None):
    """추천 결과 데이터프레임을 오프라인 정답 사전과 대조하여 지표 산출"""
    if gt_dict is None:
        gt_dict = build_ground_truth_dict()

    df_top3 = df_rec[df_rec["rank"] <= 3].copy()
    total_slots = len(df_top3)

    judged_items = []
    unjudged_count = 0

    for _, row in df_top3.iterrows():
        t_id = row["task_id"]
        c_uid = str(row["course_uid"]).strip()
        key = (t_id, c_uid)

        if key in gt_dict:
            judged_items.append({
                "task_id": t_id,
                "course_uid": c_uid,
                "judgment": gt_dict[key]["judgment"],
                "score": gt_dict[key]["score"],
            })
        else:
            unjudged_count += 1

    n_judged = len(judged_items)
    unjudged_pct = round(unjudged_count / total_slots * 100, 1) if total_slots else 0.0

    if n_judged > 0:
        strict_cnt = sum(1 for item in judged_items if item["judgment"] == "적합")
        lenient_cnt = sum(1 for item in judged_items if item["judgment"] in ["적합", "부분 적합"])
        unfit_cnt = sum(1 for item in judged_items if item["judgment"] == "부적합")
        strict_pct = round(strict_cnt / n_judged * 100, 1)
        lenient_pct = round(lenient_cnt / n_judged * 100, 1)
    else:
        strict_cnt = lenient_cnt = unfit_cnt = 0
        strict_pct = lenient_pct = None

    # 기본 추천 대비 변경 칸 수 및 강좌 수 계산
    diff_stats = {"changed_slots": 0, "changed_courses": 0, "total_slots": 0}
    if df_baseline is not None:
        base_top3 = df_baseline[df_baseline["rank"] <= 3].copy()
        base_grouped = base_top3.groupby(["task_id", "level"])
        rec_grouped = df_top3.groupby(["task_id", "level"])

        changed_slots = 0
        changed_courses = 0
        all_keys = set(base_grouped.groups.keys()) | set(rec_grouped.groups.keys())

        for k in all_keys:
            b_uids = set(base_grouped.get_group(k)["course_uid"]) if k in base_grouped.groups else set()
            r_uids = set(rec_grouped.get_group(k)["course_uid"]) if k in rec_grouped.groups else set()

            diff_courses = len(r_uids - b_uids)
            changed_courses += diff_courses
            if diff_courses > 0:
                changed_slots += 1

        diff_stats = {
            "changed_slots": changed_slots,
            "changed_courses": changed_courses,
            "total_slots": len(all_keys),
            "slot_change_pct": round(changed_slots / len(all_keys) * 100, 1) if all_keys else 0.0,
        }

    return {
        "total_top3_items": total_slots,
        "judged_count": n_judged,
        "unjudged_count": unjudged_count,
        "unjudged_pct": unjudged_pct,
        "strict_fit_count": strict_cnt,
        "lenient_fit_count": lenient_cnt,
        "unfit_count": unfit_cnt,
        "strict_precision": strict_pct,
        "lenient_precision": lenient_pct,
        "diff_stats": diff_stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline Recommender Evaluation Tool")
    parser.add_argument("input_csv", nargs="?", default=str(DEFAULT_BASELINE), help="추천 결과 CSV 경로")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="대조할 기본 추천 CSV 경로")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    baseline_path = Path(args.baseline)

    if not input_path.exists():
        print(f"[오류] 입력 파일 {input_path}을 찾을 수 없습니다.")
        sys.exit(1)

    df_in = pd.read_csv(input_path)
    df_base = pd.read_csv(baseline_path) if baseline_path.exists() else None

    gt = build_ground_truth_dict()
    res = evaluate_recommendations(df_in, df_base, gt)

    print("=" * 75)
    print(" 오프라인 추천 결과 스크리닝 평가 리포트")
    print("=" * 75)
    print(f"입력 파일: {input_path.name} (Top 3 총 {res['total_top3_items']}개 슬롯 강좌)")
    print(f"정답 사전: 총 {len(gt)}개 (업무 × 강좌) 2인 보수적 합의 판정 데이터")
    print("-" * 75)
    print(f"(a) 판정 보유 항목 평가 (표본 {res['judged_count']}개):")
    if res["strict_precision"] is not None:
        print(f"    - 엄격 적합률 (Strict, '적합'): {res['strict_precision']}% ({res['strict_fit_count']}/{res['judged_count']})")
        print(f"    - 완화 적합률 (Lenient, '적합'+'부분 적합'): {res['lenient_precision']}% ({res['lenient_fit_count']}/{res['judged_count']})")
        print(f"    - 부적합 판정 수: {res['unfit_count']}개")
    else:
        print("    - 판정 보유 항목이 없습니다.")

    print(f"\n(b) 판정 미보유 항목 비율:")
    print(f"    - 미보유 항목 수: {res['unjudged_count']}개 ({res['unjudged_pct']}%)")
    if res["unjudged_pct"] > 50.0:
        print(f"    [경고] 판정 미보유 항목 비율이 {res['unjudged_pct']}%로 매우 높습니다.")
        print("           기존 사람 평가에 없는 새로운 과정이 대거 포함되어 있으므로,")
        print("           위 (a)의 적합률 수치만으로 추천 품질을 속단할 수 없습니다.")

    print(f"\n(c) 기본 추천 대비 변경 규모:")
    ds = res["diff_stats"]
    print(f"    - 변경된 슬롯 수: {ds['changed_slots']}/{ds['total_slots']} 슬롯 ({ds.get('slot_change_pct', 0.0)}%)")
    print(f"    - 교체된 강좌 수: {ds['changed_courses']}개")
    print("-" * 75)
    print("[안내] 본 평가는 개선안 탐색 과정의 '사전 걸러내기(Screening)' 용도입니다.")
    print("       여기서 산출된 적합률은 기존 판정 표본에 국한된 추정치이며,")
    print("       새로운 홀드아웃 3차 사람 블라인드 평가를 통해서만 실제 개선 여부를 검증할 수 있습니다.")
    print("=" * 75)


if __name__ == "__main__":
    main()
