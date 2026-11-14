# -*- coding: utf-8 -*-
"""
홀드아웃 3차 사람 블라인드 평가 시트 및 정답 키 파일 생성 스크립트
파일명: scripts/make_holdout3_eval_sheet.py

목적:
1. 1차·2차·홀드아웃 1차·홀드아웃 2차에서 한 번도 평가되지 않은 60개 업무 중 10개 업무를 엄선.
   - 9개 직무 분야를 고르게 포함 (DOM_01~DOM_09 각 1개 + 추가 1개 = 10개)
   - 3개 수준(입문 3개, 실무 4개, 관리자·심화 3개)을 균형 있게 배정
   - 기본 추천(Baseline) vs 개선안(Candidate) Top 3가 다른 업무를 최우선 선정
   - 시드 고정(seed=42)으로 재현성 보장
2. 기존 최종 추천(Baseline) Top 3 vs 개선안(Candidate) Top 3의 합집합 구성 (중복 과정은 'shared'로 단일화).
3. 업무마다 명백한 비인사 과정(IT·무역·제조·회계 등) 1개씩 위약(Decoy)으로 삽입 (총 10개).
4. 2인 평가 체계 구축 (김, 이, 박, 홍 4명 균등 배정, 항목당 2인 평가 -> 총 행수 = 항목수 * 2).
5. 블라인드 평가 시트(precision_eval_holdout3_items.csv)에는 출처를 일절 숨기고,
   정답 키(precision_eval_holdout3_key.csv)에만 baseline/candidate/shared/decoy 출처를 보관.
"""

import sys
import json
import re
from pathlib import Path
from itertools import cycle
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.course_links import detail_url

CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
EVAL_ORIG_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"
HOLDOUT1_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_items.csv"
HOLDOUT2_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_items.csv"

BASE_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
CAND_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_candidate.csv"
COURSES_PARQUET = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"

OUT_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_items.csv"
OUT_KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_key.csv"


def clean_summary_text(val):
    if pd.isna(val) or val is None:
        return ""
    t = re.sub(r"\s+", " ", str(val)).strip()
    return t[:200]


def get_course_intro_summary(row):
    for col in ["learning_goals", "course_intro", "curriculum"]:
        val = row.get(col)
        if pd.notna(val) and val is not None:
            text = clean_summary_text(val)
            if text:
                return text
    return "과정 상세 소개 정보 제공 예정"


