# 교육과정 8,645건 수강 후기 및 평점 데이터 전수 조사 감사 보고서

> **프로젝트**: NCS 기반 인사·총무·경영지원 교육과정 검색·추천 시스템  
> **조사 대상**: 8,645건 통합 코퍼스, 7개 원본 SQLite DB, Parquet 및 CSV 파일 전수  
> **조사 일자**: 2026-10-21  
> **조사 기준**: 단순 컬럼명 검색을 넘어 테이블 스키마, 저장된 실제 값, NULL 비율, 파이프라인 누락 여부 전수 확인

---

## Executive Summary (핵심 결과 요약)

1. **8,645건 통합 코퍼스(`education_courses_integrated.parquet`, `education_courses_search_cleaned.parquet`)**:
   - **실제 수강 후기 원문(review text)**: **0건 (전무)**
   - **수강생 평점 및 만족도 점수(rating, satisfaction)**: **0건 (전무)**
   - **수강 후기 건수(review_count)**: **0건 (통합 코퍼스에는 미포함)**

2. **원본 7개 교육 데이터 출처 SQLite DB**:
   - **수강 후기 텍스트 및 평점 점수**: 7개 교육기관 원본 DB 전체에서 **단 1건도 수집/저장되어 있지 않음 (0건)**.
   - **유일한 수강후기 관련 데이터 발견 (KPC 한국생산성본부)**:
     * 원본 `kpc_courses.db`에 **`review_count` (수강후기 개수) 수치 컬럼이 존재**하며, 1,513건 전수에 값이 들어있음 (후기 1건 이상 강좌: **1,016건, 67.2%**, 최대 169건).
     * 그러나 **후기 원문(텍스트)이나 평점 점수는 KPC에도 없으며**, 이 누적 건수(`review_count`)마저 **8,645건 통합 코퍼스로 합쳐지는 과정에서 누락(Dropped)**되었습니다.
   - **기타 반응 지표**: GSEEK의 `recommend_count`(추천수 1,991건), KMA의 `favorite_count`(찜수 1,765건)가 원본 DB에 존재했으나 통합 과정에서 누락되었습니다.

3. **기존 CSV 중 실제 후기 데이터 발견 (`inflearn_course_reviews.csv` / `.json`)**:
   - `data/processed/inflearn_course_reviews.csv`에 **실제 수강생 후기 124건(작성자, 5점 만점 평점, 후기 원문 텍스트, 강의 평점)**이 완벽하게 보존되어 있습니다.
   - **그러나 8,645건 코퍼스와의 연결 검사 결과**: 인프런 플랫폼 전체가 인사·총무 직무 코퍼스 편입에서 제외되었기 때문에, **현재 운영 중인 8,645건 코퍼스에는 연결되어 있지 않음 (0건 매칭)**을 확인했습니다.

---

## 1. 7개 교육기관별 원본 SQLite DB 전수 조사 비교표

