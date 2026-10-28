"""
진단 결과 ↔ 공통 추천 엔진 연동 브릿지 모듈 (recommendation_bridge.py)
- UI와 독립적으로 동작하며 향후 서비스/API에서도 재사용 가능
- 부족 역량(Deficiency) ID, 수행 업무, 학습 목표, 예산/형태 필터를 UnifiedHybridRecommender에 전달
- 복수 역량별 검색 후 교차 중복 제거 및 다중 역량 연계 태그 보존
- 교육시간(총시간)과 주당 학습 가능 시간을 분리하여 현실적인 학습 페이스 안내
- 기술 용어(TF-IDF, BM25 등)를 배제하고 고객 중심 추천 사유 및 커리큘럼 근거 생성
"""

import math
import re
from datetime import date
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import pandas as pd

from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender
from src.recommendation.ksa_master import KSA_COMPETENCY_MASTER
from src.assessment.evaluator import AssessmentEvaluationResult, CompetencyScore

@dataclass
class RecommendationFilterParams:
    price_filter: str = "ALL"              # "ALL", "FREE_ONLY", "MAX_BUDGET"
    max_budget: Optional[int] = None       # None or int (원)
    edu_type: str = "ALL"                  # "ALL", "ONLINE", "OFFLINE"
    weekly_hours: Optional[float] = 4.0    # 주당 학습 가능 시간 (참고용 페이스 안내)
    durations: Optional[List[str]] = None  # ["SHORT", "MEDIUM", "LONG", "UNCONFIRMED"]
    target_difficulty: Optional[str] = None # None, "입문", "실무", "관리자·심화"

@dataclass
class RecommendedCourseCard:
    course_uid: str
    title: str
    provider: str
    url: str
    price_display: str
    numeric_price: Optional[float]
    price_status: str                      # "FREE", "PAID", "UNCONFIRMED"
    duration_display: str
    numeric_duration: Optional[float]
    education_type: str
    difficulty: str
    primary_competency_id: str
    primary_competency_name: str
    linked_competencies: List[Dict[str, Any]] = field(default_factory=list)
    customer_recommendation_reason: str = ""
    curriculum_evidence: str = ""
    goal_connection: str = ""              # 내 목표와의 연결
    content_evidence: str = ""             # 교육에서 확인한 내용
    evidence_limitation: str = ""          # 추천 근거의 한계
    schedule_display: str = "일정·모집 여부는 교육기관에서 확인" # 확인된 일정
    schedule_badge: Optional[str] = None   # 일정이 지난 과정 표시 ("운영 종료" / "안내된 일정 종료")
    source_display: str = ""               # 정보 출처 및 확인 시점
    text_richness: str = "MODERATE"        # "RICH", "MODERATE", "TITLE_ONLY"
    text_richness_warning: Optional[str] = None
    study_plan_note: str = ""
    alternative_offerings: List[Dict[str, Any]] = field(default_factory=list)
    raw_matching_score: float = 0.0
    mapping_basis: str = ""                # "기존 역량 연결 정보 기반" 또는 "교육내용 검색으로 찾은 추가 후보"

@dataclass
class CustomerRecommendationBundle:
    job_family: str
    is_sample: bool
    evaluated_competency_count: int
    prioritized_competency_ids: List[str]
    filter_params: RecommendationFilterParams
    courses_by_competency: Dict[str, List[RecommendedCourseCard]]
    all_courses_deduped: List[RecommendedCourseCard]
    total_recommended_count: int
    status_message: str
    actionable_guidance: Optional[str] = None

# 모듈 수준 싱글톤 캐시 (Streamlit 환경에서는 @st.cache_resource로 스레드 안전 관리)
_RECOMMENDER_INSTANCE: Optional[UnifiedHybridRecommender] = None

try:
    import streamlit as st
    @st.cache_resource(show_spinner="추천 인공지능 모델 및 교육 데이터베이스 로드 중...")
    def _get_st_cached_recommender() -> UnifiedHybridRecommender:
        return UnifiedHybridRecommender()
