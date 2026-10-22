"""
STEP 7-2: 합성 수강 후기 기반 감성 분석 및 추천 시뮬레이션 대시보드 컴포넌트
--------------------------------------------------------------------------------
- streamlit_integrated.py에 임베드하거나 독립 실행(streamlit run)할 수 있는 모듈
- 필수 명시 배너: "본 수강 후기 및 평점은 분석 실험을 위해 생성한 합성 데이터이며, 실제 수강생 평가를 의미하지 않습니다."
- 1. 합성 리뷰 데이터 현황 및 가상 평점/페르소나 분포
- 2. 머신러닝 감성 분석 모델 비교 (Model A TF-IDF vs Model B Ko-SRoBERTa) & 데이터 누출(Data Leakage) 방지 검증
- 3. 5대 핵심 토픽 분석 (실습, 난이도, 강사, 강의자료, 현업활용성)
- 4. 추천 모드 A/B/C 실시간 시뮬레이터 (기준 하이브리드 vs 평점 가중 vs 감성 가중)
"""

import os
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

WORKSPACE_ROOT = r"D:\26_강의자료\프로젝트2_교육"
PROCESSED_DIR = os.path.join(WORKSPACE_ROOT, "data", "hr", "processed")
OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, "data", "hr", "output", "recommendation")

FILES = {
    "reviews_parquet": os.path.join(PROCESSED_DIR, "reviews_integrated.parquet"),
    "summary_parquet": os.path.join(PROCESSED_DIR, "course_review_summary.parquet"),
    "sentiment_report": os.path.join(OUTPUT_DIR, "step7_sentiment_model_report.json"),
    "topics_report": os.path.join(OUTPUT_DIR, "review_topics_summary.json"),
    "topics_csv": os.path.join(OUTPUT_DIR, "review_topic_stats.csv"),
    "sim_benchmark": os.path.join(OUTPUT_DIR, "step7_recommendation_simulation_results.json")
}

@st.cache_data(show_spinner=False)
def load_step7_resources():
    sent_data = {}
    if os.path.exists(FILES["sentiment_report"]):
        with open(FILES["sentiment_report"], "r", encoding="utf-8") as f:
            sent_data = json.load(f)
            
    top_data = {}
    if os.path.exists(FILES["topics_report"]):
        with open(FILES["topics_report"], "r", encoding="utf-8") as f:
            top_data = json.load(f)
            
    df_top_csv = pd.read_csv(FILES["topics_csv"]) if os.path.exists(FILES["topics_csv"]) else pd.DataFrame()
    
    sim_data = {}
    if os.path.exists(FILES["sim_benchmark"]):
        with open(FILES["sim_benchmark"], "r", encoding="utf-8") as f:
            sim_data = json.load(f)
            
    df_sum = pd.read_parquet(FILES["summary_parquet"]) if os.path.exists(FILES["summary_parquet"]) else pd.DataFrame()
    
    return sent_data, top_data, df_top_csv, sim_data, df_sum

