"""
STEP 3 | 한국어 사전학습 언어모델 임베딩 & 의미 유사도 분석 파이프라인
- 입력: data/processed/hr_courses_detailed_295.csv
- 처리:
    1. 텍스트 정제 (템플릿 커리큘럼·기관 홍보 문구 제거) → 임베딩용 문서 구성
    2. 한국어 문장 임베딩 모델로 295개 과정을 768차원 벡터로 변환 (로컬 CPU, 캐시 저장)
       - ko-sroberta : jhgan/ko-sroberta-multitask (한국어 문장 유사도 학습 모델, 기본 모델)
       - klue-bert   : klue/bert-base (계획서 모델, 문장 유사도 미학습 → 평균 풀링 비교용)
    3. 비교 기준선: BM25(키워드 일치), LSA(TF-IDF → SVD 128차원)
    4. 평가: 단어를 바꿔 쓴 질의 12개로 Hit@5 / Precision@5 / MRR@10 비교
    5. 과정 간 의미 유사도 → 과정별 "비슷한 강의 Top 5"
- 출력:
    data/hr/output/embeddings/       (임베딩 캐시 .npy + 과정 ID 목록)
    data/hr/output/semantic/         (평가 결과, 질의 예시, 유사 강의 목록)
- 실행: .venv/Scripts/python.exe scripts/run_stage3_embedding_pipeline.py [--rebuild] [--models ko-sroberta klue-bert]
"""

import argparse
import io
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.processors.course_text import build_kiwi, clean_courses, make_tokenizer  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_PATH = ROOT / "data" / "processed" / "hr_courses_detailed_295.csv"
EMB_DIR = ROOT / "data" / "hr" / "output" / "embeddings"
OUT_DIR = ROOT / "data" / "hr" / "output" / "semantic"

EMBEDDING_MODELS = {
    "ko-sroberta": "jhgan/ko-sroberta-multitask",
    "klue-bert": "klue/bert-base",
}

# 평가 질의: 강의 제목과 다른 단어로 바꿔 쓴 질문 + 정답 판정용 제목 패턴
EVAL_QUERIES = [
    ("월급 계산이랑 퇴직금 법적 기준 배우고 싶어요", r"급여|임금|노무|퇴직|4대보험"),
    ("직원 뽑을 때 면접 보는 방법", r"채용|면접|인재|선발"),
    ("표 계산 프로그램으로 수식이랑 함수 쓰는 법", r"엑셀|스프레드시트|컴퓨터활용능력|컴활"),
    ("세금 신고랑 장부 정리하는 법", r"세무|회계|부가가치세|재무"),
    ("윗사람에게 올릴 보고서를 잘 쓰고 싶어요", r"보고서|문서|글쓰기|기획서"),
    ("팀원들을 이끄는 팀장의 역량", r"리더|팀장|관리자"),
    ("발표 슬라이드를 깔끔하게 만드는 법", r"파워포인트|프레젠테이션|PPT|ppt"),
    ("해외로 물건 수출할 때 통관 절차", r"무역|통관|물류|수출"),
    ("고객 불만 전화 응대 요령", r"CS|고객|VOC|서비스|민원"),
    ("챗봇으로 반복 업무 줄이기", r"GPT|AI|자동화|생성형|챗봇"),
    ("회사 정보 유출 막는 보안 규정", r"개인정보|CPPG|보안"),
    ("회사 돈 흐름과 재무제표 읽는 법", r"재무|회계|재무제표"),
]

# 계획서 예시 질의 (결과 예시 저장용)
DEMO_QUERIES = [
    "월급 계산이랑 퇴직금 법적 기준 배우고 싶어요",
    "스타트업 총무 신입인데 비품 계약이랑 사무 문서 작성이 너무 막막해요",
    "취업 스펙용으로 엑셀 실기 자격증 따고 싶어요",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="임베딩 캐시를 무시하고 다시 계산")
    parser.add_argument("--models", nargs="*", default=list(EMBEDDING_MODELS), choices=list(EMBEDDING_MODELS))
    return parser.parse_args()