except Exception:
    _get_st_cached_recommender = None

def get_shared_recommender() -> UnifiedHybridRecommender:
    """공통 추천 엔진 싱글톤 인스턴스를 반환합니다. (Streamlit 캐시 우선 활용)"""
    if _get_st_cached_recommender is not None:
        try:
            return _get_st_cached_recommender()
        except Exception:
            pass
    global _RECOMMENDER_INSTANCE
    if _RECOMMENDER_INSTANCE is None:
        _RECOMMENDER_INSTANCE = UnifiedHybridRecommender()
    return _RECOMMENDER_INSTANCE

def _common_card_fields(row: pd.Series, weekly_h: float) -> Dict[str, Any]:
    """추천 결과 1행에서 역량·업무와 무관한 공통 카드 정보(가격·시간·일정·출처·근거)를 만듭니다."""
    provider = row.get('canonical_platform', '')
    num_price = row.get('numeric_price')
    # 빈 값(pd.NA·NaN·None)은 모두 None으로 맞춤 (pd.NA는 비교식에서 오류가 남)
    num_price = None if num_price is None or pd.isna(num_price) else num_price
    price_status = row.get('price_status', 'UNCONFIRMED')

    # 수강료 정직 처리 (0=무료, 양수=수강료, 결측=가격 미확인)
    if num_price == 0 or price_status == 'FREE':
        price_disp = "무료"
    elif pd.notna(num_price) and float(num_price) > 0:
        price_disp = f"수강료 {int(num_price):,}원"
    else:
        price_disp = "가격 미확인"

    num_dur = row.get('numeric_duration')
    num_dur = None if num_dur is None or pd.isna(num_dur) else num_dur
    dur_disp = f"{float(num_dur):g}시간" if pd.notna(num_dur) and float(num_dur) > 0 else "시간 미확인"

    raw_edu = str(row.get('education_type', '')).strip()
    edu_t = raw_edu if raw_edu and raw_edu.lower() not in ['nan', 'none', ''] else "형태 미확인"

    raw_diff = str(row.get('difficulty', '')).strip()
    diff = raw_diff if raw_diff and raw_diff.lower() not in ['nan', 'none', ''] else "미확인"

    t_richness = row.get('text_richness', 'MODERATE')
    alt_offerings = row.get('alternative_offerings', [])

    # 일정 확인 (결측 시 솔직 안내)
    raw_start = str(row.get('start_date', '')).strip()
    raw_end = str(row.get('end_date', '')).strip()
    schedule_badge = None
    if raw_start and raw_start.lower() not in ['nan', 'none', '']:
        has_end = raw_end and raw_end.lower() not in ['nan', 'none', '']
        if has_end and raw_end != raw_start:
            schedule_disp = f"{raw_start} ~ {raw_end}"
        else:
            schedule_disp = f"{raw_start}"
        # 일정이 지난 과정 표시. 고용24 과정은 전체 회차를 API로 확인하므로 '운영 종료',
        # 다른 기관은 같은 과정을 다시 여는 경우가 많아 '안내된 일정 종료'로 구분한다.
        last_day = (raw_end if has_end else raw_start)[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_day) and last_day < date.today().isoformat():
            if str(row.get('source_provider', '')).startswith('고용24'):
                schedule_badge = "운영 종료"
                schedule_disp = f"운영 종료 (마지막으로 확인한 회차: {schedule_disp})"
            else:
                schedule_badge = "안내된 일정 종료"
                schedule_disp = f"{schedule_disp} (지난 일정 · 다음 일정은 교육기관에서 확인)"
    else:
        schedule_disp = "일정·모집 여부는 교육기관에서 확인"

    # 출처 및 데이터 수집 시점 (임의 최신 확인일 생성 금지)
    src_p = row.get('source_provider') or row.get('provider') or provider
    col_at = row.get('collected_at')
    if pd.notna(col_at) and str(col_at).strip() and str(col_at).strip().lower() != 'nan':
        source_disp = f"{src_p} 공개 데이터 (데이터 수집 시점: {str(col_at).split('T')[0]})"
    else:
        source_disp = f"{src_p} 공개 데이터"

    # 추천 근거의 한계
    if t_richness == "TITLE_ONLY":
        limitation_text = "상세 교육내용이 부족해 강좌명과 제공된 정보 중심으로 추천했습니다. 교육기관 상세페이지에서 세부 목차를 반드시 확인하세요."
        warning_text = "⚠️ 상세 소개·커리큘럼이 제공되지 않아 강좌명 키워드 중심으로 추천되었습니다. 상세 페이지에서 목차를 확인해 주세요."
    else:
        limitation_text = "공개된 커리큘럼 텍스트 분석에 기반한 추천이며, 최신 수강 요건 및 개강 여부는 교육기관 공지를 확인해 주세요."
        warning_text = None

    # 주당 학습 시간 안내
    if pd.notna(num_dur) and float(num_dur) > 0:
        dur_val = float(num_dur)
        weeks_est = max(1, math.ceil(dur_val / max(1.0, weekly_h)))
        study_note = (
            f"총 {dur_val:g}시간 강좌: 주당 {weekly_h:g}시간 학습 시 약 {weeks_est}주 소요 예상 "
            f"(※ 개별 교육기관의 학사 일정 및 이수 기준에 따라 상이할 수 있습니다)"
        )
    else:
        study_note = "총 교육시간 정보가 공식적으로 확인되지 않은 강좌입니다. 수강 신청 전 운영기관 안내를 확인해 주세요."

    raw_snip = row.get('clean_snippet')
    if raw_snip and str(raw_snip).strip():
        content_evidence = f"커리큘럼 발췌: {str(raw_snip).strip()}"
        curriculum_evidence = str(raw_snip).strip()
    elif row.get('content_evidence'):
        content_evidence = str(row['content_evidence'])
        curriculum_evidence = content_evidence
    else:
        content_evidence = "상세 교육내용이 부족해 강좌명과 제공된 정보 중심으로 추천했습니다."
        curriculum_evidence = content_evidence

    return dict(
        course_uid=row['course_uid'],
        title=row['title'],
        provider=provider,
        url=row.get('url', '#'),
        price_display=price_disp,
        numeric_price=float(num_price) if pd.notna(num_price) else None,
        price_status=price_status,
        duration_display=dur_disp,
        numeric_duration=float(num_dur) if pd.notna(num_dur) else None,
        education_type=edu_t,
        difficulty=diff,
        curriculum_evidence=curriculum_evidence,
        content_evidence=content_evidence,
        evidence_limitation=limitation_text,
        schedule_display=schedule_disp,
        schedule_badge=schedule_badge,
        source_display=source_disp,
        text_richness=t_richness,
        text_richness_warning=warning_text,
        study_plan_note=study_note,
        alternative_offerings=alt_offerings if isinstance(alt_offerings, list) else [],
        raw_matching_score=float(row.get('final_score', 0.0)),
    )


