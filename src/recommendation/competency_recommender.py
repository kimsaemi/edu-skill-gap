"""
NCS·KSA 직무역량 기반 맞춤형 교육 추천 엔진 모듈
- STEP 5-4: 직무(인사/총무/경영지원) 및 8대 KSA 역량 기반 맞춤 교육 추천
- Ko-SRoBERTa 768차원 임베딩 + BM25 키워드 + 난이도 레벨 적합도 + 10대 군집 사전확률 + 109건 오매핑 차단 룰
"""

import os
import sys
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

# 8대 KSA 직무 역량 마스터 정의
KSA_COMPETENCIES_MASTER = {
    "COMP_HR_01": {
        "id": "COMP_HR_01",
        "name": "인력채용",
        "job_family": "인사",
        "ncs_unit_code": "02020201_16v3",
        "ksa_type": "Skill",
        "definition": "조직의 인력 수급 계획에 따라 적합한 인재를 선발하고 배치하는 능력",
        "knowledge": "채용 프로세스, 선발 도구, 노동법상 채용 규정, 직무 분석",
        "skill": "면접 기술, 역량 평가, 입사 온보딩 기획, 인재 소싱",
        "attitude": "공정성, 윤리의식, 수용적 태도",
        "search_query": "인력채용 선발 면접 역량평가 입사 온보딩 채용프로세스 구인 직무기술서 헤드헌팅 인재영입",
        "core_keywords": ["채용", "선발", "면접", "온보딩", "인재", "구인", "서류전형", "면접관"]
    },
    "COMP_HR_02": {
        "id": "COMP_HR_02",
        "name": "인사평가 및 보상",
        "job_family": "인사",
        "ncs_unit_code": "02020202_16v3",
        "ksa_type": "Knowledge",
        "definition": "조직원의 성과 및 역량을 객관적으로 평가하고 보상 체계를 운영하는 능력",
        "knowledge": "KPI 지표 설계, 다면평가 기법, 보상 제도 설계, 직무급제, 연봉제",
        "skill": "성과 분석, 피드백 코칭, 데이터 집계, 성과관리 시트 작성",
        "attitude": "객관성, 공평성, 신뢰성",
        "search_query": "인사평가 보상체계 KPI 성과관리 직무분석 다면평가 연봉설계 피드백 코칭 평가보상 성과급",
        "core_keywords": ["인사평가", "성과평가", "KPI", "보상", "연봉", "성과관리", "다면평가", "직무급제"]
    },
    "COMP_LABOR_01": {
        "id": "COMP_LABOR_01",
        "name": "근로관계 법률 준수",
        "job_family": "인사",
        "ncs_unit_code": "02030201_16v3",
        "ksa_type": "Knowledge",
        "definition": "근로기준법, 노동조합법 등 노동관계 법령을 숙지하고 노무 리스크를 예방하는 능력",
        "knowledge": "근로기준법령, 임금 계산 기준, 해고 및 퇴직 규정, 4대보험, 주52시간제",
        "skill": "근로계약서 검토, 취업규칙 개정, 분쟁 조정, 노사협의회 운영, 급여계산",
        "attitude": "준법정신, 상호 존중, 공정성",
        "search_query": "근로기준법 근로계약서 취업규칙 노무관리 주휴수당 퇴직금 해고 4대보험 노사관계 급여대장 노동법",
        "core_keywords": ["근로기준법", "근로계약", "취업규칙", "노무", "4대보험", "퇴직금", "노동법", "주휴수당"]
    },
    "COMP_GA_01": {
        "id": "COMP_GA_01",
        "name": "문서작성 및 기획",
        "job_family": "총무",
        "ncs_unit_code": "02010101_16v3",
        "ksa_type": "Skill",
        "definition": "사내외 정보와 데이터를 분석하여 효과적인 보고서 및 기획서를 작성하는 능력",
        "knowledge": "문서 규정, 기획 프로세스, 데이터 시각화, 공문서 양식",
        "skill": "보고서 작성, 기획서 프레임워크 활용, 발표 기술, 스마트오피스 엑셀 서식",
        "attitude": "논리적 사고, 치밀성, 적극성",
        "search_query": "기획서 작성 보고서 작성 공문서 스마트 비즈니스 문서 엑셀 제안서 프레젠테이션 공문서작성 비즈니스문서",
        "core_keywords": ["문서작성", "보고서", "기획서", "공문서", "제안서", "엑셀", "비즈니스문서", "프레젠테이션"]
    },
    "COMP_GA_02": {
        "id": "COMP_GA_02",
        "name": "비품 및 자산관리",
        "job_family": "총무",
        "ncs_unit_code": "02010102_16v3",
        "ksa_type": "Skill",
        "definition": "조직의 유무형 자산과 동산·부동산을 등록, 관리, 평가, 처분하는 능력",
        "knowledge": "자산 회계 기준, 감가상각 규정, 재물조사 절차, 계약법, 사옥시설관리",
        "skill": "자산 대장 관리, 자산 실사, 구매 계약 체결, 비품 조달, 협력업체 관리",
        "attitude": "정확성, 책임감, 절약 정신",
        "search_query": "비품 관리 사옥 자산관리 재물조사 비품구매 계약체결 시설관리 고정자산 감가상각 협력업체관리 구매관리",
        "core_keywords": ["자산관리", "비품", "구매계약", "재물조사", "시설관리", "고정자산", "구매관리", "협력업체"]
    },
    "COMP_SEC_01": {
        "id": "COMP_SEC_01",
        "name": "비즈니스 매너 및 커뮤니케이션",
        "job_family": "경영지원",
        "ncs_unit_code": "02040302_16v3",
        "ksa_type": "Attitude",
        "definition": "조직 내외부 고객과의 원활한 소통을 위해 글로벌 비즈니스 에티켓을 실천하는 능력",
        "knowledge": "의전 규정, 글로벌 비즈니스 에티켓, 비언어적 커뮤니케이션, 전화응대",
        "skill": "상황별 대화 기술, 이메일 에티켓, 갈등 조정, 일정 관리, 고객응대",
        "attitude": "배려심, 전문성, 품격 있는 태도",
        "search_query": "비즈니스 매너 비즈니스 이메일 커뮤니케이션 의전 전화응대 대화법 직장예절 스피치 고객만족",
        "core_keywords": ["비즈니스매너", "이메일", "커뮤니케이션", "의전", "전화응대", "직장예절", "소통", "에티켓"]
    },
    "COMP_MGMT_01": {
        "id": "COMP_MGMT_01",
        "name": "프로젝트 및 조직관리",
        "job_family": "경영지원",
        "ncs_unit_code": "01010102_16v3",
        "ksa_type": "Skill",
        "definition": "변화하는 경영 환경에 대응하여 프로젝트 일정과 자원을 기민하게 관리하는 능력",
        "knowledge": "애자일/스크럼 방법론, 스프린트 기획, 리스크 관리, 목표관리 MBO",
        "skill": "WBS 작성, 칸반 보드 운용, 백로그 우선순위화, 회의 퍼실리테이션",
        "attitude": "유연성, 협업 지향, 피드백 수용",
        "search_query": "프로젝트 관리 조직관리 WBS 애자일 일정관리 리더십 협업 팀빌딩 리스크관리 프로젝트관리",
        "core_keywords": ["프로젝트", "일정관리", "WBS", "애자일", "조직관리", "팀빌딩", "협업", "리스크관리"]
    },
    "COMP_MGMT_02": {
        "id": "COMP_MGMT_02",
        "name": "경영전략 및 재무회계 기초",
        "job_family": "경영지원",
        "ncs_unit_code": "02030101_16v3",
        "ksa_type": "Knowledge",
        "definition": "조직의 경영 목표 달성을 위해 경영 환경을 분석하고 기초 재무제표와 원가를 관리하는 능력",
        "knowledge": "재무제표 분석(재무상태표, 손익계산서), 원가계산, 관리회계, 사업계획 수립",
        "skill": "예산 편성, 손익분기점(BEP) 분석, 회계 전표 검토, 경영실적 분석",
        "attitude": "수리적 정확성, 분석적 사고, 전략적 관점",
        "search_query": "경영전략 재무회계 기초 재무제표 손익계산서 예산편성 원가계산 결산 세무실무 사업계획 관리회계",
        "core_keywords": ["재무회계", "경영전략", "재무제표", "예산", "원가계산", "결산", "손익계산서", "사업계획"]
    }
}

