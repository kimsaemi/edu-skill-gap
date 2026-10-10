import os
import sys
import requests
import xmltodict
import json
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

print("==================================================")
print("  STEP 1: 3대 핵심 API 연동 및 실제 응답 필드 정밀 점검")
print("==================================================")

# ----------------------------------------------------
# 1. 국민내일배움카드 훈련과정 API
# ----------------------------------------------------
print("\n[1] 국민내일배움카드 훈련과정 API (고용24 310L01)")
kmbc_url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
kmbc_key = os.getenv("HRD_KMBC_API_KEY")

if not kmbc_key:
    print("  [ERROR] HRD_KMBC_API_KEY 가 .env에 설정되어 있지 않습니다.")
else:
    kmbc_params = {
        "authKey": kmbc_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": "1",
        "pageSize": "3",
        "srchNcs1": "02" # 경영·회계·사무 (인사/총무)
    }
    try:
        res = requests.get(kmbc_url, params=kmbc_params, headers=headers, timeout=10)
        print(f"  - HTTP Status: {res.status_code}")
        print(f"  - Content-Type: {res.headers.get('Content-Type')}")
        
        parsed = xmltodict.parse(res.text)
        if "HRDNet" in parsed:
            root = parsed["HRDNet"]
            total_cnt = root.get("scn_cnt", "0")
            page_num = root.get("pageNum", "1")
            page_size = root.get("pageSize", "1")
            print(f"  - Total Count (scn_cnt): {total_cnt}건")
            print(f"  - Page: {page_num} / Size: {page_size}")
            
            # 단일/다중 아이템 처리 (HRDNet -> srchList -> scn_list)
            srch_list_obj = root.get("srchList", {})
            if isinstance(srch_list_obj, dict):
                scn_items = srch_list_obj.get("scn_list", [])
            elif isinstance(srch_list_obj, list):
                scn_items = srch_list_obj
            else:
                scn_items = []
                
            if isinstance(scn_items, dict):
                srch_items = [scn_items]
            elif isinstance(scn_items, list):
                srch_items = scn_items
            else:
                srch_items = []
                
            print(f"  - First Page Items Parsed: {len(srch_items)}개")
            if srch_items:
                sample_item = srch_items[0]
                print(f"  - Item Fields ({len(sample_item.keys())}개):")
                print(f"    * title (과정명): {sample_item.get('title')}")
                print(f"    * subTitle (훈련기관명): {sample_item.get('subTitle')}")
                print(f"    * trprId (훈련과정ID): {sample_item.get('trprId')}")
                print(f"    * trprDegr (훈련과정회차): {sample_item.get('trprDegr')}")
                print(f"    * traStartDate ~ traEndDate: {sample_item.get('traStartDate')} ~ {sample_item.get('traEndDate')}")
                print(f"    * ncsCd (NCS코드): {sample_item.get('ncsCd')}")
                print(f"    * realMan (실제수강료): {sample_item.get('realMan')}원")
                print(f"    * address (훈련장소): {sample_item.get('address')}")
                print(f"    * titleLink (상세링크): {sample_item.get('titleLink')}")
        elif "error" in parsed or "returnAuthMsg" in res.text:
            print(f"  - [API Error Response]: {res.text[:300]}")
        else:
            print(f"  - [Unexpected Response Root]: {list(parsed.keys())}")
    except Exception as e:
        print(f"  - [Exception]: {e}")

# ----------------------------------------------------
# 2. 사업주훈련 훈련과정 API
# ----------------------------------------------------
print("\n[2] 사업주훈련 훈련과정 API (고용24 311L01)")
emp_url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do"
emp_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY") or os.getenv("HRD_KMBC_API_KEY")

if not emp_key:
    print("  [ERROR] HRD_EMPLOYER_TRAINING_API_KEY 가 .env에 설정되어 있지 않습니다.")
else:
    emp_params = {
        "authKey": emp_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": "1",
        "pageSize": "3",
        "srchNcs1": "02"
    }
    try:
        res = requests.get(emp_url, params=emp_params, headers=headers, timeout=10)
        print(f"  - HTTP Status: {res.status_code}")
        parsed = xmltodict.parse(res.text)
        if "HRDNet" in parsed:
            root = parsed["HRDNet"]
            total_cnt = root.get("scn_cnt", "0")
            print(f"  - Total Count (scn_cnt): {total_cnt}건")
            srch_list_obj = root.get("srchList", {})
            if isinstance(srch_list_obj, dict):
                scn_items = srch_list_obj.get("scn_list", [])
            elif isinstance(srch_list_obj, list):
                scn_items = srch_list_obj
            else:
                scn_items = []
            if isinstance(scn_items, dict):
                srch_items = [scn_items]
            elif isinstance(scn_items, list):
                srch_items = scn_items
            else:
                srch_items = []
            print(f"  - First Page Items Parsed: {len(srch_items)}개")
            if srch_items:
                sample_item = srch_items[0]
                print(f"    * title: {sample_item.get('title')}")
                print(f"    * subTitle: {sample_item.get('subTitle')}")
                print(f"    * trprId: {sample_item.get('trprId')}")
                print(f"    * ncsCd: {sample_item.get('ncsCd')}")
                print(f"    * realMan: {sample_item.get('realMan')}원")
                print(f"    * titleLink: {sample_item.get('titleLink')}")
        else:
            print(f"  - [Response snippet]: {res.text[:300]}")
    except Exception as e:
        print(f"  - [Exception]: {e}")

# ----------------------------------------------------
# 3. NCS 교육과정 API (한국산업인력공단 / 공공데이터포털)
# ----------------------------------------------------
print("\n[3] NCS 교육과정 API (한국산업인력공단 / 공공데이터포털)")
ncs_base_url = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
dec_key = os.getenv("DATA_GO_KR_API_KEY_DECODING")
enc_key = os.getenv("DATA_GO_KR_API_KEY_ENCODING")

# Decoding 키 테스트
print("  - Testing with DECODING key:")
try:
    ncs_params = {
        "serviceKey": dec_key,
        "pageNo": 1,
        "numOfRows": 3
    }
    res = requests.get(ncs_base_url, params=ncs_params, headers=headers, timeout=10)
    print(f"    * Status: {res.status_code}")
    print(f"    * Content-Type: {res.headers.get('Content-Type')}")
    print(f"    * Raw Snippet: {res.text[:200]}")
    if res.headers.get("Content-Type", "").startswith("application/json") or res.text.strip().startswith("{"):
        jd = res.json()
        print(f"    * JSON Response Root: {list(jd.keys())}")
        if "response" in jd:
            header = jd["response"].get("header", {})
            body = jd["response"].get("body", {})
            print(f"    * Header: {header}")
            print(f"    * Total Count: {body.get('totalCount')}")
            items = body.get("items", {}).get("item", [])
            print(f"    * Items Count: {len(items)}")
            if items:
                print(f"    * Sample Item: {items[0]}")
except Exception as e:
    print(f"    * Exception: {e}")

# Encoding 키 테스트 (만약 requests에서 decoding 키 오류 발생 시 대비)
print("  - Testing with ENCODING key (direct query string):")
try:
    url_enc = f"{ncs_base_url}?serviceKey={enc_key}&pageNo=1&numOfRows=3"
    res_enc = requests.get(url_enc, headers=headers, timeout=10)
    print(f"    * Status: {res_enc.status_code}, Length: {len(res_enc.text)}")
    print(f"    * Raw Snippet: {res_enc.text[:200]}")
except Exception as e:
    print(f"    * Exception: {e}")

print("\n==================================================")
print("  API 정밀 점검 완료")
print("==================================================")
