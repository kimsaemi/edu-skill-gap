import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Try calling with headers mimicking browser client
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.inflearn.com',
    'Referer': 'https://www.inflearn.com/courses',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin'
}

endpoints = [
    ("GET Search", "https://www.inflearn.com/client/api/v2/courses/search?keyword=파이썬&page_number=1&pageSize=10"),
    ("POST Search", "https://www.inflearn.com/client/api/v2/courses/search"),
    ("Main Categories", "https://www.inflearn.com/client/api/v1/category/main"),
    ("Sub Category 5", "https://www.inflearn.com/client/api/v1/category/5/sub-category")
]

for name, url in endpoints:
    print(f"\nTesting {name}: {url}")
    try:
        if name == "POST Search":
            r = requests.post(url, headers=headers, json={"keyword": "파이썬", "page_number": 1}, timeout=5)
        else:
            r = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print("Response:", json.dumps(d, ensure_ascii=False)[:300])
    except Exception as e:
        print("Error:", e)
