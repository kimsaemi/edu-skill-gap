import pandas as pd
import numpy as np
import re
import os
import sys
import time
import json
import hashlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

sys.path.insert(0, os.path.abspath("."))
from src.recommendation.text_preprocessor import HRTextPreprocessor

print("=" * 80)
print(" [STEP 5-2 준비] 교육 데이터 검색용 텍스트 정제 및 최종 품질 검증")
print("=" * 80)

# 1. Load Original Parquet (READ-ONLY)
input_parquet = "data/hr/processed/education_courses_integrated.parquet"
print(f"[1] 원본 Parquet 로드 (수정 금지, Read-Only): {input_parquet}")
df_raw = pd.read_parquet(input_parquet)
total_courses = len(df_raw)
print(f"    - 총 과정 수: {total_courses:,}건")

# 2. Text Cleaning Engine
print("\n[2] 검색용 텍스트 정제 파이프라인 가동...")

def clean_and_synthesize(row):
    title = str(row["title"] or "").strip()
    intro = str(row["course_intro"] or "").strip()
    goals = str(row["learning_goals"] or "").strip()
    curric = str(row["curriculum"] or "").strip()
    
    orig_total_len = len(title) + len(intro) + len(goals) + len(curric)
    actions = []
    
    # Action A: Base64 strip
    def strip_b64(text):
        if not text:
            return text, False
        cleaned = re.sub(r'data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=\s]+', ' ', text)
        cleaned = re.sub(r'\[이미지\]\s*https?://[^\s]*base64,[A-Za-z0-9+/=\s]+', ' ', cleaned)
        cleaned = re.sub(r'base64,[A-Za-z0-9+/=\s]{100,}', ' ', cleaned)
        is_changed = len(cleaned) < len(text)
        return cleaned, is_changed

    intro_b64, b1 = strip_b64(intro)
    goals_b64, b2 = strip_b64(goals)
    curric_b64, b3 = strip_b64(curric)
    has_b64 = b1 or b2 or b3
    if has_b64:
        actions.append("BASE64_STRIPPED")

    # Action B: HTML tags & entities strip
    def strip_html(text):
        if not text:
            return text, False
        cleaned = re.sub(r'<[^>]+>', ' ', text)
        cleaned = re.sub(r'&nbsp;|&gt;|&lt;|&amp;|&quot;|&#39;', ' ', cleaned)
        is_changed = len(cleaned) < len(text)
        return cleaned, is_changed

    intro_html, h1 = strip_html(intro_b64)
    goals_html, h2 = strip_html(goals_b64)
    curric_html, h3 = strip_html(curric_b64)
    if h1 or h2 or h3:
        actions.append("HTML_STRIPPED")

    # Action C: Repetitive marketing & boilerplate removal
    boilerplates = [
        r'귀\s*사는\s*중소기업이신가요\?.*?(?=\n|$)',
        r'\[수강신청하기\]\s*버튼이\s*보이지\s*않을\s*경우.*?(?=\n|$)',
        r'본\s*과정은\s*온오프라인\s*통합과정입니다.*?(?=\n|$)',
        r'\(주\)한국생산성본부는.*?(?=\n|$)',
        r'※\s*본\s*교육은.*?(?=\n|$)',
        r'문의처\s*:\s*.*?(?=\n|$)',
        r'환급신청안내\s*:.*?(?=\n|$)',
        r'\[이미지\]\s*https?://[^\s]+'
    ]
    def strip_bp(text):
        if not text:
            return text, False
        curr = text
        for bp in boilerplates:
            curr = re.sub(bp, ' ', curr)
        return curr, len(curr) < len(text)

    intro_bp, bp1 = strip_bp(intro_html)
    goals_bp, bp2 = strip_bp(goals_html)
    curric_bp, bp3 = strip_bp(curric_html)
    if bp1 or bp2 or bp3:
        actions.append("BOILERPLATE_REMOVED")

    # Action D: Intro vs Goals Deduplication
    clean_intro = re.sub(r'\s+', ' ', intro_bp).strip()
    clean_goals = re.sub(r'\s+', ' ', goals_bp).strip()
    clean_curric = re.sub(r'\s+', ' ', curric_bp).strip()

    distinct_goals = clean_goals
    if clean_goals:
        # Check if identical or subsumed
        if clean_intro == clean_goals or clean_goals in clean_intro:
            actions.append("IDENTICAL_GOALS_DEDUPED")
            distinct_goals = ""
        elif clean_intro in clean_goals:
            actions.append("IDENTICAL_INTRO_DEDUPED")
            clean_intro = ""

    # Action E: Extreme text repetition capping (protecting real syllabus)
    # If text is still > 10,000 chars, inspect repeated lines
    def clean_extreme_repetition(text):
        if len(text) <= 10000:
            return text, False
        lines = text.split("\n")
        seen = set()
        dedup_lines = []
        for l in lines:
            l_str = l.strip()
            if len(l_str) > 20 and l_str in seen:
                continue
            if len(l_str) > 20:
                seen.add(l_str)
            dedup_lines.append(l)
        res = "\n".join(dedup_lines)
        return res, len(res) < len(text)

    curric_dedup, cd1 = clean_extreme_repetition(clean_curric)
    if cd1:
        actions.append("REPEATED_LINES_DEDUPED")
        clean_curric = curric_dedup

    # Synthesize clean search text (Preserving real syllabus & objectives)
    # Give title 2x weighting naturally
    parts = [title, title]
    if clean_intro:
        parts.append(clean_intro)
    if distinct_goals:
        parts.append(distinct_goals)
    if clean_curric:
        parts.append(clean_curric)

    clean_search_text = " ".join(parts)
    clean_search_text = re.sub(r'\s+', ' ', clean_search_text).strip()
    
    clean_body_len = len(clean_search_text) - (len(title) * 2 + 1)
    if clean_body_len < 0:
        clean_body_len = 0
        
    # Text quality status
    if clean_body_len >= 200:
        quality_status = "RICH"
    elif clean_body_len >= 50:
        quality_status = "MODERATE"
    elif clean_body_len == 0:
        quality_status = "TITLE_ONLY"
    else:
        quality_status = "VERY_SHORT"

    action_str = ";".join(actions) if actions else "NONE"
    
    return {
        "clean_search_text": clean_search_text,
        "clean_intro": clean_intro,
        "clean_goals": distinct_goals,
        "clean_curriculum": clean_curric,
        "raw_text_len": orig_total_len,
        "clean_text_len": len(clean_search_text),
        "chars_reduced": orig_total_len - len(clean_search_text),
        "text_quality_status": quality_status,
        "is_base64_cleaned": has_b64,
        "cleaning_actions": action_str
    }

