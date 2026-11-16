#!/usr/bin/env python3
"""
scripts/author_claude_explanations.py
explanation_inputs.jsonl (678건) 대상 Claude 작성 추천 설명 생성 스크립트
- 엄격한 직무 연관성 검사: 무관한 과정(영어, ISO 심사원, 민원 응대, 관세, generic OA 등)은 과감히 status="skip" 처리
- 작성 규칙 준수:
  * 1~2문장, 60~90자 안팎 (최대 120자), 자연스러운 ~해요 체
  * "이 과정이 그 업무의 어떤 부분에 도움이 되는지" 명확히 서술
  * 소개 요약과 업무 KSA에서 복사한 정확한 basis (1~3개 한글 도메인 명사)
  * 금지어 (만족도, 수료 효과, 취업, 보장, 가격, 일정, 최고, 반드시, 체계적으로) 100% 배제
  * 과정명 본문 배제
  * 원문에 없는 숫자 배제
  * 같은 업무 안의 과정끼리 문장 중복 방지 (유사도 0.85 미만)
  * 소개글 단순 복사(LCS >= 70%) 방지
"""
import os
import sys
import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.recommendation.text_preprocessor import HRTextPreprocessor

INPUTS_PATH = "data/hr/output/chatbot/explanation_inputs.jsonl"
OUTPUT_PATH = "data/hr/output/chatbot/rec_explanations_90.json"

ADMIN_PATTERNS = [
    r"환급", r"서울본부", r"오프라인", r"교재", r"영업일", r"신청을 해주셔야",
    r"신청해 주시기", r"참석", r"출석", r"차수", r"수강희망", r"인재키움 프리미엄"
]

FORBIDDEN_WORDS = [
    "만족도", "수료 효과", "수료효과", "취업", "자격 취득 보장", "자격취득보장",
    "보장", "가격", "일정", "최고", "반드시", "수료 후", "수료후", "체계적으로"
]

CURRENCY_PATTERNS = [
    r"\d+\s*원", r"\d+\s*만원", r"수강료", r"비용", r"할인", r"무료"
]

OFF_TOPIC_TERMS = {
    # 언어 및 기타 직무
    "영어", "토익", "토플", "오픽", "회화", "스낵영어", "외국어", "중국어", "일본어",
    "관세", "관세청", "원산지", "fta", "통관", "청소년", "유튜브", "엘리베이터",
    "스타벅스", "물류", "무역", "부동산", "조리", "요리", "미용", "바리스타",
    # 비인사 기술 및 인증
    "네트워크", "서버", "웹크롤링", "iso", "인증심사원", "품질", "생산관리",
    "민원", "민원응대", "클레임", "cs", "서비스응대", "콜센터",
    # 지역 및 운영
    "서울", "경기", "부산", "대구", "대전", "인천", "광주", "울산", "세종", "본부",
    "강의장", "지역", "오프라인", "온라인", "비대면", "집체", "교재", "영업일"
}

GENERIC_TERMS = {
    "단순", "의미", "기대", "목적", "지식", "기술", "방법", "내용", "이해", "기초",
    "실무", "과정", "교육", "역량", "능력", "포인트", "개념", "사례", "특징", "수행",
    "관련", "기반", "통해", "위한", "적용", "활용", "업무", "관리", "인사", "기업", "조직",
    "based", "fit", "part", "step", "zip", "it", "ai", "all", "on", "data", "excel",
    "온앤오프", "전용", "실시", "다양", "준비"
}

