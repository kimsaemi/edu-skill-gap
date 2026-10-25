"""
수도권 직무교육 프로젝트 - 인사·총무 직무 교육과정 수집기
파일명: scripts/collect_hr_courses.py

수집 대상:
  1. 한국산업인력공단 NCS 교육과정 API (대분류 02: 경영·회계·사무 -> 중분류 02: 총무·인사)
  2. 고용24 (구 HRD-Net) 국민내일배움카드 훈련과정 API
  3. 고용24 (구 HRD-Net) 사업주훈련 훈련과정 API

원칙 준수:
  - 실제 API 데이터만 사용 (가상 Mock 데이터 생성 절대 금지)
  - 인증키 화면 미출력 (보안 준수)
  - 원본 응답 그대로 'data/hr/raw'에 JSON/XML 파일로 보관
  - 코드값 및 과정 ID의 문자열(str) 보존
  - 페이지네이션, 호출 제한(Sleep), 예외 처리, 인증 실패 대응

사용법 (API 키가 들어 있는 .env가 있는 PC에서 실행):
  python scripts/collect_hr_courses.py                 # NCS + 고용24 전체
  python scripts/collect_hr_courses.py --only work24   # 고용24 두 API만
  python scripts/collect_hr_courses.py --only kmbc --months 3 --max-pages 10
  python scripts/collect_hr_courses.py --from-raw data/hr/raw/round2/kmbc_round2_raw.json ...
                                                       # 네트워크 없이 저장된 원본으로 만족도 표만 다시 만들기

출력:
  data/hr/raw/work24/<수집일>/        고용24 원본 XML(페이지별), 회차 목록 JSON, 호출 기록
  data/hr/processed/work24_course_satisfaction.csv
      과정(trprId)당 한 행. satisfaction_official은 stdgScor > 0인 값만 담고,
      satisfaction_status는 '점수 있음' / '설문 없음(0)' / '제공 안 됨'(사업주훈련) 중 하나.
      응답자 수는 API가 제공하지 않으므로 화면에는 참고 정보로만 표시하고 추천 점수에는 넣지 않는다.

시험: python scripts/test_collect_work24.py (네트워크 불필요)
"""

import os
import sys
import time
import json
import argparse
from datetime import date, datetime, timedelta, timezone
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import load_dotenv

# 1. 환경변수 로드
load_dotenv()

# 저장 디렉토리 설정 (data/hr/raw)
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "hr" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def mask_key(k: str) -> str:
    """인증키 마스킹 (보안 출력용)"""
    if not k:
        return "[미설정]"
    if len(k) <= 8:
        return "****"
    return f"{k[:3]}****{k[-4:]} (총 {len(k)}자)"


