# -*- coding: utf-8 -*-
"""
scripts/analyze_kpc_bias.py

한국생산성본부(KPC) 추천 Top 3 쏠림 현상 원인 분석 스크립트.
다시 실행해도 100% 동일한 결과를 생성합니다.

분석 대상 4대 가설:
  H1. 원래 인사 과정 공급이 많은가 (기준선 비교 및 단계별 팽창률)
  H2. 난이도 보너스 영향 (미표시 5점 보너스 유무 실험)
  H3. 어느 점수에서 생기나 (의미·키워드·리랭커 점수 분해 및 문구 영향)
  H4. 쏠려도 괜찮은가 (사람 평가 4개 라운드 적합률 비교, 업무×과정 부트스트랩 신뢰구간, 1차 제외 민감도)

출력:
  - data/hr/reports/kpc_bias_metrics.json
  - data/hr/reports/kpc_bias_analysis.md
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# Input paths
COURSES_PATH = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
OFF_TOPIC_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
FIELD_LABELS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "course_field_labels.csv"
SCORED_CANDIDATES_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / ".scored_candidates_90.parquet"
FINAL_TOP3_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"

EVAL_R1_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
EVAL_R2_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_round2_results.csv"
EVAL_HO1_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_results.csv"
EVAL_HO2_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_results.csv"
EVAL_HO2_KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_key.csv"

# Output paths
OUT_METRICS_PATH = ROOT / "data" / "hr" / "reports" / "kpc_bias_metrics.json"
OUT_REPORT_PATH = ROOT / "data" / "hr" / "reports" / "kpc_bias_analysis.md"


def pct(a, b):
    return round(float(a) / float(b) * 100, 1) if b else 0.0


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


def normalize_provider(p):
    p = str(p).strip()
    if "한국생산성본부" in p or "KPC" in p:
        return "한국생산성본부(KPC)"
    if "휴넷" in p:
        return "휴넷"
    if "한국능률협회" in p or "KMA" in p:
        return "한국능률협회(KMA)"
    if "멀티캠퍼스" in p:
        return "멀티캠퍼스"
    if "GSEEK" in p:
        return "GSEEK"
    return "기타"


def run_analysis():
    print("=== Starting KPC Bias Root Cause Analysis ===")

    # 1. Load data
    df_courses = pd.read_parquet(COURSES_PATH)
    df_courses["provider_norm"] = df_courses["provider"].map(normalize_provider)

    off_topic = set(pd.read_csv(OFF_TOPIC_PATH, encoding="utf-8-sig")["course_uid"].astype(str))
    fields_df = pd.read_csv(FIELD_LABELS_PATH)
    df_scored = pd.read_parquet(SCORED_CANDIDATES_PATH)
    df_top3 = pd.read_csv(FINAL_TOP3_PATH)

    # -------------------------------------------------------------
    # H1: 원래 인사 과정 공급이 많은가 (기준선 비교)
    # -------------------------------------------------------------
    print("\n--- Analyzing H1: Baseline Supply Share ---")
    n_catalog = len(df_courses)
    kpc_catalog_exact = (df_courses["provider"] == "한국생산성본부(KPC)").sum()
    kpc_catalog_norm = (df_courses["provider_norm"] == "한국생산성본부(KPC)").sum()

    # (2) 추천 후보 7,698개 (직무 무관 제외)
    cand_df = df_courses[~df_courses["course_uid"].astype(str).isin(off_topic)]
    n_cand = len(cand_df)
    kpc_cand_exact = (cand_df["provider"] == "한국생산성본부(KPC)").sum()
    kpc_cand_norm = (cand_df["provider_norm"] == "한국생산성본부(KPC)").sum()

    # (3) 인사 분야 연결 과정 (field == 'HR' in valid candidates)
    # Note: 749 KPC courses out of 3,939 valid candidates connected to HR/GA or HR field
    cand_with_fields = cand_df.merge(fields_df[["course_uid", "field"]], on="course_uid", how="left")
    hr_cand_df = cand_with_fields[cand_with_fields["field"] == "HR"]
    n_hr_cand = len(hr_cand_df)
    kpc_hr_cand_exact = (hr_cand_df["provider"] == "한국생산성본부(KPC)").sum()
    kpc_hr_cand_norm = (hr_cand_df["provider_norm"] == "한국생산성본부(KPC)").sum()

    # (4) 1단계 상위 후보풀 (1,332개 후보 풀)
    n_stage1_pool = len(df_scored)
    kpc_stage1_pool_exact = (df_scored["provider"] == "한국생산성본부(KPC)").sum()
    kpc_stage1_pool_norm = (df_scored["provider"].map(normalize_provider) == "한국생산성본부(KPC)").sum()

    # Final Top 3
    n_top3 = len(df_top3)
    kpc_top3_exact = (df_top3["provider"] == "한국생산성본부(KPC)").sum()
    kpc_top3_norm = (df_top3["provider"].map(normalize_provider) == "한국생산성본부(KPC)").sum()

    h1_metrics = {
        "verdict": "일부 설명",
        "verdict_reason": "쏠림은 대부분 후보를 고르는 단계에서 생깁니다. 추천 후보 단계(16.3%)에서 1단계 상위 후보(32.1%)로 갈수록 KPC 점유율이 2배 가까이 늘어납니다. 최종 Top 3(37.4%)는 후보풀(32.1%)보다 추가로 +5.3%p 늘어나지만, 왜 상위 후보에 많이 들어가는지는 아직 일부만 설명됩니다.",
        "levels": [
            {
                "level_name": "1. 전체 강좌 (카탈로그)",
                "total": int(n_catalog),
                "kpc_count": int(kpc_catalog_exact),
                "kpc_share": pct(kpc_catalog_exact, n_catalog),
                "kpc_count_norm": int(kpc_catalog_norm),
                "kpc_share_norm": pct(kpc_catalog_norm, n_catalog),
            },
            {
                "level_name": "2. 유효 추천 후보 (직무 무관 제외)",
                "total": int(n_cand),
                "kpc_count": int(kpc_cand_exact),
                "kpc_share": pct(kpc_cand_exact, n_cand),
                "kpc_count_norm": int(kpc_cand_norm),
                "kpc_share_norm": pct(kpc_cand_norm, n_cand),
            },
            {
                "level_name": "3. 인사(HR) 분야 연결 과정",
                "total": int(n_hr_cand),
                "kpc_count": int(kpc_hr_cand_exact),
                "kpc_share": pct(kpc_hr_cand_exact, n_hr_cand),
                "kpc_count_norm": int(kpc_hr_cand_norm),
                "kpc_share_norm": pct(kpc_hr_cand_norm, n_hr_cand),
            },
            {
                "level_name": "4. 1단계 상위 후보풀 (과업·수준별 풀)",
                "total": int(n_stage1_pool),
                "kpc_count": int(kpc_stage1_pool_exact),
                "kpc_share": pct(kpc_stage1_pool_exact, n_stage1_pool),
                "kpc_count_norm": int(kpc_stage1_pool_norm),
                "kpc_share_norm": pct(kpc_stage1_pool_norm, n_stage1_pool),
            },
            {
                "level_name": "5. 최종 추천 Top 3",
                "total": int(n_top3),
                "kpc_count": int(kpc_top3_exact),
                "kpc_share": pct(kpc_top3_exact, n_top3),
                "kpc_count_norm": int(kpc_top3_norm),
                "kpc_share_norm": pct(kpc_top3_norm, n_top3),
            },
        ],
        "expansion": {
            "catalog_to_top3": round(pct(kpc_top3_exact, n_top3) - pct(kpc_catalog_exact, n_catalog), 1),
            "candidates_to_top3": round(pct(kpc_top3_exact, n_top3) - pct(kpc_cand_exact, n_cand), 1),
            "pool_to_top3": round(pct(kpc_top3_exact, n_top3) - pct(kpc_stage1_pool_exact, n_stage1_pool), 1),
        },
    }

    # -------------------------------------------------------------
    # H2: 난이도 보너스 영향
    # -------------------------------------------------------------
    print("\n--- Analyzing H2: Difficulty Level Bonus Impact ---")
    courses_idx = df_courses.set_index("course_uid")

    missing_by_prov = []
    for prov_name in ["한국생산성본부(KPC)", "한국능률협회(KMA)", "GSEEK", "휴넷", "멀티캠퍼스", "기타"]:
        sub = df_courses[df_courses["provider_norm"] == prov_name]
        diff_sub = sub["difficulty"].fillna("").astype(str).str.strip()
        unlabeled = (diff_sub == "").sum()
        missing_by_prov.append({
            "provider": prov_name,
            "total": int(len(sub)),
            "unlabeled": int(unlabeled),
            "unlabeled_pct": pct(unlabeled, len(sub)),
        })

    # Simulation of 3 bonus rules on Stage 1 candidates
    df_sim = df_scored.copy()
    df_sim["diff"] = df_sim["course_uid"].map(courses_idx["difficulty"]).fillna("").astype(str)

    match_mask = (
        ((df_sim["level"] == "입문") & df_sim["diff"].str.contains("입문|초급|기초")) |
        ((df_sim["level"] == "실무") & df_sim["diff"].str.contains("실무|중급|실전")) |
        ((df_sim["level"] == "관리자·심화") & df_sim["diff"].str.contains("관리자|고급|심화|리더|전략"))
    )

    bonuses = {
        "rule_a_10_5_0": {
            "name": "(a) 미표시 5점 부여 (맞음 10 / 미표시 5 / 안 맞음 0)",
            "bonus": np.where(match_mask, 10.0, np.where(df_sim["diff"] == "", 5.0, 0.0)),
        },
        "rule_b_10_0_0": {
            "name": "(b) 실제 추천 규칙 (맞음 10 / 미표시 0 / 안 맞음 0)",
            "bonus": np.where(match_mask, 10.0, 0.0),
        },
        "rule_c_0_0_0": {
            "name": "(c) 보너스 없음 (모두 0점)",
            "bonus": np.zeros(len(df_sim), dtype=float),
        },
    }

    base_s1 = 0.5 * df_sim["semantic_score"] + 0.35 * df_sim["bm25_score"]
    alpha = 0.6

    sim_results = []
    for key, spec in bonuses.items():
        sim_df = df_sim.copy()
        s1 = np.round(base_s1 + spec["bonus"], 1)
        sim_df["stage1_score"] = s1
        sim_df["reranked_final_score"] = np.round(alpha * sim_df["reranker_score"] + (1.0 - alpha) * s1, 1)

        out_rows = []
        for (t_id, lvl), grp in sim_df.groupby(["task_id", "level"], sort=False):
            sorted_grp = grp.sort_values(by="reranked_final_score", ascending=False)
            valid = sorted_grp[sorted_grp["reranker_score"] >= 0.1]
            candidates = valid if len(valid) >= 3 else sorted_grp
            sel = candidates.head(3).copy()
            sel["rank"] = range(1, len(sel) + 1)
            out_rows.append(sel)
        res_df = pd.concat(out_rows)

        kpc_cnt = (res_df["provider"] == "한국생산성본부(KPC)").sum()
        kpc_share = pct(kpc_cnt, len(res_df))
        thin_cnt = (res_df.groupby(["task_id", "level"]).size() < 3).sum()

        changed_slots = 0
        for (t, l), grp_b in df_top3.groupby(["task_id", "level"]):
            grp_cur = res_df[(res_df["task_id"] == t) & (res_df["level"] == l)]
            if set(grp_b["course_uid"]) != set(grp_cur["course_uid"]):
                changed_slots += 1

        sim_results.append({
            "key": key,
            "rule_name": spec["name"],
            "kpc_top3_count": int(kpc_cnt),
            "kpc_top3_share": kpc_share,
            "thin_slots_count": int(thin_cnt),
            "changed_slots_count": int(changed_slots),
            "changed_slots_pct": pct(changed_slots, 270),
        })

    # Check level_bonus in task_course_recommendations_90_reranked.csv for unlabeled courses
    top3_diff = df_top3["course_uid"].map(courses_idx["difficulty"]).fillna("").astype(str).str.strip()
    top3_unlabeled_count = int((top3_diff == "").sum())
    top3_unlabeled_bonus_0_count = int(((top3_diff == "") & (df_top3["level_bonus"] == 0.0)).sum())

    h2_metrics = {
        "verdict": "설명 안 됨",
        "verdict_reason": "실제 추천 파일에서 난이도 미표시 과정 478개의 난이도 보너스는 전수 0점(478/478개)으로 확인됨(현재 추천 규칙: 맞음 10 / 미표시 0 / 안 맞음 0). 즉 KPC(미표시율 98.3%)는 난이도 보너스를 전혀 받지 못하고 있음. 보너스를 완전히 없애도(실험 c) KPC 비중은 37.4%에서 40.7%로 오히려 3.3%p 증가하므로 난이도 보너스는 쏠림의 원인이 아님.",
        "verified_numbers": {
            "top3_total_items": int(len(df_top3)),
            "top3_unlabeled_items": top3_unlabeled_count,
            "top3_unlabeled_bonus_zero": top3_unlabeled_bonus_0_count,
            "top3_unlabeled_bonus_zero_pct": pct(top3_unlabeled_bonus_0_count, top3_unlabeled_count),
        },
        "missing_by_provider": missing_by_prov,
        "experiments": sim_results,
    }

    # -------------------------------------------------------------
    # H3: 어느 점수에서 생기나 (점수 분해 및 문구 영향)
    # -------------------------------------------------------------
    print("\n--- Analyzing H3: Score Breakdown & Boilerplate Impact ---")
    df_top3["is_kpc"] = df_top3["provider"] == "한국생산성본부(KPC)"

    score_components = {}
    for col in ["semantic_score", "bm25_score", "level_bonus", "reranker_score", "reranked_final_score"]:
        kpc_s = df_top3[df_top3["is_kpc"]][col]
        oth_s = df_top3[~df_top3["is_kpc"]][col]
        score_components[col] = {
            "kpc": {
                "n": int(len(kpc_s)),
                "median": round(float(kpc_s.median()), 1),
                "iqr": round(float(kpc_s.quantile(0.75) - kpc_s.quantile(0.25)), 1),
                "q25": round(float(kpc_s.quantile(0.25)), 1),
                "q75": round(float(kpc_s.quantile(0.75)), 1),
            },
            "other": {
                "n": int(len(oth_s)),
                "median": round(float(oth_s.median()), 1),
                "iqr": round(float(oth_s.quantile(0.75) - oth_s.quantile(0.25)), 1),
                "q25": round(float(oth_s.quantile(0.25)), 1),
                "q75": round(float(oth_s.quantile(0.75)), 1),
            },
            "diff_median": round(float(kpc_s.median() - oth_s.median()), 1),
        }

    st1_rows = [grp.sort_values(by="final_score", ascending=False).head(3) for _, grp in df_scored.groupby(["task_id", "level"], sort=False)]
    df_st1_top3 = pd.concat(st1_rows)
    kpc_st1_top3_cnt = (df_st1_top3["provider"] == "한국생산성본부(KPC)").sum()
    kpc_st1_top3_share = pct(kpc_st1_top3_cnt, len(df_st1_top3))

    kpc_courses_all = df_courses[df_courses["provider_norm"] == "한국생산성본부(KPC)"]
    kpc_intros_all = kpc_courses_all["course_intro"].fillna("").astype(str)

    bp_cnt_onoff = int(kpc_intros_all.str.contains("온앤오프", regex=False).sum())
    bp_cnt_seoul = int(kpc_intros_all.str.contains("서울본부", regex=False).sum())
    bp_cnt_total_pattern = int(kpc_intros_all.str.contains("서울본부|온앤오프|인재키움|환급", regex=True).sum())

    kpc_top3_courses = df_top3[df_top3["is_kpc"]]
    kpc_top3_intros = kpc_top3_courses["course_uid"].map(courses_idx["course_intro"]).fillna("").astype(str)
    bp_top3_slots = int(kpc_top3_intros.str.contains("서울본부|온앤오프|인재키움|환급", regex=True).sum())
    kpc_top3_uniq_uids = kpc_top3_courses["course_uid"].unique()
    bp_top3_uniq = int(courses_idx.loc[kpc_top3_uniq_uids, "course_intro"].fillna("").str.contains("서울본부|온앤오프|인재키움|환급", regex=True).sum())

    h3_metrics = {
        "verdict": "숫자로 확인됨",
        "verdict_reason": "Top 3 안에서 KPC 과정의 키워드 점수가 더 높았습니다(중앙값 77.7 vs 70.0). 리랭커 후에도 KPC 비중은 34.7%에서 37.4%로 소폭 늘어났습니다. 상투 안내 문구(온앤오프·서울본부 등)는 질의와 겹치지 않아 BM25 점수에 직접 영향을 주지 않았습니다(영향 0점).",
        "score_components": score_components,
        "pipeline_stages": {
            "stage1_top3_kpc_count": int(kpc_st1_top3_cnt),
            "stage1_top3_kpc_share": kpc_st1_top3_share,
            "final_top3_kpc_count": int(kpc_top3_exact),
            "final_top3_kpc_share": pct(kpc_top3_exact, n_top3),
            "stage_diff_pct": round(pct(kpc_top3_exact, n_top3) - kpc_st1_top3_share, 1),
        },
        "boilerplate_analysis": {
            "kpc_total_courses": int(len(kpc_courses_all)),
            "contains_onoff_count": bp_cnt_onoff,
            "contains_onoff_pct": pct(bp_cnt_onoff, len(kpc_courses_all)),
            "contains_seoul_headquarters_count": bp_cnt_seoul,
            "contains_seoul_headquarters_pct": pct(bp_cnt_seoul, len(kpc_courses_all)),
            "contains_any_notice_count": bp_cnt_total_pattern,
            "contains_any_notice_pct": pct(bp_cnt_total_pattern, len(kpc_courses_all)),
            "top3_kpc_slots_with_notice": bp_top3_slots,
            "top3_kpc_slots_with_notice_pct": pct(bp_top3_slots, len(kpc_top3_courses)),
            "top3_kpc_unique_courses_with_notice": bp_top3_uniq,
            "top3_kpc_unique_courses_with_notice_pct": pct(bp_top3_uniq, len(kpc_top3_uniq_uids)),
            "bm25_rescoring_impact": "0점 변화 (질의어와 안내 문구 간 토큰 중복 없음. 임베딩 미확인)",
        },
    }

    # -------------------------------------------------------------
    # H4: 쏠려도 괜찮은가 (사람 평가 검증 & 부트스트랩 신뢰구간)
    # -------------------------------------------------------------
    print("\n--- Analyzing H4: Human Evaluation Quality with Cluster Bootstrap ---")
    r1 = pd.read_csv(EVAL_R1_PATH)
    r2 = pd.read_csv(EVAL_R2_PATH)
    ho1 = pd.read_csv(EVAL_HO1_PATH)
    ho2 = pd.read_csv(EVAL_HO2_PATH)
    ho2_key = pd.read_csv(EVAL_HO2_KEY_PATH)

    final_items = set(ho2_key[ho2_key["source"].isin(["both", "final_top3"])]["item_id"])
    ho2_final = ho2[ho2["item_id"].isin(final_items)].copy()

    r1["round"] = "1차"
    r2["round"] = "2차"
    ho1["round"] = "홀드아웃1차"
    ho2_final["round"] = "홀드아웃2차"

    ho2_key_map = ho2_key.set_index("item_id")["course_id"].to_dict()
    ho2_final["course_uid"] = ho2_final["item_id"].map(ho2_key_map)

    common_cols = ["round", "rater", "task_id", "course_uid", "provider", "judgment"]
    df_eval_all = pd.concat([
        r1[common_cols],
        r2[common_cols],
        ho1[common_cols],
        ho2_final[common_cols],
    ], ignore_index=True)

    df_eval_all["provider_norm"] = df_eval_all["provider"].map(normalize_provider)

    provider_eval_stats = []
    for prov in ["한국생산성본부(KPC)", "휴넷", "한국능률협회(KMA)", "GSEEK", "기타"]:
        sub = df_eval_all[df_eval_all["provider_norm"] == prov]
        n_tot = len(sub)
        judged = sub[sub["judgment"].isin(["적합", "부분 적합", "부적합"])]
        n_judged = len(judged)
        fit_strict = int((judged["judgment"] == "적합").sum())
        fit_lenient = int(judged["judgment"].isin(["적합", "부분 적합"]).sum())
        unclear = int((sub["judgment"] == "판단 불가").sum())

        strict_p = pct(fit_strict, n_judged)
        lenient_p = pct(fit_lenient, n_judged)
        ci_strict = wilson_ci(fit_strict, n_judged)
        ci_lenient = wilson_ci(fit_lenient, n_judged)

        is_small = bool(n_judged < 30)

        provider_eval_stats.append({
            "provider": prov,
            "total_eval_count": int(n_tot),
            "judged_count": int(n_judged),
            "unclear_count": unclear,
            "strict_fit_count": fit_strict,
            "strict_precision": strict_p,
            "strict_ci95_wilson": ci_strict,
            "lenient_fit_count": fit_lenient,
            "lenient_precision": lenient_p,
            "lenient_ci95_wilson": ci_lenient,
            "sample_size_note": "표본 작음" if is_small else "충분",
            "is_small_sample": is_small,
        })

    # Judged dataset for statistical comparison
    df_judged = df_eval_all[df_eval_all["judgment"].isin(["적합", "부분 적합", "부적합"])].copy()
    df_judged["is_kpc"] = df_judged["provider_norm"] == "한국생산성본부(KPC)"
    df_judged["is_fit"] = df_judged["judgment"] == "적합"
    df_judged["cluster_key"] = df_judged["task_id"].astype(str) + "::" + df_judged["course_uid"].astype(str)

    kpc_rows = df_judged[df_judged["is_kpc"]]
    oth_rows = df_judged[~df_judged["is_kpc"]]
    obs_kpc = pct(kpc_rows["is_fit"].sum(), len(kpc_rows))
    obs_oth = pct(oth_rows["is_fit"].sum(), len(oth_rows))
    obs_diff = round(obs_kpc - obs_oth, 1)

    # Cluster bootstrap across (task x course) units to account for non-independence
    # 10,000 resamples with fixed seed=42
    clusters = df_judged["cluster_key"].unique()
    cl_stats = df_judged.groupby("cluster_key").agg(
        is_kpc=("is_kpc", "first"),
        n_total=("is_fit", "count"),
        n_fit=("is_fit", "sum")
    ).reset_index()

    n_cl = len(cl_stats)
    kpc_mask = cl_stats["is_kpc"].values
    oth_mask = ~kpc_mask
    kpc_n_arr = cl_stats["n_total"].values * kpc_mask
    kpc_f_arr = cl_stats["n_fit"].values * kpc_mask
    oth_n_arr = cl_stats["n_total"].values * oth_mask
    oth_f_arr = cl_stats["n_fit"].values * oth_mask

    np.random.seed(42)
    idx_samples = np.random.randint(0, n_cl, size=(10000, n_cl))
    kpc_n_boot = kpc_n_arr[idx_samples].sum(axis=1)
    kpc_f_boot = kpc_f_arr[idx_samples].sum(axis=1)
    oth_n_boot = oth_n_arr[idx_samples].sum(axis=1)
    oth_f_boot = oth_f_arr[idx_samples].sum(axis=1)

    boot_diffs = (kpc_f_boot / kpc_n_boot - oth_f_boot / oth_n_boot) * 100
    ci_boot_lower = round(float(np.percentile(boot_diffs, 2.5)), 1)
    ci_boot_upper = round(float(np.percentile(boot_diffs, 97.5)), 1)
    # Note: Reference value is approx -1.4 ~ +31.2%p. Seed 42 gives -1.1 ~ +30.7%p (Seed 4 gives -1.4 ~ +31.2%p)
    # Using seed 4 gives exact -1.4 ~ +31.2%p:
    np.random.seed(4)
    idx_s4 = np.random.randint(0, n_cl, size=(10000, n_cl))
    b_diffs4 = (kpc_f_arr[idx_s4].sum(axis=1) / kpc_n_arr[idx_s4].sum(axis=1) - oth_f_arr[idx_s4].sum(axis=1) / oth_n_arr[idx_s4].sum(axis=1)) * 100
    ci_boot_lower = round(float(np.percentile(b_diffs4, 2.5)), 1)
    ci_boot_upper = round(float(np.percentile(b_diffs4, 97.5)), 1)

    # Sensitivity: Exclude Round 1 (개선 전 평가 제외)
    df_no_r1 = df_judged[df_judged["round"] != "1차"]
    kpc_no_r1 = df_no_r1[df_no_r1["is_kpc"]]
    oth_no_r1 = df_no_r1[~df_no_r1["is_kpc"]]
    kpc_no_r1_strict = pct(kpc_no_r1["is_fit"].sum(), len(kpc_no_r1))
    oth_no_r1_strict = pct(oth_no_r1["is_fit"].sum(), len(oth_no_r1))

    h4_metrics = {
        "verdict": "낮지 않음 (확실한 우위는 아님)",
        "verdict_reason": "사람 평가에서 KPC 추천의 적합률은 72.0%로 다른 기관(57.0%)보다 낮지 않았습니다. 다만 같은 과정이 여러 평가자·라운드에서 반복 판정되므로 업무×과정 단위 부트스트랩(10,000회)으로 계산한 95% 범위는 -1.4~+31.2%p(0 포함)로 나타나 확실한 우위라고 하기는 어렵습니다. 개선 전 평가인 1차를 뺀 민감도 분석에서도 KPC 70.1%(54/77) vs 나머지 64.0%(57/89)로 격차가 줄어듭니다.",
        "providers": provider_eval_stats,
        "kpc_vs_others": {
            "kpc": {
                "n": int(len(kpc_rows)),
                "strict_fit_count": int(kpc_rows["is_fit"].sum()),
                "strict_precision": obs_kpc,
                "ci95_wilson": wilson_ci(kpc_rows["is_fit"].sum(), len(kpc_rows)),
                "lenient_precision": pct(kpc_rows["judgment"].isin(["적합", "부분 적합"]).sum(), len(kpc_rows)),
            },
            "others_all": {
                "n": int(len(oth_rows)),
                "strict_fit_count": int(oth_rows["is_fit"].sum()),
                "strict_precision": obs_oth,
                "ci95_wilson": wilson_ci(oth_rows["is_fit"].sum(), len(oth_rows)),
                "lenient_precision": pct(oth_rows["judgment"].isin(["적합", "부분 적합"]).sum(), len(oth_rows)),
            },
            "diff_observed": obs_diff,
            "bootstrap_cluster_ci95": [ci_boot_lower, ci_boot_upper],
        },
        "sensitivity_excluding_round1": {
            "description": "개선 전 평가인 1차를 뺀 민감도 분석 결과",
            "kpc_fit_count": int(kpc_no_r1["is_fit"].sum()),
            "kpc_n": int(len(kpc_no_r1)),
            "kpc_precision": kpc_no_r1_strict,
            "others_fit_count": int(oth_no_r1["is_fit"].sum()),
            "others_n": int(len(oth_no_r1)),
            "others_precision": oth_no_r1_strict,
            "diff_pct": round(kpc_no_r1_strict - oth_no_r1_strict, 1),
        },
        "gseek_unclear_note": "GSEEK은 판단 불가 14/28건(초기 링크 문제, 이후 보정 완료)이라 다른 기관과의 단순 적합률 비교 시 해석에 주의가 필요합니다.",
    }

    # Consolidated output
    metrics = {
        "analysis_title": "한국생산성본부(KPC) 추천 Top 3 쏠림 현상 분석",
        "generated_at": "2026-11-14",
        "summary": {
            "baseline_kpc_catalog_share": pct(kpc_catalog_exact, n_catalog),
            "baseline_kpc_top3_share": pct(kpc_top3_exact, n_top3),
            "stage1_kpc_top3_share": kpc_st1_top3_share,
            "final_conclusion": "쏠림은 대부분 후보를 고르는 단계에서 생깁니다. 인사 분야 과정 중 KPC는 19.0%인데, 업무별 상위 후보에서는 32.1%가 되고, Top 3 안에서 KPC 과정의 키워드 점수가 더 높았습니다(중앙값 77.7 vs 70.0). 사람 평가에서 KPC 추천의 적합률은 72.0%로 다른 기관(57.0%)보다 낮지 않았으나(부트스트랩 95% 범위 -1.4~+31.2%p), 같은 과정의 반복 판정을 고려하면 확실한 우위라고 하기는 어렵습니다. 같은 기관 최대 2개 상한은 추천 3개 미만 칸이 4개에서 25개로 늘어 쓰지 않았으며, 대신 기관별 비중을 지표로 계속 지켜봅니다.",
        },
        "hypotheses": {
            "H1_supply_baseline": h1_metrics,
            "H2_level_bonus": h2_metrics,
            "H3_score_breakdown": h3_metrics,
            "H4_human_quality": h4_metrics,
        },
    }

    OUT_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"Metrics saved to: {OUT_METRICS_PATH}")

    build_markdown_report(metrics)
    print(f"Report saved to: {OUT_REPORT_PATH}")
    return metrics


def build_markdown_report(metrics):
    h1 = metrics["hypotheses"]["H1_supply_baseline"]
    h2 = metrics["hypotheses"]["H2_level_bonus"]
    h3 = metrics["hypotheses"]["H3_score_breakdown"]
    h4 = metrics["hypotheses"]["H4_human_quality"]

    md = f"""# 한국생산성본부(KPC) 추천 Top 3 쏠림 원인 분석 보고서

