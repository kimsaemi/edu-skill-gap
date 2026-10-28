"""
NCS·KSA 직무 맞춤형 교육 추천 시스템 - 사용자용 서비스 MVP (User Recommendation MVP)
--------------------------------------------------------------------------------
1. 단계별 추천 플로우:
   Step 1. 담당 직무 선택 (인사 / 총무 / 경영지원)
   Step 2. 담당 세부 과업(Task) 선택 (18개 실무 Task 마스터)
   Step 3. 필요 KSA 역량 확인 (지식·기술·태도 및 공식 NCS 분류 확인)
   Step 4. 현재 직급 / 업무 숙련도 선택 (입문·초급 / 실무·중급 / 관리자·심화)
   Step 5. 개인 학습 조건 (예산, 교육시간, 교육방식, 추천 개수)
   Step 6. 맞춤 교육 Top 3/5/10 추천 결과 및 실제 커리큘럼 기반 추천 이유
2. 추천 강좌 간 다차원 나란히 비교(Side-by-side Comparison) 모듈
3. 엄격한 원칙 준수:
   - 합성 리뷰 데이터 및 평점 가중치 완전 배제 (운영 추천에 순수 실제 교육 데이터만 반영)
   - 공통 추천 엔진(UnifiedHybridRecommender) 재사용
   - 공식 NCS 기준과 프로젝트 자체 Task 정의 구분 명시
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import streamlit as st

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.recommendation.task_master import (
    TASK_MASTER,
    get_tasks_for_job,
    get_task_by_id,
    get_ksa_for_task
)
from src.recommendation.ksa_master import get_competency_by_id
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender

@st.cache_resource(show_spinner="맞춤 교육 추천 엔진을 초기화하고 있습니다...")
def get_mvp_recommender():
    return UnifiedHybridRecommender()

def render_user_recommendation_mvp():
    # --------------------------------------------------------------------------
    # 헤더 섹션
    # --------------------------------------------------------------------------
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #334155 100%); 
                padding: 1.8rem 2.2rem; border-radius: 16px; margin-bottom: 1.8rem; color: white;
                box-shadow: 0 8px 24px -4px rgba(15, 23, 42, 0.25); border: 1px solid rgba(255,255,255,0.08);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
        <div>
          <span style="background: linear-gradient(135deg, #6366F1 0%, #3B82F6 100%); color: white; 
                       padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em;">
            SERVICE MVP v1.0
          </span>
          <h1 style="color: #FFFFFF; font-size: 1.85rem; font-weight: 800; margin: 0.55rem 0 0.35rem 0; letter-spacing: -0.025em;">
            직무·과업 맞춤형 교육과정 추천 서비스
          </h1>
          <p style="color: #94A3B8; margin: 0; font-size: 0.92rem; font-weight: 400; max-width: 800px; line-height: 1.55;">
            담당하시는 <b>직무</b>와 <b>세부 업무(Task)</b>를 선택하시면, 국가직무능력표준(NCS) KSA 역량과 실제 8,645개 교육과정의 커리큘럼을 분석하여 최적의 교육을 추천해 드립니다.
          </p>
        </div>
        <div style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); padding: 0.6rem 1.1rem; border-radius: 12px; text-align: right;">
          <div style="font-size: 0.75rem; color: #94A3B8; font-weight: 500;">공식 연계 코퍼스</div>
          <div style="font-size: 1.15rem; font-weight: 800; color: #38BDF8;">8,645건 실무 교육</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    recommender = get_mvp_recommender()

    # --------------------------------------------------------------------------
    # 단계별 인터랙티브 선택 영역 (컨테이너 카드)
    # --------------------------------------------------------------------------
    st.markdown("#### 🎯 맞춤 학습자 프로필 및 과업 설정")
    st.caption("복잡한 설문 없이 몇 번의 선택만으로 필요한 직무 교육을 정밀하게 탐색합니다.")

    c_step1, c_step2 = st.columns([1, 1.5])

    # 1. 직무 선택
    with c_step1:
        st.markdown("**1️⃣ 담당 직무 선택**")
        job_options = ["인사", "총무", "경영지원"]
        selected_job = st.radio(
            "담당하시는 직무군을 선택하세요:",
            job_options,
            horizontal=True,
            label_visibility="collapsed"
        )

    # 2. 직무별 세부 과업(Task) 선택
    available_tasks = get_tasks_for_job(selected_job)
    task_names = [t["task_name"] for t in available_tasks]

    with c_step2:
        st.markdown("**2️⃣ 담당 세부 업무 (Task) 선택**")
        selected_task_name = st.selectbox(
            "현재 수행 중이거나 역량 개발이 필요한 세부 과업을 선택하세요:",
            task_names,
            index=0
        )

    # 선택된 Task 객체 가져오기
    current_task = next((t for t in available_tasks if t["task_name"] == selected_task_name), available_tasks[0])

    # --------------------------------------------------------------------------
    # 3. KSA 역량 확인 카드 (NCS 공식 명세 표시)
    # --------------------------------------------------------------------------
    ksa_info = current_task["ksa_summary"]
    ncs_badge = f"NCS 공식 능력단위: {current_task['ncs_unit_code']}" if current_task["is_official_ncs"] else "프로젝트 자체 표준화"

    st.markdown(f"""
    <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; border-radius: 12px; padding: 1.1rem 1.35rem; margin: 1.1rem 0;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem; flex-wrap: wrap; gap: 0.5rem;">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <span style="font-size: 1.1rem;">🧠</span>
          <span style="font-size: 0.95rem; font-weight: 700; color: #1E293B;">
            선택 과업 요구 KSA 역량: <span style="color: #4F46E5;">{current_task['competency_name']}</span>
          </span>
        </div>
        <span style="background: #EEF2FF; color: #4F46E5; border: 1px solid #C7D2FE; font-size: 0.76rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 6px;">
          🏷️ {ncs_badge}
        </span>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; font-size: 0.83rem;">
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.65rem 0.85rem;">
          <span style="color: #2563EB; font-weight: 700;">📘 필요 지식 (Knowledge):</span><br>
          <span style="color: #475569;">{ksa_info['knowledge']}</span>
        </div>
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.65rem 0.85rem;">
          <span style="color: #059669; font-weight: 700;">⚙️ 필수 기술 (Skill):</span><br>
          <span style="color: #475569;">{ksa_info['skill']}</span>
        </div>
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 0.65rem 0.85rem;">
          <span style="color: #D97706; font-weight: 700;">🤝 권장 태도 (Attitude):</span><br>
          <span style="color: #475569;">{ksa_info['attitude']}</span>
        </div>
      </div>
      <div style="margin-top: 0.65rem; font-size: 0.75rem; color: #64748B;">
        ※ 직무 및 역량 정의는 산업인력공단 NCS 표준 분류를 바탕으로 구성되었으며, 세부 Task 목록은 실무 채용 시장 분석을 바탕으로 체계화한 검토 초안입니다.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 4 & 5. 숙련도 및 개인 학습 조건 필터
    # --------------------------------------------------------------------------
    st.markdown("**3️⃣ 학습자 숙련도 및 개인 교육 조건 설정**")

    c_f1, c_f2, c_f3, c_f4, c_f5 = st.columns([1.2, 1, 1, 1, 0.8])

    with c_f1:
        level_options = ["입문·초급 (신입/초급자)", "실무·중급 (실무자/3~5년차)", "관리자·심화 (팀장/심화과정)", "전체 (수준 무관)"]
        selected_level = st.selectbox(
            "업무 숙련도 / 직급:",
            level_options,
            index=0 if "입문" in current_task["recommended_level"] else (1 if "실무" in current_task["recommended_level"] else 2)
        )

    with c_f2:
        budget_options = ["전체 (무관)", "무료 교육만", "10만원 이하", "30만원 이하", "50만원 이하"]
        selected_budget = st.selectbox("예산 한도:", budget_options, index=0)

    with c_f3:
        duration_options = ["전체 (무관)", "단기 (<10시간)", "중기 (10~40시간)", "장기 (>40시간)"]
        selected_duration = st.selectbox("교육 시간:", duration_options, index=0)

    with c_f4:
        type_options = ["전체 (온/오프라인)", "온라인 (VOD/원격)", "오프라인 (집체/현장)"]
        selected_type = st.selectbox("교육 형태:", type_options, index=0)

    with c_f5:
        top_k_options = [3, 5, 10]
        selected_top_k = st.selectbox("추천 건수:", top_k_options, index=0)

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 6. 추천 엔진 실행 (UnifiedHybridRecommender 공통 엔진 재사용)
    # --------------------------------------------------------------------------
    # 필터 인자 변환
    diff_arg = None
    if "입문" in selected_level:
        diff_arg = "INTRO"
    elif "실무" in selected_level:
        diff_arg = "PRACTICE"
    elif "관리자" in selected_level:
        diff_arg = "ADVANCED"

    price_arg = "ALL"
    budget_arg = None
    if selected_budget == "무료 교육만":
        price_arg = "FREE_ONLY"
    elif selected_budget != "전체 (무관)":
        price_arg = "MAX_BUDGET"
        budget_arg = int(selected_budget.replace("만원 이하", "0000").replace(" ", ""))

    dur_arg = None
    if selected_duration != "전체 (무관)":
        dur_arg = selected_duration

    type_arg = "ALL"
    if "온라인" in selected_type:
        type_arg = "ONLINE"
    elif "오프라인" in selected_type:
        type_arg = "OFFLINE"

    # 합성 리뷰는 절대 반영하지 않고 순수 실무 커리큘럼 추천 실행
    with st.spinner("8,645건 코퍼스에서 최적의 맞춤 교육과정을 탐색하고 있습니다..."):
        rec_df, total_cand, filtered_cand, dedup_cnt, search_summary = recommender.recommend(
            query=current_task["search_query"],
            target_domain=selected_job,
            competency_id=current_task["competency_id"],
            user_level=selected_level,
            price_filter=price_arg,
            max_budget=budget_arg,
            edu_type=type_arg,
            durations=dur_arg,
            difficulties=diff_arg,
            cluster_boost=0.0,             # 군집 보너스 기본 OFF
            filter_mismatch_109=True,       # 109건 오매핑 방어 ON
            top_n=selected_top_k,
            mode="ksa"
        )

    # --------------------------------------------------------------------------
    # 7. 추천 결과 렌더링
    # --------------------------------------------------------------------------
    st.markdown(f"### 🏆 맞춤 교육 추천 Top {selected_top_k}")
    st.caption(f"선택하신 과업 **[{current_task['task_name']}]** 및 학습 조건에 최적화된 교육 목록입니다.")

    if rec_df.empty:
        # 조건 불일치 시 친절한 안내 및 자동 완화 가이드
        st.warning("⚠️ **선택하신 조건에 일치하는 교육과정이 없습니다.**")
        st.info("""
        **💡 검색 조건 완화 팁:**
        - **예산 조건**: '무료 교육만'에서 '전체' 또는 '10~30만원 이하'로 범위를 넓혀보세요.
        - **교육 시간/형태**: '온라인' 또는 '오프라인' 구분을 '전체'로 변경하시면 더 많은 우수 강좌가 검색됩니다.
        - **숙련도**: '전체 (수준 무관)'으로 설정하시면 기초부터 심화까지 다양한 강좌를 확인할 수 있습니다.
        """)
        return

    # 추천 강좌 카드 렌더링
    recommended_courses = rec_df.to_dict("records")
    
    for idx, r in enumerate(recommended_courses):
        rank_num = idx + 1
        price_badge = "무료" if r['price_display'] == "무료" else f"수강료: {r['price_display']}"
        price_color = "#059669" if r['price_display'] == "무료" else "#1E293B"

        st.markdown(f"""
        <div style="background: white; border: 1.5px solid #E2E8F0; border-radius: 14px; padding: 1.3rem 1.6rem; margin-bottom: 1.1rem; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
              <span style="background: linear-gradient(135deg, #6366F1 0%, #3B82F6 100%); color: white; font-weight: 800; font-size: 0.85rem; padding: 0.25rem 0.65rem; border-radius: 8px;">
                #{rank_num} 추천
              </span>
              <span style="background: #F1F5F9; color: #334155; font-size: 0.78rem; font-weight: 600; padding: 0.25rem 0.55rem; border-radius: 6px; border: 1px solid #E2E8F0;">
                {r['provider']}
              </span>
              <span style="background: #FEF3C7; color: #B45309; font-size: 0.78rem; font-weight: 600; padding: 0.25rem 0.55rem; border-radius: 6px;">
                🎯 {current_task['competency_name']}
              </span>
              <span style="background: #ECFDF5; color: #047857; font-size: 0.78rem; font-weight: 600; padding: 0.25rem 0.55rem; border-radius: 6px;">
                난이도: {r['difficulty']}
              </span>
            </div>
            <div style="text-align: right;">
              <span style="font-size: 1.15rem; font-weight: 800; color: {price_color};">{price_badge}</span>
              <span style="font-size: 0.8rem; color: #64748B; margin-left: 0.4rem;">({r['duration_display']})</span>
            </div>
          </div>
          
          <h3 style="font-size: 1.2rem; font-weight: 700; color: #0F172A; margin: 0.3rem 0 0.6rem 0;">
            {r['title']}
          </h3>
          
          <div style="background: #F8FAFC; border-left: 3.5px solid #6366F1; border-radius: 0 8px 8px 0; padding: 0.85rem 1.1rem; margin: 0.75rem 0; font-size: 0.88rem; color: #334155; line-height: 1.55;">
            <b>💡 실제 커리큘럼 기반 추천 이유:</b><br>
            {r['recommendation_reason']}
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.85rem; flex-wrap: wrap; gap: 0.75rem; font-size: 0.8rem; color: #64748B;">
            <div>
              • 교육형태: <b>{r['education_type']}</b> | 
              • 매칭 키워드: <code>{r['matched_keywords']}</code> | 
              • 적합도 점수: <b style="color: #4F46E5;">{r['final_score']}점</b> (의미 유사도 {r['semantic_score']:.1f}점 + 키워드 {r['keyword_score']:.1f}점)
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # 수강신청 및 대체 수강 옵션
        c_btn, c_alt = st.columns([1, 3])
        with c_btn:
            if r['url'] and r['url'] != "#":
                st.link_button(f"🌐 수강신청 바로가기 (#{rank_num})", r['url'], use_container_width=True)
            else:
                st.button(f"수강신청 링크 미제공 (#{rank_num})", disabled=True, use_container_width=True)

        with c_alt:
            alts = r.get("alternative_offerings", [])
            if alts and len(alts) > 0:
                with st.expander(f"🔗 동일 강좌 다른 플랫폼 수강 옵션 ({len(alts)}건)"):
                    for alt in alts:
                        fit_text = "✅ [조건 충족]" if alt.get("is_suitable_alternative", True) else f"⚠️ {alt.get('unsuitability_reason', '')}"
                        st.markdown(
                            f"- **[{alt['provider']}]** {alt['title']} — 수강료: `{alt['price_display']}` | 형태: `{alt['education_type']}` {fit_text} "
                            f"[수강 링크 ↗]({alt['url']})"
                        )

    # --------------------------------------------------------------------------
    # 8. 추천 교육과정 나란히 비교(Side-by-side Comparison)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### ⚖️ 추천 교육과정 한눈에 비교하기")
    st.caption("추천된 상위 강좌들의 주요 사양(수강료, 시간, 교육기관, 난이도)을 비교하여 최적의 과정을 결정하세요.")

    comp_rows = []
    for idx, r in enumerate(recommended_courses):
        comp_rows.append({
            "순위": f"#{idx+1}",
            "교육과정명": r["title"][:28] + ("..." if len(r["title"]) > 28 else ""),
            "교육기관": r["provider"],
            "수강료": r["price_display"],
            "교육시간": r["duration_display"],
            "형태": r["education_type"],
            "난이도": r["difficulty"],
            "추천점수": f"{r['final_score']}점"
        })

    df_comp = pd.DataFrame(comp_rows)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)

    # 면책 및 안내 문구
    st.markdown("""
    <div style="font-size: 0.78rem; color: #94A3B8; text-align: center; margin-top: 1.5rem; line-height: 1.5;">
      ※ 본 시스템의 추천 점수는 실제 수집된 교육과정의 커리큘럼 텍스트, 학습 목표 및 NCS 직무 역량 간의 자연어 의미 유사도(Ko-SRoBERTa)와 BM25 키워드 적합도를 기반으로 산출되었습니다.<br>
      ※ 점수가 높다는 이유만으로 국가 공인 NCS 역량 인증을 보장하는 것은 아니며, 교육기관의 사정에 따라 수강료와 개설 일정이 변동될 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(
        page_title="NCS·KSA 직무 맞춤형 교육 추천 MVP",
        page_icon="🎓",
        layout="wide"
    )
    render_user_recommendation_mvp()