# ==============================================================================
# [수집기 1] 한국산업인력공단 NCS 교육과정 API
# ==============================================================================
def collect_ncs_hr_courses(max_pages=10, delay_sec=0.5):
    """
    한국산업인력공단 NCS 교육과정 수집 (대분류 02: 경영·회계·사무)
    - 페이지네이션 지원 (pageNo 1부터 totalPage까지)
    - 원본 JSON 응답을 data/hr/raw/ncs_courses_page_{page}.json 및 통합본에 저장
    """
    print("\n" + "=" * 70)
    print("▶ [1/3] 한국산업인력공단 NCS 교육과정 API 수집 시작")
    print("=" * 70)

    dec_key = os.getenv("NCS_COURSE_API_KEY_DECODING") or os.getenv("DATA_GO_KR_API_KEY_DECODING")
    print(f"* 인증키 상태: {mask_key(dec_key)}")

    if not dec_key:
        print("[-] [인증 실패] NCS API 디코딩 인증키가 .env에 설정되어 있지 않습니다.")
        return {"success_count": 0, "fail_count": 1, "items": []}

    endpoint = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
    current_page = 1
    total_pages = 1
    all_raw_data = []
    success_pages = 0
    fail_pages = 0

    while current_page <= total_pages and current_page <= max_pages:
        params = {
            "serviceKey": dec_key,
            "pageNo": current_page,
            "numOfRows": 20,
            "returnType": "json",
            "ncsLclasCd": "02"  # 경영·회계·사무 대분류 (필수 파라미터, 2자리 문자열)
        }

        print(f"  - [{current_page}/{total_pages}] 페이지 호출 중... (대분류: 02)")
        try:
            res = requests.get(endpoint, params=params, timeout=10)
            
            # HTTP 상태 확인
            if res.status_code != 200:
                print(f"    [-] HTTP 오류 발생: {res.status_code}")
                fail_pages += 1
                break

            # JSON 파싱
            data = res.json()
            data_info = data.get("dataInfo", {})
            api_code = data_info.get("code")
            api_msg = data_info.get("message")

            # 인증키 만료나 파라미터 에러 등 대응
            if api_code != "000":
                print(f"    [-] API 오류 응답: 코드={api_code}, 메시지={api_msg}")
                fail_pages += 1
                break

            # 페이지 정보 갱신
            total_pages = int(data_info.get("totalPage", 1))
            tot_cnt = int(data_info.get("totCnt", 0))
            page_items = data.get("data", [])

            # 원본 응답 파일 저장 (수집 원본 그대로 보존)
            page_file = RAW_DIR / f"ncs_courses_page_{current_page}.json"
            with open(page_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            all_raw_data.extend(page_items)
            success_pages += 1
            print(f"    [+] {len(page_items)}건 수신 (누적 {len(all_raw_data)}/{tot_cnt}건) -> 원본 저장: {page_file.name}")

            current_page += 1
            time.sleep(delay_sec)  # API 호출 제한 방지 (Sleep)

        except requests.exceptions.Timeout:
            print("    [-] [타임아웃] 요청 시간이 초과되었습니다.")
            fail_pages += 1
            break
        except requests.exceptions.RequestException as e:
            print(f"    [-] [통신 오류] {e}")
            fail_pages += 1
            break
        except json.JSONDecodeError:
            print("    [-] [파싱 오류] JSON 응답을 해석할 수 없습니다.")
            fail_pages += 1
            break

    # 통합 원본 파일 저장
    combined_file = RAW_DIR / "ncs_courses_raw.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_raw_data, f, ensure_ascii=False, indent=2)

    # 인사·총무 관련 과정 필터링 확인 (NCS 중분류코드 '02' = 총무·인사)
    hr_candidates = []
    for item in all_raw_data:
        mclas_cd = str(item.get("ncsMclasCd", "")).zfill(2)
        mclas_nm = str(item.get("ncsMclasCdnm", ""))
        subj_name = str(item.get("asubjName", ""))
        edu_text = str(item.get("eduText", ""))

        # 중분류 02(총무·인사)이거나 관련 키워드가 포함된 경우
        if mclas_cd == "02" or any(kw in (subj_name + edu_text + mclas_nm) for kw in ["인사", "총무", "노무", "사무"]):
            hr_candidates.append(item)

    print(f"\n* NCS 교육과정 수집 결과:")
    print(f"  - 성공 페이지: {success_pages}개, 실패 페이지: {fail_pages}개")
    print(f"  - 수집된 전체 원본 건수: {len(all_raw_data)}건")
    print(f"  - 인사·총무·사무 관련 후보 건수: {len(hr_candidates)}건")

    return {
        "success_count": len(all_raw_data),
        "fail_count": fail_pages,
        "hr_candidate_count": len(hr_candidates),
        "raw_file": str(combined_file)
    }


# ==============================================================================
# [수집기 2·3] 고용24 국민내일배움카드 / 사업주훈련 훈련과정 API
# ==============================================================================
# 두 API는 응답 구조가 같으므로 하나의 함수로 수집한다.
#
# 이전 버전과 달라진 점 (2026-10-25)
#   - 1페이지 20건만 받던 것을 모든 페이지 반복 수집으로 변경
#   - 검색 기간을 2025년 고정값에서 '오늘 ~ N개월 뒤'로 변경 (수강 가능한 회차만)
#   - 검색어 파라미터를 srchTraProcess -> srchTraProcessNm(훈련과정명)으로 수정
#     (srchTraProcess로는 검색어가 적용되지 않아 전체 18,051건이 조회되었음)
#   - 오류 응답(HTML 리다이렉트 등)을 정상 응답으로 저장하지 않도록 검사
#   - 원본은 data/hr/raw/work24/<수집일>/ 아래에 새로 저장
#     (기존 kmbc_courses_raw.json 등은 다른 스크립트가 읽으므로 덮어쓰지 않음)

WORK24_APIS = {
    "kmbc": {
        "name": "국민내일배움카드",
        "endpoint": "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do",
        "key_env": "HRD_KMBC_API_KEY",
    },
    "employer": {
        "name": "사업주훈련",
        "endpoint": "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do",
        "key_env": "HRD_EMPLOYER_TRAINING_API_KEY",
    },
}

# 1·2차 수집에서 쓰던 검색어를 합친 목록 (훈련과정명 검색)
# 검색 결과가 넓게 잡히므로(예: '인사관리' 2025년 3,926건) 수집 후 기존 분류 단계에서 관련 과정만 거른다.
WORK24_KEYWORDS = [
    "인사", "총무", "인사관리", "채용", "근로기준법", "노무", "인사평가",
    "급여", "총무관리", "자산관리", "비서", "사무행정",
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
WORK24_RAW_DIR = RAW_DIR / "work24"


def parse_work24_xml(xml_text):
    """고용24 목록 응답 XML -> (전체 건수, 과정 목록). 정상 응답이 아니면 ValueError."""
    root = ET.fromstring(xml_text)
    if root.tag != "HRDNet":
        raise ValueError(f"예상하지 못한 응답 형식입니다 (루트 태그: {root.tag})")
    total = int(root.findtext("scn_cnt") or 0)
    items = [{child.tag: child.text for child in it} for it in root.findall(".//scn_list")]
    return total, items


def fetch_work24_page(endpoint, auth_key, keyword, start_date, end_date, page, page_size, retries=3):
    """한 페이지 호출. 일시적 오류는 잠시 쉬었다가 다시 시도한다."""
    params = {
        "authKey": auth_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": str(page),
        "pageSize": str(page_size),
        "srchTraStDt": start_date.strftime("%Y%m%d"),
        "srchTraEndDt": end_date.strftime("%Y%m%d"),
        "srchTraProcessNm": keyword,
    }
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(endpoint, params=params, headers=HTTP_HEADERS, timeout=20, allow_redirects=False)
            if res.status_code != 200:
                raise ValueError(f"HTTP {res.status_code}")
            total, items = parse_work24_xml(res.text)
            return res.text, total, items
        except (requests.exceptions.RequestException, ET.ParseError, ValueError) as e:
            last_error = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"'{keyword}' {page}페이지 호출 실패: {last_error}")


def collect_work24_courses(api_id, keywords=WORK24_KEYWORDS, months_ahead=6,
                           page_size=100, max_pages=30, delay_sec=0.3, today=None):
    """
    고용24 훈련과정을 검색어별로 모든 페이지 수집한다.
    반환: 과정·회차(trprId, trprDegr) 기준 중복 제거된 목록과 호출 기록
    """
    api = WORK24_APIS[api_id]
    print("\n" + "=" * 70)
    print(f"▶ 고용24 {api['name']} 훈련과정 수집")
    print("=" * 70)

    auth_key = os.getenv(api["key_env"])
    print(f"* 인증키 상태: {mask_key(auth_key)}")
    if not auth_key:
        print(f"[-] [인증 실패] {api['key_env']}가 .env에 설정되어 있지 않습니다.")
        return {"api": api_id, "items": [], "logs": [], "error": "인증키 없음"}

    today = today or date.today()
    end_date = today + timedelta(days=round(months_ahead * 30.4))
    run_dir = WORK24_RAW_DIR / today.strftime("%Y%m%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"* 훈련 시작일 검색 기간: {today} ~ {end_date}")

    collected = {}
    logs = []
    for kw in keywords:
        page = 1
        total = None
        while page <= max_pages:
            try:
                xml_text, total, items = fetch_work24_page(
                    api["endpoint"], auth_key, kw, today, end_date, page, page_size)
            except RuntimeError as e:
                print(f"  [-] {e}")
                logs.append({"api": api_id, "keyword": kw, "page": page, "error": str(e)})
                break

            # 원본 응답 보관 (인증키는 응답에 포함되지 않음)
            (run_dir / f"{api_id}_{kw}_p{page:03d}.xml").write_text(xml_text, encoding="utf-8")
            for it in items:
                it["_source_api"] = api["name"]
                it["_search_keyword"] = kw
                it["_collected_at"] = datetime.now(timezone.utc).isoformat()
                collected.setdefault((it.get("trprId"), it.get("trprDegr")), it)
            logs.append({"api": api_id, "keyword": kw, "page": page,
                         "server_total": total, "received": len(items), "error": None})
            print(f"  [+] '{kw}' {page}페이지: {len(items)}건 (검색 결과 전체 {total}건)")

            if not items or page * page_size >= total:
                break
            page += 1
            time.sleep(delay_sec)
        else:
            print(f"  [!] '{kw}': 최대 {max_pages}페이지에서 멈춤 (전체 {total}건). --max-pages를 늘려 주세요.")
        time.sleep(delay_sec)

    items = list(collected.values())
    (run_dir / f"{api_id}_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / f"{api_id}_logs.json").write_text(
        json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"* 중복 제거 후 {len(items)}개 회차 -> {run_dir.relative_to(BASE_DIR)}")
    return {"api": api_id, "items": items, "logs": logs, "raw_dir": str(run_dir)}


def build_satisfaction_table(items):
    """
    회차 단위 목록 -> 과정(trprId) 단위 만족도 표.

    stdgScor 해석 원칙
      - 0보다 큰 값만 실제 만족도로 사용 (0은 '설문 없음'으로 보고 결측 처리)
      - 사업주훈련 API는 stdgScor 항목 자체가 없음 -> '제공 안 됨'
      - 응답자 수는 API가 주지 않으므로 표본 크기를 알 수 없음
      - 같은 과정은 회차가 달라도 값이 같았음(기존 원본 42개 과정 확인). 다르면 최댓값이 아니라
        가장 최근 회차 값을 쓰고 score_varies_by_session으로 표시
    """
    import pandas as pd

    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    if "stdgScor" not in df.columns:
        df["stdgScor"] = None
    df["has_field"] = df["stdgScor"].notna()
    df["score"] = pd.to_numeric(df["stdgScor"], errors="coerce")
    df["start"] = pd.to_datetime(df.get("traStartDate"), errors="coerce")
    df["end"] = pd.to_datetime(df.get("traEndDate"), errors="coerce")

    rows = []
    for trpr_id, g in df.sort_values("start").groupby("trprId", sort=False):
        positive = g.loc[g["score"] > 0, "score"]
        if positive.empty:
            status = "설문 없음(0)" if g["has_field"].any() else "제공 안 됨"
            value = None
        else:
            status = "점수 있음"
            value = float(positive.iloc[-1])
        rows.append({
            "trprId": trpr_id,
            "course_name": g["title"].iloc[-1],
            "institution": g.get("subTitle", pd.Series([None])).iloc[-1],
            "source_api": g["_source_api"].iloc[-1],
            "ncs_code": g.get("ncsCd", pd.Series([None])).iloc[-1],
            "n_sessions": len(g),
            "next_start_date": g["start"].min().date().isoformat() if g["start"].notna().any() else None,
            "last_end_date": g["end"].max().date().isoformat() if g["end"].notna().any() else None,
            "satisfaction_official": value,
            "satisfaction_status": status,
            "score_varies_by_session": positive.nunique() > 1,
            "satisfaction_source": "고용24 공식 만족도(stdgScor), 응답자 수 미공개",
            "collected_at": g["_collected_at"].iloc[-1] if "_collected_at" in g else None,
            "course_url": g.get("titleLink", pd.Series([None])).iloc[-1],
        })
    return pd.DataFrame(rows)


def save_satisfaction_table(items, out_path=None):
    out_path = Path(out_path or BASE_DIR / "data" / "hr" / "processed" / "work24_course_satisfaction.csv")
    table = build_satisfaction_table(items)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_path, index=False, encoding="utf-8-sig")
    if not table.empty:
        print(f"\n* 과정별 만족도 표 저장: {out_path.relative_to(BASE_DIR)} ({len(table)}개 과정)")
        print(table["satisfaction_status"].value_counts().to_string())
    return table


def load_items_from_raw(paths):
    """이미 저장된 원본(JSON 목록 또는 XML)에서 회차 목록을 다시 읽는다. 네트워크 불필요."""
    items = []
    for p in map(Path, paths):
        if p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            for it in data:
                it.setdefault("_source_api", "사업주훈련" if "employer" in p.name else "국민내일배움카드")
                it.setdefault("_collected_at", None)
            items.extend(data)
        else:
            try:
                _, data = parse_work24_xml(p.read_text(encoding="utf-8", errors="ignore"))
            except (ET.ParseError, ValueError):
                print(f"  [건너뜀] 정상 응답이 아닌 파일: {p}")
                continue
            for it in data:
                it["_source_api"] = "사업주훈련" if "employer" in p.name else "국민내일배움카드"
                it["_collected_at"] = None
            items.extend(data)
    dedup = {}
    for it in items:
        dedup.setdefault((it.get("trprId"), it.get("trprDegr")), it)
    return list(dedup.values())


# ==============================================================================
# 메인 실행 진입점
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="인사·총무 교육과정 수집 (NCS + 고용24)")
    parser.add_argument("--only", choices=["ncs", "kmbc", "employer", "work24"], help="일부 API만 수집")
    parser.add_argument("--months", type=float, default=6, help="고용24: 오늘부터 몇 개월 뒤까지 시작하는 회차를 받을지 (기본 6)")
    parser.add_argument("--max-pages", type=int, default=30, help="검색어별 최대 페이지 수 (기본 30)")
    parser.add_argument("--page-size", type=int, default=100, help="페이지당 건수 (기본 100)")
    parser.add_argument("--ncs-max-pages", type=int, default=50, help="NCS 교육과정 최대 페이지 수 (기본 50)")
    parser.add_argument("--from-raw", nargs="+", metavar="FILE",
                        help="네트워크 없이 저장된 원본(JSON/XML)으로 만족도 표만 다시 만들기")
    args = parser.parse_args()

    print("=" * 70)
    print(" [수도권 직무교육] 인사·총무 직무 교육과정 데이터 수집 파이프라인")
    print(f" 저장 위치: {RAW_DIR}")
    print("=" * 70)

    if args.from_raw:
        save_satisfaction_table(load_items_from_raw(args.from_raw))
        return

    if args.only in (None, "ncs"):
        ncs_result = collect_ncs_hr_courses(max_pages=args.ncs_max_pages, delay_sec=0.3)
        print(f"\n[NCS] 수집 {ncs_result['success_count']}건, 인사·총무 후보 {ncs_result.get('hr_candidate_count', 0)}건")

    work24_items = []
    for api_id in ("kmbc", "employer"):
        if args.only in (None, "work24", api_id):
            result = collect_work24_courses(api_id, months_ahead=args.months,
                                            page_size=args.page_size, max_pages=args.max_pages)
            work24_items.extend(result["items"])
            errors = [l for l in result["logs"] if l.get("error")]
            print(f"[{WORK24_APIS[api_id]['name']}] 회차 {len(result['items'])}건, 실패 호출 {len(errors)}건")

    if work24_items:
        save_satisfaction_table(work24_items)

    print("-" * 70)
    print(f"* 전체 저장 경로: {RAW_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
