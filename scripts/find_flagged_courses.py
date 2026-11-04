# -*- coding: utf-8 -*-
"""
리랭커 추천 결과(task_course_recommendations_90_reranked.csv) 내의
SAP, QA 상담품질, 전산회계 등 제외/점검 대상 키워드 과정 출현 현황 점검 스크립트
"""
import sys
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
REC_RERANK = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"

df = pd.read_csv(REC_RERANK)

print("=== Flagged Courses in 90_reranked.csv ===")
sap = df[df["title"].str.contains("S/4HANA|SAP", case=False, na=False)]
print(f"\n1. SAP S/4HANA CO (Total: {len(sap)})")
for _, r in sap.iterrows():
    print(f"  [{r['task_id']} | {r['level']} | Rank {r['rank']}] CE: {r['reranker_score']} | {r['task_name']} -> {r['title']}")

qa = df[df["title"].str.contains("QA 전문가|상담품질", case=False, na=False)]
print(f"\n2. QA 상담품질 (Total: {len(qa)})")
for _, r in qa.iterrows():
    print(f"  [{r['task_id']} | {r['level']} | Rank {r['rank']}] CE: {r['reranker_score']} | {r['task_name']} -> {r['title']}")

acc = df[df["title"].str.contains("전산회계", case=False, na=False)]
print(f"\n3. 전산회계 (Total: {len(acc)})")
for _, r in acc.iterrows():
    print(f"  [{r['task_id']} | {r['level']} | Rank {r['rank']}] CE: {r['reranker_score']} | {r['task_name']} -> {r['title']}")

