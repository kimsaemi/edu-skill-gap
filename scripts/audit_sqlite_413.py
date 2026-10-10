"""Audit the 413 extracted SQLite courses in detail."""
import sys
import pandas as pd
import json

sys.stdout.reconfigure(encoding="utf-8")

df = pd.read_csv("data/hr/processed/sqlite_hr_courses_integrated.csv", dtype=str)

print(f"Total courses: {len(df)}")
for p in df["platform"].unique():
    sub = df[df["platform"] == p]
    print(f"\n=== Platform: {p} ({len(sub)} courses) ===")
    for idx, r in sub.head(10).iterrows():
        title = r['course_name'].replace("\n", " ").replace("\r", " ").replace("\u2028", " ")
        print(f"  [{r['course_id']}] {title} | Cat: {r['category']} | Fam: {r['job_family']}")
