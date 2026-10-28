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
    print(" [검증] 세부 조건 필터링(Faceted Filtering) & 추천 파이프라인 연계 테스트")
    print("=" * 80)

    # 1. 데이터 및 모델 로드
    p_clean = "data/hr/processed/education_courses_search_cleaned.parquet"
    p_tok = "data/hr/processed/tokenized_corpus_cache.parquet"
    p_emb = "data/hr/output/recommendation/embeddings_ko_sroberta_all.npy"

    df_corpus = pd.read_parquet(p_clean)
    df_tok = pd.read_parquet(p_tok)
    df_corpus = df_corpus.merge(df_tok, on="course_uid", how="left")
    df_corpus["tokenized_text"] = df_corpus["tokenized_text"].fillna("")
    corpus_tokens = [txt.split() for txt in df_corpus["tokenized_text"]]

    bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
    bm25_voc = {t for doc_toks in corpus_tokens for t in doc_toks}

    embeddings = np.load(p_emb)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=device)

    # 2. Faceted Metadata 생성
    def map_platform(row):
        p = str(row.get("provider", "")).upper()
        sp = str(row.get("source_provider", "")).upper()
        uid = str(row.get("course_uid", "")).upper()
        if "GSEEK" in p or "GSEEK" in sp or uid.startswith("GSEEK"):
            return "GSEEK"
        elif "HUNET" in p or "HUNET" in sp or "휴넷" in p or uid.startswith("HUNET"):
            return "휴넷"
        elif "KMA" in p or "KMA" in sp or "한국능률협회" in p or uid.startswith("KMA"):
            return "KMA"
        elif "KPC" in p or "KPC" in sp or "한국생산성본부" in p or uid.startswith("KPC"):
            return "KPC"
        elif "MULTICAMPUS" in sp or "멀티캠퍼스" in p or "패스트캠퍼스" in p:
            return "패스트캠퍼스"
        else:
            return "고용24"

    df_corpus["platform_label"] = df_corpus.apply(map_platform, axis=1)
    df_corpus["numeric_price"] = pd.to_numeric(df_corpus["price"], errors="coerce").fillna(0).astype(int)
    
    def map_edu_type(row):
        et = str(row.get("education_type", "")).strip()
        if any(k in et for k in ["온라인", "이러닝", "원격", "비대면"]):
            return "온라인/이러닝"
        elif any(k in et for k in ["오프라인", "집합"]):
            return "오프라인/집합"
        else:
            return "온라인/이러닝"

    df_corpus["edu_type_cat"] = df_corpus.apply(map_edu_type, axis=1)
    hours = pd.to_numeric(df_corpus["duration_hours"], errors="coerce").fillna(0)
    
    def map_duration(h):
        if h < 10:
            return "단기 (10시간 미만)"
        elif h < 40:
            return "중기 (10~40시간)"
        else:
            return "장기 (40시간 이상)"

    df_corpus["duration_cat"] = hours.apply(map_duration)

    def map_difficulty(row):
        d = str(row.get("difficulty", "")).strip()
        t = str(row.get("title", "")) + " " + str(row.get("target_audience", ""))
        if any(k in d for k in ["고급"]) or any(k in t for k in ["팀장", "관리자", "임원", "리더", "고급", "심화", "전략"]):
            return "관리자/심화"
        elif any(k in d for k in ["중급"]) or any(k in t for k in ["실무", "실전", "현업", "중급", "프로세스", "기획"]):
            return "실무"
        else:
            return "입문"

    df_corpus["difficulty_cat"] = df_corpus.apply(map_difficulty, axis=1)

    # 3. 2가지 시나리오 필터링 파이프라인 테스트
    test_cases = [
        {
            "name": "시나리오 A: [근로기준법 개정] + 무료 + 온라인 + 입문/실무",
            "query": "근로기준법 개정",
            "platforms": ["고용24", "KPC", "KMA", "휴넷", "패스트캠퍼스", "GSEEK"],
            "free_only": True,
            "max_budget": 0,
            "edu_type": "온라인/이러닝",
            "durations": ["단기 (10시간 미만)", "중기 (10~40시간)"],
            "difficulties": ["입문", "실무"]
        },
        {
            "name": "시나리오 B: [생성형 AI 업무활용] + KPC/KMA + 유료 오프라인 + 실무/관리자",
            "query": "생성형 AI 업무활용",
            "platforms": ["KPC", "KMA"],
            "free_only": False,
            "max_budget": 1000000,
            "edu_type": "오프라인/집합",
            "durations": ["단기 (10시간 미만)", "중기 (10~40시간)", "장기 (40시간 이상)"],
            "difficulties": ["실무", "관리자/심화"]
        }
    ]

    for tc in test_cases:
        print(f"\n========================================================")
        print(f"테스트: {tc['name']}")
        print(f"========================================================")

        # 1) 필터링
        mask = (
            df_corpus["platform_label"].isin(tc["platforms"]) &
            df_corpus["duration_cat"].isin(tc["durations"]) &
            df_corpus["difficulty_cat"].isin(tc["difficulties"])
        )
        if tc["free_only"]:
            mask &= (df_corpus["numeric_price"] == 0)
        else:
            mask &= (df_corpus["numeric_price"] <= tc["max_budget"])

        if tc["edu_type"] != "전체":
            mask &= (df_corpus["edu_type_cat"] == tc["edu_type"])

        cand_indices = np.where(mask)[0]
        print(f"1. 필터링 통과 후보군: {len(cand_indices):,}건 / {len(df_corpus):,}건 ({len(cand_indices)/len(df_corpus)*100:.1f}%)")

        if len(cand_indices) == 0:
            print("  - 후보군 없음!")
            continue

        # 2) 후보군 대상 하이브리드 점수 연산
        q = tc["query"]
        q_vec = model.encode(q, normalize_embeddings=True, device=device)
        cand_emb = embeddings[cand_indices]
        dense_sims = np.dot(cand_emb, q_vec)
        dense_scores = np.clip(dense_sims, 0, 1) * 100.0

        q_toks = [t for t in q.split() if t in bm25_voc]
        if q_toks:
            bm25_raw_all = bm25.get_scores(q_toks)
            bm25_cand = bm25_raw_all[cand_indices]
            max_b = bm25_cand.max()
            sparse_scores = (bm25_cand / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_cand)
        else:
            sparse_scores = np.zeros(len(cand_indices))

        rating_scores = np.full(len(cand_indices), 80.0)
        final_scores = (0.50 * dense_scores) + (0.35 * sparse_scores) + (0.15 * rating_scores)

        # 3) Top-N 정렬
        cand_df = df_corpus.iloc[cand_indices].copy()
        cand_df["final_hybrid_score"] = np.round(final_scores, 1)
        cand_df["ko_sroberta_dense_score"] = np.round(dense_scores, 1)
        cand_df["bm25_sparse_score"] = np.round(sparse_scores, 1)
        cand_df = cand_df.sort_values(by="final_hybrid_score", ascending=False)

        # 4) 다회차 중복 제거
        dedup_df = cand_df.drop_duplicates(subset=["provider", "title"]).head(3).reset_index(drop=True)
        dedup_df["rank"] = [1, 2, 3]

        print(f"2. 하이브리드 추천 연산 및 중복 제거 후 Top 3 결과:")
        for _, r in dedup_df.iterrows():
            print(f"  [{r['rank']}위] {r['title']} ({r['provider']})")
            print(f"        - 점수: {r['final_hybrid_score']}점 (Ko-SRoBERTa: {r['ko_sroberta_dense_score']}점, BM25: {r['bm25_sparse_score']}점)")
            print(f"        - 속성: {r['platform_label']} | {r['edu_type_cat']} | {r['duration_cat']} | {r['difficulty_cat']} | 수강료: {r['numeric_price']:,}원")

if __name__ == "__main__":
    main()
