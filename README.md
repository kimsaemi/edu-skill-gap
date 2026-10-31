# 프로젝트 2 | NCS 기반 인사 직무역량 분석 및 맞춤형 교육과정 추천

## 1. 개요 및 핵심 질문
- **핵심 질문**: 인사 직무에 필요한 핵심 역량은 무엇이며, 이를 개발하기 위해 어떤 교육과정을 우선 추천할 수 있을까?
- **분석 범위**:
  - **대상 직무**: 인사(HR). 1차 탐색에서는 총무·사무행정도 함께 봤으나 2026-10-28 팀 결정으로 범위에서 제외
  - **역량 체계**: 인사 9개 분야 (아래 '범위와 역량 체계' 참고)
  - **숙련도**: Level 1 ~ Level 2 (입문·초급)
  - **연계 교육과정**: 초기 3대 공공 API 30개 강좌로 시작 → 현재 인사 범위 확정 217건(공공 API + 6개 교육기관 DB, 295건에서 오분류 29건·총무 20건·이상치 1건·검수 결과 무관 28건 제외), 통합 검색용 8,645건
- **최종 목표**: 기업 HR 담당자가 직무별 필수 역량을 파악하고, 적합한 교육과정을 선택할 수 있도록 교육 추천 기초 자료 및 대시보드 구축

## 현재 구성과 실행 방법 (2026-10-29)

| 구분 | 파일 | 실행 |
| :--- | :--- | :--- |
| **고객 서비스** (v2.1) | `customer_dashboard/streamlit_customer.py` | `streamlit run app.py` |
| **발표 자료** | `presentation/index.html` (배포: https://hr-edu-map.vercel.app) | 브라우저로 열기 |
| 내부 분석 대시보드 | `app/streamlit_integrated.py` | `streamlit run app/streamlit_integrated.py` |
| 발표용 marimo 대시보드 | `app_marimo.py` → `dashboard.html` | `marimo export html app_marimo.py -o dashboard.html` |
| 1차 탐색 공개 화면 | `src/dashboard/public_app.py` | `streamlit run src/dashboard/app.py` |
| 예전 화면 | `legacy/` (HTML 고객 화면 2종, 성장 경로, 온보딩 대시보드) | `legacy/README.md` 참고 |

- **고객 서비스 흐름**: 직급 선택 → 인사 9개 분야의 업무 진단 → 부족한 업무별 추천 교육, 전체 교육 찾기, 내 학습 현황.
  교육 카탈로그 9,089개 중 제외 목록 1,292개를 뺀 7,797개를 검색·추천에 쓴다. 공식 만족도는 정보로만 보여 주고 순위에는 쓰지 않는다.
- **패키지**: `pip install -r requirements.txt`. 추천 모델(`jhgan/ko-sroberta-multitask`)은 처음 실행할 때 Hugging Face에서 내려받는다.
  모델을 못 받으면 고객 앱은 키워드(BM25) 검색으로 동작한다.
- **API 키**: 고용24 재수집에만 필요하다. `.env.example`을 `.env`로 복사해 키를 넣고, 키 파일은 커밋하지 않는다.

### 데이터를 다시 만드는 순서

```bash
# 1) 고용24 과정 최신화 (API 키 필요) → 상세 설명 보강
python scripts/refresh_work24_courses_2026.py
python scripts/enrich_work24_course_text.py
python scripts/fix_catalog_data_errors.py   # 가격·일정·시간 오류 정정 (모델 불필요)
# 2) 분야 라벨 → 제외 목록 → 업무 90개별 추천 (모델 필요)
python scripts/build_course_field_labels.py
python scripts/build_off_topic_exclusions.py
python scripts/build_hr_task_catalog.py --reuse-catalog
#    모델을 못 받는 환경에서 제외 목록만 바꿨다면: python scripts/apply_exclusions_to_task_recommendations.py
# 3) 발표 자료 (데이터 계산에 모델 필요)
python scripts/build_presentation_data.py
python scripts/build_presentation.py
```

팀원 분야 검수 결과를 바꿨다면: 구글 시트 '분야–과정 검수 시트'의 값을
`data/hr/output/recommendation/domain_mapping_review_results.csv`·`domain_mapping_cross_review_results.csv`에 저장한 뒤
`python scripts/apply_domain_review_results.py` → `python scripts/build_off_topic_exclusions.py` → 위 2)의 추천 단계를 실행한다.

