"""
고용24 국민내일배움카드 공식 만족도(stdgScor) 전체 페이지 수집기
파일명: scripts/collect_official_satisfaction.py

목적:
  - 고용24 국민내일배움카드 훈련과정 목록 API(310L01)의 stdgScor(만족도) 값을
    모든 페이지에서 수집해 과정(trprId) 단위로 정리합니다.
  - 합성/추정 평점을 쓰지 않고, 공식 값만 satisfaction_official 컬럼으로 제공합니다.

원칙:
  - stdgScor가 0 또는 빈 값이면 "설문 없음"으로 보고 None 처리 (0점으로 쓰지 않음)
  - 같은 과정은 회차가 달라도 점수가 같으므로 trprId당 1행만 남김
  - 사업주훈련 API(311L01)는 stdgScor 항목이 없어 수집 대상에서 제외
  - 인증키는 화면에 출력하지 않음, 원본 응답은 data/hr/raw/satisfaction/에 보관

출력:
  - data/hr/raw/satisfaction/kmbc_satisfaction_raw.json   (원본 행 전체)
  - data/hr/processed/official_satisfaction.csv           (trprId 단위 정리본)
  - data/hr/processed/official_satisfaction_summary.json  (수집/매칭 요약)

사용법:
  python scripts/collect_official_satisfaction.py
  python scripts/collect_official_satisfaction.py --start 20250101 --end 20261231 --max-pages 30
"""

import argparse
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "hr" / "raw" / "satisfaction"
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"
CATALOG_PATH = PROCESSED_DIR / "education_courses_search_cleaned.parquet"

ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
PAGE_SIZE = 100

# 1차·2차 수집에서 쓴 인사·총무 키워드를 합친 목록
DEFAULT_KEYWORDS = [
    "인사", "총무", "노무", "인사관리", "채용", "근로기준법",
    "인사평가", "총무관리", "자산관리", "급여", "교육훈련", "조직관리",
]

SOURCE_LABEL = "고용24 공식 만족도(국민내일배움카드)"


def mask_key(k: str) -> str:
    """인증키 마스킹 (보안 출력용)"""
    if not k:
        return "[미설정]"
    return f"{k[:3]}****{k[-4:]} (총 {len(k)}자)" if len(k) > 8 else "****"


def parse_score(raw):
    """stdgScor 문자열을 float로 변환. 0·빈 값·비정상 값은 None(설문 없음)."""
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    if value <= 0 or value > 100:
        return None
    return value


def fetch_page(auth_key, keyword, page, start, end):
    """API 1페이지 호출. (전체 건수, 행 목록) 반환. 실패 시 예외 발생."""
    params = {
        "authKey": auth_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": str(page),
        "pageSize": str(PAGE_SIZE),
        "srchTraStDt": start,
        "srchTraEndDt": end,
        "srchTraProcessNm": keyword,
        "sort": "ASC",
        "sortCol": "TRNG_BGDE",
    }
    res = requests.get(ENDPOINT, params=params, headers=HEADERS, timeout=20)
    res.raise_for_status()

    # 권한 오류 시 HTTP 200 + HTML 오류 페이지가 오므로 본문으로 판별
    if "<HRDNet" not in res.text[:500]:
        raise ValueError("XML이 아닌 응답(권한 오류 또는 HTML 오류 페이지)")

    root = ET.fromstring(res.text)
    total = int(root.findtext("scn_cnt") or 0)
    rows = [{child.tag: child.text for child in elem} for elem in root.findall(".//scn_list")]
    return total, rows


