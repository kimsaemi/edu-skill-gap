"""
src/chatbot package
"""
from src.chatbot.explain import generate_rule_based_explanation
from src.chatbot.store import ExplanationStore, get_default_store
from src.chatbot.matcher import match_and_recommend, TASK_SIMILARITY_THRESHOLD
from src.chatbot.guard import validate_user_query, validate_llm_response
from src.chatbot.llm_optional import is_llm_available, generate_llm_explanation

__all__ = [
    "generate_rule_based_explanation",
    "ExplanationStore",
    "get_default_store",
    "match_and_recommend",
    "TASK_SIMILARITY_THRESHOLD",
    "validate_user_query",
    "validate_llm_response",
    "is_llm_available",
    "generate_llm_explanation"
]
