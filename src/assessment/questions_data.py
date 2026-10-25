"""
역량 자기점검 진단 문항 데이터 및 직무-업무 매핑 정의 모듈
- 인사·총무·경영지원 재직자를 위한 직무별 8~12개 행동 기반 자기점검 문항
- 출처 및 검수 상태: "자기점검용 자체 구성 초안 (Draft)" 명시 (공식 인증 도구 사칭 방지)
- 1~5점 행동 척도 및 '해당 업무 아님(NA)', '판단하기 어려움(UNCERTAIN)' 제공
"""

from typing import Dict, List, Any

from src.recommendation import hr_task_catalog

# 인사 기존 6개 업무 (90개 카탈로그가 없을 때의 대체 선택지, 이전 세션 ID 호환용)
LEGACY_HR_TASKS: List[Dict[str, Any]] = [
    {"task_id": "TASK_HR_RECRUIT", "task_name": "인력 채용 및 면접 진행", "primary_comp_id": "COMP_HR_01"},
    {"task_id": "TASK_HR_ONBOARD", "task_name": "신규 입사자 온보딩 및 수습 평가", "primary_comp_id": "COMP_HR_01"},
    {"task_id": "TASK_HR_EVAL", "task_name": "KPI 수립 및 인사평가 운영", "primary_comp_id": "COMP_HR_02"},
    {"task_id": "TASK_HR_COMP", "task_name": "급여 정산 및 성과 보상 체계 관리", "primary_comp_id": "COMP_HR_02"},
    {"task_id": "TASK_HR_LABOR_CONTRACT", "task_name": "근로계약서 및 취업규칙 관리", "primary_comp_id": "COMP_LABOR_01"},
    {"task_id": "TASK_HR_LABOR_LAW", "task_name": "근로시간·4대보험 및 노동법 준수", "primary_comp_id": "COMP_LABOR_01"}
]


def _hr_task_options() -> List[Dict[str, Any]]:
    """인사 업무 선택지: 9개 분야 × 90개 세부 업무 카탈로그 (없으면 기존 6개)."""
    if not hr_task_catalog.is_available():
        return LEGACY_HR_TASKS
    return [
        {
            "task_id": t["task_id"],
            "task_name": t["task_name"],
            "primary_comp_id": t["primary_comp_id"],
            "domain_id": t["domain_id"],
            "domain_name": t["domain_name"],
            "stage": t["stage"],
        }
        for t in hr_task_catalog.get_hr_tasks()
    ]


# 직무별 표준 수행 업무 선택지 ↔ KSA 역량 ID 매핑 정의
JOB_TASK_MAPPING: Dict[str, List[Dict[str, Any]]] = {
    "인사": _hr_task_options(),
    "총무": [
        {"task_id": "TASK_GA_DOC", "task_name": "사내 공문서 및 업무 규정 관리", "primary_comp_id": "COMP_GA_01"},
        {"task_id": "TASK_GA_REPORT", "task_name": "경영진 기획보고서 및 품의서 작성", "primary_comp_id": "COMP_GA_01"},
        {"task_id": "TASK_GA_DATA", "task_name": "스마트 엑셀 데이터 가공 및 서식 운용", "primary_comp_id": "COMP_GA_01"},
        {"task_id": "TASK_GA_PURCHASE", "task_name": "사무비품 구매 계약 및 업체 관리", "primary_comp_id": "COMP_GA_02"},
        {"task_id": "TASK_GA_ASSET", "task_name": "고정자산 대장 관리 및 재물조사", "primary_comp_id": "COMP_GA_02"},
        {"task_id": "TASK_GA_FACILITY", "task_name": "사옥 시설 유지보수 및 안전 점검", "primary_comp_id": "COMP_GA_02"}
    ],
    "경영지원": [
        {"task_id": "TASK_MS_COMM", "task_name": "비즈니스 매너 및 사내외 커뮤니케이션", "primary_comp_id": "COMP_SEC_01"},
        {"task_id": "TASK_MS_SCHEDULE", "task_name": "임원 의전 및 부서 간 일정 조율", "primary_comp_id": "COMP_SEC_01"},
        {"task_id": "TASK_MS_PROJECT", "task_name": "프로젝트 WBS 및 일정 관리", "primary_comp_id": "COMP_MGMT_01"},
        {"task_id": "TASK_MS_TEAM", "task_name": "부서 업무 협업 및 리스크 관리", "primary_comp_id": "COMP_MGMT_01"},
        {"task_id": "TASK_MS_FIN_BASIC", "task_name": "재무제표 기초 이해 및 전표 검토", "primary_comp_id": "COMP_MGMT_02"},
        {"task_id": "TASK_MS_BUDGET", "task_name": "부서 예산 편성 및 손익 관리", "primary_comp_id": "COMP_MGMT_02"}
    ]
}

