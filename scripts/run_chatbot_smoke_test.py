#!/usr/bin/env python3
"""
scripts/run_chatbot_smoke_test.py
대표 질문 10개에 대해 match_and_recommend 실행 및 결과 리포트 docs/chatbot_smoke_test.md 생성
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatbot.matcher import match_and_recommend, TASK_SIMILARITY_THRESHOLD

QUERIES = [
    "4대보험 신고를 처음 맡았어요",
    "직무급제 도입을 검토 중인데 뭘 알아야 해?",
    "신입사원 온보딩 프로그램을 기획해야 해요",
    "노사협의회 운영 절차가 궁금해요",
    "파이썬으로 인사 데이터 분석하고 싶어요",
    "엑셀 실무 강좌 알려줘",
    "퇴직금 계산이 복잡해요",
    "성희롱 예방교육 법정의무교육 찾아줘",
    "뭘 들어야 할지 모르겠어요",
    "안녕 반가워"
]

OUTPUT_MD = "docs/chatbot_smoke_test.md"


def main():
    print(f"Running smoke test on {len(QUERIES)} queries...")
    mock_weak = {
        "id": "DOM_06_T05",
        "name": "매월 임직원 급여·상여 계산, 4대보험 공제 및 원천징수 급여 대장 마감",
        "k": "4대보험 요율, 통상임금"
    }

    report_lines = [
        "# AI 추천 상담 챗봇 스모크 테스트 (10개 대표 질의)",
        "",
        "## 1. 개요",
        f"- **일시**: 2026-11-16",
        f"- **유사도 임계값**: `{TASK_SIMILARITY_THRESHOLD}` (0.55 이상: 업무 매핑 / 0.55 미만: 과정 검색 / 개인화 키워드: 진단 연계)",
        f"- **검토 원칙**: 사람 판정란은 비워 두어 팀 검토자가 직접 입력할 수 있도록 구성",
        "",
        "## 2. 질의별 추천 및 설명 실행 결과",
        ""
    ]

    for idx, q in enumerate(QUERIES, 1):
        # 9번 쿼리(뭘 들어야 할지 모르겠어요)는 개인화 연계 테스트용으로 weak_task 전달
        weak = mock_weak if idx == 9 else None
        res = match_and_recommend(query=q, grade_idx=1, use_reranker=True, weak_task=weak)

        matched_info = ""
        if res.mode == "task_match" and res.matched_task:
            matched_info = f"업무 매핑 (`{res.matched_task.get('name')}`), 유사도: {res.similarity_score:.4f}"
        elif res.mode == "personalization" and res.matched_task:
            matched_info = f"개인화 진단 연계 (`{res.matched_task.get('name')}`), 유사도: {res.similarity_score:.4f}"
        else:
            matched_info = f"키워드 검색 모드, 유사도: {res.similarity_score:.4f}"

        report_lines.append(f"### Q{idx}. \"{q}\"")
        report_lines.append(f"- **실행 모드**: {matched_info}")
        report_lines.append(f"- **시스템 메시지**: {res.system_message}")
        if res.alternative_task:
            report_lines.append(f"- **대안 업무 제안**: {res.alternative_task.get('name')}")
        report_lines.append("")
        report_lines.append("| 순번 | 과정명 | 제공기관 | 추천 이유 설명 | 설명 출처 | 팀 판정 (적합/보통/부적합) |")
        report_lines.append("| :---: | :--- | :--- | :--- | :---: | :---: |")

        for c_idx, (card, exp) in enumerate(zip(res.cards[:3], res.explanations[:3]), 1):
            title = card.get("title", "").replace("|", "-")
            inst = card.get("provider", "") or card.get("institution", "")
            exp_text = exp.get("text", "").replace("|", "-")
            source = exp.get("source", "")
            report_lines.append(f"| {c_idx} | {title} | {inst} | {exp_text} | {source} | |")

        report_lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print(f"Smoke test completed. Saved to {OUTPUT_MD}")


if __name__ == "__main__":
    main()
