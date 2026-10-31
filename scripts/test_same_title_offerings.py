"""
같은 제목 과정의 '다른 운영 기관' 표시 검증.

- work24_same_title_offerings.csv의 대표 과정이 모두 카탈로그에 있는지
- 대표 과정을 운영하는 기관이 '다른 기관' 목록에 다시 나오지 않는지
- 운영 중·개강 예정 회차만 있는지, 고용24 링크가 맞는 형식인지
- 고객 앱 카드에 요약 문구와 기관 목록이 붙는지
실행: python scripts/test_same_title_offerings.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.customer import career_platform as cp  # noqa: E402

off = pd.read_csv(cp.OFFERINGS_PATH, dtype=str)
det = pd.read_csv(cp.WORK24_DETAIL_PATH, dtype=str)
assert len(off) > 0, "다른 운영 기관 데이터가 비어 있음"
assert off["course_uid"].isin(det["course_uid"]).all(), "카탈로그에 없는 대표 과정이 있음"
assert not off.duplicated(["course_uid", "institution", "trprId"]).any(), "같은 기관 회차가 중복됨"
assert off["status"].isin(["운영 중", "개강 예정"]).all(), "끝난 회차가 섞임"
assert (off["end"] >= off["checked"]).all(), "확인일 기준으로 이미 끝난 회차가 있음"
assert off["url"].str.startswith("https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl").all(), "고용24 링크 형식 오류"
same = off.merge(det[["course_uid", "institution"]].rename(columns={"institution": "rep"}), on="course_uid")
assert not (same["institution"].str.strip() == same["rep"].str.strip()).any(), "대표 과정 기관이 다른 기관 목록에 섞임"
print(f"[PASS] 데이터: 대표 과정 {off['course_uid'].nunique()}개 · 다른 기관 {len(off)}줄 (확인일 {off['checked'].iloc[0]})")

uid = off["course_uid"].value_counts().index[0]
row = cp._row(uid)
assert row is not None, "카탈로그에서 대표 과정을 못 찾음"
card = cp.make_card(row)
n = int((off["course_uid"] == uid).sum())
assert len(card["other_offerings"]) == n, "카드의 기관 수가 데이터와 다름"
assert card["other_offerings_summary"].startswith(f"다른 기관 {n}곳에서도 운영"), card["other_offerings_summary"]
print(f"[PASS] 카드: {card['title'][:30]} → {card['other_offerings_summary']}")

plain = cp.make_card(cp._row(det.loc[~det["course_uid"].isin(off["course_uid"]), "course_uid"].iloc[0]))
assert plain["other_offerings"] == [] and plain["other_offerings_summary"] is None, "다른 기관이 없는 과정에 요약이 붙음"
print("[PASS] 다른 기관이 없는 과정은 표시 없음")
print("\n🎉 같은 제목 과정 '다른 운영 기관' 검증 통과")
