# -*- coding: utf-8 -*-
"""
과정 중복 군집화 및 인사 교육 지도 단위 테스트
- 군집 결과 무결성 (카탈로그 존재 여부, 제외 목록 포함 여부)
- Top 3 군집 중복 제거 제약조건 검증 (옵션 B)
- 기관 상한 제약조건 검증 (옵션 C)
- course_map.json 메타데이터 및 크기/개수 정합성
"""

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

CATALOG_PARQUET = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
EXCLUSIONS_CSV = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
DEDUP_GROUPS_CSV = ROOT / "data" / "hr" / "processed" / "course_dedup_groups.csv"
COURSE_MAP_JSON = ROOT / "presentation" / "src" / "course_map.json"
REC_B_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked_B.csv"
REC_C_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked_C.csv"


def test_dedup_groups_consistency():
    """군집 결과의 모든 과정이 카탈로그에 있고, 제외 목록 과정은 다중 군집에 포함되지 않음"""
    assert DEDUP_GROUPS_CSV.exists(), "course_dedup_groups.csv missing"
    assert CATALOG_PARQUET.exists(), "catalog parquet missing"

    df_courses = pd.read_parquet(CATALOG_PARQUET)
    df_groups = pd.read_csv(DEDUP_GROUPS_CSV)
    catalog_uids = set(df_courses["course_uid"])

    # 1. 모든 과정이 카탈로그에 존재
    group_uids = set(df_groups["course_uid"])
    assert group_uids == catalog_uids, f"Mismatch in course UIDs: {len(group_uids)} vs {len(catalog_uids)}"

    # 2. 제외 목록에 있는 과정은 다중 군집(group_size > 1)에 묶이지 않아야 함
    if EXCLUSIONS_CSV.exists():
        df_excl = pd.read_csv(EXCLUSIONS_CSV, dtype=str)
        excl_uids = set(df_excl["course_uid"])
        excl_groups = df_groups[df_groups["course_uid"].isin(excl_uids)]
        multi_excl = excl_groups[excl_groups["group_size"] > 1]
        assert len(multi_excl) == 0, f"Excluded courses found in multi-groups: {len(multi_excl)}"
    print("test_dedup_groups_consistency PASSED")


def test_dedup_groups_option_b_constraint():
    """옵션 B에서는 한 슬롯 Top 3에 같은 group_id가 두 번 나오지 않음"""
    if not REC_B_CSV.exists():
        print("Skipping option B check: file missing")
        return

    df_rec_b = pd.read_csv(REC_B_CSV)
    df_groups = pd.read_csv(DEDUP_GROUPS_CSV)
    group_map = dict(zip(df_groups["course_uid"], df_groups["group_id"]))

    df_rec_b["group_id"] = df_rec_b["course_uid"].map(group_map).fillna(df_rec_b["course_uid"])
    counts = df_rec_b.groupby(["task_id", "level"])["group_id"].value_counts()
    duplicates = counts[counts > 1]
    assert len(duplicates) == 0, f"Found duplicate groups in Option B: {len(duplicates)}"
    print("test_dedup_groups_option_b_constraint PASSED")


def test_max_per_provider_option_c_constraint():
    """옵션 C에서는 한 슬롯 Top 3에 동일 교육기관이 3개(2개 초과) 나오지 않음"""
    if not REC_C_CSV.exists():
        print("Skipping option C check: file missing")
        return

    df_rec_c = pd.read_csv(REC_C_CSV)
    prov_counts = df_rec_c.groupby(["task_id", "level"])["provider"].value_counts()
    exceeded = prov_counts[prov_counts > 2]
    assert len(exceeded) == 0, f"Found provider count > 2 in Option C: {len(exceeded)}"
    print("test_max_per_provider_option_c_constraint PASSED")


def test_course_map_consistency():
    """course_map.json의 과정 수와 업무 수가 전체 데이터와 일치하고 유효함"""
    assert COURSE_MAP_JSON.exists(), "presentation/src/course_map.json missing"
    with open(COURSE_MAP_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    assert "method" in meta, "Missing reduction method in metadata"
    assert "UMAP" in meta["method"] or "TruncatedSVD" in meta["method"]

    courses = data.get("courses", [])
    tasks = data.get("tasks", [])

    n_plotted = len(courses)
    n_omitted = meta.get("n_omitted_courses", 0)
    assert n_plotted + n_omitted == 9075, f"Expected 9075 total courses, got {n_plotted} + {n_omitted} = {n_plotted + n_omitted}"
    assert n_plotted == meta.get("n_plotted_courses", n_plotted), "Mismatch in plotted course count"
    assert len(tasks) == 90, f"Expected 90 tasks, got {len(tasks)}"

    thin_tasks = [t for t in tasks if t[4] == 1]
    assert len(thin_tasks) == meta.get("n_thin_tasks", 0), "Mismatch in thin task count"
    assert len(thin_tasks) == 2, f"Expected 2 thin tasks (D02_T02, D02_T06), got {len(thin_tasks)}"
    print("test_course_map_consistency PASSED")




def test_default_filter_top3_matches_main():
    """옵션 없이 filter_top3를 실행한 결과가 main 최종 추천과 행 단위로 100% 일치하는지 회귀 검증"""
    cache_path = ROOT / "data" / "hr" / "output" / "recommendation" / ".scored_candidates_90.parquet"
    main_rec_path = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"

    if not cache_path.exists():
        print("[SKIP] .scored_candidates_90.parquet 캐시 파일이 없어 모델 없이 실행하는 환경에서는 건너뜁니다.")
        return

    assert main_rec_path.exists(), "task_course_recommendations_90_reranked.csv missing"

    import importlib.util
    spec = importlib.util.spec_from_file_location("build_reranked", ROOT / "scripts" / "build_reranked_90_recommendations.py")
    br = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(br)

    df_scored = pd.read_parquet(cache_path)
    df_a, _ = br.filter_top3(df_scored, dedup_groups=False, max_per_provider=0, group_map={})
    df_main = pd.read_csv(main_rec_path)

    assert len(df_a) == len(df_main), f"Row count mismatch: df_a={len(df_a)}, df_main={len(df_main)}"

    key_cols = ["task_id", "level", "rank", "course_uid"]
    diff = (df_a[key_cols] != df_main[key_cols]).any(axis=1)
    diff_count = int(diff.sum())
    assert diff_count == 0, f"Found {diff_count} differing rows between default filter_top3 and main recommendations!"
    print(f"test_default_filter_top3_matches_main PASSED: 100% match ({len(df_a)} rows, 0 diff)")

if __name__ == "__main__":
    test_default_filter_top3_matches_main()
    test_dedup_groups_consistency()
    test_dedup_groups_option_b_constraint()
    test_max_per_provider_option_c_constraint()
    test_course_map_consistency()
    print("All tests in test_dedup_and_map.py PASSED!")
