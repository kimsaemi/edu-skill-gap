"""
고용24 Open API로 카탈로그의 고용24 과정(work24_course_details.csv) 일정을 지금 기준으로 다시 확인한다.
카탈로그·임베딩은 바꾸지 않는다(새 과정을 넣으려면 모델이 필요해 refresh_work24_courses_2026.py를 써야 함).

1. 국민내일배움카드(310L01)·사업주훈련(311L01) 목록 API에서 2026-01-01 ~ 2027-12-31 개강 회차를 수집
   (검색어는 refresh_work24_courses_2026.py의 KEYWORDS와 같음)
2. 카탈로그 과정(trprId)마다 다음 개강일·남은 회차 수를 찾아 저장된 운영 상태와 비교
   목록 검색에서 운영 중·개강 예정 회차가 안 보이는 과정은 과정별 일정 API(310L03·311D02)로 한 번 더 확인
3. 카탈로그에 없는 인사 범위(NCS 020202…) 새 과정 수를 센다
4. --apply: work24_course_details.csv의 running_status·checked_at을 지금 결과로 바꾸고 next_session_start를 채운다
   (고객 앱은 running_status가 '운영 중'·'개강 예정'일 때만 운영 표시를 붙인다)

필요: .env 또는 환경 변수 HRD_KMBC_API_KEY, HRD_EMPLOYER_TRAINING_API_KEY
출력
- data/hr/raw/work24_live/{kmbc,employer}_sessions_<날짜>.json.gz  (API 응답 원본 gzip, 인증키 없음)
- data/hr/reports/work24_live_check.csv                         (과정별 비교)
- data/hr/reports/work24_live_check.md                          (요약)
실행: python scripts/check_work24_live.py [--delay 0.2] [--from-raw] [--apply]  (--from-raw: 오늘 받은 목록 원본을 다시 씀)
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DETAILS = ROOT / "data" / "hr" / "processed" / "work24_course_details.csv"
RAW_DIR = ROOT / "data" / "hr" / "raw" / "work24_live"
OUT_CSV = ROOT / "data" / "hr" / "reports" / "work24_live_check.csv"
OUT_MD = ROOT / "data" / "hr" / "reports" / "work24_live_check.md"
BASE = "https://www.work24.go.kr/cm/openApi/call/hr/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TODAY = date.today().isoformat()
SINCE = "2026-01-01"  # 이미 시작해 운영 중인 회차도 잡으려고 올해 1월부터 검색
UNTIL = "2027-12-31"
HR_NCS = "020202"  # 총무·인사 > 인사·조직 (인사·노무관리)
SERVICES = {
    "국민내일배움카드": ("callOpenApiSvcInfo310L01.do", "HRD_KMBC_API_KEY", "kmbc"),
    "사업주훈련": ("callOpenApiSvcInfo311L01.do", "HRD_EMPLOYER_TRAINING_API_KEY", "employer"),
}


def keywords():
    spec = importlib.util.spec_from_file_location("refresh", ROOT / "scripts" / "refresh_work24_courses_2026.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.KEYWORDS


def get(url, params, tries=3):
    """오류 메시지에 인증키가 담긴 주소가 찍히지 않도록 예외 내용을 감춘다."""
    for attempt in range(tries):
        try:
            return requests.get(url, params=params, headers=HEADERS, timeout=25).text
        except requests.RequestException as e:
            print(f"    (연결 오류 {type(e).__name__}, {attempt + 1}/{tries}회)")
            time.sleep(2 * (attempt + 1))
    return ""


def collect(program, kws, delay):
    svc, key_name, _ = SERVICES[program]
    key = os.getenv(key_name)
    if not key:
        sys.exit(f"{key_name} 환경 변수가 없습니다.")
    rows = []
    for kw in kws:
        for page in range(1, 400):
            text = get(BASE + svc, {
                "authKey": key, "returnType": "XML", "outType": "1", "pageNum": str(page), "pageSize": "100",
                "srchTraStDt": SINCE.replace("-", ""), "srchTraEndDt": UNTIL.replace("-", ""), "srchTraProcessNm": kw,
            })
            if "<HRDNet" not in text[:300]:
                print(f"  - {program} [{kw}] {page}쪽: 응답 이상, 다음 검색어로")
                break
            root = ET.fromstring(text)
            items = root.findall(".//scn_list")
            rows += [{**{c.tag: c.text for c in it}, "_kw": kw} for it in items]
            if not items or page * 100 >= int(root.findtext("scn_cnt") or 0):
                break
            time.sleep(delay)
        print(f"  - {program} [{kw}] 누적 {len(rows)}행")
    df = pd.DataFrame(rows)
    if len(df):
        df = df.drop_duplicates(["trprId", "trprDegr"])
        df["program"] = program
    return df


SCHEDULE_API = {"ABA": ("callOpenApiSvcInfo311D02.do", "HRD_EMPLOYER_TRAINING_API_KEY"),
                "ACG": ("callOpenApiSvcInfo310L03.do", "HRD_KMBC_API_KEY"),
                "AIG": ("callOpenApiSvcInfo310L03.do", "HRD_KMBC_API_KEY")}


def schedule(tid):
    """과정 하나의 전체 회차 (개강일, 종료일)."""
    ep, key = SCHEDULE_API.get(tid[:3], SCHEDULE_API["AIG"])
    text = get(BASE + ep, {"authKey": os.getenv(key), "returnType": "XML", "outType": "1", "srchTrprId": tid})
    if "<HRDNet" not in text[:300]:
        return None
    try:
        items = ET.fromstring(text).findall(".//scn_list")
    except ET.ParseError:
        return None
    return [((it.findtext("trStaDt") or "")[:10], (it.findtext("trEndDt") or "")[:10]) for it in items
            if it.findtext("trStaDt")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--from-raw", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    kws = keywords()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for program, (_, _, slug) in SERVICES.items():
        raw = RAW_DIR / f"{slug}_sessions_{TODAY.replace('-', '')}.json.gz"
        if args.from_raw and raw.exists():
            frames.append(pd.read_json(raw, dtype=False))
            continue
        df = collect(program, kws, args.delay)
        df.drop(columns=[c for c in df.columns if c.lower().endswith("link")], errors="ignore") \
          .to_json(RAW_DIR / f"{slug}_sessions_{TODAY.replace('-', '')}.json.gz", orient="records", force_ascii=False)
        frames.append(df)
    live = pd.concat(frames, ignore_index=True)
    live["start"] = live["traStartDate"].str[:10]
    live["end"] = live["traEndDate"].str[:10]

    det = pd.read_csv(DETAILS, dtype=str)
    rows = []
    for r in det.itertuples():
        s = live[live["trprId"] == r.trprId]
        future = s[s["start"] >= TODAY]
        running = s[(s["start"] < TODAY) & (s["end"] >= TODAY)]
        source = "목록 API"
        if not len(future) and not len(running):  # 목록에서 남은 회차가 안 보이면 과정별 일정 API로 확인
            sess = schedule(r.trprId)
            time.sleep(args.delay)
            if sess:
                s = pd.DataFrame(sess, columns=["start", "end"])
                future = s[s["start"] >= TODAY]
                running = s[(s["start"] < TODAY) & (s["end"] >= TODAY)]
                source = "과정별 일정 API"
        if len(running):
            status = "운영 중"
        elif len(future):
            status = "개강 예정"
        elif len(s):
            status = "남은 회차 없음"
        else:
            status = "조회된 회차 없음"
        rows.append({
            "course_uid": r.course_uid, "trprId": r.trprId, "program": r.program, "title": r.title,
            "stored_status": r.running_status, "stored_rep_start": r.rep_session_start,
            "stored_rep_end": r.rep_session_end, "stored_upcoming": r.upcoming_sessions,
            "live_status": status, "live_source": source, "live_last_end": s["end"].max() if len(s) else "", "live_next_start": future["start"].min() if len(future) else "",
            "live_upcoming_sessions": len(future), "live_sessions_2027": int((future["start"] >= "2027-01-01").sum()),
            "stored_session_passed": (r.rep_session_end or "") < TODAY,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    in_cat = set(det["trprId"])
    hr_live = live[live["ncsCd"].fillna("").str.startswith(HR_NCS)]
    new_courses = hr_live[~hr_live["trprId"].isin(in_cat)].drop_duplicates("trprId")
    n = len(out)
    vc = out["live_status"].value_counts()
    lines = [
        f"# 고용24 일정 실시간 확인 ({TODAY})",
        "",
        f"고용24 Open API(310L01·311L01)로 {SINCE} ~ {UNTIL} 개강 회차를 검색어 {len(kws)}개로 다시 받아, "
        f"카탈로그의 고용24 과정 {n}개와 비교했다. 받은 회차는 국민내일배움카드 {len(frames[0]):,}건, 사업주훈련 {len(frames[1]):,}건이다.",
        "",
        "| 지금 상태 | 과정 수 | 비중 |",
        "| --- | ---: | ---: |",
    ] + [f"| {k} | {v} | {v / n * 100:.1f}% |" for k, v in vc.items()] + [
        "",
        f"- 저장된 대표 회차가 이미 끝난 과정: {int(out['stored_session_passed'].sum())}개. "
        f"그중 다음 회차가 조회된 과정 {int((out['stored_session_passed'] & out['live_upcoming_sessions'].gt(0)).sum())}개.",
        f"- 2027년 회차가 이미 열린 과정: {int(out['live_sessions_2027'].gt(0).sum())}개.",
        f"- 목록 검색으로 남은 회차가 안 보여 과정별 일정 API로 다시 확인한 과정: {int(out['live_source'].eq('과정별 일정 API').sum())}개.",
        "- '남은 회차 없음'은 올해 회차가 모두 끝나 운영 종료로 볼 수 있는 과정이다. 고객 화면에서 '운영 종료'로 표시하는 것이 맞다.",
        f"- 카탈로그에 없는 인사 범위(NCS {HR_NCS}…) 새 과정: {len(new_courses)}개 "
        f"(국민내일배움카드 {int(new_courses['program'].eq('국민내일배움카드').sum())}, 사업주훈련 {int(new_courses['program'].eq('사업주훈련').sum())}). "
        "카탈로그에 넣으려면 모델이 있는 PC에서 refresh_work24_courses_2026.py를 실행해야 한다.",
        "",
    ]
    if args.apply:
        status_map = {"운영 중": "운영 중", "개강 예정": "개강 예정", "남은 회차 없음": "운영 종료", "조회된 회차 없음": "확인 필요"}
        live_by = out.set_index("course_uid")
        det["running_status"] = det["course_uid"].map(live_by["live_status"].map(status_map)).fillna(det["running_status"])
        det["next_session_start"] = det["course_uid"].map(live_by["live_next_start"]).fillna("")
        det["upcoming_sessions"] = det["course_uid"].map(live_by["live_upcoming_sessions"]).fillna(det["upcoming_sessions"])
        det["checked_at"] = TODAY
        det.to_csv(DETAILS, index=False, encoding="utf-8-sig")
        lines.append(f"`--apply`로 {DETAILS.relative_to(ROOT)}의 운영 상태를 바꿨다: " +
                     ", ".join(f"{k} {v}" for k, v in det["running_status"].value_counts().items()) + ".")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
