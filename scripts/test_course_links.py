"""
GSEEK 상세 링크 보정(src/course_links.py) 회귀 테스트.

- GSEEK 과정 링크에만 s_sbjct_cycl_sn=1이 붙고, 다른 기관 링크·빈 값은 그대로인지
- 여러 번 적용해도 한 번만 붙는지, 원래 쿼리 값(s_sbjct_sn)이 그대로인지
- 고객 앱 카드, 최신 대시보드, 평가표의 GSEEK 링크가 모두 상세 링크인지
- 원본 강좌 데이터(parquet)의 URL은 바뀌지 않았는지
실행: python scripts/test_course_links.py   (모델·인터넷 필요 없음)
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT))

from src.course_links import detail_url  # noqa: E402

BASE = "https://www.gseek.kr/user/course/online/view?s_sbjct_sn=5040"
FIXED = BASE + "&s_sbjct_cycl_sn=1"

# 1) 함수 동작
assert detail_url(BASE) == FIXED, detail_url(BASE)
assert detail_url(FIXED) == FIXED, "이미 붙은 링크에 또 붙음"
assert detail_url(detail_url(BASE)) == FIXED, "두 번 적용하면 결과가 달라짐"
for other in ["https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=47021&cono=157542",
              "https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=A&tracseTme=2",
              "https://www.gseek.kr/user/course/online", "", "#", None]:
    assert detail_url(other) == other, f"바뀌면 안 되는 값이 바뀜: {other!r}"
print("[PASS] 함수: GSEEK 과정 링크에만 한 번 붙고, 다른 링크·빈 값은 그대로")

# 2) 원본 데이터는 그대로
src = pd.read_parquet(ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet",
                      columns=["course_uid", "url"])
g = src[src["url"].fillna("").str.contains("gseek.kr")]
assert len(g) > 0 and not g["url"].str.contains("s_sbjct_cycl_sn").any(), "원본 parquet의 GSEEK URL이 바뀌어 있음"
assert all(re.search(r"s_sbjct_sn=(\d+)", detail_url(u)).group(1) == re.search(r"s_sbjct_sn=(\d+)", u).group(1)
           for u in g["url"]), "과정 번호가 바뀜"
print(f"[PASS] 원본 데이터: GSEEK {len(g):,}개 URL 그대로, 보정 후에도 과정 번호 같음")

# 3) 고객 앱 카드
from src.customer import career_platform as cp  # noqa: E402

uid = "GSEEK_5040"
card = cp.make_card(cp._row(uid))
assert card["url"] == FIXED, card["url"]
kpc = src[src["course_uid"].str.startswith("KPC")].iloc[0]
assert cp.make_card(cp._row(kpc["course_uid"]))["url"] == kpc["url"], "다른 기관 카드 링크가 바뀜"
print(f"[PASS] 고객 카드: {uid} → 상세 링크, 다른 기관 링크는 그대로")

# 4) 최신 대시보드와 평가표
path = sorted(ROOT.glob("hr_career_platform_v2_*.html"))[-1]
text = path.read_text(encoding="utf-8")
data, _ = json.JSONDecoder().raw_decode(text[re.search(r"const DATA = ", text).end():])
gs = [c["url"] for c in data["courses"] if "gseek.kr" in str(c.get("url", ""))]
assert gs and all(u == detail_url(u) and "s_sbjct_cycl_sn=1" in u for u in gs), "대시보드에 보정 안 된 GSEEK 링크가 있음"
print(f"[PASS] 대시보드 {path.name}: GSEEK 링크 {len(gs):,}개 모두 상세 링크")
for name in ("precision_eval_round2_items.csv", "precision_eval_holdout_items.csv"):
    df = pd.read_csv(ROOT / "data" / "hr" / "output" / "recommendation" / name, dtype=str, keep_default_na=False)
    u = df.loc[df["url"].str.contains("gseek.kr"), "url"]
    assert len(u) and (u == u.map(detail_url)).all() and u.str.contains("s_sbjct_cycl_sn=1").all(), name
    print(f"[PASS] 평가표 {name}: GSEEK 링크 {len(u)}개 모두 상세 링크")
print("\n🎉 GSEEK 상세 링크 보정 검증 통과")
