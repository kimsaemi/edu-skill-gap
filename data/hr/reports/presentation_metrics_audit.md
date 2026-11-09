# 발표 지표 종합 감사 보고서 (Presentation Metrics Audit)

> **기준일**: 2026-11-09  
> **대상 저장소**: `kimsaemi/edu-skill-gap` (`claude/feedback-stage1` 브랜치)  
> **대상 범위**: 인사 9개 분야 · 실무 과업 90개 · 정제 교육 카탈로그 9,075개

---

## 1. 발표 지표 전수 감사 목록

| 지표 이름 | 화면 표기 값 | 분자 | 분모 | 평가·계산 대상 | 계산식 (코드 위치) | 원본 파일 | 데이터 생성일 |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- | :--- |
| **정제 카탈로그 과정 수** | 9,075개 | 9,075 | - | 통합 교육과정 전수 | `len(df)` (`build_presentation_data.py:catalog_kpis`) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **추천 제외 과정 수** | 1,377개 | 1,377 | - | 인사 무관·자격증 등 제외 | `len(df_off)` (`build_presentation_data.py:catalog_kpis`) | `off_topic_exclusions.csv` | 2026-11-04 |
| **추천 후보 풀** | 7,698개 | 7,698 | - | 1단계 추천 후보군 | `9,075 - 1,377` (UID 고유성 검증 완료) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **참여 교육기관 수** | 239개 | 239 | - | 카탈로그 내 교육기관 | `df["provider"].nunique()` (`build_presentation_data.py:catalog_kpis`) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **추천 커버리지** | 98.5% | 266 | 270 | 과업(90개) × 수준(3개) 슬롯 | `(270 - lt3) / 270 * 100` (`build_presentation_data.py:monitor_section`) | `task_course_recommendations_90_reranked.csv` | 2026-11-04 |
| **1위 의미 유사도 중앙값** | 68.9점 | - | 90 | 90개 과업별 1순위 유사도 | `med(top1_scores)` (`build_presentation_data.py:recommend_section`) | `task_course_recommendations_90_reranked.csv` | 2026-11-04 |
| **제목만 있는 강좌 비율** | 전체 19.7% / Top3 2.5% | 1,791 / 20 | 9,075 / 803 | 설명 부실 강좌 비율 | `title_only / total * 100` (`build_presentation_data.py:catalog_kpis`) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **반복 추천 점유율 (Top3)** | 14.3% | 115 | 803 | 5회 이상 중복 추천 과정 (10개) | `sum(reused5_counts) / 803 * 100` (`build_presentation_data.py`) | `task_course_recommendations_90_reranked.csv` | 2026-11-04 |
| **기관 쏠림 (KPC)** | Top3 37.4% (카탈로그 16.7%) | 300 / 1,513 | 803 / 9,075 | 한국생산성본부 점유율 | `kpc_top3 / 803 * 100` (`build_presentation_data.py:monitor_section`) | `task_course_recommendations_90_reranked.csv` | 2026-11-04 |
| **고용24 운영 비율** | 97.1% | 544 | 560 | 고용24 개강일 유효 과정 | `open_courses / 560 * 100` (`build_presentation_data.py:monitor_section`) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **H1 난이도 공급 비율** | 입문 78.4%, 중급 17.7%, 고급 3.9% | 4,400 / 996 / 219 | 5,615 | 난이도 표기 과정 (미기재 3,460개) | `n_lvl / 5,615 * 100` (`build_presentation_data.py:difficulty_section`) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **H1 중급 유료 가격 중앙값** | 638,250원 | - | 245 | 인사 분야 중급 유료 강좌 | `median(paid_price)` (`build_presentation_data.py:robust_section`) | `education_courses_search_cleaned.parquet` | 2026-11-04 |
| **H2 노무·보상 강좌 수** | 노무 256개, 보상 249개 | 256 / 249 | - | 임베딩 유사도 0.60 이상 강좌 | `sum(sim >= 0.60)` (`build_presentation_data.py:domain_supply_section`) | `embeddings_ko_sroberta_all.npy` | 2026-11-04 |
| **H3 카탈로그 만족도 보유율** | 4.0% | 367 | 9,075 | 공식 HRD 만족도 매칭 강좌 | `scored / 9,075 * 100` (`build_presentation_data.py:satisfaction_section`) | `hrd_course_satisfaction.parquet` | 2026-11-04 |
| **사람 평가 1차 (A: 판정건)** | 52.7% (부분적합 87.3%) | 29 (48) | 55 | 팀원 4명, 30개 항목 2중 판정 | `fit / n * 100` (`apply_precision_eval_results.py`) | `precision_eval_results.csv` | 2026-11-09 |
| **사람 평가 1차 (B: 항목합의)**| 36.7% | 11 | 30 | 30개 항목 중 보수적 판정 | `fit_consensus / 30 * 100` (`apply_precision_eval_results.py`) | `precision_eval_results.csv` | 2026-11-09 |
| **사람 평가 1차 (C: 일치도)**| 일치율 56.7%, κ=0.343 | 17 | 30 | 두 평가자 모두 판정한 30쌍 | `agree / pairs * 100`, `cohen_kappa_score` | `precision_eval_results.csv` | 2026-11-09 |
| **사람 평가 2차 (A: 판정건)** | 67.3% (부분적합 100%) | 35 (52) | 52 | 1차와 동일 업무 10개 재평가 | `fit / n * 100` (`apply_precision_eval_results.py`) | `precision_eval_round2_results.csv` | 2026-11-09 |
| **사람 평가 2차 (B: 항목합의)**| 50.0% | 14 | 28 | 28개 유효 항목 (2개 양자판단불가) | `fit_consensus / 28 * 100` (`apply_precision_eval_results.py`) | `precision_eval_round2_results.csv` | 2026-11-09 |
| **사람 평가 2차 (C: 일치도)**| 일치율 56.7%, κ=0.244 | 17 | 30 | 두 평가자 모두 판정한 30쌍 | `agree / pairs * 100`, `cohen_kappa_score` | `precision_eval_round2_results.csv` | 2026-11-09 |
| **사람 평가 홀드아웃 (A: 판정건)**| 74.5% (부분적합 94.5%) | 41 (52) | 55 | 규칙 제작 시 미사용 업무 10개 | `fit / n * 100` (`apply_precision_eval_results.py`) | `precision_eval_holdout_results.csv` | 2026-11-09 |
| **사람 평가 홀드아웃 (B: 항목합의)**| 60.7% | 17 | 28 | 28개 유효 항목 (2개 양자판단불가) | `fit_consensus / 28 * 100` (`apply_precision_eval_results.py`) | `precision_eval_holdout_results.csv` | 2026-11-09 |
| **사람 평가 홀드아웃 (C: 일치도)**| 일치율 73.3%, κ=0.457 | 22 | 30 | 두 평가자 모두 판정한 30쌍 | `agree / pairs * 100`, `cohen_kappa_score` | `precision_eval_holdout_results.csv` | 2026-11-09 |

