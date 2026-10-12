import pandas as pd
import pickle
import time
import os
import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from rank_bm25 import BM25Okapi

sys.path.insert(0, os.path.abspath("."))
from src.recommendation.text_preprocessor import HRTextPreprocessor

cache_file = "data/hr/output/recommendation/search_models_cache.pkl"

if os.path.exists(cache_file):
    print(f"Cache file already exists: {cache_file}")
else:
    print("Building search models cache for instantaneous Streamlit loading...")
    df = pd.read_parquet("data/hr/processed/education_courses_search_cleaned.parquet")
    preprocessor = HRTextPreprocessor()
    
    t0 = time.time()
    corpus_tokens = []
    for txt in df["clean_search_text"]:
        toks = preprocessor.tokenize(txt)
        corpus_tokens.append(toks if toks else ["기초"])
        
    vectorizer = TfidfVectorizer(tokenizer=preprocessor.tokenize, min_df=2, max_df=0.8, sublinear_tf=True)
    tfidf_matrix = vectorizer.fit_transform(df["clean_search_text"])
    bm25 = BM25Okapi(corpus_tokens)
    
    with open(cache_file, "wb") as f:
        pickle.dump({
            "vectorizer": vectorizer,
            "tfidf_matrix": tfidf_matrix,
            "bm25": bm25,
            "corpus_tokens": corpus_tokens
        }, f)
        
    print(f"Cache successfully saved to {cache_file} in {time.time()-t0:.1f}s!")
