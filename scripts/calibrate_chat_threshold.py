#!/usr/bin/env python3
"""
scripts/calibrate_chat_threshold.py
AI 상담 업무 연결 기준값 점검

- 90개 업무명을 그대로 넣었을 때: 자기 업무 1위 비율, 결과 종류 분포
- 인사 질문 묶음 / 인사와 무관한 질문 묶음: 업무 점수, 1·2위 차이, 의미 유사도 최고값, 결과 종류
- 결과: data/hr/output/chatbot/threshold_calibration.json, docs/chat_threshold_report.md
  (보고서 숫자는 모두 json에서 읽어 쓴다. 질문 묶음이 작으므로 질문을 늘리면 다시 실행한다.)
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.chatbot import matcher as M  # noqa: E402
from src.customer import career_platform as cp  # noqa: E402

OUTPUT_JSON = "data/hr/output/chatbot/threshold_calibration.json"
OUTPUT_REPORT = "docs/chat_threshold_report.md"

HR_QUERIES = [
    "4대보험 신고를 처음 맡았어요",
    "4대보험 신고 처음이에요",
    "직무급제 도입을 검토 중인데 뭘 알아야 해?",
    "신입사원 온보딩 프로그램을 기획해야 해요",
    "노사협의회 운영 절차가 궁금해요",
    "파이썬으로 인사 데이터 분석하고 싶어요",
    "엑셀 실무 강좌 알려줘",
    "퇴직금 계산이 복잡해요",
    "성희롱 예방교육 법정의무교육 찾아줘",
    "평가 면담을 잘하고 싶어요",
    "채용 공고 쓰는 법을 배우고 싶어요",
    "연말정산 처음 해봐요",
]

NON_HR_QUERIES = [
    "안녕 반가워",
    "오늘 날씨 어때",
    "점심 메뉴 추천해줘",
    "파이썬으로 웹크롤링하는 법",
    "토익 점수 올리는 꿀팁",
    "국내 주식 투자 전략",
    "주말에 드라이브 갈만한 코스",
    "헬스장 초보 분할 운동 루틴",
    "넷플릭스 주말 영화 추천",
    "스마트폰 요금제 알뜰폰 비교",
]


def describe(query: str, tasks) -> dict:
    scores = M.compute_task_scores(query)
    mode = M.classify(scores, M.is_hr_relevant_query(query))
    (s1, sem1, t1), (s2, _, t2) = scores[0], scores[1]
    return {
        "query": query,
        "mode": mode,
        "top1": tasks[t1]["name"],
        "top2": tasks[t2]["name"],
        "score": round(s1, 4),
        "margin": round(s1 - s2, 4),
        "max_sem": round(max(s for _, s, _ in scores), 4),
    }


def main():
    tasks = cp.task_index()
    ids = list(tasks)

    self_rows = []
    for tid in ids:
        scores = M.compute_task_scores(tasks[tid]["name"])
        self_rows.append({
            "task_id": tid,
            "top1_is_self": scores[0][2] == tid,
            "mode": M.classify(scores, M.is_hr_relevant_query(tasks[tid]["name"])),
        })

    result = {
        "settings": {
            "LEX_WEIGHT": M.LEX_WEIGHT,
            "CONFIDENT_SCORE": M.CONFIDENT_SCORE,
            "CONFIDENT_MARGIN": M.CONFIDENT_MARGIN,
            "CANDIDATE_SCORE": M.CANDIDATE_SCORE,
            "OUT_OF_SCOPE_SEM": M.OUT_OF_SCOPE_SEM,
        },
        "self_match": {
            "n": len(self_rows),
            "top1_self": sum(r["top1_is_self"] for r in self_rows),
            "modes": dict(Counter(r["mode"] for r in self_rows)),
        },
        "hr": [describe(q, tasks) for q in HR_QUERIES],
        "non_hr": [describe(q, tasks) for q in NON_HR_QUERIES],
    }
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    write_report(result)
    print(f"saved {OUTPUT_JSON}, {OUTPUT_REPORT}")


def write_report(r: dict):
    st, sm = r["settings"], r["self_match"]
    non_sem = max(x["max_sem"] for x in r["non_hr"])
    hr_sem = min(x["max_sem"] for x in r["hr"])
    lines = [
        "# AI 상담 업무 연결 기준값 점검",
        "",
        "`scripts/calibrate_chat_threshold.py` 실행 결과(`data/hr/output/chatbot/threshold_calibration.json`)에서 숫자를 옮겼습니다.",
        "",
        "## 점수 계산",
        f"- 업무 점수 = 의미 유사도(질문 ↔ 업무명) + {st['LEX_WEIGHT']} × BM25(업무명·쉬운 설명·지식·기술)",
        "- BM25는 90개 업무 안에서 드문 단어에 높은 가중치를 주므로 '직무'·'관리' 같은 흔한 단어 가산점은 두지 않습니다.",
        "",
        "## 결과 종류와 기준값",
        "| 결과 | 조건 | 화면 |",
        "| --- | --- | --- |",
        f"| 업무 연결 | 점수 ≥ {st['CONFIDENT_SCORE']}, 또는 점수 ≥ {st['CANDIDATE_SCORE']}이면서 1·2위 차이 ≥ {st['CONFIDENT_MARGIN']} | 그 업무의 기본 추천 3개 |",
        f"| 업무 후보 | 점수 ≥ {st['CANDIDATE_SCORE']}이지만 1·2위가 비슷함 | 업무 후보 버튼 2개 + 질문 검색 결과 |",
        f"| 검색 | 점수 < {st['CANDIDATE_SCORE']} | 질문 검색 결과 |",
        f"| 범위 밖 | 의미 유사도 최고값 < {st['OUT_OF_SCOPE_SEM']}이고 인사 관련 단어 없음 | 안내 문구만 |",
        "",
        "## 근거",
        f"- 90개 업무명을 그대로 넣었을 때 자기 업무 1위: {sm['top1_self']}/{sm['n']}, 결과 종류: {sm['modes']}",
        f"- 인사와 무관한 질문 {len(r['non_hr'])}개의 의미 유사도 최고값: {non_sem} (범위 밖 기준 {st['OUT_OF_SCOPE_SEM']})",
        f"- 인사 질문 {len(r['hr'])}개의 의미 유사도 최저값: {hr_sem}",
        "- 1·2위 차이 기준은 아래 인사 질문 표에서 업무가 분명한 질문과 1·2위가 비슷한 질문을 가르는 값으로 정했습니다.",
        "  질문 수가 적어서 확정값이 아니며, 애매하면 업무를 단정하지 않고 후보를 보여 주는 쪽으로 정했습니다.",
        "",
        "## 인사 질문",
        "| 질문 | 결과 | 점수 | 1·2위 차이 | 1위 업무 | 2위 업무 |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for x in r["hr"]:
        lines.append(f"| {x['query']} | {x['mode']} | {x['score']} | {x['margin']} | {x['top1']} | {x['top2']} |")
    lines += [
        "",
        "## 인사와 무관한 질문",
        "| 질문 | 결과 | 의미 유사도 최고값 |",
        "| --- | --- | ---: |",
    ]
    for x in r["non_hr"]:
        lines.append(f"| {x['query']} | {x['mode']} | {x['max_sem']} |")
    lines += ["", "1위 업무가 질문 의도에 맞는지는 팀이 판단합니다(이 보고서는 판단을 적지 않습니다).", ""]
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
