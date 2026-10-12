# NCS 교육 데이터 Long-form / Wide-form 구조화 및 다차원 집계 분석 보고서

**프로젝트**: NCS 기반 인사·총무·경영지원 맞춤형 교육과정 검색·추천 시스템 (`edu-skill-gap`)  
**작성일자**: 2026-10-12  
**분석 대상**:
- 통합 교육과정 8,645건 (`education_courses_search_cleaned.parquet`)
- 교육-NCS/KSA 역량 매핑 8,291건 (`education_ncs_mapping.csv`)
- TF-IDF 핵심 키워드 8,645건 (`course_tfidf_keywords.csv`)
- 표준 역량 정의(`competencies.csv`) 및 직무 정의(`jobs.csv`)

---

## 1. 개요 및 목적

본 보고서는 통합 교육과정 8,645건과 NCS/KSA 역량 매핑 데이터를 대상으로 데이터 엔지니어링의 핵심 원칙인 **관측 단위(Observational Unit)를 명확히 정립**하고, 데이터 분석 및 기계학습 모델링에 필수적인 **Long-form (Tidy Data)**과 **Wide-form (Matrix/Spreadsheet)** 구조를 상호 변환·구축한 결과를 정리합니다.

또한, `groupby`, `crosstab`, `pivot_table`을 활용하여 교육기관별, 직무군별, 역량별로 다차원 집계를 수행하고, 관계형 조인 시 자주 발생하는 **고유 과정 수(`nunique`)와 연결 건수(`count`)의 혼동에 따른 중복 집계 오류를 원천 차단하는 정량적 분석**을 제공합니다.

---

## 2. 데이터 관측 단위 (Observational Units) 점검

데이터 분석을 시작하기 전, 각 테이블의 **한 행(Row)이 현실 세계의 무엇을 나타내는지(관측 단위)**를 엄밀하게 정의했습니다.

| 구분 | 관측 단위 (Observational Unit) | 기본 키 (Primary Key) | 전체 건수 | 특징 및 주의점 |
| :--- | :--- | :--- | :---: | :--- |
| **A. 교육과정 단위** | 교육기관에 등록된 **개설 강좌 1건** | `course_uid` | **8,645건** | 각 기관의 고유 ID 단위로 100% 고유(Unique)함 |
| **B. 개설 회차 단위** | 동일 교육콘텐츠의 **다회차 반복 개설** | `(provider, title)` | **6,497개 고유 제목** | 1,987건이 동일 제목 다회차 개설 강좌 (KMA 다회차율 69.3%) |
| **C. 역량 연결 단위** | 교육과정과 역량 간의 **다대다(N:M) 매핑 1건** | `(course_uid, competency_id)` | **8,291건** | 4,966개 강좌가 평균 1.67개 역량에 연결됨 (미매핑 3,679건) |
| **D. 키워드 단위** | 교육과정에서 추출된 **TF-IDF 핵심 단어 1건** | `(course_uid, keyword_rank)` | **68,348건** | 강좌당 상위 1~8순위 키워드와 중요도 점수 보유 |

> **⚠️ 다회차 개설(B)과 교육과정(A)의 혼동 주의**:  
> 예를 들어 한국능률협회(KMA)는 전체 1,765개 개설 회차 중 순수 고유 제목은 541개에 불과합니다. 인기 강좌를 연중 여러 번 개설하기 때문입니다. 반면 경기도 평생학습포털(GSEEK)은 1,991개 강좌가 모두 서로 다른 단일 VOD 강좌입니다. 따라서 교육기관 간 규모 비교 시 '개설 회차 수'와 '고유 강좌 수'를 반드시 구분해야 합니다.

---

## 3. Long-form (Tidy Data) 데이터셋 구축

Hadley Wickham의 **Tidy Data 원칙**에 따라:
1. 각 변수(Variable)는 하나의 열(Column)을 이룹니다.
2. 각 관측치(Observation)는 하나의 행(Row)을 이룹니다.
3. 각 관측 단위의 유형은 별도의 테이블을 형성합니다.

