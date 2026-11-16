# -*- coding: utf-8 -*-
"""
지어낸 과정(환각) 방지 및 검증 모듈
- 답변에 나온 [번호]가 후보 범위(1~N) 안에 있는지 확인
- 답변에 나온 과정명이 해당 [번호] 후보의 실제 과정명과 일치하는지 확인
- 둘 중 하나라도 틀리면 해당 문장을 제거하고 로그를 남김
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("chatbot.validator")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def normalize_title(title: str) -> str:
    """비교를 위한 공백 및 특수기호 정규화"""
    if not title:
        return ""
    # 공백 및 특수문자 제거
    return re.sub(r"[\s\(\)\[\]\_\-\,\.\/\·\:]+", "", title).lower()


def validate_and_filter_response(
    response_text: str,
    candidates: List[Dict[str, Any]]
) -> Tuple[str, bool, List[str]]:
    """
    AI 모델 응답 텍스트를 검증하고, 유효하지 않은 추천 문장을 제거합니다.

    Args:
        response_text: AI 모델의 생성 텍스트
        candidates: 후보 과정 목록 (각 dict는 'title' 또는 'course_name' 포함, 1-indexed)

    Returns:
        (filtered_text, has_hallucination, removed_sentences)
    """
    if not response_text:
        return "", False, []

    if not candidates:
        # 후보가 없는 경우 번호 참조가 있으면 환각으로 판정
        has_num = bool(re.search(r"\[\d+\]", response_text))
        return response_text, has_num, []

    max_idx = len(candidates)
    # 후보 정규화 제목 목록 (0-indexed -> 번호-1)
    cand_titles = []
    for c in candidates:
        t = c.get("title") or c.get("course_name") or ""
        cand_titles.append(str(t).strip())

    cleaned_lines = []
    removed_sentences = []
    has_hallucination = False

    lines = response_text.splitlines()

    for line in lines:
        stripped = line.strip()
        num_matches = re.findall(r"\[(\d+)\]", stripped)

        if not num_matches:
            # [번호]가 없는 일반 설명(요약, 안내, 인사 무관 안내 등)은 보존
            cleaned_lines.append(line)
            continue

        # [번호]가 포함된 추천 문장 검증
        line_is_valid = True
        for num_str in num_matches:
            idx = int(num_str)
            # 1. 번호 범위 확인 (1 <= idx <= max_idx)
            if idx < 1 or idx > max_idx:
                logger.warning(
                    f"환각 감지(범위 초과 번호): [번호] [{idx}]는 후보 범위(1~{max_idx}) 밖입니다. 문장: '{stripped}'"
                )
                line_is_valid = False
                break

            # 2. 과정명 일치 확인
            target_title = cand_titles[idx - 1]
            norm_target = normalize_title(target_title)
            norm_line = normalize_title(stripped)

            # 대상 과정명의 핵심 어절(최소 2글자 이상) 또는 정규화 제목이 문장에 포함되어 있는지 검사
            # 또한 정규화 제목이 4글자 이상이면 부분 매칭 확인
            if len(norm_target) >= 4:
                # 4글자 이상의 제목이면 접두어나 공통 문자열 존재 여부 확인
                target_words = [w for w in re.split(r"[\s\(\)\[\]\_\-\,\.\/\·\:]+", target_title) if len(w) >= 2]
                matched_words = [w for w in target_words if normalize_title(w) in norm_line]
                # 주요 키워드의 절반 이상 또는 전체 제목이 일치해야 함
                ratio = len(matched_words) / len(target_words) if target_words else 0
                title_in_line = (norm_target in norm_line) or (ratio >= 0.5)
            else:
                title_in_line = norm_target in norm_line

            if not title_in_line:
                logger.warning(
                    f"환각 감지(과정명 불일치): [번호] [{idx}]의 실제 과정명('{target_title}')이 문장에 없습니다. 문장: '{stripped}'"
                )
                line_is_valid = False
                break

        if line_is_valid:
            cleaned_lines.append(line)
        else:
            has_hallucination = True
            removed_sentences.append(stripped)

    filtered_text = "\n".join(cleaned_lines).strip()
    return filtered_text, has_hallucination, removed_sentences
