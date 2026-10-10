import requests, re, sys

sys.stdout.reconfigure(encoding='utf-8')
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

res = requests.get('https://www.inflearn.com/course/클로드-코드-완벽-마스터-ai-개발', headers=headers)
from bs4 import BeautifulSoup
soup = BeautifulSoup(res.text, 'html.parser')
scripts = [s.get('src') for s in soup.find_all('script') if s.get('src')]

for src in scripts:
    if not src.startswith('http'):
        src = 'https://www.inflearn.com' + src
    try:
        js = requests.get(src, headers=headers, timeout=5).text
        if 'bestReviews' in js or 'reviewContent' in js or '/reviews' in js:
            # find surrounding code
            snippets = re.findall(r'.{0,80}(?:bestReviews|/reviews|reviewContent).{0,80}', js)
            print(f'=== In {src.split("/")[-1]} ===')
            for sn in snippets[:5]:
                print('...', sn.replace('\n', ' '), '...')
    except:
        pass
