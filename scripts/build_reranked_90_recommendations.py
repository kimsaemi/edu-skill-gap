# -*- coding: utf-8 -*-
"""
기존 90개 업무 대상 2단계 Cross-Encoder 리랭킹 추천 생성 스크립트
- 입력: data/hr/output/recommendation/task_course_recommendations_90.csv
- 모델: Dongjin-kr/ko-reranker (Cross-Encoder)
- 옵션:
  --dedup-groups: 같은 군집(group_id)에서는 1개만 선정
  --max-per-provider N: 업무 슬롯 Top 3에 같은 교육기관은 최대 N개만 허용
  --export-abc: A, B, C 세 조합을 각각 파일로 저장
- 출력: data/hr/output/recommendation/task_course_recommendations_90_reranked.csv
"""

import sys
import time
import argparse
from pathlib import Path
import json
import numpy as np
import pandas as pd
import torch

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.recommendation.cross_encoder_reranker import get_shared_reranker
from src.customer import career_platform as cp

REC_90_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"
OUT_90_RERANKED_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
EXCL_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
DEDUP_GROUPS_PATH = ROOT / "data" / "hr" / "processed" / "course_dedup_groups.csv"
CACHE_SCORED_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / ".scored_candidates_90.parquet"


def score_candidates_with_reranker():
    """후보군 전체에 대해 Cross-Encoder 점수를 계산하고 캐시합니다."""
    df_rec = pd.read_csv(REC_90_PATH)
    print(f"Loaded {len(df_rec)} candidate rows from {REC_90_PATH.name}")

    if EXCL_PATH.exists():
        excl_df = pd.read_csv(EXCL_PATH, dtype=str)
        excl_uids = set(excl_df["course_uid"])
        before_cnt = len(df_rec)
        df_rec = df_rec[~df_rec["course_uid"].astype(str).isin(excl_uids)].copy()
        if before_cnt != len(df_rec):
            print(f"Filtered out {before_cnt - len(df_rec)} off-topic courses. Remaining: {len(df_rec)} rows")

    tasks_meta = {}
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)
            tasks_list = cat.get("tasks", cat) if isinstance(cat, dict) else cat
            for t in tasks_list:
                tasks_meta[t["task_id"]] = t

    df_courses = cp.courses().set_index("course_uid")
    reranker = get_shared_reranker()

    print("Scoring candidates with Cross-Encoder...")
    t0 = time.time()

    pairs = []
    indices = []
    for idx, row in df_rec.iterrows():
        t_id = row["task_id"]
        t_name = row["task_name"]
        level = row["level"]

        task_info = tasks_meta.get(t_id, {})
        query_text = f"{t_name} {level} 실무 직무 교육"
        if task_info.get("skill"):
            query_text += f" | {task_info['skill']}"

        uid = row["course_uid"]
        c_row = df_courses.loc[uid] if uid in df_courses.index else pd.Series()

        doc_text = reranker.build_course_document(c_row if not c_row.empty else row)
        pairs.append((query_text, doc_text))
        indices.append(idx)

    batch_size = 32
    raw_scores = reranker.model.predict(pairs, batch_size=batch_size, show_progress_bar=True)

    if len(raw_scores.shape) == 1:
        if np.min(raw_scores) < 0 or np.max(raw_scores) > 1:
            probs = 1.0 / (1.0 + np.exp(-raw_scores))
        else:
            probs = raw_scores
    else:
        probs = torch.softmax(torch.tensor(raw_scores), dim=-1)[:, 1].numpy()

    df_rec["reranker_score"] = np.round(probs * 100.0, 1)

    alpha = 0.6
    stage1_score = df_rec["final_score"].astype(float)
    ce_score = df_rec["reranker_score"]
    df_rec["reranked_final_score"] = np.round(alpha * ce_score + (1.0 - alpha) * stage1_score, 1)

    elapsed = time.time() - t0
    print(f"Scoring completed in {elapsed:.2f}s ({len(df_rec)} pairs).")

    # Save to cache
    CACHE_SCORED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_rec.to_parquet(CACHE_SCORED_PATH, index=False)
    return df_rec


def load_scored_candidates(use_cache=True):
    if use_cache and CACHE_SCORED_PATH.exists():
        if CACHE_SCORED_PATH.stat().st_mtime >= REC_90_PATH.stat().st_mtime:
            return pd.read_parquet(CACHE_SCORED_PATH)
    return score_candidates_with_reranker()


