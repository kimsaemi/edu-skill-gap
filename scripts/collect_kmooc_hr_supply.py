"""
K-MOOC(공공데이터포털 B552881/kmooc_v2_0) 강좌 목록에서 인사 관련 무료 대학 강좌를 찾아,
우리 카탈로그 밖의 공급을 확인한다. 카탈로그에는 넣지 않는다(넣으려면 임베딩 모델이 필요).

- 전체 강좌 목록을 받아 제목 키워드로 인사 9개 영역과 추천 빈자리 업무에 대응시킨다.
- 수강 기간(study_end)이 오늘 이후인 강좌를 '지금 들을 수 있음'으로 본다.

필요: 환경 변수 DATA_GO_KR_API_KEY_DECODING (공공데이터포털에서 K-MOOC 활용 신청한 키)
출력
- data/hr/raw/kmooc/kmooc_courses_<날짜>.json.gz (gzip)
- data/hr/reports/kmooc_hr_supply.csv, kmooc_hr_supply.md
실행: python scripts/collect_kmooc_hr_supply.py
"""
import gzip
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
URL = "https://apis.data.go.kr/B552881/kmooc_v2_0/courseList_v2_0"
RAW_DIR = ROOT / "data" / "hr" / "raw" / "kmooc"
OUT_CSV = ROOT / "data" / "hr" / "reports" / "kmooc_hr_supply.csv"
OUT_MD = ROOT / "data" / "hr" / "reports" / "kmooc_hr_supply.md"
TODAY = date.today().isoformat()

# 인사 9개 영역 (제목 키워드). presentation 데이터의 DOMAIN_KEYWORDS와 같은 기준에 대학 강좌 표현을 조금 더함.
DOMAINS = {
    "인사전략·인력기획": r"인사전략|인력계획|인력운영|HR ?전략|인적자원관리|인적자원 관리|인사관리|HRM",
    "조직설계·직무분석": r"조직설계|직무분석|직무설계|조직구조|직무기술서|조직론",
    "인재채용": r"채용|면접관|인재선발",
    "온보딩·직원경험": r"온보딩|직원경험|조직사회화",
    "성과평가·목표관리": r"인사평가|성과평가|성과관리|KPI|OKR|목표관리|평가제도",
    "보상·급여·복리후생": r"급여|임금|보상|복리후생|연말정산|4대보험",
    "인재육성·사내교육": r"HRD|인적자원개발|교육훈련|기업교육|교수설계|평생교육방법|인재육성",
    "조직문화·사내소통": r"조직문화|조직개발|조직행동|조직심리|조직커뮤니케이션|구성원 몰입",
    "노사관계·노무": r"노무|노사관계|노사협의|노동법|근로기준|노동관계|노동조합|고용관계",
}
# 추천 빈자리 중 '공급 부족' 업무 (data/hr/reports/thin_task_supply.csv)
THIN_TASKS = {
    "직무기술서 갱신": r"직무기술서|직무분석",
    "평가자 편향 분석": r"평가자|평가 ?오류|인사평가",
    "성과급(PS/PI) 산정": r"성과급|인센티브|보상",
    "총인건비 예산": r"인건비",
    "정원·현원 관리": r"인력계획|인력운영|정원관리|인력 ?정원",
    "LMS 학습 데이터 분석": r"LMS|학습 ?분석|교육 ?데이터|러닝 ?애널리틱스",
    "HCVA 노동생산성": r"인적자본|노동생산성|HR ?애널리틱스|피플 ?애널리틱스",
    "채용 전략·채널": r"채용",
    "온보딩 설계": r"온보딩|조직사회화",
    "사내 소통 콘텐츠": r"조직커뮤니케이션|사내 ?커뮤니케이션|기업 ?커뮤니케이션",
}