def render_step7_synthetic_dashboard():
    # 1. 최상단 필수 경고 및 면책 배너
    st.markdown("""
    <div style="background: linear-gradient(135deg, #451A03 0%, #78350F 50%, #B45309 100%); 
                padding: 1.25rem 1.6rem; border-radius: 12px; margin-bottom: 1.5rem; 
                border: 1px solid rgba(251, 191, 36, 0.4); box-shadow: 0 4px 12px rgba(180, 83, 9, 0.15);">
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span style="font-size: 1.5rem;">⚠️</span>
        <div>
          <div style="font-size: 1.05rem; font-weight: 800; color: #FEF3C7; letter-spacing: -0.01em;">
            [필수 고지] 분석 실험용 합성 데이터 (Synthetic Dataset) 알림
          </div>
          <div style="font-size: 0.92rem; font-weight: 600; color: #FDE68A; margin-top: 0.2rem;">
            "본 수강 후기 및 평점은 분석 실험을 위해 생성한 합성 데이터이며, 실제 수강생 평가를 의미하지 않습니다."
          </div>
        </div>
      </div>
      <div style="font-size: 0.82rem; color: #FCD34D; margin-top: 0.5rem; padding-left: 2.25rem;">
        • 본 탭의 데이터는 실제 웹사이트 크롤링 결과가 아니며, 자연어 처리 파이프라인 검증 및 추천 시뮬레이션을 위해 통계적 규칙으로 생성된 데이터입니다.<br>
        • 합성 평점 및 감성 점수는 실제 운영 중인 추천 시스템 기본 랭킹(Mode A)에 절대 반영되지 않습니다.
      </div>
    </div>
    """, unsafe_allow_html=True)

    sent_data, top_data, df_top_csv, sim_data, df_sum = load_step7_resources()
    
    # 2. 상단 핵심 KPI 카드
    st.markdown("### 📊 1. 합성 리뷰 데이터셋 현황")
    st.caption("7개 플랫폼(9,406개 강좌)에서 시뮬레이션된 482,078건 리뷰의 전수 메트릭")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("총 합성 리뷰 수", "482,078건", "7개 플랫폼 전수")
    with kpi2:
        st.metric("리뷰 연계 강좌 수", "9,406개", "코퍼스 매칭: 8,505개")
    with kpi3:
        st.metric("전체 평균 평점", "4.01점 / 5.0", "5점(40%) / 4점(35%)")
    with kpi4:
        st.metric("고유 텍스트 수", "232,802건", "중복 반복율: 49.7%")

    # 평점 및 페르소나 분포 시각화
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        st.markdown("**⭐ 가상 평점 분포 (전 플랫폼 균일 다항분포)**")
        rating_df = pd.DataFrame([
            {"평점": "5점", "건수": 192987, "비율": 40.03},
            {"평점": "4점", "건수": 169016, "비율": 35.06},
            {"평점": "3점", "건수": 72052, "비율": 14.95},
            {"평점": "2점", "건수": 28805, "비율": 5.98},
            {"평점": "1점", "건수": 19218, "비율": 3.99}
        ])
        fig_r = px.bar(rating_df, x="평점", y="건수", text="비율", color="평점",
                       color_discrete_sequence=["#10B981", "#3B82F6", "#F59E0B", "#F97316", "#EF4444"])
        fig_r.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_r.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20), showlegend=False)
        st.plotly_chart(fig_r, use_container_width=True)

    with c_p2:
        st.markdown("**👥 가상 페르소나 배분 (인위적 1:1:1 균등 분할)**")
        persona_df = pd.DataFrame([
            {"페르소나": "학생", "건수": 161170, "비율": 33.43},
            {"페르소나": "전공자", "건수": 160709, "비율": 33.34},
            {"페르소나": "직장인", "건수": 160199, "비율": 33.23}
        ])
        fig_p = px.pie(persona_df, names="페르소나", values="건수", hole=0.5,
                       color_discrete_sequence=["#6366F1", "#06B6D4", "#EC4899"])
        fig_p.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_p, use_container_width=True)

    st.markdown("---")

    # 3. 머신러닝 감성 분석 모델 비교
    st.markdown("### 🤖 2. 머신러닝 감성 분석 모델 비교 & 데이터 누출(Data Leakage) 검증")
    st.caption("Model A(TF-IDF + LR) vs Model B(Ko-SRoBERTa 768D + LR) 성능 및 템플릿 그룹 분할 효과")

    if sent_data and "model_comparison" in sent_data:
        m_comp = sent_data["model_comparison"]
        m_a_grp = m_comp.get("model_a_tfidf_group_split", {})
        m_a_rnd = m_comp.get("model_a_tfidf_naive_split", {})
        m_b_grp = m_comp.get("model_b_kosroberta_group_split", {})

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Model A (TF-IDF) [누출차단]", f"Macro-F1: {m_a_grp.get('macro_f1', 1.0):.4f}", f"정확도: {m_a_grp.get('accuracy', 1.0)*100:.1f}%")
        with m2:
            st.metric("Model A (TF-IDF) [단순분할]", f"Macro-F1: {m_a_rnd.get('macro_f1', 1.0):.4f}", "템플릿 누출 존재")
        with m3:
            st.metric("Model B (Ko-SRoBERTa) [누출차단]", f"Macro-F1: {m_b_grp.get('macro_f1', 0.9999):.4f}", f"정확도: {m_b_grp.get('accuracy', 1.0)*100:.1f}%")

        st.info("""
        💡 **통계적 이상 발견 (Scientific Observation)**:  
        동일/유사 템플릿 문장이 Train과 Test에 섞이지 않도록 `GroupShuffleSplit`으로 완벽히 차단했음에도, 
        **두 모델 모두 Macro-F1 0.9999 ~ 1.0000**이라는 비현실적으로 높은 성능을 기록했습니다.  
        이는 모델이 인간의 미묘한 감성을 잘 포착해서가 아니라, **합성 데이터의 긍정/중립/부정 템플릿에 사용된 어휘 집합이 사전에 결정론적으로 분리되어 생성되었기 때문**입니다.  
        따라서 이 점수를 **실제 수강생 리뷰에 대한 감성 분류 정확도라고 주장해서는 안 됩니다**.
        """)

        # 혼동행렬 시각화
        c_cm1, c_cm2 = st.columns(2)
        with c_cm1:
            st.markdown("**Model A (TF-IDF) 혼동행렬 (Group Split)**")
            cm_a = np.array(m_a_grp.get("confusion_matrix", [[2500,0,0],[0,2500,0],[0,0,2500]]))
            fig_cm_a = px.imshow(cm_a, x=['긍정', '중립', '부정'], y=['긍정', '중립', '부정'],
                                 text_auto=True, color_continuous_scale="Blues")
            fig_cm_a.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_cm_a, use_container_width=True)

        with c_cm2:
            st.markdown("**Model B (Ko-SRoBERTa 768D) 혼동행렬 (Group Split)**")
            cm_b = np.array(m_b_grp.get("confusion_matrix", [[2500,0,0],[0,2500,0],[0,0,2500]]))
            fig_cm_b = px.imshow(cm_b, x=['긍정', '중립', '부정'], y=['긍정', '중립', '부정'],
                                 text_auto=True, color_continuous_scale="Purples")
            fig_cm_b.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_cm_b, use_container_width=True)

    st.markdown("---")

    # 4. 리뷰 토픽 분석
    st.markdown("### 🔍 3. 5대 핵심 토픽 및 키워드 마이닝 결과")
    st.caption("실습, 난이도, 강사, 강의자료, 현업활용성 등 주요 언급 영역 분석")

    if not df_top_csv.empty:
        c_t1, c_t2 = st.columns([1.2, 1])
        with c_t1:
            fig_top = px.bar(df_top_csv, x="topic", y="total_ratio_pct", text="total_ratio_pct",
                             color="topic", title="5대 토픽별 전체 출현 빈도 (%)",
                             color_discrete_sequence=["#3B82F6", "#F59E0B", "#10B981", "#8B5CF6", "#EC4899"])
            fig_top.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_top.update_layout(height=300, showlegend=False, margin=dict(l=20, r=20, t=35, b=20))
            st.plotly_chart(fig_top, use_container_width=True)

        with c_t2:
            st.markdown("**📌 토픽별 매칭 키워드 및 감성 분포**")
            st.dataframe(df_top_csv[["topic", "total_ratio_pct", "positive_ratio_pct", "negative_ratio_pct"]].rename(
                columns={"topic": "토픽", "total_ratio_pct": "전체비중(%)", "positive_ratio_pct": "긍정비율(%)", "negative_ratio_pct": "부정비율(%)"}
            ), use_container_width=True, height=260)

    # 대표 표현 표
    with st.expander("📝 긍정 vs 부정 대표 표현 및 문장 패턴 보기"):
        col_pos, col_neg = st.columns(2)
        with col_pos:
            st.success("**🟢 주요 긍정 표현 (합성 템플릿)**\n"
                       "- '핵심 압축 요약본이 큰 역할을 해주었습니다'\n"
                       "- '실무 관점에서 깔끔하게 연결해주셔서 매우 유익'\n"
                       "- '이론과 실무 현장의 간극을 확실히 해소'\n"
                       "- '자주 발생하는 오류나 핵심 빈출 유형 체계적 정리'\n"
                       "- '전문성이 돋보이며 실전 적응력 강화'")
        with col_neg:
            st.error("**🔴 주요 부정 표현 (합성 템플릿)**\n"
                     "- '뒤쪽 심화 실습과 응용 문제는 난이도가 다소 부담'\n"
                     "- '혼자 복습하는 시간이 조금 더 필요'\n"
                     "- '퇴근 후 피로한 상태에서 듣기에는 다소 벅참'\n"
                     "- '교재나 강의자료의 상세 설명이 다소 부족'\n"
                     "- '선수 지식 없이 따라가기에 진도가 빠름'")

    st.markdown("---")

    # 5. 추천 시뮬레이션 인터랙티브 플레이그라운드
    st.markdown("### 🎯 4. 추천 모드 A/B/C 실시간 시뮬레이션 실험")
    st.caption("기준 하이브리드 추천(Mode A) vs 합성 평점 부스팅(Mode B) vs 합성 감성 부스팅(Mode C) 순위 변동 비교")

    standard_queries = [
        "신입사원 비즈니스 엑셀 데이터 분석 및 보고서 작성",
        "인사평가 및 핵심성과지표 KPI 수립 실무",
        "근로기준법 및 4대보험 노무관리",
        "생성형 AI를 활용한 업무 자동화 및 생산성 혁신",
        "팀장 리더십 및 조직 갈등 관리 소통 스킬"
    ]
    
    sel_q = st.selectbox("실험할 직무 질의어를 선택하거나 직접 입력하세요:", standard_queries + ["직접 입력"])
    if sel_q == "직접 입력":
        query_input = st.text_input("질의어 입력:", "파이썬 데이터 분석 머신러닝")
    else:
        query_input = sel_q

    from src.recommendation.simulation_recommender import RecommendationSimulator
    sim_engine = RecommendationSimulator()
    sim_res = sim_engine.simulate_query(query_input, top_k=5)

    # 3대 모드 결과 비교 테이블
    st.markdown(f"**🔍 검색어: `{query_input}`에 대한 Top 5 추천 결과 비교**")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("""
        <div style="background: #F8FAFC; border: 1.5px solid #CBD5E1; border-radius: 8px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem;">
          <b style="color: #0F172A;">[Mode A] 기준 하이브리드 추천</b><br>
          <span style="font-size: 0.78rem; color: #475569;">실제 교육정보만 활용 (Ko-SRoBERTa + BM25)</span>
        </div>
        """, unsafe_allow_html=True)
        for idx, row in enumerate(sim_res["top_a"]):
            st.markdown(f"""
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 6px; padding: 0.6rem; margin-bottom: 0.4rem; font-size: 0.85rem;">
              <b>{idx+1}위. {row['title']}</b><br>
              <span style="color: #64748B; font-size: 0.76rem;">{row['provider']} | 기준점수: <b>{row['score_mode_a']:.1f}점</b></span>
            </div>
            """, unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div style="background: #EFF6FF; border: 1.5px solid #93C5FD; border-radius: 8px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem;">
          <b style="color: #1D4ED8;">[Mode B] 합성 평점 가중 (가상 실험)</b><br>
          <span style="font-size: 0.78rem; color: #2563EB;">Mode A + 합성 평점 부스팅 (+15%)</span>
        </div>
        """, unsafe_allow_html=True)
        for idx, row in enumerate(sim_res["top_b"]):
            st.markdown(f"""
            <div style="background: white; border: 1px solid #BFDBFE; border-radius: 6px; padding: 0.6rem; margin-bottom: 0.4rem; font-size: 0.85rem;">
              <b>{idx+1}위. {row['title']}</b><br>
              <span style="color: #1E40AF; font-size: 0.76rem;">{row['provider']} | 실험점수: <b>{row['score_mode_b']:.1f}점</b> (⭐ {row['average_rating_calculated']:.2f})</span>
            </div>
            """, unsafe_allow_html=True)

    with col_c:
        st.markdown("""
        <div style="background: #FDF2F8; border: 1.5px solid #F472B6; border-radius: 8px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem;">
          <b style="color: #BE185D;">[Mode C] 합성 감성 가중 (가상 실험)</b><br>
          <span style="font-size: 0.78rem; color: #DB2777;">Mode A + 합성 긍정비율 부스팅 (+15%)</span>
        </div>
        """, unsafe_allow_html=True)
        for idx, row in enumerate(sim_res["top_c"]):
            st.markdown(f"""
            <div style="background: white; border: 1px solid #FBCFE8; border-radius: 6px; padding: 0.6rem; margin-bottom: 0.4rem; font-size: 0.85rem;">
              <b>{idx+1}위. {row['title']}</b><br>
              <span style="color: #9D174D; font-size: 0.76rem;">{row['provider']} | 실험점수: <b>{row['score_mode_c']:.1f}점</b> (긍정: {row['positive_review_ratio']*100:.1f}%)</span>
            </div>
            """, unsafe_allow_html=True)

    # 순위 일치도 메트릭
    metrics = sim_res["metrics"]
    st.info(f"""
    📈 **시뮬레이션 순위 변동 요약**:  
    • Mode A vs Mode B (평점 가중) Top-5 Jaccard 유사도: **{metrics['jaccard_similarity_mode_a_vs_b']*100:.1f}%** | 평균 순위 변동: **{metrics['mean_rank_shift_a_vs_b']:.1f}순위**  
    • Mode A vs Mode C (감성 가중) Top-5 Jaccard 유사도: **{metrics['jaccard_similarity_mode_a_vs_c']*100:.1f}%**  
    *(평점이나 감성 점수를 합산하면, 실제 교육과정의 본질적 적합도와 무관하게 합성 데이터 평점이 우연히 높은 강좌로 순위가 역전되는 왜곡 현상이 관찰됩니다.)*
    """)

if __name__ == "__main__":
    st.set_page_config(page_title="STEP 7-2 합성 리뷰 감성 분석 및 추천 시뮬레이션", layout="wide")
    render_step7_synthetic_dashboard()
