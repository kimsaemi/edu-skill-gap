"""
최신 결과(PR #12: 2026-10-31 데이터 검증 탭 14 포함)가 반영된 내부 분석용 Streamlit 대시보드 진입점
- 실행 방법:
  1) .\.venv\Scripts\streamlit.exe run app_integrated_latest.py
  2) 또는 '실행_통합분석_대시보드.bat' 더블클릭
"""

import sys
from pathlib import Path
import runpy

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 최신 탭 14가 탑재된 내부 분석 대시보드 실행
INTEGRATED_APP_PATH = ROOT_DIR / "app" / "streamlit_integrated_latest.py"

if __name__ == "__main__":
    runpy.run_path(str(INTEGRATED_APP_PATH), run_name="__main__")

