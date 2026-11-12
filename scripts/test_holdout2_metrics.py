# -*- coding: utf-8 -*-
"""
홀드아웃 2차 평가 집계 로직 및 위약 검정 단위 테스트 (test_holdout2_metrics.py)

규칙 준수:
- 실제 사람 평가 파일(precision_eval_holdout2_items.csv 등)을 수정하거나 평가 결과를 덮어쓰지 않습니다.
- 메모리 상의 가상 판정 데이터(Mock)로만 calculate_holdout2_metrics의 계산식, 통계적 유효성, 위약 탐지 로직을 검증합니다.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.apply_precision_eval_results import calculate_holdout2_metrics, build_holdout_all_df

KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_key.csv"
ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_items.csv"
RESULTS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_results.csv"


def test_holdout2_mock_metrics():
    print("=== 1. Testing calculate_holdout2_metrics with Mock Data ===")
    assert KEY_PATH.exists(), f"Key file {KEY_PATH} not found"
    assert ITEMS_PATH.exists(), f"Items file {ITEMS_PATH} not found"

    df_key = pd.read_csv(KEY_PATH)
    df_items = pd.read_csv(ITEMS_PATH, dtype=str).fillna("")

    # 1. Verify actual items file has blank judgments (Rule 1 preservation check)
    assert (df_items["judgment"] == "").all(), "Actual items file must have completely blank judgments!"
    print("[PASS] Actual precision_eval_holdout2_items.csv has 100% blank judgments")

    # 2. Construct mock results in memory
    mock_df = df_items.copy()
    key_map = dict(zip(df_key["item_id"], df_key["source"]))

    rng = np.random.default_rng(123)
    mock_judgments = []

    for _, row in mock_df.iterrows():
        source = key_map.get(int(row["item_id"]))
        if source == "decoy":
            # Decoy: 90% unfit, 10% partial fit/fit
            j = rng.choice(["부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부분 적합"])
        elif source == "final_top3":
            # Final top3: 75% fit, 20% partial, 5% unfit
            j = rng.choice(["적합", "적합", "적합", "부분 적합", "부적합"])
        elif source == "bm25_top3":
            # BM25 top3: 45% fit, 35% partial, 20% unfit
            j = rng.choice(["적합", "부분 적합", "부적합", "부분 적합"])
        else:  # both
            j = rng.choice(["적합", "적합", "부분 적합"])
        mock_judgments.append(j)

    mock_df["judgment"] = mock_judgments

    # 3. Run calculate_holdout2_metrics
    result = calculate_holdout2_metrics(mock_df, df_key, rng=np.random.default_rng(42))

    assert result["status"] == "완료", f"Status should be 완료, got {result['status']}"
    assert result["entered"] == len(mock_df), "Entered count should match mock_df length"

    # Final recommendations check
    fin_p = result["final_recommendation"]["precision_at_3"]
    fin_c = result["final_recommendation"]["consensus"]
    assert fin_p["n"] > 0, "Final precision n should be > 0"
    assert fin_p["strict"] is not None and fin_p["strict"] > 0, "Final strict precision should be > 0"
    assert len(fin_p["ci95_wilson"]) == 2, "Wilson CI format invalid"
    assert len(fin_p["ci95_cluster_bootstrap"]) == 2, "Cluster bootstrap CI format invalid"
    assert fin_c["strict"] is not None and fin_c["strict"] > 0, "Final consensus strict should be > 0"
    print(f"[PASS] Final Recommendation Precision@3 A={fin_p['strict']}% (Wilson {fin_p['ci95_wilson']}), Consensus B={fin_c['strict']}%")

    # BM25 recommendations check
    bm_p = result["bm25_recommendation"]["precision_at_3"]
    bm_c = result["bm25_recommendation"]["consensus"]
    assert bm_p["n"] > 0, "BM25 precision n should be > 0"
    assert bm_p["strict"] is not None and bm_p["strict"] > 0, "BM25 strict precision should be > 0"
    assert fin_p["strict"] > bm_p["strict"], f"Expected final strict ({fin_p['strict']}) > bm25 strict ({bm_p['strict']})"
    print(f"[PASS] BM25 Recommendation Precision@3 A={bm_p['strict']}% (Wilson {bm_p['ci95_wilson']}), Consensus B={bm_c['strict']}%")

    # Difference check
    cmp = result["comparison"]
    assert cmp["diff_strict_a"] is not None and cmp["diff_strict_a"] > 0, "diff_strict_a should be positive"
    assert cmp["ci95_diff_a"] is not None and len(cmp["ci95_diff_a"]) == 2, "diff_a CI invalid"
    assert cmp["diff_strict_b"] is not None and cmp["diff_strict_b"] > 0, "diff_strict_b should be positive"
    print(f"[PASS] Performance Difference: A Diff={cmp['diff_strict_a']}%p (95% CI {cmp['ci95_diff_a']}), B Diff={cmp['diff_strict_b']}%p")

    # Decoy analysis check
    dec = result["decoy_analysis"]
    assert dec["total_items"] == 10, f"Expected 10 decoy items, got {dec['total_items']}"
    assert dec["total_evaluations"] == 20, f"Expected 20 decoy evals (2 raters x 10 items), got {dec['total_evaluations']}"
    assert dec["filter_success_rate"] is not None and dec["filter_success_rate"] >= 70.0, (
        f"Expected high decoy filter success rate, got {dec['filter_success_rate']}%"
    )
    assert dec["passed_count"] == len(dec["false_positives"]), "passed_count must match false_positives list length"
    print(f"[PASS] Decoy Analysis: Normal Filter Rate={dec['filter_success_rate']}%, False Positives={dec['passed_count']}")

    # 4. Verify actual files remain completely untouched
    df_items_recheck = pd.read_csv(ITEMS_PATH, dtype=str).fillna("")
    assert (df_items_recheck["judgment"] == "").all(), "Actual items file judgment was contaminated!"
    print("[PASS] Zero side-effects: actual items file remains untouched with blank judgments")


def test_holdout_all_combine():
    print("\n=== 2. Testing build_holdout_all_df (Holdout 1 + Holdout 2 Final Only) ===")
    df_h1 = pd.DataFrame([
        {"item_no": "1", "rater": "김", "domain": "D1", "task": "T1", "level": "실무", "rank": "1", "title": "C1", "provider": "P1", "judgment": "적합"},
        {"item_no": "1", "rater": "이", "domain": "D1", "task": "T1", "level": "실무", "rank": "1", "title": "C1", "provider": "P1", "judgment": "적합"},
        {"item_no": "2", "rater": "김", "domain": "D1", "task": "T1", "level": "실무", "rank": "2", "title": "C2", "provider": "P1", "judgment": "부분 적합"},
        {"item_no": "2", "rater": "이", "domain": "D1", "task": "T1", "level": "실무", "rank": "2", "title": "C2", "provider": "P1", "judgment": "적합"},
    ])
    df_h2 = pd.DataFrame([
        {"item_id": "1", "rater": "박", "domain": "D2", "task": "T2", "level": "입문", "title": "C3", "provider": "P2", "judgment": "적합"},
        {"item_id": "1", "rater": "홍", "domain": "D2", "task": "T2", "level": "입문", "title": "C3", "provider": "P2", "judgment": "부적합"},
        {"item_id": "2", "rater": "박", "domain": "D2", "task": "T2", "level": "입문", "title": "C4", "provider": "P2", "judgment": "적합"},
        {"item_id": "2", "rater": "홍", "domain": "D2", "task": "T2", "level": "입문", "title": "C4", "provider": "P2", "judgment": "적합"},
        {"item_id": "3", "rater": "박", "domain": "D2", "task": "T2", "level": "입문", "title": "C5", "provider": "P2", "judgment": "부적합"},
        {"item_id": "3", "rater": "홍", "domain": "D2", "task": "T2", "level": "입문", "title": "C5", "provider": "P2", "judgment": "부적합"},
    ])
    df_k = pd.DataFrame([
        {"item_id": 1, "source": "final_top3"},
        {"item_id": 2, "source": "bm25_top3"},
        {"item_id": 3, "source": "decoy"},
    ])

    combined = build_holdout_all_df(df_h1, df_h2, df_k)
    assert len(combined) == 6, f"Expected 6 rows (4 from H1 + 2 from H2 final_top3), got {len(combined)}"
    assert set(combined["combined_item_id"]) == {"h1_1", "h1_2", "h2_1"}, f"Unexpected IDs: {set(combined['combined_item_id'])}"
    assert "bm25_top3" not in set(combined["source"])
    assert "decoy" not in set(combined["source"])

    # Consensus count check (should be 3 distinct items: h1_1=적합, h1_2=부분 적합, h2_1=부적합)
    rank_of = {"적합": 2, "부분 적합": 1, "부적합": 0}
    item = (
        combined[combined["judgment"].isin(rank_of)]
        .assign(score=lambda x: x["judgment"].map(rank_of))
        .groupby(["combined_item_id"], as_index=False)
        .agg(score=("score", "min"))
    )
    assert len(item) == 3, f"Expected 3 consensus items, got {len(item)}"
    assert (RESULTS_PATH.exists()), "precision_eval_holdout2_results.csv should exist"
    df_res = pd.read_csv(RESULTS_PATH, dtype=str).fillna("")
    assert (df_res["judgment"] != "").sum() > 0, "results.csv should contain entered judgments from sheet"
    print("[PASS] holdout_all excludes bm25/decoy, separates h1_/h2_ IDs, and produces 3 consensus items")


if __name__ == "__main__":
    test_holdout2_mock_metrics()
    test_holdout_all_combine()
    print("\nAll tests in test_holdout2_metrics.py PASSED!")
