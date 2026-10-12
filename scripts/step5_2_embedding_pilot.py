import os
import sys
import time
import json
import torch
import numpy as np
import pandas as pd
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

sys.path.insert(0, os.path.abspath("."))
from src.recommendation.text_preprocessor import HRTextPreprocessor

print("=" * 80)
print(" [STEP 5-2] 400건 파일럿 로컬 한국어 임베딩 모델 비교 및 유사도 분석")
print("=" * 80)

# Check device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[1] 실행 디바이스: {device.upper()}")
if device == "cuda":
    print(f"    - GPU: {torch.cuda.get_device_name(0)}")
    print(f"    - Initial VRAM Allocated: {torch.cuda.memory_allocated(0)/(1024**2):.1f} MB")

# Load Pilot 400 dataset
pilot_path = "data/hr/processed/pilot_courses_embedding_400.parquet"
df_pilot = pd.read_parquet(pilot_path)
print(f"[2] 파일럿 400건 데이터셋 로드 완료: {len(df_pilot)}건 (고유 ID: {df_pilot['course_uid'].nunique()}건)")

# Texts for embedding (Truncate to 512 chars/tokens safely)
texts = df_pilot["clean_search_text"].tolist()

# ------------------------------------------------------------------------------
# STEP 3-A: Model 1 - klue/bert-base
# ------------------------------------------------------------------------------
print("\n[3-A] 모델 1: klue/bert-base 로컬 임베딩 생성...")
model_name_klue = "klue/bert-base"

t0_load_klue = time.time()
tokenizer_klue = AutoTokenizer.from_pretrained(model_name_klue)
model_klue = AutoModel.from_pretrained(model_name_klue).to(device)
model_klue.eval()
t_load_klue = time.time() - t0_load_klue
print(f"    - 모델 로드 시간: {t_load_klue:.2f}초")

def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0] # First element of model_output contains all token embeddings
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    return sum_embeddings / sum_mask

batch_size = 32
klue_embeddings_list = []

t0_infer_klue = time.time()
with torch.no_grad():
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        encoded = tokenizer_klue(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt"
        ).to(device)
        
        output = model_klue(**encoded)
        pooled = mean_pooling(output, encoded["attention_mask"])
        # L2 Normalize
        normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
        klue_embeddings_list.append(normalized.cpu().numpy())

t_infer_klue = time.time() - t0_infer_klue
klue_embeddings = np.vstack(klue_embeddings_list)
print(f"    - 400건 임베딩 생성 시간: {t_infer_klue:.2f}초 (배치당 {t_infer_klue/(len(texts)/batch_size)*1000:.1f}ms)")
print(f"    - 임베딩 차원: {klue_embeddings.shape}")

if device == "cuda":
    klue_vram = torch.cuda.memory_allocated(0)/(1024**2)
    print(f"    - Peak VRAM Usage: {klue_vram:.1f} MB")
    torch.cuda.empty_cache()

# ------------------------------------------------------------------------------
# STEP 3-B: Model 2 - jhgan/ko-sroberta-multitask
# ------------------------------------------------------------------------------
print("\n[3-B] 모델 2: jhgan/ko-sroberta-multitask 로컬 임베딩 생성...")
model_name_roberta = "jhgan/ko-sroberta-multitask"

t0_load_roberta = time.time()
model_roberta = SentenceTransformer(model_name_roberta, device=device)
t_load_roberta = time.time() - t0_load_roberta
print(f"    - 모델 로드 시간: {t_load_roberta:.2f}초")

t0_infer_roberta = time.time()
roberta_embeddings = model_roberta.encode(
    texts,
    batch_size=batch_size,
    show_progress_bar=False,
    normalize_embeddings=True,
    device=device
)
t_infer_roberta = time.time() - t0_infer_roberta
print(f"    - 400건 임베딩 생성 시간: {t_infer_roberta:.2f}초 (배치당 {t_infer_roberta/(len(texts)/batch_size)*1000:.1f}ms)")
print(f"    - 임베딩 차원: {roberta_embeddings.shape}")

