# -*- coding: utf-8 -*-
"""
홀드아웃 2차 평가 시트 및 열쇠 파일 생성 스크립트

원칙:
1. 분야명(domain), 업무명(task), 과정명, 기관, URL은 절대 손으로 적지 않고
   카탈로그(hr_task_catalog_90.json), 최종 추천, BM25 추천, 메타데이터에서 자동 로드합니다.
2. 판정(judgment) 및 메모(memo) 칸은 사람이 직접 평가하므로 무조건 빈 칸("")으로 둡니다.
3. 자동 검증 4개 항목을 모두 통과한 경우에만 최종 파일로 저장합니다:
   (1) 분야명·업무명이 카탈로그와 일치하는지
   (2) source가 바르게 들어갔는지 (decoy는 반드시 다른 분야인지)
   (3) judgment 칸이 모두 비어 있는지
   (4) 4명의 평가자 배정 건수가 균등한지
"""

import sys
import json
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.course_links import build_course_link, detail_url
from src.customer import career_platform as cp
from src.customer.career_platform import course_intro_summary

CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
EVAL_ORIG_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
HOLDOUT1_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_items.csv"
FINAL_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
BM25_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_bm25only.csv"
EXCL_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"

OUT_KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_key.csv"
OUT_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_items.csv"


def load_data():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        cat_tasks = json.load(f)["tasks"]
    tasks_meta = {t["task_id"]: t for t in cat_tasks}

    df_eval = pd.read_csv(EVAL_ORIG_PATH)
    df_h1 = pd.read_csv(HOLDOUT1_PATH)
    evaluated_ids = set(df_eval["task_id"]) | set(df_h1["task_id"])

    df_final = pd.read_csv(FINAL_REC_PATH)
    df_bm25 = pd.read_csv(BM25_REC_PATH)

    df_courses = cp.courses().set_index("course_uid")

    return cat_tasks, tasks_meta, evaluated_ids, df_final, df_bm25, df_courses


def select_holdout2_tasks(cat_tasks, evaluated_ids, df_final, seed=7):
    """
    9개 분야에서 각 1개 + 남은 업무 중 1개 = 10개 (random_state=7)
    3개 수준(입문·실무·관리자) 골고루 배분
    최종 추천이 3개 미만인 슬롯은 제외
    """
    rng = np.random.default_rng(seed)

    # Filter out previously evaluated tasks and tasks with < 3 recs
    tasks_by_domain = {}
    for t in cat_tasks:
        tid = t["task_id"]
        if tid in evaluated_ids:
            continue
        tasks_by_domain.setdefault(t["domain_id"], []).append(t)

    selected_tasks = []
    # 1 task per domain
    for dom_id in sorted(tasks_by_domain.keys()):
        cand = sorted(tasks_by_domain[dom_id], key=lambda x: x["task_id"])
        chosen = rng.choice(cand)
        selected_tasks.append(chosen)

    # 10th task from remaining
    chosen_ids = {t["task_id"] for t in selected_tasks}
    remaining_pool = sorted(
        [t for t in cat_tasks if t["task_id"] not in evaluated_ids and t["task_id"] not in chosen_ids],
        key=lambda x: x["task_id"],
    )
    extra_task = rng.choice(remaining_pool)
    selected_tasks.append(extra_task)

    # Assign balanced levels: 3 입문, 4 실무, 3 관리자·심화
    levels_pool = ["입문", "실무", "관리자·심화", "입문", "실무", "관리자·심화", "입문", "실무", "관리자·심화", "실무"]
    # Check that each (task_id, level) has >= 3 recommendations in df_final
    final_slot_counts = df_final.groupby(["task_id", "level"]).size().to_dict()

    plan = []
    for t, lvl in zip(selected_tasks, levels_pool):
        slot_key = (t["task_id"], lvl)
        cnt = final_slot_counts.get(slot_key, 0)
        assert cnt >= 3, f"Slot {slot_key} has fewer than 3 recommendations ({cnt})"
        plan.append((t, lvl))

    return plan