---

## 2. 화면 값과 원본 계산 값 대조 및 불일치 정정 내역

| 항목 | 기존 화면/문서 표기 | 실제 계산/원본 값 | 원인 및 정정 조치 |
| :--- | :--- | :--- | :--- |
| **발표 메타 태그** | "직무교육 과정 약 9,100개" | **정제 카탈로그 9,075개** | `template.html:3` 메타 태그 정확한 수치로 수정 완료 |
| **README 카탈로그 수치** | "통합 검색용 8,645건", "제외 1,326건", "추천 대상 7,749건" | **카탈로그 9,075개, 제외 1,377개, 추천 후보 7,698개** | 고용24 2026년 교체(130건→560건) 전 구버전 잔재. README 최신 수치로 동기화 완료 |
| **01장 목표 표 사람 평가** | `<span class="pill pend">측정 예정</span>` | **74.5% (홀드아웃 검증)** | 홀드아웃 평가 완료 결과(74.5%)를 바인딩하도록 템플릿 정정 완료 |
| **고용24 운영 비율** | 기존 하드코딩 문맥상 97.7% | **97.1% (544/560)** | data.json 동적 바인딩 및 정확한 분모(560) 반영 |

---

## 3. 과정 수 정의 및 데이터 흐름 체계

```
[원천 수집 데이터 (공공 API + 6개 교육기관 DB)]
               │
               ▼
[정제 카탈로그 전체: 9,075개] (education_courses_search_cleaned.parquet)
       │                        │
       ├────────────────────────┼────────────────────────┐
       ▼                        ▼                        ▼
[추천 제외 목록: 1,377개]   [추천 후보군: 7,698개]     [고객 대시보드 표출: 5,059개]
(off_topic_exclusions.csv) (9,075 - 1,377, 중복 없음) (동일 과정명 회차 통합 기준)
```

