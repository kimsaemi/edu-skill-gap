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
    get_shared_recommender,
    get_recommendations_for_tasks
)
from src.recommendation import hr_task_catalog
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

/* ==============================================================================
   HRD-Net 스타일 직업훈련 포털 컴포넌트 (검색 박스, 3열 헤더, 3열 강좌 카드)
   ============================================================================== */
.hrd-search-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 1.4rem 1.6rem 1.2rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.hrd-filter-row {
  display: flex;
  align-items: center;
  margin-bottom: 0.85rem;
  gap: 0.8rem;
}
.hrd-filter-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: #1E293B;
  width: 95px;
  flex-shrink: 0;
}
.hrd-scope-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.hrd-checkbox-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.86rem;
  color: #334155;
  background: #F8FAFC;
  border: 1px solid #CBD5E1;
  padding: 0.25rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  user-select: none;
}
.hrd-checkbox-chip.active {
  background: #EEF2FF;
  border-color: #6366F1;
  color: #4338CA;
  font-weight: 600;
}
.hrd-tag-applied {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: #FFFFFF;
  border: 1px solid #CBD5E1;
  padding: 0.25rem 0.65rem;
  border-radius: 9999px;
  font-size: 0.82rem;
  color: #334155;
}
.hrd-condition-count-badge {
  background: #EFF6FF;
  color: #2563EB;
  border: 1px solid #BFDBFE;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.82rem;
  margin-right: 0.5rem;
}

/* 3열 리스트 테이블 헤더 */
.hrd-table-header {
  background: #F1F5F9;
  border-top: 2px solid #334155;
  border-bottom: 1px solid #CBD5E1;
  padding: 0.75rem 1.25rem;
  font-size: 0.88rem;
  font-weight: 700;
  color: #334155;
  margin-top: 1.5rem;
  margin-bottom: 0.8rem;
  border-radius: 4px 4px 0 0;
  display: flex;
  align-items: center;
}

/* HRD-Net 3열 통합 강좌 카드 */
.hrd-card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 1.35rem 1.4rem;
  margin-bottom: 1.1rem;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.hrd-card:hover {
  border-color: #3B82F6;
  box-shadow: 0 4px 16px -2px rgba(37, 99, 235, 0.12);
  transform: translateY(-2px);
}
.hrd-inst-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: #475569;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
}
.hrd-badge-cert {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  font-size: 0.74rem;
  font-weight: 700;
  color: #047857;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  border-radius: 4px;
  margin-bottom: 0.4rem;
}
.hrd-course-title {
  font-size: 1.12rem;
  font-weight: 800;
  color: #0F172A;
  margin-bottom: 0.5rem;
  line-height: 1.45;
}
.hrd-support-text {
  font-size: 0.82rem;
  color: #2563EB;
  font-weight: 600;
  margin-bottom: 0.45rem;
}
.hrd-reason-box {
  background: #F8FAFC;
  border-left: 3px solid #6366F1;
  padding: 0.45rem 0.75rem;
  font-size: 0.82rem;
  color: #334155;
  border-radius: 0 4px 4px 0;
  margin-top: 0.45rem;
}

/* 중앙 정보 열 */
.hrd-meta-row {
  font-size: 0.86rem;
  color: #475569;
  margin-bottom: 0.4rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.hrd-meta-icon {
  width: 18px;
  text-align: center;
  font-size: 0.95rem;
  flex-shrink: 0;
}

/* 우측 모집/금액 열 */
.hrd-status-recruiting {
  color: #DC2626;
  font-size: 1.05rem;
  font-weight: 800;
  text-align: right;
  margin-bottom: 0.3rem;
}
.hrd-price-large {
  font-size: 1.25rem;
  font-weight: 800;
  color: #0F172A;
  text-align: right;
  margin-bottom: 0.75rem;
}
.hrd-action-btn-link {
  display: block;
  text-align: center;
  border: 1px solid #2563EB;
  color: #2563EB !important;
  background: #FFFFFF;
  padding: 0.45rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: none;
  margin-bottom: 0.4rem;
  transition: all 0.15s ease;
}
.hrd-action-btn-link:hover {
  background: #EFF6FF;
  border-color: #1D4ED8;
  color: #1D4ED8 !important;
}

/* 우측 플로팅 퀵 버튼 (도우미 & 맨위로) */
.hrd-floating-actions {
  position: fixed;
  right: 28px;
  bottom: 35px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hrd-circle-btn {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.18);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}
.hrd-circle-btn:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.24);
}
.hrd-circle-help {
  background: #2563EB;
  color: #FFFFFF !important;
  border: none;
}
.hrd-circle-top {
  background: #FFFFFF;
  color: #334155 !important;
  border: 1px solid #CBD5E1;
}

/* 우측 상단 플로팅 퀵 배지 */
.hrd-side-quick {
  position: fixed;
  right: 20px;
  top: 140px;
  z-index: 9998;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hrd-quick-pill {
  background: #FFFFFF;
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 0.78rem;
  font-weight: 700;
  color: #334155;
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
  text-decoration: none;
  transition: all 0.15s ease;
}
.hrd-quick-pill:hover {
  border-color: #2563EB;
  color: #2563EB;
}

/* 맞춤 교육 탭 점프 대형 버튼 (고대비 선명한 화이트 텍스트) */
.btn-jump-recommend {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.75rem !important;
  background: #2563EB !important; /* 선명한 로열 블루 */
  color: #FFFFFF !important;
  font-weight: 800 !important;
  font-size: 1.15rem !important;
  padding: 1.1rem 2.8rem !important;
  border-radius: 12px !important;
  border: none !important;
  text-decoration: none !important;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.45) !important;
  cursor: pointer !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  line-height: 1.2 !important;
}
.btn-jump-recommend:hover {
  background: #1D4ED8 !important;
  color: #FFFFFF !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 26px rgba(37, 99, 235, 0.6) !important;
}
.btn-jump-recommend:active {
  transform: translateY(0) !important;
}
.btn-jump-recommend *,
.btn-jump-recommend span {
  color: #FFFFFF !important;
  font-weight: 800 !important;
  text-decoration: none !important;
}
</style>

<script>
window.switchToRecommendTab = function(event) {
  if (event) {
    try { event.preventDefault(); event.stopPropagation(); } catch(e){}
  }
  
  const searchDocs = [document];
  try { if (window.parent && window.parent.document) searchDocs.push(window.parent.document); } catch(e){}
  try { if (window.top && window.top.document) searchDocs.push(window.top.document); } catch(e){}

  let found = false;
  for (const d of searchDocs) {
    // 1. 텍스트에 '맞춤 교육' 또는 '맞춤교육'이 포함된 탭 버튼 검색
    const allBtns = d.querySelectorAll('button[role="tab"], button[data-baseweb="tab"], [data-testid="stTabs"] button, button');
    for (const b of allBtns) {
      const label = (b.innerText || b.textContent || '').trim();
      if (label.includes('맞춤 교육') || label.includes('맞춤교육')) {
        b.click();
        b.focus();
        found = true;
        break;
      }
    }
    
    // 2. 텍스트로 못 찾은 경우 두 번째(인덱스 1) 탭 버튼 클릭
    if (!found) {
      const tabs = d.querySelectorAll('[data-testid="stTabs"] button, button[role="tab"], button[data-baseweb="tab"]');
      if (tabs && tabs.length >= 2) {
        tabs[1].click();
        tabs[1].focus();
        found = true;
      }
    }
    
    if (found) {
      const anchor = d.getElementById('top-anchor');
      if (anchor) {
        anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        const win = d.defaultView || window;
        win.scrollTo({ top: 0, behavior: 'smooth' });
      }
      break;
    }
  }
  return false;
};

