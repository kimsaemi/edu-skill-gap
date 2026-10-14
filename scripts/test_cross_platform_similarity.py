import pandas as pd
import numpy as np
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load courses and clusters
df_clean = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')
df_cl = pd.read_parquet('data/hr/output/recommendation/course_clusters_8645.parquet')
embeddings = np.load('data/hr/output/recommendation/embeddings_ko_sroberta_all.npy')

df = df_clean.merge(df_cl[['course_uid', 'cluster_id', 'topic_label', 'canonical_platform']], on='course_uid', how='left')

def normalize_title(t):
    t = str(t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t

df['norm_title'] = df['title'].apply(normalize_title)

# Test title similarity & content similarity for a couple of cases
# Case 1: "월급이 낭비되지 않도록, 알기 쉬운 세금 상식"
idx_gseek = df[df['course_uid'] == 'GSEEK_51888'].index[0]
idx_hunet = df[df['course_uid'] == 'HUNET_Y00310480'].index[0]

cos_sim_1 = np.dot(embeddings[idx_gseek], embeddings[idx_hunet])
print(f"Case 1 (Tax course GSEEK vs HUNET):")
print(f"  Title GSEEK: {df.iloc[idx_gseek]['title']}")
print(f"  Title HUNET: {df.iloc[idx_hunet]['title']}")
print(f"  Norm Title Match: {df.iloc[idx_gseek]['norm_title'] == df.iloc[idx_hunet]['norm_title']}")
print(f"  Embedding Cosine Similarity: {cos_sim_1:.4f}")

# Case 2: KPC vs KMA "PM 양성"
pm_courses = df[df['norm_title'] == 'pm 양성']
print(f"\nCase 2 ('pm 양성' courses count: {len(pm_courses)}):")
for idx, r in pm_courses.iterrows():
    print(f"  [{r['canonical_platform']}] {r['title']} | UID: {r['course_uid']}")

if len(pm_courses) >= 2:
    idx_a = pm_courses.index[0]
    idx_b = pm_courses.index[1]
    cos_sim_2 = np.dot(embeddings[idx_a], embeddings[idx_b])
    print(f"  Cosine Similarity between first two PM courses: {cos_sim_2:.4f}")
    print(f"  Intro A: {str(df.iloc[idx_a]['clean_intro'])[:60]}...")
    print(f"  Intro B: {str(df.iloc[idx_b]['clean_intro'])[:60]}...")