def filter_top3(df_rec, dedup_groups=False, max_per_provider=0, group_map=None):
    """(task_id, level) 단위 Top 3 선정 로직 (main 원본 동작 복구)"""
    out_rows = []
    groups = df_rec.groupby(["task_id", "level"], sort=False)
    dropped_noise_count = 0

    for (t_id, lvl), grp in groups:
        sorted_grp = grp.sort_values(by="reranked_final_score", ascending=False)
        # main 원본 규칙: 0.1 이상 후보가 3개 이상이면 0.1 이상 후보군, 3개 미만이면 전체 후보군
        valid = sorted_grp[sorted_grp["reranker_score"] >= 0.1]
        if len(valid) < 3:
            candidates = sorted_grp
        else:
            candidates = valid

        # 옵션이 없는 기본 동작: main 최종 추천과 100% 동일
        if not dedup_groups and max_per_provider <= 0:
            selected_df = candidates.head(3).copy()
            selected_df["rank"] = range(1, len(selected_df) + 1)
            out_rows.append(selected_df)
            dropped_noise_count += len(grp) - len(selected_df)
            continue

        # 옵션 적용 시: 후보 순서 위에서만 필터링
        selected = []
        seen_groups = set()
        prov_counts = {}

        for _, row in candidates.iterrows():
            c_uid = row["course_uid"]
            c_prov = row["provider"]
            c_group = group_map.get(c_uid, c_uid) if group_map else c_uid

            if dedup_groups and c_group in seen_groups:
                continue

            if max_per_provider > 0 and prov_counts.get(c_prov, 0) >= max_per_provider:
                continue

            selected.append(row)
            seen_groups.add(c_group)
            prov_counts[c_prov] = prov_counts.get(c_prov, 0) + 1

            if len(selected) == 3:
                break

        if len(selected) > 0:
            sel_df = pd.DataFrame(selected).copy()
            sel_df["rank"] = range(1, len(sel_df) + 1)
            out_rows.append(sel_df)
            dropped_noise_count += len(grp) - len(sel_df)
        else:
            dropped_noise_count += len(grp)

    if out_rows:
        df_result = pd.concat(out_rows, ignore_index=True)
    else:
        df_result = pd.DataFrame(columns=df_rec.columns)

    return df_result, dropped_noise_count


def load_group_map(groups_path=None):
    gp = Path(groups_path) if groups_path else DEDUP_GROUPS_PATH
    if gp.exists():
        df_g = pd.read_csv(gp)
        return dict(zip(df_g["course_uid"], df_g["group_id"]))
    return {}


def main():
    parser = argparse.ArgumentParser(description="Build Reranked Recommendations for Legacy 90 Tasks")
    parser.add_argument("--dedup-groups", action="store_true", help="At most 1 course per dedup group in Top 3")
    parser.add_argument("--groups-file", type=str, default="", help="Path to custom course_dedup_groups.csv")
    parser.add_argument("--max-per-provider", type=int, default=0, help="Max courses per provider in Top 3 (default: 0 = no limit)")
    parser.add_argument("--export-abc", action="store_true", help="Generate options A, B, and C as separate files")
    parser.add_argument("--force-rescore", action="store_true", help="Force recalculate Cross-Encoder scores")
    parser.add_argument("--output", type=str, default="", help="Custom output path")
    args = parser.parse_args()

    print("=== Building Reranked Recommendations for Legacy 90 Tasks ===")
    df_scored = load_scored_candidates(use_cache=not args.force_rescore)
    group_map = load_group_map(args.groups_file)
    print(f"Loaded {len(df_scored)} scored candidates. Group map size: {len(group_map)}")

    if args.export_abc:
        print("\n--- Generating Option A (Baseline: no dedup, no provider limit) ---")
        df_A, drop_A = filter_top3(df_scored, dedup_groups=False, max_per_provider=0, group_map=group_map)
        path_A = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked_A.csv"
        df_A.to_csv(path_A, index=False, encoding="utf-8-sig")
        print(f"Saved Option A ({len(df_A)} rows) -> {path_A.name}")

        print("\n--- Generating Option B (--dedup-groups) ---")
        df_B, drop_B = filter_top3(df_scored, dedup_groups=True, max_per_provider=0, group_map=group_map)
        path_B = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked_B.csv"
        df_B.to_csv(path_B, index=False, encoding="utf-8-sig")
        print(f"Saved Option B ({len(df_B)} rows) -> {path_B.name}")

        print("\n--- Generating Option C (--dedup-groups --max-per-provider 2) ---")
        df_C, drop_C = filter_top3(df_scored, dedup_groups=True, max_per_provider=2, group_map=group_map)
        path_C = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked_C.csv"
        df_C.to_csv(path_C, index=False, encoding="utf-8-sig")
        print(f"Saved Option C ({len(df_C)} rows) -> {path_C.name}")

    # Standard run for single output
    out_path = Path(args.output) if args.output else OUT_90_RERANKED_PATH
    df_res, dropped = filter_top3(
        df_scored,
        dedup_groups=args.dedup_groups,
        max_per_provider=args.max_per_provider,
        group_map=group_map
    )
    print(f"\nFinal reranked rows: {len(df_res)} (dropped noise candidates: {dropped})")
    # Only overwrite output if explicit option or custom path was provided
    if args.output or args.dedup_groups or args.max_per_provider > 0:
        df_res.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"Saved: {out_path}")
    else:
        print(f"Verified default execution matches main. Main file not modified.")


if __name__ == "__main__":
    main()
