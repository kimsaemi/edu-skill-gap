"""
사람 평가(추천 평가) 결과로 북극성 지표 Precision@3를 계산한다.

입력: data/hr/output/recommendation/precision_eval_results.csv
      구글 시트 '분야–과정 검수 시트'의 '추천 평가' 탭을 그대로 옮긴 것.
      업무×수준 10개 조합 × 추천 Top 3 = 30개 항목, 항목마다 평가자 2명 (김·이·박·홍).
      판정: 적합 / 부분 적합 / 부적합 / 판단 불가 (빈칸은 아직 평가 전)
출력: data/hr/reports/precision_eval_metrics.json, precision_eval_report.md

지표
- Precision@3 (적합만)        = 적합 ÷ (입력 − 판단 불가)      ← 북극성 지표 (목표 70%)
- Precision@3 (적합+부분 적합) = (적합 + 부분 적합) ÷ (입력 − 판단 불가)
- 두 평가자 일치율: 두 사람이 모두 입력한 항목 중 같은 판정을 고른 비율
평가가 덜 끝났으면 status를 '중간'으로 표시한다. 다 끝나면 이 스크립트를 다시 실행한다.
실행: python scripts/apply_precision_eval_results.py
      2차·홀드아웃 평가: python scripts/apply_precision_eval_results.py --round round2   (또는 holdout)
        입력 precision_eval_<round>_results.csv → 출력 precision_eval_<round>_metrics.json, _report.md
"""
import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
OUT_JSON = ROOT / "data" / "hr" / "reports" / "precision_eval_metrics.json"
OUT_MD = ROOT / "data" / "hr" / "reports" / "precision_eval_report.md"
TARGET = 0.70  # 발표 01장 '사람이 봐도 맞다' 목표
LABELS = ["적합", "부분 적합", "부적합", "판단 불가"]


def pct(a, b):
    return round(a / b * 100, 1) if b else None


def precision(s):
    judged = s[s.isin(["적합", "부분 적합", "부적합"])]
    n = len(judged)
    return {"n": n, "strict": pct(int((judged == "적합").sum()), n),
            "lenient": pct(int(judged.isin(["적합", "부분 적합"]).sum()), n)}


