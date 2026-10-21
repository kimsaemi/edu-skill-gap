"""
Step 6 사전 점검 스크립트:
1. 대상 6개 파일의 실제 경로, 크기, 컬럼 스키마 점검
2. course_uid 기준 각 데이터셋 간 고유 식별자 일치 및 정렬 여부
3. search_models_cache.pkl 내용 점검 (기존 모델 중복 여부 확인)
4. 역량 라벨(course_competency_long, matrix_course_competency_wide) 내 8개 KSA 역량 분포, 매핑 방식(VERIFIED/WEAK, 오매핑 의심 109건) 점검
5. 중복 강좌 / 개설 회차(session) / 교차 플랫폼 유사 강좌 현황 분석
"""

import sys
import os
import pickle
import numpy as np
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"d:\26_강의자료\프로젝트2_교육"

FILES = {
    "search_cleaned": os.path.join(BASE_DIR, "data", "hr", "processed", "education_courses_search_cleaned.parquet"),
    "embeddings_npy": os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "embeddings_ko_sroberta_all.npy"),
    "embeddings_meta": os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "course_embeddings_metadata_all.parquet"),
    "comp_long": os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "course_competency_long.parquet"),
    "comp_wide": os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "matrix_course_competency_wide.parquet"),
    "clusters": os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "course_clusters_8645.parquet"),
    "search_cache": os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "search_models_cache.pkl")
}

def main():
    print("=" * 70)
    print("STEP 6: 1. 기존 데이터·코드 및 파일 스키마 점검")
    print("=" * 70)

    for key, path in FILES.items():
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        print(f"[{'O' if exists else 'X'}] {key}: {path} ({size:,} bytes)")

    # 1. search_cache.pkl 내용 점검
    print("\n--- 1. search_models_cache.pkl 구조 점검 ---")
    if os.path.exists(FILES["search_cache"]):
        size = os.path.getsize(FILES["search_cache"])
        if size == 0:
            print(f"search_models_cache.pkl exists but is 0 bytes (Empty/Uninitialized). No existing model inside.")
        else:
            try:
                with open(FILES["search_cache"], "rb") as f:
                    cache_obj = pickle.load(f)
                    print(f"Type of search_models_cache: {type(cache_obj)}")
            except Exception as e:
                print(f"Error loading search_cache: {e}")

    # 2. 각 Parquet 파일 스키마 및 행 수 확인
    dfs = {}
    print("\n--- 2. Parquet 파일 스키마 및 행 수 ---")
    for key in ["search_cleaned", "embeddings_meta", "comp_long", "comp_wide", "clusters"]:
        df = pd.read_parquet(FILES[key])
        dfs[key] = df
        print(f"\n[{key}] Shape: {df.shape}")
        print(f"Columns ({len(df.columns)}): {list(df.columns[:15])}{'...' if len(df.columns) > 15 else ''}")
        print(f"course_uid in columns? {'course_uid' in df.columns}")
        if 'course_uid' in df.columns:
            print(f"Unique course_uids: {df['course_uid'].nunique():,}")

    # 3. 임베딩 NPY 점검
    print("\n--- 3. embeddings_ko_sroberta_all.npy 점검 ---")
    emb = np.load(FILES["embeddings_npy"])
    print(f"Embedding shape: {emb.shape}, dtype: {emb.dtype}")

    # 4. course_uid 연결성 및 정렬 상태 확인
    print("\n--- 4. course_uid 일치 및 정렬 검사 ---")
    cleaned_uids = dfs["search_cleaned"]["course_uid"].tolist()
    meta_uids = dfs["embeddings_meta"]["course_uid"].tolist()
    clusters_uids = dfs["clusters"]["course_uid"].tolist()
    wide_uids = dfs["comp_wide"]["course_uid"].tolist()

    print(f"search_cleaned == embeddings_meta (순서 및 동일성)? {cleaned_uids == meta_uids}")
    print(f"search_cleaned == clusters (순서 및 동일성)? {cleaned_uids == clusters_uids}")
    print(f"search_cleaned len: {len(cleaned_uids)}, comp_wide len: {len(wide_uids)}")
    print(f"comp_wide uids in search_cleaned? {set(wide_uids).issubset(set(cleaned_uids))}")
    print(f"search_cleaned uids not in comp_wide: {len(set(cleaned_uids) - set(wide_uids))}")

    # 5. 역량 매핑 및 라벨 현황 상세 분석
    print("\n--- 5. 역량 데이터 (comp_long, comp_wide) 분석 ---")
    df_long = dfs["comp_long"]
    print("comp_long Head:")
    print(df_long.head())
    print("\ncomp_long value counts of competency_id:")
    print(df_long["competency_id"].value_counts())
    if "mapping_source" in df_long.columns:
        print("\ncomp_long mapping_source counts:")
        print(df_long["mapping_source"].value_counts())
    if "confidence" in df_long.columns:
        print("\ncomp_long confidence describe:")
        print(df_long["confidence"].describe())

    df_wide = dfs["comp_wide"]
    print("\ncomp_wide Head:")
    print(df_wide.head())

    # 6. 오매핑 의심 109건 확인
    print("\n--- 6. 오매핑 의심 109건 및 이상치 점검 ---")
    p_mismatch = os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "mapping_mismatch_samples.json")
    if os.path.exists(p_mismatch):
        import json
        with open(p_mismatch, 'r', encoding='utf-8') as f:
            mismatch_data = json.load(f)
        print(f"mapping_mismatch_samples.json exists! Count: {len(mismatch_data)}")
        mismatch_uids = [item['course_uid'] for item in mismatch_data if 'course_uid' in item]
        print(f"Sample mismatch item: {mismatch_data[0] if mismatch_data else None}")
        
        # comp_wide에서 이 109건의 라벨 분포
        sub_wide = df_wide[df_wide['course_uid'].isin(mismatch_uids)]
        print(f"Mismatch UIDs present in comp_wide: {len(sub_wide)}")
        verified_cols = [c for c in df_wide.columns if c.endswith('_VERIFIED')]
        print("Verified count in 109 mismatch cases:")
        print(sub_wide[verified_cols].sum())

    # 7. 강좌명 중복 및 플랫폼 중복 확인 (Data Leakage 위험도)
    print("\n--- 7. 데이터 누출(Data Leakage) 사전 점검 ---")
    df_clean = dfs["search_cleaned"]
    print(f"Cleaned Course Titles - total: {len(df_clean)}, unique: {df_clean['title'].nunique()}")
    dup_titles = df_clean[df_clean.duplicated(subset=['title'], keep=False)]
    print(f"Rows with duplicate exact title: {len(dup_titles)} ({dup_titles['title'].nunique()} unique names)")
    
    # 정규화 타이틀 중복
    import re
    def norm_title(t):
        if not t: return ""
        t = re.sub(r'\[.*?\]|\(.*?\)', '', str(t))
        t = re.sub(r'[^\w\s]', '', t)
        return t.strip().lower()

    df_clean['norm_title'] = df_clean['title'].apply(norm_title)
    dup_norm = df_clean[df_clean.duplicated(subset=['norm_title'], keep=False)]
    print(f"Rows with duplicate normalized title: {len(dup_norm)} ({df_clean['norm_title'].nunique()} unique normalized names)")

    if "provider" in df_clean.columns:
        print(f"\nProvider distribution:\n{df_clean['provider'].value_counts()}")
        
    print(f"\nAll comp_wide columns ({len(df_wide.columns)}):")
    print(list(df_wide.columns))

if __name__ == "__main__":
    main()
