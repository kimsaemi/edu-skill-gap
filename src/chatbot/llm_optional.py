"""
src/chatbot/llm_optional.py
선택적 실시간 Claude LLM 설명 생성기
- 기본 모델: DEFAULT_MODEL = "claude-haiku-5-5"
- st.secrets 또는 CHAT_LLM_MODEL 환경변수로 재지정 가능 (기본 상태는 꺼짐)
- anthropic 패키지가 없어도 에러 없이 안전하게 폴백 (lazy import)
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from src.chatbot.guard import validate_llm_response

DEFAULT_MODEL = "claude-haiku-5-5"


def get_configured_model() -> str:
    """설정된 LLM 모델명 반환 (기본값: claude-haiku-5-5)"""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "CHAT_LLM_MODEL" in st.secrets:
            return st.secrets["CHAT_LLM_MODEL"]
    except Exception:
        pass
    return os.environ.get("CHAT_LLM_MODEL", DEFAULT_MODEL)


def is_llm_available() -> Tuple[bool, str]:
    """실시간 LLM 설명 기능 사용 가능 여부 확인"""
    enabled = os.environ.get("CHAT_LLM_ENABLED", "").lower() in ("true", "1", "yes")
    if not enabled:
        return False, "설정에서 비활성화됨"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return False, "ANTHROPIC_API_KEY 미설정"

    try:
        import anthropic  # noqa: F401
        return True, "사용 가능"
    except ImportError:
        return False, "anthropic 라이브러리 미설치"


def generate_llm_explanation(
    query: str,
    cards: List[Dict[str, Any]]
) -> Optional[str]:
    """
    추천된 3개 과정에 대해 설정된 모델(기본: claude-haiku-5-5)을 호출하여
    1~2문장의 종합 추천 이유를 생성합니다.
    검증 가드를 통과하지 못하면 None을 반환하여 기존 설명으로 안전하게 대체됩니다.
    """
    avail, _ = is_llm_available()
    if not avail or not cards:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic()
        model_name = get_configured_model()

        course_snippets = []
        for i, c in enumerate(cards[:3], 1):
            title = c.get("title", "")
            prov = c.get("provider", "") or c.get("institution", "")
            intro = c.get("intro_summary", "")[:100]
            course_snippets.append(f"{i}. [{prov}] {title} - {intro}")

        course_text = "\n".join(course_snippets)
        prompt = (
            f"당신은 HR 교육 컨설턴트입니다. 아래 3개 과정만 가지고 추천 이유를 1~2문장으로 설명하세요.\n"
            f"새 과정을 지어내지 마세요. 친절한 존댓말(~해요 체)로 작성하세요.\n\n"
            f"사용자 질문: {query}\n\n"
            f"추천된 과정:\n{course_text}\n\n"
            f"설명:"
        )

        response = client.messages.create(
            model=model_name,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        output_text = response.content[0].text.strip()
        if validate_llm_response(output_text, cards):
            return output_text
        return None
    except Exception:
        return None
