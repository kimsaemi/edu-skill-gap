# -*- coding: utf-8 -*-
"""
AI 응답 생성 및 환각 필터링 모듈 (Generation & LLM Integration)

- 환경변수 ANTHROPIC_API_KEY 에서만 API 키를 읽음 (파일 열람 금지)
- 모델 ID 설정값 (기본: claude-sonnet-5-5)
- API 키가 없으면 None을 반환하여 검색 결과 표 전용 모드로 동작
- 생성된 텍스트에 대해 validate_and_filter_response()를 호출하여 지어낸 과정 차단
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from src.chatbot.prompts import SYSTEM_PROMPT, format_user_prompt
from src.chatbot.validator import validate_and_filter_response

logger = logging.getLogger("chatbot.generator")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 기본 모델 ID
DEFAULT_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")


class ChatbotGenerator:
    """Claude 기반 RAG 응답 생성기"""

    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or DEFAULT_MODEL
        # API 키는 환경변수에서만 로드
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    @property
    def is_available(self) -> bool:
        """API 키가 설정되어 있는지 여부"""
        return bool(self.api_key)

    def generate(
        self,
        user_query: str,
        linked_task_str: str,
        candidates_str: str,
        candidates: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], str, bool, List[str]]:
        """
        AI 모델을 호출하여 추천 이유를 생성하고, 지어낸 과정(환각)을 검증·제거합니다.

        Returns:
            (final_response_text, status, has_hallucination, removed_sentences)
            - status: "SUCCESS" | "NO_API_KEY" | "API_ERROR" | "FALLBACK_TABLE_ONLY"
        """
        if not self.is_available:
            return None, "NO_API_KEY", False, []

        user_content = format_user_prompt(
            linked_task_str=linked_task_str,
            candidate_courses_str=candidates_str,
            user_query=user_query
        )

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            response = client.messages.create(
                model=self.model_id,
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}]
            )

            raw_text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    raw_text += block.text

            # 지어낸 과정(환각) 검증 및 정제
            filtered_text, has_hallucination, removed = validate_and_filter_response(
                response_text=raw_text,
                candidates=candidates
            )

            # 환각으로 인해 본문이 완전히 제거된 경우 표만 보여주기 위한 상태 반환
            if has_hallucination and not filtered_text.strip():
                logger.warning("응답 내 모든 추천 문장이 환각으로 판정되어 '근거 과정' 표만 표시합니다.")
                return None, "FALLBACK_TABLE_ONLY", True, removed

            return filtered_text, "SUCCESS", has_hallucination, removed

        except Exception as e:
            logger.error(f"Anthropic API 호출 중 오류 발생: {e}")
            return None, "API_ERROR", False, []