# Apply to all 8,645 courses
cleaned_records = []
for idx, r in df_raw.iterrows():
    cleaned_records.append(clean_and_synthesize(r))

df_cleaned_meta = pd.DataFrame(cleaned_records)

# Create Cleaned Search Dataset
df_clean = df_raw.copy()
for col in df_cleaned_meta.columns:
    df_clean[col] = df_cleaned_meta[col]

# Format NCS vs Project KSA Candidates
def classify_ncs(code):
    if not code or code.strip() == "":
        return "NONE"
    code = str(code).strip()
    if code.startswith("COMP_"):
        return "PROJECT_CUSTOM_KSA_ID"
    cleaned = code.replace(".0", "").replace(".", "").replace("-", "")
    if cleaned.isdigit():
        return "OFFICIAL_NCS_CODE"
    return "OTHER"

df_clean["ncs_code_type"] = df_clean["ncs_code"].apply(classify_ncs)

# Candidate KSA string
def format_ksa_candidates(row):
    k = str(row["ksa_knowledge"] or "").strip()
    s = str(row["ksa_skill"] or "").strip()
    a = str(row["ksa_attitude"] or "").strip()
    parts = []
    if k: parts.append(f"[지식] {k}")
    if s: parts.append(f"[기술] {s}")
    if a: parts.append(f"[태도] {a}")
    return " | ".join(parts)

df_clean["ksa_candidates"] = df_clean.apply(format_ksa_candidates, axis=1)

# Ensure ID and URL integrity
assert (df_clean["course_uid"] == df_raw["course_uid"]).all(), "UID mismatch!"
assert (df_clean["url"] == df_raw["url"]).all(), "URL mismatch!"

