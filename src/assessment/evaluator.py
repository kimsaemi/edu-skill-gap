"""
역량 진단 평가 및 갭 분석 모듈 (evaluator.py)
- 응답 유효성 검증 및 2문항 미만 응답 시 '정보 부족(INSUFFICIENT_INFO)' 처리
- 현재 수준(자기평가 평균), 목표 수준(사용자 설정), 역량 차이(max(목표 - 현재, 0)) 계산
- 우선 보완 역량 산출 (1순위: 수행 업무 관련성, 2순위: 갭 크기, 3순위: 학습 관심도)
- 샘플 결과 데이터 제공 (실제 진단 결과와 명확히 구분 표기)
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from src.recommendation.ksa_master import KSA_COMPETENCY_MASTER
from src.assessment.questions_data import (
    ASSESSMENT_QUESTIONS,
    JOB_TASK_MAPPING,
    get_questions_for_job,
    get_tasks_for_job
)

@dataclass
class CompetencyScore:
    competency_id: str
    competency_name: str
    ksa_type: str
    valid_response_count: int
    total_question_count: int
    current_level: Optional[float]  # None if insufficient info
    target_level: float
    gap: Optional[float]            # None if insufficient info
    is_insufficient: bool
    status_label: str               # "유효 평가", "정보 부족 (추가 응답 필요)"
    is_task_related: bool           # 사용자의 실제 수행 업무와 직접 연관 여부
    is_user_interest: bool          # 사용자가 학습 관심 역량으로 선택했는지 여부
    priority_rank: Optional[int]    # 1, 2, 3 등 (우선 보완 대상일 경우)
    description: str

@dataclass
class AssessmentEvaluationResult:
    job_family: str
    is_sample: bool                 # 샘플 데이터 여부
    career_range: str
    selected_tasks: List[str]
    difficult_task_desc: str
    learning_goal: str
    competency_scores: Dict[str, CompetencyScore]
    prioritized_deficiencies: List[CompetencyScore]  # 최대 3개 부족 역량
    insufficient_competencies: List[CompetencyScore] # 정보 부족 역량
    zero_gap_competencies: List[CompetencyScore]     # 갭이 없는(0인) 역량 (심화 학습 대상)
    overall_summary: Dict[str, Any]

def calculate_competency_scores(
    job_family: str,
    responses: Dict[str, Any],
    target_levels: Optional[Dict[str, float]] = None,
    user_task_ids: Optional[List[str]] = None,
    interest_comp_ids: Optional[List[str]] = None,
    career_range: str = "3~5년차",
    difficult_task_desc: str = "",
    learning_goal: str = "업무 전문성 강화",
    is_sample: bool = False
) -> AssessmentEvaluationResult:
    """
    사용자의 설문 응답을 바탕으로 역량별 점수, 목표 갭 및 보완 우선순위를 계산합니다.
    
    규칙:
    1. 유효 응답 점수: 1, 2, 3, 4, 5 정수 응답만 점수 계산에 포함 ('NA', 'UNCERTAIN'은 제외)
    2. 정보 부족 규칙: 유효 응답 수가 2개 미만인 역량은 점수를 확정하지 않고 '정보 부족' 처리
    3. 현재 수준: 유효 응답의 산술평균 (소수점 1자리 반올림)
    4. 역량 갭: max(round(목표 수준 - 현재 수준, 1), 0.0)
    5. 우선순위:
       - 1차: 사용자 수행 업무(user_task_ids)와 매핑된 역량 여부 (True > False)
       - 2차: 갭 크기 내림차순 (큰 차이 우선)
       - 3차: 사용자 학습 관심 역량(interest_comp_ids) 포함 여부 (True > False)
    """
    questions = get_questions_for_job(job_family)
    task_list = get_tasks_for_job(job_family)
    user_task_ids = user_task_ids or []
    interest_comp_ids = interest_comp_ids or []
    target_levels = target_levels or {}

    # 수행 업무와 매핑된 역량 집합 파악
    task_related_comp_ids = set()
    for task in task_list:
        if task["task_id"] in user_task_ids:
            task_related_comp_ids.add(task["primary_comp_id"])

    # 역량별 문항 매핑 및 응답 집계
    comp_questions: Dict[str, List[Dict[str, Any]]] = {}
    for q in questions:
        c_id = q["competency_id"]
        comp_questions.setdefault(c_id, []).append(q)

    competency_scores: Dict[str, CompetencyScore] = {}

    for c_id, q_list in comp_questions.items():
        master_info = KSA_COMPETENCY_MASTER.get(c_id, {})
        comp_name = master_info.get("name", q_list[0].get("competency_name", c_id))
        ksa_type = master_info.get("ksa_type", q_list[0].get("ksa_type", "Skill"))
        desc = master_info.get("description", "")

        valid_scores = []
        for q in q_list:
            ans = responses.get(q["question_id"])
            if isinstance(ans, (int, float)) and ans in [1, 2, 3, 4, 5]:
                valid_scores.append(float(ans))

        valid_count = len(valid_scores)
        total_count = len(q_list)
        # 기본 제안 목표 수준: 4.0 (초안 기준 안내, 사용자가 변경 가능)
        target = float(target_levels.get(c_id, 4.0))

        if valid_count < 2:
            # 2문항 미만: 정보 부족 처리 (점수 확정 불가)
            competency_scores[c_id] = CompetencyScore(
                competency_id=c_id,
                competency_name=comp_name,
                ksa_type=ksa_type,
                valid_response_count=valid_count,
                total_question_count=total_count,
                current_level=None,
                target_level=target,
                gap=None,
                is_insufficient=True,
                status_label="정보 부족 (추가 응답 필요)",
                is_task_related=(c_id in task_related_comp_ids),
                is_user_interest=(c_id in interest_comp_ids),
                priority_rank=None,
                description=desc
            )
        else:
            current = round(sum(valid_scores) / valid_count, 1)
            gap = max(round(target - current, 1), 0.0)
            competency_scores[c_id] = CompetencyScore(
                competency_id=c_id,
                competency_name=comp_name,
                ksa_type=ksa_type,
                valid_response_count=valid_count,
                total_question_count=total_count,
                current_level=current,
                target_level=target,
                gap=gap,
                is_insufficient=False,
                status_label="유효 진단",
                is_task_related=(c_id in task_related_comp_ids),
                is_user_interest=(c_id in interest_comp_ids),
                priority_rank=None,
                description=desc
            )

    # 보완 우선순위 정렬 대상: 유효 진단이면서 gap > 0인 역량
    deficient_candidates = [
        cs for cs in competency_scores.values()
        if not cs.is_insufficient and cs.gap is not None and cs.gap > 0
    ]

    # 정렬 키: 1) 수행업무 매핑 (True=1, False=0), 2) gap 내림차순, 3) 관심 역량 (True=1, False=0)
    deficient_candidates.sort(
        key=lambda x: (
            1 if x.is_task_related else 0,
            x.gap or 0.0,
            1 if x.is_user_interest else 0
        ),
        reverse=True
    )

    prioritized_deficiencies: List[CompetencyScore] = []
    for rank, cs in enumerate(deficient_candidates[:3], 1):
        cs.priority_rank = rank
        prioritized_deficiencies.append(cs)

    # 정보 부족 항목들
    insufficient_items = [cs for cs in competency_scores.values() if cs.is_insufficient]

    # 갭이 없는(0.0) 역량들 (심화 대상)
    zero_gap_items = [
        cs for cs in competency_scores.values()
        if not cs.is_insufficient and cs.gap == 0.0
    ]

    summary = {
        "total_competencies": len(competency_scores),
        "valid_competencies_count": len(competency_scores) - len(insufficient_items),
        "insufficient_count": len(insufficient_items),
        "deficient_count": len(deficient_candidates),
        "zero_gap_count": len(zero_gap_items)
    }

    return AssessmentEvaluationResult(
        job_family=job_family,
        is_sample=is_sample,
        career_range=career_range,
        selected_tasks=user_task_ids,
        difficult_task_desc=difficult_task_desc,
        learning_goal=learning_goal,
        competency_scores=competency_scores,
        prioritized_deficiencies=prioritized_deficiencies,
        insufficient_competencies=insufficient_items,
        zero_gap_competencies=zero_gap_items,
        overall_summary=summary
    )

def get_sample_assessment_result(job_family: str = "인사") -> AssessmentEvaluationResult:
    """
    진단 전 결과 화면을 미리 살펴볼 수 있는 가상의 샘플 평가 결과를 반환합니다.
    (실제 사용자 결과와 구분되도록 is_sample=True 설정)
    """
    if job_family == "인사":
        sample_responses = {
            "Q_HR_01": 2,  # 채용 JD 작성 미흡
            "Q_HR_02": 2,  # 면접 질문 설계 미흡
            "Q_HR_03": 1,  # 온보딩 미경험 -> COMP_HR_01 avg: 1.7
            "Q_HR_04": 3,  # KPI 수립 혼자 수행
            "Q_HR_05": 4,  # 평가 운영 예외 대응 -> COMP_HR_02 avg: 3.5
            "Q_HR_06": 3,
            "Q_HR_07": 4,  # 근로계약서 양호
            "Q_HR_08": 4,  # 주52시간 준수
            "Q_HR_09": 3   # COMP_LABOR_01 avg: 3.7
        }
        user_tasks = ["TASK_HR_RECRUIT", "TASK_HR_LABOR_CONTRACT"]
        target_levels = {"COMP_HR_01": 4.0, "COMP_HR_02": 4.0, "COMP_LABOR_01": 4.0}
        difficult_task = "신규 개발자 직군 채용 공고 작성 및 역량 기반 면접 질문 구성이 어렵습니다."
    elif job_family == "총무":
        sample_responses = {
            "Q_GA_01": 4, "Q_GA_02": 3, "Q_GA_03": 4, "Q_GA_04": 3, # COMP_GA_01 avg: 3.5
            "Q_GA_05": 2, "Q_GA_06": 2, "Q_GA_07": 1, "Q_GA_08": 2  # COMP_GA_02 avg: 1.8
        }
        user_tasks = ["TASK_GA_PURCHASE", "TASK_GA_ASSET"]
        target_levels = {"COMP_GA_01": 4.0, "COMP_GA_02": 4.5}
        difficult_task = "자산실사 및 비품 구매 시 공급업체 계약과 단가 절감 기준 마련이 까다롭습니다."
    else:  # 경영지원
        sample_responses = {
            "Q_MS_01": 4, "Q_MS_02": 4, "Q_MS_03": 4, # COMP_SEC_01 avg: 4.0
            "Q_MS_04": 2, "Q_MS_05": 2, "Q_MS_06": 3, # COMP_MGMT_01 avg: 2.3
            "Q_MS_07": 3, "Q_MS_08": 4, "Q_MS_09": 3  # COMP_MGMT_02 avg: 3.3
        }
        user_tasks = ["TASK_MS_PROJECT", "TASK_MS_TEAM"]
        target_levels = {"COMP_SEC_01": 4.0, "COMP_MGMT_01": 4.5, "COMP_MGMT_02": 4.0}
        difficult_task = "동시에 여러 부서와 진행하는 프로젝트 일정 관리(WBS)와 리스크 조율이 힘듭니다."

    return calculate_competency_scores(
        job_family=job_family,
        responses=sample_responses,
        target_levels=target_levels,
        user_task_ids=user_tasks,
        interest_comp_ids=[],
        career_range="1~3년차",
        difficult_task_desc=difficult_task,
        learning_goal="핵심 실무 역량 보완 및 혼자서 문제 해결하기",
        is_sample=True
    )