- **9,075건 (정제 카탈로그)**: 텍스트 노이즈, 홍보 상용구, 중복 등을 전처리한 단일 고유 UID 코퍼스 전수.
- **1,377건 (무관 제외)**: IT/개발 실습, 외국어 시험, 단순 자격증, 유아/교양 등 인사 직무와 무관한 과정.
- **7,698건 (추천 후보군)**: 9,075건에서 1,377건을 순수 차감한 실제 임베딩 및 BM25 추천 탐색 모수.
- **8,645건 (과거 수치)**: 2024년 수집 당시 고용24 구버전 130건을 포함하던 초창기 코퍼스 수치 (커밋 `465f994`에서 2026년 최신 560건으로 확장 교체되면서 9,075건으로 최종 확정됨).
- **5,059건 (대시보드 그룹화)**: 동일 교육기관의 동일 명칭 차수/회차 과정을 단일 카드로 묶어 표시할 때의 고유 강좌 수.

---

## 4. 참고 대시보드(언더스코어 × MBC 《PD수첩》) 벤치마킹 분석

- **참고 프로젝트**: 「AI의 등장 이후 고용 시장은 어떻게 변화했을까?」 ([https://korean-labor-market-after-ai.vercel.app](https://korean-labor-market-after-ai.vercel.app))

| 구분 | 참고 대시보드 기법 | 본 프로젝트 발표 반영 내용 | 미반영 사유 및 향후 과제 |
| :--- | :--- | :--- | :--- |
| **1. 결론 우선 제시** | 상단에 명확한 발견 문장과 종합 KPI 카드 배치 | 첫 화면에 2개 요약 결론 문단 및 목표·분모·기준일 명시 4개 KPI 카드 배치 완료 | - |
| **2. 외생 변수 / 왜곡 점검** | 직종 분류 기준 변화, 플랫폼 편향 등 교차 점검 | GSEEK/휴넷 제외 시 초급·중급 비율 변화(H1), 유사도 임계치(0.55~0.65) 변화 검증(H2), 기관 쏠림 분해 완료 | - |
| **3. 한계점의 명시적 번호화** | '분석 시 유의사항'을 01~05 카드로 독립 분리 | '읽을 때 알아 둘 것' 섹션에 난이도 미표기, 자동 매핑 오차, 기관 편향, 평가자 독립성 한계 명시 완료 | - |
| **4. 불확실성 시각화** | 점추정치 대신 신뢰구간(Confidence Interval) 에러바 표기 | 사람 평가 Precision@3에 95% Wilson CI 및 보수적 클러스터 부트스트랩 에러바 SVG 구현 완료 | - |
| **5. 대조군 위약 검정** | Placebo test (무작위 배치 대비 효과 비교) | **미반영** | 무작위 추천 대조군과의 A/B 블라인드 평가는 2단계 확장 과제로 설정 |
| **6. 선행 연구 메타 분석** | 국내외 노동시장 선행 연구 문헌과의 수치 비교 | **미반영** | 교육공학/HRD 추천 분야 선행 학술 벤치마크 정리는 차기 고도화 보고서에서 다룸 |
| **7. 베이스라인 모델 비교** | 전통적 모형 vs 신규 모형 정량 비교 (예: BM25 vs AI) | **부분 반영** | 하이브리드 엔진 내 결합 비중(의미 50%, BM25 35%)은 수립하였으나, 순수 BM25 단독 오프라인 평가는 추후 비교 과제로 분리 |

