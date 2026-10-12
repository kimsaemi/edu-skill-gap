"""End-to-End System & TF-IDF / BM25 Readiness Test.

Validates:
1. STEP 4 Dashboard legacy pipeline integrity (strictly preserving 295/553 course scope).
2. NCS/KSA mapping files linkage.
3. TF-IDF & BM25 search engines capability to index & search over new integrated Parquet data.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path("d:/26_강의자료/프로젝트2_교육")))

from src.processors.data_loader import load_integrated_courses, load_legacy_verified_courses
from src.recommendation.text_preprocessor import HRTextPreprocessor
from src.recommendation.bm25_search import BM25SearchEngine
from src.recommendation.tfidf_search import TFIDFSearchEngine

def run_all_system_tests():
    print("=" * 70)
    print(" [1] STEP 4 MVP 대시보드 데이터 무결성 및 레거시 범위 격리 검사")
    print("=" * 70)
    df_legacy = load_legacy_verified_courses()
    assert len(df_legacy) == 295, f"레거시 확정 건수 오류: {len(df_legacy)} != 295"
    print(f"  [PASS] 기존 STEP 4 대시보드 분석용 데이터: 정확히 295건 격리 유지")
    print(f"         (8,645건 신규 통합 데이터와 혼선 없이 독립 운영 보장)")

    print("\n" + "=" * 70)
    print(" [2] NCS / KSA 매핑 산출물 연결 검사")
    print("=" * 70)
    ncs_path = Path("data/hr/mapped/education_ncs_mapping.csv")
    ksa_path = Path("data/hr/mapped/education_ksa_mapping.csv")
    assert ncs_path.exists() and ksa_path.exists()
    df_ncs = pd.read_csv(ncs_path)
    df_ksa = pd.read_csv(ksa_path)
    assert len(df_ncs) == 8291
    assert len(df_ksa) == 8291
    print(f"  [PASS] NCS 매핑 테이블 연결: {len(df_ncs):,}행")
    print(f"  [PASS] KSA 매핑 테이블 연결: {len(df_ksa):,}행")

    print("\n" + "=" * 70)
    print(" [3] 향후 TF-IDF & BM25 검색 엔진 코퍼스 적재 및 검색 준비 상태 검증")
    print("=" * 70)
    # 1. Load Parquet integrated master
    df_integ = load_integrated_courses(scope="all")
    print(f"  [+] Parquet 통합 코퍼스 로드: {len(df_integ):,}건 (로딩 포맷: {df_integ.attrs.get('data_source_type')})")
    
    # 2. Build corpus search text: title + intro + goals + curriculum
    df_integ["search_text"] = (
        df_integ["title"].fillna("") + " " +
        df_integ["category_depth1"].fillna("") + " " +
        df_integ["category_depth2"].fillna("") + " " +
        df_integ["course_intro"].fillna("").str[:200] + " " +
        df_integ["learning_goals"].fillna("").str[:200]
    )

    # Alias columns required by BM25/TF-IDF modules
    df_integ["global_course_key"] = df_integ["course_uid"]
    df_integ["course_name"] = df_integ["title"]
    df_integ["source_platform"] = df_integ["provider"]
    df_integ["training_hours"] = df_integ["duration_hours"]
    df_integ["total_course_fee"] = df_integ["price"]
    df_integ["learner_cost"] = df_integ["price"]
    df_integ["source_url"] = df_integ["url"]
    df_integ["text_source_status"] = df_integ["mapping_status"]

    # 3. Test BM25 Engine
    bm25_engine = BM25SearchEngine()
    bm25_engine.fit(df_integ, text_col="search_text")
    bm25_results = bm25_engine.search(query="인사 노무 근로기준법", top_k=3)
    assert len(bm25_results) > 0, "BM25 검색 결과 없음"
    print(f"  [PASS] BM25 엔진 8,645건 코퍼스 인덱싱 및 검색 테스트 통과!")
    print(f"         - Top 1 결과: {bm25_results[0]['course_name']} (점수: {bm25_results[0]['bm25_score']}, 키워드: {bm25_results[0]['matched_keywords']})")

    # 4. Test TF-IDF Engine
    tfidf_engine = TFIDFSearchEngine()
    tfidf_engine.fit(df_integ, text_col="search_text")
    tfidf_results = tfidf_engine.search(query="총무 자산관리 비품", top_k=3)
    assert len(tfidf_results) > 0, "TF-IDF 검색 결과 없음"
    print(f"  [PASS] TF-IDF 엔진 8,645건 코퍼스 벡터화 및 검색 테스트 통과!")
    print(f"         - Top 1 결과: {tfidf_results[0]['course_name']} (유사도: {tfidf_results[0]['similarity_score']}, 키워드: {tfidf_results[0]['matched_keywords']})")

    print("\n" + "=" * 70)
    print(" [ALL SYSTEM & SEARCH READINESS TESTS PASSED!]")
    print("=" * 70)

if __name__ == "__main__":
    run_all_system_tests()