window.switchToMyLearningTab = function(event) {
  if (event) {
    try { event.preventDefault(); event.stopPropagation(); } catch(e){}
  }
  const searchDocs = [document];
  try { if (window.parent && window.parent.document) searchDocs.push(window.parent.document); } catch(e){}
  try { if (window.top && window.top.document) searchDocs.push(window.top.document); } catch(e){}

  for (const d of searchDocs) {
    const allBtns = d.querySelectorAll('button[role="tab"], button[data-baseweb="tab"], [data-testid="stTabs"] button, button');
    for (const b of allBtns) {
      const label = (b.innerText || b.textContent || '').trim();
      if (label.includes('나의 학습') || label.includes('나의학습')) {
        b.click();
        b.focus();
        const anchor = d.getElementById('top-anchor');
        if (anchor) {
          anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
          const win = d.defaultView || window;
          win.scrollTo({ top: 0, behavior: 'smooth' });
        }
        return false;
      }
    }
    // 인덱스 기준 폴백 (세 번째 탭)
    const tabs = d.querySelectorAll('[data-testid="stTabs"] button, button[role="tab"], button[data-baseweb="tab"]');
    if (tabs && tabs.length >= 3) {
      tabs[2].click();
      tabs[2].focus();
      return false;
    }
  }
  return false;
};
</script>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. 세션 상태 초기화 및 관리
# ------------------------------------------------------------------------------
def init_session_state():
    """사용자 세션 상태를 안전하게 초기화합니다."""
    defaults = {
        "job_family": "인사",
        "career_range": "3~5년차",
        "selected_tasks": ["TASK_HR_D03_T01", "TASK_HR_D04_T01"],
        "selected_task_domains": [],
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
        "saved_courses": {},      # course_uid -> dict (관심 교육 보관함)
        "compared_courses": {},   # course_uid -> card (최대 3개 비교)
        "assessment_history": [],  # 재점검 기록 비교용
        "stale_results": False,
        "real_user_survey": {},
        "real_user_targets": {},
        "real_user_eval": None,
        "real_user_bundle": None,
        "active_main_tab": "📋 내 역량 점검",
        "selected_competency_filter": "ALL",
        "scroll_to_step1": False,
        "scroll_to_result": False
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
    st.session_state["real_user_survey"] = {}
    st.session_state["real_user_targets"] = {}
    st.session_state["real_user_eval"] = None
    st.session_state["real_user_bundle"] = None
    st.session_state["selected_competency_filter"] = "ALL"
    st.session_state["target_tab"] = "📋 내 역량 점검"

def switch_main_tab(target_tab_name: str):
    """프로그래밍 방식으로 메인 탭을 안전하게 전환합니다 (위젯 충돌 방지)."""
    st.session_state["target_tab"] = target_tab_name
    st.rerun()

def render_sample_banner(location_key: str = ""):
    """샘플 모드일 때 모든 주요 화면에 '예시 응답으로 생성한 샘플 결과입니다' 배너 및 종료 버튼을 일관되게 표시합니다."""
    if st.session_state.get("is_sample_mode", False):
        col_banner, col_exit = st.columns([3.6, 1.4])
        with col_banner:
            st.markdown("""
            <div class="callout-warning" style="margin-bottom: 0.8rem; border-left-color: #F59E0B; background: #FFFBEB;">
              📢 <strong>예시 응답으로 생성한 샘플 결과입니다</strong> (실제 진단 결과가 아닙니다).<br>
              본인의 실제 역량을 점검하시려면 우측의 <strong>'샘플 종료 · 내 진단 시작'</strong> 버튼을 눌러주세요.
            </div>
            """, unsafe_allow_html=True)
        with col_exit:
            if st.button("⏹️ 샘플 종료 · 내 진단 시작", key=f"btn_exit_sample_{location_key}", type="primary", use_container_width=True):
                st.session_state["survey_responses"] = copy.deepcopy(st.session_state.get("real_user_survey", {}))
                st.session_state["target_levels"] = copy.deepcopy(st.session_state.get("real_user_targets", {}))
                st.session_state["eval_result"] = st.session_state.get("real_user_eval")
                st.session_state["rec_bundle"] = st.session_state.get("real_user_bundle")
                st.session_state["is_sample_mode"] = False
                st.session_state["current_step"] = "STEP_SURVEY" if st.session_state["survey_responses"] else "STEP_PROFILE"
                st.toast("샘플 모드를 종료하고 내 진단 모드로 전환되었습니다.")
                st.rerun()

# ------------------------------------------------------------------------------
# 3. 상단 헤더 및 메뉴 탭 네비게이션
# ------------------------------------------------------------------------------
st.markdown("""
<div class="hero-banner">
  <div class="hero-title">내 업무에 필요한 역량과 교육을 찾아보세요</div>
  <div class="hero-subtitle">
    인사·총무·경영지원 업무를 점검하고, 보완하고 싶은 역량에 맞는 교육을 확인하세요.
  </div>
  
  <div style="display: flex; justify-content: center; align-items: center; gap: 0.6rem; margin: 1.2rem 0 0.8rem 0; flex-wrap: wrap;">
    <div style="background: rgba(255,255,255,0.18); padding: 0.45rem 0.95rem; border-radius: 8px; font-weight: 700; font-size: 0.88rem; color: #FFFFFF;">
      1️⃣ 업무 선택
    </div>
    <span style="color: #93C5FD; font-size: 0.9rem;">➔</span>
    <div style="background: rgba(255,255,255,0.18); padding: 0.45rem 0.95rem; border-radius: 8px; font-weight: 700; font-size: 0.88rem; color: #FFFFFF;">
      2️⃣ 자기점검
    </div>
    <span style="color: #93C5FD; font-size: 0.9rem;">➔</span>
    <div style="background: rgba(255,255,255,0.18); padding: 0.45rem 0.95rem; border-radius: 8px; font-weight: 700; font-size: 0.88rem; color: #FFFFFF;">
      3️⃣ 결과·교육 확인
    </div>
  </div>

  <div style="display: flex; justify-content: center; gap: 0.8rem; flex-wrap: wrap; margin-top: 0.6rem;">
    <span style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); color: #FFFFFF; padding: 0.3rem 0.85rem; border-radius: 20px; font-size: 0.82rem; font-weight: 600;">
      🔒 로그인 없이 이용
    </span>
    <span style="background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); color: #FFFFFF; padding: 0.3rem 0.85rem; border-radius: 20px; font-size: 0.82rem; font-weight: 600;">
      📖 자기평가 기반 학습 가이드
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# 첫 화면 주요 액션 버튼 (내 역량 점검 시작 / 샘플 결과 먼저 보기)
hero_c1, hero_c2 = st.columns([1.6, 1.4])
with hero_c1:
    if st.button("🚀 내 역량 점검 시작", type="primary", use_container_width=True, key="hero_start_btn"):
        st.session_state["scroll_to_step1"] = True
        switch_main_tab("📋 내 역량 점검")
with hero_c2:
    if not st.session_state.get("is_sample_mode"):
        if st.button("👀 샘플 결과 보기 (샘플 먼저 보기)", use_container_width=True, key="hero_sample_btn"):
            st.session_state["real_user_survey"] = copy.deepcopy(st.session_state.get("survey_responses", {}))
            st.session_state["real_user_targets"] = copy.deepcopy(st.session_state.get("target_levels", {}))
            st.session_state["real_user_eval"] = st.session_state.get("eval_result")
            st.session_state["real_user_bundle"] = st.session_state.get("rec_bundle")
            sample_res = get_sample_assessment_result(st.session_state.get("job_family", "인사"))
            st.session_state["eval_result"] = sample_res
            st.session_state["is_sample_mode"] = True
            st.session_state["current_step"] = "STEP_RESULT"
            st.session_state["scroll_to_result"] = True
            f_params = RecommendationFilterParams(
                price_filter=st.session_state["price_filter"],
                max_budget=st.session_state["max_budget"] if st.session_state["price_filter"] == "MAX_BUDGET" else None,
                edu_type=st.session_state["edu_type"],
                weekly_hours=st.session_state["weekly_hours"]
            )
            st.session_state["rec_bundle"] = get_recommendations_for_assessment(sample_res, f_params)
            switch_main_tab("📋 내 역량 점검")
    else:
        st.button("🔄 전체 초기화", on_click=reset_all_assessment, use_container_width=True, key="hero_reset_btn")

# 긴 기술 설명·NCS 코드·계산 기준은 상세 안내로 이동
with st.expander("ℹ️ 진단 기준 및 NCS 연계 상세 안내 (클릭하여 확인)", expanded=False):
    st.markdown("""
    • **진단 목적**: 인사·총무·경영지원 실무 재직자가 본인의 직무 행동 수준을 점검하고, 부족한 역량을 채울 수 있는 최적의 학습 경로를 추천받기 위한 자기점검 도구입니다.<br>
    • **역량 분류 기준**: 국가직무능력표준(NCS) 및 기업 실무 KSA(Knowledge, Skill, Attitude) 프레임워크를 기반으로 구성되었습니다.<br>
    • **점수 산출 방식**: 각 역량별 2문항 이상 유효하게 응답(1~5점)된 경우에만 평균 점수와 목표 갭을 산출하며, '해당 업무 아님' 또는 '판단 어려움'은 0점 처리되지 않고 산출에서 안전하게 제외됩니다.<br>
    • **교육 추천 기준**: 강좌 소개·커리큘럼 내용이 부족 역량의 정의와 얼마나 가까운지, 핵심 키워드가 얼마나 일치하는지, 난이도가 내 수준에 맞는지를 기준으로 순서를 정합니다. 수강 후기·평점은 추천 순위에 사용하지 않습니다.<br>
    • **학습 가이드**: 본 진단은 공인 자격시험이나 인사평가 도구가 아니며, 개인의 주관적 자기평가를 바탕으로 한 학습 권장 가이드입니다.
    """, unsafe_allow_html=True)

def render_course_card(card: RecommendedCourseCard, key_prefix: str = ""):
    """추천 교육 카드 1개를 렌더링합니다 (역량별·업무별 추천 공통)."""
    is_saved = card.course_uid in st.session_state["saved_courses"]
    save_btn_label = "⭐ 관심 저장됨" if is_saved else "☆ 관심 교육 저장"

    is_compared = card.course_uid in st.session_state["compared_courses"]
    cmp_btn_label = "📊 비교함 담김" if is_compared else "📊 비교에 추가"

    comp_badges_html = " ".join([
        f"<span class='badge-tag badge-primary' title='{item.get('mapping_basis', '추천 연계')} (사람의 검토 완료를 의미하지 않음)'>"
        + (f"📌 업무 연결 · {item['competency_name']} 역량"
           if item.get("is_task") else
           f"🎯 {item['competency_name']} (차이 {item.get('gap', 0.0):.1f}점 · {item.get('mapping_basis', '추천 연계')})")
        + f"</span>"
        for item in card.linked_competencies
    ])

    with st.container():
        st.markdown('<div class="hrd-card">', unsafe_allow_html=True)

        # 기본 카드 정보: 교육명, 교육기관, 연결된 보완 역량, 비용·시간·형태, 추천 이유
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.8rem; margin-bottom: 0.35rem; flex-wrap: wrap;">
          <div class="hrd-inst-name">
            <span>🏢 {card.provider}</span>
          </div>
          <div>
            {comp_badges_html}
          </div>
        </div>
        <div class="hrd-course-title">
          {card.title}
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.9rem; font-size: 0.88rem; color: #334155; margin: 0.5rem 0 0.7rem 0; background: #F8FAFC; padding: 0.6rem 0.9rem; border-radius: 8px; border: 1px solid #E2E8F0;">
          <span>💰 <strong>비용</strong>: <strong style="color: {'#059669' if '무료' in card.price_display else '#0F172A'};">{card.price_display}</strong></span>
          <span>⏱️ <strong>총 교육시간</strong>: {card.duration_display}</span>
          <span>💻 <strong>교육형태</strong>: {card.education_type}</span>
        </div>
        <div class="hrd-reason-box">
          <div style="margin-bottom: 0.3rem; color: #1E293B;">
            <strong>🎯 내 목표와의 연결</strong>: {card.goal_connection}
          </div>
          <div style="color: #475569;">
            <strong>📖 교육에서 확인한 내용</strong>: {card.content_evidence}
          </div>
        </div>
        """, unsafe_allow_html=True)

        if card.text_richness_warning:
            st.caption(f"{card.text_richness_warning}")

        # 기본 카드 액션 버튼 (3열: 교육 상세·신청 안내 / 관심 교육 저장 / 비교에 추가)
        act_c1, act_c2, act_c3 = st.columns([1.6, 1.2, 1.2])
        with act_c1:
            st.markdown(f"""
            <a href="{card.url}" target="_blank" class="hrd-action-btn-link" title="해당 교육기관 강좌 상세페이지로 이동">
              교육 상세·신청 안내 ↗
            </a>
            """, unsafe_allow_html=True)
        with act_c2:
            if st.button(save_btn_label, key=f"{key_prefix}save_btn_{card.course_uid}", use_container_width=True):
                if is_saved:
                    del st.session_state["saved_courses"][card.course_uid]
                    st.toast("관심 교육 목록에서 제거되었습니다.")
                else:
                    st.session_state["saved_courses"][card.course_uid] = {
                        "card": card,
                        "status": "학습 예정",
                        "notes": ""
                    }
                    st.toast("관심 교육 목록에 저장되었습니다! ('나의 학습' 탭에서 확인)")
                st.rerun()
        with act_c3:
            if st.button(cmp_btn_label, key=f"{key_prefix}cmp_btn_{card.course_uid}", use_container_width=True):
                if is_compared:
                    del st.session_state["compared_courses"][card.course_uid]
                    st.toast("비교 목록에서 제외되었습니다.")
                else:
                    if len(st.session_state["compared_courses"]) >= 3:
                        st.toast("⚠️ 비교는 최대 3개 강좌까지 가능합니다. 기존 강좌를 제외 후 추가해 주세요.")
                    else:
                        st.session_state["compared_courses"][card.course_uid] = card
                        st.toast(f"비교 목록에 추가되었습니다. (현재 {len(st.session_state['compared_courses'])}/3개)")
                st.rerun()

        # 상세 펼치기 (실제 커리큘럼 근거, 추천 근거의 한계, 동일 강좌의 다른 수강처, 확인된 일정과 출처)
        with st.expander("🔍 상세 정보 및 추천 근거 확인 (커리큘럼 발췌·일정·출처)", expanded=False):
            basis_summary = " · ".join([f"{item['competency_name']}: {item.get('mapping_basis', '추천 연계')}" for item in card.linked_competencies])
            st.markdown(f"• **역량 연계 근거**: {basis_summary} *(※ 사람의 검토 완료를 의미하지 않음)*")
            st.markdown(f"• **실제 커리큘럼 근거**: {card.curriculum_evidence}")
            st.markdown(f"• **추천 근거의 한계**: {card.evidence_limitation}")
            st.markdown(f"• **확인된 일정**: {card.schedule_display}")
            st.markdown(f"• **정보 출처**: {card.source_display}")

            if card.alternative_offerings:
                st.markdown(f"• **동일 강좌의 다른 수강처 ({len(card.alternative_offerings)}개)**:")
                for alt in card.alternative_offerings:
                    suit_badge = "✅ 조건 부합" if alt["is_suitable_alternative"] else alt["unsuitability_reason"]
                    st.markdown(f"  - **[{alt['provider']}]** {alt['title']} | {alt['price_display']} | {alt['education_type']} ({suit_badge}) [바로가기]({alt['url']})")
            else:
                st.markdown("• **동일 강좌의 다른 수강처**: 타 플랫폼 중복 개설 내역 없음")

        st.markdown('</div>', unsafe_allow_html=True)


def render_task_recommendations(key_prefix: str = ""):
    """선택한 인사 세부 업무별 추천 교육 (업무 설명 ↔ 교육내용 의미 유사도 기반)."""
    if st.session_state.get("job_family") != "인사":
        return
    task_ids = [t for t in st.session_state.get("selected_tasks", []) if hr_task_catalog.get_hr_task(t)]
    if not task_ids:
        return

    st.markdown("---")
    st.markdown("### 📌 선택한 업무별 추천 교육")
    st.caption("'실제 수행 중인 업무'에서 고른 업무마다, 업무 설명과 교육 소개·커리큘럼 내용이 가까운 교육을 골랐습니다. (최대 5개 업무, 업무별 3개)")
    if len(task_ids) > 5:
        st.info(f"업무를 {len(task_ids)}개 선택하셨어요. 처음 5개 업무만 표시합니다.")

    f_params = RecommendationFilterParams(
        price_filter=st.session_state["price_filter"],
        max_budget=st.session_state["max_budget"] if st.session_state["price_filter"] == "MAX_BUDGET" else None,
        edu_type=st.session_state["edu_type"],
        weekly_hours=st.session_state["weekly_hours"],
    )
    with st.spinner("업무별 교육을 찾는 중..."):
        task_recs = get_recommendations_for_tasks(task_ids, st.session_state["career_range"], f_params)

    for tr in task_recs:
        view = tr.career_view
        role = view.get("role") or {}
        with st.expander(f"[{tr.domain_name} · {tr.stage}] {tr.task_name}  —  추천 {len(tr.courses)}개", expanded=True):
            st.markdown(f"{tr.easy_description}")
            st.markdown(
                f"• **지식(K)**: {tr.knowledge}<br>"
                f"• **기술(S)**: {tr.skill}<br>"
                f"• **태도(A)**: {tr.attitude}",
                unsafe_allow_html=True,
            )
            level_line = f"• **내 연차 기준 숙련도 ({view['level_name']})**: {view['level_text']}"
            if role.get("role"):
                level_line += f"<br>• **내 연차 역할 ({role.get('badge', '')})**: {role['role']}"
            if view.get("next_level_text"):
                level_line += f"<br>• **다음 단계 ({view['next_level_name']})**: {view['next_level_text']}"
            st.markdown(level_line, unsafe_allow_html=True)
            if tr.needs_review:
                st.caption(f"ℹ️ 이 업무의 자기점검 역량 연결([{tr.primary_comp_name}])은 자동 판정 결과이며 담당자 검토가 필요합니다.")

            if not tr.courses:
                st.info("이 업무와 내용이 충분히 가까운 교육을 찾지 못했어요. 학습 조건(예산·교육 형태)을 넓혀 보세요.")
            for card in tr.courses:
                render_course_card(card, key_prefix=f"{key_prefix}{tr.task_id}_")
            if tr.excluded_low_similarity:
                st.caption(f"업무 내용과 관련성이 낮거나 분야가 다른(개발·마케팅 등) 후보 {tr.excluded_low_similarity}건은 제외했습니다.")


def render_recommendation_view(bundle: CustomerRecommendationBundle, key_prefix: str = ""):
    """정직한 사실 정보와 추천 사유를 기반으로 교육과정 카드 및 비교 뷰를 렌더링합니다."""
    saved_cnt = len(st.session_state.get("saved_courses", {}))
    eval_job = bundle.job_family

    # 1. 상단 인라인 안내 & 관심 보관함 바로가기 (실제 작동하는 링크)
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background: #F1F5F9; border-radius: 8px; padding: 0.65rem 1rem; margin-bottom: 1.1rem; flex-wrap: wrap; gap: 0.6rem;">
      <div style="font-size: 0.88rem; color: #334155;">
        💡 <strong>이용 안내</strong>: 진단된 역량 차이에 맞춰 실제 커리큘럼이 검증된 교육과정입니다. 마음에 드는 강좌는 <strong>[☆ 관심 교육 저장]</strong>하거나 <strong>[📊 비교에 추가]</strong>해 보세요.
      </div>
      <div>
        <button onclick="window.switchToMyLearningTab(event);" style="background: #FFFFFF; border: 1.5px solid #2563EB; color: #2563EB; font-weight: 700; font-size: 0.85rem; padding: 0.35rem 0.85rem; border-radius: 6px; cursor: pointer; transition: all 0.15s ease;">
          📚 관심 보관함 바로가기 ({saved_cnt}개)
        </button>
      </div>
    </div>

    <!-- 우측 하단 플로팅 퀵 액션: 페이지 맨위로 이동 전용 -->
    <div class="hrd-floating-actions">
      <a href="#top-anchor" class="hrd-circle-btn hrd-circle-top" title="페이지 맨 위로 이동">
        <span style="font-size: 1.15rem; line-height: 1;">↑</span>
        <span>맨위로</span>
      </a>
    </div>
    """, unsafe_allow_html=True)

    # 2. 검색 및 필터 박스
    st.markdown('<div class="hrd-search-card">', unsafe_allow_html=True)
    
    # 검색어 및 교육기관명 입력창
    s_col1, s_col2 = st.columns([1, 6])
    with s_col1:
        st.markdown("<div style='font-size: 0.92rem; font-weight: 700; color: #1E293B; padding-top: 0.5rem;'>검색어</div>", unsafe_allow_html=True)
    with s_col2:
        search_query = st.text_input(
            "검색어",
            placeholder="강좌명 또는 연계 역량 키워드를 입력해 보세요.",
            label_visibility="collapsed",
            key=f"{key_prefix}hrd_search_input"
        )

    i_col1, i_col2 = st.columns([1, 6])
    with i_col1:
        st.markdown("<div style='font-size: 0.92rem; font-weight: 700; color: #1E293B; padding-top: 0.5rem;'>교육기관명</div>", unsafe_allow_html=True)
    with i_col2:
        provider_query = st.text_input(
            "교육기관명",
            placeholder="교육기관명을 입력하여 훈련과정을 찾아보세요. (예: 휴넷, GSEEK, KPC, 한국생산성본부 등)",
            label_visibility="collapsed",
            key=f"{key_prefix}hrd_provider_input"
        )

    # 추가 검색조건 열기 (Expander)
    with st.expander("추가 검색조건 열기 ∨", expanded=False):
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            p_filter_new = st.selectbox(
                "수강료 조건",
                options=["전체 (유료+무료)", "무료 과정만", "예산 한도 설정"],
                index=0 if st.session_state["price_filter"] == "ALL" else (1 if st.session_state["price_filter"] == "FREE_ONLY" else 2),
                key=f"{key_prefix}filter_tab2_price"
            )
        with f_col2:
            edu_new = st.selectbox(
                "교육 형태",
                options=["전체", "온라인 우선", "오프라인/집체 우선"],
                index=0 if st.session_state["edu_type"] == "ALL" else (1 if st.session_state["edu_type"] == "ONLINE" else 2),
                key=f"{key_prefix}filter_tab2_edu"
            )
        with f_col3:
            w_new = st.slider("주당 학습 가능 시간 (시간)", 1.0, 20.0, float(st.session_state["weekly_hours"]), 0.5, key=f"{key_prefix}filter_tab2_weekly")

    # 선택된 검색조건 표시 & 검색/초기화 액션 버튼
    btn_col_left, btn_col_right = st.columns([4, 1.5])
    
    cond_tags = [f"직무: {eval_job}"]
    if st.session_state["edu_type"] != "ALL":
        cond_tags.append(f"형태: {'온라인' if st.session_state['edu_type'] == 'ONLINE' else '오프라인'}")
    if st.session_state["price_filter"] == "FREE_ONLY":
        cond_tags.append("수강료: 무료")
    elif st.session_state["price_filter"] == "MAX_BUDGET":
        cond_tags.append(f"수강료: {st.session_state['max_budget']:,}원 이하" if st.session_state.get('max_budget') else "수강료: 예산한도")

    with btn_col_left:
        tags_html = " ".join([f"<span class='hrd-tag-applied'>{t}</span>" for t in cond_tags])
        st.markdown(f"""
        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 0.4rem; padding-top: 0.4rem;">
          <span class="hrd-condition-count-badge">적용 조건 {len(cond_tags)}개</span>
          {tags_html}
        </div>
        """, unsafe_allow_html=True)

    with btn_col_right:
        act_col1, act_col2 = st.columns([1, 1.4])
        with act_col1:
            if st.button("🔄 조건 초기화", key=f"{key_prefix}hrd_btn_reset", use_container_width=True):
                st.session_state["price_filter"] = "ALL"
                st.session_state["max_budget"] = None
                st.session_state["edu_type"] = "ALL"
                st.session_state["weekly_hours"] = 4.0
                f_params = RecommendationFilterParams(
                    price_filter="ALL",
                    max_budget=None,
                    edu_type="ALL",
                    weekly_hours=4.0
                )
                st.session_state["rec_bundle"] = get_recommendations_for_assessment(st.session_state["eval_result"], f_params)
                st.rerun()

        with act_col2:
            if st.button("🔍 검색", type="primary", key=f"{key_prefix}hrd_btn_search", use_container_width=True):
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

                f_params = RecommendationFilterParams(
                    price_filter=st.session_state["price_filter"],
                    max_budget=st.session_state["max_budget"],
                    edu_type=st.session_state["edu_type"],
                    weekly_hours=st.session_state["weekly_hours"]
                )
                st.session_state["rec_bundle"] = get_recommendations_for_assessment(st.session_state["eval_result"], f_params)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    # 3. 결과 필터링 (선택 역량 필터 및 검색어/기관명 실시간 매칭)
    courses_to_render = bundle.all_courses_deduped
    sel_c_id = st.session_state.get("selected_competency_filter", "ALL")
    if sel_c_id != "ALL":
        sel_c_name = sel_c_id
        for c in bundle.all_courses_deduped:
            for item in c.linked_competencies:
                if item["competency_id"] == sel_c_id:
                    sel_c_name = item["competency_name"]
                    break
            if sel_c_name != sel_c_id:
                break
        
        comp_filtered = [
            c for c in courses_to_render
            if any(item["competency_id"] == sel_c_id for item in c.linked_competencies)
        ]
        if comp_filtered:
            courses_to_render = comp_filtered
            c_f1, c_f2 = st.columns([3.8, 1.2])
            with c_f1:
                st.info(f"🎯 **[{sel_c_name}]** 역량에 연계된 교육과정을 우선 표시하고 있습니다.")
            with c_f2:
                if st.button("🔄 전체 보완 역량 보기", key=f"{key_prefix}btn_clear_comp_filter", use_container_width=True):
                    st.session_state["selected_competency_filter"] = "ALL"
                    st.rerun()

    if search_query:
        sq = search_query.strip().lower()
        courses_to_render = [
            c for c in courses_to_render
            if sq in c.title.lower() or sq in c.primary_competency_name.lower() or sq in c.customer_recommendation_reason.lower()
        ]
    if provider_query:
        pq = provider_query.strip().lower()
        courses_to_render = [c for c in courses_to_render if pq in c.provider.lower()]

    # 4. 강좌 비교 드로어 (비교 강좌가 선택되어 있으면 표시)
    compared_dict = st.session_state.get("compared_courses", {})
    if compared_dict:
        with st.expander(f"⚖️ 선택 강좌 나란히 비교 (현재 {len(compared_dict)}/3개 담김)", expanded=True):
            cmp_cols = st.columns(len(compared_dict))
            for c_idx, (cmp_uid, cmp_card) in enumerate(list(compared_dict.items())):
                with cmp_cols[c_idx]:
                    st.markdown(f"""
                    <div class="customer-card" style="height: 100%; border: 1.5px solid #2563EB;">
                      <div style="font-weight: 800; font-size: 1.02rem; margin-bottom: 0.4rem; height: 3.2rem; overflow: hidden; line-height: 1.35; color: #0F172A;">
                        {cmp_card.title}
                      </div>
                      <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; margin-bottom: 0.5rem;">
                        • <strong>기관</strong>: {cmp_card.provider}<br>
                        • <strong>비용</strong>: {cmp_card.price_display}<br>
                        • <strong>시간</strong>: {cmp_card.duration_display}<br>
                        • <strong>형태</strong>: {cmp_card.education_type}<br>
                        • <strong>보완 역량</strong>: {cmp_card.primary_competency_name}<br>
                        • <strong>일정</strong>: {cmp_card.schedule_display}
                      </div>
                      <div style="font-size: 0.8rem; color: #1E3A8A; background: #EFF6FF; padding: 0.45rem; border-radius: 4px; margin-bottom: 0.5rem;">
                        {cmp_card.goal_connection}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<a href='{cmp_card.url}' target='_blank' style='display:block; text-align:center; font-size:0.85rem; font-weight:700; color:#2563EB; margin:0.3rem 0;'>교육 상세·신청 안내 ↗</a>", unsafe_allow_html=True)
                    if st.button("비교 제외", key=f"{key_prefix}btn_remove_cmp_{cmp_uid}", use_container_width=True):
                        del st.session_state["compared_courses"][cmp_uid]
                        st.toast("비교 목록에서 제외되었습니다.")
                        st.rerun()

    # 5. 결과 타이틀 (정확한 목록명 사용)
    st.markdown(f"""
    <div style="display: flex; align-items: baseline; gap: 0.6rem; margin-top: 1.4rem; margin-bottom: 0.8rem; flex-wrap: wrap;">
      <h3 style="margin: 0; font-size: 1.35rem; font-weight: 800; color: #0F172A;">내 보완 역량에 맞는 교육</h3>
      <span style="font-size: 1rem; color: #475569;">총 <strong style="color: #2563EB; font-size: 1.15rem;">{len(courses_to_render)}</strong>건</span>
      <span style="font-size: 0.85rem; color: #64748B;">(보완 대상 역량 {bundle.evaluated_competency_count}개 연계)</span>
    </div>
    """, unsafe_allow_html=True)

    if bundle.actionable_guidance:
        st.markdown(f"""
        <div class="callout-warning">
          {bundle.actionable_guidance.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)

    # 6. 강좌 카드 렌더링 (우선 추천 3개 + 더보기 구조)
    if not courses_to_render:
        st.info("검색 조건에 일치하는 교육과정이 없습니다. 검색어 또는 필터 조건을 조정해 보세요.")
    else:
        show_all_key = f"{key_prefix}show_all_cards"
        if show_all_key not in st.session_state:
            st.session_state[show_all_key] = False

        is_show_all = st.session_state[show_all_key]
        cards_to_display = courses_to_render if is_show_all else courses_to_render[:3]

        for card in cards_to_display:
            render_course_card(card, key_prefix)

        # 우선 추천 3개 초과 시 더보기 / 접기 버튼
        if len(courses_to_render) > 3:
            if not is_show_all:
                if st.button(f"추천 교육과정 더보기 ({len(courses_to_render) - 3}건 더보기) ∨", key=f"{key_prefix}btn_expand_more", use_container_width=True):
                    st.session_state[show_all_key] = True
                    st.rerun()
            else:
                if st.button("추천 교육과정 접기 (우선 추천 3개만 보기) ∧", key=f"{key_prefix}btn_collapse_more", use_container_width=True):
                    st.session_state[show_all_key] = False
                    st.rerun()


# 메인 탭 네비게이션
st.markdown('<div id="top-anchor"></div>', unsafe_allow_html=True)
MAIN_TAB_OPTIONS = [
    "📋 내 역량 점검",
    "🎓 맞춤 교육",
    "📚 나의 학습"
]
# target_tab 요청이 있으면 active_main_tab에 반영 (st.tabs 인스턴스화 전 처리)
if "target_tab" in st.session_state and st.session_state["target_tab"]:
    st.session_state["active_main_tab"] = st.session_state.pop("target_tab")

if st.session_state.get("active_main_tab") not in MAIN_TAB_OPTIONS:
    st.session_state["active_main_tab"] = "📋 내 역량 점검"

tab_assessment, tab_recommend, tab_my_learning = st.tabs(
    MAIN_TAB_OPTIONS,
    default=st.session_state["active_main_tab"],
    key="active_main_tab",
    on_change="rerun"
)

# ------------------------------------------------------------------------------
# TAB 1: 내 역량 점검 (내 업무 설정 -> 행동 점검 -> 결과 확인)
# ------------------------------------------------------------------------------
with tab_assessment:
    # 상단 샘플 모드 알림 또는 바로보기 안내
    if st.session_state["is_sample_mode"]:
        render_sample_banner("tab1_top")
        col_res1, col_res2 = st.columns([3.8, 1.2])
        with col_res2:
            st.button("🔄 전체 초기화", on_click=reset_all_assessment, use_container_width=True, key="reset_in_sample")
    else:
        top_col1, top_col2 = st.columns([3, 1.4])
        with top_col1:
            st.caption("💡 설문 작성이 부담스러우시다면 '샘플 결과 보기'로 진단 결과 및 추천 화면을 먼저 체험해 보세요.")
        with top_col2:
            btn_sample_col1, btn_sample_col2 = st.columns(2)
            with btn_sample_col1:
                if st.button("👀 샘플 결과 보기", use_container_width=True, help="설문 작성 없이 예시 결과를 먼저 확인합니다."):
                    st.session_state["real_user_survey"] = copy.deepcopy(st.session_state.get("survey_responses", {}))
                    st.session_state["real_user_targets"] = copy.deepcopy(st.session_state.get("target_levels", {}))
                    st.session_state["real_user_eval"] = st.session_state.get("eval_result")
                    st.session_state["real_user_bundle"] = st.session_state.get("rec_bundle")
                    sample_res = get_sample_assessment_result(st.session_state.get("job_family", "인사"))
                    st.session_state["eval_result"] = sample_res
                    st.session_state["is_sample_mode"] = True
                    st.session_state["current_step"] = "STEP_RESULT"
                    st.session_state["scroll_to_result"] = True
                    f_params = RecommendationFilterParams(
                        price_filter=st.session_state["price_filter"],
                        max_budget=st.session_state["max_budget"] if st.session_state["price_filter"] == "MAX_BUDGET" else None,
                        edu_type=st.session_state["edu_type"],
                        weekly_hours=st.session_state["weekly_hours"]
                    )
                    st.session_state["rec_bundle"] = get_recommendations_for_assessment(sample_res, f_params)
                    st.rerun()
            with btn_sample_col2:
                st.button("🔄 전체 초기화", on_click=reset_all_assessment, use_container_width=True, key="reset_in_normal")

    # 1단계: 내 업무 설정 (프로필)
    st.markdown('<div id="section-step1-profile"></div>', unsafe_allow_html=True)
    if st.session_state.pop("scroll_to_step1", False):
        st.markdown("""
        <script>
        setTimeout(function() {
          const el = document.getElementById("section-step1-profile");
          if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
        }, 200);
        </script>
        """, unsafe_allow_html=True)
    st.subheader("1. 나의 업무 설정")
    step1_expanded = (st.session_state["eval_result"] is None) or st.session_state.get("scroll_to_step1", False)
    with st.expander("💼 담당 직무 및 업무 환경 설정", expanded=step1_expanded):
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
        has_domains = any("domain_id" in t for t in job_tasks)

        if has_domains:
            # 인사: 9개 분야를 먼저 고르고, 분야별 세부 업무(90개)를 선택
            domain_names = {}
            for t in job_tasks:
                domain_names.setdefault(t["domain_id"], t["domain_name"])
            task_domain_of = {t["task_id"]: t["domain_id"] for t in job_tasks}
            default_domains = st.session_state.get("selected_task_domains") or sorted(
                {task_domain_of[t] for t in st.session_state["selected_tasks"] if t in task_domain_of}
            )
            sel_domains = st.multiselect(
                "① 담당 인사 분야",
                options=list(domain_names.keys()),
                default=[d for d in default_domains if d in domain_names],
                format_func=lambda d: domain_names.get(d, d),
            )
            st.session_state["selected_task_domains"] = sel_domains
            visible_tasks = [t for t in job_tasks if t["domain_id"] in sel_domains]
            task_opts = {t["task_id"]: f"[{t['domain_name']} · {t['stage']}] {t['task_name']}" for t in visible_tasks}
            st.caption("업무 목록은 팀이 실무 기준으로 정리한 초안이며 NCS 공식 능력단위가 아닙니다. 업무를 고르면 '맞춤 교육'에서 업무별 추천 교육을 함께 볼 수 있어요.")
        else:
            task_opts = {t["task_id"]: t["task_name"] for t in job_tasks}

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

    # 응답 진행 상태 표시 (무응답을 기본 3점으로 자동 처리하지 않음)
    answered_cnt = sum(1 for q in job_questions if st.session_state["survey_responses"].get(q["question_id"]) is not None)
    total_q_cnt = len(job_questions)
    progress_pct = (answered_cnt / total_q_cnt * 100.0) if total_q_cnt > 0 else 0.0

    st.markdown(f"**응답 진행 상태**: {answered_cnt} / {total_q_cnt} 문항 완료 ({progress_pct:.0f}%)")
    st.progress(min(1.0, progress_pct / 100.0))

    if st.session_state.get("stale_results") and st.session_state.get("eval_result") is not None:
        st.markdown("""
        <div class="callout-warning" style="margin-bottom: 1rem;">
          ⚠️ <strong>설문 응답 또는 업무 설정이 변경되었습니다.</strong> 아래 [📊 역량 자기점검 결과 계산하기] 버튼을 눌러 결과를 다시 계산해 주세요.
        </div>
        """, unsafe_allow_html=True)
    
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
            with st.expander(f"기준 자세히 보기 ({comp_name} 역량 정의 및 NCS 분류)", expanded=False):
                st.markdown(f"""
                • **역량 정의**: {master_info.get('definition', '')}<br>
                • **NCS 분류 기준**: {ncs_code} (초안)
                """, unsafe_allow_html=True)

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

                prev_val = st.session_state["survey_responses"].get(qid, None)
                ans_options = [
                    "1점: 아직 직접 수행해본 적이 없다",
                    "2점: 매뉴얼이나 선배의 구체적인 도움을 받아 수행한다",
                    "3점: 일반적인 상황에서 혼자 무리 없이 완수한다",
                    "4점: 예외 상황이나 예상치 못한 문제에도 유연하게 대처한다",
                    "5점: 프로세스를 개선하거나 다른 동료에게 노하우를 가르친다",
                    "해당 업무 아님 (평가 제외)",
                    "판단하기 어려움 (평가 제외)"
                ]

                # 기본 선택 인덱스 매핑 (이전 응답이 없으면 선택하지 않은 상태 index=None 유지)
                def_idx = None
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

                if chosen is not None:
                    if "1점" in chosen: form_responses[qid] = 1
                    elif "2점" in chosen: form_responses[qid] = 2
                    elif "3점" in chosen: form_responses[qid] = 3
                    elif "4점" in chosen: form_responses[qid] = 4
                    elif "5점" in chosen: form_responses[qid] = 5
                    elif "해당 업무 아님" in chosen: form_responses[qid] = "NA"
                    elif "판단하기 어려움" in chosen: form_responses[qid] = "UNCERTAIN"

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
        st.markdown('<div id="result-summary-section"></div>', unsafe_allow_html=True)
        if st.session_state.pop("scroll_to_result", False):
            st.markdown("""
            <script>
            setTimeout(function() {
              const el = document.getElementById("result-summary-section");
              if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
            }, 300);
            </script>
            """, unsafe_allow_html=True)
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
            st.metric("진단 직무", f"{eval_res.job_family} ({eval_res.career_range})")
        with m_col2:
            st.metric("유효 평가 역량", f"{eval_res.overall_summary['valid_competencies_count']}개")
        with m_col3:
            st.metric("우선 보완 필요 역량", f"{len(eval_res.prioritized_deficiencies)}개")
        with m_col4:
            st.metric("정보 부족 역량", f"{eval_res.overall_summary['insufficient_count']}개")

        # 1. 최상단 배치: 우선 보완할 핵심 역량 (최대 3개)
        st.markdown("##### 🚀 우선 보완할 핵심 역량 (최대 3개)")
        if eval_res.prioritized_deficiencies:
            for cs in eval_res.prioritized_deficiencies:
                task_badge = '<span class="badge-tag badge-teal" style="margin-left:0.35rem;">💼 수행 업무 연계</span>' if cs.is_task_related else ''
                reason_desc = (
                    "사용자의 실제 수행 업무와 직접 연관되어 있으며, 목표 수준과의 차이가 가장 커 우선적인 보완이 시급합니다."
                    if cs.is_task_related else
                    "설정하신 목표 수준 대비 자기평가 차이가 커 집중적인 보완 학습이 권장됩니다."
                )

                card_c1, card_c2 = st.columns([3.8, 1.2])
                with card_c1:
                    card_html = (
                        '<div class="customer-card" style="margin-bottom: 0.5rem;">'
                        '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.4rem;">'
                        f'<div><span class="badge-tag badge-primary">우선순위 {cs.priority_rank}위</span>{task_badge}'
                        f'<span style="font-size: 1.15rem; font-weight: 800; margin-left: 0.35rem; color: #0F172A;">[{cs.competency_name}]</span></div>'
                        f'<div><span style="font-size: 0.92rem; font-weight: 600; color: #4F46E5;">'
                        f'현재 자기평가 {cs.current_level:.1f}점 ➔ 목표 {cs.target_level:.1f}점 (목표와의 차이: <strong>{cs.gap:.1f}점</strong>)</span></div>'
                        '</div>'
                        f'<div style="font-size: 0.88rem; color: #475569; line-height: 1.6;">'
                        f'• <strong>역량 설명</strong>: {cs.description}<br>'
                        f'• <strong>우선순위 선정 이유</strong>: {reason_desc}<br>'
                        f'• <strong>응답 현황</strong>: 총 {cs.total_question_count}문항 중 유효 응답 {cs.valid_response_count}문항 (유효 평가 완료)'
                        '</div>'
                        '</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                with card_c2:
                    st.markdown("<div style='padding-top: 1.3rem;'></div>", unsafe_allow_html=True)
                    if st.button("🎓 이 역량 교육 보기", key=f"btn_see_comp_rec_{cs.competency_id}", use_container_width=True):
                        st.session_state["selected_competency_filter"] = cs.competency_id
                        switch_main_tab("🎓 맞춤 교육")
        elif eval_res.overall_summary['valid_competencies_count'] == 0:
            st.markdown("""
            <div class="callout-warning" style="border-left-color: #E11D48; background: #FFF1F2; color: #9F1239; margin: 1rem 0;">
              ⚠️ <strong>모든 역량 문항에 유효 응답이 부족하여 진단 기반 추천을 확정할 수 없습니다.</strong><br>
              모든 문항에서 '해당 업무 아님' 또는 '판단하기 어려움'이 선택되어 점수와 역량 차이를 산출할 수 없습니다.<br>
              상단의 <strong>'2. 핵심 역량 자기점검'</strong> 문항에서 1~5점 척도로 본인의 행동 수준을 응답하신 후 [📊 역량 자기점검 결과 계산하기]를 다시 눌러주세요.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="callout-info">
              🎉 <strong>축하합니다!</strong> 설정하신 모든 목표 수준을 이미 달성하셨거나 역량 차이가 없습니다.<br>
              부족한 역량을 임의로 생성하지 않으며, 현재의 전문성을 유지·심화할 수 있는 <strong>심화·전문가 과정</strong>을 맞춤 추천합니다.
            </div>
            """, unsafe_allow_html=True)

        # 2. 역량별 비교 차트 (동일 1~5 척도 기준 가로 막대 차트, 정보 부족 항목은 0점으로 그리지 않고 제외)
        st.markdown("##### 📊 역량별 현재 자기평가 vs 설정 목표 수준 비교 (1~5점 척도)")
        chart_comps = []
        curr_scores = []
        target_scores = []
        gaps = []

        valid_comps = [cs for cs in eval_res.competency_scores.values() if not cs.is_insufficient]
        if valid_comps:
            chart_comps = [cs.competency_name for cs in valid_comps]
            curr_scores = [cs.current_level for cs in valid_comps]
            target_scores = [cs.target_level for cs in valid_comps]
            customdata_curr = [
                [f"{cs.valid_response_count}/{cs.total_question_count}문항", cs.gap or 0.0, cs.competency_id]
                for cs in valid_comps
            ]
            customdata_target = [
                [f"{cs.valid_response_count}/{cs.total_question_count}문항", cs.gap or 0.0, cs.competency_id]
                for cs in valid_comps
            ]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=chart_comps,
                x=curr_scores,
                name="현재 자기평가",
                orientation="h",
                marker=dict(
                    color="#4F46E5",
                    line=dict(color="#3730A3", width=1)
                ),
                text=[f"{v:.1f}점" for v in curr_scores],
                textposition="auto",
                customdata=customdata_curr,
                hovertemplate="<b>%{y}</b><br>현재 자기평가: <b>%{x:.1f}점</b><br>유효 응답: <b>%{customdata[0]}</b><br>목표와의 차이: <b>%{customdata[1]:.1f}점</b><extra></extra>"
            ))
            fig.add_trace(go.Bar(
                y=chart_comps,
                x=target_scores,
                name="설정 목표 수준",
                orientation="h",
                marker=dict(
                    color="#93C5FD",
                    line=dict(color="#60A5FA", width=1)
                ),
                text=[f"{v:.1f}점" for v in target_scores],
                textposition="auto",
                customdata=customdata_target,
                hovertemplate="<b>%{y}</b><br>설정 목표 수준: <b>%{x:.1f}점</b><br>목표와의 차이: <b>%{customdata[1]:.1f}점</b><extra></extra>"
            ))
            fig.update_layout(
                barmode="group",
                height=max(260, 180 + len(valid_comps) * 45),
                margin=dict(l=15, r=15, t=30, b=15),
                xaxis=dict(
                    range=[0, 5.3],
                    title=dict(text="역량 점수 (5점 척도)", font=dict(size=12, color="#475569")),
                    dtick=1.0,
                    gridcolor="#E2E8F0"
                ),
                yaxis=dict(
                    autorange="reversed",
                    tickfont=dict(size=12, color="#0F172A", family="Pretendard, sans-serif")
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.03,
                    xanchor="right",
                    x=1,
                    font=dict(size=11)
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                hoverlabel=dict(
                    bgcolor="#1E293B",
                    font_size=12,
                    font_color="#FFFFFF",
                    font_family="Pretendard, sans-serif"
                )
            )
            st.plotly_chart(fig, use_container_width=True)

            # 역량 선택과 맞춤 교육 필터 연계 인터랙션 바
            st.markdown("<div style='font-size: 0.88rem; font-weight: 700; color: #334155; margin-top: 0.2rem; margin-bottom: 0.4rem;'>🎯 차트 역량 클릭 연계 (선택 시 해당 교육 바로 이동):</div>", unsafe_allow_html=True)
            filter_cols = st.columns(min(len(valid_comps), 4))
            for i, cs in enumerate(valid_comps):
                col_target = filter_cols[i % len(filter_cols)]
                with col_target:
                    gap_badge = f" (차이 {cs.gap:.1f}점)" if cs.gap and cs.gap > 0 else " (충족)"
                    btn_text = f"🎓 {cs.competency_name}{gap_badge}"
                    if st.button(btn_text, key=f"chart_comp_btn_{cs.competency_id}", use_container_width=True):
                        st.session_state["selected_competency_filter"] = cs.competency_id
                        switch_main_tab("🎓 맞춤 교육")

        # 정보 부족 역량 안내 (0점으로 왜곡하지 않고 별도 격리 안내)
        if eval_res.insufficient_competencies:
            ins_names = [f"[{cs.competency_name}] (유효 응답 {cs.valid_response_count}/{cs.total_question_count}문항)" for cs in eval_res.insufficient_competencies]
            st.markdown(f"""
            <div class="callout-warning">
              ⚠️ <strong>정보 부족 항목 ({len(eval_res.insufficient_competencies)}건)</strong>: {', '.join(ins_names)}<br>
              '해당 업무 아님' 또는 '판단 어려움'으로 인해 유효 응답이 2문항 미만입니다. 
              점수를 0점으로 왜곡하여 비교하지 않고 차트 및 부족 판정에서 제외했습니다. 상단 설문에서 추가 응답 시 정확한 진단이 가능합니다.
            </div>
            """, unsafe_allow_html=True)

        # 3. 진단 결과 하단: 맞춤 교육 이동 안내 및 결과 다운로드 (교육 목록은 맞춤 교육 탭으로 완전 분리)
        if eval_res.overall_summary['valid_competencies_count'] > 0:
            st.markdown("""
            <div style="background: #EFF6FF; border: 1.5px solid #BFDBFE; border-radius: 12px; padding: 1.25rem 1.6rem; margin-top: 1.6rem; margin-bottom: 1rem;">
              <div style="font-size: 1.18rem; font-weight: 800; color: #1E3A8A; margin-bottom: 0.35rem;">
                선택한 보완 역량에 맞는 교육을 확인해보세요
              </div>
              <div style="font-size: 0.9rem; color: #475569; line-height: 1.6;">
                진단 결과 도출된 우선 보완 역량을 채워줄 수 있는 검증된 교육과정이 준비되어 있습니다.<br>
                아래 버튼을 누르면 <strong>'🎓 맞춤 교육'</strong> 탭으로 이동하여 추천 강좌, 커리큘럼 근거, 교육기관 일정을 확인하고 비교할 수 있습니다.
              </div>
            </div>
            """, unsafe_allow_html=True)

            bot_c1, bot_c2 = st.columns([1.6, 1.4])
            with bot_c1:
                if st.button("🎓 내 역량에 맞는 교육 보기", type="primary", use_container_width=True, key="btn_go_to_matched_tab"):
                    st.session_state["selected_competency_filter"] = "ALL"
                    switch_main_tab("🎓 맞춤 교육")
            with bot_c2:
                # 결과 다운로드 기능 (실제 작동하는 텍스트 요약 파일 생성)
                summary_lines = [
                    "=== 실무 역량 자기점검 결과 요약 ===",
                    f"진단 직무: {eval_res.job_family} ({eval_res.career_range})",
                    f"학습 목표: {eval_res.learning_goal}",
                    f"유효 평가 역량: {eval_res.overall_summary['valid_competencies_count']}개 | 정보 부족 역량: {eval_res.overall_summary['insufficient_count']}개",
                    "",
                    "■ 우선 보완 필요 역량:"
                ]
                if eval_res.prioritized_deficiencies:
                    for cs in eval_res.prioritized_deficiencies:
                        summary_lines.append(f"- [{cs.competency_name}] 현재 자기평가 {cs.current_level:.1f}점 -> 목표 {cs.target_level:.1f}점 (차이 {cs.gap:.1f}점)")
                else:
                    summary_lines.append("- 설정된 모든 목표 수준 달성 (심화 학습 대상)")
                summary_lines.append("\n■ 역량별 세부 점수 현황:")
                for cid, cs in eval_res.competency_scores.items():
                    if not cs.is_insufficient:
                        summary_lines.append(f"- {cs.competency_name}: 현재 {cs.current_level:.1f}점 / 목표 {cs.target_level:.1f}점 (차이 {cs.gap:.1f}점)")
                    else:
                        summary_lines.append(f"- {cs.competency_name}: 정보 부족 (유효 응답 2문항 미만)")
                
                res_txt = "\n".join(summary_lines)
                st.download_button(
                    "📥 진단 결과 텍스트 요약 다운로드",
                    data=res_txt,
                    file_name=f"역량자기점검결과_{eval_res.job_family}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="btn_download_eval_summary"
                )

# ------------------------------------------------------------------------------
# TAB 2: 맞춤 교육 추천 (부족 역량 기반 강좌 카드, 대체 수강처, 상세 비교)
# ------------------------------------------------------------------------------
with tab_recommend:
    render_sample_banner("tab2")
    bundle: Optional[CustomerRecommendationBundle] = st.session_state.get("rec_bundle")
    
    if bundle is None:
        st.markdown("""
        <div style="text-align: center; padding: 2.5rem 1.5rem; background: #F8FAFC; border-radius: 12px; border: 1px dashed #CBD5E1; margin: 1.5rem 0;">
          <div style="font-size: 2.2rem; margin-bottom: 0.8rem;">📋</div>
          <div style="font-size: 1.25rem; font-weight: 800; color: #0F172A; margin-bottom: 0.5rem;">
            역량 점검을 완료하면 맞춤 교육을 확인할 수 있어요
          </div>
          <div style="font-size: 0.92rem; color: #64748B; max-width: 500px; margin: 0 auto 1.5rem auto; line-height: 1.6;">
            현재 수행 중인 업무와 핵심 역량 자기평가를 입력하시면, 목표 수준과의 차이를 분석하여 보완이 필요한 최적의 실제 교육과정을 추천해 드립니다.
          </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 내 역량 점검 시작", type="primary", use_container_width=True, key="btn_start_from_rec_empty"):
            st.session_state["scroll_to_step1"] = True
            switch_main_tab("📋 내 역량 점검")
    else:
        # 응답/목표가 변경된 경우 이전 추천 불일치 안내 & 재계산
        if st.session_state.get("stale_results"):
            st.markdown("""
            <div class="callout-warning" style="border-left-color: #E11D48; background: #FFF1F2; color: #9F1239; margin-bottom: 1.2rem;">
              ⚠️ <strong>[추천 갱신 필요]</strong><br>
              설문 응답 또는 업무 조건이 변경되었습니다. 현재 표시된 추천은 이전 진단 기준입니다. 
              최신 진단 결과를 반영한 교육을 확인하시려면 아래 버튼을 눌러주세요.
            </div>
            """, unsafe_allow_html=True)
            if st.button("📊 최신 결과로 재계산하기", type="primary", key="btn_recalc_in_rec", use_container_width=True):
                st.session_state["stale_results"] = False
                eval_res = calculate_competency_scores(
                    job_family=st.session_state["job_family"],
                    responses=st.session_state["survey_responses"],
                    target_levels=st.session_state["target_levels"],
                    user_task_ids=st.session_state["selected_tasks"],
                    career_range=st.session_state["career_range"],
                    difficult_task_desc=st.session_state["difficult_task"],
                    learning_goal=st.session_state["learning_goal"],
                    is_sample=st.session_state.get("is_sample_mode", False)
                )
                st.session_state["eval_result"] = eval_res
                f_params = RecommendationFilterParams(
                    price_filter=st.session_state["price_filter"],
                    max_budget=st.session_state["max_budget"] if st.session_state["price_filter"] == "MAX_BUDGET" else None,
                    edu_type=st.session_state["edu_type"],
                    weekly_hours=st.session_state["weekly_hours"]
                )
                st.session_state["rec_bundle"] = get_recommendations_for_assessment(eval_res, f_params)
                st.toast("최신 조건으로 교육 추천이 갱신되었습니다.")
                st.rerun()

        # 상단 헤더 컨트롤: 진단 결과 다시 보기 & 맞춤 교육 타이틀
        top_hdr1, top_hdr2 = st.columns([3.5, 1.5])
        with top_hdr1:
            st.markdown("### 🎓 내 보완 역량에 맞는 교육")
            st.caption("진단 결과 도출된 역량 차이와 설정하신 학습 조건을 반영한 실제 교육과정입니다.")
        with top_hdr2:
            st.markdown("<div style='padding-top: 0.35rem;'></div>", unsafe_allow_html=True)
            if st.button("📋 진단 결과 다시 보기", key="btn_back_to_eval_from_rec", use_container_width=True):
                st.session_state["scroll_to_result"] = True
                switch_main_tab("📋 내 역량 점검")

        # 상단 요약 박스: 이번 추천에 반영한 역량과 적용한 학습 조건
        eval_obj = st.session_state.get("eval_result")
        comp_summary_items = []
        if eval_obj:
            if eval_obj.prioritized_deficiencies:
                comp_summary_items = [f"<strong>{cs.competency_name}</strong>(차이 {cs.gap:.1f}점)" for cs in eval_obj.prioritized_deficiencies]
            elif eval_obj.zero_gap_competencies:
                comp_summary_items = [f"<strong>{cs.competency_name}</strong>(전문성 심화)" for cs in eval_obj.zero_gap_competencies[:3]]
        
        comp_summary_text = ", ".join(comp_summary_items) if comp_summary_items else "진단 결과 연계"
        p_text = "무료 과정만" if st.session_state["price_filter"] == "FREE_ONLY" else (f"{st.session_state['max_budget']:,}원 이하" if st.session_state.get('max_budget') else "전체(유료+무료)")
        e_text = "온라인 우선" if st.session_state["edu_type"] == "ONLINE" else ("오프라인 우선" if st.session_state["edu_type"] == "OFFLINE" else "전체")

        st.markdown(f"""
        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1.2rem; font-size: 0.88rem; line-height: 1.6; color: #334155;">
          • <strong>이번 추천에 반영한 역량</strong>: {comp_summary_text}<br>
          • <strong>적용한 학습 조건</strong>: 직무 {bundle.job_family} | 교육형태: {e_text} | 수강료: {p_text} | 주당 학습: {st.session_state['weekly_hours']}시간
        </div>
        """, unsafe_allow_html=True)

        render_recommendation_view(bundle, key_prefix="t2_main_")

        render_task_recommendations(key_prefix="t2_task_")

# ------------------------------------------------------------------------------
# TAB 3: 나의 학습 (선택 강좌 나란히 비교, 저장된 관심 강좌 관리, 재점검 히스토리)
# ------------------------------------------------------------------------------
with tab_my_learning:
    render_sample_banner("tab3")
    st.subheader("📚 나의 학습 관리함")
    
    st.markdown("""
    <div class="callout-info">
      💡 <strong>세션 안내</strong>: 본 서비스는 로그인 없이 브라우저 세션 단위로 보관함 및 비교함이 유지됩니다.<br>
      새로고침 시 임시 데이터가 초기화될 수 있으므로, 관심 있는 교육의 상세 링크를 북마크해 두시길 권장합니다.
    </div>
    """, unsafe_allow_html=True)

    compared_dict = st.session_state.get("compared_courses", {})
    saved_dict = st.session_state.get("saved_courses", {})

    # 1. 강좌 상세 비교 (최대 3개 나란히 비교 - compared_courses 기반)
    st.markdown(f"##### ⚖️ 선택 강좌 나란히 비교 (현재 {len(compared_dict)}/3개 담김)")
    if not compared_dict:
        st.info("💡 추천 강좌 카드에서 **[📊 비교에 추가]** 버튼을 클릭하시면 최대 3개 강좌를 여기서 나란히 비교할 수 있습니다.")
    else:
        with st.container():
            cmp_cols = st.columns(len(compared_dict))
            for idx, (c_uid, c_card) in enumerate(list(compared_dict.items())):
                with cmp_cols[idx]:
                    st.markdown(f"""
                    <div class="customer-card" style="height: 100%; border: 1.5px solid #2563EB;">
                      <div style="font-weight: 800; font-size: 1.02rem; margin-bottom: 0.4rem; height: 3.2rem; overflow: hidden; line-height: 1.35; color: #0F172A;">
                        {c_card.title}
                      </div>
                      <div style="font-size: 0.85rem; color: #475569; line-height: 1.6; margin-bottom: 0.5rem;">
                        • <strong>기관</strong>: {c_card.provider}<br>
                        • <strong>비용</strong>: {c_card.price_display}<br>
                        • <strong>시간</strong>: {c_card.duration_display}<br>
                        • <strong>형태</strong>: {c_card.education_type}<br>
                        • <strong>보완 역량</strong>: {c_card.primary_competency_name}<br>
                        • <strong>일정</strong>: {c_card.schedule_display}
                      </div>
                      <div style="font-size: 0.8rem; color: #1E3A8A; background: #EFF6FF; padding: 0.45rem; border-radius: 4px; margin-bottom: 0.5rem;">
                        {c_card.goal_connection}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<a href='{c_card.url}' target='_blank' style='display:block; text-align:center; font-size:0.85rem; font-weight:700; color:#2563EB; margin:0.3rem 0;'>교육 상세·신청 안내 ↗</a>", unsafe_allow_html=True)
                    if st.button("비교에서 제외", key=f"btn_my_remove_cmp_{c_uid}", use_container_width=True):
                        del st.session_state["compared_courses"][c_uid]
                        st.toast("비교 목록에서 제외되었습니다.")
                        st.rerun()

    st.markdown("---")

    # 2. 관심 교육 보관함 (saved_courses 기반)
    st.markdown(f"##### ⭐ 관심 교육 보관함 (현재 {len(saved_dict)}개 저장됨)")
    if not saved_dict:
        st.info("💡 추천 강좌 카드에서 **[☆ 관심 교육 저장]** 버튼을 누르시면 여기에 강좌가 보관되어 학습 메모와 진도를 관리할 수 있습니다.")
    else:
        for c_uid, item in list(saved_dict.items()):
            c_card: RecommendedCourseCard = item["card"]
            with st.container():
                st_col1, st_col2, st_col3 = st.columns([3, 1.5, 1])
                with st_col1:
                    st.markdown(f"**{c_card.title}** ({c_card.provider})")
                    st.markdown(f"<a href='{c_card.url}' target='_blank' style='font-size:0.85rem; color:#2563EB; font-weight:600;'>교육 상세·신청 안내 ↗</a>", unsafe_allow_html=True)
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
                    if st.button("🗑️ 보관함 삭제", key=f"del_saved_{c_uid}", use_container_width=True):
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
  📝 <strong>수강 후기·평점</strong>: 검증된 실제 수강 후기가 충분하지 않아, 추천 순위와 화면에 후기·평점 정보를 사용하지 않습니다.<br>
  ⚙️ kimsaemi/edu-skill-gap | 실무 역량 진단 & 맞춤 교육 추천 서비스
</div>
""", unsafe_allow_html=True)
