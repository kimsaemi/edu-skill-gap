import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

for kw in ['파이썬', '스마트팩토리', '회계', '마케팅']:
    url = f"https://www.inflearn.com/courses?s={urllib.parse.quote(kw)}"
    res = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, 'html.parser')
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        jd = json.loads(next_data.string)
        queries = jd.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        for q in queries:
            qk = q.get('queryKey', [])
            if len(qk) > 1 and isinstance(qk[1], dict) and 's' in qk[1]:
                search_term = qk[1].get('s')
                items = q.get('state', {}).get('data', {}).get('data', {}).get('items', [])
                print(f"Key search term: '{search_term}' -> {len(items)} items")
                if items:
                    print(f"  First: {items[0].get('course', {}).get('title')}")