### 3.1 교육-역량 연결 Long-form (`course_competency_long.parquet`, `.csv`)
- **총 레코드 수**: **8,291행**
- **관측 단위**: 1개 교육과정과 1개 역량 간의 개별 매핑 관계
- **주요 컬럼**:
  - `course_uid`, `course_title`, `provider`: 교육과정 기본 정보
  - `target_job_family`: 타겟 직무군 (인사, 노무, 총무/사무행정, 경영지원 등)
  - `competency_id`, `competency_name`, `ksa_type`: 매핑된 역량 및 유형(Knowledge/Skill/Attitude)
  - `mapping_confidence`, `mapping_status`: 신뢰도(HIGH/MEDIUM/LOW) 및 실무 검증 여부(`VERIFIED`/`REVIEW_NEEDED`)
  - `is_verified` (bool), `confidence_weight` (float: 1.0, 0.7, 0.4)
- **장점**: 새 역량이 추가되어도 컬럼 구조 변경이 불필요하며, SQL 조인 및 Seaborn/Plotly 다차원 그룹핑 시각화에 최적화됩니다.

### 3.2 교육-키워드 Long-form (`course_keyword_long.parquet`, `.csv`)
- **총 레코드 수**: **68,348행**
- **관측 단위**: 1개 교육과정의 1개 핵심 키워드
- **주요 컬럼**:
  - `course_uid`: 교육과정 고유 식별자
  - `provider`, `course_title`: 출처 기관 및 제목
  - `keyword`: 추출된 형태소/키워드 (예: "노무관리", "취업규칙", "엑셀")
  - `tfidf_score`: TF-IDF 중요도 점수 (float)
  - `keyword_rank`: 해당 교육과정 내 키워드 순위 (1 ~ 8)

---

## 4. Wide-form (Matrix/Spreadsheet) 데이터셋 구축

Wide-form은 1개 교육과정(또는 교육기관)을 1개 행으로 고정하고, 다차원 속성(역량, 키워드 순위 등)을 **가로 컬럼**으로 펼친 포맷입니다.

### 4.1 교육과정 × KSA 역량 연결 행렬 (`matrix_course_competency_wide.parquet`, `.csv`)
- **형태**: **8,645행 × 24열** (전체 8,645개 교육과정 100% 포함, 미매핑 3,679건은 0 처리)
- **구성 컬럼**:
  - `course_uid`, `provider`, `title`, `price`, `duration_hours` (기본 정보)
  - 8대 역량 이진 플래그 (0 또는 1): `COMP_GA_01`, `COMP_GA_02`, `COMP_HR_01`, `COMP_HR_02`, `COMP_LABOR_01`, `COMP_MGMT_01`, `COMP_MGMT_02`, `COMP_SEC_01`
  - 8대 역량 검증 플래그 (0 또는 1): `COMP_GA_01_VERIFIED` ~ `COMP_SEC_01_VERIFIED`
  - 요약 집계 컬럼: `total_comp_count` (매핑된 역량 개수), `verified_comp_count`, `is_mapped` (매핑 여부 1/0)
- **용도**: 머신러닝/추천 모델의 특성 행렬($X$ Matrix) 입력, 다중 라벨 분류(Multi-label Classification), 코사인 유사도 연산.

### 4.2 교육과정 × 핵심 키워드 랭킹 행렬 (`matrix_course_keyword_wide.csv`)
- **형태**: **8,645행 × 13열**
- **구성 컬럼**:
  - `course_uid`, `provider`, `title`
  - 1~5순위 키워드명: `kw_rank_1`, `kw_rank_2`, `kw_rank_3`, `kw_rank_4`, `kw_rank_5`
  - 1~5순위 TF-IDF 점수: `tfidf_rank_1`, `tfidf_rank_2`, `tfidf_rank_3`, `tfidf_rank_4`, `tfidf_rank_5`
- **용도**: 엑셀 보고서 출력 및 강좌별 대표 키워드 요약 브라우징.

### 4.3 교육기관 × 역량별 고유 교육과정 수 (`pivot_provider_competency_wide.csv`)
- **형태**: 6대 주요 교육기관 × 8개 KSA 역량 교차표
- **집계 함수**: `nunique(course_uid)` (고유 교육과정 수)

