"""
고용24 과정 상세정보로 카탈로그의 훈련시간·훈련비 보강
파일명: scripts/enrich_work24_course_details.py

대상: 카탈로그(education_courses_search_cleaned.parquet)의 고용24 과정
  - 사업주훈련(ABA…)          → 상세 API 311D01
  - 국민내일배움카드(ACG/AIG…) → 상세 API 310L02

상세 API 항목 (목록 API 값과 대조해 확인한 뜻)
  - totTraingTime        : 총 훈련시간
  - totTraingDyct        : 총 훈련일수 (원격과정은 0 또는 빈 값)
  - perTrco              : 1인당 실제 훈련비 (목록 API realMan과 일치)
  - tgcrGnrlTrneOwepAllt : 수강생 자기부담금 (내일배움카드 약 25%, 사업주훈련은 전액 회사 부담 후 환급)

카탈로그 반영 규칙
  - duration_hours 가 비어 있으면 총 훈련시간으로 채움
  - 사업주훈련의 price 가 0 이면 실제 훈련비로 바꿈
    (처음 수집 때 수강비 항목을 써서 0이 들어갔고, 추천 화면에서 '무료'로 잘못 보이던 문제)
  - 그 밖의 값은 덮어쓰지 않음. 상세 값 전체는 work24_course_details.csv 에 따로 저장

사용법:
  python scripts/enrich_work24_course_details.py            # 조회 + 카탈로그 반영
  python scripts/enrich_work24_course_details.py --dry-run  # 조회만 하고 카탈로그는 그대로
"""

import argparse
import glob
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PROCESSED = ROOT / "data" / "hr" / "processed"
CATALOG = PROCESSED / "education_courses_search_cleaned.parquet"
BACKUP_DIR = PROCESSED / "backup"
RAW_OUT = ROOT / "data" / "hr" / "raw" / "work24_details" / "work24_course_details_raw.json"
OUT_CSV = PROCESSED / "work24_course_details.csv"

BASE = "https://www.work24.go.kr/cm/openApi/call/hr/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
API = {
    "ABA": {"detail": "callOpenApiSvcInfo311D01.do", "list": "callOpenApiSvcInfo311L01.do", "key": "HRD_EMPLOYER_TRAINING_API_KEY", "name": "사업주훈련"},
    "ACG": {"detail": "callOpenApiSvcInfo310L02.do", "list": "callOpenApiSvcInfo310L01.do", "key": "HRD_KMBC_API_KEY", "name": "국민내일배움카드"},
    "AIG": {"detail": "callOpenApiSvcInfo310L02.do", "list": "callOpenApiSvcInfo310L01.do", "key": "HRD_KMBC_API_KEY", "name": "국민내일배움카드"},
}
TRPR_RE = r"A[A-Z]{2}\d{14}"


def to_int(v):
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def known_institution_ids():
    """이미 수집한 원본 JSON과 공식 만족도 표에서 (trprId → 훈련기관 ID, 회차 목록)을 모음."""
    torg, degrees = {}, {}
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
            if isinstance(x, dict) and x.get("trprId") and x.get("trainstCstId"):
                torg.setdefault(x["trprId"], x["trainstCstId"])
                if x.get("trprDegr"):
                    degrees.setdefault(x["trprId"], set()).add(str(x["trprDegr"]))
    sat = PROCESSED / "official_satisfaction.csv"
    if sat.exists():
        for r in pd.read_csv(sat, dtype=str).itertuples():
            if isinstance(r.trainstCstId, str):
                torg.setdefault(r.trprId, r.trainstCstId)
    return torg, degrees


def find_by_title(prefix, trpr_id, title, delay, max_pages=40):
    """목록 API를 제목으로 검색해 해당 trprId의 훈련기관 ID와 회차들을 찾음."""
    api = API[prefix]
    key = os.getenv(api["key"])
    found_torg, found_degr = None, set()
    for page in range(1, max_pages + 1):
        params = {
            "authKey": key, "returnType": "XML", "outType": "1", "pageNum": str(page), "pageSize": "100",
            "srchTraStDt": "20240101", "srchTraEndDt": "20261231", "srchTraProcessNm": title,
        }
        text = get_text(BASE + api["list"], params)
        if "<HRDNet" not in text[:300]:
            break
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            break
        items = root.findall(".//scn_list")
        for it in items:
            if it.findtext("trprId") == trpr_id:
                found_torg = found_torg or it.findtext("trainstCstId")
                found_degr.add(it.findtext("trprDegr"))
        total = int(root.findtext("scn_cnt") or 0)
        if found_torg or not items or page * 100 >= total:
            break
        time.sleep(delay)
    return found_torg, found_degr


def get_text(url, params, tries=3):
    """연결 오류는 몇 번 다시 시도. 오류 메시지에 인증키가 담긴 주소가 찍히지 않도록 예외를 감춤."""
    for attempt in range(tries):
        try:
            return requests.get(url, params=params, headers=HEADERS, timeout=20).text
        except requests.RequestException as e:
            print(f"    (연결 오류 {type(e).__name__}, {attempt + 1}/{tries}회)")
            time.sleep(2 * (attempt + 1))
    return ""


