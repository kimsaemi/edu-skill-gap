"""
NCS 기반 인사·총무 교육 데이터 대시보드 (STEP 4 MVP)
- 실행: streamlit run app/streamlit_step4.py
- 데이터 출처: 공공 API (140건) + 7대 민간/공공 플랫폼 SQLite DB (413건) 통합 데이터셋
- 구성:
    TAB 1. 교육 데이터 현황 (KPI 카드, 플랫폼/직무/출처 분포)
    TAB 2. 교육과정 탐색 (다차원 실시간 필터링, 정렬, 상세 링크)
    TAB 3. 직무역량 KSA 분석 (NCS 7대 핵심 역량 매핑 및 KSA 분포)
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
    # NCS 역량 마스터의 실무 기술(skill)에서 정제된 업무 선택지 도출 (안정적인 task_id 부여)
    task_catalog = {}
    task_labels = []
    for task_row in task_source.itertuples():
        c_id = task_row.competency_id
        c_name = task_row.competency_name
        skill_raw = str(task_row.skill) if pd.notna(task_row.skill) else ""
        raw_items = [s.strip() for s in skill_raw.replace("/", ",").replace("\n", ",").split(",") if s.strip()]
        for idx, item in enumerate(raw_items, start=1):
            if item.lower() in ["nan", "none", "-"]:
                continue
            task_id = f"TASK_{c_id}_{idx:02d}"
            label = f"{item} (연계 역량: {c_name})"
            task_catalog[label] = {
                "task_id": task_id,
                "task_name": item,
                "competency_id": c_id,
                "competency_name": c_name
            }
            task_labels.append(label)

    with diagnosis_col:
        st.markdown("**실제 수행 중인 업무 (복수 선택)**")
        st.caption("NCS 역량 마스터의 실무 기술(Skill) 항목에서 도출한 안정적 업무 선택지입니다.")
        default_tasks = task_labels if current_level == "입문" else task_labels[:2]
        selected_tasks = st.multiselect(
            "수행 중인 세부 업무",
            task_labels,
            default=default_tasks,
            help="선택한 업무의 연계 역량과 과정만 추천 우선순위에 반영합니다.",
            key=f"learning_tasks_{selected_job_id}",
        )
        with st.expander("기타 업무가 있나요? (선택)"):
            custom_task = st.text_input(
                "목록에 없는 업무만 직접 입력", placeholder="예: 해외 지사 인사운영 지원", key=f"learning_custom_task_{selected_job_id}"
            )

    selected_competency_ids = list(dict.fromkeys(
        task_catalog[task]["competency_id"] for task in selected_tasks if task in task_catalog
    ))
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
        st.warning("선택한 역량과 직접 연결된 전처리 선별 교육과정이 아직 없습니다. 탐색 탭에서 검토 대기 과정까지 확인해 보세요.")
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
        st.progress(completion / len(recommendations), text="자가 학습 완료율 (자기 기록용)")

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
                    f"출처: {course.source_platform} ({course.source_type}) · 데이터 수집 시점: {format_collected_at(course.collected_at)} · "
                    "완료 기준: 학습자가 수강기관의 수료 기준을 충족한 뒤 이 화면에서 체크하는 자가 학습 기록 (자가 체크로 역량 점수가 자동 상승하지 않음)"
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
# 6. 메인 앱 진입점
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
    tab1, tab2, tab3 = st.tabs([
        "📊 TAB 1. 교육 데이터 현황", 
        "🔍 TAB 2. 교육과정 탐색", 
        "🧠 TAB 3. 직무역량 KSA 분석"
    ])

    with tab1:
        render_tab1_overview(datasets["candidates"])

    with tab2:
        render_tab2_explorer(datasets["candidates"])

    with tab3:
        render_tab3_competency(datasets)

    # 푸터
    st.markdown("---")
    st.caption("NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천 프로젝트 | GitHub: [kimsaemi/edu-skill-gap](https://github.com/kimsaemi/edu-skill-gap)")

if __name__ == "__main__":
    main()
