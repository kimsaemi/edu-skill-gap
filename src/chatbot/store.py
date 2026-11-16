"""
src/chatbot/store.py
사전 제작 추천 설명(rec_explanations_90.json) 조회 저장소
"""
import os
import re
import json
from typing import Dict, Any, Optional

DEFAULT_EXPLANATIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "hr", "output", "chatbot", "rec_explanations_90.json"
)


class ExplanationStore:
    def __init__(self, json_path: Optional[str] = None):
        self.path = json_path or DEFAULT_EXPLANATIONS_PATH
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _normalize_key(self, task_id: str, course_uid: str) -> str:
        t = task_id.strip()
        # DOM_01_T01 -> TASK_HR_D01_T01 변환
        m = re.match(r"^DOM_(\d+)_T(\d+)$", t)
        if m:
            t = f"TASK_HR_D{m.group(1)}_T{m.group(2)}"
        return f"{t}|{course_uid.strip()}"

    def _load(self):
        if not os.path.exists(self.path):
            self._data = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def get_raw_explanation(self, task_id: str, course_uid: str) -> Optional[Dict[str, Any]]:
        """원시 설명 데이터 반환 (status가 skip인 항목 포함)"""
        # 1. 정규화 키 시도
        key = self._normalize_key(task_id, course_uid)
        if key in self._data:
            return self._data[key]
        # 2. 전달된 원본 키 시도
        raw_key = f"{task_id.strip()}|{course_uid.strip()}"
        if raw_key in self._data:
            return self._data[raw_key]
        return None

    def get_explanation(self, task_id: str, course_uid: str) -> Optional[Dict[str, Any]]:
        """유효한 설명 데이터 반환 (status가 'skip'이 아니며 유효한 text가 있는 경우만)"""
        raw = self.get_raw_explanation(task_id, course_uid)
        if not raw:
            return None
        status = raw.get("status", "")
        text = raw.get("text", "").strip()
        if status in ("claude_draft", "ai_draft", "reviewed") and text:
            return raw
        return None

    def has_valid_explanation(self, task_id: str, course_uid: str) -> bool:
        return self.get_explanation(task_id, course_uid) is not None

    def __len__(self) -> int:
        return len(self._data)


_DEFAULT_STORE: Optional[ExplanationStore] = None


def get_default_store() -> ExplanationStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = ExplanationStore()
    return _DEFAULT_STORE
