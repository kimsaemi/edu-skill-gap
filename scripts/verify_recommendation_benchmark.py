import sys
import io
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

def main():
    print("=" * 80)
    print(" [검증 1] Ko-SRoBERTa 8,645건 전수 임베딩 행렬 검증")
    print("=" * 80)

    emb_path = "data/hr/output/recommendation/embeddings_ko_sroberta_all.npy"
    embeddings = np.load(emb_path)
    print(f" - 파일 경로: {emb_path}")
    print(f" - 행렬 Shape: {embeddings.shape}")
    print(f" - 총 교육과정 수: {embeddings.shape[0]:,}건")
    print(f" - 임베딩 차원 수: {embeddings.shape[1]}차원")
    print(f" - 결측치(NaN/Inf) 존재 여부: {np.isnan(embeddings).any() or np.isinf(embeddings).any()}")
    print(f" - L2 단위 벡터 정규화 검증 (Norm 평균): {np.linalg.norm(embeddings, axis=1).mean():.4f}")
    print(f" - 데이터 타입: {embeddings.dtype}")

    print("\n" + "=" * 80)
    print(" [검증 2] 대표 쿼리 2건 하이브리드 추천 엔진 Top 3 결과")
    print("  - 가중치: (Ko-SRoBERTa 0.50) + (BM25 0.35) + (평점 보정 0.15)")
    print("  - 3대 결함 보정: Min-Max [0, 100], 베이지안 중립 80점, 동일과정 다회차 중복 제거")
    print("=" * 80)

    # 코퍼스 및 BM25 준비
    df_corpus = pd.read_parquet("data/hr/processed/education_courses_search_cleaned.parquet")
    p_tok = "data/hr/processed/tokenized_corpus_cache.parquet"
    df_tok = pd.read_parquet(p_tok)
    df_all = df_corpus.merge(df_tok, on="course_uid", how="left")
    df_all["tokenized_text"] = df_all["tokenized_text"].fillna("")
    corpus_tokens = [txt.split() for txt in df_all["tokenized_text"]]

    bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
    bm25_vocab = {t for doc_toks in corpus_tokens for t in doc_toks}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f" - 추론 디바이스: {device.upper()}")
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=device)

    benchmark_queries = ["근로기준법 개정", "생성형 AI 업무활용"]

    for q in benchmark_queries:
        # 1) Ko-SRoBERTa 코사인 유사도
        q_vec = model.encode(q, normalize_embeddings=True, device=device)
        dense_sim = np.dot(embeddings, q_vec)
        dense_score = np.clip(dense_sim, 0, 1) * 100.0

        # 2) BM25 키워드 유사도
        q_tokens = [t for t in q.split() if t in bm25_vocab]
        if q_tokens:
            bm25_raw = bm25.get_scores(q_tokens)
            max_b = bm25_raw.max()
            sparse_score = (bm25_raw / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_raw)
        else:
            sparse_score = np.zeros(len(df_all))

        # 3) 베이지안 평점 결측 보정 (80점)
        rating_score = np.full(len(df_all), 80.0)

        # 4) 하이브리드 점수
        final_score = (0.50 * dense_score) + (0.35 * sparse_score) + (0.15 * rating_score)

        res_df = pd.DataFrame({
            "course_uid": df_all["course_uid"],
            "provider": df_all["provider"],
            "title": df_all["title"],
            "category_depth1": df_all["category_depth1"].fillna(""),
            "category_depth2": df_all["category_depth2"].fillna(""),
            "price": pd.to_numeric(df_all["price"], errors="coerce").fillna(0).astype(int),
            "duration_hours": pd.to_numeric(df_all["duration_hours"], errors="coerce").fillna(0),
            "final_hybrid_score": np.round(final_score, 1),
            "ko_sroberta_dense_score": np.round(dense_score, 1),
            "bm25_sparse_score": np.round(sparse_score, 1),
            "url": df_all["url"]
        }).sort_values(by="final_hybrid_score", ascending=False)

        top3 = res_df.drop_duplicates(subset=["provider", "title"]).head(3).reset_index(drop=True)
        top3["rank"] = [1, 2, 3]

        print(f"\n[QUERY] 대표 쿼리: \"{q}\"")
        for _, r in top3.iterrows():
            cat = f"{r['category_depth1']} > {r['category_depth2']}" if r['category_depth1'] else "미분류"
            print(f"  [{r['rank']}위] {r['title']} | 교육기관: {r['provider']}")
            print(f"        - 종합 점수: {r['final_hybrid_score']}점 (Ko-SRoBERTa: {r['ko_sroberta_dense_score']}점(50%), BM25: {r['bm25_sparse_score']}점(35%), 평점보정: 80.0점(15%))")
            print(f"        - 직무 카테고리: {cat} | 교육시간: {r['duration_hours']}시간 | 수강료: {r['price']:,}원")
            print(f"        - 과정 UID: {r['course_uid']}")

if __name__ == "__main__":
    main()
