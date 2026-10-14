"""
NCS 인사·총무 교육 통합 대시보드 (리서치 + 교육과정 데이터 + 텍스트분석/추천)
- 실행: streamlit run app/streamlit_integrated.py
- 구성:
    TAB 1. 리서치 요약   (NCS_Demand_Analysis_Report.md 핵심 결과)
    TAB 2. 교육 공급 현황 (295개 강좌: 플랫폼·시수·수강료)
    TAB 3. 키워드·군집    (TF-IDF Top 키워드, K-Means 8군집)
    TAB 4. 리서치 vs 공급 갭 (공통 핵심 역량별 교육 공급량)
    TAB 5. 맞춤 추천      (하이브리드 추천 시나리오 + 키워드 검색)
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
NLP_CSV = ROOT / "data" / "processed" / "hr_courses_nlp_ready_295.csv"
CLUSTER_CSV = ROOT / "data" / "hr" / "output" / "dashboard" / "text_analysis" / "cluster_summary.csv"
KEYWORD_CSV = ROOT / "data" / "hr" / "output" / "dashboard" / "text_analysis" / "keyword_top50.csv"
BENCH_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "hybrid_recommendation_benchmark.csv"

PALETTE = px.colors.qualitative.Set2

# 리서치 보고서(NCS_Demand_Analysis_Report.md)의 수치
LEVEL_DIST = pd.DataFrame({
    "레벨": ["Level 1~2 (입문)", "Level 3~4 (주니어)", "Level 5~6 (중급)", "Level 7~8 (시니어)"],
    "비중(%)": [10, 48, 32, 10],
})

# 리서치의 '공통 핵심 역량' → 강좌 텍스트에서 찾을 키워드
CORE_SKILLS = {
    "생성형 AI 활용": ["생성형", "chatgpt", "챗gpt", "프롬프트", "ai"],
    "데이터 분석·시각화": ["데이터", "시각화", "bi", "파이썬", "python", "sql", "대시보드"],
    "엑셀·업무 자동화": ["엑셀", "매크로", "vba", "자동화", "스프레드시트"],
    "노무·준법(컴플라이언스)": ["노무", "근로기준", "준법", "개인정보", "4대보험", "노동법"],
    "문서·보고서 작성": ["보고서", "문서", "기획서", "공문서", "파워포인트"],
    "리더십·소통·협업": ["리더십", "협업", "커뮤니케이션", "팀워크"],
}


@st.cache_data(show_spinner=False)
def load_data():
    courses = pd.read_csv(NLP_CSV)
    for c in ["training_hours", "cost"]:
        courses[c] = pd.to_numeric(courses[c], errors="coerce")
    courses["text"] = (
        courses[["course_title", "overview", "learning_objectives", "syllabus_text", "top_keywords"]]
        .fillna("").agg(" ".join, axis=1).str.lower()
    )
    clusters = pd.read_csv(CLUSTER_CSV)
    keywords = pd.read_csv(KEYWORD_CSV)
    bench = pd.read_csv(BENCH_CSV) if BENCH_CSV.exists() else None
    label_map = dict(zip(clusters["cluster"], clusters["cluster_label"]))
    return courses, clusters, keywords, bench, label_map


def kpi(col, label, value):
    col.metric(label, value)


def tab_research():
    st.subheader("NCS 수요 분석 핵심 결과")
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.bar(LEVEL_DIST, x="레벨", y="비중(%)", text="비중(%)", color="레벨",
                     color_discrete_sequence=PALETTE, template="plotly_white")
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.info("**핵심 구간**: Level 3~4(48%)와 Level 5~6(32%)가 전체의 80%입니다. "
                "기본 직무·서비스 산업은 Level 3~4 실무 단위가 중심입니다.")
        st.markdown("**KSA 구조**\n- **지식**: 근로기준법, 세무회계, 생성형 AI 원리\n"
                    "- **기술**: Python/SQL, Excel BI, AI 보고서 작성\n"
                    "- **태도**: 데이터 기반 의사결정, 규정 준수, 협업")
    st.markdown("#### 2-Track 학습 로드맵")
    t1, t2 = st.columns(2)
    t1.success("**주니어 Track (Level 3~4)**  \n30~40시간 · 온라인 60% + 오프라인 40%  \n결과물: 마이크로 크레덴셜")
    t2.warning("**시니어/리더 Track (Level 5~6)**  \n60~80시간 · 케이스 스터디 + 현장 프로젝트  \n결과물: 학점인정 마이크로디그리")


def tab_supply(df):
    st.subheader("교육 공급 현황 (확정 295개 강좌)")
    platforms = sorted(df["platform"].dropna().unique())
    sel = st.multiselect("플랫폼", platforms, default=platforms)
    d = df[df["platform"].isin(sel)]
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "강좌 수", f"{len(d):,}")
    kpi(k2, "플랫폼 수", d["platform"].nunique())
    kpi(k3, "평균 교육시간", f"{d['training_hours'].mean():.1f}h" if d["training_hours"].notna().any() else "-")
    kpi(k4, "무료 강좌 비율", f"{(d['cost'] == 0).mean() * 100:.0f}%")
    c1, c2 = st.columns(2)
    with c1:
        cnt = d["platform"].value_counts().reset_index()
        cnt.columns = ["플랫폼", "강좌 수"]
        st.plotly_chart(px.bar(cnt, x="강좌 수", y="플랫폼", orientation="h", template="plotly_white",
                               color_discrete_sequence=PALETTE), width="stretch")
    with c2:
        h = d.dropna(subset=["training_hours"])
        if len(h):
            fig = px.histogram(h, x="training_hours", nbins=25, template="plotly_white",
                               labels={"training_hours": "교육시간(h)"}, color_discrete_sequence=PALETTE)
            fig.add_vrect(x0=30, x1=45, fillcolor="green", opacity=0.12, annotation_text="리서치 권장 30~45h")
            st.plotly_chart(fig, width="stretch")
    with st.expander("강좌 목록"):
        st.dataframe(d[["course_title", "platform", "institution", "training_hours", "cost", "keyword_tags", "url"]],
                     column_config={"url": st.column_config.LinkColumn("링크", display_text="바로가기")},
                     hide_index=True, width="stretch")


def tab_keywords(df, clusters, keywords):
    st.subheader("키워드 · 군집 분석")
    c1, c2 = st.columns(2)
    with c1:
        top = keywords.head(20).sort_values("tfidf_sum")
        st.plotly_chart(px.bar(top, x="tfidf_sum", y="keyword", orientation="h", template="plotly_white",
                               title="TF-IDF Top 20 키워드", color_discrete_sequence=PALETTE), width="stretch")
    with c2:
        st.plotly_chart(px.pie(clusters, names="cluster_label", values="n_courses", hole=0.45,
                               title="8대 군집별 강좌 비중", color_discrete_sequence=PALETTE), width="stretch")
    sel = st.selectbox("군집 선택", clusters["cluster_label"].tolist())
    row = clusters[clusters["cluster_label"] == sel].iloc[0]
    st.markdown(f"**대표 키워드**: {row['top_keywords']}")
    st.caption("군집 경계는 흐릿합니다(실루엣 점수 낮음). 대략적인 주제 묶음으로 해석하세요.")


def tab_gap(df):
    st.subheader("리서치 공통 핵심 역량 vs 교육 공급")
    st.caption("리서치가 제시한 공통 핵심 역량 키워드가 강좌 제목·소개·목차에 나타나는 강좌 수입니다.")
    rows = []
    for skill, kws in CORE_SKILLS.items():
        mask = df["text"].apply(lambda t: any(k in t for k in kws))
        rows.append({"역량": skill, "강좌 수": int(mask.sum()), "비율(%)": round(mask.mean() * 100, 1)})
    g = pd.DataFrame(rows).sort_values("강좌 수")
    fig = px.bar(g, x="강좌 수", y="역량", orientation="h", text="비율(%)", template="plotly_white",
                 color="강좌 수", color_continuous_scale="Tealgrn")
    fig.update_layout(coloraxis_showscale=False, height=420)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(g.sort_values("강좌 수", ascending=False), hide_index=True, width="stretch")
    st.warning("공급량은 키워드 포함 여부 기준의 근사치이며, 실제 역량 부족 수준을 뜻하지 않습니다. "
               "'ai' 같은 짧은 키워드는 다른 단어에 포함돼 과대 집계될 수 있습니다.")


def tab_recommend(df, bench):
    st.subheader("맞춤 교육과정 추천")
    if bench is not None:
        st.markdown("#### 시나리오별 하이브리드 추천 (0.50 의미 + 0.35 BM25 + 0.15 만족도)")
        sc = st.selectbox("시나리오", bench["scenario"].unique().tolist())
        b = bench[bench["scenario"] == sc]
        st.markdown(f"**질의**: {b['query'].iloc[0]}")
        st.dataframe(b[["rank", "course_title", "platform", "final_score", "semantic_sim", "bm25_score"]],
                     hide_index=True, width="stretch")
    st.markdown("#### 키워드로 강좌 찾기")
    q = st.text_input("관심 키워드 (공백으로 구분)", "엑셀 보고서")
    terms = [t.lower() for t in q.split() if t.strip()]
    if terms:
        s = df["text"].apply(lambda t: sum(t.count(w) for w in terms))
        res = df.assign(점수=s)[s > 0].sort_values("점수", ascending=False).head(15)
        st.dataframe(res[["course_title", "platform", "training_hours", "keyword_tags", "점수", "url"]],
                     column_config={"url": st.column_config.LinkColumn("링크", display_text="바로가기")},
                     hide_index=True, width="stretch")
    st.caption("단어가 같아야 찾는 단순 일치 검색입니다. 의미 기반 추천은 위 시나리오 결과를 참고하세요.")


def main():
    st.set_page_config(page_title="NCS 인사·총무 통합 대시보드", page_icon="📊", layout="wide")
    st.title("📊 NCS 인사·총무 직무역량 · 교육과정 통합 대시보드")
    st.caption("리서치(NCS 수요 분석) + 교육과정 295개 + 텍스트 분석·추천 결과")
    try:
        df, clusters, keywords, bench, _ = load_data()
    except FileNotFoundError as e:
        st.error(f"데이터 파일이 없습니다: {e.filename}")
        return
    tabs = st.tabs(["🔬 1. 리서치 요약", "📚 2. 교육 공급", "🔤 3. 키워드·군집", "⚖️ 4. 갭 분석", "🎯 5. 맞춤 추천"])
    with tabs[0]:
        tab_research()
    with tabs[1]:
        tab_supply(df)
    with tabs[2]:
        tab_keywords(df, clusters, keywords)
    with tabs[3]:
        tab_gap(df)
    with tabs[4]:
        tab_recommend(df, bench)


if __name__ == "__main__":
    main()
