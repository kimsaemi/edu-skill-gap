"""
BM25 기반 교육과정 정보 검색 엔진 모듈
- rank_bm25.BM25Okapi 알고리즘 활용
- 문서 길이 정규화 및 단어 빈도 포화도(Saturation) 반영
"""
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from src.recommendation.text_preprocessor import HRTextPreprocessor

class BM25SearchEngine:
    def __init__(self, preprocessor: HRTextPreprocessor = None):
        self.preprocessor = preprocessor or HRTextPreprocessor()
        self.bm25 = None
        self.df_corpus = None
        self.tokenized_corpus = []
        self.is_fitted = False

    def fit(self, df_corpus: pd.DataFrame, text_col: str = "search_text"):
        """코퍼스 데이터셋으로 토큰화 및 BM25 인덱스 구축"""
        self.df_corpus = df_corpus.reset_index(drop=True)
        texts = self.df_corpus[text_col].fillna("").astype(str).tolist()
        self.tokenized_corpus = [self.preprocessor.tokenize(t) for t in texts]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        self.is_fitted = True
        return self

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """사용자 검색어로 BM25 관련도 점수 기반 상위 과정 도출"""
        if not self.is_fitted:
            raise ValueError("BM25 engine is not fitted yet. Call fit() first.")

        query_tokens = self.preprocessor.tokenize(query)
        if not query_tokens:
            return []

        # BM25 스코어 계산
        scores = self.bm25.get_scores(query_tokens)
        
        # 상위 top_k 인덱스 추출 (내림차순)
        ranked_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(ranked_indices, start=1):
            score = float(scores[idx])
            row = self.df_corpus.iloc[idx]
            doc_tokens = set(self.tokenized_corpus[idx])
            
            # 쿼리와 실제 매칭된 토큰 교집합
            matched_tokens = [q for q in query_tokens if q in doc_tokens]

            results.append({
                "rank": rank,
                "global_course_key": row.get("global_course_key"),
                "course_name": row.get("course_name"),
                "source_platform": row.get("source_platform"),
                "ncs_code": row.get("ncs_code"),
                "bm25_score": round(score, 4),
                "matched_keywords": list(dict.fromkeys(matched_tokens))[:5],
                "training_hours": row.get("training_hours"),
                "total_course_fee": row.get("total_course_fee"),
                "learner_cost": row.get("learner_cost"),
                "source_url": row.get("source_url"),
                "text_source_status": row.get("text_source_status")
            })

        return results
