"""
통합 하이브리드 추천 엔진 공통 모듈 (Unified Hybrid Recommender)
- 8,645건 통합 교육 코퍼스 대상 Ko-SRoBERTa(50%) + BM25(35%) + 레벨/평점(15%)
- 세부 조건 Faceted Filtering (비용 결측 왜곡 차단, 시간 경계값)
- 오매핑 109건 조건부 선별 차단 (오류 강좌 제외 vs 유효 강좌 유지 구분)
- 가변 군집 부스팅 (기본값 0.0점 ~ 실험값 5.0점 비교 지원)
- 크로스 플랫폼 실제 동일 강좌 중복 제거 (대체 수강 옵션 보존)
- 분석 스크립트(step8) 및 Streamlit 대시보드(탭 8, 탭 10) 공통 재사용
"""

import os
import re
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data" / "hr"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "output" / "recommendation"

class UnifiedHybridRecommender:
    """통합 하이브리드 추천 엔진 코어 클래스"""

    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._load_data()
        self._init_models()

    def _load_data(self):
        # 1. 정제 코퍼스 8,645건
        p_clean = PROCESSED_DIR / "education_courses_search_cleaned.parquet"
        self.df_courses = pd.read_parquet(p_clean)

        # 2. STEP 5-3 10대 군집 데이터셋
        p_clusters = OUTPUT_DIR / "course_clusters_8645.parquet"
        if p_clusters.exists():
            df_cl = pd.read_parquet(p_clusters)
            self.df_courses = self.df_courses.merge(
                df_cl[['course_uid', 'cluster_id', 'topic_label', 'canonical_platform']],
                on='course_uid',
                how='left'
            )
        else:
            self.df_courses['cluster_id'] = 0
            self.df_courses['topic_label'] = "미분류"
            self.df_courses['canonical_platform'] = self.df_courses['provider']

        # 3. Ko-SRoBERTa 768차원 임베딩 (안전 로드 및 폴백)
        p_emb = OUTPUT_DIR / "embeddings_ko_sroberta_all.npy"
        if p_emb.exists():
            self.embeddings = np.load(p_emb)
            self.has_embeddings = True
        else:
            self.embeddings = np.zeros((len(self.df_courses), 768), dtype=np.float32)
            self.has_embeddings = False

        # 4. 토큰화 캐시 (BM25)
        p_tok = PROCESSED_DIR / "tokenized_corpus_cache.parquet"
        self.df_tokens = pd.read_parquet(p_tok)
        self.df_courses = self.df_courses.merge(self.df_tokens, on='course_uid', how='left')
        self.df_courses['tokenized_text'] = self.df_courses['tokenized_text'].fillna('')

        # 5. 오매핑 의심 109건 목록
        p_mismatch = OUTPUT_DIR / "mapping_mismatch_samples.json"
        self.mismatch_109_uids = set()
        if p_mismatch.exists():
            with open(p_mismatch, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.mismatch_109_uids = {item['course_uid'] for item in data if 'course_uid' in item}

        # 수치형 변환 및 결측치 안전 처리
        self.df_courses['numeric_price'] = pd.to_numeric(self.df_courses['price'], errors='coerce')
        self.df_courses['numeric_duration'] = pd.to_numeric(self.df_courses['duration_hours'], errors='coerce')

        # 가격 상태 정의: FREE, PAID, UNCONFIRMED
        price_is_na = self.df_courses['numeric_price'].isna()
        is_free = (self.df_courses['numeric_price'] == 0) & (~price_is_na)
        self.df_courses['price_status'] = 'PAID'
        self.df_courses.loc[price_is_na, 'price_status'] = 'UNCONFIRMED'
        self.df_courses.loc[is_free, 'price_status'] = 'FREE'

        # 정규화 강좌명 사전 생성 (괄호, 태그, 특수기호 제거)
        self.df_courses['norm_title'] = self.df_courses['title'].apply(self.normalize_course_title)

        # O(1) 인덱스 역방향 매핑 딕셔너리
        self.uid_to_idx = {uid: idx for idx, uid in enumerate(self.df_courses['course_uid'])}

    def _init_models(self):
        # BM25 초기화
        corpus_tokens = [txt.split() for txt in self.df_courses['tokenized_text']]
        self.bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
        self.bm25_vocab = {t for toks in corpus_tokens for t in toks}

        # Ko-SRoBERTa 질의 인코더 로드
        self.model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=self.device)

    @staticmethod
    def normalize_course_title(t: str) -> str:
        """강좌명의 대괄호, 소괄호 태그 및 특수문자를 제거하여 정규화합니다."""
        t = str(t)
        t = re.sub(r'\[.*?\]', '', t)
        t = re.sub(r'\(.*?\)', '', t)
        t = re.sub(r'[^\w\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip().lower()
        return t

    def filter_candidates(
        self,
        target_domain: str = None,
        platforms: list = None,
        price_filter: str = "ALL", # "ALL", "FREE_ONLY", "MAX_BUDGET"
        max_budget: int = None,
        edu_type: str = "ALL", # "ALL", "ONLINE", "OFFLINE"
        durations: list = None, # ["SHORT", "MEDIUM", "LONG", "UNCONFIRMED"]
        difficulties: list = None,
        filter_mismatch_109: bool = True
    ) -> tuple:
        """
        1단계: 사용자 조건 필터링 및 오매핑 의심 강좌 조건부 선별
        - 반환: (유효 인덱스 np.ndarray, 제외된 109건 수, 유지된 109건 수)
        """
        df = self.df_courses
        mask = np.ones(len(df), dtype=bool)

        # 1. 플랫폼 필터
        if platforms:
            mask &= df['canonical_platform'].isin(platforms)

        # 2. 가격 필터 (결측치 왜곡 차단)
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
        if edu_type == "ONLINE" or edu_type == "온라인":
            mask &= df['education_type'].astype(str).str.contains('온라인|사이버|원격|플립', na=False)
        elif edu_type == "OFFLINE" or edu_type == "오프라인":
            mask &= df['education_type'].astype(str).str.contains('오프라인|집체|현장', na=False)

        # 4. 교육 시간 필터
        if durations:
            dur_mask = np.zeros(len(df), dtype=bool)
            d_val = df['numeric_duration']
            d_isna = d_val.isna()
            if "SHORT" in durations or "단기 (<10시간)" in durations:
                dur_mask |= ((d_val < 10.0) & (~d_isna))
            if "MEDIUM" in durations or "중기 (10~40시간)" in durations:
                dur_mask |= ((d_val >= 10.0) & (d_val <= 40.0) & (~d_isna))
            if "LONG" in durations or "장기 (>40시간)" in durations:
                dur_mask |= ((d_val > 40.0) & (~d_isna))
            if "UNCONFIRMED" in durations or "시간 미확인" in durations:
                dur_mask |= d_isna
            mask &= dur_mask

        # 5. 난이도 필터
        if difficulties:
            diff_mask = np.zeros(len(df), dtype=bool)
            diff_s = df['difficulty'].fillna('').astype(str)
            if "INTRO" in difficulties or "입문" in difficulties:
                diff_mask |= diff_s.str.contains('입문|초급|기초', na=False)
            if "PRACTICE" in difficulties or "실무" in difficulties:
                diff_mask |= diff_s.str.contains('실무|중급|실전', na=False)
            if "ADVANCED" in difficulties or "관리자·심화" in difficulties or "심화" in difficulties:
                diff_mask |= diff_s.str.contains('관리자|고급|심화|리더|전략', na=False)
            mask &= diff_mask

        # 6. 오매핑 의심 109건 조건부 선별 (오류 배제 vs 유효 보존 구분)
        excluded_109_cnt = 0
        preserved_109_cnt = 0

        if filter_mismatch_109:
            # HR/총무/경영 직무 질의 시
            is_hr_target = target_domain in ["총무", "인사", "노무", "인사평가", "경영기획", "사무행정", "조직문화"] if target_domain else True
            if is_hr_target:
                is_109 = df['course_uid'].isin(self.mismatch_109_uids)
                # 비-HR 군집: C0(데이터/AI), C6(스마트워크 코딩), C7(어학)
                is_non_hr_cluster = df['cluster_id'].isin([0, 6, 7])
                title_it_term = df['title'].str.contains('파이썬|코딩|개발|서버|Spring|Docker|AWS|클라우드|Java|React|자바', case=False, na=False)
                
                # 명백한 IT 코딩/비관련 과정만 선별하여 제외
                mismatch_exclude = is_109 & (is_non_hr_cluster | title_it_term)
                excluded_109_cnt = int((mismatch_exclude & mask).sum())
                preserved_109_cnt = int(((is_109 & ~mismatch_exclude) & mask).sum())
                
                mask &= (~mismatch_exclude)

        cand_indices = np.where(mask)[0]
        return cand_indices, excluded_109_cnt, preserved_109_cnt

    def deduplicate_cross_platform(
        self,
        df_sorted_candidates: pd.DataFrame,
        user_max_budget: int = None,
        user_edu_type: str = "ALL"
    ) -> pd.DataFrame:
        """
        크로스 플랫폼 실제 동일 강좌 중복 제거 알고리즘:
        1. 같은 플랫폼 내 다회차 중복 제거 (Intra-platform Dedup)
        2. 서로 다른 플랫폼 간 실제 동일 교육 탐지 (Cross-platform Dedup):
           - 정규화된 강좌명이 동일하고,
           - 코퍼스 임베딩 코사인 유사도가 0.85 이상이거나, 동일 디지털 신디케이션 교육인 경우 병합
           - 교육기관이 자체 제작한 별개 오프라인 과정은 독립 보존
        3. 대표 강좌(Primary Course)는 최고 득점 강좌로 선정하고, 다른 플랫폼 강좌는 alternative_offerings에 보존
        4. 사용자 예산/형태 조건에 위배되는 대체 옵션은 경고 플래그 부여
        """
        if df_sorted_candidates.empty:
            return df_sorted_candidates

        # 4단계: 같은 플랫폼 다회차 중복 제거 (Intra-platform Dedup)
        df_intra_dedup = df_sorted_candidates.drop_duplicates(subset=['canonical_platform', 'norm_title']).copy()

        # 5단계: 서로 다른 플랫폼 간 실제 동일 강좌 크로스 플랫폼 중복 제거
        # Top-N(최대 10건) 도출을 위해 점수 상위 150건 대상 정밀 크로스 플랫폼 병합 수행
        eval_pool = df_intra_dedup.head(150).to_dict('records')
        tail_pool = df_intra_dedup.iloc[150:].to_dict('records')

        visited_indices = set()
        primary_rows = []
        n_cands = len(eval_pool)

        for i in range(n_cands):
            if i in visited_indices:
                continue

            base_item = eval_pool[i]
            base_norm_title = base_item['norm_title']
            base_uid = base_item['course_uid']
            base_idx = self.uid_to_idx.get(base_uid, 0)
            base_emb = self.embeddings[base_idx]

            alt_offerings = []

            # 이후 후보 강좌들과 비교하여 동일 강좌군 병합
            for j in range(i + 1, n_cands):
                if j in visited_indices:
                    continue

                comp_item = eval_pool[j]
                comp_norm_title = comp_item['norm_title']
                comp_uid = comp_item['course_uid']
                comp_idx = self.uid_to_idx.get(comp_uid, 0)

                # 동일 강좌 판정 조건:
                # 1) 정규화 강좌명이 완전히 일치하거나
                is_exact_title = (base_norm_title == comp_norm_title) and (len(base_norm_title) >= 4)
                
                # 2) 임베딩 유사도 계산
                comp_emb = self.embeddings[comp_idx]
                sim_between = float(np.dot(base_emb, comp_emb))

                is_same_course = False

                if is_exact_title:
                    # 제목이 완전 일치하는 경우:
                    base_offline = any(k in str(base_item.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])
                    comp_offline = any(k in str(comp_item.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])

                    # 독립 교육기관(KMA, KPC 등)의 자체 기획 집체/오프라인 과정은 제목이 같아도 독립 보존
                    if base_offline or comp_offline:
                        is_same_course = False
                    else:
                        # 둘 다 온라인/e-러닝 과정인 경우 신디케이션/동일 콘텐츠 여부 확인
                        is_both_online = ("온라인" in str(base_item.get('education_type', '')) and "온라인" in str(comp_item.get('education_type', '')))
                        if sim_between >= 0.82 or is_both_online:
                            is_same_course = True
                else:
                    # 제목이 유사한 경우: 둘 다 온라인이고 임베딩 유사도가 극히 높으며(>=0.95), 토큰 자카드 유사도가 높은 경우만 제한 병합
                    base_offline = any(k in str(base_item.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])
                    comp_offline = any(k in str(comp_item.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])
                    if not (base_offline or comp_offline):
                        title_tokens_a = set(base_norm_title.split())
                        title_tokens_b = set(comp_norm_title.split())
                        jaccard = len(title_tokens_a & title_tokens_b) / max(1, len(title_tokens_a | title_tokens_b))
                        if jaccard >= 0.85 and sim_between >= 0.95:
                            is_same_course = True

                if is_same_course:
                    visited_indices.add(j)

                    # 사용자 예산 및 수강 형태 적합성 감사
                    p_num = comp_item.get('numeric_price')
                    meets_budget = True
                    if user_max_budget is not None and user_max_budget != "전체":
                        b_limit = int(user_max_budget)
                        if b_limit == 0:
                            meets_budget = (comp_item.get('price_status') == 'FREE')
                        elif pd.notna(p_num) and p_num > b_limit:
                            meets_budget = False

                    meets_edu_type = True
                    if user_edu_type in ["ONLINE", "온라인"]:
                        meets_edu_type = any(k in str(comp_item.get('education_type', '')) for k in ['온라인', '사이버', '원격', '플립', '동영상', 'VOD'])
                    elif user_edu_type in ["OFFLINE", "오프라인"]:
                        meets_edu_type = any(k in str(comp_item.get('education_type', '')) for k in ['집체', '집합', '오프라인', '현장'])

                    is_suitable = bool(meets_budget and meets_edu_type)
                    unsuitability_reason = ""
                    if not is_suitable:
                        reasons = []
                        if not meets_budget:
                            reasons.append(f"예산 초과({comp_item.get('price_display')})")
                        if not meets_edu_type:
                            reasons.append(f"수강형태 불일치({comp_item.get('education_type')})")
                        unsuitability_reason = "⚠️ " + ", ".join(reasons)

                    alt_offerings.append({
                        "provider": comp_item.get('canonical_platform'),
                        "title": comp_item.get('title'),
                        "price_display": comp_item.get('price_display', '가격 미확인'),
                        "numeric_price": p_num,
                        "url": comp_item.get('url', '#'),
                        "education_type": comp_item.get('education_type', '온라인'),
                        "meets_user_budget": meets_budget,
                        "meets_user_edu_type": meets_edu_type,
                        "is_suitable_alternative": is_suitable,
                        "unsuitability_reason": unsuitability_reason
                    })

            base_item['alternative_offerings'] = alt_offerings
            base_item['alt_count'] = len(alt_offerings)
            primary_rows.append(base_item)
            visited_indices.add(i)

        for tail_item in tail_pool:
            tail_item['alternative_offerings'] = []
            tail_item['alt_count'] = 0
            primary_rows.append(tail_item)

        return pd.DataFrame(primary_rows)

    def recommend(
        self,
        query: str = None,
        target_domain: str = None, # "총무", "인사", "노무", "회계", "OA", "경영기획"
        competency_id: str = None, # e.g. "COMP_HR_01", etc.
        user_level: str = None, # "입문", "실무", "관리자·심화"
        platforms: list = None,
        price_filter: str = "ALL", # "ALL", "FREE_ONLY", "MAX_BUDGET"
        max_budget: int = None,
        edu_type: str = "ALL", # "ALL", "ONLINE", "OFFLINE"
        durations: list = None,
        difficulties: list = None,
        cluster_boost: float = 0.0, # 기본값 0.0점, 실험값 5.0점 비교 가능
        filter_mismatch_109: bool = True,
        top_n: int = 5
    ) -> tuple:
        """
        통합 6단계 하이브리드 추천 실행:
        [1] 사전 조건 및 109건 조건부 필터링
        [2] 하이브리드 점수 계산 (Ko-SRoBERTa 50% + BM25 35% + 레벨/보정 15% + 군집 부스팅)
        [3] 전체 후보 점수순 정렬
        [4] 같은 플랫폼 다회차 중복 제거 (Intra-platform Dedup)
        [5] 실제 동일 강좌 크로스 플랫폼 중복 제거 (Cross-platform Dedup) 및 대체 옵션 저장
        [6] 최종 Top N 선정 및 텍스트 근거 기반 추천 사유 도출
        """
        # STEP 1: 필터링
        cand_indices, excluded_109_cnt, preserved_109_cnt = self.filter_candidates(
            target_domain=target_domain,
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

        # 검색 텍스트 구성 (질의어 또는 역량 텍스트)
        search_text = query or ""
        if not search_text and target_domain:
            search_text = f"{target_domain} 핵심 실무 역량 강화 교육"

        # STEP 2: 하이브리드 점수 계산
        # 1) Ko-SRoBERTa 768차원 시맨틱 유사도
        if self.has_embeddings and self.model is not None:
            q_vec = self.model.encode(search_text, normalize_embeddings=True, device=self.device)
            cand_embs = self.embeddings[cand_indices]
            sims = np.dot(cand_embs, q_vec)
            semantic_scores = np.clip(sims, 0.0, 1.0) * 100.0
        else:
            semantic_scores = np.full(len(cand_indices), 50.0, dtype=np.float32)

        # 2) BM25 Okapi 키워드 적합도
        q_tokens = [t for t in search_text.split() if t in self.bm25_vocab]
        if q_tokens:
            bm25_raw_all = self.bm25.get_scores(q_tokens)
            bm25_cand = bm25_raw_all[cand_indices]
            max_b = bm25_cand.max()
            bm25_scores = (bm25_cand / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_cand)
        else:
            bm25_scores = np.zeros(len(cand_indices))

        df_cand = self.df_courses.iloc[cand_indices].copy()

        # 3) 레벨 적합도 점수 (최대 10점)
        level_bonus = np.zeros(len(cand_indices))
        if user_level:
            diff_s = df_cand['difficulty'].fillna('').astype(str)
            if user_level == "입문":
                level_bonus[diff_s.str.contains('입문|초급|기초', na=False)] = 10.0
            elif user_level == "실무":
                level_bonus[diff_s.str.contains('실무|중급|실전', na=False)] = 10.0
            elif user_level == "관리자·심화":
                level_bonus[diff_s.str.contains('관리자|고급|심화|리더|전략', na=False)] = 10.0

        # 4) 군집 부스팅 점수 (가변 파라미터 cluster_boost)
        cluster_bonus = np.zeros(len(cand_indices))
        if cluster_boost > 0.0 and target_domain:
            if target_domain in ["총무", "경영기획"]:
                is_match = df_cand['cluster_id'].isin([2, 3]).values # 실무역량, 경영기획
                cluster_bonus[is_match] = float(cluster_boost)
            elif target_domain in ["인사", "인사평가", "노무"]:
                is_match = df_cand['cluster_id'].isin([2, 5, 8, 9]).values # 실무, 법정, 리더십, HRD
                cluster_bonus[is_match] = float(cluster_boost)

        # 5) 평점 보정 점수 (데이터 전원 결측이므로 공통 80점 중립값)
        rating_score = 80.0

        # 최종 스코어링 공식
        final_scores = (0.50 * semantic_scores) + (0.35 * bm25_scores) + (0.15 * rating_score) + level_bonus + cluster_bonus

        df_cand['final_score'] = final_scores
        df_cand['semantic_score'] = semantic_scores
        df_cand['bm25_score'] = bm25_scores
        df_cand['level_bonus'] = level_bonus
        df_cand['cluster_bonus'] = cluster_bonus

        # 가격 및 시간 표시 문자열 준비
        def format_price(p):
            if pd.isna(p):
                return "가격 미확인"
            elif p == 0:
                return "무료"
            else:
                return f"{int(p):,}원"

        def format_dur(d):
            if pd.isna(d):
                return "시간 미확인"
            else:
                return f"{d}시간"

        df_cand['price_display'] = df_cand['numeric_price'].apply(format_price)
        df_cand['duration_display'] = df_cand['numeric_duration'].apply(format_dur)

        # STEP 3: 전체 후보 점수순 정렬
        df_cand_sorted = df_cand.sort_values(by='final_score', ascending=False)

        # STEP 4 & 5: 동일 플랫폼 다회차 및 크로스 플랫폼 실제 동일 강좌 중복 제거
        df_dedup = self.deduplicate_cross_platform(
            df_cand_sorted,
            user_max_budget=max_budget,
            user_edu_type=edu_type
        )

        # STEP 6: 최종 Top N 선정 및 실제 교육 텍스트 근거 생성
        top_df = df_dedup.head(top_n).copy()

        recommendation_cards = []
        for rank, (_, row) in enumerate(top_df.iterrows(), 1):
            intro = str(row.get('clean_intro', ''))
            curri = str(row.get('clean_curriculum', ''))
            full_text = f"{row['title']} {intro} {curri}"

            # 텍스트 충실도 판정
            if (len(intro) + len(curri)) > 200:
                richness = "RICH"
            elif (len(intro) + len(curri)) > 50:
                richness = "MODERATE"
            else:
                richness = "TITLE_ONLY"

            # 추천 사유 도출 (실제 교육내용 근거 발췌)
            if richness == "TITLE_ONLY":
                rec_reason = f"⚠️ [상세내용 미제공] 강좌명({row['title']})의 핵심 직무 키워드 및 도메인 정합성에 근거하여 추천되었습니다."
            else:
                rec_reason = f"과정 커리큘럼 및 소개 내용에 기반하여 검색 의도({search_text[:25]}...)에 부합하는 실무 내용을 제공합니다."

            # 109건 상태 태그
            is_109 = row['course_uid'] in self.mismatch_109_uids
            mismatch_tag = "🔵 [검증보존 강좌]" if is_109 else "🟢 [정규 강좌]"

            recommendation_cards.append({
                "rank": rank,
                "course_uid": row["course_uid"],
                "title": row["title"],
                "provider": row["canonical_platform"],
                "url": row.get("url", "#"),
                "final_score": round(row["final_score"], 1),
                "semantic_score": round(row["semantic_score"], 1),
                "bm25_score": round(row["bm25_score"], 1),
                "level_bonus": round(row["level_bonus"], 1),
                "cluster_bonus": round(row["cluster_bonus"], 1),
                "cluster_id": row.get("cluster_id", 0),
                "topic_label": row.get("topic_label", "미분류"),
                "price_display": row["price_display"],
                "duration_display": row["duration_display"],
                "education_type": str(row.get("education_type", "온라인")),
                "difficulty": str(row.get("difficulty", "실무")),
                "text_richness": richness,
                "mismatch_status": mismatch_tag,
                "recommendation_reason": rec_reason,
                "alternative_offerings": row.get("alternative_offerings", []),
                "alt_count": row.get("alt_count", 0)
            })

        return pd.DataFrame(recommendation_cards), n_candidates, excluded_109_cnt, preserved_109_cnt, "추천이 성공적으로 생성되었습니다."
