#!/usr/bin/env python3
"""
scripts/validate_chat_explanations.py
검증 스크립트:
1. data/hr/output/chatbot/rec_explanations_90.json 의 모든 키가 explanation_inputs.jsonl 에 존재하는지
2. 120자 초과 0건
3. 금지어 포함 0건
4. 과정명(title) 본문 직접 포함 0건
5. 임의 숫자(본문에 없는 숫자) 포함 0건
6. 검증 통과 통계 보고서: docs/chat_explanations_report.md
7. 팀 검토용 CSV 생성: data/hr/output/chatbot/rec_explanations_review.csv
"""
import os
import re
import json
import csv
from typing import Dict, Any, List

INPUTS_PATH = "data/hr/output/chatbot/explanation_inputs.jsonl"
EXPLANATIONS_PATH = "data/hr/output/chatbot/rec_explanations_90.json"
REPORT_PATH = "docs/chat_explanations_report.md"
REVIEW_CSV_PATH = "data/hr/output/chatbot/rec_explanations_review.csv"

FORBIDDEN_WORDS = [
    "만족도", "수료 효과", "수료효과", "취업", "자격 취득 보장", "자격취득보장",
    "가격", "일정", "최고", "반드시", "수료 후", "수료후"
]
CURRENCY_PATTERNS = [
    r"\d+\s*원", r"\d+\s*만원", r"수강료", r"비용", r"할인", r"무료"
]


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

    # Errors list
    unknown_keys = []
    len_violations = []
    forbidden_violations = []
    title_violations = []
    number_violations = []

    ai_draft_count = 0
    skip_count = 0
    reviewed_count = 0
    lengths = []

    for key, data in explanations.items():
        if key not in inputs_map:
            # check if key might be DOM_XX_TYY|UID or TASK_HR_DXX_TYY|UID
            unknown_keys.append(key)
            continue

        inp = inputs_map[key]
        text = data.get("text", "").strip()
        status = data.get("status", "ai_draft")
        basis = data.get("basis", [])

        if status == "skip" or not text:
            skip_count += 1
            continue

        if status == "ai_draft":
            ai_draft_count += 1
        elif status == "reviewed":
            reviewed_count += 1

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
            for cp in CURRENCY_PATTERNS:
                if re.search(cp, text):
                    forbidden_violations.append((key, cp, text))
                    break

        # Check 3: Title verbatim included
        title = inp.get("title", "").strip()
        if title and len(title) >= 4 and title in text:
            title_violations.append((key, title, text))

        # Check 4: Arbitrary numbers
        digits_in_text = re.findall(r"\d+", text)
        if digits_in_text:
            source_text = f"{inp.get('intro_summary', '')} {inp.get('task_name', '')} {inp.get('ksa_summary', '')}"
            for d in digits_in_text:
                if d not in source_text:
                    number_violations.append((key, d, text))
                    break

    avg_len = sum(lengths) / len(lengths) if lengths else 0.0
    max_len = max(lengths) if lengths else 0

    # Write review CSV
    os.makedirs(os.path.dirname(REVIEW_CSV_PATH), exist_ok=True)
    with open(REVIEW_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["업무", "과정명", "설명", "팀 검토(적합/수정 필요)"])
        for key, inp in inputs_map.items():
            exp = explanations.get(key, {})
            text = exp.get("text", "")
            writer.writerow([inp.get("task_name", ""), inp.get("title", ""), text, ""])

    # Write Markdown Report
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    report_content = f"""# 챗봇 추천 과정 사전 생성 설명(rec_explanations_90) 검증 보고서

## 1. 개요
- **검증 대상**: `{EXPLANATIONS_PATH}`
- **전체 (업무, 강좌) 후보 쌍**: {total_inputs}건
- **설명 데이터 총 항목**: {total_explanations}건
- **작성 완료 (`ai_draft` / `reviewed`)**: {ai_draft_count + reviewed_count}건
- **건너뜀 (`skip`, 규칙 기반 폴백 대상)**: {skip_count}건

## 2. 규칙 준수 검증 결과
| 검증 항목 | 허용 기준 | 실제 위반 건수 | 결과 |
| :--- | :--- | :---: | :---: |
| 미등록 키 검증 | 0건 | {len(unknown_keys)}건 | {'✅ PASS' if len(unknown_keys) == 0 else '❌ FAIL'} |
| 글자 수 초과 (120자 초과) | 0건 | {len(len_violations)}건 | {'✅ PASS' if len(len_violations) == 0 else '❌ FAIL'} |
| 금지어 및 금액 표현 포함 | 0건 | {len(forbidden_violations)}건 | {'✅ PASS' if len(forbidden_violations) == 0 else '❌ FAIL'} |
| 과정명 본문 직접 포함 | 0건 | {len(title_violations)}건 | {'✅ PASS' if len(title_violations) == 0 else '❌ FAIL'} |
| 임의 숫자 (원문에 없는 수치) | 0건 | {len(number_violations)}건 | {'✅ PASS' if len(number_violations) == 0 else '❌ FAIL'} |

## 3. 텍스트 통계
- **작성된 설명 평균 글자 수**: {avg_len:.1f}자
- **최대 글자 수**: {max_len}자 (제한: 120자)
- **산출물**:
  - 검증 완료 JSON: `{EXPLANATIONS_PATH}`
  - 팀 검토용 CSV: `{REVIEW_CSV_PATH}`

## 4. 세부 위반 내역
"""
    if not (unknown_keys or len_violations or forbidden_violations or title_violations or number_violations):
        report_content += "- 특이사항 없음: 모든 검증 항목을 100% 통과했습니다.\n"
    else:
        if unknown_keys:
            report_content += f"### 미등록 키 ({len(unknown_keys)}건)\n"
            for k in unknown_keys[:5]:
                report_content += f"- `{k}`\n"
        if len_violations:
            report_content += f"### 글자 수 초과 ({len(len_violations)}건)\n"
            for k, l, t in len_violations[:5]:
                report_content += f"- `{k}` ({l}자): {t}\n"
        if forbidden_violations:
            report_content += f"### 금지어 검출 ({len(forbidden_violations)}건)\n"
            for k, w, t in forbidden_violations[:5]:
                report_content += f"- `{k}` (금지어 '{w}'): {t}\n"
        if title_violations:
            report_content += f"### 과정명 포함 ({len(title_violations)}건)\n"
            for k, ttl, t in title_violations[:5]:
                report_content += f"- `{k}` (과정명 '{ttl}'): {t}\n"
        if number_violations:
            report_content += f"### 임의 숫자 검출 ({len(number_violations)}건)\n"
            for k, d, t in number_violations[:5]:
                report_content += f"- `{k}` (숫자 '{d}'): {t}\n"

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Validation finished. Total: {total_inputs}, Skip: {skip_count}, Active: {ai_draft_count + reviewed_count}")
    print(f"Violations - Unknown keys: {len(unknown_keys)}, Length: {len(len_violations)}, Forbidden: {len(forbidden_violations)}, Title: {len(title_violations)}, Numbers: {len(number_violations)}")

    passed = (len(unknown_keys) == 0 and len(len_violations) == 0 and
              len(forbidden_violations) == 0 and len(title_violations) == 0 and
              len(number_violations) == 0)
    return passed


if __name__ == "__main__":
    import sys
    success = validate_explanations()
    sys.exit(0 if success else 1)