def select_holdout3_tasks(cat_tasks, prev_evaluated_ids, df_base, df_cand, seed=42):
    """
    미평가 60개 업무 중 10개 업무 및 수준 선정
    - 9개 직무 분야 각 1개 + 추가 1개 = 10개
    - 입문 3개, 실무 4개, 관리자·심화 3개 균형 배정
    - 기본 추천 vs 개선안 Top 3가 다른 업무를 최우선 선택
    """
    rng = np.random.default_rng(seed)

    rem_tasks = [t for t in cat_tasks if t["task_id"] not in prev_evaluated_ids]
    tasks_by_dom = {}
    for t in rem_tasks:
        tasks_by_dom.setdefault(t["domain_id"], []).append(t)

    # 1. 미평가 업무 중 기본 vs 개선안 Top 3 차이가 있는 슬롯 우선 탐색
    diff_tasks_by_dom = {}
    for t in rem_tasks:
        t_id = t["task_id"]
        for lvl in ["입문", "실무", "관리자·심화"]:
            b_uids = set(df_base[(df_base["task_id"] == t_id) & (df_base["level"] == lvl)]["course_uid"])
            c_uids = set(df_cand[(df_cand["task_id"] == t_id) & (df_cand["level"] == lvl)]["course_uid"])
            diff_cnt = len(b_uids - c_uids) + len(c_uids - b_uids)
            if diff_cnt > 0:
                diff_tasks_by_dom.setdefault(t["domain_id"], []).append((t, lvl, diff_cnt))

    # 분야별 확정 슬롯 배정
    plan = []
    assigned_task_ids = set()

    # D01: T09 [관리자·심화] (diff=2)
    # D02: T09 [관리자·심화] (diff=2)
    # D03: T01 [실무] (diff=4)
    # D06: T06 [입문] (diff=2)
    # D07: T10 [실무] (diff=2)
    # D08: T01 [실무] (diff=2)
    priority_slots = [
        ("DOM_01", "TASK_HR_D01_T09", "관리자·심화"),
        ("DOM_02", "TASK_HR_D02_T09", "관리자·심화"),
        ("DOM_03", "TASK_HR_D03_T01", "실무"),
        ("DOM_06", "TASK_HR_D06_T06", "입문"),
        ("DOM_07", "TASK_HR_D07_T10", "실무"),
        ("DOM_08", "TASK_HR_D08_T01", "실무"),
    ]

    t_map = {t["task_id"]: t for t in rem_tasks}
    for dom_id, t_id, lvl in priority_slots:
        if t_id in t_map:
            plan.append((t_map[t_id], lvl))
            assigned_task_ids.add(t_id)

    # 차이가 없는 나머지 3개 분야(DOM_04, DOM_05, DOM_09)에서 수준 균형 고려하여 선정
    # 현재 배정: 관리자·심화 2개, 실무 3개, 입문 1개
    # 필요 배정: 입문 2개, 관리자·심화 1개, 실무 1개 (총 10개)
    d04_cands = sorted([t for t in tasks_by_dom["DOM_04"] if t["task_id"] not in assigned_task_ids], key=lambda x: x["task_id"])
    d04_t = rng.choice(d04_cands)
    plan.append((d04_t, "입문"))
    assigned_task_ids.add(d04_t["task_id"])

    d05_cands = sorted([t for t in tasks_by_dom["DOM_05"] if t["task_id"] not in assigned_task_ids], key=lambda x: x["task_id"])
    d05_t = rng.choice(d05_cands)
    plan.append((d05_t, "입문"))
    assigned_task_ids.add(d05_t["task_id"])

    d09_cands = sorted([t for t in tasks_by_dom["DOM_09"] if t["task_id"] not in assigned_task_ids], key=lambda x: x["task_id"])
    d09_t = rng.choice(d09_cands)
    plan.append((d09_t, "관리자·심화"))
    assigned_task_ids.add(d09_t["task_id"])

    # 10번째 업무 (잔여 풀에서 추가, 실무 1개 배정하여 입문 3 / 실무 4 / 관리자·심화 3 완성)
    rem_pool = sorted([t for t in rem_tasks if t["task_id"] not in assigned_task_ids and t["domain_id"] == "DOM_07"], key=lambda x: x["task_id"])
    extra_t = rng.choice(rem_pool)
    plan.append((extra_t, "실무"))
    assigned_task_ids.add(extra_t["task_id"])

    # 정렬: 분야 순서대로
    plan.sort(key=lambda x: (x[0]["domain_id"], x[0]["task_id"]))

    return plan


def select_10_distinct_decoys(df_courses, seed=42):
    """
    명백한 비인사 과정(IT개발, 무역통관, 민사소송, AI그래픽, 구매조달, SAP비인사, 콜센터, 회계세무, 스마트제조, 전자/통신) 10개 추출
    """
    decoy_queries = [
        ("IT_딥러닝", r"PyTorch|신경망|딥러닝\s*첫걸음|추천\s*시스템\s*알고리즘"),
        ("무역_통관", r"수출입통관|FTA관세|원산지증명|보세사"),
        ("민사_소송", r"민사\s*소송|부동산등기|경매\s*실무"),
        ("AI_그래픽", r"ComfyUI|미드저니|Midjourney|AI\s*그림"),
        ("구매_조달", r"구매원가|구매전략|자재관리|협력사\s*조달"),
        ("SAP_비인사", r"S/4HANA\s*(?:CO|MM|SD)|SAP\s*(?:CO|MM|SD)"),
        ("콜센터_QA", r"상담품질\s*평가|QA\s*전문가"),
        ("재무_회계", r"전산회계|재무제표\s*읽는\s*법|원가회계"),
        ("제조_품질", r"스마트공장|생산자동화|품질경영|QC"),
        ("전자_통신", r"반도체|전자회로|네트워크\s*보안|CCNA"),
    ]

    selected_decoys = []
    used_uids = set()

    for category, pattern in decoy_queries:
        rx = re.compile(pattern, re.IGNORECASE)
        matched = df_courses[df_courses["title"].str.contains(rx, regex=True, na=False)]
        valid = matched[~matched.index.isin(used_uids)]
        if len(valid) == 0:
            valid = matched

        chosen_row = valid.iloc[0]
        used_uids.add(chosen_row.name)
        selected_decoys.append({
            "category": category,
            "course_uid": chosen_row.name,
            "title": str(chosen_row["title"]),
            "provider": str(chosen_row.get("provider", "")),
            "url": str(chosen_row.get("url", "")),
            "row": chosen_row,
        })

    return selected_decoys


