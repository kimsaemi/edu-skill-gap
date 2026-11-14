# -*- coding: utf-8 -*-
"""
홀드아웃 3차 모의 평가 집계 로직 및 위약 검정 단위 테스트 (test_holdout3_metrics.py)

규칙 준수:
- 실제 사람 평가 파일(precision_eval_holdout3_items.csv)을 수정하거나 평가 결과를 디스크에 쓰지 않습니다.
- 메모리 상의 가상 판정 데이터(Mock)로만 calculate_holdout3_metrics의 계산식, 통계적 유효성, 위약 탐지 로직을 검증합니다.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.apply_precision_eval_results import calculate_holdout3_metrics

KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_key.csv"
ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_items.csv"


def test_holdout3_mock_metrics():
    print("=== 1. Testing calculate_holdout3_metrics with Mock Data ===")
    assert KEY_PATH.exists(), f"Key file {KEY_PATH} not found"
    assert ITEMS_PATH.exists(), f"Items file {ITEMS_PATH} not found"

    df_key = pd.read_csv(KEY_PATH)
    df_items = pd.read_csv(ITEMS_PATH, dtype=str).fillna("")

    # 1. 실제 평가 시트의 빈칸 보존 여부 검증 (규칙 1)
    assert (df_items["판정 (고르기)"] == "").all(), "실제 items 파일의 판정 칸은 반드시 100% 빈칸이어야 합니다!"
    assert (df_items["메모 (선택)"] == "").all(), "실제 items 파일의 메모 칸은 반드시 100% 빈칸이어야 합니다!"
    print(f"[PASS] 실제 {ITEMS_PATH.name} 파일 100% 빈칸 상태 검증 완료 ({len(df_items)}행)")

    # 2. 메모리 상의 단일 평가자 가상 판정 데이터 생성
    mock_df = df_items.copy()
    key_map = dict(zip(df_key["번호"], df_key["출처"]))

    rng = np.random.default_rng(42)
    mock_judgments = []

    for _, row in mock_df.iterrows():
        source = key_map.get(int(row["번호"]))
        if source == "decoy":
            # 디코이: 90% 부적합, 10% 부분 적합
            j = rng.choice(["부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부적합", "부분 적합"])
        elif source == "candidate":
            # 개선안 단독: 70% 적합, 30% 부분 적합
            j = rng.choice(["적합", "적합", "적합", "적합", "적합", "적합", "적합", "부분 적합", "부분 적합", "부분 적합"])
        elif source == "baseline":
            # 기본 추천 단독: 40% 적합, 40% 부분 적합, 20% 부적합
            j = rng.choice(["적합", "적합", "부분 적합", "부분 적합", "부적합"])
        else:  # shared
            # 공통 추천: 70% 적합, 25% 부분 적합, 5% 부적합
            j = rng.choice(["적합", "적합", "적합", "적합", "적합", "부분 적합", "부분 적합", "부적합"])
        mock_judgments.append(j)

    mock_df["판정 (고르기)"] = mock_judgments

    # 3. 집계 실행 (단일 평가자 모의)
    result = calculate_holdout3_metrics(mock_df, df_key, rng=np.random.default_rng(42))

    assert result["status"] == "완료", f"Status should be 완료, got {result['status']}"
    assert result["entered"] == len(mock_df), "Entered count should match mock_df length"

    # Candidate 검증
    cand_p = result["candidate_recommendation"]["precision_at_3"]
    cand_c = result["candidate_recommendation"]["consensus"]
    assert cand_p["n"] > 0, "Candidate precision n should be > 0"
    assert cand_p["strict"] is not None and cand_p["strict"] > 0, "Candidate strict precision should be > 0"
    assert len(cand_p["ci95_wilson"]) == 2, "Wilson CI format invalid"
    assert len(cand_p["ci95_cluster_bootstrap"]) == 2, "Cluster bootstrap CI format invalid"
    assert cand_c["strict"] is not None and cand_c["strict"] > 0, "Candidate consensus strict should be > 0"
    print(f"[PASS] Candidate Recommendation Precision@3 A={cand_p['strict']}% (Wilson {cand_p['ci95_wilson']}), Consensus B={cand_c['strict']}%")

    # Baseline 검증
    base_p = result["baseline_recommendation"]["precision_at_3"]
    base_c = result["baseline_recommendation"]["consensus"]
    assert base_p["n"] > 0, "Baseline precision n should be > 0"
    assert base_p["strict"] is not None and base_p["strict"] > 0, "Baseline strict precision should be > 0"
    print(f"[PASS] Baseline Recommendation Precision@3 A={base_p['strict']}% (Wilson {base_p['ci95_wilson']}), Consensus B={base_c['strict']}%")

    # 성능 차이 검증
    cmp = result["comparison"]
    assert cmp["diff_strict_a"] is not None, "diff_strict_a should not be None"
    assert cmp["ci95_diff_a"] is not None and len(cmp["ci95_diff_a"]) == 2, "diff_a CI invalid"
    print(f"[PASS] Performance Difference: A Diff={cmp['diff_strict_a']}%p (95% CI {cmp['ci95_diff_a']}), B Diff={cmp['diff_strict_b']}%p")

    # 디코이 검정 검증
    dec = result["decoy_analysis"]
    assert dec["total_items"] == 10, f"Expected 10 decoy items, got {dec['total_items']}"
    assert dec["total_evaluations"] == 10, f"Expected 10 decoy evals, got {dec['total_evaluations']}"
    assert dec["filter_success_rate"] is not None and dec["filter_success_rate"] >= 70.0, (
        f"Expected high decoy filter success rate, got {dec['filter_success_rate']}%"
    )
    print(f"[PASS] Decoy Validation: Filter Success Rate={dec['filter_success_rate']}% ({dec['unfit_count']}/{dec['total_evaluations']})")

    # 4. 2인 평가자 교차 모의 테스트 (김, 이 평가자)
    print("\n=== 2. Testing 2-Rater Paired Evaluation ===")
    mock_df_2r = []
    for rater_name in ["김", "이"]:
        r_df = mock_df.copy()
        r_df["평가자"] = rater_name
        # 약간의 노이즈 추가
        noisy_judgments = []
        for j in mock_judgments:
            if rng.random() < 0.15:
                noisy_judgments.append(rng.choice(["적합", "부분 적합", "부적합"]))
            else:
                noisy_judgments.append(j)
        r_df["판정 (고르기)"] = noisy_judgments
        mock_df_2r.append(r_df)
    mock_2r_all = pd.concat(mock_df_2r, ignore_index=True)

    result_2r = calculate_holdout3_metrics(mock_2r_all, df_key, rng=np.random.default_rng(42))
    assert result_2r["status"] == "완료"
    assert result_2r["entered"] == len(mock_2r_all)
    assert len(result_2r["raters"]) == 2, "Should have 2 raters"
    assert result_2r["decoy_analysis"]["total_evaluations"] == 20, "2 raters x 10 items = 20 decoy evals"
    print(f"[PASS] 2-Rater Evaluation: Assigned={result_2r['assigned']}, Raters={[r['rater'] for r in result_2r['raters']]}")

    print("\n[ALL PASS] test_holdout3_metrics.py 모든 검증 성공적으로 통과")


if __name__ == "__main__":
    test_holdout3_mock_metrics()