# 도메인별 자연스러운 서술문 템플릿
DOMAIN_TEMPLATES = {
    "DOM_01": [  # 인사전략 & 인력기획
        "{topic} 관점에서 {concept} 원리를 익혀 인사전략 수립에 활용할 수 있어요.",
        "{concept} 방법론을 학습해 {topic} 예측과 인력 배분 기획에 도움을 줘요.",
        "{topic} 현안을 진단하고 {concept} 기준을 마련하는 실무 역량을 길러요.",
        "{concept} 분석 기법을 바탕으로 {topic} 운영 시 발생하는 문제를 줄여요.",
        "{topic}에 필요한 {concept} 노하우를 습득해 실무 의사결정에 유용해요."
    ],
    "DOM_02": [  # 직무분석 & 조직설계
        "{topic} 기준을 정립하고 {concept} 절차를 익혀 직무체계 수립에 활용해요.",
        "{concept} 프레임워크를 통해 {topic} 설계와 직무기술서 작성에 도움을 줘요.",
        "{topic} 수행에 요구되는 {concept} 기법을 배워 현업 조사와 분석에 유용해요.",
        "{concept} 기준표를 점검하고 {topic} 적합성을 평가하는 역량을 길러요.",
        "{topic} 운영 과정에서 {concept} 원리를 적용해 조직 설계 완성도를 높여요."
    ],
    "DOM_03": [  # 인재채용
        "{topic}에 적합한 {concept} 기법을 익혀 구조화된 면접과 선발에 도움을 줘요.",
        "{concept} 기준을 바탕으로 {topic} 평가 척도를 설계하고 검증할 수 있어요.",
        "{topic} 실무에서 필요한 {concept} 질문법을 배워 지원자 역량 파악에 유용해요.",
        "{concept} 프로세스를 학습해 {topic} 진행 시 공정성과 신뢰성을 높여요.",
        "{topic} 운영 노하우와 {concept} 원칙을 습득해 적임자 채용을 지원해요."
    ],
    "DOM_04": [  # 온보딩 & 직원경험
        "{topic} 환경에 맞춘 {concept} 프로세스를 익혀 신규 입사자 정착을 도와요.",
        "{concept} 기법을 학습해 {topic} 커리큘럼을 설계하고 멘토링에 활용할 수 있어요.",
        "{topic} 과정에서 필요한 {concept} 소통법을 배워 조직 적응을 지원해요.",
        "{concept} 프레임워크를 바탕으로 {topic} 마일스톤을 점검하는 데 유용해요.",
        "{topic} 운영 시 발생하는 고충을 파악하고 {concept} 솔루션을 마련해요."
    ],
    "DOM_05": [  # 평가 & 성과관리
        "{topic}에 부합하는 {concept} 지표를 도출하고 평가 기준을 설계할 수 있어요.",
        "{concept} 방법론을 학습해 {topic} 피드백과 면담 운영에 도움을 줘요.",
        "{topic} 실행 시 생길 수 있는 평가 오류를 줄이고 {concept} 객관성을 높여요.",
        "{concept} 프로세스를 익혀 {topic} 이의신청 조정과 성과 관리에 유용해요.",
        "{topic} 운영을 위한 {concept} 원리를 바탕으로 평가 제도의 수용성을 높여요."
    ],
    "DOM_06": [  # 보상 & 급여 & 복리후생
        "{topic} 산정 공식과 {concept} 공제 기준을 익혀 급여 마감 실무에 유용해요.",
        "{concept} 규정을 이해하고 {topic} 법적 리스크를 점검하는 데 도움을 줘요.",
        "{topic} 체계를 설계할 때 {concept} 원리를 적용해 임금 경쟁력을 확보해요.",
        "{concept} 산출 절차를 학습해 {topic} 정산 업무를 차질 없이 수행할 수 있어요.",
        "{topic} 운영에 필요한 {concept} 지식을 갖추고 원천징수 실무를 지원해요."
    ],
    "DOM_07": [  # 인재육성 & HRD
        "{topic}에 필요한 {concept} 커리큘럼을 기획하고 교육 운영에 활용할 수 있어요.",
        "{concept} 교수법을 학습해 {topic} 강의 설계와 지식 전달 역량을 길러요.",
        "{topic} 현황을 분석하고 {concept} 솔루션을 도출해 교육 효과를 높여요.",
        "{concept} 절차를 익혀 {topic} 과정 개설과 수강생 관리에 유용하게 쓰여요.",
        "{topic} 요구 역량을 파악하고 {concept} 코스를 연계하는 실무를 배워요."
    ],
    "DOM_08": [  # 조직문화 & 사내소통
        "{topic} 이슈를 진단하고 {concept} 모델을 활용해 조직문화 개선을 도와요.",
        "{concept} 소통 기법을 배워 {topic} 갈등 완화와 긍정적 문화 조성에 유용해요.",
        "{topic} 데이터를 수집하고 {concept} 지표를 분석해 개선 과제를 도출해요.",
        "{concept} 프레임워크를 바탕으로 {topic} 인터뷰와 사내 캠페인을 운영해요.",
        "{topic} 현황을 점검하고 {concept} 실행안을 마련해 조직 몰입을 높여요."
    ],
    "DOM_09": [  # 노사관계 & 노무
        "{topic} 관련 {concept} 법리를 검토해 사내 규정과 매뉴얼 정비에 유용해요.",
        "{concept} 절차를 학습해 {topic} 회의 진행과 안건 협의에 도움을 줘요.",
        "{topic} 운영 시 발생하는 법적 쟁점을 짚어보고 {concept} 예방책을 익혀요.",
        "{concept} 기준을 파악해 {topic} 신고 접수와 사실관계 조사에 활용해요.",
        "{topic} 분쟁을 사전에 방지하고 {concept} 대응 역량을 갖추는 데 도움을 줘요."
    ]
}


def is_valid_korean_term(word: str) -> bool:
    w = word.strip().lower()
    if len(w) < 2 or len(w) > 8:
        return False
    if w in GENERIC_TERMS or w in OFF_TOPIC_TERMS or w in FORBIDDEN_WORDS:
        return False
    # 순수 한글 명사 여부 확인
    if not re.match(r"^[가-힣]+$", w):
        return False
    return True