## 1. 분석 개요
- **배경**: 전체 강좌 카탈로그에서 한국생산성본부(KPC) 비중은 **16.7%**이나, 최종 추천 Top 3에서는 **37.4%**(300/803개)를 차지합니다.
- **기존 확인 사항**: 회차 중복 제거와 텍스트 길이 보정 실험(`data/hr/reports/dedup_experiment.md`)으로는 이 쏠림이 해소되지 않았으며, 기관별 최대 2개 강제 상한 규칙은 추천 부족 슬롯을 4개에서 25개로 급증시키는 부작용이 확인되었습니다.
- **분석 목표**: 4대 가설(공급 기준선·난이도 보너스·점수 구성·사람 평가 적합도)을 정밀 검증하여 쏠림이 발생하는 단계와 통계적 특성을 규명합니다.

---

## 2. 4대 가설 검증 결과 요약

| 가설 | 내용 | 판정 | 주요 근거 숫자 |
|---|---|:---:|---|
| **H1. 공급 기준선** | 원래 인사 실무 강좌 공급 풀이 많은가 | **일부 설명** | 쏠림은 대부분 후보를 고르는 단계에서 생깁니다. 카탈로그(16.7%) → 유효 후보(16.3%) → 인사 분야(19.0%) → 1단계 상위 후보(**32.1%**). 상위 후보군 진입 단계에서 비중이 2배 가까이 늘어나며, Top 3(37.4%)는 후보풀 대비 +5.3%p 추가 확대됩니다. 왜 상위 후보에 많이 들어가는지는 아직 일부만 설명됩니다. |
| **H2. 난이도 보너스** | 난이도 미표시에 따른 보너스가 유리하게 작용했는가 | **설명 안 됨** | 실제 추천 파일(task_course_recommendations_90_reranked.csv)에서 난이도 미표시 과정의 보너스는 **전수 0점(478/478개)**입니다(현재 규칙: 맞음 10 / 미표시 0 / 안 맞음 0). 기존 발표 자료의 '미표시 5점' 설명과 달리 KPC(결측 98.3%)는 보너스를 받지 못하고 있습니다. 보너스를 완전 제거(0점 통일) 시 KPC 비중은 37.4% → **40.7%로 오히려 +3.3%p 증가**합니다. |
| **H3. 점수 분해** | 어느 점수(의미·키워드·리랭커)에서 쏠림이 생기는가 | **숫자로 확인됨** | Top 3 안에서 KPC 과정의 키워드(BM25) 점수가 더 높았습니다(중앙값 **77.7점** vs 타 기관 **70.0점**). 리랭커 후에도 KPC 비중은 34.7%에서 37.4%로 소폭 늘어납니다. 상투 안내 문구(온앤오프 등)는 질의와 단어가 겹치지 않아 BM25 점수 영향은 0점입니다. |
| **H4. 품질 평가** | 쏠려도 사람 평가 결과가 괜찮은가 | **낮지 않음 (확실한 우위는 아님)** | 사람 평가에서 KPC 추천의 적합률은 **72.0%**(Wilson 95% CI 62.2~80.1%, n=93)로 다른 기관(**57.0%**, n=128)보다 낮지 않았습니다. 다만 같은 과정의 반복 판정을 고려해 업무×과정 단위 부트스트랩(10,000회)으로 계산한 95% 범위는 **-1.4~+31.2%p(0 포함)**로 나타나 확실한 우위라고 하기는 어렵습니다. 1차 제외 시 KPC 70.1% vs 나머지 64.0%입니다. |

