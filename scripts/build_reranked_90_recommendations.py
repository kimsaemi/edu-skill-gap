# -*- coding: utf-8 -*-
"""
기존 90개 업무 대상 2단계 Cross-Encoder 리랭킹 추천 생성 스크립트
- 입력: data/hr/output/recommendation/task_course_recommendations_90.csv
- 모델: Dongjin-kr/ko-reranker (Cross-Encoder)
- 출력: data/hr/output/recommendation/task_course_recommendations_90_reranked.csv
"""

import sys
import time
from pathlib import Path
import json
import numpy as np
import pandas as pd

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


def main():
    print("=== Building Reranked Recommendations for Legacy 90 Tasks ===")
    df_rec = pd.read_csv(REC_90_PATH)
    print(f"Loaded {len(df_rec)} candidate rows from {REC_90_PATH.name}")

    # Exclude any off-topic courses
    if EXCL_PATH.exists():
        excl_df = pd.read_csv(EXCL_PATH, dtype=str)
        excl_uids = set(excl_df["course_uid"])
        before_cnt = len(df_rec)
        df_rec = df_rec[~df_rec["course_uid"].astype(str).isin(excl_uids)].copy()
        print(f"Filtered out {before_cnt - len(df_rec)} off-topic courses. Remaining: {len(df_rec)} rows")

    # Load task details
    tasks_meta = {}
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)
            tasks_list = cat.get("tasks", cat) if isinstance(cat, dict) else cat
            for t in tasks_list:
                tasks_meta[t["task_id"]] = t

    # Load course metadata from career_platform
    df_courses = cp.courses().set_index("course_uid")
    reranker = get_shared_reranker()

    print("Scoring candidates with Cross-Encoder...")
    t0 = time.time()

    # Prepare query and doc pairs
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

    # Batch inference
    batch_size = 32
    raw_scores = reranker.model.predict(pairs, batch_size=batch_size, show_progress_bar=True)
    
    # Sigmoid to 0.0 ~ 1.0 if not already probabilities
    if len(raw_scores.shape) == 1:
        if np.min(raw_scores) < 0 or np.max(raw_scores) > 1:
            probs = 1.0 / (1.0 + np.exp(-raw_scores))
        else:
            probs = raw_scores
    else:
        probs = torch.softmax(torch.tensor(raw_scores), dim=-1)[:, 1].numpy()

    df_rec["reranker_score"] = np.round(probs * 100.0, 1)

    # Compute reranked final score: 60% Cross-Encoder + 40% Stage-1
    alpha = 0.6
    stage1_score = df_rec["final_score"].astype(float)
    ce_score = df_rec["reranker_score"]
    df_rec["reranked_final_score"] = np.round(alpha * ce_score + (1.0 - alpha) * stage1_score, 1)

    # Keep Top 3 per (task_id, level)
    out_rows = []
    groups = df_rec.groupby(["task_id", "level"], sort=False)
    
    dropped_noise_count = 0
    for (t_id, lvl), grp in groups:
        sorted_grp = grp.sort_values(by="reranked_final_score", ascending=False)
        # Prioritize courses with reranker_score >= 0.1, up to Top 3
        valid = sorted_grp[sorted_grp["reranker_score"] >= 0.1]
        if len(valid) < 3:
            valid = sorted_grp.head(3)
        else:
            valid = valid.head(3)
        
        dropped_noise_count += len(grp) - len(valid)
        valid = valid.copy()
        valid["rank"] = range(1, len(valid) + 1)
        out_rows.append(valid)

    df_result = pd.concat(out_rows, ignore_index=True)
    elapsed = time.time() - t0
    print(f"Completed in {elapsed:.2f}s ({len(df_rec)} pairs). Dropped noise candidates: {dropped_noise_count}")
    print(f"Final reranked rows: {len(df_result)}")

    df_result.to_csv(OUT_90_RERANKED_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_90_RERANKED_PATH}")


if __name__ == "__main__":
    main()
