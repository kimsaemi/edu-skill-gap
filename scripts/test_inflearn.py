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

def crawl_inflearn_keyword(keyword, max_pages=1):
    all_courses = []
    for page in range(1, max_pages + 1):
        url = f"https://www.inflearn.com/courses?s={keyword}&page_number={page}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                print(f"[{keyword}] Page {page} status {res.status_code}")
                continue
            soup = BeautifulSoup(res.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            if not next_data:
                continue
            jd = json.loads(next_data.string)
            dehydrated = jd.get('props', {}).get('pageProps', {}).get('dehydratedState', {})
            queries = dehydrated.get('queries', [])
            for q in queries:
                data = q.get('state', {}).get('data', {})
                if isinstance(data, dict) and 'data' in data:
                    inner = data['data']
                    if 'items' in inner:
                        for item in inner['items']:
                            c = item.get('course', {})
                            instructor = item.get('instructor', {}) or {}
                            price_info = item.get('price', {}) or {}
                            all_courses.append({
                                'search_keyword': keyword,
                                'course_id': c.get('id'),
                                'title': c.get('title'),
                                'instructor': instructor.get('name', ''),
                                'description': c.get('description', ''),
                                'slug': c.get('slug', ''),
                                'url': f"https://www.inflearn.com/course/{c.get('slug')}" if c.get('slug') else '',
                                'thumbnail': c.get('thumbnailUrl', ''),
                                'tags': " | ".join(item.get('tagTitles', [])),
                                'is_kdt': item.get('isKdt', False)
                            })
        except Exception as e:
            print(f"Error crawling {keyword} p{page}:", e)
        time.sleep(0.5)
    return all_courses

# Test keywords
keywords = ['데이터분석', '스마트팩토리', '전산회계', '디지털마케팅', 'B2B영업']
results = []
for kw in keywords:
    print(f"Crawling Inflearn for: {kw} ...")
    courses = crawl_inflearn_keyword(kw, max_pages=1)
    print(f" -> Found {len(courses)} courses for {kw}")
    results.extend(courses)

df_inf = pd.DataFrame(results)
print(f"\nTotal Crawled Courses: {len(df_inf)}")
print(df_inf[['search_keyword', 'title', 'instructor', 'tags']].head(10))
