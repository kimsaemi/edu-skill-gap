"""
인사·총무(HR) 295개 교육과정 심화 상세 커리큘럼 웹 크롤러 (파일럿 테스트)
"""
import os
import sys
import time
import json
import requests
import xmltodict
from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_work24_detail_page(url):
    """고용24 상세 웹페이지에서 4대 핵심 항목 파싱"""
    res = {
        "overview": "",
        "syllabus": [],
        "learning_objectives": "",
        "target_audience": ""
    }
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return res
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 1. 훈련목표 (learning_objectives)
        for el in soup.find_all(["th", "dt", "strong", "h3", "h4"]):
            txt = el.get_text(strip=True)
            if "훈련목표" in txt:
                parent = el.find_parent(["tr", "dl", "div", "section"])
                if parent:
                    # '훈련목표' 단어 제거 후 본문 추출
                    p_txt = parent.get_text(strip=True).replace("훈련목표", "").strip()
                    res["learning_objectives"] = p_txt
                    break
                    
        # 2. 훈련과정 개요 (overview)
        for el in soup.find_all(["th", "dt", "strong", "h3", "h4"]):
            txt = el.get_text(strip=True)
            if any(k in txt for k in ["훈련과정의 장점", "추진배경", "훈련과정 개요"]):
                parent = el.find_parent(["tr", "dl", "div", "section"])
                if parent:
                    p_txt = parent.get_text(" ", strip=True)
                    res["overview"] = p_txt
                    break
        if not res["overview"] and res["learning_objectives"]:
            res["overview"] = res["learning_objectives"]

        # 3. 추천 수강 대상 (target_audience)
        audience_parts = []
        for el in soup.find_all(["th", "dt"]):
            txt = el.get_text(strip=True)
            if any(k in txt for k in ["선수학습", "직무경력", "기취득자격", "훈련대상"]):
                parent = el.find_parent(["tr", "dl"])
                if parent:
                    val = parent.get_text(" ", strip=True)
                    audience_parts.append(val)
        res["target_audience"] = " | ".join(audience_parts) if audience_parts else "신입/주니어 실무자 및 직무 전직 희망자"

        # 4. 세부 커리큘럼 (syllabus - NCS능력단위 및 교과목 목록)
        units = []
        for tbl in soup.find_all("table"):
            tbl_txt = tbl.get_text()
            if "NCS능력단위" in tbl_txt or "교과목" in tbl_txt:
                for tr in tbl.find_all("tr"):
                    cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(cols) >= 3 and cols[1] not in ["-", "NCS능력단위(요소)"]:
                        unit_name = cols[2] if len(cols) > 3 and cols[2] != "-" else cols[1]
                        hours = cols[-1] if "시간" in cols[-1] else ""
                        if unit_name and unit_name != "-":
                            units.append(f"{unit_name} ({hours})" if hours else unit_name)
        res["syllabus"] = units
    except Exception as e:
        print(f"Error parsing work24 detail: {e}")
    return res

if __name__ == "__main__":
    test_url = "https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20230000454583&tracseTme=3&crseTracseSe=C0061&trainstCstmrId=500020019063"
    print("Testing parser on 1 sample Work24 course...")
    data = parse_work24_detail_page(test_url)
    print("\n[Parsed Objectives]:", data["learning_objectives"])
    print("\n[Parsed Overview]:", data["overview"][:200])
    print("\n[Parsed Audience]:", data["target_audience"])
    print("\n[Parsed Syllabus]:", data["syllabus"])