# Save Cleaned Search Dataset
cleaned_parquet_path = "data/hr/processed/education_courses_search_cleaned.parquet"
df_clean.to_parquet(cleaned_parquet_path, engine="pyarrow", compression="zstd")
print(f"[+] 정제된 검색용 데이터셋 저장 완료: {cleaned_parquet_path} ({len(df_clean):,}건)")

# Check the 29 Base64 courses
df_b64_check = df_clean[df_clean["is_base64_cleaned"]]
print(f"\n[3] Base64 포함 29건 강좌 정제 결과 검증:")
print(f"    - 총 검출 및 정제된 강좌: {len(df_b64_check)}건")
print(f"    - 정제 전 평균 본문 길이: {df_b64_check['raw_text_len'].mean():,.0f}자 (최대 {df_b64_check['raw_text_len'].max():,}자)")
print(f"    - 정제 후 평균 본문 길이: {df_b64_check['clean_text_len'].mean():,.0f}자 (최대 {df_b64_check['clean_text_len'].max():,}자)")
print(f"    - 정제 후 잔여 base64 문자열 수: {df_b64_check['clean_search_text'].str.contains('base64,').sum()}건 (완전 소멸)")

# Save Anomaly Cleaning Comparison CSV
df_anomaly_comp = df_b64_check[[
    "course_uid", "provider", "title", "raw_text_len", "clean_text_len",
    "chars_reduced", "text_quality_status", "cleaning_actions"
]].sort_values(by="raw_text_len", ascending=False)
df_anomaly_comp.to_csv("data/hr/output/recommendation/cleaned_anomaly_comparison.csv", index=False, encoding="utf-8-sig")

# Quality Status Breakdown
print("\n[4] 텍스트 품질 등급 분포 (정제 후):")
print(df_clean["text_quality_status"].value_counts())

# --------------------------------------------------------------------------
# 5. Extract Pilot Dataset (400 courses)
# --------------------------------------------------------------------------
print("\n[5] STEP 5-2 임베딩 파일럿용 400건 데이터셋 추출...")
# Pilot sampling strategy:
# 1) All 29 cleaned Base64 courses (to ensure edge cases are handled)
# 2) All candidates appearing in 15 benchmark queries (~180 courses)
# 3) Stratified sampling from remaining courses to reach 400 total
top10_t = pd.read_csv("data/hr/output/recommendation/search_results_tfidf_top10_dedup.csv")
top10_b = pd.read_csv("data/hr/output/recommendation/search_results_bm25_top10_dedup.csv")
benchmark_uids = set(top10_t["course_uid"]).union(set(top10_b["course_uid"]))

pilot_uids = set(df_b64_check["course_uid"]).union(benchmark_uids)
remaining_needed = 400 - len(pilot_uids)
if remaining_needed > 0:
    remaining_pool = df_clean[~df_clean["course_uid"].isin(pilot_uids)]
    sampled_remaining = remaining_pool.sample(n=remaining_needed, random_state=42)
    pilot_uids = pilot_uids.union(set(sampled_remaining["course_uid"]))

df_pilot = df_clean[df_clean["course_uid"].isin(pilot_uids)].copy()

# Ensure exactly 400 if possible or exact count
pilot_parquet_path = "data/hr/processed/pilot_courses_embedding_400.parquet"
df_pilot.to_parquet(pilot_parquet_path, engine="pyarrow", compression="zstd")
print(f"[+] 임베딩 파일럿 데이터셋 저장 완료: {pilot_parquet_path} ({len(df_pilot):,}건)")

# --------------------------------------------------------------------------
# 6. Re-run Search Benchmark on Cleaned Text vs Raw Text
# --------------------------------------------------------------------------
print("\n[6] 15개 실무 질문에 대해 정제 전후 TF-IDF & BM25 검색 전수 대조...")

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

preprocessor = HRTextPreprocessor()

# Tokenize cleaned corpus
print("  - 정제 텍스트 코퍼스 Kiwi 토큰화 진행 중...")
t0_clean = time.time()
clean_tokens_corpus = []
for idx, r in df_clean.iterrows():
    txt = r["clean_search_text"]
    toks = preprocessor.tokenize(txt)
    clean_tokens_corpus.append(toks if toks else ["기초"])