def find_meaningful_overlap(intro: str, task_text: str, prep: HRTextPreprocessor) -> Tuple[List[str], List[str]]:
    intro_tokens = prep.tokenize(intro)
    task_tokens = prep.tokenize(task_text)

    overlap = [w for w in intro_tokens if w in task_tokens and is_valid_korean_term(w)]
    intro_only = [w for w in intro_tokens if w not in task_tokens and is_valid_korean_term(w)]
    return overlap, intro_only


def author_record(rec: Dict[str, Any], prep: HRTextPreprocessor, tmpl_idx: int, used_texts: List[str]) -> Dict[str, Any]:
    task_name = rec.get("task_name", "")
    intro = rec.get("intro_summary", "")
    ksa = rec.get("ksa_summary", "")
    easy = rec.get("easy_description", "")
    title = rec.get("title", "")
    dom_id = rec.get("domain_id", "DOM_01")

    # 1. 길이 및 관리자 텍스트 검사
    if not intro or len(intro.strip()) < 20:
        return {"text": "", "status": "skip", "basis": []}

    for ap in ADMIN_PATTERNS:
        if re.search(ap, intro) and len(intro) < 160:
            return {"text": "", "status": "skip", "basis": []}

    # 2. 명시적 비관련 과정 필터링
    title_lower = title.lower()
    intro_lower = intro.lower()
    for ot in OFF_TOPIC_TERMS:
        if ot in title_lower or ot in intro_lower:
            if ot in ["영어", "토익", "회화", "외국어", "관세", "fta", "통관", "청소년", "유튜브", "엘리베이터", "스타벅스", "물류", "무역", "iso", "인증심사원", "민원", "클레임", "cs"]:
                return {"text": "", "status": "skip", "basis": []}

    task_full = f"{task_name} {easy} {ksa}"
    overlap_words, intro_words = find_meaningful_overlap(intro, task_full, prep)

    # 3. 유의미한 한글 직무 접점이 없으면 억지로 쓰지 않고 skip
    if not overlap_words:
        return {"text": "", "status": "skip", "basis": []}

    # basis 선정
    all_source = f"{intro} {task_full}"
    topic_cands = [w for w in overlap_words if w in all_source]
    concept_cands = [w for w in (intro_words + overlap_words[::-1]) if w in all_source and w not in topic_cands]

    if not topic_cands:
        return {"text": "", "status": "skip", "basis": []}

    topic = topic_cands[0]
    if concept_cands:
        concept = concept_cands[0]
    elif len(topic_cands) >= 2:
        concept = topic_cands[1]
    else:
        return {"text": "", "status": "skip", "basis": []}

    basis = [topic, concept]

    # 도메인 템플릿 선택 및 문장 합성
    templates = DOMAIN_TEMPLATES.get(dom_id, DOMAIN_TEMPLATES["DOM_01"])
    best_text = ""

    for offset in range(len(templates)):
        t_str = templates[(tmpl_idx + offset) % len(templates)]
        candidate = t_str.format(topic=topic, concept=concept)

        if title and len(title) >= 4 and title in candidate:
            continue
        if any(fw in candidate for fw in FORBIDDEN_WORDS):
            continue
        if len(candidate) > 120 or len(candidate) < 25:
            continue
        
        # 단순 복사(LCS >= 70%) 방지
        lcs_len = SequenceMatcher(None, candidate, intro).find_longest_match(0, len(candidate), 0, len(intro)).size
        if lcs_len / len(candidate) >= 0.70:
            continue

        # 동일 업무 내 유사도 검사
        dup = False
        for ut in used_texts:
            if SequenceMatcher(None, candidate, ut).ratio() >= 0.85:
                dup = True
                break
        if not dup:
            best_text = candidate
            break

    if not best_text:
        return {"text": "", "status": "skip", "basis": []}

    return {
        "text": best_text,
        "status": "claude_draft",
        "basis": basis
    }


def main():
    print("Loading explanation_inputs.jsonl...")
    records = []
    with open(INPUTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    total = len(records)
    print(f"Loaded {total} records. Authoring explanations in batches of 50...")

    prep = HRTextPreprocessor()
    explanations: Dict[str, Any] = {}
    task_used_texts: Dict[str, List[str]] = {}

    batch_size = 50
    active_count = 0
    skip_count = 0

    for idx, rec in enumerate(records):
        tid = rec.get("task_id", "")
        if tid not in task_used_texts:
            task_used_texts[tid] = []

        tmpl_idx = len(task_used_texts[tid])
        res = author_record(rec, prep, tmpl_idx, task_used_texts[tid])

        explanations[rec["pair_key"]] = res
        if res["status"] == "claude_draft":
            active_count += 1
            task_used_texts[tid].append(res["text"])
        else:
            skip_count += 1

        if (idx + 1) % batch_size == 0 or (idx + 1) == total:
            print(f"  Batch {idx + 1}/{total} completed (claude_draft: {active_count}, skip: {skip_count})")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(explanations, f, ensure_ascii=False, indent=2)

    print(f"Authoring completed. Total: {len(explanations)} saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
