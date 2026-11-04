"""
최신 대시보드(hr_career_platform_v2_*.html)의 업무-강좌 매핑 현황을 집계해 발표 데이터에 넣는다.
파일명: scripts/build_dashboard_mapping_stats.py

- 분야별 연결 강좌 수, 업무×수준 슬롯별 추천 강좌 수(3개 미만 부족 슬롯), 분야×카테고리에서 비어 있는 칸
- presentation/src/data.json 의 "dashboard_mapping" 키만 갱신한다. (다른 값은 건드리지 않는다)

사용법:
  python scripts/build_dashboard_mapping_stats.py
  python scripts/build_presentation.py
"""

import collections
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "presentation" / "src" / "data.json"
SLOT_MIN = 3  # 리랭커 정상 슬롯의 목표 추천 수 (Top 3)
LEVELS = ["입문", "실무", "관리자·심화"]


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

    slots_total = 0
    thin_slot_list = []
    thin_tasks_set = set()
    tasks_count = 0

    for d in domains:
        for t in d["tasks"]:
            tasks_count += 1
            t_id = t["id"]
            rec = t.get("rec", [])
            for lvl_idx, lvl_name in enumerate(LEVELS):
                slots_total += 1
                lvl_recs = rec[lvl_idx] if lvl_idx < len(rec) else []
                n = len(lvl_recs)
                if n < SLOT_MIN:
                    thin_slot_list.append({
                        "domain": d["short"],
                        "task": t["name"],
                        "level": lvl_name,
                        "n": n,
                    })
                    thin_tasks_set.add(t_id)

    gaps = [
        {"domain": dn, "category": cats[ck]}
        for dn in dom_name.values() for ck in cats
        if cross.get((dn, ck), 0) == 0
    ]
    return {
        "source": path.name,
        "courses": len(courses),
        "domains": [{"label": k, "n": v} for k, v in sorted(per_domain.items(), key=lambda x: x[1])],
        "tasks_total": tasks_count,
        "slots_total": slots_total,
        "slot_min": SLOT_MIN,
        "thin_slots": len(thin_slot_list),
        "thin_slot_list": thin_slot_list,
        "thin_tasks": len(thin_tasks_set),
        "empty_cells": gaps,
    }


def main():
    data = json.loads(OUT.read_text(encoding="utf-8"))
    data["dashboard_mapping"] = dashboard_mapping()
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    m = data["dashboard_mapping"]
    print(f"{m['source']}: 강좌 {m['courses']}, 부족 슬롯 {m['thin_slots']}/{m['slots_total']} (업무 {m['thin_tasks']}개), 빈 칸 {len(m['empty_cells'])}")


if __name__ == "__main__":
    main()
