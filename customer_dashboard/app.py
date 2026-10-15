"""
고객용 대시보드 메인 진입점 (customer_dashboard/app.py)
- 실행 명령어: streamlit run customer_dashboard/app.py
- 또는: streamlit run customer_dashboard/streamlit_customer.py
"""

from pathlib import Path
import runpy
import sys

CUSTOMER_DASHBOARD_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = CUSTOMER_DASHBOARD_DIR.parent

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

MAIN_SCRIPT = CUSTOMER_DASHBOARD_DIR / "streamlit_customer.py"

if __name__ == "__main__":
    runpy.run_path(str(MAIN_SCRIPT), run_name="__main__")
