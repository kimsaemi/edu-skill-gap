import os
import sys
import requests
import xmltodict
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

kmbc_key = os.getenv("HRD_KMBC_API_KEY")
emp_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

candidates = [
    # 1. 고용24 / HRD-Net 공식 훈련과정 목록 API (HRDPOA60_1.jsp / HRDPOA60_2.jsp)
    ("HRD-Net KMBC http", "http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp", kmbc_key, {
        "authKey": kmbc_key, "returnType": "XML", "outType": "1", "pageNum": "1", "pageSize": "2", "srchNcs1": "02"
    }),
    ("HRD-Net Employer http", "http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp", emp_key, {
        "authKey": emp_key, "returnType": "XML", "outType": "1", "pageNum": "1", "pageSize": "2", "srchNcs1": "02"
    }),
    # 2. 파라미터 변형 (srchTraProcess, srchTraArea1 등 필수 파라미터 포함 여부)
    ("HRD-Net KMBC with full params", "http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp", kmbc_key, {
        "authKey": kmbc_key, "returnType": "XML", "outType": "1", "pageNum": "1", "pageSize": "2",
        "srchTraProcess": "", "srchTraArea1": "", "srchNcs1": "02", "srchTraGbn": "M1001", "srchTraType": "1"
    }),
    # 3. 고용24 직업훈련포털 통합 API
    ("HRD-Net Worknet OpenApi", "http://openapi.work.go.kr/opi/opi/opia/korSearchApi.do", kmbc_key, {
        "authKey": kmbc_key, "returnType": "XML", "startPage": "1", "display": "2"
    })
]

print("Testing HRD-Net API Endpoints...")
for label, url, key, params in candidates:
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10, allow_redirects=True)
        print(f"\n[{res.status_code}] {label} (Final URL: {res.url[:80]}...)")
        if res.text.strip().startswith("<?xml") or "<HRDNet>" in res.text:
            print("  -> SUCCESS: Valid XML response received!")
            parsed = xmltodict.parse(res.text)
            print(f"  -> XML Root: {list(parsed.keys())}")
            if "HRDNet" in parsed:
                cnt = parsed["HRDNet"].get("scn_cnt")
                print(f"  -> Total Count: {cnt}")
        elif "<html" in res.text.lower():
            print("  -> WARNING: HTML redirection received (Not API XML). Size:", len(res.text))
        else:
            print("  -> Snippet:", res.text[:200])
    except Exception as e:
        print(f"  -> Error: {e}")
