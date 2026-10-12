import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path("d:/26_강의자료/프로젝트2_교육")))

from src.processors.data_loader import (
    load_integrated_courses,
    load_standardized_courses,
    load_legacy_verified_courses
)

def test_loader():
    print("=" * 60)
    print(" [공통 데이터 로더 단위 테스트] ")
    print("=" * 60)

    # 1. Parquet priority test
    df_all = load_integrated_courses(scope="all")
    print(f" [PASS] load_integrated_courses(all): {len(df_all):,}행 | 읽은 포맷: {df_all.attrs.get('data_source_type')}")
    assert len(df_all) == 8645
    assert df_all.attrs.get("data_source_type") == "PARQUET"

    # 2. Scope filter test
    df_ver = load_integrated_courses(scope="verified_only")
    print(f" [PASS] load_integrated_courses(verified_only): {len(df_ver):,}행 (규칙 기반 자동 매핑 적합 3,595건 선별: 신규 3,499건 + 공공 96건, 사람의 전수 검수 대기)")
    assert len(df_ver) == 3595

    # 3. Force CSV fallback test
    df_csv = load_integrated_courses(scope="all", force_csv=True)
    print(f" [PASS] load_integrated_courses(force_csv=True): {len(df_csv):,}행 | 읽은 포맷: {df_csv.attrs.get('data_source_type')}")
    assert len(df_csv) == 8645
    assert df_csv.attrs.get("data_source_type") == "CSV"

    # 4. Standardized courses test
    df_std = load_standardized_courses()
    print(f" [PASS] load_standardized_courses(): {len(df_std):,}행")
    assert len(df_std) == 8505

    # 5. Legacy backward compatibility test
    df_legacy = load_legacy_verified_courses()
    print(f" [PASS] load_legacy_verified_courses(): {len(df_legacy):,}행 (기존 295건 호환)")
    assert len(df_legacy) == 295

    # 6. ID string preservation test
    assert df_all["course_uid"].dtype.name in ["string", "object"]
    assert df_all["source_course_id"].dtype.name in ["string", "object"]
    print(f" [PASS] 문자열 ID (course_uid, source_course_id) string 타입 보존 확인")

    print("\n" + "=" * 60)
    print(" [SUCCESS] All Common Data Loader tests PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_loader()
