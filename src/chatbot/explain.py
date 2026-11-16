"""
src/chatbot/explain.py
규칙 기반 추천 설명 생성기
- 미리 만든 설명이 없거나 status가 skip일 때, 또는 90개 업무와 무관한 질문일 때 동작
- Kiwi 형태소 분석기를 사용하여 질문/KSA와 과정 소개글의 겹치는 명사를 추출하고 정형 템플릿 문장을 구성합니다.
"""
from typing import Optional, List
from src.recommendation.text_preprocessor import HRTextPreprocessor

_PREPROCESSOR: Optional[HRTextPreprocessor] = None


def get_preprocessor() -> HRTextPreprocessor:
    global _PREPROCESSOR
    if _PREPROCESSOR is None:
        _PREPROCESSOR = HRTextPreprocessor()
    return _PREPROCESSOR


def generate_rule_based_explanation(
    query: str,
    intro_summary: str = "",
    task_name: Optional[str] = None,
    ksa_text: Optional[str] = None
) -> str:
    """
    질문, 강좌 소개글 요약, (선택) 업무명 및 KSA를 바탕으로 1문장의 규칙 기반 설명을 생성합니다.
    - 길이: 1문장, 80자 이내
    - 겹치는 명사 1개 이상:
      * 업무 연계: f"'{task_name}' 업무의 '{ksa_repr}'과 관련된 {k1}·{k2} 내용을 다뤄요."
      * 질문 연계: f"질문하신 {k1}·{k2}와 관련된 내용을 다루는 과정이에요."
    - 겹치는 명사 0개:
      * "질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요."
    """
    default_msg = "질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요."
    intro_summary = (intro_summary or "").strip()
    if not intro_summary:
        return default_msg

    prep = get_preprocessor()
    intro_tokens = set(prep.tokenize(intro_summary))

    # 대상 텍스트 토큰 추출
    source_text = query
    if task_name and ksa_text:
        source_text = f"{query} {ksa_text}"
    source_tokens = set(prep.tokenize(source_text))

    # 겹치는 명사 추출 (우선순위: 긴 단어 순, 동률 시 질의어 앞부분 등장 순으로 결정론적 정렬)
    overlap = sorted(
        list(intro_tokens & source_tokens),
        key=lambda x: (-len(x), source_text.find(x) if source_text.find(x) != -1 else 999)
    )
    # 불용 명사 필터링
    generic_drop = {"교육", "과정", "내용", "학습", "수강", "이해", "방법"}
    filtered_overlap = [w for w in overlap if w not in generic_drop]
    if not filtered_overlap:
        filtered_overlap = overlap

    if not filtered_overlap:
        return default_msg

    keywords = filtered_overlap[:2]
    k_str = "·".join(keywords)

    if task_name:
        # KSA 대표 표현 추출
        ksa_repr = ""
        if ksa_text:
            first_part = ksa_text.split(",")[0].split("|")[0].strip()
            # 지식: / 기술: / 태도: 접두사 정리
            for prefix in ["지식:", "기술:", "태도:"]:
                if first_part.startswith(prefix):
                    first_part = first_part[len(prefix):].strip()
            ksa_repr = first_part[:15]
        if not ksa_repr:
            ksa_repr = "실무 역량"

        # 80자 초과 방지를 위한 길이 조정
        # f"'{t_name}' 업무의 '{ksa_repr}'과 관련된 {k_str} 내용을 다뤄요."
        # 고정 글자 수: 약 25자
        t_name = task_name
        sentence = f"'{t_name}' 업무의 '{ksa_repr}'과 관련된 {k_str} 내용을 다뤄요."
        if len(sentence) > 80:
            allowed_t_len = max(10, 80 - len(f"'' 업무의 '{ksa_repr}'과 관련된 {k_str} 내용을 다뤄요."))
            t_name = t_name[:allowed_t_len - 1] + "…"
            sentence = f"'{t_name}' 업무의 '{ksa_repr}'과 관련된 {k_str} 내용을 다뤄요."
        if len(sentence) > 80:
            sentence = f"'{t_name}' 업무와 관련된 {k_str} 내용을 다뤄요."
        return sentence
    else:
        sentence = f"질문하신 {k_str}와 관련된 내용을 다루는 과정이에요."
        if len(sentence) > 80:
            sentence = f"질문하신 {keywords[0]}와 관련된 내용을 다뤄요."
        return sentence
