# -*- coding: utf-8 -*-
"""
홀드아웃 3차 사람 블라인드 평가 시트 및 정답 키 파일 생성 스크립트
파일명: scripts/make_holdout3_eval_sheet.py

목적:
1. 1차·2차·홀드아웃 1차·홀드아웃 2차에서 한 번도 평가되지 않은 60개 업무 중 10개 업무를 엄선.
   - 9개 직무 분야를 고르게 포함 (DOM_01~DOM_09 각 1개 + 추가 1개 = 10개)
   - 3개 수준(입문 3개, 실무 4개, 관리자·심화 3개)을 균형 있게 배정
   - 시드 고정(seed=42)으로 재현성 보장
2. 기존 최종 추천(Baseline) Top 3 vs 통합 개선안(Candidate) Top 3의 합집합 구성 (중복 과정은 'shared'로 단일화).
3. 업무마다 명백한 비인사 과정(IT·무역·제조·회계 등) 1개씩 위약(Decoy)으로 삽입 (총 10개).
4. 블라인드 평가 시트(precision_eval_holdout3_items.csv)에는 출처를 일절 숨기고,
   정답 키(precision_eval_holdout3_key.csv)에만 baseline/candidate/shared/decoy 출처를 보관.
"""

import sys
import json
import re
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.course_links import detail_url

CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
EVAL_ORIG_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
HOLDOUT1_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_items.csv"
HOLDOUT2_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_items.csv"

BASE_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
CAND_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_candidate.csv"
COURSES_PARQUET = ROOT / "data" / "hr" / "processed" / "education_courses_integrated.parquet"

OUT_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_items.csv"
OUT_KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_key.csv"


def clean_summary_text(val):
    if pd.isna(val) or val is None:
        return ""
    t = re.sub(r"\s+", " ", str(val)).strip()
    return t[:200]


def get_course_intro_summary(row):
    for col in ["learning_goals", "course_intro", "curriculum"]:
        val = row.get(col)
        if pd.notna(val) and val is not None:
            text = clean_summary_text(val)
            if text:
                return text
    return ""


def select_holdout3_tasks(cat_tasks, prev_evaluated_ids, df_base, df_cand, seed=42):
    """
    미평가 60개 업무 중 10개 업무 및 수준 선정
    - 9개 직무 분야 각 1개 + 잔여 풀 1개 = 10개
    - 입문 3개, 실무 4개, 관리자·심화 3개 균형 배정
    """
    rng = np.random.default_rng(seed)

    rem_tasks = [t for t in cat_tasks if t["task_id"] not in prev_evaluated_ids]
    tasks_by_dom = {}
    for t in rem_tasks:
        tasks_by_dom.setdefault(t["domain_id"], []).append(t)

    selected = []
    # 9개 분야에서 각 1개
    for dom_id in sorted(tasks_by_dom.keys()):
        cand_list = sorted(tasks_by_dom[dom_id], key=lambda x: x["task_id"])
        chosen = rng.choice(cand_list)
        selected.append(chosen)

    # 10번째 업무 (잔여 풀에서 1개 추가)
    chosen_ids = {t["task_id"] for t in selected}
    rem_pool = sorted([t for t in rem_tasks if t["task_id"] not in chosen_ids], key=lambda x: x["task_id"])
    extra = rng.choice(rem_pool)
    selected.append(extra)

    # 10개 슬롯의 수준: 입문 3개, 실무 4개, 관리자·심화 3개
    levels_pool = ["입문", "실무", "관리자·심화", "입문", "실무", "관리자·심화", "입문", "실무", "관리자·심화", "실무"]

    base_cnts = df_base.groupby(["task_id", "level"]).size().to_dict()
    cand_cnts = df_cand.groupby(["task_id", "level"]).size().to_dict()

    plan = []
    for t, lvl in zip(selected, levels_pool):
        key = (t["task_id"], lvl)
        b_cnt = base_cnts.get(key, 0)
        c_cnt = cand_cnts.get(key, 0)
        assert b_cnt >= 3, f"Baseline slot {key} has fewer than 3 recs: {b_cnt}"
        assert c_cnt >= 3, f"Candidate slot {key} has fewer than 3 recs: {c_cnt}"
        plan.append((t, lvl))

    return plan


