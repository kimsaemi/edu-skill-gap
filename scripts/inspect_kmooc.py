import requests
import re

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.data.go.kr/data/15042355/openapi.do"
r = requests.get(url, headers=headers)
endpoints = re.findall(r'apis\.data\.go\.kr[^\s"\'<>]+', r.text)
print("Endpoints:", set(endpoints))
ops = re.findall(r'value="([^"]+)"', r.text)
print("Matching ops:", [o for o in ops if 'apis' in o or 'kmooc' in o.lower()])
