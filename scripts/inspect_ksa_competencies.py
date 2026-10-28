import pandas as pd
import json
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=== 1. Unique Competencies in course_competency_long.parquet ===")
df_comp = pd.read_parquet('data/hr/output/recommendation/course_competency_long.parquet')
unique_comps = df_comp[['competency_id', 'competency_name', 'target_job_family', 'ksa_type']].drop_duplicates().sort_values('competency_id')
for _, r in unique_comps.iterrows():
    print(f"- {r['competency_id']}: {r['competency_name']} | 직무군: {r['target_job_family']} | KSA: {r['ksa_type']}")

print("\n=== 2. Check any KSA or Task definition files in workspace ===")
for p in glob.glob('data/**/ncs*.*', recursive=True) + glob.glob('data/**/ksa*.*', recursive=True) + glob.glob('data/**/competenc*.*', recursive=True):
    print(p)

print("\n=== 3. Check columns in education_courses_search_cleaned.parquet related to KSA ===")
df_clean = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')
ksa_cols = [c for c in df_clean.columns if 'ksa' in c or 'ncs' in c or 'task' in c]
print("KSA/NCS columns in cleaned corpus:", ksa_cols)
if 'ksa_candidates' in df_clean.columns:
    print("Sample ksa_candidates:")
    print(df_clean['ksa_candidates'].dropna().head(3).tolist())
if 'ksa_knowledge' in df_clean.columns:
    print("Sample ksa_knowledge / skill / attitude:")
    print("Knowledge:", df_clean['ksa_knowledge'].dropna().head(2).tolist())
    print("Skill:", df_clean['ksa_skill'].dropna().head(2).tolist())
    print("Attitude:", df_clean['ksa_attitude'].dropna().head(2).tolist())
