"""Step D: Execute Round 2 Targeted API Collection for Deficient HR/GA Competencies.
Endpoints:
1. Work24 (HRD-Net) KMBC API (callOpenApiSvcInfo310L01.do)
2. Work24 (HRD-Net) Employer Training API (callOpenApiSvcInfo311L01.do)
3. HRDKorea NCS Course API (openapi20)
Saves raw JSON/XML to data/hr/raw/round2/ without exposing API keys.
"""
import os
import sys
import time
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

BASE_DIR = Path(".")
ROUND2_RAW_DIR = BASE_DIR / "data" / "hr" / "raw" / "round2"
ROUND2_RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def mask_key(k):
    if not k:
        return "[미설정]"
    return f"{k[:3]}****{k[-3:]} (길이 {len(k)})"

def run_round2_collection():
    print("=" * 80)
    print(" [STEP D] 2차 맞춤형 실측 API 데이터 수집 실행 (부족 역량 집중 타겟팅)")
    print("=" * 80)

    kmbc_key = os.getenv("HRD_KMBC_API_KEY")
    emp_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY")
    ncs_key = os.getenv("NCS_COURSE_API_KEY_DECODING") or os.getenv("DATA_GO_KR_API_KEY_DECODING")

    print(f"* KMBC 인증키 상태: {mask_key(kmbc_key)}")
    print(f"* 사업주훈련 인증키 상태: {mask_key(emp_key)}")
    print(f"* NCS 인증키 상태: {mask_key(ncs_key)}")

    logs = []
    
    # 수집 타겟 키워드 (인사 4개, 총무 2개)
    target_keywords = [
        {"kw": "인사관리", "priority": "1순위(인사)", "comp": "COMP_HR_01/02"},
        {"kw": "채용실무", "priority": "1순위(채용)", "comp": "COMP_HR_01"},
        {"kw": "근로기준법", "priority": "1순위(노무)", "comp": "COMP_LABOR_01"},
        {"kw": "인사평가", "priority": "1순위(평가)", "comp": "COMP_HR_02"},
        {"kw": "총무관리", "priority": "2순위(총무)", "comp": "COMP_GA_01/02"},
        {"kw": "자산관리", "priority": "2순위(자산)", "comp": "COMP_GA_02"}
    ]

    # --------------------------------------------------------------------------
    # 1. 고용24 국민내일배움카드 수집
    # --------------------------------------------------------------------------
    print("\n--- [1] 국민내일배움카드 2차 수집 ---")
    ep_kmbc = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
    kmbc_items = []

    for item in target_keywords:
        kw = item["kw"]
        p = {
            "authKey": kmbc_key,
            "returnType": "XML",
            "outType": "1",
            "pageNum": "1",
            "pageSize": "10",
            "srchTraStDt": "20250101",
            "srchTraEndDt": "20251231",
            "srchTraProcessNm": kw
        }
        req_time = datetime.now(timezone.utc).isoformat()
        try:
            r = requests.get(ep_kmbc, params=p, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                elements = root.findall(".//scn_list")
                cnt = root.findtext("scn_cnt") or "0"
                for elem in elements:
                    d = {child.tag: child.text for child in elem}
                    d["_target_keyword"] = kw
                    d["_source_api"] = "국민내일배움카드"
                    kmbc_items.append(d)
                logs.append({
                    "api": "국민내일배움카드",
                    "keyword": kw,
                    "status_code": 200,
                    "total_server_cnt": int(cnt),
                    "received_count": len(elements),
                    "error": None,
                    "timestamp": req_time
                })
                print(f"  [OK] 키워드 '{kw}': 수신 {len(elements)}건 (서버 전체 {cnt}건)")
            else:
                logs.append({
                    "api": "국민내일배움카드",
                    "keyword": kw,
                    "status_code": r.status_code,
                    "received_count": 0,
                    "error": f"HTTP {r.status_code}",
                    "timestamp": req_time
                })
                print(f"  [-] 키워드 '{kw}': HTTP 오류 {r.status_code}")
        except Exception as e:
            logs.append({
                "api": "국민내일배움카드",
                "keyword": kw,
                "status_code": None,
                "received_count": 0,
                "error": str(e),
                "timestamp": req_time
            })
            print(f"  [-] 키워드 '{kw}': 예외 발생 {e}")
        time.sleep(0.3)

    # --------------------------------------------------------------------------
    # 2. 고용24 사업주훈련 수집
    # --------------------------------------------------------------------------
    print("\n--- [2] 사업주훈련 2차 수집 ---")
    ep_emp = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do"
    emp_items = []

    for item in target_keywords:
        kw = item["kw"]
        p = {
            "authKey": emp_key,
            "returnType": "XML",
            "outType": "1",
            "pageNum": "1",
            "pageSize": "10",
            "srchTraStDt": "20250101",
            "srchTraEndDt": "20251231",
            "srchTraProcessNm": kw
        }
        req_time = datetime.now(timezone.utc).isoformat()
        try:
            r = requests.get(ep_emp, params=p, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                elements = root.findall(".//scn_list")
                cnt = root.findtext("scn_cnt") or "0"
                for elem in elements:
                    d = {child.tag: child.text for child in elem}
                    d["_target_keyword"] = kw
                    d["_source_api"] = "사업주훈련"
                    emp_items.append(d)
                logs.append({
                    "api": "사업주훈련",
                    "keyword": kw,
                    "status_code": 200,
                    "total_server_cnt": int(cnt),
                    "received_count": len(elements),
                    "error": None,
                    "timestamp": req_time
                })
                print(f"  [OK] 키워드 '{kw}': 수신 {len(elements)}건 (서버 전체 {cnt}건)")
            else:
                logs.append({
                    "api": "사업주훈련",
                    "keyword": kw,
                    "status_code": r.status_code,
                    "received_count": 0,
                    "error": f"HTTP {r.status_code}",
                    "timestamp": req_time
                })
                print(f"  [-] 키워드 '{kw}': HTTP 오류 {r.status_code}")
        except Exception as e:
            logs.append({
                "api": "사업주훈련",
                "keyword": kw,
                "status_code": None,
                "received_count": 0,
                "error": str(e),
                "timestamp": req_time
            })
            print(f"  [-] 키워드 '{kw}': 예외 발생 {e}")
        time.sleep(0.3)

    # --------------------------------------------------------------------------
    # 3. 한국산업인력공단 NCS 교육과정 (추가 페이지 수집)
    # --------------------------------------------------------------------------
    print("\n--- [3] 한국산업인력공단 NCS 교육과정 (추가 페이지 수집) ---")
    ep_ncs = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
    ncs_items = []

    # 2페이지 및 3페이지 조회
    for p_no in [2, 3]:
        p = {
            "serviceKey": ncs_key,
            "pageNo": p_no,
            "numOfRows": 10,
            "returnType": "json",
            "ncsLclasCd": "02"  # 경영·회계·사무
        }
        req_time = datetime.now(timezone.utc).isoformat()
        try:
            r = requests.get(ep_ncs, params=p, timeout=12)
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", [])
                for it in items:
                    it["_target_page"] = p_no
                    it["_source_api"] = "NCS 교육과정"
                    ncs_items.append(it)
                logs.append({
                    "api": "NCS 교육과정",
                    "keyword": f"대분류02_p{p_no}",
                    "status_code": 200,
                    "received_count": len(items),
                    "error": None,
                    "timestamp": req_time
                })
                print(f"  [OK] NCS p{p_no}: 수신 {len(items)}건")
            else:
                logs.append({
                    "api": "NCS 교육과정",
                    "keyword": f"대분류02_p{p_no}",
                    "status_code": r.status_code,
                    "received_count": 0,
                    "error": f"HTTP {r.status_code}",
                    "timestamp": req_time
                })
        except Exception as e:
            logs.append({
                "api": "NCS 교육과정",
                "keyword": f"대분류02_p{p_no}",
                "status_code": None,
                "received_count": 0,
                "error": str(e),
                "timestamp": req_time
            })
            print(f"  [-] NCS p{p_no} 예외: {e}")
        time.sleep(0.3)

    # --------------------------------------------------------------------------
    # 원본 파일 저장 (data/hr/raw/round2/)
    # --------------------------------------------------------------------------
    with open(ROUND2_RAW_DIR / "kmbc_round2_raw.json", "w", encoding="utf-8") as f:
        json.dump(kmbc_items, f, ensure_ascii=False, indent=2)
    with open(ROUND2_RAW_DIR / "employer_round2_raw.json", "w", encoding="utf-8") as f:
        json.dump(emp_items, f, ensure_ascii=False, indent=2)
    with open(ROUND2_RAW_DIR / "ncs_round2_raw.json", "w", encoding="utf-8") as f:
        json.dump(ncs_items, f, ensure_ascii=False, indent=2)
    with open(ROUND2_RAW_DIR / "round2_collection_logs.json", "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print(f"[+] 2차 수집 원본 저장 완료 -> {ROUND2_RAW_DIR.resolve()}")
    print(f"    - KMBC 수집 건수: {len(kmbc_items)}건")
    print(f"    - 사업주훈련 수집 건수: {len(emp_items)}건")
    print(f"    - NCS 교육과정 수집 건수: {len(ncs_items)}건")
    print(f"    - 총 2차 원본 레코드 수: {len(kmbc_items) + len(emp_items) + len(ncs_items)}건")
    print("=" * 80)

if __name__ == "__main__":
    run_round2_collection()
