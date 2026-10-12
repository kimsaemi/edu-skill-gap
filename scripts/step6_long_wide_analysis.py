"""
STEP 6: NCS 교육 데이터 Long-form / Wide-form 구조화, Groupby/Crosstab/Pivot 심층 분석 및 검증 스크립트
- 입력:
    - data/hr/processed/education_courses_search_cleaned.parquet (8,645건 통합 교육과정)
    - data/hr/mapped/education_ncs_mapping.csv (8,291건 교육과정-역량 매핑)
    - data/hr/output/recommendation/course_tfidf_keywords.csv (8,645건 TF-IDF 키워드)
    - data/hr/processed/competencies.csv (NCS/KSA 역량 정의)
    - data/hr/processed/jobs.csv (직무 정의)
- 출력:
    - Long-form 교육-역량: data/hr/output/recommendation/course_competency_long.parquet (.csv)
    - Long-form 교육-키워드: data/hr/output/recommendation/course_keyword_long.parquet (.csv)
    - Wide-form 교육-역량 행렬: data/hr/output/recommendation/matrix_course_competency_wide.parquet (.csv)
    - Wide-form 교육-키워드 행렬: data/hr/output/recommendation/matrix_course_keyword_wide.csv
    - Wide-form 기관-역량 교차표: data/hr/output/recommendation/pivot_provider_competency_wide.csv
    - 연결 건수 교차표: data/hr/output/recommendation/crosstab_provider_competency_links.csv
    - 집계 요약 CSV들 (기관별, 직무별, 역량별, 역량연결수별)
"""

import os
import re
import time
import json
from pathlib import Path
import pandas as pd
import numpy as np

