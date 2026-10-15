"""
kimsaemi/edu-skill-gap 프로젝트 메인 Streamlit 진입점 (Root app.py)
- 기본 진입: 고객용 역량 자기점검 및 맞춤 교육 추천 서비스 (app/streamlit_customer.py)

실행 안내:
1. [고객용 추천 서비스 (MVP)]
   streamlit run app/streamlit_customer.py
   (또는 루트에서: streamlit run app.py)

2. [내부 분석용 통합 대시보드 (10개 분석 탭)]
   streamlit run app/streamlit_integrated.py

3. [구버전 표본 대시보드 (STEP 4 레거시)]
   streamlit run app/streamlit_step4.py
"""

import sys
from pathlib import Path
import runpy

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 기본 실행 진입점을 최신 고객용 대시보드 전용 폴더의 화면으로 지정
CUSTOMER_APP_PATH = ROOT_DIR / "customer_dashboard" / "streamlit_customer.py"

if __name__ == "__main__":
    runpy.run_path(str(CUSTOMER_APP_PATH), run_name="__main__")
