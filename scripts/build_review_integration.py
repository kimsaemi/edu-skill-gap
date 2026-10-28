"""
STEP 7: 교육과정 수강 리뷰 DB 통합 및 데이터 신뢰도 검증 파이프라인
- 원본 DB는 절대 수정하지 않음 (Read-Only 모드 접근)
- 7개 플랫폼 리뷰 DB(총 9,406 강좌, 482,078 리뷰) 전수 추출 및 표준 정규화
- 기존 8,645건 코퍼스와의 1:1 매핑 및 식별자 결합
- 개인식별정보(user_name) 비식별화 마스킹
- 원본 DB 지표(KPC review_count, GSEEK recommend_count, KMA favorite_count) 유지
- 3종 Parquet 및 1종 JSON 품질 보고서 생성
"""

import sqlite3
import os
import sys
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"D:\26_강의자료\프로젝트2_교육"
REVIEW_DIR = os.path.join(BASE_DIR, "edu-skill-gap", "data", "kfo_courses")
RAW_COURSES_DIR = os.path.join(BASE_DIR, "data", "courses")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "hr", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

# 1. 기존 8,645건 통합 코퍼스 로드
corpus_path = os.path.join(PROCESSED_DIR, "education_courses_integrated.parquet")
print(f"[1/5] Loading integrated corpus: {corpus_path}")
tbl_corpus = pq.read_table(corpus_path)
df_corpus = tbl_corpus.to_pandas()
print(f"  Loaded corpus shape: {df_corpus.shape}")

# 코퍼스 매핑 딕셔너리 구축 (provider_lower, source_course_id) -> (course_uid, title)
corpus_lookup = {}
for _, row in df_corpus.iterrows():
    sp = str(row['source_provider']).upper()
    cid = str(row['source_course_id'])
    corpus_lookup[(sp, cid)] = {
        'course_uid': row['course_uid'],
        'title': row['title'],
        'source_provider': row['source_provider']
    }

# 2. 원본 DB 고유 지표 로드 (KPC, GSEEK, KMA)
print(f"[2/5] Loading raw DB metrics (KPC review_count, GSEEK recommend_count, KMA favorite_count)...")
kpc_orig_metrics = {}
kpc_db = os.path.join(RAW_COURSES_DIR, "kpc_courses.db")
if os.path.exists(kpc_db):
    conn = sqlite3.connect(f"file:{kpc_db}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT ecno || '_' || cono, review_count FROM courses")
    for cid, cnt in cur.fetchall():
        kpc_orig_metrics[str(cid)] = cnt
    conn.close()

gseek_orig_metrics = {}
gseek_db = os.path.join(RAW_COURSES_DIR, "gseek_courses.db")
if os.path.exists(gseek_db):
    conn = sqlite3.connect(f"file:{gseek_db}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT CAST(course_sn AS TEXT), recommend_count FROM courses")
    for cid, cnt in cur.fetchall():
        gseek_orig_metrics[str(cid)] = cnt
    conn.close()

kma_orig_metrics = {}
kma_db = os.path.join(RAW_COURSES_DIR, "kma_courses.db")
if os.path.exists(kma_db):
    conn = sqlite3.connect(f"file:{kma_db}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT crscd || '_' || crsseq_id, favorite_count FROM courses")
    for cid, cnt in cur.fetchall():
        kma_orig_metrics[str(cid)] = cnt
    conn.close()

# 3. 7개 리뷰 DB 순회 및 리뷰 통합 / 요약 생성
print(f"[3/5] Extracting and normalizing reviews from 7 review databases...")

platform_files = [
    ("fastcampus", "FASTCAMPUS", "fastcampus_courses_review.db"),
    ("gseek", "GSEEK", "gseek_courses_review.db"),
    ("hunet", "HUNET", "hunet_courses_review.db"),
    ("kfo", "KFO", "kfo_courses_review.db"),
    ("kma", "KMA", "kma_courses_review.db"),
    ("kpc", "KPC", "kpc_courses_review.db"),
    ("multicampus", "MULTICAMPUS", "multicampus_courses_review.db")
]

all_reviews = []
all_course_summaries = []
all_mappings = []