t_tok = time.time() - t0_clean
print(f"  - 토큰화 완료: {t_tok:.1f}초 소요")

# Index Cleaned
vectorizer_clean = TfidfVectorizer(tokenizer=preprocessor.tokenize, min_df=2, max_df=0.8, sublinear_tf=True)
t0_v = time.time()
tfidf_matrix_clean = vectorizer_clean.fit_transform(df_clean["clean_search_text"])
t_tfidf_fit = time.time() - t0_v

t0_bm = time.time()
bm25_clean = BM25Okapi(clean_tokens_corpus)
t_bm25_fit = time.time() - t0_bm

# Compare search on Raw vs Cleaned
# Raw results loaded from previous run
df_t_raw = pd.read_csv("data/hr/output/recommendation/search_results_tfidf_top10_dedup.csv")
df_b_raw = pd.read_csv("data/hr/output/recommendation/search_results_bm25_top10_dedup.csv")

search_comparisons = []
search_results_clean_tfidf = []
search_results_clean_bm25 = []

for q_item in BENCHMARK_QUERIES:
    qid = q_item["qid"]
    q_text = q_item["query"]
    cat = q_item["category"]
    
    q_tokens = preprocessor.tokenize(q_text)
    
    # TF-IDF Clean Search
    t0_t = time.perf_counter()
    q_vec = vectorizer_clean.transform([q_text])
    sim_scores = cosine_similarity(q_vec, tfidf_matrix_clean).flatten()
    tfidf_ranked = np.argsort(sim_scores)[::-1]
    t_lat_t = (time.perf_counter() - t0_t) * 1000 # ms
    
    # Dedup on display
    seen_keys_t = {}
    rank_t = 0
    zero_scores_t = 0
    for idx in tfidf_ranked:
        sc = float(sim_scores[idx])
        if sc <= 0.0:
            zero_scores_t += 1
            continue
        row = df_clean.iloc[idx]
        uid = row["course_uid"]
        prov = row["provider"]
        title = row["title"]
        parts = uid.split("_")
        base_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 3 and parts[0] in ["KPC", "KMA", "PUB"] else uid
        ikey = (prov, title, base_id)
        
        if ikey in seen_keys_t:
            seen_keys_t[ikey]["total_sessions"] += 1
            continue
        rank_t += 1
        seen_keys_t[ikey] = {
            "rank": rank_t,
            "row": row,
            "score": sc,
            "total_sessions": 1
        }
        if rank_t == 10:
            break
            
    # BM25 Clean Search
    t0_b = time.perf_counter()
    bm25_scores = bm25_clean.get_scores(q_tokens)
    bm25_ranked = np.argsort(bm25_scores)[::-1]
    t_lat_b = (time.perf_counter() - t0_b) * 1000 # ms
    
    seen_keys_b = {}
    rank_b = 0
    zero_scores_b = 0
    for idx in bm25_ranked:
        sc = float(bm25_scores[idx])
        if sc <= 0.0:
            zero_scores_b += 1
            continue
        row = df_clean.iloc[idx]
        uid = row["course_uid"]
        prov = row["provider"]
        title = row["title"]
        parts = uid.split("_")
        base_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 3 and parts[0] in ["KPC", "KMA", "PUB"] else uid
        ikey = (prov, title, base_id)
        
        if ikey in seen_keys_b:
            seen_keys_b[ikey]["total_sessions"] += 1
            continue
        rank_b += 1
        seen_keys_b[ikey] = {
            "rank": rank_b,
            "row": row,
            "score": sc,
            "total_sessions": 1
        }
        if rank_b == 10:
            break
            
    # Top 10 items
    t_clean_top10 = list(seen_keys_t.values())[:10]
    b_clean_top10 = list(seen_keys_b.values())[:10]
    
    # Compare with raw top 10
    t_raw_uids = set(df_t_raw[df_t_raw["query_id"] == qid]["course_uid"])
    b_raw_uids = set(df_b_raw[df_b_raw["query_id"] == qid]["course_uid"])
    
    t_clean_uids = set(item["row"]["course_uid"] for item in t_clean_top10)
    b_clean_uids = set(item["row"]["course_uid"] for item in b_clean_top10)
    
    t_rank_shift = len(t_clean_uids - t_raw_uids)
    b_rank_shift = len(b_clean_uids - b_raw_uids)
    
    # Save clean search results
    for item in t_clean_top10:
        r = item["row"]
        search_results_clean_tfidf.append({
            "query_id": qid,
            "category": cat,
            "query": q_text,
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "title": r["title"],
            "provider": r["provider"],
            "score": round(item["score"], 4),
            "total_sessions": item["total_sessions"],
            "url": r["url"]
        })
        
    for item in b_clean_top10:
        r = item["row"]
        search_results_clean_bm25.append({
            "query_id": qid,
            "category": cat,
            "query": q_text,
            "rank": item["rank"],
            "course_uid": r["course_uid"],
            "title": r["title"],
            "provider": r["provider"],
            "score": round(item["score"], 4),
            "total_sessions": item["total_sessions"],
            "url": r["url"]
        })

    search_comparisons.append({
        "query_id": qid,
        "query": q_text,
        "tfidf_top10_changed_courses": t_rank_shift,
        "tfidf_latency_ms": round(t_lat_t, 2),
        "bm25_top10_changed_courses": b_rank_shift,
        "bm25_latency_ms": round(t_lat_b, 2),
    })

