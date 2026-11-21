"""
tests/test_presentation_consistency.py
발표 자료 일관성 및 지표 정직성 검사 단위 테스트
- 기본 상태에서 점검 통과(issues == 0) 확인
- data.json 숫자가 위변조되거나 어긋났을 때 점검 실패 감지 확인
"""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_presentation_consistency as cpc


class TestPresentationConsistency(unittest.TestCase):
    def test_clean_presentation_consistency(self):
        """정상 상태의 발표 자료에서 어긋난 지표나 금지 표현이 0건이어야 함"""
        ref, issues = cpc.run_checks()
        self.assertEqual(len(issues), 0, f"정상 상태에서 점검 이슈가 발생했습니다: {issues}")
        self.assertEqual(ref.get("kpc_hr_domain_share"), 17.3)
        self.assertEqual(ref.get("kpc_ci95"), [-1.1, 30.7])

    def test_tampered_data_json_fails(self):
        """data.json 내의 지표를 일부러 틀었을 때 점검 실패가 발생하는지 확인"""
        ref = cpc.load_references()
        original_text = cpc.DATA_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(original_text)

        # KPC 비중을 일부러 조작
        tampered_data = copy.deepcopy(data)
        tampered_data["kpc_bias"]["kpc_hr_pct"] = 99.9

        issues = []
        with patch.object(Path, "read_text", return_value=json.dumps(tampered_data)):
            cpc.check_data_json_values(ref, issues)

        self.assertTrue(len(issues) > 0, "조작된 data.json이 통과되었습니다.")
        self.assertTrue(any(i["type"] == "DATA_JSON_VALUE_MISMATCH" for i in issues))
        mismatch = next(i for i in issues if i["type"] == "DATA_JSON_VALUE_MISMATCH")
        self.assertIn("kpc_bias.kpc_hr_pct", mismatch["found"])

    def test_tampered_holdout_strict_fails(self):
        """data.json 내의 홀드아웃 지표를 조작했을 때 감지하는지 확인"""
        ref = cpc.load_references()
        original_text = cpc.DATA_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(original_text)

        tampered_data = copy.deepcopy(data)
        tampered_data["human_eval_rounds"]["holdout_all"]["precision_at_3"]["strict"] = 10.0

        issues = []
        with patch.object(Path, "read_text", return_value=json.dumps(tampered_data)):
            cpc.check_data_json_values(ref, issues)

        self.assertTrue(len(issues) > 0, "조작된 홀드아웃 지표가 통과되었습니다.")
        self.assertTrue(any(i["type"] == "DATA_JSON_VALUE_MISMATCH" for i in issues))


if __name__ == "__main__":
    unittest.main()