class CompetencyRecommender:
    """NCS·KSA 직무역량 기반 맞춤형 교육 추천 엔진"""

    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._load_datasets()
        self._init_search_engines()

    def _load_datasets(self):
        # 1. 8,645건 정제 코퍼스
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

        # 3. Ko-SRoBERTa 768차원 임베딩 행렬
        p_emb = OUTPUT_DIR / "embeddings_ko_sroberta_all.npy"
        self.embeddings = np.load(p_emb)

        # 4. 토큰화 캐시 (BM25용)
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

        # 6. KSA 기존 매핑 데이터 (보조 신호용)
        p_comp_long = OUTPUT_DIR / "course_competency_long.parquet"
        self.df_comp_long = pd.read_parquet(p_comp_long) if p_comp_long.exists() else pd.DataFrame()

        # 수치 변환
        self.df_courses['numeric_price'] = pd.to_numeric(self.df_courses['price'], errors='coerce')
        self.df_courses['numeric_duration'] = pd.to_numeric(self.df_courses['duration_hours'], errors='coerce')

        # 가격 상태 정의: FREE, PAID, UNCONFIRMED
        price_is_na = self.df_courses['numeric_price'].isna()
        is_free = (self.df_courses['numeric_price'] == 0) & (~price_is_na)
        self.df_courses['price_status'] = 'PAID'
        self.df_courses.loc[price_is_na, 'price_status'] = 'UNCONFIRMED'
        self.df_courses.loc[is_free, 'price_status'] = 'FREE'

    def _init_search_engines(self):
        # BM25 초기화
        corpus_tokens = [txt.split() for txt in self.df_courses['tokenized_text']]
        self.bm25 = BM25Okapi(corpus_tokens, k1=1.5, b=0.75)
        self.bm25_vocab = {t for toks in corpus_tokens for t in toks}

        # Ko-SRoBERTa 질의 인코더 초기화
        self.model = SentenceTransformer("jhgan/ko-sroberta-multitask", device=self.device)

    def get_competencies_for_job(self, job_family: str = None) -> list:
        """선택한 직무군에 해당하는 KSA 역량 목록을 반환합니다."""
        results = []
        for comp_id, info in KSA_COMPETENCIES_MASTER.items():
            if not job_family or job_family == "전체" or info["job_family"] == job_family:
                results.append(info)
        return results

    def filter_candidate_indices(
        self,
        job_family: str,
        competency_info: dict,
        platforms: list = None,
        max_budget: int = None,
        duration_type: str = "전체",
        edu_type: str = "전체"
    ) -> np.ndarray:
        """사용자가 지정한 하드 제약조건을 사전 필터링하고 오매핑 109건을 차단합니다."""
        df = self.df_courses
        mask = np.ones(len(df), dtype=bool)

        # 1. 플랫폼 필터
        if platforms:
            mask &= df['canonical_platform'].isin(platforms)

        # 2. 예산 필터 (결측치는 무료로 왜곡하지 않고 분리 배제)
        if max_budget is not None and max_budget != "전체":
            b_val = int(max_budget)
            if b_val == 0:
                # 순수 무료 과정만 허용
                mask &= (df['price_status'] == 'FREE')
            else:
                # 확인된 무료 및 예산 이하 유료 과정 허용 (가격 미확인은 기본 배제)
                mask &= (
                    (df['price_status'] == 'FREE') |
                    ((df['price_status'] == 'PAID') & (df['numeric_price'] <= b_val))
                )

        # 3. 교육 형태 필터
        if edu_type == "온라인":
            mask &= df['education_type'].astype(str).str.contains('온라인|사이버|원격|플립', na=False)
        elif edu_type == "오프라인":
            mask &= df['education_type'].astype(str).str.contains('오프라인|집체|현장', na=False)

        # 4. 학습 시간 필터
        if duration_type == "단기 (<10시간)":
            mask &= (df['numeric_duration'] < 10.0)
        elif duration_type == "중기 (10~40시간)":
            mask &= ((df['numeric_duration'] >= 10.0) & (df['numeric_duration'] <= 40.0))
        elif duration_type == "장기 (>40시간)":
            mask &= (df['numeric_duration'] > 40.0)

        # 5. 오매핑 109건 차단 룰 (HR/총무 질의 시 IT/코딩 비-HR 강좌 원천 차단)
        if job_family in ["인사", "총무", "경영지원"]:
            is_109 = df['course_uid'].isin(self.mismatch_109_uids)
            is_non_hr_cluster = df['cluster_id'].isin([0, 1, 4, 5, 7]) # 데이터/AI, 북러닝, 공공시민, 안전, 어학
            title_it_term = df['title'].str.contains('파이썬|코딩|개발|서버|Spring|Docker|AWS|클라우드|Java|React', case=False, na=False)
            
            suspect_leak = is_109 & (is_non_hr_cluster | title_it_term)
            mask &= (~suspect_leak)

        return np.where(mask)[0]

    def recommend(
        self,
        job_family: str,
        competency_id: str,
        user_level: str = "실무",
        duration_type: str = "전체",
        max_budget: int = None,
        edu_type: str = "전체",
        platforms: list = None,
        top_n: int = 5
    ) -> tuple:
        """
        직무역량 기반 맞춤형 추천 4단계 파이프라인:
        [1] 사전 조건 및 109건 오매핑 필터링
        [2] 역량 정합성(Ko-SRoBERTa 50% + BM25 30% + 난이도 10% + 군집/보조매핑 10%) 스코어링
        [3] 다회차 중복 제거 (Dedup)
        [4] Top-N 선정 및 텍스트 근거 기반 추천 사유 생성
        """
        competency_info = KSA_COMPETENCIES_MASTER.get(competency_id)
        if not competency_info:
            return pd.DataFrame(), 0, "유효하지 않은 KSA 역량 ID입니다."

        # STEP 1: 사전 필터링
        cand_idx = self.filter_candidate_indices(
            job_family=job_family,
            competency_info=competency_info,
            platforms=platforms,
            max_budget=max_budget,
            duration_type=duration_type,
            edu_type=edu_type
        )

        n_candidates = len(cand_idx)
        if n_candidates == 0:
            return pd.DataFrame(), 0, "선택하신 조건을 충족하는 교육과정이 없습니다."

        # STEP 2: 스코어링
        # 1) 시맨틱 유사도 (Ko-SRoBERTa 768차원): 역량 정의 + 검색 쿼리 벡터화
        comp_text = f"{competency_info['name']} {competency_info['definition']} {competency_info['knowledge']} {competency_info['skill']}"
        q_vec = self.model.encode(comp_text, normalize_embeddings=True, device=self.device)
        cand_embs = self.embeddings[cand_idx]
        sims = np.dot(cand_embs, q_vec)
        semantic_scores = np.clip(sims, 0.0, 1.0) * 100.0

        # 2) 키워드 점수 (BM25 Okapi)
        q_tokens = [t for t in competency_info['search_query'].split() if t in self.bm25_vocab]
        if q_tokens:
            bm25_raw_all = self.bm25.get_scores(q_tokens)
            bm25_cand = bm25_raw_all[cand_idx]
            max_b = bm25_cand.max()
            keyword_scores = (bm25_cand / max_b * 100.0) if max_b > 0 else np.zeros_like(bm25_cand)
        else:
            keyword_scores = np.zeros(len(cand_idx))

        df_cand = self.df_courses.iloc[cand_idx].copy()

        # 3) 난이도 레벨 적합도 점수 (최대 10점)
        level_scores = np.zeros(len(cand_idx))
        diff_str = df_cand['difficulty'].fillna('').astype(str)
        if user_level == "입문":
            # 입문, 기초, 초급 우대
            match_mask = diff_str.str.contains('입문|초급|기초', na=False)
            level_scores[match_mask] = 10.0
            level_scores[diff_str == ''] = 5.0
        elif user_level == "실무":
            # 실무, 중급, 실전 우대
            match_mask = diff_str.str.contains('실무|중급|실전', na=False)
            level_scores[match_mask] = 10.0
            level_scores[diff_str == ''] = 5.0
        elif user_level == "관리자·심화":
            # 관리자, 고급, 심화, 리더 우대
            match_mask = diff_str.str.contains('관리자|고급|심화|리더|전략', na=False)
            level_scores[match_mask] = 10.0
            level_scores[diff_str == ''] = 5.0

        # 4) 클러스터 도메인 보너스 (5점)
        cluster_bonus = np.zeros(len(cand_idx))
        if job_family == "총무":
            is_match = df_cand['cluster_id'].isin([2, 3]).values # 실무역량, 경영기획
            cluster_bonus[is_match] = 5.0
        elif job_family == "인사":
            is_match = df_cand['cluster_id'].isin([2, 5, 8, 9]).values # 실무, 법정, 리더십, HRD
            cluster_bonus[is_match] = 5.0
        elif job_family == "경영지원":
            is_match = df_cand['cluster_id'].isin([2, 3, 8]).values # 실무, 경영기획, 리더십
            cluster_bonus[is_match] = 5.0

        # 5) KSA 기존 매핑 보조 보너스 (5점)
        ksa_aux_bonus = np.zeros(len(cand_idx))
        if not self.df_comp_long.empty:
            mapped_uids = set(self.df_comp_long[self.df_comp_long['competency_id'] == competency_id]['course_uid'])
            is_aux_mapped = df_cand['course_uid'].isin(mapped_uids).values
            ksa_aux_bonus[is_aux_mapped] = 5.0

        # 종합 점수 (가중치: 의미 50% + 키워드 30% + 난이도 10% + 군집 5% + 보조매핑 5%)
        # 필수 제약인 비용 및 시간은 이미 사전 필터링되었으므로 점수에서 중복 반영 배제
        final_scores = (0.50 * semantic_scores) + (0.30 * keyword_scores) + level_scores + cluster_bonus + ksa_aux_bonus

        df_cand['final_score'] = final_scores
        df_cand['semantic_score'] = semantic_scores
        df_cand['keyword_score'] = keyword_scores
        df_cand['level_score'] = level_scores
        df_cand['cluster_bonus'] = cluster_bonus
        df_cand['ksa_aux_bonus'] = ksa_aux_bonus

        # STEP 3: 정렬 및 동일 강좌 다회차/플랫폼 간 중복 제거 (Dedup)
        df_cand = df_cand.sort_values(by='final_score', ascending=False)
        df_dedup = df_cand.drop_duplicates(subset=['title'])

        # STEP 4: Top N 선정 및 실제 교육 텍스트 근거 기반 추천 사유 도출
        top_df = df_dedup.head(top_n).copy()

        recommendation_cards = []
        for rank, (_, row) in enumerate(top_df.iterrows(), 1):
            intro = str(row.get('clean_intro', ''))
            curri = str(row.get('clean_curriculum', ''))
            full_text = f"{row['title']} {intro} {curri}"

            # 핵심 키워드 매칭 여부 탐색
            matched_kws = [kw for kw in competency_info['core_keywords'] if kw in full_text]
            matched_str = ", ".join(matched_kws[:4]) if matched_kws else "직무 적합성 매칭"

            # 텍스트 충실도 판정
            intro_len = len(intro)
            curri_len = len(curri)
            if (intro_len + curri_len) > 200:
                richness = "RICH"
            elif (intro_len + curri_len) > 50:
                richness = "MODERATE"
            else:
                richness = "TITLE_ONLY"

            # 교육 텍스트에 근거한 구체적 추천 사유 생성 (가짜 내용 생성 방지)
            if richness == "TITLE_ONLY":
                rec_reason = f"⚠️ [상세내용 미제공] 본 과정은 강좌명({row['title']})의 핵심 키워드와 직무역량({competency_info['name']}) 연계성에 근거해 추천되었습니다."
            else:
                # 커리큘럼에서 실제 매칭 문구 발췌
                snippets = []
                for kw in matched_kws[:3]:
                    if kw in curri:
                        idx = curri.find(kw)
                        snippet = curri[max(0, idx - 15):min(len(curri), idx + 25)].strip().replace('\n', ' ')
                        snippets.append(f"'{snippet}...'")
                
                if snippets:
                    snippet_text = " / ".join(snippets[:2])
                    rec_reason = f"커리큘럼 내 {snippet_text} 등 실제 실무 내용을 포함하여 [{competency_info['name']}] 역량 향상에 부합합니다."
                else:
                    rec_reason = f"과정 소개 내용 중 직무 키워드({matched_str})를 중심으로 [{competency_info['name']}] 실무 역량 강화를 제공합니다."

            # 수강료 및 시간 포맷
            p_val = row.get('numeric_price')
            if pd.isna(p_val):
                price_disp = "가격 미확인"
            elif p_val == 0:
                price_disp = "무료"
            else:
                price_disp = f"{int(p_val):,}원"
            
            d_val = row.get('numeric_duration')
            if pd.isna(d_val):
                dur_disp = "시간 미확인"
            else:
                dur_disp = f"{d_val}시간"

            recommendation_cards.append({
                "rank": rank,
                "course_uid": row["course_uid"],
                "title": row["title"],
                "provider": row["canonical_platform"],
                "url": row.get("url", "#"),
                "final_score": round(row["final_score"], 1),
                "semantic_score": round(row["semantic_score"], 1),
                "keyword_score": round(row["keyword_score"], 1),
                "level_score": round(row["level_score"], 1),
                "cluster_bonus": round(row["cluster_bonus"], 1),
                "ksa_aux_bonus": round(row["ksa_aux_bonus"], 1),
                "job_family": job_family,
                "competency_id": competency_id,
                "competency_name": competency_info["name"],
                "ncs_unit_code": competency_info["ncs_unit_code"],
                "matched_keywords": matched_str,
                "difficulty": str(row.get("difficulty", "실무")),
                "price_display": price_disp,
                "duration_display": dur_disp,
                "education_type": str(row.get("education_type", "온라인")),
                "topic_label": row.get("topic_label", "미분류"),
                "text_richness": richness,
                "recommendation_reason": rec_reason,
                "mapping_status": "EXPERT-VERIFIED" if row.get("is_verified") is True else "AUTO-ESTIMATED"
            })

        return pd.DataFrame(recommendation_cards), n_candidates, "추천이 성공적으로 생성되었습니다."
