# 교육 데이터 통합 및 전처리 파이프라인 가이드

본 문서는 `edu-skill-gap` 프로젝트에 신규 교육기관의 SQLite DB를 수납하고, 공통 스키마로 표준화하여 NCS·KSA 추천 풀을 생성하는 파이프라인 명세서입니다.

## 1. 디렉터리 아키텍처

```text
data/hr/
├── raw/external_courses/      # 6개 교육기관 원본 SQLite DB (읽기 전용 무손실 보존)
├── processed/                 # 표준화 및 마스터 통합 데이터 (.csv, .db)
├── mapped/                    # NCS 직무 및 KSA 역량 매핑 관계
└── reports/                   # 데이터 품질, 중복, 매핑 분석 보고서
```

## 2. 파이프라인 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 신규 DB 통합 및 표준화 파이프라인 전과정 일괄 실행
python scripts/integrate_external_courses_pipeline.py

# 3. 대시보드 실행
streamlit run app/streamlit_step4.py
```