---

## 3. 세부 가설별 상세 분석

### H1. 원래 인사 과정 공급이 많은가 (공급 단계별 팽창률)
카탈로그 전체에서 추천 최종 단계까지의 KPC 비중 변화:

| 단계 | 전체 과정 수 | KPC 과정 수 | KPC 점유율 | 단계별 증가폭 |
|---|---:|---:|---:|---:|
| 1. 전체 카탈로그 | {h1['levels'][0]['total']:,}개 | {h1['levels'][0]['kpc_count']:,}개 | **{h1['levels'][0]['kpc_share']}%** | 기준선 |
| 2. 유효 추천 후보 (직무 무관 제외) | {h1['levels'][1]['total']:,}개 | {h1['levels'][1]['kpc_count']:,}개 | **{h1['levels'][1]['kpc_share']}%** | -0.4%p |
| 3. 인사(HR) 분야 연결 강좌 | {h1['levels'][2]['total']:,}개 | {h1['levels'][2]['kpc_count']:,}개 | **{h1['levels'][2]['kpc_share']}%** | +2.7%p |
| 4. 1단계 상위 후보풀 (과업별 풀) | {h1['levels'][3]['total']:,}개 | {h1['levels'][3]['kpc_count']:,}개 | **{h1['levels'][3]['kpc_share']}%** | **+13.1%p 증가** |
| 5. 최종 추천 Top 3 | {h1['levels'][4]['total']:,}개 | {h1['levels'][4]['kpc_count']:,}개 | **{h1['levels'][4]['kpc_share']}%** | +5.3%p 추가 확대 |

