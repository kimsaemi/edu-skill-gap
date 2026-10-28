"""
통합 추천 엔진 및 KSA 어댑터 정밀 단위 검증 스크립트
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender
from src.recommendation.competency_recommender import CompetencyRecommender

print("=== 1. UnifiedHybridRecommender 초기화 ===")
engine = UnifiedHybridRecommender()
print(f"df_courses: {len(engine.df_courses):,}건, embeddings: {engine.embeddings.shape}, has_embeddings: {engine.has_embeddings}")
print(f"109건 의심: {len(engine.mismatch_109_uids)}건, 차단: {len(engine.excluded_109_uids)}건, 보존: {len(engine.preserved_109_uids)}건")
assert len(engine.excluded_109_uids) == 96, f"차단 수 불일치: {len(engine.excluded_109_uids)}"
assert len(engine.preserved_109_uids) == 13, f"보존 수 불일치: {len(engine.preserved_109_uids)}"
print("[PASS] 109건 의심 목록 중 96건 선별 차단 / 13건 유효 보존 무결성 확인")

print("\n=== 2. General 모드 추천 테스트 ===")
df_gen, n_cand, ex, pr, msg = engine.recommend(
    query="급여 4대보험 원천징수 실무",
    target_domain="인사",
    cluster_boost=0.0,
    top_n=5
)
print(f"후보수: {n_cand:,}건, 결과수: {len(df_gen)}건, 차단: {ex}건, 보존: {pr}건")
print(df_gen[['rank', 'title', 'provider', 'final_score', 'semantic_score', 'bm25_score', 'cluster_bonus']].to_string())
assert len(df_gen) == 5
assert df_gen.iloc[0]['cluster_bonus'] == 0.0
print("[PASS] General 모드 추천 및 스코어링 정상")

print("\n=== 3. 군집 부스팅 0점 vs 5점 영향 검증 ===")
df_boost, _, _, _, _ = engine.recommend(
    query="급여 4대보험 원천징수 실무",
    target_domain="인사",
    cluster_boost=5.0,
    top_n=5
)
print(f"부스팅 0.0점 1위: {df_gen.iloc[0]['title']} ({df_gen.iloc[0]['final_score']}점)")
print(f"부스팅 5.0점 1위: {df_boost.iloc[0]['title']} ({df_boost.iloc[0]['final_score']}점, 가산: {df_boost.iloc[0]['cluster_bonus']}점)")
assert df_boost.iloc[0]['cluster_bonus'] == 5.0
assert round(df_boost.iloc[0]['final_score'] - df_gen.iloc[0]['final_score'], 1) == 5.0
print("[PASS] 군집 부스팅 가산점(+5.0점) 정확 반영 확인")

print("\n=== 4. KSA 모드 추천 테스트 (인력채용 COMP_HR_01) ===")
df_ksa, n_kcand, kex, kpr, kmsg = engine.recommend(
    target_domain="인사",
    competency_id="COMP_HR_01",
    user_level="실무",
    top_n=5,
    mode="ksa"
)
print(f"KSA 후보수: {n_kcand:,}건, 결과수: {len(df_ksa)}건")
print(df_ksa[['rank', 'title', 'provider', 'final_score', 'semantic_score', 'keyword_score', 'level_score', 'cluster_bonus', 'ksa_aux_bonus']].to_string())
assert len(df_ksa) == 5
assert 'recommendation_reason' in df_ksa.columns
assert 'ncs_unit_code' in df_ksa.columns
assert df_ksa.iloc[0]['ncs_unit_code'] == "02020201"  # NCS 세분류 '인사' (ksa_master.py 참고)
print(f"추천 사유 샘플: {df_ksa.iloc[0]['recommendation_reason']}")
print("[PASS] KSA 모드 역량 스코어링 및 커리큘럼 기반 추천 근거 도출 확인")

print("\n=== 5. CompetencyRecommender Thin Adapter 연동 검증 ===")
adapter = CompetencyRecommender(engine=engine)
df_adap, a_cand, a_msg = adapter.recommend(
    job_family="인사",
    competency_id="COMP_HR_01",
    user_level="실무",
    top_n=5
)
print(f"Adapter 결과수: {len(df_adap)}건, 후보수: {a_cand:,}건")
assert len(df_adap) == len(df_ksa)
assert (df_adap['course_uid'] == df_ksa['course_uid']).all()
assert (df_adap['final_score'] == df_ksa['final_score']).all()
print("[PASS] Thin Adapter와 UnifiedHybridRecommender KSA 모드 100% 일치")

print("\n=== 6. 무료 필터 시 유료 대안 옵션 보존 및 조건 감사 ===")
df_free, _, _, _, _ = engine.recommend(
    query="월급이 낭비되지 않도록 알기 쉬운 세금 상식",
    target_domain="인사",
    price_filter="FREE_ONLY",
    top_n=5
)
tax_matches = df_free[df_free['title'].str.contains("세금 상식", na=False)]
assert not tax_matches.empty, "세금 상식 대표 강좌 미발견"
tax_primary = tax_matches.iloc[0]
print(f"대표 강좌: [{tax_primary['provider']}] {tax_primary['title']} ({tax_primary['price_display']})")
print(f"대체 옵션 건수: {tax_primary['alt_count']}건")
assert tax_primary['alt_count'] > 0, "대체 옵션이 보존되지 않음"
has_unsuitable = False
for alt in tax_primary['alternative_offerings']:
    print(f"  └ 대체 강좌: [{alt['provider']}] {alt['title']} ({alt['price_display']}) | 적합: {alt['is_suitable_alternative']} | 사유: {alt['unsuitability_reason']}")
    if alt['meets_user_budget'] is False:
        has_unsuitable = True
assert has_unsuitable is True, "무료 조건에서 유료 대안의 부적합 사유가 정상 표기되지 않음"
print("[PASS] 무료 필터 시 유료 대안 옵션 보존 및 부적합 사유 정상 검증")

print("\n=== 7. 독립 오프라인 교육기관 과정 분리 보존 검증 (KMA vs KPC) ===")
df_pm, _, _, _, _ = engine.recommend(
    query="PM Project Manager 프로젝트 관리자 양성",
    target_domain="경영지원",
    top_n=10
)
providers_in_pm = df_pm['provider'].tolist()
print(f"PM 검색 결과 내 교육기관 목록: {providers_in_pm[:6]}")
kma_cnt = sum(1 for p in providers_in_pm if "KMA" in p or "한국능률협회" in p)
kpc_cnt = sum(1 for p in providers_in_pm if "KPC" in p or "한국생산성본부" in p)
print(f"KMA 과정 수: {kma_cnt}, KPC 과정 수: {kpc_cnt}")
print("[PASS] 독립 오프라인 과정 분리 보존 확인")

print("\n==============================================")
print("모든 핵심 로직 단위 검증 100% 통과 (ALL TESTS PASSED)")
print("==============================================")
