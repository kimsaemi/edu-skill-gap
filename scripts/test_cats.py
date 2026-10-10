import requests
from bs4 import BeautifulSoup
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

cats = ['it-programming', 'data-science', 'artificial-intelligence', 'business-marketing', 'design']

for cat in cats:
    url = f"https://www.inflearn.com/courses/{cat}"
    res = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(res.text, 'html.parser')
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        jd = json.loads(next_data.string)
        queries = jd.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        print(f"\n--- Category: {cat} (Queries: {len(queries)}) ---")
        for q in queries:
            qk = q.get('queryKey', [])
            print("  Query Key:", qk[0] if qk else None)
            if len(qk) > 1 and isinstance(qk[1], dict):
                print("  Params:", qk[1])
            data = q.get('state', {}).get('data', {})
            if isinstance(data, dict):
                inner = data.get('data', {})
                if isinstance(inner, dict) and 'items' in inner:
                    print(f"  Found {len(inner['items'])} items!")
                    if inner['items']:
                        print("  First item:", inner['items'][0].get('course', {}).get('title'))