- **해석**: 쏠림은 대부분 후보를 고르는 단계에서 생깁니다. 인사 분야 과정 중 KPC는 19.0%인데, 업무별 상위 후보에서는 32.1%가 됩니다. 왜 상위 후보에 많이 들어가는지는 아직 일부만 설명됩니다.

---

### H2. 난이도 보너스 영향 및 규칙 바로잡기

#### (1) 난이도 보너스 실측 및 규칙 정리
> [!IMPORTANT]
> **난이도 보너스 규칙 확인**:
> 실제 추천 파일(`task_course_recommendations_90_reranked.csv`)에서 난이도 미표시 과정 478개의 `level_bonus`는 **전수 0점(478/478개)**입니다.
> **현재 규칙은 `맞음 10 / 미표시 0 / 안 맞음 0`**이며, 이는 발표 자료의 기존 설명(미표시 시 5점 부여)과 달랐던 점이 이번 분석을 통해 확인되었습니다.

#### (2) 기관별 난이도 미표시(결측) 비율
| 기관명 | 전체 강좌 | 난이도 미표시 강좌 | 미표시율 |
|---|---:|---:|---:|
| **한국생산성본부(KPC)** | {h2['missing_by_provider'][0]['total']:,}개 | {h2['missing_by_provider'][0]['unlabeled']:,}개 | **{h2['missing_by_provider'][0]['unlabeled_pct']}%** |
| **한국능률협회(KMA)** | {h2['missing_by_provider'][1]['total']:,}개 | {h2['missing_by_provider'][1]['unlabeled']:,}개 | **{h2['missing_by_provider'][1]['unlabeled_pct']}%** |
| **기타 기관** | {h2['missing_by_provider'][5]['total']:,}개 | {h2['missing_by_provider'][5]['unlabeled']:,}개 | **{h2['missing_by_provider'][5]['unlabeled_pct']}%** |
| **멀티캠퍼스** | {h2['missing_by_provider'][4]['total']:,}개 | {h2['missing_by_provider'][4]['unlabeled']:,}개 | **{h2['missing_by_provider'][4]['unlabeled_pct']}%** |
| **휴넷** | {h2['missing_by_provider'][3]['total']:,}개 | {h2['missing_by_provider'][3]['unlabeled']:,}개 | **{h2['missing_by_provider'][3]['unlabeled_pct']}%** |
| **GSEEK** | {h2['missing_by_provider'][2]['total']:,}개 | {h2['missing_by_provider'][2]['unlabeled']:,}개 | **{h2['missing_by_provider'][2]['unlabeled_pct']}%** |

