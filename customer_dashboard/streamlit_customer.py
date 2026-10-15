"""
고객용 역량 자기점검 및 맞춤 교육 추천 서비스 (Customer MVP)
- 실행 명령어: streamlit run app/streamlit_customer.py
- 대상: 인사·총무·경영지원 실무 재직자
- 주요 메뉴: 
    1) 📋 내 역량 점검 (업무 설정 -> 행동 기반 점검 -> 수준 및 갭 분석)
    2) 🎓 맞춤 교육 (역량 갭 기반 실제 교육 추천, 커리큘럼 근거, 대체 수강처)
    3) 📚 나의 학습 (관심 강좌 보관함, 3개 비교, 상태 관리 및 재점검 히스토리)
- 원칙:
    - 챗봇/외부 LLM 배제
    - 내부 기술 용어(TF-IDF, BM25, 군집ID) 미노출
    - 2문항 미만 정보 부족 처리, 0점 처리 방지
    - 강좌 수료 시 역량 점수 자동 조작 금지
    - Lucian UX 모던 디자인 토큰 적용
"""

import sys
import copy
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# 프로젝트 루트 경로 등록
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.assessment.questions_data import (
    ASSESSMENT_QUESTIONS,
    STANDARD_RESPONSE_ANCHORS,
    get_questions_for_job,
    get_tasks_for_job
)
from src.assessment.evaluator import (
    calculate_competency_scores,
    get_sample_assessment_result,
    AssessmentEvaluationResult,
    CompetencyScore
)
from src.assessment.recommendation_bridge import (
    get_recommendations_for_assessment,
    RecommendationFilterParams,
    RecommendedCourseCard,
    CustomerRecommendationBundle,
    get_shared_recommender
)
from src.recommendation.ksa_master import KSA_COMPETENCIES_MASTER

# ------------------------------------------------------------------------------
# 1. 스트림릿 페이지 설정 및 Lucian UX 디자인 토큰 주입
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="역량 자기점검 & 맞춤 교육 추천",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
  --ux-page: #F8FAFC;
  --ux-surface: #FFFFFF;
  --ux-surface-sub: #F1F5F9;
  --ux-surface-border: #E2E8F0;
  --ux-ink-primary: #0F172A;
  --ux-ink-secondary: #475569;
  --ux-ink-muted: #94A3B8;
  --ux-primary: #4F46E5;
  --ux-primary-hover: #4338CA;
  --ux-primary-soft: #EEF2FF;
  --ux-accent-teal: #0D9488;
  --ux-accent-amber: #D97706;
  --ux-accent-rose: #E11D48;
  --ux-radius-sm: 8px;
  --ux-radius-md: 12px;
  --ux-radius-lg: 16px;
  --ux-shadow-card: 0 4px 20px -2px rgba(15, 23, 42, 0.06);
  --ux-shadow-hover: 0 10px 25px -4px rgba(79, 70, 229, 0.12);
}

html, body, [class*="css"] {
  font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
  color: var(--ux-ink-primary);
  background-color: var(--ux-page);
}

