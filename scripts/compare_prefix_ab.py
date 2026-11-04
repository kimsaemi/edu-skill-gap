"""
Condition A (query_prefix 없음) vs Condition B (query_prefix 있음) 상세 비교 스크립트
"""

import json
from collections import Counter
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

PATH_A = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"
PATH_B = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_prefix_B.csv"
EVAL_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"

df_a = pd.read_csv(PATH_A)
df_b = pd.read_csv(PATH_B)

eval_df = pd.read_csv(EVAL_PATH)
eval_tasks = sorted(eval_df["task"].unique())
eval_task_ids = sorted(eval_df["task_id"].unique())

print("=== 1. 기본 슬롯 및 다양성 비교 ===")
for name, df in [("Condition A (기준선)", df_a), ("Condition B (지시어 추가)", df_b)]:
    top3 = df[df["rank"] <= 3]
    counts_per_slot = top3.groupby(["task_id", "level"]).size()
    total_slots = 90 * 3  # 270
    present_slots = len(counts_per_slot)
    lt3_slots = (counts_per_slot < 3).sum() + (total_slots - present_slots)
    empty_slots = total_slots - present_slots
    distinct = top3["course_uid"].nunique()
    top1 = df[df["rank"] == 1]
    med_sem = top1["semantic_score"].median()
    min_sem = top1["semantic_score"].min()
    print(f"[{name}]")
    print(f"  - 총 추천 건수(Top3): {len(top3)}")
    print(f"  - 3개 미만 슬롯 수: {lt3_slots} (빈 슬롯: {empty_slots})")
    print(f"  - Top 3 서로 다른 강좌 수: {distinct}")
    print(f"  - 1위 의미 유사도: 중앙값 {med_sem:.2f}, 최솟값 {min_sem:.2f}")

print("\n=== 2. 가장 많이 추천된 상위 5개 강좌 및 출현 횟수 ===")
def top5_reused(df):
    top3 = df[df["rank"] <= 3]
    title_map = dict(zip(df["course_uid"], df["title"]))
    counts = Counter(top3["course_uid"])
    res = []
    for uid, c in counts.most_common(5):
        res.append((title_map[uid], c))
    return res

print("[Condition A 상위 5개]")
for t, c in top5_reused(df_a):
    print(f"  - {c}회: {t}")

print("[Condition B 상위 5개]")
for t, c in top5_reused(df_b):
    print(f"  - {c}회: {t}")

print("\n=== 3. 의심/비인사 과정 출현 횟수 (전체 Top 3 기준) ===")
def check_suspicious(df):
    top3 = df[df["rank"] <= 3]
    suspicious_patterns = [
        ("구매 데이터분석", top3["title"].str.contains("구매.*데이터분석|데이터분석.*구매", regex=True)),
        ("SAP/ERP 회계", top3["title"].str.contains("SAP|S/4HANA|원가관리|ERP.*회계", regex=True)),
        ("QA 상담품질", top3["title"].str.contains("상담품질|QA.*품질", regex=True)),
        ("순수 전산세무회계", top3["title"].str.contains("전산세무|전산회계", regex=True) & ~top3["title"].str.contains("인사|급여|노무|4대보험|연말정산", regex=True)),
    ]
    return {label: int(cond.sum()) for label, cond in suspicious_patterns}

print("Condition A:", check_suspicious(df_a))
print("Condition B:", check_suspicious(df_b))

print("\n=== 4. 10개 사람 평가 업무의 Top 3 비교 ===")
top3_a = df_a[df_a["rank"] <= 3]
top3_b = df_b[df_b["rank"] <= 3]

import sys
sys.stdout.reconfigure(encoding='utf-8')

eval_task_slots = eval_df[["task_id", "task", "level"]].drop_duplicates().to_dict("records")

for slot in sorted(eval_task_slots, key=lambda x: x["task_id"]):
    tid = slot["task_id"]
    tname = slot["task"]
    level = slot["level"]
    sub_a = top3_a[(top3_a["task_id"] == tid) & (top3_a["level"] == level)]
    sub_b = top3_b[(top3_b["task_id"] == tid) & (top3_b["level"] == level)]
    titles_a = list(sub_a["title"])
    titles_b = list(sub_b["title"])
    same = (titles_a == titles_b)
    print(f"\n[Task: {tname} ({tid}) - {level}] {'(일치)' if same else '(변경됨)'}")
    if not same:
        print(f"  - A (지시어 없음):")
        for i, t in enumerate(titles_a, 1):
            print(f"      {i}. {t}")
        print(f"  - B (지시어 추가):")
        for i, t in enumerate(titles_b, 1):
            print(f"      {i}. {t}")
    else:
        for i, t in enumerate(titles_a, 1):
            print(f"      {i}. {t}")
