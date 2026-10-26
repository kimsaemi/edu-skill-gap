"""
고용24 과정의 카탈로그 오류 수정 + 회차 이력·공식 링크 보강
파일명: scripts/fix_work24_catalog_fields.py
(먼저 scripts/enrich_work24_course_details.py 로 상세정보를 받아 둔 뒤 실행)

카탈로그(education_courses_search_cleaned.parquet) 수정
  1. NCS 코드 복원: 숫자로 저장되며 앞자리 0이 빠진 공식 코드("2020201.0")를 8자리("02020201")로
  2. 교육 형태: 고용24 과정이 모두 '집합/원격 혼합'으로 들어가 온라인·오프라인 필터에 둘 다 걸리던 문제
     → 상세 API의 총 훈련일수가 0/빈 값이면 '원격(온라인)', 1일 이상이면 '집합'
  3. duration_days: 모집 기간(약 30일)이 들어가 있던 값 → 공식 훈련일수 (원격은 빈 값)
  4. url: 고용24 메인 주소 → 목록 API가 준 과정별 공식 링크(titleLink)

work24_course_details.csv 에 추가 (카탈로그 날짜 칸은 바꾸지 않음)
  - 훈련일정 API(310L03 / 311D02)의 전체 회차 수, 마지막 회차 개강·종료일, 오늘 이후 개강 회차 수, 운영 상태
  - 이미 끝난 회차 날짜를 카탈로그에 넣으면 고객 화면에 곧 열리는 일정처럼 보이므로 따로 둠

사용법:
  python scripts/fix_work24_catalog_fields.py
  python scripts/fix_work24_catalog_fields.py --dry-run
"""

import argparse
import glob
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PROCESSED = ROOT / "data" / "hr" / "processed"
CATALOG = PROCESSED / "education_courses_search_cleaned.parquet"
DETAIL_CSV = PROCESSED / "work24_course_details.csv"
DETAIL_RAW = ROOT / "data" / "hr" / "raw" / "work24_details" / "work24_course_details_raw.json"
SCHEDULE_RAW = ROOT / "data" / "hr" / "raw" / "work24_details" / "work24_schedules_raw.json"
BACKUP_DIR = PROCESSED / "backup"

BASE = "https://www.work24.go.kr/cm/openApi/call/hr/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
SCHEDULE_API = {
    "ABA": ("callOpenApiSvcInfo311D02.do", "HRD_EMPLOYER_TRAINING_API_KEY"),
    "ACG": ("callOpenApiSvcInfo310L03.do", "HRD_KMBC_API_KEY"),
    "AIG": ("callOpenApiSvcInfo310L03.do", "HRD_KMBC_API_KEY"),
}
TODAY = date.today().isoformat()


def get_text(url, params, tries=3):
    """연결 오류는 다시 시도. 오류 메시지에 인증키가 담긴 주소가 찍히지 않도록 예외를 감춤."""
    for attempt in range(tries):
        try:
            return requests.get(url, params=params, headers=HEADERS, timeout=20).text
        except requests.RequestException as e:
            print(f"    (연결 오류 {type(e).__name__}, {attempt + 1}/{tries}회)")
            time.sleep(2 * (attempt + 1))
    return ""


def fix_ncs_code(code):
    s = str(code).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(8) if s.isdigit() and len(s) <= 8 else s


def fetch_schedules(trpr_ids, delay):
    out = {}
    for tid in trpr_ids:
        ep, key = SCHEDULE_API[tid[:3]]
        text = get_text(BASE + ep, {"authKey": os.getenv(key), "returnType": "XML", "outType": "1", "srchTrprId": tid})
        sessions = []
        if "<HRDNet" in text[:300]:
            try:
                sessions = [{c.tag: c.text for c in it} for it in ET.fromstring(text).findall(".//scn_list")]
            except ET.ParseError:
                pass
        out[tid] = sessions
        time.sleep(delay)
    return out


def official_links():
    """이미 수집한 목록 API 원본에서 (trprId, 회차) → titleLink."""
    links = {}
    for f in glob.glob(str(ROOT / "data" / "hr" / "raw" / "**" / "*.json"), recursive=True):
        try:
            data = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [])
        if not isinstance(data, list):
            continue
        for x in data:
            if isinstance(x, dict) and x.get("trprId") and x.get("titleLink", "").startswith("https://www.work24.go.kr/"):
                links.setdefault(x["trprId"], {})[str(x.get("trprDegr"))] = x["titleLink"]
    return links