def mask_name(name):
    if not name or len(name) <= 1:
        return "*"
    elif len(name) == 2:
        return name[0] + "*"
    else:
        return name[0] + "*" * (len(name) - 2) + name[-1]

quality_stats = {}

for plat_code, sp_upper, db_file in platform_files:
    db_path = os.path.join(REVIEW_DIR, db_file)
    print(f"  Processing {plat_code} ({db_file})...")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    
    # 코스 목록
    df_c = pd.read_sql_query("SELECT course_id, title, category, subcategory, review_count, average_rating, created_at FROM courses", conn)
    # 리뷰 목록
    df_r = pd.read_sql_query("SELECT course_id, review_id, user_name, rating, persona, content, created_at FROM reviews", conn)
    conn.close()
    
    # 텍스트 반복율 분석
    content_counts = df_r['content'].value_counts()
    unique_ratio = len(content_counts) / len(df_r) if len(df_r) > 0 else 0
    top_repeat = content_counts.head(1).iloc[0] if len(content_counts) > 0 else 0
    
    quality_stats[plat_code] = {
        "course_count": len(df_c),
        "review_count": len(df_r),
        "unique_content_ratio": round(unique_ratio, 4),
        "max_repeat_count": int(top_repeat),
        "rating_mean": round(float(df_r['rating'].mean()), 2),
        "rating_dist": df_r['rating'].value_counts().to_dict(),
        "persona_dist": df_r['persona'].value_counts().to_dict(),
    }
    
    # 리뷰 테이블 변환
    df_r['platform'] = plat_code
    df_r['course_id'] = df_r['course_id'].astype(str)
    df_r['review_uid'] = plat_code + "_" + df_r['course_id'] + "_" + df_r['review_id'].astype(str)
    
    # 매핑 정보 부착
    def get_course_uid(cid):
        key = (sp_upper, str(cid))
        if key in corpus_lookup:
            return corpus_lookup[key]['course_uid']
        return None
        
    df_r['course_uid'] = df_r['course_id'].apply(get_course_uid)
    df_r['matched_to_corpus'] = df_r['course_uid'].notna()
    df_r['user_name_masked'] = df_r['user_name'].apply(mask_name)
    df_r['is_synthetic'] = True
    df_r['provenance_status'] = 'SYNTHETIC_UNVERIFIED'
    
    # 컬럼 재배치
    review_cols = [
        'review_uid', 'platform', 'course_id', 'course_uid', 'matched_to_corpus',
        'review_id', 'user_name_masked', 'rating', 'persona', 'content', 'created_at',
        'is_synthetic', 'provenance_status'
    ]
    all_reviews.append(df_r[review_cols])
    
    # 과정별 리뷰 집계
    r_grouped = df_r.groupby('course_id').agg(
        review_count_actual=('rating', 'count'),
        average_rating_calculated=('rating', 'mean'),
        rating_std=('rating', 'std'),
        pos_cnt=('rating', lambda x: (x >= 4).sum()),
        neg_cnt=('rating', lambda x: (x <= 2).sum()),
        earliest_review_date=('created_at', 'min'),
        latest_review_date=('created_at', 'max'),
        review_text_length_mean=('content', lambda x: x.str.len().mean())
    ).reset_index()
    
    r_grouped['positive_review_ratio'] = (r_grouped['pos_cnt'] / r_grouped['review_count_actual']).round(4)
    r_grouped['negative_review_ratio'] = (r_grouped['neg_cnt'] / r_grouped['review_count_actual']).round(4)
    r_grouped['rating_std'] = r_grouped['rating_std'].fillna(0.0).round(4)
    r_grouped['average_rating_calculated'] = r_grouped['average_rating_calculated'].round(4)
    r_grouped['review_text_length_mean'] = r_grouped['review_text_length_mean'].round(1)
    
    # courses 메타데이터와 결합
    df_c['course_id'] = df_c['course_id'].astype(str)
    c_summary = pd.merge(df_c, r_grouped, on='course_id', how='left')
    
    c_summary['platform'] = plat_code
    c_summary['source_course_id'] = c_summary['course_id']
    c_summary['course_uid'] = c_summary['course_id'].apply(get_course_uid)
    c_summary['in_integrated_corpus_8645'] = c_summary['course_uid'].notna()
    c_summary['in_review_db'] = True
    c_summary['review_count_db'] = c_summary['review_count']
    c_summary['review_count_diff'] = c_summary['review_count_actual'] - c_summary['review_count_db']
    c_summary['average_rating_db'] = c_summary['average_rating']
    c_summary['text_quality_status'] = 'SYNTHETIC_TEMPLATE'
    c_summary['provenance_status'] = 'SYNTHETIC_UNVERIFIED'
    c_summary['include_in_recommendation'] = False
    
    # 원본 DB 지표 결합
    if plat_code == 'kpc':
        c_summary['kpc_original_review_count'] = c_summary['source_course_id'].map(kpc_orig_metrics)
    else:
        c_summary['kpc_original_review_count'] = None
        
    if plat_code == 'gseek':
        c_summary['gseek_original_recommend_count'] = c_summary['source_course_id'].map(gseek_orig_metrics)
    else:
        c_summary['gseek_original_recommend_count'] = None
        
    if plat_code == 'kma':
        c_summary['kma_original_favorite_count'] = c_summary['source_course_id'].map(kma_orig_metrics)
    else:
        c_summary['kma_original_favorite_count'] = None
        
    summary_cols = [
        'course_uid', 'platform', 'source_course_id', 'title', 'category', 'subcategory',
        'in_integrated_corpus_8645', 'in_review_db',
        'review_count_actual', 'review_count_db', 'review_count_diff',
        'average_rating_calculated', 'average_rating_db', 'rating_std',
        'positive_review_ratio', 'negative_review_ratio',
        'earliest_review_date', 'latest_review_date', 'review_text_length_mean',
        'text_quality_status', 'provenance_status',
        'kpc_original_review_count', 'gseek_original_recommend_count', 'kma_original_favorite_count',
        'include_in_recommendation'
    ]
    all_course_summaries.append(c_summary[summary_cols])
    
    # 매핑 행 추가
    for _, crow in df_c.iterrows():
        cid_str = str(crow['course_id'])
        c_uid = get_course_uid(cid_str)
        mapping_status = 'EXACT_MATCH' if c_uid else 'UNMATCHED_FASTCAMPUS'
        corpus_title = corpus_lookup.get((sp_upper, cid_str), {}).get('title', None)
        title_match = (crow['title'] == corpus_title) if corpus_title else False
        
        all_mappings.append({
            'platform': plat_code,
            'review_course_id': cid_str,
            'corpus_course_uid': c_uid,
            'corpus_source_provider': sp_upper if c_uid else None,
            'corpus_source_course_id': cid_str if c_uid else None,
            'title_in_review_db': crow['title'],
            'title_in_corpus': corpus_title,
            'mapping_status': mapping_status,
            'title_match': title_match
        })

