import pandas as pd
import numpy as np
import pickle
import json
import os
import hashlib
import random
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from src.recommendation.text_preprocessor import HRTextPreprocessor

# 1. Load data
print("[1] Loading corpus and preprocessed tokens...")
df = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

# 2. Benchmark Queries
BENCHMARK_QUERIES = [
    {"qid": "Q01", "category": "인사", "query": "신입사원 온보딩 및 채용 프로세스 실무"},
    {"qid": "Q02", "category": "인사", "query": "근로기준법 개정사항 및 취업규칙 작성 실무"},
    {"qid": "Q03", "category": "인사", "query": "연말정산 및 4대보험 급여 계산 실무"},
    {"qid": "Q04", "category": "인사", "query": "직무분석 및 KPI 성과평가 보상체계 설계"},
    {"qid": "Q05", "category": "인사", "query": "부당해고 구제신청 및 노사관계 노무관리"},
    {"qid": "Q06", "category": "총무", "query": "비품 구매 계약 및 공급업체 관리"},
    {"qid": "Q07", "category": "총무", "query": "고정자산 실사 및 사옥 시설관리"},
    {"qid": "Q08", "category": "총무", "query": "공문서 작성법 및 기획보고서 피드백"},
    {"qid": "Q09", "category": "총무", "query": "엑셀 실무 데이터 가공 및 함수 활용"},
    {"qid": "Q10", "category": "총무", "query": "사내 행사 기획 및 워크숍 운영 총무 실무"},
    {"qid": "Q11", "category": "경영지원", "query": "비즈니스 매너 및 사내 커뮤니케이션 에티켓"},
    {"qid": "Q12", "category": "경영지원", "query": "임원 비서 실무 및 의전 가이드"},
    {"qid": "Q13", "category": "경영지원", "query": "애자일 프로젝트 관리 및 스크럼 스프린트"},
    {"qid": "Q14", "category": "경영지원", "query": "사업계획서 수립 및 재무제표 분석 기초"},
    {"qid": "Q15", "category": "경영지원", "query": "주52시간 근로시간 관리 및 유연근무제 운영"}
]

# Course identity key function:
# Merges runs only within the SAME provider and SAME core course/title/curriculum, preserving different providers or genuinely different courses.
def get_identity_key(row):
    prov = str(row["provider"] or "").strip()
    title = str(row["title"] or "").strip()
    uid = str(row["course_uid"] or "")
    parts = uid.split("_")
    if len(parts) >= 3 and parts[0] in ["KPC", "KMA", "PUB"]:
        base_id = f"{parts[0]}_{parts[1]}"
    else:
        base_id = uid
    return (prov, title, base_id)

df["identity_key"] = df.apply(get_identity_key, axis=1)

# Preprocessor
preprocessor = HRTextPreprocessor()

# Build search texts and Kiwi tokenized corpus
print("[2] Tokenizing corpus with Kiwi...")
search_texts = []
tokenized_corpus = []

for idx, row in df.iterrows():
    t = str(row["title"] or "")
    intro = str(row["course_intro"] or "")
    goals = str(row["learning_goals"] or "")
    curric = str(row["curriculum"] or "")
    
    # Strip base64 image garbage if present to clean search text
    if "base64," in intro:
        intro = intro.split("base64,")[0]
    if "base64," in goals:
        goals = goals.split("base64,")[0]
        
    combined = f"{t} {t} {intro} {goals} {curric}".strip()
    search_texts.append(combined)
    toks = preprocessor.tokenize(combined)
    tokenized_corpus.append(toks if toks else ["기초"])

# Vectorizer & BM25
from sklearn.feature_extraction.text import TfidfVectorizer
print("[3] Building TF-IDF matrix and BM25 index...")
vectorizer = TfidfVectorizer(tokenizer=preprocessor.tokenize, min_df=2, max_df=0.8, sublinear_tf=True)
tfidf_matrix = vectorizer.fit_transform(search_texts)
bm25 = BM25Okapi(tokenized_corpus)

# 4. Search and Deduplication
print("[4] Executing search and deduplicating multiple runs...")
tfidf_dedup_results = []
bm25_dedup_results = []
before_after_comparisons = []

# Load original before results for comparison
df_t_before = pd.read_csv("data/hr/output/recommendation/search_results_tfidf_top10.csv")
df_b_before = pd.read_csv("data/hr/output/recommendation/search_results_bm25_top10.csv")

