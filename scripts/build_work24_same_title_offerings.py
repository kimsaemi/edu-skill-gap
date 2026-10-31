"""
같은 제목의 고용24 과정을 다른 훈련기관도 운영하는 경우, 그 기관 목록을 만든다.

카탈로그에는 제목마다 대표 회차 하나만 넣는다(refresh_work24_courses_2026.py). 추천 카드는 그대로 하나로 보여 주고,
카드 안에 '다른 기관 N곳에서도 운영'과 기관별 훈련비·지역·다음 개강일을 붙이기 위한 데이터다. (2026-10-31 팀 결정)

입력
- data/hr/raw/work24_live/{kmbc,employer}_sessions_<날짜>.json.gz : check_work24_live.py가 저장한 고용24 목록 API 응답 (가장 최근 날짜)
- data/hr/processed/work24_course_details.csv                     : 카탈로그에 넣은 대표 과정
출력
- data/hr/processed/work24_same_title_offerings.csv
  (course_uid = 카탈로그 대표 과정, 그 과정과 제목이 같은 다른 기관의 운영 중·개강 예정 과정 한 줄씩)
실행: python scripts/build_work24_same_title_offerings.py   (API 호출 없음)
"""
import glob
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "hr" / "raw" / "work24_live"
DETAILS = ROOT / "data" / "hr" / "processed" / "work24_course_details.csv"
OUT = ROOT / "data" / "hr" / "processed" / "work24_same_title_offerings.csv"
TODAY = date.today().isoformat()
PROGRAM = {"kmbc": "국민내일배움카드", "employer": "사업주훈련"}


def norm_title(s):
    """refresh_work24_courses_2026.py와 같은 제목 정규화."""
    return re.sub(r"[\s\[\]\(\)【】<>·,.!?:~\-_\"']", "", str(s)).lower()


def course_url(r):
    """고용24 과정 상세 주소. 사업주훈련은 selectTracseDetl2.do, 그 밖은 selectTracseDetl.do."""
    page = "selectTracseDetl2.do" if str(r.trprId).startswith("ABA") else "selectTracseDetl.do"
    return (f"https://www.work24.go.kr/hr/a/a/3100/{page}?tracseId={r.trprId}&tracseTme={r.trprDegr}"
            f"&crseTracseSe={str(r.trainTargetCd)[:5]}&trainstCstmrId={r.trainstCstId}")


def latest_raw():
    frames = []
    for slug, name in PROGRAM.items():
        files = sorted(glob.glob(str(RAW_DIR / f"{slug}_sessions_*.json.gz")))
        if not files:
            raise SystemExit(f"{RAW_DIR}에 {slug} 원본이 없습니다. 먼저 python scripts/check_work24_live.py 를 실행하세요.")
        df = pd.read_json(files[-1], dtype=False)
        df["program"] = name
        frames.append(df)
        print(f"  {Path(files[-1]).name}: {len(df):,}회차")
    return pd.concat(frames, ignore_index=True)


def main():
    s = latest_raw()
    s = s[s["ncsCd"].fillna("").str.startswith("0202")].copy()  # 총무·인사
    s["start"] = s["traStartDate"].str[:10]
    s["end"] = s["traEndDate"].str[:10]
    s = s[s["end"] >= TODAY]  # 운영 중이거나 개강 예정인 회차만
    s["norm"] = s["title"].map(norm_title)
    s["fee"] = pd.to_numeric(s["realMan"], errors="coerce")

    det = pd.read_csv(DETAILS, dtype=str)
    det["norm"] = det["title"].map(norm_title)
    rep_inst = dict(zip(det["norm"], det["trainstCstId"]))
    rep_uid = dict(zip(det["norm"], det["course_uid"]))

    s = s[s["norm"].isin(rep_uid)]
    s = s[s["trainstCstId"] != s["norm"].map(rep_inst)]  # 대표 과정을 운영하는 기관은 빼고
    # 기관마다 회차 하나: 수강 신청할 수 있는 가장 빠른 개강 회차, 없으면 지금 운영 중인 회차
    s["running"] = s["start"] < TODAY
    s = s.sort_values(["norm", "trainstCstId", "running", "start"], ascending=[True, True, True, True])
    s = s.drop_duplicates(["norm", "trainstCstId"])

    out = pd.DataFrame({
        "course_uid": s["norm"].map(rep_uid),
        "institution": s["subTitle"].fillna("").str.strip(),
        "program": s["program"],
        "trprId": s["trprId"], "trprDegr": s["trprDegr"],
        "status": s["running"].map({True: "운영 중", False: "개강 예정"}),
        "start": s["start"], "end": s["end"],
        "fee": s["fee"].astype("Int64"),
        "region": s["address"].fillna("").str.split().str[:2].str.join(" "),
        "url": [course_url(r) for r in s.itertuples()],
        "checked": TODAY,
    }).sort_values(["course_uid", "start"])
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    g = out.groupby("course_uid")
    print(f"저장: {OUT.relative_to(ROOT)}  ({len(out)}줄)")
    print(f"  다른 기관도 운영하는 대표 과정 {g.ngroups}개, 기관 수 중앙값 {g.size().median():.0f}, 최대 {g.size().max()}")


if __name__ == "__main__":
    main()