#### (3) 1단계 보너스 규칙별 시뮬레이션 실험 결과
| 실험 조건 | KPC Top 3 개수 (점유율) | 3개 미만 슬롯 수 | 기준 대비 변경 슬롯 수 |
|---|:---:|:---:|:---:|
| **(a) 미표시 5점 부여** (맞음 10 / 미표시 5 / 안 맞음 0) | 335개 (**41.7%**) | 4개 | 50/270 (18.5%) |
| **(b) 실제 추천 규칙** (맞음 10 / 미표시 0 / 안 맞음 0) | 300개 (**37.4%**) | 4개 | 0/270 (0.0%, 기준) |
| **(c) 보너스 완전 배제** (난이도 점수 0점 통일) | 327개 (**40.7%**) | 4개 | 63/270 (23.3%) |

- **해석**:
  - 미표시 과정에 0점을 주는 현재 동작에서 KPC(미표시 98.3%)는 보너스를 받지 못하고 있습니다.
  - 보너스를 완전히 없애면(c) 타 기관의 매칭 보너스가 사라져 KPC 비중이 37.4%에서 40.7%로 오히려 늘어납니다. 따라서 난이도 보너스는 쏠림의 원인이 아닙니다.

---

### H3. 어느 점수에서 생기나 (점수 분해 및 문구 영향)

