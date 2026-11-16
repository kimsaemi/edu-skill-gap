"""
src/chatbot package (고객 대시보드 AI 상담 탭)
"""
from src.chatbot.explain import generate_rule_based_explanation
from src.chatbot.matcher import match_and_recommend, recommend_for_task
from src.chatbot.guard import validate_user_query, validate_llm_response
from src.chatbot.llm_optional import is_llm_available, generate_llm_explanation

__all__ = [
    "generate_rule_based_explanation",
    "match_and_recommend",
    "recommend_for_task",
    "validate_user_query",
    "validate_llm_response",
    "is_llm_available",
    "generate_llm_explanation",
]