def build_holdout3_evaluation_data():
    print("=== 홀드아웃 3차 평가 데이터 준비 시작 ===")

    # 1. 데이터 로드
    cat_tasks = json.load(open(CATALOG_PATH, encoding="utf-8"))["tasks"]

    prev_ids = (
        set(pd.read_csv(EVAL_ORIG_PATH)["task_id"])
        | set(pd.read_csv(HOLDOUT1_PATH)["task_id"])
        | set(pd.read_csv(HOLDOUT2_PATH)["task_id"])
    )
    print(f"과거 평가 완료 과업: {len(prev_ids)}개 (미평가 잔여 과업: {90 - len(prev_ids)}개)")

    df_base = pd.read_csv(BASE_REC_PATH)
    df_cand = pd.read_csv(CAND_REC_PATH)
    df_courses = pd.read_parquet(COURSES_PARQUET).set_index("course_uid")

    # 2. 10개 업무 및 수준 선정
    plan = select_holdout3_tasks(cat_tasks, prev_ids, df_base, df_cand, seed=42)
    print("\n선정된 홀드아웃 3차 10개 업무 및 수준 (seed=42):")
    for i, (t, lvl) in enumerate(plan, 1):
        print(f"  {i:2d}. [{lvl}] {t['task_id']} ({t['domain_name']}) - {t['task_name']}")

    # 수준 분포 검증
    level_counts = pd.Series([lvl for _, lvl in plan]).value_counts().to_dict()
    print(f"수준 분포: {level_counts} (입문 3, 실무 4, 관리자·심화 3 달성)")

    # 3. 10개 디코이 과정 추출
    decoys = select_10_distinct_decoys(df_courses, seed=42)
    print("\n선정된 비인사 디코이 과정 10건:")
    for i, dec in enumerate(decoys, 1):
        print(f"  {i:2d}. [{dec['category']}] {dec['provider']} - {dec['title']}")

    # 4. 슬롯별 추천 합집합 및 디코이 조합 생성
    rng = np.random.default_rng(42)
    item_definitions = []

    global_item_id = 1

    for slot_idx, (t_info, level) in enumerate(plan):
        t_id = t_info["task_id"]
        dom_name = t_info["domain_name"]
        t_name = t_info["task_name"]

        sub_base = df_base[(df_base["task_id"] == t_id) & (df_base["level"] == level) & (df_base["rank"] <= 3)].copy()
        sub_cand = df_cand[(df_cand["task_id"] == t_id) & (df_cand["level"] == level) & (df_cand["rank"] <= 3)].copy()

        base_uids = set(sub_base["course_uid"])
        cand_uids = set(sub_cand["course_uid"])

        slot_candidates = {}

        # Baseline
        for _, r in sub_base.iterrows():
            uid = str(r["course_uid"])
            slot_candidates[uid] = {
                "course_uid": uid,
                "title": str(r["title"]),
                "provider": str(r["provider"]),
                "source": "shared" if uid in cand_uids else "baseline",
            }

        # Candidate
        for _, r in sub_cand.iterrows():
            uid = str(r["course_uid"])
            if uid not in slot_candidates:
                slot_candidates[uid] = {
                    "course_uid": uid,
                    "title": str(r["title"]),
                    "provider": str(r["provider"]),
                    "source": "candidate",
                }

        # Decoy (slot마다 1개)
        decoy_item = decoys[slot_idx]
        dec_uid = str(decoy_item["course_uid"])
        slot_candidates[dec_uid] = {
            "course_uid": dec_uid,
            "title": decoy_item["title"],
            "provider": decoy_item["provider"],
            "source": "decoy",
            "decoy_category": decoy_item["category"],
        }

        # 블라인드 무작위 셔플 (순서로 출처를 알 수 없도록)
        cand_items = list(slot_candidates.values())
        rng.shuffle(cand_items)

        for c in cand_items:
            c_uid = c["course_uid"]
            c_row = df_courses.loc[c_uid] if c_uid in df_courses.index else pd.Series()
            raw_url = str(c_row.get("url", "")) if not c_row.empty else ""
            c_url = detail_url(raw_url) if raw_url else ""
            summary = get_course_intro_summary(c_row) if not c_row.empty else "과정 상세 소개 정보 제공 예정"

            item_definitions.append({
                "item_id": global_item_id,
                "task_id": t_id,
                "domain": dom_name,
                "task": t_name,
                "level": level,
                "title": c["title"],
                "provider": c["provider"],
                "url": c_url,
                "과정 소개(요약)": summary,
                "course_uid": c_uid,
                "source": c["source"],
                "decoy_category": c.get("decoy_category", ""),
            })
            global_item_id += 1

    # 5. 2인 평가자 배분 (김, 이, 박, 홍 4명 균등 교차 배정)
    # 6개 고유 쌍을 라운드로빈 순환하여 4명의 부하를 완전히 균등하게 분산
    rater_pairs = [
        ("김", "이"),
        ("박", "홍"),
        ("김", "박"),
        ("이", "홍"),
        ("김", "홍"),
        ("이", "박"),
    ]
    pair_cycle = cycle(rater_pairs)

    items_rows = []
    key_rows = []

    for item in item_definitions:
        r1, r2 = next(pair_cycle)
        # items sheet: 2 rows per item_id
        for rater in [r1, r2]:
            items_rows.append({
                "item_id": item["item_id"],
                "rater": rater,
                "task_id": item["task_id"],
                "domain": item["domain"],
                "task": item["task"],
                "level": item["level"],
                "title": item["title"],
                "provider": item["provider"],
                "url": item["url"],
                "과정 소개(요약)": item["과정 소개(요약)"],
                "judgment": "",
                "memo": "",
            })

        # key file: 1 row per item_id
        key_rows.append({
            "item_id": item["item_id"],
            "task_id": item["task_id"],
            "course_uid": item["course_uid"],
            "source": item["source"],
            "decoy_category": item["decoy_category"],
        })

    df_items = pd.DataFrame(items_rows)
    df_key = pd.DataFrame(key_rows)

    # 6. 엄격 검증
    print("\n=== 자동 정합성 검증 수행 ===")
    assert (df_items["judgment"] == "").all(), "오류: judgment 칸이 비어 있지 않습니다."
    assert (df_items["memo"] == "").all(), "오류: memo 칸이 비어 있지 않습니다."
    assert "source" not in df_items.columns, "오류: 블라인드 평가 시트에 source 열이 노출되었습니다."
    assert len(df_items) == len(df_key) * 2, f"오류: items 행 수({len(df_items)})는 key 행 수({len(df_key)})의 정확히 2배여야 합니다."

    # 출처 단어 누출 검사 (평가자가 출처를 알 수 있는 라벨)
    source_forbidden_words = ["baseline", "candidate", "shared", "decoy", "가짜 추천", "개선안 추천", "기본 추천"]
    for word in source_forbidden_words:
        assert not df_items["title"].str.contains(word, case=False).any(), f"오류: title에 출처 단어({word})가 포함되어 있습니다."
        assert not df_items["과정 소개(요약)"].str.contains(word, case=False).any(), f"오류: 소개에 출처 단어({word})가 포함되어 있습니다."

    # 평가자 균등 배분 검증
    rater_counts = df_items["rater"].value_counts().to_dict()
    print(f"평가자별 배정 건수: {rater_counts}")
    max_r = max(rater_counts.values())
    min_r = min(rater_counts.values())
    assert max_r - min_r <= 1, f"오류: 평가자 간 배정 격차({max_r - min_r})가 1을 초과합니다."

    # 디코이 개수 검증
    decoy_cnt = int((df_key["source"] == "decoy").sum())
    assert decoy_cnt == 10, f"오류: 디코이 건수가 10건이 아닙니다 ({decoy_cnt}건)"

    source_counts = df_key["source"].value_counts().to_dict()
    print(f"출처별 고유 항목 분포: {source_counts}")
    print(f"[PASS] 블라인드 시트 및 키 파일 정합성 검증 완료 (고유 {len(df_key)}개 항목, 2인 배정 총 {len(df_items)}행)")

    # 7. 파일 저장
    OUT_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_items.to_csv(OUT_ITEMS_PATH, index=False, encoding="utf-8-sig")
    df_key.to_csv(OUT_KEY_PATH, index=False, encoding="utf-8-sig")

    print(f"\n평가 시트 저장 완료: {OUT_ITEMS_PATH} ({len(df_items)}행)")
    print(f"정답 키 저장 완료: {OUT_KEY_PATH} ({len(df_key)}행)")


if __name__ == "__main__":
    build_holdout3_evaluation_data()
