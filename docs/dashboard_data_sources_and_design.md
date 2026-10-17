# 교육·역량 대시보드 데이터 및 설계 명세서

## 1. 문서 목적

이 문서는 `edu-skill-gap` 대시보드가 어떤 데이터를 사용하고, 추천 결과를 어떻게 생성하며, 사용자에게 어떤 한계와 이용 정보를 제공하는지 설명한다.
특히 **STEP 4 표본 검증 데이터셋(553건/295건)**과 **고객용 Customer MVP 전체 통합 코퍼스(8,645건/8,291건)**의 범위를 엄격히 구분하고, 전처리 선별 상태와 실제 추천 기준을 명확히 정의한다. (기준일: 2026-10-17 확인)

---

## 2. 대시보드의 범위 및 실행 경로

| 구분 | 고객용 대시보드 (Customer MVP) | 분석·표본 대시보드 (STEP 4 / Integrated) |
|---|---|---|
| **기본 진입 파일** | `app.py` ➔ `customer_dashboard/streamlit_customer.py` | `app/streamlit_step4.py`, `app/streamlit_integrated.py` |
| **주요 대상** | 인사·총무·경영지원 실무 재직자 | 연구원, 교육 기획자, 데이터 분석가 |
| **데이터 코퍼스** | **8,645건** 정제 교육 코퍼스 | **553건** 표본 후보 (295건 선별) |
| **역량 체계** | **8대 KSA 직무역량 마스터** (경영전략·재무 포함) | **7대 핵심 역량** (초기 표본) |
| **추천 엔진** | `UnifiedHybridRecommender` (임베딩+BM25+군집) | 규칙 기반 역량 매핑 갭 정렬 (Gap 우선) |
| **검증 정책** | 오매핑 109건 감사 차단, 대체 수강처 제공 | `INCLUDED` 전처리 선별 강좌 매핑 |

---

## 3. 데이터 범위 및 코퍼스 비교

### 3.1 4단계 데이터 거버넌스 단계 구분
1. **수집 (Raw Collection)**: 고용24 공공 API 및 7개 민간·공공 플랫폼(휴넷, KPC, KMA, 멀티캠퍼스, 패스트캠퍼스, 경기도GSEEK 등)에서 수집된 교육 메타데이터.
2. **전처리 선별 (Preprocessing Inclusion)**: 직무 무관 강좌(간호, 부동산, 소방 등)를 `EXCLUDED`로 배제하고, 연관성 키워드와 분류 코드가 확인된 과정을 `INCLUDED`로 1차 선별.
   - ⚠️ `INCLUDED`는 **공인 자격 인증이나 사람의 전수 품질 보증이 아니며, 규칙 기반 전처리 선별 상태**임. ("적합 확정" 표현 지양)
3. **자동 하이브리드 매핑 (Automated Mapping)**: 8,645건 코퍼스 대상 Ko-SRoBERTa(768차원) 임베딩 유사도 및 BM25 Okapi 텍스트 매칭을 결합한 8,291건 KSA 역량 매핑.
4. **오매핑 선별 및 규칙 기반 차단 (Mismatch Filtering)**: 오매핑 의심 109건에 대해 비직무 군집(C0/C6/C7) 및 IT 개발 키워드 조건을 적용한 규칙 기반 차단(96건 차단 / 차단 규칙 비해당 13건 유지) 적용.

### 3.2 데이터셋 상세 명세표