if device == "cuda":
    roberta_vram = torch.cuda.memory_allocated(0)/(1024**2)
    print(f"    - Peak VRAM Usage: {roberta_vram:.1f} MB")
    torch.cuda.empty_cache()

# Save Embeddings & Metadata Mapping
os.makedirs("data/hr/output/recommendation", exist_ok=True)
np.save("data/hr/output/recommendation/embeddings_klue_bert_base_400.npy", klue_embeddings)
np.save("data/hr/output/recommendation/embeddings_ko_sroberta_400.npy", roberta_embeddings)

df_pilot_meta = df_pilot[["course_uid", "provider", "title", "ncs_code", "url", "text_quality_status"]].copy()
df_pilot_meta["vector_index"] = np.arange(len(df_pilot))
df_pilot_meta.to_parquet("data/hr/output/recommendation/pilot_course_embeddings_metadata.parquet", compression="zstd")
print(f"[+] 임베딩 벡터 및 메타데이터 저장 완료 (.npy 및 .parquet)")

# ------------------------------------------------------------------------------
# STEP 4: 5대 대표 실무 질문 유사도 검색 분석
# ------------------------------------------------------------------------------
print("\n[4] 5대 대표 실무 질문에 대한 모델별 코사인 유사도 검색...")

BENCHMARK_5_QUERIES = [
    {"qid": "Q01", "category": "인사/채용", "query": "신입사원 온보딩 및 채용 프로세스 실무"},
    {"qid": "Q02", "category": "노무/근로기준", "query": "근로기준법 개정사항 및 취업규칙 작성 실무"},
    {"qid": "Q04", "category": "인사/평가보상", "query": "직무분석 및 KPI 성과평가 보상체계 설계"},
    {"qid": "Q06", "category": "총무/구매", "query": "비품 구매 계약 및 공급업체 관리"},
    {"qid": "Q09", "category": "실무스킬", "query": "엑셀 실무 데이터 가공 및 함수 활용"}
]

# Helper function for deduplication on display
def dedup_top10(scored_indices, scores, df_corpus):
    seen_keys = {}
    rank = 0
    results = []
    for idx in scored_indices:
        r = df_corpus.iloc[idx]
        uid = r["course_uid"]
        prov = r["provider"]
        title = r["title"]
        parts = uid.split("_")
        base_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 3 and parts[0] in ["KPC", "KMA", "PUB"] else uid
        ikey = (prov, title, base_id)
        
        if ikey in seen_keys:
            seen_keys[ikey]["total_sessions"] += 1
            continue
            
        rank += 1
        seen_keys[ikey] = {
            "rank": rank,
            "row": r,
            "score": float(scores[idx]),
            "total_sessions": 1
        }
        results.append(seen_keys[ikey])
        if rank == 10:
            break
    return results

search_results_klue = []
search_results_roberta = []

for q_item in BENCHMARK_5_QUERIES:
    qid = q_item["qid"]
    q_text = q_item["query"]
    cat = q_item["category"]
    
    # 1. KLUE BERT Query Embedding
    with torch.no_grad():
        q_enc = tokenizer_klue([q_text], return_tensors="pt").to(device)
        q_out = model_klue(**q_enc)
        q_pool = mean_pooling(q_out, q_enc["attention_mask"])
        q_vec_klue = torch.nn.functional.normalize(q_pool, p=2, dim=1).cpu().numpy()[0]
        
    klue_scores = np.dot(klue_embeddings, q_vec_klue)
    klue_ranked = np.argsort(klue_scores)[::-1]
    klue_top10 = dedup_top10(klue_ranked, klue_scores, df_pilot)
    
    for item in klue_top10:
        r = item["row"]
        search_results_klue.append({
            "query_id": qid,
            "category": cat,
            "query": q_text,
            "model": "klue/bert-base",
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "title": r["title"],
            "provider": r["provider"],
            "similarity": round(item["score"], 4),
            "total_sessions": item["total_sessions"],
            "source_url": r["url"]
        })

    # 2. Ko-SRoBERTa Query Embedding
    q_vec_roberta = model_roberta.encode(q_text, normalize_embeddings=True)
    roberta_scores = np.dot(roberta_embeddings, q_vec_roberta)
    roberta_ranked = np.argsort(roberta_scores)[::-1]
    roberta_top10 = dedup_top10(roberta_ranked, roberta_scores, df_pilot)
    
    for item in roberta_top10:
        r = item["row"]
        search_results_roberta.append({
            "query_id": qid,
            "category": cat,
            "query": q_text,
            "model": "jhgan/ko-sroberta-multitask",
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "title": r["title"],
            "provider": r["provider"],
            "similarity": round(item["score"], 4),
            "total_sessions": item["total_sessions"],
            "source_url": r["url"]
        })