def run_long_wide_analysis():
    start_time = time.time()
    workspace_root = Path(__file__).resolve().parent.parent
    
    # 1. 파일 경로 설정
    p_courses = workspace_root / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
    p_ncs = workspace_root / "data" / "hr" / "mapped" / "education_ncs_mapping.csv"
    p_tfidf = workspace_root / "data" / "hr" / "output" / "recommendation" / "course_tfidf_keywords.csv"
    p_comp = workspace_root / "data" / "hr" / "processed" / "competencies.csv"
    p_jobs = workspace_root / "data" / "hr" / "processed" / "jobs.csv"
    
    out_dir = workspace_root / "data" / "hr" / "output" / "recommendation"
    reports_dir = workspace_root / "data" / "hr" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("STEP 6: Long-form / Wide-form 데이터 구조화 및 심층 분석 시작")
    print("=" * 80)
    
    # 2. 원본 데이터 로드 (불변 보존)
    print("1. 원본 데이터 로드 중...")
    df_courses = pd.read_parquet(p_courses)
    df_ncs_raw = pd.read_csv(p_ncs, encoding="utf-8")
    df_tfidf_raw = pd.read_csv(p_tfidf, encoding="utf-8")
    df_comp = pd.read_csv(p_comp, encoding="utf-8")
    df_jobs = pd.read_csv(p_jobs, encoding="utf-8")
    
    print(f" - 전체 교육과정: {len(df_courses):,}건 (고유 course_uid: {df_courses['course_uid'].nunique():,}개)")
    print(f" - NCS 매핑 원본: {len(df_ncs_raw):,}행 (고유 course_uid: {df_ncs_raw['course_uid'].nunique():,}개)")
    print(f" - TF-IDF 키워드 원본: {len(df_tfidf_raw):,}행")
    
    # =========================================================================
    # 3. 관측 단위 점검 (Observational Units)
    # =========================================================================
    print("\n2. 데이터 관측 단위(Observational Units) 점검...")
    unit_stats = {
        "course_unit": {
            "description": "교육과정 단위 (개설 강좌 등록 건)",
            "primary_key": "course_uid",
            "total_rows": len(df_courses),
            "unique_keys": int(df_courses['course_uid'].nunique()),
            "is_unique": bool(len(df_courses) == df_courses['course_uid'].nunique())
        },
        "session_unit": {
            "description": "교육과정 × 개설 회차 단위 (동일 제목 다회차 개설 강좌)",
            "composite_key": ["provider", "title"],
            "unique_content_titles": int(df_courses['title'].nunique()),
            "unique_provider_titles": int(df_courses.groupby(['provider', 'title']).ngroups),
            "multiple_session_offerings": int(len(df_courses) - df_courses.groupby(['provider', 'title']).ngroups)
        },
        "competency_link_unit": {
            "description": "교육과정 × 역량 연결 단위 (다대다 N:M 매핑)",
            "composite_key": ["course_uid", "competency_id"],
            "total_links": len(df_ncs_raw),
            "unique_courses_mapped": int(df_ncs_raw['course_uid'].nunique()),
            "unique_competencies": int(df_ncs_raw['competency_id'].nunique()),
            "unmapped_courses": int(len(df_courses) - df_ncs_raw['course_uid'].nunique()),
            "avg_links_per_mapped_course": round(len(df_ncs_raw) / df_ncs_raw['course_uid'].nunique(), 2)
        }
    }
    
    # =========================================================================
    # 4. Long-form 데이터 생성
    # =========================================================================
    print("\n3. Long-form (Tidy Data) 데이터셋 구축 중...")
    
    # (1) Long-form 1: Course-Competency Link
    # df_ncs_raw를 기반으로 필요한 메타데이터 정렬 및 수치형 가중치/검증 플래그 보강
    df_comp_long = df_ncs_raw.copy()
    
    # 코스 메타데이터(카테고리, 수강료, 교육시간 등) 조인
    meta_cols = ['course_uid', 'category_depth1', 'category_depth2', 'price', 'duration_hours']
    df_comp_long = df_comp_long.merge(
        df_courses[meta_cols],
        on='course_uid',
        how='left'
    )
    
    # 파생 변수
    df_comp_long['is_verified'] = df_comp_long['mapping_status'] == 'VERIFIED'
    
    # 신뢰도 수치 가중치
    confidence_weights = {'HIGH': 1.0, 'MEDIUM': 0.7, 'LOW': 0.4}
    df_comp_long['confidence_weight'] = df_comp_long['mapping_confidence'].map(confidence_weights).fillna(0.5)
    
    # 파일 저장 (Parquet 및 CSV)
    p_comp_long_parquet = out_dir / "course_competency_long.parquet"
    p_comp_long_csv = out_dir / "course_competency_long.csv"
    df_comp_long.to_parquet(p_comp_long_parquet, index=False, compression="zstd")
    df_comp_long.to_csv(p_comp_long_csv, index=False, encoding="utf-8-sig")
    print(f" -> [완료] course_competency_long: {len(df_comp_long):,}행 저장 완료")
    
    # (2) Long-form 2: Course-Keyword Link
    print(" - TF-IDF 키워드 Long-form 변환 중...")
    kw_records = []
    kw_pattern = re.compile(r'([^,\(\)]+?)\(([\d\.]+)\)')
    
    for _, row in df_tfidf_raw.iterrows():
        c_uid = row['course_uid']
        prov = row['provider']
        title = row['title']
        scores_str = str(row.get('keyword_scores', ''))
        
        matches = kw_pattern.findall(scores_str)
        if matches:
            for rank, (kw, score) in enumerate(matches, 1):
                kw_clean = kw.strip()
                if kw_clean:
                    kw_records.append({
                        'course_uid': c_uid,
                        'provider': prov,
                        'course_title': title,
                        'keyword': kw_clean,
                        'tfidf_score': float(score),
                        'keyword_rank': rank
                    })
        else:
            # 키워드가 없는 경우 빈 레코드 방지
            raw_kws = str(row.get('top_tfidf_keywords', '')).split(',')
            for rank, kw in enumerate(raw_kws, 1):
                kw_clean = kw.strip()
                if kw_clean:
                    kw_records.append({
                        'course_uid': c_uid,
                        'provider': prov,
                        'course_title': title,
                        'keyword': kw_clean,
                        'tfidf_score': 0.0,
                        'keyword_rank': rank
                    })
                    
    df_kw_long = pd.DataFrame(kw_records)
    p_kw_long_parquet = out_dir / "course_keyword_long.parquet"
    p_kw_long_csv = out_dir / "course_keyword_long.csv"
    df_kw_long.to_parquet(p_kw_long_parquet, index=False, compression="zstd")
    df_kw_long.to_csv(p_kw_long_csv, index=False, encoding="utf-8-sig")
    print(f" -> [완료] course_keyword_long: {len(df_kw_long):,}행 저장 완료 (8,645개 강좌별 상위 키워드)")
    
    # =========================================================================
    # 5. Wide-form 데이터 생성
    # =========================================================================
    print("\n4. Wide-form 데이터셋 구축 중...")
    
    # (1) Wide-form 1: 교육과정 × KSA 역량 연결 행렬 (Course × Competency Matrix)
    # 전체 8,645개 교육과정이 누락 없이 포함되어야 함!
    all_competencies = sorted(df_comp_long['competency_id'].unique().tolist())
    
    # 전체 매핑 피벗 (연결 여부 1 or 0)
    # 한 코스가 동일 역량에 중복 매핑되지 않으므로 max 또는 count(>0 -> 1)
    df_pivot_all = df_comp_long.pivot_table(
        index='course_uid',
        columns='competency_id',
        values='mapping_confidence',
        aggfunc=lambda x: 1,
        fill_value=0
    )
    
    # 검증(VERIFIED) 전용 피벗
    df_comp_verified = df_comp_long[df_comp_long['is_verified']]
    df_pivot_ver = df_comp_verified.pivot_table(
        index='course_uid',
        columns='competency_id',
        values='mapping_confidence',
        aggfunc=lambda x: 1,
        fill_value=0
    )
    df_pivot_ver.columns = [f"{col}_VERIFIED" for col in df_pivot_ver.columns]
    
    # 전체 8,645개 코스와 결합 (누락된 코스는 모두 0으로 채움)
    df_course_base = df_courses[['course_uid', 'provider', 'title', 'price', 'duration_hours']].copy()
    
    df_course_comp_wide = df_course_base.merge(df_pivot_all, on='course_uid', how='left')
    df_course_comp_wide[all_competencies] = df_course_comp_wide[all_competencies].fillna(0).astype(int)
    
    df_course_comp_wide = df_course_comp_wide.merge(df_pivot_ver, on='course_uid', how='left')
    ver_cols = [f"{col}_VERIFIED" for col in all_competencies]
    # 만약 일부 역량에 VERIFIED가 없으면 컬럼 생성
    for vc in ver_cols:
        if vc not in df_course_comp_wide.columns:
            df_course_comp_wide[vc] = 0
    df_course_comp_wide[ver_cols] = df_course_comp_wide[ver_cols].fillna(0).astype(int)
    
    # 요약 집계 컬럼
    df_course_comp_wide['total_comp_count'] = df_course_comp_wide[all_competencies].sum(axis=1)
    df_course_comp_wide['verified_comp_count'] = df_course_comp_wide[ver_cols].sum(axis=1)
    df_course_comp_wide['is_mapped'] = (df_course_comp_wide['total_comp_count'] > 0).astype(int)
    
    p_course_comp_wide_csv = out_dir / "matrix_course_competency_wide.csv"
    p_course_comp_wide_parquet = out_dir / "matrix_course_competency_wide.parquet"
    df_course_comp_wide.to_csv(p_course_comp_wide_csv, index=False, encoding="utf-8-sig")
    df_course_comp_wide.to_parquet(p_course_comp_wide_parquet, index=False, compression="zstd")
    print(f" -> [완료] matrix_course_competency_wide: {len(df_course_comp_wide):,}행 × {df_course_comp_wide.shape[1]}열 저장 완료 (전체 8,645개 교육과정 누락 없음)")
    
    # (2) Wide-form 2: 교육과정 × 핵심 키워드 행렬 (Top Rank Wide)
    # 각 교육과정별 1~5순위 키워드와 점수를 가로 컬럼으로 피벗
    df_kw_top5 = df_kw_long[df_kw_long['keyword_rank'] <= 5].copy()
    
    pivot_kw = df_kw_top5.pivot(
        index='course_uid',
        columns='keyword_rank',
        values=['keyword', 'tfidf_score']
    )
    # 컬럼 플래트닝: kw_rank_1, score_rank_1 ...
    flat_cols = []
    for val_type, rank in pivot_kw.columns:
        prefix = "kw" if val_type == "keyword" else "tfidf"
        flat_cols.append(f"{prefix}_rank_{rank}")
    pivot_kw.columns = flat_cols
    pivot_kw = pivot_kw.reset_index()
    
    df_course_kw_wide = df_course_base[['course_uid', 'provider', 'title']].merge(pivot_kw, on='course_uid', how='left')
    p_course_kw_wide_csv = out_dir / "matrix_course_keyword_wide.csv"
    df_course_kw_wide.to_csv(p_course_kw_wide_csv, index=False, encoding="utf-8-sig")
    print(f" -> [완료] matrix_course_keyword_wide: {len(df_course_kw_wide):,}행 × {df_course_kw_wide.shape[1]}열 저장 완료")
    
    # (3) Wide-form 3: 교육기관 × KSA 역량별 교육과정 수 (Pivot Table: Distinct Courses Count)
    # 행: provider, 열: competency_name (또는 id), 값: 고유 과정 수(nunique)
    # 전체 매핑 기준
    pt_prov_comp = df_comp_long.pivot_table(
        index='provider',
        columns='competency_name',
        values='course_uid',
        aggfunc='nunique',
        fill_value=0
    )
    # 합계 행과 열 추가
    pt_prov_comp_with_totals = pt_prov_comp.copy()
    # 주의: 교차표의 각 행 합(Row Sum)은 '연결 건수'가 되며, '기관별 고유 매핑 강좌 수'와 다름!
    # 따라서 명확히 구분된 컬럼 추가
    distinct_by_prov = df_comp_long.groupby('provider')['course_uid'].nunique()
    total_courses_by_prov = df_courses.groupby('provider')['course_uid'].nunique()
    
    pt_prov_comp_with_totals['고유매핑과정수'] = distinct_by_prov
    pt_prov_comp_with_totals['전체개설과정수'] = total_courses_by_prov
    pt_prov_comp_with_totals['매핑율(%)'] = (pt_prov_comp_with_totals['고유매핑과정수'] / pt_prov_comp_with_totals['전체개설과정수'] * 100).round(1)
    
    p_pivot_prov_comp_csv = out_dir / "pivot_provider_competency_wide.csv"
    pt_prov_comp_with_totals.to_csv(p_pivot_prov_comp_csv, encoding="utf-8-sig")
    print(f" -> [완료] pivot_provider_competency_wide: {pt_prov_comp_with_totals.shape[0]}개 기관 교차표 저장 완료")
    
    # 연결 건수 기준 crosstab (비교 대조용)
    ct_prov_comp_links = pd.crosstab(
        df_comp_long['provider'],
        df_comp_long['competency_name'],
        margins=True,
        margins_name="총연결건수"
    )
    p_ct_prov_comp_csv = out_dir / "crosstab_provider_competency_links.csv"
    ct_prov_comp_links.to_csv(p_ct_prov_comp_csv, encoding="utf-8-sig")
    print(f" -> [완료] crosstab_provider_competency_links: {ct_prov_comp_links.shape[0]}개 기관 연결건수 교차표 저장 완료")
    
    # =========================================================================
    # 6. Groupby / Crosstab / Pivot 심층 분석 및 통계 집계
    # =========================================================================
    print("\n5. Groupby / Crosstab / Pivot 심층 통계 산출 중...")
    
    # (1) 기관별 교육과정 통계 (고유 과정수, 회차수, 평균 수강료, 평균 교육시간)
    df_courses['price_numeric'] = pd.to_numeric(df_courses['price'], errors='coerce')
    df_courses['hours_numeric'] = pd.to_numeric(df_courses['duration_hours'], errors='coerce')
    
    summary_prov = df_courses.groupby('provider').agg(
        전체과정수=('course_uid', 'count'),
        고유제목수=('title', 'nunique'),
        무료과정수=('price_numeric', lambda x: (x == 0).sum()),
        유료과정수=('price_numeric', lambda x: (x > 0).sum()),
        평균수강료_전체=('price_numeric', 'mean'),
        평균수강료_유료만=('price_numeric', lambda x: x[x > 0].mean() if (x > 0).any() else 0),
        중앙값수강료=('price_numeric', 'median'),
        평균교육시간=('hours_numeric', 'mean'),
        중앙값교육시간=('hours_numeric', 'median'),
        교육시간기재건수=('hours_numeric', 'count')
    ).reset_index()
    
    # 매핑 강좌 수 결합
    summary_prov = summary_prov.merge(
        distinct_by_prov.rename('NCS매핑과정수').reset_index(),
        on='provider',
        how='left'
    ).fillna(0)
    summary_prov['NCS매핑과정수'] = summary_prov['NCS매핑과정수'].astype(int)
    summary_prov['다회차비율(%)'] = ((1 - summary_prov['고유제목수'] / summary_prov['전체과정수']) * 100).round(1)
    summary_prov['평균수강료_전체'] = summary_prov['평균수강료_전체'].round(0)
    summary_prov['평균수강료_유료만'] = summary_prov['평균수강료_유료만'].round(0)
    summary_prov['평균교육시간'] = summary_prov['평균교육시간'].round(1)
    
    p_summary_prov_csv = out_dir / "summary_provider_stats.csv"
    summary_prov.to_csv(p_summary_prov_csv, index=False, encoding="utf-8-sig")
    
    # (2) 직무별 교육과정 통계 (고유 과정수 vs 연결 건수, 검증 건수)
    summary_job = df_comp_long.groupby('target_job_family').agg(
        연결건수=('course_uid', 'count'),
        고유교육과정수=('course_uid', 'nunique'),
        검증매핑건수=('is_verified', lambda x: x.sum()),
        검토필요건수=('is_verified', lambda x: (~x).sum()),
        검증비율=('is_verified', lambda x: round(x.mean() * 100, 1))
    ).reset_index()
    summary_job['평균역량연결수'] = (summary_job['연결건수'] / summary_job['고유교육과정수']).round(2)
    summary_job = summary_job.sort_values(by='고유교육과정수', ascending=False)
    p_summary_job_csv = out_dir / "summary_job_family_stats.csv"
    summary_job.to_csv(p_summary_job_csv, index=False, encoding="utf-8-sig")
    
    # (3) 역량별 교육과정 통계
    summary_comp = df_comp_long.groupby(['competency_id', 'competency_name', 'ksa_type']).agg(
        연결건수=('course_uid', 'count'),
        고유교육과정수=('course_uid', 'nunique'),
        검증건수=('is_verified', lambda x: x.sum()),
        검토필요건수=('is_verified', lambda x: (~x).sum()),
        검증비율=('is_verified', lambda x: round(x.mean() * 100, 1))
    ).reset_index().sort_values(by='고유교육과정수', ascending=False)
    p_summary_comp_csv = out_dir / "summary_competency_stats.csv"
    summary_comp.to_csv(p_summary_comp_csv, index=False, encoding="utf-8-sig")
    
    # (4) 교육과정별 역량 연결 개수 분포
    comp_count_dist = df_course_comp_wide['total_comp_count'].value_counts().sort_index().reset_index()
    comp_count_dist.columns = ['연결역량개수', '교육과정수']
    comp_count_dist['비율(%)'] = (comp_count_dist['교육과정수'] / len(df_course_comp_wide) * 100).round(2)
    p_summary_counts_csv = out_dir / "summary_course_comp_counts.csv"
    comp_count_dist.to_csv(p_summary_counts_csv, index=False, encoding="utf-8-sig")
    
    # (5) 전체 코퍼스 상위 키워드 빈도 및 평균 점수
    summary_top_kws = df_kw_long.groupby('keyword').agg(
        출현과정수=('course_uid', 'nunique'),
        평균TFIDF점수=('tfidf_score', 'mean'),
        최고TFIDF점수=('tfidf_score', 'max'),
        최상위랭크수=('keyword_rank', lambda x: (x == 1).sum())
    ).reset_index().sort_values(by='출현과정수', ascending=False).head(50)
    summary_top_kws['평균TFIDF점수'] = summary_top_kws['평균TFIDF점수'].round(3)
    summary_top_kws['최고TFIDF점수'] = summary_top_kws['최고TFIDF점수'].round(3)
    p_summary_kws_csv = out_dir / "summary_top50_keywords.csv"
    summary_top_kws.to_csv(p_summary_kws_csv, index=False, encoding="utf-8-sig")
    
    # =========================================================================
    # 7. 엄밀한 무결성 검증 (Verification)
    # =========================================================================
    print("\n6. 데이터 무결성 및 관계 수 검증 중...")
    
    # 검증 1: Long-form과 Wide-form의 매핑 관계 총 수 일치 여부
    total_long_links = len(df_comp_long)
    total_wide_links = int(df_course_comp_wide[all_competencies].sum().sum())
    assert total_long_links == total_wide_links, f"관계 수 불일치! Long: {total_long_links}, Wide: {total_wide_links}"
    
    # 검증 2: 전체 교육과정 ID 보존 여부 (Wide-form에 누락된 교육과정 없음)
    assert len(df_course_comp_wide) == len(df_courses), f"행 수 불일치! Wide: {len(df_course_comp_wide)}, Courses: {len(df_courses)}"
    assert set(df_course_comp_wide['course_uid']) == set(df_courses['course_uid']), "교육 ID 불일치 발견!"
    
    # 검증 3: 매핑 과정 수 일치 여부
    unique_mapped_long = df_comp_long['course_uid'].nunique()
    unique_mapped_wide = int((df_course_comp_wide['total_comp_count'] > 0).sum())
    assert unique_mapped_long == unique_mapped_wide, f"매핑 과정 수 불일치! Long: {unique_mapped_long}, Wide: {unique_mapped_wide}"
    
    # 검증 4: TF-IDF 키워드 Long-form 코스 보존 확인
    unique_kw_courses = df_kw_long['course_uid'].nunique()
    assert unique_kw_courses == len(df_courses), f"키워드 누락 과정 존재! {unique_kw_courses} vs {len(df_courses)}"
    
    verification_metrics = {
        "status": "PASS",
        "total_courses": len(df_courses),
        "total_competency_links_long": total_long_links,
        "total_competency_links_wide": total_wide_links,
        "is_links_count_matched": bool(total_long_links == total_wide_links),
        "unique_courses_with_mapping": unique_mapped_long,
        "courses_without_mapping": len(df_courses) - unique_mapped_long,
        "total_keyword_records_long": len(df_kw_long),
        "unique_courses_with_keywords": unique_kw_courses,
        "distinct_check_summary": {
            "GSEEK_links": int(ct_prov_comp_links.loc['GSEEK', '총연결건수']),
            "GSEEK_unique_mapped_courses": int(distinct_by_prov['GSEEK']),
            "KMA_links": int(ct_prov_comp_links.loc['한국능률협회(KMA)', '총연결건수']),
            "KMA_unique_mapped_courses": int(distinct_by_prov['한국능률협회(KMA)']),
            "KPC_links": int(ct_prov_comp_links.loc['한국생산성본부(KPC)', '총연결건수']),
            "KPC_unique_mapped_courses": int(distinct_by_prov['한국생산성본부(KPC)'])
        }
    }
    
    p_verif_json = reports_dir / "long_wide_verification_metrics.json"
    with open(p_verif_json, "w", encoding="utf-8") as f:
        json.dump(verification_metrics, f, ensure_ascii=False, indent=2)
    
    print("=" * 80)
    print(" [검증 합격] Long-form <-> Wide-form 관계 수 및 고유 ID 무결성 100% 일치")
    print(f" - 전체 교육과정: {len(df_courses):,}건")
    print(f" - 매핑 관계 수: Long {total_long_links:,}개 == Wide {total_wide_links:,}개 (완벽 일치)")
    print(f" - 매핑 보유 과정: {unique_mapped_long:,}건 / 미매핑 과정: {len(df_courses) - unique_mapped_long:,}건")
    print(f" - 키워드 레코드: {len(df_kw_long):,}행 (전체 8,645개 과정 100% 매핑)")
    print(f" - 소요 시간: {time.time() - start_time:.2f}초")
    print("=" * 80)

if __name__ == "__main__":
    run_long_wide_analysis()
