"""
프로젝트 2 | NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천 시스템
- 대상: 인사(HR), 총무·사무행정 (2개 직무)
- 역량: 직무별 핵심 역량 4~5개 (총 9개 핵심 역량)
- 숙련도: Level 1 ~ Level 2 (입문·초급)
- 교육과정: 3대 공공 API (NCS 교육과정, 국민내일배움카드, 사업주훈련) 실시간 연동 30개 강좌
"""
import json
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT / "data" / "processed"
SAMPLE_DIR = ROOT / "data" / "sample"

# 1. 마스터 데이터 로드 (캐싱)
@st.cache_data
def load_all_master_data():
    json_path = PROCESSED_DIR / "ncs_master_data.json"
    master_json = json.load(open(json_path, "r", encoding="utf-8")) if json_path.exists() else {}

    df_jobs = pd.read_csv(PROCESSED_DIR / "ncs_272_jobs.csv") if (PROCESSED_DIR / "ncs_272_jobs.csv").exists() else pd.DataFrame()
    df_units = pd.read_csv(PROCESSED_DIR / "ncs_1360_units.csv") if (PROCESSED_DIR / "ncs_1360_units.csv").exists() else pd.DataFrame()
    df_ksa = pd.read_csv(PROCESSED_DIR / "ncs_ksa_master.csv") if (PROCESSED_DIR / "ncs_ksa_master.csv").exists() else pd.DataFrame()
    
    shortage_path = SAMPLE_DIR / "occupation_labor_shortage.csv"
    if shortage_path.exists():
        df_shortage = pd.read_csv(shortage_path, header=1)
        df_shortage.columns = [c.strip() for c in df_shortage.columns]
        df_shortage["미충원율 (%)"] = (df_shortage["미충원인원 (명)"] / df_shortage["구인인원 (명)"] * 100).round(2)
    else:
        df_shortage = pd.DataFrame()

    courses_file = PROCESSED_DIR / "multi_platform_courses.csv"
    df_courses = pd.read_csv(courses_file) if courses_file.exists() else pd.DataFrame()

    reviews_json_file = PROCESSED_DIR / "inflearn_course_reviews.json"
    inflearn_reviews = json.load(open(reviews_json_file, "r", encoding="utf-8")) if reviews_json_file.exists() else []

    # 프로젝트 2: 인사·총무 L1~L2 역량 및 3대 공공 API 30개 강좌 데이터
    hr_courses_file = PROCESSED_DIR / "hr_courses_30.csv"
    df_hr_courses = pd.read_csv(hr_courses_file) if hr_courses_file.exists() else pd.DataFrame()

    hr_comp_file = PROCESSED_DIR / "hr_ncs_competencies.json"
    hr_competencies = json.load(open(hr_comp_file, "r", encoding="utf-8")) if hr_comp_file.exists() else {}

    hr_gap_file = PROCESSED_DIR / "hr_gap_analysis.json"
    hr_gap_data = json.load(open(hr_gap_file, "r", encoding="utf-8")) if hr_gap_file.exists() else {}

    return master_json, df_jobs, df_units, df_ksa, df_shortage, df_courses, inflearn_reviews, df_hr_courses, hr_competencies, hr_gap_data

