# [STEP 7-3] 교육과정 코퍼스(8,645건) - 리뷰 DB(9,406건) 식별자 연결 및 매핑 보고서
(Course Corpus & Review DB Key Mapping Report)

> **프로젝트**: NCS·KSA 기반 직무 맞춤형 교육 추천 시스템  
> **기준 마스터**: `data/hr/processed/education_courses_integrated.parquet` (8,645건)  
> **대응 리뷰셋**: `data/kfo_courses/` 내 7개 플랫폼 리뷰 DB (9,406건)  
> **매핑 결과물**: `data/hr/processed/review_course_id_mapping.parquet` (9,546건 마스터 매핑 테이블)  
> **작성 일자**: 2026-10-22  

---

## 1. 개요 및 매핑 목적

본 보고서는 인사·총무·경영지원 전문 교육 코퍼스인 **8,645건의 기준 마스터 데이터셋**과, 신규 업로드된 **7개 플랫폼 9,406개 강좌 리뷰 DB** 간의 식별자 체계를 전수 검증하고, 오매핑(False Positive)이나 ID 충돌 없이 **결정론적(Deterministic) 1:1 매핑 관계**를 확립한 기술 보고서입니다.

> ⚠️ **매핑 원칙**:  
> 본 프로젝트에서는 단순 텍스트/제목 유사도(Fuzzy Title Matching)를 배제하고, 플랫폼 고유의 원본 식별자(`source_course_id`)와 통합 마스터 키(`course_uid`)를 기반으로 엄밀한 **결정론적 키 매핑(Deterministic Key Joining)**을 적용하였습니다.

---

## 2. 매핑 결과 종합 통계 (Core Statistics)

| 구분 지표 | 건수 | 비율 (%) | 비고 |
| :--- | :---: | :---: | :--- |
| **리뷰 DB 전체 교육과정 수** | **9,406건** | 100.0% | 7개 플랫폼 전체 |
| ├─ **기존 코퍼스와 정확하게 연결된 교육 수** | **8,505건** | **90.42%** | 6개 플랫폼 (GSEEK, HUNET, KMA, KPC, MULTICAMPUS, KFO) |
| └─ **연결되지 않은 교육 수 (미포함 플랫폼)** | **901건** | **9.58%** | **패스트캠퍼스(FastCampus) 전수** |
| **기존 코퍼스(8,645건) 기준 매핑 현황** | **8,645건** | 100.0% | `education_courses_integrated.parquet` |
| ├─ **리뷰가 존재하는 기존 교육 수** | **8,505건** | **98.38%** | 위 8,505건과 정확히 1:1 대응 |
| └─ **리뷰가 없는 기존 교육 수** | **140건** | **1.62%** | **고용24 공공 3종 (내일배움 65, 사업주 65, NCS 10)** |
| **식별자 중복 및 충돌(Collision) 수** | **0건** | **0.0%** | 결함 없음 (100% 무결성) |
| **전체 합집합 교육과정 마스터 수** | **9,546건** | - | 8,505(공통) + 901(FC) + 140(고용24) |

---

## 3. 플랫폼별 실제 식별자(Key) 매핑 규칙

각 교육 플랫폼의 원본 DB 식별자와 기존 코퍼스의 `course_uid` 생성 규칙은 다음과 같이 1:1로 엄밀하게 연결됩니다:

| 플랫폼 | 리뷰 DB `course_id` 형식 | 원본 DB 원천 컬럼 | 기존 코퍼스 `course_uid` 규칙 | 매칭 건수 | 매칭 성공률 |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **GSEEK (경기지식)** | `299`, `300` | `courses.course_sn` | `GSEEK_{course_id}` | 1,991건 | **100.0% (1,991/1,991)** |
| **휴넷 (HUNET)** | `Y00406516` | `courses.course_id` | `HUNET_{course_id}` | 1,958건 | **100.0% (1,958/1,958)** |
| **KMA (한국능률협회)** | `110936_124341` | `courses.crscd || '_' || crsseq_id` | `KMA_{course_id}` | 1,765건 | **100.0% (1,765/1,765)** |
| **KPC (생산성본부)** | `47199_150944` | `courses.ecno || '_' || cono` | `KPC_{course_id}` | 1,513건 | **100.0% (1,513/1,513)** |
| **멀티캠퍼스** | `FA004Q`, `FA0088` | `courses.course_id` | `MULTICAMPUS_{course_id}` | 1,116건 | **100.0% (1,116/1,116)** |
| **KFO (한국직업방송)** | `kfo_event100_cdcs_1`| `courses.course_id` | `KFO_{course_id}` | 162건 | **100.0% (162/162)** |
| **소계 (매칭 성공)** | - | - | - | **8,505건** | **100.0%** |
| **패스트캠퍼스** | `200260`, `202418` | `courses.course_id` | (코퍼스 미포함 - NULL) | 901건 | 0.0% (독립 플랫폼) |
| **고용24 (공공)** | (리뷰 DB 없음) | `courses.course_id` | `PUB_{source_course_id}` | 140건 | 0.0% (리뷰 미존재) |

