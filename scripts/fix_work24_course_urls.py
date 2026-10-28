"""
확정 과정 데이터의 고용24 과정 링크를 과정별 상세 페이지 주소로 고친다.

문제: 고용24 과정 96건의 course_url이 모두 홈페이지 주소(https://www.work24.go.kr)뿐이었다.
해결: 고용24 API 원본 응답의 titleLink(과정·회차별 상세 페이지)를 course_id(PUB_<trprId>_<회차>)로 찾아 넣는다.
      원본에서 찾지 못하면 기존 값을 그대로 둔다. 여러 번 실행해도 결과가 같다.

실행: python scripts/fix_work24_course_urls.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_FILES = [
    "data/hr/raw/kmbc_courses_raw.json",
    "data/hr/raw/employer_courses_raw.json",
    "data/hr/raw/round2/kmbc_round2_raw.json",
    "data/hr/raw/round2/employer_round2_raw.json",
]
TARGETS = {
    "data/hr/output/integration/hr_integrated_verified.csv": "global_course_key",
    "data/hr/output/integration/hr_integrated_candidates.csv": "global_course_key",
    "data/hr/output/recommendation/hr_recommendation_candidates.csv": "course_id",
}


def load_links():
    links = {}
    for f in RAW_FILES:
        for it in json.loads((ROOT / f).read_text(encoding="utf-8")):
            if it.get("titleLink"):
                links[f"PUB_{it['trprId']}_{it['trprDegr']}"] = it["titleLink"]
    return links


def main():
    links = load_links()
    for rel, key_col in TARGETS.items():
        path = ROOT / rel
        df = pd.read_csv(path, dtype=str)
        new = df[key_col].map(links)
        changed = new.notna() & (new != df["course_url"])
        df.loc[new.notna(), "course_url"] = new[new.notna()]
        df.to_csv(path, index=False, encoding="utf-8-sig")
        generic = (df["course_url"] == "https://www.work24.go.kr").sum()
        print(f"[정정] {rel}: {changed.sum()}건 링크 수정, 홈페이지 주소로 남은 행 {generic}건")


if __name__ == "__main__":
    main()