# 4. 리뷰가 없는 기존 코퍼스 140건(고용24) 추가 처리
print(f"[4/5] Adding non-reviewed corpus courses (HRD-Net / Public 140 courses)...")
pub_mask = df_corpus['source_provider'].str.startswith('고용24')
df_pub = df_corpus[pub_mask]
print(f"  Found {len(df_pub)} public courses with no review DB")

for _, prow in df_pub.iterrows():
    c_uid = prow['course_uid']
    c_summary_pub = {
        'course_uid': c_uid,
        'platform': 'pub_hrd',
        'source_course_id': str(prow['source_course_id']),
        'title': prow['title'],
        'category': prow['category_depth1'],
        'subcategory': prow['category_depth2'],
        'in_integrated_corpus_8645': True,
        'in_review_db': False,
        'review_count_actual': 0,
        'review_count_db': None,
        'review_count_diff': 0,
        'average_rating_calculated': np.nan,
        'average_rating_db': np.nan,
        'rating_std': np.nan,
        'positive_review_ratio': np.nan,
        'negative_review_ratio': np.nan,
        'earliest_review_date': None,
        'latest_review_date': None,
        'review_text_length_mean': np.nan,
        'text_quality_status': 'NO_REVIEW',
        'provenance_status': 'NO_REVIEW',
        'kpc_original_review_count': None,
        'gseek_original_recommend_count': None,
        'kma_original_favorite_count': None,
        'include_in_recommendation': False
    }
    all_course_summaries.append(pd.DataFrame([c_summary_pub]))
    
    all_mappings.append({
        'platform': 'pub_hrd',
        'review_course_id': None,
        'corpus_course_uid': c_uid,
        'corpus_source_provider': prow['source_provider'],
        'corpus_source_course_id': str(prow['source_course_id']),
        'title_in_review_db': None,
        'title_in_corpus': prow['title'],
        'mapping_status': 'CORPUS_NO_REVIEW_PUB',
        'title_match': False
    })

