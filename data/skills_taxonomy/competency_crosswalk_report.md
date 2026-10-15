# KSA 직무역량 ↔ ESCO / O*NET Crosswalk 매핑 보고서

본 문서는 `kimsaemi/edu-skill-gap`의 8대 KSA 직무역량과 글로벌 표준 직무 체계(유럽 ESCO v1.2.0, 미국 O*NET 29.1) 간의
소규모 참고 체계(총 24개 개념) 매핑 결과 및 연계 원칙을 정리한 공식 크로스워크 문서입니다.

## 1. 수집 및 매핑 핵심 원칙
1. **소규모 엄선 (24개 개념)**: 기존 추천 시스템을 일괄 치환하지 않고, 8대 역량과 가장 밀접한 공통 직무 스킬·활동 24개만 선별 수집했습니다 (ESCO 12개, O*NET 12개).
2. **국내 노동법 고유성 보호**: `COMP_LABOR_01`(근로관계 법률 준수)은 대한민국 근로기준법 및 4대보험 법정 규제이므로 외국 체계로 대체하지 않고 `related`(참고)로만 연결했습니다.
3. **정밀 매핑 관계 구분**: 단순 명칭 유사성만으로 `exact`를 부여하지 않고, `exact`(완전 일치 2건), `broader`(상위 포괄 8건), `narrower`(세부 실행 10건), `related`(연관 4건)로 엄격히 구분했습니다.
4. **공식 출처 및 라이선스 분리 준수**:
   - **ESCO v1.2.0**: 유럽연합 위원회 공식 REST API 조회, CC BY 4.0 라이선스 적용.
   - **O*NET 29.1**: 미국 노동부 고용훈련청(USDOL/ETA) 공식 Content Model 및 직업 정보망, CC BY 4.0 라이선스 적용 (API 소프트웨어 라이선스와 데이터 이용조건 구분 기록).
5. **한국어 번역 명시**: 모든 한국어 번역은 공식 번역이 아니므로 `초안 (DRAFT)`으로 명기했습니다.

## 2. Crosswalk 매핑 상세표 (24개 개념)

