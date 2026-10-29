"""
Tab 2. 수도권(대학 + 서울시 + 경기도) 통합 평생교육 자원 공급 및 3중 스킬 갭(Skill-Gap) 분석
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

def render_tab2(df_courses, analyzer):
    st.subheader("🏫 수도권(대학 평생교육원 + 서울시 + 경기도) 통합 교육 자원 & 3중 스킬 갭 분석")
    st.write("대학 K-MOOC(이론 중심)뿐 아니라 **서울시 평생학습포털**과 **경기데이터드림**의 지자체 실무 자원을 결합하여, 기업 실무 요구와의 간극(Gap)을 어떻게 극복할 수 있는지 분석합니다.")
    
    # 1. 3중 스킬 갭 레이더 차트
    st.markdown("#### 🕸️ 3중 스킬 갭(Gap) 레이더 분석: [기업 요구 vs 대학 단독 vs 지자체 결합]")
    cats, demand_scores, univ_scores, metro_scores = analyzer.get_tri_radar_data()
    
    fig_radar = go.Figure()
    # 1. 기업 실무 요구
    fig_radar.add_trace(go.Scatterpolar(
        r=demand_scores + [demand_scores[0]],
        theta=cats + [cats[0]],
        fill='toself',
        fillcolor='rgba(37, 99, 235, 0.15)',
        line=dict(color='#2563EB', width=2),
        name='1. 기업 실무 요구 수준 (NCS 기준)'
    ))
    # 2. 대학 K-MOOC 단독
    fig_radar.add_trace(go.Scatterpolar(
        r=univ_scores + [univ_scores[0]],
        theta=cats + [cats[0]],
        fill='toself',
        fillcolor='rgba(239, 68, 68, 0.15)',
        line=dict(color='#EF4444', width=2, dash='dot'),
        name='2. 대학 K-MOOC 단독 공급 수준 (이론 위주)'
    ))
    # 3. 서울·경기 지자체 결합
    fig_radar.add_trace(go.Scatterpolar(
        r=metro_scores + [metro_scores[0]],
        theta=cats + [cats[0]],
        fill='toself',
        fillcolor='rgba(16, 185, 129, 0.2)',
        line=dict(color='#10B981', width=3),
        name='3. 대학 + 서울/경기 지자체 결합 시 충족 수준 (실무 보완)'
    ))
    
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[30, 100]
            )
        ),
        showlegend=True,
        title="초록선(지자체 결합)이 파란선(기업 요구)에 근접하는 산·학·관 협력 시너지 시각화",
        height=480,
        margin=dict(l=50, r=50, t=60, b=30)
    )
    st.plotly_chart(fig_radar, width="stretch")
    
    st.success("""
    💡 **산·학·관(대학-서울시-경기도) 연계 핵심 인사이트**:
    - **빨간선(대학 단독)**: 회계나 통계 등 기본 이론에는 강하지만, 최신 광고 세팅이나 스마트스토어 등 실무 영역(Gap 40%)에서 부족함이 나타납니다.
    - **초록선(서울·경기 결합)**: 서울시민대학, 동대문 패션상권 스마트스토어, 판교 스타트업 캠퍼스, 경기 GSEEK 등 **지자체 실무 강좌를 결합할 때 기업 요구 역량 충족률이 88~92%까지 수직 상승**합니다!
    """)
    
    st.markdown("---")
    
    # 2. 기관별 / 지역별 강좌 자원 분포
    col_a, col_b = st.columns(2)
    with col_a:
        fig_source = px.histogram(
            df_courses,
            x="source_api",
            color="source_api",
            title="수도권 평생교육 자원 출처별 강좌 수 분포",
            labels={"source_api": "데이터 출처 API", "count": "강좌 수"},
            color_discrete_map={
                "K-MOOC(대학)": "#2563EB",
                "서울시 평생학습포털": "#EC4899",
                "경기데이터드림": "#10B981"
            }
        )
        st.plotly_chart(fig_source, width="stretch")
        
    with col_b:
        fig_region = px.bar(
            df_courses,
            x="region",
            color="source_api",
            title="수도권 세부 지역(구/시)별 평생학습 강좌 인프라",
            labels={"region": "수도권 지역", "count": "강좌 수", "source_api": "출처 API"}
        )
        st.plotly_chart(fig_region, width="stretch")

    # 3. 출처별 필터 탭 & 상세 목록
    st.markdown("#### 🔍 수도권 통합 평생교육 강좌 상세 데이터 탐색")
    source_filter = st.radio(
        "데이터 출처 선택",
        options=["전체 통합 (대학+서울+경기)", "K-MOOC(대학)", "서울시 평생학습포털", "경기데이터드림"],
        horizontal=True
    )
    
    if source_filter == "전체 통합 (대학+서울+경기)":
        display_courses = df_courses
    else:
        display_courses = df_courses[df_courses["source_api"] == source_filter]
        
    st.dataframe(
        display_courses[["source_api", "org_name", "region", "course_title", "category", "credit_type", "cost"]],
        hide_index=True,
        width="stretch"
    )