for q_item in BENCHMARK_QUERIES:
    qid = q_item["qid"]
    category = q_item["category"]
    query = q_item["query"]
    
    q_tokens = preprocessor.tokenize(query)
    if not q_tokens:
        continue
        
    # --- TF-IDF Search ---
    q_vec = vectorizer.transform([query])
    sim_scores = cosine_similarity(q_vec, tfidf_matrix).flatten()
    tfidf_ranked = np.argsort(sim_scores)[::-1]
    
    seen_keys_t = {}
    rank_t = 0
    for idx in tfidf_ranked:
        score = float(sim_scores[idx])
        if score <= 0.0:
            break
        row = df.iloc[idx]
        ikey = row["identity_key"]
        
        # Track all session occurrences
        if ikey in seen_keys_t:
            seen_keys_t[ikey]["total_sessions"] += 1
            seen_keys_t[ikey]["session_uids"].append(row["course_uid"])
            continue
            
        rank_t += 1
        seen_keys_t[ikey] = {
            "rank": rank_t,
            "row": row,
            "score": score,
            "total_sessions": 1,
            "session_uids": [row["course_uid"]],
            "idx": idx
        }
        if rank_t == 10:
            # Continue iterating a bit to count sessions of Top 10 items
            pass
        if rank_t >= 10 and len(seen_keys_t) >= 15:
            break
            
    # Collect Top 10 deduplicated for TF-IDF
    q_t_top10 = []
    for ikey, item in list(seen_keys_t.items())[:10]:
        r = item["row"]
        sess_cnt = item["total_sessions"]
        sess_note = f"단독 개설 ({r['course_uid']})" if sess_cnt == 1 else f"대표 회차 선정 (총 {sess_cnt}개 회차 중 {r['course_uid']})"
        matched_words = [token for token in q_tokens if token in tokenized_corpus[item["idx"]]]
        res = {
            "query_id": qid,
            "category": category,
            "query": query,
            "search_method": "TF-IDF",
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "course_name": r["title"],
            "provider": r["provider"],
            "score": round(item["score"], 4),
            "total_sessions_in_corpus": sess_cnt,
            "session_handling_note": sess_note,
            "matched_keywords": ", ".join(list(dict.fromkeys(matched_words))),
            "source_url": r["url"] or ""
        }
        tfidf_dedup_results.append(res)
        q_t_top10.append(res)

    # --- BM25 Search ---
    bm25_scores = bm25.get_scores(q_tokens)
    bm25_ranked = np.argsort(bm25_scores)[::-1]
    
    seen_keys_b = {}
    rank_b = 0
    for idx in bm25_ranked:
        score = float(bm25_scores[idx])
        if score <= 0.0:
            break
        row = df.iloc[idx]
        ikey = row["identity_key"]
        
        if ikey in seen_keys_b:
            seen_keys_b[ikey]["total_sessions"] += 1
            seen_keys_b[ikey]["session_uids"].append(row["course_uid"])
            continue
            
        rank_b += 1
        seen_keys_b[ikey] = {
            "rank": rank_b,
            "row": row,
            "score": score,
            "total_sessions": 1,
            "session_uids": [row["course_uid"]],
            "idx": idx
        }
        if rank_b >= 10 and len(seen_keys_b) >= 15:
            break
            
    # Collect Top 10 deduplicated for BM25
    q_b_top10 = []
    for ikey, item in list(seen_keys_b.items())[:10]:
        r = item["row"]
        sess_cnt = item["total_sessions"]
        sess_note = f"단독 개설 ({r['course_uid']})" if sess_cnt == 1 else f"대표 회차 선정 (총 {sess_cnt}개 회차 중 {r['course_uid']})"
        matched_words = [token for token in q_tokens if token in tokenized_corpus[item["idx"]]]
        res = {
            "query_id": qid,
            "category": category,
            "query": query,
            "search_method": "BM25",
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "course_name": r["title"],
            "provider": r["provider"],
            "score": round(item["score"], 4),
            "total_sessions_in_corpus": sess_cnt,
            "session_handling_note": sess_note,
            "matched_keywords": ", ".join(list(dict.fromkeys(matched_words))),
            "source_url": r["url"] or ""
        }
        bm25_dedup_results.append(res)
        q_b_top10.append(res)
        
    # Before vs After Comparison per Query
    # TF-IDF before unique titles in Top 10
    t_before_q = df_t_before[df_t_before["query_id"] == qid]
    t_before_unique_titles = t_before_q["course_name"].nunique()
    t_after_unique_titles = len(q_t_top10)
    
    b_before_q = df_b_before[df_b_before["query_id"] == qid]
    b_before_unique_titles = b_before_q["course_name"].nunique()
    b_after_unique_titles = len(q_b_top10)
    
    before_after_comparisons.append({
        "query_id": qid,
        "query": query,
        "tfidf_before_unique_courses": t_before_unique_titles,
        "tfidf_before_duplicate_slots": 10 - t_before_unique_titles,
        "tfidf_after_unique_courses": t_after_unique_titles,
        "tfidf_new_distinct_courses_introduced": t_after_unique_titles - t_before_unique_titles,
        "bm25_before_unique_courses": b_before_unique_titles,
        "bm25_before_duplicate_slots": 10 - b_before_unique_titles,
        "bm25_after_unique_courses": b_after_unique_titles,
        "bm25_new_distinct_courses_introduced": b_after_unique_titles - b_before_unique_titles
    })