| 역량 ID | 외부 체계 | 외부 식별자 | 원어 명칭 | 한국어 번역 (초안) | 매핑 관계 | 매핑 근거 |
| :--- | :---: | :--- | :--- | :--- | :---: | :--- |
| `COMP_HR_01` | **ESCO** | `http://data.europa.eu/esco/skill/65...` | recruit personnel | 인력 채용 및 선발 (초안) | `narrower` | 인력채용 역량의 핵심 실행 활동인 인재 모집 및 선발에 직접 대응하나, 직무기술서 작성 및 온보딩 기획을 포괄하는 프로젝트 KSA보다 세부적인 실행 스킬임. |
| `COMP_HR_01` | **ESCO** | `http://data.europa.eu/esco/skill/4d...` | perform interviews | 면접 평가 진행 (초안) | `narrower` | 채용 프로세스 중 면접 계획 수립 및 구조화된 인터뷰 실행 기술에 대응. |
| `COMP_HR_02` | **ESCO** | `http://data.europa.eu/esco/skill/8a...` | evaluate employees work | 직원 업무 및 성과 평가 (초안) | `narrower` | 인사평가 및 보상 역량 중 성과 및 역량 평가 실행 영역에 직접 대응. |
| `COMP_HR_02` | **ESCO** | `http://data.europa.eu/esco/skill/67...` | determine salaries | 급여 및 임금 산정 (초안) | `narrower` | 성과 보상 체계 및 연봉/급여 구조 운영 영역에 대응. |
| `COMP_LABOR_01` | **ESCO** | `http://data.europa.eu/esco/skill/08...` | labour legislation | 노동 법률 및 고용 규제 (초안) | `related` | 노동 법률 전반을 다루나, 대한민국 근로기준법·취업규칙·주52시간제·4대보험은 국가 고유 컴플라이언스이므로 해외 체계로 대체 불가하며 개념적 참고(related)로만 연결. |
| `COMP_GA_01` | **ESCO** | `http://data.europa.eu/esco/skill/6a...` | office administration | 사무 행정 및 일반 지원 (초안) | `broader` | 사내 공문서 관리, 업무 규정, 일반 사무 지원을 포괄하는 상위 개념. |
| `COMP_GA_01` | **ESCO** | `http://data.europa.eu/esco/skill/ea...` | develop business plans | 사업 계획 및 기획서 수립 (초안) | `narrower` | 기획서 프레임워크 작성 및 기획 프로세스 실행에 대응. |
| `COMP_GA_02` | **ESCO** | `http://data.europa.eu/esco/skill/31...` | maintain inventory of office supplies | 사무 비품 재고 및 조달 관리 (초안) | `narrower` | 사무 비품 관리, 구매 조달 및 소모품 수급 관리에 직접 대응. |
| `COMP_GA_02` | **ESCO** | `http://data.europa.eu/esco/skill/ed...` | manage brand assets | 조직 자산 유지 및 관리 (초안) | `broader` | 사내 동산/부동산 및 유무형 자산의 등록, 실사, 감가상각 관리를 포괄. |
| `COMP_SEC_01` | **ESCO** | `http://data.europa.eu/esco/skill/fe...` | communication principles | 비즈니스 커뮤니케이션 원칙 (초안) | `broader` | 상황별 대화 기술, 비즈니스 에티켓, 의전 소통의 기본 원칙을 포괄. |
| `COMP_MGMT_01` | **ESCO** | `http://data.europa.eu/esco/skill/22...` | manage project information | 프로젝트 정보 및 일정 관리 (초안) | `narrower` | WBS 작성, 일정 관리, 백로그 관리 등 프로젝트 세부 실행 스킬에 대응. |
| `COMP_MGMT_02` | **ESCO** | `http://data.europa.eu/esco/skill/52...` | financial management | 재무 관리 및 원가 분석 (초안) | `broader` | 재무제표 분석, 원가계산, 관리회계 기초 지식을 광범위하게 포괄. |
| `COMP_HR_01` | **O*NET** | `4.A.4.b.5...` | Staffing Organizational Units | 조직 인력 충원 및 채용 (초안) | `broader` | O*NET 세부 업무활동(GWA)으로서 채용, 인터뷰, 선발, 고용 전반을 포괄하여 프로젝트 인력채용 KSA와 개념적으로 일치. |
| `COMP_HR_01` | **O*NET** | `2.B.5.c...` | Management of Personnel Resources | 인적 자원 관리 및 배치 (초안) | `related` | 적재적소 인력 배치 및 인재 식별 스킬로서 채용 역량의 인적 자원 배분 관점과 연계. |
| `COMP_HR_02` | **O*NET** | `2.C.1.e...` | Personnel and Human Resources | 인사 및 인적자원 관리 지식 (초안) | `broader` | O*NET 지식 범주로서 평가 및 보상 제도를 포함한 인사 전반의 체계적 이론을 포괄. |
| `COMP_HR_02` | **O*NET** | `4.A.2.a.4...` | Analyzing Data or Information | 데이터 및 정보 분석 (초안) | `related` | 다면평가 점수 집계, KPI 성과 데이터 분석, 급여 시뮬레이션 업무에 필요한 분석적 기초 활동. |
| `COMP_LABOR_01` | **O*NET** | `4.A.4.b.4...` | Resolving Conflicts and Negotiating with Others | 갈등 해결 및 노사 협상 (초안) | `related` | 노무 관리의 핵심인 고충 처리 및 분쟁 조정 활동과 연계되나, 대한민국 근로기준법/취업규칙 체계와 동일시할 수 없음. |
| `COMP_GA_01` | **O*NET** | `2.A.1.c...` | Writing | 서면 작성 및 커뮤니케이션 (초안) | `broader` | 문서작성 및 기획 역량의 기초가 되는 기본 작성 스킬. |
| `COMP_GA_01` | **O*NET** | `2.C.1.b...` | Clerical | 사무 행정 및 양식 관리 (초안) | `related` | 공문서 양식 관리, 사내 업무 규정 서식 설계, 엑셀/워드 서식 운용 지식과 직접 부합. |
| `COMP_GA_02` | **O*NET** | `2.B.5.b...` | Management of Material Resources | 물품·비품 및 물적 자원 관리 (초안) | `exact` | 사내 비품, 장비, 시설의 조달 및 적정 사용·유지 관리 정의와 완전히 일치. |
| `COMP_SEC_01` | **O*NET** | `4.A.4.a.1...` | Communicating with Supervisors, Peers, or Subordinates | 조직 내 상하 및 동료 소통 (초안) | `broader` | 전화응대, 이메일 에티켓, 일정 조율 등 비즈니스 커뮤니케이션 전반을 포괄. |
| `COMP_SEC_01` | **O*NET** | `2.B.1.b...` | Coordination | 업무 조정 및 조율 (초안) | `related` | 임원 의전 및 부서 간 일정 조율 행동 지표에 대응. |
| `COMP_MGMT_01` | **O*NET** | `2.C.1.a...` | Administration and Management | 경영 관리 및 조직 기획 (초안) | `broader` | 프로젝트 목표 수립, 리소스 배분, 팀 리더십을 포괄하는 경영 지식. |
| `COMP_MGMT_02` | **O*NET** | `2.B.5.a...` | Management of Financial Resources | 재무 자원 및 예산 지출 관리 (초안) | `exact` | 부서 예산 편성, 원가 관리, 지출 결산 업무 정의와 직접 일치. |
