"""
Streamlit Cloud 배포 및 추천 엔진 연동 종합 검증 스위트 (고도화 버전)
- 10대 핵심 검증 항목 전수 실행:
  1. 필수 모듈 import 검증
  2. 전처리 모듈 (Kiwi) 테스트
  3. 통합 추천 엔진(UnifiedHybridRecommender) & KSA 어댑터(CompetencyRecommender) 무결성
  4. 군집 부스팅(0.0점 vs 5.0점) 및 오매핑 109건 조건부 선별(96건 차단 / 13건 보존) 검증
  5. 크로스 플랫폼 중복 제거 (GSEEK/휴넷 대표 강좌 + 유료 대안 보존 + 조건 부적합 사유 감사)
  6. 독립 오프라인 교육기관(KMA vs KPC) 과정 분리 보존 검증
  7. KSA 역량(채용 vs 근로기준법) 변경에 따른 질의 구성 및 스코어링 반영 검증
  8. 필수 파일 누락/임베딩 부재 시 안전 제한 동작(Fallback) 검증
  9. Streamlit AppTest 기반 탭 8·탭 10 실제 위젯 상호작용 및 세션 상태 초기화 검증
  10. app/streamlit_integrated.py 문법 컴파일 (py_compile 문법 검증)
"""

import sys
import os
import json
from pathlib import Path
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

