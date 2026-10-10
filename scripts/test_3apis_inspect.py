"""
API 실제 응답 점검 스크립트 (인증키 절대 미출력)
대상:
1. 국민내일배움카드 훈련과정 (HRD-Net)
2. 사업주훈련 훈련과정 (HRD-Net)
3. 한국산업인력공단 NCS 교육과정 (공공데이터포털)
"""
import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

def mask_key(k):
    if not k:
        return "None"
    return k[:4] + "****" + k[-4:] if len(k) > 8 else "****"

print("="*60)
print("1. 고용24 (HRD-Net) 국민내일배움카드 훈련과정 API 점검")
print("="*60)
kmbc_key = os.getenv("HRD_KMBC_API_KEY")
print(f"Key loaded: {mask_key(kmbc_key)} (len: {len(kmbc_key) if kmbc_key else 0})")

# HRD-Net 훈련과정 기본 엔드포인트 후보들
# 기존 코드: http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp
# 파라미터 확인: authKey, returnType, outType, pageNum, pageSize, srchTraStDt, srchTraEndDt, sort, sortCol 등
# 고용24 HRD-Net API는 대개 srchTraStDt, srchTraEndDt 필수 요구 여부 확인 필요
hrd_endpoints = [
    "http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp",
    "https://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp",
    "http://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo.do"
]

params_kmbc_default = {
    "authKey": kmbc_key,
    "returnType": "XML",
    "outType": "1",
    "pageNum": "1",
    "pageSize": "10",
    "srchTraStDt": "20240101",
    "srchTraEndDt": "20241231",
    "sort": "DESC",
    "sortCol": "TR_ST_DT"
}

for ep in hrd_endpoints[:1]:
    try:
        res = requests.get(ep, params=params_kmbc_default, timeout=10)
        print(f"Endpoint: {ep}")
        print(f"Status Code: {res.status_code}")
        print(f"Response Headers Content-Type: {res.headers.get('Content-Type')}")
        print(f"Response Snippet (first 400 chars):\n{res.text[:400]}")
        
        # XML 구조 파싱 시도
        try:
            root = ET.fromstring(res.text)
            print(f"Root tag: {root.tag}")
            for child in list(root)[:5]:
                print(f" - Child tag: {child.tag}, text preview: {str(child.text)[:50]}")
            # scn_list or item 찾기
            items = root.findall(".//scn_list") or root.findall(".//item") or root.findall(".//srchList")
            print(f"Found items count: {len(items)}")
            if items:
                print("First item field tags:")
                for elem in items[0]:
                    print(f"   <{elem.tag}>: {str(elem.text)[:60]}")
        except Exception as e_xml:
            print(f"XML Parse error: {e_xml}")
    except Exception as e:
        print(f"Request error: {e}")

print("\n" + "="*60)
print("2. 고용24 (HRD-Net) 사업주훈련 훈련과정 API 점검")
print("="*60)
employer_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY")
print(f"Key loaded: {mask_key(employer_key)} (len: {len(employer_key) if employer_key else 0})")

# 사업주훈련 엔드포인트: HRDPOA60_2.jsp 인지 확인 필요 (HRDPOA60_1은 구직자/내일배움, HRDPOA60_2는 근로자/사업주 등인지)
employer_endpoints = [
    "http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_2.jsp",
    "http://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp"
]

params_emp_default = {
    "authKey": employer_key,
    "returnType": "XML",
    "outType": "1",
    "pageNum": "1",
    "pageSize": "10",
    "srchTraStDt": "20240101",
    "srchTraEndDt": "20241231",
    "sort": "DESC",
    "sortCol": "TR_ST_DT"
}

for ep in employer_endpoints:
    try:
        res = requests.get(ep, params=params_emp_default, timeout=10)
        print(f"\nEndpoint: {ep}")
        print(f"Status Code: {res.status_code}")
        print(f"Response Snippet (first 300 chars):\n{res.text[:300]}")
        try:
            root = ET.fromstring(res.text)
            print(f"Root tag: {root.tag}")
            items = root.findall(".//scn_list") or root.findall(".//item") or root.findall(".//srchList")
            print(f"Found items count: {len(items)}")
            if items:
                print("First item field tags:")
                for elem in items[0]:
                    print(f"   <{elem.tag}>: {str(elem.text)[:60]}")
        except Exception as e_xml:
            print(f"XML parse snippet error: {e_xml}")
    except Exception as e:
        print(f"Request error: {e}")

print("\n" + "="*60)
print("3. 한국산업인력공단 NCS 교육과정 API 점검")
print("="*60)
ncs_key_dec = os.getenv("NCS_COURSE_API_KEY_DECODING") or os.getenv("DATA_GO_KR_API_KEY_DECODING")
ncs_key_enc = os.getenv("NCS_COURSE_API_KEY") or os.getenv("DATA_GO_KR_API_KEY_ENCODING")
print(f"Key Dec loaded: {mask_key(ncs_key_dec)}")
print(f"Key Enc loaded: {mask_key(ncs_key_enc)}")

ncs_url = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
# params test
for key_name, k_val in [("decoding", ncs_key_dec), ("encoding", ncs_key_enc)]:
    try:
        p = {"serviceKey": k_val, "pageNo": 1, "numOfRows": 5}
        res = requests.get(ncs_url, params=p, timeout=10)
        print(f"\nCalling NCS with {key_name} key in params:")
        print(f"Status Code: {res.status_code}")
        print(f"Response text snippet:\n{res.text[:300]}")
    except Exception as e:
        print(f"NCS error: {e}")