def check_link(url, title):
    text = get_text(url, {}, tries=2)
    key = title[:8]
    return bool(text) and key in text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    df = pd.read_parquet(CATALOG)
    det = pd.read_csv(DETAIL_CSV, dtype={"trprId": str, "trprDegr": str, "trainstCstId": str})
    raw = {r["course_uid"]: (r["detail"] or {}) for r in json.load(open(DETAIL_RAW, encoding="utf-8"))}

    # 1) NCS 코드 복원
    off = df["ncs_code_type"] == "OFFICIAL_NCS_CODE"
    fixed_ncs = df.loc[off, "ncs_code"].map(fix_ncs_code)
    changed_ncs = int((fixed_ncs != df.loc[off, "ncs_code"]).sum())
    official = df.loc[off, "course_uid"].map(lambda u: (raw.get(u) or {}).get("ncsCd"))
    compared = official.notna()
    agree = int((fixed_ncs[compared] == official[compared]).sum())
    print(f"[1] NCS 코드 복원 {changed_ncs}/{int(off.sum())}행 | 고용24 상세 API 공식 코드와 일치 {agree}/{int(compared.sum())}")

    # 2·3) 교육 형태와 훈련일수
    days = df["course_uid"].map(lambda u: (raw.get(u) or {}).get("totTraingDyct") or (raw.get(u) or {}).get("trDcnt"))
    has_detail = df["course_uid"].isin(raw.keys())
    days_num = pd.to_numeric(days, errors="coerce")
    new_type = pd.Series(pd.NA, index=df.index, dtype="object")
    new_type[has_detail & (days_num.fillna(0) <= 0)] = "원격(온라인)"
    new_type[has_detail & (days_num > 0)] = "집합"
    print(f"[2] 교육 형태 수정 {int(has_detail.sum())}행: {new_type.value_counts().to_dict()}")

    # 4) 공식 링크
    links = official_links()

    def pick_link(row):
        by_degr = links.get(row["source_course_id"], {})
        degr = str(row["course_uid"]).rsplit("_", 1)[-1]
        if degr in by_degr:
            return by_degr[degr]
        if by_degr:
            return by_degr[max(by_degr, key=lambda d: int(d) if d.isdigit() else -1)]
        return None

    new_url = df[has_detail].apply(pick_link, axis=1)
    print(f"[4] 공식 링크 확보 {int(new_url.notna().sum())}/{int(has_detail.sum())}행")

    # 원본에 링크가 없는 과정은 API가 준 링크와 같은 형식으로 만들고, 실제로 열어 제목이 보일 때만 사용
    torg = det.set_index("course_uid")["trainstCstId"]
    built_ok = 0
    for idx in new_url[new_url.isna()].index:
        row = df.loc[idx]
        tid, degr = row["source_course_id"], str(row["course_uid"]).rsplit("_", 1)[-1]
        page, kind = ("selectTracseDetl2.do", "C0041") if tid.startswith("ABA") else ("selectTracseDetl.do", "C0031")
        url = (f"https://www.work24.go.kr/hr/a/a/3100/{page}?tracseId={tid}&tracseTme={degr}"
               f"&crseTracseSe={kind}&trainstCstmrId={torg.get(row['course_uid'])}")
        if check_link(url, row["title"]):
            new_url[idx] = url
            built_ok += 1
        time.sleep(args.delay)
    print(f"    같은 형식으로 만든 링크 중 열림 확인 {built_ok}개 → 최종 {int(new_url.notna().sum())}/{int(has_detail.sum())}행")
    sample = df.loc[new_url.dropna().index[:5], ["title"]].assign(url=new_url.dropna().iloc[:5])
    link_ok = [check_link(r.url, r.title) for r in sample.itertuples()]
    print(f"    링크 표본 {len(link_ok)}개 중 과정 페이지가 제목과 함께 열린 것 {sum(link_ok)}개")

    # 회차 이력
    print("[+] 훈련일정 API로 회차 이력 조회")
    sched = fetch_schedules(sorted(det["trprId"].unique()), args.delay)
    SCHEDULE_RAW.write_text(json.dumps(sched, ensure_ascii=False, indent=1), encoding="utf-8")

    def summarize(tid):
        ses = sched.get(tid, [])
        starts = [s["trStaDt"] for s in ses if s.get("trStaDt")]
        ends = [s["trEndDt"] for s in ses if s.get("trEndDt")]
        upcoming = sum(s >= TODAY for s in starts)
        running = sum(st <= TODAY <= en for st, en in zip(starts, ends))
        status = "모집·운영 중" if (upcoming or running) else ("운영 종료" if starts else "일정 정보 없음")
        return pd.Series({
            "n_sessions": len(ses), "last_session_start": max(starts) if starts else None,
            "last_session_end": max(ends) if ends else None, "upcoming_sessions": upcoming, "running_status": status,
        })

    det = det.drop(columns=[c for c in ["n_sessions", "last_session_start", "last_session_end", "upcoming_sessions",
                                         "running_status", "course_url", "schedule_checked_at"] if c in det.columns])
    det = det.join(det["trprId"].apply(summarize))
    det["course_url"] = det["course_uid"].map(new_url.set_axis(df.loc[new_url.index, "course_uid"]))
    det["schedule_checked_at"] = datetime.now(timezone.utc).isoformat()
    print(det.drop_duplicates("trprId")["running_status"].value_counts().to_string())
    print(f"    마지막 회차 개강일 범위: {det['last_session_start'].min()} ~ {det['last_session_start'].max()} (오늘 {TODAY})")

    if args.dry_run:
        print("--dry-run: 파일을 바꾸지 않았습니다.")
        return

    det.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"education_courses_search_cleaned.before_work24_fix_{datetime.now():%Y%m%d_%H%M%S}.parquet"
    shutil.copy2(CATALOG, backup)

    df.loc[off, "ncs_code"] = fixed_ncs
    df.loc[new_type.dropna().index, "education_type"] = new_type.dropna()
    days_fill = days_num.where(days_num > 0)
    df.loc[has_detail, "duration_days"] = days_fill[has_detail].astype("Int64")
    df.loc[new_url.dropna().index, "url"] = new_url.dropna()
    touched = df.index[off | has_detail]
    note = "work24_fields_fixed"
    df.loc[touched, "cleaning_actions"] = df.loc[touched, "cleaning_actions"].fillna("").map(
        lambda s: s if note in s else (f"{s}, {note}" if s else note)
    )
    df.to_parquet(CATALOG, index=False, compression="zstd", compression_level=9)
    print(f"카탈로그 저장 완료 (백업: {backup.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
