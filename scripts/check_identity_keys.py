import pandas as pd
import numpy as np
import pickle
import re
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
import hashlib

# Load data and preprocessing
df = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

# Define deduplication key
def get_course_identity_key(row):
    prov = str(row["provider"] or "").strip()
    title = str(row["title"] or "").strip()
    curric = str(row["curriculum"] or "").strip()
    # Curriculum signature (first 100 chars or hash to confirm it's same curriculum)
    curric_sig = hashlib.md5(curric.encode("utf-8")).hexdigest()[:8] if curric else "no_curric"
    
    # Extract base course id from course_uid if possible:
    # KPC_47199_150944 -> KPC_47199
    # KMA_110936_124341 -> KMA_110936
    # PUB_ACG..._4 -> PUB_ACG...
    uid = str(row["course_uid"] or "")
    parts = uid.split("_")
    if len(parts) >= 3 and parts[0] in ["KPC", "KMA", "PUB"]:
        base_id = f"{parts[0]}_{parts[1]}"
    else:
        base_id = uid
        
    return (prov, title, base_id)

df["identity_key"] = df.apply(get_course_identity_key, axis=1)
print(f"Total rows: {len(df):,}, Unique identity keys: {df['identity_key'].nunique():,}")
