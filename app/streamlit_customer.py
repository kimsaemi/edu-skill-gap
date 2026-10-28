"""
app/streamlit_customer.py (하위 호환성 포워더)
- 고객용 대시보드가 'customer_dashboard/' 전용 폴더로 공식 분리되었습니다.
- 기존 실행 경로 호환성을 위해 'customer_dashboard/streamlit_customer.py'로 실행을 자동 위임합니다.
"""

from pathlib import Path
import runpy
import sys

APP_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = APP_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

TARGET_APP = WORKSPACE_ROOT / "customer_dashboard" / "streamlit_customer.py"

if __name__ == "__main__":
    runpy.run_path(str(TARGET_APP), run_name="__main__")
