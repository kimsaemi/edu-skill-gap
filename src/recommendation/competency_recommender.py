"""
NCS·KSA 직무역량 기반 맞춤형 교육 추천 엔진 어댑터 모듈
- 통합 하이브리드 추천 엔진(UnifiedHybridRecommender)을 호출하는 얇은 호환 어댑터(Thin Adapter)
- 데이터 로딩, BM25, 시맨틱 임베딩, 오매핑 109건 차단, 크로스 플랫폼 중복 제거를 공통 엔진으로 일원화
- 탭 10 및 기존 호출 코드와의 100% 하위 호환성 유지
"""

from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from src.recommendation.ksa_master import (
    KSA_COMPETENCIES_MASTER,
    get_competencies_for_job,
    get_competency_by_id
)
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender


class CompetencyRecommender:
    """
    NCS·KSA 직무역량 맞춤 추천 호환 어댑터 클래스.
    내부적으로 단일 통합 엔진(UnifiedHybridRecommender)을 호출하여
    중복 모델 로딩과 메모리 낭비를 제거하고 일관된 추천 로직을 보장합니다.
    """

    def __init__(self, engine: Optional[UnifiedHybridRecommender] = None, device: str = None):
        if engine is not None:
            self.engine = engine
        else:
            self.engine = UnifiedHybridRecommender(device=device)

    # 하위 호환 속성 매핑
    @property
    def df_courses(self) -> pd.DataFrame:
        return self.engine.df_courses

    @property
    def embeddings(self):
        return self.engine.embeddings

    @property
    def has_embeddings(self) -> bool:
        return self.engine.has_embeddings

    @property
    def mismatch_109_uids(self):
        return self.engine.mismatch_109_uids

    @property
    def df_comp_long(self) -> pd.DataFrame:
        return self.engine.df_comp_long

    def get_competencies_for_job(self, job_family: str = None) -> List[Dict[str, Any]]:
        """선택한 직무군에 해당하는 KSA 역량 목록을 반환합니다."""
        return get_competencies_for_job(job_family)

    def filter_candidate_indices(
        self,
        job_family: str,
        competency_info: dict = None,
        platforms: list = None,
        max_budget: int = None,
        duration_type: str = "전체",
        edu_type: str = "전체"
    ):
        """사전 필터링 호환 메서드: 공통 엔진의 filter_candidates를 호출합니다."""
        durations = [duration_type] if duration_type != "전체" else None
        p_filter = "MAX_BUDGET" if (max_budget is not None and max_budget != "전체") else "ALL"
        cand_indices, _, _ = self.engine.filter_candidates(
            target_domain=job_family,
            platforms=platforms,
            price_filter=p_filter,
            max_budget=max_budget,
            edu_type=edu_type,
            durations=durations,
            filter_mismatch_109=True
        )
        return cand_indices

    def recommend(
        self,
        job_family: str,
        competency_id: str,
        user_level: str = "실무",
        duration_type: str = "전체",
        max_budget: int = None,
        edu_type: str = "전체",
        platforms: list = None,
        top_n: int = 5,
        cluster_boost: float = 0.0
    ) -> Tuple[pd.DataFrame, int, str]:
        """
        KSA 직무역량 맞춤형 추천 실행:
        공통 추천 엔진(UnifiedHybridRecommender)에 mode='ksa' 및 competency_id를 전달하여
        통일된 6단계 파이프라인(4축 스코어링 + 크로스 플랫폼 중복 제거 + 커리큘럼 추천 근거)을 수행합니다.
        반환 규격: (results_df, n_candidates, msg)
        """
        durations = [duration_type] if duration_type != "전체" else None
        p_filter = "MAX_BUDGET" if (max_budget is not None and max_budget != "전체") else "ALL"

        results_df, n_cand, ex_109, pr_109, msg = self.engine.recommend(
            query=None,
            target_domain=job_family,
            competency_id=competency_id,
            user_level=user_level,
            platforms=platforms,
            price_filter=p_filter,
            max_budget=max_budget,
            edu_type=edu_type,
            durations=durations,
            cluster_boost=cluster_boost,
            filter_mismatch_109=True,
            top_n=top_n,
            mode="ksa"
        )

        return results_df, n_cand, msg
