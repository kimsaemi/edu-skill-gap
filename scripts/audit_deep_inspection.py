"""
정밀 전수 조사:
1. 7개 교육기관별 원본 DB 전체 컬럼 및 후기/평점 컬럼 확인
2. KPC의 review_count 상세 및 후기 원문 유무 확인
3. Inflearn 리뷰 124건의 8,645건 통합 코퍼스 연결 여부 확인
4. 통합 Parquet 전체 컬럼 목록 전수 조사
"""

import sys
import os
import sqlite3
import json
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"d:\26_강의자료\프로젝트2_교육"

# 1. 원본 7개 교육 데이터 출처의 DB 점검
DB_DIRS = [
    os.path.join(BASE_DIR, "data", "courses"),
    os.path.join(BASE_DIR, "data", "SQLite")
]

print("=" * 80)
print("1. 교육 데이터 출처별 원본 DB 테이블 및 컬럼 전수 점검")
print("=" * 80)

for d in DB_DIRS:
    print(f"\n[Directory: {os.path.relpath(d, BASE_DIR)}]")
    for db_f in sorted(os.listdir(d)):
        if not db_f.endswith('.db'):
            continue
        p = os.path.join(d, db_f)
        conn = sqlite3.connect(p)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in c.fetchall()]
        print(f"\n  📁 DB: {db_f} (Size: {os.path.getsize(p):,} bytes)")
        for tbl in tables:
            c.execute(f"PRAGMA table_info('{tbl}')")
            cols = [col[1] for col in c.fetchall()]
            c.execute(f"SELECT COUNT(*) FROM '{tbl}'")
            cnt = c.fetchone()[0]
            print(f"    - Table: {tbl} ({cnt:,} rows)")
            print(f"      Columns ({len(cols)}): {cols}")
        conn.close()

# 2. KPC의 review_count 및 후기 관련 데이터 상세 점검
print("\n" + "=" * 80)
print("2. KPC courses.db의 review_count 정밀 점검")
print("=" * 80)
kpc_db = os.path.join(BASE_DIR, "data", "courses", "kpc_courses.db")
if os.path.exists(kpc_db):
    conn = sqlite3.connect(kpc_db)
    df_kpc = pd.read_sql("SELECT * FROM courses", conn)
    conn.close()
    print(f"KPC total rows: {len(df_kpc)}")
    print("KPC columns:", df_kpc.columns.tolist())
    if "review_count" in df_kpc.columns:
        rc = pd.to_numeric(df_kpc["review_count"], errors="coerce")
        print("review_count non-null:", rc.notna().sum())
        print("review_count > 0 건수:", (rc > 0).sum())
        print("review_count max:", rc.max(), "min:", rc.min(), "mean:", rc.mean())
        print("review_count 상위 5개 과정:")
        top_rc = df_kpc.sort_values(by="review_count", ascending=False).head(5)
        for _, r in top_rc.iterrows():
            print(f"  * [{r.get('course_id', r.get('id', ''))}] {r.get('course_name', r.get('title', ''))} -> review_count: {r.get('review_count')}")
    # 혹시 후기 텍스트가 들어있는 컬럼이 있는지 확인
    for col in df_kpc.columns:
        sample_str = str(df_kpc[col].dropna().iloc[0]) if not df_kpc[col].dropna().empty else ""
        if any(w in col.lower() for w in ['review', 'comment', 'feedback', 'eval', 'score', 'star']):
            print(f"  Column '{col}' found! Samples: {df_kpc[col].dropna().head(3).tolist()}")

# 3. 인프런(Inflearn) 리뷰 데이터와 8,645건 코퍼스 연결성 점검
print("\n" + "=" * 80)
print("3. Inflearn 리뷰 124건의 8,645건 코퍼스 연결 여부 점검")
print("=" * 80)
inf_csv = os.path.join(BASE_DIR, "data", "processed", "inflearn_course_reviews.csv")
p_cleaned = os.path.join(BASE_DIR, "data", "hr", "processed", "education_courses_search_cleaned.parquet")
p_integ = os.path.join(BASE_DIR, "data", "hr", "processed", "education_courses_integrated.parquet")

df_inf = pd.read_csv(inf_csv)
df_clean = pd.read_parquet(p_cleaned)
df_integ = pd.read_parquet(p_integ)

print(f"Inflearn reviews total: {len(df_inf)} reviews")
print("Inflearn CSV columns:", df_inf.columns.tolist())
print(f"Unique courses in Inflearn reviews: {df_inf['course_id'].nunique()} courses")
print("Inflearn course titles sample:")
for t in df_inf['course_title'].unique()[:5]:
    print("  *", t)

# 8,645건 코퍼스에 인프런 강의가 포함되어 있는지 검사
print("\n8,645건 코퍼스(df_clean) 내 플랫폼 목록:")
print(df_clean['provider'].value_counts())

inf_in_clean = df_clean[df_clean['provider'].str.contains('인프런|inflearn', case=False, na=False)]
print(f"\n8,645건 코퍼스 내 '인프런' 제공 강의 수: {len(inf_in_clean)}건")

# 제목 매칭 여부
inf_titles = set(df_inf['course_title'].unique())
matched_titles = df_clean[df_clean['title'].isin(inf_titles)]
print(f"8,645건 코퍼스 내 인프런 리뷰 강의 제목과 정확히 일치하는 강의 수: {len(matched_titles)}건")

# 4. 8,645건 통합 Parquet 전체 컬럼 목록 전수 조사
print("\n" + "=" * 80)
print("4. education_courses_integrated.parquet 전체 컬럼 전수 점검")
print("=" * 80)
print(f"Total columns ({len(df_integ.columns)}):")
for idx, col in enumerate(df_integ.columns):
    val_cnt = df_integ[col].notna().sum()
    print(f"  [{idx+1:02d}] {col} (dtype: {df_integ[col].dtype}, non-null: {val_cnt:,} / {len(df_integ):,})")

print("\n" + "=" * 80)
print("5. education_courses_search_cleaned.parquet 전체 컬럼 전수 점검")
print("=" * 80)
print(f"Total columns ({len(df_clean.columns)}):")
for idx, col in enumerate(df_clean.columns):
    val_cnt = df_clean[col].notna().sum()
    print(f"  [{idx+1:02d}] {col} (dtype: {df_clean[col].dtype}, non-null: {val_cnt:,} / {len(df_clean):,})")