def select_10_distinct_decoys(df_courses, seed=42):
    """
    명백한 비인사 과정(IT개발, 무역통관, 민사소송, AI그래픽, 구매조달, SAP비인사, 콜센터, 회계세무, 스마트제조, 전자/통신) 10개 추출
    """
    decoy_queries = [
        ("IT_딥러닝", r"PyTorch|신경망|딥러닝\s*첫걸음|추천\s*시스템\s*알고리즘"),
        ("무역_통관", r"수출입통관|FTA관세|원산지증명|보세사"),
        ("민사_소송", r"민사\s*소송|부동산등기|경매\s*실무"),
        ("AI_그래픽", r"ComfyUI|미드저니|Midjourney|AI\s*그림"),
        ("구매_조달", r"구매원가|구매전략|자재관리|협력사\s*조달"),
        ("SAP_비인사", r"S/4HANA\s*(?:CO|MM|SD)|SAP\s*(?:CO|MM|SD)"),
        ("콜센터_QA", r"상담품질\s*평가|QA\s*전문가"),
        ("재무_회계", r"전산회계|재무제표\s*읽는\s*법|원가회계"),
        ("제조_품질", r"스마트공장|생산자동화|품질경영|QC"),
        ("전자_통신", r"반도체|전자회로|네트워크\s*보안|CCNA"),
    ]

    selected_decoys = []
    used_uids = set()

    for category, pattern in decoy_queries:
        rx = re.compile(pattern, re.IGNORECASE)
        matched = df_courses[df_courses["title"].str.contains(rx, regex=True, na=False)]
        valid = matched[~matched.index.isin(used_uids)]
        if len(valid) == 0:
            # fallback: any course matched
            valid = matched

        chosen_row = valid.iloc[0]
        used_uids.add(chosen_row.name)
        selected_decoys.append({
            "category": category,
            "course_uid": chosen_row.name,
            "title": str(chosen_row["title"]),
            "provider": str(chosen_row.get("provider", "")),
            "url": str(chosen_row.get("url", "")),
            "row": chosen_row,
        })

    return selected_decoys