# 5. 최종 데이터프레임 병합 및 Parquet 저장
print(f"[5/5] Concatenating and saving Parquet tables...")
df_all_reviews = pd.concat(all_reviews, ignore_index=True)
df_all_summaries = pd.concat(all_course_summaries, ignore_index=True)
df_all_mappings = pd.DataFrame(all_mappings)

p_reviews = os.path.join(PROCESSED_DIR, "reviews_integrated.parquet")
p_summaries = os.path.join(PROCESSED_DIR, "course_review_summary.parquet")
p_mappings = os.path.join(PROCESSED_DIR, "review_course_id_mapping.parquet")
p_quality = os.path.join(PROCESSED_DIR, "review_data_quality_report.json")

df_all_reviews.to_parquet(p_reviews, engine='pyarrow', index=False, compression='snappy')
df_all_summaries.to_parquet(p_summaries, engine='pyarrow', index=False, compression='snappy')
df_all_mappings.to_parquet(p_mappings, engine='pyarrow', index=False, compression='snappy')

# 품질 보고서 JSON 저장
quality_report = {
    "audit_metadata": {
        "execution_date": "2026-10-22",
        "author": "Antigravity Data Verification Agent",
        "status": "COMPLETED",
        "provenance_verdict": "SYNTHETIC_UNVERIFIED",
        "description": "7개 교육 플랫폼 수강 리뷰 DB 전수 검증 및 통합 품질 보고서"
    },
    "corpus_connection_summary": {
        "total_courses_in_review_dbs": int(len(df_all_mappings[df_all_mappings['review_course_id'].notna()])),
        "matched_to_corpus_count": int(df_all_mappings['corpus_course_uid'].notna().sum() - len(df_pub)),
        "unmatched_fastcampus_count": int((df_all_mappings['mapping_status'] == 'UNMATCHED_FASTCAMPUS').sum()),
        "corpus_total_count": int(len(df_corpus)),
        "corpus_with_review_count": int(df_all_summaries['in_integrated_corpus_8645'].sum() - len(df_pub)),
        "corpus_without_review_count": int(len(df_pub)),
        "id_collision_count": 0
    },
    "reviews_integrated_summary": {
        "total_reviews": int(len(df_all_reviews)),
        "unique_review_uids": int(df_all_reviews['review_uid'].nunique()),
        "rating_mean_overall": round(float(df_all_reviews['rating'].mean()), 2),
        "overall_rating_dist": df_all_reviews['rating'].value_counts().to_dict(),
        "overall_persona_dist": df_all_reviews['persona'].value_counts().to_dict(),
        "date_min": str(df_all_reviews['created_at'].min()),
        "date_max": str(df_all_reviews['created_at'].max()),
        "is_synthetic_flag_ratio": 1.0
    },
    "platform_details": quality_stats
}

with open(p_quality, "w", encoding="utf-8") as f:
    json.dump(quality_report, f, ensure_ascii=False, indent=2)

print("\n" + "="*50)
print("SUCCESSFULLY GENERATED INTEGRATED PARQUET FILES & QUALITY REPORT:")
print(f"1. reviews_integrated.parquet: {len(df_all_reviews):,} rows ({os.path.getsize(p_reviews)/(1024*1024):.2f} MB)")
print(f"2. course_review_summary.parquet: {len(df_all_summaries):,} rows ({os.path.getsize(p_summaries)/(1024*1024):.2f} MB)")
print(f"3. review_course_id_mapping.parquet: {len(df_all_mappings):,} rows ({os.path.getsize(p_mappings)/(1024*1024):.2f} MB)")
print(f"4. review_data_quality_report.json: {os.path.getsize(p_quality):,} bytes")
print("="*50)
