"""
Streamlit STEP 4 대시보드 로직 및 데이터 검증 테스트 스크립트
"""

import sys
from pathlib import Path
import pandas as pd

WORKSPACE_ROOT = Path("d:/26_강의자료/프로젝트2_교육")
sys.path.insert(0, str(WORKSPACE_ROOT))
INTEG_DIR = WORKSPACE_ROOT / "data" / "hr" / "output" / "integration"
PROCESSED_DIR = WORKSPACE_ROOT / "data" / "hr" / "processed"

def test_data_integrity():
    print("[1] 데이터 파일 존재 및 로드 테스트...")
    files = [
        INTEG_DIR / "hr_integrated_candidates.csv",
        INTEG_DIR / "hr_integrated_verified.csv",
        INTEG_DIR / "hr_integrated_review.csv",
        INTEG_DIR / "hr_mapping_verified.csv",
        PROCESSED_DIR / "jobs.csv",
        PROCESSED_DIR / "competencies.csv",
        PROCESSED_DIR / "job_competencies.csv"
    ]
    for f in files:
        assert f.exists(), f"파일 누락: {f}"
        df = pd.read_csv(f, dtype=str)
        print(f"  - PASS: {f.name} (행 수: {len(df):,}개, 컬럼: {len(df.columns)}개)")

def test_dynamic_kpi_counts():
    print("\n[2] 동적 KPI 및 상태 카운트 정합성 테스트...")
    df_cand = pd.read_csv(INTEG_DIR / "hr_integrated_candidates.csv", dtype=str)
    total = len(df_cand)
    inc = (df_cand["classification_status"] == "INCLUDED").sum()
    rev = (df_cand["classification_status"] == "REVIEW_NEEDED").sum()
    exc = (df_cand["classification_status"] == "EXCLUDED").sum()
    print(f"  - 전체 후보: {total}건")
    print(f"  - 확정 포함(INCLUDED): {inc}건")
    print(f"  - 검토 대기(REVIEW): {rev}건")
    print(f"  - 제외(EXCLUDED): {exc}건")
    assert inc + rev + exc == total, f"합계 불일치: {inc}+{rev}+{exc} != {total}"
    print("  - PASS: 합계 무손실 정합성 100% 일치")

def test_filter_logic():
    print("\n[3] 탐색기 필터링 로직 테스트...")
    df_cand = pd.read_csv(INTEG_DIR / "hr_integrated_candidates.csv", dtype=str)
    
    # 3-1: INCLUDED 필터
    df_inc = df_cand[df_cand["classification_status"] == "INCLUDED"]
    assert len(df_inc) > 0, "INCLUDED 데이터 없음"
    print(f"  - PASS: INCLUDED 필터링 ({len(df_inc)}건)")

    # 3-2: 직무군 필터
    df_hr = df_inc[df_inc["job_group"] == "인사(HR)"]
    print(f"  - PASS: 인사(HR) 직무군 필터링 ({len(df_hr)}건)")

    # 3-3: 키워드 검색
    df_search = df_inc[df_inc["course_name"].str.contains("채용", case=False, na=False)]
    print(f"  - PASS: '채용' 키워드 검색 ({len(df_search)}건)")

def test_formatting_functions():
    print("\n[4] 포맷팅 유틸리티 함수 테스트...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("streamlit_step4", "app/streamlit_step4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    format_fee = mod.format_fee
    format_hours = mod.format_hours
    
    assert format_fee(0) == "무료 (국비/공공)", "0원 포맷팅 실패"
    assert format_fee(280000) == "280,000원", "유료 포맷팅 실패"
    assert format_fee(None) == "미기재 (문의)", "결측치 포맷팅 실패"
    assert format_hours(16.0) == "16.0시간", "시수 포맷팅 실패"
    assert format_hours(None) == "시수 미기재", "시수 결측치 포맷팅 실패"
    print("  - PASS: 수강료 및 시수 포맷팅 검증 완료")

if __name__ == "__main__":
    try:
        test_data_integrity()
        test_dynamic_kpi_counts()
        test_filter_logic()
        test_formatting_functions()
        print("\n" + "="*50)
        print("[SUCCESS] All Streamlit data and logic tests PASSED!")
        print("="*50)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
