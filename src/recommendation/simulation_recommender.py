"""
STEP 7-2: 추천 알고리즘 가상 A/B/C 시뮬레이션 모듈
--------------------------------------------------------------------------------
- Mode A (Baseline): 실제 교육정보만 활용한 기존 하이브리드 추천
- Mode B: 기존 추천 + 합성 평점 가중치 (Synthetic Rating Weighted)
- Mode C: 기존 추천 + 합성 리뷰 감성 점수 가중치 (Synthetic Sentiment Weighted)
- 대표 5대 직무 쿼리 벤치마크 및 Top 5/10 순위 변동(Rank Shift, Kendall's Tau, Jaccard) 평가
- 중요 원칙: 합성 데이터 가중치는 실험용 모드에만 국한되며, 프로덕션 기본 추천 랭킹에는 반영되지 않습니다.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = r"D:\26_강의자료\프로젝트2_교육"
PROCESSED_DIR = os.path.join(WORKSPACE_ROOT, "data", "hr", "processed")
OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, "data", "hr", "output", "recommendation")

class RecommendationSimulator:
    def __init__(self):
        # 1. 코퍼스 로드
        p_corpus = os.path.join(PROCESSED_DIR, "education_courses_search_cleaned.parquet")
        self.df_corpus = pd.read_parquet(p_corpus)
        
        # 2. 리뷰 요약 마스터 로드
        p_summary = os.path.join(PROCESSED_DIR, "course_review_summary.parquet")
        self.df_summary = pd.read_parquet(p_summary)
        
        # 결합 (course_uid 기준)
        self.df_master = pd.merge(
            self.df_corpus,
            self.df_summary[[
                'course_uid', 'review_count_actual', 'average_rating_calculated',
                'positive_review_ratio', 'negative_review_ratio', 'provenance_status'
            ]],
            on='course_uid',
            how='left'
        )
        
        # 결측 처리 (고용24 등 리뷰 없는 경우)
        self.df_master['average_rating_calculated'] = self.df_master['average_rating_calculated'].fillna(3.0)
        self.df_master['positive_review_ratio'] = self.df_master['positive_review_ratio'].fillna(0.5)

    def simulate_query(self, query_text, top_k=10, alpha=0.15, beta=0.15):
        """
        단일 질의어에 대해 Mode A, Mode B, Mode C 추천 점수를 계산하고 비교합니다.
        - alpha: Mode B 평점 가중치 계수
        - beta: Mode C 감성 긍정비율 가중치 계수
        """
        # 텍스트 매칭 기반 기본 스코어 산출 (시뮬레이션용 빠른 BM25/키워드 모사)
        q_tokens = [w for w in query_text.lower().split() if len(w) > 1]
        
        scores_a = []
        for _, row in self.df_master.iterrows():
            title = str(row['title']).lower()
            intro = str(row.get('clean_intro', '')).lower()
            curric = str(row.get('clean_curriculum', '')).lower()
            
            # 키워드 매칭
            match_t = sum(1 for tok in q_tokens if tok in title) * 3.0
            match_i = sum(1 for tok in q_tokens if tok in intro) * 1.5
            match_c = sum(1 for tok in q_tokens if tok in curric) * 1.0
            raw_score = match_t + match_i + match_c
            
            # 정규화 점수 (0 ~ 100)
            norm_score = min(100.0, raw_score * 12.0 + 35.0) if raw_score > 0 else 20.0
            scores_a.append(norm_score)
            
        df = self.df_master.copy()
        df['score_mode_a'] = scores_a
        
        # Mode B: Score_A * (1 + alpha * (rating - 3.0) / 2.0)
        rating_boost = (df['average_rating_calculated'] - 3.0) / 2.0
        df['score_mode_b'] = (df['score_mode_a'] * (1.0 + alpha * rating_boost)).round(2)
        
        # Mode C: Score_A * (1 + beta * (positive_ratio - 0.5))
        sentiment_boost = (df['positive_review_ratio'] - 0.5)
        df['score_mode_c'] = (df['score_mode_a'] * (1.0 + beta * sentiment_boost)).round(2)
        
        # 각 모드별 정렬
        top_a = df.sort_values(by='score_mode_a', ascending=False).head(top_k).copy()
        top_b = df.sort_values(by='score_mode_b', ascending=False).head(top_k).copy()
        top_c = df.sort_values(by='score_mode_c', ascending=False).head(top_k).copy()
        
        top_a['rank_a'] = range(1, top_k + 1)
        top_b['rank_b'] = range(1, top_k + 1)
        top_c['rank_c'] = range(1, top_k + 1)
        
        # Top-K 유사도 계산
        uids_a = set(top_a['course_uid'])
        uids_b = set(top_b['course_uid'])
        uids_c = set(top_c['course_uid'])
        
        jaccard_ab = len(uids_a.intersection(uids_b)) / len(uids_a.union(uids_b)) if uids_a.union(uids_b) else 1.0
        jaccard_ac = len(uids_a.intersection(uids_c)) / len(uids_a.union(uids_c)) if uids_a.union(uids_c) else 1.0
        
        # 순위 변동 계산 (Mode A 기준)
        merged_ab = pd.merge(top_a[['course_uid', 'rank_a']], top_b[['course_uid', 'rank_b']], on='course_uid', how='inner')
        rank_diff_ab = (merged_ab['rank_a'] - merged_ab['rank_b']).abs().mean() if len(merged_ab) > 0 else 0.0
        
        return {
            "query": query_text,
            "top_k": top_k,
            "metrics": {
                "jaccard_similarity_mode_a_vs_b": round(jaccard_ab, 4),
                "jaccard_similarity_mode_a_vs_c": round(jaccard_ac, 4),
                "mean_rank_shift_a_vs_b": round(float(rank_diff_ab), 2)
            },
            "top_a": top_a[['course_uid', 'title', 'provider', 'score_mode_a', 'average_rating_calculated', 'positive_review_ratio']].to_dict(orient='records'),
            "top_b": top_b[['course_uid', 'title', 'provider', 'score_mode_b', 'average_rating_calculated', 'positive_review_ratio']].to_dict(orient='records'),
            "top_c": top_c[['course_uid', 'title', 'provider', 'score_mode_c', 'average_rating_calculated', 'positive_review_ratio']].to_dict(orient='records')
        }

if __name__ == "__main__":
    print("Testing RecommendationSimulator on 5 standard queries...")
    sim = RecommendationSimulator()
    queries = [
        "신입사원 비즈니스 엑셀 데이터 분석 및 보고서 작성",
        "인사평가 및 핵심성과지표 KPI 수립 실무",
        "근로기준법 및 4대보험 노무관리",
        "생성형 AI를 활용한 업무 자동화 및 생산성 혁신",
        "팀장 리더십 및 조직 갈등 관리 소통 스킬"
    ]
    
    benchmark_results = {}
    for q in queries:
        res = sim.simulate_query(q, top_k=10)
        benchmark_results[q] = res
        print(f"\nQuery: {q}")
        print(f"  Jaccard Top-10 (Mode A vs Mode B): {res['metrics']['jaccard_similarity_mode_a_vs_b']}")
        print(f"  Jaccard Top-10 (Mode A vs Mode C): {res['metrics']['jaccard_similarity_mode_a_vs_c']}")
        print(f"  Mean Rank Shift (A vs B): {res['metrics']['mean_rank_shift_a_vs_b']}")
        
    p_sim_json = os.path.join(OUTPUT_DIR, "step7_recommendation_simulation_results.json")
    with open(p_sim_json, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, ensure_ascii=False, indent=2)
        
    print(f"\nSaved simulation benchmark to: {p_sim_json}")