| 데이터셋 | 파일 경로 | 코퍼스 구분 | 건수 / 규모 | 설명 |
|---|---|---|---|---|
| **고객용 정제 코퍼스** | `data/hr/processed/education_courses_search_cleaned.parquet` | Customer MVP (전체) | **8,645건** | 9대 플랫폼 정제 교육과정, 텍스트 품질 점검 완료 (임베딩 1:1 매핑 확인) |
| **KSA 역량 매핑 (Parquet)** | `data/hr/output/recommendation/course_competency_long.parquet` | Customer MVP (엔진) | **8,291행** (4,966개 고유 강좌) | 추천 엔진(`UnifiedHybridRecommender`)이 직접 읽는 8대 KSA 역량 매핑 |
| **KSA 역량 매핑 (CSV)** | `data/hr/mapped/education_ksa_mapping.csv` | Customer MVP (조회) | **8,291행** (4,966개 고유 강좌) | 검증 및 조회용 KSA 매핑 테이블 (Parquet과 동일 데이터) |
| **Ko-SRoBERTa 임베딩** | `data/hr/output/recommendation/embeddings_ko_sroberta_all.npy` | Customer MVP (벡터) | **8,645 × 768** | 768차원 L2 정규화 임베딩 행렬 (`jhgan/ko-sroberta-multitask`) |
| **임베딩 메타데이터** | `data/hr/output/recommendation/course_embeddings_metadata_all.parquet` | Customer MVP (메타) | **8,645행** | `vector_index` (0~8,644)와 `course_uid` 1:1 순서 엄격 일치 |
| **10대 직무 군집 데이터** | `data/hr/output/recommendation/course_clusters_8645.parquet` | Customer MVP (군집) | **8,645행** | K-Means 10대 직무 군집 및 토픽 레이블 매핑 |
| **BM25 토큰 캐시** | `data/hr/processed/tokenized_corpus_cache.parquet` | Customer MVP (검색) | **8,645행** | BM25 키워드 적합도 연산용 사전 토큰화 캐시 |
| **오매핑 의심 목록** | `data/hr/output/recommendation/mapping_mismatch_samples.json` | Customer MVP (차단) | **109건** | 규칙 기반 선별 차단(96건 차단 / 규칙 비해당 13건 유지) |
| **표본 교육과정 후보** | `data/hr/output/integration/hr_integrated_candidates.csv` | STEP 4 표본 (Pilot) | **553건** | 공공 API 140건 + 플랫폼 SQLite 413건 (코퍼스와 95.3% 중복 확인) |
| **표본 전처리 선별 매핑** | `data/hr/output/integration/hr_mapping_verified.csv` | STEP 4 표본 (Pilot) | **295행** (295개 고유 강좌) | 1차 전처리 규칙 기반 선별 과정과 7대 역량 매핑 |
| **NCS 직무 마스터** | `data/hr/processed/jobs.csv` | 공통 마스터 | **6개 직무** | 인사, 노무, 총무, 비서, 경영기획, 기타 |
| **NCS 역량 마스터** | `data/hr/processed/competencies.csv` | STEP 4 마스터 | **7개 역량** | 채용, 평가보상, 근로관계법, 문서기획, 자산, 매너, 프로젝트 |
| **KSA 역량 마스터** | `src/recommendation/ksa_master.py` | Customer MVP 마스터 | **8개 역량** | 위 7개 역량 + **`COMP_MGMT_02` (경영전략 및 재무회계 기초)** |

> 📌 **미매핑 강좌(3,679건) 추천 취급 원칙**:
> 전체 8,645건 중 KSA 매핑에 포함되지 않은 3,679건은 추천 질의와의 시맨틱/키워드 유사도가 높을 경우 후보로 추천될 수 있으나, 이는 의미 검색 기반 추천일 뿐 'KSA 검증 완료' 상태가 아니므로 카드의 배지(`교육내용 검색으로 찾은 추가 후보`)를 통해 구분을 명확히 관리한다.

---

### 3.3 딥러닝 임베딩 모델 및 질의 인코더 기술 명세
1. **실제 적용 모델**: `jhgan/ko-sroberta-multitask` (SentenceTransformer 기반)
   - 아키텍처: KLUE RoBERTa-base 파인튜닝 (KorNLI + KorSTS 다중 작업 학습)
   - 임베딩 차원: **768차원** (Max Sequence Length: 128)
   - 풀링 방식: `Mean Pooling`
   - 정규화 설정: `normalize_embeddings=True` (L2 정규화 단위 벡터)
   - 유사도 계산: 코퍼스 벡터와 질의 벡터 간 내적(`dot product`)으로 코사인 유사도 산출
2. **질의 인코더 일치성**:
   - `UnifiedHybridRecommender`의 질의 인코더 또한 동일한 `SentenceTransformer("jhgan/ko-sroberta-multitask")`와 `normalize_embeddings=True`를 적용하여 코퍼스 임베딩 공간과 엄격히 일치함.
3. **문서상 모델 표기 오류 정정**:
   - 과거 기획 문서(`docs/EMBEDDING_AND_CLUSTERING_ROADMAP.md` 등)에 후보군으로 기록되었던 `snunlp/KR-SBERT-V40K`는 사전 검토 후보였을 뿐 실제 임베딩 생성 및 런타임 추론에 일절 사용되지 않음.
