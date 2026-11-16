#!/usr/bin/env python3
"""
scripts/run_chatbot_smoke_test.py
대표 질문 10개에 대해 match_and_recommend 실행 및 결과 리포트 docs/chatbot_smoke_test.md 생성
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatbot import matcher as M
from src.chatbot.matcher import match_and_recommend

QUERIES = [
    "4대보험 신고를 처음 맡았어요",
    "직무급제 도입을 검토 중인데 뭘 알아야 해?",
    "신입사원 온보딩 프로그램을 기획해야 해요",
    "노사협의회 운영 절차가 궁금해요",
    "파이썬으로 인사 데이터 분석하고 싶어요",
    "엑셀 실무 강좌 알려줘",
    "퇴직금 계산이 복잡해요",
    "평가 면담을 잘하고 싶어요",
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
        "# AI 상담 스모크 테스트 (대표 질문)",
        "",
        "## 1. 개요",
        f"- **기준값**: 업무 연결 점수 ≥ {M.CONFIDENT_SCORE} 또는 (≥ {M.CANDIDATE_SCORE} 이면서 1·2위 차이 ≥ {M.CONFIDENT_MARGIN}) / 후보 {M.CANDIDATE_SCORE} / 범위 밖 의미 유사도 < {M.OUT_OF_SCOPE_SEM} (근거: docs/chat_threshold_report.md)",
        "- **추천 이유**: 모두 규칙 기반 자동 생성 문장",
        "- **팀 판정**: 빈칸으로 두고 팀원이 채웁니다",
        "",
        "## 2. 질의별 추천 및 설명 실행 결과",
        ""
    ]

    for idx, q in enumerate(QUERIES, 1):
        # '뭘 들어야 할지 모르겠어요'는 진단 결과 연계 확인용으로 예시 부족 업무를 넘긴다
        weak = mock_weak if q.startswith("뭘 들어야") else None
        res = match_and_recommend(query=q, grade_idx=1, use_reranker=True, weak_task=weak)

        matched_info = ""
        if res.mode == "task_match" and res.matched_task:
            matched_info = f"업무 매핑 (`{res.matched_task.get('name')}`), 점수: {res.similarity_score:.4f}"
        elif res.mode == "personalization" and res.matched_task:
            matched_info = f"개인화 진단 연계 (`{res.matched_task.get('name')}`), 점수: {res.similarity_score:.4f}"
        elif res.mode == "out_of_scope":
            matched_info = f"범위 밖 질의 (안내 메시지 표시, 과정 카드 미표시), 점수: {res.similarity_score:.4f}"
        elif res.mode == "candidates":
            names = " / ".join(t.get("name", "") for t in res.candidate_tasks)
            matched_info = f"업무 후보 버튼 ({names}) + 질문 검색 결과, 점수: {res.similarity_score:.4f}"
        else:
            matched_info = f"질문 검색 결과, 점수: {res.similarity_score:.4f}"

        report_lines.append(f"### Q{idx}. \"{q}\"")
        report_lines.append(f"- **실행 모드**: {matched_info}")
        report_lines.append(f"- **시스템 메시지**: {res.system_message}")
        report_lines.append("")

        if not res.cards:
            report_lines.append("*(범위 밖 안내 메시지만 표시되며 추천 과정 카드는 표시되지 않습니다.)*")
        else:
            report_lines.append("| 순번 | 과정명 | 제공기관 | 추천 이유 설명 | 설명 출처 | 팀 판정 (적합/보통/부적합) |")
            report_lines.append("| :---: | :--- | :--- | :--- | :---: | :---: |")

            for c_idx, (card, exp) in enumerate(zip(res.cards[:3], res.explanations[:3]), 1):
                title = card.get("title", "").replace("|", "-")
                inst = card.get("provider", "") or card.get("institution", "")
                exp_text = exp.get("text", "").replace("|", "-")
                source = "자동 생성 문장"
                report_lines.append(f"| {c_idx} | {title} | {inst} | {exp_text} | {source} | |")

        report_lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print(f"Smoke test completed. Saved to {OUTPUT_MD}")


if __name__ == "__main__":
    main()