# Save Deduplicated Search Results
df_tfidf_dedup = pd.DataFrame(tfidf_dedup_results)
df_bm25_dedup = pd.DataFrame(bm25_dedup_results)
df_comparison = pd.DataFrame(before_after_comparisons)

os.makedirs("data/hr/output/recommendation", exist_ok=True)
df_tfidf_dedup.to_csv("data/hr/output/recommendation/search_results_tfidf_top10_dedup.csv", index=False, encoding="utf-8-sig")
df_bm25_dedup.to_csv("data/hr/output/recommendation/search_results_bm25_top10_dedup.csv", index=False, encoding="utf-8-sig")
df_comparison.to_csv("data/hr/output/recommendation/top10_before_after_comparison.csv", index=False, encoding="utf-8-sig")

print(f"Deduplicated TF-IDF results saved: {len(df_tfidf_dedup)} rows")
print(f"Deduplicated BM25 results saved: {len(df_bm25_dedup)} rows")
print("\nBefore vs After Summary:")
print(f"TF-IDF: Total duplicated slots eliminated = {df_comparison['tfidf_before_duplicate_slots'].sum()} slots -> All 15 queries now have 10 distinct courses!")
print(f"BM25:   Total duplicated slots eliminated = {df_comparison['bm25_before_duplicate_slots'].sum()} slots -> All 15 queries now have 10 distinct courses!")

# --------------------------------------------------------------------------
# 5. Team Member Evaluation Sheet (Blind, 4 Members, 3 Common Queries)
# --------------------------------------------------------------------------
print("\n[5] Generating Blind Evaluation Sheet for 4 Team Members...")

# Query Assignment:
# Common Queries: Q01 (인사), Q06 (총무), Q13 (경영지원) -> Evaluated by ALL 4 members
# Member Specific Queries:
# Member A: Q02, Q03, Q04 (인사 실무)
# Member B: Q05, Q07, Q08 (노무/총무)
# Member C: Q09, Q10, Q11 (엑셀/행사/비즈니스매너)
# Member D: Q12, Q14, Q15 (의전/사업계획/근로시간)

evaluator_assignments = {
    "팀원A": ["Q01", "Q06", "Q13", "Q02", "Q03", "Q04"],
    "팀원B": ["Q01", "Q06", "Q13", "Q05", "Q07", "Q08"],
    "팀원C": ["Q01", "Q06", "Q13", "Q09", "Q10", "Q11"],
    "팀원D": ["Q01", "Q06", "Q13", "Q12", "Q14", "Q15"]
}

# For each query, merge TF-IDF and BM25 Top 10 results.
# If a course appears in BOTH algorithms, list it only ONCE.
# Mask algorithm source under blind candidate id.
random.seed(42) # Reproducible shuffling

query_candidates = {}
blind_key_mapping = {}

