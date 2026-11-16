"""
src/chatbot/guard.py
입력 검증 및 출력 가드레일 모듈
- 입력 안전성 검증 (빈 문자열, 부적절한 질의 차단)
- 출력 일치성 검증 (실시간 LLM 설명 시 실제 추천 과정 3개와의 일치 검증)
"""
from typing import List, Dict, Any, Optional, Tuple

INAPPROPRIATE_KEYWORDS = [
    "시스템 프롬프트", "system prompt", "jailbreak", "탈옥", "비밀번호",
    "api key", "인증키"
]


def validate_user_query(query: str) -> Tuple[bool, str]:
    q = (query or "").strip()
    if not q:
        return False, "질문 내용을 입력해 주세요."
    if len(q) > 300:
        return False, "질문이 너무 깁니다. 300자 이내로 입력해 주세요."
    ql = q.lower()
    for kw in INAPPROPRIATE_KEYWORDS:
        if kw in ql:
            return False, "HR 직무 및 교육과 관련된 질문만 입력해 주세요."
    return True, ""


def validate_llm_response(
    llm_text: str,
    recommended_cards: List[Dict[str, Any]]
) -> bool:
    """
    실시간 LLM 응답이 실제 추천된 3개 과정의 맥락을 벗어나거나
    엉뚱한 과정을 지어내지 않았는지 검증합니다.
    - 3개 과정 중 최소 1개 이상의 핵심 키워드나 기관명이 언급되었는지 확인
    - 금지어 ("만족도", "취업 보장", "가격" 등) 검사
    """
    if not llm_text or not recommended_cards:
        return False

    # 금지어 검사
    forbidden = ["만족도", "취업 보장", "자격 취득 보장", "최고", "반드시"]
    for fb in forbidden:
        if fb in llm_text:
            return False

    # 추천 과정 관련성 검사 (과정명 명사 또는 제공기관명 포함 여부)
    valid_mentions = 0
    for card in recommended_cards:
        title = card.get("title", "")
        provider = card.get("provider", "") or card.get("institution", "")
        if provider and provider in llm_text:
            valid_mentions += 1
            continue
        # 제목의 의미 있는 단어 확인
        title_words = [w for w in title.split() if len(w) >= 2 and not w.startswith("[")]
        for tw in title_words:
            if tw in llm_text:
                valid_mentions += 1
                break

    return valid_mentions > 0