/* 상단 히어로 배너 */
.hero-banner {
  background: linear-gradient(135deg, #1E1B4B 0%, #312E81 50%, #4338CA 100%);
  color: #FFFFFF;
  padding: 2.2rem 2.4rem;
  border-radius: var(--ux-radius-lg);
  margin-bottom: 1.8rem;
  box-shadow: 0 10px 25px -5px rgba(49, 46, 129, 0.35);
}
.hero-title {
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin-bottom: 0.5rem;
  color: #FFFFFF;
}
.hero-subtitle {
  font-size: 0.98rem;
  font-weight: 400;
  color: #E0E7FF;
  line-height: 1.6;
}

/* 고객 카드 컨테이너 */
.customer-card {
  background: var(--ux-surface);
  border: 1px solid var(--ux-surface-border);
  border-radius: var(--ux-radius-md);
  padding: 1.5rem;
  margin-bottom: 1.2rem;
  box-shadow: var(--ux-shadow-card);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.customer-card:hover {
  box-shadow: var(--ux-shadow-hover);
  border-color: #CBD5E1;
}

/* 태그 뱃지 */
.badge-tag {
  display: inline-block;
  padding: 0.25rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 600;
  margin-right: 0.4rem;
  margin-bottom: 0.4rem;
}
.badge-primary { background: #EEF2FF; color: #4F46E5; border: 1px solid #C7D2FE; }
.badge-teal { background: #CCFBF1; color: #0F766E; border: 1px solid #99F6E4; }
.badge-amber { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; }
.badge-rose { background: #FFE4E6; color: #BE123C; border: 1px solid #FECDD3; }
.badge-neutral { background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; }

/* 대체 수강 옵션 박스 */
.alt-offering-box {
  background: #F8FAFC;
  border-left: 3.5px solid #4F46E5;
  padding: 0.85rem 1.1rem;
  border-radius: 0 var(--ux-radius-sm) var(--ux-radius-sm) 0;
  margin-top: 0.85rem;
  font-size: 0.84rem;
}

/* 안내 및 주의 콜아웃 */
.callout-info {
  background: #EFF6FF;
  border-left: 4px solid #3B82F6;
  padding: 1rem 1.25rem;
  border-radius: 0 var(--ux-radius-sm) var(--ux-radius-sm) 0;
  font-size: 0.88rem;
  color: #1E40AF;
  margin-bottom: 1.2rem;
}
.callout-warning {
  background: #FFFBEB;
  border-left: 4px solid #F59E0B;
  padding: 1rem 1.25rem;
  border-radius: 0 var(--ux-radius-sm) var(--ux-radius-sm) 0;
  font-size: 0.88rem;
  color: #92400E;
  margin-bottom: 1.2rem;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. 세션 상태 초기화 및 관리
# ------------------------------------------------------------------------------
def init_session_state():
    """사용자 세션 상태를 안전하게 초기화합니다."""
    defaults = {
        "job_family": "인사",
        "career_range": "3~5년차",
        "selected_tasks": ["TASK_HR_RECRUIT", "TASK_HR_ONBOARD"],
        "custom_task": "",
        "difficult_task": "신규 채용 공고 작성 및 직무 면접 질문 구성에 어려움이 있습니다.",
        "learning_goal": "채용 및 온보딩 실무 프로세스를 혼자서 완수하고 역량 강화",
        "weekly_hours": 4.0,
        "price_filter": "ALL",
        "max_budget": 0,
        "edu_type": "ALL",
        "survey_responses": {},
        "target_levels": {},
        "current_step": "STEP_PROFILE",  # STEP_PROFILE, STEP_SURVEY, STEP_RESULT
        "eval_result": None,
        "rec_bundle": None,
        "is_sample_mode": False,
        "saved_courses": {},  # course_uid -> dict
        "assessment_history": [],  # 재점검 기록 비교용
        "stale_results": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session_state()

def reset_all_assessment():
    """모든 설문과 진단 상태를 깨끗이 초기화하는 콜백 함수"""
    st.session_state["survey_responses"] = {}
    st.session_state["target_levels"] = {}
    st.session_state["eval_result"] = None
    st.session_state["rec_bundle"] = None
    st.session_state["is_sample_mode"] = False
    st.session_state["current_step"] = "STEP_PROFILE"
    st.session_state["stale_results"] = False

# ------------------------------------------------------------------------------
# 3. 상단 헤더 및 메뉴 탭 네비게이션
# ------------------------------------------------------------------------------
st.markdown("""
<div class="hero-banner">
  <div class="hero-title">🎯 실무 역량 자기점검 & 맞춤 교육 추천</div>
  <div class="hero-subtitle">
    인사·총무·경영지원 재직자를 위한 실무 중심 역량 진단 서비스입니다.<br>
    현재 수행 업무를 점검하고, 목표 수준과의 차이를 분석하여 최적의 실제 교육 과정을 추천합니다.
  </div>
</div>
""", unsafe_allow_html=True)

# 메인 탭 네비게이션
st.markdown('<div id="top-anchor"></div>', unsafe_allow_html=True)
tab_assessment, tab_recommend, tab_my_learning = st.tabs([
    "📋 내 역량 점검",
    "🎓 맞춤 교육",
    "📚 나의 학습"
])

# ------------------------------------------------------------------------------
# TAB 1: 내 역량 점검 (내 업무 설정 -> 행동 점검 -> 결과 확인)
# ------------------------------------------------------------------------------
with tab_assessment:
    # 상단 샘플 모드 알림 또는 바로보기 안내
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        if st.session_state["is_sample_mode"]:
            st.markdown("""
            <div class="callout-warning">
              <strong>📢 [샘플 결과 미리보기 모드]</strong> 현재 표시된 데이터는 가상의 진단 결과 샘플입니다. 
              실제 본인의 역량을 측정하시려면 아래 <strong>'새로 진단 시작'</strong> 버튼을 눌러주세요.
            </div>
            """, unsafe_allow_html=True)
    with top_col2:
        btn_sample_col1, btn_sample_col2 = st.columns(2)
        with btn_sample_col1:
            if st.button("👀 샘플 결과 보기", use_container_width=True, help="설문 작성 없이 예시 결과를 먼저 확인합니다."):
                sample_res = get_sample_assessment_result(st.session_state.get("job_family", "인사"))
                st.session_state["eval_result"] = sample_res
                st.session_state["is_sample_mode"] = True
                st.session_state["current_step"] = "STEP_RESULT"
                # 추천 번들 즉시 생성
                f_params = RecommendationFilterParams(
                    price_filter=st.session_state["price_filter"],
                    max_budget=st.session_state["max_budget"] if st.session_state["price_filter"] == "MAX_BUDGET" else None,
                    edu_type=st.session_state["edu_type"],
                    weekly_hours=st.session_state["weekly_hours"]
                )
                st.session_state["rec_bundle"] = get_recommendations_for_assessment(sample_res, f_params)
                st.rerun()
        with btn_sample_col2:
            st.button("🔄 전체 초기화", on_click=reset_all_assessment, use_container_width=True)

    # 1단계: 내 업무 설정 (프로필)
    st.subheader("1. 나의 업무 설정")
    with st.expander("💼 담당 직무 및 업무 환경 설정", expanded=(st.session_state["eval_result"] is None)):
        prof_col1, prof_col2 = st.columns(2)
        with prof_col1:
            job_choice = st.selectbox(
                "담당 직무 (필수)",
                options=["인사", "총무", "경영지원"],
                index=["인사", "총무", "경영지원"].index(st.session_state["job_family"]),
                key="sel_job_family"
            )
            if job_choice != st.session_state["job_family"]:
                st.session_state["job_family"] = job_choice
                st.session_state["survey_responses"] = {}
                st.session_state["eval_result"] = None
                st.session_state["stale_results"] = True

            career_choice = st.selectbox(
                "경력 구간 (참고용)",
                options=["1년 미만(신입)", "1~3년차", "3~5년차", "5~10년차", "10년 이상"],
                index=["1년 미만(신입)", "1~3년차", "3~5년차", "5~10년차", "10년 이상"].index(st.session_state["career_range"]),
                help="경력 구간은 학습 계획 수립을 위한 참고값이며, 경력만으로 역량 수준을 단정하지 않습니다."
            )
            st.session_state["career_range"] = career_choice

        with prof_col2:
            st.markdown("**주요 학습 조건**")
            p_filter = st.selectbox(
                "수강료 예산 조건",
                options=["전체 (유료+무료)", "무료 과정만", "예산 한도 설정"],
                index=0 if st.session_state["price_filter"] == "ALL" else (1 if st.session_state["price_filter"] == "FREE_ONLY" else 2)
            )
            if p_filter == "무료 과정만":
                st.session_state["price_filter"] = "FREE_ONLY"
                st.session_state["max_budget"] = 0
            elif p_filter == "예산 한도 설정":
                st.session_state["price_filter"] = "MAX_BUDGET"
                b_val = st.number_input("최대 수강료 한도(원)", min_value=10000, max_value=2000000, value=300000, step=50000)
                st.session_state["max_budget"] = b_val
            else:
                st.session_state["price_filter"] = "ALL"
                st.session_state["max_budget"] = None

            edu_t_choice = st.selectbox(
                "교육 형태 선호",
                options=["전체", "온라인 우선", "오프라인/집체 우선"],
                index=0 if st.session_state["edu_type"] == "ALL" else (1 if st.session_state["edu_type"] == "ONLINE" else 2)
            )
            st.session_state["edu_type"] = "ALL" if edu_t_choice == "전체" else ("ONLINE" if edu_t_choice == "온라인 우선" else "OFFLINE")

            w_hours = st.slider("주당 학습 가능 시간 (시간)", min_value=1.0, max_value=20.0, value=float(st.session_state["weekly_hours"]), step=0.5)
            st.session_state["weekly_hours"] = w_hours

        # 실제 수행 업무 선택
        st.markdown("---")
        st.markdown("**실제 수행 중인 업무 (복수 선택)**")
        st.caption("선택하신 업무는 부족 역량 진단 시 보완 우선순위(1순위) 산정에 반영됩니다.")
        
        job_tasks = get_tasks_for_job(st.session_state["job_family"])
        task_opts = {t["task_id"]: f"{t['task_name']} (연계 역량: {t['primary_comp_id']})" for t in job_tasks}
        
        selected_t_ids = st.multiselect(
            "수행 중인 세부 업무",
            options=list(task_opts.keys()),
            default=[t for t in st.session_state["selected_tasks"] if t in task_opts],
            format_func=lambda x: task_opts.get(x, x)
        )
        if selected_t_ids != st.session_state["selected_tasks"]:
            st.session_state["selected_tasks"] = selected_t_ids
            if st.session_state.get("eval_result") is not None:
                st.session_state["stale_results"] = True

        custom_t = st.text_input("직접 입력 (위 항목에 없는 추가 수행 업무)", value=st.session_state["custom_task"], placeholder="예: 해외 지사 노무 규정 검토")
        if custom_t != st.session_state["custom_task"]:
            st.session_state["custom_task"] = custom_t
            if st.session_state.get("eval_result") is not None:
                st.session_state["stale_results"] = True

        diff_t = st.text_area("현재 가장 어렵거나 보완이 시급한 업무", value=st.session_state["difficult_task"], placeholder="예: 사내 평가 프로세스 진행 시 부서 간 이견 조율이 어렵습니다.")
        if diff_t != st.session_state["difficult_task"]:
            st.session_state["difficult_task"] = diff_t
            if st.session_state.get("eval_result") is not None:
                st.session_state["stale_results"] = True

        goal_t = st.text_input("학습 목표", value=st.session_state["learning_goal"], placeholder="예: 3개월 내 채용 및 평가 보상 실무 역량 마스터")
        if goal_t != st.session_state["learning_goal"]:
            st.session_state["learning_goal"] = goal_t
            if st.session_state.get("eval_result") is not None:
                st.session_state["stale_results"] = True

    # 2단계: 역량 자기점검 문항 (직무별 8~12개 문항)
    st.subheader("2. 핵심 역량 자기점검 (행동 기준 척도)")
    st.markdown("""
    <div class="callout-info">
      📌 <strong>자기점검 안내 (Draft)</strong>: 본 진단은 NCS 및 실무 행동 지표를 참조하여 구성한 <strong>'자기점검용 초안'</strong>입니다. 
      공식 자격시험이나 인사평가 도구가 아니며, 실무 역량 보완을 위한 학습 가이드로 활용됩니다.<br>
      • <strong>1점</strong>: 아직 수행해본 적 없음 | <strong>2점</strong>: 구체적 도움 받아 수행 | <strong>3점</strong>: 혼자 무리 없이 완수 | <strong>4점</strong>: 예외 상황 대응 | <strong>5점</strong>: 개선 제안/동료 지도<br>
      • <strong>해당 업무 아님</strong> 또는 <strong>판단하기 어려움</strong>을 선택하시면 0점 처리되지 않고 평가 집계에서 제외됩니다.
    </div>
    """, unsafe_allow_html=True)

    job_questions = get_questions_for_job(st.session_state["job_family"])
    
    with st.form("assessment_form"):
        # 역량별로 문항 묶어서 표시
        comp_grouped: Dict[str, List[Dict[str, Any]]] = {}
        for q in job_questions:
            comp_grouped.setdefault(q["competency_id"], []).append(q)

        form_responses = {}
        form_targets = {}

        for comp_id, q_list in comp_grouped.items():
            comp_name = q_list[0].get("competency_name", comp_id)
            ksa_type = q_list[0].get("ksa_type", "Skill")
            master_info = KSA_COMPETENCIES_MASTER.get(comp_id, {})
            ncs_code = master_info.get("ncs_unit_code", "참조 초안")

            st.markdown(f"#### 🔹 [{comp_name}] ({ksa_type} 역량)")
            st.caption(f"정의: {master_info.get('definition', '')} | NCS 참조: {ncs_code} (초안)")

            # 목표 수준 설정 슬라이더
            default_target = st.session_state["target_levels"].get(comp_id, 4.0)
            target_val = st.select_slider(
                f"🎯 [{comp_name}] 목표 수준 설정 (기본 제안: 4.0점)",
                options=[1.0, 2.0, 3.0, 4.0, 5.0],
                value=float(default_target),
                key=f"target_slider_{comp_id}",
                help="본인이 도달하고자 하는 실무 목표 수준입니다. 4점은 '예외 상황 대응 및 자율 수행' 수준입니다."
            )
            form_targets[comp_id] = target_val

            for q in q_list:
                qid = q["question_id"]
                st.markdown(f"**Q. {q['question_text']}**")
                st.caption(f"💡 구체적 행동 예시: {q.get('behavior_example', '')}")

                prev_val = st.session_state["survey_responses"].get(qid, 3)
                ans_options = [
                    "1점: 아직 직접 수행해본 적이 없다",
                    "2점: 매뉴얼이나 선배의 구체적인 도움을 받아 수행한다",
                    "3점: 일반적인 상황에서 혼자 무리 없이 완수한다",
                    "4점: 예외 상황이나 예상치 못한 문제에도 유연하게 대처한다",
                    "5점: 프로세스를 개선하거나 다른 동료에게 노하우를 가르친다",
                    "해당 업무 아님 (평가 제외)",
                    "판단하기 어려움 (평가 제외)"
                ]

                # 기본 선택 인덱스 매핑
                def_idx = 2  # 기본 3점
                if prev_val == 1: def_idx = 0
                elif prev_val == 2: def_idx = 1
                elif prev_val == 3: def_idx = 2
                elif prev_val == 4: def_idx = 3
                elif prev_val == 5: def_idx = 4
                elif prev_val == "NA": def_idx = 5
                elif prev_val == "UNCERTAIN": def_idx = 6

                chosen = st.radio(
                    f"문항 {qid} 응답",
                    options=ans_options,
                    index=def_idx,
                    key=f"radio_{qid}",
                    label_visibility="collapsed"
                )

                if "1점" in chosen: form_responses[qid] = 1
                elif "2점" in chosen: form_responses[qid] = 2
                elif "3점" in chosen: form_responses[qid] = 3
                elif "4점" in chosen: form_responses[qid] = 4
                elif "5점" in chosen: form_responses[qid] = 5
                elif "해당 업무 아님" in chosen: form_responses[qid] = "NA"
                else: form_responses[qid] = "UNCERTAIN"

            st.markdown("---")

        submit_btn = st.form_submit_button("📊 역량 자기점검 결과 계산하기", type="primary", use_container_width=True)
        if submit_btn:
            st.session_state["survey_responses"] = form_responses
            st.session_state["target_levels"] = form_targets
            st.session_state["is_sample_mode"] = False
            
            # 이전 결과가 있다면 히스토리에 보존 (재점검 비교용)
            if st.session_state["eval_result"] and not st.session_state["eval_result"].is_sample:
                st.session_state["assessment_history"].append(copy.deepcopy(st.session_state["eval_result"]))

            # 평가 점수 및 갭 계산
            eval_res = calculate_competency_scores(
                job_family=st.session_state["job_family"],
                responses=form_responses,
                target_levels=form_targets,
                user_task_ids=st.session_state["selected_tasks"],
                career_range=st.session_state["career_range"],
                difficult_task_desc=st.session_state["difficult_task"],
                learning_goal=st.session_state["learning_goal"],
                is_sample=False
            )
            st.session_state["eval_result"] = eval_res
            st.session_state["current_step"] = "STEP_RESULT"
            st.session_state["stale_results"] = False

            # 추천 브릿지 연결
            f_params = RecommendationFilterParams(
                price_filter=st.session_state["price_filter"],
                max_budget=st.session_state["max_budget"] if st.session_state["price_filter"] == "MAX_BUDGET" else None,
                edu_type=st.session_state["edu_type"],
                weekly_hours=st.session_state["weekly_hours"]
            )
            st.session_state["rec_bundle"] = get_recommendations_for_assessment(eval_res, f_params)
            st.success("✅ 자기점검 결과가 성공적으로 산출되었습니다! 아래에서 결과를 확인하세요.")
            st.rerun()

    # 3단계: 결과 확인 (현재 수준 vs 목표 수준 vs 갭 분석)
    eval_res: Optional[AssessmentEvaluationResult] = st.session_state.get("eval_result")
    if eval_res is not None:
        st.subheader("3. 역량 점검 결과 및 보완 우선순위")

        # 입력값 변경 시 오래된 결과 알림
        if st.session_state.get("stale_results"):
            st.markdown("""
            <div class="callout-warning" style="border-left-color: #E11D48; background: #FFF1F2; color: #9F1239; margin-bottom: 1.2rem;">
              ⚠️ <strong>[오래된 결과 안내 — 재계산 필요]</strong><br>
              직무 설정 또는 수행 업무가 변경되었습니다. 
              현재 표시된 결과는 변경 전 입력 기준이므로, 상단의 <strong>'📊 역량 자기점검 결과 계산하기'</strong> 버튼을 눌러 최신 결과로 재산출해 주세요.
            </div>
            """, unsafe_allow_html=True)
        
        # 샘플 모드 뱃지
        if eval_res.is_sample:
            st.markdown('<span class="badge-tag badge-amber">⚠️ 예시 샘플 데이터 결과</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-tag badge-teal">✅ 실제 사용자 자기평가 결과</span>', unsafe_allow_html=True)

        # 결과 요약 지표 카드
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("진단 직무", eval_res.job_family)
        with m_col2:
            st.metric("유효 평가 역량", f"{eval_res.overall_summary['valid_competencies_count']}개")
        with m_col3:
            st.metric("우선 보완 필요 역량", f"{len(eval_res.prioritized_deficiencies)}개")
        with m_col4:
            st.metric("정보 부족 역량", f"{eval_res.overall_summary['insufficient_count']}개")

        # 시각화: 현재 수준(자기평가) vs 목표 수준(사용자설정) 가로 막대 차트
        st.markdown("##### 📊 역량별 현재 자기평가 vs 설정 목표 수준 비교")
        chart_comps = []
        curr_scores = []
        target_scores = []
        gaps = []

        for c_id, cs in eval_res.competency_scores.items():
            if not cs.is_insufficient:
                chart_comps.append(cs.competency_name)
                curr_scores.append(cs.current_level)
                target_scores.append(cs.target_level)
                gaps.append(cs.gap)

        if chart_comps:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=chart_comps,
                x=curr_scores,
                name="현재 자기평가 (1~5점)",
                orientation="h",
                marker=dict(color="#4F46E5"),
                text=[f"{v:.1f}점" for v in curr_scores],
                textposition="auto"
            ))
            fig.add_trace(go.Bar(
                y=chart_comps,
                x=target_scores,
                name="사용자 설정 목표 (1~5점)",
                orientation="h",
                marker=dict(color="#93C5FD"),
                text=[f"{v:.1f}점" for v in target_scores],
                textposition="auto"
            ))
            fig.update_layout(
                barmode="group",
                height=260 + len(chart_comps) * 35,
                margin=dict(l=20, r=20, t=25, b=25),
                xaxis=dict(range=[0, 5.2], title="역량 점수 (5점 척도)", dtick=1.0),
                yaxis=dict(autorange="reversed"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)

        # 정보 부족 역량 안내
        if eval_res.insufficient_competencies:
            ins_names = [f"[{cs.competency_name}]" for cs in eval_res.insufficient_competencies]
            st.markdown(f"""
            <div class="callout-warning">
              ⚠️ <strong>정보 부족 항목 ({len(eval_res.insufficient_competencies)}건)</strong>: {', '.join(ins_names)}<br>
              '해당 업무 아님' 또는 '판단 어려움'으로 인해 유효 응답이 2문항 미만입니다. 
              점수를 확정하거나 부족 역량으로 판정하지 않았으며, 추가 응답 시 정확한 진단이 가능합니다.
            </div>
            """, unsafe_allow_html=True)

        # 우선 보완할 핵심 역량 Top 3 카드
        st.markdown("##### 🚀 우선 보완할 역량 (최대 3개)")
        if eval_res.prioritized_deficiencies:
            for cs in eval_res.prioritized_deficiencies:
                task_badge = '<span class="badge-tag badge-teal" style="margin-left:0.35rem;">💼 수행 업무 연계</span>' if cs.is_task_related else ''
                reason_desc = "사용자의 실제 수행 업무와 직접 연관되어 있으며, 목표 수준 대비 역량 차이가 가장 큽니다." if cs.is_task_related else "목표 수준 대비 역량 차이가 가장 크며, 우선적인 보완 학습이 권장됩니다."
                
                card_html = (
                    '<div class="customer-card">'
                    '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.5rem;">'
                    f'<div><span class="badge-tag badge-primary">우선순위 {cs.priority_rank}위</span>{task_badge}'
                    f'<span style="font-size: 1.15rem; font-weight: 700; margin-left: 0.3rem; color: #0F172A;">[{cs.competency_name}]</span></div>'
                    f'<div><span style="font-size: 0.95rem; font-weight: 600; color: #4F46E5;">'
                    f'현재 {cs.current_level:.1f}점 ➔ 목표 {cs.target_level:.1f}점 (보완 필요: <strong>+{cs.gap:.1f}점</strong>)</span></div>'
                    '</div>'
                    f'<div style="font-size: 0.88rem; color: #475569; line-height: 1.6;">'
                    f'• <strong>역량 설명</strong>: {cs.description}<br>'
                    f'• <strong>보완 추천 이유</strong>: {reason_desc}'
                    '</div>'
                    '</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="callout-info">
              🎉 <strong>축하합니다!</strong> 설정하신 모든 목표 수준을 이미 달성하셨거나 역량 차이가 없습니다.<br>
              부족한 역량을 억지로 생성하지 않으며, 현재의 전문성을 유지·심화할 수 있는 <strong>심화·전문가 과정</strong>을 맞춤 추천합니다.
            </div>
            """, unsafe_allow_html=True)

        # 하단 맞춤 교육 탭 상단 이동 및 탭 전환 버튼
        st.markdown("""
        <div style="margin: 2.5rem 0 1.5rem 0; text-align: center; background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 16px; padding: 1.8rem 1.2rem;">
          <div style="font-size: 1.05rem; font-weight: 700; color: #1E293B; margin-bottom: 0.5rem;">
            🎯 내 역량 갭에 맞는 실제 교육과정이 준비되어 있습니다
          </div>
          <div style="font-size: 0.88rem; color: #64748B; margin-bottom: 1.2rem;">
            아래 버튼을 누르면 페이지 상단으로 이동하며 <strong>'🎓 맞춤 교육'</strong> 탭이 자동으로 열립니다.
          </div>
          <a href="#top-anchor" onclick="
            try {
              const doc = (window.parent && window.parent.document) ? window.parent.document : document;
              const win = window.parent || window;
              const tabs = doc.querySelectorAll('button[data-baseweb=\\'tab\\']');
              if (tabs && tabs.length >= 2) {
                tabs[1].click();
              }
              win.scrollTo({top: 0, behavior: 'smooth'});
            } catch (err) {
              console.log(err);
            }
          " style="
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
            background: linear-gradient(135deg, #4F46E5 0%, #3730A3 100%);
            color: #FFFFFF !important;
            font-weight: 700;
            font-size: 1.05rem;
            padding: 0.95rem 2.4rem;
            border-radius: 12px;
            text-decoration: none;
            box-shadow: 0 4px 16px rgba(79, 70, 229, 0.38);
            transition: all 0.2s ease;
            cursor: pointer;
          ">
            <span>🎓 맞춤 교육 추천 강좌 바로 확인하기</span>
            <span style="font-size: 1.2rem;">➔</span>
          </a>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# TAB 2: 맞춤 교육 추천 (부족 역량 기반 강좌 카드, 대체 수강처, 상세 비교)
# ------------------------------------------------------------------------------
with tab_recommend:
    st.subheader("🎓 내 역량 갭 기반 맞춤 교육 추천")

    bundle: Optional[CustomerRecommendationBundle] = st.session_state.get("rec_bundle")
    
    if bundle is None:
        st.info("먼저 **'📋 내 역량 점검'** 탭에서 진단을 진행하시거나 '샘플 결과 보기'를 선택해 주세요.")
    else:
        # 상단 필터 조정 영역 (설문 재작성 없이 예산/형태만 즉시 변경 가능)
        with st.expander("⚙️ 학습 조건(예산·형태·시간) 재조정", expanded=False):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                p_filter_new = st.selectbox(
                    "수강료 조건 변경",
                    options=["전체 (유료+무료)", "무료 과정만", "예산 한도 설정"],
                    index=0 if st.session_state["price_filter"] == "ALL" else (1 if st.session_state["price_filter"] == "FREE_ONLY" else 2),
                    key="filter_tab2_price"
                )
            with f_col2:
                edu_new = st.selectbox(
                    "교육 형태 변경",
                    options=["전체", "온라인 우선", "오프라인/집체 우선"],
                    index=0 if st.session_state["edu_type"] == "ALL" else (1 if st.session_state["edu_type"] == "ONLINE" else 2),
                    key="filter_tab2_edu"
                )
            with f_col3:
                w_new = st.slider("주당 학습 가능 시간 (시간)", 1.0, 20.0, float(st.session_state["weekly_hours"]), 0.5, key="filter_tab2_weekly")

            if st.button("🔄 필터 조건 즉시 적용", type="primary"):
                if p_filter_new == "무료 과정만":
                    st.session_state["price_filter"] = "FREE_ONLY"
                    st.session_state["max_budget"] = 0
                elif p_filter_new == "예산 한도 설정":
                    st.session_state["price_filter"] = "MAX_BUDGET"
                else:
                    st.session_state["price_filter"] = "ALL"
                    st.session_state["max_budget"] = None
                st.session_state["edu_type"] = "ALL" if edu_new == "전체" else ("ONLINE" if edu_new == "온라인 우선" else "OFFLINE")
                st.session_state["weekly_hours"] = w_new

                # 추천 재실행
                f_params = RecommendationFilterParams(
                    price_filter=st.session_state["price_filter"],
                    max_budget=st.session_state["max_budget"],
                    edu_type=st.session_state["edu_type"],
                    weekly_hours=st.session_state["weekly_hours"]
                )
                st.session_state["rec_bundle"] = get_recommendations_for_assessment(st.session_state["eval_result"], f_params)
                st.rerun()

        # 추천 번들 결과 요약
        st.markdown(f"**{bundle.status_message}**")
        if bundle.is_sample:
            st.caption("※ 현재 화면은 샘플 평가 데이터를 바탕으로 추출된 교육과정입니다.")

        if bundle.actionable_guidance:
            st.markdown(f"""
            <div class="callout-warning">
              {bundle.actionable_guidance.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)


        # 추천 강좌 카드 렌더링
        if bundle.all_courses_deduped:
            for card in bundle.all_courses_deduped:
                is_saved = card.course_uid in st.session_state["saved_courses"]
                save_btn_label = "⭐ 관심 저장됨" if is_saved else "☆ 관심 교육 저장"

                with st.container():
                    st.markdown(f"""
                    <div class="customer-card">
                      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                          <span class="badge-tag badge-primary">{card.provider}</span>
                          <span class="badge-tag badge-teal">{card.education_type}</span>
                          <span class="badge-tag badge-amber">{card.price_display}</span>
                          <span class="badge-tag badge-neutral">{card.duration_display}</span>
                          <div style="font-size: 1.15rem; font-weight: 700; margin-top: 0.4rem; color: #0F172A;">
                            {card.title}
                          </div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    card_col1, card_col2 = st.columns([4, 1])
                    with card_col1:
                        # 보완 역량 태그들
                        comp_badges = " ".join([f"`{item['competency_name']} (갭 {item.get('gap', 0.0):.1f}점)`" for item in card.linked_competencies])
                        st.markdown(f"**연계 보완 역량**: {comp_badges}")
                        st.markdown(f"📌 **추천 사유**: {card.customer_recommendation_reason}")
                        st.caption(f"⏱️ **학습 계획 페이스**: {card.study_plan_note}")

                        if card.text_richness_warning:
                            st.caption(f"{card.text_richness_warning}")

                        # 대체 수강처 목록 (크로스 플랫폼)
                        if card.alternative_offerings:
                            with st.expander(f"🔄 동일 강좌 대체 수강처 ({len(card.alternative_offerings)}개 플랫폼)"):
                                for alt in card.alternative_offerings:
                                    suit_badge = "✅ 조건 부합" if alt["is_suitable_alternative"] else alt["unsuitability_reason"]
                                    st.markdown(f"- **[{alt['provider']}]** {alt['title']} | 수강료: {alt['price_display']} | 형태: {alt['education_type']} ({suit_badge}) [바로가기]({alt['url']})")

                    with card_col2:
                        st.markdown(f"[🔗 강의 상세]({card.url})")
                        if st.button(save_btn_label, key=f"save_btn_{card.course_uid}", use_container_width=True):
                            if is_saved:
                                del st.session_state["saved_courses"][card.course_uid]
                                st.toast("관심 교육 목록에서 제거되었습니다.")
                            else:
                                st.session_state["saved_courses"][card.course_uid] = {
                                    "card": card,
                                    "status": "학습 예정",
                                    "notes": ""
                                }
                                st.toast("관심 교육 목록에 저장되었습니다! ('나의 학습' 탭 확인)")
                            st.rerun()

                    st.markdown("---")

# ------------------------------------------------------------------------------
# TAB 3: 나의 학습 (저장된 관심 강좌 관리, 최대 3개 비교, 재점검 히스토리)
# ------------------------------------------------------------------------------
with tab_my_learning:
    st.subheader("📚 나의 학습 관리함")
    
    st.markdown("""
    <div class="callout-info">
      💡 <strong>세션 안내</strong>: 본 서비스는 로그인 없이 브라우저 세션 단위로 보관함이 유지됩니다.<br>
      새로고침 시 임시 데이터가 초기화될 수 있으므로, 관심 있는 교육의 상세 링크를 북마크해 두시길 권장합니다.
    </div>
    """, unsafe_allow_html=True)

    saved_dict = st.session_state.get("saved_courses", {})

    if not saved_dict:
        st.info("아직 관심 교육으로 저장된 강좌가 없습니다. '맞춤 교육' 탭에서 원하는 강좌의 [관심 교육 저장] 버튼을 눌러보세요.")
    else:
        st.markdown(f"**현재 저장된 관심 교육 ({len(saved_dict)}개)**")

        # 최대 3개 강좌 나란히 비교
        with st.expander("⚖️ 관심 강좌 상세 비교 (최대 3개)", expanded=True):
            compare_uids = list(saved_dict.keys())[:3]
            cols = st.columns(len(compare_uids))
            for idx, c_uid in enumerate(compare_uids):
                item = saved_dict[c_uid]
                c_card: RecommendedCourseCard = item["card"]
                with cols[idx]:
                    st.markdown(f"""
                    <div class="customer-card">
                      <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.5rem; height: 3.2rem; overflow: hidden;">
                        {c_card.title}
                      </div>
                      <div style="font-size: 0.85rem; color: #475569; line-height: 1.6;">
                        • <strong>기관</strong>: {c_card.provider}<br>
                        • <strong>비용</strong>: {c_card.price_display}<br>
                        • <strong>시간</strong>: {c_card.duration_display}<br>
                        • <strong>형태</strong>: {c_card.education_type}<br>
                        • <strong>보완 역량</strong>: {c_card.primary_competency_name}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"[🔗 상세 페이지 바로가기]({c_card.url})")

        # 강좌별 학습 상태 관리 및 메모
        st.markdown("##### 📝 학습 진도 상태 & 개인 메모")
        for c_uid, item in list(saved_dict.items()):
            c_card: RecommendedCourseCard = item["card"]
            with st.container():
                st_col1, st_col2, st_col3 = st.columns([3, 1.5, 1])
                with st_col1:
                    st.markdown(f"**{c_card.title}** ({c_card.provider})")
                    memo_input = st.text_input(
                        "개인 학습 메모",
                        value=item.get("notes", ""),
                        key=f"memo_{c_uid}",
                        placeholder="예: 2주차까지 완강 목표, 1강 채용 규정 확인 필수"
                    )
                    item["notes"] = memo_input
                with st_col2:
                    status_choice = st.selectbox(
                        "학습 상태",
                        options=["학습 예정", "학습 중", "학습 완료"],
                        index=["학습 예정", "학습 중", "학습 완료"].index(item.get("status", "학습 예정")),
                        key=f"status_{c_uid}",
                        help="수료 시에도 역량 점수는 자동 상승하지 않으며, 재점검을 통해 실질적인 변화를 측정합니다."
                    )
                    item["status"] = status_choice
                with st_col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ 보관함 삭제", key=f"del_saved_{c_uid}"):
                        del st.session_state["saved_courses"][c_uid]
                        st.rerun()
                st.markdown("---")

    # 역량 재점검 및 이전 결과 변화 비교
    st.markdown("##### 🔁 역량 재점검 히스토리")
    history = st.session_state.get("assessment_history", [])
    if history:
        st.markdown(f"총 **{len(history)}회**의 이전 진단 기록이 보존되어 있습니다.")
        for h_idx, past_res in enumerate(reversed(history), 1):
            with st.expander(f"📅 이전 진단 기록 #{len(history) - h_idx + 1} ({past_res.job_family})"):
                hist_cols = []
                hist_scores = []
                for cid, past_cs in past_res.competency_scores.items():
                    if not past_cs.is_insufficient:
                        hist_cols.append(past_cs.competency_name)
                        hist_scores.append(f"{past_cs.current_level:.1f}점 (목표: {past_cs.target_level:.1f}점)")
                st.write(dict(zip(hist_cols, hist_scores)))
    else:
        st.caption("진단 문항을 다시 작성하여 재계산하시면 이전 진단 결과와 비교할 수 있는 히스토리가 기록됩니다.")

# ------------------------------------------------------------------------------
# 4. 공개 서비스 푸터 (세션 격리 안내 및 데이터 면책 조항)
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown("""
<div style="text-align: center; font-size: 0.8rem; color: #94A3B8; padding: 1.5rem 0 2rem 0; line-height: 1.6;">
  🔒 <strong>개인정보 보호 및 세션 안내</strong>: 본 서비스는 비로그인 독립 세션으로 운영됩니다. 입력하신 응답과 결과는 서버에 영구 저장되지 않으며, 다른 사용자와 일체 공유되지 않습니다.<br>
  📖 <strong>교육 데이터 출처 및 저작권</strong>: 본 대시보드에서 제공하는 교육과정 메타데이터는 공공데이터포털(HRD-Net, K-MOOC, 서울/경기 평생학습) 및 공개 강좌 정보를 바탕으로 구성되었습니다. 각 교육의 저작권 및 수강신청 권한은 해당 교육기관에 있습니다.<br>
  ⚙️ kimsaemi/edu-skill-gap | 실무 역량 진단 & 맞춤 교육 추천 서비스
</div>
""", unsafe_allow_html=True)
