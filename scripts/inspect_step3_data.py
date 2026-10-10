"""Step 3 detailed analysis and verification script."""
import json
import os
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(".")
RAW_DIR = BASE_DIR / "data" / "hr" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"

def run_analysis():
    df_courses = pd.read_csv(PROCESSED_DIR / "courses.csv", dtype=str)
    
    print("=" * 80)
    print("1. NCS 코드별 교육과정 분포 및 내용 분석")
    print("=" * 80)
    for code, group in sorted(df_courses.groupby("ncs_classification_code")):
        print(f"\n[NCS Code: {code}] (총 {len(group)}건)")
        for _, r in group.iterrows():
            print(f"  - [{r['source_api']}] {r['instance_key']} | {r['course_name_std']} | {r['institution_name_std']} | Job: {r['job_id']}({r['job_clarity']})")
            if pd.notna(r["edu_goal_text"]) and r["edu_goal_text"] != "":
                print(f"    * 목표: {str(r['edu_goal_text'])[:60]}...")
            if pd.notna(r["edu_content_text"]) and r["edu_content_text"] != "":
                print(f"    * 내용: {str(r['edu_content_text'])[:60]}...")

    print("\n" + "=" * 80)
    print("2. 직무 및 역량 매핑 관계 분석")
    print("=" * 80)
    df_jobs = pd.read_csv(PROCESSED_DIR / "jobs.csv", dtype=str)
    df_comp = pd.read_csv(PROCESSED_DIR / "competencies.csv", dtype=str)
    df_job_comp = pd.read_csv(PROCESSED_DIR / "job_competencies.csv", dtype=str)
    df_course_comp = pd.read_csv(PROCESSED_DIR / "course_competencies.csv", dtype=str)

    print("\n[jobs.csv]")
    print(df_jobs[["job_id", "job_name", "ncs_code_prefix", "description"]])

    print("\n[competencies.csv]")
    print(df_comp[["competency_id", "ncs_unit_code", "competency_name", "ksa_type"]])

    print("\n[job_competencies.csv]")
    print(df_job_comp)

    print("\n[course_competencies.csv 통계]")
    print(df_course_comp["competency_id"].value_counts())
    print("\n매핑 유형별:")
    print(df_course_comp["mapping_type"].value_counts())

if __name__ == "__main__":
    run_analysis()