def fetch_detail(prefix, trpr_id, degr, torg):
    api = API[prefix]
    params = {
        "authKey": os.getenv(api["key"]), "returnType": "XML", "outType": "2",
        "srchTrprId": trpr_id, "srchTrprDegr": degr, "srchTorgId": torg,
    }
    text = get_text(BASE + api["detail"], params)
    if "<HRDNet" not in text[:300]:
        return None
    root = ET.fromstring(text)
    out = {}
    for sec in ("inst_base_info", "inst_detail_info"):
        node = root.find(sec)
        if node is not None:
            out.update({c.tag: c.text for c in node})
    return out or None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="카탈로그를 바꾸지 않음")
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    df = pd.read_parquet(CATALOG)
    sid = df["source_course_id"].astype(str)
    pub = df[sid.str.fullmatch(TRPR_RE)].copy()
    pub["prefix"] = pub["source_course_id"].str[:3]
    pub["degr"] = pub["course_uid"].str.extract(r"_(\d+)$")[0]
    print(f"카탈로그 고용24 과정: {len(pub)}행 (고유 과정 {pub['source_course_id'].nunique()}개)")
    print(pub["prefix"].map(lambda p: API[p]["name"]).value_counts().to_string())

    torg_map, degr_map = known_institution_ids()
    missing = pub.loc[~pub["source_course_id"].isin(torg_map)].drop_duplicates("source_course_id")
    print(f"\n훈련기관 ID 없는 과정 {len(missing)}개 → 목록 API에서 제목으로 찾기")
    for r in missing.itertuples():
        t, degs = find_by_title(r.prefix, r.source_course_id, r.title, args.delay)
        if t:
            torg_map[r.source_course_id] = t
            degr_map.setdefault(r.source_course_id, set()).update(d for d in degs if d)
        print(f"  - {r.source_course_id} {r.title[:28]}: {'찾음' if t else '못 찾음'}")

    raw, rows = [], []
    print("\n상세정보 조회")
    for r in pub.itertuples():
        torg = torg_map.get(r.source_course_id)
        detail, used_degr = None, None
        if torg:
            # 카탈로그 회차 먼저, 안 되면 원본에서 본 다른 회차로
            for degr in [r.degr] + sorted(degr_map.get(r.source_course_id, set()) - {r.degr}):
                if not degr:
                    continue
                detail = fetch_detail(r.prefix, r.source_course_id, degr, torg)
                time.sleep(args.delay)
                if detail:
                    used_degr = degr
                    break
        raw.append({"course_uid": r.course_uid, "trprId": r.source_course_id, "degr": used_degr, "torg": torg, "detail": detail})
        d = detail or {}
        rows.append({
            "course_uid": r.course_uid,
            "trprId": r.source_course_id,
            "program": API[r.prefix]["name"],
            "trprDegr": used_degr,
            "trainstCstId": torg,
            "title": r.title,
            "training_hours": to_int(d.get("totTraingTime") or d.get("trtm")),
            "training_days": to_int(d.get("totTraingDyct") or d.get("trDcnt")),
            "fee_per_person": to_int(d.get("perTrco")),
            "self_pay": to_int(d.get("tgcrGnrlTrneOwepAllt")),
            "gov_program": d.get("govBusiNm"),
            "method_code": d.get("traingMthCd"),
            "status": "OK" if detail else ("NO_INSTITUTION_ID" if not torg else "DETAIL_NOT_FOUND"),
            "catalog_hours_before": r.duration_hours,
            "catalog_price_before": r.price,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    out = pd.DataFrame(rows)
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUT.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(out.groupby(["program", "status"]).size().to_string())

    ok = out[out["status"] == "OK"].set_index("course_uid")
    hours_fill = df["course_uid"].isin(ok.index) & df["duration_hours"].isna()
    new_hours = df.loc[hours_fill, "course_uid"].map(ok["training_hours"])
    price_fix = (
        df["course_uid"].isin(ok[ok["program"] == "사업주훈련"].index)
        & (df["price"].fillna(-1) == 0)
    )
    new_price = df.loc[price_fix, "course_uid"].map(ok["fee_per_person"])
    print(f"\n카탈로그 반영 예정: 훈련시간 {int(new_hours.notna().sum())}행, 사업주훈련 훈련비 {int(new_price.notna().sum())}행 (0원 → 실제 훈련비)")

    if args.dry_run:
        print("--dry-run: 카탈로그는 바꾸지 않았습니다.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"education_courses_search_cleaned.before_work24_detail_{datetime.now():%Y%m%d_%H%M%S}.parquet"
    shutil.copy2(CATALOG, backup)

    idx_h = new_hours.dropna().index
    df.loc[idx_h, "duration_hours"] = new_hours.dropna().astype(float)
    idx_p = new_price.dropna().index
    df.loc[idx_p, "price"] = new_price.dropna().astype("int64")
    touched = idx_h.union(idx_p)
    note = "work24_detail_enriched"
    df.loc[touched, "cleaning_actions"] = df.loc[touched, "cleaning_actions"].fillna("").map(
        lambda s: s if note in s else (f"{s}, {note}" if s else note)
    )
    df.to_parquet(CATALOG, index=False, compression="zstd", compression_level=9)
    print(f"카탈로그 저장 완료 (백업: {backup.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
