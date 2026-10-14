"""
STEP 3 & 4 | 의미 유사도(Semantic Similarity, LSA Dense) & BM25 하이브리드 AI 추천 엔진
- 원리:
    1. Sparse 검색: BM25 (키워드 정확도 매칭)
    2. Dense 의미 검색: Latent Semantic Analysis (LSA / SVD 128차원)
       - 글자가 달라도 동일 문맥(월급 ↔ 급여 ↔ 4대보험)을 벡터 공간의 각도(코사인 유사도)로 계산
    3. 품질 보정: 수강생 만족도 평점
- 최종 스코어링:
    최종 추천 점수 = 0.50 * Dense 의미 유사도 + 0.35 * Sparse BM25 점수 + 0.15 * 수강생 평점
"""

import io
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 1. 데이터 로드
input_csv = Path("data/processed/hr_courses_detailed_295.csv")
clusters_csv = Path("data/hr/output/text_analysis/course_keywords_clusters_k8.csv")
df_raw = pd.read_csv(input_csv)
df_clust = pd.read_csv(clusters_csv) if clusters_csv.exists() else None

print(f"[1/5] 데이터 로드 완료: {len(df_raw)}개 과정")

# 2. 텍스트 정제 및 문서 결합
template_marker = "핵심 프로세스 실습 // 실무 서식 작성"


def strip_session_suffix(title):
    return re.sub(r"\s*\([^()]*(\([^()]*\))?[^()]*\d+회차\)\s*$", "", title).strip()


def clean_syllabus(text):
    if template_marker in str(text):
        return ""
    text = re.sub(r"총시간\s*\(\s*\d+\s*시간\s*\)", " ", str(text))
    return re.sub(r"\(\s*\d+\s*시간\s*\)", " ", text).strip()


df_raw["base_title"] = df_raw["course_title"].map(strip_session_suffix)
df_raw["clean_syl"] = df_raw["syllabus_text"].map(clean_syllabus)
# 제목(가중치 x2) + 소개글 + 목차
df_raw["doc"] = (
    (df_raw["base_title"] + " ") * 2 + df_raw["overview"].fillna("").str[:150] + " " + df_raw["clean_syl"]
)

# 3. Kiwi 형태소 분석 및 토큰화
kiwi = Kiwi()
hr_user_words = [
    "통상임금", "4대보험", "연말정산", "원천징수", "근로기준법", "주52시간", "퇴직급여", "퇴직연금",
    "인적자원관리", "인사노무", "다면평가", "성과관리", "역량면접", "온보딩", "컴활", "컴퓨터활용능력",
    "전산회계", "전산세무", "부가가치세", "재무제표", "고정자산", "비품관리", "공문서", "개인정보",
    "사무행정", "물류관리", "유통관리", "취업규칙", "임금대장", "연차휴가", "비품구매", "사무문서",
]
for _word in hr_user_words:
    kiwi.add_user_word(_word, "NNP")

noun_tags = {"NNG", "NNP"}
stopwords = set(
    """강의 강좌 과정 교육 훈련 실무 이해 학습 수강 수강생 기초 기본 활용 방법 내용 관련 필요 능력 역량
    업무 직무 직장인 실습 프로세스 목표 기대 효과 학습자 대상 분야 기술 지식 향상 습득 수행 제공 사례 실제
    중심 기반 대비 올인원 왕초보 초보 입문 마스터 정복 완전정복 노하우 개념 흐름 제고 기능 사용 시간 변화
    스킬 수립 시대 훈련생 프로그램 단계 설명 중요 중요성 포인트 강사 장비 배정 지정 실전 예제 상황 직장
    이론 방안 부분 다양 가능 이상 이후 핵심 완벽 최신 온라인 진행 운영 하나 가지 처음 누구 이제 지금
    모든 각종 전반 여러분 우리 자신 정도 경우 위주 구성 통해 위해 대한 수업 강화 체계 완성 노하우 비법 공략
    총시간 회차 인증 우수 기관 적용 파악 주요 정리 구체 의미 비교 문제 관리 plus up basic""".split()
)


def tokenize(text):
    tokens = []
    prev = None
    for tok in kiwi.tokenize(str(text)):
        is_noun = tok.tag in noun_tags
        if is_noun or tok.tag == "SL":
            form = tok.form.lower()
            if len(form) >= 2 and form not in stopwords:
                tokens.append(form)
        if is_noun and prev is not None and prev.start + prev.len == tok.start:
            compound = prev.form + tok.form
            if compound not in stopwords:
                tokens.append(compound)
        prev = tok if is_noun else None
    return tokens


doc_tokens = [tokenize(d) for d in df_raw["doc"]]
print("[2/5] Kiwi 형태소 분석 및 토큰화 완료")

# 4. Dense 의미 모델 (LSA: TF-IDF -> TruncatedSVD 128차원)
vectorizer_args = dict(
    tokenizer=lambda toks: toks,
    preprocessor=lambda toks: toks,
    lowercase=False,
    token_pattern=None,
    min_df=2,
    max_df=0.5,
)
tfidf_vec = TfidfVectorizer(sublinear_tf=True, **vectorizer_args)
tfidf_matrix = tfidf_vec.fit_transform(doc_tokens)

