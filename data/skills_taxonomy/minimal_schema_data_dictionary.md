# 최소 보완 데이터 스키마 및 데이터 사전 (Data Dictionary)

본 규격은 `kimsaemi/edu-skill-gap` 대시보드의 역량 진단·교육 추천에 필요한 핵심 필드를 표준화하고,
출처 관리, 관계 분리, 사람 검토 거버넌스를 완결성 있게 보장하기 위한 최소 데이터 스키마입니다.

## 1. 설계 원칙
1. **기존 필드 의미 재사용**: 기존 데이터에 존재하는 필드는 불필요하게 이름을 변경하거나 중복 컬럼을 만들지 않고 온전히 계승합니다.
2. **관계 테이블 분리**: 교육과정 테이블에 역량 컬럼을 무리하게 욱여넣지 않고, `course_competency_mapping` 별도 관계로 관리합니다.
3. **출처 메타데이터 무결성**: 수집일(`collected_at`), 원문 수정일(`source_updated_at`), 최종 확인일(`last_verified_at`)을 절대 같은 값으로 채우지 않으며, 확인되지 않은 날짜와 검토자는 `NULL`로 보존합니다.
4. **텍스트 증거 무결성**: 원문에 실재하지 않는 텍스트 증거를 임의로 지어내지 않으며, 없을 경우 `UNAVAILABLE`로 기록합니다.

## 2. 테이블: `competency_master`
- **설명**: 8대 KSA 직무역량 마스터 및 거버넌스 메타데이터
- **기본키(PK)**: `competency_id`

| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |
| :--- | :--- | :---: | :--- | :--- |
| `competency_id` | `VARCHAR(20)` | **NO (필수)** | - | 역량 고유 식별자 (예: COMP_HR_01) |
| `competency_name` | `VARCHAR(50)` | **NO (필수)** | - | 역량 공식 명칭 |
| `job_family` | `VARCHAR(30)` | **NO (필수)** | - | 소속 직무군 (인사, 총무, 경영지원) |
| `ksa_type` | `VARCHAR(15)` | **NO (필수)** | Knowledge, Skill, Attitude | K/S/A 구분 |
| `definition` | `TEXT` | **NO (필수)** | - | 역량 공식 행동 정의문 |
| `knowledge` | `TEXT` | YES | - | 핵심 관련 지식 요소 |
| `skill` | `TEXT` | YES | - | 핵심 관련 기술/기법 요소 |
| `attitude` | `TEXT` | YES | - | 핵심 관련 태도/가치관 요소 |
| `related_tasks` | `JSON` | **NO (필수)** | - | 연계된 표준 수행 업무 태스크 ID 목록 |
| `source` | `VARCHAR(50)` | **NO (필수)** | NCS_2016v3_AND_KSA_FRAMEWORK | 기반 표준 출처 |
| `version` | `VARCHAR(10)` | **NO (필수)** | v1.1 | 마스터 버전 |
| `review_status` | `VARCHAR(20)` | **NO (필수)** | CONFIRMED_MASTER, DRAFT, ARCHIVED | 검토 상태 |

---

## 2. 테이블: `course_core`
- **설명**: 교육과정 정제 코어 메타데이터
- **기본키(PK)**: `course_uid`

| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |
| :--- | :--- | :---: | :--- | :--- |
| `course_uid` | `VARCHAR(50)` | **NO (필수)** | - | 교육과정 전역 고유 식별자 |
| `title` | `VARCHAR(255)` | **NO (필수)** | - | 교육과정 원본 제목 |
| `provider` | `VARCHAR(50)` | **NO (필수)** | - | 교육기관/플랫폼 명칭 |
| `course_intro` | `TEXT` | YES | - | 과정 소개 요약문 |
| `learning_goals` | `TEXT` | YES | - | 학습 목표 및 기대 효과 |
| `curriculum` | `TEXT` | YES | - | 커리큘럼 상세 목차 |
| `price` | `INTEGER` | YES | - | 수강료 정수형 금액 (원) - 미확인 시 NULL |
| `duration_hours` | `FLOAT` | YES | - | 총 교육시간 (시간) - 미확인 시 NULL |
| `education_type` | `VARCHAR(30)` | **NO (필수)** | 온라인, 오프라인, 혼합, 미확인 | 교육 진행 형태 |
| `url` | `VARCHAR(500)` | **NO (필수)** | - | 교육 상세 및 수강신청 링크 |

---

## 2. 테이블: `course_source_metadata`
- **설명**: 교육과정 원천 수집 및 출처 이력 메타데이터 (동일 날짜 일괄 채우기 금지)
- **기본키(PK)**: `course_uid`
- **외래키(FK)**:
  - `course_uid` ➔ `course_core(course_uid)`

| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |
| :--- | :--- | :---: | :--- | :--- |
| `course_uid` | `VARCHAR(50)` | **NO (필수)** | - | 교육과정 UID |
| `source_provider` | `VARCHAR(50)` | **NO (필수)** | - | 수집 원천 식별자 (GSEEK, HUNET, KMA, KPC 등) |
| `source_url` | `VARCHAR(500)` | **NO (필수)** | - | 수집 원천 웹 URL |
| `collected_at` | `TIMESTAMP` | **NO (필수)** | - | 최초 메타데이터 수집 일시 (ISO-8601) |
| `source_updated_at` | `TIMESTAMP` | YES | - | 원문 웹페이지 수정 일시 (크롤러 미수집 시 NULL 유지) |
| `last_verified_at` | `TIMESTAMP` | YES | - | 사람/운영자 최종 사실 확인 일자 (확인 이력 없을 시 NULL 유지) |

---

## 2. 테이블: `course_competency_mapping`
- **설명**: 교육과정-역량 연결 관계 및 텍스트 증거 (별도 매핑 테이블)
- **기본키(PK)**: `course_uid, competency_id`
- **외래키(FK)**:
  - `course_uid` ➔ `course_core(course_uid)`
  - `competency_id` ➔ `competency_master(competency_id)`

| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |
| :--- | :--- | :---: | :--- | :--- |
| `mapping_id` | `VARCHAR(60)` | **NO (필수)** | - | 매핑 고유 키 (course_uid + '_' + competency_id) |
| `course_uid` | `VARCHAR(50)` | **NO (필수)** | - | 교육과정 UID |
| `competency_id` | `VARCHAR(20)` | **NO (필수)** | - | KSA 역량 ID |
| `relation_type` | `VARCHAR(20)` | **NO (필수)** | DIRECT, PARTIAL, INSUFFICIENT, REJECTED | 연계 정합성 수준 |
| `evidence_text` | `TEXT` | YES | - | 원문에 실재하는 커리큘럼/본문 발췌 증거 (임의 생성 금지) |
| `evidence_location` | `VARCHAR(30)` | **NO (필수)** | CURRICULUM, TITLE, INTRO, GOALS, UNAVAILABLE | 증거 발견 위치 |
| `mapping_method` | `VARCHAR(30)` | **NO (필수)** | HYBRID_EMBEDDING_BM25, RULE_BASED, MANUAL_CURATION | 매핑 생성 알고리즘 |
| `mapping_confidence` | `VARCHAR(10)` | **NO (필수)** | HIGH, MEDIUM, LOW | 추정 신뢰도 |
| `review_status` | `VARCHAR(25)` | **NO (필수)** | PENDING_HUMAN_REVIEW, VERIFIED_BY_HUMAN, REJECTED_BY_HUMAN | 검토 상태 (자동생성은 PENDING_HUMAN_REVIEW) |

---

## 2. 테이블: `human_review_log`
- **설명**: 사람 전문가 검토 거버넌스 로그
- **기본키(PK)**: `review_id`
- **외래키(FK)**:
  - `mapping_id` ➔ `course_competency_mapping(mapping_id)`

| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |
| :--- | :--- | :---: | :--- | :--- |
| `review_id` | `VARCHAR(60)` | **NO (필수)** | - | 검토 일련번호 |
| `mapping_id` | `VARCHAR(60)` | **NO (필수)** | - | 대상 매핑 ID |
| `reviewer` | `VARCHAR(50)` | YES | - | 사람 검토자 실명 또는 ID (미검토 시 NULL) |
| `reviewed_at` | `TIMESTAMP` | YES | - | 검토 일시 (미검토 시 NULL) |
| `human_verdict` | `VARCHAR(20)` | YES | DIRECT, PARTIAL, INSUFFICIENT, REJECTED | 사람 최종 판정 |
| `review_note` | `TEXT` | YES | - | 사람 검토 의견 및 판정 근거 (미검토 시 NULL) |

---

## 2. 테이블: `assessment_definition`
- **설명**: 역량 자기점검 진단 문항 및 평가 규격 정의
- **기본키(PK)**: `question_id`
- **외래키(FK)**:
  - `competency_id` ➔ `competency_master(competency_id)`

| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |
| :--- | :--- | :---: | :--- | :--- |
| `question_id` | `VARCHAR(20)` | **NO (필수)** | - | 문항 고유 ID (예: Q_HR_01) |
| `job_family` | `VARCHAR(30)` | **NO (필수)** | - | 소속 직무 |
| `competency_id` | `VARCHAR(20)` | **NO (필수)** | - | 측정 대상 KSA 역량 ID |
| `question_text` | `TEXT` | **NO (필수)** | - | 행동 기반 자기점검 질문문 |
| `behavior_example` | `TEXT` | **NO (필수)** | - | 구체적 행동 지표 예시 |
| `question_version` | `VARCHAR(10)` | **NO (필수)** | v1.0 | 문항 개정 버전 |
| `scale_scoring_version` | `VARCHAR(10)` | **NO (필수)** | v1.0 | 1~5점 척도 및 정보부족(2문항 미만 제외) 계산 규격 버전 |
| `review_status` | `VARCHAR(30)` | **NO (필수)** | DRAFT_SELF_ASSESSMENT | 문항 검수 상태 |

---

