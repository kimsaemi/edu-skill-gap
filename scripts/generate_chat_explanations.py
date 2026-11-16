#!/usr/bin/env python3
"""
scripts/generate_chat_explanations.py
explanation_inputs.jsonl 로부터 678개 유니크 (업무, 강좌) 쌍의 사전 설명 생성
- rec_explanations_90.json 생성
- 규칙:
  * 1~2문장, 120자 이내
  * 친절하고 명확한 존댓말 (~해요 체)
  * 강좌 intro_summary 와 업무 KSA 에 기반한 사실만 반영
  * 강좌명(title) 본문 직접 사용 금지
  * 금지어 ("만족도", "수료 효과", "취업", "자격 취득 보장", "가격", "일정", "최고", "반드시", "수료 후", "원") 배제
  * 원문에 없는 숫자 생성 금지
  * 근거 부족/행정 안내문/일반적 문구일 경우 status="skip"
"""
import os
import sys
import re
import json
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.recommendation.text_preprocessor import HRTextPreprocessor

INPUTS_PATH = "data/hr/output/chatbot/explanation_inputs.jsonl"
OUTPUT_PATH = "data/hr/output/chatbot/rec_explanations_90.json"

FORBIDDEN_WORDS = [
    "만족도", "수료 효과", "수료효과", "취업", "자격 취득 보장", "자격취득보장",
    "가격", "일정", "최고", "반드시", "수료 후", "수료후"
]
CURRENCY_PATTERNS = [
    r"\d+\s*원", r"\d+\s*만원", r"수강료", r"비용", r"할인", r"무료"
]

ADMIN_PATTERNS = [
    r"환급", r"서울본부", r"오프라인", r"교재", r"영업일", r"신청을 해주셔야",
    r"신청해 주시기", r"참석", r"출석", r"차수", r"수강희망", r"인재키움 프리미엄"
]