### 확인용 테스트

```bash
python scripts/check_customer_no_synthetic_reviews.py   # 고객 화면에 합성 리뷰·평점이 없는지
python scripts/verify_customer_mvp.py                   # 고객 앱 단위 검증
python scripts/test_new_flow_verification.py            # 고객 앱 단계 흐름
python scripts/test_recommender_integration.py          # 추천 엔진
python scripts/test_common_loader.py                    # 데이터 로더
```

### 데이터 검증 (모델·API 불필요, 결과: `data/hr/reports/data_validation_report.md`)

```bash
python scripts/validate_catalog.py            # 가격·일정·중복·추천 결과 정합성 점검
python scripts/analyze_thin_task_supply.py    # 추천 3개를 못 채운 업무가 공급 부족인지 확인
python scripts/eda_work24_employer_2026.py    # 저장된 고용24 사업주훈련 API 응답 EDA
```

## 범위와 역량 체계 (2026-10-28 결정)

- **범위**: 인사. 총무 과정은 확정 과정에서 제외(`EXCLUDED_OUT_OF_SCOPE`, 20건)
- **기준 역량 체계**: 인사 9개 분야. 고객용 화면·팀원 검수 시트·대응표가 같은 목록을 쓴다.
- 문서마다 달랐던 역량 수(7·8·9·16개)는 서로 다른 체계가 섞여 있던 것으로, 아래처럼 정리했다.

| 예전 표기 | 정체 | 정리 |
| :--- | :--- | :--- |
| 8개(7개) 역량 코드 `COMP_*` | 데이터 분석용 코드 | 내부 분석용으로 유지. 인사 핵심 3개(HR_01·HR_02·LABOR_01), 공통 업무역량 2개(GA_01·SEC_01), 범위 밖 나머지 (`hr_scope` 컬럼) |
| 9개 역량(인사 4 + 총무 5) | 1차 탐색 때 정의 | 발표용 대시보드 탭 1~4의 1차 기록으로만 남김 |
| 9개 분야 | 인사 9개 분야 | **기준 체계** |
| 16대 직무 | 고객용 화면 데이터에 남아 있던 예전 이름표 | 삭제(실제 화면 데이터는 이미 9개 분야) |

인사 9개 분야와 NCS 대응표: `data/hr/reference/hr_domain_ncs_crosswalk.csv` (`scripts/apply_hr_scope_and_ncs_crosswalk.py`)

v2.1 고객 앱(`customer_dashboard/`)과 인사 업무 90개별 추천은 `scripts/build_off_topic_exclusions.py`의 제외 목록으로 같은 범위를 적용한다(NCS 총무 과정, 팀원 검수 '무관' 과정, 법정 안전보건교육, 마케팅·커머스 제외). 앱 화면에는 인사 9개 분야만 보인다.

| 분야 | NCS 세분류 · 능력단위 |
| :--- | :--- |
| 인사전략·인력기획 | 인사(02020201) · 인사기획 |
| 조직설계·직무분석 | 인사 · 인사기획 일부 |
| 인재채용 | 인사 · 인력채용 |
| 온보딩·직원경험 | 인사 · 인력이동관리 일부 (NCS 외 현업 확장) |
| 성과평가·목표관리 | 인사 · 인사평가 |
| 보상·급여·복리후생 | 인사 · 임금관리 |
| 인재육성·사내교육 | 인사 · 교육훈련 |
| 조직문화·사내소통 | 직접 대응 없음 (NCS 외 현업 확장) |
| 노사관계·노무 | 노무관리(02020202) |

