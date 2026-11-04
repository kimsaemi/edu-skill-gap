"""
이미 만든 결과물의 강좌 링크를 상세 페이지 링크로 고친다 (src/course_links.py의 detail_url).
원본 강좌 데이터(parquet)는 바꾸지 않는다. 여러 번 실행해도 결과가 같다.

- 최신 대시보드 hr_career_platform_v2_*.html 의 DATA.courses[].url
- 평가표 data/hr/output/recommendation/precision_eval_{round2,holdout}_items.csv 의 url 열
실행: python scripts/apply_detail_links.py
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.course_links import detail_url  # noqa: E402

RECO = ROOT / "data" / "hr" / "output" / "recommendation"


def fix_dashboard() -> None:
    path = sorted(ROOT.glob("hr_career_platform_v2_*.html"))[-1]
    text = path.read_text(encoding="utf-8")
    start = re.search(r"const DATA = ", text).end()
    data, length = json.JSONDecoder().raw_decode(text[start:])
    changed = 0
    for c in data["courses"]:
        new = detail_url(c.get("url", ""))
        changed += new != c.get("url", "")
        c["url"] = new
    path.write_text(text[:start] + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + text[start + length:],
                    encoding="utf-8")
    print(f"{path.name}: 링크 {changed}개 보정")


def fix_eval_items() -> None:
    for name in ("precision_eval_round2_items.csv", "precision_eval_holdout_items.csv"):
        path = RECO / name
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        new = df["url"].map(detail_url)
        changed = int((new != df["url"]).sum())
        df["url"] = new
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{name}: 링크 {changed}개 보정")


if __name__ == "__main__":
    fix_dashboard()
    fix_eval_items()
