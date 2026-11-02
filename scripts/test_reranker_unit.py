# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from src.recommendation.cross_encoder_reranker import KoreanCrossEncoderReranker
from scripts.new_57_tasks_definition import NEW_TASKS_57
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender
from src.recommendation.hr_task_catalog import task_semantic_query, task_keyword_query, task_anchor_query, GENERIC_TASK_TOKENS

print("Loading Recommender and Reranker...")
engine = UnifiedHybridRecommender()
reranker = KoreanCrossEncoderReranker()

# Test Case 1: HR06-02 (성과급·인센티브 제도 설계) - Was contaminated by 자금세탁방지
t = [x for x in NEW_TASKS_57 if x['task_id'] == 'HR06-02'][0]
query = task_semantic_query(t)
df_rec, *_ = engine.recommend(
    query=query,
    keyword_query=task_keyword_query(t),
    keyword_stopwords=GENERIC_TASK_TOKENS,
    anchor_query=task_anchor_query(t),
    target_domain="인사",
    user_level="입문",
    cluster_boost=0.0,
    filter_mismatch_109=True,
    top_n=15,
    mode="general"
)

print("\n=== Test 1: HR06-02 (성과급·인센티브 제도 및 산정기준 설계) ===")
print("--- [Before Re-ranking: 1단계 Bi-Encoder + BM25] ---")
for idx, r in df_rec.head(5).iterrows():
    print(f"  [{r['provider']}] {r['title']} | Final: {r['final_score']} | Sem: {r['semantic_score']}")

df_reranked = reranker.rerank(query, df_rec, top_k=3)
print("\n--- [After Re-ranking: 2단계 Cross-Encoder 정밀 평가] ---")
for idx, r in df_reranked.iterrows():
    print(f"  [{r['provider']}] {r['title']} | RerankerScore: {r['reranker_score']} | Blended: {r['reranked_final_score']}")


# Test Case 2: HR09-03 (이러닝·마이크로러닝 과정 개설·운영) - Was contaminated by 비즈니스 이메일
t2 = [x for x in NEW_TASKS_57 if x['task_id'] == 'HR09-03'][0]
query2 = task_semantic_query(t2)
df_rec2, *_ = engine.recommend(
    query=query2,
    keyword_query=task_keyword_query(t2),
    keyword_stopwords=GENERIC_TASK_TOKENS,
    anchor_query=task_anchor_query(t2),
    target_domain="인사",
    user_level="실무",
    cluster_boost=0.0,
    filter_mismatch_109=True,
    top_n=15,
    mode="general"
)

print("\n=== Test 2: HR09-03 (이러닝·마이크로러닝 과정 개설·운영) ===")
print("--- [Before Re-ranking: 1단계 Bi-Encoder + BM25] ---")
for idx, r in df_rec2.head(5).iterrows():
    print(f"  [{r['provider']}] {r['title']} | Final: {r['final_score']} | Sem: {r['semantic_score']}")

df_reranked2 = reranker.rerank(query2, df_rec2, top_k=3)
print("\n--- [After Re-ranking: 2단계 Cross-Encoder 정밀 평가] ---")
for idx, r in df_reranked2.iterrows():
    print(f"  [{r['provider']}] {r['title']} | RerankerScore: {r['reranker_score']} | Blended: {r['reranked_final_score']}")

