# -*- coding: utf-8 -*-
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

실행:
  python scripts/apply_precision_eval_results.py
  python scripts/apply_precision_eval_results.py --round round2
  python scripts/apply_precision_eval_results.py --round holdout
  python scripts/apply_precision_eval_results.py --round holdout2
  python scripts/apply_precision_eval_results.py --round holdout_all
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
    return {
        "n": n,
        "strict": pct(int((judged == "적합").sum()), n),
        "lenient": pct(int(judged.isin(["적합", "부분 적합"]).sum()), n),
    }


ROUND_TITLES = {
    "": "1차",
    "round2": "2차 (SAP·QA·전산회계 제외 후 같은 업무 10개)",
    "holdout": "홀드아웃 (처음 보는 업무 10개)",
    "holdout2": "홀드아웃 2차 (키워드 추천 대조군 + 위약 검정 포함 10개 업무)",
    "holdout_all": "홀드아웃 전체 (1차+2차 통합 20개 업무)",
}


def calculate_holdout2_metrics(df, df_key, rng=None):
    """홀드아웃 2차 결과 분석: 최종 추천 vs BM25 추천 Precision@3 비교 및 위약 검정"""
    if rng is None:
        rng = np.random.default_rng(42)

    df = df.copy()
    df_key = df_key.copy()
    df["item_id"] = df["item_id"].astype(int)
    df_key["item_id"] = df_key["item_id"].astype(int)

    merged = df.merge(df_key[["item_id", "source", "decoy_origin_task_id"]], on="item_id", how="left")
    done = merged[merged["judgment"].fillna("") != ""].copy()
    entered = len(done)
    assigned = len(merged)

    # Decoy Analysis
    decoy_df = done[done["source"] == "decoy"]
    total_decoy_evals = len(decoy_df)
    unfit_decoy_cnt = int((decoy_df["judgment"] == "부적합").sum())
    passed_decoy_df = decoy_df[decoy_df["judgment"].isin(["적합", "부분 적합"])]
    passed_decoy_cnt = len(passed_decoy_df)

    decoy_analysis = {
        "total_items": int(df_key[df_key["source"] == "decoy"]["item_id"].nunique()),
        "total_evaluations": total_decoy_evals,
        "unfit_count": unfit_decoy_cnt,
        "filter_success_rate": pct(unfit_decoy_cnt, total_decoy_evals) if total_decoy_evals else None,
        "passed_count": passed_decoy_cnt,
        "passed_rate": pct(passed_decoy_cnt, total_decoy_evals) if total_decoy_evals else None,
        "false_positives": [
            {
                "item_id": int(r["item_id"]),
                "rater": r["rater"],
                "task": r["task"],
                "title": r["title"],
                "judgment": r["judgment"],
            }
            for _, r in passed_decoy_df.iterrows()
        ],
    }

    def compute_subset_metrics(sub_done, sub_all):
        if len(sub_done) == 0:
            return {
                "precision_at_3": {"n": 0, "strict": None, "lenient": None, "ci95_wilson": [0.0, 0.0], "ci95_cluster_bootstrap": [0.0, 0.0]},
                "consensus": {"items_total": int(sub_all["item_id"].nunique()), "items_rated": 0, "strict": None, "ci95_task_bootstrap": [0.0, 0.0]},
                "item_df": pd.DataFrame(),
            }

        p_a = precision(sub_done["judgment"])
        judged_a = sub_done[sub_done["judgment"].isin(["적합", "부분 적합", "부적합"])]
        fit_a = int((judged_a["judgment"] == "적합").sum())
        n_a = len(judged_a)
        ci_w = wilson_ci(fit_a, n_a)

        item_stats_a = {item_no: ((g["judgment"] == "적합").sum(), len(g)) for item_no, g in judged_a.groupby("item_id")}
        item_keys_a = list(item_stats_a.keys())
        if len(item_keys_a) > 0 and n_a > 0:
            fit_arr_a = np.array([item_stats_a[k][0] for k in item_keys_a])
            tot_arr_a = np.array([item_stats_a[k][1] for k in item_keys_a])
            n_items_a = len(item_keys_a)
            resamples_a = rng.choice(n_items_a, size=(5000, n_items_a), replace=True)
            res_fits_a = fit_arr_a[resamples_a].sum(axis=1)
            res_tots_a = tot_arr_a[resamples_a].sum(axis=1)
            valid_b = res_tots_a > 0
            boot_strict_a = np.where(valid_b, res_fits_a / np.maximum(res_tots_a, 1) * 100, 0.0)
            ci_cb = [round(float(np.percentile(boot_strict_a, 2.5)), 1), round(float(np.percentile(boot_strict_a, 97.5)), 1)]
        else:
            ci_cb = [0.0, 0.0]

        p_a["ci95_wilson"] = ci_w
        p_a["ci95_cluster_bootstrap"] = ci_cb

        # Consensus B
        rank_of = {"적합": 2, "부분 적합": 1, "부적합": 0}
        inv = {v: k for k, v in rank_of.items()}
        item = (
            sub_done[sub_done["judgment"].isin(rank_of)]
            .assign(score=lambda x: x["judgment"].map(rank_of))
            .groupby(["item_id", "domain", "task", "level", "title", "provider"], as_index=False)
            .agg(score=("score", "min"), raters=("rater", lambda s: "·".join(s)))
        )
        item["judgment"] = item["score"].map(inv)

        task_stats_b = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in item.groupby("task")}
        t_list_b = list(task_stats_b.keys())
        if len(t_list_b) > 0 and len(item) > 0:
            t_fit_arr_b = np.array([task_stats_b[k][0] for k in t_list_b])
            t_tot_arr_b = np.array([task_stats_b[k][1] for k in t_list_b])
            n_tasks_b = len(t_list_b)
            t_resamples_b = rng.choice(n_tasks_b, size=(5000, n_tasks_b), replace=True)
            t_res_fits_b = t_fit_arr_b[t_resamples_b].sum(axis=1)
            t_res_tots_b = t_tot_arr_b[t_resamples_b].sum(axis=1)
            valid_tb = t_res_tots_b > 0
            boot_strict_b = np.where(valid_tb, t_res_fits_b / np.maximum(t_res_tots_b, 1) * 100, 0.0)
            ci_tb = [round(float(np.percentile(boot_strict_b, 2.5)), 1), round(float(np.percentile(boot_strict_b, 97.5)), 1)]
        else:
            ci_tb = [0.0, 0.0]

        items_total = int(sub_all["item_id"].nunique())
        items_rated = int(item["item_id"].nunique())
        fit_b = int((item["judgment"] == "적합").sum())
        consensus = {
            "items_total": items_total,
            "items_rated": items_rated,
            "both_unclear": items_total - items_rated,
            "fit": fit_b,
            "partial": int((item["judgment"] == "부분 적합").sum()),
            "unfit": int((item["judgment"] == "부적합").sum()),
            "strict": pct(fit_b, items_rated),
            "ci95_task_bootstrap": ci_tb,
        }
        return {"precision_at_3": p_a, "consensus": consensus, "item_df": item}

    final_sub_done = done[done["source"].isin(["final_top3", "both"])]
    final_sub_all = merged[merged["source"].isin(["final_top3", "both"])]
    final_res = compute_subset_metrics(final_sub_done, final_sub_all)

    bm25_sub_done = done[done["source"].isin(["bm25_top3", "both"])]
    bm25_sub_all = merged[merged["source"].isin(["bm25_top3", "both"])]
    bm25_res = compute_subset_metrics(bm25_sub_done, bm25_sub_all)

    # Difference bootstrap (Final - BM25)
    all_tasks = sorted(set(final_sub_done["task"]) | set(bm25_sub_done["task"]))
    n_tasks = len(all_tasks)
    diff_a = None
    ci95_diff_a = None
    diff_b = None
    ci95_diff_b = None

    if final_res["precision_at_3"]["strict"] is not None and bm25_res["precision_at_3"]["strict"] is not None:
        diff_a = round(final_res["precision_at_3"]["strict"] - bm25_res["precision_at_3"]["strict"], 1)

    if final_res["consensus"]["strict"] is not None and bm25_res["consensus"]["strict"] is not None:
        diff_b = round(final_res["consensus"]["strict"] - bm25_res["consensus"]["strict"], 1)

    if n_tasks > 0 and len(final_sub_done) > 0 and len(bm25_sub_done) > 0:
        task_f_a = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in final_sub_done[final_sub_done["judgment"].isin(["적합", "부분 적합", "부적합"])].groupby("task")}
        task_b_a = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in bm25_sub_done[bm25_sub_done["judgment"].isin(["적합", "부분 적합", "부적합"])].groupby("task")}

        resamp = rng.choice(n_tasks, size=(5000, n_tasks), replace=True)
        task_arr = np.array(all_tasks)

        boot_diff_a = []
        for idxs in resamp:
            sampled_tasks = task_arr[idxs]
            f_fit = sum(task_f_a.get(t, (0, 0))[0] for t in sampled_tasks)
            f_tot = sum(task_f_a.get(t, (0, 0))[1] for t in sampled_tasks)
            b_fit = sum(task_b_a.get(t, (0, 0))[0] for t in sampled_tasks)
            b_tot = sum(task_b_a.get(t, (0, 0))[1] for t in sampled_tasks)
            if f_tot > 0 and b_tot > 0:
                boot_diff_a.append((f_fit / f_tot - b_fit / b_tot) * 100)

        if boot_diff_a:
            ci95_diff_a = [round(float(np.percentile(boot_diff_a, 2.5)), 1), round(float(np.percentile(boot_diff_a, 97.5)), 1)]

        # Task-level bootstrap for difference B
        item_f = final_res["item_df"]
        item_b = bm25_res["item_df"]
        if not item_f.empty and not item_b.empty:
            t_f_b = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in item_f.groupby("task")}
            t_b_b = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in item_b.groupby("task")}
            boot_diff_b = []
            for idxs in resamp:
                sampled_tasks = task_arr[idxs]
                f_fit_b = sum(t_f_b.get(t, (0, 0))[0] for t in sampled_tasks)
                f_tot_b = sum(t_f_b.get(t, (0, 0))[1] for t in sampled_tasks)
                b_fit_b = sum(t_b_b.get(t, (0, 0))[0] for t in sampled_tasks)
                b_tot_b = sum(t_b_b.get(t, (0, 0))[1] for t in sampled_tasks)
                if f_tot_b > 0 and b_tot_b > 0:
                    boot_diff_b.append((f_fit_b / f_tot_b - b_fit_b / b_tot_b) * 100)
            if boot_diff_b:
                ci95_diff_b = [round(float(np.percentile(boot_diff_b, 2.5)), 1), round(float(np.percentile(boot_diff_b, 97.5)), 1)]

    comparison = {
        "diff_strict_a": diff_a,
        "ci95_diff_a": ci95_diff_a,
        "diff_strict_b": diff_b,
        "ci95_diff_b": ci95_diff_b,
    }

    raters = []
    for r, g in df.groupby("rater", sort=False):
        c = g["judgment"].value_counts()
        raters.append({
            "rater": r,
            "assigned": len(g),
            "entered": int((g["judgment"] != "").sum()),
            **{lab: int(c.get(lab, 0)) for lab in LABELS},
        })

    result = {
        "round": "홀드아웃 2차 (키워드 추천 대조군 + 위약 검정 포함 10개 업무)",
        "checked": date.today().isoformat(),
        "status": "완료" if entered == assigned and entered > 0 else "중간",
        "entered": entered,
        "assigned": assigned,
        "final_recommendation": {
            "precision_at_3": final_res["precision_at_3"],
            "consensus": final_res["consensus"],
        },
        "bm25_recommendation": {
            "precision_at_3": bm25_res["precision_at_3"],
            "consensus": bm25_res["consensus"],
        },
        "comparison": comparison,
        "decoy_analysis": decoy_analysis,
        "raters": raters,
        # top level shortcuts for compatibility
        "precision_at_3": final_res["precision_at_3"],
        "consensus": final_res["consensus"],
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="", choices=list(ROUND_TITLES), help="빈값=1차, round2, holdout, holdout2, holdout_all")
    rnd = ap.parse_args().round
    global SRC, OUT_JSON, OUT_MD

    if rnd == "holdout2":
        SRC = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_results.csv"
        KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_key.csv"
        ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_items.csv"
        OUT_JSON = ROOT / "data" / "hr" / "reports" / "precision_eval_holdout2_metrics.json"
        OUT_MD = ROOT / "data" / "hr" / "reports" / "precision_eval_holdout2_report.md"

        if SRC.exists():
            df = pd.read_csv(SRC, dtype=str).fillna("")
        elif ITEMS_PATH.exists():
            df = pd.read_csv(ITEMS_PATH, dtype=str).fillna("")
        else:
            raise FileNotFoundError(f"Neither {SRC} nor {ITEMS_PATH} found.")

        if not KEY_PATH.exists():
            raise FileNotFoundError(f"Key file {KEY_PATH} not found.")
        df_key = pd.read_csv(KEY_PATH)

        result = calculate_holdout2_metrics(df, df_key)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        # Report MD
        fin_p = result["final_recommendation"]["precision_at_3"]
        fin_c = result["final_recommendation"]["consensus"]
        bm_p = result["bm25_recommendation"]["precision_at_3"]
        bm_c = result["bm25_recommendation"]["consensus"]
        cmp = result["comparison"]
        dec = result["decoy_analysis"]

        lines = [
            f"# 사람 평가 결과: 홀드아웃 2차 ({result['status']}, {result['checked']})",
            "",
            "## 1. 최종 추천 vs 키워드(BM25) 비교",
            "",
            "| 구분 | A. 판정 단위 Precision@3 (Wilson 95%) | B. 항목 합의 Precision@3 (부트스트랩 95%) |",
            "| :--- | :---: | :---: |",
            f"| **최종 추천 (하이브리드+리랭커)** | {fin_p['strict']}% ({fin_p['ci95_wilson'][0]}~{fin_p['ci95_wilson'][1]}%) | {fin_c['strict']}% ({fin_c['ci95_task_bootstrap'][0]}~{fin_c['ci95_task_bootstrap'][1]}%) |",
            f"| **대조군 (BM25 키워드 단독)** | {bm_p['strict']}% ({bm_p['ci95_wilson'][0]}~{bm_p['ci95_wilson'][1]}%) | {bm_c['strict']}% ({bm_c['ci95_task_bootstrap'][0]}~{bm_c['ci95_task_bootstrap'][1]}%) |",
            f"| **성능 차이 (최종 - BM25)** | **{cmp['diff_strict_a']}%p** ({cmp['ci95_diff_a'][0] if cmp['ci95_diff_a'] else '-'}~{cmp['ci95_diff_a'][1] if cmp['ci95_diff_a'] else '-'}%p) | **{cmp['diff_strict_b']}%p** ({cmp['ci95_diff_b'][0] if cmp['ci95_diff_b'] else '-'}~{cmp['ci95_diff_b'][1] if cmp['ci95_diff_b'] else '-'}%p) |",
            "",
            "## 2. 위약(가짜 추천) 검정 결과",
            "",
            f"- **전체 위약 평가 건수**: {dec['total_evaluations']}건 ({dec['total_items']}개 과정)",
            f"- **부적합 판정 정상 차단율**: **{dec['filter_success_rate']}%** ({dec['unfit_count']}/{dec['total_evaluations']}건)",
            f"- **오판정(적합/부분 적합) 통과율**: **{dec['passed_rate']}%** ({dec['passed_count']}/{dec['total_evaluations']}건)",
        ]
        if dec["false_positives"]:
            lines += ["", "### 위약 오판정 상세 내역:"]
            for fp in dec["false_positives"]:
                lines.append(f"- [{fp['judgment']}] 평가자 {fp['rater']}: {fp['task']} → {fp['title']}")

        OUT_MD.write_text("\n".join(lines), encoding="utf-8")
        print(f"[{result['round']}] Done -> {OUT_JSON.name}, {OUT_MD.name}")
        return

    if rnd == "holdout_all":
        # Combine Holdout 1 and Holdout 2 (Final recommendations only)
        H1_SRC = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_results.csv"
        H2_SRC = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_results.csv"
        KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_key.csv"
        OUT_JSON = ROOT / "data" / "hr" / "reports" / "precision_eval_holdout_all_metrics.json"
        OUT_MD = ROOT / "data" / "hr" / "reports" / "precision_eval_holdout_all_report.md"

        if not H1_SRC.exists():
            raise FileNotFoundError(f"{H1_SRC} not found")

        df_h1 = pd.read_csv(H1_SRC, dtype=str).fillna("")
        df_h1["holdout_round"] = 1

        if H2_SRC.exists() and KEY_PATH.exists():
            df_h2 = pd.read_csv(H2_SRC, dtype=str).fillna("")
            df_k = pd.read_csv(KEY_PATH)
            df_h2["item_id"] = df_h2["item_id"].astype(int)
            df_k["item_id"] = df_k["item_id"].astype(int)
            m_h2 = df_h2.merge(df_k[["item_id", "source"]], on="item_id", how="left")
            # filter final recommendations only
            m_h2 = m_h2[m_h2["source"].isin(["final_top3", "both"])].copy()
            m_h2["holdout_round"] = 2
            # combine
            df_all = pd.concat([df_h1, m_h2], ignore_index=True)
        else:
            df_all = df_h1

        # Calculate standard metrics on combined
        df = df_all
    else:
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
    id_col = "item_id" if "item_id" in judged_a.columns else "item_no"
    item_stats_a = {item_no: ((g["judgment"] == "적합").sum(), len(g)) for item_no, g in judged_a.groupby(id_col)}
    item_keys_a = list(item_stats_a.keys())
    if len(item_keys_a) > 0 and n_a > 0:
        fit_arr_a = np.array([item_stats_a[k][0] for k in item_keys_a])
        tot_arr_a = np.array([item_stats_a[k][1] for k in item_keys_a])
        n_items_a = len(item_keys_a)
        resamples_a = rng.choice(n_items_a, size=(10000, n_items_a), replace=True)
        res_fits_a = fit_arr_a[resamples_a].sum(axis=1)
        res_tots_a = tot_arr_a[resamples_a].sum(axis=1)
        boot_strict_a = res_fits_a / np.maximum(res_tots_a, 1) * 100
        ci95_cluster_bootstrap = [round(float(np.percentile(boot_strict_a, 2.5)), 1), round(float(np.percentile(boot_strict_a, 97.5)), 1)]
    else:
        ci95_cluster_bootstrap = [0.0, 0.0]

    overall["ci95_wilson"] = ci95_wilson
    overall["ci95_cluster_bootstrap"] = ci95_cluster_bootstrap

    raters = []
    for r, g in df.groupby("rater", sort=False):
        c = g["judgment"].value_counts()
        raters.append({
            "rater": r,
            "assigned": len(g),
            "entered": int((g["judgment"] != "").sum()),
            **{lab: int(c.get(lab, 0)) for lab in LABELS},
        })

    # 두 평가자 일치 (같은 항목을 두 사람이 모두 입력한 경우)
    pairs = done.groupby(id_col)["judgment"].agg(list)
    both = pairs[pairs.map(len) == 2]
    agree = int(both.map(lambda x: x[0] == x[1]).sum())
    r1 = [p[0] for p in both]
    r2 = [p[1] for p in both]
    kappa = round(float(cohen_kappa_score(r1, r2, labels=LABELS)), 3) if len(both) > 0 else 0.0

    # B. 항목 단위 결론 (합의 기준): 두 사람 판정 중 낮은 쪽(보수적)을 항목 판정으로 씀
    rank_of = {"적합": 2, "부분 적합": 1, "부적합": 0}
    inv = {v: k for k, v in rank_of.items()}
    item_group_cols = [id_col, "domain", "task", "level", "title", "provider"]
    if "rank" in done.columns:
        item_group_cols.append("rank")

    item = (
        done[done["judgment"].isin(rank_of)]
        .assign(score=lambda x: x["judgment"].map(rank_of))
        .groupby(item_group_cols, as_index=False)
        .agg(score=("score", "min"), raters=("rater", lambda s: "·".join(s)))
    )
    item["judgment"] = item["score"].map(inv)
    item[id_col] = item[id_col].astype(int)
    item = item.sort_values(id_col)

    # B task-level cluster bootstrap (10,000 resamples, random_state=42)
    task_stats_b = {t: ((g["judgment"] == "적합").sum(), len(g)) for t, g in item.groupby("task")}
    t_list_b = list(task_stats_b.keys())
    if len(t_list_b) > 0 and len(item) > 0:
        t_fit_arr_b = np.array([task_stats_b[k][0] for k in t_list_b])
        t_tot_arr_b = np.array([task_stats_b[k][1] for k in t_list_b])
        n_tasks_b = len(t_list_b)
        t_resamples_b = rng.choice(n_tasks_b, size=(10000, n_tasks_b), replace=True)
        t_res_fits_b = t_fit_arr_b[t_resamples_b].sum(axis=1)
        t_res_tots_b = t_tot_arr_b[t_resamples_b].sum(axis=1)
        boot_strict_b = t_res_fits_b / np.maximum(t_res_tots_b, 1) * 100
        ci95_task_bootstrap = [round(float(np.percentile(boot_strict_b, 2.5)), 1), round(float(np.percentile(boot_strict_b, 97.5)), 1)]
    else:
        ci95_task_bootstrap = [0.0, 0.0]

    items_total = int(df[id_col].nunique())
    items_rated = int(item[id_col].nunique())
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
        by_task.append({
            "domain": dom,
            "task": task,
            "level": lvl,
            "items": len(g),
            "fit": int((g["judgment"] == "적합").sum()),
            "partial": int((g["judgment"] == "부분 적합").sum()),
            "unfit": int((g["judgment"] == "부적합").sum()),
        })

    by_rank = {}
    if "rank" in done.columns:
        by_rank = {str(r): precision(done.loc[done["rank"].astype(str) == str(r), "judgment"]) for r in ["1", "2", "3"]}

    entered, assigned = len(done), len(df)
    result = {
        "round": ROUND_TITLES[rnd],
        "checked": date.today().isoformat(),
        "status": "완료" if entered == assigned and entered > 0 else "중간",
        "entered": entered,
        "assigned": assigned,
        "items_total": items_total,
        "items_rated": items_rated,
        "precision_at_3": overall,
        "target_pct": TARGET * 100,
        "meets_target": (overall["strict"] or 0) >= TARGET * 100,
        "agreement": {"pairs": int(len(both)), "agree": agree, "pct": pct(agree, len(both)), "cohen_kappa": kappa},
        "consensus": consensus,
        "ci95_wilson": ci95_wilson,
        "ci95_cluster_bootstrap": ci95_cluster_bootstrap,
        "raters": raters,
        "by_rank": by_rank,
        "by_task": by_task,
        "unfit_items": item.loc[item["judgment"] == "부적합", [id_col, "task", "title", "provider"]].to_dict("records"),
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
        + (f" [둘 다 판단 불가 {consensus['both_unclear']}개 제외]" if consensus["both_unclear"] > 0 else ""),
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
    ] + [
        f"| {r['rater']} | {r['assigned']} | {r['entered']} | {r['적합']} | {r['부분 적합']} | {r['부적합']} | {r['판단 불가']} |"
        for r in raters
    ] + [
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
    ] + [f"- {u[id_col]}번 {u['task']} → {u['title']} ({u['provider']})" for u in result["unfit_items"]] + [""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[{result['round']}] Done -> {OUT_JSON.name}, {OUT_MD.name}")


if __name__ == "__main__":
    main()
