"""
최신 결과(PR #12: 2026-10-31 데이터 검증)가 반영된 고객용 Streamlit 대시보드 메인 진입점
- 실행 방법:
  1) .\.venv\Scripts\streamlit.exe run app_latest.py
  2) 또는 '실행_고객용_대시보드.bat' 더블클릭
"""

import sys
from pathlib import Path
import runpy

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 최신 검증된 고객용 대시보드 실행
CUSTOMER_APP_PATH = ROOT_DIR / "customer_dashboard" / "streamlit_customer_latest.py"

if __name__ == "__main__":
    runpy.run_path(str(CUSTOMER_APP_PATH), run_name="__main__")