# 1~5점 기본 응답 척도 정의
STANDARD_RESPONSE_ANCHORS = {
    1: "1점: 아직 직접 수행해본 적이 없다",
    2: "2점: 매뉴얼이나 선배의 구체적인 도움을 받아 수행한다",
    3: "3점: 일반적인 상황에서 혼자 무리 없이 완수한다",
    4: "4점: 예외 상황이나 예상치 못한 문제에도 유연하게 대처한다",
    5: "5점: 프로세스를 개선하거나 다른 동료에게 노하우를 가르친다",
    "NA": "해당 업무 아님 (평가 제외)",
    "UNCERTAIN": "판단하기 어려움 (평가 제외)"
}

# 직무별 역량 자기점검 문항 (인사 9문항, 총무 8문항, 경영지원 9문항)
ASSESSMENT_QUESTIONS: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # 인사 (HR) 직무 문항: 9문항 (채용 3문항, 평가보상 3문항, 노무 3문항)
    # --------------------------------------------------------------------------
    {
        "question_id": "Q_HR_01",
        "job_family": "인사",
        "competency_id": "COMP_HR_01",
        "competency_name": "인력채용",
        "ksa_type": "Skill",
        "question_text": "현업 부서의 인력 요청을 분석하여 직무기술서(JD)와 채용 공고를 작성할 수 있습니까?",
        "behavior_example": "부서별 요구 자격요건을 구체적인 필요 역량으로 정리하여 채용 채널에 맞게 게시하는 행동",
        "source_reference": "NCS 능력단위 02020201(인력채용) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_02",
        "job_family": "인사",
        "competency_id": "COMP_HR_01",
        "competency_name": "인력채용",
        "ksa_type": "Skill",
        "question_text": "지원자의 이력서를 검토하고 직무역량 기반의 면접 질문과 평가 기준을 설계할 수 있습니까?",
        "behavior_example": "단순 스펙 확인이 아닌 지원자의 과거 행동 경험을 구조화된 질문으로 검증하는 행동",
        "source_reference": "NCS 능력단위 02020201(인력채용) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_03",
        "job_family": "인사",
        "competency_id": "COMP_HR_01",
        "competency_name": "인력채용",
        "ksa_type": "Skill",
        "question_text": "최종 합격자의 처우 협의 및 신규 입사자 조기 적응(온보딩) 프로그램을 기획·운영할 수 있습니까?",
        "behavior_example": "입사 첫날 안내부터 수습 기간 피드백 면담까지 조기 퇴사를 예방하는 지원 행동",
        "source_reference": "NCS 능력단위 02020201(인력채용) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_04",
        "job_family": "인사",
        "competency_id": "COMP_HR_02",
        "competency_name": "인사평가 및 보상",
        "ksa_type": "Knowledge",
        "question_text": "조직의 사업 목표와 연계된 부서 및 개인별 핵심 성과지표(KPI) 설정을 지원할 수 있습니까?",
        "behavior_example": "측정 가능하고 달성 가능한 성과 지표 가이드를 제공하고 목표 합의를 돕는 행동",
        "source_reference": "NCS 능력단위 02020202(인사평가) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_05",
        "job_family": "인사",
        "competency_id": "COMP_HR_02",
        "competency_name": "인사평가 및 보상",
        "ksa_type": "Knowledge",
        "question_text": "정기 인사평가 프로세스를 운영하고 평가 데이터 집계 및 피드백 절차를 조율할 수 있습니까?",
        "behavior_example": "평가 오류(관대화·중심화 경향)를 검토하고 객관적인 평가 결과를 도출하는 행동",
        "source_reference": "NCS 능력단위 02020202(인사평가) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_06",
        "job_family": "인사",
        "competency_id": "COMP_HR_02",
        "competency_name": "인사평가 및 보상",
        "ksa_type": "Knowledge",
        "question_text": "평가 결과에 따른 기본급 인상률, 인센티브(성과급) 차등 지급 기준을 산정하고 설명할 수 있습니까?",
        "behavior_example": "보상 규정과 재원 한도 내에서 공정하고 일관된 보상 시뮬레이션을 수행하는 행동",
        "source_reference": "NCS 능력단위 02020202(보상관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_07",
        "job_family": "인사",
        "competency_id": "COMP_LABOR_01",
        "competency_name": "근로관계 법률 준수",
        "ksa_type": "Knowledge",
        "question_text": "근로기준법 필수 기재사항을 반영하여 근로계약서를 작성하고, 취업규칙 개정 절차를 파악하고 있습니까?",
        "behavior_example": "법정 필수 조항 누락 없이 계약을 체결하고 근로자 동의 절차를 올바르게 준수하는 행동",
        "source_reference": "NCS 능력단위 02030201(노무관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_08",
        "job_family": "인사",
        "competency_id": "COMP_LABOR_01",
        "competency_name": "근로관계 법률 준수",
        "ksa_type": "Knowledge",
        "question_text": "주 52시간 근로시간 한도 관리 및 연장·야간·휴일근로 수당을 관련 법령 기준에 맞춰 산정할 수 있습니까?",
        "behavior_example": "근태 기록을 바탕으로 법 위반 위험을 사전에 점검하고 유연근무제를 적법하게 관리하는 행동",
        "source_reference": "NCS 능력단위 02030201(노무관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_HR_09",
        "job_family": "인사",
        "competency_id": "COMP_LABOR_01",
        "competency_name": "근로관계 법률 준수",
        "ksa_type": "Knowledge",
        "question_text": "해고·권고사직, 퇴직금 지급, 4대보험 취득/상실 등 고용관계 종료 시 노무 리스크를 예방할 수 있습니까?",
        "behavior_example": "부당해고 및 임금체불 분쟁을 방지하기 위해 법정 절차와 기한을 철저히 확인하는 행동",
        "source_reference": "NCS 능력단위 02030201(노무관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },

    # --------------------------------------------------------------------------
    # 총무 (General Affairs) 직무 문항: 8문항 (문서기획 4문항, 자산관리 4문항)
    # --------------------------------------------------------------------------
    {
        "question_id": "Q_GA_01",
        "job_family": "총무",
        "competency_id": "COMP_GA_01",
        "competency_name": "문서작성 및 기획",
        "ksa_type": "Skill",
        "question_text": "사내 표준 공문서, 기안서 및 업무 규정 서식을 목적과 규정에 맞게 작성하고 관리할 수 있습니까?",
        "behavior_example": "공식 문서 작성 규칙을 준수하여 명확하고 결재선이 이해하기 쉬운 기안을 올리는 행동",
        "source_reference": "NCS 능력단위 02010101(사무행정) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_02",
        "job_family": "총무",
        "competency_id": "COMP_GA_01",
        "competency_name": "문서작성 및 기획",
        "ksa_type": "Skill",
        "question_text": "경영진 또는 부서장이 검토할 수 있는 총무 기획서 및 품의서를 논리적인 구조로 작성할 수 있습니까?",
        "behavior_example": "추진 배경, 예산 소요액, 기대 효과를 체계적으로 요약하여 의사결정을 돕는 행동",
        "source_reference": "NCS 능력단위 02010101(사무행정) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_03",
        "job_family": "총무",
        "competency_id": "COMP_GA_01",
        "competency_name": "문서작성 및 기획",
        "ksa_type": "Skill",
        "question_text": "엑셀 함수(VLOOKUP, IF 등) 및 피벗테이블을 활용하여 대량의 총무 업무 데이터를 정리·분석할 수 있습니까?",
        "behavior_example": "수작업을 줄이고 자동 계산 서식을 만들어 비용이나 재고 통계를 정확히 집계하는 행동",
        "source_reference": "NCS 능력단위 02010101(사무행정) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_04",
        "job_family": "총무",
        "competency_id": "COMP_GA_01",
        "competency_name": "문서작성 및 기획",
        "ksa_type": "Skill",
        "question_text": "사내 행사, 워크숍, 정기 총회 등 전사 행사의 세부 진행 계획을 수립하고 운영할 수 있습니까?",
        "behavior_example": "장소 섭외, 타임테이블, 예산 집행, 사전 안내를 차질 없이 챙기는 행동",
        "source_reference": "NCS 능력단위 02010101(사무행정) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_05",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ksa_type": "Skill",
        "question_text": "사무용 비품의 구매 요청을 검토하고, 견적 비교 및 공급업체 계약을 합리적으로 진행할 수 있습니까?",
        "behavior_example": "복수의 견적을 비교하여 가성비를 확보하고 구매 계약 조건을 면밀히 검토하는 행동",
        "source_reference": "NCS 능력단위 02010102(비품관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_06",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ksa_type": "Skill",
        "question_text": "회사의 고정자산(PC, 사무가구 등)을 자산대장에 등록하고 정기 재물조사를 통해 실물과 일치시킬 수 있습니까?",
        "behavior_example": "자산 라벨 부착, 부서 이동 내역 갱신, 유휴 자산 및 불용 처분을 체계적으로 관리하는 행동",
        "source_reference": "NCS 능력단위 02010102(비품관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_07",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ksa_type": "Skill",
        "question_text": "사옥 및 임차 사무실의 시설 유지보수, 환경 미화, 경비/방재 협력업체의 계약 및 이행을 감독할 수 있습니까?",
        "behavior_example": "시설 결함을 신속히 조치하고 외주 서비스 용역 업체의 업무 품질을 점검하는 행동",
        "source_reference": "NCS 능력단위 02010102(시설관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_GA_08",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ksa_type": "Skill",
        "question_text": "사무실 소모품, 인쇄비, 통신비 등 총무 경비 지출 현황을 모니터링하고 절감 방안을 도출할 수 있습니까?",
        "behavior_example": "불필요한 지출 패턴을 파악하여 사용 기준을 정비하거나 단가 조정을 제안하는 행동",
        "source_reference": "NCS 능력단위 02010102(비품관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },

    # --------------------------------------------------------------------------
    # 경영지원 (Management Support) 직무 문항: 9문항 (커뮤니케이션 3, 프로젝트 3, 재무기초 3)
    # --------------------------------------------------------------------------
    {
        "question_id": "Q_MS_01",
        "job_family": "경영지원",
        "competency_id": "COMP_SEC_01",
        "competency_name": "비즈니스 매너 및 커뮤니케이션",
        "ksa_type": "Attitude",
        "question_text": "대내외 공식 비즈니스 이메일과 메신저 소통 시 예의와 명확성을 갖추어 커뮤니케이션합니까?",
        "behavior_example": "상황에 맞는 격식과 핵심 메시지를 간결하게 전달하여 불필요한 오해를 방지하는 행동",
        "source_reference": "NCS 능력단위 02040302(비즈니스매너) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_02",
        "job_family": "경영지원",
        "competency_id": "COMP_SEC_01",
        "competency_name": "비즈니스 매너 및 커뮤니케이션",
        "ksa_type": "Attitude",
        "question_text": "외부 주요 고객, 임원, 협력사 내방 시 적절한 의전과 일정 조율 매너를 발휘할 수 있습니까?",
        "behavior_example": "일정 변동 시 신속하고 정중하게 재조율하고 안내를 매끄럽게 수행하는 행동",
        "source_reference": "NCS 능력단위 02040302(비즈니스매너) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_03",
        "job_family": "경영지원",
        "competency_id": "COMP_SEC_01",
        "competency_name": "비즈니스 매너 및 커뮤니케이션",
        "ksa_type": "Attitude",
        "question_text": "부서 간 의견 대립이나 민원 발생 시 상대방의 입장을 경청하고 협력적인 대안을 제시합니까?",
        "behavior_example": "감정적 대립을 피하고 사실 관계에 집중하여 타협점을 모색하는 행동",
        "source_reference": "NCS 능력단위 02040302(비즈니스매너) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_04",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_01",
        "competency_name": "프로젝트 및 조직관리",
        "ksa_type": "Skill",
        "question_text": "담당 업무나 프로젝트의 작업분할구조도(WBS)를 작성하고 세부 마일스톤 일정을 수립할 수 있습니까?",
        "behavior_example": "전체 목표를 실행 가능한 단위 업무로 쪼개고 담당자와 마감일을 명확히 설정하는 행동",
        "source_reference": "NCS 능력단위 01010102(프로젝트관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_05",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_01",
        "competency_name": "프로젝트 및 조직관리",
        "ksa_type": "Skill",
        "question_text": "다양한 업무가 동시에 주어졌을 때 중요도와 긴급도에 따라 우선순위를 정렬하고 리스크를 선제 공유합니까?",
        "behavior_example": "일정 지연 가능성을 조기에 감지하여 유관 부서 및 관리자에게 공유하고 조율하는 행동",
        "source_reference": "NCS 능력단위 01010102(프로젝트관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_06",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_01",
        "competency_name": "프로젝트 및 조직관리",
        "ksa_type": "Skill",
        "question_text": "팀 정기 회의의 안건을 준비하고 회의록을 작성하여 결정 사항의 후속 이행을 점검할 수 있습니까?",
        "behavior_example": "회의 내용 요약과 액션 아이템(담당자/기한)을 명문화하여 실행을 담보하는 행동",
        "source_reference": "NCS 능력단위 01010102(프로젝트관리) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_07",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_02",
        "competency_name": "경영전략 및 재무회계 기초",
        "ksa_type": "Knowledge",
        "question_text": "재무제표(재무상태표, 손익계산서)의 기본 구조와 주요 계정과목(매출, 매출원가, 판관비, 당기순이익)을 이해하고 있습니까?",
        "behavior_example": "회사의 재무 현황을 파악하고 기초적인 비용 증감 요인을 파악할 수 있는 행동",
        "source_reference": "NCS 능력단위 02030101(경영기획) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_08",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_02",
        "competency_name": "경영전략 및 재무회계 기초",
        "ksa_type": "Knowledge",
        "question_text": "부서 연간 예산 계획을 수립하고, 월별 집행 실적과 예실 대비 차이를 모니터링할 수 있습니까?",
        "behavior_example": "예산 초과 위험을 사전에 인지하고 항목별 집행 근거를 투명하게 관리하는 행동",
        "source_reference": "NCS 능력단위 02030101(경영기획) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    },
    {
        "question_id": "Q_MS_09",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_02",
        "competency_name": "경영전략 및 재무회계 기초",
        "ksa_type": "Knowledge",
        "question_text": "회사의 사업계획 작성을 지원하거나 기초적인 손익분기점(BEP) 분석을 통해 수익성을 가늠할 수 있습니까?",
        "behavior_example": "고정비와 변동비를 감안하여 목표 달성에 필요한 매출/수량 규모를 추정하는 행동",
        "source_reference": "NCS 능력단위 02030101(경영기획) 참조 구성 초안",
        "review_status": "DRAFT_SELF_ASSESSMENT"
    }
]

def get_questions_for_job(job_family: str) -> List[Dict[str, Any]]:
    """선택한 직무에 해당하는 진단 문항 목록을 반환합니다."""
    return [q for q in ASSESSMENT_QUESTIONS if q["job_family"] == job_family]

def get_tasks_for_job(job_family: str) -> List[Dict[str, Any]]:
    """직무별 실제 수행 업무 선택지 목록을 반환합니다."""
    return JOB_TASK_MAPPING.get(job_family, [])

def get_task_comp_map(job_family: str) -> Dict[str, str]:
    """업무 ID → 연결 역량 ID (현재 선택지 + 인사 기존 6개 업무 ID 호환)."""
    mapping = {t["task_id"]: t["primary_comp_id"] for t in get_tasks_for_job(job_family)}
    if job_family == "인사":
        for t in LEGACY_HR_TASKS:
            mapping.setdefault(t["task_id"], t["primary_comp_id"])
    return mapping
