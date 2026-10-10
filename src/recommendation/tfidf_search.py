"""
TF-IDF 기반 교육과정 어휘 검색 엔진 모듈
- scikit-learn TfidfVectorizer & 코사인 유사도 활용
- 인사·총무 전문 형태소 분석 결합
"""
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.recommendation.text_preprocessor import HRTextPreprocessor

class TFIDFSearchEngine:
    def __init__(self, preprocessor: HRTextPreprocessor = None):
        self.preprocessor = preprocessor or HRTextPreprocessor()
        self.vectorizer = TfidfVectorizer(
            tokenizer=self._tokenizer_wrapper,
            token_pattern=None,
            min_df=1,
            sublinear_tf=True
        )
        self.df_corpus = None
        self.tfidf_matrix = None
        self.is_fitted = False

    def _tokenizer_wrapper(self, text: str) -> List[str]:
        return self.preprocessor.tokenize(text)

    def fit(self, df_corpus: pd.DataFrame, text_col: str = "search_text"):
        """코퍼스 데이터셋으로 TF-IDF 행렬 학습 및 적재"""
        self.df_corpus = df_corpus.reset_index(drop=True)
        texts = self.df_corpus[text_col].fillna("").astype(str).tolist()
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        self.is_fitted = True
        return self

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """사용자 검색어로 코사인 유사도 기반 상위 과정 도출"""
        if not self.is_fitted:
            raise ValueError("Search engine is not fitted yet. Call fit() first.")
        
        query_tokens = self.preprocessor.tokenize(query)
        if not query_tokens:
            return []

        # 쿼리 벡터 변환 및 코사인 유사도 계산
        query_vec = self.vectorizer.transform([query])
        sim_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # 상위 top_k 인덱스 추출 (내림차순)
        ranked_indices = np.argsort(sim_scores)[::-1][:top_k]

        results = []
        feature_names = np.array(self.vectorizer.get_feature_names_out())
        
        for rank, idx in enumerate(ranked_indices, start=1):
            score = float(sim_scores[idx])
            row = self.df_corpus.iloc[idx]
            
            # 매칭된 주요 단어 식별
            doc_vec = self.tfidf_matrix[idx].toarray().flatten()
            overlap_words = [token for token in query_tokens if token in self.vectorizer.vocabulary_]
            
            matched_keywords = []
            for w in overlap_words:
                w_idx = self.vectorizer.vocabulary_[w]
                if doc_vec[w_idx] > 0:
                    matched_keywords.append((w, float(doc_vec[w_idx])))
            matched_keywords.sort(key=lambda x: x[1], reverse=True)
            
            results.append({
                "rank": rank,
                "global_course_key": row.get("global_course_key"),
                "course_name": row.get("course_name"),
                "source_platform": row.get("source_platform"),
                "ncs_code": row.get("ncs_code"),
                "similarity_score": round(score, 4),
                "matched_keywords": [w for w, _ in matched_keywords[:5]],
                "training_hours": row.get("training_hours"),
                "total_course_fee": row.get("total_course_fee"),
                "learner_cost": row.get("learner_cost"),
                "source_url": row.get("source_url"),
                "text_source_status": row.get("text_source_status")
            })

        return results
