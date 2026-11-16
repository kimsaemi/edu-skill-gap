"""
src/chatbot/explain.py
규칙 기반 추천 설명 생성기
- AI 상담 탭의 모든 추천 이유를 만든다 (실시간 AI 호출 없음)
- Kiwi 형태소 분석기를 사용하여 질문/KSA와 과정 소개글의 겹치는 명사를 추출하고 정형 템플릿 문장을 구성합니다.
"""
from typing import Optional, List
from src.recommendation.text_preprocessor import HRTextPreprocessor

_PREPROCESSOR: Optional[HRTextPreprocessor] = None
TASK_DEFAULT_MSG = "이 업무의 기본 추천 과정이에요. 과정 소개를 확인해 주세요."


def get_preprocessor() -> HRTextPreprocessor:
    global _PREPROCESSOR
    if _PREPROCESSOR is None:
        _PREPROCESSOR = HRTextPreprocessor()
    return _PREPROCESSOR


def _josa_wa(word: str) -> str:
    """받침 있으면 '과', 없으면 '와' (한글이 아니면 '와')"""
    ch = word[-1] if word else ""
    if "가" <= ch <= "힣":
        return "과" if (ord(ch) - 0xAC00) % 28 else "와"
    return "와"


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
      * 업무 연계: f"과정 소개에 '{k1}'·'{k2}' 내용이 있어 이 업무와 연결돼요."
        (겹치는 단어 = 과정 소개 ∩ (질문 + 업무명 + 업무 지식))
      * 질문 연계: f"질문하신 {k1}·{k2}와(과) 관련된 내용을 다루는 과정이에요."
    - 겹치는 명사 0개:
      * "질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요."
    """
    default_msg = "질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요."
    intro_summary = (intro_summary or "").strip()
    if not intro_summary:
        return TASK_DEFAULT_MSG if task_name else default_msg

    prep = get_preprocessor()
    intro_tokens = set(prep.tokenize(intro_summary))

    # 대상 텍스트 토큰 추출
    source_text = query
    if task_name:
        source_text = f"{query} {task_name} {ksa_text or ''}"
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
        return TASK_DEFAULT_MSG if task_name else default_msg

    keywords = filtered_overlap[:2]
    k_str = "·".join(keywords)

    if task_name:
        # 업무가 정해진 경우: 과정 소개에 실제로 나오는 단어만 보여 준다 (업무명은 대화 메시지에 이미 나온다)
        quoted = "·".join(f"'{k}'" for k in keywords)
        return f"과정 소개에 {quoted} 내용이 있어 이 업무와 연결돼요."
    sentence = f"질문하신 {k_str}{_josa_wa(keywords[-1])} 관련된 내용을 다루는 과정이에요."
    if len(sentence) > 80:
        sentence = f"질문하신 {keywords[0]}{_josa_wa(keywords[0])} 관련된 내용을 다뤄요."
    return sentence
