"""
NCS 기반 인사·총무·경영지원 교육 추천 및 분석 시스템 — 통합 대시보드
- 실행 명령어: streamlit run app/streamlit_integrated.py
- 데이터 소스:
    1. 통합 정제 데이터셋 (8,645건): data/hr/processed/education_courses_search_cleaned.parquet
    2. STEP 4 기존 표본 (553건/295건): data/hr/output/integration/hr_integrated_candidates.csv
    3. 사전 토큰화 캐시: data/hr/processed/tokenized_corpus_cache.parquet
    4. 키워드 분석 결과: data/hr/output/recommendation/course_tfidf_keywords.csv
    5. 검색 벤치마크 결과: search_results_tfidf_top10_cleaned.csv / search_results_bm25_top10_cleaned.csv
    6. 데이터 품질 및 이상치: cleaned_anomaly_comparison.csv
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

# ------------------------------------------------------------------------------
# 0. 기본 환경 및 스트림릿 페이지 설정
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="NCS 교육 추천 통합 분석 대시보드",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.recommendation.text_preprocessor import HRTextPreprocessor

DATA_PROCESSED = WORKSPACE_ROOT / "data" / "hr" / "processed"
DATA_INTEG = WORKSPACE_ROOT / "data" / "hr" / "output" / "integration"
DATA_RECOM = WORKSPACE_ROOT / "data" / "hr" / "output" / "recommendation"

# ------------------------------------------------------------------------------
# 1. 데이터셋 로딩 및 캐싱
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_main_datasets():
    """정제된 8,645건 교육 코퍼스 및 분석 결과 파일들을 로드합니다."""
    # 1. 메인 8,645건 정제 데이터셋
    df_main = pd.read_parquet(DATA_PROCESSED / "education_courses_search_cleaned.parquet")
    
    # 숫자형 처리
    df_main["duration_hours"] = pd.to_numeric(df_main["duration_hours"], errors="coerce")
    df_main["price"] = pd.to_numeric(df_main["price"], errors="coerce")
    
    # 2. STEP 4 기초 표본 데이터셋 (553건)
    p_step4 = DATA_INTEG / "hr_integrated_candidates.csv"
    df_step4 = pd.read_csv(p_step4, dtype=str) if p_step4.exists() else pd.DataFrame()
    if not df_step4.empty:
        for c in ["training_hours", "course_fee"]:
            if c in df_step4.columns:
                df_step4[c] = pd.to_numeric(df_step4[c], errors="coerce")

    # 3. 키워드 분석 파일
    p_kw = DATA_RECOM / "course_tfidf_keywords.csv"
    df_kw = pd.read_csv(p_kw) if p_kw.exists() else pd.DataFrame()
    
    p_title_desc = DATA_RECOM / "title_vs_desc_keywords.csv"
    df_td = pd.read_csv(p_title_desc) if p_title_desc.exists() else pd.DataFrame()

    # 4. 정제 후 검색 벤치마크 결과 (15개 질문 Top 10)
    p_t_clean = DATA_RECOM / "search_results_tfidf_top10_cleaned.csv"
    p_b_clean = DATA_RECOM / "search_results_bm25_top10_cleaned.csv"
    df_t_search = pd.read_csv(p_t_clean) if p_t_clean.exists() else pd.DataFrame()
    df_b_search = pd.read_csv(p_b_clean) if p_b_clean.exists() else pd.DataFrame()

    # 5. 이상치 및 품질 비교 파일
    p_anom = DATA_RECOM / "cleaned_anomaly_comparison.csv"
    df_anom = pd.read_csv(p_anom) if p_anom.exists() else pd.DataFrame()
    
    p_search_comp = DATA_RECOM / "search_clean_before_after_comparison.csv"
    df_search_comp = pd.read_csv(p_search_comp) if p_search_comp.exists() else pd.DataFrame()

    p_dedup_comp = DATA_RECOM / "top10_before_after_comparison.csv"
    df_dedup_comp = pd.read_csv(p_dedup_comp) if p_dedup_comp.exists() else pd.DataFrame()

    # 6. STEP 6 Long-form / Wide-form 데이터셋
    p_comp_long = DATA_RECOM / "course_competency_long.parquet"
    df_comp_long = pd.read_parquet(p_comp_long) if p_comp_long.exists() else pd.DataFrame()

    p_comp_wide = DATA_RECOM / "matrix_course_competency_wide.parquet"
    df_comp_wide = pd.read_parquet(p_comp_wide) if p_comp_wide.exists() else pd.DataFrame()

    p_kw_long = DATA_RECOM / "course_keyword_long.parquet"
    df_kw_long = pd.read_parquet(p_kw_long) if p_kw_long.exists() else pd.DataFrame()

    p_pivot_wide = DATA_RECOM / "pivot_provider_competency_wide.csv"
    df_pivot_wide = pd.read_csv(p_pivot_wide, index_col=0) if p_pivot_wide.exists() else pd.DataFrame()

    p_summary_prov = DATA_RECOM / "summary_provider_stats.csv"
    df_summary_prov = pd.read_csv(p_summary_prov) if p_summary_prov.exists() else pd.DataFrame()

    p_summary_comp = DATA_RECOM / "summary_competency_stats.csv"
    df_summary_comp = pd.read_csv(p_summary_comp) if p_summary_comp.exists() else pd.DataFrame()

    p_summary_job = DATA_RECOM / "summary_job_family_stats.csv"
    df_summary_job = pd.read_csv(p_summary_job) if p_summary_job.exists() else pd.DataFrame()

    return {
        "df_main": df_main,
        "df_step4": df_step4,
        "df_kw": df_kw,
        "df_td": df_td,
        "df_t_search": df_t_search,
        "df_b_search": df_b_search,
        "df_anom": df_anom,
        "df_search_comp": df_search_comp,
        "df_dedup_comp": df_dedup_comp,
        "df_comp_long": df_comp_long,
        "df_comp_wide": df_comp_wide,
        "df_kw_long": df_kw_long,
        "df_pivot_wide": df_pivot_wide,
        "df_summary_prov": df_summary_prov,
        "df_summary_comp": df_summary_comp,
        "df_summary_job": df_summary_job
    }

@st.cache_resource(show_spinner=False)
def load_interactive_search_engine():
    """사전 토큰화 캐시를 활용해 즉각 반응하는 실시간 검색 엔진(TF-IDF, BM25)을 초기화합니다."""
    cache_path = DATA_PROCESSED / "tokenized_corpus_cache.parquet"
    if not cache_path.exists():
        return None, None, None, None
        
    df_cache = pd.read_parquet(cache_path)
    corpus_tokens = [txt.split() for txt in df_cache["tokenized_text"]]
    
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=2, max_df=0.8, sublinear_tf=True)
    tfidf_matrix = vectorizer.fit_transform(df_cache["tokenized_text"])
    bm25 = BM25Okapi(corpus_tokens)
    preprocessor = HRTextPreprocessor()
    
    return vectorizer, tfidf_matrix, bm25, preprocessor

# ------------------------------------------------------------------------------
# 2. 사이드바 및 공통 정보 렌더링
# ------------------------------------------------------------------------------
datasets = load_main_datasets()
df_main = datasets["df_main"]

with st.sidebar:
    st.image("https://img.shields.io/badge/Project-edu--skill--gap-blue?style=for-the-badge", use_container_width=True)
    st.title("🎓 NCS 교육 추천 시스템")
    st.markdown("**통합 분석 및 검색 대시보드 (v2.0)**")
    st.markdown("---")
    
    st.markdown("### 📌 코퍼스 핵심 요약")
    st.metric("총 분석 코퍼스", f"{len(df_main):,}건")
    st.metric("수집 교육기관", f"{df_main['provider'].nunique()}개 기관")
    
    rich_cnt = (df_main["text_quality_status"] == "RICH").sum()
    st.metric("상세 풍부 강좌 (≥200자)", f"{rich_cnt:,}건", f"{(rich_cnt/len(df_main)*100):.1f}%")
    
    st.markdown("---")
    st.markdown("### 🧭 안내 및 프로젝트 링크")
    st.caption("• **GitHub**: [kimsaemi/edu-skill-gap](https://github.com/kimsaemi/edu-skill-gap)")
    st.caption("• **데이터 포맷**: Parquet (ZSTD Level 9 압축)")
    st.caption("• **매핑 상태**: '자동 매핑 후보'는 100% 규칙 기반 자동 매핑 결과입니다.")
    st.caption("• **임베딩 모델**: STEP 5-2 도입 예정 (현재 TF-IDF·BM25 적용)")

# ------------------------------------------------------------------------------
# 3. 메인 타이틀 및 6개 탭 구성
# ------------------------------------------------------------------------------
st.title("🏛️ NCS 기반 인사·총무 맞춤형 교육과정 통합 대시보드")
st.markdown(
    "본 대시보드는 **8,645건의 7대 교육기관 코퍼스**에 대한 데이터 현황, EDA 분석, NCS·KSA 자동 매핑, "
    "TF-IDF 핵심 키워드, TF-IDF vs BM25 어휘 검색 벤치마크 및 데이터 품질 정제 결과를 통합 시각화합니다."
)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 탭 1. 교육 데이터 현황",
    "📈 탭 2. EDA 분석 (STEP 4 & 5)",
    "🧠 탭 3. NCS·KSA 역량 분석",
    "🔑 탭 4. 교육과정 키워드 분석",
    "🔍 탭 5. TF-IDF vs BM25 검색 벤치마크",
    "🛡️ 탭 6. 데이터 품질 및 이상치 관리",
    "📐 탭 7. Long/Wide-form 구조화 & 교차집계"
])

# ------------------------------------------------------------------------------
# 탭 1: 교육 데이터 현황
# ------------------------------------------------------------------------------
with tab1:
    st.subheader("📊 전체 8,645건 교육과정 데이터 현황")
    st.caption("통합 교육 데이터의 기관별 분포, 직무 카테고리, 교육 시간 및 비용, 텍스트 결측 현황을 파악합니다.")

    # 1. 상단 핵심 KPI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("전체 교육과정", f"{len(df_main):,}건", help="신규 6대 DB(8,505건) + 공공 API(140건)")
    with col2:
        prov_cnt = df_main["provider"].nunique()
        st.metric("통합 교육기관", f"{prov_cnt}개 기관", "휴넷, KPC, KMA, 멀티캠퍼스 등")
    with col3:
        free_cnt = (df_main["price"] == 0).sum()
        st.metric("무료 과정 (공공/GSEEK 등)", f"{free_cnt:,}건", f"{(free_cnt/len(df_main)*100):.1f}%")
    with col4:
        avg_hours = df_main["duration_hours"].dropna().mean()
        st.metric("평균 교육시간", f"{avg_hours:.1f}시간", "중앙값: 8시간")

    st.markdown("---")

    # 2. 기관별 및 직무별 분포 차트
    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("#### 🏢 교육기관(플랫폼)별 과정 수")
        prov_counts = df_main["provider"].value_counts().reset_index()
        prov_counts.columns = ["교육기관", "과정수"]
        fig_prov = px.bar(
            prov_counts,
            x="교육기관",
            y="과정수",
            text="과정수",
            color="과정수",
            color_continuous_scale="Blues",
            title="7대 교육기관별 코퍼스 규모 (건수)",
            template="plotly_white"
        )
        fig_prov.update_traces(texttemplate="%{text:,}건", textposition="outside")
        fig_prov.update_layout(coloraxis_showscale=False, xaxis_tickangle=-25)
        st.plotly_chart(fig_prov, use_container_width=True)

    with c_right:
        st.markdown("#### 🎯 직무 카테고리별 과정 비중")
        # ncs_code 기반 직무 구분
        def get_job_family(code):
            c = str(code or "").strip()
            if c.startswith("COMP_HR"): return "인사 (HR)"
            if c.startswith("COMP_LABOR"): return "노무관리"
            if c.startswith("COMP_GA"): return "총무/자산관리"
            if c.startswith("COMP_MGMT"): return "경영기획/전략"
            if c.startswith("COMP_SEC"): return "비서/의전"
            if c.replace(".0","").isdigit(): return "공공표준 NCS"
            return "일반 소양 / 직무 외"

        df_main["job_family"] = df_main["ncs_code"].apply(get_job_family)
        jf_counts = df_main["job_family"].value_counts().reset_index()
        jf_counts.columns = ["직무분야", "과정수"]
        fig_jf = px.pie(
            jf_counts,
            names="직무분야",
            values="과정수",
            hole=0.42,
            title="직무별 공급 비중 (NCS/KSA 매핑 기준)",
            color_discrete_sequence=px.colors.qualitative.Safe,
            template="plotly_white"
        )
        st.plotly_chart(fig_jf, use_container_width=True)

    # 3. 교육시간 & 비용 분포
    st.markdown("---")
    st.markdown("#### ⏱️ 교육시간 및 수강료 분포")
    col_h, col_p = st.columns(2)

    with col_h:
        # 시간대 그룹핑
        def group_hours(h):
            if pd.isna(h): return "미기재"
            if h <= 4: return "초단기 (≤4h)"
            if h <= 8: return "단기 1일 (5~8h)"
            if h <= 24: return "중기 (9~24h)"
            return "장기 집중 (>24h)"

        df_main["hour_group"] = df_main["duration_hours"].apply(group_hours)
        hg_counts = df_main["hour_group"].value_counts().reindex(
            ["초단기 (≤4h)", "단기 1일 (5~8h)", "중기 (9~24h)", "장기 집중 (>24h)", "미기재"]
        ).fillna(0).reset_index()
        hg_counts.columns = ["교육시수구간", "과정수"]
        fig_h = px.bar(
            hg_counts,
            x="교육시수구간",
            y="과정수",
            text="과정수",
            color="교육시수구간",
            title="교육 시수(시간) 구간별 분포",
            template="plotly_white"
        )
        fig_h.update_traces(texttemplate="%{text:,}건", textposition="outside")
        fig_h.update_layout(showlegend=False)
        st.plotly_chart(fig_h, use_container_width=True)

    with col_p:
        # 비용대 그룹핑
        def group_price(p):
            if pd.isna(p): return "미기재"
            if p == 0: return "무료 (국비/공공)"
            if p < 100000: return "10만원 미만"
            if p < 300000: return "10~30만원"
            if p < 600000: return "30~60만원"
            return "60만원 이상"

        df_main["price_group"] = df_main["price"].apply(group_price)
        pg_counts = df_main["price_group"].value_counts().reindex(
            ["무료 (국비/공공)", "10만원 미만", "10~30만원", "30~60만원", "60만원 이상", "미기재"]
        ).fillna(0).reset_index()
        pg_counts.columns = ["수강료구간", "과정수"]
        fig_p = px.bar(
            pg_counts,
            x="수강료구간",
            y="과정수",
            text="과정수",
            color="수강료구간",
            title="수강료(비용) 구간별 분포",
            template="plotly_white"
        )
        fig_p.update_traces(texttemplate="%{text:,}건", textposition="outside")
        fig_p.update_layout(showlegend=False)
        st.plotly_chart(fig_p, use_container_width=True)

    # 4. 결측 현황
    st.markdown("---")
    st.markdown("#### 📋 주요 교육정보 필드별 데이터 보유율 (결측 현황)")
    missing_data = [
        {"필드명": "과정명 (title)", "보유건수": len(df_main), "보유율(%)": 100.0},
        {"필드명": "교육기관 (provider)", "보유건수": len(df_main), "보유율(%)": 100.0},
        {"필드명": "상세URL (url)", "보유건수": df_main["url"].fillna("").str.startswith("http").sum(), "보유율(%)": 100.0},
        {"필드명": "커리큘럼 (curriculum)", "보유건수": df_main["curriculum"].fillna("").str.strip().ne("").sum(), "보유율(%)": 84.2},
        {"필드명": "학습목표 (learning_goals)", "보유건수": df_main["learning_goals"].fillna("").str.strip().ne("").sum(), "보유율(%)": 76.5},
        {"필드명": "교육소개글 (course_intro)", "보유건수": df_main["course_intro"].fillna("").str.strip().ne("").sum(), "보유율(%)": 71.0},
        {"필드명": "교육시간 (duration_hours)", "보유건수": df_main["duration_hours"].notna().sum(), "보유율(%)": round(df_main["duration_hours"].notna().sum()/len(df_main)*100, 1)},
        {"필드명": "수강료 (price)", "보유건수": df_main["price"].notna().sum(), "보유율(%)": round(df_main["price"].notna().sum()/len(df_main)*100, 1)},
    ]
    df_missing = pd.DataFrame(missing_data)
    fig_miss = px.bar(
        df_missing,
        x="보유율(%)",
        y="필드명",
        orientation="h",
        text="보유율(%)",
        color="보유율(%)",
        color_continuous_scale="Viridis",
        title="필드별 유효 정보 보유율 (%)",
        template="plotly_white"
    )
    fig_miss.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
    fig_miss.update_traces(texttemplate="%{text}%", textposition="outside")
    st.plotly_chart(fig_miss, use_container_width=True)

# ------------------------------------------------------------------------------
# 탭 2: EDA 분석 (STEP 4 & STEP 5)
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("📈 다차원 EDA 분석 및 데이터 범위 비교")
    st.caption("기존 STEP 4의 295건 표본과 신규 8,645건 통합 데이터셋의 차이를 구분하고 심층 비교합니다.")

    # 1. 데이터 범위 구분 카드
    col_scope1, col_scope2 = st.columns(2)
    with col_scope1:
        st.info(
            "📌 **기존 STEP 4 분석 범위 (295건 / 553건)**\n\n"
            "- **데이터 출처**: 공공 API(고용24 140건) + 초기 7대 기관 표본(413건)\n"
            "- **주요 특징**: 직무 적합 확정(INCLUDED 295건), 수기 정제 표본\n"
            "- **파일 위치**: `data/hr/output/integration/hr_integrated_candidates.csv`"
        )
    with col_scope2:
        st.success(
            "🚀 **신규 STEP 5 대규모 통합 범위 (8,645건)**\n\n"
            "- **데이터 출처**: 신규 6대 기관 SQLite DB(8,505건) + 공공 API(140건)\n"
            "- **주요 특징**: Parquet 최적화, 텍스트 정제, 15개 벤치마크, Base64 노이즈 제거\n"
            "- **파일 위치**: `data/hr/processed/education_courses_search_cleaned.parquet`"
        )

    st.markdown("---")

    # 2. 주요 교육기관별 시간 vs 비용 비교 분석
    st.markdown("#### 🏢 주요 교육기관별 수강료 및 시수 특성 비교")
    prov_eda = df_main.groupby("provider").agg(
        총과정수=("course_uid", "count"),
        평균시수=("duration_hours", "mean"),
        평균수강료=("price", "mean"),
        무료과정수=("price", lambda p: (p == 0).sum())
    ).reset_index()
    prov_eda["무료비율(%)"] = (prov_eda["무료과정수"] / prov_eda["총과정수"] * 100).round(1)
    prov_eda["평균수강료(원)"] = prov_eda["평균수강료"].fillna(0).round().astype(int)
    prov_eda["평균시수(h)"] = prov_eda["평균시수"].fillna(0).round(1)

    st.dataframe(
        prov_eda[["provider", "총과정수", "평균시수(h)", "평균수강료(원)", "무료과정수", "무료비율(%)"]],
        column_config={
            "provider": "교육기관",
            "총과정수": st.column_config.NumberColumn("총 과정수", format="%d건"),
            "평균시수(h)": st.column_config.NumberColumn("평균 시수", format="%.1f 시간"),
            "평균수강료(원)": st.column_config.NumberColumn("평균 수강료", format="%d 원"),
            "무료비율(%)": st.column_config.NumberColumn("무료 비율", format="%.1f%%")
        },
        hide_index=True,
        use_container_width=True
    )

    # 3. 수강료 vs 교육시수 산점도 (Scatter)
    st.markdown("---")
    st.markdown("#### 💸 교육비 vs 교육시간 상관관계 분석")
    valid_scatter = df_main[df_main["duration_hours"].notna() & df_main["price"].notna() & (df_main["price"] > 0)].copy()
    valid_scatter = valid_scatter[valid_scatter["duration_hours"] <= 80] # 이상치 제외
    valid_scatter = valid_scatter[valid_scatter["price"] <= 1500000]

    fig_scatter = px.scatter(
        valid_scatter,
        x="duration_hours",
        y="price",
        color="provider",
        hover_name="title",
        hover_data={"duration_hours": True, "price": True, "provider": True},
        title=f"유료 강좌 {len(valid_scatter):,}건의 교육시간 대비 수강료 산점도 (시수 ≤80h, 비용 ≤150만원)",
        labels={"duration_hours": "교육시간 (시간)", "price": "수강료 (원)", "provider": "교육기관"},
        template="plotly_white",
        opacity=0.65
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# ------------------------------------------------------------------------------
# 탭 3: NCS·KSA 역량 분석
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("🧠 NCS 직무역량 체계 및 교육과정 자동 매핑 현황")
    st.caption("공식 표준 NCS 코드와 프로젝트 자체 KSA 역량 ID를 구분하고 매핑 근거와 상태를 파악합니다.")

    # 경고 및 명확한 정의 고지
    st.warning(
        "⚠️ **중요 안내 (매핑 상태 정의)**: 본 화면의 **'자동 매핑 후보 (규칙 검증)'** 상태는 사람이 최종 검증한 결과가 아니라, "
        "키워드 룰셋에 기반한 **100% 규칙 기반 자동 매핑(Rule-based Auto-matched)** 결과입니다. "
        "따라서 NCS 코드가 같더라도 실제 교육의 적합성은 사람 평가를 통해 검증되어야 합니다."
    )

    # 1. 역량별 교육 공급 수 차트
    comp_counts = df_main["ncs_code"].value_counts().reset_index()
    comp_counts.columns = ["역량코드", "과정수"]
    # 빈 값은 GENERAL
    comp_counts["역량코드"] = comp_counts["역량코드"].replace({"": "GENERAL (일반소양)"})
    
    col_c1, col_c2 = st.columns([1.3, 1.0])
    with col_c1:
        st.markdown("#### 🎯 프로젝트 역량 ID별 연결 교육 수")
        fig_c = px.bar(
            comp_counts.head(10),
            x="과정수",
            y="역량코드",
            orientation="h",
            text="과정수",
            color="과정수",
            color_continuous_scale="Teal",
            title="상위 10개 KSA/NCS 역량별 교육 공급 건수",
            template="plotly_white"
        )
        fig_c.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        fig_c.update_traces(texttemplate="%{text:,}건", textposition="outside")
        st.plotly_chart(fig_c, use_container_width=True)

    with col_c2:
        st.markdown("#### 🏷️ 매핑 상태 분포 (`mapping_status`)")
        # 사용자 친화적 명칭 매핑
        status_map = {
            "VERIFIED": "자동 매핑 후보 (규칙 검증)",
            "GENERAL": "일반 소양 / 직무 외",
            "REVIEW_NEEDED": "추가 검토 필요 후보"
        }
        df_main["display_status"] = df_main["mapping_status"].map(status_map).fillna("기타")
        status_counts = df_main["display_status"].value_counts().reset_index()
        status_counts.columns = ["매핑상태", "과정수"]
        
        fig_st = px.pie(
            status_counts,
            names="매핑상태",
            values="과정수",
            hole=0.45,
            title="8,645건 코퍼스 매핑 상태 비중",
            color_discrete_map={
                "자동 매핑 후보 (규칙 검증)": "#27ae60",
                "일반 소양 / 직무 외": "#95a5a6",
                "추가 검토 필요 후보": "#e67e22"
            },
            template="plotly_white"
        )
        st.plotly_chart(fig_st, use_container_width=True)

    # 2. 역량별 교육과정 인터랙티브 검색 테이블
    st.markdown("---")
    st.markdown("#### 🔍 NCS·KSA 매핑 교육과정 탐색기")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        f_status = st.selectbox(
            "매핑 상태 필터",
            ["전체 상태", "자동 매핑 후보 (규칙 검증)", "추가 검토 필요 후보", "일반 소양 / 직무 외"]
        )
    with col_f2:
        f_prov = st.selectbox(
            "교육기관 필터",
            ["전체 기관"] + sorted(list(df_main["provider"].unique()))
        )
    with col_f3:
        f_search = st.text_input("과정명 또는 KSA 키워드 검색", placeholder="예: 취업규칙, 노무, 엑셀")

    # 필터 적용
    df_comp_view = df_main.copy()
    if f_status != "전체 상태":
        df_comp_view = df_comp_view[df_comp_view["display_status"] == f_status]
    if f_prov != "전체 기관":
        df_comp_view = df_comp_view[df_comp_view["provider"] == f_prov]
    if f_search.strip():
        kw = f_search.strip()
        df_comp_view = df_comp_view[
            df_comp_view["title"].str.contains(kw, case=False, na=False) |
            df_comp_view["ksa_candidates"].str.contains(kw, case=False, na=False)
        ]

    st.markdown(f"**총 `{len(df_comp_view):,}`건의 교육과정이 필터링되었습니다.**")
    
    st.dataframe(
        df_comp_view[[
            "course_uid", "provider", "title", "ncs_code", "display_status",
            "ksa_candidates", "mapping_confidence", "url"
        ]],
        column_config={
            "course_uid": "고유ID",
            "provider": "교육기관",
            "title": "교육과정명",
            "ncs_code": "역량코드",
            "display_status": "매핑상태",
            "ksa_candidates": "관련 KSA 후보 (지식/기술/태도)",
            "mapping_confidence": st.column_config.NumberColumn("신뢰도", format="%.2f"),
            "url": st.column_config.LinkColumn("상세URL", display_text="상세보기 🔗")
        },
        hide_index=True,
        use_container_width=True,
        height=450
    )

# ------------------------------------------------------------------------------
# 탭 4: 교육 키워드 분석
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("🔑 교육과정별 TF-IDF 핵심 키워드 및 제목 vs 본문 비교")
    st.caption("형태소 분석(Kiwi)과 TF-IDF를 통해 추출한 강좌별 상위 8대 키워드를 분석합니다.")

    df_kw = datasets["df_kw"]
    df_td = datasets["df_td"]

    # 1. 상위 빈출 핵심 키워드 종합 순위
    if not df_kw.empty:
        st.markdown("#### 🏆 전체 8,645건 코퍼스에서 가장 많이 등장한 상위 TF-IDF 키워드")
        all_kws = []
        for kw_str in df_kw["top_tfidf_keywords"].dropna():
            for k in str(kw_str).split(","):
                k_clean = k.strip()
                if k_clean and len(k_clean) > 1:
                    all_kws.append(k_clean)
        
        kw_series = pd.Series(all_kws).value_counts().head(25).reset_index()
        kw_series.columns = ["키워드", "등장횟수"]

        fig_kw = px.bar(
            kw_series,
            x="등장횟수",
            y="키워드",
            orientation="h",
            text="등장횟수",
            color="등장횟수",
            color_continuous_scale="Purples",
            title="상위 25개 주요 실무 어휘 빈도",
            template="plotly_white"
        )
        fig_kw.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        fig_kw.update_traces(texttemplate="%{text:,}회", textposition="outside")
        st.plotly_chart(fig_kw, use_container_width=True)

    st.markdown("---")

    # 2. 개별 교육과정 주요 키워드 상세 조회기
    st.markdown("#### 🎯 개별 교육과정 선택 및 주요 키워드 확인")
    col_k1, col_k2 = st.columns([1.2, 1.0])
    
    with col_k1:
        sel_prov = st.selectbox("교육기관 선택", ["전체"] + sorted(list(df_main["provider"].unique())), key="kw_prov")
        if sel_prov != "전체":
            sub_courses = df_main[df_main["provider"] == sel_prov]
        else:
            sub_courses = df_main
            
        course_options = sub_courses["title"].head(300).tolist()
        sel_title = st.selectbox("교육과정명 선택 (상위 300건)", course_options)

    with col_k2:
        if sel_title:
            row_main = df_main[df_main["title"] == sel_title].iloc[0]
            st.markdown(f"**과정명**: `{row_main['title']}`")
            st.markdown(f"**기관**: `{row_main['provider']}` | **ID**: `{row_main['course_uid']}`")
            st.markdown(f"**본문 품질**: `{row_main['text_quality_status']}` ({row_main['clean_text_len']:,}자)")
            
            # 매칭 키워드 조회
            if not df_kw.empty and row_main["course_uid"] in df_kw["course_uid"].values:
                kw_row = df_kw[df_kw["course_uid"] == row_main["course_uid"]].iloc[0]
                st.markdown("**상위 8대 TF-IDF 키워드 및 점수**:")
                st.info(f"🏷️ {kw_row['keyword_scores']}")
            else:
                st.caption("해당 과정의 키워드 정보를 로드하는 중입니다.")

    # 3. 제목 키워드 vs 본문 키워드 비교 표
    st.markdown("---")
    st.markdown("#### 📑 제목 키워드 vs 본문 키워드 비교 샘플")
    if not df_td.empty:
        st.dataframe(
            df_td[["course_uid", "provider", "title", "title_keywords", "desc_keywords", "overlap_keywords"]].head(100),
            column_config={
                "course_uid": "과정ID",
                "provider": "기관",
                "title": "교육과정명",
                "title_keywords": "제목 키워드",
                "desc_keywords": "본문 키워드",
                "overlap_keywords": "제목-본문 공통 키워드"
            },
            hide_index=True,
            use_container_width=True,
            height=380
        )

# ------------------------------------------------------------------------------
# 탭 5: TF-IDF vs BM25 검색 벤치마크
# ------------------------------------------------------------------------------
with tab5:
    st.subheader("🔍 TF-IDF vs BM25 검색 벤치마크 및 실시간 검색")
    st.caption("15대 실무 질의 검색 결과 대조 및 사용자가 직접 입력하는 대화형 검색 기능을 제공합니다.")

    df_t_search = datasets["df_t_search"]
    df_b_search = datasets["df_b_search"]

    # 1. 서브 탭: 표준 15대 질의 vs 실시간 직접 검색
    subtab_bench, subtab_live = st.tabs(["📋 15대 표준 실무 질의 벤치마크", "⚡ 실시간 대화형 검색 (Custom Search)"])

    with subtab_bench:
        st.markdown("#### 15대 실무 질문 선택")
        query_list = [
            "Q01 (인사) - 신입사원 온보딩 및 채용 프로세스 실무",
            "Q02 (인사) - 근로기준법 개정사항 및 취업규칙 작성 실무",
            "Q03 (인사) - 연말정산 및 4대보험 급여 계산 실무",
            "Q04 (인사) - 직무분석 및 KPI 성과평가 보상체계 설계",
            "Q05 (인사) - 부당해고 구제신청 및 노사관계 노무관리",
            "Q06 (총무) - 비품 구매 계약 및 공급업체 관리",
            "Q07 (총무) - 고정자산 실사 및 사옥 시설관리",
            "Q08 (총무) - 공문서 작성법 및 기획보고서 피드백",
            "Q09 (총무) - 엑셀 실무 데이터 가공 및 함수 활용",
            "Q10 (총무) - 사내 행사 기획 및 워크숍 운영 총무 실무",
            "Q11 (경영지원) - 비즈니스 매너 및 사내 커뮤니케이션 에티켓",
            "Q12 (경영지원) - 임원 비서 실무 및 의전 가이드",
            "Q13 (경영지원) - 애자일 프로젝트 관리 및 스크럼 스프린트",
            "Q14 (경영지원) - 사업계획서 수립 및 재무제표 분석 기초",
            "Q15 (경영지원) - 주52시간 근로시간 관리 및 유연근무제 운영"
        ]
        sel_q = st.selectbox("평가 질문을 선택하세요", query_list, index=0)
        selected_qid = sel_q.split()[0] # "Q01"

        st.caption("💡 **점수 체계 안내**: TF-IDF 점수(0~1 코사인 유사도)와 BM25 점수(단어 포화 및 길이 정규화 점수)는 공식과 스케일이 다르므로 단순 합산하지 않고 독립 비교합니다.")

        # 해당 질의 결과 필터
        res_t = df_t_search[df_t_search["query_id"] == selected_qid].sort_values("rank").copy()
        res_b = df_b_search[df_b_search["query_id"] == selected_qid].sort_values("rank").copy()

        # 공통 과정 하이라이트 계산
        common_uids = set(res_t["course_uid"]).intersection(set(res_b["course_uid"]))
        res_t["공통노출"] = res_t["course_uid"].apply(lambda u: "★ 양쪽 일치" if u in common_uids else "")
        res_b["공통노출"] = res_b["course_uid"].apply(lambda u: "★ 양쪽 일치" if u in common_uids else "")

        # 다회차 중복 안내 태그
        res_t["회차정보"] = res_t["total_sessions"].apply(lambda s: f"단독 ({s}회)" if s == 1 else f"대표회차 (총 {s}회차 개설)")
        res_b["회차정보"] = res_b["total_sessions"].apply(lambda s: f"단독 ({s}회)" if s == 1 else f"대표회차 (총 {s}회차 개설)")

        col_t, col_b = st.columns(2)
        with col_t:
            st.markdown(f"##### 🔹 TF-IDF Top 10 (어휘 빈도 및 코사인 유사도)")
            st.dataframe(
                res_t[["rank", "title", "provider", "score", "공통노출", "회차정보", "url"]],
                column_config={
                    "rank": "순위",
                    "title": "교육과정명",
                    "provider": "교육기관",
                    "score": st.column_config.NumberColumn("TF-IDF점수", format="%.4f"),
                    "공통노출": "일치여부",
                    "회차정보": "회차개설현황",
                    "url": st.column_config.LinkColumn("상세URL", display_text="상세보기 🔗")
                },
                hide_index=True,
                use_container_width=True
            )

        with col_b:
            st.markdown(f"##### 🔸 BM25 Top 10 (단어 포화도 & 길이 정규화)")
            st.dataframe(
                res_b[["rank", "title", "provider", "score", "공통노출", "회차정보", "url"]],
                column_config={
                    "rank": "순위",
                    "title": "교육과정명",
                    "provider": "교육기관",
                    "score": st.column_config.NumberColumn("BM25점수", format="%.2f"),
                    "공통노출": "일치여부",
                    "회차정보": "회차개설현황",
                    "url": st.column_config.LinkColumn("상세URL", display_text="상세보기 🔗")
                },
                hide_index=True,
                use_container_width=True
            )

        st.success(f"두 알고리즘의 Top 10 중 **총 {len(common_uids)}개 과정**이 상위 10위권에 동시에 포함되었습니다.")

    with subtab_live:
        st.markdown("#### ⚡ 실시간 대화형 검색 (Custom Query Search)")
        st.caption("사용자가 입력한 검색어를 바탕으로 TF-IDF 및 BM25 검색 엔진이 8,645건 코퍼스를 실시간 검색합니다.")

        custom_query = st.text_input("검색어를 입력하세요", placeholder="예: 취업규칙 개정, 엑셀 피벗테이블, 사옥 시설관리, 애자일 스크럼")
        
        if custom_query.strip():
            engine = load_interactive_search_engine()
            if engine[0] is None:
                st.error("사전 토큰화 캐시 파일이 존재하지 않습니다.")
            else:
                vectorizer, tfidf_matrix, bm25, preprocessor = engine
                q_tokens = preprocessor.tokenize(custom_query.strip())
                
                if not q_tokens:
                    st.warning("유효한 검색 키워드가 감지되지 않았습니다.")
                else:
                    # 1. TF-IDF Search
                    q_vec = vectorizer.transform([" ".join(q_tokens)])
                    sim_scores = cosine_similarity(q_vec, tfidf_matrix).flatten()
                    ranked_t = np.argsort(sim_scores)[::-1]
                    
                    # Dedup Top 10
                    seen_t = {}
                    for idx in ranked_t:
                        sc = float(sim_scores[idx])
                        if sc <= 0.0: break
                        r = df_main.iloc[idx]
                        ikey = (r["provider"], r["title"])
                        if ikey in seen_t: continue
                        seen_t[ikey] = {"순위": len(seen_t)+1, "교육과정명": r["title"], "교육기관": r["provider"], "TF-IDF점수": round(sc, 4), "상세URL": r["url"]}
                        if len(seen_t) == 10: break

                    # 2. BM25 Search
                    bm25_scores = bm25.get_scores(q_tokens)
                    ranked_b = np.argsort(bm25_scores)[::-1]
                    
                    seen_b = {}
                    for idx in ranked_b:
                        sc = float(bm25_scores[idx])
                        if sc <= 0.0: break
                        r = df_main.iloc[idx]
                        ikey = (r["provider"], r["title"])
                        if ikey in seen_b: continue
                        seen_b[ikey] = {"순위": len(seen_b)+1, "교육과정명": r["title"], "교육기관": r["provider"], "BM25점수": round(sc, 2), "상세URL": r["url"]}
                        if len(seen_b) == 10: break

                    col_lt, col_lb = st.columns(2)
                    with col_lt:
                        st.markdown(f"**TF-IDF 실시간 검색 결과 ({len(seen_t)}건)**")
                        st.dataframe(
                            pd.DataFrame(list(seen_t.values())),
                            column_config={"상세URL": st.column_config.LinkColumn("상세URL", display_text="상세보기 🔗")},
                            hide_index=True, use_container_width=True
                        )
                    with col_lb:
                        st.markdown(f"**BM25 실시간 검색 결과 ({len(seen_b)}건)**")
                        st.dataframe(
                            pd.DataFrame(list(seen_b.values())),
                            column_config={"상세URL": st.column_config.LinkColumn("상세URL", display_text="상세보기 🔗")},
                            hide_index=True, use_container_width=True
                        )

# ------------------------------------------------------------------------------
# 탭 6: 데이터 품질 관리
# ------------------------------------------------------------------------------
with tab6:
    st.subheader("🛡️ 데이터 품질 점검, 이상값 관리 및 STEP 5-2 로드맵")
    st.caption("Base64 인라인 이미지, 중복 텍스트, 제목 전용 강좌 등의 정제 결과와 원본 보존 상태를 확인합니다.")

    # 1. 이상치 처리 요약 카드
    df_anom = datasets["df_anom"]
    
    q_c1, q_c2, q_c3, q_c4 = st.columns(4)
    with q_c1:
        st.metric("Base64 이미지 인라인 강좌", "29건", "정제 완료 (잔여 0건)")
    with q_c2:
        st.metric("최대 텍스트 길이 감소", "271만자 → 883자", "노이즈 99.9% 제거")
    with q_c3:
        st.metric("소개-목표 중복 강좌", "1,394건", "1회 결합으로 중복 방지")
    with q_c4:
        st.metric("제목 전용 과정 (0자)", "608건", "임의 생성 배제 / 보존")

    st.markdown("---")

    # 2. Base64 29건 정제 전후 비교 테이블
    st.markdown("#### 🚨 Base64 인라인 이미지 포함 29건 강좌 정제 전후 비교")
    st.caption("웹 크롤링 시 이미지 문자열이 원시 유입되어 문서 길이가 비정상적으로 비대화되었던 29건의 정제 결과입니다.")

    if not df_anom.empty:
        st.dataframe(
            df_anom[[
                "course_uid", "provider", "title", "raw_text_len", "clean_text_len",
                "chars_reduced", "text_quality_status", "cleaning_actions"
            ]],
            column_config={
                "course_uid": "과정ID",
                "provider": "기관",
                "title": "과정명",
                "raw_text_len": st.column_config.NumberColumn("정제 전 길이", format="%d자"),
                "clean_text_len": st.column_config.NumberColumn("정제 후 길이", format="%d자"),
                "chars_reduced": st.column_config.NumberColumn("감소 글자수", format="%d자"),
                "text_quality_status": "품질등급",
                "cleaning_actions": "적용 정제 조치"
            },
            hide_index=True,
            use_container_width=True
        )

    # 3. 정제 전후 검색 영향
    st.markdown("---")
    st.markdown("#### 📊 텍스트 정제 전후 15대 질의 검색 순위 변동률")
    df_search_comp = datasets["df_search_comp"]
    if not df_search_comp.empty:
        st.dataframe(
            df_search_comp[[
                "query_id", "query", "tfidf_top10_changed_courses",
                "tfidf_latency_ms", "bm25_top10_changed_courses", "bm25_latency_ms"
            ]],
            column_config={
                "query_id": "질의ID",
                "query": "검색 질의",
                "tfidf_top10_changed_courses": st.column_config.NumberColumn("TF-IDF 교체과정수", format="%d개 / 10개"),
                "tfidf_latency_ms": st.column_config.NumberColumn("TF-IDF 응답속도", format="%.2f ms"),
                "bm25_top10_changed_courses": st.column_config.NumberColumn("BM25 교체과정수", format="%d개 / 10개"),
                "bm25_latency_ms": st.column_config.NumberColumn("BM25 응답속도", format="%.2f ms")
            },
            hide_index=True,
            use_container_width=True
        )

    # 4. STEP 5-2 임베딩 로드맵 안내
    st.markdown("---")
    st.markdown("#### 🚀 다음 단계: STEP 5-2 로컬 임베딩 및 유사도 분석 로드맵")
    st.info(
        "📌 **STEP 5-2 도입 예정 모델 및 파일럿 사양**\n\n"
        "1. **비교 대상 모델**: `klue/bert-base` vs `jhgan/ko-sroberta-multitask` (STS 특화 Bi-Encoder)\n"
        "2. **임베딩 파일럿 데이터셋**: 400건 표본 준비 완료 (`data/hr/processed/pilot_courses_embedding_400.parquet`)\n"
        "3. **저장 및 검색 방식**: 768차원 Float32 벡터(`.npy`, 약 25.3MB) 및 FAISS `IndexFlatIP` 초고속 내적 검색\n"
        "4. **진행 원칙**: 단위 파일럿 테스트를 거친 후 전체 8,645건으로 확장하며, 현재 어휘 검색(TF-IDF·BM25)과 앙상블 하이브리드 검색을 구성합니다."
    )

# ------------------------------------------------------------------------------
# 탭 7: Long-form / Wide-form 구조화 및 교차집계
# ------------------------------------------------------------------------------
with tab7:
    st.subheader("📐 탭 7. Long-form(Tidy Data) / Wide-form 구조화 & 심층 교차분석")
    st.caption(
        "데이터 관측 단위(교육과정 단위, 다회차 개설 회차 단위, 역량 연결 단위, 키워드 단위)를 명확히 분리하고, "
        "Long-form과 Wide-form의 상호 변환 및 중복 집계 없는 Groupby / Crosstab / Pivot 다차원 분석을 제공합니다."
    )

    df_comp_long = datasets["df_comp_long"]
    df_comp_wide = datasets["df_comp_wide"]
    df_kw_long = datasets["df_kw_long"]
    df_pivot_wide = datasets["df_pivot_wide"]
    df_summary_prov = datasets["df_summary_prov"]
    df_summary_comp = datasets["df_summary_comp"]
    df_summary_job = datasets["df_summary_job"]

    # 1. 상단 핵심 지표 카드
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("전체 교육과정 (고유)", f"{len(df_main):,}건", help="개설 강좌 고유 ID 단위 (course_uid)")
    with col2:
        mapped_cnt = df_comp_long['course_uid'].nunique() if not df_comp_long.empty else 0
        st.metric("NCS 매핑 보유 과정", f"{mapped_cnt:,}건", f"{(mapped_cnt/len(df_main)*100):.1f}%")
    with col3:
        link_cnt = len(df_comp_long) if not df_comp_long.empty else 0
        st.metric("역량 매핑 관계 (Long)", f"{link_cnt:,}건", help="과정 × 역량 N:M 연결 관계 총합")
    with col4:
        ratio = round(link_cnt / mapped_cnt, 2) if mapped_cnt > 0 else 0
        st.metric("과정당 평균 역량연결", f"{ratio}개", help="1개 과정이 평균 몇 개 역량과 매핑되는지")
    with col5:
        kw_cnt = len(df_kw_long) if not df_kw_long.empty else 0
        st.metric("TF-IDF 키워드 (Long)", f"{kw_cnt:,}건", "8,645건 전수 매핑")

    st.markdown("---")

    # 2. 섹션 1: 기관별 교육과정 분포 및 비용/시수 다차원 분석
    st.markdown("#### 🏛️ 1. 교육기관별 공급 구조 및 교육비·시수 집계 (Groupby 분석)")
    st.markdown(
        "> **💡 관측 단위 주의**: KMA(69.3%)나 KFO(65.4%)처럼 **동일 교육과정이 여러 회차로 개설된 경우(다회차 개설)** "
        "전체 개설 건수(`count`)와 고유 강좌 제목 수(`nunique`) 간에 뚜렷한 차이가 발생합니다."
    )

    if not df_summary_prov.empty:
        # 주요 6대 기관 필터링
        main_provs = ["한국능률협회(KMA)", "한국생산성본부(KPC)", "멀티캠퍼스", "휴넷", "GSEEK", "한국직업방송(KFO)"]
        df_p_main = df_summary_prov[df_summary_prov["provider"].isin(main_provs)].copy()
        
        col_c1, col_c2 = st.columns([3, 2])
        with col_c1:
            fig_p_bar = px.bar(
                df_p_main,
                x="provider",
                y=["고유제목수", "전체과정수"],
                barmode="group",
                title="기관별 전체 개설 건수 vs 고유 강좌 수 (다회차 구조 분석)",
                labels={"value": "과정 수 (건)", "variable": "구분", "provider": "교육기관"},
                color_discrete_map={"전체과정수": "#3366CC", "고유제목수": "#109618"},
                template="plotly_white"
            )
            fig_p_bar.update_layout(xaxis_tickangle=-15, legend_title="")
            st.plotly_chart(fig_p_bar, use_container_width=True)

        with col_c2:
            st.dataframe(
                df_p_main[[
                    "provider", "전체과정수", "고유제목수", "다회차비율(%)",
                    "무료과정수", "평균수강료_유료만", "평균교육시간", "NCS매핑과정수"
                ]],
                column_config={
                    "provider": "교육기관",
                    "전체과정수": st.column_config.NumberColumn("개설 회차", format="%d건"),
                    "고유제목수": st.column_config.NumberColumn("고유 강좌", format="%d건"),
                    "다회차비율(%)": st.column_config.NumberColumn("다회차 비율", format="%.1f%%"),
                    "무료과정수": st.column_config.NumberColumn("무료 강좌", format="%d건"),
                    "평균수강료_유료만": st.column_config.NumberColumn("평균수강료(유료)", format="%d원"),
                    "평균교육시간": st.column_config.NumberColumn("평균시간", format="%.1f시간"),
                    "NCS매핑과정수": st.column_config.NumberColumn("매핑과정", format="%d건")
                },
                hide_index=True,
                use_container_width=True
            )

    st.markdown("---")

    # 3. 섹션 2: 역량별 & 직무별 교육과정 수 (고유과정 vs 연결건수 비교)
    st.markdown("#### 🎯 2. 직무 및 역량별 교육과정 수 (중복 방지: 고유 과정수 vs 연결 건수)")
    col_j1, col_j2 = st.columns(2)

    with col_j1:
        st.markdown("##### (1) 직무군(Job Family)별 공급 규모")
        if not df_summary_job.empty:
            fig_job = px.bar(
                df_summary_job,
                x="target_job_family",
                y=["고유교육과정수", "연결건수"],
                barmode="group",
                title="직무별 고유 과정수 vs 총 연결건수",
                labels={"value": "건수", "variable": "구분", "target_job_family": "직무군"},
                color_discrete_map={"고유교육과정수": "#4285F4", "연결건수": "#FBBC05"},
                template="plotly_white"
            )
            st.plotly_chart(fig_job, use_container_width=True)

    with col_j2:
        st.markdown("##### (2) KSA 역량별 교육과정 수 & 검증 비율")
        if not df_summary_comp.empty:
            fig_comp = px.bar(
                df_summary_comp.head(8),
                y="competency_name",
                x="고유교육과정수",
                orientation="h",
                color="검증비율",
                color_continuous_scale="Viridis",
                title="역량별 고유 교육과정 수 (색상: 실무 검증 비율 %)",
                labels={"고유교육과정수": "과정 수", "competency_name": "역량명"},
                template="plotly_white"
            )
            fig_comp.update_layout(yaxis={"autorange": "reversed"})
            st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("---")

    # 4. 섹션 3: 교육기관 × 역량 교차 히트맵 (Wide-form Pivot Table)
    st.markdown("#### 🗺️ 3. 교육기관 × KSA 역량 교차 히트맵 (Wide-form Pivot 분석)")
    st.caption("기관별로 어떤 역량 영역의 교육과정이 집중 공급되고 있는지 직관적으로 파악합니다.")

    if not df_pivot_wide.empty:
        # 주요 8개 역량 컬럼만 추출하여 히트맵 구성
        comp_cols = [c for c in df_pivot_wide.columns if c not in ["고유매핑과정수", "전체개설과정수", "매핑율(%)"]]
        hm_data = df_pivot_wide[comp_cols]

        fig_hm = px.imshow(
            hm_data,
            labels=dict(x="NCS/KSA 역량명", y="교육기관", color="고유 과정수"),
            x=comp_cols,
            y=hm_data.index.tolist(),
            text_auto=True,
            aspect="auto",
            color_continuous_scale="YlGnBu",
            title="교육기관 × KSA 역량별 고유 교육과정 수 교차표 (Pivot Table)"
        )
        fig_hm.update_xaxes(tickangle=-25)
        st.plotly_chart(fig_hm, use_container_width=True)

    st.markdown("---")

    # 5. 섹션 4: 교육과정별 TF-IDF 키워드 상세 조회표 (Long-form 탐색기)
    st.markdown("#### 🔑 4. 교육과정별 주요 키워드 상세 조회 (Long-form 기반 탐색)")
    st.caption("특정 교육과정을 선택하면 Long-form에 저장된 상위 1~8순위 키워드와 TF-IDF 가중치를 즉시 조회합니다.")

    if not df_kw_long.empty:
        sample_course_ids = df_kw_long["course_uid"].drop_duplicates().head(200).tolist()
        col_s1, col_s2 = st.columns([2, 3])
        with col_s1:
            sel_cid = st.selectbox(
                "조회할 교육과정 ID 선택:",
                options=sample_course_ids,
                index=0,
                key="kw_explorer_sel"
            )
            kw_match = df_kw_long[df_kw_long["course_uid"] == sel_cid]
            if not kw_match.empty:
                c_title = kw_match.iloc[0]["course_title"]
                c_prov = kw_match.iloc[0]["provider"]
                st.info(f"**과정명**: {c_title}\n\n**기관**: {c_prov}")

        with col_s2:
            if not kw_match.empty:
                fig_kw_bar = px.bar(
                    kw_match,
                    x="tfidf_score",
                    y="keyword",
                    orientation="h",
                    text="tfidf_score",
                    color="tfidf_score",
                    color_continuous_scale="Teal",
                    title=f"'{sel_cid}' 핵심 키워드 랭킹 (TF-IDF)",
                    labels={"tfidf_score": "TF-IDF 점수", "keyword": "키워드"},
                    template="plotly_white"
                )
                fig_kw_bar.update_traces(texttemplate="%.3f", textposition="outside")
                fig_kw_bar.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
                st.plotly_chart(fig_kw_bar, use_container_width=True)

    st.markdown("---")

    # 6. 섹션 5: Long-form vs Wide-form 상호 변환 대조 시각화
    st.markdown("#### 🔄 5. Long-form(Tidy Data) vs Wide-form(행렬) 상호 변환 대조")
    st.markdown(
        "초보자도 이해할 수 있도록 **동일한 교육과정 매핑 데이터가 두 포맷에서 어떻게 다르게 표현되는지** 실시간 비교합니다."
    )

    # 2개 이상 역량이 매핑된 샘플 교육과정 추출
    sample_multi_uids = [
        "HUNET_Y00406516",  # 4개 역량
        "HUNET_Y00405808",  # 2개 역량
        "HUNET_Y00405809"   # 2개 역량
    ]
    sel_demo_uid = st.radio(
        "비교 대상 샘플 교육과정 선택:",
        options=sample_multi_uids,
        horizontal=True,
        key="demo_uid_radio"
    )

    demo_long = df_comp_long[df_comp_long["course_uid"] == sel_demo_uid]
    demo_wide = df_comp_wide[df_comp_wide["course_uid"] == sel_demo_uid]

    col_fmt1, col_fmt2 = st.columns(2)

    with col_fmt1:
        st.markdown("##### 📄 (A) Long-form (세로형, Tidy Data)")
        st.caption(f"관측 단위: **교육과정 × 역량 연결 (총 {len(demo_long)}행)**. 행마다 하나의 역량 연결 관계를 기록.")
        if not demo_long.empty:
            st.dataframe(
                demo_long[[
                    "course_uid", "competency_id", "competency_name",
                    "ksa_type", "mapping_confidence", "mapping_status"
                ]],
                hide_index=True,
                use_container_width=True
            )
        st.markdown(
            "- **장점**: 새로운 역량이 추가되어도 테이블 구조(Schema) 변경 불필요, `groupby` 필터링 및 집계에 최적화\n"
            "- **용도**: RDBMS/SQL 관계 테이블, Seaborn/Plotly 시각화용 데이터셋"
        )

    with col_fmt2:
        st.markdown("##### 📊 (B) Wide-form (가로형, Matrix/Spreadsheet)")
        st.caption(f"관측 단위: **교육과정 (단 1행)**. 8개 역량이 가로 컬럼으로 펼쳐져 0/1 또는 플래그로 표현.")
        if not demo_wide.empty:
            comp_demo_cols = ["course_uid", "COMP_GA_01", "COMP_GA_02", "COMP_HR_01", "COMP_HR_02", "COMP_LABOR_01", "COMP_MGMT_01", "COMP_MGMT_02", "COMP_SEC_01", "total_comp_count"]
            st.dataframe(
                demo_wide[comp_demo_cols],
                hide_index=True,
                use_container_width=True
            )
        st.markdown(
            "- **장점**: 한눈에 전체 역량 보유 프로필 조망 가능, 행렬 연산 및 기계학습 모델 입력에 최적화\n"
            "- **용도**: Scikit-learn 특성 행렬(X), 추천 코사인 유사도 연산, 엑셀/스프레드시트 보고서"
        )