def embedding_text(courses):
    """임베딩 입력: 제목 + 정제 소개글 + 실제 커리큘럼 (모델 최대 길이에 맞춰 앞부분 위주)"""
    return (
        courses["base_title"] + ". " + courses["overview_clean"].str[:400] + " " + courses["syllabus_clean"].str[:150]
    ).str.strip().tolist()


def load_or_encode(key, texts, course_ids, rebuild):
    """임베딩 캐시가 있고 과정 ID가 같으면 재사용, 아니면 모델로 인코딩 후 저장"""
    emb_path = EMB_DIR / f"course_embeddings_{key}.npy"
    ids_path = EMB_DIR / "course_ids.csv"
    if not rebuild and emb_path.exists() and ids_path.exists():
        cached_ids = pd.read_csv(ids_path)["id"].tolist()
        if cached_ids == course_ids:
            print(f"    - {key}: 캐시 사용 ({emb_path.name})")
            return np.load(emb_path), load_model(key)

    model = load_model(key)
    vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    np.save(emb_path, vectors.astype(np.float32))
    pd.DataFrame({"id": course_ids}).to_csv(ids_path, index=False)
    print(f"    - {key}: {vectors.shape[0]}개 × {vectors.shape[1]}차원 인코딩 완료 → {emb_path.name}")
    return vectors, model


_model_cache = {}


def load_model(key):
    from sentence_transformers import SentenceTransformer

    if key not in _model_cache:
        # klue/bert-base는 sentence-transformers 설정이 없어 자동으로 평균 풀링(mean pooling)이 붙음
        _model_cache[key] = SentenceTransformer(EMBEDDING_MODELS[key], device="cpu")
    return _model_cache[key]


def ranking_metrics(scores, relevant, k_hit=5, k_mrr=10):
    order = np.argsort(-scores)
    top_hit = relevant[order[:k_hit]]
    ranks = np.flatnonzero(relevant[order[:k_mrr]])
    return {
        f"hit@{k_hit}": float(top_hit.any()),
        f"precision@{k_hit}": float(top_hit.mean()),
        f"mrr@{k_mrr}": float(1 / (ranks[0] + 1)) if len(ranks) else 0.0,
    }