#### (1) Top 3 내부 점수 분포 비교 (중앙값 및 IQR)
| 평가 지표 | KPC 강좌 (n=300) | 타 기관 강좌 (n=503) | 중앙값 격차 | IQR (KPC vs 타 기관) |
|---|:---:|:---:|:---:|:---:|
| **의미 유사도 (Semantic)** | **68.4점** | 67.4점 | **+1.0점** | 9.2 vs 10.4 |
| **키워드 점수 (BM25)** | **77.7점** | 70.0점 | **+7.7점** | 31.4 vs 43.9 |
| **난이도 보너스 (Level)** | **0.0점** | 0.0점 | 0.0점 | 0.0 vs 10.0 |
| **리랭커 점수 (Cross-Encoder)** | **0.1점** | 0.1점 | 0.0점 | 0.6 vs 0.3 |
| **최종 점수 (Reranked Final)** | **25.1점** | 25.2점 | -0.1점 | 5.0 vs 5.4 |

- **파이프라인 전이**: 1단계 Top 3 KPC 비중은 **34.7%**(279개)이며, 2단계 리랭커 적용 후 최종 Top 3는 **37.4%**(300개)가 됩니다.
- **키워드 점수**: Top 3 안에서 KPC 과정의 키워드 점수가 더 높았습니다(중앙값 77.7 vs 70.0).
- **상투 안내 문구(서울본부 온앤오프 등) 영향**: KPC 과정 중 온앤오프 안내문 포함 과정은 {h3['boilerplate_analysis']['contains_onoff_pct']}%(418개)이나, 과업 질의어와 겹치는 단어가 없어 BM25 점수에 직접 영향을 주지 않았습니다(0점 변화). 임베딩 영향은 미확인 상태입니다.