NCS 세분류 코드는 고용24 API의 공식 `ncsCd`와 과정명으로 확인했다(02020101 총무, 02020201 인사, 02020202 노무관리).
능력단위 이름은 NCS 기반 직무기술서(2차 자료)로 확인했으며, 공식 사이트(ncs.go.kr)에서 최종 확인이 필요하다.

## 데이터 신뢰도 및 한계 (2026-10-25 검토, 10-28 갱신)

결과를 인용하기 전에 아래 사항을 확인하세요.

| 자료 | 상태 | 비고 |
| :--- | :--- | :--- |
| `data/processed/ncs_1360_units.csv`, `ncs_272_jobs.csv`, `ncs_ksa_master.csv` | **예시 데이터** | 공식 NCS 아님. 모든 직무가 레벨 1~5와 같은 문구로 된 틀. 공식 NCS 재수집 필요 |
| `data/sample/*` | **시연용 생성 데이터** | 난수로 생성(`scripts/generate_sample_dataset.py` 등) |
| `data/processed/hr_courses_detailed_295.*` (팀원 295건) | 일부 값 정정 | 만족도·교육시간·인프런 수강료는 기본값/고정값이어서 결측 처리(`scripts/fix_295_imputed_values.py`). 실제 평점은 국민내일배움카드 72건만 보유 |
| `data/hr/mapped/education_*_mapping.csv` | 재생성 | 영문 약어(oa, pm, mbo 등) 부분 일치 오류 수정, 휴넷 '접속 차단' 페이지 1,331건 제거 후 재생성 |
| 고용24 사업주훈련 수강료 | 표시 정정 | 0원 44건은 수강비 값이며 실제 훈련비는 26,730원~60만 원 → '무료'가 아님 (`scripts/fix_work24_fee_and_scope.py`) |
| 확정 과정 범위 | 29건 제외 | 키워드 오분류: '농협은행 자산관리 전문역 양성'(금융 자산관리) 1건, 휴넷 '2026 안전보건교육(채용 시)' 28건('채용 시'가 '채용'에 걸림). 고객 화면의 인재채용 과정은 48개 → 20개 |
| 인사 범위 적용 | 20건 제외 | 비품·자산관리 역량 또는 고용24 NCS 총무(02020101) 과정 |
| 팀원 검수 반영 | 28건 제외 | 팀원 4명이 183개 과정의 분야를 검수(183개 모두 입력). '인사 업무와 무관' 판정 과정 제외. 남은 확정 과정 217건 = 인사 핵심 158 + 공통 업무역량 59 (`scripts/apply_domain_review_results.py`) |
| NCS 코드 | 정정 | `competencies.csv`의 `02020201_16v3` 등은 세분류 코드를 능력단위로 잘못 적은 값. 확인된 세분류만 남김. `ncs_code_consistency_report.md`의 코드표는 인사·총무가 뒤바뀌어 있음 |
| 추천 점수 | 공식 변경 | 실제 만족도가 없어 `(0.50 × 의미 유사도 + 0.35 × BM25) ÷ 0.85`로 계산 |
| 과정→분야 자동 분류 | **측정 완료** | 팀원 검수 기준 정밀도 91.7%(88/96), 재현율 89.8%(88/98), 교차검수 κ=0.88(20쌍). 고객 화면은 키워드 대신 검수 결과 사용 (`data/hr/reports/domain_review_report.md`) |
| 검색·추천 순위 정확도 | **미측정** | 팀원 블라인드 평가 시트가 비어 있음. Hit@5 등 기존 수치는 '제목에 단어 포함=정답' 기준의 참고치 |
| 군집(K-Means k=8) | 약한 군집 | 실루엣 점수 약 0.04로 주제 경계가 뚜렷하지 않음 |

## 2. 4단계 프로세스 아키텍처
1. **직무·역량 선정 및 데이터 수집**: 1차로 인사·총무의 요구역량 9개 정리(최종 범위는 인사 9개 분야), 3대 공공 API 실시간 30개 강좌 수집
2. **데이터 전처리 및 EDA**: 교육 키워드 표준화, 중복 제거, 직무별 역량·교육 분포 및 수강료/시수 분석
3. **교육 매핑 및 추천 기준 설정**: 역량별 교육 연결, 적합도 점수(Suitability Score) 계산, 직무별 Top 3 추천
4. **대시보드 및 리포트 완성**: 직무별 추천 교육 Top 3, 교육 공백(Skill Gap) 분석, 한계점 및 향후 확장 방향(HRD 추가, L3~L5 심화, 평생교육원 연계) 정리