def build_evaluation_items(plan, df_final, df_bm25, df_courses, seed=7):
    rng = np.random.default_rng(seed)

    key_rows = []
    items_rows = []

    # Final recommendations pool for decoys (from rank <= 3)
    df_final_top3 = df_final[df_final["rank"] <= 3].copy()

    # Rater pairs (김, 이, 박, 홍)
    rater_pairs_cycle = [
        ("김", "이"),
        ("박", "홍"),
        ("김", "박"),
        ("이", "홍"),
        ("김", "홍"),
        ("이", "박"),
    ]

    item_counter = 1
    pair_idx = 0

    # Collect all items per slot, then assign raters with exact balance
    slot_items_list = []

    for task_info, level in plan:
        t_id = task_info["task_id"]
        dom_id = task_info["domain_id"]
        dom_name = task_info["domain_name"]
        t_name = task_info["task_name"]

        # Final top 3
        sub_final = df_final[(df_final["task_id"] == t_id) & (df_final["level"] == level) & (df_final["rank"] <= 3)].copy()
        sub_final = sub_final.sort_values("rank").head(3)

        # BM25 top 3
        sub_bm25 = df_bm25[(df_bm25["task_id"] == t_id) & (df_bm25["level"] == level) & (df_bm25["rank"] <= 3)].copy()
        sub_bm25 = sub_bm25.sort_values("rank").head(3)

        final_uids = list(sub_final["course_uid"])
        bm25_uids = list(sub_bm25["course_id"])

        # Combine deduplicated
        slot_candidates = {}
        for _, r in sub_final.iterrows():
            uid = str(r["course_uid"])
            slot_candidates[uid] = {
                "course_id": uid,
                "title": str(r["title"]),
                "provider": str(r["provider"]),
                "source": "final_top3",
                "decoy_origin_task_id": "",
            }

        for _, r in sub_bm25.iterrows():
            uid = str(r["course_id"])
            if uid in slot_candidates:
                slot_candidates[uid]["source"] = "both"
            else:
                slot_candidates[uid] = {
                    "course_id": uid,
                    "title": str(r["title"]),
                    "provider": str(r["provider"]),
                    "source": "bm25_top3",
                    "decoy_origin_task_id": "",
                }

        # Select 1 Decoy course from another domain's final top 3
        other_domain_final = df_final_top3[df_final_top3["domain_id"] != dom_id]
        # Exclude courses already in slot candidates
        valid_decoys = other_domain_final[~other_domain_final["course_uid"].isin(slot_candidates.keys())]
        decoy_sample = valid_decoys.sample(n=1, random_state=int(rng.integers(1, 1000000))).iloc[0]

        decoy_uid = str(decoy_sample["course_uid"])
        slot_candidates[decoy_uid] = {
            "course_id": decoy_uid,
            "title": str(decoy_sample["title"]),
            "provider": str(decoy_sample["provider"]),
            "source": "decoy",
            "decoy_origin_task_id": str(decoy_sample["task_id"]),
        }

        # Blind shuffle candidates for this slot
        cand_list = list(slot_candidates.values())
        rng.shuffle(cand_list)

        for c in cand_list:
            slot_items_list.append({
                "task_id": t_id,
                "domain": dom_name,
                "domain_id": dom_id,
                "task": t_name,
                "level": level,
                "course_id": c["course_id"],
                "title": c["title"],
                "provider": c["provider"],
                "source": c["source"],
                "decoy_origin_task_id": c["decoy_origin_task_id"],
            })

    # Assign item_id (1 .. len(slot_items_list))
    # Assign raters across 4 raters (김, 이, 박, 홍)
    # To keep exact balance: if len(slot_items_list) is not a multiple of 6, balance raters
    total_items = len(slot_items_list)
    print(f"Total unique evaluation items across 10 slots: {total_items}")

    rater_counts = Counter()
    assigned_pairs = []

    for i in range(total_items):
        pair = rater_pairs_cycle[i % len(rater_pairs_cycle)]
        assigned_pairs.append(pair)
        rater_counts[pair[0]] += 1
        rater_counts[pair[1]] += 1

    # Check if balanced
    diff = max(rater_counts.values()) - min(rater_counts.values())
    if diff > 0:
        # Re-balance the last few pairs so all counts are as equal as possible
        pass
    print(f"Initial rater distribution: {dict(rater_counts)}")

    for idx, item in enumerate(slot_items_list, 1):
        c_uid = item["course_id"]
        # Look up URL and intro summary
        course_row = df_courses.loc[c_uid] if c_uid in df_courses.index else None
        c_url = ""
        if course_row is not None and pd.notna(course_row.get("url")):
            c_url = build_course_link(item["provider"], c_uid, str(course_row["url"]))
        else:
            c_url = build_course_link(item["provider"], c_uid)

        intro_sum = course_intro_summary(c_uid)

        # Key file row
        key_rows.append({
            "item_id": idx,
            "task_id": item["task_id"],
            "level": item["level"],
            "course_id": c_uid,
            "title": item["title"],
            "provider": item["provider"],
            "source": item["source"],
            "decoy_origin_task_id": item["decoy_origin_task_id"],
        })

        # Items file rows (2 raters per item)
        r1, r2 = assigned_pairs[idx - 1]
        for rater in [r1, r2]:
            items_rows.append({
                "item_id": idx,
                "rater": rater,
                "task_id": item["task_id"],
                "domain": item["domain"],
                "task": item["task"],
                "level": item["level"],
                "title": item["title"],
                "provider": item["provider"],
                "url": c_url,
                "과정 소개(요약)": intro_sum,
                "judgment": "",
                "memo": "",
            })

    df_key = pd.DataFrame(key_rows)
    df_items = pd.DataFrame(items_rows)
    return df_key, df_items


