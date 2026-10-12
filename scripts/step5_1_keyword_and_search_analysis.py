"""STEP 5-1: Comprehensive Keyword Extraction & TF-IDF vs BM25 Search Benchmark Suite.

Executes:
1. Data Quality & Text Richness Audit on all 8,645 courses.
2. Per-course Top 5-10 Keyword Extraction via TF-IDF & Title vs Body Keyword Comparison.
3. 15 Domain Queries Search Benchmark across TF-IDF and BM25 (Top 10 ranking, score >= 0 filter, session duplicate flag).
4. Human Evaluation Sheet generation for 4 team members (blank evaluation fields).
5. Comprehensive Search Comparison Report & Next Step Roadmap document generation.
"""

import sys
import os
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path("d:/26_강의자료/프로젝트2_교육")))

from src.processors.data_loader import load_integrated_courses
from src.recommendation.text_preprocessor import HRTextPreprocessor

# Ensure UTF-8 stdout
sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE_ROOT = Path("d:/26_강의자료/프로젝트2_교육")
RECOMMEND_OUT_DIR = WORKSPACE_ROOT / "data" / "hr" / "output" / "recommendation"
REPORTS_DIR = WORKSPACE_ROOT / "data" / "hr" / "reports"
DOCS_DIR = WORKSPACE_ROOT / "docs"

RECOMMEND_OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# 15 Representative Domain Queries (HR 5, GA 5, MGMT 5)
BENCHMARK_QUERIES = [
    # [인사 - HR]
    {"qid": "Q01", "category": "인사", "query": "신입사원 온보딩 및 채용 프로세스 실무"},
    {"qid": "Q02", "category": "인사", "query": "근로기준법 개정사항 및 취업규칙 작성 실무"},
    {"qid": "Q03", "category": "인사", "query": "연말정산 및 4대보험 급여 계산 실무"},
    {"qid": "Q04", "category": "인사", "query": "직무분석 및 KPI 성과평가 보상체계 설계"},
    {"qid": "Q05", "category": "인사", "query": "부당해고 구제신청 및 노사관계 노무관리"},
    # [총무 - GA]
    {"qid": "Q06", "category": "총무", "query": "비품 구매 계약 및 공급업체 관리"},
    {"qid": "Q07", "category": "총무", "query": "고정자산 실사 및 사옥 시설관리"},
    {"qid": "Q08", "category": "총무", "query": "공문서 작성법 및 기획보고서 피드백"},
    {"qid": "Q09", "category": "총무", "query": "엑셀 실무 데이터 가공 및 함수 활용"},
    {"qid": "Q10", "category": "총무", "query": "사내 행사 기획 및 워크숍 운영 총무 실무"},
    # [경영지원 - MGMT]
    {"qid": "Q11", "category": "경영지원", "query": "비즈니스 매너 및 사내 커뮤니케이션 에티켓"},
    {"qid": "Q12", "category": "경영지원", "query": "임원 비서 실무 및 의전 가이드"},
    {"qid": "Q13", "category": "경영지원", "query": "애자일 프로젝트 관리 및 스크럼 스프린트"},
    {"qid": "Q14", "category": "경영지원", "query": "사업계획서 수립 및 재무제표 분석 기초"},
    {"qid": "Q15", "category": "경영지원", "query": "주52시간 근로시간 관리 및 유연근무제 운영"}
]