---

## 4. 고용24 140건 및 패스트캠퍼스 901건의 명확한 포함 범위 구분

분석 과정에서 드러난 가장 중요한 데이터 범위의 비대칭성은 **고용24 140건**과 **패스트캠퍼스 901건**의 취급 방식입니다:

### 1) 패스트캠퍼스 901건의 범위와 미포함 사유
- **현황**: 리뷰 DB에는 `fastcampus_courses_review.db`가 존재하여 901개 강좌와 44,383건의 리뷰가 수록되어 있으나, 기존 8,645건 코퍼스(`education_courses_integrated.parquet`)에는 단 1건도 포함되어 있지 않습니다.
- **원인 분석**:
  * 초기 프로젝트 2(NCS 인사·총무 직무 교육 추천) 기획 당시, 패스트캠퍼스는 IT/SW/영상/AI 테크 위주로 구성되어 있어 공공·직무 자격 중심의 8,645건 코퍼스 구축 파이프라인에서 제외되었습니다.
  * 따라서 패스트캠퍼스 강좌는 `mapping_status = 'UNMATCHED_FASTCAMPUS'`로 분류되며, `course_uid = NULL`로 안전하게 보관됩니다. 향후 IT 직무 확장 시 독립 코퍼스로 편입 가능합니다.

### 2) 고용24 140건의 범위와 리뷰 부재 사유
- **현황**: 기존 8,645건 코퍼스에는 고용24 공공 API로 실시간 수집된 140건이 포함되어 있습니다:
  * 국민내일배움카드: 65건
  * 사업주훈련: 65건
  * NCS 교육과정: 10건
- **원인 분석**:
  * 고용24는 공공기관(HRD-Net)으로, 수강생 후기 텍스트가 공개 API에 포함되지 않으므로 이번 7개 리뷰 DB에 고용24 리뷰 DB는 존재하지 않습니다.
  * 따라서 이 140건 강좌는 `mapping_status = 'CORPUS_NO_REVIEW_PUB'`, `review_count_actual = 0`, `average_rating_calculated = NaN`으로 올바르게 결측 처리되었습니다.

---

## 5. 생성된 매핑 테이블 명세 (`review_course_id_mapping.parquet`)

본 매핑 결과는 `data/hr/processed/review_course_id_mapping.parquet`로 영구 저장되었으며, 다음과 같은 9개 표준 컬럼을 갖습니다:

```sql
review_course_id_mapping (
    platform                 TEXT,    -- fastcampus, gseek, hunet, kfo, kma, kpc, multicampus, pub_hrd
    review_course_id         TEXT,    -- 리뷰 DB 상의 course_id (고용24의 경우 NULL)
    corpus_course_uid        TEXT,    -- 기존 8,645건 코퍼스의 course_uid (패스트캠퍼스는 NULL)
    corpus_source_provider   TEXT,    -- GSEEK, HUNET, KMA, KPC, MULTICAMPUS, KFO, 고용24_...
    corpus_source_course_id  TEXT,    -- 코퍼스 원천 ID
    title_in_review_db       TEXT,    -- 리뷰 DB에 기록된 강좌명
    title_in_corpus          TEXT,    -- 코퍼스에 기록된 강좌명
    mapping_status           TEXT,    -- EXACT_MATCH (8,505), UNMATCHED_FASTCAMPUS (901), CORPUS_NO_REVIEW_PUB (140)
    title_match              BOOLEAN  -- 강좌명 일치 여부 (EXACT_MATCH 8,505건 전수 True)
)
```

### 제목 일치성 검증 (Title Concordance Check)
식별자(`source_course_id`)로 연결된 8,505건에 대해 리뷰 DB의 강좌명(`title_in_review_db`)과 코퍼스의 강좌명(`title_in_corpus`)을 1:1 교차 대조한 결과, **8,505건 전수(100.0%)에서 강좌명이 완벽히 일치**하여 식별자 매핑의 신뢰성이 교차 검증되었습니다.