| 교육기관 / DB 경로 | 수집 강좌수 | 후기 관련 컬럼 | 실제 값 저장 건수 | NULL/공백 비율 | 후기 원문 유무 | 평점 점수 유무 | course_uid 연결 가능 여부 | 통합 과정 누락 여부 |
|---|---|---|---|---|---|---|---|---|
| **KPC (한국생산성본부)**<br>`data/courses/kpc_courses.db` | 1,513건 | **`review_count`**<br>(후기 건수) | **1,513건**<br>(>0건: 1,016건) | **0.0%**<br>(전수 수치) | **없음 (X)**<br>(숫자만 존재) | **없음 (X)** | **가능 (O)**<br>`KPC_{ecno}` 매핑 | **누락됨 (O)**<br>통합 시 컬럼 제외됨 |
| **GSEEK (경기도 지식)**<br>`data/courses/gseek_courses.db` | 1,991건 | 없음<br>(`recommend_count`) | 1,991건<br>(추천수) | 0.0% | **없음 (X)** | **없음 (X)** | 가능 (O)<br>`GSEEK_{sn}` | **누락됨 (O)**<br>추천수 컬럼 제외됨 |
| **KMA (한국능률협회)**<br>`data/courses/kma_courses.db` | 1,765건 | 없음<br>(`favorite_count`) | 1,765건<br>(찜수) | 0.0% | **없음 (X)** | **없음 (X)** | 가능 (O)<br>`KMA_{crscd}` | **누락됨 (O)**<br>찜수 컬럼 제외됨 |
| **휴넷 (HUNET)**<br>`data/courses/hunet_courses.db` | 1,958건 | **없음** | 0건 | - | **없음 (X)** | **없음 (X)** | 가능 (O) | 누락 없음 (원본에 부재) |
| **멀티캠퍼스**<br>`data/courses/multicampus_courses.db`| 1,116건 | **없음** | 0건 | - | **없음 (X)** | **없음 (X)** | 가능 (O) | 누락 없음 (원본에 부재) |
| **KFO (한국직업방송)**<br>`data/courses/kfo_courses.db` | 162건 | **없음** | 0건 | - | **없음 (X)** | **없음 (X)** | 가능 (O) | 누락 없음 (원본에 부재) |
| **패스트캠퍼스**<br>`data/SQLite/fastcampus_courses.db`| 901건 | **없음** | 0건 | - | **없음 (X)** | **없음 (X)** | 미포함 플랫폼 | 통합 대상 제외 플랫폼 |
| **공공 API (고용24 등)**<br>HRD-Net 등 140건 | 140건 | **없음** | 0건 | - | **없음 (X)** | **없음 (X)** | 가능 (O) | 누락 없음 (원본에 부재) |

---

## 2. 통합 Parquet 데이터셋 전수 검증

### 2.1 `education_courses_integrated.parquet` (30개 컬럼)
전체 30개 컬럼을 전수 검사한 결과:
- `course_uid`, `provider`, `title`, `course_intro`, `target_audience`, `learning_goals`, `curriculum`, `duration_hours`, `price`, `start_date`, `end_date`, `url`, `ncs_code`, `ksa_knowledge`, `ksa_skill`, `ksa_attitude`, `mapping_status` 등으로 구성됨.
- `review`, `rating`, `stars`, `satisfaction`, `comment`, `feedback`, `후기`, `평점`, `만족도` 관련 컬럼: **0개 (전혀 없음)**.
- `start_date` 컬럼이 'star' 검색어에 매칭되었으나, 이는 교육 개설일(예: `2026-10-19`)이며 평점/별점과 무관함.

### 2.2 `education_courses_search_cleaned.parquet` (42개 컬럼)
전체 42개 컬럼을 전수 검사한 결과:
- 30개 컬럼에 전처리 텍스트(`clean_search_text`, `clean_intro`, `clean_goals`, `clean_curriculum`), 텍스트 품질 플래그(`text_quality_status`, `is_base64_cleaned`) 등이 추가된 구조임.
- 후기 본문, 평점, 만족도 점수, 리뷰 개수 컬럼: **0개 (전혀 없음)**.

---

## 3. 세부 데이터 출처별 심층 분석

### 3.1 KPC (한국생산성본부)의 `review_count` 데이터 분석
- **테이블**: `courses` (1,513행)
- **컬럼**: `review_count` (INTEGER)
- **통계치**:
  * 결측치(NULL): **0건 (0.0%)**
  * `review_count > 0`인 강좌: **1,016건 (67.15%)**
  * 최대값: **169건** (`비즈니스문서작성실무`)
  * 평균값: **16.18건**
  * 상위 강좌: `비즈니스문서작성실무` (169건), `커뮤니케이션스킬` (152건), `기획서작성실무` (140건)
- **한계점**:
  1. 수강 후기의 원문(텍스트 내용)은 크롤링되지 않았고 **후기 개수 숫자만 수집**됨.
  2. 별점이나 평점(예: 4.8점 등) 데이터는 크롤링되지 않음.
  3. 통합 Parquet 생성 파이프라인에서 해당 컬럼이 제외되어 현재 검색/추천 코퍼스에서는 참조할 수 없음.

### 3.2 인프런(Inflearn) 실제 후기 124건 분석 (`inflearn_course_reviews.csv`)
- **저장 위치**: `data/processed/inflearn_course_reviews.csv` 및 `.json`
- **데이터 건수**: 20개 강좌에 대한 **실제 수강생 후기 124건**
- **포함된 상세 컬럼 및 실제 값**:
  * `review_content`: 실제 수강생이 작성한 텍스트 후기 124건 (평균 150~300자)
  * `review_rating`: 작성자 개별 평점 (1~5점 정수, 124건 전수 존재)
  * `review_author`: 작성자 닉네임 (124건 전수 존재)
  * `rating_score`: 강좌 종합 평점 (예: 4.9점 등 소수점 점수)
  * `review_count`: 강좌별 총 후기 수
