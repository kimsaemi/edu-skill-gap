import pandas as pd
import time
import os
import sys

sys.path.insert(0, os.path.abspath("."))
from src.recommendation.text_preprocessor import HRTextPreprocessor

cache_path = "data/hr/processed/tokenized_corpus_cache.parquet"

if os.path.exists(cache_path):
    print(f"Tokenized cache already exists: {cache_path}")
else:
    print("Pre-tokenizing corpus for instant Streamlit startup...")
    df = pd.read_parquet("data/hr/processed/education_courses_search_cleaned.parquet")
    prep = HRTextPreprocessor()
    
    t0 = time.time()
    token_strings = []
    for txt in df["clean_search_text"]:
        toks = prep.tokenize(txt)
        token_strings.append(" ".join(toks) if toks else "기초")
        
    df_cache = pd.DataFrame({
        "course_uid": df["course_uid"],
        "tokenized_text": token_strings
    })
    
    df_cache.to_parquet(cache_path, compression="zstd")
    print(f"Saved tokenized cache to {cache_path} ({len(df_cache)} rows) in {time.time()-t0:.1f}s")
