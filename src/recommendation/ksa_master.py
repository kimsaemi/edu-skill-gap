"""
NCS·KSA 직무역량 마스터 정의 및 도메인 매핑 공통 모듈
- 인사, 총무, 경영지원 3대 직무군 및 8대 KSA 직무역량 마스터 정의
- 순환 참조(circular import) 방지 및 공통 추천 엔진·UI 전반 재사용
"""

from typing import Dict, List, Optional, Any

# 직무 도메인별 10대 K-Means 군집 매핑 정의
# C0: [데이터/AI], C1: [인문/교양], C2: [실무역량], C3: [경영/기획], C4: [공공/시민]
# C5: [법정/안전], C6: [스마트워크], C7: [어학/글로벌], C8: [리더십/경영], C9: [HRD/자격]
DOMAIN_CLUSTER_MAP: Dict[str, List[int]] = {
    "인사": [2, 5, 8, 9],
    "총무": [2, 3],
    "경영지원": [2, 3, 8],
    "노무": [2, 5],
    "경영기획": [2, 3, 8],
    "사무행정": [2, 3],
    "조직문화": [2, 8]
}

# ncs_unit_code: 고용24 공식 ncsCd와 과정명으로 확인한 NCS 세분류 코드만 적는다(인사 02020201, 노무관리 02020202,
# 총무 02020101). 예전 값(예: 02020202_16v3를 '인사평가'로 표기)은 세분류 코드에 버전을 붙인 것으로 능력단위 코드가 아니었다.
# 확인하지 못한 코드는 비워 두며 화면에는 '-'로 표시된다. 대응표: data/hr/reference/hr_domain_ncs_crosswalk.csv
# 8대 KSA 직무 역량 마스터 정의
KSA_COMPETENCIES_MASTER: Dict[str, Dict[str, Any]] = {
    "COMP_HR_01": {
        "id": "COMP_HR_01",
        "name": "인력채용",
        "job_family": "인사",
        "ncs_unit_code": "02020201",
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
        "ncs_unit_code": "02020201",
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
        "ncs_unit_code": "02020202",
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
        "ncs_unit_code": "",
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
        "ncs_unit_code": "02020101",
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
        "ncs_unit_code": "",
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
        "ncs_unit_code": "",
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
        "ncs_unit_code": "",
        "ksa_type": "Knowledge",
        "definition": "조직의 경영 목표 달성을 위해 경영 환경을 분석하고 기초 재무제표와 원가를 관리하는 능력",
        "knowledge": "재무제표 분석(재무상태표, 손익계산서), 원가계산, 관리회계, 사업계획 수립",
        "skill": "예산 편성, 손익분기점(BEP) 분석, 회계 전표 검토, 경영실적 분석",
        "attitude": "수리적 정확성, 분석적 사고, 전략적 관점",
        "search_query": "경영전략 재무회계 기초 재무제표 손익계산서 예산편성 원가계산 결산 세무실무 사업계획 관리회계",
        "core_keywords": ["재무회계", "경영전략", "재무제표", "예산", "원가계산", "결산", "손익계산서", "사업계획"]
    }
}

def get_competencies_for_job(job_family: Optional[str] = None) -> List[Dict[str, Any]]:
    """선택한 직무군(인사/총무/경영지원)에 해당하는 KSA 역량 목록을 반환합니다."""
    results = []
    for _, info in KSA_COMPETENCIES_MASTER.items():
        if not job_family or job_family in ["전체", "선택 안 함 (전체)"] or info["job_family"] == job_family:
            results.append(info)
    return results

def get_competency_by_id(competency_id: str) -> Optional[Dict[str, Any]]:
    """역량 ID로 마스터 정보를 조회합니다."""
    return KSA_COMPETENCIES_MASTER.get(competency_id)

def get_job_cluster_ids(job_family: Optional[str]) -> List[int]:
    """직무명에 대응하는 10대 군집 ID 목록을 반환합니다."""
    if not job_family:
        return []
    return DOMAIN_CLUSTER_MAP.get(job_family, [])

# 호환성 별칭
KSA_COMPETENCY_MASTER = KSA_COMPETENCIES_MASTER