def build_holdout3_evaluation_data():
    print("=== 홀드아웃 3차 평가 데이터 준비 시작 ===")

    # 1. 데이터 로드
    cat_tasks = json.load(open(CATALOG_PATH, encoding="utf-8"))["tasks"]
    tasks_meta = {t["task_id"]: t for t in cat_tasks}

    prev_ids = (
        set(pd.read_csv(EVAL_ORIG_PATH)["task_id"])
        | set(pd.read_csv(HOLDOUT1_PATH)["task_id"])
        | set(pd.read_csv(HOLDOUT2_PATH)["task_id"])
    )
    print(f"과거 평가 완료 과업: {len(prev_ids)}개 (미평가 잔여 과업: {90 - len(prev_ids)}개)")

    df_base = pd.read_csv(BASE_REC_PATH)
    df_cand = pd.read_csv(CAND_REC_PATH)
    df_courses = pd.read_parquet(COURSES_PARQUET).set_index("course_uid")

    # 2. 10개 업무 및 수준 선정
    plan = select_holdout3_tasks(cat_tasks, prev_ids, df_base, df_cand, seed=42)
    print("\n선정된 홀드아웃 3차 10개 업무 및 수준 (seed=42):")
    for i, (t, lvl) in enumerate(plan, 1):
        print(f"  {i:2d}. [{lvl}] {t['task_id']} ({t['domain_name']}) - {t['task_name']}")

    # 3. 10개 디코이 과정 추출
    decoys = select_10_distinct_decoys(df_courses, seed=42)
    print("\n선정된 비인사 디코이 과정 10건:")
    for i, dec in enumerate(decoys, 1):
        print(f"  {i:2d}. [{dec['category']}] {dec['provider']} - {dec['title']}")

    # 4. 슬롯별 추천 합집합 및 디코이 조합 생성
    rng = np.random.default_rng(42)
    item_rows = []
    key_rows = []

    global_item_no = 1

    for slot_idx, (t_info, level) in enumerate(plan):
        t_id = t_info["task_id"]
        dom_name = t_info["domain_name"]
        t_name = t_info["task_name"]

        sub_base = df_base[(df_base["task_id"] == t_id) & (df_base["level"] == level) & (df_base["rank"] <= 3)].copy()
        sub_cand = df_cand[(df_cand["task_id"] == t_id) & (df_cand["level"] == level) & (df_cand["rank"] <= 3)].copy()

        base_uids = set(sub_base["course_uid"])
        cand_uids = set(sub_cand["course_uid"])

        slot_candidates = {}

        # Baseline
        for _, r in sub_base.iterrows():
            uid = str(r["course_uid"])
            slot_candidates[uid] = {
                "course_uid": uid,
                "title": str(r["title"]),
                "provider": str(r["provider"]),
                "source": "shared" if uid in cand_uids else "baseline",
            }

        # Candidate
        for _, r in sub_cand.iterrows():
            uid = str(r["course_uid"])
            if uid not in slot_candidates:
                slot_candidates[uid] = {
                    "course_uid": uid,
                    "title": str(r["title"]),
                    "provider": str(r["provider"]),
                    "source": "candidate",
                }

        # Decoy (slot마다 1개)
        decoy_item = decoys[slot_idx]
        dec_uid = str(decoy_item["course_uid"])
        slot_candidates[dec_uid] = {
            "course_uid": dec_uid,
            "title": decoy_item["title"],
            "provider": decoy_item["provider"],
            "source": "decoy",
            "decoy_category": decoy_item["category"],
        }

        # 블라인드 무작위 셔플 (순서로 출처를 알 수 없도록)
        cand_items = list(slot_candidates.values())
        rng.shuffle(cand_items)

        for c in cand_items:
            c_uid = c["course_uid"]
            c_row = df_courses.loc[c_uid] if c_uid in df_courses.index else pd.Series()
            raw_url = str(c_row.get("url", "")) if not c_row.empty else ""
            c_url = detail_url(raw_url) if raw_url else ""
            summary = get_course_intro_summary(c_row) if not c_row.empty else ""

            # 사용자 제공 열 구조 준수
            item_rows.append({
                "번호": global_item_no,
                "업무 분야": dom_name,
                "업무": t_name,
                "수준": level,
                "과정명": c["title"],
                "기관": c["provider"],
                "링크": c_url,
                "과정 소개(요약)": summary,
                "판정 (고르기)": "",
                "메모 (선택)": "",
            })

            key_rows.append({
                "번호": global_item_no,
                "업무 ID": t_id,
                "과정 UID": c_uid,
                "출처": c["source"],
                "수준": level,
                "과정명": c["title"],
                "기관": c["provider"],
                "디코이_분류": c.get("decoy_category", ""),
            })

            global_item_no += 1

    df_items = pd.DataFrame(item_rows)
    df_key = pd.DataFrame(key_rows)

    # 5. 엄격 검증
    print("\n=== 자동 검증 수행 ===")
    assert (df_items["판정 (고르기)"] == "").all(), "오류: 판정 칸이 비어 있지 않습니다."
    assert (df_items["메모 (선택)"] == "").all(), "오류: 메모 칸이 비어 있지 않습니다."
    assert "출처" not in df_items.columns, "오류: 블라인드 평가 시트에 출처가 노출되었습니다."
    assert len(df_items) == len(df_key), "오류: 평가 시트와 키 파일 행 수가 일치하지 않습니다."
    assert set(df_key["출처"]).issubset({"baseline", "candidate", "shared", "decoy"}), "오류: 허용되지 않은 출처 코드입니다."

    decoy_cnt = int((df_key["출처"] == "decoy").sum())
    assert decoy_cnt == 10, f"오류: 디코이 건수가 10건이 아닙니다 ({decoy_cnt}건)"
    print(f"[PASS] 블라인드 시트 및 키 파일 정합성 검증 통과 (총 {len(df_items)}개 평가 항목, 디코이 10개)")

    source_counts = df_key["출처"].value_counts().to_dict()
    print(f"출처별 항목 분포: {source_counts}")

    # 6. 파일 저장
    OUT_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_items.to_csv(OUT_ITEMS_PATH, index=False, encoding="utf-8-sig")
    df_key.to_csv(OUT_KEY_PATH, index=False, encoding="utf-8-sig")

    print(f"\n평가 시트 저장 완료: {OUT_ITEMS_PATH} ({len(df_items)}행)")
    print(f"정답 키 저장 완료: {OUT_KEY_PATH} ({len(df_key)}행)")


if __name__ == "__main__":
    build_holdout3_evaluation_data()
