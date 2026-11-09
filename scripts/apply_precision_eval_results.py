"""
사람 평가(추천 평가) 결과로 북극성 지표 Precision@3를 계산한다.

입력: data/hr/output/recommendation/precision_eval_results.csv
      구글 시트 '분야–과정 검수 시트'의 '추천 평가' 탭을 그대로 옮긴 것.
      업무×수준 10개 조합 × 추천 Top 3 = 30개 항목, 항목마다 평가자 2명 (김·이·박·홍).
      판정: 적합 / 부분 적합 / 부적합 / 판단 불가 (빈칸은 아직 평가 전)
출력: data/hr/reports/precision_eval_metrics.json, precision_eval_report.md

지표
- A. Precision@3 (판정 단위)     = 적합 ÷ (입력 − 판단 불가)      ← 북극성 지표 (목표 70%)
- B. Precision@3 (항목 합의 단위) = 두 사람 중 낮은 판정 기준 적합 ÷ 판정 항목 수
- C. 두 평가자 일치율 및 코헨 카파: 두 사람이 모두 입력한 항목의 일치도
평가가 덜 끝났으면 status를 '중간'으로 표시한다. 다 끝나면 이 스크립트를 다시 실행한다.
실행: python scripts/apply_precision_eval_results.py
      2차·홀드아웃 평가: python scripts/apply_precision_eval_results.py --round round2   (또는 holdout)
        입력 precision_eval_<round>_results.csv → 출력 precision_eval_<round>_metrics.json, _report.md
"""
import argparse
import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
OUT_JSON = ROOT / "data" / "hr" / "reports" / "precision_eval_metrics.json"
OUT_MD = ROOT / "data" / "hr" / "reports" / "precision_eval_report.md"
TARGET = 0.70  # 발표 01장 '사람이 봐도 맞다' 목표
LABELS = ["적합", "부분 적합", "부적합", "판단 불가"]


def pct(a, b):
    return round(a / b * 100, 1) if b else None


