"""
Tab 1. NCS 24개 산업 272개 직무 역량(KSA) & KOSIS 노동시장 정밀 EDA
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "data" / "processed"
SAMPLE_DIR = ROOT / "data" / "sample"

@st.cache_data
def load_tab1_data():
    # 1. NCS 직무 및 능력단위 마스터
    df_jobs = pd.read_csv(PROCESSED_DIR / "ncs_272_jobs.csv")
    df_units = pd.read_csv(PROCESSED_DIR / "ncs_1360_units.csv")
    df_ksa = pd.read_csv(PROCESSED_DIR / "ncs_ksa_master.csv")
    
    # 2. KOSIS 노동시장 통계
    df_shortage = pd.read_csv(SAMPLE_DIR / "occupation_labor_shortage.csv", header=1)
    df_shortage.columns = [c.strip() for c in df_shortage.columns]
    df_shortage["미충원율 (%)"] = (df_shortage["미충원인원 (명)"] / df_shortage["구인인원 (명)"] * 100).round(2)
    
    return df_jobs, df_units, df_ksa, df_shortage

def render_tab1(df_ncs_dummy=None):
    df_jobs, df_units, df_ksa, df_shortage = load_tab1_data()

    st.markdown("### 🏛️ [1단계] NCS 24개 산업 272개 직무 역량(KSA) 체계 & 노동시장 EDA")
    st.write("한국산업인력공단 NCS 표준 프레임워크와 고용노동부 KOSIS 노동력 통계를 결합하여 **산업별 직무 역량 구조와 인력 공백(Skill-Gap)**을 정밀 분석합니다.")

    st.warning("⚠️ 예시 데이터 안내: 이 화면의 NCS 직무·능력단위·KSA는 공식 NCS가 아니라 같은 틀(레벨 1~5, 공통 문구)로 만든 예시 데이터이고, 인력 부족 통계(data/sample)도 시연용 생성 데이터입니다. 실제 분석·의사결정에 사용하지 마세요.")

    # 1. 상단 KPI 요약 카드
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("분석 대상 산업 대분류", "24개 산업군", "전 산업 포괄")
    with kpi2:
        st.metric("표준 분석 직무", f"{len(df_jobs)}개 직무", "NCS 공식 세분류")
    with kpi3:
        st.metric("구조화 능력단위", f"{len(df_units):,}개 유닛", "Level 1~5 전 레벨")
    with kpi4:
        st.metric("추출 KSA 역량 항목", f"{len(df_ksa):,}개 항목", "지식·기술·태도 분해")

    st.markdown("---")

    # 2. 산업 대분류 및 세부 직무 인터랙티브 필터
    col_filter1, col_filter2 = st.columns([1, 1])
    with col_filter1:
        major_list = ["전체 산업"] + sorted(df_jobs["major_name"].unique().tolist())
        selected_major = st.selectbox("🎯 1. 분석할 산업 대분류 선택", major_list, index=0)

    with col_filter2:
        if selected_major == "전체 산업":
            filtered_jobs = df_jobs
        else:
            filtered_jobs = df_jobs[df_jobs["major_name"] == selected_major]
        
        job_list = filtered_jobs["job_name"].tolist()
        selected_job = st.selectbox("📌 2. 세부 직무 선택 (KSA 역량 명세 확인)", job_list, index=0 if job_list else None)

    # 3. EDA 파트 1: 산업군별 직무 수 및 직능 레벨 분포
    col_c1, col_c2 = st.columns([3, 2])
    with col_c1:
        st.markdown("#### 📊 24개 산업군별 직무 규모 및 역량 집중도")
        major_counts = df_jobs["major_name"].value_counts().reset_index()
        major_counts.columns = ["major_name", "job_count"]
        
        fig_major = px.bar(
            major_counts,
            x="job_count",
            y="major_name",
            orientation="h",
            text="job_count",
            title="산업 대분류별 공식 직무 수 (상위 순)",
            labels={"job_count": "직무 수 (개)", "major_name": "산업 대분류"},
            color="job_count",
            color_continuous_scale="Viridis",
            height=450
        )
        fig_major.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_major, width="stretch")

    with col_c2:
        st.markdown("#### 📈 KOSIS 직종별 인력 미충원율 (적격자 부족)")
        valid_shortage = df_shortage[df_shortage["직종별"] != "전직종"].sort_values("미충원율 (%)", ascending=True)
        
        fig_short = px.bar(
            valid_shortage,
            x="미충원율 (%)",
            y="직종별",
            orientation="h",
            text="미충원율 (%)",
            title="직종별 미충원율 (%) (구인 대비 미충원 비중)",
            labels={"미충원율 (%)": "미충원율 (%)", "직종별": "직종 분류"},
            color="미충원율 (%)",
            color_continuous_scale="Reds",
            height=450
        )
        fig_short.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_short.update_layout(margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_short, width="stretch")

    st.markdown("---")

    # 4. EDA 파트 2: 선택 직무의 KSA(지식·기술·태도) 세부 분해 및 레벨 사다리
    if selected_job:
        job_units = df_units[df_units["job_name"] == selected_job].sort_values("level")
        st.markdown(f"### 🎯 [{selected_job}] 직무 역량(KSA) 심층 분해")
        
        tab_k, tab_s, tab_a, tab_matrix = st.tabs([
            "🧠 지식 (Knowledge)", 
            "🛠️ 기술 및 도구 (Skill/Tools)", 
            "🤝 태도 (Attitude)",
            "🪜 직능 레벨 1~5 성장 사다리"
        ])
        
        with tab_k:
            st.markdown("##### 📚 직무 수행에 필요한 표준 지식 체계")
            for _, u in job_units.iterrows():
                st.markdown(f"**[Level {u['level']}] {u['unit_name']}**")
                k_items = u["knowledge_list"].split(" | ")
                st.write(" • " + "  • ".join([f"`{k}`" for k in k_items]))
                
        with tab_s:
            st.markdown("##### 💻 실무 도구 조작 및 소프트웨어/엔지니어링 기술")
            for _, u in job_units.iterrows():
                st.markdown(f"**[Level {u['level']}] {u['unit_name']}**")
                s_items = u["skills_list"].split(" | ")
                st.write(" • " + "  • ".join([f"`{s}`" for s in s_items]))
                
        with tab_a:
            st.markdown("##### 🧭 직무 윤리, 협업 소통 및 문제해결 태도")
            for _, u in job_units.iterrows():
                st.markdown(f"**[Level {u['level']}] {u['unit_name']}**")
                a_items = u["attitudes_list"].split(" | ")
                st.write(" • " + "  • ".join([f"`{a}`" for a in a_items]))

        with tab_matrix:
            st.markdown("##### 📋 직능 레벨별 수행준거(Performance Criteria) 및 권장 소요시간")
            st.dataframe(
                job_units[["level", "unit_name", "recommended_hours", "performance_criteria"]].rename(
                    columns={
                        "level": "직능레벨",
                        "unit_name": "능력단위명",
                        "recommended_hours": "권장훈련시간(H)",
                        "performance_criteria": "수행준거 (수행 가능 역량)"
                    }
                ),
                hide_index=True,
                width="stretch"
            )

    st.markdown("---")
    st.markdown("#### 💡 1단계 직무 역량 EDA 핵심 시사점")
    st.info("""
    1. **산업별 역량 분포:** 경영·회계(21개), 금융·보험(18개), 정보통신(18개) 분야의 직무 수가 가장 많고 세분화되어 있습니다.
    2. **노동시장 미충원 실태:** 영업·판매·운송(7.62%)과 디자인·방송(7.03%)의 미충원율이 가장 높으며, 이는 이론 지식보다 **'실제 도구를 다루는 기술(Skill)'**의 공급 부족을 의미합니다.
    3. **스킬 진화 구조:** Level 1~2는 단순 OA 및 서식 입력에 머물지만, **Level 3 이상부터는 데이터 가공 및 이상치 해결 역량이 필수**로 요구됩니다.
    """)