def main():
    args = parse_args()

    # 1. 데이터 로드 및 정제
    courses = clean_courses(pd.read_csv(DATA_PATH))
    course_ids = courses["id"].tolist()
    texts = embedding_text(courses)
    print(f"[1/5] 데이터 로드·정제 완료: {len(courses)}개 과정 (임베딩 입력 평균 {np.mean([len(t) for t in texts]):.0f}자)")

    # 2. 기준선: BM25 / LSA
    tokenize = make_tokenizer(build_kiwi())
    doc_tokens = [tokenize(d) for d in courses["doc"]]
    bm25 = BM25Okapi(doc_tokens, k1=1.5, b=0.75)
    tfidf_vec = TfidfVectorizer(
        tokenizer=lambda toks: toks,
        preprocessor=lambda toks: toks,
        lowercase=False,
        token_pattern=None,
        min_df=2,
        max_df=0.5,
        sublinear_tf=True,
    )
    tfidf = tfidf_vec.fit_transform(doc_tokens)
    svd = TruncatedSVD(n_components=128, random_state=42)
    lsa_vectors = svd.fit_transform(tfidf)
    lsa_vectors /= np.linalg.norm(lsa_vectors, axis=1, keepdims=True) + 1e-12
    print("[2/5] 기준선 구축 완료: BM25, LSA(128차원)")

    # 3. 언어모델 임베딩
    print("[3/5] 한국어 언어모델 임베딩 (최초 실행 시 모델 다운로드)")
    embeddings, models = {}, {}
    for key in args.models:
        embeddings[key], models[key] = load_or_encode(key, texts, course_ids, args.rebuild)

    # 검색 방식별 점수 함수: 질의 → 295개 과정 점수
    def score_bm25(query):
        return np.asarray(bm25.get_scores(tokenize(query)))

    def score_lsa(query):
        q = svd.transform(tfidf_vec.transform([tokenize(query)]))
        q /= np.linalg.norm(q) + 1e-12
        return (lsa_vectors @ q.T).ravel()

    def make_dense_scorer(key):
        def score(query):
            q = models[key].encode([query], normalize_embeddings=True)
            return (embeddings[key] @ q.T).ravel()

        return score

    scorers = {"BM25 (키워드)": score_bm25, "LSA (기존 방식)": score_lsa}
    for key in args.models:
        scorers[f"{key} (언어모델)"] = make_dense_scorer(key)

    # 4. 평가
    titles = courses["base_title"]
    eval_rows = []
    for query, pattern in EVAL_QUERIES:
        relevant = titles.str.contains(pattern, regex=True).to_numpy()
        for method, scorer in scorers.items():
            eval_rows.append(
                {"query": query, "method": method, "n_relevant": int(relevant.sum()), **ranking_metrics(scorer(query), relevant)}
            )
    eval_detail = pd.DataFrame(eval_rows)
    eval_summary = (
        eval_detail.groupby("method", sort=False)[["hit@5", "precision@5", "mrr@10"]].mean().round(3).reset_index()
    )
    print("[4/5] 검색 방식별 평가 (질의 12개 평균, 정답 = 제목에 관련 단어 포함)")
    print(eval_summary.to_string(index=False))

    # 5. 결과 저장
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    eval_detail.to_csv(OUT_DIR / "retrieval_eval_detail.csv", index=False, encoding="utf-8-sig")
    eval_summary.to_csv(OUT_DIR / "retrieval_eval_summary.csv", index=False, encoding="utf-8-sig")

    demo_rows = []
    for query in DEMO_QUERIES:
        for method, scorer in scorers.items():
            scores = scorer(query)
            for rank, idx in enumerate(np.argsort(-scores)[:5], 1):
                demo_rows.append(
                    {
                        "query": query,
                        "method": method,
                        "rank": rank,
                        "id": course_ids[idx],
                        "course_title": courses["course_title"].iat[idx],
                        "score": round(float(scores[idx]), 4),
                    }
                )
    pd.DataFrame(demo_rows).to_csv(OUT_DIR / "semantic_search_examples.csv", index=False, encoding="utf-8-sig")

    # 기본 모델 기준 과정별 비슷한 강의 Top 5 (같은 강의의 다른 회차는 제외)
    best_key = args.models[0] if args.models else "lsa"
    best_vectors = embeddings[best_key] if args.models else lsa_vectors
    sim = best_vectors @ best_vectors.T
    similar_rows = []
    for i in range(len(courses)):
        same_course = (titles == titles.iat[i]).to_numpy()
        candidates = [j for j in np.argsort(-sim[i]) if not same_course[j]][:5]
        for rank, j in enumerate(candidates, 1):
            similar_rows.append(
                {
                    "id": course_ids[i],
                    "course_title": courses["course_title"].iat[i],
                    "rank": rank,
                    "similar_id": course_ids[j],
                    "similar_title": courses["course_title"].iat[j],
                    "cosine_similarity": round(float(sim[i, j]), 4),
                }
            )
    pd.DataFrame(similar_rows).to_csv(OUT_DIR / f"similar_courses_top5_{best_key}.csv", index=False, encoding="utf-8-sig")
    print(f"[5/5] 저장 완료: {OUT_DIR.relative_to(ROOT)}")

    print("\n[예시] 계획서 질의 Top 3 비교")
    for query in DEMO_QUERIES[:1]:
        print(f'질의: "{query}"')
        for method, scorer in scorers.items():
            top = np.argsort(-scorer(query))[:3]
            print(f"  {method}: " + " | ".join(re.sub(r"\s+", " ", courses['base_title'].iat[i])[:30] for i in top))


if __name__ == "__main__":
    main()