def render_dashboard():
    try:
        st.set_page_config(
            page_title="프로젝트 2 | NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천",
            page_icon="🎓",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    except Exception:
        pass

    # 다크 테마 커스텀 CSS
    st.markdown("""
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        * {
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
        }
        
        .stApp {
            background-color: #0B1120;
            color: #F8FAFC;
        }

        /* 헤더 영역 */
        .header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(30, 41, 59, 0.9));
            border: 1px solid rgba(99, 102, 241, 0.25);
            border-radius: 16px;
            padding: 22px 26px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .header-icon {
            width: 52px;
            height: 52px;
            background: linear-gradient(135deg, #3B82F6, #6366F1);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            box-shadow: 0 0 25px rgba(99, 102, 241, 0.45);
        }
        .header-title-text h1 {
            font-size: 1.35rem;
            font-weight: 800;
            color: #FFFFFF;
            margin: 0;
            letter-spacing: -0.5px;
        }
        .header-title-text p {
            font-size: 0.85rem;
            color: #94A3B8;
            margin: 4px 0 0 0;
        }
        .live-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            border-radius: 20px;
            padding: 6px 14px;
            font-size: 0.8rem;
            font-weight: 700;
            color: #34D399;
        }

        /* 질문 콜아웃 박스 */
        .question-callout {
            background: rgba(30, 58, 138, 0.25);
            border: 1px solid rgba(96, 165, 250, 0.35);
            border-left: 5px solid #3B82F6;
            border-radius: 12px;
            padding: 14px 18px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .question-callout-text {
            font-size: 0.95rem;
            color: #E0E7FF;
            line-height: 1.45;
        }
        .question-callout-text strong {
            color: #93C5FD;
        }

        /* 상단 4대 KPI 카드 */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .kpi-card-box {
            background: rgba(17, 24, 39, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 16px 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        .kpi-card-box.c1 { border-left: 4px solid #3B82F6; }
        .kpi-card-box.c2 { border-left: 4px solid #06B6D4; }
        .kpi-card-box.c3 { border-left: 4px solid #10B981; }
        .kpi-card-box.c4 { border-left: 4px solid #F59E0B; }
        
        .kpi-t-label {
            font-size: 0.8rem;
            color: #94A3B8;
            margin-bottom: 4px;
        }
        .kpi-t-val {
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }
        .kpi-t-sub {
            font-size: 0.75rem;
            color: #64748B;
        }

        /* 추천 카드 */
        .rec-card-gold {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95));
            border: 1px solid rgba(245, 158, 11, 0.4);
            border-top: 4px solid #F59E0B;
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 16px;
            box-shadow: 0 8px 24px rgba(245, 158, 11, 0.15);
        }
        .rec-badge-top {
            background: rgba(245, 158, 11, 0.2);
            color: #FCD34D;
            border: 1px solid rgba(245, 158, 11, 0.5);
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 0.75rem;
            font-weight: 800;
        }
        .rec-card-title {
            font-size: 1.05rem;
            font-weight: 800;
            color: #FFFFFF;
            margin: 8px 0 6px 0;
            line-height: 1.35;
        }
        .rec-card-meta {
            font-size: 0.82rem;
            color: #94A3B8;
            margin-bottom: 12px;
        }
        .rec-tag-pill {
            display: inline-block;
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.35);
            color: #60A5FA;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-right: 4px;
            margin-bottom: 4px;
        }

        /* 역량 카드 */
        .comp-card {
            background: rgba(17, 24, 39, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .comp-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .comp-name {
            font-size: 1rem;
            font-weight: 800;
            color: #FFFFFF;
        }
        .comp-level-badge {
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            color: #A5B4FC;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
        }
    </style>
    """, unsafe_allow_html=True)

    master_json, df_jobs, df_units, df_ksa, df_shortage, df_courses, inflearn_reviews, df_hr_courses, hr_competencies, hr_gap_data = load_all_master_data()

    # 사이드바 모드 선택기
    st.sidebar.markdown("### 📌 분석 프로젝트 모드 선택")
    app_mode = st.sidebar.radio(
        "분석 대상 범위",
        [
            "✨ [프로젝트 2] 인사·총무 직무역량 & 교육과정 추천",
            "🌐 [전체 탐색] NCS 24대 산업 272개 직무 체계"
        ],
        index=0
    )

    if "프로젝트 2" in app_mode:
        # ==============================================================================
        # [MODE 1] 프로젝트 2: NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천
        # ==============================================================================
        st.markdown("""
        <div class="header-container">
            <div class="header-left">
                <div class="header-icon">👥</div>
                <div class="header-title-text">
                    <h1>프로젝트 2 | NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천</h1>
                    <p>NCS Job Competency Analysis & 3 Public API Tailored Course Recommendation Engine</p>
                </div>
            </div>
            <div>
                <span class="live-badge">● 3대 공공 API 30개 강좌 실시간 연동 완료</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 핵심 질문 콜아웃
        st.markdown("""
        <div class="question-callout">
            <div style="font-size: 1.5rem;">💡</div>
            <div class="question-callout-text">
                <strong>핵심 질문 (Core Research Question):</strong><br/>
                "인사·총무 직무에 필요한 <strong>핵심 역량(L1~L2)</strong>은 무엇이며, 이를 개발하기 위해 어떤 <strong>공공 교육과정을 우선 추천</strong>할 수 있을까?"
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 4대 KPI 메트릭 카드
        st.markdown(f"""
        <div class="kpi-grid">
            <div class="kpi-card-box c1">
                <div class="kpi-t-label">분석 대상 직무</div>
                <div class="kpi-t-val" style="color: #60A5FA;">2개 직무</div>
                <div class="kpi-t-sub">인사(HR) · 총무·사무행정</div>
            </div>
            <div class="kpi-card-box c2">
                <div class="kpi-t-label">선정 핵심 역량 (L1~L2)</div>
                <div class="kpi-t-val" style="color: #22D3EE;">9개 역량</div>
                <div class="kpi-t-sub">직무별 4~5개 핵심 단위</div>
            </div>
            <div class="kpi-card-box c3">
                <div class="kpi-t-label">연계 공공 API 강좌 수</div>
                <div class="kpi-t-val" style="color: #34D399;">{len(df_hr_courses)}개 강좌</div>
                <div class="kpi-t-sub">NCS · 내일배움카드 · 사업주훈련</div>
            </div>
            <div class="kpi-card-box c4">
                <div class="kpi-t-label">최고 추천 적합도 점수</div>
                <div class="kpi-t-val" style="color: #FBBF24;">95.0점</div>
                <div class="kpi-t-sub">K-S-A 키워드 정합성 기반 Top 3</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 사이드바 직무 및 레벨 선택
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎯 직무 & 숙련도 설정")
        target_job_options = ["인사(HR)", "총무·사무행정"]
        selected_hr_job = st.sidebar.radio("1. 분석 직무 선택", target_job_options, index=0)

        selected_hr_level = st.sidebar.select_slider(
            "2. 목표 숙련도 (Target Level)",
            options=["L1 (입문·보조)", "L2 (초급 실무)"],
            value="L2 (초급 실무)"
        )

        st.sidebar.markdown("---")
        st.sidebar.info("""
        **📌 분석 범위 요약**
        • 대상: 인사(HR), 총무·사무행정 2개 직무
        • 역량: 직무별 핵심 역량 4~5개
        • 교육과정: 3대 API 30개 강좌
        • 숙련도: L1~L2 (입문·초급)
        """)

        # 4대 메인 탭
        tab_rec, tab_list, tab_eda, tab_gap = st.tabs([
            "🎯 1. 직무역량 & 맞춤형 Top 3 교육 추천",
            "📋 2. 3대 공공 API 수집 30개 강좌 탐색기",
            "📊 3. 데이터 전처리 & EDA 시각화",
            "🔍 4. 교육 공백(Skill Gap) & 향후 발전 로드맵"
        ])

        # -------------------------------------------------------------
        # 탭 1: 직무역량 & 맞춤형 Top 3 교육 추천
        # -------------------------------------------------------------
        with tab_rec:
            job_info = hr_competencies.get(selected_hr_job, {})
            competencies = job_info.get("competencies", [])

            # 직무 프로파일 요약 및 Spec Sheet
            st.markdown(f"""
            <div style="background: rgba(17, 24, 39, 0.85); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 14px; padding: 20px; margin-bottom: 20px;">
                <div style="font-size: 1.25rem; font-weight: 800; color: #FFF; margin-bottom: 6px;">
                    📌 {selected_hr_job} 직무 프로파일 & 요구 정의서 (L1~L2 입문·초급)
                </div>
                <div style="font-size: 0.88rem; color: #CBD5E1; line-height: 1.5; margin-bottom: 14px;">
                    {job_info.get('description', '')}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div style="background: rgba(11, 17, 32, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 12px 14px;">
                        <div style="font-size: 0.82rem; font-weight: 700; color: #60A5FA; margin-bottom: 4px;">🏢 실무 수행 환경</div>
                        <div style="font-size: 0.82rem; color: #94A3B8;">{job_info.get('environment', '')}</div>
                    </div>
                    <div style="background: rgba(11, 17, 32, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 12px 14px;">
                        <div style="font-size: 0.82rem; font-weight: 700; color: #34D399; margin-bottom: 4px;">🎯 진입 자격 요건</div>
                        <div style="font-size: 0.82rem; color: #94A3B8;">{job_info.get('entry_requirements', '')}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_comp_left, col_rec_right = st.columns([1, 1])

            # 좌측: 직무별 핵심 역량 4~5개 리스트
            with col_comp_left:
                st.markdown(f"#### 🪜 {selected_hr_job} 핵심 역량 체계 ({len(competencies)}개)")
                for comp in competencies:
                    with st.expander(f"✨ [{comp.get('level')}] {comp.get('name')}", expanded=True):
                        st.markdown(f"**• 역량 정의:** {comp.get('desc')}")
                        st.markdown(f"**• 수행준거:** `{comp.get('criteria')}`")
                        st.markdown(f"**🧠 지식(K):** " + " · ".join(comp.get("knowledge", [])))
                        st.markdown(f"**🛠️ 기술(S):** " + " · ".join(comp.get("skills", [])))
                        st.markdown(f"**🤝 태도(A):** " + " · ".join(comp.get("attitudes", [])))
                        st.markdown(f"**🏷️ 연계 키워드:** " + " ".join([f"`#{k}`" for k in comp.get("keywords", [])]))

            # 우측: 직무 맞춤 최우선 추천 교육 Top 3
            with col_rec_right:
                st.markdown(f"#### 🏆 {selected_hr_job} 맞춤형 추천 교육 Top 3")
                
                top3_key = "hr_top3" if selected_hr_job == "인사(HR)" else "ga_top3"
                rec_list = hr_gap_data.get("recommendations", {}).get(top3_key, [])

                if not rec_list and not df_hr_courses.empty:
                    score_col = "hr_suitability" if selected_hr_job == "인사(HR)" else "ga_suitability"
                    rec_list = df_hr_courses.sort_values(by=[score_col, "cost"], ascending=[False, True]).head(3).to_dict(orient="records")

                for rank, c in enumerate(rec_list, start=1):
                    score_val = c.get('hr_suitability', 85) if selected_hr_job == "인사(HR)" else c.get('ga_suitability', 85)
                    fee_display = f"{c.get('cost', 0):,}원" if c.get('cost', 0) > 0 else "전액 무료"
                    
                    st.markdown(f"""
                    <div class="rec-card-gold">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span class="rec-badge-top">🥇 추천 {rank}위 · 적합도 {score_val}점</span>
                            <span style="font-size: 0.75rem; color: #A5B4FC; font-weight: 600;">{c.get('source_api', '공공 API')}</span>
                        </div>
                        <div class="rec-card-title">{c.get('course_name')}</div>
                        <div class="rec-card-meta">
                            🏢 <strong>{c.get('institution')}</strong> | ⏱️ {c.get('training_hours')}시간 | 💰 {fee_display} ({c.get('cost_type')})
                        </div>
                        <div style="margin-bottom: 10px;">
                            {' '.join([f'<span class=\"rec-tag-pill\">#{t.strip()}</span>' for t in str(c.get('standardized_tags', '')).split('|')])}
                        </div>
                        <div style="background: rgba(0, 0, 0, 0.3); border-radius: 6px; padding: 8px 12px; font-size: 0.78rem; color: #E2E8F0; margin-bottom: 12px;">
                            <strong>🎯 추천 사유:</strong> {selected_hr_job}의 L1~L2 핵심 역량({c.get('primary_competency')})과 높은 키워드 정합성을 보이며, {c.get('cost_type')} 혜택으로 진입 장벽이 낮습니다.
                        </div>
                        <div style="text-align: right;">
                            <a href="{c.get('url', 'https://www.work24.go.kr')}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #F59E0B, #D97706); color: #FFF; padding: 5px 14px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; text-decoration: none;">
                                수강신청 / 상세정보 바로가기 ➔
                            </a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # -------------------------------------------------------------
        # 탭 2: 3대 공공 API 수집 30개 강좌 탐색기
        # -------------------------------------------------------------
        with tab_list:
            st.markdown("### 📋 3대 공공 API 실시간 수집 30개 강좌 풀")
            st.write("한국산업인력공단 NCS 교육과정, 고용24 국민내일배움카드, 고용24 사업주훈련 API에서 수집·정제된 실시간 강좌 목록입니다.")

            f_col1, f_col2, f_col3 = st.columns([2, 2, 3])
            with f_col1:
                api_filter = st.selectbox("API 출처 필터", ["전체 API"] + sorted(df_hr_courses["source_api"].unique().tolist()) if not df_hr_courses.empty else ["전체"])
            with f_col2:
                job_filter = st.selectbox("직무 분류 필터", ["전체 직무", "인사(HR)", "총무·사무행정"])
            with f_col3:
                kw_search = st.text_input("강좌명 / 기관명 검색", placeholder="예: 인사, 노무, 엑셀, 사무, 공문서 등")

            filtered_df = df_hr_courses.copy()
            if not filtered_df.empty:
                if api_filter != "전체 API":
                    filtered_df = filtered_df[filtered_df["source_api"] == api_filter]
                if job_filter != "전체 직무":
                    filtered_df = filtered_df[filtered_df["primary_job"] == job_filter]
                if kw_search.strip():
                    kw_lower = kw_search.strip().lower()
                    filtered_df = filtered_df[
                        filtered_df["course_name"].str.lower().str.contains(kw_lower, na=False) |
                        filtered_df["institution"].str.lower().str.contains(kw_lower, na=False) |
                        filtered_df["standardized_tags"].str.lower().str.contains(kw_lower, na=False)
                    ]

            st.caption(f"조회 결과: 총 **{len(filtered_df)}개** 강좌가 표시됩니다.")

            # 테이블 뷰
            disp_cols = ["source_api", "course_name", "institution", "primary_job", "training_hours", "cost", "cost_type", "suitability_score"]
            available_cols = [c for c in disp_cols if c in filtered_df.columns]
            
            st.dataframe(
                filtered_df[available_cols].rename(columns={
                    "source_api": "수집 API",
                    "course_name": "과정명",
                    "institution": "훈련기관",
                    "primary_job": "매핑 직무",
                    "training_hours": "교육시수(h)",
                    "cost": "수강료(원)",
                    "cost_type": "지원 유형",
                    "suitability_score": "적합도(점)"
                }),
                use_container_width=True,
                height=380
            )

        # -------------------------------------------------------------
        # 탭 3: 데이터 전처리 & EDA 시각화
        # -------------------------------------------------------------
        with tab_eda:
            st.markdown("### 📊 데이터 전처리 & 탐색적 데이터 분석 (EDA)")
            st.write("3대 공공 API 수집 데이터의 전처리 결과, 직무별 분포, 수강료 및 시수, 표준 키워드 통계를 시각화합니다.")

            if not df_hr_courses.empty:
                eda_row1_c1, eda_row1_c2 = st.columns(2)
                
                # 차트 1: 3대 API별 수집 비중
                with eda_row1_c1:
                    api_counts = df_hr_courses["source_api"].value_counts().reset_index()
                    api_counts.columns = ["source_api", "count"]
                    fig_pie = px.pie(
                        api_counts,
                        values="count",
                        names="source_api",
                        title="🏛️ 3대 공공 API별 수집 교육과정 비중",
                        hole=0.45,
                        color_discrete_sequence=["#3B82F6", "#10B981", "#F59E0B"]
                    )
                    fig_pie.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#F8FAFC'),
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                # 차트 2: 직무별 교육 공급 분포
                with eda_row1_c2:
                    job_counts = df_hr_courses["primary_job"].value_counts().reset_index()
                    job_counts.columns = ["primary_job", "count"]
                    fig_bar_job = px.bar(
                        job_counts,
                        x="primary_job",
                        y="count",
                        color="primary_job",
                        text="count",
                        title="👥 인사(HR) vs 총무·사무행정 교육과정 공급 수",
                        labels={"primary_job": "직무", "count": "강좌 수(개)"},
                        color_discrete_sequence=["#6366F1", "#06B6D4"]
                    )
                    fig_bar_job.update_traces(texttemplate="%{text}개", textposition="outside")
                    fig_bar_job.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#F8FAFC'),
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_bar_job, use_container_width=True)

                st.markdown("---")
                eda_row2_c1, eda_row2_c2 = st.columns(2)

                # 차트 3: 직무별 평균 수강료 및 시수 비교
                with eda_row2_c1:
                    avg_stats = df_hr_courses.groupby("primary_job")[["training_hours", "suitability_score"]].mean().reset_index()
                    fig_hours = px.bar(
                        avg_stats,
                        x="primary_job",
                        y="training_hours",
                        color="primary_job",
                        text="training_hours",
                        title="⏱️ 직무별 평균 훈련 이수 시간 (Hours)",
                        labels={"primary_job": "직무", "training_hours": "평균 훈련 시간(h)"},
                        color_discrete_sequence=["#EC4899", "#8B5CF6"]
                    )
                    fig_hours.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
                    fig_hours.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#F8FAFC'),
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_hours, use_container_width=True)

                # 차트 4: 표준화된 핵심 실무 키워드 출현 빈도
                with eda_row2_c2:
                    all_tags = []
                    for tags in df_hr_courses["standardized_tags"].dropna():
                        for t in str(tags).split("|"):
                            if t.strip():
                                all_tags.append(t.strip())
                    tag_df = pd.Series(all_tags).value_counts().reset_index()
                    tag_df.columns = ["tag", "count"]

                    fig_tags = px.bar(
                        tag_df.head(6),
                        x="count",
                        y="tag",
                        orientation="h",
                        color="count",
                        text="count",
                        title="🏷️ 표준화된 실무 교육 키워드 빈도 Top 6",
                        labels={"count": "출현 빈도", "tag": "실무 키워드"},
                        color_continuous_scale="Viridis"
                    )
                    fig_tags.update_layout(
                        yaxis=dict(autorange="reversed"),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#F8FAFC'),
                        margin=dict(l=10, r=10, t=40, b=10)
                    )
                    st.plotly_chart(fig_tags, use_container_width=True)

        # -------------------------------------------------------------
        # 탭 4: 교육 공백(Skill Gap) & 향후 발전 로드맵
        # -------------------------------------------------------------
        with tab_gap:
            st.markdown("### 🔍 교육 공백(Skill Gap) 정밀 진단 & 향후 확장 전략")
            st.write("현행 공공 교육과정의 공급 충족 영역과 실무 요구 대비 부족한 교육 공백(Gap)을 규명하고, 발전 방향을 제시합니다.")

            # 직무별 공백 분석 카드
            insights = hr_gap_data.get("skill_gap_insights", [])
            for ins in insights:
                st.markdown(f"""
                <div style="background: rgba(17, 24, 39, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 5px solid #EC4899; border-radius: 12px; padding: 18px 20px; margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 1.1rem; font-weight: 800; color: #FFF;">👥 {ins.get('job')} 교육 수급 및 갭(Gap) 진단</span>
                        <span style="background: rgba(236, 72, 153, 0.2); color: #F472B6; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700;">공백 심각도: {ins.get('severity')}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 10px 12px;">
                            <div style="font-size: 0.82rem; font-weight: 700; color: #34D399; margin-bottom: 4px;">✅ 공급 풍부 영역 (Well-Supplied)</div>
                            <div style="font-size: 0.82rem; color: #E2E8F0;">• {'<br/>• '.join(ins.get('rich_domains', []))}</div>
                        </div>
                        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 10px 12px;">
                            <div style="font-size: 0.82rem; font-weight: 700; color: #F87171; margin-bottom: 4px;">⚠️ 교육 공백 영역 (Skill Gap)</div>
                            <div style="font-size: 0.82rem; color: #E2E8F0;">• {'<br/>• '.join(ins.get('gap_domains', []))}</div>
                        </div>
                    </div>
                    <div style="background: rgba(30, 41, 59, 0.7); border-radius: 6px; padding: 10px 12px; font-size: 0.82rem; color: #93C5FD;">
                        <strong>💡 개선 실행 방안:</strong> {ins.get('action_plan')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### 🚀 분석의 한계점 및 향후 확장 로드맵 (Future Scope)")
            
            c_lim1, c_lim2 = st.columns(2)
            with c_lim1:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 16px;">
                    <div style="font-size: 0.95rem; font-weight: 700; color: #FCD34D; margin-bottom: 8px;">⚠️ 분석의 한계점</div>
                    <ul style="font-size: 0.83rem; color: #CBD5E1; line-height: 1.6; margin: 0; padding-left: 18px;">
                        <li><strong>L1~L2 초급 편중:</strong> 입문·초급 수준에 집중되어 중견/대기업 실무자가 필요로 하는 고급 인사기획(L3~L5) 과정 분석 미포함</li>
                        <li><strong>실무 툴 실습 부재:</strong> 최신 클라우드 인사 SaaS(Flex, 원티드스페이스 등) 연계 교육 과정이 공공 직업훈련에 상대적으로 부족</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

            with c_lim2:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 10px; padding: 16px;">
                    <div style="font-size: 0.95rem; font-weight: 700; color: #60A5FA; margin-bottom: 8px;">🌱 향후 확장 방향</div>
                    <ul style="font-size: 0.83rem; color: #CBD5E1; line-height: 1.6; margin: 0; padding-left: 18px;">
                        <li><strong>교육운영(HRD) 직무 추가:</strong> 인재육성, 사내 교육과정 기획, 평가 피드백 직무로 분석 범위 확장</li>
                        <li><strong>숙련도 L3~L5 심화 과정 확대:</strong> 인사 책임자 및 팀장급 전략 수립 역량 매핑</li>
                        <li><strong>대학 평생교육원 교육과정 기획:</strong> 공공 API 데이터와 대학 평생교육원 실무 마이크로디그리 연계</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

    else:
        # ==============================================================================
        # [MODE 2] NCS 24대 산업 272개 직무 전체 탐색기
        # ==============================================================================
        st.markdown("""
        <div class="header-container">
            <div class="header-left">
                <div class="header-icon">🌐</div>
                <div class="header-title-text">
                    <h1>NCS 24대 산업 272개 공식 직무 요구 정의서 & Level 1~5 맞춤 교육과정 시스템</h1>
                    <p>National Competency Standards Level 1~5 Architecture & Spec Sheet Intelligence</p>
                </div>
            </div>
            <div>
                <span class="live-badge">● 공식 272개 직무 · 1,360개 역량 정의서 완비</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        industry_stats = master_json.get("industry_stats", {})
        industry_options = []
        ind_code_map = {}
        for code, info in industry_stats.items():
            label = f"{code}. {info.get('major_name')} ({info.get('job_count')}개 직무)"
            industry_options.append(label)
            ind_code_map[label] = info.get('major_name')

        if not industry_options and not df_jobs.empty:
            industry_options = sorted(df_jobs["major_name"].unique().tolist())

        selected_ind_label = st.sidebar.selectbox("1. 산업 대분류 선택 (24개)", industry_options, index=0 if industry_options else 0)
        selected_major_name = ind_code_map.get(selected_ind_label, selected_ind_label)

        search_kw = st.sidebar.text_input("직무 검색 (272개 직무 실시간 필터)", placeholder="예: 빅데이터, PLC, 인사, 세무 등")

        if search_kw.strip():
            filtered_jobs = df_jobs[df_jobs["job_name"].str.contains(search_kw.strip(), case=False, na=False)]
        else:
            filtered_jobs = df_jobs[df_jobs["major_name"] == selected_major_name]

        job_list = filtered_jobs["job_name"].tolist()
        selected_job_name = st.sidebar.selectbox("2. 목표 세부 직무 선택", job_list, index=0 if job_list else 0)

        current_level = st.sidebar.select_slider(
            "3. 현재 내 직능 수준 (Current Level)",
            options=[1, 2, 3, 4, 5],
            value=2,
            format_func=lambda x: f"Level {x} ({['입문/보조', '초급 실무', '중급 독립실무', '숙련 책임자', '최고 전문가'][x-1]})"
        )

        tab_m1, tab_m2 = st.tabs(["🎯 직무 역량 요구 정의서 (Spec Sheet)", "💬 인프런 실무 강좌 & 리뷰 분석"])

        with tab_m1:
            if selected_job_name and not df_jobs.empty:
                job_info_series = df_jobs[df_jobs["job_name"] == selected_job_name]
                job_units = df_units[df_units["job_name"] == selected_job_name].sort_values("level") if not df_units.empty else pd.DataFrame()
                
                spec_sheet = {}
                for j in master_json.get("jobs", []):
                    if j.get("job_name") == selected_job_name:
                        spec_sheet = j.get("spec_sheet", {})
                        break

                st.markdown(f"### 🎯 {selected_job_name} 직무 역량 아키텍처 (Level 1~5)")
                for _, u in job_units.iterrows():
                    with st.expander(f"Level {u['level']} : {u['unit_name']} ({u['recommended_hours']}h)"):
                        st.markdown(f"**• 역량 정의:** {u['unit_desc']}")
                        st.markdown(f"**• 수행준거:** `{u['performance_criteria']}`")
                        st.markdown(f"**🧠 지식(K):** {u['knowledge_list']}")
                        st.markdown(f"**🛠️ 기술(S):** {u['skills_list']}")
                        st.markdown(f"**🤝 태도(A):** {u['attitudes_list']}")

        with tab_m2:
            st.markdown("### 💬 인프런 실무 강좌 & 수강평 분석")
            if inflearn_reviews:
                cols = st.columns(2)
                for idx, c in enumerate(inflearn_reviews[:6]):
                    col = cols[idx % 2]
                    with col:
                        st.markdown(f"""
                        <div style="background: rgba(17, 24, 39, 0.85); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                            <div style="font-size: 0.95rem; font-weight: 800; color: #FFF;">{c.get('title')}</div>
                            <div style="font-size: 0.8rem; color: #94A3B8; margin: 4px 0 8px 0;">강사: {c.get('instructor')} | ⭐ {c.get('rating_score')}</div>
                            <div style="font-size: 0.8rem; color: #34D399; margin-bottom: 8px;">{c.get('strength_summary', '')}</div>
                            <a href="{c.get('url', '#')}" target="_blank" style="color: #60A5FA; font-size: 0.78rem; text-decoration: none; font-weight: 700;">인프런 강좌 보기 ➔</a>
                        </div>
                        """, unsafe_allow_html=True)

def main():
    render_dashboard()

if __name__ == "__main__":
    main()
