# 예전 화면 (legacy)

현재 서비스와 발표에는 아래 파일을 씁니다.

- 고객 서비스: `customer_dashboard/streamlit_customer.py` (Streamlit, 인사 9개 분야·업무 90개 기반 추천)
- 발표 자료: `presentation/index.html` (`scripts/build_presentation_data.py` → `scripts/build_presentation.py`로 생성)

이 폴더의 화면은 v2.1 고객 앱 이전에 만든 것으로, 2026-10-29에 저장소 최상위에서 옮겼습니다.
지우지 않은 이유는 발표 이력과 비교 자료로 남기기 위해서입니다. 화면마다 맨 위에 '예전 버전' 안내가 있습니다.

| 파일 | 내용 | 다시 만들기 |
| :--- | :--- | :--- |
| `hr_career_platform_v2.html` | 3단계 안내형 고객 화면 | `python scripts/build_customer_platform_data.py` |
| `hr_career_platform_easy.html` | 쉬운 버전 고객 화면 | 위와 같음 |
| `hr_career_growth_path.html` | 직급별 성장 경로 화면 | 정적 파일 |
| `career_onboarding_dashboard.py` / `.html` | 온보딩·승급 내비게이터 (marimo) | 저장소 최상위에서 `marimo export html legacy/career_onboarding_dashboard.py -o legacy/career_onboarding_dashboard.html` |

과정 데이터는 2026-10-28 확정 과정(`data/hr/output/recommendation/hr_recommendation_candidates.csv`, 인사 범위·팀원 검수 반영 217건) 기준입니다.
근거 없는 과정명·연봉·효과 수치는 이미 뺐습니다. 직급별 역할·과제·조언은 팀이 만든 예시입니다.
