"""Pre-check all files and paths for STEP 3 Extension."""
import os
import glob
from pathlib import Path
import pandas as pd

files_to_verify = [
    "data/hr/raw/kmbc_courses_raw.json",
    "data/hr/raw/employer_courses_raw.json",
    "data/hr/raw/ncs_courses_raw.json",
    "data/hr/raw/round2/kmbc_round2_raw.json",
    "data/hr/raw/round2/employer_round2_raw.json",
    "data/hr/processed/courses.csv",
    "data/hr/processed/hr_courses_eda.csv",
    "data/hr/processed/hr_courses_eda_v2.csv",
    "data/hr/processed/hr_mapping_verified.csv",
    "data/hr/processed/hr_mapping_verified_v2.csv",
    "data/hr/output/reports/final_quality_verification_summary.md",
    "data/hr/output/reports/eda_round1_vs_round2_comparison.csv",
    "data/SQLite/fastcampus_courses.db",
    "data/SQLite/gseek_courses.db",
    "data/SQLite/hunet_courses.db",
    "data/SQLite/kfo_courses.db",
    "data/SQLite/kma_courses.db",
    "data/SQLite/kpc_courses.db",
    "data/SQLite/multicampus_courses.db",
    "data/hr/processed/sqlite_hr_courses_integrated.csv",
    "data/SQLite/sqlite_database_catalog.json",
    "data/SQLite/README.md",
    "scripts/register_sqlite_courses.py"
]

print("=== [Task 3] 파일 실재 점검 결과 ===")
for f in files_to_verify:
    p = Path(f)
    exists = p.exists()
    if exists:
        if p.suffix == ".csv":
            df = pd.read_csv(p, dtype=str)
            print(f"[OK] {f} | 크기: {p.stat().st_size:,} bytes | 행수: {len(df)}행, 열수: {len(df.columns)}열")
        elif p.suffix == ".db":
            print(f"[OK] {f} | 크기: {p.stat().st_size:,} bytes (SQLite DB)")
        else:
            print(f"[OK] {f} | 크기: {p.stat().st_size:,} bytes")
    else:
        print(f"[MISSING] {f}")