# 128차원 잠재 의미 공간으로 압축 (Dense Semantic Vectors)
n_components = min(128, tfidf_matrix.shape[1] - 1)
svd = TruncatedSVD(n_components=n_components, random_state=42)
course_dense_vectors = svd.fit_transform(tfidf_matrix)
# L2 정규화 (코사인 유사도 연산 최적화)
norms = np.linalg.norm(course_dense_vectors, axis=1, keepdims=True) + 1e-9
course_dense_vectors = course_dense_vectors / norms

# 5. Sparse 키워드 모델 (BM25)
bm25 = BM25Okapi(doc_tokens, k1=1.5, b=0.75)
print(f"[3/5] LSA 의미 벡터({n_components}차원) 및 BM25 인덱싱 완료")


# 6. 하이브리드 추천 함수
def recommend_courses(query: str, top_k: int = 3, max_budget: int = None):
    # (1) 쿼리 토큰화
    q_tokens = tokenize(query)
    if not q_tokens:
        q_tokens = [tok.form.lower() for tok in kiwi.tokenize(query) if len(tok.form) >= 2]

    # (2) Dense 의미 유사도 (LSA 코사인 유사도)
    q_tfidf = tfidf_vec.transform([q_tokens])
    q_dense = svd.transform(q_tfidf)
    q_dense_norm = q_dense / (np.linalg.norm(q_dense, axis=1, keepdims=True) + 1e-9)
    semantic_sims = cosine_similarity(q_dense_norm, course_dense_vectors).ravel()
    # 0~1 스케일링
    dense_scores = np.clip(semantic_sims, 0.0, 1.0)

    # (3) Sparse 키워드 점수 (BM25)
    bm25_raw = np.array(bm25.get_scores(q_tokens))
    bm25_norm = bm25_raw / (bm25_raw.max() + 1e-6) if bm25_raw.max() > 0 else bm25_raw

    # (4) 수강생 만족도 점수 (Quality)
    ratings = df_raw["satisfaction_score_100"].fillna(80.0).values / 100.0

    # (5) 하이브리드 스코어 결합 (0~100점)
    hybrid_score = (0.50 * dense_scores) + (0.35 * bm25_norm) + (0.15 * ratings)

    res = df_raw.copy()
    res["semantic_sim"] = (dense_scores * 100).round(1)
    res["bm25_score"] = (bm25_norm * 100).round(1)
    res["satisfaction"] = df_raw["satisfaction_score_100"].fillna(0).astype(int)
    res["final_score"] = (hybrid_score * 100).round(1)

    if df_clust is not None:
        res["top_keywords"] = df_clust["top_keywords"]
        res["cluster"] = df_clust["cluster"]

    if max_budget is not None:
        res = res[res["cost"] <= max_budget]

    return res.sort_values("final_score", ascending=False).head(top_k)


print("\n" + "=" * 75)
print(" 🚀 [3·4단계 실전 테스트] 사용자 맞춤형 AI 하이브리드 추천 결과")
print("=" * 75)

test_scenarios = [
    {
        "role": "스타트업 총무 신입사원",
        "query": "사무용 비품 구매 계약이랑 회사 기획 문서, 공문서 작성법 배우고 싶어요",
    },
    {
        "role": "인사담당 1년 차",
        "query": "직원 월급 주는 법이랑 퇴직금, 4대보험 법적 기준 계산을 체계적으로 알고 싶습니다",
    },
    {
        "role": "취업준비생",
        "query": "취업 스펙용으로 엑셀 실기 자격증 따고 데이터 다루는 법을 마스터하고 싶어요",
    },
]

for idx, sc in enumerate(test_scenarios, 1):
    print(f"\n[시나리오 {idx}] {sc['role']}")
    print(f"질의: \"{sc['query']}\"")
    print("-" * 75)
    top_courses = recommend_courses(sc["query"], top_k=3)
    for rank, (_, row) in enumerate(top_courses.iterrows(), 1):
        cost_str = "무료" if row["cost"] == 0 else f"{int(row['cost']):,}원"
        print(f"  {rank}위. {row['course_title']}")
        print(f"       기관: {row['institution']} ({row['platform']}) | 시간: {row['training_hours']}H | 비용: {cost_str}")
        print(f"       ★ 종합추천: {row['final_score']}점 [의미일치 {row['semantic_sim']}% / 키워드일치 {row['bm25_score']}% / 만족도 {row['satisfaction']}점]")
        if "top_keywords" in row and pd.notna(row["top_keywords"]):
            print(f"       태그: #{row['top_keywords'].replace(', ', ' #')}")
print("=" * 75)

out_dir = Path("data/hr/output/recommendation")
out_dir.mkdir(parents=True, exist_ok=True)
# 벤치마크 결과 저장
benchmark_rows = []
for sc in test_scenarios:
    top = recommend_courses(sc["query"], top_k=3)
    for r_idx, (_, row) in enumerate(top.iterrows(), 1):
        benchmark_rows.append({
            "scenario": sc["role"],
            "query": sc["query"],
            "rank": r_idx,
            "course_title": row["course_title"],
            "platform": row["platform"],
            "final_score": row["final_score"],
            "semantic_sim": row["semantic_sim"],
            "bm25_score": row["bm25_score"],
        })
pd.DataFrame(benchmark_rows).to_csv(out_dir / "hybrid_recommendation_benchmark.csv", index=False, encoding="utf-8-sig")
print(f"\n[저장 완료] 벤치마크 결과가 {out_dir / 'hybrid_recommendation_benchmark.csv'} 에 저장되었습니다.")
