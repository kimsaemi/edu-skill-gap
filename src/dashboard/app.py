import importlib.util
from pathlib import Path

# NCS 기반 인사·총무 교육 대시보드 (STEP 4 MVP) 대시보드 진입점
app_path = Path(__file__).resolve().parents[2] / "app" / "streamlit_step4.py"
spec = importlib.util.spec_from_file_location("streamlit_step4", str(app_path))
step4_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step4_mod)

if __name__ == "__main__":
    step4_mod.main()
