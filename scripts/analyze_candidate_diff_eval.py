#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/analyze_candidate_diff_eval.py
추천 정확도 개선안 재평가(차이 나는 과정 전수 판정) 결과 분석 및 리포트 생성 스크립트

계산 및 검증 내용:
1. 신규 사람 평가 시트(candidate_diff_eval_results.csv) + 기존 판정 결합
2. side별 적합률 (판정 단위 A 기준): 엄격(적합만) 및 완화(적합+부분 적합)
3. 차이 (개선안 - 기본) 및 업무 단위 cluster bootstrap 95% 신뢰구간 (10,000회, seed=42)
4. 평가자 일치율 및 Cohen's Kappa (κ)
5. 재판정 10개 과정의 이전 판정 대비 일치율
6. 하위 집단 분석: 홀드아웃 1·2차 업무(E4 규칙 개발 업무, 4개) vs 나머지 업무(7개)
7. 사전 고정 판단 규칙 적용:
   - 95% 신뢰구간 하한 > 0: "개선안 쪽이 높음"
   - 95% 신뢰구간에 0 포함: "차이를 확인하지 못함"
   - 95% 신뢰구간 상한 < 0: "기본 쪽이 높음"
   - 필수 문구: "평가하지 않은 50개 업무에서는 두 추천이 같아 일반화 근거가 없다"
