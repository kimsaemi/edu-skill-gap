# [STEP 4.5] EDA 완료 후 교육 추천 데이터 최종 정밀 감사 보고서

- **감사 일시**: 2026-10-10
- **감사 대상**: 확정 교육과정 295건 및 KSA 역량 매핑 295행
- **감사 목적**: STEP 5 교육 추천 알고리즘의 정확도에 치명적인 왜곡을 유발하는 구조적 결함 전수 점검 및 정제
- **최종 STEP 5 판정**: **`GO` (추천 데이터셋 분리 구축 완료)**

---

## 1. 핵심 감사 영역별 발견사항 및 조치 결과

### A. 교육-역량 매핑 타당성 감사
- **결함 발견**:
  1. **1:1 강제 매핑 왜곡**: 295개 교육과정이 무조건 1개의 KSA에만 매핑되어 있어, "채용과 노무를 아우르는 종합 과정"이나 "총무기획과 자산관리 복합 과정"의 다중 역량이 사장됨.
  2. **키워드 미검출 강제 할당 (33건)**: 제목/내용에 역량 키워드가 전혀 검출되지 않은 33개 과정이 `else` 조건문에 의해 일괄 `COMP_GA_01`(문서작성 및 기획)으로 강제 할당되었던 오류 확인.
- **개선 조치**:
  - **1:N 복합 역량 지원**: 2개 이상의 KSA를 포괄하는 **47개 복합 과정**을 발굴하여 주요 역량(`VERIFIED_CORE`)과 연계 역량(`VERIFIED_MULTI`)으로 분리.
  - **총 342개 매핑 관계 확립**: [hr_recommendation_mappings.csv](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/hr_recommendation_mappings.csv)를 생성하여 295건의 단일 강제 매핑 구조 탈피.
  - **키워드 부재 33건 재분류**: 임의 확정 대신 `REVIEW_NEEDED`로 상태를 정정하고 추천 가중치 조정.

### B. 교육 난이도 검증 및 보고서 불일치 규명
- **보고서 수치(85건)와 실제 데이터의 불일치 원인 규명**:
  - 보고서에 기재되었던 **"입문·초급 85건 (인사 51, 총무 30, 공통 4)"**은 교육시간 8시간 이하 단기 과정을 초급으로 가정한 **초기 시뮬레이션 가설치**였음.
  - 그러나 실제 CSV에 저장되었던 수치는 제목 내 특정 키워드(`초보`, `첫걸음`, `기초` 등)만 필터링한 결과 **단 12건(또는 초기 5건)**에 불과했으며, 나머지 270건(91.5%)은 **플랫폼의 공식 난이도가 없어 `중급/실무`로 fallback** 되었음.
- **개선 조치**:
  - 난이도 검증 상태를 `EXPLICIT_KEYWORD`(명시적 키워드 보유, 25건)와 `INFERRED_DEFAULT`(미확인 실무 추정, 270건)로 명확히 분리하여, STEP 5에서 임의 단정으로 인한 추천 왜곡을 방지.

### C. 비용 및 교육시간 검증
- **수강료 0원 (64건) 무결성 확인**:
  - 결측치가 아니며, 고용24 사업주 전액환급(44건), GSEEK 경기도 무료 평생학습(17건), KPC 무료 국비지원 세미나(3건)로 **실제 0원(무료/환급) 확인**.
- **수강료 이상치 (8,900,000원) 발견 및 격리**:
  - KMA 한국능률협회의 `[해외] HR Tech 2026 한국대표단` 과정으로, 해외 컨퍼런스 참가비 및 체재비가 포함된 특수 상품.
  - 일반 직무 교육 추천 풀에서 왜곡을 유발하므로 `EXCLUDED_OUTLIER`로 분류하여 추천 목록에서 격리.
- **교육시간(112건 유효, 183건 결측) 관리**:
  - 온라인 마이크로러닝 과정(휴넷 등)의 시수 미기재 상태(183건)를 명시하고, 대신 개설/수강 유효기간(`duration_days`, 202건 유효)을 보조 지표로 제공.

### D. 데이터 출처 및 추천 가능성 (3단계 티어화)
- **`TIER_1_READY` (172건)**: 핵심 역량 매핑 완비 + 수강료 확인 + 상세소개 완비 (STEP 5 우선 추천 대상)
- **`TIER_2_CONDITIONAL` (122건)**: 복합 역량 과정 또는 시수/비용 결측이 있어 메타데이터 안내가 수반되어야 하는 대상
- **`EXCLUDED_OUTLIER` (1건)**: 890만원 해외연수단 (추천 배제)

### E. 과장 수사 및 해석 교정
- **수정 전**: "통계적 유의성 완전 확보", "공급 사각지대 완전 해소"
- **수정 후**: "표본이 9건에서 295건으로 32.8배 확대되어 **초기 탐색 및 추천 프로토타입 구현에 충분한 실증 풀을 확보**하였으나, 특정 민간 플랫폼(휴넷) 및 공공 API(고용24)의 수집 비중이 65.7%에 달해 플랫폼별 편향이 존재하므로 다원화된 가중치 적용이 필수적임."

---

## 2. STEP 5에서 활용할 정제 데이터셋 명세

### 1) [hr_recommendation_candidates.csv](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/hr_recommendation_candidates.csv) (295건)
- **핵심 컬럼**:
  - `course_id`: 고유 식별자 (`PUB_...`, `SQL_...`)
  - `course_name`: 교육과정명
  - `institution_name`: 교육 기관명
  - `job_group` / `job_category`: 상위 직무군 및 세부 직무
  - `primary_competency_id` / `primary_competency_name`: 주요 핵심 역량
  - `all_competency_names`: 연계된 모든 KSA 역량 목록 (1:N 매핑)
  - `competency_count`: 연계 역량 수 (1개 vs 2개 이상)
  - `mapping_verification_tier`: 매핑 검증 등급 (`VERIFIED_CORE`, `REVIEW_NEEDED`)
  - `course_level`: 난이도 수준 (`입문/초급`, `중급/실무`, `고급/전문`)
  - `level_verification_status`: 난이도 근거 (`EXPLICIT_KEYWORD`, `INFERRED_DEFAULT`)
  - `training_hours`: 교육시간 (시수)
  - `hours_status`: 시수 상태 (`RECORDED_HOURS`, `MISSING_HOURS`)
  - `course_fee`: 수강료 (원)
  - `fee_type`: 비용 유형 (`GOV_SUBSIDIZED_FREE`, `STANDARD_PAID`, `OUTLIER_OVERSEAS_CONFERENCE`, `UNSPECIFIED`)
  - `course_url`: 상세 페이지 URL
  - `recommendation_readiness`: 추천 적합성 등급 (`TIER_1_READY`, `TIER_2_CONDITIONAL`, `EXCLUDED_OUTLIER`)
  - `unverified_items`: 미확인/주의 항목 리스트

### 2) [hr_recommendation_mappings.csv](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/hr_recommendation_mappings.csv) (342행)
- 교육과정과 7대 KSA 역량 간의 다대다(N:M) 연결 브릿지 테이블.
