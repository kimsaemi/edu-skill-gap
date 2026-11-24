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


def make_mock_read(tampered_data):
    orig_read_text = Path.read_text
    def _read_text(self, *args, **kwargs):
        if self == cpc.DATA_JSON_PATH or self.name == "data.json":
            return json.dumps(tampered_data, ensure_ascii=False)
        return orig_read_text(self, *args, **kwargs)
    return _read_text


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
        with patch.object(Path, "read_text", make_mock_read(tampered_data)):
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
        with patch.object(Path, "read_text", make_mock_read(tampered_data)):
            cpc.check_data_json_values(ref, issues)

        self.assertTrue(len(issues) > 0, "조작된 홀드아웃 지표가 통과되었습니다.")
        self.assertTrue(any(i["type"] == "DATA_JSON_VALUE_MISMATCH" for i in issues))

    def test_tampered_r1_strict_fails(self):
        """data.json 1차(human_eval) strict를 52.7 -> 99.9로 변경 시 불일치 감지 및 종료 코드 1 확인"""
        ref = cpc.load_references()
        original_text = cpc.DATA_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(original_text)

        tampered_data = copy.deepcopy(data)
        tampered_data["human_eval"]["precision_at_3"]["strict"] = 99.9

        issues = []
        with patch.object(Path, "read_text", make_mock_read(tampered_data)):
            cpc.check_data_json_values(ref, issues)

        self.assertTrue(len(issues) > 0, "1차 strict 조작이 감지되지 않았습니다.")
        self.assertTrue(any(i["type"] == "DATA_JSON_VALUE_MISMATCH" and "human_eval.precision_at_3.strict" in i["found"] for i in issues))

        # main() 실행 시 sys.exit(1) 호출 확인
        with patch.object(Path, "read_text", make_mock_read(tampered_data)), patch("sys.exit") as mock_exit:
            cpc.main()
            mock_exit.assert_called_with(1)

    def test_tampered_r2_strict_fails(self):
        """data.json 2차(human_eval_rounds.round2) strict 값 변경 시 불일치 감지 및 종료 코드 1 확인"""
        ref = cpc.load_references()
        original_text = cpc.DATA_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(original_text)

        tampered_data = copy.deepcopy(data)
        tampered_data["human_eval_rounds"]["round2"]["precision_at_3"]["strict"] = 12.3

        issues = []
        with patch.object(Path, "read_text", make_mock_read(tampered_data)):
            cpc.check_data_json_values(ref, issues)

        self.assertTrue(len(issues) > 0, "2차 strict 조작이 감지되지 않았습니다.")
        self.assertTrue(any(i["type"] == "DATA_JSON_VALUE_MISMATCH" and "round2.precision_at_3.strict" in i["found"] for i in issues))

        with patch.object(Path, "read_text", make_mock_read(tampered_data)), patch("sys.exit") as mock_exit:
            cpc.main()
            mock_exit.assert_called_with(1)

    def test_missing_data_json_item_fails(self):
        """data.json에서 필수 항목 삭제 시 DATA_JSON_KEY_MISSING 감지 및 종료 코드 1 확인"""
        ref = cpc.load_references()
        original_text = cpc.DATA_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(original_text)

        tampered_data = copy.deepcopy(data)
        # 2차 항목 삭제
        del tampered_data["human_eval_rounds"]["round2"]

        issues = []
        with patch.object(Path, "read_text", make_mock_read(tampered_data)):
            cpc.check_data_json_values(ref, issues)

        self.assertTrue(len(issues) > 0, "항목 삭제가 감지되지 않았습니다.")
        self.assertTrue(any(i["type"] == "DATA_JSON_KEY_MISSING" for i in issues))

        with patch.object(Path, "read_text", make_mock_read(tampered_data)), patch("sys.exit") as mock_exit:
            cpc.main()
            mock_exit.assert_called_with(1)

    def test_missing_ref_key_safety_check_fails(self):
        """load_references()에 추가된 키가 check_definitions에 누락되면 안전장치에 의해 실패 확인"""
        ref = cpc.load_references()
        fake_ref = copy.deepcopy(ref)
        fake_ref["unaccounted_new_metric"] = 99.9

        issues = []
        cpc.check_data_json_values(fake_ref, issues)
        self.assertTrue(any(i["type"] == "REF_KEYS_UNVERIFIED" for i in issues))


if __name__ == "__main__":
    unittest.main()
