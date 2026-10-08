import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

candidates = [
    "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo.do",
    "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcList.do",
    "https://www.work24.go.kr/wk/a/b/1200/retriveOpenApiList.do",
    "https://www.work24.go.kr/wk/openApi/callOpenApiSvcInfo.do",
    "https://www.hrd.go.kr/hrdp/co/hrcoc/Hrcoc0100L.do",
    "http://www.hrd.go.kr/hrdp/co/hrcoc/Hrcoc0100L.do"
]

for url in candidates:
    try:
        r = requests.get(url, headers=headers, timeout=5, allow_redirects=False)
        print(f"URL: {url} -> Status: {r.status_code}, Location: {r.headers.get('Location')}")
    except Exception as e:
        print(f"URL: {url} -> Error: {e}")
