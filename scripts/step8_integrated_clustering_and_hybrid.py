"""
STEP 8: 통합 교육과정 코퍼스 대상 군집화(K-Means k=5,6,8,10,12 비교), 
토픽 분석, 하이브리드 추천 엔진(LSA+BM25+평점 개선) 구현 및 다차원 집계 스크립트
- 입력:
    - data/hr/processed/education_courses_search_cleaned.parquet (8,645건)
    - data/hr/processed/tokenized_corpus_cache.parquet (8,645건 Kiwi 토큰화 캐시)
    - data/hr/output/recommendation/course_competency_long.parquet (역량 매핑)
- 출력:
    - data/hr/output/recommendation/cluster_metrics_comparison_k_values.csv
    - data/hr/output/recommendation/integrated_cluster_summary_k8.csv
    - data/hr/output/recommendation/integrated_course_clusters_k8.csv
    - data/hr/output/recommendation/integrated_cluster_top10_keywords.csv
    - data/hr/output/recommendation/integrated_cluster_rep_courses.csv
    - data/hr/output/recommendation/hybrid_recommendation_evaluated_benchmark.csv
    - data/hr/reports/integrated_clustering_and_hybrid_report.json
"""

import os
import re
import json
import time
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import silhouette_score
from rank_bm25 import BM25Okapi