## 3. 실행 방법 (1차 탐색 단계)

현재 고객 서비스·발표 자료 실행은 위 '현재 구성과 실행 방법'을 보세요. 아래는 1차 탐색(공공 API 30개 강좌) 당시 명령입니다.

```bash
# 1. 의존성 설치 및 가상환경 실행
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 3대 공공 API 실시간 수집 & 전처리 파이프라인 가동 (30개 강좌)
.venv\Scripts\python.exe scripts/collect_and_process_hr_data.py

# 3. 1차 탐색 공개 화면 실행 (루트 app.py는 현재 고객 서비스를 실행함)
.venv\Scripts\streamlit.exe run src/dashboard/app.py
```

앱 자체는 API 키 없이 실행할 수 있습니다.

## 주요 파일

- `src/dashboard/public_app.py`: 공통 공개 화면과 필터·설계 로직
- `src/dashboard/app.py`: 1차 탐색 공개 화면 실행 진입점 (루트 `app.py`는 고객 서비스 `customer_dashboard/streamlit_customer.py`를 실행)
- `src/collectors/edu_collector.py`: 별도 API 수집 인터페이스; 현재 화면과 연결되지 않음
- `data/sample/`: 시연 자료. 실제 개설·학점 인정 여부를 보장하지 않음
- `scripts/check_public_dashboard.py`: 메뉴·필터·시간 계산 검증

```bash
uv run python -m scripts.check_public_dashboard
```

## 실제 자료 연결 전 확인 사항

1. 각 API의 최신 명세와 응답 항목, 이용 조건을 확인합니다.
2. 수집일·기준 기간·원문 URL·지역 범위와 함께 원본을 보관합니다.
3. 시간대 미확인 자료를 주간으로 처리하지 않습니다. 판정 가능한 강좌만 분모로 사용하고 미확인 비율을 공개합니다.
4. 산업 수요 분석에는 채용·기업 조사 등 수요 측 근거를 보완합니다.
5. 영상 길이·평가 유무·수료율이 없으면 해당 회귀분석은 수행하지 않습니다.
6. 설계 결과는 초안이며 대학 개설, 학점·학위·자격 인정과 구분합니다.

API 수집을 별도로 사용할 때만 `.env.example`을 `.env`로 복사해 키를 설정합니다. 키는 커밋하지 않습니다.

## 배포

