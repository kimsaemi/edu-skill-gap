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

WORK24_ENDPOINTS = {
    "국민내일배움카드 훈련과정": {
        "url": "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do",
        "key_env": "HRD_KMBC_API_KEY",
        "params": {
            "returnType": "XML",
            "outType": "1",
            "pageNum": "1",
            "pageSize": "3",
            "srchNcs1": "02"
        }
    },
    "사업주 훈련과정": {
        "url": "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do",
        "key_env": "HRD_EMPLOYER_TRAINING_API_KEY",
        "params": {
            "returnType": "XML",
            "outType": "1",
            "pageNum": "1",
            "pageSize": "3",
            "srchNcs1": "02"
        }
    },
    "일 병행 훈련과정": {
        "url": "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo313L01.do",
        "key_env": "HRD_WORK_STUDY_API_KEY",
        "params": {
            "returnType": "XML",
            "outType": "1",
            "pageNum": "1",
            "pageSize": "3",
            "srchNcs1": "02"
        }
    },
    "직무정보": {
        "url": "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo215L01.do",
        "key_env": "WORKNET_JOB_INFO_API_KEY",
        "params": {
            "returnType": "XML",
            "target": "jobInfo",
            "startPage": "1",
            "display": "3"
        }
    },
    "학과정보": {
        "url": "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo213L01.do",
        "key_env": "WORKNET_MAJOR_INFO_API_KEY",
        "params": {
            "returnType": "XML",
            "target": "majorInfo",
            "startPage": "1",
            "display": "3"
        }
    },
    "직업정보": {
        "url": "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo212L01.do",
        "key_env": "WORKNET_OCCUPATION_INFO_API_KEY",
        "params": {
            "returnType": "XML",
            "target": "jobList",
            "startPage": "1",
            "display": "3"
        }
    }
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("=================================================================")
print("  고용24(Work24) 신규 변경 Open API 엔드포인트 6종 전수 점검")
print("=================================================================\n")

results = []

for name, meta in WORK24_ENDPOINTS.items():
    url = meta["url"]
    key_env = meta["key_env"]
    api_key = os.getenv(key_env) or os.getenv("HRD_KMBC_API_KEY")
    
    print(f"[{name}]")
    print(f"  - 엔드포인트 URL: {url}")
    print(f"  - 인증키 환경변수: {key_env} (키 유무: {'O' if bool(api_key) else 'X'})")
    
    req_params = dict(meta["params"])
    if api_key:
        req_params["authKey"] = api_key
        
    try:
        res = requests.get(url, params=req_params, headers=headers, timeout=12)
        status = res.status_code
        content_len = len(res.content)
        content_type = res.headers.get("Content-Type", "")
        
        print(f"  - HTTP 상태코드: {status}")
        print(f"  - 응답 크기: {content_len:,} 바이트 | Content-Type: {content_type}")
        
        # XML 또는 JSON 파싱 시도
        is_success = False
        parsed_summary = ""
        total_items = "알수없음"
        
        try:
            if "xml" in content_type.lower() or res.text.strip().startswith("<"):
                parsed = xmltodict.parse(res.text)
                root_tag = list(parsed.keys())[0]
                
                # 에러 메시지 검사
                if "returnAuthMsg" in res.text or "error" in root_tag.lower():
                    parsed_summary = f"API 인증/요청 에러: {res.text.strip()[:200]}"
                elif "HRDNet" in root_tag:
                    hrd = parsed["HRDNet"]
                    total_items = hrd.get("scn_cnt", "0")
                    is_success = True
                    parsed_summary = f"HRDNet 정상 응답 (총 {total_items}건 조회됨)"
                elif "workApi" in root_tag:
                    wapi = parsed["workApi"]
                    total_items = wapi.get("total", "0")
                    is_success = True
                    parsed_summary = f"workApi 정상 응답 (총 {total_items}건 조회됨)"
                elif "wantedRoot" in root_tag:
                    wroot = parsed["wantedRoot"]
                    total_items = wroot.get("total", "0")
                    is_success = True
                    parsed_summary = f"wantedRoot 정상 응답 (총 {total_items}건 조회됨)"
                else:
                    parsed_summary = f"XML 루트: <{root_tag}> | {res.text[:150]}"
            else:
                parsed_summary = f"비XML 응답 (HTML/텍스트): {res.text[:150]}"
        except Exception as pe:
            parsed_summary = f"파싱 예외 ({pe}): {res.text[:150]}"
            
        print(f"  - 결과 분석: {parsed_summary}\n")
        results.append({
            "name": name,
            "url": url,
            "status": status,
            "is_success": is_success,
            "total_items": total_items,
            "summary": parsed_summary
        })
    except Exception as e:
        print(f"  - [호출 실패]: {e}\n")
        results.append({
            "name": name,
            "url": url,
            "status": "Exception",
            "is_success": False,
            "total_items": 0,
            "summary": str(e)
        })

print("=================================================================")
print("  점검 요약 보고서")
print("=================================================================")
for r in results:
    mark = "✅ 성공" if r["is_success"] else "⚠️ 확인필요"
    print(f"- {mark} | {r['name']} ({r['status']}): {r['summary']}")