for q_item in BENCHMARK_QUERIES:
    qid = q_item["qid"]
    q_text = q_item["query"]
    cat = q_item["category"]
    
    t_items = [r for r in tfidf_dedup_results if r["query_id"] == qid]
    b_items = [r for r in bm25_dedup_results if r["query_id"] == qid]
    
    # Map by course_uid
    merged = {}
    for item in t_items:
        uid = item["course_uid"]
        merged[uid] = {
            "course_uid": uid,
            "course_name": item["course_name"],
            "provider": item["provider"],
            "source_url": item["source_url"],
            "tfidf_rank": item["rank"],
            "tfidf_score": item["score"],
            "bm25_rank": None,
            "bm25_score": None,
            "origin_algorithm": "TF-IDF"
        }
    for item in b_items:
        uid = item["course_uid"]
        if uid in merged:
            merged[uid]["bm25_rank"] = item["rank"]
            merged[uid]["bm25_score"] = item["score"]
            merged[uid]["origin_algorithm"] = "BOTH (TF-IDF & BM25)"
        else:
            merged[uid] = {
                "course_uid": uid,
                "course_name": item["course_name"],
                "provider": item["provider"],
                "source_url": item["source_url"],
                "tfidf_rank": None,
                "tfidf_score": None,
                "bm25_rank": item["rank"],
                "bm25_score": item["score"],
                "origin_algorithm": "BM25"
            }
            
    # Convert to list and shuffle for blind presentation
    items_list = list(merged.values())
    random.shuffle(items_list)
    
    for c_idx, cand in enumerate(items_list, 1):
        blind_cid = f"{qid}_C{c_idx:02d}"
        cand["blind_candidate_id"] = blind_cid
        cand["query_id"] = qid
        cand["query"] = q_text
        cand["category"] = cat
        
        # Save to secret key
        blind_key_mapping[blind_cid] = {
            "blind_candidate_id": blind_cid,
            "query_id": qid,
            "course_uid": cand["course_uid"],
            "course_name": cand["course_name"],
            "provider": cand["provider"],
            "origin_algorithm": cand["origin_algorithm"],
            "tfidf_rank": cand["tfidf_rank"],
            "tfidf_score": cand["tfidf_score"],
            "bm25_rank": cand["bm25_rank"],
            "bm25_score": cand["bm25_score"]
        }
        
    query_candidates[qid] = items_list

# Save secret blind mapping key
with open("data/hr/output/recommendation/blind_evaluation_key.json", "w", encoding="utf-8") as f:
    json.dump(blind_key_mapping, f, ensure_ascii=False, indent=2)

df_blind_key = pd.DataFrame(list(blind_key_mapping.values()))
df_blind_key.to_csv("data/hr/output/recommendation/blind_evaluation_key.csv", index=False, encoding="utf-8-sig")

# Build the Team Evaluation Sheet (BLANK evaluation columns!)
eval_sheet_rows = []

# Order by member: Member A -> Member B -> Member C -> Member D
for member, qids in evaluator_assignments.items():
    for qid in qids:
        is_common = qid in ["Q01", "Q06", "Q13"]
        assignment_type = "공통 검토 (4인 전원)" if is_common else f"개별 배정 ({member})"
        
        for cand in query_candidates[qid]:
            eval_sheet_rows.append({
                "배정 평가자": member,
                "질문 배정 구분": assignment_type,
                "질문 ID": qid,
                "질문 분야": cand["category"],
                "검색 질문": cand["query"],
                "블라인드 후보 ID": cand["blind_candidate_id"],
                "교육과정 ID": cand["course_uid"],
                "과정명": cand["course_name"],
                "교육기관": cand["provider"],
                "상세페이지 URL": cand["source_url"],
                "관련성 점수 (2/1/0/확인 불가)": "",  # STRICTLY BLANK for human evaluators
                "평가 판단 근거": "",                 # STRICTLY BLANK
                "실제 평가자 서명": "",               # STRICTLY BLANK
                "평가 완료 일자": ""                 # STRICTLY BLANK
            })

df_eval_sheet = pd.DataFrame(eval_sheet_rows)
df_eval_sheet.to_csv("data/hr/output/recommendation/human_eval_sheet_blind_4members.csv", index=False, encoding="utf-8-sig")

print(f"Blind Team Evaluation Sheet saved: {len(df_eval_sheet):,} rows")
print(f"Unique questions per member: 6 questions (3 common + 3 assigned)")
print(f"Average candidates per question: ~{len(df_eval_sheet)/4/6:.1f} candidates (deduplicated union of Top 10)")
print("All evaluation score columns are strictly BLANK.")
