"""Analyze HR & General Affairs courses across the 7 SQLite databases."""
import sqlite3
import glob
import os
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

db_files = sorted(glob.glob("data/SQLite/*.db"))

# 핵심 키워드 목록
hr_keywords = [
    "인사", "채용", "노무", "근로기준", "인사평가", "평가보상", "급여", "연봉", "노사", "HR",
    "총무", "비품", "자산관리", "사무행정", "문서작성", "기획서", "보고서", "비즈니스 매너", "에티켓"
]

print("=== 7대 교육 플랫폼 SQLite DB 인사·총무 과정 추출 분석 ===\n")

platform_stats = []
all_hr_courses = []

for db_path in db_files:
    pname = os.path.basename(db_path).replace("_courses.db", "")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 테이블 확인
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses';")
    if not cur.fetchone():
        conn.close()
        continue
        
    df = pd.read_sql_query("SELECT * FROM courses", conn)
    conn.close()
    
    total_cnt = len(df)
    
    # 텍스트 컬럼 파악
    text_cols = [c for c in df.columns if c in ['title', 'description', 'category_name', 'category_depth1', 'category_depth2', 'category_depth3', 'category', 'subcategory', 'subcategory_name', 'keywords', 'tags']]
    
    # 키워드 검색
    pattern = "|".join(hr_keywords)
    mask = pd.Series(False, index=df.index)
    for c in text_cols:
        if c in df.columns:
            mask = mask | df[c].fillna("").astype(str).str.contains(pattern, case=False, regex=True)
            
    df_hr = df[mask].copy()
    hr_cnt = len(df_hr)
    
    print(f"[{pname.upper()}] 전체 {total_cnt}건 중 인사·총무 관련 {hr_cnt}건 ({hr_cnt/total_cnt*100:.1f}%)")
    platform_stats.append({
        "platform": pname,
        "db_file": os.path.basename(db_path),
        "total_courses": total_cnt,
        "hr_ga_courses": hr_cnt,
        "ratio": f"{hr_cnt/total_cnt*100:.1f}%",
        "sample_titles": df_hr['title'].head(3).tolist() if hr_cnt > 0 else []
    })
    
print("\n" + "="*80)
for ps in platform_stats:
    print(f"* {ps['platform'].upper()} ({ps['db_file']}): 전체 {ps['total_courses']}건 -> 인사·총무 {ps['hr_ga_courses']}건 ({ps['ratio']})")
    for st in ps['sample_titles']:
        print(f"    - {st}")