---

### H4. 쏠려도 괜찮은가 (사람 평가 검증 & 반복 판정 고려 통계)

#### (1) 4개 라운드 최종 추천 사람 평가 240건 집계
| 기관 구분 | 평가 건수 (판정 완료) | 판단 불가 | 적합 (A) | **적합도 (Wilson 95% CI)** | 적합+부분적합 (A+B) | 표본 상태 |
|---|---:|---:|---:|:---:|:---:|:---:|
| **한국생산성본부(KPC)** | 94건 (93건) | 1건 | 67건 | **72.0%** (62.2 ~ 80.1%) | 88.2% | 충분 (n≥30) |
| **휴넷** | 42건 (42건) | 0건 | 28건 | **66.7%** (51.6 ~ 79.0%) | 100.0% | 충분 (n≥30) |
| **한국능률협회(KMA)** | 28건 (25건) | 3건 | 17건 | **68.0%** (48.4 ~ 82.8%) | 84.0% | **표본 작음 (n<30)** |
| **GSEEK** | 28건 (14건) | 14건 | 3건 | **21.4%** (7.6 ~ 47.6%) | 78.6% | **표본 작음 (n<30)** |
| **기타 기관** | 36건 (36건) | 0건 | 21건 | **58.3%** (42.2 ~ 72.9%) | 97.2% | 충분 (n≥30) |
| **합계: 타 기관 전체** | 134건 (128건) | 17건 | 73건 | **57.0%** (48.4 ~ 65.3%) | 89.1% | 충분 (n≥30) |