ROUND_TITLES = {"": "1차", "round2": "2차 (SAP·QA·전산회계 제외 후 같은 업무 10개)",
                "holdout": "홀드아웃 (처음 보는 업무 10개)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="", choices=list(ROUND_TITLES), help="빈값=1차, round2, holdout")
    rnd = ap.parse_args().round
    global SRC, OUT_JSON, OUT_MD
    if rnd:
        SRC = SRC.with_name(f"precision_eval_{rnd}_results.csv")
        OUT_JSON = OUT_JSON.with_name(f"precision_eval_{rnd}_metrics.json")
        OUT_MD = OUT_MD.with_name(f"precision_eval_{rnd}_report.md")
    df = pd.read_csv(SRC, dtype=str).fillna("")
    done = df[df["judgment"] != ""]
    overall = precision(done["judgment"])

    raters = []
    for r, g in df.groupby("rater", sort=False):
        c = g["judgment"].value_counts()
        raters.append({"rater": r, "assigned": len(g), "entered": int((g["judgment"] != "").sum()),
                       **{lab: int(c.get(lab, 0)) for lab in LABELS}})

    # 두 평가자 일치 (같은 항목을 두 사람이 모두 입력한 경우)
    pairs = done.groupby("item_no")["judgment"].agg(list)
    both = pairs[pairs.map(len) == 2]
    agree = int(both.map(lambda x: x[0] == x[1]).sum())

    # 항목 단위 결론: 두 사람 판정 중 낮은 쪽(보수적)을 항목 판정으로 씀
    rank_of = {"적합": 2, "부분 적합": 1, "부적합": 0}
    item = (done[done["judgment"].isin(rank_of)]
            .assign(score=lambda x: x["judgment"].map(rank_of))
            .groupby(["item_no", "domain", "task", "level", "rank", "title", "provider"], as_index=False)
            .agg(score=("score", "min"), raters=("rater", lambda s: "·".join(s))))
    inv = {v: k for k, v in rank_of.items()}
    item["judgment"] = item["score"].map(inv)
    item["item_no"] = item["item_no"].astype(int)
    item = item.sort_values("item_no")

    by_task = []
    for (dom, task, lvl), g in item.groupby(["domain", "task", "level"], sort=False):
        by_task.append({"domain": dom, "task": task, "level": lvl, "items": len(g),
                        "fit": int((g["judgment"] == "적합").sum()), "partial": int((g["judgment"] == "부분 적합").sum()),
                        "unfit": int((g["judgment"] == "부적합").sum())})
    by_rank = {r: precision(done.loc[done["rank"] == r, "judgment"]) for r in ["1", "2", "3"]}

    entered, assigned = len(done), len(df)
    result = {
        "round": ROUND_TITLES[rnd],
        "checked": date.today().isoformat(),
        "status": "완료" if entered == assigned else "중간",
        "entered": entered, "assigned": assigned,
        "items_total": int(df["item_no"].nunique()), "items_rated": int(item["item_no"].nunique()),
        "precision_at_3": overall, "target_pct": TARGET * 100,
        "meets_target": (overall["strict"] or 0) >= TARGET * 100,
        "agreement": {"pairs": int(len(both)), "agree": agree, "pct": pct(agree, len(both))},
        "raters": raters, "by_rank": by_rank, "by_task": by_task,
        "unfit_items": item.loc[item["judgment"] == "부적합", ["item_no", "task", "title", "provider"]].to_dict("records"),
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    p = overall
    lines = [
        f"# 사람 평가 결과: Precision@3 — {result['round']} ({result['status']}, {result['checked']})",
        "",
        f"추천 Top 3 30개 항목을 두 사람씩 판정하는 평가에서 {assigned}건 중 {entered}건이 입력됐다"
        + (" (평가가 아직 끝나지 않은 중간 결과)." if result["status"] == "중간" else ".")
        + f" 판정된 {p['n']}건 기준 **Precision@3(적합만) {p['strict']}%**, 적합+부분 적합 {p['lenient']}%다."
        f" 목표 {TARGET * 100:.0f}%에 {'도달했다' if result['meets_target'] else '못 미친다'}.",
        "",
        "## 평가자별",
        "",
        "| 평가자 | 배정 | 입력 | 적합 | 부분 적합 | 부적합 | 판단 불가 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ] + [f"| {r['rater']} | {r['assigned']} | {r['entered']} | {r['적합']} | {r['부분 적합']} | {r['부적합']} | {r['판단 불가']} |"
         for r in raters] + [
        "",
        f"두 사람이 모두 입력한 항목은 {result['agreement']['pairs']}개이고 그중 {result['agreement']['agree']}개가 같은 판정이다"
        + (f" (일치율 {result['agreement']['pct']}%)." if result["agreement"]["pairs"] else "."),
        "",
        "## 순위별 Precision",
        "",
        "| 순위 | 판정 수 | 적합만 | 적합+부분 적합 |",
        "| --- | ---: | ---: | ---: |",
    ] + [f"| {r}위 | {v['n']} | {v['strict']}% | {v['lenient']}% |" for r, v in by_rank.items()] + [
        "",
        "## 업무별 (항목 판정은 두 사람 중 낮은 쪽)",
        "",
        "| 분야 | 업무 | 수준 | 적합 | 부분 적합 | 부적합 |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ] + [f"| {t['domain']} | {t['task']} | {t['level']} | {t['fit']} | {t['partial']} | {t['unfit']} |" for t in by_task] + [
        "",
        "## 부적합으로 판정된 추천",
        "",
    ] + [f"- {u['item_no']}번 {u['task']} → {u['title']} ({u['provider']})" for u in result["unfit_items"]] + [""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
