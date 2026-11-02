# -*- coding: utf-8 -*-
"""
사람 평가 60건(30개 항목) 기준,
1) 기존 Baseline 추천(task_course_recommendations_90.csv)과
2) 현재 리랭커 추천(task_course_recommendations_90_reranked.csv)의
Top 3 추천 목록 및 Precision@3 비교 스크립트
"""

import sys
from pathlib import Path
import pandas as pd
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

EVAL_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
REC_BASE = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"
REC_RERANK = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"


def main():
    eval_df = pd.read_csv(EVAL_CSV)
    
    # 두 사람의 판정 매핑 (낮은 쪽을 항목 보수적 판정으로 사용)
    rank_of = {"적합": 2, "부분 적합": 1, "부적합": 0}
    inv_rank = {2: "적합", 1: "부분 적합", 0: "부적합"}
    
    eval_done = eval_df[eval_df["judgment"].isin(rank_of)].copy()
    eval_done["score"] = eval_done["judgment"].map(rank_of)
    
    # item_no 단위 ground truth
    item_gt = (eval_done.groupby(["task_id", "level", "course_uid", "title"], as_index=False)
               .agg({"score": "min", "judgment": lambda s: list(s)}))
    item_gt["final_judgment"] = item_gt["score"].map(inv_rank)
    
    gt_lookup = {}
    for _, r in item_gt.iterrows():
        key = (r["task_id"], r["level"], r["course_uid"])
        gt_lookup[key] = {
            "judgment": r["final_judgment"],
            "raw": r["judgment"],
            "title": r["title"]
        }

    print(f"=== Ground Truth Loaded: {len(gt_lookup)} unique evaluated course instances ===")

    # Compare for the 10 evaluated tasks
    tasks = eval_df[["task_id", "task", "level"]].drop_duplicates()
    
    df_base = pd.read_csv(REC_BASE)
    df_rerank = pd.read_csv(REC_RERANK)

    print("\n--- Comparing Top 3 for the 10 Evaluated Tasks ---")
    
    base_scores = []
    rerank_scores = []

    for _, t in tasks.iterrows():
        t_id, t_name, lvl = t["task_id"], t["task"], t["level"]
        print(f"\n[Task: {t_id} | {lvl}] {t_name}")
        
        # 1. Base Top 3
        b_sub = df_base[(df_base["task_id"] == t_id) & (df_base["level"] == lvl)].sort_values("rank").head(3)
        print("  <1단계 Baseline Top 3>")
        for _, row in b_sub.iterrows():
            uid = row["course_uid"]
            gt = gt_lookup.get((t_id, lvl, uid))
            judg = gt["judgment"] if gt else "미평가"
            base_scores.append(judg)
            print(f"    - Rank {row['rank']}: {row['title'][:32]}... | 판정: {judg}")

        # 2. Reranked Top 3
        r_sub = df_rerank[(df_rerank["task_id"] == t_id) & (df_rerank["level"] == lvl)].sort_values("rank").head(3)
        print("  <2단계 리랭커 Top 3>")
        for _, row in r_sub.iterrows():
            uid = row["course_uid"]
            gt = gt_lookup.get((t_id, lvl, uid))
            judg = gt["judgment"] if gt else "신규(미평가)"
            rerank_scores.append(judg)
            print(f"    - Rank {row['rank']}: {row['title'][:32]}... | CE: {row.get('reranker_score', 0):.1f} | 판정: {judg}")

    # Summary metrics
    b_counts = pd.Series(base_scores).value_counts()
    r_counts = pd.Series(rerank_scores).value_counts()
    print("\n=== Summary Distribution ===")
    print("Baseline:", b_counts.to_dict())
    print("Reranked:", r_counts.to_dict())


if __name__ == "__main__":
    main()

