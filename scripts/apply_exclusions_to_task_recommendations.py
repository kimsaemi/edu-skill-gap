"""
이미 계산된 업무별 추천(task_course_recommendations_90.csv)에서 제외 목록(off_topic_exclusions.csv)에 오른 강좌를 빼고
순위를 다시 매깁니다. 추천 엔진을 다시 돌리지 않고 결과만 정리할 때 씁니다.

언제 쓰나
  - build_off_topic_exclusions.py로 제외 규칙을 바꿨는데, 임베딩 모델(Ko-SRoBERTa)을 내려받을 수 없는 환경일 때.
  - 모델을 쓸 수 있으면 대신 `python scripts/build_hr_task_catalog.py --reuse-catalog`로 다시 계산하는 것이 낫습니다.
    엔진이 제외 목록을 읽어 후보에서 빼고 남은 후보로 Top 5를 다시 채웁니다. 이 스크립트는 저장된 Top 5 안에서만
    빼므로, 빠진 자리가 채워지지 않아 결과가 3개 미만인 업무·숙련도가 생길 수 있습니다.

바꾸는 파일
  - data/hr/output/recommendation/task_course_recommendations_90.csv      (제외 강좌 행 삭제, rank 다시 매김)
  - data/hr/output/recommendation/task_course_recommendations_90_summary.json (요약 다시 계산)
  - 뺀 행은 data/hr/output/recommendation/task_course_recommendations_90_removed.csv 에 사유와 함께 남깁니다.

실행: python scripts/build_off_topic_exclusions.py && python scripts/apply_exclusions_to_task_recommendations.py
여러 번 실행해도 결과가 같습니다(이미 뺀 행은 다시 빼지 않음).
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RECO = ROOT / "data" / "hr" / "output" / "recommendation"
REC_PATH = RECO / "task_course_recommendations_90.csv"
SUMMARY_PATH = RECO / "task_course_recommendations_90_summary.json"
REMOVED_PATH = RECO / "task_course_recommendations_90_removed.csv"
EXCL_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
LEVELS = ["입문", "실무", "관리자·심화"]


def main() -> int:
    rec = pd.read_csv(REC_PATH, encoding="utf-8-sig")
    excl = pd.read_csv(EXCL_PATH, encoding="utf-8-sig", dtype=str)
    reason = dict(zip(excl["course_uid"], excl["reason"]))

    hit = rec["course_uid"].astype(str).isin(reason)
    removed = rec[hit].assign(removed_reason=rec.loc[hit, "course_uid"].astype(str).map(reason))
    if REMOVED_PATH.exists():
        removed = pd.concat([pd.read_csv(REMOVED_PATH, encoding="utf-8-sig"), removed]).drop_duplicates(
            subset=["task_id", "level", "course_uid"])
    removed.to_csv(REMOVED_PATH, index=False, encoding="utf-8-sig")

    rec = rec[~hit].copy()
    rec["rank"] = rec.groupby(["task_id", "level"])["final_score"].rank(ascending=False, method="first").astype(int)
    rec = rec.sort_values(["task_id", "level", "rank"]).reset_index(drop=True)
    rec.to_csv(REC_PATH, index=False, encoding="utf-8-sig")

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    top3 = rec[rec["rank"] <= 3]
    use = Counter(top3["course_uid"])
    title_of = dict(zip(rec["course_uid"], rec["title"]))
    per_task_level = top3.groupby(["task_id", "level"]).size()
    n_tasks = summary.get("task_count", rec["task_id"].nunique())
    summary.update({
        "top3_slots": int(len(top3)),
        "top3_distinct_courses": len(use),
        "top3_most_reused": [{"title": title_of[u], "count": n} for u, n in use.most_common(10)],
        "task_level_with_lt3_results": int((per_task_level < 3).sum()) + (n_tasks * len(LEVELS) - len(per_task_level)),
        "top1_semantic_score_median": float(rec[rec["rank"] == 1]["semantic_score"].median()),
        "top1_semantic_score_min": float(rec[rec["rank"] == 1]["semantic_score"].min()),
        "excluded_after_engine": {
            "rows_removed": int(len(removed)),
            "by_reason": removed["removed_reason"].value_counts().to_dict(),
            "note": "인사 범위·팀원 검수에 따른 제외를 저장된 결과에서 적용함. 모델을 쓸 수 있는 PC에서 "
                    "build_hr_task_catalog.py --reuse-catalog로 다시 계산하면 빈자리가 채워짐",
        },
    })
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[제외 반영] 이번에 뺀 행 {int(hit.sum())}건 (누적 {len(removed)}건)")
    print(removed["removed_reason"].value_counts().to_string())
    print(f"Top3 슬롯 {len(top3)}개, 3개 미만인 업무·숙련도 {summary['task_level_with_lt3_results']}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