| 교육기관 | 경영전략 및 재무회계 | 근로관계 법률 | 문서작성 및 기획 | 비서 및 사무지원 | 인사기획 및 채용 | 인사평가 및 보상 | 자산 및 비품관리 | 프로젝트 및 조직관리 | 고유 매핑과정수 | 전체 개설과정수 | 매핑율(%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **한국능률협회(KMA)** | 120 | 83 | 1,505 | 596 | 134 | 123 | 42 | 680 | **1,717** | 1,765 | **97.3%** |
| **한국생산성본부(KPC)** | 227 | 87 | 1,397 | 163 | 167 | 164 | 204 | 228 | **1,415** | 1,513 | **93.5%** |
| **휴넷** | 101 | 150 | 360 | 167 | 56 | 99 | 24 | 439 | **1,006** | 1,969 | **51.1%** |
| **GSEEK** | 36 | 62 | 227 | 117 | 20 | 25 | 54 | 101 | **542** | 1,991 | **27.2%** |
| **멀티캠퍼스** | 10 | 14 | 129 | 18 | 9 | 10 | 6 | 103 | **262** | 1,116 | **23.5%** |
| **한국직업방송(KFO)** | 10 | 8 | 7 | 0 | 1 | 1 | 3 | 4 | **24** | 162 | **14.8%** |

---

## 5. Groupby / Crosstab / Pivot 심층 분석 결과

### 5.1 기관별 공급 구조 및 교육비·시수 비교 (`summary_provider_stats.csv`)

| 기관명 | 전체 개설수 | 고유 제목수 | 다회차 비율 | 무료 강좌수 | 평균 수강료(유료) | 평균 교육시간 | NCS 매핑과정 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **한국능률협회(KMA)** | 1,765건 | 541개 | **69.3%** | 30건 | 653,285원 | 11.7시간 | 1,717건 |
| **한국생산성본부(KPC)** | 1,513건 | 935개 | **38.2%** | 41건 | 604,078원 | 15.4시간 | 1,415건 |
| **멀티캠퍼스** | 1,116건 | 1,108개 | 0.7% | 4건 | **668,585원** | 14.3시간 | 262건 |
| **휴넷** | 1,969건 | 1,953개 | 0.8% | 10건 | **50,490원** | - (온라인) | 1,006건 |
| **GSEEK** | 1,991건 | 1,991개 | 0.0% | **1,991건** | **0원** (전면 무료) | - (VOD) | 542건 |
| **한국직업방송(KFO)** | 162건 | 56개 | **65.4%** | 0건 | 312,347원 | **120.7시간** | 24건 |

**핵심 인사이트**:
1. **교육 형태별 수강료 양극화**: KMA, KPC, 멀티캠퍼스 등 오프라인 집합교육 중심 기관의 평균 수강료는 약 60만~66만원대인 반면, 휴넷(온라인 직무 e-러닝)은 약 5만원대, 경기도 GSEEK은 100% 무료(공공 지원)로 뚜렷하게 구분됩니다.
2. **다회차 개설 특성**: KMA와 KFO는 소수의 인기 커리큘럼을 연중 반복 개설(다회차율 65% 이상)하는 구조이며, GSEEK과 휴넷은 방대한 단일 VOD 라이브러리를 구축하고 있습니다.

### 5.2 직무군별 & 역량별 공급 규모 (고유 과정수 vs 연결 건수)

| 직무군 (Target Job Family) | 연결 건수 (`count`) | 고유 교육과정 수 (`nunique`) | 검증 완료 건수 | 검토 필요 건수 | 검증 비율(%) | 과정당 평균 역량 수 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **총무/사무행정** | 3,625건 | **3,625건** | 1,923건 | 1,702건 | 53.0% | 1.00개 |
| **경영지원** | 2,059건 | **1,964건** | 1,373건 | 686건 | **66.7%** | 1.05개 |
| **경영지원/비서** | 1,061건 | **1,061건** | 368건 | 693건 | 34.7% | 1.00개 |
| **인사 (HR)** | 809건 | **760건** | 286건 | 523건 | 35.4% | 1.06개 |
| **인사/노무** | 404건 | **404건** | 207건 | 197건 | 51.2% | 1.00개 |
| **총무** | 333건 | **333건** | 95건 | 238건 | 28.5% | 1.00개 |

### 5.3 교육과정별 역량 연결 개수 분포 (`summary_course_comp_counts.csv`)

| 연결된 역량 개수 | 교육과정 수 | 전체 대비 비중(%) | 누적 비중(%) | 설명 |
| :---: | :---: | :---: | :---: | :--- |
| **0개 (미매핑)** | 3,679건 | 42.56% | 42.56% | 인사·총무 직무 외 일반 교양, IT, 취미, 어학 등 |
| **1개** | 2,686건 | 31.07% | 73.63% | 단일 역량 집중형 강좌 (예: 엑셀 실무, 노무법령 단과) |
| **2개** | 1,493건 | 17.27% | 90.90% | 융합 강좌 (예: 기획문서 작성 + 프로젝트 관리) |
| **3개** | 570건 | 6.59% | 97.49% | 종합 실무 과정 |
| **4개** | 181건 | 2.09% | 99.58% | 총괄 관리자/팀장 리더십 및 경영종합 |
| **5개 이상** | 36건 | 0.42% | 100.00% | 장기 종합 양성과정 |

---

## 6. 관계형 조인 시 중복 집계 방지 핵심 원칙

> **🚨 데이터 분석 시 가장 치명적인 함정: `count()` vs `nunique()`의 혼동**

1. **문제 현상**:  
   교육과정과 역량이 **다대다(N:M) 관계**일 때, 교육과정 테이블과 역량 매핑 테이블을 조인(`merge`)하면 1개 교육과정이 2개 이상의 행으로 복제(Fan-out)됩니다.
2. **실제 데이터 사례 (한국능률협회 KMA)**:
   - KMA의 역량 매핑 연결 건수(`count`): **3,283건**
   - KMA의 고유 매핑 교육과정 수(`nunique`): **1,717건**
   - 만약 분석가가 조인된 Long-form 테이블에서 단순히 `groupby('provider').size()` 또는 `.count()`를 구하면, KMA의 교육과정 수가 **1.91배(1,566건)나 뻥튀기(Double Counting)**되어 집계됩니다!
3. **해결 원칙**:
   - 교육기관이 보유한 **과정 규모**를 셀 때는 반드시 **`df.groupby('provider')['course_uid'].nunique()`**를 사용해야 합니다.
   - 역량 연결 강도나 포트폴리오 다양성을 분석할 때만 **`count()` (연결 건수)**를 사용해야 합니다.
   - 교차표 생성 시에도 `pd.crosstab`의 Margins(총합)는 '총 연결 건수'를 뜻하므로, '고유 과정수'와 컬럼명을 명확히 분리 표기해야 합니다.

---

## 7. 엄밀한 무결성 검증 (Verification) 결과

| 검증 항목 | 검증 대상 및 조건 | 결과 값 | 판정 |
| :--- | :--- | :---: | :---: |
| **1. 관계 수 보존** | Long-form 행 수 == Wide-form 행렬 원소 합계 | 8,291 == 8,291 | **PASS (100% 일치)** |
| **2. 전체 과정 ID 보존** | Wide 행렬의 `course_uid` 개수 == 원본 코퍼스 개수 | 8,645 == 8,645 | **PASS (누락 0건)** |
| **3. 매핑 과정 수 일치** | Long의 `course_uid.nunique()` == Wide의 `is_mapped==1` 합 | 4,966 == 4,966 | **PASS (100% 일치)** |
| **4. 키워드 레코드 보존** | Long 키워드의 `course_uid.nunique()` == 원본 코퍼스 개수 | 8,645 == 8,645 | **PASS (전수 매핑)** |
| **5. N:M 다대다 관계** | 1개 과정당 최대 6개 역량 다중 매핑 정상 수용 | 최대 6개 확인 | **PASS (다대다 온전 유지)** |

---

## 8. 최종 산출 파일 요약

1. **Long-form 데이터셋**:
   - [`course_competency_long.parquet`](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/course_competency_long.parquet) (8,291행)
   - [`course_keyword_long.parquet`](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/course_keyword_long.parquet) (68,348행)
2. **Wide-form 데이터셋**:
   - [`matrix_course_competency_wide.parquet`](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/matrix_course_competency_wide.parquet) (8,645행 × 24열)
   - [`matrix_course_keyword_wide.csv`](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/matrix_course_keyword_wide.csv) (8,645행 × 13열)
   - [`pivot_provider_competency_wide.csv`](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/pivot_provider_competency_wide.csv) (6대 기관 교차표)
   - [`crosstab_provider_competency_links.csv`](file:///d:/26_강의자료/프로젝트2_교육/data/hr/output/recommendation/crosstab_provider_competency_links.csv) (연결건수 교차표)
3. **요약 집계 테이블**:
   - `summary_provider_stats.csv`, `summary_job_family_stats.csv`, `summary_competency_stats.csv`, `summary_course_comp_counts.csv`
4. **대시보드 반영**:
   - [`app/streamlit_integrated.py`](file:///d:/26_강의자료/프로젝트2_교육/app/streamlit_integrated.py) (탭 7: Long/Wide-form 구조화 및 교차집계 신설)
