import urllib.parse
import requests
from bs4 import BeautifulSoup
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

for kw in ['파이썬', '스마트팩토리', '전산회계', '마케팅']:
    encoded = urllib.parse.quote(kw)
    url = f"https://www.inflearn.com/courses?s={encoded}"
    res = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, 'html.parser')
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        jd = json.loads(next_data.string)
        dehydrated = jd.get('props', {}).get('pageProps', {}).get('dehydratedState', {})
        for q in dehydrated.get('queries', []):
            data = q.get('state', {}).get('data', {})
            if isinstance(data, dict) and 'data' in data:
                items = data['data'].get('items', [])
                print(f"[{kw}] URL-encoded query -> Found {len(items)} courses!")
                if items:
                    print(f"  Sample: {items[0].get('course', {}).get('title')}")