def get_recommendations_for_assessment(
    eval_result: AssessmentEvaluationResult,
    filter_params: Optional[RecommendationFilterParams] = None,
    recommender: Optional[UnifiedHybridRecommender] = None,
    top_n_per_comp: int = 3
) -> CustomerRecommendationBundle:
    """
    진단 결과(eval_result)의 우선 보완 역량들을 공통 추천 엔진에 연결하여 맞춤 교육 번들을 생성합니다.
    """
    filter_params = filter_params or RecommendationFilterParams()
    engine = recommender or get_shared_recommender()

    # 대상 역량 결정: 보완 대상(gap > 0) 우선, 없으면 심화 대상(gap == 0) 안내
    target_comp_scores: List[CompetencyScore] = []
    is_deepening_mode = False

    if eval_result.prioritized_deficiencies:
        target_comp_scores = eval_result.prioritized_deficiencies
    elif eval_result.zero_gap_competencies:
        # 역량 차이가 없는 경우 -> 억지로 부족 역량을 만들지 않고 심화 학습 대상 역량 선정
        is_deepening_mode = True
        target_comp_scores = eval_result.zero_gap_competencies[:2]
    else:
        # 정보 부족 등으로 평가된 역량이 없는 경우
        return CustomerRecommendationBundle(
            job_family=eval_result.job_family,
            is_sample=eval_result.is_sample,
            evaluated_competency_count=len(eval_result.competency_scores),
            prioritized_competency_ids=[],
            filter_params=filter_params,
            courses_by_competency={},
            all_courses_deduped=[],
            total_recommended_count=0,
            status_message="보완할 역량을 확정할 수 없습니다. (응답 정보 부족)",
            actionable_guidance="진단 문항에서 '해당 업무 아님'이나 '판단 어려움' 대신 1~5점 척도로 2문항 이상 응답하시면 정확한 맞춤 추천을 받으실 수 있습니다."
        )

    courses_by_comp: Dict[str, List[RecommendedCourseCard]] = {}
    deduped_cards_map: Dict[str, RecommendedCourseCard] = {}
    prioritized_ids = [cs.competency_id for cs in target_comp_scores]

    # (course_uid, competency_id) 매핑 유효성 검증용 튜플 세트 (엔진 사전 계산 세트 재사용)
    ksa_pair_set = getattr(engine, 'ksa_pair_set', None)
    if ksa_pair_set is None:
        ksa_pair_set = set(zip(engine.df_comp_long['course_uid'], engine.df_comp_long['competency_id'])) if not engine.df_comp_long.empty else set()

    weekly_h = filter_params.weekly_hours or 4.0

    for cs in target_comp_scores:
        c_id = cs.competency_id
        c_name = cs.competency_name
        
        # 난이도 레벨 자동 결정
        if filter_params.target_difficulty:
            user_level = filter_params.target_difficulty
        elif is_deepening_mode:
            user_level = "관리자·심화"
        elif cs.current_level is not None and cs.current_level < 2.5:
            user_level = "입문"
        elif cs.current_level is not None and cs.current_level >= 4.0:
            user_level = "관리자·심화"
        else:
            user_level = "실무"

        # 질의 컨텍스트 보강 (사용자가 입력한 어려운 업무 설명 및 학습 목표 반영)
        query_context = ""
        if eval_result.difficult_task_desc and eval_result.difficult_task_desc.strip():
            query_context = eval_result.difficult_task_desc.strip()
        elif eval_result.learning_goal and eval_result.learning_goal.strip():
            query_context = eval_result.learning_goal.strip()

        # 공통 추천 엔진 호출 (mode='ksa')
        top_df, n_cands, exc_cnt, pres_cnt, msg = engine.recommend(
            query=query_context,
            target_domain=eval_result.job_family,
            competency_id=c_id,
            user_level=user_level,
            platforms=None,
            price_filter=filter_params.price_filter,
            max_budget=filter_params.max_budget,
            edu_type=filter_params.edu_type,
            durations=filter_params.durations,
            difficulties=None,
            cluster_boost=0.0,
            filter_mismatch_109=True,
            top_n=top_n_per_comp,
            mode="ksa"
        )

        comp_cards: List[RecommendedCourseCard] = []

        if not top_df.empty:
            for _, row in top_df.iterrows():
                uid = row['course_uid']
                title = row['title']
                common = _common_card_fields(row, weekly_h)
                final_sc = common["raw_matching_score"]

                # 목표와의 연결 및 교육에서 확인한 내용
                curr_str = f"{cs.current_level:.1f}" if cs.current_level is not None else "미확정"
                target_str = f"{cs.target_level:.1f}"
                gap_val = abs(cs.gap) if cs.gap is not None else 0.0
                gap_str = f"{gap_val:.1f}"

                # 해당 추천의 (course_uid, competency_id) 매핑 여부 판별 (다른 역량에 매핑되어 있어도 현재 역량에 없으면 미매핑 후보로 분류)
                is_premapped_for_comp = (uid, c_id) in ksa_pair_set
                basis_for_comp = "기존 역량 연결 정보 기반" if is_premapped_for_comp else "교육내용 검색으로 찾은 추가 후보"

                if is_deepening_mode:
                    goal_connection = f"[{c_name}] 보유 역량의 심화·전문성 강화 및 최신 실무 심화 학습 ({basis_for_comp})"
                else:
                    goal_connection = f"[{c_name}] 현재 자기평가 {curr_str}점 → 목표 {target_str}점 (목표와의 차이 {gap_str}점) 보완 ({basis_for_comp})"

                content_evidence = common["content_evidence"]
                customer_reason = f"🎯 [목표 연결] {goal_connection}\n📖 [확인 내용] {content_evidence}"

                card = RecommendedCourseCard(
                    primary_competency_id=c_id,
                    primary_competency_name=c_name,
                    linked_competencies=[{
                        "competency_id": c_id,
                        "competency_name": c_name,
                        "gap": gap_val,
                        "is_premapped": is_premapped_for_comp,
                        "mapping_basis": basis_for_comp
                    }],
                    customer_recommendation_reason=customer_reason,
                    goal_connection=goal_connection,
                    mapping_basis=basis_for_comp,
                    **common
                )
                comp_cards.append(card)

                # 전체 통합 목록 중복 제거 및 연계 역량 보존 (역량별 매핑 구분 개별 보존)
                if uid not in deduped_cards_map:
                    deduped_cards_map[uid] = card
                else:
                    existing_card = deduped_cards_map[uid]
                    if not any(item["competency_id"] == c_id for item in existing_card.linked_competencies):
                        is_premapped_new = (uid, c_id) in ksa_pair_set
                        basis_new = "기존 역량 연결 정보 기반" if is_premapped_new else "교육내용 검색으로 찾은 추가 후보"
                        existing_card.linked_competencies.append({
                            "competency_id": c_id,
                            "competency_name": c_name,
                            "gap": gap_val,
                            "is_premapped": is_premapped_new,
                            "mapping_basis": basis_new
                        })

        courses_by_comp[c_id] = comp_cards

    all_deduped = list(deduped_cards_map.values())
    total_cnt = len(all_deduped)

    status_msg = f"총 {len(target_comp_scores)}개 보완 대상 역량에 대해 {total_cnt}개의 맞춤 교육과정을 추천했습니다."
    actionable_guidance = None

    if total_cnt == 0:
        status_msg = "선택하신 학습 조건(예산, 교육 형태, 교육시간)을 충족하는 추천 과정을 찾지 못했습니다."
        actionable_guidance = (
            "💡 [대안 제안]\n"
            "1. 예산 조건을 '전체'로 넓히거나 무료 전용 필터를 해제해 보세요.\n"
            "2. 온라인/오프라인 교육 형태를 '전체'로 변경해 보세요.\n"
            "3. 직무 수행 업무를 추가 선택하여 진단 범위를 확장해 보세요."
        )

    return CustomerRecommendationBundle(
        job_family=eval_result.job_family,
        is_sample=eval_result.is_sample,
        evaluated_competency_count=len(eval_result.competency_scores),
        prioritized_competency_ids=prioritized_ids,
        filter_params=filter_params,
        courses_by_competency=courses_by_comp,
        all_courses_deduped=all_deduped,
        total_recommended_count=total_cnt,
        status_message=status_msg,
        actionable_guidance=actionable_guidance
    )