- 발표 자료: `presentation/`을 Vercel 정적 호스팅으로 배포 (https://hr-edu-map.vercel.app, `presentation/.vercelignore`로 `src/` 제외).
- 고객 서비스: Python/Streamlit 실행을 지원하는 호스팅에서 루트 `app.py`를 시작 파일로 사용합니다(`.streamlit/config.toml`). 데모 공개 시 모든 화면과 다운로드의 시연 표시를 유지해야 합니다. 실제 서비스 전환 전에는 실제 자료 검증·모집 정보 갱신·모바일 접근성 점검이 필요합니다.

## 팀 자료실·분석실 (추가)

홈의 ‘팀 자료실·분석실 열기’에서 다음 작업을 할 수 있습니다.

- 3종 샘플 원자료 선택 또는 CSV 업로드(UTF-8/CP949/EUC-KR, 최대 20MB)
- 코드의 앞자리 0 보존, 열별 검색, 범주 필터, 필터 결과 전체 다운로드
- 결측률·고유값·전체 행 중복 수 확인
- 필터 결과의 그룹별 건수·평균·중앙값·합계 비교 및 결과 다운로드
- 출처·기간·작성자·분석 조건·검토 메모를 JSON으로 내보내기

숫자로 변환되지 않는 값은 수치 집계에서 제외하고 건수를 표시합니다. 비율의 평균은 동일 행 가중치이므로 수료율을 집계할 때 분모를 반영한 별도 분석이 필요합니다. 그래프는 상위 30개 그룹, 화면 원자료는 1,000행까지 표시하며 다운로드는 전체 필터 결과를 포함합니다.

업로드와 메모는 접속 세션에 한정됩니다. 팀원 간 자동 동기화·공동 편집·영구 저장은 구현되지 않았습니다. 자료와 분석 기록을 내려받아 팀 공유 폴더 또는 GitHub Issue에서 공유하세요. 현재 localhost 주소는 다른 컴퓨터에서 접속할 수 없으며 외부 공유에는 별도 호스팅이 필요합니다.

---

## [STEP 4 MVP] NCS 인사·총무 교육 데이터 대시보드 (1차 탐색 단계)

### 1. 대시보드 목적
- **STEP 4 탐색적 데이터 분석(EDA) 결과 시각화**: 공공 API 및 7개 민간/공공 플랫폼에서 수집·통합된 553건(확정 295건)의 직무교육 데이터 구조를 직관적으로 파악합니다.
- **다차원 교육과정 탐색(Course Explorer)**: 직무, 플랫폼, 난이도, 수강료 필터 및 키워드 검색을 통해 실무 교육과정을 실시간으로 조회하고 공식 URL로 연결합니다.
- **NCS KSA 역량 매핑 구조 분석**: 역량 코드 7개(분석용, 범위는 `hr_scope` 컬럼 참고)(지식·기술·태도)과 교육 공급 현황의 연계 상태를 시각화합니다. (※ STEP 5 추천 알고리즘은 포함하지 않음)

### 2. 실행 방법
```bash
# 가상환경 활성화 후 실행
streamlit run app/streamlit_step4.py
```
브라우저에서 `http://localhost:8501` (또는 터미널에 표시된 포트)로 접속합니다.

### 3. 사용 데이터
- `data/hr/output/integration/hr_integrated_candidates.csv`: 통합 전체 후보 마스터 (553건)
- `data/hr/output/integration/hr_integrated_verified.csv`: 직무 적합 확정 과정 (295건)
- `data/hr/output/integration/hr_mapping_verified.csv`: NCS 핵심 역량 매핑 관계 (295행)
- `data/hr/processed/competencies.csv`: 분석용 역량 코드 마스터 (`hr_scope`, 확인된 NCS 세분류 코드)
- `data/hr/processed/jobs.csv`: NCS 직무 분류 마스터

### 4. 주요 화면 구성
- **TAB 1. 교육 데이터 현황**: 상단 4대 핵심 KPI 카드(전체/확정/검토/제외), 수집 플랫폼별 막대그래프, 상위 직무군 파이차트, 세부 직무 가로막대, 출처 비중(API vs SQLite).
- **TAB 2. 교육과정 탐색**: 직무군/세부직무/플랫폼/난이도/검색어 다차원 실시간 필터링, 정렬 가능한 인터랙티브 테이블, 상세 페이지 바로가기 링크(URL), 필터 결과 CSV 다운로드.
- **TAB 3. 직무역량 KSA 분석**: KSA 유형별(지식/기술/태도) 도넛차트, 역량 코드별 연결 교육과정 수, 역량 코드 마스터 명세표.

### 5. 데이터 해석 시 주의사항 (Disclaimers)
1. **역량 공급 지표의 의미**: 본 대시보드의 역량별 교육 연결 건수는 '교육 시장의 공급 현황'을 측정한 것이며, 실제 재직자의 역량 부족 수준이나 전체 시장의 결핍을 의미하지 않습니다.
2. **공식 NCS와 프로젝트 가설 구분**: '애자일 프로젝트 관리' 등 일부 항목은 최신 산업 수요를 반영하여 프로젝트 자체 가설로 설정된 연계 항목입니다.
3. **수강료 및 교육시간**: 0원 수강료는 국비 전액 환급 또는 지자체 무료 과정이며, 미기재 과정은 무료가 아닌 별도 상담 과정으로 구분하여 표기됩니다.

