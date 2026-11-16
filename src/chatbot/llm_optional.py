"""
src/chatbot/llm_optional.py
선택적 실시간 Claude LLM 설명 생성기
- 기본 상태: 비활성화 (기본 추천은 실시간 API 호출 0건, 비용 0원)
- 활성화 조건: CHAT_LLM_ENABLED=true 및 ANTHROPIC_API_KEY 환경변수 설정 시
- anthropic 패키지가 없어도 ImportError 없이 안전하게 폴백 (lazy import)
"""
import os
from typing import List, Dict, Any, Optional, Tuple
from src.chatbot.guard import validate_llm_response


def is_llm_available() -> Tuple[bool, str]:
    """실시간 LLM 설명 기능 사용 가능 여부 확인"""
    enabled = os.environ.get("CHAT_LLM_ENABLED", "").lower() in ("true", "1", "yes")
    if not enabled:
        return False, "설정에서 비활성화됨"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return False, "ANTHROPIC_API_KEY 미설정"

    try:
        import anthropic
        return True, "사용 가능"
    except ImportError:
        return False, "anthropic 라이브러리 미설치"


def generate_llm_explanation(
    query: str,
    cards: List[Dict[str, Any]]
) -> Optional[str]:
    """
    추천된 3개 과정에 대해 Claude 3.5 Haiku를 사용하여 1~2문장의 종합 추천 이유를 생성합니다.
    검증 가드를 통과하지 못하면 None을 반환하여 기존 ①·② 설명으로 대체됩니다.
    """
    avail, _ = is_llm_available()
    if not avail or not cards:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic()

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
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        output_text = response.content[0].text.strip()
        if validate_llm_response(output_text, cards):
            return output_text
        return None
    except Exception:
        return None
