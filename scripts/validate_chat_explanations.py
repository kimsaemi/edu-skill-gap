#!/usr/bin/env python3
"""
scripts/validate_chat_explanations.py
강화된 추천 설명 검증 스크립트:
1. 모든 키가 explanation_inputs.jsonl 에 존재하는지
2. 120자 초과 0건 (목표: 80자 안팎)
3. 금지어 0건 ("만족도", "수료 효과", "취업", "보장", "가격", "일정", "최고", "반드시", "체계적으로" 등)
4. 과정명(title) 본문 직접 포함 0건
5. 임의 숫자(원문에 없는 숫자) 0건
6. basis 표현이 해당 짝의 입력 텍스트에 실제 존재하는지 (100% 부분 문자열 일치)
7. 같은 업무 내 설명 중복 검사 (동일 문장 및 유사도 0.9 이상 실패)
8. 과정 소개 요약 단순 복사 검사 (최장 공통 부분 문자열이 설명 길이의 70% 이상이면 실패)
9. 고정 문장 틀 흔적 검사 ("업무에 필요한 * 실무 역량을 체계적으로", "교재 실무" 등)
10. 비문 및 어색한 끝맺음 검사 ("을 이해를", "를 이해를", "에 대해 다뤄요" 등)
11. 무작위 30개(seed=42 고정) 표본 파일 생성: docs/chat_explanations_sample.md
12. 검증 통계 JSON 저장 (data/hr/output/chatbot/explanation_validation_results.json) 및
    보고서 작성 (docs/chat_explanations_report.md)
13. 팀 검토용 CSV 생성: data/hr/output/chatbot/rec_explanations_review.csv
"""
import os
import re
import json
import csv
import random
from typing import Dict, Any, List, Tuple
from difflib import SequenceMatcher

INPUTS_PATH = "data/hr/output/chatbot/explanation_inputs.jsonl"
EXPLANATIONS_PATH = "data/hr/output/chatbot/rec_explanations_90.json"
RESULTS_JSON_PATH = "data/hr/output/chatbot/explanation_validation_results.json"
REPORT_PATH = "docs/chat_explanations_report.md"
SAMPLE_PATH = "docs/chat_explanations_sample.md"
REVIEW_CSV_PATH = "data/hr/output/chatbot/rec_explanations_review.csv"

FORBIDDEN_WORDS = [
    "만족도", "수료 효과", "수료효과", "취업", "자격 취득 보장", "자격취득보장",
    "보장", "가격", "일정", "최고", "반드시", "수료 후", "수료후", "체계적으로"
]
CURRENCY_PATTERNS = [
    r"\d+\s*원", r"\d+\s*만원", r"수강료", r"비용", r"할인", r"무료"
]
AWKWARD_PATTERNS = [
    r"[을를]\s*이해를", r"에\s*대해\s*다뤄요", r"기초지식을\s*이해를",
    r"실무\s*역량을\s*체계적으로", r"교재\s*실무", r"가능·희망", r"승진·부장"
]
TEMPLATE_PATTERNS = [
    r"업무에\s*필요한.+실무\s*역량을\s*체계적으로",
    r"업무에\s*필요한.+실무\s*역량을\s*다뤄요"
]


def longest_common_substring(s1: str, s2: str) -> str:
    m = SequenceMatcher(None, s1, s2).find_longest_match(0, len(s1), 0, len(s2))
    return s1[m.a:m.a + m.size]


