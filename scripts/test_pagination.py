import requests
from bs4 import BeautifulSoup
import json
import sys
import time
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

all_courses = []
seen = set()

# Fetch across top popular pages 1 to 8
for page in range(1, 9):
    url = f"https://www.inflearn.com/courses?types=ONLINE&order=popular&page_number={page}"
    print(f"Fetching page {page}: {url} ...")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, 'html.parser')
        nd = soup.find('script', id='__NEXT_DATA__')
        if not nd:
            continue
        jd = json.loads(nd.string)
        queries = jd.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        p_count = 0
        for q in queries:
            data = q.get('state', {}).get('data', {})
            if isinstance(data, dict) and 'data' in data:
                items = data['data'].get('items', [])
                for item in items:
                    c = item.get('course', {})
                    cid = c.get('id')
                    if not cid or cid in seen:
                        continue
                    seen.add(cid)
                    instructor = item.get('instructor', {}) or {}
                    slug = c.get('slug', '')
                    title = (c.get('title') or '').strip()
                    if title:
                        all_courses.append({
                            'course_id': cid,
                            'title': title,
                            'instructor': (instructor.get('name') or '인프런 지식공유자').strip(),
                            'description': (c.get('description') or '').strip()[:180],
                            'slug': slug,
                            'url': f"https://www.inflearn.com/course/{slug}",
                            'thumbnail': c.get('thumbnailUrl', '')
                        })
                        p_count += 1
        print(f" -> Page {page}: {p_count} new courses (Total: {len(all_courses)})")
    except Exception as e:
        print(f"Error p{page}:", e)
    time.sleep(0.3)

df = pd.DataFrame(all_courses)
print(f"\nTotal Crawled Popular Inflearn Courses: {len(df)}")
if not df.empty:
    print(df[['course_id', 'title', 'instructor']].head(10))