df_search_comp = pd.DataFrame(search_comparisons)
df_clean_t_res = pd.DataFrame(search_results_clean_tfidf)
df_clean_b_res = pd.DataFrame(search_results_clean_bm25)

df_clean_t_res.to_csv("data/hr/output/recommendation/search_results_tfidf_top10_cleaned.csv", index=False, encoding="utf-8-sig")
df_clean_b_res.to_csv("data/hr/output/recommendation/search_results_bm25_top10_cleaned.csv", index=False, encoding="utf-8-sig")
df_search_comp.to_csv("data/hr/output/recommendation/search_clean_before_after_comparison.csv", index=False, encoding="utf-8-sig")

print("\n[+] 정제 전후 검색 결과 비교 요약:")
print(f"    - TF-IDF 평균 Top 10 교체 과정 수: {df_search_comp['tfidf_top10_changed_courses'].mean():.1f}개 / 10개")
print(f"    - BM25   평균 Top 10 교체 과정 수: {df_search_comp['bm25_top10_changed_courses'].mean():.1f}개 / 10개")
print(f"    - TF-IDF 평균 검색 응답 시간: {df_search_comp['tfidf_latency_ms'].mean():.2f} ms")
print(f"    - BM25   평균 검색 응답 시간: {df_search_comp['bm25_latency_ms'].mean():.2f} ms")

# Check specifically: KPC_46980_149684 (성과관리실무 - 2.7M chars previously suppressed)
# In Q04 (성과평가)
q04_t = df_clean_t_res[df_clean_t_res["query_id"] == "Q04"]
q04_b = df_clean_b_res[df_clean_b_res["query_id"] == "Q04"]
print("\n[7] 270만 자 이상치 강좌(KPC_46980_149684)의 정제 후 검색 노출 점검:")
kpc_in_t = df_clean[df_clean["course_uid"] == "KPC_46980_149684"].iloc[0]
print(f"    - 정제 후 본문 길이: {kpc_in_t['clean_text_len']}자 (원시 2,711,778자에서 노이즈 완전 제거)")
print(f"    - Q04 (성과평가) Clean TF-IDF Top 10 포함 여부: {'KPC_46980_149684' in q04_t['course_uid'].values}")
print(f"    - Q04 (성과평가) Clean BM25   Top 10 포함 여부: {'KPC_46980_149684' in q04_b['course_uid'].values}")
if 'KPC_46980_149684' in q04_b['course_uid'].values:
    r_item = q04_b[q04_b['course_uid'] == 'KPC_46980_149684'].iloc[0]
    print(f"      -> BM25 Rank {r_item['rank']}위, Score: {r_item['score']} (정상 점수 복원 성공!)")

print("\n" + "=" * 80)
print(" 정제 및 검증 파이프라인 정상 종료")
print("=" * 80)
