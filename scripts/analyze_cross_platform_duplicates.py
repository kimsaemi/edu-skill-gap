import pandas as pd
import numpy as np
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

df_clean = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')
df_cl = pd.read_parquet('data/hr/output/recommendation/course_clusters_8645.parquet')

# Merge
df = df_clean.merge(df_cl[['course_uid', 'cluster_id', 'topic_label', 'canonical_platform']], on='course_uid', how='left')

def normalize_title(t):
    t = str(t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t

df['norm_title'] = df['title'].apply(normalize_title)

# Cross-platform duplicates
title_prov_counts = df.groupby('norm_title')['canonical_platform'].nunique()
cross_prov_titles = title_prov_counts[title_prov_counts > 1]

print(f"전체 코퍼스: {len(df):,}건")
print(f"정규화된 고유 강좌명: {df['norm_title'].nunique():,}개")
print(f"2개 이상의 서로 다른 플랫폼에 걸쳐 등록된 동일/유사 제목 수: {len(cross_prov_titles):,}개")

cross_df = df[df['norm_title'].isin(cross_prov_titles.index)]
top_cross = cross_df['norm_title'].value_counts().head(15)

print("\n=== 상위 15대 크로스 플랫폼 중복 의심 강좌명 ===")
for title, cnt in top_cross.items():
    sub = cross_df[cross_df['norm_title'] == title]
    provs = sub['canonical_platform'].unique().tolist()
    prices = sub['price'].dropna().tolist()
    print(f"- '{title}': 총 {cnt}건 | 제공기관: {provs} | 가격 샘플: {prices[:4]}")

# Case 1: GSEEK vs 휴넷 동일 강좌 확인: e.g. "월급이 낭비되지 않도록, 알기 쉬운 세금 상식"
print("\n=== 케이스 1: '알기 쉬운 세금 상식' 강좌 비교 ===")
tax_courses = df[df['norm_title'].str.contains('세금 상식', na=False)]
print(tax_courses[['course_uid', 'canonical_platform', 'title', 'price', 'education_type']])

# Check intro and curriculum similarity for tax_courses
for idx, r in tax_courses.iterrows():
    print(f"\n[{r['canonical_platform']}] {r['title']} (가격: {r['price']}, 시간: {r['duration_hours']})")
    print(f"  Intro: {str(r['clean_intro'])[:100]}...")
    print(f"  Curri: {str(r['clean_curriculum'])[:100]}...")