df_res_klue = pd.DataFrame(search_results_klue)
df_res_roberta = pd.DataFrame(search_results_roberta)

df_res_klue.to_csv("data/hr/output/recommendation/pilot_search_top10_klue_bert.csv", index=False, encoding="utf-8-sig")
df_res_roberta.to_csv("data/hr/output/recommendation/pilot_search_top10_ko_sroberta.csv", index=False, encoding="utf-8-sig")

# ------------------------------------------------------------------------------
# STEP 4-B: 교육과정별 유사 강좌 Top 5 (Course-to-Course Recommendation)
# ------------------------------------------------------------------------------
print("\n[4-B] 400건 교육과정 간 상호 코사인 유사도 매트릭스 계산 및 Top 5 유사 강좌 도출...")

# Pairwise cosine similarity matrix (400 x 400) using Ko-SRoBERTa
pairwise_sim = np.dot(roberta_embeddings, roberta_embeddings.T)

course_to_course_top5 = []
for i in range(len(df_pilot)):
    r_src = df_pilot.iloc[i]
    sims = pairwise_sim[i].copy()
    sims[i] = -1.0 # Exclude self
    
    top5_idx = np.argsort(sims)[::-1][:5]
    for r_rank, tgt_idx in enumerate(top5_idx, 1):
        r_tgt = df_pilot.iloc[tgt_idx]
        course_to_course_top5.append({
            "source_course_uid": r_src["course_uid"],
            "source_title": r_src["title"],
            "source_provider": r_src["provider"],
            "target_rank": r_rank,
            "target_course_uid": r_tgt["course_uid"],
            "target_title": r_tgt["title"],
            "target_provider": r_tgt["provider"],
            "cosine_similarity": round(float(sims[tgt_idx]), 4),
            "target_url": r_tgt["url"]
        })

df_c2c = pd.DataFrame(course_to_course_top5)
df_c2c.to_csv("data/hr/output/recommendation/pilot_course_to_course_top5.csv", index=False, encoding="utf-8-sig")
print(f"[+] 교육과정별 유사 강좌 Top 5 저장 완료 ({len(df_c2c):,}행)")

# ------------------------------------------------------------------------------
# STEP 5: 기존 TF-IDF & BM25와 공정 비교 (동일 400건 대상 재실행)
# ------------------------------------------------------------------------------
print("\n[5] 동일 400건 파일럿 데이터 대상 TF-IDF 및 BM25 베이스라인 재실행 및 비교...")

preprocessor = HRTextPreprocessor()
pilot_corpus_tokens = [preprocessor.tokenize(t) for t in texts]

# Fit on pilot 400
vec_pilot = TfidfVectorizer(tokenizer=preprocessor.tokenize, min_df=1, sublinear_tf=True)
tfidf_pilot_mat = vec_pilot.fit_transform(texts)
bm25_pilot = BM25Okapi(pilot_corpus_tokens)

search_results_lexical = []
overlap_stats = []