def run_full_verification_suite():
    print("=" * 80)
    print("🎓 NCS 교육 추천 통합 시스템 — 실데이터 및 UI 종합 검증 스위트")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. 필수 모듈 import 테스트
    # --------------------------------------------------------------------------
    print("\n=== 1. 필수 모듈 import 테스트 ===")
    modules = [
        'streamlit', 'pandas', 'numpy', 'scipy', 'sklearn', 'sentence_transformers',
        'rank_bm25', 'torch', 'pyarrow', 'plotly', 'altair', 'kiwipiepy'
    ]
    for mod in modules:
        try:
            __import__(mod)
            print(f"  [PASS] {mod}")
        except Exception as e:
            print(f"  [FAIL] {mod}: {e}")
            raise

    # --------------------------------------------------------------------------
    # 2. 전처리 모듈 및 Kiwi 테스트
    # --------------------------------------------------------------------------
    print("\n=== 2. 전처리 모듈 (HRTextPreprocessor) 및 Kiwi 테스트 ===")
    from src.recommendation.text_preprocessor import HRTextPreprocessor, HAS_KIWI
    prep = HRTextPreprocessor()
    sample_text = "<b>2024년 근로기준법</b> 개정 및 [인사평가] 실무 가이드입니다."
    cleaned = prep.clean_text(sample_text)
    tokens = prep.tokenize(sample_text)
    print(f"  - HAS_KIWI 플래그: {HAS_KIWI}")
    print(f"  - prep.kiwi 초기화 여부: {prep.kiwi is not None}")
    print(f"  - 정제 텍스트: {cleaned}")
    print(f"  - 추출 토큰: {tokens}")
    assert len(tokens) > 0, "토큰화 결과가 비어 있습니다."
    print("  [PASS] 텍스트 전처리 정상 작동")

    # --------------------------------------------------------------------------
    # 3. 통합 추천 엔진 및 KSA 어댑터 연동 테스트
    # --------------------------------------------------------------------------
    print("\n=== 3. 통합 추천 엔진 (UnifiedHybridRecommender) 및 KSA 어댑터 연동 테스트 ===")
    from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender
    from src.recommendation.competency_recommender import CompetencyRecommender
    from src.recommendation.ksa_master import KSA_COMPETENCIES_MASTER, DOMAIN_CLUSTER_MAP

    engine = UnifiedHybridRecommender()
    adapter = CompetencyRecommender(engine=engine)

    print(f"  - 코퍼스 크기: {len(engine.df_courses):,}건")
    print(f"  - 10대 군집 분포: {engine.df_courses['cluster_id'].nunique()}개 군집")
    print(f"  - 임베딩 차원: {engine.embeddings.shape}")
    print(f"  - 109건 오매핑 의심 세트: {len(engine.mismatch_109_uids)}건 (차단: {len(engine.excluded_109_uids)}건 / 보존: {len(engine.preserved_109_uids)}건)")
    assert len(engine.df_courses) == 8645, "코퍼스 건수가 8,645건이 아닙니다."
    assert engine.df_courses['cluster_id'].nunique() == 10, "10대 군집이 로드되지 않았습니다."
    assert len(engine.excluded_109_uids) == 96, f"차단 건수 불일치: {len(engine.excluded_109_uids)}"
    assert len(engine.preserved_109_uids) == 13, f"보존 건수 불일치: {len(engine.preserved_109_uids)}"
    print("  [PASS] 데이터셋, 군집 및 109건(96건 차단 / 13건 보존) 무결성 확인")

    # --------------------------------------------------------------------------
    # 4. 군집 부스팅 0점 vs 5점 영향 및 109건 차단 검증
    # --------------------------------------------------------------------------
    print("\n=== 4. 군집 부스팅 (0.0점 vs 5.0점) 및 109건 차단 검증 ===")
    res_off, c_off, ex_off, pr_off, _ = engine.recommend(
        query="급여 4대보험 원천징수 실무", target_domain="인사", cluster_boost=0.0, filter_mismatch_109=True, top_n=5
    )
    res_on, c_on, ex_on, pr_on, _ = engine.recommend(
        query="급여 4대보험 원천징수 실무", target_domain="인사", cluster_boost=5.0, filter_mismatch_109=True, top_n=5
    )
    score_diff = round(res_on.iloc[0]['final_score'] - res_off.iloc[0]['final_score'], 1)
    print(f"  - 109건 차단 수: {ex_off}건, 유지 수: {pr_off}건")
    print(f"  - 군집 부스팅 0.0점 1위 점수: {res_off.iloc[0]['final_score']} (가산: {res_off.iloc[0]['cluster_bonus']})")
    print(f"  - 군집 부스팅 5.0점 1위 점수: {res_on.iloc[0]['final_score']} (가산: {res_on.iloc[0]['cluster_bonus']})")
    print(f"  - 부스팅에 따른 1위 점수 차이: {score_diff}점")
    # 유지 13건 중 주제 이탈 제외 목록에 든 과정은 후보에서 빠지므로 차감
    expected_pr = 13 - len(engine.preserved_109_uids & engine.off_topic_uids)
    assert ex_off == 96 and pr_off == expected_pr, f"109건 차단/유지 건수 불일치: ex={ex_off}, pr={pr_off} (기대 유지 {expected_pr})"
    assert res_on.iloc[0]['cluster_bonus'] == 5.0, "군집 부스팅 가산점이 적용되지 않았습니다."
    assert score_diff == 5.0, f"부스팅 점수 차이가 정확히 5.0점이 아닙니다: {score_diff}"
    print("  [PASS] 군집 부스팅 및 109건 조건부 선별 확인")

    # --------------------------------------------------------------------------
    # 5. 크로스 플랫폼 중복 제거 및 무료 필터 시 유료 대안 옵션 보존 검증
    # --------------------------------------------------------------------------
    print("\n=== 5. 크로스 플랫폼 중복 제거 및 무료 필터 시 유료 대안 옵션 보존 검증 ===")
    res_tax, _, _, _, _ = engine.recommend(
        query="월급이 낭비되지 않도록 알기 쉬운 세금 상식",
        target_domain="인사",
        price_filter="FREE_ONLY",
        top_n=5
    )
    tax_matches = res_tax[res_tax['title'].str.contains("세금 상식", na=False)]
    assert not tax_matches.empty, "세금 상식 대표 강좌 미발견"
    tax_row = tax_matches.iloc[0]
    print(f"  - 대표 강좌: [{tax_row['provider']}] {tax_row['title']} ({tax_row['price_display']})")
    print(f"  - 대체 수강 옵션 건수: {tax_row['alt_count']}건")
    assert tax_row['price_display'] == "무료", "무료 필터 대표 강좌가 무료가 아닙니다."
    assert tax_row['alt_count'] > 0, "대체 수강 옵션이 연결되지 않았습니다."

    has_unsuitable = False
    for alt in tax_row['alternative_offerings']:
        print(f"     └ 대체 강좌: [{alt['provider']}] {alt['title']} ({alt['price_display']}) | 적합: {alt['is_suitable_alternative']} | 사유: {alt['unsuitability_reason']}")
        if alt['is_suitable_alternative'] is False:
            has_unsuitable = True
    assert has_unsuitable is True, "무료 조건에서 유료 대안의 부적합 사유가 정상 표기되지 않았습니다."
    print("  [PASS] 크로스 플랫폼 중복 제거 및 무료 조건 하 유료 대안 보존 확인")

    # --------------------------------------------------------------------------
    # 6. 독립 오프라인 교육기관(KMA vs KPC) 과정 분리 보존 검증
    # --------------------------------------------------------------------------
    print("\n=== 6. 독립 오프라인 교육기관(KMA vs KPC) 과정 분리 보존 검증 ===")
    res_pm, _, _, _, _ = engine.recommend(
        query="PM Project Manager 프로젝트 관리자 양성",
        target_domain="경영지원",
        top_n=10
    )
    providers_pm = res_pm['provider'].tolist()
    kma_present = any("KMA" in p or "한국능률협회" in p for p in providers_pm)
    kpc_present = any("KPC" in p or "한국생산성본부" in p for p in providers_pm)
    print(f"  - Top 10 내 KMA 과정 포함: {kma_present}, KPC 과정 포함: {kpc_present}")
    assert kma_present and kpc_present, "KMA 또는 KPC 독립 오프라인 과정이 보존되지 않았습니다."
    print("  [PASS] 독립 오프라인 교육기관 과정 분리 보존 확인")

    # --------------------------------------------------------------------------
    # 7. KSA 역량 선택 변경에 따른 질의 구성 및 추천 결과 변동 검증
    # --------------------------------------------------------------------------
    print("\n=== 7. KSA 역량 변경에 따른 질의 구성 및 추천 결과 변동 검증 ===")
    res_hr01, _, _ = adapter.recommend(job_family="인사", competency_id="COMP_HR_01", top_n=5)
    res_labor, _, _ = adapter.recommend(job_family="인사", competency_id="COMP_LABOR_01", top_n=5)

    uids_hr01 = res_hr01['course_uid'].tolist()
    uids_labor = res_labor['course_uid'].tolist()
    print(f"  - [COMP_HR_01 채용] 1위: [{res_hr01.iloc[0]['provider']}] {res_hr01.iloc[0]['title']} ({res_hr01.iloc[0]['final_score']}점)")
    print(f"  - [COMP_LABOR_01 노무] 1위: [{res_labor.iloc[0]['provider']}] {res_labor.iloc[0]['title']} ({res_labor.iloc[0]['final_score']}점)")
    print(f"  - 두 역량 간 추천 UID 상이 여부: {uids_hr01 != uids_labor}")
    assert uids_hr01 != uids_labor, "KSA 역량을 변경했음에도 추천 결과가 동일합니다."
    assert 'recommendation_reason' in res_hr01.columns and len(res_hr01.iloc[0]['recommendation_reason']) > 10
    print("  [PASS] KSA 역량 변경에 따른 질의·스코어링 및 추천 사유 생성 확인")

    # --------------------------------------------------------------------------
    # 8. 안전 제한 동작 (임베딩 누락 시 폴백) 단위 검증
    # --------------------------------------------------------------------------
    print("\n=== 8. 임베딩 누락 시 안전 폴백(Fallback) 동작 검증 ===")
    orig_has_emb = engine.has_embeddings
    orig_model = engine.model
    try:
        # 임베딩 강제 비활성화
        engine.has_embeddings = False
        engine.model = None

        res_fb, n_fb, _, _, _ = engine.recommend(
            query="급여 4대보험 원천징수 실무", target_domain="인사", top_n=5
        )
        print(f"  - 임베딩 부재 시 후보수: {n_fb:,}건, 결과수: {len(res_fb)}건")
        assert len(res_fb) == 5, "임베딩 누락 시 폴백 추천이 동작하지 않습니다."
        assert (res_fb['semantic_score'] == 50.0).all(), "임베딩 누락 시 시맨틱 점수가 중립값(50점)으로 설정되지 않았습니다."
        print("  [PASS] 임베딩 모델 부재 시 BM25 중심 안전 폴백 정상 동작")
    finally:
        engine.has_embeddings = orig_has_emb
        engine.model = orig_model

    # --------------------------------------------------------------------------
    # 9. Streamlit AppTest를 통한 탭 8·탭 10 실제 위젯 상호작용 검증
    # --------------------------------------------------------------------------
    print("\n=== 9. Streamlit AppTest 기반 실제 위젯 상호작용 검증 ===")
    from streamlit.testing.v1 import AppTest

    # AppTest 실행 (경로: app/streamlit_integrated.py)
    at = AppTest.from_file(str(WORKSPACE_ROOT / "app" / "streamlit_integrated.py"), default_timeout=300)
    at.run()
    assert not at.exception, f"Streamlit 앱 로딩 중 예외 발생: {at.exception}"
    print("  - Streamlit 앱 기본 화면 로딩 성공 (예외 없음)")

    # 기본 화면은 사용자 모드이므로, 분석 탭이 있는 관리자·분석 모드로 전환
    view_radio = [r for r in at.sidebar.radio if "화면 모드" in r.label][0]
    view_radio.set_value(view_radio.options[1]).run()
    assert not at.exception, f"분석 모드 전환 중 예외 발생: {at.exception}"
    print("  - 관리자·분석 모드 전환 성공 (예외 없음)")

    # 탭 8 위젯 존재 및 상태 확인
    assert "tab8_ui_platforms" in at.session_state, "tab8_ui_platforms 위젯이 세션에 등록되지 않았습니다."
    assert "tab8_ui_domain" in at.session_state, "tab8_ui_domain 위젯이 세션에 등록되지 않았습니다."
    assert "tab8_ui_cluster_boost" in at.session_state, "tab8_ui_cluster_boost 위젯이 세션에 등록되지 않았습니다."
    print("  - 탭 8 위젯 세션 상태 등록 확인: PASS")

    # 탭 10 위젯 존재 및 상태 확인
    assert "tab10_ui_job_family" in at.session_state, "tab10_ui_job_family 위젯이 세션에 등록되지 않았습니다."
    assert "tab10_ui_comp" in at.session_state, "tab10_ui_comp 위젯이 세션에 등록되지 않았습니다."
    assert "tab10_ui_cluster_boost" in at.session_state, "tab10_ui_cluster_boost 위젯이 세션에 등록되지 않았습니다."
    print("  - 탭 10 위젯 세션 상태 등록 확인: PASS")

    # 탭 8 필터 변경 및 추천 실행 테스트
    at.text_input(key="tab8_unified_query_input").input("근로기준법 취업규칙 개정 실무").run()
    at.button(key="tab8_btn_search").click().run()
    assert not at.exception, f"탭 8 즉시 추천 버튼 클릭 후 예외 발생: {at.exception}"
    assert "tab8_recommendation_results" in at.session_state, "탭 8 추천 결과가 세션에 저장되지 않았습니다."
    t8_res, t8_cand, _, _, _, t8_params = at.session_state["tab8_recommendation_results"]
    assert len(t8_res) > 0, "탭 8 추천 결과가 비어 있습니다."
    assert t8_params["query"] == "근로기준법 취업규칙 개정 실무", "입력한 쿼리가 엔진 파라미터로 전달되지 않았습니다."
    print(f"  - 탭 8 위젯 입력 ➔ 추천 실행 ➔ 결과 저장({len(t8_res)}건) 확인: PASS")

    # 탭 8 필터 초기화 버튼 클릭 테스트
    at.button(key="tab8_btn_reset_filters").click().run()
    assert not at.exception, f"탭 8 필터 초기화 버튼 클릭 후 예외 발생: {at.exception}"
    assert at.session_state["tab8_ui_domain"] == "인사", "초기화 후 직무 도메인이 기본값으로 복구되지 않았습니다."
    assert at.session_state["tab8_ui_cluster_boost"] == 0.0, "초기화 후 군집 부스팅이 0.0으로 복구되지 않았습니다."
    print("  - 탭 8 필터 초기화 위젯 세션 키 리셋 확인: PASS")

    # 탭 10 추천 실행 버튼 클릭 테스트
    at.button(key="tab10_btn_search").click().run()
    assert not at.exception, f"탭 10 추천 실행 버튼 클릭 후 예외 발생: {at.exception}"
    assert "tab10_recommendation_results" in at.session_state, "탭 10 추천 결과가 세션에 저장되지 않았습니다."
    t10_res, t10_cand, _, t10_params = at.session_state["tab10_recommendation_results"]
    assert len(t10_res) > 0, "탭 10 추천 결과가 비어 있습니다."
    assert t10_params["job_family"] == "인사", "탭 10 선택 직무가 파라미터로 전달되지 않았습니다."
    print(f"  - 탭 10 위젯 입력 ➔ 추천 실행 ➔ 결과 저장({len(t10_res)}건) 확인: PASS")
    print("  [PASS] Streamlit AppTest 기반 UI ➔ 엔진 위젯 경로 검증 완료")

    # --------------------------------------------------------------------------
    # 10. app/streamlit_integrated.py 문법 컴파일
    # --------------------------------------------------------------------------
    print("\n=== 10. Streamlit 파일 문법 컴파일 (py_compile) ===")
    import py_compile
    py_compile.compile(str(WORKSPACE_ROOT / "app" / "streamlit_integrated.py"), doraise=True)
    print("  [PASS] app/streamlit_integrated.py 문법 컴파일 무결성 확인")

    print("\n" + "=" * 80)
    print("🎉 전체 검증 스위트 10대 항목 100% 전수 통과 (ALL TESTS PASSED)")
    print("=" * 80)

if __name__ == "__main__":
    run_full_verification_suite()
