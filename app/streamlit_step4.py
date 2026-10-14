"""
NCS 기반 인사·총무 교육 데이터 대시보드 (STEP 4 MVP)
- 실행: streamlit run app/streamlit_step4.py
- 데이터 출처: 공공 API (140건) + 7대 민간/공공 플랫폼 SQLite DB (413건) 통합 데이터셋
- 구성:
    TAB 1. 교육 데이터 현황 (KPI 카드, 플랫폼/직무/출처 분포)
    TAB 2. 교육과정 탐색 (다차원 실시간 필터링, 정렬, 상세 링크)
    TAB 3. 직무역량 KSA 분석 (NCS 7대 핵심 역량 매핑 및 KSA 분포)
    TAB 4. 텍스트 분석·군집화 (TF-IDF 키워드, K-Means 군집, BM25 검색, 검색 방식 비교)
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------------------------------------
# 0. 환경 및 경로 설정
# ------------------------------------------------------------------------------
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
INTEG_DIR = WORKSPACE_ROOT / "data" / "hr" / "output" / "integration"
PROCESSED_DIR = WORKSPACE_ROOT / "data" / "hr" / "processed"

# ------------------------------------------------------------------------------
# 1. 데이터 로딩 및 캐싱 함수
# ------------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all_datasets():
    """실제 CSV 파일들을 로드하고 결측치 및 타입을 정제하여 반환합니다."""
    # 1. 통합 후보 전체 마스터 (553건)
    df_candidates = pd.read_csv(INTEG_DIR / "hr_integrated_candidates.csv", dtype=str)
    
    # 숫자형 컬럼 복원
    for col in ["training_hours", "duration_days", "course_fee"]:
        if col in df_candidates.columns:
            df_candidates[col] = pd.to_numeric(df_candidates[col], errors="coerce")
            
    # 결측 텍스트 채우기
    df_candidates["institution_name"] = df_candidates["institution_name"].fillna("기관명 미제공")
    df_candidates["course_level"] = df_candidates["course_level"].fillna("중급/실무")
    df_candidates["job_group"] = df_candidates["job_group"].fillna("인접/검토")
    df_candidates["job_category"] = df_candidates["job_category"].fillna("일반직무")

    # 2. 매핑 테이블 (295행)
    df_mapping = pd.read_csv(INTEG_DIR / "hr_mapping_verified.csv", dtype=str)
    
    # 3. NCS 마스터 정보
    df_jobs = pd.read_csv(PROCESSED_DIR / "jobs.csv", dtype=str)
    df_comp = pd.read_csv(PROCESSED_DIR / "competencies.csv", dtype=str)
    df_job_comp = pd.read_csv(PROCESSED_DIR / "job_competencies.csv", dtype=str)

    return {
        "candidates": df_candidates,
        "mapping": df_mapping,
        "jobs": df_jobs,
        "competencies": df_comp,
        "job_competencies": df_job_comp
    }

# ------------------------------------------------------------------------------
# 2. 유틸리티 포맷팅 함수
# ------------------------------------------------------------------------------
def format_fee(val):
    """수강료 값을 사용자 친화적 문자열로 변환합니다."""
    if pd.isna(val):
        return "미기재 (문의)"
    val = float(val)
    if val == 0.0:
        return "무료 (국비/공공)"
    return f"{int(val):,}원"

def format_hours(val):
    """교육 시수를 사용자 친화적 문자열로 변환합니다."""
    if pd.isna(val):
        return "시수 미기재"
    return f"{float(val):.1f}시간"


def format_collected_at(value):
    """수집 시각을 신뢰 정보에 사용할 수 있는 날짜 문자열로 변환합니다."""
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else "수집일 미기재"


# ------------------------------------------------------------------------------
# 3. 학습 여정: 가치 제안 · 진단 · 추천 · 피드백 · 성과
# ------------------------------------------------------------------------------
def render_learning_journey(datasets):
    """사용자의 자기진단을 실제 NCS 매핑·교육과정 데이터와 연결합니다."""
    df_jobs = datasets["jobs"]
    df_comp = datasets["competencies"]
    df_job_comp = datasets["job_competencies"]
    df_mapping = datasets["mapping"]
    df_courses = datasets["candidates"]

    st.markdown("## 🎯 내 직무에 맞는 학습 경로 설계")
    st.markdown(
        "**인사·총무 직무에 필요한 NCS 핵심 역량을 확인하고, 현재 부족한 역량에 맞는 "
        "교육과정을 골라 다음 실무 단계까지 연결합니다.**"
    )
    st.caption("자기진단 결과는 이 브라우저 세션에서만 사용되며, 실제 역량 평가 결과가 아닙니다.")

    steps = st.columns(4)
    for column, title, description in zip(
        steps,
        ["1. 직무·수준 설정", "2. 부족 역량 진단", "3. 맞춤 과정 학습", "4. 피드백·다음 행동"],
        ["목표 직무와 현재 수준 선택", "보완할 핵심 역량 선택", "근거를 확인하고 과정 시작", "완료 기록과 다음 과제 확인"],
    ):
        with column:
            st.markdown(f"**{title}**")
            st.caption(description)

    job_options = df_jobs.set_index("job_name")["job_id"].to_dict()
    setup_col, diagnosis_col = st.columns([1, 1.4])
    with setup_col:
        selected_job_name = st.selectbox("목표 직무", list(job_options), key="learning_target_job")
        current_level = st.select_slider(
            "현재 숙련도", ["입문", "기초", "실무 경험 있음"], value="입문", key="learning_current_level"
        )

    selected_job_id = job_options[selected_job_name]
    required = (
        df_job_comp[df_job_comp["job_id"] == selected_job_id]
        .merge(df_comp[["competency_id", "competency_name", "definition"]], on="competency_id", how="left")
    )
    competency_options = required["competency_name"].tolist()
    task_source = required.merge(
        df_comp[["competency_id", "skill"]], on="competency_id", how="left"
    )
    task_to_competency = {}
    for task_row in task_source.itertuples():
        for task in str(task_row.skill).split(","):
            task = task.strip()
            if task and task.lower() != "nan":
                task_to_competency[f"{task} (연계 역량: {task_row.competency_name})"] = task_row.competency_id

    with diagnosis_col:
        st.markdown("**실제 수행 중인 업무 (복수 선택)**")
        st.caption("NCS 역량 마스터의 실무 기술(Skill) 항목에서 자동으로 구성한 선택지입니다.")
        default_tasks = list(task_to_competency) if current_level == "입문" else list(task_to_competency)[:2]
        selected_tasks = st.multiselect(
            "수행 중인 세부 업무",
            list(task_to_competency),
            default=default_tasks,
            help="선택한 업무의 연결 역량과 과정만 추천 우선순위에 반영합니다.",
            key=f"learning_tasks_{selected_job_id}",
        )
        with st.expander("기타 업무가 있나요? (선택)"):
            custom_task = st.text_input(
                "목록에 없는 업무만 직접 입력", placeholder="예: 해외 지사 인사운영 지원", key=f"learning_custom_task_{selected_job_id}"
            )

    selected_competency_ids = list(dict.fromkeys(task_to_competency[task] for task in selected_tasks))
    if not selected_competency_ids:
        st.info("수행 중인 업무를 하나 이상 선택하면 연결 역량과 맞춤 교육과정을 안내합니다.")
        return

    selected_detail = required[required["competency_id"].isin(selected_competency_ids)]
    selected_gaps = selected_detail["competency_name"].tolist()
    rationale = " · ".join(
        f"{row.competency_name}: {row.mapping_rationale}"
        for row in selected_detail.itertuples()
    )

    st.markdown("### 🧭 현재 수준과 목표 수준")
    target_score = 3 if current_level == "입문" else 4 if current_level == "기초" else 5
    assessment_cols = st.columns(min(3, len(selected_detail)))
    assessment_rows = []
    for index, row in enumerate(selected_detail.itertuples()):
        with assessment_cols[index % len(assessment_cols)]:
            current_score = st.select_slider(
                row.competency_name,
                options=[1, 2, 3, 4, 5],
                value=min(target_score - 1, 3),
                format_func=lambda score: f"{score}/5",
                key=f"assessment_{selected_job_id}_{row.competency_id}",
            )
            gap = max(target_score - current_score, 0)
            st.caption(f"목표 {target_score}/5 · 보완 필요 {gap}단계")
            assessment_rows.append({"competency_id": row.competency_id, "gap": gap})
    assessment_df = pd.DataFrame(assessment_rows)

    st.markdown("### 🧭 지금의 추천 근거")
    st.success(
        f"**{selected_job_name} / {current_level}** 기준으로, 선택한 업무가 연결된 "
        f"**{', '.join(selected_gaps)}** 역량과 사용자가 입력한 현재 수준 대비 목표 수준을 우선 반영했습니다. "
        f"NCS 직무-역량 매핑 근거: {rationale}"
    )
    if custom_task.strip():
        st.caption(f"기타 업무 메모: {custom_task} — 현재 NCS 매핑이 없는 자유 입력이며, 추천 결과에는 선택 업무 기반 근거를 우선 적용합니다.")

    matching = df_mapping[df_mapping["competency_id"].isin(selected_competency_ids)].copy()
    matching = matching.merge(assessment_df, on="competency_id", how="left")
    matching["matched_competencies"] = matching.groupby("global_course_key")["competency_name"].transform(
        lambda values: ", ".join(sorted(set(values)))
    )
    recommendations = (
        matching.groupby(["global_course_key", "matched_competencies"], as_index=False)
        .agg(matched_count=("competency_id", "size"), learning_gap=("gap", "max"))
        .merge(df_courses, on="global_course_key", how="left")
    )
    recommendations = recommendations[recommendations["classification_status"] == "INCLUDED"]
    recommendations = recommendations.sort_values(
        ["learning_gap", "matched_count", "training_hours"], ascending=[False, False, True], na_position="last"
    ).head(3)

    if recommendations.empty:
        st.warning("선택한 역량과 직접 연결된 확정 교육과정이 아직 없습니다. 탐색 탭에서 검토 대기 과정까지 확인해 보세요.")
        return

    if "completed_course_keys" not in st.session_state:
        st.session_state.completed_course_keys = set()
    completed = st.session_state.completed_course_keys
    completion = len(set(recommendations["global_course_key"]) & completed)
    st.markdown("### 📚 추천 학습과정과 성과")
    metric_col, progress_col = st.columns([1, 2])
    with metric_col:
        st.metric("완료한 추천 과정", f"{completion}/{len(recommendations)}개")
    with progress_col:
        st.progress(completion / len(recommendations), text="추천 과정 완료율")

    for rank, course in enumerate(recommendations.itertuples(), start=1):
        is_completed = course.global_course_key in completed
        with st.container(border=True):
            title_col, action_col = st.columns([4, 1])
            with title_col:
                st.markdown(f"**{rank}순위 · {course.course_name}**")
                st.caption(
                    f"{course.institution_name} · {course.course_level} · {format_hours(course.training_hours)} · {format_fee(course.course_fee)}"
                )
                st.write(f"추천 이유: 선택한 **{course.matched_competencies}** 역량과 직접 연결된 과정입니다.")
                st.caption(
                    f"출처: {course.source_platform} ({course.source_type}) · 데이터 수집일: {format_collected_at(course.collected_at)} · "
                    "완료 기준: 학습자가 수강기관의 수료 기준을 충족한 뒤 이 화면에서 완료 처리"
                )
                if pd.notna(course.course_url) and str(course.course_url).startswith("http"):
                    st.link_button("과정 상세 보기 ↗", str(course.course_url), key=f"course_link_{course.global_course_key}")
            with action_col:
                if is_completed:
                    st.success("완료")
                elif st.button("완료 처리", key=f"complete_{course.global_course_key}"):
                    st.session_state.completed_course_keys.add(course.global_course_key)
                    st.rerun()

    feedback = st.radio(
        "학습 후 체감 난이도", ["아직 시작 전", "적절함", "어려움", "너무 쉬움"], horizontal=True, key="learning_feedback"
    )
    if feedback == "어려움":
        next_action = "다음 행동: 교육과정 탐색 탭에서 입문/기초 과정으로 필터를 좁혀 먼저 학습하세요."
    elif completion == len(recommendations):
        next_action = "다음 행동: 선택한 역량을 다시 진단하거나, 인접 직무의 역량으로 학습 범위를 넓혀보세요."
    else:
        next_action = "다음 행동: 첫 번째 추천 과정을 시작하고 완료 후 체크해 다음 우선순위를 갱신하세요."
    st.info(next_action)


def render_service_support():
    """서비스 이용 안내, 데이터 범위, 문의 경로를 제공한다."""
    st.markdown("---")
    with st.expander("서비스 이용·데이터·문의 안내"):
        left, right = st.columns(2)
        with left:
            st.markdown("**데이터 사용과 개인정보**")
            st.write("이 대시보드는 공개 교육과정 메타데이터와 NCS 역량 정보를 분석합니다. 자기진단·완료 기록은 현재 브라우저 세션에만 남으며 서버에 저장하지 않습니다.")
            st.write("추천은 과정-역량 연결 정보에 기반한 참고 자료입니다. 실제 수강 가능 여부, 비용, 일정, 수료 조건은 과정 상세 페이지에서 확인해야 합니다.")
        with right:
            st.markdown("**결과가 보이지 않거나 개선 의견이 있나요?**")
            st.write("필터를 완화하거나 다른 업무를 선택해 보세요. 오류와 개선 의견은 GitHub 저장소의 Issue로 남길 수 있습니다.")
            st.link_button("GitHub Issue로 의견 보내기", "https://github.com/kimsaemi/edu-skill-gap/issues")
        st.caption("모바일에서는 표와 차트가 가로로 길어질 수 있습니다. 과정 탐색 표는 좌우로 스크롤해 확인하세요.")

# ------------------------------------------------------------------------------
# 3. 탭 1: 교육 데이터 현황 렌더러
# ------------------------------------------------------------------------------
def render_tab1_overview(df_all):
    st.markdown("### 📊 수집 및 통합 데이터 현황")
    st.caption("공공 API(고용24) 및 7개 민간/공공 교육 플랫폼(휴넷, KPC, KMA 등)에서 확보한 교육과정의 분포를 파악합니다.")

    # 1. 동적 KPI 계산 (하드코딩 배제)
    total_cand = len(df_all)
    inc_count = (df_all["classification_status"] == "INCLUDED").sum()
    rev_count = (df_all["classification_status"] == "REVIEW_NEEDED").sum()
    exc_count = (df_all["classification_status"] == "EXCLUDED").sum()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("전체 수집 후보", f"{total_cand:,}건", help="공공 API 140건 + 민간/공공 SQLite 413건")
    with kpi2:
        st.metric("직무 적합 확정 (INCLUDED)", f"{inc_count:,}건", f"{(inc_count/total_cand*100):.1f}%", help="인사·총무 직무 관련성 검증 완료")
    with kpi3:
        st.metric("추가 검토 대기 (REVIEW)", f"{rev_count:,}건", f"{(rev_count/total_cand*100):.1f}%", help="리더십/AI인접/기획 과정")
    with kpi4:
        st.metric("분석 제외 (EXCLUDED)", f"{exc_count:,}건", f"-{(exc_count/total_cand*100):.1f}%", delta_color="inverse", help="IT개발/어학/제조 등 비관련")

    st.markdown("---")

    # 2. 시각화 섹션 1: 플랫폼별 & 직무군별
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 🏢 플랫폼별 교육과정 분포")
        plat_counts = df_all.groupby(["source_platform", "classification_status"]).size().reset_index(name="count")
        fig_plat = px.bar(
            plat_counts, 
            x="source_platform", 
            y="count", 
            color="classification_status",
            title="플랫폼별 상태 분포 (INCLUDED / REVIEW / EXCLUDED)",
            labels={"source_platform": "수집 플랫폼", "count": "강좌 수", "classification_status": "분류 상태"},
            color_discrete_map={"INCLUDED": "#2ecc71", "REVIEW_NEEDED": "#f39c12", "EXCLUDED": "#e74c3c"},
            template="plotly_white"
        )
        fig_plat.update_layout(xaxis_tickangle=-30, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_plat, use_container_width=True)

    with col_right:
        st.markdown("#### 🎯 직무군별 확정 강좌 비중 (INCLUDED 기준)")
        df_inc = df_all[df_all["classification_status"] == "INCLUDED"]
        jg_counts = df_inc["job_group"].value_counts().reset_index()
        jg_counts.columns = ["직무군", "강좌수"]
        fig_jg = px.pie(
            jg_counts,
            names="직무군",
            values="강좌수",
            hole=0.45,
            title=f"확정 표본 {len(df_inc):,}건의 상위 직무 비중",
            color_discrete_sequence=["#3498db", "#9b59b6", "#1abc9c"],
            template="plotly_white"
        )
        st.plotly_chart(fig_jg, use_container_width=True)

    # 3. 시각화 섹션 2: 세부 직무별 카테고리 & 출처 유형
    col_cat, col_src = st.columns([1.4, 1.0])

    with col_cat:
        st.markdown("#### 📌 세부 직무별 강좌 수 (INCLUDED 기준)")
        cat_counts = df_inc["job_category"].value_counts().reset_index()
        cat_counts.columns = ["세부직무", "강좌수"]
        fig_cat = px.bar(
            cat_counts,
            x="강좌수",
            y="세부직무",
            orientation="h",
            text="강좌수",
            color="강좌수",
            color_continuous_scale="Blues",
            title="세부 직무 카테고리별 공급 현황",
            template="plotly_white"
        )
        fig_cat.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        fig_cat.update_traces(texttemplate="%{text}건", textposition="outside")
        st.plotly_chart(fig_cat, use_container_width=True)

    with col_src:
        st.markdown("#### 🌐 데이터 수집 출처 비중")
        src_counts = df_all["source_type"].value_counts().reset_index()
        src_counts.columns = ["출처유형", "강좌수"]
        fig_src = px.pie(
            src_counts,
            names="출처유형",
            values="강좌수",
            title=f"공공 API vs SQLite DB (전체 {total_cand}건)",
            color_discrete_map={"PUBLIC_API": "#2980b9", "SQLITE_DB": "#e67e22"},
            template="plotly_white"
        )
        st.plotly_chart(fig_src, use_container_width=True)

    st.info("💡 **데이터 해석 안내**: 본 집계는 고유 교육과정 식별자(global_course_key) 기준이며, 단순 중복이 제거된 상태입니다.")

# ------------------------------------------------------------------------------
# 4. 탭 2: 교육과정 탐색 (Course Explorer)
# ------------------------------------------------------------------------------
def render_tab2_explorer(df_all):
    st.markdown("### 🔍 인사·총무 교육과정 다차원 탐색기")
    st.caption("직무, 플랫폼, 난이도 및 키워드 필터를 활용하여 적합한 교육과정을 실시간으로 검색합니다.")

    # 필터 섹션
    with st.expander("🛠️ 검색 필터 설정 (여기를 클릭하여 조건 변경)", expanded=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            status_options = ["INCLUDED (직무 적합 확정)", "전체 과정 보기", "REVIEW_NEEDED (검토 대기)", "EXCLUDED (제외 과정)"]
            selected_status_label = st.selectbox("데이터 상태 필터", status_options, index=0)
            
        with f_col2:
            jg_list = ["전체 직무군"] + sorted(list(df_all["job_group"].unique()))
            selected_jg = st.selectbox("상위 직무군", jg_list, index=0)
            
        with f_col3:
            plat_list = ["전체 플랫폼"] + sorted(list(df_all["source_platform"].unique()))
            selected_plat = st.selectbox("수집 플랫폼", plat_list, index=0)

        f_col4, f_col5, f_col6 = st.columns(3)
        with f_col4:
            # 세부직무 필터 (선택된 직무군에 연동)
            if selected_jg != "전체 직무군":
                cat_available = sorted(list(df_all[df_all["job_group"] == selected_jg]["job_category"].unique()))
            else:
                cat_available = sorted(list(df_all["job_category"].unique()))
            selected_cat = st.selectbox("세부 직무", ["전체 세부직무"] + cat_available, index=0)

        with f_col5:
            level_list = ["전체 난이도"] + sorted(list(df_all["course_level"].dropna().unique()))
            selected_level = st.selectbox("교육 난이도", level_list, index=0)

        with f_col6:
            search_kw = st.text_input("과정명 키워드 검색", placeholder="예: 채용, 노무, 엑셀, 평가")

    # 필터 적용
    filtered_df = df_all.copy()

    # 상태 필터링
    if selected_status_label.startswith("INCLUDED"):
        filtered_df = filtered_df[filtered_df["classification_status"] == "INCLUDED"]
    elif selected_status_label.startswith("REVIEW"):
        filtered_df = filtered_df[filtered_df["classification_status"] == "REVIEW_NEEDED"]
    elif selected_status_label.startswith("EXCLUDED"):
        filtered_df = filtered_df[filtered_df["classification_status"] == "EXCLUDED"]

    # 직무군
    if selected_jg != "전체 직무군":
        filtered_df = filtered_df[filtered_df["job_group"] == selected_jg]

    # 세부직무
    if selected_cat != "전체 세부직무":
        filtered_df = filtered_df[filtered_df["job_category"] == selected_cat]

    # 플랫폼
    if selected_plat != "전체 플랫폼":
        filtered_df = filtered_df[filtered_df["source_platform"] == selected_plat]

    # 난이도
    if selected_level != "전체 난이도":
        filtered_df = filtered_df[filtered_df["course_level"] == selected_level]

    # 검색어
    if search_kw.strip():
        filtered_df = filtered_df[
            filtered_df["course_name"].str.contains(search_kw.strip(), case=False, na=False) |
            filtered_df["institution_name"].str.contains(search_kw.strip(), case=False, na=False)
        ]

    # 결과 통계 안내
    res_count = len(filtered_df)
    st.markdown(f"**총 `{res_count:,}`건의 교육과정이 조회되었습니다.**")

    if res_count == 0:
        st.warning("⚠️ 선택하신 검색 조건에 부합하는 교육과정이 없습니다. 필터를 완화해 보세요.")
        return

    # 표 표시용 데이터 가공
    display_df = pd.DataFrame({
        "상태": filtered_df["classification_status"],
        "교육과정명": filtered_df["course_name"],
        "교육기관": filtered_df["institution_name"],
        "직무군": filtered_df["job_group"],
        "세부직무": filtered_df["job_category"],
        "난이도": filtered_df["course_level"],
        "교육시간": filtered_df["training_hours"].apply(format_hours),
        "수강료": filtered_df["course_fee"].apply(format_fee),
        "플랫폼": filtered_df["source_platform"],
        "상세URL": filtered_df["course_url"].apply(lambda u: str(u) if pd.notna(u) and str(u).startswith("http") else None)
    })

    # 인터랙티브 테이블 표시 (Streamlit LinkColumn 지원)
    st.dataframe(
        display_df,
        column_config={
            "상세URL": st.column_config.LinkColumn("상세페이지", display_text="바로가기 🔗"),
            "상태": st.column_config.TextColumn("검증상태", help="INCLUDED: 직무적합, REVIEW: 검토대기, EXCLUDED: 제외")
        },
        hide_index=True,
        use_container_width=True,
        height=480
    )

    # CSV 다운로드 버튼
    csv_bytes = filtered_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        label="📥 현재 필터 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="filtered_courses_step4.csv",
        mime="text/csv"
    )

# ------------------------------------------------------------------------------
# 5. 탭 3: 직무역량 KSA 분석 렌더러
# ------------------------------------------------------------------------------
def render_tab3_competency(datasets):
    df_comp = datasets["competencies"]
    df_map = datasets["mapping"]
    df_cand = datasets["candidates"]
    df_job_comp = datasets["job_competencies"]
    df_jobs = datasets["jobs"]

    st.markdown("### 🧠 NCS 직무역량 KSA 구조 및 교육 공급 분석")
    st.caption("NCS 공식 표준 역량 체계와 현재 확보된 교육과정 간의 연계 상태를 분석합니다.")

    # 1. 상단 통계 카드
    total_comps = len(df_comp)
    total_mappings = len(df_map)
    # 역량별 강좌 수 계산
    comp_course_counts = df_map["competency_id"].value_counts().to_dict()
    rich_comps = sum(1 for cid in df_comp["competency_id"] if comp_course_counts.get(cid, 0) >= 20)
    zero_comps = sum(1 for cid in df_comp["competency_id"] if comp_course_counts.get(cid, 0) == 0)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("NCS 핵심 역량", f"{total_comps}개", help="인사·총무 핵심 KSA 마스터 역량")
    with mc2:
        st.metric("총 역량 매핑 관계", f"{total_mappings:,}행", help="확정 교육과정과의 1:1 또는 1:N 매핑 관계")
    with mc3:
        st.metric("충분 공급 역량 (20건↑)", f"{rich_comps}개", "채용/문서/노무 등 풍부")
    with mc4:
        st.metric("공급 사각지대 (0건)", f"{zero_comps}개", "애자일 프로젝트 관리", delta_color="inverse")

    st.markdown("---")

    # 2. 역량별 교육 공급 차트 & KSA 분포 차트
    c_left, c_right = st.columns([1.4, 1.0])

    with c_left:
        st.markdown("#### 🎯 NCS 7대 핵심 역량별 교육 공급 현황")
        df_comp_chart = df_comp.copy()
        df_comp_chart["강좌수"] = df_comp_chart["competency_id"].apply(lambda cid: comp_course_counts.get(cid, 0))
        df_comp_chart = df_comp_chart.sort_values(by="강좌수", ascending=True)

        fig_comp = px.bar(
            df_comp_chart,
            x="강좌수",
            y="competency_name",
            orientation="h",
            text="강좌수",
            color="ksa_type",
            title="역량별 확정 교육과정 공급 수",
            labels={"competency_name": "핵심 역량명", "강좌수": "연결 강좌 수 (건)", "ksa_type": "KSA 유형"},
            color_discrete_map={"Skill": "#3498db", "Knowledge": "#9b59b6", "Attitude": "#1abc9c"},
            template="plotly_white"
        )
        fig_comp.update_traces(texttemplate="%{text}건", textposition="outside")
        st.plotly_chart(fig_comp, use_container_width=True)

    with c_right:
        st.markdown("#### 🧩 KSA 유형별 역량 분포")
        ksa_summary = df_comp["ksa_type"].value_counts().reset_index()
        ksa_summary.columns = ["KSA유형", "역량개수"]
        fig_ksa = px.pie(
            ksa_summary,
            names="KSA유형",
            values="역량개수",
            title="7대 역량의 K/S/A 구성 비율",
            color="KSA유형",
            color_discrete_map={"Skill": "#3498db", "Knowledge": "#9b59b6", "Attitude": "#1abc9c"},
            template="plotly_white"
        )
        st.plotly_chart(fig_ksa, use_container_width=True)

    # 3. 7대 핵심 역량 마스터 정보 테이블
    st.markdown("#### 📋 NCS 7대 핵심 역량 마스터 명세")
    df_comp_table = pd.DataFrame({
        "역량 ID": df_comp["competency_id"],
        "NCS 능력단위코드": df_comp["ncs_unit_code"],
        "역량명": df_comp["competency_name"],
        "KSA 유형": df_comp["ksa_type"],
        "공급 강좌수": df_comp["competency_id"].apply(lambda cid: f"{comp_course_counts.get(cid, 0)}건"),
        "역량 정의 및 설명": df_comp["definition"]
    })
    st.dataframe(df_comp_table, hide_index=True, use_container_width=True)

    # 4. 분석 해석 주의사항 공지
    st.warning("""
    ⚠️ **데이터 해석 시 주의사항 (Disclaimers)**
    1. **역량 공급 측정치**: 본 대시보드에 표시된 역량별 연결 강좌 수는 '교육 시장의 공급 현황'을 측정한 것이며, **실제 직원의 역량 부족 수준을 측정한 결과가 아닙니다.**
    2. **공식 NCS와 프로젝트 정의 구분**: '애자일 프로젝트 관리' 등 일부 항목은 최신 디지털 전환 수요를 반영하기 위해 공식 NCS 직무체계에 프로젝트 자체 가설로 연계된 항목입니다.
    """)

# ------------------------------------------------------------------------------
# 6. 탭 4: 교육과정 텍스트 분석 (키워드·군집화·검색) 렌더러
#    - 분석은 로컬에서 scripts/export_text_analysis_dashboard.py로 수행하고 결과 CSV만 읽습니다.
# ------------------------------------------------------------------------------
TEXT_DIR = WORKSPACE_ROOT / "data" / "hr" / "output" / "dashboard" / "text_analysis"
SEMANTIC_DIR = WORKSPACE_ROOT / "data" / "hr" / "output" / "semantic"


@st.cache_data(show_spinner=False)
def load_text_analysis():
    """텍스트 분석 결과 CSV 로드 (3단계 검색 평가 결과는 있으면 함께 로드)"""
    data = {
        name: pd.read_csv(TEXT_DIR / f"{name}.csv")
        for name in ["cleaning_summary", "keyword_top50", "k_selection", "cluster_summary", "lda_topics", "course_text_features"]
    }
    data["course_text_features"]["tokens"] = data["course_text_features"]["tokens"].fillna("")
    for name in ["retrieval_eval_summary", "semantic_search_examples"]:
        path = SEMANTIC_DIR / f"{name}.csv"
        data[name] = pd.read_csv(path) if path.exists() else None
    return data


@st.cache_data(show_spinner=False)
def build_bm25_index(token_strings):
    """과정별 토큰 문자열로 BM25(k1=1.5, b=0.75) 계산에 필요한 통계를 만듭니다."""
    docs = [s.split() for s in token_strings]
    doc_tf = [pd.Series(d, dtype=str).value_counts().to_dict() for d in docs]
    doc_len = np.array([len(d) for d in docs], dtype=float)
    doc_freq = pd.Series([t for d in docs for t in set(d)], dtype=str).value_counts().to_dict()
    vocab = sorted(doc_freq, key=len, reverse=True)
    return doc_tf, doc_len, doc_freq, vocab


def bm25_search(query, doc_tf, doc_len, doc_freq, vocab, k1=1.5, b=0.75):
    """질의에 포함된 어휘 단어를 찾아 BM25 점수를 계산합니다 (형태소 분석기 없이 동작)."""
    q = query.lower()
    q_compact = q.replace(" ", "")
    matched = [t for t in vocab if t in q or t in q_compact]
    # 더 긴 단어의 일부인 단어는 제외 (예: '연말정산'이 있으면 '연말', '정산' 제외)
    matched = [t for t in matched if not any(t != o and t in o for o in matched)]
    n_docs = len(doc_tf)
    scores = np.zeros(n_docs)
    avg_len = doc_len.mean()
    for term in matched:
        df = doc_freq[term]
        idf = np.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        tf = np.array([d.get(term, 0) for d in doc_tf], dtype=float)
        scores += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len / avg_len))
    return scores, matched


def render_tab4_text_analysis():
    st.markdown("### 🔤 교육과정 텍스트 분석 (키워드 · 군집화 · 검색)")
    st.caption(
        "295개 교육과정의 제목·소개글·커리큘럼을 한국어 형태소 분석(kiwipiepy)으로 쪼개고, "
        "TF-IDF로 핵심 키워드를 뽑고, K-Means로 비슷한 강의끼리 자동으로 묶었습니다."
    )

    try:
        data = load_text_analysis()
    except FileNotFoundError:
        st.warning("텍스트 분석 결과 파일이 없습니다. `scripts/export_text_analysis_dashboard.py`를 먼저 실행해 주세요.")
        return

    features = data["course_text_features"]
    cluster_summary = data["cluster_summary"]
    cleaning = data["cleaning_summary"].set_index("item")["value"]
    k_sel = data["k_selection"]
    n_clusters = int(cluster_summary["cluster"].nunique())
    silhouette = float(k_sel.loc[k_sel["k"] == n_clusters, "silhouette"].iloc[0])

    # 1. KPI 카드
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("분석 교육과정", f"{int(cleaning['전체 과정'])}개", help="data/processed/hr_courses_detailed_295.csv")
    with c2:
        st.metric(
            "자동생성 커리큘럼 제외",
            f"{int(cleaning['템플릿 커리큘럼 (분석 제외)'])}개",
            help="같은 틀로 찍어낸 커리큘럼 문장은 실제 강의 내용이 아니어서 분석에서 뺐습니다.",
        )
    with c3:
        st.metric("분석 어휘", f"{int(cleaning['분석 어휘 수']):,}개", help="2개 이상 과정에 등장하고, 전체 50% 이하에 등장하는 단어")
    with c4:
        st.metric("자동 군집", f"{n_clusters}개", f"실루엣 {silhouette:.3f}", delta_color="off",
                  help="실루엣 점수(-1~1)는 군집이 얼마나 잘 나뉘었는지 나타냅니다. 0에 가까울수록 경계가 흐릿합니다.")

    with st.expander("🧹 데이터를 어떻게 정제했나요?"):
        st.markdown(f"""
