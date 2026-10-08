import os
import requests
import re
import json

os.makedirs('data/api_docs', exist_ok=True)

# 1. data.go.kr NCS API 상세 테이블 파싱
url = 'https://www.data.go.kr/data/15086418/openapi.do'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
res = requests.get(url, headers=headers)

rows = re.findall(r'<tr[^>]*>(.*?)</tr>', res.text, re.DOTALL)
param_info = []
for r in rows:
    tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.DOTALL)
    if tds:
        clean_tds = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
        param_info.append(clean_tds)

with open('data/api_docs/ncs_api_doc_table.json', 'w', encoding='utf-8') as f:
    json.dump(param_info, f, ensure_ascii=False, indent=2)

print("Saved NCS API doc table to data/api_docs/ncs_api_doc_table.json")
for row in param_info[:25]:
    if len(row) >= 3:
        print(" | ".join(row[:4]))