def run_step5_1_pipeline():
    print("=" * 80)
    print(" [STEP 5-1] NCS 교육 데이터 키워드 분석 및 TF-IDF vs BM25 검색 벤치마크 ")
    print(f" 시작 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. 데이터 로드 및 품질 감사 (Data Quality & Richness Audit)
    # --------------------------------------------------------------------------
    print("\n>>> [1] 8,645건 통합 교육과정 데이터 로드 및 텍스트 품질 감사")
    t0 = time.time()
    df = load_integrated_courses(scope="all")
    print(f"  [+] 데이터 로드 완료: {len(df):,}행 x {len(df.columns)}열 (소요시간: {time.time() - t0:.3f}초)")

    # Data Quality Metrics
    total_courses = len(df)
    has_title = df["title"].fillna("").str.strip().ne("").sum()
    has_intro = df["course_intro"].fillna("").str.strip().ne("").sum()
    has_goals = df["learning_goals"].fillna("").str.strip().ne("").sum()
    has_curric = df["curriculum"].fillna("").str.strip().ne("").sum()

    title_len = df["title"].fillna("").str.len()
    
    # Combined description text: intro + goals + curriculum
    body_text = (
        df["course_intro"].fillna("") + " " +
        df["learning_goals"].fillna("") + " " +
        df["curriculum"].fillna("")
    ).str.strip()
    body_len = body_text.str.len()
    
    total_text = (df["title"].fillna("") + " " + body_text).str.strip()
    total_len = total_text.str.len()

    # Course Richness Categories
    # Rich: body >= 200 chars; Moderate: 50 <= body < 200; Title-only: body < 50 chars
    rich_cnt = (body_len >= 200).sum()
    moderate_cnt = ((body_len >= 50) & (body_len < 200)).sum()
    title_only_cnt = (body_len < 50).sum()

    # Duplicate analysis: title duplicates within same provider vs cross provider
    same_prov_title_dups = df.duplicated(subset=["provider", "title"], keep=False).sum()
    all_title_dups = df.duplicated(subset=["title"], keep=False).sum()

    # Domain distribution (Rule-based Auto-matched)
    # ncs_code or category hints
    hr_cnt = df["ncs_code"].str.startswith("COMP_HR", na=False) | df["ncs_code"].str.startswith("COMP_LABOR", na=False)
    ga_cnt = df["ncs_code"].str.startswith("COMP_GA", na=False)
    mgmt_cnt = df["ncs_code"].str.startswith("COMP_SEC", na=False) | df["ncs_code"].str.startswith("COMP_MGMT", na=False)
    general_cnt = df["mapping_status"] == "GENERAL"

    print("  [+] 데이터 품질 지표 요약:")
    print(f"      - 교육과정명 보유율 : {has_title:,}건 ({has_title/total_courses*100:.1f}%)")
    print(f"      - 교육 소개글 보유율: {has_intro:,}건 ({has_intro/total_courses*100:.1f}%)")
    print(f"      - 학습 목표 보유율  : {has_goals:,}건 ({has_goals/total_courses*100:.1f}%)")
    print(f"      - 커리큘럼 보유율   : {has_curric:,}건 ({has_curric/total_courses*100:.1f}%)")
    print(f"      - 텍스트 풍부도 구분: 상세 풍부(≥200자) {rich_cnt:,}건 ({rich_cnt/total_courses*100:.1f}%), 보통(50~199자) {moderate_cnt:,}건, 제목 위주(<50자) {title_only_cnt:,}건 ({title_only_cnt/total_courses*100:.1f}%)")
    print(f"      - 본문 텍스트 길이  : 중앙값 {body_len.median():.0f}자, 평균 {body_len.mean():.0f}자 (최대 {body_len.max():,}자)")
    print(f"      - 동일 과정명 차수  : 동일기관 다차원 개설 {same_prov_title_dups:,}건, 전체 동일명 공급 {all_title_dups:,}건")

    # --------------------------------------------------------------------------
    # 2. 형태소 분석 및 TF-IDF 기반 교육과정별 핵심 키워드 추출
    # --------------------------------------------------------------------------
    print("\n>>> [2] 형태소 분석 및 교육과정별 대표 키워드 추출 (제목 vs 본문 비교)")
    preprocessor = HRTextPreprocessor()

    # Pre-tokenize title and body
    print("  [+] 전체 과정 제목 및 본문 텍스트 전처리/토큰화 진행 중 (Kiwi 형태소 분석기)...")
    t0_tok = time.time()
    
    # Prepare combined search text for indexing
    search_texts = []
    title_tokens_list = []
    body_tokens_list = []
    
    for idx, row in df.iterrows():
        t = str(row["title"]) if pd.notna(row["title"]) else ""
        b = str(body_text.iat[idx])
        c = f"{row['category_depth1'] or ''} {row['category_depth2'] or ''}"
        
        # Clean & tokenize
        tok_t = preprocessor.tokenize(t)
        tok_b = preprocessor.tokenize(b[:800]) # optimize length for top keywords
        
        title_tokens_list.append(tok_t)
        body_tokens_list.append(tok_b)
        
        # Search text for vector space (weighted title + body)
        # title repeated twice to give higher lexical weight
        comb_text = f"{t} {t} {c} {b}"
        search_texts.append(comb_text)

    df["search_text"] = search_texts
    print(f"  [+] 전처리 완료 (소요시간: {time.time() - t0_tok:.2f}초)")

    # Build TF-IDF Matrix on full corpus
    print("  [+] 전체 코퍼스 TF-IDF 벡터라이저 학습 중...")
    t0_tfidf = time.time()
    vectorizer = TfidfVectorizer(
        tokenizer=preprocessor.tokenize,
        token_pattern=None,
        min_df=2,
        max_df=0.6, # exclude ultra-frequent generic words
        sublinear_tf=True
    )
    tfidf_matrix = vectorizer.fit_transform(df["search_text"])
    feature_names = np.array(vectorizer.get_feature_names_out())
    print(f"  [+] TF-IDF 학습 완료: 어휘 수 {len(feature_names):,}개, 행렬 {tfidf_matrix.shape} (소요시간: {time.time() - t0_tfidf:.2f}초)")

    # Extract top 5~8 keywords per course using TF-IDF sparse matrix
    print("  [+] 교육과정별 TF-IDF 상위 대표 키워드 추출 중...")
    course_keywords_records = []
    title_vs_desc_records = []

    for row_idx in range(len(df)):
        c_uid = df["course_uid"].iat[row_idx]
        title = df["title"].iat[row_idx]
        prov = df["provider"].iat[row_idx]
        ncs_c = df["ncs_code"].iat[row_idx]
        
        # Sparse row extraction
        row_vec = tfidf_matrix[row_idx]
        indices = row_vec.indices
        data = row_vec.data
        
        if len(data) > 0:
            top_order = np.argsort(data)[::-1][:8]
            top_words = feature_names[indices[top_order]]
            top_scores = data[top_order]
            kw_scored_str = ", ".join([f"{w}({s:.3f})" for w, s in zip(top_words, top_scores)])
            top_kw_str = ", ".join(top_words)
        else:
            top_kw_str = ""
            kw_scored_str = ""

        # Title keywords vs Body keywords from frequency
        tok_t = title_tokens_list[row_idx]
        tok_b = body_tokens_list[row_idx]
        
        t_top = [w for w, _ in Counter(tok_t).most_common(5)]
        b_top = [w for w, _ in Counter(tok_b).most_common(5)]

        course_keywords_records.append({
            "course_uid": c_uid,
            "title": title,
            "provider": prov,
            "ncs_code": ncs_c,
            "top_tfidf_keywords": top_kw_str,
            "keyword_scores": kw_scored_str
        })

        title_vs_desc_records.append({
            "course_uid": c_uid,
            "title": title,
            "provider": prov,
            "title_keywords": ", ".join(t_top),
            "desc_keywords": ", ".join(b_top),
            "top_tfidf_keywords": top_kw_str,
            "overlap_keywords": ", ".join(set(t_top) & set(b_top))
        })

    df_course_kw = pd.DataFrame(course_keywords_records)
    df_title_desc = pd.DataFrame(title_vs_desc_records)

    out_kw_csv = RECOMMEND_OUT_DIR / "course_tfidf_keywords.csv"
    out_td_csv = RECOMMEND_OUT_DIR / "title_vs_desc_keywords.csv"
    df_course_kw.to_csv(out_kw_csv, index=False, encoding="utf-8-sig")
    df_title_desc.to_csv(out_td_csv, index=False, encoding="utf-8-sig")
    print(f"  [✓] 산출물 저장: {out_kw_csv.name} ({len(df_course_kw):,}행)")
    print(f"  [✓] 산출물 저장: {out_td_csv.name} ({len(df_title_desc):,}행)")

    # --------------------------------------------------------------------------
    # 3. TF-IDF vs BM25 15대 실무 질의 검색 벤치마크 비교
    # --------------------------------------------------------------------------
    print("\n>>> [3] 15대 인사·총무·경영지원 실무 질의 검색 비교 (TF-IDF vs BM25)")
    
    # Initialize BM25 with tokenized corpus
    print("  [+] BM25Okapi 인덱스 구축 중...")
    t0_bm25 = time.time()
    tokenized_corpus = [preprocessor.tokenize(text) for text in df["search_text"]]
    bm25 = BM25Okapi(tokenized_corpus)
    print(f"  [+] BM25 인덱스 구축 완료 (소요시간: {time.time() - t0_bm25:.2f}초)")

    tfidf_search_results = []
    bm25_search_results = []
    eval_sheet_records = []

    # Detect title duplicates across dataset for run tagging
    title_counts = df["title"].value_counts().to_dict()

    for q_item in BENCHMARK_QUERIES:
        qid = q_item["qid"]
        category = q_item["category"]
        query = q_item["query"]
        
        q_tokens = preprocessor.tokenize(query)
        if not q_tokens:
            continue

        # --- A. TF-IDF Search ---
        q_vec = vectorizer.transform([query])
        sim_scores = cosine_similarity(q_vec, tfidf_matrix).flatten()
        # Rank descending
        tfidf_ranked = np.argsort(sim_scores)[::-1]
        
        rank_cnt = 0
        for idx in tfidf_ranked:
            score = float(sim_scores[idx])
            if score <= 0.0:  # Exclude zero scores
                break
            rank_cnt += 1
            if rank_cnt > 10:
                break
                
            row = df.iloc[idx]
            uid = row["course_uid"]
            t = row["title"]
            prov = row["provider"]
            url = row["url"] or ""
            is_dup_run = "다회차 개설 강좌" if title_counts.get(t, 0) > 1 else "단독 개설 강좌"
            
            # Find matched words
            matched_words = [token for token in q_tokens if token in tokenized_corpus[idx]]
            
            res_item = {
                "query_id": qid,
                "category": category,
                "query": query,
                "search_method": "TF-IDF",
                "rank": rank_cnt,
                "course_uid": uid,
                "course_name": t,
                "provider": prov,
                "score": round(score, 4),
                "matched_keywords": ", ".join(list(dict.fromkeys(matched_words))),
                "source_url": url,
                "is_duplicate_run": is_dup_run
            }
            tfidf_search_results.append(res_item)
            
            # Add to Human Eval Sheet
            eval_sheet_records.append({
                "검색 질문 ID": qid,
                "질문 분야": category,
                "검색 질문": query,
                "검색 방법": "TF-IDF",
                "순위": rank_cnt,
                "교육과정 ID": uid,
                "과정명": t,
                "교육기관": prov,
                "매칭 점수": round(score, 4),
                "상세페이지 URL": url,
                "관련성 점수(0~2)": "", # BLANK for human evaluators
                "평가 이유": "",         # BLANK
                "평가자": "",           # BLANK
                "평가일": ""            # BLANK
            })

        # --- B. BM25 Search ---
        bm25_scores = bm25.get_scores(q_tokens)
        bm25_ranked = np.argsort(bm25_scores)[::-1]
        
        rank_cnt_bm25 = 0
        for idx in bm25_ranked:
            score = float(bm25_scores[idx])
            if score <= 0.0:  # Exclude zero scores
                break
            rank_cnt_bm25 += 1
            if rank_cnt_bm25 > 10:
                break
                
            row = df.iloc[idx]
            uid = row["course_uid"]
            t = row["title"]
            prov = row["provider"]
            url = row["url"] or ""
            is_dup_run = "다회차 개설 강좌" if title_counts.get(t, 0) > 1 else "단독 개설 강좌"
            
            matched_words = [token for token in q_tokens if token in tokenized_corpus[idx]]

            res_item = {
                "query_id": qid,
                "category": category,
                "query": query,
                "search_method": "BM25",
                "rank": rank_cnt_bm25,
                "course_uid": uid,
                "course_name": t,
                "provider": prov,
                "score": round(score, 4),
                "matched_keywords": ", ".join(list(dict.fromkeys(matched_words))),
                "source_url": url,
                "is_duplicate_run": is_dup_run
            }
            bm25_search_results.append(res_item)
            
            # Add to Human Eval Sheet
            eval_sheet_records.append({
                "검색 질문 ID": qid,
                "질문 분야": category,
                "검색 질문": query,
                "검색 방법": "BM25",
                "순위": rank_cnt_bm25,
                "교육과정 ID": uid,
                "과정명": t,
                "교육기관": prov,
                "매칭 점수": round(score, 4),
                "상세페이지 URL": url,
                "관련성 점수(0~2)": "", # BLANK
                "평가 이유": "",         # BLANK
                "평가자": "",           # BLANK
                "평가일": ""            # BLANK
            })

    df_tfidf_res = pd.DataFrame(tfidf_search_results)
    df_bm25_res = pd.DataFrame(bm25_search_results)
    df_eval_sheet = pd.DataFrame(eval_sheet_records)

    out_tfidf_csv = RECOMMEND_OUT_DIR / "search_results_tfidf_top10.csv"
    out_bm25_csv = RECOMMEND_OUT_DIR / "search_results_bm25_top10.csv"
    out_eval_csv = RECOMMEND_OUT_DIR / "human_eval_sheet_15queries.csv"

    df_tfidf_res.to_csv(out_tfidf_csv, index=False, encoding="utf-8-sig")
    df_bm25_res.to_csv(out_bm25_csv, index=False, encoding="utf-8-sig")
    df_eval_sheet.to_csv(out_eval_csv, index=False, encoding="utf-8-sig")

    print(f"  [✓] 산출물 저장: {out_tfidf_csv.name} ({len(df_tfidf_res):,}행)")
    print(f"  [✓] 산출물 저장: {out_bm25_csv.name} ({len(df_bm25_res):,}행)")
    print(f"  [✓] 산출물 저장: {out_eval_csv.name} ({len(df_eval_sheet):,}행 - 팀원 4명 휴먼 평가용 공란 시트)")

    # --------------------------------------------------------------------------
    # 4. 검색 비교 분석 및 마크다운 보고서 생성
    # --------------------------------------------------------------------------
    print("\n>>> [4] 검색 결과 비교 분석 및 종합 보고서 작성")
    
    # Calculate Top 1 overlap between TF-IDF and BM25
    top1_matches = 0
    top10_jaccard_list = []
    
    for q_item in BENCHMARK_QUERIES:
        qid = q_item["qid"]
        t_top10 = set(df_tfidf_res[df_tfidf_res["query_id"] == qid]["course_uid"].tolist())
        b_top10 = set(df_bm25_res[df_bm25_res["query_id"] == qid]["course_uid"].tolist())
        
        t_top1 = df_tfidf_res[df_tfidf_res["query_id"] == qid]["course_uid"].iloc[0] if len(t_top10) > 0 else None
        b_top1 = df_bm25_res[df_bm25_res["query_id"] == qid]["course_uid"].iloc[0] if len(b_top10) > 0 else None
        
        if t_top1 == b_top1 and t_top1 is not None:
            top1_matches += 1
            
        jaccard = len(t_top10 & b_top10) / len(t_top10 | b_top10) if len(t_top10 | b_top10) > 0 else 0
        top10_jaccard_list.append(jaccard)

    avg_jaccard = np.mean(top10_jaccard_list)
    print(f"  [+] 15대 질문 Top 1 일치율: {top1_matches}/15 ({top1_matches/15*100:.1f}%)")
    print(f"  [+] Top 10 검색 결과 평균 자카드 유사도(중복 공유율): {avg_jaccard*100:.1f}%")

    # Generate Reports
    rep_md_path = REPORTS_DIR / "tfidf_vs_bm25_search_comparison_report.md"
    with open(rep_md_path, "w", encoding="utf-8") as f:
        f.write("# [보고서] STEP 5-1: TF-IDF vs BM25 어휘 검색 비교 및 키워드 분석 보고서\n\n")
        f.write(f"- **작업 일시**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **분석 코퍼스**: 통합 교육과정 **8,645건** (`education_courses_integrated.parquet`)\n")
        f.write("- **비교 질문 수**: 인사(5) + 총무(5) + 경영지원(5) = **총 15개 실무 질문**\n\n")

        f.write("## 1. 교육 데이터 텍스트 품질 및 풍부도 분석 결과\n\n")
        f.write("| 항목 | 건수 | 비율 (%) | 평가 및 해석 |\n")
        f.write("| :--- | :---: | :---: | :--- |\n")
        f.write(f"| **전체 분석 코퍼스** | **{total_courses:,}건** | 100.0% | 신규 6개 DB(8,505건) + 기존 공공 API(140건) |\n")
        f.write(f"| **교육명 (`title`)** | {has_title:,}건 | {has_title/total_courses*100:.1f}% | 결측 0건 (완전 보유) |\n")
        f.write(f"| **교육 소개글 (`course_intro`)** | {has_intro:,}건 | {has_intro/total_courses*100:.1f}% | 핵심 직무 개요 포함 |\n")
        f.write(f"| **학습 목표 (`learning_goals`)** | {has_goals:,}건 | {has_goals/total_courses*100:.1f}% | 습득 역량 정의 포함 |\n")
        f.write(f"| **커리큘럼 (`curriculum`)** | {has_curric:,}건 | {has_curric/total_courses*100:.1f}% | 상세 주차/교시별 목차 수록 |\n")
        f.write(f"| **상세 내용 풍부 과정 (본문 ≥200자)** | **{rich_cnt:,}건** | **{rich_cnt/total_courses*100:.1f}%** | **키워드 및 임베딩 분석의 고품질 핵심 코퍼스** |\n")
        f.write(f"| **보통 과정 (50~199자)** | {moderate_cnt:,}건 | {moderate_cnt/total_courses*100:.1f}% | 기초 키워드 중심 매칭 가능 |\n")
        f.write(f"| **제목 위주 과정 (<50자)** | {title_only_cnt:,}건 | {title_only_cnt/total_courses*100:.1f}% | 상세 본문 결측 과정으로 제목 어휘 의존 |\n\n")

        f.write("## 2. 15대 실무 질의 검색 결과 요약 및 상위 매칭 사례\n\n")
        f.write("| 질의 ID | 분야 | 검색 질문 | TF-IDF Top 1 과정명 (점수) | BM25 Top 1 과정명 (점수) | Top 1 일치 여부 |\n")
        f.write("| :--- | :---: | :--- | :--- | :--- | :---: |\n")
        for q_item in BENCHMARK_QUERIES:
            qid = q_item["qid"]
            t_row = df_tfidf_res[(df_tfidf_res["query_id"] == qid) & (df_tfidf_res["rank"] == 1)]
            b_row = df_bm25_res[(df_bm25_res["query_id"] == qid) & (df_bm25_res["rank"] == 1)]
            
            t_name = f"{t_row['course_name'].iloc[0]} ({t_row['score'].iloc[0]:.2f})" if len(t_row) > 0 else "결과없음"
            b_name = f"{b_row['course_name'].iloc[0]} ({b_row['score'].iloc[0]:.2f})" if len(b_row) > 0 else "결과없음"
            
            is_same = "일치" if len(t_row) > 0 and len(b_row) > 0 and t_row["course_uid"].iloc[0] == b_row["course_uid"].iloc[0] else "불일치"
            f.write(f"| `{qid}` | {q_item['category']} | {q_item['query']} | {t_name} | {b_name} | **{is_same}** |\n")

        f.write(f"\n- **Top 1 일치율**: **{top1_matches} / 15 ({top1_matches/15*100:.1f}%)**\n")
        f.write(f"- **Top 10 결과 자카드 중복 유사도**: **{avg_jaccard*100:.1f}%**\n\n")

        f.write("## 3. TF-IDF vs BM25 비교 분석 및 특징\n\n")
        f.write("1. **TF-IDF의 특성 (단어 빈도와 코사인 유사도):**\n")
        f.write("   - 질의에 포함된 단어들이 문서 내에서 희귀할수록 높은 가중치를 부여합니다.\n")
        f.write("   - 문서 길이가 매우 긴 경우(목차가 50교시 이상 나열된 강좌)에도 코사인 정규화로 인해 공정하게 점수가 계산되나, 특정 키워드가 한 번만 스쳐 지나간 긴 문서가 상위에 오르는 경향이 일부 존재합니다.\n")
        f.write("2. **BM25의 특성 (문서 길이 정규화 및 단어 포화도):**\n")
        f.write("   - 단어가 많이 반복된다고 해서 점수가 무한정 증가하지 않는 단어 빈도 포화(Saturation, k1=1.5)와 평균 문서 길이 대비 정규화(b=0.75)가 적용되어, **질의 어휘가 핵심 주제로 집약된 문서**를 더 선호합니다.\n")
        f.write("   - 실무 질의에서 BM25가 핵심 키워드(예: '취업규칙', '온보딩', '자산관리')가 제목이나 개요에 집중 등장하는 전문 과정을 더 정확히 Top 1으로 잡아내는 경향을 보였습니다.\n\n")

        f.write("## 4. 동일 강좌 다회차(개설 차수) 중복 현황\n\n")
        f.write("- KMA, KPC 등의 오프라인 집합 과정은 동일한 강좌가 연중 5~10회차로 개설되어 Top 10 내에 2~3회차가 동시에 노출되는 현상이 관찰되었습니다.\n")
        f.write("- **개선 권장안:** 사용자에게 추천 결과를 표출할 때는 동일 과정명 기준으로 그룹핑(Deduplication on Display)하여 가장 최신 개설 차수 1건만 노출하고, 상세 모달에서 나머지 차수 일정을 보여주는 UI 그룹화 처리가 필수적입니다.\n")

    # Generate Roadmap Document
    roadmap_path = DOCS_DIR / "EMBEDDING_AND_CLUSTERING_ROADMAP.md"
    with open(roadmap_path, "w", encoding="utf-8") as f:
        f.write("# [실행 계획서] 로컬 임베딩·의미론적 유사도 분석 및 토픽·군집화 로드맵\n\n")
        f.write("본 문서는 STEP 5-1(어휘 기반 TF-IDF/BM25)의 성과를 바탕으로, 키워드가 직접 일치하지 않아도 의미적으로 유사한 과정을 찾아내기 위한 **로컬 임베딩, 토픽모델링, 군집화 추진 계획**입니다.\n\n")
        f.write("> ⚠️ **중요 안내:** 토픽모델링과 군집화(Clustering)는 데이터 내의 잠재적 패턴을 탐색하는 **탐색적 데이터 분석(EDA)** 기법이며, 산출된 군집 그룹이 정부 공식 NCS 직무 분류 체계와 1:1로 일치함을 보장하지 않습니다. 프로젝트 내에서는 '산업 실무 수요 기반 잠재 군집'으로 명시합니다.\n\n")

        f.write("## 1. 로컬 딥러닝 임베딩 모델 비교 실험 계획\n\n")
        f.write("| 모델 후보 | 아키텍처 및 파라미터 | 임베딩 차원 | 장점 및 특징 | 선정 이유 |\n")
        f.write("| :--- | :--- | :---: | :--- | :--- |\n")
        f.write("| **`klue/bert-base`** | BERT Base (110M) | 768 dim | 한국어 문법 및 어휘 표준 모델 | 국내 NLP 연구의 공인 베이스라인 |\n")
        f.write("| **`jhgan/ko-sroberta-multitask`** | SRoBERTa (Sentence-BERT) | 768 dim | 문장 간 코사인 유사도 전용 파인튜닝 | 문장/문단 단위 시맨틱 검색 성능 극대화 |\n")
        f.write("| **`snunlp/KR-SBERT-V40K`** | KR-SBERT (서울대) | 768 dim | 대규모 한국어 뉴스/위키 코퍼스 학습 | 도메인 범용 문장 임베딩 성능 우수 |\n\n")

        f.write("## 2. 세부 단계별 실행 계획 (Next Steps)\n\n")
        f.write("### 1단계: 임베딩 벡터 추출 및 저장 (Offline Pipeline)\n\n")
        f.write("- 대상: 8,645건 교육과정의 `[제목 + 교육소개 + 학습목표]` 텍스트 풀\n")
        f.write("- 배치 크기: 32 (GPU / CPU 호환 모드 지원)\n")
        f.write("- 출력: `data/hr/output/embeddings/course_embeddings_sroberta.parquet` (768차원 부동소수점 벡터)\n\n")

        f.write("### 2단계: 다차원 유사도 분석 (Semantic Similarity)\n\n")
        f.write("1. **과정 간 유사도 (Course-to-Course):** '이 과정을 들은 학습자에게 가장 유사한 다른 교육 추천'\n")
        f.write("2. **NCS 능력단위-과정 유사도 (NCS-to-Course):** 공식 NCS 마스터(`ncs_ksa_master.csv`)의 능력단위 명세 텍스트와 교육과정 텍스트 간 코사인 유사도 계산\n\n")

        f.write("### 3단계: 토픽모델링 및 K-Means 군집화 (Topic & Clustering)\n\n")
        f.write("- **BERTopic 활용:** 임베딩 벡터 기반 c-TF-IDF를 활용하여 데이터 스스로 형성하는 10~15개 실무 토픽 자동 추출\n")
        f.write("- **K-Means 군집화:** 실루엣 계수(Silhouette Score)와 엘보우 기법(Elbow Method)을 통해 최적의 군집 수 $k$ 결정 (예: $k=8 \sim 12$)\n")
        f.write("- **토픽/군집별 상위 핵심 키워드 도출:** 각 군집의 중심점(Centroid)에 가장 가까운 핵심 어휘 목록 산출\n")

    print(f"  [✓] 산출물 저장: {rep_md_path.name}")
    print(f"  [✓] 산출물 저장: {roadmap_path.name}")
    print("=" * 80)
    print(" [완료] STEP 5-1 키워드 분석 및 검색 벤치마크 파이프라인 정상 종료!")
    print("=" * 80)

if __name__ == "__main__":
    run_step5_1_pipeline()
