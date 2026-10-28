"""
NCS·KSA 기반 직무 → 세부 과업(Task) → 역량(Competency) 데이터 연결 마스터 모듈
--------------------------------------------------------------------------------
1. 공식 NCS 체계(대분류 02. 경영·회계·사무)와 프로젝트 실무 Task 초안(Draft)을 엄격히 구분
2. 3대 직무군: 인사(HR), 총무(General Affairs), 경영지원(Management Support)
3. 18개 세부 실무 Task 및 8대 KSA 역량 매핑
4. 직급이 없는 조직도 사용할 수 있도록 숙련도(Level 1~4) 기반 선택 지원
"""

from typing import Dict, List, Optional, Any

# ncs_unit_code: 고용24 공식 ncsCd와 과정명으로 확인한 NCS 세분류 코드만 적는다(인사 02020201, 노무관리 02020202,
# 총무 02020101). 예전 값(예: 02020202_16v3를 '인사평가'로 표기)은 세분류 코드에 버전을 붙인 것으로 능력단위 코드가 아니었다.
# 확인하지 못한 코드는 비워 두며 화면에는 '-'로 표시된다. 대응표: data/hr/reference/hr_domain_ncs_crosswalk.csv
# ==============================================================================
# 1. 18대 실무 세부 과업(Task) 마스터 정의
# ==============================================================================
# 주의: 본 Task 체계는 NCS 공식 능력단위 요소를 기초로 하되, 채용 시장과 기업 실무 프로세스에 맞춰 
# 프로젝트 팀에서 체계화한 '실무 세부 업무 초안(Project Expert Draft)'입니다.
TASK_MASTER: Dict[str, Dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # 인사 (HR) 직무군
    # --------------------------------------------------------------------------
    "TASK_HR_01": {
        "task_id": "TASK_HR_01",
        "task_name": "신규 인력 채용 및 채용 전형 기획",
        "job_family": "인사",
        "competency_id": "COMP_HR_01",
        "competency_name": "인력채용",
        "ncs_unit_code": "02020201",
        "is_official_ncs": True,
        "recommended_level": "실무·중급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "채용 계획 수립, 채용 공고 작성, 서류 전형 및 면접 평가 기준을 기획·운영하는 업무",
        "search_query": "채용 프로세스 인력채용 서류전형 면접관 채용기획 인재소싱 직무기술서 선발평가",
        "ksa_summary": {
            "knowledge": "채용 프로세스, 선발 도구, 노동법상 채용 규정, 직무 분석",
            "skill": "면접 기술, 역량 평가 기준표 작성, 인재 소싱, 서류 검토",
            "attitude": "공정성, 윤리의식, 수용적 태도"
        }
    },
    "TASK_HR_02": {
        "task_id": "TASK_HR_02",
        "task_name": "신입사원 입사 온보딩 및 OJT 교육 운영",
        "job_family": "인사",
        "competency_id": "COMP_HR_01",
        "competency_name": "인력채용",
        "ncs_unit_code": "02020201",
        "is_official_ncs": True,
        "recommended_level": "입문·초급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "신규 입사자의 조기 적응을 위한 사내 오리엔테이션, 온보딩 커리큘럼 및 멘토링 프로그램 운영",
        "search_query": "온보딩 OJT 신입사원 교육 멘토링 사내교육 입사오리엔테이션 적응프로그램 인재육성",
        "ksa_summary": {
            "knowledge": "성인학습 원리, 사내 제도 및 문화, 온보딩 가이드라인",
            "skill": "사내 오리엔테이션 진행, 교육 자료 제작, 피드백 면담",
            "attitude": "공감 능력, 환대 태도, 친화력"
        }
    },
    "TASK_HR_03": {
        "task_id": "TASK_HR_03",
        "task_name": "근로계약 체결 및 4대보험 취득·상실 신고",
        "job_family": "인사",
        "competency_id": "COMP_LABOR_01",
        "competency_name": "근로관계 법률 준수",
        "ncs_unit_code": "02020202",
        "is_official_ncs": True,
        "recommended_level": "입문·초급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "표준근로계약서 작성·교부, 4대보험 자격 취득·상실 및 EDI 전산 신고 처리 업무",
        "search_query": "근로계약서 4대보험 취득상실 EDI신고 국민연금 건강보험 고용보험 산재보험 입퇴사처리",
        "ksa_summary": {
            "knowledge": "근로기준법 필수기재사항, 4대보험 관계법령, EDI 전산 시스템",
            "skill": "근로계약서 검토, 4대보험 모의계산 및 EDI 신고, 증빙 관리",
            "attitude": "정확성, 기한 준수, 꼼꼼함"
        }
    },
    "TASK_HR_04": {
        "task_id": "TASK_HR_04",
        "task_name": "월별 급여 계산, 원천징수 및 퇴직금 정산",
        "job_family": "인사",
        "competency_id": "COMP_LABOR_01",
        "competency_name": "근로관계 법률 준수",
        "ncs_unit_code": "02020202",
        "is_official_ncs": True,
        "recommended_level": "실무·중급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "통상임금·평균임금 산정, 주휴·연장·야간수당 계산, 급여명세서 발급 및 퇴직연금 정산 업무",
        "search_query": "급여계산 통상임금 평균임금 주휴수당 연차수당 퇴직연금 원천징수 급여대장 엑셀급여",
        "ksa_summary": {
            "knowledge": "임금 산정 법리, 통상임금 기준, 세법상 간이세액표, 퇴직급여보장법",
            "skill": "엑셀 급여 시트 수식 운용, 급여명세서 산출, 수당 적법성 검토",
            "attitude": "수리적 치밀성, 개인정보 보호, 기밀 유지"
        }
    },
    "TASK_HR_05": {
        "task_id": "TASK_HR_05",
        "task_name": "취업규칙 개정, 주52시간제 및 노사협의회 관리",
        "job_family": "인사",
        "competency_id": "COMP_LABOR_01",
        "competency_name": "근로관계 법률 준수",
        "ncs_unit_code": "02020202",
        "is_official_ncs": True,
        "recommended_level": "관리자·심화",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "사내 취업규칙 적법성 검토 및 개정 신고, 유연근무제 설계, 근로자의 날·노사협의회 운영",
        "search_query": "취업규칙 개정 주52시간 유연근무제 탄력근로제 노사협의회 고용노동부 노동법개정 노무리스크",
        "ksa_summary": {
            "knowledge": "최신 노동법 개정령, 취업규칙 불이익변경 법리, 노사협의회법",
            "skill": "규정 개정안 작성, 노사 협상 및 중재, 노동청 진정 대응",
            "attitude": "준법정신, 전략적 균형감, 상호 존중"
        }
    },
    "TASK_HR_06": {
        "task_id": "TASK_HR_06",
        "task_name": "정기 인사평가(KPI·다면평가) 및 성과관리 운영",
        "job_family": "인사",
        "competency_id": "COMP_HR_02",
        "competency_name": "인사평가 및 보상",
        "ncs_unit_code": "02020201",
        "is_official_ncs": True,
        "recommended_level": "실무·중급",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "조직 및 개인별 KPI 지표 설정 지원, 중간점검, 다면평가 운영 및 평가 데이터 집계",
        "search_query": "인사평가 KPI 성과관리 목표관리 MBO 다면평가 평가시트 성과분석 피드백",
        "ksa_summary": {
            "knowledge": "KPI 지표 설계론, MBO 평가 기법, 평가 오류(관대화/중심화 경향)",
            "skill": "평가 데이터 집계 및 정규화, 평가 매뉴얼 작성, 이의신청 처리",
            "attitude": "객관성, 공평성, 신뢰성"
        }
    },
    "TASK_HR_07": {
        "task_id": "TASK_HR_07",
        "task_name": "연봉 계약, 인센티브 및 직무급 보상체계 기획",
        "job_family": "인사",
        "competency_id": "COMP_HR_02",
        "competency_name": "인사평가 및 보상",
        "ncs_unit_code": "02020201",
        "is_official_ncs": True,
        "recommended_level": "관리자·심화",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "연봉 테이블 설계, 성과급/인센티브 룰 세팅, 직무급 도입 검토 및 연봉 협상 운영",
        "search_query": "보상체계 연봉테이블 인센티브 직무급제 임금체계개편 연봉협상 복리후생 성과급설계",
        "ksa_summary": {
            "knowledge": "임금체계 유형(호봉제/연봉제/직무급), 시장 임금 벤치마킹, 인건비 시뮬레이션",
            "skill": "보상 시뮬레이션 모델링, 연봉 계약서 양식 설계, 경영진 보고",
            "attitude": "전략적 사고, 공정성, 기밀 유지"
        }
    },

    # --------------------------------------------------------------------------
    # 총무 (General Affairs) 직무군
    # --------------------------------------------------------------------------
    "TASK_GA_01": {
        "task_id": "TASK_GA_01",
        "task_name": "비즈니스 공문서 및 사내 기획서·보고서 작성",
        "job_family": "총무",
        "competency_id": "COMP_GA_01",
        "competency_name": "문서작성 및 기획",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "입문·초급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "사내 품의서, 기안서, 대외 공문서 양식 작성 및 엑셀·PPT를 활용한 실무 보고서 작성",
        "search_query": "공문서 기안서 품의서 비즈니스 문서 보고서작성 기획서작성 엑셀문서 파워포인트",
        "ksa_summary": {
            "knowledge": "행정업무 규정, 기안문/품의서 서식, 공문서 맞춤법 및 표준 표기법",
            "skill": "논리적 문서 구성(MECE/기승전결), 엑셀/한글/워드 서식 편집, 요약 정리",
            "attitude": "치밀성, 명확성, 책임감"
        }
    },
    "TASK_GA_02": {
        "task_id": "TASK_GA_02",
        "task_name": "사내 소모품·비품 구매 및 조달 계약 관리",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ncs_unit_code": "02020101",
        "is_official_ncs": True,
        "recommended_level": "입문·초급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "사내 사무용품·비품 소요량 파악, 견적 비교 및 공급업체 구매 발주·정산 관리",
        "search_query": "비품구매 소모품관리 견적비교 구매발주 조달계약 단가계약 협력업체관리 대금정산",
        "ksa_summary": {
            "knowledge": "구매 프로세스, 계약서 필수 조항, 비품 적정 재고 기준",
            "skill": "견적 비교표 작성, 단가 협상, ERP 발주 입력, 정산 전표 작성",
            "attitude": "원가 절감 의식, 꼼꼼함, 공정성"
        }
    },
    "TASK_GA_03": {
        "task_id": "TASK_GA_03",
        "task_name": "고정자산 등록, 감가상각 및 정기 재물조사",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ncs_unit_code": "02020101",
        "is_official_ncs": True,
        "recommended_level": "실무·중급",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "유형자산(PC, 전산기기, 가구 등) 라벨링 및 등록, 자산 대장 관리, 연간 재물조사 실사",
        "search_query": "고정자산 재물조사 자산대장 바코드라벨 감가상각 자산실사 유형자산폐기 불용처리",
        "ksa_summary": {
            "knowledge": "고정자산 회계 기준, 내구연한 및 감가상각법, 재물조사 지침",
            "skill": "자산 바코드 실사, 불용 자산 처분 기안, 회계팀 자산 대사",
            "attitude": "정직성, 치밀성, 책임감"
        }
    },
    "TASK_GA_04": {
        "task_id": "TASK_GA_04",
        "task_name": "사옥 시설관리, 임대차 계약 및 보안·안전 관리",
        "job_family": "총무",
        "competency_id": "COMP_GA_02",
        "competency_name": "비품 및 자산관리",
        "ncs_unit_code": "02020101",
        "is_official_ncs": True,
        "recommended_level": "관리자·심화",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "사옥 임대차 계약 관리, 관리비 정산, 인테리어 공사, 소방/방재 점검 및 보안 출입 통제",
        "search_query": "사옥관리 시설관리 임대차계약 관리비정산 소방안전 빌딩관리 출입보안 인테리어공사",
        "ksa_summary": {
            "knowledge": "부동산 임대차보호법, 소방안전관리 규정, 시설 유지보수 기준",
            "skill": "임대차 계약 조건 검토, 시설 하자 보수 요청, 외주 용역 관리",
            "attitude": "안전의식, 위기대응력, 꼼꼼함"
        }
    },

    # --------------------------------------------------------------------------
    # 경영지원 (Management Support) 직무군
    # --------------------------------------------------------------------------
    "TASK_MGMT_01": {
        "task_id": "TASK_MGMT_01",
        "task_name": "내방객 의전, 임원 일정 관리 및 비즈니스 매너",
        "job_family": "경영지원",
        "competency_id": "COMP_SEC_01",
        "competency_name": "비즈니스 매너 및 커뮤니케이션",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "입문·초급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "VIP 내방객 응대, 전화 및 이메일 에티켓, 경영진 일정 조율 및 의전 서비스 수행",
        "search_query": "비즈니스매너 의전 고객응대 전화예절 이메일에티켓 일정관리 비서실무 커뮤니케이션",
        "ksa_summary": {
            "knowledge": "글로벌 비즈니스 매너, 의전 서열 규정, 경어법 및 언어 예절",
            "skill": "일정 조율 및 리마인드, 상황별 응대 멘트 구사, 복장/자세 매너",
            "attitude": "배려심, 품격 있는 태도, 신속성"
        }
    },
    "TASK_MGMT_02": {
        "task_id": "TASK_MGMT_02",
        "task_name": "대내외 커뮤니케이션, 갈등 조정 및 사내 소통 촉진",
        "job_family": "경영지원",
        "competency_id": "COMP_SEC_01",
        "competency_name": "비즈니스 매너 및 커뮤니케이션",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "실무·중급",
        "suitable_levels": ["입문·초급", "실무·중급", "관리자·심화"],
        "description": "부서 간 협업 요청, 업무 갈등 중재, 전사 공지 작성 및 경청 기반 커뮤니케이션",
        "search_query": "조직소통 갈등관리 협업스킬 커뮤니케이션 대화법 경청 피드백 사내공지 협상스킬",
        "ksa_summary": {
            "knowledge": "갈등 관리 모델, 비폭력 대화(NVC) 기법, 사내 커뮤니케이션 채널 특성",
            "skill": "조정 및 중재 대화, 명확한 공문서 작성, 설득 스피치",
            "attitude": "중립성, 열린 자세, 공감적 경청"
        }
    },
    "TASK_MGMT_03": {
        "task_id": "TASK_MGMT_03",
        "task_name": "부서 프로젝트 일정(WBS) 관리 및 협업 조율",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_01",
        "competency_name": "프로젝트 및 조직관리",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "실무·중급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "프로젝트 일정표(WBS/칸반) 수립, 마일스톤 점검, 업무 진척도 트래킹 및 리스크 보고",
        "search_query": "프로젝트관리 WBS 일정관리 칸반 애자일 협업툴 노션 먼데이 마일스톤 진척관리",
        "ksa_summary": {
            "knowledge": "WBS 작성 원리, 칸반/애자일 프레임워크, 마일스톤 관리 기법",
            "skill": "간트차트 작성, 협업 툴(Notion/Jira) 운용, 진척도 회의 주관",
            "attitude": "주도성, 일정 준수, 투명한 공유"
        }
    },
    "TASK_MGMT_04": {
        "task_id": "TASK_MGMT_04",
        "task_name": "팀 빌딩, 조직문화 활성화 및 리더십 코칭",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_01",
        "competency_name": "프로젝트 및 조직관리",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "관리자·심화",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "팀 내 워크숍 기획, 동기부여 및 원온원(1 on 1) 면담을 통한 조직 몰입도 제고",
        "search_query": "조직문화 팀빌딩 리더십 코칭 1on1 면담 동기부여 팀워크 사내워크숍 리더십스킬",
        "ksa_summary": {
            "knowledge": "조직 행동론, 코칭 프레임워크(GROW 모델), 동기부여 이론",
            "skill": "1on1 질문 및 경청, 팀 워크숍 퍼실리테이션, 팀원 피드백",
            "attitude": "신뢰 형성, 포용성, 긍정적 영향력"
        }
    },
    "TASK_MGMT_05": {
        "task_id": "TASK_MGMT_05",
        "task_name": "기초 회계 전표 검토 및 지출결의·증빙 관리",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_02",
        "competency_name": "경영전략 및 재무회계 기초",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "입문·초급",
        "suitable_levels": ["입문·초급", "실무·중급"],
        "description": "법인카드 전표 대사, 지출결의서 적법성 검토, 세금계산서 확인 및 부가세 기본 정산",
        "search_query": "지출결의서 세금계산서 법인카드정산 회계전표 부가세 기초회계 증빙관리 적격증빙",
        "ksa_summary": {
            "knowledge": "적격증빙 규정(세금계산서/신용카드), 계정과목 기본 개념, 부가가치세 기본",
            "skill": "ERP 전표 입력, 증빙 대사 및 결격 사유 검토, 엑셀 정산",
            "attitude": "정확성, 준법의식, 꼼꼼함"
        }
    },
    "TASK_MGMT_06": {
        "task_id": "TASK_MGMT_06",
        "task_name": "연간 예산 편성, 손익분기점(BEP) 분석 및 경영실적 보고",
        "job_family": "경영지원",
        "competency_id": "COMP_MGMT_02",
        "competency_name": "경영전략 및 재무회계 기초",
        "ncs_unit_code": "",
        "is_official_ncs": True,
        "recommended_level": "관리자·심화",
        "suitable_levels": ["실무·중급", "관리자·심화"],
        "description": "사업계획에 따른 연간 예산 편성, 원가/비용 통제, 손익분기점 분석 및 경영진 실적 리포팅",
        "search_query": "예산편성 손익분기점 BEP 원가관리 재무제표분석 손익계산서 사업계획 경영실적보고",
        "ksa_summary": {
            "knowledge": "재무제표(재무상태표, 손익계산서), CVP(원가-조업도-이익) 분석, 관리회계",
            "skill": "손익분기점 시뮬레이션, 예산 실적 대비 분석표 작성, 재무 대시보드 구성",
            "attitude": "분석적 사고, 전략적 판단, 수리적 엄밀성"
        }
    }
}

# ==============================================================================
# 2. 직무별 과업 조회 헬퍼 함수
# ==============================================================================
def get_tasks_for_job(job_family: str) -> List[Dict[str, Any]]:
    """선택한 직무(인사/총무/경영지원)에 해당하는 Task 목록을 반환합니다."""
    return [
        task for task in TASK_MASTER.values()
        if task["job_family"] == job_family
    ]

def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
    """Task ID로 세부 정보를 반환합니다."""
    return TASK_MASTER.get(task_id)

def get_ksa_for_task(task_id: str) -> Optional[Dict[str, Any]]:
    """선택한 Task의 연결 KSA 및 세부 명세를 반환합니다."""
    task = get_task_by_id(task_id)
    if not task:
        return None
    return {
        "competency_id": task["competency_id"],
        "competency_name": task["competency_name"],
        "ncs_unit_code": task["ncs_unit_code"],
        "is_official_ncs": task["is_official_ncs"],
        "ksa_summary": task["ksa_summary"]
    }
