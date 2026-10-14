import runpy
from pathlib import Path

# NCS 기반 인사·총무 교육 통합 대시보드 (탭 10개) 메인 진입점
# 기존 STEP 4 MVP 대시보드는 app/streamlit_step4.py 로 그대로 남아 있습니다.
runpy.run_path(str(Path(__file__).resolve().parent / "app" / "streamlit_integrated.py"), run_name="__main__")
