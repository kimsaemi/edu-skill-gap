@echo off
chcp 65001 > nul
echo ========================================================
echo [최신 검증판] NCS 기반 인사 직무 분석 통합 대시보드 (14개 탭)
echo ========================================================
echo.
echo 잠시만 기다려주세요... 웹 브라우저가 자동으로 열립니다.
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\streamlit.exe" (
    ".venv\Scripts\streamlit.exe" run app_integrated_latest.py
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run app_integrated_latest.py
) else (
    streamlit run app_integrated_latest.py
)

pause

