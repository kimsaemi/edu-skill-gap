# -*- coding: utf-8 -*-
"""
인사 담당자용 "교육과정 추천 RAG 챗봇" 프로토타입 (Streamlit)
파일명: chatbot_app.py

실행 방법:
  streamlit run chatbot_app.py
  (환경변수 ANTHROPIC_API_KEY 설정 시 AI 설명 활성화, 미설정 시 검색 결과 표 모드로 자동 동작)
"""

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# 프로젝트 루트 경로 추가
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.chatbot.generator import ChatbotGenerator, DEFAULT_MODEL
from src.chatbot.retriever import ChatbotRetriever, TASK_SIMILARITY_THRESHOLD

st.set_page_config(
    page_title="인사 교육과정 추천 RAG 챗봇",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# 공용 리소스 캐싱 (최초 1회만 모델 및 데이터 로드)
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="추천 엔진 및 강좌 코퍼스를 불러오는 중입니다...")
def load_retriever() -> ChatbotRetriever:
    return ChatbotRetriever()


@st.cache_resource
def load_generator() -> ChatbotGenerator:
    return ChatbotGenerator()


retriever = load_retriever()
generator = load_generator()

# -----------------------------------------------------------------------------
# 사이드바
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("💬 HR 추천 챗봇")
    st.caption("인사 실무 과업 기반 2단계 RAG 검색 & 추천")
    st.markdown("---")

    # API 연동 상태 표시
    if generator.is_available:
        st.success(f"🟢 **AI 설명 모드 활성화**\n\n모델: `{generator.model_id}`")
    else:
        st.warning(
            "🟡 **검색 결과 표 전용 모드**\n\n"
            "`ANTHROPIC_API_KEY` 환경변수가 설정되지 않아, AI 설명 없이 **2단계 하이브리드 검색 표**만 제공합니다."
        )

    st.markdown("---")
    st.subheader("⚙️ 검색 옵션")
    selected_level = st.selectbox(
        "추천 난이도 기준",
        options=["실무", "입문", "관리자·심화"],
        index=0,
        help="사용자 직급 및 숙련도에 맞춰 난이도 보너스(10점)를 적용합니다."
    )

    st.markdown("---")
    st.subheader("💡 추천 예시 질문")
    examples = [
        "4대보험 신고를 처음 맡았어요",
        "급여 정산 엑셀 실무 교육을 찾고 있어요",
        "신입사원 온보딩 프로그램을 기획해야 합니다",
        "표준 직무기술서(JD) 작성 방법",
        "파이썬 웹 크롤링 자동화"
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["user_input_from_btn"] = ex

    if st.button("🔄 대화 초기화", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

# -----------------------------------------------------------------------------
# 메인 화면 구성
# -----------------------------------------------------------------------------
st.subheader("인사 담당자를 위한 맞춤형 교육과정 추천 RAG 챗봇")
st.write(
    "자연어로 업무 고민이나 배우고 싶은 직무 내용을 질문해 보세요. "
    "90개 표준 인사 업무와 7,698개 검증 후보 강좌를 기반으로 가장 적합한 교육을 추천합니다."
)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 기존 대화 렌더링
for msg in st.session_state["messages"]:
    role = msg.get("role", "user")
    with st.chat_message(role):
        if msg.get("content"):
            st.markdown(msg["content"])

        # 근거 과정 표 렌더링
        cands = msg.get("candidates")
        if cands:
            st.markdown("##### 📚 근거 과정 목록 (Top Candidates)")
            table_rows = []
            for c in cands:
                url = c.get("url", "#")
                link_md = f"[{c['title']}]({url})" if url and url != "#" else c["title"]
                table_rows.append({
                    "번호": f"[{c['index']}]",
                    "과정명 (상세 링크)": link_md,
                    "교육기관": c["provider"],
                    "난이도": c.get("difficulty", "미표시"),
                    "점수": f"{c.get('score', 0.0):.1f}점"
                })
            df_table = pd.DataFrame(table_rows)
            st.markdown(df_table.to_markdown(index=False), unsafe_allow_html=True)

            meta_info = msg.get("meta_info")
            if meta_info:
                st.caption(meta_info)

# 버튼 클릭 등으로 전달된 입력 처리
pending_input = st.session_state.pop("user_input_from_btn", None)
chat_input = st.chat_input("업무 고민이나 교육 질문을 입력하세요 (예: '4대보험 신고를 처음 맡았어요')")
user_query = pending_input or chat_input

if user_query:
    # 1. 사용자 메시지 등록 및 표시
    st.session_state["messages"].append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # 2. 어시스턴트 응답 처리
    with st.chat_message("assistant"):
        with st.spinner("관련 인사 업무 및 교육과정을 검색하는 중입니다..."):
            matched_task, candidates, retrieval_mode = retriever.retrieve_candidates(
                query=user_query,
                top_k=5,
                user_level=selected_level
            )

        linked_task_str = retriever.format_linked_task_for_prompt(matched_task)
        candidates_str = retriever.format_candidates_for_prompt(candidates)

        assistant_content = ""
        meta_note = ""

        # AI 모델 호출 또는 검색 결과 표 전용 모드
        if not generator.is_available:
            assistant_content = (
                "ℹ️ **[검색 전용 모드]** `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 "
                "AI 요약 설명 대신 **2단계 하이브리드 검색으로 도출된 근거 과정 표**를 안내해 드립니다."
            )
            st.info(assistant_content)
        else:
            with st.spinner("AI 모델이 추천 이유를 정리하고 있습니다..."):
                ai_text, status, has_hallucination, removed = generator.generate(
                    user_query=user_query,
                    linked_task_str=linked_task_str,
                    candidates_str=candidates_str,
                    candidates=candidates
                )

            if status == "SUCCESS" and ai_text:
                assistant_content = ai_text
                st.markdown(assistant_content)
                if has_hallucination:
                    meta_note = f"⚠️ 검증되지 않은 {len(removed)}개 문장이 환각 방지 규칙에 의해 정제되었습니다."
                    st.caption(meta_note)
            elif status == "FALLBACK_TABLE_ONLY":
                assistant_content = "⚠️ AI 응답에 검증되지 않은 과정이 포함되어 정제되었으며, 아래 '근거 과정' 표를 안내합니다."
                st.warning(assistant_content)
            else:
                assistant_content = "⚠️ AI 설명 생성 중 오류가 발생하여 근거 과정 표만 안내합니다."
                st.warning(assistant_content)

        # 근거 과정 표 표시
        if candidates:
            st.markdown("##### 📚 근거 과정 목록 (Top Candidates)")
            table_rows = []
            for c in candidates:
                url = c.get("url", "#")
                link_md = f"[{c['title']}]({url})" if url and url != "#" else c["title"]
                table_rows.append({
                    "번호": f"[{c['index']}]",
                    "과정명 (상세 링크)": link_md,
                    "교육기관": c["provider"],
                    "난이도": c.get("difficulty", "미표시"),
                    "점수": f"{c.get('score', 0.0):.1f}점"
                })
            df_table = pd.DataFrame(table_rows)
            st.markdown(df_table.to_markdown(index=False), unsafe_allow_html=True)

            mode_caption = f"🔍 검색 모드: `{retrieval_mode}`"
            st.caption(mode_caption)

        # 세션에 저장
        st.session_state["messages"].append({
            "role": "assistant",
            "content": assistant_content,
            "candidates": candidates,
            "meta_info": f"🔍 검색 모드: `{retrieval_mode}`"
        })
