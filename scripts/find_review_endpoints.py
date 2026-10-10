import sys
import requests
import re
from bs4 import BeautifulSoup
import json

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

res = requests.get('https://www.inflearn.com/course/operating-system-sto', headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')
scripts = [s.get('src') for s in soup.find_all('script') if s.get('src')]

print('Total scripts:', len(scripts))
found_endpoints = set()

for src in scripts:
    if not src.startswith('http'):
        src = 'https://www.inflearn.com' + src
    try:
        js = requests.get(src, headers=headers, timeout=5).text
        # Look for API paths with review
        apis = re.findall(r'/(?:client/)?api/v\d+/[a-zA-Z0-9_\-\$/]+', js)
        for api in apis:
            if 'review' in api.lower() or 'course' in api.lower():
                found_endpoints.add(api)
    except Exception as e:
        pass

for ep in sorted(found_endpoints):
    print('Discovered API pattern:', ep)