def wilson_ci(k, n, z=1.95996):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return [round(lower * 100, 1), round(upper * 100, 1)]


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
    done = df[df["judgment"] != ""].copy()
    overall = precision(done["judgment"])

    # A 신뢰구간: Wilson & Item Cluster Bootstrap
    judged_a = done[done["judgment"].isin(["적합", "부분 적합", "부적합"])]
    fit_a = int((judged_a["judgment"] == "적합").sum())
    n_a = len(judged_a)
    ci95_wilson = wilson_ci(fit_a, n_a)

    rng = np.random.default_rng(42)
    item_stats_a = {item_no: ((g["judgment"] == "적합").sum(), len(g)) for item_no, g in judged_a.groupby("item_no")}
    item_keys_a = list(item_stats_a.keys())
    fit_arr_a = np.array([item_stats_a[k][0] for k in item_keys_a])
    tot_arr_a = np.array([item_stats_a[k][1] for k in item_keys_a])
    n_items_a = len(item_keys_a)
    resamples_a = rng.choice(n_items_a, size=(10000, n_items_a), replace=True)
    res_fits_a = fit_arr_a[resamples_a].sum(axis=1)
    res_tots_a = tot_arr_a[resamples_a].sum(axis=1)
    boot_strict_a = res_fits_a / res_tots_a * 100
    ci95_cluster_bootstrap = [round(float(np.percentile(boot_strict_a, 2.5)), 1),
                              round(float(np.percentile(boot_strict_a, 97.5)), 1)]

    overall["ci95_wilson"] = ci95_wilson
    overall["ci95_cluster_bootstrap"] = ci95_cluster_bootstrap

    raters = []
    for r, g in df.groupby("rater", sort=False):
        c = g["judgment"].value_counts()
        raters.append({"rater": r, "assigned": len(g), "entered": int((g["judgment"] != "").sum()),
                       **{lab: int(c.get(lab, 0)) for lab in LABELS}})

    # 두 평가자 일치 (같은 항목을 두 사람이 모두 입력한 경우)
    pairs = done.groupby("item_no")["judgment"].agg(list)
    both = pairs[pairs.map(len) == 2]
    agree = int(both.map(lambda x: x[0] == x[1]).sum())
    r1 = [p[0] for p in both]
    r2 = [p[1] for p in both]
    kappa = round(float(cohen_kappa_score(r1, r2, labels=LABELS)), 3) if len(both) > 0 else 0.0

    # B. 항목 단위 결론 (합의 기준): 두 사람 판정 중 낮은 쪽(보수적)을 항목 판정으로 씀
    rank_of = {"적합": 2, "부분 적합": 1, "부적합": 0}
    inv = {v: k for k, v in rank_of.items()}
    item = (done[done["judgment"].isin(rank_of)]
            .assign(score=lambda x: x["judgment"].map(rank_of))
            .groupby(["item_no", "domain", "task", "level", "rank", "title", "provider"], as_index=False)
            .agg(score=("score", "min"), raters=("rater", lambda s: "·".join(s))))
    item["judgment"] = item["score"].map(inv)
    item["item_no"] = item["item_no"].astype(int)
    item = item.sort_values("item_no")

    # B task-level cluster bootstrap (10,000 resamples, random_state=42)
    task_stats_b = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in item.groupby("task")}
    t_list_b = list(task_stats_b.keys())
    t_fit_arr_b = np.array([task_stats_b[k][0] for k in t_list_b])
    t_tot_arr_b = np.array([task_stats_b[k][1] for k in t_list_b])
    n_tasks_b = len(t_list_b)
    t_resamples_b = rng.choice(n_tasks_b, size=(10000, n_tasks_b), replace=True)
    t_res_fits_b = t_fit_arr_b[t_resamples_b].sum(axis=1)
    t_res_tots_b = t_tot_arr_b[t_resamples_b].sum(axis=1)
    boot_strict_b = t_res_fits_b / t_res_tots_b * 100
    ci95_task_bootstrap = [round(float(np.percentile(boot_strict_b, 2.5)), 1),
                           round(float(np.percentile(boot_strict_b, 97.5)), 1)]

    items_total = int(df["item_no"].nunique())
    items_rated = int(item["item_no"].nunique())
    fit_b = int((item["judgment"] == "적합").sum())
    consensus = {
        "items_total": items_total,
        "items_rated": items_rated,
        "both_unclear": items_total - items_rated,
        "fit": fit_b,
        "partial": int((item["judgment"] == "부분 적합").sum()),
        "unfit": int((item["judgment"] == "부적합").sum()),
        "strict": pct(fit_b, items_rated),
        "ci95_task_bootstrap": ci95_task_bootstrap,
    }

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
        "items_total": items_total, "items_rated": items_rated,
        "precision_at_3": overall, "target_pct": TARGET * 100,
        "meets_target": (overall["strict"] or 0) >= TARGET * 100,
        "agreement": {"pairs": int(len(both)), "agree": agree, "pct": pct(agree, len(both)), "cohen_kappa": kappa},
        "consensus": consensus,
        "ci95_wilson": ci95_wilson,
        "ci95_cluster_bootstrap": ci95_cluster_bootstrap,
        "raters": raters, "by_rank": by_rank, "by_task": by_task,
        "unfit_items": item.loc[item["judgment"] == "부적합", ["item_no", "task", "title", "provider"]].to_dict("records"),
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    p = overall
    lines = [
        f"# 사람 평가 결과: Precision@3 — {result['round']} ({result['status']}, {result['checked']})",
        "",
        f"추천 Top 3 {items_total}개 항목을 두 사람씩 판정하는 평가에서 {assigned}건 중 {entered}건이 입력됐다"
        + (" (평가가 아직 끝나지 않은 중간 결과)." if result["status"] == "중간" else ".")
        + f" 판정된 {p['n']}건 기준 **Precision@3(적합만, A) {p['strict']}%**, 적합+부분 적합 {p['lenient']}%다."
        f" 목표 {TARGET * 100:.0f}%에 {'도달했다' if result['meets_target'] else '못 미친다'}.",
        "",
        "## 핵심 지표 종합 (A · B · C)",
        "",
        f"- **A. 판정 단위 Precision@3 (평가 건 기준, n={p['n']})**: **{p['strict']}%**"
        f" (Wilson 95%: {ci95_wilson[0]}~{ci95_wilson[1]}%, 항목 클러스터 부트스트랩 95%: {ci95_cluster_bootstrap[0]}~{ci95_cluster_bootstrap[1]}%)",
        f"- **B. 항목 합의 Precision@3 (아이템 기준 보수적, n={items_rated})**: **{consensus['strict']}%**"
        f" ({fit_b}/{items_rated}개 항목 적합, 업무 클러스터 부트스트랩 95%: {ci95_task_bootstrap[0]}~{ci95_task_bootstrap[1]}%)"
        + (f" [둘 다 판단 불가 {consensus['both_unclear']}개 제외]" if consensus['both_unclear'] > 0 else ""),
        f"- **C. 평가자 간 일치도**: 일치율 **{result['agreement']['pct']}%** ({agree}/{result['agreement']['pairs']}쌍 일치), 코헨 카파(Cohen's Kappa) **κ={kappa}**",
        "",
        "> **지표 구분 및 차이 설명**  ",
        "> - **A (판정 단위)**는 평가자 4명의 개별 평가 건(n=55 등)을 독립된 관측치로 집계한 지표입니다. 평가자 한 명이 적합으로 판단한 건도 분자에 반영됩니다.  ",
        "> - **B (항목 합의 단위)**는 추천 항목(과정) 하나에 대해 두 평가자의 판정 중 **더 낮은(보수적인) 판정**을 채택한 지표입니다. 두 사람 모두 '적합'으로 합의해야 적합으로 인정되므로 A보다 엄격하며 수치가 더 낮게 산출됩니다.  ",
        "> - **C (평가자 일치도)**는 두 평가자의 판정 일치율과 우연에 의한 일치를 보정한 코헨 카파 지수입니다. 동일 항목을 두 평가자가 중복 채점하므로 신뢰구간 산출 시 클러스터 부트스트랩을 적용해 독립성 위반을 보정합니다.",
        "",
        "## 평가자별",
        "",
        "| 평가자 | 배정 | 입력 | 적합 | 부분 적합 | 부적합 | 판단 불가 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ] + [f"| {r['rater']} | {r['assigned']} | {r['entered']} | {r['적합']} | {r['부분 적합']} | {r['부적합']} | {r['판단 불가']} |"
         for r in raters] + [
        "",
        f"두 사람이 모두 입력한 항목은 {result['agreement']['pairs']}개이고 그중 {result['agreement']['agree']}개가 같은 판정이다"
        + (f" (일치율 {result['agreement']['pct']}%, 코헨 카파 κ={kappa})." if result["agreement"]["pairs"] else "."),
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
    print(f"[{result['round']}] Done -> {OUT_JSON.name}, {OUT_MD.name}")


if __name__ == "__main__":
    main()
