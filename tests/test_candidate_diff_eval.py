# -*- coding: utf-8 -*-
"""
tests/test_candidate_diff_eval.py
추천 정확도 개선안 재평가 단위 테스트

검증 항목:
1. 차이 숫자 정확성: 다른 칸 17개, 업무 11개, side별 과정 22개, 미평가 50개 업무 차이 0개
2. key와 시트의 행 수 일치 (len(df_key) == len(df_sheet) == 64)
3. 시트에 side/retest 정보 누출 여부 (블라인드 철저 검증)
4. 동일 업무 연속 배치 금지 규칙 준수
5. 가짜 판정(Mock)을 통한 계산 및 메트릭 산출 무결성
"""

import sys
import unittest
import json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIFF_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_items.csv"
ITEMS_SHEET_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_items.csv"
KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_key.csv"

from scripts.analyze_candidate_diff_eval import analyze_candidate_diff, compute_side_precision, compute_cluster_bootstrap


class TestCandidateDiffEval(unittest.TestCase):

    def test_01_diff_numbers_exact_match(self):
        """차이 목록 숫자 검증 (17개 칸, 11개 업무, side별 22개, 판정 필요 22개)"""
        self.assertTrue(DIFF_ITEMS_PATH.exists(), f"차이 목록 파일 누락: {DIFF_ITEMS_PATH}")
        df = pd.read_csv(DIFF_ITEMS_PATH)

        self.assertEqual(len(df), 44, f"차이 항목 총합 오류: {len(df)} != 44")
        base_cnt = (df["side"] == "baseline_only").sum()
        cand_cnt = (df["side"] == "candidate_only").sum()
        self.assertEqual(base_cnt, 22, f"기본 전용 과정 수 오류: {base_cnt} != 22")
        self.assertEqual(cand_cnt, 22, f"개선안 전용 과정 수 오류: {cand_cnt} != 22")

        diff_tasks = df["task_id"].nunique()
        self.assertEqual(diff_tasks, 11, f"차이 업무 수 오류: {diff_tasks} != 11")

        diff_cells = df.groupby(["task_id", "level"]).ngroups
        self.assertEqual(diff_cells, 17, f"차이 칸 수 오류: {diff_cells} != 17")

        need_cnt = (df["eval_status"] == "판정 필요").sum()
        already_cnt = (df["eval_status"] == "판정 완료").sum()
        self.assertEqual(need_cnt, 22, f"판정 필요 과정 수 오류: {need_cnt} != 22")
        self.assertEqual(already_cnt, 22, f"판정 완료 과정 수 오류: {already_cnt} != 22")

    def test_02_key_and_sheet_row_counts_match(self):
        """key와 시트의 행 수가 정확히 같은지 확인 (len(key) == len(sheet))"""
        self.assertTrue(ITEMS_SHEET_PATH.exists(), f"시트 파일 누락: {ITEMS_SHEET_PATH}")
        self.assertTrue(KEY_PATH.exists(), f"키 파일 누락: {KEY_PATH}")

        df_sheet = pd.read_csv(ITEMS_SHEET_PATH)
        df_key = pd.read_csv(KEY_PATH)

        # key와 시트의 행 수 일치
        self.assertEqual(len(df_key), len(df_sheet), f"key 행 수({len(df_key)})와 시트 행 수({len(df_sheet)}) 불일치")
        self.assertEqual(len(df_sheet), 64, f"시트 행 수 오류 (32개 항목 * 2인 평가): {len(df_sheet)} != 64")
        self.assertEqual(len(df_key), 64, f"키 행 수 오류: {len(df_key)} != 64")

        # 고유 item_id 일치 (32개)
        self.assertEqual(df_sheet["item_id"].nunique(), 32)
        self.assertEqual(df_key["item_id"].nunique(), 32)

    def test_03_no_side_or_retest_leak_in_sheet(self):
        """시트에 side(기본/개선안) 및 retest(재판정) 정보가 새지 않는지 전수 확인"""
        df_sheet = pd.read_csv(ITEMS_SHEET_PATH, dtype=str).fillna("")

        # 1. 컬럼명 검사
        forbidden_col_keywords = ["side", "source", "baseline", "candidate", "retest", "기본", "개선안", "재판정"]
        for col in df_sheet.columns:
            for kw in forbidden_col_keywords:
                self.assertNotIn(kw, col.lower(), f"시트 컬럼명에 side 정보 누출: {col}")

        # 2. 데이터 값 검사
        forbidden_val_keywords = ["baseline_only", "candidate_only", "is_retest"]
        for col in df_sheet.columns:
            for val in df_sheet[col]:
                for kw in forbidden_val_keywords:
                    self.assertNotIn(kw, str(val).lower(), f"시트 데이터 값에 side/retest 누출: {col}={val}")

        # 3. rater, judgment, memo 빈칸 유지 확인
        self.assertTrue((df_sheet["rater"] == "").all(), "시트의 rater 열은 100% 빈칸이어야 합니다.")
        self.assertTrue((df_sheet["judgment"] == "").all(), "시트의 judgment 열은 100% 빈칸이어야 합니다.")
        self.assertTrue((df_sheet["memo"] == "").all(), "시트의 memo 열은 100% 빈칸이어야 합니다.")

    def test_04_no_consecutive_tasks_in_sheet(self):
        """시트에서 같은 업무의 항목이 연달아 나오지 않는지 확인"""
        df_sheet = pd.read_csv(ITEMS_SHEET_PATH)
        # item_id 순으로 정렬 후 고유 항목 추출
        unique_items = df_sheet.drop_duplicates("item_id").sort_values("item_id").reset_index(drop=True)

        for i in range(1, len(unique_items)):
            prev_task = unique_items.loc[i - 1, "task_id"]
            curr_task = unique_items.loc[i, "task_id"]
            self.assertNotEqual(prev_task, curr_task, f"동일 업무 연속 배치 발견: item {i} ({prev_task}) and item {i+1} ({curr_task})")

    def test_05_mock_evaluation_pipeline(self):
        """가짜 판정(Mock)으로 계산 로직 및 판단 규칙이 맞는지 확인"""
        metrics = analyze_candidate_diff(is_mock=True)

        self.assertIsNotNone(metrics)
        self.assertIn("baseline_recommendation", metrics)
        self.assertIn("candidate_recommendation", metrics)
        self.assertIn("comparison", metrics)

        b = metrics["baseline_recommendation"]
        c = metrics["candidate_recommendation"]
        cmp = metrics["comparison"]

        # 평가 건수 (총 88건 중 기존 2건 '판단 불가' 제외 86건 유효 판정)
        self.assertEqual(metrics["sample_counts"]["total_combined_evaluations"], 88)
        self.assertEqual(b["n"] + c["n"], 86, f"유효 평가 건수 오류: {b['n'] + c['n']} != 86")

        # 95% 부트스트랩 범위 계산 확인
        ci_boot = cmp["ci95_diff_strict_bootstrap"]
        self.assertEqual(len(ci_boot), 2)
        self.assertLessEqual(ci_boot[0], ci_boot[1])

        # 사전 고정 판단 규칙 검증
        if ci_boot[0] > 0:
            self.assertEqual(cmp["decision"], "개선안 쪽이 높음")
        elif ci_boot[1] < 0:
            self.assertEqual(cmp["decision"], "기본 쪽이 높음")
        else:
            self.assertEqual(cmp["decision"], "차이를 확인하지 못함")

        # 필수 일반화 제약 문구 확인
        self.assertIn("평가하지 않은 50개 업무에서 추천 과정 구성은 같고", metrics["generalization_constraint"])
        self.assertIn("7개 업무에서 순서가 다르며 그중 3개는 1위가 바뀐다", metrics["generalization_constraint"])
        self.assertIn("E4 규칙은 홀드아웃 1·2차 오답을 보고 만들었으므로", metrics["bias_note"])

    def test_06_preliminary_pipeline(self):
        """사전 집계 모드 검증: 새 판정 전에는 부트스트랩 미수행 및 판정 보류 처리"""
        metrics = analyze_candidate_diff(preliminary=True)
        self.assertIsNotNone(metrics)
        cmp = metrics["comparison"]
        self.assertEqual(cmp["decision"], "판정 보류 (새 판정 필요)")
        self.assertIsNone(cmp["ci95_diff_strict_bootstrap"])
        self.assertIn("새 판정 필요", cmp["decision_reason"])
        self.assertIn("7개 업무에서 순서가 다르며 그중 3개는 1위가 바뀐다", metrics["generalization_constraint"])


if __name__ == "__main__":
    unittest.main()