def validate_explanations() -> bool:
    if not os.path.exists(INPUTS_PATH):
        print(f"Error: {INPUTS_PATH} does not exist.")
        return False
    if not os.path.exists(EXPLANATIONS_PATH):
        print(f"Error: {EXPLANATIONS_PATH} does not exist.")
        return False

    inputs_map = {}
    with open(INPUTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                inputs_map[rec["pair_key"]] = rec

    with open(EXPLANATIONS_PATH, "r", encoding="utf-8") as f:
        explanations: Dict[str, Any] = json.load(f)

    total_inputs = len(inputs_map)
    total_explanations = len(explanations)

    unknown_keys = []
    len_violations = []
    forbidden_violations = []
    title_violations = []
    number_violations = []
    basis_violations = []
    task_dup_violations = []
    overcopy_violations = []
    template_violations = []
    awkward_violations = []

    claude_draft_count = 0
    skip_count = 0
    reviewed_count = 0
    lengths = []

    # 업무별 설명 수집 (중복 검사용)
    task_explanations: Dict[str, List[Tuple[str, str]]] = {}

    for key, data in explanations.items():
        if key not in inputs_map:
            unknown_keys.append(key)
            continue

        inp = inputs_map[key]
        text = data.get("text", "").strip()
        status = data.get("status", "claude_draft")
        basis = data.get("basis", [])

        if status == "skip" or not text:
            skip_count += 1
            continue

        if status == "claude_draft":
            claude_draft_count += 1
        elif status == "reviewed":
            reviewed_count += 1

        tid = inp.get("task_id", "")
        if tid not in task_explanations:
            task_explanations[tid] = []
        task_explanations[tid].append((key, text))

        # Check 1: Length <= 120
        lengths.append(len(text))
        if len(text) > 120:
            len_violations.append((key, len(text), text))

        # Check 2: Forbidden words & currency
        for fw in FORBIDDEN_WORDS:
            if fw in text:
                forbidden_violations.append((key, fw, text))
                break
        else:
            for cp_pat in CURRENCY_PATTERNS:
                if re.search(cp_pat, text):
                    forbidden_violations.append((key, cp_pat, text))
                    break

        # Check 3: Title verbatim included
        title = inp.get("title", "").strip()
        if title and len(title) >= 4 and title in text:
            title_violations.append((key, title, text))

        # Check 4: Arbitrary numbers
        digits_in_text = re.findall(r"\d+", text)
        source_text = f"{inp.get('intro_summary', '')} {inp.get('task_name', '')} {inp.get('ksa_summary', '')} {inp.get('easy_description', '')}"
        if digits_in_text:
            for d in digits_in_text:
                if d not in source_text:
                    number_violations.append((key, d, text))
                    break

        # Check 5: Basis presence in source
        if not basis:
            basis_violations.append((key, "empty_basis", text))
        else:
            for b in basis:
                if b not in source_text:
                    basis_violations.append((key, f"not_in_source: '{b}'", text))
                    break

        # Check 6: Overcopy from intro_summary (>= 70%)
        intro = inp.get("intro_summary", "")
        if intro:
            lcs = longest_common_substring(text, intro)
            if len(text) > 0 and (len(lcs) / len(text)) >= 0.70:
                overcopy_violations.append((key, f"LCS {len(lcs)}/{len(text)} ({len(lcs)/len(text)*100:.1f}%)", text))

        # Check 7: Template pattern check
        for tp in TEMPLATE_PATTERNS:
            if re.search(tp, text):
                template_violations.append((key, tp, text))
                break

        # Check 8: Awkward endings & phrasing
        for ap in AWKWARD_PATTERNS:
            if re.search(ap, text):
                awkward_violations.append((key, ap, text))
                break

    # Check 9: Task intra-duplicate check
    for tid, items in task_explanations.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                k1, t1 = items[i]
                k2, t2 = items[j]
                sim = SequenceMatcher(None, t1, t2).ratio()
                if sim >= 0.90:
                    task_dup_violations.append((k1, k2, f"sim={sim:.2f}", t1))

    avg_len = sum(lengths) / len(lengths) if lengths else 0.0
    max_len = max(lengths) if lengths else 0

    # Save validation results JSON
    val_results = {
        "total_inputs": total_inputs,
        "total_explanations": total_explanations,
        "claude_draft_count": claude_draft_count,
        "reviewed_count": reviewed_count,
        "skip_count": skip_count,
        "active_count": claude_draft_count + reviewed_count,
        "avg_length": round(avg_len, 1),
        "max_length": max_len,
        "violations": {
            "unknown_keys": len(unknown_keys),
            "length_over_120": len(len_violations),
            "forbidden_words": len(forbidden_violations),
            "title_included": len(title_violations),
            "arbitrary_numbers": len(number_violations),
            "basis_mismatch": len(basis_violations),
            "intra_task_duplicates": len(task_dup_violations),
            "overcopy_intro": len(overcopy_violations),
            "template_patterns": len(template_violations),
            "awkward_phrasing": len(awkward_violations)
        }
    }

    os.makedirs(os.path.dirname(RESULTS_JSON_PATH), exist_ok=True)
    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(val_results, f, ensure_ascii=False, indent=2)

    # Write review CSV
    os.makedirs(os.path.dirname(REVIEW_CSV_PATH), exist_ok=True)
    with open(REVIEW_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["업무", "과정명", "설명", "팀 검토(적합/수정 필요)"])
        for key, inp in inputs_map.items():
            exp = explanations.get(key, {})
            text = exp.get("text", "")
            writer.writerow([inp.get("task_name", ""), inp.get("title", ""), text, ""])

    # Write random 30 sample markdown (fixed seed=42)
    random.seed(42)
    sample_keys = [k for k, d in explanations.items() if d.get("status") == "claude_draft" and d.get("text")]
    sampled = random.sample(sample_keys, min(30, len(sample_keys))) if sample_keys else []

    sample_lines = [
        "# 챗봇 사전 제작 추천 설명 30개 무작위 표본 (seed=42 고정)",
        "",
        "## 검토 안내",
        "- 표본 추출 기준: `claude_draft` 작성 설명 중 난수 시드 42로 무작위 30건 추출",
        "- 팀 판정 칸은 검토자가 직접 판정할 수 있도록 비워 둠",
        "",
        "| 번호 | 업무명 | KSA 요약 | 과정명 & 소개 요약 | Claude 작성 설명 (basis) | 팀 판정 (적합/수정필요) |",
        "| :---: | :--- | :--- | :--- | :--- | :---: |"
    ]
    for idx, sk in enumerate(sampled, 1):
        inp = inputs_map[sk]
        exp = explanations[sk]
        t_name = inp.get("task_name", "").replace("|", "-")
        ksa = inp.get("ksa_summary", "")[:50].replace("|", "-")
        c_title = inp.get("title", "").replace("|", "-")
        intro = inp.get("intro_summary", "")[:60].replace("|", "-")
        exp_text = exp.get("text", "").replace("|", "-")
        basis_str = ", ".join(exp.get("basis", []))
        sample_lines.append(
            f"| {idx} | {t_name} | {ksa}… | **{c_title}**<br>{intro}… | {exp_text}<br><small>({basis_str})</small> | |"
        )

    os.makedirs(os.path.dirname(SAMPLE_PATH), exist_ok=True)
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sample_lines) + "\n")

    # Write Markdown Report (reading strictly from val_results)
    total_violations = sum(val_results["violations"].values())
    report_content = f"""# 챗봇 추천 과정 사전 생성 설명 검증 보고서

## 1. 개요
- **검증 대상**: `{EXPLANATIONS_PATH}`
- **전체 후보 쌍**: {val_results['total_inputs']}건
- **작성 완료 (`claude_draft` / `reviewed`)**: {val_results['active_count']}건 (작성률: {val_results['active_count']/val_results['total_inputs']*100:.1f}%)
- **건너뜀 (`skip`, 규칙 설명 폴백 대상)**: {val_results['skip_count']}건
- **평균 글자 수**: {val_results['avg_length']}자 (최대 {val_results['max_length']}자 / 제한 120자)

## 2. 세부 검사 항목 및 결과
| 검사항목 | 허용 기준 | 위반 건수 | 결과 |
| :--- | :---: | :---: | :---: |
| 미등록 키 검증 | 0건 | {val_results['violations']['unknown_keys']}건 | {'✅ PASS' if val_results['violations']['unknown_keys'] == 0 else '❌ FAIL'} |
| 글자 수 초과 (120자 초과) | 0건 | {val_results['violations']['length_over_120']}건 | {'✅ PASS' if val_results['violations']['length_over_120'] == 0 else '❌ FAIL'} |
| 금지어 및 금액 표현 포함 | 0건 | {val_results['violations']['forbidden_words']}건 | {'✅ PASS' if val_results['violations']['forbidden_words'] == 0 else '❌ FAIL'} |
| 과정명 본문 직접 포함 | 0건 | {val_results['violations']['title_included']}건 | {'✅ PASS' if val_results['violations']['title_included'] == 0 else '❌ FAIL'} |
| 임의 숫자 (원문에 없는 수치) | 0건 | {val_results['violations']['arbitrary_numbers']}건 | {'✅ PASS' if val_results['violations']['arbitrary_numbers'] == 0 else '❌ FAIL'} |
| basis 표현 원문 일치 검증 | 0건 | {val_results['violations']['basis_mismatch']}건 | {'✅ PASS' if val_results['violations']['basis_mismatch'] == 0 else '❌ FAIL'} |
| 같은 업무 내 설명 중복 (유사도 0.9 이상) | 0건 | {val_results['violations']['intra_task_duplicates']}건 | {'✅ PASS' if val_results['violations']['intra_task_duplicates'] == 0 else '❌ FAIL'} |
| 소개글 단순 복사 (LCS >= 70%) | 0건 | {val_results['violations']['overcopy_intro']}건 | {'✅ PASS' if val_results['violations']['overcopy_intro'] == 0 else '❌ FAIL'} |
| 고정 문장 틀 흔적 ("* 실무 역량을 체계적으로" 등) | 0건 | {val_results['violations']['template_patterns']}건 | {'✅ PASS' if val_results['violations']['template_patterns'] == 0 else '❌ FAIL'} |
| 어색한 비문 및 종결 ("을 이해를", "에 대해 다뤄요" 등) | 0건 | {val_results['violations']['awkward_phrasing']}건 | {'✅ PASS' if val_results['violations']['awkward_phrasing'] == 0 else '❌ FAIL'} |

## 3. 검증 산출물
- **검증 통계 JSON**: `{RESULTS_JSON_PATH}`
- **무작위 30건 검토 표본**: `{SAMPLE_PATH}`
- **전체 팀 검토용 CSV**: `{REVIEW_CSV_PATH}`
"""
    if total_violations == 0:
        report_content += "\n## 4. 종합 판정\n- **전체 검사 통과 (0건 위반)**: 모든 제약 조건과 자연스러운 문체 기준을 충족했습니다.\n"
    else:
        report_content += f"\n## 4. 종합 판정\n- **검사 실패 ({total_violations}건 위반)**: 수정이 필요한 항목이 존재합니다.\n"

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Validation finished. Total: {total_inputs}, Active: {val_results['active_count']}, Skip: {val_results['skip_count']}")
    print(f"Total violations: {total_violations}")
    return total_violations == 0


if __name__ == "__main__":
    import sys
    success = validate_explanations()
    sys.exit(0 if success else 1)