# ==============================================================================
# 선택 업무(Task)별 맞춤 교육 추천 (인사 90개 업무 카탈로그)
# ==============================================================================
# 업무 추천 노출 기준은 hr_task_catalog.passes_task_gate 참고
# (의미 유사도 하한, 업무명 핵심어 일치, 분야가 다른 강좌 차단)


@dataclass
class TaskRecommendation:
    task_id: str
    task_name: str
    domain_name: str
    stage: str
    easy_description: str
    knowledge: str
    skill: str
    attitude: str
    primary_comp_name: str
    needs_review: bool
    career_view: Dict[str, Any]
    courses: List[RecommendedCourseCard]
    excluded_low_similarity: int = 0


def get_recommendations_for_tasks(
    task_ids: List[str],
    career_range: str,
    filter_params: Optional[RecommendationFilterParams] = None,
    recommender: Optional[UnifiedHybridRecommender] = None,
    top_n: int = 3,
    max_tasks: int = 5,
) -> List[TaskRecommendation]:
    """선택한 인사 세부 업무마다 하이브리드 엔진(의미 유사도 + BM25 + 난이도)으로 교육을 추천합니다."""
    from src.recommendation import hr_task_catalog

    filter_params = filter_params or RecommendationFilterParams()
    engine = recommender or get_shared_recommender()
    weekly_h = filter_params.weekly_hours or 4.0
    results: List[TaskRecommendation] = []

    for t_id in task_ids[:max_tasks]:
        task = hr_task_catalog.get_hr_task(t_id)
        if not task:
            continue
        view = hr_task_catalog.task_view_for_career(task, career_range)
        level = filter_params.target_difficulty or view["engine_level"]

        top_df, *_ = engine.recommend(
            query=hr_task_catalog.task_semantic_query(task),
            keyword_query=hr_task_catalog.task_keyword_query(task),
            keyword_stopwords=hr_task_catalog.GENERIC_TASK_TOKENS,
            anchor_query=hr_task_catalog.task_anchor_query(task),
            target_domain="인사",
            user_level=level,
            price_filter=filter_params.price_filter,
            max_budget=filter_params.max_budget,
            edu_type=filter_params.edu_type,
            durations=filter_params.durations,
            cluster_boost=0.0,
            filter_mismatch_109=True,
            top_n=top_n * 5,
            mode="general",
        )

        cards: List[RecommendedCourseCard] = []
        excluded = 0
        for _, row in top_df.iterrows():
            if not hr_task_catalog.passes_task_gate(
                float(row.get('semantic_score', 0.0)),
                float(row.get('anchor_score', 0.0)),
                row.get('field'),
            ):
                excluded += 1
                continue
            if len(cards) >= top_n:
                break
            common = _common_card_fields(row, weekly_h)
            role = view.get("role") or {}
            goal = f"[{task['task_name']}] 업무 · {view['level_name']} 단계"
            if role.get("badge"):
                goal += f" (내 연차 역할: {role['badge']})"
            cards.append(RecommendedCourseCard(
                primary_competency_id=task["primary_comp_id"],
                primary_competency_name=task["primary_comp_name"],
                linked_competencies=[{
                    "competency_id": task["primary_comp_id"],
                    "competency_name": task["primary_comp_name"],
                    "gap": 0.0,
                    "is_premapped": False,
                    "is_task": True,
                    "mapping_basis": "업무 설명과 교육내용의 의미 유사도 기반",
                }],
                customer_recommendation_reason=f"🎯 [업무 연결] {goal}\n📖 [확인 내용] {common['content_evidence']}",
                goal_connection=goal,
                mapping_basis="업무 설명과 교육내용의 의미 유사도 기반",
                **common,
            ))

        results.append(TaskRecommendation(
            task_id=task["task_id"],
            task_name=task["task_name"],
            domain_name=task["domain_name"],
            stage=task["stage"],
            easy_description=task["easy_description"],
            knowledge=task["knowledge"],
            skill=task["skill"],
            attitude=task["attitude"],
            primary_comp_name=task["primary_comp_name"],
            needs_review=task.get("needs_review", False),
            career_view=view,
            courses=cards,
            excluded_low_similarity=excluded,
        ))
    return results
