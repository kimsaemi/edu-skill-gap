# 기존 데이터셋 및 파이프라인 필드 감사 보고서

본 보고서는 `kimsaemi/edu-skill-gap` 저장소의 실데이터, KSA 마스터, 설문 정의, 매핑 테이블, 추천 엔진, 화면에 걸친 모든 필드의 결측률·자료형·사용 위치 및 보완 방안을 정밀 감사한 결과입니다.

## 1. 감사 개요 및 요약 통계
- **분석 코퍼스 건수**: 교육과정 8,645건 (`education_courses_search_cleaned.parquet`)
- **역량 매핑 건수**: 8,291건 (`course_competency_long.parquet`, 4,966개 강좌와 8대 KSA 역량 연계)
- **외래키(UID) 참조 무결성**: 100% 무결 (누락된 코스 UID를 참조하는 매핑 0건)
- **역량 ID 무결성**: 100% 무결 (마스터 정의 외 미정의 역량 ID 0건)

## 2. 상태별 필드 분류 요약
- **이미 충족 (SATISFIED)**: `course_uid`, `title`, `provider`, `url`, `curriculum`, `clean_search_text` 등 추천 코어 필드
- **값 부족 (INSUFFICIENT_VALUES)**: `duration_hours` (48.3% 결측), `price` (23.6% 결측), `start_date/end_date` (51.8% 공란), `ksa_knowledge/attitude` (86~87% 공란)
- **의미 불명확 (AMBIGUOUS_SEMANTICS)**: `ncs_code` (공식 NCS 코드와 자체 COMP_* ID 혼용), `category_depth1~3` (플랫폼별 분류 체계 상이)
- **컬럼 없음 (MISSING_COLUMN)**: `source_url`, `source_updated_at`, `last_verified_at`, `relation_type`, `evidence_location`, `reviewer`, `reviewed_at`, `review_note` 등 거버넌스 메타데이터

## 3. 전체 필드 감사 상세표