for q_item in BENCHMARK_5_QUERIES:
    qid = q_item["qid"]
    q_text = q_item["query"]
    cat = q_item["category"]
    q_toks = preprocessor.tokenize(q_text)
    
    # TF-IDF
    t0_t = time.perf_counter()
    sim_t = cosine_similarity(vec_pilot.transform([q_text]), tfidf_pilot_mat).flatten()
    lat_t = (time.perf_counter() - t0_t) * 1000
    top10_t = dedup_top10(np.argsort(sim_t)[::-1], sim_t, df_pilot)
    
    # BM25
    t0_b = time.perf_counter()
    scores_b = bm25_pilot.get_scores(q_toks)
    lat_b = (time.perf_counter() - t0_b) * 1000
    top10_b = dedup_top10(np.argsort(scores_b)[::-1], scores_b, df_pilot)
    
    for item in top10_t:
        r = item["row"]
        search_results_lexical.append({
            "query_id": qid,
            "category": cat,
            "query": q_text,
            "model": "TF-IDF (400건 파일럿)",
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "title": r["title"],
            "provider": r["provider"],
            "score": round(item["score"], 4),
            "source_url": r["url"]
        })
    for item in top10_b:
        r = item["row"]
        search_results_lexical.append({
            "query_id": qid,
            "category": cat,
            "query": q_text,
            "model": "BM25 (400건 파일럿)",
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "title": r["title"],
            "provider": r["provider"],
            "score": round(item["score"], 4),
            "source_url": r["url"]
        })
        
    # Calculate overlap between lexical and dense models
    uids_t = set(item["row"]["course_uid"] for item in top10_t)
    uids_b = set(item["row"]["course_uid"] for item in top10_b)
    uids_klue = set(df_res_klue[df_res_klue["query_id"] == qid]["course_uid"])
    uids_roberta = set(df_res_roberta[df_res_roberta["query_id"] == qid]["course_uid"])
    
    overlap_stats.append({
        "query_id": qid,
        "query": q_text,
        "tfidf_vs_roberta_overlap": len(uids_t & uids_roberta),
        "bm25_vs_roberta_overlap": len(uids_b & uids_roberta),
        "klue_vs_roberta_overlap": len(uids_klue & uids_roberta),
        "tfidf_vs_bm25_overlap": len(uids_t & uids_b),
        "latency_tfidf_ms": round(lat_t, 2),
        "latency_bm25_ms": round(lat_b, 2)
    })

df_res_lexical = pd.DataFrame(search_results_lexical)
df_res_lexical.to_csv("data/hr/output/recommendation/pilot_search_top10_tfidf_bm25_baseline.csv", index=False, encoding="utf-8-sig")

df_overlap = pd.DataFrame(overlap_stats)
print("\n" + "=" * 80)
print(" [결과 요약] 5대 질의 Top 10 모델 간 교집합 비교표 (400건 파일럿)")
print("=" * 80)
print(df_overlap.to_string(index=False))

# Distribution statistics
print("\n[코사인 유사도 분포 비교]")
print(f"klue/bert-base: 평균={klue_embeddings.mean():.4f}, std={klue_embeddings.std():.4f}, min={klue_embeddings.min():.4f}, max={klue_embeddings.max():.4f}")
print(f"ko-sroberta:    평균={roberta_embeddings.mean():.4f}, std={roberta_embeddings.std():.4f}, min={roberta_embeddings.min():.4f}, max={roberta_embeddings.max():.4f}")

# Model Performance Report Summary
with open("data/hr/reports/model_execution_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "hardware": {
            "device": device,
            "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else "N/A"
        },
        "models": {
            "klue_bert_base": {
                "load_time_sec": round(t_load_klue, 2),
                "infer_time_sec": round(t_infer_klue, 2),
                "peak_vram_mb": round(klue_vram, 1) if device == "cuda" else 0,
                "dimension": 768,
                "pooling": "mean_pooling"
            },
            "ko_sroberta_multitask": {
                "load_time_sec": round(t_load_roberta, 2),
                "infer_time_sec": round(t_infer_roberta, 2),
                "peak_vram_mb": round(roberta_vram, 1) if device == "cuda" else 0,
                "dimension": 768,
                "pooling": "mean_pooling (sentence-transformers STS fine-tuned)"
            }
        },
        "overlap_summary": overlap_stats
    }, f, ensure_ascii=False, indent=2)

print("\n[+] STEP 5-2 파일럿 실행 완료!")