def get_json(params, tries=4):
    key = os.getenv("DATA_GO_KR_API_KEY_DECODING")
    if not key:
        sys.exit("DATA_GO_KR_API_KEY_DECODING 환경 변수가 없습니다.")
    for i in range(tries):
        try:
            return requests.get(URL, params={"serviceKey": key, **params}, timeout=30).json()
        except Exception as e:  # 인증키가 담긴 주소가 찍히지 않도록 예외 이름만
            print(f"  (재시도 {i + 1}/{tries}: {type(e).__name__})")
            time.sleep(2 * (i + 1))
    return {}


def ts(v):
    try:
        return datetime.fromtimestamp(int(v)).date().isoformat()
    except (TypeError, ValueError):
        return ""


def main():
    raw = RAW_DIR / f"kmooc_courses_{TODAY.replace('-', '')}.json.gz"
    if raw.exists():  # 오늘 받은 원본이 있으면 다시 받지 않음
        items = json.loads(gzip.decompress(raw.read_bytes()).decode("utf-8"))
        total = len(items)
    else:
        first = get_json({"Page": 1, "Size": 100})
        total = int(first.get("totalCount") or first.get("header", {}).get("totalCount") or 0)
        items = list(first.get("items", []))
        for page in range(2, total // 100 + 2):
            items += get_json({"Page": page, "Size": 100}).get("items", [])
            time.sleep(0.1)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(gzip.compress(json.dumps(items, ensure_ascii=False).encode("utf-8")))
    print(f"K-MOOC 강좌 {len(items):,}개 (전체 {total:,})")

    df = pd.DataFrame(items).drop_duplicates("id")
    df["study_start"] = df["study_start"].map(ts)
    df["study_end"] = df["study_end"].map(ts)
    df["open_now"] = df["study_end"] >= TODAY
    df["domains"] = df["name"].map(lambda t: ", ".join(d for d, p in DOMAINS.items() if re.search(p, str(t))))
    df["thin_tasks"] = df["name"].map(lambda t: ", ".join(d for d, p in THIN_TASKS.items() if re.search(p, str(t))))
    hr = df[(df["domains"] != "") | (df["thin_tasks"] != "")].copy()
    hr[["id", "name", "org_name", "professor", "study_start", "study_end", "open_now", "rating", "domains", "thin_tasks", "url"]] \
        .sort_values(["open_now", "study_end"], ascending=[False, False]).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    def count(col, keys):
        rows = []
        for k in keys:
            m = hr[col].str.contains(re.escape(k))
            rows.append((k, int(m.sum()), int((m & hr["open_now"]).sum()), int(hr.loc[m, "name"].nunique())))
        return rows

    lines = [
        f"# K-MOOC 인사 관련 강좌 ({TODAY})",
        "",
        f"공공데이터포털 K-MOOC 강좌 목록 API로 전체 {len(df):,}개 강좌를 받아 제목 키워드로 찾았다. "
        f"인사 관련 강좌는 {len(hr)}개(서로 다른 제목 {hr['name'].nunique()}개)이고, 지금 수강 기간인 강좌는 {int(hr['open_now'].sum())}개다. "
        "K-MOOC는 무료 대학 강좌라 우리 카탈로그(기관 유료·국비 과정)를 보완할 수 있다. 카탈로그에는 아직 넣지 않았다.",
        "",
        "## 인사 9개 영역별",
        "",
        "| 영역 | 강좌 | 지금 수강 가능 | 서로 다른 제목 |",
        "| --- | ---: | ---: | ---: |",
    ] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in count("domains", DOMAINS)] + [
        "",
        "## 추천 빈자리 '공급 부족' 업무별",
        "",
        "| 업무 | 강좌 | 지금 수강 가능 | 서로 다른 제목 |",
        "| --- | ---: | ---: | ---: |",
    ] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in count("thin_tasks", THIN_TASKS)] + [
        "",
        "키워드가 넓은 업무(평가자 편향 → 인사평가, 성과급 → 보상)는 직접 다루지 않는 강좌도 포함된다. 강좌 목록은 kmooc_hr_supply.csv에 있다.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