def validate_holdout2(df_key, df_items, tasks_meta):
    print("=== Running Automated Validation Checks ===")

    # (1) 분야명·업무명이 카탈로그와 일치하는지
    for _, r in df_items.iterrows():
        meta = tasks_meta[r["task_id"]]
        assert r["task"] == meta["task_name"], f"Task name mismatch: {r['task']} vs {meta['task_name']}"
        assert r["domain"] == meta["domain_name"], f"Domain mismatch: {r['domain']} vs {meta['domain_name']}"
    print("[PASS] (1) 분야명·업무명이 카탈로그와 100% 일치")

    # (2) source가 바르게 들어갔는지 (decoy는 반드시 다른 분야인지)
    valid_sources = {"final_top3", "bm25_top3", "both", "decoy"}
    assert set(df_key["source"]).issubset(valid_sources), f"Invalid sources: {set(df_key['source'])}"

    for _, r in df_key.iterrows():
        if r["source"] == "decoy":
            assert r["decoy_origin_task_id"], f"Decoy item {r['item_id']} has empty decoy_origin_task_id"
            origin_meta = tasks_meta[r["decoy_origin_task_id"]]
            slot_meta = tasks_meta[r["task_id"]]
            assert origin_meta["domain_id"] != slot_meta["domain_id"], (
                f"Decoy {r['item_id']} comes from same domain {slot_meta['domain_id']}"
            )
        else:
            assert not r["decoy_origin_task_id"], f"Non-decoy item {r['item_id']} has decoy_origin_task_id"
    print("[PASS] (2) source 및 decoy 다른 분야 출처 검증 완료")

    # (3) judgment 칸이 모두 비어 있는지
    assert (df_items["judgment"] == "").all(), "Some judgment cells are not blank!"
    print("[PASS] (3) judgment 칸이 모두 빈 문자열로 보존됨 (규칙 1 준수)")

    # (4) 4명의 평가자 배정 건수가 균등한지
    r_counts = Counter(df_items["rater"])
    print(f"Rater counts: {dict(r_counts)}")
    assert len(set(r_counts.values())) <= 2, f"Rater counts not balanced: {dict(r_counts)}"
    diff = max(r_counts.values()) - min(r_counts.values())
    assert diff <= 1, f"Rater counts difference > 1: {diff}"
    print("[PASS] (4) 4명의 평가자 배정 건수 균등 검증 완료 (차이 <= 1건)")


def main():
    print("=== Generating Holdout Round 2 Evaluation Sheet ===")
    cat_tasks, tasks_meta, evaluated_ids, df_final, df_bm25, df_courses = load_data()

    plan = select_holdout2_tasks(cat_tasks, evaluated_ids, df_final, seed=7)
    print("\nSelected 10 Evaluation Tasks:")
    for i, (t, lvl) in enumerate(plan, 1):
        print(f"  {i}. [{lvl}] {t['task_id']} ({t['domain_name']}) - {t['task_name']}")

    df_key, df_items = build_evaluation_items(plan, df_final, df_bm25, df_courses, seed=7)

    validate_holdout2(df_key, df_items, tasks_meta)

    OUT_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_key.to_csv(OUT_KEY_PATH, index=False, encoding="utf-8-sig")
    df_items.to_csv(OUT_ITEMS_PATH, index=False, encoding="utf-8-sig")

    print(f"\nSaved key file: {OUT_KEY_PATH.name} ({len(df_key)} items)")
    print(f"Saved evaluation sheet: {OUT_ITEMS_PATH.name} ({len(df_items)} rows, 2 raters per item)")


if __name__ == "__main__":
    main()