def run_clustering_and_hybrid():
    start_time = time.time()
    workspace_root = Path(__file__).resolve().parent.parent
    out_dir = workspace_root / "data" / "hr" / "output" / "recommendation"
    reports_dir = workspace_root / "data" / "hr" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("STEP 8: 통합 데이터(8,645건) 기반 군집화·토픽 분석 및 하이브리드 추천 고도화")
    print("=" * 80)

    # 1. 데이터 로드
    p_cleaned = workspace_root / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
    p_token_cache = workspace_root / "data" / "hr" / "processed" / "tokenized_corpus_cache.parquet"
    p_comp_long = out_dir / "course_competency_long.parquet"

    df_courses = pd.read_parquet(p_cleaned)
    df_tokens = pd.read_parquet(p_token_cache)
    df_comp = pd.read_parquet(p_comp_long) if p_comp_long.exists() else pd.DataFrame()

    print(f"1. 데이터 로드 완료: 전체 코퍼스 {len(df_courses):,}건")
    
    # 토큰 데이터 조인
    df_all = df_courses.merge(df_tokens, on="course_uid", how="left")
    df_all["tokenized_text"] = df_all["tokenized_text"].fillna("")

    # 실험 대상: 인사·총무·경영지원 관련 매핑이 있거나 텍스트 품질이 RICH/MODERATE인 코퍼스 (우선 상세내용 충분 강좌 중심)
    # 전체 8,645건에 대해 군집화 및 검색 인덱스를 구성하되, 분석 실험 시 하위군 통계도 동시 산출
    corpus_tokens = [txt.split() for txt in df_all["tokenized_text"]]

    # 2. TF-IDF 벡터화 (Kiwi 사전 토큰 활용)
    print("2. TF-IDF 벡터화 중 (최소 빈도 3, 최대 문서빈도 60%)...")
    tfidf_vec = TfidfVectorizer(
        tokenizer=lambda x: x,
        preprocessor=lambda x: x,
        lowercase=False,
        token_pattern=None,
        min_df=3,
        max_df=0.6,
        sublinear_tf=True
    )
    tfidf_matrix = tfidf_vec.fit_transform(corpus_tokens)
    vocab = tfidf_vec.get_feature_names_out()
    print(f" - TF-IDF 어휘 크기: {len(vocab):,}개 (행렬 shape: {tfidf_matrix.shape})")

    # 3. K-Means k값 비교 (k = 5, 6, 8, 10, 12)
    print("\n3. K-Means 군집 수(k) 후보군 비교 평가 중 (k in [5, 6, 8, 10, 12])...")
    k_candidates = [5, 6, 8, 10, 12]
    k_comparison_rows = []
    kmeans_models = {}

    for k in k_candidates:
        t_k = time.time()
        km = KMeans(n_clusters=k, n_init=5, random_state=42)
        labels = km.fit_predict(tfidf_matrix)
        kmeans_models[k] = (km, labels)
        
        # 샘플 2,000건 기반 코사인 실루엣 점수 고속 산출 (전수 8,645건 실루엣 연산 최적화)
        sample_indices = np.random.RandomState(42).choice(len(df_all), size=min(2500, len(df_all)), replace=False)
        sil_sample = silhouette_score(
            tfidf_matrix[sample_indices],
            labels[sample_indices],
            metric="cosine"
        )
        
        # 최소/최대 군집 크기
        bincounts = np.bincount(labels)
        min_size, max_size = int(bincounts.min()), int(bincounts.max())
        
        k_comparison_rows.append({
            "k": k,
            "silhouette_cosine": round(sil_sample, 4),
            "inertia": round(km.inertia_, 1),
            "min_cluster_size": min_size,
            "max_cluster_size": max_size,
            "size_ratio_max_to_min": round(max_size / max(1, min_size), 1),
            "elapsed_sec": round(time.time() - t_k, 2)
        })
        print(f" - k={k:2d}: 실루엣(코사인)={sil_sample:.4f}, 관성(Inertia)={km.inertia_:.1f}, "
              f"최소군집={min_size}, 최대군집={max_size} ({time.time() - t_k:.1f}초)")

    df_k_comp = pd.DataFrame(k_comparison_rows)
    df_k_comp.to_csv(out_dir / "cluster_metrics_comparison_k_values.csv", index=False, encoding="utf-8-sig")

    # 4. 기본 후보 k=8 상세 분석 (팀원 k=8 직무 분류와 일치 및 연계)
    print("\n4. 기준 모델 k=8 기반 상세 토픽 및 군집 분석...")
    km_8, labels_8 = kmeans_models[8]
    df_all["cluster_k8"] = labels_8
    
    # TruncatedSVD로 중심점 및 강좌별 코사인 거리 연산
    svd = TruncatedSVD(n_components=100, random_state=42)
    lsa_matrix = svd.fit_transform(tfidf_matrix)
    # L2 정규화
    lsa_norm = np.linalg.norm(lsa_matrix, axis=1, keepdims=True)
    lsa_norm[lsa_norm == 0] = 1.0
    lsa_matrix = lsa_matrix / lsa_norm

    # 군집별 중심점(Centroid) 계산
    dense_tfidf = tfidf_matrix.toarray()
    cluster_k8_rows = []
    cluster_top10_keywords_rows = []
    cluster_rep_courses_rows = []

    # 군집 이름은 결과에서 나온 대표 키워드 상위 3개로 자동 생성한다.
    # (예전에는 번호별로 이름을 미리 정해 두어, 실제 내용과 이름이 어긋났다.
    #  K-Means 번호는 데이터가 바뀌면 달라지므로 고정 이름을 붙이면 안 된다.)

    for c_id in range(8):
        mask = labels_8 == c_id
        n_courses = int(mask.sum())
        
        # c-TF-IDF 기반 군집 차별화 키워드 산출
        mean_in = dense_tfidf[mask].mean(axis=0)
        mean_out = dense_tfidf[~mask].mean(axis=0)
        diff_score = mean_in - 0.4 * mean_out
        top_kw_indices = np.argsort(-diff_score)[:10]
        top_kws = [vocab[idx] for idx in top_kw_indices]

        # 군집 중심점과의 코사인 거리 기준 대표 강좌 5개 추출
        c_centroid = mean_in / (np.linalg.norm(mean_in) + 1e-9)
        c_sims = np.dot(dense_tfidf[mask], c_centroid)
        best_in_mask_idx = np.argsort(-c_sims)[:5]
        rep_courses_df = df_all[mask].iloc[best_in_mask_idx]

        rep_titles = rep_courses_df["title"].tolist()
        
        # 요약 행
        cluster_k8_rows.append({
            "cluster_id": c_id,
            "temporary_name": f"클러스터 {c_id} (자동 명명): {' · '.join(top_kws[:3])}",
            "is_official_ncs": False,
            "n_courses": n_courses,
            "ratio_pct": round(n_courses / len(df_all) * 100, 2),
            "top_10_keywords": ", ".join(top_kws),
            "example_titles": " | ".join(rep_titles[:3])
        })

        for rank, kw in enumerate(top_kws, 1):
            cluster_top10_keywords_rows.append({
                "cluster_id": c_id,
                "rank": rank,
                "keyword": kw,
                "score": round(float(diff_score[top_kw_indices[rank-1]]), 4)
            })

        for r_rank, (_, r_course) in enumerate(rep_courses_df.iterrows(), 1):
            cluster_rep_courses_rows.append({
                "cluster_id": c_id,
                "representative_rank": r_rank,
                "course_uid": r_course["course_uid"],
                "provider": r_course["provider"],
                "title": r_course["title"],
                "price": r_course["price"],
                "duration_hours": r_course["duration_hours"],
                "centroid_cosine_similarity": round(float(c_sims[best_in_mask_idx[r_rank-1]]), 4)
            })

    df_c8_summary = pd.DataFrame(cluster_k8_rows)
    df_c8_top10 = pd.DataFrame(cluster_top10_keywords_rows)
    df_c8_rep = pd.DataFrame(cluster_rep_courses_rows)

    df_c8_summary.to_csv(out_dir / "integrated_cluster_summary_k8.csv", index=False, encoding="utf-8-sig")
    df_c8_top10.to_csv(out_dir / "integrated_cluster_top10_keywords.csv", index=False, encoding="utf-8-sig")
    df_c8_rep.to_csv(out_dir / "integrated_cluster_rep_courses.csv", index=False, encoding="utf-8-sig")

    # 강좌별 군집 라벨 저장 (메타데이터 포함)
    df_all_clusters = df_all[[
        "course_uid", "provider", "title", "category_depth1", "category_depth2",
        "price", "duration_hours", "cluster_k8"
    ]].copy()
    cluster_name_map = {r["cluster_id"]: r["temporary_name"] for r in cluster_k8_rows}
    df_all_clusters["temporary_cluster_name"] = df_all_clusters["cluster_k8"].map(cluster_name_map)
    df_all_clusters.to_csv(out_dir / "integrated_course_clusters_k8.csv", index=False, encoding="utf-8-sig")

    print(" - [완료] k=8 군집 요약 및 강좌별 클러스터 매핑 CSV 생성 완료")

    # 5. 하이브리드 추천 엔진 검토 및 벤치마크 (LSA + BM25 + 평점 신뢰성 보정)
    print("\n5. 하이브리드 추천 엔진 검토 및 시나리오 벤치마크...")
    
    # BM25 초기화
    bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
    bm25_vocab = {t for toks in corpus_tokens for t in toks}

    # 평가 질문 시나리오 (팀원 3대 시나리오 + 인사총무 실무 2대 시나리오 = 총 5개)
    eval_scenarios = [
        ("스타트업 총무 신입사원", "사무용 비품 구매 계약이랑 회사 기획 문서, 공문서 작성법 배우고 싶어요", "총무"),
        ("인사담당 1년 차", "직원 월급 주는 법이랑 퇴직금, 4대보험 법적 기준 계산을 체계적으로 알고 싶습니다", "인사"),
        ("취업준비생", "취업 스펙용으로 엑셀 실기 자격증 따고 데이터 다루는 법을 마스터하고 싶어요", "OA/사무"),
        ("노무 리스크 관리자", "근로기준법 개정사항 및 취업규칙 작성 노무관리 핵심 실무", "노무"),
        ("팀장/관리자", "직무분석 및 KPI 성과평가 보상체계 설계 관리자 워크숍", "인사평가")
    ]

    hybrid_results = []
    
    # 평점 처리 원칙: 실제 평점이 없으므로 점수에 반영하지 않는다 (아래 3번 참고)

    for sc_name, query, target_domain in eval_scenarios:
        q_tokens = [t for t in query.split() if t in bm25_vocab]
        
        # 1) BM25 원점수 산출 및 [0, 100] Min-Max 정규화
        if q_tokens:
            bm25_raw = bm25.get_scores(q_tokens)
            max_b = bm25_raw.max()
            bm25_norm = (bm25_raw / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_raw)
        else:
            bm25_norm = np.zeros(len(df_all))

        # 2) LSA 의미 유사도 산출 및 [0, 100] 정규화
        q_vec = tfidf_vec.transform([q_tokens])
        q_lsa = svd.transform(q_vec)
        q_lsa_norm = np.linalg.norm(q_lsa)
        if q_lsa_norm > 0:
            q_lsa = q_lsa / q_lsa_norm
            lsa_sim = np.dot(lsa_matrix, q_lsa.T).ravel()
            lsa_norm_score = np.clip(lsa_sim, 0, 1) * 100.0
        else:
            lsa_norm_score = np.zeros(len(df_all))

        # 3) 하이브리드 점수 공식: (0.50 * LSA + 0.35 * BM25) / 0.85
        # 통합 8,645건에는 실제 수강생 평점 데이터가 없다. 예전에는 모든 강좌에 80점을
        # 일괄 대입해 0.15 가중치로 더했는데, 이는 순위에 영향 없이 점수만 12점 부풀렸다.
        # 실제 평점이 확보되기 전까지 평점 항은 제외하고, 두 점수를 0~100 범위로 재정규화한다.
        hybrid_scores = ((0.50 * lsa_norm_score) + (0.35 * bm25_norm)) / 0.85

        # 5) 동일 강좌 다회차 중복 제거 (Dedup): (provider, title) 기준 최고점 1건만 노출
        # 정렬 후 drop_duplicates
        temp_res = pd.DataFrame({
            "course_uid": df_all["course_uid"],
            "provider": df_all["provider"],
            "title": df_all["title"],
            "price": df_all["price"],
            "duration_hours": df_all["duration_hours"],
            "cluster_k8": df_all["cluster_k8"],
            "hybrid_score": hybrid_scores,
            "lsa_score": lsa_norm_score,
            "bm25_score": bm25_norm
        }).sort_values(by="hybrid_score", ascending=False)

        temp_dedup = temp_res.drop_duplicates(subset=["provider", "title"]).head(5)

        for rank, (_, row) in enumerate(temp_dedup.iterrows(), 1):
            hybrid_results.append({
                "scenario": sc_name,
                "query": query,
                "target_domain": target_domain,
                "rank": rank,
                "course_uid": row["course_uid"],
                "provider": row["provider"],
                "title": row["title"],
                "cluster_k8": row["cluster_k8"],
                "final_hybrid_score": round(row["hybrid_score"], 1),
                "lsa_dense_score": round(row["lsa_score"], 1),
                "bm25_sparse_score": round(row["bm25_score"], 1),
                "price": row["price"],
                "duration_hours": row["duration_hours"]
            })

    df_hybrid_eval = pd.DataFrame(hybrid_results)
    df_hybrid_eval.to_csv(out_dir / "hybrid_recommendation_evaluated_benchmark.csv", index=False, encoding="utf-8-sig")
    print(f" - [완료] 하이브리드 추천 5대 시나리오 Top 5 벤치마크 결과 저장 완료")

    # 결과 지표 JSON
    metrics_summary = {
        "status": "PASS",
        "total_corpus_courses": len(df_all),
        "vocab_size": len(vocab),
        "k_candidates_evaluated": k_candidates,
        "selected_base_k": 8,
        "selected_k_silhouette": float(df_k_comp.loc[df_k_comp["k"] == 8, "silhouette_cosine"].iloc[0]),
        "cluster_distribution": df_c8_summary.set_index("cluster_id")["n_courses"].to_dict(),
        "reproduction_notes": {
            "is_ko_sroberta_implemented_full_corpus": False,
            "ko_sroberta_status_note": "Ko-SRoBERTa는 STEP 5-2 400건 파일럿 단계 실측 완료 (embeddings_ko_sroberta_400.npy 존재), 8,645건 전수 임베딩은 후속 과제임",
            "rating_term": "실제 평점 데이터 없음 → 평점 항 제외, (0.50*LSA + 0.35*BM25)/0.85 로 산출",
            "deduplication_applied": "(provider, title) 기준 다회차 중복 제거 적용"
        },
        "execution_time_sec": round(time.time() - start_time, 2)
    }

    with open(reports_dir / "integrated_clustering_and_hybrid_report.json", "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"STEP 8 완료! 소요 시간: {time.time() - start_time:.2f}초")
    print(f" - 군집화 메트릭 비교표: {out_dir / 'cluster_metrics_comparison_k_values.csv'}")
    print(f" - 8대 군집 요약표: {out_dir / 'integrated_cluster_summary_k8.csv'}")
    print(f" - 5대 시나리오 하이브리드 추천: {out_dir / 'hybrid_recommendation_evaluated_benchmark.csv'}")
    print("=" * 80)

if __name__ == "__main__":
    run_clustering_and_hybrid()
