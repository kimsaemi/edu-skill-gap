"""
scripts/profile_and_benchmark_bottlenecks.py
Customer MVP 성능 병목 정밀 측정 및 DuckDB 비교 벤치마크
측정 항목:
1. 패키지 import 시간 (pandas, torch, sentence_transformers, duckdb 등)
2. 파일 읽기 시간 (Parquet, npy, JSON)
3. 데이터 조인 시간 (Pandas in-memory vs DuckDB direct parquet query)
4. 모델 초기화 시간 (SentenceTransformer 가중치 로드)
5. 질의 인코딩 시간 (Ko-SRoBERTa 단일 질의)
6. 점수 계산 시간 (NumPy 시맨틱 내적 + BM25 키워드 점수 + 가중 결합)
7. 중복 제거 및 카드 포맷팅 시간 (Intra/Cross-platform dedup)
8. 메모리 사용량 (RSS MB) 변화 추적
9. 1회차(Cold) vs 반복(Warm) 실행 시간 비교
"""
import sys
import time
import gc
from pathlib import Path
import psutil
import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def get_process_memory_mb():
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)

def run_profiling():
    results = {}
    mem_snapshots = {}

    mem_snapshots["start"] = get_process_memory_mb()
    print("=" * 80)
    print("🚀 Customer MVP 8대 세부 성능 병목 정밀 측정 시작")
    print(f"초기 프로세스 메모리: {mem_snapshots['start']:.1f} MB")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. 패키지 Import 시간 측정
    # --------------------------------------------------------------------------
    print("\n[1] 패키지 Import 시간 측정...")
    import_timings = {}
    
    t0 = time.perf_counter()
    import torch
    import_timings["torch"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    from sentence_transformers import SentenceTransformer
    import_timings["sentence_transformers"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    from rank_bm25 import BM25Okapi
    import_timings["rank_bm25"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    import duckdb
    import_timings["duckdb"] = (time.perf_counter() - t0) * 1000

    results["import_timings"] = import_timings
    total_import = sum(import_timings.values())
    print(f"  - torch: {import_timings['torch']:.1f} ms")
    print(f"  - sentence_transformers: {import_timings['sentence_transformers']:.1f} ms")
    print(f"  - rank_bm25: {import_timings['rank_bm25']:.1f} ms")
    print(f"  - duckdb: {import_timings['duckdb']:.1f} ms")
    print(f"  ➔ 총 Import 지연: {total_import:.1f} ms")
    mem_snapshots["after_imports"] = get_process_memory_mb()
    print(f"  (메모리: {mem_snapshots['after_imports']:.1f} MB, 증가 +{mem_snapshots['after_imports'] - mem_snapshots['start']:.1f} MB)")

    # --------------------------------------------------------------------------
    # 2. 파일 읽기 시간 측정
    # --------------------------------------------------------------------------
    print("\n[2] 파일 읽기 시간 측정 (코퍼스, 임베딩, 군집, 토큰)...")
    data_dir = WORKSPACE_ROOT / "data" / "hr"
    p_clean = data_dir / "processed" / "education_courses_search_cleaned.parquet"
    p_clusters = data_dir / "output" / "recommendation" / "course_clusters_8645.parquet"
    p_emb = data_dir / "output" / "recommendation" / "embeddings_ko_sroberta_all.npy"
    p_tok = data_dir / "processed" / "tokenized_corpus_cache.parquet"
    p_comp = data_dir / "output" / "recommendation" / "course_competency_long.parquet"

    file_read_timings = {}
    
    t0 = time.perf_counter()
    df_courses = pd.read_parquet(p_clean)
    file_read_timings["clean_parquet_8645"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    df_clusters = pd.read_parquet(p_clusters)
    file_read_timings["clusters_parquet"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    embeddings = np.load(p_emb)
    file_read_timings["embeddings_npy_8645x768"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    df_tokens = pd.read_parquet(p_tok)
    file_read_timings["tokens_parquet"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    df_comp = pd.read_parquet(p_comp)
    file_read_timings["comp_parquet"] = (time.perf_counter() - t0) * 1000

    total_file_read = sum(file_read_timings.values())
    for k, v in file_read_timings.items():
        print(f"  - {k}: {v:.1f} ms")
    print(f"  ➔ 총 파일 읽기 지연: {total_file_read:.1f} ms")
    mem_snapshots["after_file_read"] = get_process_memory_mb()
    print(f"  (메모리: {mem_snapshots['after_file_read']:.1f} MB, 증가 +{mem_snapshots['after_file_read'] - mem_snapshots['after_imports']:.1f} MB)")

    # --------------------------------------------------------------------------
    # 3. 데이터 조인 시간 측정: Pandas vs DuckDB
    # --------------------------------------------------------------------------
    print("\n[3] 데이터 조인 시간 측정: Pandas (In-Memory) vs DuckDB (Direct Parquet Query)...")
    
    # Pandas Merge
    t0 = time.perf_counter()
    df_merged_pandas = df_courses.merge(df_clusters[['course_uid', 'cluster_id', 'topic_label']], on='course_uid', how='left')
    df_merged_pandas = df_merged_pandas.merge(df_tokens[['course_uid', 'tokenized_text']], on='course_uid', how='left')
    t_pandas_join = (time.perf_counter() - t0) * 1000
    print(f"  - Pandas in-memory merge (2회): {t_pandas_join:.2f} ms ({len(df_merged_pandas)}행)")

    # DuckDB Query on Parquet files directly
    con = duckdb.connect(database=':memory:')
    t0 = time.perf_counter()
    clean_p_str = str(p_clean).replace('\\', '/')
    cl_p_str = str(p_clusters).replace('\\', '/')
    tok_p_str = str(p_tok).replace('\\', '/')
    query = f"""
    SELECT c.*, cl.cluster_id, cl.topic_label, tok.tokenized_text
    FROM read_parquet('{clean_p_str}') c
    LEFT JOIN read_parquet('{cl_p_str}') cl ON c.course_uid = cl.course_uid
    LEFT JOIN read_parquet('{tok_p_str}') tok ON c.course_uid = tok.course_uid
    """
    df_duckdb_parquet = con.execute(query).fetchdf()
    t_duckdb_parquet = (time.perf_counter() - t0) * 1000
    print(f"  - DuckDB direct parquet join: {t_duckdb_parquet:.2f} ms ({len(df_duckdb_parquet)}행)")

    # DuckDB Query on In-memory registered tables
    con.register("courses_mem", df_courses)
    con.register("clusters_mem", df_clusters)
    con.register("tokens_mem", df_tokens)
    t0 = time.perf_counter()
    query_mem = """
    SELECT c.*, cl.cluster_id, cl.topic_label, tok.tokenized_text
    FROM courses_mem c
    LEFT JOIN clusters_mem cl ON c.course_uid = cl.course_uid
    LEFT JOIN tokens_mem tok ON c.course_uid = tok.course_uid
    """
    df_duckdb_mem = con.execute(query_mem).fetchdf()
    t_duckdb_mem = (time.perf_counter() - t0) * 1000
    print(f"  - DuckDB in-memory registered tables join: {t_duckdb_mem:.2f} ms ({len(df_duckdb_mem)}행)")
    con.close()

    # --------------------------------------------------------------------------
    # 4. 모델 초기화 시간 측정
    # --------------------------------------------------------------------------
    print("\n[4] Ko-SRoBERTa 모델 초기화 시간 측정...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.perf_counter()
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=device)
    t_model_init = (time.perf_counter() - t0) * 1000
    print(f"  - SentenceTransformer 로드 ({device}): {t_model_init:.1f} ms")
    mem_snapshots["after_model_load"] = get_process_memory_mb()
    print(f"  (메모리: {mem_snapshots['after_model_load']:.1f} MB, 증가 +{mem_snapshots['after_model_load'] - mem_snapshots['after_file_read']:.1f} MB)")

    # --------------------------------------------------------------------------
    # 5. 질의 인코딩 시간 측정 (Cold vs Warm)
    # --------------------------------------------------------------------------
    print("\n[5] 질의 인코딩 시간 측정 (Ko-SRoBERTa)...")
    sample_query = "구조화 면접 질문 설계 및 신규 입사자 온보딩 기획 능력 향상"
    
    t0 = time.perf_counter()
    q_vec_1 = model.encode(sample_query, normalize_embeddings=True, device=device)
    t_encode_cold = (time.perf_counter() - t0) * 1000
    print(f"  - 1회차 인코딩 (Cold): {t_encode_cold:.2f} ms")

    warm_encode_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = model.encode(sample_query, normalize_embeddings=True, device=device)
        warm_encode_times.append((time.perf_counter() - t0) * 1000)
    t_encode_warm_median = np.median(warm_encode_times)
    print(f"  - 반복 인코딩 (Warm 중앙값 5회): {t_encode_warm_median:.2f} ms")

    # --------------------------------------------------------------------------
    # 6. 점수 계산 시간 측정 (NumPy 내적 vs BM25 vs KSA 필터)
    # --------------------------------------------------------------------------
    print("\n[6] 추천 점수 계산 세부 측정...")
    # BM25 초기화
    corpus_tokens = [txt.split() for txt in df_merged_pandas['tokenized_text']]
    bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
    bm25_vocab = {t for toks in corpus_tokens for t in toks}

    # 후보군 필터링 (8,645건 전수 대상)
    cand_indices = np.arange(len(df_merged_pandas))
    
    # 6-1. 시맨틱 내적 (Vector Dot Product)
    t0 = time.perf_counter()
    sims = np.dot(embeddings[cand_indices], q_vec_1)
    sem_scores = np.clip(sims, 0.0, 1.0) * 100.0
    t_dot_product = (time.perf_counter() - t0) * 1000
    print(f"  - 8,645건 시맨틱 내적 연산: {t_dot_product:.2f} ms")

    # 6-2. BM25 점수 계산
    t0 = time.perf_counter()
    q_tokens = [t for t in sample_query.split() if t in bm25_vocab]
    bm25_raw = bm25.get_scores(q_tokens)
    max_b = bm25_raw.max()
    bm25_sc = (bm25_raw / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_raw)
    t_bm25_calc = (time.perf_counter() - t0) * 1000
    print(f"  - BM25 점수 계산 및 정규화: {t_bm25_calc:.2f} ms")

    # 6-3. 가중 결합 및 정렬
    t0 = time.perf_counter()
    final_scores = (0.50 * sem_scores) + (0.30 * bm25_sc)
    top_indices = np.argsort(final_scores)[::-1][:50]
    t_ranking = (time.perf_counter() - t0) * 1000
    print(f"  - 가중 결합 및 Top 50 정렬: {t_ranking:.2f} ms")

    # --------------------------------------------------------------------------
    # 7. 중복 제거 및 발췌문 가공 시간 측정
    # --------------------------------------------------------------------------
    print("\n[7] 중복 제거 및 발췌문 가공 시간 측정...")
    from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender
    recommender = UnifiedHybridRecommender()

    t0 = time.perf_counter()
    top_df, n_cands, exc_cnt, pres_cnt, msg = recommender.recommend(
        query=sample_query,
        target_domain="인사",
        competency_id="COMP_HR_01",
        user_level="실무",
        top_n=5,
        mode="ksa"
    )
    t_full_recommend_first = (time.perf_counter() - t0) * 1000
    print(f"  - Recommender.recommend() 1회차 전체 시간: {t_full_recommend_first:.1f} ms")

    warm_rec_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = recommender.recommend(
            query=sample_query,
            target_domain="인사",
            competency_id="COMP_HR_01",
            user_level="실무",
            top_n=5,
            mode="ksa"
        )
        warm_rec_times.append((time.perf_counter() - t0) * 1000)
    t_full_recommend_warm_median = np.median(warm_rec_times)
    print(f"  - Recommender.recommend() 반복(Warm) 중앙값: {t_full_recommend_warm_median:.1f} ms")

    mem_snapshots["final"] = get_process_memory_mb()
    print(f"\n최종 프로세스 메모리: {mem_snapshots['final']:.1f} MB (총 증가 +{mem_snapshots['final'] - mem_snapshots['start']:.1f} MB)")

    # --------------------------------------------------------------------------
    # 종합 요약표 생성
    # --------------------------------------------------------------------------
    summary_rows = [
        {"구분": "1. 패키지 Import", "세부 항목": "torch, sentence_transformers, duckdb 등", "지연 시간(ms)": f"{total_import:.1f} ms", "비율(%)": f"{(total_import/(total_import+total_file_read+t_model_init))*100:.1f}%", "최적화 방안": "서버 기동 시 1회만 발생 (@st.cache_resource)"},
        {"구분": "2. 파일 읽기", "세부 항목": "Parquet 3종 + 임베딩 npy", "지연 시간(ms)": f"{total_file_read:.1f} ms", "비율(%)": f"{(total_file_read/(total_import+total_file_read+t_model_init))*100:.1f}%", "최적화 방안": "메모리 캐싱 (@st.cache_data / cache_resource)"},
        {"구분": "3. 데이터 조인", "세부 항목": "Pandas Merge vs DuckDB Direct", "지연 시간(ms)": f"Pandas {t_pandas_join:.1f}ms / DuckDB {t_duckdb_parquet:.1f}ms", "비율(%)": "-", "최적화 방안": "DuckDB vs Pandas 성능 비교 검증"},
        {"구분": "4. 모델 초기화 (Cold)", "세부 항목": "Ko-SRoBERTa 모델 가중치 로드", "지연 시간(ms)": f"{t_model_init:.1f} ms", "비율(%)": f"{(t_model_init/(total_import+total_file_read+t_model_init))*100:.1f}%", "최적화 방안": "@st.cache_resource 싱글톤 재사용"},
        {"구분": "5. 질의 인코딩", "세부 항목": "Ko-SRoBERTa 단일 텍스트 인코딩", "지연 시간(ms)": f"Cold {t_encode_cold:.1f}ms / Warm {t_encode_warm_median:.1f}ms", "비율(%)": "-", "최적화 방안": "동일 질의 인코딩 LRU 캐시 적용"},
        {"구분": "6. 점수 계산", "세부 항목": "NumPy 시맨틱 내적 + BM25 연산", "지연 시간(ms)": f"내적 {t_dot_product:.1f}ms + BM25 {t_bm25_calc:.1f}ms", "비율(%)": "-", "최적화 방안": "NumPy C-extension 벡터 연산 유지 (초고속)"},
        {"구분": "7. 중복제거/추천완료", "세부 항목": "전체 추천 파이프라인 (recommend)", "지연 시간(ms)": f"Cold {t_full_recommend_first:.1f}ms / Warm {t_full_recommend_warm_median:.1f}ms", "비율(%)": "-", "최적화 방안": "조건별 추천 결과 키 캐싱 (TTL/LRU)"}
    ]
    df_summary = pd.DataFrame(summary_rows)
    print("\n" + "=" * 80)
    print("📊 Customer MVP 병목 정밀 측정 종합 결과")
    print("=" * 80)
    print(df_summary.to_string(index=False))

    out_csv = WORKSPACE_ROOT / "data" / "hr" / "reports" / "bottleneck_profile_report.csv"
    df_summary.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: {out_csv}")

if __name__ == "__main__":
    run_profiling()