- **자동생성 커리큘럼 제거**: 295개 중 {int(cleaning['템플릿 커리큘럼 (분석 제외)'])}개는 "○○ 핵심 프로세스 실습 // 실무 서식 작성…"처럼 같은 틀로 만든 문장이라 제외했습니다.
- **학원 홍보 문구 제거**: 서로 다른 강의 3개 이상에 똑같이 나오는 문장(학원 소개, 취업지원 안내 등)을 지웠습니다.
  소개글 평균 길이 {int(cleaning['평균 소개글 길이 (정제 전)'])}자 → {int(cleaning['평균 소개글 길이 (정제 후)'])}자
- **회차 표기 통합**: "(○○학원 2회차)" 꼬리표를 떼어 같은 강의로 봤습니다 (고유 강의명 {int(cleaning['고유 강의명 (회차 통합)'])}개).
- **단어 쪼개기**: "인사노무관리" → 인사 / 노무 / 인사노무 / 노무관리. "연말정산", "4대보험" 같은 인사 용어는 사전에 등록해 그대로 유지했습니다.
""")

    st.markdown("---")

    # 2. 핵심 키워드 & 군집 크기
    col_kw, col_cl = st.columns(2)
    with col_kw:
        st.markdown("#### 🏷️ 전체 핵심 키워드 Top 20 (TF-IDF)")
        kw = data["keyword_top50"].head(20).iloc[::-1]
        fig_kw = px.bar(
            kw, x="tfidf_sum", y="keyword", orientation="h",
            labels={"tfidf_sum": "TF-IDF 합계 (중요도)", "keyword": "", "doc_freq": "등장 과정 수"},
            hover_data=["doc_freq"], template="plotly_white", color_discrete_sequence=["#3498db"],
        )
        fig_kw.update_layout(height=520, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_kw, width="stretch")
        st.caption("어디에나 나오는 단어(강의, 실무, 과정 …)는 점수를 낮추고, 특정 강의에만 나오는 단어는 점수를 높인 결과입니다.")

    with col_cl:
        st.markdown(f"#### 🧩 자동 분류된 {n_clusters}개 군집")
        cl = cluster_summary.sort_values("n_courses")
        fig_cl = px.bar(
            cl, x="n_courses", y="cluster_label", orientation="h", text="n_courses",
            labels={"n_courses": "강좌 수", "cluster_label": "", "top_keywords": "대표 키워드"},
            hover_data=["top_keywords"], template="plotly_white",
            color="cluster_label", color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_cl.update_layout(height=520, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_cl, width="stretch")
        st.caption("군집 이름은 각 군집에서 가장 특징적인 키워드 3개로 자동으로 붙였습니다.")

    st.markdown("---")

    # 3. 군집 지도 & 군집별 강좌
    st.markdown("#### 🗺️ 교육과정 군집 지도")
    st.caption("가까이 있는 점일수록 쓰인 단어가 비슷한 강의입니다. 점에 마우스를 올리면 강의명이 보입니다.")
    fig_map = px.scatter(
        features, x="x", y="y", color="cluster_label",
        hover_name="course_title", hover_data={"platform": True, "top_keywords": True, "x": False, "y": False},
        labels={"cluster_label": "군집", "platform": "플랫폼", "top_keywords": "핵심 키워드"},
        template="plotly_white", color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_map.update_traces(marker=dict(size=9, opacity=0.8))
    fig_map.update_layout(height=520, xaxis_title="", yaxis_title="", xaxis_showticklabels=False, yaxis_showticklabels=False)
    st.plotly_chart(fig_map, width="stretch")

    sel_label = st.selectbox(
        "군집을 선택하면 소속 강좌를 보여줍니다",
        cluster_summary["cluster_label"].tolist(),
        format_func=lambda lb: f"{lb} ({int(cluster_summary.set_index('cluster_label').at[lb, 'n_courses'])}개)",
    )
    sel_row = cluster_summary.set_index("cluster_label").loc[sel_label]
    st.markdown(f"**대표 키워드:** {sel_row['top_keywords']}")
    st.dataframe(
        features.loc[features["cluster_label"] == sel_label, ["course_title", "platform", "institution", "top_keywords", "url"]],
        column_config={
            "course_title": "강좌명", "platform": "플랫폼", "institution": "기관", "top_keywords": "핵심 키워드",
            "url": st.column_config.LinkColumn("상세 링크", display_text="바로가기"),
        },
        hide_index=True, width="stretch",
    )

    with st.expander("📚 LDA 토픽 모델링 결과 (강의마다 여러 주제가 섞여 있다고 보는 방식)"):
        st.dataframe(
            data["lda_topics"],
            column_config={"topic": "토픽", "n_main_courses": "주 토픽 강좌 수", "top_words": "대표 단어"},
            hide_index=True, width="stretch",
        )
    with st.expander("📈 군집 수(k)에 따른 실루엣 점수"):
        fig_k = px.line(k_sel, x="k", y="silhouette", markers=True, template="plotly_white",
                        labels={"k": "군집 수 k", "silhouette": "실루엣 점수"})
        st.plotly_chart(fig_k, width="stretch")
        st.caption("모든 k에서 0.03~0.06 수준으로 낮아, 군집은 '대략적인 주제 묶음'으로 해석해야 합니다.")

    st.markdown("---")

    # 4. 키워드 검색 (BM25)
    st.markdown("#### 🔍 키워드 검색 (BM25)")
    st.caption("배우고 싶은 내용을 입력하면 단어가 일치하는 강의를 찾습니다. 검색 엔진(Elasticsearch 등)의 표준 점수 방식입니다.")
    doc_tf, doc_len, doc_freq, vocab = build_bm25_index(tuple(features["tokens"]))
    sc1, sc2 = st.columns([4, 1])
    with sc1:
        query = st.text_input("검색어", value="급여 계산 4대보험 연말정산", key="tab4_bm25_query")
    with sc2:
        top_n = st.number_input("결과 개수", min_value=3, max_value=30, value=10, key="tab4_bm25_topn")
    scores, matched = bm25_search(query, doc_tf, doc_len, doc_freq, vocab)
    if not matched:
        st.info("검색어에서 분석 어휘에 있는 단어를 찾지 못했습니다. 다른 단어로 검색해 보세요.")
    else:
        order = np.argsort(-scores)[: int(top_n)]
        order = order[scores[order] > 0]
        st.markdown(f"**인식된 검색 단어:** {', '.join(matched)} · 일치 강좌 {int((scores > 0).sum())}개")
        st.dataframe(
            features.iloc[order][["course_title", "platform", "institution", "cluster_label", "url"]].assign(
                bm25=scores[order].round(2)
            ),
            column_config={
                "course_title": "강좌명", "platform": "플랫폼", "institution": "기관", "cluster_label": "군집",
                "bm25": st.column_config.NumberColumn("BM25 점수", format="%.2f"),
                "url": st.column_config.LinkColumn("상세 링크", display_text="바로가기"),
            },
            hide_index=True, width="stretch",
        )
    st.caption("⚠️ 단어가 같아야 찾습니다. '월급'으로는 '급여' 강의를 못 찾는데, 이 문제는 언어모델 기반 의미 검색(3단계)에서 다룹니다.")

    # 5. 검색 방식 비교 (3단계 평가 결과가 있을 때)
    eval_summary = data["retrieval_eval_summary"]
    if eval_summary is not None:
        st.markdown("---")
        st.markdown("#### ⚖️ 검색 방식 비교 (3단계 의미 유사도 평가)")
        st.caption(
            "강의 제목과 다른 단어로 바꿔 쓴 질문 12개(예: '표 계산 프로그램' → 엑셀 강의)로 각 검색 방식을 채점했습니다. "
            "Hit@5 = 상위 5개 안에 정답이 있는 비율, MRR@10 = 첫 정답 순위의 역수 평균(1등이면 1.0)."
        )
        eval_long = eval_summary.melt(id_vars="method", var_name="지표", value_name="점수")
        fig_eval = px.bar(
            eval_long, x="지표", y="점수", color="method", barmode="group", text_auto=".2f",
            labels={"method": "검색 방식"}, template="plotly_white", range_y=[0, 1],
        )
        st.plotly_chart(fig_eval, width="stretch")
        if not eval_summary["method"].str.contains("언어모델").any():
            st.info("🧠 한국어 언어모델(ko-sroberta) 임베딩 결과는 준비 중입니다. 현재는 키워드 방식(BM25, LSA)만 비교되어 있습니다.")

        examples = data["semantic_search_examples"]
        if examples is not None:
            ex_query = st.selectbox("예시 질문별 검색 결과 비교", examples["query"].unique().tolist(), key="tab4_example_query")
            ex = examples[examples["query"] == ex_query]
            ex_cols = st.columns(ex["method"].nunique())
            for col, (method, grp) in zip(ex_cols, ex.groupby("method", sort=False)):
                with col:
                    st.markdown(f"**{method}**")
                    for _, r in grp.iterrows():
                        st.markdown(f"{r['rank']}. {r['course_title']}")

    # 6. 해석 주의사항
    st.warning("""
    ⚠️ **텍스트 분석 해석 시 주의사항**
    1. **군집 경계가 흐릿합니다**: 강의 소개글이 짧고, 220개 과정은 실제 커리큘럼이 없어 군집은 '대략적인 주제 묶음'으로 봐야 합니다.
    2. **계획했던 4대 군집(채용·노무·평가보상·총무)은 그대로 나타나지 않았습니다**: 수집 강좌 대부분이 총무·사무행정(286개)이고 인사(HR) 강좌는 9개뿐이기 때문입니다.
    3. **직무와 무관한 강좌가 섞여 있습니다**: 마케팅, 개발, 사주 서비스 등은 추천 대상에서 제외 기준을 정할 때 군집 결과를 참고할 수 있습니다.
    """)

# ------------------------------------------------------------------------------
# 7. 메인 앱 진입점
# ------------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="NCS 인사·총무 직무교육 대시보드 MVP",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    st.markdown("""
    <style>
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        [data-testid="stHorizontalBlock"] > div { min-width: 100% !important; }
        h1 { font-size: 1.65rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    # 상단 헤더
    st.title("🎓 NCS 기반 인사·총무 직무역량 분석 및 교육과정 대시보드")
    st.markdown("**STEP 4 MVP** | 공공 API 및 7개 민간/공공 플랫폼 교육 데이터 통합 검증 및 시각화")

    # 데이터 로드
    try:
        with st.spinner("교육과정과 NCS 역량 데이터를 불러오는 중입니다..."):
            datasets = load_all_datasets()
    except Exception as e:
        st.error("데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.")
        st.info("문제가 계속되면 GitHub Issue로 오류 화면과 접속 시각을 알려주세요. 데이터 파일 경로(`data/hr/output/integration/` 등)도 함께 점검해 주세요.")
        return

    # 사용자가 바로 목표 직무·부족 역량·추천 과정·진척을 연결해 볼 수 있는 학습 여정
    render_learning_journey(datasets)
    render_service_support()

    st.markdown("---")
    st.markdown("## 🔎 데이터 탐색과 근거 확인")
    st.caption("아래 분석 탭에서 추천의 원천 데이터와 역량-교육과정 연결 구조를 직접 확인할 수 있습니다.")

    # 3개 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 TAB 1. 교육 데이터 현황",
        "🔍 TAB 2. 교육과정 탐색",
        "🧠 TAB 3. 직무역량 KSA 분석",
        "🔤 TAB 4. 텍스트 분석·군집화"
    ])

    with tab1:
        render_tab1_overview(datasets["candidates"])

    with tab2:
        render_tab2_explorer(datasets["candidates"])

    with tab3:
        render_tab3_competency(datasets)

    with tab4:
        render_tab4_text_analysis()

    # 푸터
    st.markdown("---")
    st.caption("NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천 프로젝트 | GitHub: [kimsaemi/edu-skill-gap](https://github.com/kimsaemi/edu-skill-gap)")

if __name__ == "__main__":
    main()
