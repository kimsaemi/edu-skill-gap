import sqlite3
import pandas as pd
import numpy as np
import glob, os

def inspect_raw_dbs():
    print("=== 1. RAW DB INSPECTION ===")
    dbs = [
        'data/courses/kfo_courses.db',
        'data/courses/multicampus_courses.db',
        'data/courses/hunet_courses.db',
        'data/courses/gseek_courses.db',
        'data/courses/kma_courses.db',
        'data/courses/kpc_courses.db',
        'data/SQLite/fastcampus_courses.db'
    ]
    for db in dbs:
        if os.path.exists(db):
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            counts = {}
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                counts[t] = cur.fetchone()[0]
            print(f"{db}: {counts}")
            conn.close()
        else:
            print(f"{db}: NOT FOUND")

def inspect_cleaned_parquet():
    print("\n=== 2. PARQUET INSPECTION ===")
    df = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')
    print("Columns in education_courses_search_cleaned.parquet:", df.columns.tolist())
    print("Shape:", df.shape)
    print("Value counts of provider:")
    print(df['provider'].value_counts(dropna=False))
    if 'source_provider' in df.columns:
        print("\nValue counts of source_provider:")
        print(df['source_provider'].value_counts(dropna=False))

    # Also inspect education_courses_integrated.parquet if exists
    if os.path.exists('data/hr/processed/education_courses_integrated.parquet'):
        df_int = pd.read_parquet('data/hr/processed/education_courses_integrated.parquet')
        print("\nColumns in education_courses_integrated.parquet:", df_int.columns.tolist())
        print("Shape:", df_int.shape)
        if 'provider' in df_int.columns:
            print(df_int['provider'].value_counts(dropna=False))
        if 'source_provider' in df_int.columns:
            print(df_int['source_provider'].value_counts(dropna=False))

def inspect_embeddings_and_metadata():
    print("\n=== 3. EMBEDDINGS & METADATA ===")
    emb = np.load('data/hr/output/recommendation/embeddings_ko_sroberta_all.npy')
    meta = pd.read_parquet('data/hr/output/recommendation/course_embeddings_metadata_all.parquet')
    df = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')
    print("Embedding shape:", emb.shape)
    print("Metadata shape:", meta.shape)
    print("Cleaned parquet shape:", df.shape)
    is_matching = (df['course_uid'] == meta['course_uid']).all()
    print("UID 1:1 order match:", is_matching)

if __name__ == '__main__':
    inspect_raw_dbs()
    inspect_cleaned_parquet()
    inspect_embeddings_and_metadata()
