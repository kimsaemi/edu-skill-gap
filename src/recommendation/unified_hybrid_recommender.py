"""
통합 하이브리드 추천 엔진 공통 모듈 (Unified Hybrid Recommender)
- 8,645건 통합 교육 코퍼스 대상 Ko-SRoBERTa 딥러닝(768차원) + BM25 Okapi + 난이도 통합 (수강 리뷰·평점 미사용)
- 직무(인사·총무·경영지원) 및 8대 KSA 역량 기반 맞춤형 스코어링 모드(KSA Mode) 완전 통합
- 세부 조건 Faceted Filtering (비용 결측 왜곡 차단, 시간 경계값)
- 오매핑 109건 조건부 선별 차단 (96건 차단 / 13건 보존 엄격 재현 및 추적)
- 가변 군집 부스팅 (기본값 0.0점 ~ 실험값 5.0점) 및 KSA 보조매핑 점수 명확한 분리
- 크로스 플랫폼 실제 동일 강좌 중복 제거 및 대체 수강 옵션(무료 필터 시 유료 대안 보존 등)
- 분석 스크립트(step8) 및 Streamlit 대시보드(탭 8, 탭 10) 공통 재사용
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from src.recommendation.ksa_master import (
    KSA_COMPETENCIES_MASTER,
    DOMAIN_CLUSTER_MAP,
    get_competency_by_id,
    get_job_cluster_ids
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data" / "hr"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "output" / "recommendation"


class UnifiedHybridRecommender:
    """통합 하이브리드 추천 엔진 코어 클래스 (탭 8 및 탭 10 공통 엔진)"""

    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._load_data()
        self._init_models()

    def _load_data(self):
        # 1. 정제 코퍼스 8,645건
        p_clean = PROCESSED_DIR / "education_courses_search_cleaned.parquet"
        self.df_courses = pd.read_parquet(p_clean)

        # 2. STEP 5-3 10대 군집 데이터셋 병합
        p_clusters = OUTPUT_DIR / "course_clusters_8645.parquet"
        if p_clusters.exists():
            df_cl = pd.read_parquet(p_clusters)
            # UID 중복 방지 및 안전 매핑
            if 'canonical_platform' not in df_cl.columns and 'canonical_platform' in self.df_courses.columns:
                cl_cols = ['course_uid', 'cluster_id', 'topic_label']
            else:
                cl_cols = ['course_uid', 'cluster_id', 'topic_label', 'canonical_platform']
            
            self.df_courses = self.df_courses.merge(
                df_cl[[c for c in cl_cols if c in df_cl.columns]],
                on='course_uid',
                how='left'
            )
            if 'canonical_platform' not in self.df_courses.columns:
                self.df_courses['canonical_platform'] = self.df_courses['provider']
            else:
                self.df_courses['canonical_platform'] = self.df_courses['canonical_platform'].fillna(self.df_courses['provider'])
        else:
            self.df_courses['cluster_id'] = 0
            self.df_courses['topic_label'] = "미분류"
            self.df_courses['canonical_platform'] = self.df_courses['provider']

        # 3. Ko-SRoBERTa 768차원 임베딩 (안전 로드 및 폴백)
        p_emb = OUTPUT_DIR / "embeddings_ko_sroberta_all.npy"
        if p_emb.exists():
            self.embeddings = np.load(p_emb)
            if len(self.embeddings) == len(self.df_courses):
                self.has_embeddings = True
            else:
                # 길이 불일치 시 안전 폴백
                self.embeddings = np.zeros((len(self.df_courses), 768), dtype=np.float32)
                self.has_embeddings = False
        else:
            self.embeddings = np.zeros((len(self.df_courses), 768), dtype=np.float32)
            self.has_embeddings = False

        # 4. 토큰화 캐시 (BM25)
        p_tok = PROCESSED_DIR / "tokenized_corpus_cache.parquet"
        if p_tok.exists():
            self.df_tokens = pd.read_parquet(p_tok)
            self.df_courses = self.df_courses.merge(self.df_tokens[['course_uid', 'tokenized_text']], on='course_uid', how='left')
            self.df_courses['tokenized_text'] = self.df_courses['tokenized_text'].fillna('')
        else:
            self.df_courses['tokenized_text'] = ''

        # 4-0. 강좌 분야 라벨 (scripts/build_course_field_labels.py, 업무별 추천의 분야 판정용)
        p_field = OUTPUT_DIR / "course_field_labels.csv"
        if p_field.exists():
            df_field = pd.read_csv(p_field, encoding="utf-8-sig", usecols=["course_uid", "field", "field_margin"])
            self.df_courses = self.df_courses.merge(df_field, on="course_uid", how="left")
        else:
            self.df_courses["field"] = None
            self.df_courses["field_margin"] = None

        # 4-1. 직무교육과 무관한 강좌 제외 목록 (scripts/build_off_topic_exclusions.py)
        p_offtopic = PROCESSED_DIR / "off_topic_exclusions.csv"
        self.off_topic_uids: Set[str] = set()
        if p_offtopic.exists():
            self.off_topic_uids = set(pd.read_csv(p_offtopic, encoding="utf-8-sig")["course_uid"].astype(str))

        # 5. 오매핑 의심 109건 목록 및 선별 차단 정책 사전 계산
        p_mismatch = OUTPUT_DIR / "mapping_mismatch_samples.json"
        self.mismatch_109_uids: Set[str] = set()
        self.excluded_109_uids: Set[str] = set()
        self.preserved_109_uids: Set[str] = set()

        if p_mismatch.exists():
            with open(p_mismatch, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.mismatch_109_uids = {item['course_uid'] for item in data if 'course_uid' in item}

            # 10대 군집 기준 선별 차단 규칙:
            # 비-HR 군집: C0(데이터/AI), C6(스마트워크 코딩/프롬프트), C7(어학/글로벌)
            # IT 키워드: 파이썬, 코딩, 개발, 서버, Spring, Docker, AWS, 클라우드, Java, React, 자바
            is_109 = self.df_courses['course_uid'].isin(self.mismatch_109_uids)
            is_non_hr_cluster = self.df_courses['cluster_id'].isin([0, 6, 7])
            title_it_term = self.df_courses['title'].str.contains(
                '파이썬|코딩|개발|서버|Spring|Docker|AWS|클라우드|Java|React|자바',
                case=False, na=False
            )
            mismatch_exclude = is_109 & (is_non_hr_cluster | title_it_term)
            self.excluded_109_uids = set(self.df_courses.loc[mismatch_exclude, 'course_uid'])
            self.preserved_109_uids = set(self.df_courses.loc[is_109 & ~mismatch_exclude, 'course_uid'])

        # 6. KSA 보조 매핑 데이터 (course_competency_long.parquet)
        p_comp_long = OUTPUT_DIR / "course_competency_long.parquet"
        if p_comp_long.exists():
            self.df_comp_long = pd.read_parquet(p_comp_long)
        else:
            self.df_comp_long = pd.DataFrame()

        # 수치형 변환 및 결측치 안전 처리
        self.df_courses['numeric_price'] = pd.to_numeric(self.df_courses['price'], errors='coerce')
        self.df_courses['numeric_duration'] = pd.to_numeric(self.df_courses['duration_hours'], errors='coerce')

        # 가격 상태 정의: FREE, PAID, UNCONFIRMED
        price_is_na = self.df_courses['numeric_price'].isna()
        is_free = (self.df_courses['numeric_price'] == 0) & (~price_is_na)
        self.df_courses['price_status'] = 'PAID'
        self.df_courses.loc[price_is_na, 'price_status'] = 'UNCONFIRMED'
        self.df_courses.loc[is_free, 'price_status'] = 'FREE'

        # 정규화 강좌명 사전 생성 (대괄호, 소괄호, 특수기호 제거)
        self.df_courses['norm_title'] = self.df_courses['title'].apply(self.normalize_course_title)

        # O(1) 인덱스 역방향 매핑 딕셔너리
        self.uid_to_idx = {uid: idx for idx, uid in enumerate(self.df_courses['course_uid'])}

        # O(1) 정규화 강좌명 -> 코퍼스 인덱스 목록 (크로스 플랫폼 대체 수강처 초고속 매핑용)
        self.norm_title_to_indices: Dict[str, List[int]] = {}
        for idx, n_title in enumerate(self.df_courses['norm_title']):
            if len(n_title) >= 4:
                self.norm_title_to_indices.setdefault(n_title, []).append(idx)

        # KSA (course_uid, competency_id) 검증용 튜플 세트 사전 생성 (8,291건 1회만 계산)
        self.ksa_pair_set = set(zip(self.df_comp_long['course_uid'], self.df_comp_long['competency_id'])) if not self.df_comp_long.empty else set()

        # 정적 표시 포맷 사전 생성 (8,645건 전수 대상 최초 1회만 계산하여 쿼리 시점 반복 연산 제거)
        self.df_courses['price_display'] = self.df_courses['numeric_price'].apply(self.format_price)
        self.df_courses['duration_display'] = self.df_courses['numeric_duration'].apply(self.format_duration)

        def get_mismatch_status(uid):
            if uid in self.excluded_109_uids:
                return "🚨 [오매핑 차단]"
            elif uid in self.preserved_109_uids:
                return "🛡️ [오매핑 보존 (유효 강좌)]"
            else:
                return "✅ [정상 검증 강좌]"

        self.df_courses['mismatch_status'] = self.df_courses['course_uid'].apply(get_mismatch_status)

        # 데이터 버전 및 모델 버전 식별자 (캐시 키 무효화용)
        p_clean = PROCESSED_DIR / "education_courses_search_cleaned.parquet"
        self.model_version = "jhgan/ko-sroberta-multitask"
        self.data_version = f"corpus_{len(self.df_courses)}_{p_clean.stat().st_mtime if p_clean.exists() else 'v1'}"

        # 질의 인코딩 캐시 (최대 256개)
        self._query_vector_cache: Dict[str, np.ndarray] = {}

        # 추천 결과 캐시 (최대 128개, TTL 1시간)
        self._rec_cache: Dict[Tuple, Tuple[pd.DataFrame, int, int, int, str]] = {}
        self._rec_cache_timestamps: Dict[Tuple, float] = {}
        self._rec_cache_ttl: float = 3600.0
        self._rec_cache_max: int = 128

    def _doc_token_sets(self) -> List[Set[str]]:
        """강좌별 검색 토큰 집합 (핵심어 일치 판정용, 최초 1회 생성)."""
        if not hasattr(self, "_doc_token_sets_cache"):
            self._doc_token_sets_cache = [set(str(t).split()) for t in self.df_courses['tokenized_text']]
        return self._doc_token_sets_cache

    def _doc_freq(self) -> Dict[str, int]:
        """토큰별 등장 강좌 수 (최초 1회 생성)."""
        if not hasattr(self, "_doc_freq_cache"):
            from collections import Counter
            self._doc_freq_cache = Counter(t for s in self._doc_token_sets() for t in s)
        return self._doc_freq_cache

    def _keyword_tokens(self, text: str, use_kiwi: bool = True) -> List[str]:
        """BM25 질의 토큰: 코퍼스와 같은 Kiwi 명사 토큰화를 적용하고, 공백 분리 토큰도 함께 사용합니다."""
        if not text or not text.strip():
            return []
        if not use_kiwi:
            return [t for t in text.split() if t in self.bm25_vocab]
        if not hasattr(self, "_query_tokenizer"):
            try:
                from src.recommendation.text_preprocessor import HRTextPreprocessor
                self._query_tokenizer = HRTextPreprocessor()
            except Exception:
                self._query_tokenizer = None
        tokens = text.split()
        if self._query_tokenizer is not None:
            try:
                tokens = tokens + self._query_tokenizer.tokenize(text)
            except Exception:
                pass
        seen, result = set(), []
        for t in tokens:
            if t in self.bm25_vocab and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def _init_models(self):
        # BM25 초기화
        corpus_tokens = [txt.split() for txt in self.df_courses['tokenized_text']]
        self.bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
        self.bm25_vocab = {t for toks in corpus_tokens for t in toks}

        # Ko-SRoBERTa 질의 인코더 로드
        if self.has_embeddings:
            try:
                self.model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=self.device)
            except Exception as e:
                print(f"[WARN] SentenceTransformer 모델 로드 실패: {e}. BM25 모드로 폴백합니다.")
                self.model = None
                self.has_embeddings = False
        else:
            self.model = None

    @staticmethod
    def normalize_course_title(t: str) -> str:
        """강좌명의 대괄호, 소괄호 태그 및 특수문자를 제거하여 정규화합니다."""
        t = str(t)
        t = re.sub(r'\[.*?\]', '', t)
        t = re.sub(r'\(.*?\)', '', t)
        t = re.sub(r'[^\w\s]', ' ', t)
        # 띄어쓰기만 다른 동일 강좌(예: '운영실무' / '운영 실무')를 같은 강좌로 보도록 공백 제거
        t = re.sub(r'\s+', '', t).strip().lower()
        return t

    def filter_candidates(
        self,
        target_domain: str = None,
        platforms: list = None,
        price_filter: str = "ALL",  # "ALL", "FREE_ONLY", "MAX_BUDGET"
        max_budget: int = None,
        edu_type: str = "ALL",  # "ALL", "ONLINE", "OFFLINE"
        durations: list = None,  # ["SHORT", "MEDIUM", "LONG", "UNCONFIRMED"]
        difficulties: list = None,
        filter_mismatch_109: bool = True
    ) -> Tuple[np.ndarray, int, int]:
        """
        1단계: 사용자 조건 필터링 및 오매핑 의심 강좌 조건부 선별
        - 반환: (유효 인덱스 np.ndarray, 제외된 109건 수, 유지된 109건 수)
        """
        df = self.df_courses
        mask = np.ones(len(df), dtype=bool)

        # 0. 직무교육과 무관한 강좌 제외
        if self.off_topic_uids:
            mask &= ~df['course_uid'].astype(str).isin(self.off_topic_uids).values

        # 1. 플랫폼 필터
        if platforms:
            mask &= df['canonical_platform'].isin(platforms)

        # 2. 가격 필터 (결측치 왜곡 차단: 결측치는 무료로 취급하지 않음)
        if price_filter == "FREE_ONLY":
            mask &= (df['price_status'] == 'FREE')
        elif price_filter == "MAX_BUDGET" and max_budget is not None and max_budget != "전체":
            b_val = int(max_budget)
            if b_val == 0:
                mask &= (df['price_status'] == 'FREE')
            else:
                mask &= (
                    (df['price_status'] == 'FREE') |
                    ((df['price_status'] == 'PAID') & (df['numeric_price'] <= b_val))
                )

        # 3. 교육 형태 필터
        if edu_type in ["ONLINE", "온라인"]:
            mask &= df['education_type'].astype(str).str.contains('온라인|사이버|원격|플립|동영상|VOD', na=False)
        elif edu_type in ["OFFLINE", "오프라인"]:
            mask &= df['education_type'].astype(str).str.contains('오프라인|집체|현장|집합', na=False)

        # 4. 교육 시간 필터
        if durations and durations != "전체" and durations != ["전체"]:
            dur_mask = np.zeros(len(df), dtype=bool)
            d_val = df['numeric_duration']
            d_isna = d_val.isna()
            if isinstance(durations, str):
                dur_list = [durations]
            else:
                dur_list = durations

            if any(k in dur_list for k in ["SHORT", "단기 (<10시간)"]):
                dur_mask |= ((d_val < 10.0) & (~d_isna))
            if any(k in dur_list for k in ["MEDIUM", "중기 (10~40시간)"]):
                dur_mask |= ((d_val >= 10.0) & (d_val <= 40.0) & (~d_isna))
            if any(k in dur_list for k in ["LONG", "장기 (>40시간)"]):
                dur_mask |= ((d_val > 40.0) & (~d_isna))
            if any(k in dur_list for k in ["UNCONFIRMED", "시간 미확인"]):
                dur_mask |= d_isna
            mask &= dur_mask

        # 5. 난이도 필터
        if difficulties and difficulties != "전체":
            diff_mask = np.zeros(len(df), dtype=bool)
            diff_s = df['difficulty'].fillna('').astype(str)
            if isinstance(difficulties, str):
                diff_list = [difficulties]
            else:
                diff_list = difficulties

            if any(k in diff_list for k in ["INTRO", "입문"]):
                diff_mask |= diff_s.str.contains('입문|초급|기초', na=False)
            if any(k in diff_list for k in ["PRACTICE", "실무"]):
                diff_mask |= diff_s.str.contains('실무|중급|실전', na=False)
            if any(k in diff_list for k in ["ADVANCED", "관리자·심화", "심화"]):
                diff_mask |= diff_s.str.contains('관리자|고급|심화|리더|전략', na=False)
            mask &= diff_mask

        # 6. 오매핑 의심 109건 조건부 선별 (96건 차단 vs 13건 보존)
        excluded_109_cnt = 0
        preserved_109_cnt = 0

        if filter_mismatch_109:
            # HR/총무/경영 직무 질의 시 명백한 IT 코딩/비관련 96건 제외
            is_hr_target = True
            if target_domain and target_domain not in ["전체", "선택 안 함 (전체)"]:
                is_hr_target = target_domain in ["총무", "인사", "노무", "인사평가", "경영기획", "사무행정", "조직문화", "경영지원"]

            if is_hr_target:
                is_excluded = df['course_uid'].isin(self.excluded_109_uids)
                is_preserved = df['course_uid'].isin(self.preserved_109_uids)

                excluded_109_cnt = int((is_excluded & mask).sum())
                preserved_109_cnt = int((is_preserved & mask).sum())

                mask &= (~is_excluded)

        cand_indices = np.where(mask)[0]
        return cand_indices, excluded_109_cnt, preserved_109_cnt

    def deduplicate_cross_platform(
        self,
        df_sorted_candidates: pd.DataFrame,
        user_price_filter: str = "ALL",
        user_max_budget: int = None,
        user_edu_type: str = "ALL"
    ) -> pd.DataFrame:
        """
        크로스 플랫폼 실제 동일 강좌 중복 제거 및 대체 수강 옵션 보존:
        1. 대표 강좌(Primary Course)는 사용자 조건을 통과한 후보 중 최고 득점 강좌로 선정
        2. 동일 강좌의 대체 수강처 조회 범위는 전체 코퍼스로 확장:
           - 무료 필터로 유료 버전이 대표 후보에서 제외되었더라도, 동일 강좌의 유료 수강처는 대체 옵션으로 온전히 보존
           - 단, 109건 차단 강좌(self.excluded_109_uids)는 대체 옵션 조회에서도 절대 복원되지 않음
           - 독립 교육기관(KMA, KPC 등)의 자체 기획 집체/오프라인 과정은 독립 보존
        3. 각 대체 옵션에 사용자 조건 충족 여부(is_suitable_alternative) 및 부적합 사유 표시
        """
        if df_sorted_candidates.empty:
            return df_sorted_candidates

        # 1. 같은 플랫폼 내 다회차 중복 제거 (Intra-platform Dedup)
        df_intra_dedup = df_sorted_candidates.drop_duplicates(subset=['canonical_platform', 'norm_title']).copy()

        # 점수 상위 150건 대상 정밀 크로스 플랫폼 병합 수행
        eval_pool = df_intra_dedup.head(150).to_dict('records')
        tail_pool = df_intra_dedup.iloc[150:].to_dict('records')

        visited_uids: Set[str] = set()
        primary_rows = []

        for base_item in eval_pool:
            base_uid = base_item['course_uid']
            if base_uid in visited_uids:
                continue

            base_norm_title = base_item['norm_title']
            base_idx = self.uid_to_idx.get(base_uid, 0)
            base_emb = self.embeddings[base_idx] if self.has_embeddings else None
            base_platform = base_item.get('canonical_platform', '')

            base_offline = any(k in str(base_item.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])

            alt_offerings = []

            # 사전 색인된 norm_title_to_indices를 활용하여 전체 코퍼스에서 동일 강좌 후보 조회
            same_title_indices = self.norm_title_to_indices.get(base_norm_title, [])

            for comp_idx in same_title_indices:
                comp_item_series = self.df_courses.iloc[comp_idx]
                comp_uid = comp_item_series['course_uid']

                # 자기 자신 제외
                if comp_uid == base_uid:
                    continue

                # 차단된 109건 강좌는 대체 수강 옵션으로도 절대 복원 배제
                if comp_uid in self.excluded_109_uids:
                    continue

                comp_platform = comp_item_series['canonical_platform']
                # 동일 플랫폼 다회차는 대체 수강처에서 배제
                if comp_platform == base_platform:
                    continue

                comp_offline = any(k in str(comp_item_series.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])

                # KMA, KPC 등 독립 기관의 오프라인/집체 과정은 별개 과정으로 보존
                if base_offline or comp_offline:
                    continue

                # 동일 강좌 적합 판정 (둘 다 온라인이고 임베딩 유사도 >= 0.82 이거나 임베딩 부재 시 제목 일치)
                is_same_course = False
                if self.has_embeddings and base_emb is not None:
                    comp_emb = self.embeddings[comp_idx]
                    sim = float(np.dot(base_emb, comp_emb))
                    if sim >= 0.80 or ("온라인" in str(base_item.get('education_type', '')) and "온라인" in str(comp_item_series.get('education_type', ''))):
                        is_same_course = True
                else:
                    is_same_course = True

                if is_same_course:
                    visited_uids.add(comp_uid)

                    # 사용자 예산 및 형태 조건 충족 여부 검사
                    p_num = comp_item_series['numeric_price']
                    p_status = comp_item_series['price_status']
                    meets_budget = True

                    if user_price_filter == "FREE_ONLY" or user_max_budget == 0:
                        meets_budget = (p_status == 'FREE')
                    elif user_max_budget is not None and user_max_budget != "전체":
                        b_limit = int(user_max_budget)
                        if pd.notna(p_num) and p_num > b_limit:
                            meets_budget = False
                        elif p_status == 'UNCONFIRMED':
                            meets_budget = False

                    meets_edu_type = True
                    if user_edu_type in ["ONLINE", "온라인"]:
                        meets_edu_type = any(k in str(comp_item_series.get('education_type', '')) for k in ['온라인', '사이버', '원격', '플립', '동영상', 'VOD'])
                    elif user_edu_type in ["OFFLINE", "오프라인"]:
                        meets_edu_type = any(k in str(comp_item_series.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])

                    is_suitable = bool(meets_budget and meets_edu_type)
                    unsuitability_reason = ""
                    if not is_suitable:
                        reasons = []
                        if not meets_budget:
                            price_desc = "무료 아님(가격 미확인)" if p_status == 'UNCONFIRMED' else f"예산 초과({self.format_price(p_num)})"
                            reasons.append(price_desc)
                        if not meets_edu_type:
                            reasons.append(f"수강형태 불일치({comp_item_series.get('education_type')})")
                        unsuitability_reason = "⚠️ " + ", ".join(reasons)

                    alt_offerings.append({
                        "course_uid": comp_uid,
                        "provider": comp_platform,
                        "title": comp_item_series['title'],
                        "price_display": self.format_price(p_num),
                        "numeric_price": p_num,
                        "url": comp_item_series.get('url', '#'),
                        "education_type": comp_item_series.get('education_type', '온라인'),
                        "meets_user_budget": meets_budget,
                        "meets_user_edu_type": meets_edu_type,
                        "is_suitable_alternative": is_suitable,
                        "unsuitability_reason": unsuitability_reason
                    })

            base_item['alternative_offerings'] = alt_offerings
            base_item['alt_count'] = len(alt_offerings)
            primary_rows.append(base_item)
            visited_uids.add(base_uid)

        for tail_item in tail_pool:
            if tail_item['course_uid'] not in visited_uids:
                tail_item['alternative_offerings'] = []
                tail_item['alt_count'] = 0
                primary_rows.append(tail_item)
                visited_uids.add(tail_item['course_uid'])

        return pd.DataFrame(primary_rows)

    @staticmethod
    def format_price(p) -> str:
        """가격을 원화 표시 문자열로 포맷합니다."""
        if pd.isna(p):
            return "가격 미확인"
        p_int = int(p)
        if p_int == 0:
            return "무료"
        return f"{p_int:,}원"

    @staticmethod
    def format_duration(d) -> str:
        """교육시간을 포맷합니다."""
        if pd.isna(d):
            return "시간 미확인"
        return f"{float(d):.1f}시간"

    @staticmethod
    def clean_text_for_snippet(text: str) -> str:
        """Markdown 표 기호, HTML 태그, 중복 공백 등을 제거하여 정제합니다."""
        if not text or pd.isna(text):
            return ""
        s = str(text)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = re.sub(r'\|[-:\s|]+\|', ' ', s)
        s = re.sub(r'\|', ' ', s)
        s = re.sub(r'^[#*>\-]+\s*', '', s, flags=re.MULTILINE)
        s = re.sub(r'[ \t\r\f\v]+', ' ', s)
        return s.strip()

    @classmethod
    def extract_clean_curriculum_snippet(cls, curri: str, intro: str, keywords: List[str]) -> str:
        """단어 중간을 자르지 않고 온전한 문장/항목 단위로 커리큘럼 핵심 근거를 발췌합니다."""
        cleaned_curri = cls.clean_text_for_snippet(curri)
        cleaned_intro = cls.clean_text_for_snippet(intro)
        target_corpus = cleaned_curri if len(cleaned_curri) >= 30 else f"{cleaned_curri} {cleaned_intro}".strip()
        if not target_corpus:
            return ""

        units = re.split(r'[\r\n]+|[;•▶·/]\s*|[.!?]\s+|\s*\d{1,2}[.)]\s*', target_corpus)
        units = [u.strip() for u in units if len(u.strip()) >= 5]
        matched_units = []
        seen = set()

        for kw in keywords:
            if not kw or len(kw) < 2:
                continue
            for unit in units:
                if kw in unit and unit not in seen:
                    if len(unit) > 80:
                        kw_idx = unit.find(kw)
                        start_pos = max(0, kw_idx - 30)
                        end_pos = min(len(unit), kw_idx + len(kw) + 35)
                        if start_pos > 0:
                            fs = unit.find(' ', start_pos)
                            if fs != -1 and fs < kw_idx:
                                start_pos = fs + 1
                        if end_pos < len(unit):
                            ls = unit.rfind(' ', kw_idx, end_pos)
                            if ls != -1 and ls > kw_idx + len(kw):
                                end_pos = ls
                        clipped = unit[start_pos:end_pos].strip()
                        if start_pos > 0:
                            clipped = "..." + clipped
                        if end_pos < len(unit):
                            clipped = clipped + "..."
                        matched_units.append(clipped)
                    else:
                        matched_units.append(unit)
                    seen.add(unit)
                    break
            if len(matched_units) >= 2:
                break

        return " / ".join(matched_units)

    def recommend(
        self,
        query: str = None,
        target_domain: str = None,  # "인사", "총무", "경영지원", "노무", "경영기획", 등
        competency_id: str = None,  # e.g. "COMP_HR_01"
        user_level: str = None,  # "입문", "실무", "관리자·심화"
        platforms: list = None,
        price_filter: str = "ALL",  # "ALL", "FREE_ONLY", "MAX_BUDGET"
        max_budget: int = None,
        edu_type: str = "ALL",  # "ALL", "ONLINE", "OFFLINE"
        durations: list = None,
        difficulties: list = None,
        cluster_boost: float = 0.0,  # 기본값 0.0점, 실험값 5.0점
        filter_mismatch_109: bool = True,
        top_n: int = 5,
        mode: str = "general",  # "general" 또는 "ksa" (competency_id 전달 시 자동 ksa)
        keyword_query: str = None,  # BM25 전용 키워드 질의 (미지정 시 모드별 기본 질의 사용)
        keyword_stopwords: Optional[Set[str]] = None,  # BM25 질의에서 뺄 범용 단어 (예: 작성·분석·설계)
        anchor_query: str = None  # 핵심어 질의: 핵심어가 하나도 없는 강좌는 키워드 점수를 낮춤
    ) -> Tuple[pd.DataFrame, int, int, int, str]:
        """
        통합 6단계 하이브리드 추천 실행 (일반 모드 및 KSA 역량 모드 지원):
        [1] 사전 조건 및 109건 조건부 선별 필터링
        [2] 모드별 하이브리드 점수 계산:
            - General 모드: Ko-SRoBERTa(50%) + BM25(35%) + 레벨보너스 + 군집부스팅 (리뷰·평점 미사용)
            - KSA 모드: Ko-SRoBERTa(50%) + BM25(30%) + 레벨적합(10%) + 군집부스팅(0 or 5%) + KSA보조매핑(5%)
        [3] 전체 후보 점수순 정렬
        [4] 같은 플랫폼 다회차 중복 제거 (Intra-platform Dedup)
        [5] 실제 동일 강좌 크로스 플랫폼 중복 제거 (Cross-platform Dedup) 및 대체 옵션 저장
        [6] 최종 Top N 선정 및 텍스트 근거 기반 추천 사유 도출
        """
        # [캐시 검사] 데이터 버전, 모델 버전, 검색 조건 전수 포함된 키 생성
        cache_key = (
            self.data_version,
            self.model_version,
            bool(self.has_embeddings and self.model is not None),  # 임베딩 폴백 여부에 따라 결과가 달라짐
            (query or "").strip(),
            target_domain,
            competency_id,
            user_level,
            tuple(platforms) if platforms else None,
            price_filter,
            max_budget,
            edu_type,
            tuple(durations) if durations else None,
            tuple(difficulties) if difficulties else None,
            float(cluster_boost),
            bool(filter_mismatch_109),
            int(top_n),
            mode,
            (keyword_query or "").strip(),
            tuple(sorted(keyword_stopwords)) if keyword_stopwords else None,
            (anchor_query or "").strip()
        )

        now = time.time()
        if cache_key in self._rec_cache:
            ts = self._rec_cache_timestamps.get(cache_key, 0)
            if (now - ts) < self._rec_cache_ttl:
                c_df, n_c, e_c, p_c, msg = self._rec_cache[cache_key]
                return c_df.copy(), n_c, e_c, p_c, msg
            else:
                self._rec_cache.pop(cache_key, None)
                self._rec_cache_timestamps.pop(cache_key, None)

        # 모드 판별: competency_id가 주어지면 자동으로 KSA 모드 전환
        is_ksa_mode = (mode == "ksa") or (competency_id is not None)
        competency_info = get_competency_by_id(competency_id) if is_ksa_mode and competency_id else None

        # 타겟 도메인 보정
        effective_domain = target_domain
        if is_ksa_mode and competency_info and not effective_domain:
            effective_domain = competency_info["job_family"]

        # STEP 1: 사전 필터링
        cand_indices, excluded_109_cnt, preserved_109_cnt = self.filter_candidates(
            target_domain=effective_domain,
            platforms=platforms,
            price_filter=price_filter,
            max_budget=max_budget,
            edu_type=edu_type,
            durations=durations,
            difficulties=difficulties,
            filter_mismatch_109=filter_mismatch_109
        )

        n_candidates = len(cand_indices)
        if n_candidates == 0:
            return pd.DataFrame(), 0, 0, 0, "선택하신 조건을 충족하는 교육과정이 없습니다."

        # STEP 2: 검색 질의 및 텍스트 구성
        if is_ksa_mode and competency_info:
            semantic_query_text = f"{competency_info['name']} {competency_info['definition']} {competency_info['knowledge']} {competency_info['skill']}"
            if query:
                semantic_query_text = f"{query} {semantic_query_text}"
            keyword_query_text = competency_info['search_query']
        else:
            semantic_query_text = query or ""
            if not semantic_query_text and effective_domain:
                semantic_query_text = f"{effective_domain} 핵심 실무 역량 강화 교육"
            keyword_query_text = semantic_query_text
        if keyword_query and keyword_query.strip():
            keyword_query_text = keyword_query.strip()

        # 1) Ko-SRoBERTa 시맨틱 유사도 (질의 벡터 LRU 캐시 적용)
        if self.has_embeddings and self.model is not None and semantic_query_text.strip():
            sq_clean = semantic_query_text.strip()
            if sq_clean in self._query_vector_cache:
                q_vec = self._query_vector_cache[sq_clean]
            else:
                q_vec = self.model.encode(sq_clean, normalize_embeddings=True, device=self.device)
                if len(self._query_vector_cache) >= 256:
                    self._query_vector_cache.pop(next(iter(self._query_vector_cache)))
                self._query_vector_cache[sq_clean] = q_vec

            cand_embs = self.embeddings[cand_indices]
            sims = np.dot(cand_embs, q_vec)
            semantic_scores = np.clip(sims, 0.0, 1.0) * 100.0
        else:
            semantic_scores = np.full(len(cand_indices), 50.0, dtype=np.float32)

        # 2) BM25 Okapi 키워드 적합도
        # KSA 기본 검색어는 이미 정제된 키워드이므로 공백 분리만, 자유 입력·Task 질의는 Kiwi 토큰화 적용
        use_kiwi = not (is_ksa_mode and competency_info and not (keyword_query and keyword_query.strip()))
        q_tokens = self._keyword_tokens(keyword_query_text, use_kiwi=use_kiwi)
        if keyword_stopwords:
            q_tokens = [t for t in q_tokens if t not in keyword_stopwords]
        if q_tokens:
            bm25_raw_all = self.bm25.get_scores(q_tokens)
            bm25_cand = bm25_raw_all[cand_indices]
            max_b = bm25_cand.max()
            bm25_scores = (bm25_cand / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_cand)
        else:
            bm25_scores = np.zeros(len(cand_indices), dtype=np.float32)

        # 핵심어 앵커: 범용 단어만 많이 겹친 강좌가 키워드 점수를 독차지하지 않도록 보정
        # 핵심어 점수 = 일치한 핵심어 수 (강좌 8% 이상에 나오는 넓은 단어는 0.5개로 계산)
        # 키워드 점수 배율: 핵심어 점수 0 → ×0.4, 1 이상 → ×0.7, 2 이상 → ×1.0
        anchor_scores = None
        if anchor_query and anchor_query.strip() and q_tokens:
            anchors = set(self._keyword_tokens(anchor_query)) - set(keyword_stopwords or ())
            if anchors:
                doc_sets = self._doc_token_sets()
                doc_freq = self._doc_freq()
                n_docs = len(doc_sets)
                weights = {a: (0.5 if doc_freq.get(a, 0) / n_docs >= 0.08 else 1.0) for a in anchors}
                anchor_scores = np.array(
                    [sum(w for a, w in weights.items() if a in doc_sets[i]) for i in cand_indices], dtype=np.float32
                )
                factor = np.where(anchor_scores >= 2, 1.0, np.where(anchor_scores >= 1, 0.7, 0.4))
                bm25_scores = bm25_scores * factor

        df_cand = self.df_courses.iloc[cand_indices].copy()

        # 3) 난이도 레벨 보너스 (최대 10점)
        level_bonus = np.zeros(len(cand_indices), dtype=np.float32)
        target_level = user_level or "실무"
        diff_s = df_cand['difficulty'].fillna('').astype(str)

        if target_level == "입문":
            match_mask = diff_s.str.contains('입문|초급|기초', na=False)
            level_bonus[match_mask] = 10.0
            if is_ksa_mode:
                level_bonus[diff_s == ''] = 5.0
        elif target_level == "실무":
            match_mask = diff_s.str.contains('실무|중급|실전', na=False)
            level_bonus[match_mask] = 10.0
            if is_ksa_mode:
                level_bonus[diff_s == ''] = 5.0
        elif target_level == "관리자·심화":
            match_mask = diff_s.str.contains('관리자|고급|심화|리더|전략', na=False)
            level_bonus[match_mask] = 10.0
            if is_ksa_mode:
                level_bonus[diff_s == ''] = 5.0

        # 4) 가변 군집 부스팅 (기본 0점 ~ 실험 5점 통일)
        cluster_bonus = np.zeros(len(cand_indices), dtype=np.float32)
        if cluster_boost > 0.0 and effective_domain:
            target_cluster_ids = get_job_cluster_ids(effective_domain)
            if target_cluster_ids:
                is_cluster_match = df_cand['cluster_id'].isin(target_cluster_ids).values
                cluster_bonus[is_cluster_match] = float(cluster_boost)

        # 5) KSA 기존 매핑 보조 신호 (KSA 모드 전용, 5.0점)
        ksa_aux_bonus = np.zeros(len(cand_indices), dtype=np.float32)
        verified_uids = set()
        if is_ksa_mode and not self.df_comp_long.empty and competency_id:
            comp_slice = self.df_comp_long[self.df_comp_long['competency_id'] == competency_id]
            mapped_uids = set(comp_slice['course_uid'])
            is_aux_mapped = df_cand['course_uid'].isin(mapped_uids).values
            ksa_aux_bonus[is_aux_mapped] = 5.0

            # 실제 전문가 검증 플래그 추적
            if 'is_verified' in comp_slice.columns:
                verified_uids = set(comp_slice[comp_slice['is_verified'] == True]['course_uid'])

        # 최종 점수 계산
        if is_ksa_mode:
            # KSA 공식: Semantic 50% + BM25 30% + Level 10점 + ClusterBonus + KsaAuxBonus 5점
            final_scores = (0.50 * semantic_scores) + (0.30 * bm25_scores) + level_bonus + cluster_bonus + ksa_aux_bonus
        else:
            # 일반 모드 공식: Semantic 50% + BM25 35% + LevelBonus + ClusterBonus
            # 수강 리뷰·평점은 사용하지 않습니다 (검증된 실제 리뷰 부족, 확보된 리뷰 DB는 합성 데이터).
            final_scores = (0.50 * semantic_scores) + (0.35 * bm25_scores) + level_bonus + cluster_bonus

        df_cand['final_score'] = np.round(final_scores, 1)
        df_cand['semantic_score'] = np.round(semantic_scores, 1)
        df_cand['bm25_score'] = np.round(bm25_scores, 1)
        df_cand['keyword_score'] = df_cand['bm25_score']
        df_cand['level_bonus'] = np.round(level_bonus, 1)
        df_cand['level_score'] = df_cand['level_bonus']
        df_cand['cluster_bonus'] = np.round(cluster_bonus, 1)
        df_cand['ksa_aux_bonus'] = np.round(ksa_aux_bonus, 1)
        if anchor_scores is not None:
            df_cand['anchor_score'] = anchor_scores

        # 표시용 포맷 필드(price_display, duration_display, mismatch_status)는
        # _load_data()에서 사전 생성되어 df_cand에 이미 포함되어 있으므로 쿼리 시점 반복 연산을 생략합니다.

        # STEP 3: 점수 기준 정렬
        df_sorted = df_cand.sort_values(by=['final_score', 'semantic_score'], ascending=False)

        # STEP 4 & 5: 크로스 플랫폼 중복 제거 및 대체 옵션 생성
        eff_budget = 0 if price_filter == "FREE_ONLY" else max_budget
        df_dedup = self.deduplicate_cross_platform(
            df_sorted_candidates=df_sorted,
            user_price_filter=price_filter,
            user_max_budget=eff_budget,
            user_edu_type=edu_type
        )

        # STEP 6: 최종 Top N 선정 및 텍스트 근거 기반 추천 사유 도출
        top_df = df_dedup.head(top_n).copy().reset_index(drop=True)
        top_df['rank'] = range(1, len(top_df) + 1)

        recommendation_reasons = []
        clean_snippets_list = []
        content_evidences_list = []
        matched_keywords_list = []
        text_richness_list = []
        mapping_status_list = []

        for _, row in top_df.iterrows():
            intro = str(row.get('clean_intro', ''))
            curri = str(row.get('clean_curriculum', ''))
            full_text = f"{row['title']} {intro} {curri}"

            # 텍스트 충실도
            t_len = len(intro) + len(curri)
            if t_len >= 200:
                richness = "RICH"
            elif t_len >= 50:
                richness = "MODERATE"
            else:
                richness = "TITLE_ONLY"
            text_richness_list.append(richness)

            # 매핑 상태: 군집 일치나 단순 매핑만으로 EXPERT-VERIFIED를 표시하지 않음
            if row['course_uid'] in verified_uids:
                m_status = "EXPERT-VERIFIED"
            elif row.get('is_verified') is True:
                m_status = "EXPERT-VERIFIED"
            else:
                m_status = "AUTO-ESTIMATED"
            mapping_status_list.append(m_status)

            clean_snippet = ""
            content_evidence = ""

            if is_ksa_mode and competency_info:
                matched_kws = [kw for kw in competency_info['core_keywords'] if kw in full_text]
                matched_str = ", ".join(matched_kws[:4]) if matched_kws else "직무 역량 정합"
                matched_keywords_list.append(matched_str)

                clean_snippet = self.extract_clean_curriculum_snippet(curri, intro, matched_kws or competency_info['core_keywords'])

                if clean_snippet:
                    rec_reason = f"커리큘럼 내 '{clean_snippet}' 등 실제 실무 내용을 확인하여 [{competency_info['name']}] 역량 향상에 부합합니다."
                    content_evidence = f"커리큘럼 발췌: {clean_snippet}"
                elif richness == "TITLE_ONLY":
                    rec_reason = f"상세 교육내용이 부족해 강좌명과 제공된 정보 중심으로 추천했습니다. 강좌명 키워드가 [{competency_info['name']}] 역량 정의에 부합합니다."
                    content_evidence = "상세 교육내용이 부족해 강좌명과 제공된 정보 중심으로 추천했습니다."
                else:
                    rec_reason = f"과정 소개 내용 중 직무 키워드({matched_str})를 중심으로 [{competency_info['name']}] 실무 역량 강화를 제공합니다."
                    content_evidence = f"과정 소개 키워드({matched_str}) 확인"
            else:
                # 일반 모드 추천 근거
                matched_keywords_list.append(row.get('topic_label', '직무 역량'))
                search_kws = [k for k in [query, effective_domain, row.get('topic_label')] if k and isinstance(k, str)]
                clean_snippet = self.extract_clean_curriculum_snippet(curri, intro, search_kws)
                if clean_snippet:
                    rec_reason = f"커리큘럼 내 '{clean_snippet}' 등 실무 내용을 확인하여 추천되었습니다."
                    content_evidence = f"커리큘럼 발췌: {clean_snippet}"
                elif richness == "TITLE_ONLY":
                    rec_reason = "상세 교육내용이 부족해 강좌명과 제공된 정보 중심으로 추천했습니다."
                    content_evidence = "상세 교육내용이 부족해 강좌명과 제공된 정보 중심으로 추천했습니다."
                else:
                    rec_reason = f"교육과정 소개 및 분석 결과, '{query or effective_domain}' 실무 요구 역량과 부합하는 과정입니다."
                    content_evidence = f"교육 소개 분석({row.get('topic_label', '직무')}) 확인"

            recommendation_reasons.append(rec_reason)
            clean_snippets_list.append(clean_snippet)
            content_evidences_list.append(content_evidence)

        top_df['recommendation_reason'] = recommendation_reasons
        top_df['clean_snippet'] = clean_snippets_list
        top_df['content_evidence'] = content_evidences_list
        top_df['matched_keywords'] = matched_keywords_list
        top_df['text_richness'] = text_richness_list
        top_df['mapping_status'] = mapping_status_list

        if is_ksa_mode and competency_info:
            top_df['job_family'] = competency_info['job_family']
            top_df['competency_id'] = competency_id
            top_df['competency_name'] = competency_info['name']
        msg = "추천이 성공적으로 완료되었습니다."

        # 추천 결과 LRU 캐시 저장 (메모리 상한 128개 유지)
        if len(self._rec_cache) >= self._rec_cache_max:
            oldest_k = next(iter(self._rec_cache))
            self._rec_cache.pop(oldest_k, None)
            self._rec_cache_timestamps.pop(oldest_k, None)

        self._rec_cache[cache_key] = (top_df.copy(), n_candidates, excluded_109_cnt, preserved_109_cnt, msg)
        self._rec_cache_timestamps[cache_key] = now

        return top_df, n_candidates, excluded_109_cnt, preserved_109_cnt, msg