def clean_bullet_and_punct(text: str) -> str:
    text = re.sub(r"[💡✒️📌ㅇ🎯※\*•\-\|\d+\.\s]+", " ", text)
    text = text.strip("\"'“”‘’「」 ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_haeyo_ending(text: str) -> Optional[str]:
    """한국어 서술어를 자연스러운 ~해요 체로 변환. 부자연스러우면 None 반환"""
    text = text.strip("\"'“”‘’「」 ").rstrip(".!~ ")
    
    # 일반적인 서술어 어미 패턴 변환
    replacements = [
        (r"습득할 수 있습니다$", "습득해요"),
        (r"습득할 수 있다$", "습득해요"),
        (r"배울 수 있습니다$", "배워요"),
        (r"배울 수 있다$", "배워요"),
        (r"확인할 수 있습니다$", "확인해요"),
        (r"확인할 수 있다$", "확인해요"),
        (r"이해할 수 있습니다$", "이해를 도와줘요"),
        (r"이해할 수 있다$", "이해를 도와줘요"),
        (r"수립할 수 있습니다$", "수립하는 실무를 다뤄요"),
        (r"수립할 수 있다$", "수립하는 실무를 다뤄요"),
        (r"활용할 수 있습니다$", "활용법을 익혀요"),
        (r"활용할 수 있다$", "활용법을 익혀요"),
        (r"도출할 수 있다$", "도출하는 역량을 다뤄요"),
        (r"도출할 수 있습니다$", "도출하는 역량을 다뤄요"),
        (r"익힐 수 있습니다$", "익혀요"),
        (r"익힐 수 있다$", "익혀요"),
        (r"실천할 수 있다$", "실천할 수 있도록 도와줘요"),
        (r"수 있습니다$", "수 있어요"),
        (r"수 있다$", "수 있어요"),
        (r"제고$", "높이는 방법을 다뤄요"),
        (r"설계하고 진단한다$", "설계하고 진단해요"),
        (r"구축한다$", "구축해요"),
        (r"실천한다$", "실천해요"),
        (r"실행한다$", "실행해요"),
        (r"배운다$", "배워요"),
        (r"익힌다$", "익혀요"),
        (r"다룬다$", "다뤄요"),
        (r"알아본다$", "알아봐요"),
        (r"살펴본다$", "살펴봐요"),
        (r"한다$", "해요"),
        (r"된다$", "돼요"),
        (r"양성을 위함$", "역량을 기르는 데 집중해요"),
    ]
    for pattern, rep in replacements:
        if re.search(pattern, text):
            return re.sub(pattern, rep, text) + "."

    # 명사형 종결
    if text.endswith("이해"):
        return text + "를 도와줘요."
    if text.endswith("역량강화") or text.endswith("역량 강화"):
        return text + "에 도움이 돼요."
    if text.endswith("실무"):
        return text + "를 중점적으로 다뤄요."
    if text.endswith("방법"):
        return text + "을 학습해요."

    return None


def split_sentences(text: str) -> List[str]:
    # bullet or newline or period split
    cleaned = re.sub(r"[💡✒️📌🎯※\*\#\•]+", "\n", text)
    cleaned = re.sub(r"\d+\.\s+", "\n", cleaned)
    raw_lines = re.split(r"[\n\r]+", cleaned)
    sentences = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        for p in parts:
            p = p.strip()
            if len(p) >= 10:
                sentences.append(p)
    return sentences


def generate_explanation_for_record(rec: Dict[str, Any], prep: HRTextPreprocessor) -> Dict[str, Any]:
    task_name = rec.get("task_name", "")
    intro = rec.get("intro_summary", "")
    ksa = rec.get("ksa_summary", "")
    easy_desc = rec.get("easy_description", "")
    title = rec.get("title", "")

    # Basic validity checks
    if not intro or len(intro.strip()) < 15:
        return {"text": "", "status": "skip", "basis": []}

    # If intro is mostly administrative info
    for ap in ADMIN_PATTERNS:
        if re.search(ap, intro) and len(intro) < 150:
            return {"text": "", "status": "skip", "basis": []}

    # Extract tokens
    intro_tokens = prep.tokenize(intro)
    task_context = f"{task_name} {easy_desc} {ksa}"
    task_tokens = prep.tokenize(task_context)

    overlap = sorted(list(set(intro_tokens) & set(task_tokens)), key=lambda x: -len(x))
    if not overlap:
        return {"text": "", "status": "skip", "basis": []}

    # Filter out generic stopwords from basis
    generic_basis_drop = {"인사", "업무", "관리", "기업", "조직", "역량", "필요", "중심", "핵심"}
    basis = [w for w in overlap if w not in generic_basis_drop][:3]
    if not basis:
        basis = overlap[:2]

    # Find the most relevant sentence from intro
    sentences = split_sentences(intro)
    candidates = []
    for s in sentences:
        s_clean = s.strip()
        # skip sentences with admin notices
        if any(re.search(ap, s_clean) for ap in ADMIN_PATTERNS):
            continue
        # skip generic boilerplate
        if "본 과정을 통해 관련 직무 지식 및 실무 핵심 역량을" in s_clean:
            continue
        # skip if title verbatim in sentence
        if title and len(title) >= 4 and title in s_clean:
            continue
        # count matching basis words
        score = sum(1 for b in basis if b in s_clean)
        if score > 0:
            candidates.append((score, len(s_clean), s_clean))

    candidates.sort(key=lambda x: (-x[0], x[1]))

    explanation_text = ""
    if candidates:
        best_sentence = candidates[0][2]
        # clean punctuation, HTML, images
        best_sentence = re.sub(r"\[이미지\]\s*https?:\S+", "", best_sentence)
        best_sentence = re.sub(r"https?:\S+", "", best_sentence)
        best_sentence = re.sub(r"^[ㅇ\-\*\•\d\.\s]+", "", best_sentence).strip()
        
        # Convert to haeyo ending
        converted = to_haeyo_ending(best_sentence)
        if converted and len(converted) <= 115:
            explanation_text = converted

    # If sentence candidate is not suitable, construct a structured template using basis
    if not explanation_text:
        k_str = "·".join(basis[:2])
        explanation_text = f"'{task_name}' 업무에 필요한 {k_str} 실무 역량을 체계적으로 다뤄요."

    # Final check on constraints
    # 1. Length
    if len(explanation_text) > 120 or len(explanation_text) < 15:
        # shorten if possible
        if len(explanation_text) > 120:
            explanation_text = explanation_text[:115].rsplit(" ", 1)[0] + "를 다뤄요."

    if len(explanation_text) > 120:
        return {"text": "", "status": "skip", "basis": []}

    # 2. Forbidden words
    for fw in FORBIDDEN_WORDS:
        if fw in explanation_text:
            return {"text": "", "status": "skip", "basis": []}
    for cp in CURRENCY_PATTERNS:
        if re.search(cp, explanation_text):
            return {"text": "", "status": "skip", "basis": []}

    # 3. Title directly contained
    if title and len(title) >= 4 and title in explanation_text:
        return {"text": "", "status": "skip", "basis": []}

    # 4. Check digits: if explanation has digits not in source texts, drop them or skip
    digits = re.findall(r"\d+", explanation_text)
    if digits:
        source_text = f"{intro} {task_context}"
        for d in digits:
            if d not in source_text:
                return {"text": "", "status": "skip", "basis": []}

    # 5. Tone check: should end with .
    if not explanation_text.endswith("."):
        explanation_text += "."

    return {
        "text": explanation_text,
        "status": "ai_draft",
        "basis": basis
    }


def main():
    print(f"Loading inputs from {INPUTS_PATH}...")
    prep = HRTextPreprocessor()
    records = []
    with open(INPUTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f"Loaded {len(records)} records. Generating explanations...")
    explanations: Dict[str, Any] = {}

    skip_count = 0
    draft_count = 0

    for rec in records:
        pair_key = rec["pair_key"]
        result = generate_explanation_for_record(rec, prep)
        explanations[pair_key] = result
        if result["status"] == "skip":
            skip_count += 1
        else:
            draft_count += 1

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(explanations, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(explanations)} explanations saved to {OUTPUT_PATH}")
    print(f"ai_draft: {draft_count}, skip: {skip_count}")


if __name__ == "__main__":
    main()
