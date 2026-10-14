import pandas as pd
import numpy as np

for path in [
    'data/hr/processed/education_courses_search_cleaned.parquet',
    'data/hr/output/recommendation/course_embeddings_metadata_all.parquet',
    'data/hr/output/recommendation/course_keyword_long.parquet',
    'data/hr/output/recommendation/course_competency_long.parquet'
]:
    df = pd.read_parquet(path)
    print(f"\n=== {path} ===")
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist()[:15])
    print("Sample:\n", df.head(2))

emb = np.load('data/hr/output/recommendation/embeddings_ko_sroberta_all.npy')
print("\n=== embeddings_ko_sroberta_all.npy ===")
print("Shape:", emb.shape, "Dtype:", emb.dtype)