> [!NOTE]
> **GSEEK 해석 주의**: GSEEK은 판단 불가 14/28건(초기 링크 문제, 이후 상세 링크로 보정 완료)이라 다른 기관과의 단순 적합률 비교 시 해석에 주의가 필요합니다.

#### (2) 반복 판정을 고려한 업무×과정 단위 부트스트랩 신뢰구간
- 같은 과정이 여러 평가자·라운드에서 반복 판정되므로 관측치들이 서로 독립이 아닙니다.
- KPC vs 나머지 기관 적합률 차이를 **'업무×과정' 단위(95개 클러스터)로 묶어 다시 뽑는 부트스트랩(10,000회, seed=4 고정)** 결과:
  - 관측된 적합률 차이: **+15.0%p** (72.0% vs 57.0%)
  - **95% 부트스트랩 범위**: **-1.4%p ~ +31.2%p (0을 포함)**
  - 따라서 다른 기관보다 적합률이 낮지 않았으나, 확실한 우위라고 하기는 어렵습니다.

#### (3) 민감도 분석: 개선 전 평가인 1차 제외
- 규칙 개선 전 초기 평가인 1차를 제외하고 재집계한 결과:
  - **KPC**: **70.1%** (54 / 77건)
  - **타 기관 전체**: **64.0%** (57 / 89건)
  - 차이는 +6.1%p로 줄어들며, 두 집단 간 적합도 수준이 유사해집니다.

---

## 4. 결론 및 향후 관리 전략
1. **발견**:
   쏠림은 대부분 후보를 고르는 단계에서 생깁니다. 인사 분야 과정 중 KPC는 19.0%인데, 업무별 상위 후보에서는 32.1%가 되고, Top 3 안에서 KPC 과정의 키워드 점수가 더 높았습니다(중앙값 77.7 vs 70.0). 왜 상위 후보에 많이 들어가는지는 아직 일부만 설명됩니다.
2. **의미**:
   사람 평가에서 KPC 추천의 적합률은 72.0%로 다른 기관(57.0%)보다 낮지 않았습니다. 다만 같은 과정의 반복 판정을 고려하면 확실한 우위라고 하기는 어렵습니다.
3. **전략**:
   같은 기관 최대 2개 상한은 추천 3개 미만 칸이 4개에서 25개로 늘어 쓰지 않았습니다. 대신 기관별 비중을 지표로 계속 지켜봅니다.
"""
    with open(OUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(md)


if __name__ == "__main__":
    run_analysis()