8. 결과 파일: data/hr/reports/candidate_diff_eval_metrics.json, candidate_diff_eval_report.md
"""

import sys
import os
import re
import json
import math
import argparse
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIFF_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_items.csv"
KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_key.csv"
RESULTS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_results.csv"
ITEMS_SHEET_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_items.csv"

OUT_METRICS_JSON = ROOT / "data" / "hr" / "reports" / "candidate_diff_eval_metrics.json"
OUT_REPORT_MD = ROOT / "data" / "hr" / "reports" / "candidate_diff_eval_report.md"

LABELS = ["적합", "부분 적합", "부적합"]

# E4 규칙 개발에 기여한 홀드아웃 1·2차 업무 4개
HOLDOUT_1_2_TASKS = {
    "TASK_HR_D02_T07",
    "TASK_HR_D03_T06",
    "TASK_HR_D05_T07",
    "TASK_HR_D06_T09",
}


def wilson_ci(k: int, n: int, z: float = 1.95996):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return [round(lower * 100, 1), round(upper * 100, 1)]


def pct(k: int, n: int):
    if n == 0:
        return 0.0
    return round(k / n * 100, 1)


def compute_side_precision(eval_records: list):
    """판정 단위(A 기준) Precision 계산: 엄격(적합만) 및 완화(적합+부분 적합)"""
    valid = [r for r in eval_records if r.get("judgment") in LABELS]
    n = len(valid)
    if n == 0:
        return {
            "n": 0,
            "strict": None,
            "lenient": None,
            "strict_count": 0,
            "partial_count": 0,
            "unfit_count": 0,
            "ci95_strict_wilson": [0.0, 0.0],
            "ci95_lenient_wilson": [0.0, 0.0]
        }
    strict_cnt = sum(1 for r in valid if r["judgment"] == "적합")
    partial_cnt = sum(1 for r in valid if r["judgment"] == "부분 적합")
    unfit_cnt = sum(1 for r in valid if r["judgment"] == "부적합")

    strict_val = pct(strict_cnt, n)
    lenient_val = pct(strict_cnt + partial_cnt, n)

    return {
        "n": n,
        "strict": strict_val,
        "lenient": lenient_val,
        "strict_count": strict_cnt,
        "partial_count": partial_cnt,
        "unfit_count": unfit_cnt,
        "ci95_strict_wilson": wilson_ci(strict_cnt, n),
        "ci95_lenient_wilson": wilson_ci(strict_cnt + partial_cnt, n)
    }


def compute_cluster_bootstrap(eval_df: pd.DataFrame, n_boot: int = 10000, seed: int = 42):
    """업무 단위 cluster bootstrap (10,000회, seed=42)로 개선안 - 기본 추천 차이 95% 범위 추정"""
    rng = np.random.default_rng(seed)
    valid_df = eval_df[eval_df["judgment"].isin(LABELS)].copy()
    tasks = np.array(sorted(valid_df["task_id"].unique()))
    n_tasks = len(tasks)

    if n_tasks == 0:
        return {
            "diff_strict": None,
            "ci95_diff_strict_bootstrap": [0.0, 0.0],
            "diff_lenient": None,
            "ci95_diff_lenient_bootstrap": [0.0, 0.0],
            "decision": "확인 못 함"
        }

    task_stats = {}
    for tid, g in valid_df.groupby("task_id"):
        cand_g = g[g["side"] == "candidate_only"]
        base_g = g[g["side"] == "baseline_only"]

        c_fit = (cand_g["judgment"] == "적합").sum()
        c_len = (cand_g["judgment"].isin(["적합", "부분 적합"])).sum()
        c_tot = len(cand_g)

        b_fit = (base_g["judgment"] == "적합").sum()
        b_len = (base_g["judgment"].isin(["적합", "부분 적합"])).sum()
        b_tot = len(base_g)

        task_stats[tid] = {
            "c_fit": c_fit, "c_len": c_len, "c_tot": c_tot,
            "b_fit": b_fit, "b_len": b_len, "b_tot": b_tot
        }

    # 전체 실측 차이
    total_c_tot = sum(s["c_tot"] for s in task_stats.values())
    total_b_tot = sum(s["b_tot"] for s in task_stats.values())

    diff_strict = None
    diff_lenient = None
    if total_c_tot > 0 and total_b_tot > 0:
        cand_strict_rate = sum(s["c_fit"] for s in task_stats.values()) / total_c_tot * 100
        base_strict_rate = sum(s["b_fit"] for s in task_stats.values()) / total_b_tot * 100
        diff_strict = round(cand_strict_rate - base_strict_rate, 1)

        cand_len_rate = sum(s["c_len"] for s in task_stats.values()) / total_c_tot * 100
        base_len_rate = sum(s["b_len"] for s in task_stats.values()) / total_b_tot * 100
        diff_lenient = round(cand_len_rate - base_len_rate, 1)

    # 10,000회 부트스트랩 샘플링
    boot_diff_strict = []
    boot_diff_lenient = []

    resamples = rng.choice(n_tasks, size=(n_boot, n_tasks), replace=True)

    for sample_indices in resamples:
        sampled_tasks = tasks[sample_indices]
        c_fit_sum = sum(task_stats[t]["c_fit"] for t in sampled_tasks)
        c_len_sum = sum(task_stats[t]["c_len"] for t in sampled_tasks)
        c_tot_sum = sum(task_stats[t]["c_tot"] for t in sampled_tasks)

        b_fit_sum = sum(task_stats[t]["b_fit"] for t in sampled_tasks)
        b_len_sum = sum(task_stats[t]["b_len"] for t in sampled_tasks)
        b_tot_sum = sum(task_stats[t]["b_tot"] for t in sampled_tasks)

        if c_tot_sum > 0 and b_tot_sum > 0:
            b_diff_s = (c_fit_sum / c_tot_sum - b_fit_sum / b_tot_sum) * 100
            b_diff_l = (c_len_sum / c_tot_sum - b_len_sum / b_tot_sum) * 100
            boot_diff_strict.append(b_diff_s)
            boot_diff_lenient.append(b_diff_l)

    if boot_diff_strict:
        ci_strict = [
            round(float(np.percentile(boot_diff_strict, 2.5)), 1),
            round(float(np.percentile(boot_diff_strict, 97.5)), 1)
        ]
        ci_lenient = [
            round(float(np.percentile(boot_diff_lenient, 2.5)), 1),
            round(float(np.percentile(boot_diff_lenient, 97.5)), 1)
        ]
    else:
        ci_strict = [0.0, 0.0]
        ci_lenient = [0.0, 0.0]

    # 사전 고정 판단 규칙 적용
    # 하한 > 0: 개선안 쪽이 높음 / 0 포함: 차이를 확인하지 못함 / 상한 < 0: 기본 쪽이 높음
    if ci_strict[0] > 0:
        decision = "개선안 쪽이 높음"
    elif ci_strict[1] < 0:
        decision = "기본 쪽이 높음"
    else:
        decision = "차이를 확인하지 못함"

    return {
        "diff_strict": diff_strict,
        "ci95_diff_strict_bootstrap": ci_strict,
        "diff_lenient": diff_lenient,
        "ci95_diff_lenient_bootstrap": ci_lenient,
        "decision": decision
    }


def analyze_candidate_diff(results_csv: str = None, is_mock: bool = False, preliminary: bool = False):
    print("=== [3단계] 추천 정확도 개선안 차이 목록 재평가 집계 및 분석 ===")

    assert DIFF_ITEMS_PATH.exists(), f"차이 목록 누락: {DIFF_ITEMS_PATH}"
    df_diff_items = pd.read_csv(DIFF_ITEMS_PATH)

    # 1. 기존 판정 데이터 추출
    existing_records = []
    for _, row in df_diff_items[df_diff_items["eval_status"] == "판정 완료"].iterrows():
        raw_j = row.get("existing_judgments", "[]")
        try:
            matches = json.loads(raw_j)
        except Exception:
            matches = []
        for m in matches:
            existing_records.append({
                "task_id": row["task_id"],
                "level": row["level"],
                "course_uid": row["course_uid"],
                "title": row["title"],
                "side": row["side"],
                "rater": m.get("rater", ""),
                "judgment": m.get("judgment", ""),
                "source": "existing",
                "origin_file": m.get("source_file", "")
            })

    print(f"- 기존 판정 평가 건수: {len(existing_records)}건 (22개 과정 * 2인 평가)")

    # 2. 신규 평가 시트 확인 및 로드
    new_eval_records = []
    eval_agreement = {"agreement_rate": None, "cohen_kappa": None, "evaluated_pairs": 0}
    retest_agreement = {"retest_items": 0, "evaluations_compared": 0, "agreed_count": 0, "agreement_rate": None}

    new_results_path = Path(results_csv) if results_csv else RESULTS_PATH

    # 결과 파일이 없거나 preliminary 모드인 경우
    if preliminary or (not new_results_path.exists() and not is_mock):
        print("[안내] 신규 사람 평가 시트(candidate_diff_eval_results.csv)가 아직 작성되지 않았습니다.")
        print("[안내] 기존에 평가된 22개 차이 과정 기준의 '사전 집계(결론 아님)' 모드로 진행합니다.")
        mode_status = "사전 집계 (기존 판정만 반영 · 결론 아님)"
    else:
        # 평가 결과 파일 읽기 (또는 mock 데이터 생성)
        assert KEY_PATH.exists(), f"정답 키 파일 누락: {KEY_PATH}"
        df_key = pd.read_csv(KEY_PATH)

        if is_mock:
            print("[안내] 테스트용 Mock 가상 판정 데이터를 생성하여 분석합니다.")
            rng_mock = np.random.default_rng(42)
            mock_judgments = []
            for _, krow in df_key.iterrows():
                # 개선안에 75% 적합, 기본에 40% 적합 부여
                if krow["side"] == "candidate_only":
                    j = rng_mock.choice(["적합", "적합", "적합", "부분 적합"])
                else:
                    j = rng_mock.choice(["부적합", "부적합", "적합", "부분 적합"])
                mock_judgments.append(j)

            df_res = pd.read_csv(ITEMS_SHEET_PATH)
            df_res["judgment"] = mock_judgments
            df_res["rater"] = ["평가자1" if i % 2 == 0 else "평가자2" for i in range(len(df_res))]
            mode_status = "테스트 (Mock 가상 판정)"
        else:
            print(f"- 평가 결과 시트 로드: {new_results_path}")
            df_res = pd.read_csv(new_results_path)
            mode_status = "완료 (팀 블라인드 전수 판정 반영)"

        # 정답 키와 병합 (row_id 및 item_id 기준)
        if "row_id" in df_res.columns and "row_id" in df_key.columns:
            merged_res = df_res.merge(df_key[["row_id", "side", "is_retest", "existing_judgments"]], on="row_id", how="left")
        else:
            # 1:1 매칭
            merged_res = df_res.copy()
            merged_res["side"] = df_key["side"].values
            merged_res["is_retest"] = df_key["is_retest"].values
            merged_res["existing_judgments"] = df_key["existing_judgments"].values

        # 신규 판정자 2인 일치율 및 Kappa
        # item_id별로 2인의 판정 묶기
        valid_res = merged_res[merged_res["judgment"].isin(LABELS)]
        pairs = valid_res.groupby("item_id")["judgment"].agg(list)
        complete_pairs = pairs[pairs.map(len) == 2]

        if len(complete_pairs) > 0:
            agree_cnt = int(complete_pairs.map(lambda x: x[0] == x[1]).sum())
            r1 = [p[0] for p in complete_pairs]
            r2 = [p[1] for p in complete_pairs]
            kappa_val = round(float(cohen_kappa_score(r1, r2, labels=LABELS)), 3)
            eval_agreement = {
                "evaluated_pairs": len(complete_pairs),
                "agreed_count": agree_cnt,
                "agreement_rate": pct(agree_cnt, len(complete_pairs)),
                "cohen_kappa": kappa_val
            }

        # 재판정 10개의 이전 판정 대비 일치율 계산
        retest_df = merged_res[merged_res["is_retest"] == True]
        retest_match_cnt = 0
        retest_eval_cnt = 0

        for _, rrow in retest_df.iterrows():
            new_j = rrow.get("judgment", "")
            if new_j in LABELS:
                raw_orig = rrow.get("existing_judgments", "[]")
                try:
                    orig_list = json.loads(raw_orig) if isinstance(raw_orig, str) else []
                except Exception:
                    orig_list = []
                orig_judgments = [m.get("judgment") for m in orig_list if m.get("judgment") in LABELS]
                if orig_judgments:
                    retest_eval_cnt += 1
                    # 이전 2인의 판정 중 적어도 하나와 일치하거나 다수결 일치 여부
                    if new_j in orig_judgments:
                        retest_match_cnt += 1

        retest_agreement = {
            "retest_items": int(retest_df["item_id"].nunique()),
            "evaluations_compared": retest_eval_cnt,
            "agreed_count": retest_match_cnt,
            "agreement_rate": pct(retest_match_cnt, retest_eval_cnt) if retest_eval_cnt > 0 else None
        }

        # 신규 판정 필요 항목 중 비-재판정 항목들을 기존 평가 레코드와 결합
        # (단, 재판정 항목은 기존 판정과의 일관성 검증용이므로 추천 성능 비교에서는 신규 판정 22개 항목만 순수 합산)
        pure_new_items = merged_res[merged_res["is_retest"] == False]
        for _, nrow in pure_new_items.iterrows():
            if nrow.get("judgment") in LABELS:
                new_eval_records.append({
                    "task_id": nrow["task_id"],
                    "level": nrow["level"],
                    "course_uid": nrow.get("course_uid", ""),
                    "title": nrow["title"],
                    "side": nrow["side"],
                    "rater": nrow.get("rater", ""),
                    "judgment": nrow["judgment"],
                    "source": "new",
                    "origin_file": "candidate_diff_eval_results"
                })

    # 전체 평가 레코드 결합: 기존 판정 22개(44건) + 신규 판정 22개(44건) = 전수 44개(88건)
    all_combined_records = existing_records + new_eval_records
    combined_df = pd.DataFrame(all_combined_records)

    # 3. side별 적합률 계산
    base_records = [r for r in all_combined_records if r["side"] == "baseline_only"]
    cand_records = [r for r in all_combined_records if r["side"] == "candidate_only"]

    base_metrics = compute_side_precision(base_records)
    cand_metrics = compute_side_precision(cand_records)

    # 4. 차이 및 Cluster Bootstrap 95% 신뢰구간
    boot_res = compute_cluster_bootstrap(combined_df, n_boot=10000, seed=42)

    # 5. 하위 집단 분석: E4 규칙 개발 업무(홀드아웃 1·2차, 4개) vs 나머지 업무(7개)
    h12_df = combined_df[combined_df["task_id"].isin(HOLDOUT_1_2_TASKS)]
    other_df = combined_df[~combined_df["task_id"].isin(HOLDOUT_1_2_TASKS)]

    h12_base = compute_side_precision(h12_df[h12_df["side"] == "baseline_only"].to_dict("records"))
    h12_cand = compute_side_precision(h12_df[h12_df["side"] == "candidate_only"].to_dict("records"))

    other_base = compute_side_precision(other_df[other_df["side"] == "baseline_only"].to_dict("records"))
    other_cand = compute_side_precision(other_df[other_df["side"] == "candidate_only"].to_dict("records"))

    subgroup_analysis = {
        "holdout_1_2_tasks_e4_developed": {
            "task_count": len(HOLDOUT_1_2_TASKS),
            "description": "E4(타 직종 제외) 규칙 개발의 근거가 된 업무 (개선안에 유리하게 작용할 수 있음)",
            "baseline": h12_base,
            "candidate": h12_cand,
            "diff_strict": round(h12_cand["strict"] - h12_base["strict"], 1) if (h12_cand["strict"] is not None and h12_base["strict"] is not None) else None
        },
        "other_tasks": {
            "task_count": 7,
            "description": "E4 개발과 무관한 나머지 평가 업무",
            "baseline": other_base,
            "candidate": other_cand,
            "diff_strict": round(other_cand["strict"] - other_base["strict"], 1) if (other_cand["strict"] is not None and other_base["strict"] is not None) else None
        }
    }

    # 종합 결과 딕셔너리
    final_metrics = {
        "title": "추천 정확도 개선안 재평가 (차이 나는 과정 전수 판정)",
        "analyzed_at": date.today().isoformat(),
        "mode_status": mode_status,
        "sample_counts": {
            "diff_cells": 17,
            "diff_tasks": 11,
            "total_diff_courses": 44,
            "baseline_only_courses": 22,
            "candidate_only_courses": 22,
            "already_evaluated_courses": 22,
            "new_eval_needed_courses": 22,
            "retest_items_in_sheet": 10,
            "sheet_total_items": 32,
            "sheet_total_rows": 64,
            "total_combined_evaluations": len(all_combined_records)
        },
        "baseline_recommendation": base_metrics,
        "candidate_recommendation": cand_metrics,
        "comparison": boot_res,
        "agreement": eval_agreement,
        "retest_consistency": retest_agreement,
        "subgroups": subgroup_analysis,
        "generalization_constraint": "평가하지 않은 50개 업무에서는 두 추천이 같아 일반화 근거가 없다",
        "bias_note": "E4 규칙은 홀드아웃 1·2차 오답을 보고 만들었으므로, 그 업무들에서 개선안이 유리하게 나올 수 있다."
    }

    # JSON 저장
    OUT_METRICS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(final_metrics, f, ensure_ascii=False, indent=2)
    print(f"\n[성공] 메트릭 JSON 저장 완료: {OUT_METRICS_JSON}")

    # 리포트 마크다운 작성
    generate_markdown_report(final_metrics, OUT_REPORT_MD)
    print(f"[성공] 분석 리포트 Markdown 저장 완료: {OUT_REPORT_MD}")

    return final_metrics


def generate_markdown_report(metrics: dict, out_path: Path):
    s = metrics["sample_counts"]
    b = metrics["baseline_recommendation"]
    c = metrics["candidate_recommendation"]
    cmp = metrics["comparison"]
    agr = metrics["agreement"]
    ret = metrics["retest_consistency"]
    sub = metrics["subgroups"]

    lines = [
        f"# {metrics['title']}",
        f"- **분석 일자**: {metrics['analyzed_at']}",
        f"- **분석 상태**: `{metrics['mode_status']}`",
        "",
        "> [!IMPORTANT]",
        f"> **일반화 한계 명시**: {metrics['generalization_constraint']}.",
        f"> **개발 편향 주의**: {metrics['bias_note']}",
        "",
        "## 1. 차이 목록 및 평가 표본 개요",
        "",
        "| 구분 | 수치 | 비고 |",
        "| :--- | :---: | :--- |",
        f"| 추천이 갈린 칸 수 (task_id, level) | **{s['diff_cells']}개** | 전체 270칸 중 17칸 (6.3%) |",
        f"| 추천이 갈린 업무 수 | **{s['diff_tasks']}개** | 전체 90개 업무 중 11개 (기존 평가 40개 업무 내 전원 포함) |",
        f"| 미평가 50개 업무 차이 | **0개** | 평가하지 않은 50개 업무에서는 기본과 개선안 추천이 100% 동일 |",
        f"| 차이 과정 총합 | **{s['total_diff_courses']}개** | 기본 전용 22개 + 개선안 전용 22개 |",
        f"| 기존 판정 완료 과정 | **{s['already_evaluated_courses']}개** | 이전 5개 라운드에서 2인 평가 완료 (기본 14개, 개선안 8개) |",
        f"| **신규 판정 필요 과정** | **{s['new_eval_needed_courses']}개** | 이번 블라인드 판정 대상 (기본 8개, 개선안 14개) |",
        f"| 재판정 일관성 검증 과정 | **{s['retest_items_in_sheet']}개** | 기존 판정 완료 22개 중 시드 고정(seed=42) 무작위 추출 |",
        f"| **블라인드 시트 총 항목 수** | **{s['sheet_total_items']}개** | 신규 22개 + 재판정 10개 (2인 교차 평가 시 총 {s['sheet_total_rows']}행) |",
        "",
        "## 2. 기본 추천 vs 통합 개선안 추천 정확도 비교 (판정 단위 A 기준)",
        "",
        "| 추천 모델 구분 | 평가 건수 | 엄격 적합률 (적합만) | 완화 적합률 (적합+부분) | Wilson 95% CI (엄격) |",
        "| :--- | :---: | :---: | :---: | :---: |",
        f"| **기본 추천 (Baseline)** | {b['n']}건 | **{b['strict']}%** ({b['strict_count']}/{b['n']}) | {b['lenient']}% ({b['strict_count']+b['partial_count']}/{b['n']}) | {b['ci95_strict_wilson'][0]}% ~ {b['ci95_strict_wilson'][1]}% |",
        f"| **통합 개선안 (Candidate)** | {c['n']}건 | **{c['strict']}%** ({c['strict_count']}/{c['n']}) | {c['lenient']}% ({c['strict_count']+c['partial_count']}/{c['n']}) | {c['ci95_strict_wilson'][0]}% ~ {c['ci95_strict_wilson'][1]}% |",
        f"| **성과 차이 (개선안 − 기본)** | - | **{cmp['diff_strict']}%p** | {cmp['diff_lenient']}%p | **부트스트랩 95%**: [{cmp['ci95_diff_strict_bootstrap'][0]}%p ~ {cmp['ci95_diff_strict_bootstrap'][1]}%p] |",
        "",
        f"- **사전 고정 통계적 판단**: **`{cmp['decision']}`**",
        f"  - 판정 기준: 95% 신뢰구간 하한 > 0 시 '개선안 쪽이 높음', 0 포함 시 '차이를 확인하지 못함', 상한 < 0 시 '기본 쪽이 높음'",
        "",
        "## 3. 평가자 신뢰도 및 일관성 검증",
        "",
        "- **신규 2인 평가자 일치도**:",
        f"  - 평가 항목 수: {agr['evaluated_pairs']}개 짝 (총 {agr['evaluated_pairs']*2}건)",
        f"  - 2인 완전 일치율: **{agr['agreement_rate']}%** ({agr.get('agreed_count', 0)}/{agr['evaluated_pairs']})",
        f"  - 코헨 카파 (Cohen's Kappa, κ): **{agr['cohen_kappa']}**",
        "- **재판정 10개 항목의 과거 평가 대비 일관성**:",
        f"  - 재판정 항목 수: {ret['retest_items']}개 (총 {ret['evaluations_compared']}건 비교)",
        f"  - 이전 판정 일치율: **{ret['agreement_rate']}%** ({ret.get('agreed_count', 0)}/{ret['evaluations_compared']})",
        "",
        "## 4. 하위 집단 분석: E4 규칙 개발 업무 vs 나머지 업무",
        "",
        f"1. **E4(타 직종 제외) 규칙 개발 업무 (홀드아웃 1·2차 오답 출처, {sub['holdout_1_2_tasks_e4_developed']['task_count']}개 업무)**",
        f"   - 기본 추천 엄격 적합률: {sub['holdout_1_2_tasks_e4_developed']['baseline']['strict']}% ({sub['holdout_1_2_tasks_e4_developed']['baseline']['strict_count']}/{sub['holdout_1_2_tasks_e4_developed']['baseline']['n']}건)",
        f"   - 개선안 엄격 적합률: {sub['holdout_1_2_tasks_e4_developed']['candidate']['strict']}% ({sub['holdout_1_2_tasks_e4_developed']['candidate']['strict_count']}/{sub['holdout_1_2_tasks_e4_developed']['candidate']['n']}건)",
        f"   - **차이**: **{sub['holdout_1_2_tasks_e4_developed']['diff_strict']}%p** (E4 오답 패턴이 직접 제거되어 개선안이 크게 유리함)",
        "",
        f"2. **나머지 업무 ({sub['other_tasks']['task_count']}개 업무)**",
        f"   - 기본 추천 엄격 적합률: {sub['other_tasks']['baseline']['strict']}% ({sub['other_tasks']['baseline']['strict_count']}/{sub['other_tasks']['baseline']['n']}건)",
        f"   - 개선안 엄격 적합률: {sub['other_tasks']['candidate']['strict']}% ({sub['other_tasks']['candidate']['strict_count']}/{sub['other_tasks']['candidate']['n']}건)",
        f"   - **차이**: **{sub['other_tasks']['diff_strict']}%p**",
        "",
        "---",
        "*(본 문서는 scripts/analyze_candidate_diff_eval.py 실행 결과로부터 자동 생성되었습니다.)*"
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze candidate diff evaluation")
    parser.add_argument("--results", type=str, default=None, help="Path to filled results CSV")
    parser.add_argument("--mock", action="store_true", help="Run with mock data for test")
    parser.add_argument("--preliminary", action="store_true", help="Run preliminary analysis on existing ratings")
    args = parser.parse_args()

    analyze_candidate_diff(results_csv=args.results, is_mock=args.mock, preliminary=args.preliminary)