| 데이터셋 | 필드명 | 자료형 | 결측률(%) | 공란률(%) | 분류 상태 | 사용 범위 | 의미 및 사용처 | 보완 대책 |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| education_courses_search_cleaned.parquet | `course_uid` | string | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 교육과정 고유 식별자 (DB/엔진/화면 전반 UID 매핑) | 유지 |
| education_courses_search_cleaned.parquet | `provider` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 교육기관/운영플랫폼명 (휴넷, KMA, KPC 등) (화면 노출 및 검색 가중치) | 유지 |
| education_courses_search_cleaned.parquet | `source_course_id` | string | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 원천 플랫폼 내 강좌 ID (크롤링 내부 추적용) | 유지 |
| education_courses_search_cleaned.parquet | `title` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 교육과정 원본 제목 (화면 노출, 검색 토큰화, 비교함) | 유지 |
| education_courses_search_cleaned.parquet | `category_depth1` | str | 0.0% | 0.76% | **의미 불명확** | EXPERIMENTAL_OFFLINE | 플랫폼별 1차 대분류 카테고리 (초기 필터링 참고용 (표준화 부재)) | 10대 군집(cluster_id) 및 KSA 마스터 체계로 표준화 |
| education_courses_search_cleaned.parquet | `category_depth2` | str | 0.0% | 38.16% | **값 부족** | EXPERIMENTAL_OFFLINE | 플랫폼별 2차 중분류 카테고리 (초기 필터링 참고용) | 결측율이 극심하여 주 필터로 사용하지 않고 검색 전문 코퍼스로 대체 |
| education_courses_search_cleaned.parquet | `category_depth3` | str | 0.0% | 54.74% | **값 부족** | EXPERIMENTAL_OFFLINE | 플랫폼별 3차 소분류 카테고리 (초기 필터링 참고용) | 결측율이 극심하여 주 필터로 사용하지 않고 검색 전문 코퍼스로 대체 |
| education_courses_search_cleaned.parquet | `course_intro` | str | 0.0% | 29.01% | **값 부족** | PRODUCTION_ACTIVE | 과정 소개 요약문 (검색 텍스트 합성 및 카드 상세) | 제목 기반 폴백 근거 제공 및 text_richness 경고 부여 |
| education_courses_search_cleaned.parquet | `target_audience` | str | 0.0% | 19.92% | **값 부족** | PRODUCTION_ACTIVE | 수강 대상 (권장 직급, 대상자) (추천 적합도 참고용) | 유지 |
| education_courses_search_cleaned.parquet | `learning_goals` | str | 0.0% | 23.52% | **값 부족** | PRODUCTION_ACTIVE | 학습 목표 (기대 효과) (검색 텍스트 합성 및 근거 추출) | 제목 기반 폴백 근거 제공 및 text_richness 경고 부여 |
| education_courses_search_cleaned.parquet | `curriculum` | str | 0.0% | 15.84% | **이미 충족** | PRODUCTION_ACTIVE | 커리큘럼 목차 (교시/차시별 내용) (커리큘럼 근거 발췌 및 검색 합성) | 유지 |
| education_courses_search_cleaned.parquet | `education_type` | str | 0.0% | 4.16% | **이미 충족** | PRODUCTION_ACTIVE | 교육 형태 (온라인, 오프라인, 혼합 등) (고객 필터 및 배지 노출) | 유지 |
| education_courses_search_cleaned.parquet | `difficulty` | str | 0.0% | 38.52% | **값 부족** | PRODUCTION_ACTIVE | 과정 난이도 (초급, 중급, 고급 등) (학습 수준 매칭) | 유지 |
| education_courses_search_cleaned.parquet | `duration_hours` | float64 | 48.33% | 0.0% | **값 부족** | PRODUCTION_ACTIVE | 총 학습 시간 (시) (학습 페이스 계산 및 카드 노출) | 결측 시 시간 표기 생략 및 미확인 안내 |
| education_courses_search_cleaned.parquet | `duration_days` | Int64 | 55.07% | 0.0% | **값 부족** | EXPERIMENTAL_OFFLINE | 수강 기간 (일) (학습 기간 참고용) | 결측 시 시간 표기 생략 및 미확인 안내 |
| education_courses_search_cleaned.parquet | `price` | Int64 | 23.59% | 0.0% | **값 부족** | PRODUCTION_ACTIVE | 수강료 원문 숫자 (원) (가격 필터 및 무료/유료 판정) | 결측 시 '가격 정보 미확인(UNCONFIRMED)'으로 처리하며 0원 무료로 오인 금지 |
| education_courses_search_cleaned.parquet | `price_type` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 가격 유형 문자열 (무료/유료 보조 판정) | 유지 |
| education_courses_search_cleaned.parquet | `start_date` | str | 0.0% | 51.75% | **값 부족** | PRODUCTION_ACTIVE | 개강일자 (YYYY-MM-DD) (일정 안내 (있을 때만 노출)) | 공란 시 '일정·모집 여부는 교육기관에서 확인'으로 폴백 처리 |
| education_courses_search_cleaned.parquet | `end_date` | str | 0.0% | 51.75% | **값 부족** | PRODUCTION_ACTIVE | 종강일자 (YYYY-MM-DD) (일정 안내) | 유지 |
| education_courses_search_cleaned.parquet | `url` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 교육 상세/신청 웹페이지 URL (교육 바로가기 링크) | 유지 |
| education_courses_search_cleaned.parquet | `collected_at` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 최초 메타데이터 수집일시 (데이터 신선도 추적) | 유지 |
| education_courses_search_cleaned.parquet | `detail_crawled_at` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 상세 본문 크롤링 일시 (본문 수집 신선도 추적) | 유지 |
| education_courses_search_cleaned.parquet | `source_provider` | str | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 수집 원천 코드 (원천 식별용) | 유지 |
| education_courses_search_cleaned.parquet | `source_file` | str | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 수집 원천 DB 파일명 (내부 감사용) | 유지 |
| education_courses_search_cleaned.parquet | `ncs_code` | string | 0.0% | 40.94% | **의미 불명확** | PRODUCTION_ACTIVE | 매핑된 KSA 역량 ID 또는 NCS 코드 (초기 KSA 분류) | 공식 NCS 분류코드와 프로젝트 자체 COMP_* ID가 혼용되어 있으므로 ksa_master.py를 진실공급원으로 단일화 |
| education_courses_search_cleaned.parquet | `ksa_knowledge` | str | 0.0% | 86.21% | **값 부족** | LEGACY_UNUSED | KSA 지식 태그 텍스트 (초기 분류 (86% 결측)) | 결측율이 극심하여 주 필터로 사용하지 않고 검색 전문 코퍼스로 대체 |
| education_courses_search_cleaned.parquet | `ksa_skill` | str | 0.0% | 47.32% | **값 부족** | LEGACY_UNUSED | KSA 기술 태그 텍스트 (초기 분류 (47% 결측)) | 결측율이 극심하여 주 필터로 사용하지 않고 검색 전문 코퍼스로 대체 |
| education_courses_search_cleaned.parquet | `ksa_attitude` | str | 0.0% | 87.73% | **값 부족** | LEGACY_UNUSED | KSA 태도 태그 텍스트 (초기 분류 (88% 결측)) | 결측율이 극심하여 주 필터로 사용하지 않고 검색 전문 코퍼스로 대체 |
| education_courses_search_cleaned.parquet | `mapping_confidence` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 역량 매핑 신뢰도 (HIGH/MED/LOW) (추천 가중치 부여) | 유지 |
| education_courses_search_cleaned.parquet | `mapping_status` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 매핑 검수 상태 (VERIFIED 등) (신뢰도 필터링) | 유지 |
| education_courses_search_cleaned.parquet | `clean_search_text` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 정제된 검색 코퍼스 전문 (TF-IDF / BM25 / Embedding 입력) | 유지 |
| education_courses_search_cleaned.parquet | `clean_intro` | str | 0.0% | 30.16% | **이미 충족** | PRODUCTION_ACTIVE | 정제된 소개문 (검색 및 근거 생성) | 유지 |
| education_courses_search_cleaned.parquet | `clean_goals` | str | 0.0% | 42.24% | **값 부족** | PRODUCTION_ACTIVE | 정제된 학습목표 (검색 및 근거 생성) | 제목 기반 폴백 근거 제공 및 text_richness 경고 부여 |
| education_courses_search_cleaned.parquet | `clean_curriculum` | str | 0.0% | 20.96% | **이미 충족** | PRODUCTION_ACTIVE | 정제된 커리큘럼 (커리큘럼 근거 발췌) | 유지 |
| education_courses_search_cleaned.parquet | `raw_text_len` | int64 | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 전처리 전 원문 글자 수 (텍스트 품질 진단) | 유지 |
| education_courses_search_cleaned.parquet | `clean_text_len` | int64 | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 전처리 후 글자 수 (텍스트 품질 진단) | 유지 |
| education_courses_search_cleaned.parquet | `chars_reduced` | int64 | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 정제로 감소된 글자 수 (전처리 감사) | 유지 |
| education_courses_search_cleaned.parquet | `text_quality_status` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 텍스트 풍부도 (RICH, MODERATE 등) (정보 부족 경고 생성) | 유지 |
| education_courses_search_cleaned.parquet | `is_base64_cleaned` | bool | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | base64 노이즈 제거 여부 (전처리 감사) | 유지 |
| education_courses_search_cleaned.parquet | `cleaning_actions` | str | 0.0% | 0.0% | **이미 충족** | EXPERIMENTAL_OFFLINE | 적용된 정제 액션 리스트 (전처리 감사) | 유지 |
| education_courses_search_cleaned.parquet | `ncs_code_type` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 코드 체계 구분 (PROJECT_CUSTOM_KSA_ID) (코드 해석 기준) | 유지 |
| education_courses_search_cleaned.parquet | `ksa_candidates` | str | 0.0% | 42.56% | **값 부족** | EXPERIMENTAL_OFFLINE | 후보 KSA 목록 문자열 (매핑 후보군 추적) | 결측율이 극심하여 주 필터로 사용하지 않고 검색 전문 코퍼스로 대체 |
| course_competency_long.parquet | `course_uid` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 교육과정 UID (외래키 (df_courses 조인)) | 유지 (외래키 무결성 100%) |
| course_competency_long.parquet | `course_title` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 강좌명 스냅샷 (매핑 테이블 내 가독성용) | 유지 |
| course_competency_long.parquet | `provider` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 교육기관명 스냅샷 (매핑 테이블 내 가독성용) | 유지 |
| course_competency_long.parquet | `target_job_family` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 대상 직무군 (인사/총무/경영지원) (직무별 추천 가중치) | 유지 |
| course_competency_long.parquet | `competency_id` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | KSA 역량 ID (COMP_*) (진단 결과 갭과 교육 추천 연결) | 유지 (8대 KSA 일치) |
| course_competency_long.parquet | `competency_name` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 역량명 스냅샷 (가독성용) | 유지 |
| course_competency_long.parquet | `ksa_type` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | K/S/A 구분 (Knowledge/Skill/Attitude) (역량 유형 가이드) | 유지 |
| course_competency_long.parquet | `mapping_confidence` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 매핑 신뢰도 (HIGH/MED/LOW) (매핑 품질 필터링) | 유지 |
| course_competency_long.parquet | `matched_evidence` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 매핑 근거 키워드/문장 (추천 사유 생성 시 활용) | 정제된 문장 발췌로 고도화 |
| course_competency_long.parquet | `mapping_status` | str | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 매핑 상태 (VERIFIED/REVIEW_NEEDED) (신뢰할 수 있는 매핑 우선 노출) | 유지 |
| course_competency_long.parquet | `category_depth1` | str | 0.0% | 0.24% | **의미 불명확** | EXPERIMENTAL_OFFLINE | 1차 카테고리 스냅샷 (참고용) | 단일화 |
| course_competency_long.parquet | `category_depth2` | str | 0.0% | 71.55% | **값 부족** | EXPERIMENTAL_OFFLINE | 2차 카테고리 스냅샷 (참고용) | 단일화 |
| course_competency_long.parquet | `price` | Int64 | 17.01% | 0.0% | **값 부족** | EXPERIMENTAL_OFFLINE | 가격 스냅샷 (참고용) | df_courses 조인으로 일원화 |
| course_competency_long.parquet | `duration_hours` | float64 | 24.74% | 0.0% | **값 부족** | EXPERIMENTAL_OFFLINE | 학습시간 스냅샷 (참고용) | df_courses 조인으로 일원화 |
| course_competency_long.parquet | `is_verified` | bool | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 검수 검증 여부 (True/False) (추천 신뢰도 가중치 1.0 vs 0.4) | 유지 |
| course_competency_long.parquet | `confidence_weight` | float64 | 0.0% | 0.0% | **이미 충족** | PRODUCTION_ACTIVE | 신뢰도 가중치 (1.0 or 0.4) (하이브리드 스코어 보정) | 유지 |
| [신규 최소 스키마 필요] courses | `source_url` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 원천 크롤링 출처 URL (출처 신뢰성 검증) | url과 분리하여 원천 수집 주소 명시 |
| [신규 최소 스키마 필요] courses | `source_updated_at` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 원천 웹페이지 최종 수정일시 (데이터 신선도 판정) | 크롤러 미수집 상태이므로 미확인(NULL) 유지 (임의 조작 금지) |
| [신규 최소 스키마 필요] courses | `last_verified_at` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 운영자 최종 사실 확인일자 (추천 카드 일정/출처 안내) | 사람 검토 시점에 타임스탬프 기록 (기본 NULL) |
| [신규 최소 스키마 필요] course_competency | `relation_type` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 역량-교육 관계 유형 (DIRECT/PARTIAL) (추천 정합성 판정) | 신규 관계 매핑 테이블에 DIRECT/PARTIAL/INSUFFICIENT/REJECTED로 명시 |
| [신규 최소 스키마 필요] course_competency | `evidence_location` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 증거 위치 (TITLE/CURRICULUM/INTRO) (근거 추적성) | 증거 발췌 위치 명시 |
| [신규 최소 스키마 필요] course_competency | `mapping_method` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 매핑 산출 방식 (HYBRID_EMBEDDING/RULE/HUMAN) (투명성 및 모델 검증) | 산출 경로 기록 |
| [신규 최소 스키마 필요] course_competency | `reviewer` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 사람 검토자 식별자 (검토자 실명/ID) | 사람 검토 전까지 NULL 유지 (가짜 채우기 금지) |
| [신규 최소 스키마 필요] course_competency | `reviewed_at` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 사람 검토 일시 (검토 완료 시점) | 사람 검토 전까지 NULL 유지 |
| [신규 최소 스키마 필요] course_competency | `review_note` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 사람 검토 의견 및 판정 사유 (품질 리뷰 기록) | 검토 의견 기록 필드 제공 |
| [신규 최소 스키마 필요] assessment_definition | `question_version` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 진단 문항 버전 (v1.0 등) (설문 변경 이력 관리) | v1.0 명시 |
| [신규 최소 스키마 필요] assessment_definition | `scoring_standard_version` | string | 100.0% | 0.0% | **컬럼 없음** | PRODUCTION_ACTIVE | 점수 및 갭 계산식 버전 (v1.0) (평가 알고리즘 변경 추적) | v1.0 명시 |