def collect(auth_key, keywords, start, end, max_pages, delay):
    """키워드별로 모든 페이지를 순회하며 원본 행과 호출 로그를 모음."""
    all_rows, logs = [], []
    for keyword in keywords:
        page, total_pages = 1, 1
        while page <= total_pages and page <= max_pages:
            try:
                total, rows = fetch_page(auth_key, keyword, page, start, end)
                total_pages = max(1, -(-total // PAGE_SIZE))
                for row in rows:
                    row["_keyword"] = keyword
                all_rows.extend(rows)
                logs.append({"keyword": keyword, "page": page, "total": total, "rows": len(rows), "ok": True})
                print(f"  - [{keyword}] {page}/{total_pages}쪽: {len(rows)}건 (전체 {total}건)")
                if not rows:
                    break
            except Exception as e:
                logs.append({"keyword": keyword, "page": page, "ok": False, "error": str(e)})
                print(f"  - [{keyword}] {page}쪽 실패: {e}")
                break
            page += 1
            time.sleep(delay)
    return all_rows, logs


def dedupe_rows(rows):
    """키워드 간 중복 행을 (trprId, trprDegr) 기준으로 합치고, 걸린 키워드는 '|'로 묶음."""
    merged = {}
    for row in rows:
        key = (row.get("trprId"), row.get("trprDegr"))
        if key in merged:
            kws = set(merged[key]["_keyword"].split("|")) | {row["_keyword"]}
            merged[key]["_keyword"] = "|".join(sorted(kws))
        else:
            merged[key] = dict(row)
    return list(merged.values())


def build_course_table(rows):
    """원본 행을 trprId 단위 1행으로 정리."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["satisfaction_official"] = df["stdgScor"].map(parse_score)
    df["trprDegr_num"] = pd.to_numeric(df["trprDegr"], errors="coerce")

    grouped = df.groupby("trprId", sort=False)
    table = grouped.agg(
        title=("title", "first"),
        institution=("subTitle", "first"),
        trainstCstId=("trainstCstId", "first"),
        ncsCd=("ncsCd", "first"),
        satisfaction_raw=("stdgScor", "first"),
        satisfaction_official=("satisfaction_official", "max"),
        distinct_scores=("satisfaction_official", lambda s: s.dropna().nunique()),
        degree_count=("trprDegr", "nunique"),
        latest_degree=("trprDegr_num", "max"),
        first_start=("traStartDate", "min"),
        last_end=("traEndDate", "max"),
        keywords=("_keyword", lambda s: "|".join(sorted({k for v in s for k in v.split("|")}))),
    ).reset_index()

    table["has_satisfaction"] = table["satisfaction_official"].notna()
    table["satisfaction_source"] = table["has_satisfaction"].map(lambda x: SOURCE_LABEL if x else None)
    table["collected_at"] = datetime.now(timezone.utc).isoformat()
    return table


def catalog_missing_courses(found_ids):
    """카탈로그의 국민내일배움카드 과정(ACG…) 중 아직 수집되지 않은 {trprId: 제목}."""
    if not CATALOG_PATH.exists():
        return {}
    catalog = pd.read_parquet(CATALOG_PATH, columns=["source_course_id", "title"])
    catalog = catalog[catalog["source_course_id"].astype(str).str.fullmatch(r"ACG\d{14}")]
    missing = catalog[~catalog["source_course_id"].isin(found_ids)].dropna(subset=["title"])
    return dict(zip(missing["source_course_id"], missing["title"]))


def lookup_by_title(auth_key, missing, start, end, delay, max_pages=60):
    """제목으로 검색해 해당 trprId 행만 수집. 찾으면 그 과정의 검색을 멈춤."""
    rows, logs = [], []
    for trpr_id, title in missing.items():
        page, total_pages, hits = 1, 1, []
        while page <= total_pages and page <= max_pages:
            try:
                total, page_rows = fetch_page(auth_key, title, page, start, end)
            except Exception as e:
                logs.append({"keyword": title, "page": page, "ok": False, "error": str(e)})
                break
            total_pages = max(1, -(-total // PAGE_SIZE))
            hits = [r for r in page_rows if r.get("trprId") == trpr_id]
            logs.append({"keyword": title, "page": page, "total": total, "rows": len(hits), "ok": True})
            if hits or not page_rows:
                break
            page += 1
            time.sleep(delay)
        for r in hits:
            r["_keyword"] = "catalog_title"
        rows.extend(hits)
        print(f"  - [{trpr_id}] {title[:30]}: {'찾음' if hits else '못 찾음'} ({page}쪽)")
    return rows, logs


def match_catalog(table):
    """추천 카탈로그(source_course_id = trprId)와 연결 현황 계산."""
    if not CATALOG_PATH.exists() or table.empty:
        return table, {}
    catalog = pd.read_parquet(CATALOG_PATH, columns=["source_course_id"])
    catalog_ids = set(catalog["source_course_id"].dropna().astype(str))
    table["in_catalog"] = table["trprId"].isin(catalog_ids)

    work24_ids = {i for i in catalog_ids if re.fullmatch(r"A[A-Z]{2}\d{14}", i)}
    scored_ids = set(table.loc[table["has_satisfaction"], "trprId"])
    return table, {
        "catalog_trprId_count": len(work24_ids),
        "catalog_matched": int(table["in_catalog"].sum()),
        "catalog_matched_with_score": len(scored_ids & catalog_ids),
    }


def main():
    parser = argparse.ArgumentParser(description="고용24 공식 만족도(stdgScor) 전체 수집")
    parser.add_argument("--start", default="20240101", help="훈련 시작일 검색 시작 (YYYYMMDD)")
    parser.add_argument("--end", default="20261231", help="훈련 시작일 검색 끝 (YYYYMMDD)")
    parser.add_argument("--max-pages", type=int, default=500, help="키워드당 최대 페이지 수")
    parser.add_argument("--delay", type=float, default=0.4, help="호출 간 대기(초)")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS)
    args = parser.parse_args()

    auth_key = os.getenv("HRD_KMBC_API_KEY")
    print("=" * 70)
    print(" 고용24 국민내일배움카드 공식 만족도(stdgScor) 수집")
    print(f" 인증키: {mask_key(auth_key)} | 기간: {args.start}~{args.end} | 키워드 {len(args.keywords)}개")
    print("=" * 70)
    if not auth_key:
        print("[-] HRD_KMBC_API_KEY가 .env에 없습니다. 수집을 중단합니다.")
        return

    rows, logs = collect(auth_key, args.keywords, args.start, args.end, args.max_pages, args.delay)

    # 키워드에 안 걸린 카탈로그 내 고용24 과정은 제목으로 한 번 더 검색
    # (제목 검색은 부분 일치라 무관한 과정이 섞이므로, 해당 trprId 행만 남김)
    found_ids = {r.get("trprId") for r in rows}
    missing = catalog_missing_courses(found_ids)
    if missing:
        print(f"\n* 카탈로그 미연결 과정 {len(missing)}개를 제목으로 추가 검색")
        extra_rows, extra_logs = lookup_by_title(auth_key, missing, args.start, args.end, args.delay)
        rows += extra_rows
        logs += extra_logs
    raw_row_count = len(rows)
    rows = dedupe_rows(rows)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_DIR / "kmbc_satisfaction_raw.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    table = build_course_table(rows)
    table, catalog_stats = match_catalog(table)

    out_csv = PROCESSED_DIR / "official_satisfaction.csv"
    table.to_csv(out_csv, index=False, encoding="utf-8-sig")

    scored = table[table["has_satisfaction"]] if not table.empty else table
    summary = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "period": [args.start, args.end],
        "keywords": args.keywords,
        "raw_rows": raw_row_count,
        "deduped_rows": len(rows),
        "unique_courses": len(table),
        "courses_with_score": len(scored),
        "courses_without_score": len(table) - len(scored),
        "courses_with_conflicting_scores": int((table["distinct_scores"] > 1).sum()) if not table.empty else 0,
        "score_mean": round(float(scored["satisfaction_official"].mean()), 2) if len(scored) else None,
        "score_min": float(scored["satisfaction_official"].min()) if len(scored) else None,
        "score_max": float(scored["satisfaction_official"].max()) if len(scored) else None,
        "failed_calls": sum(1 for l in logs if not l["ok"]),
        **catalog_stats,
        "note": "stdgScor 0/빈 값은 설문 없음으로 보고 None 처리. 사업주훈련은 해당 항목 미제공.",
        "call_logs": logs,
    }
    with open(PROCESSED_DIR / "official_satisfaction_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("-" * 70)
    print(f"원본 행 {summary['raw_rows']}건 → 중복 제거 {summary['deduped_rows']}건 → 고유 과정 {summary['unique_courses']}개")
    print(f"만족도 있음 {summary['courses_with_score']}개 / 없음 {summary['courses_without_score']}개")
    if catalog_stats:
        print(f"카탈로그 연결: {catalog_stats['catalog_matched']}개 (점수 있음 {catalog_stats['catalog_matched_with_score']}개)")
    print(f"실패 호출 {summary['failed_calls']}건 | 저장: {out_csv.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
