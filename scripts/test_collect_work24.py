"""
collect_hr_courses.py의 고용24 수집 로직을 네트워크 없이 시험한다.
가짜 API 응답을 쓰며, 결과 파일은 임시 폴더에만 만들고 data/에는 아무것도 쓰지 않는다.

실행: python scripts/test_collect_work24.py
"""
import sys, os, tempfile, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_hr_courses as c

def page_xml(total, ids):
    rows = "".join(f"<scn_list><trprId>T{i}</trprId><trprDegr>1</trprDegr><title>과정{i}</title>"
                   f"<stdgScor>{'85.7' if i % 2 else '0'}</stdgScor><traStartDate>2026-11-01</traStartDate>"
                   f"<traEndDate>2026-12-01</traEndDate></scn_list>" for i in ids)
    return f"<HRDNet><scn_cnt>{total}</scn_cnt><srchList>{rows}</srchList></HRDNet>"

class Resp:
    def __init__(self, text, code=200): self.text, self.status_code = text, code

calls = []
def fake_get(url, params, **kw):
    calls.append((params["srchTraProcessNm"], params["pageNum"], params["srchTraStDt"], params["srchTraEndDt"]))
    kwd, page = params["srchTraProcessNm"], int(params["pageNum"])
    if kwd == "오류":
        return Resp("<!DOCTYPE html><html></html>")          # HTML 리다이렉트 같은 비정상 응답
    if kwd == "A":                                           # 250건 -> 3페이지
        ids = range((page - 1) * 100, min(page * 100, 250))
        return Resp(page_xml(250, ids))
    return Resp(page_xml(2, [0, 1]))                          # B: A와 겹치는 T0, T1 (중복 제거 확인)

c.requests.get = fake_get
c.time.sleep = lambda s: None
os.environ["HRD_KMBC_API_KEY"] = "test-key-not-real"
tmp = Path(tempfile.mkdtemp())
c.WORK24_RAW_DIR = tmp
c.BASE_DIR = tmp.parent

r = c.collect_work24_courses("kmbc", keywords=["A", "B", "오류"], months_ahead=6,
                             today=dt.date(2026, 10, 25))
pages_A = [p for k, p, *_ in calls if k == "A"]
assert pages_A == ["1", "2", "3"], pages_A
assert calls[0][2:] == ("20261025", "20270425"), calls[0]
assert len(r["items"]) == 250, len(r["items"])              # B의 2건은 A와 중복
assert sum(1 for k, *_ in calls if k == "오류") == 3          # 재시도 3회
assert any(l["error"] for l in r["logs"] if l["keyword"] == "오류")
assert len(list((tmp / "20261025").glob("kmbc_A_p*.xml"))) == 3

t = c.build_satisfaction_table(r["items"])
assert len(t) == 250
assert (t.satisfaction_status == "점수 있음").sum() == 125
assert t.loc[t.satisfaction_status == "설문 없음(0)", "satisfaction_official"].isna().all()

os.environ.pop("HRD_EMPLOYER_TRAINING_API_KEY", None)
assert c.collect_work24_courses("employer")["error"] == "인증키 없음"
print("ALL TESTS PASSED", calls[:2])