- **8,645건 통합 코퍼스와의 관계**:
  * 8,645건 코퍼스 내 제공기관(provider)에 **'인프런'은 0건**입니다.
  * 20개 강좌의 제목(예: "클로드 코드 완벽 마스터", "Docker가 쉬워지는 운영체제 이야기")은 IT/개발 중심 강좌로, 현재 인사·총무·경영지원 전문 코퍼스인 8,645건에는 편입되지 않았습니다.
  * 따라서 **`course_uid`로 연결할 수 없는 독립 분리 데이터셋**입니다.

---

## 4. 원본 데이터 누락(Dropped) 원인 및 복원 가능성

### 누락 발생 원인
프로젝트 초기 데이터 통합 파이프라인(`integrate_external_courses_pipeline.py`) 설계 시:
1. 6개 교육기관의 상이한 스키마를 단일 표준 스키마(30개 공통 컬럼)로 맞추는 과정에서,
2. KPC에만 존재하던 `review_count`, GSEEK에만 존재하던 `view_count`/`recommend_count`, KMA에만 존재하던 `favorite_count`와 같은 **기관별 비공통 메트릭이 공통 컬럼에서 누락(Dropped)**되었습니다.

### 복원 가능성 및 조치 방안
- KPC 원본 `kpc_courses.db`에 `ecno`와 `review_count`가 고스란히 남아있으므로, 원본 수정을 일체 하지 않고도 `course_uid`(`KPC_{ecno}`)를 매핑 키로 활용하여 **언제든 1:1 Left Join으로 복원 및 부착**할 수 있습니다.
- 마찬가지로 GSEEK의 `recommend_count`, KMA의 `favorite_count`도 각각 고유 ID로 조인하여 "사용자 인기/신뢰도 피처"로 복원할 수 있습니다.

---

## 5. 결론 및 최종 요약 답변

| 사용자 질의 항목 | 최종 전수 감사 결과 |
|---|---|
| **1. 후기 관련 테이블/컬럼 존재 여부** | 8,645건 통합 Parquet에는 **전무(0개)**. 원본 DB 중에서는 **KPC에만 `review_count` 컬럼이 유일하게 존재**함. |
| **2. 실제 값이 저장된 건수** | 8,645건 통합 Parquet: **0건**. KPC 원본 DB: **1,513건 전수 저장** (>0인 건수: 1,016건). 인프런 별도 CSV: **124건**. |
| **3. NULL 및 공백 비율** | KPC `review_count`: **NULL 0.0%** (전수 수치 저장). 통합 Parquet: 컬럼 미존재. |
| **4. 후기 원문 존재 여부** | **8,645건 전수 및 7개 원본 DB 전체에 후기 원문은 전혀 없음 (0건)**. (오직 8,645건과 무관한 인프런 20개 강좌에만 124건 존재). |
| **5. 평점/만족도 점수 존재 여부** | **8,645건 전수 및 7개 원본 DB 전체에 평점 점수 전혀 없음 (0건)**. |
| **6. course_uid와 연결 가능 여부** | KPC `review_count`: `KPC_{ecno}`를 통해 **100% 연결 가능**. 인프런 리뷰 124건: 코퍼스에 미포함되어 **연결 불가**. |
| **7. 원본에는 있지만 통합 시 누락된 정보** | **KPC의 `review_count` (1,513건)**, **GSEEK의 `recommend_count` (1,991건)**, **KMA의 `favorite_count` (1,765건)**가 공통 스키마 통합 시 누락됨. |

> **데이터 무결성 원칙 준수 확인**:  
> 본 조사는 워크스페이스 내 원본 데이터 및 Parquet 파일을 일체 수정하지 않고 사실 그대로 전수 감사했습니다.  
> 실제 사용자가 작성하지 않은 가짜 AI 생성 후기나 조작된 평점은 일절 생성하거나 주입하지 않았음을 보증합니다.