4. **향후 모델 교체 시 거버넌스 원칙**:
   - 차원이 동일(768차원)하더라도 사전학습 코퍼스와 가중치 공간이 상이하므로 **이종 모델의 임베딩 행렬과 질의 인코더는 절대로 혼용할 수 없음**.
   - 차기 모델 도입 시에는 `embeddings_v2_<model_slug>.npy` 및 `metadata_v2.parquet`로 완전히 격리된 버전 디렉토리에서 관리해야 함.

---

## 4. 실제 수행 업무 선택지 도출 방식

- **방식**: 빈 텍스트 자유 입력 대신, NCS 역량 마스터의 실무 기술(`skill`) 항목에서 문장 분리 품질 검토를 거쳐 안정적인 `task_id`와 `competency_id`를 구조화하여 선택지로 제공한다.
- **예시**: 인사 직무의 `COMP_HR_01(인력채용)` ➔ `면접 기술`, `역량 평가`, `입사 온보딩 기획`, `인재 소싱` (`TASK_COMP_HR_01_01` ~ `04`).
- **고유 ID 불변성(Invariance)**: 순서 변경이나 항목 삽입에 영향받지 않도록 `f"{c_id}:{item}"`의 SHA-256 해시 슬러그 기반 고유 ID를 부여함. 업무명이 변경될 경우 신규 ID가 부여되며, 기존 세션 선택 상태는 재매핑 또는 재확인 처리됨.
- **자유 입력 메모**: 목록에 없는 업무는 보조 입력(메모)으로 보존하되, 추천 점수 왜곡 방지를 위해 선택된 표준 역량을 우선 반영한다.
- **Customer MVP 설문 보존**: 기존 고객용 대시보드의 1~5점 행동 척도 점검 문항(인사 9문항, 총무 8문항, 경영지원 9문항) 및 `JOB_TASK_MAPPING`과의 호환성을 완벽히 보존한다.

---

## 5. 추천 기준 및 성과 측정 원칙

### 5.1 추천 산식 및 근거 구분
1. **역량 갭 계산**: `보완 필요 단계 = max(목표 수준 - 현재 수준, 0)`
2. **과정 랭킹**:
   - Customer MVP: `UnifiedHybridRecommender` (하이브리드 유사도 + 역량 연계 가중치 + 군집 보조 매핑 + 오매핑 차단 필터)
   - STEP 4 표본: `보완 필요 단계(learning_gap)` 우선 ➔ 다중 연계 역량 수(`matched_count`) ➔ 짧은 교육 시수(`training_hours`) 순 정렬
3. **추천 카드의 근거 구분**:
   - `(course_uid, competency_id)` 쌍이 매핑 테이블에 존재: `기존 역량 연결 정보 기반`
   - 매핑 테이블에 부재: `교육내용 검색으로 찾은 추가 후보`
   - 공통 안내: `*(※ 사람의 검토 완료를 의미하지 않음)*` 필수 표기
4. **투명성 정보 제공**:
   - 교육기관명, 수강료(무료/수강료/가격 미확인 정직 표기), 총 시수, 교육 형태
   - **데이터 출처 및 데이터 수집 시점** (`collected_at` 기반, 임의의 '최신 확인일' 사칭 금지)
   - **원문 URL 링크** (`course_url`로 직접 이동하여 최신 일정·비용·개강 여부 확인 유도)

### 5.2 학습 완료 및 성과 기록 원칙
- **자가 학습 기록**: 대시보드의 완료 처리는 학습자가 교육기관에서 실제 수료 후 스스로 진척을 관리하는 **브라우저 세션 자가 기록**이다.
- **점수 자동 조작 금지**: 완료 체크 시 공식 평가 점수나 역량 수준을 자동으로 상향 조정하지 않는다.
- **외부 택소노미 정책**: ESCO/O*NET Crosswalk 보완 기능은 분석 목적 외에는 **기본 비활성화(OFF)** 정책을 엄격히 유지한다.

---

## 6. 서비스 한계 및 이용자 유의사항

