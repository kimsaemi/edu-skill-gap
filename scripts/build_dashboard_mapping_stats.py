"""
최신 대시보드(hr_career_platform_v2_*.html)의 업무-강좌 매핑 현황을 집계해 발표 데이터에 넣는다.
파일명: scripts/build_dashboard_mapping_stats.py

- 분야별 연결 강좌 수, 업무별 추천 강좌 수(적은 업무), 분야×카테고리에서 비어 있는 칸
- notebooks/eda_course_mapping_*.py 와 같은 기준이다.
- presentation/src/data.json 의 "dashboard_mapping" 키만 갱신한다. (다른 값은 건드리지 않는다)

사용법:
  python scripts/build_dashboard_mapping_stats.py
  python scripts/build_presentation.py
"""

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "presentation" / "src" / "data.json"
THIN_MAX = 6  # 서로 다른 추천 강좌가 이 값 이하면 '부족'


def latest_dashboard() -> Path:
    return sorted(ROOT.glob("hr_career_platform_v2_*.html"))[-1]


def dashboard_mapping() -> dict:
    path = latest_dashboard()
    text = path.read_text(encoding="utf-8")
    start = re.search(r"const DATA = ", text).end()
    data, _ = json.JSONDecoder().raw_decode(text[start:])
    courses, domains = data["courses"], data["domains"]
    dom_name = {d["id"]: d["short"] for d in domains}
    cats = data["cats"]

    per_domain = collections.Counter(dom_name[i] for c in courses for i in c["doms"] if i in dom_name)
    cross = collections.Counter((dom_name[i], c["cat"]) for c in courses for i in c["doms"] if i in dom_name)

    tasks = []
    for d in domains:
        for t in d["tasks"]:
            n = len({cid for lvl in t["rec"] for cid in lvl})
            tasks.append({"domain": d["short"], "label": t["name"], "n": n})
    tasks.sort(key=lambda x: x["n"])

    gaps = [
        {"domain": dn, "category": cats[ck]}
        for dn in dom_name.values() for ck in cats
        if cross.get((dn, ck), 0) == 0
    ]
    return {
        "source": path.name,
        "courses": len(courses),
        "domains": [{"label": k, "n": v} for k, v in sorted(per_domain.items(), key=lambda x: x[1])],
        "tasks_total": len(tasks),
        "thin_max": THIN_MAX,
        "thin_count": sum(1 for t in tasks if t["n"] <= THIN_MAX),
        "task_max": tasks[-1]["n"],
        "thinnest": tasks[:10],
        "empty_cells": gaps,
    }


def main():
    data = json.loads(OUT.read_text(encoding="utf-8"))
    data["dashboard_mapping"] = dashboard_mapping()
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    m = data["dashboard_mapping"]
    print(f"{m['source']}: 강좌 {m['courses']}, 부족 업무 {m['thin_count']}/{m['tasks_total']}, 빈 칸 {len(m['empty_cells'])}")


if __name__ == "__main__":
    main()
