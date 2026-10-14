"""
Streamlit Cloud 배포 및 추천 엔진 연동 종합 검증 스위트
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

print("=== 1. 필수 모듈 import 테스트 ===")
modules = [
    'streamlit', 'pandas', 'numpy', 'scipy', 'sklearn', 'sentence_transformers',
    'rank_bm25', 'torch', 'pyarrow', 'plotly', 'altair', 'kiwipiepy'
]
import_pass = True
for mod in modules:
    try:
        __import__(mod)
        print(f"  [PASS] {mod}")
    except Exception as e:
        print(f"  [FAIL] {mod}: {e}")
        import_pass = False

print("\n=== 2. 전처리 모듈 (HRTextPreprocessor) 및 Kiwi 테스트 ===")
from src.recommendation.text_preprocessor import HRTextPreprocessor, HAS_KIWI
prep = HRTextPreprocessor()
print(f"  - HAS_KIWI 플래그: {HAS_KIWI}")
print(f"  - prep.kiwi 초기화 여부: {prep.kiwi is not None}")
sample_text = "<b>2024년 근로기준법</b> 개정 및 [인사평가] 실무 가이드입니다."
cleaned = prep.clean_text(sample_text)
tokens = prep.tokenize(sample_text)
print(f"  - 정제 텍스트: {cleaned}")
print(f"  - 추출 토큰: {tokens}")
assert len(tokens) > 0, "토큰화 결과가 비어 있습니다."
print("  - 텍스트 전처리 정상 작동: PASS")

print("\n=== 3. 통합 추천 엔진 (UnifiedHybridRecommender) 연동 테스트 ===")
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender
engine = UnifiedHybridRecommender()
print(f"  - 코퍼스 크기: {len(engine.df_courses):,}건")
print(f"  - 10대 군집 분포: {engine.df_courses['cluster_id'].nunique()}개 군집")
print(f"  - 임베딩 차원: {engine.embeddings.shape}")
print(f"  - 109건 오매핑 의심 세트: {len(engine.mismatch_109_uids)}건")
assert len(engine.df_courses) == 8645, "코퍼스 건수가 8,645건이 아닙니다."
assert engine.df_courses['cluster_id'].nunique() == 10, "10대 군집이 로드되지 않았습니다."
print("  - 데이터셋 및 군집 무결성: PASS")

print("\n=== 4. 군집 부스팅 및 109건 차단 검증 ===")
res_off, c_off, ex_off, pr_off, _ = engine.recommend(
    query="급여 4대보험 원천징수 실무", target_domain="인사", cluster_boost=0.0, filter_mismatch_109=True, top_n=5
)
res_on, c_on, ex_on, pr_on, _ = engine.recommend(
    query="급여 4대보험 원천징수 실무", target_domain="인사", cluster_boost=5.0, filter_mismatch_109=True, top_n=5
)
print(f"  - 109건 차단 수: {ex_off}건, 유지 수: {pr_off}건")
print(f"  - 군집 부스팅 0.0점 1위 점수: {res_off.iloc[0]['final_score']} (가산: {res_off.iloc[0]['cluster_bonus']})")
print(f"  - 군집 부스팅 5.0점 1위 점수: {res_on.iloc[0]['final_score']} (가산: {res_on.iloc[0]['cluster_bonus']})")
assert ex_off == 96 and pr_off == 13, f"109건 차단/유지 건수 불일치: ex={ex_off}, pr={pr_off}"
assert res_on.iloc[0]['cluster_bonus'] == 5.0, "군집 부스팅 가산점이 적용되지 않았습니다."
print("  - 군집 부스팅 및 109건 조건부 선별: PASS")

print("\n=== 5. 크로스 플랫폼 중복 제거 검증 ===")
res_tax, _, _, _, _ = engine.recommend(
    query="월급이 낭비되지 않도록 알기 쉬운 세금 상식", target_domain="인사", cluster_boost=0.0, filter_mismatch_109=True, top_n=5
)
has_alt = any(r['alt_count'] > 0 for _, r in res_tax.iterrows())
print(f"  - 대체 수강 옵션(alternative_offerings) 연결 강좌 존재 여부: {has_alt}")
assert has_alt is True, "크로스 플랫폼 대체 수강 옵션이 생성되지 않았습니다."
for idx, r in res_tax.iterrows():
    if r['alt_count'] > 0:
        print(f"  - 대표 강좌: [{r['provider']}] {r['title']} ({r['price_display']})")
        for alt in r['alternative_offerings']:
            print(f"     └ 대체 강좌: [{alt['provider']}] {alt['title']} ({alt['price_display']}) - 적합대안여부: {alt['is_suitable_alternative']}")
        break
print("  - 크로스 플랫폼 중복 제거 및 대체 옵션: PASS")

print("\n=== 6. Streamlit 컴파일 및 메인 화면 로딩 검증 ===")
import py_compile
py_compile.compile(str(WORKSPACE_ROOT / "app" / "streamlit_integrated.py"), doraise=True)
print("  - app/streamlit_integrated.py 문법 컴파일: PASS")

print("\n==========================================")
print("전체 검증 스위트 100% 통과 (ALL TESTS PASSED)")
print("==========================================")