1. **품질 보증 한계**: 전처리 선별(`INCLUDED`)은 데이터 정제 파이프라인 상의 직무 연관성 통과 상태일 뿐, 정부 기관이나 교육기관의 공식 추천 또는 품질 인증이 아니다.
2. **정보 최신성**: 교육과정의 모집 여부, 수강료 변동, 폐강 여부는 수집 시점 이후 달라질 수 있으므로 반드시 원문 링크를 통해 최종 확인해야 한다.
3. **개인정보 보호**: 사용자 입력 진단 결과 및 세션 완료 상태는 서버에 저장되지 않고 브라우저 세션 내에서만 유지된다.
4. **결과 없음 및 지원**: 조건에 맞는 확정 과정이 없거나 오류 발생 시 안내 가이드 및 GitHub Issues 피드백 채널을 제공한다.

---

## 7. 응답 지연 시간(Latency) SLA 및 측정 실측치

> ⚠️ **SLA 정의 유의사항**: "2초 이내" 표현은 모델 캐시가 상주하는 웜 세션(Warm Cache) 기준의 **미검증 목표 SLA**이며, 서버 콜드 스타트 시점에는 2초 이내 달성이 불가능함을 명시한다.

| 단계 | 측정 항목 | 목표 SLA (미검증 목표) | 로컬 실측치 (2026-10-17) | 비고 |
|---|---|---|---|---|
| **1. 첫 접속 (First Access)** | 기본 모듈 import 및 평가기 초기화 | `< 500 ms` | **5,530.4 ms** (약 5.5초) | 파이썬 런타임 및 Streamlit 핸드셰이크 |
| **2. 모델 초기화 (Cold Start)** | Ko-SRoBERTa 가중치 로드 + 코퍼스/임베딩 적재 | `< 2,000 ms` | **3,840.0 ms** (약 3.8초) | `@st.cache_resource`로 최초 1회만 발생 |
| **3. 첫 추천 (First Query)** | 질의 인코딩 + 시맨틱 내적 + BM25 + KSA 랭킹 | `< 500 ms` | **1,229.2 ms** (약 1.2초) | 실무 9문항 진단 완료 후 첫 결과 산출 |
| **4. 반복 추천 (Warm Cache)** | 기로드 모델 및 메모리 캐시 기반 후속/반복 추천 | `< 200 ms` | **665.3 ms** (약 0.6초) | 필터 변경 및 재검색 시 1초 미만 응답 |

---

## 8. 배포 운영 거버넌스 및 안전 롤백 가이드

### 8.1 로컬 Checkout과 공개 앱(Public App) 복구의 구분
- `git checkout <commit_hash>`는 **로컬 개발자의 작업 디렉토리 상태만 변경**하는 명령어로, 원격 클라우드(Streamlit Community Cloud, Hugging Face Spaces 등)에 배포된 공개 애플리케이션에는 **일절 영향을 주지 않는다**.
- 공개 앱의 장애 복구는 반드시 **배포 브랜치(`main` 또는 `release`)에 롤백 커밋을 반영하고 원격 푸시**하여 CI/CD 재배포를 완료해야 실 서비스에 적용된다.

### 8.2 비파괴적 복구(Non-destructive Revert) 원칙
- **1순위 (추천 / 안전 복구)**:
  - 기존 이력을 보존하며 결함 커밋을 취소하는 리버트 커밋 생성:
    ```bash
    git revert <faulty_commit_hash> -m 1  # 머지 커밋인 경우 부모 1 기준
    # 또는 단일 커밋인 경우
    git revert <faulty_commit_hash> --no-edit
    git push origin <deployment_branch>
    ```
  - 강제 푸시(`--force`) 없이 안전하게 원격 브랜치에 반영되며, 클라우드 빌드가 자동 트리거됨.
- **2순위 (대시보드 롤백)**:
  - Streamlit Community Cloud 관리 콘솔에서 배포 포인터를 이전 안정 릴리즈 태그(`v1.0.0` 등)로 즉시 전환.
- **금지 사항**:
  - `git reset --hard` 후 `git push --force`는 협업자의 로컬 브랜치 충돌 및 이력 유실을 유발하므로 배포 거버넌스상 엄격히 금지함.

### 8.3 복구 후 실제 실행 버전 확인 절차
1. 배포 플랫폼 빌드 로그에서 `Build Succeeded` 및 새 커밋 해시 반영 확인.
2. 공개 서비스 접속 후 사이드바 하단 빌드 버전 또는 진입 화면의 릴리즈 태그 확인.
3. 대표 시나리오(인사 채용, 총무 문서) 진단 및 추천 카드가 정상 출력되는지 헬스체크 수행.
4. *(※ 현재 팀원 시험 운영 준비 단계에서는 복구 명령을 실행하지 않음)*
