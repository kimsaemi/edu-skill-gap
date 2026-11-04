# -*- coding: utf-8 -*-
"""
최신 리랭커 추천(task_course_recommendations_90_reranked.csv)을 반영하여
hr_career_platform_v2_2026-11-04.html 을 생성하고, 이전 2026-11-02.html은 archive/로 이동한다.
"""

import json
import re
import shutil
import sys
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.course_links import detail_url  # noqa: E402

OLD_HTML = ROOT / "hr_career_platform_v2_2026-11-02.html"
NEW_HTML = ROOT / "hr_career_platform_v2_2026-11-04.html"
ARCHIVE_DIR = ROOT / "archive"
RERANK_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
CLEANED_PARQUET = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"


def main():
    if not OLD_HTML.exists():
        if NEW_HTML.exists():
            print("NEW_HTML already exists and OLD_HTML does not.")
            return
        raise FileNotFoundError(f"{OLD_HTML} not found.")

    text = OLD_HTML.read_text(encoding="utf-8")
    m = re.search(r"const DATA = ", text)
    if not m:
        raise ValueError("Could not find const DATA = in HTML")
    data_start = m.end()
    data, end_idx = json.JSONDecoder().raw_decode(text[data_start:])

    df_rerank = pd.read_csv(RERANK_CSV)
    df_cleaned = pd.read_parquet(CLEANED_PARQUET)
    cleaned_by_uid = df_cleaned.set_index("course_uid").to_dict(orient="index")

    c_dict = {c["id"]: c for c in data["courses"]}

    def to_dashboard_id(uid):
        uid = str(uid)
        m = re.match(r"^PUB_([A-Z0-9]+)_\d+$", uid)
        if m and m.group(1) in c_dict:
            return m.group(1)
        if uid in c_dict:
            return uid
        if uid.startswith("PUB_"):
            sub = uid[4:]
            if sub in c_dict:
                return sub
            sub2 = re.sub(r"_\d+$", "", sub)
            if sub2 in c_dict:
                return sub2
        return uid

    # 1. Add any missing courses from df_rerank to data['courses']
    missing_uids = []
    for uid in df_rerank["course_uid"].unique():
        did = to_dashboard_id(uid)
        if did not in c_dict:
            missing_uids.append(uid)

    print(f"Missing courses to add: {len(missing_uids)} -> {missing_uids}")
    for uid in missing_uids:
        meta = cleaned_by_uid.get(uid, {})
        title = meta.get("title", uid)
        provider = meta.get("provider", "GSEEK")
        url = detail_url(meta.get("url", ""))
        # Create minimal course entry matching dashboard schema
        new_course = {
            "id": uid,
            "t": title,
            "inst": "경기도 GSEEK" if provider == "GSEEK" else provider,
            "plat": provider,
            "url": url,
            "cat": "HR",
            "doms": [],
            "grades": [0, 1, 2],
            "f": "HR",
            "src": "integrated",
            "lv": 0,
            "ct": "free" if meta.get("price_type") == "무료" or meta.get("price", 0) == 0 else "paid",
        }
        data["courses"].append(new_course)
        c_dict[uid] = new_course

    levels = ["입문", "실무", "관리자·심화"]

    # 2. Update task rec and rs
    updated_tasks = 0
    for dom in data["domains"]:
        dom_num = dom["id"].split("_")[1]
        for t in dom["tasks"]:
            t_num = t["id"].split("_")[-1]
            hr_tid = f"TASK_HR_D{dom_num}_{t_num}"

            new_rec = []
            new_rs = {}

            task_sub = df_rerank[df_rerank["task_id"] == hr_tid]
            for lvl_idx, lvl in enumerate(levels):
                lvl_sub = task_sub[task_sub["level"] == lvl].sort_values("rank")
                lvl_cids = []
                for _, r in lvl_sub.iterrows():
                    cid = to_dashboard_id(r["course_uid"])
                    lvl_cids.append(cid)
                    score = int(round(float(r["reranked_final_score"])))
                    if cid not in new_rs:
                        new_rs[cid] = [score, score, score]
                    new_rs[cid][lvl_idx] = score
                new_rec.append(lvl_cids)

            t["rec"] = new_rec
            t["rs"] = new_rs
            updated_tasks += 1

    print(f"Updated recommendations for {updated_tasks} tasks.")

    # 3. Serialize back into HTML
    for c in data["courses"]:  # GSEEK는 상세 페이지 링크로 (src/course_links.py)
        c["url"] = detail_url(c.get("url", ""))
    new_json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    new_html_content = text[:data_start] + new_json_str + text[data_start + end_idx:]

    NEW_HTML.write_text(new_html_content, encoding="utf-8")
    print(f"Created: {NEW_HTML.name} ({len(new_html_content)} bytes)")

    # 4. Move OLD_HTML to archive
    ARCHIVE_DIR.mkdir(exist_ok=True)
    dest_archive = ARCHIVE_DIR / OLD_HTML.name
    shutil.move(str(OLD_HTML), str(dest_archive))
    print(f"Archived: {OLD_HTML.name} -> {dest_archive}")


if __name__ == "__main__":
    main()
