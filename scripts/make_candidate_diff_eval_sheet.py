#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/make_candidate_diff_eval_sheet.py
추천 정확도 개선안 재평가 블라인드 판정 시트 및 정답 키 생성 스크립트

규칙:
1. 판정 필요 과정 22개 전수 포함
2. 판정자 일관성 점검용 재판정 항목 10개(seed=42 고정) 무작위 추출 및 포함 (총 32개 항목)
3. 시트 항목 순서는 seed=42로 섞되, 동일 업무가 연속으로 배치되지 않도록 조정
4. 블라인드 평가 시트(candidate_diff_eval_items.csv)에는 side(기본/개선안) 및 재판정 여부 일체 비노출
   - 컬럼: item_id, rater, task_id, task, task_easy, level, title, provider, url, 과정 소개 요약, judgment, memo
   - 평가자 2인 체계: 항목당 2행 구성 (총 64행), rater/judgment/memo는 빈칸
5. 정답 키(candidate_diff_eval_key.csv)에만 side(기본/개선안)와 재판정 메타데이터 보관
"""

import sys
import os
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DIFF_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_items.csv"
CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
OUT_ITEMS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_items.csv"
OUT_KEY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_eval_key.csv"


def load_task_descriptions():
    desc_map = {}
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            tasks = data.get("tasks", []) if isinstance(data, dict) else data
            for t in tasks:
                tid = t.get("task_id")
                easy = t.get("easy_description") or t.get("easy") or t.get("description") or ""
                desc_map[tid] = easy
    return desc_map


def make_eval_sheets(seed=42):
    print("=== [2단계] 블라인드 판정 시트 및 정답 키 생성 ===")
    assert DIFF_ITEMS_PATH.exists(), f"차이 목록 파일 없음: {DIFF_ITEMS_PATH}"

    df_diff = pd.read_csv(DIFF_ITEMS_PATH)
    task_desc_map = load_task_descriptions()

    # 1. 판정 필요 22개 추출
    need_eval = df_diff[df_diff["eval_status"] == "판정 필요"].copy()
    already_eval = df_diff[df_diff["eval_status"] == "판정 완료"].copy()

    assert len(need_eval) == 22, f"판정 필요 항목 수 오류: {len(need_eval)} != 22"
    assert len(already_eval) == 22, f"기존 판정 완료 항목 수 오류: {len(already_eval)} != 22"

    need_eval["is_retest"] = False
    need_eval["retest_origin"] = ""

    # 2. 일관성 점검용 재판정 10개 추출 (seed=42)
    rng = np.random.default_rng(seed)
    retest_indices = rng.choice(len(already_eval), size=10, replace=False)
    retest_items = already_eval.iloc[retest_indices].copy()
    retest_items["is_retest"] = True
    retest_items["retest_origin"] = retest_items["existing_eval_sources"]

    # 3. 32개 항목 합치기
    all_32 = pd.concat([need_eval, retest_items], ignore_index=True)
    assert len(all_32) == 32, f"전체 항목 수 오류: {len(all_32)} != 32"

    # 4. 동일 업무 연속 등장 방지 셔플 (seed=42)
    items_list = all_32.to_dict("records")
    shuffle_rng = np.random.default_rng(seed)
    placed = False

    for attempt in range(10000):
        shuffle_rng.shuffle(items_list)
        if all(items_list[i]["task_id"] != items_list[i - 1]["task_id"] for i in range(1, len(items_list))):
            placed = True
            print(f"- 시드 고정 셔플 성공 (시도 횟수: {attempt}, 동일 업무 연속 없음)")
            break

    assert placed, "동일 업무 연속 회피 셔플 실패"

    # 5. 블라인드 평가 시트 및 키 생성 (항목당 2행 구성 -> 총 64행)
    sheet_rows = []
    key_rows = []

    for item_idx, it in enumerate(items_list, 1):
        tid = it["task_id"]
        task_easy = task_desc_map.get(tid, "")

        # 2인 평가 체계: 평가자 1, 평가자 2
        for rater_slot in [1, 2]:
            row_id = (item_idx - 1) * 2 + rater_slot

            # 시트 행 (side, retest 정보 완전 배제)
            sheet_rows.append({
                "item_id": item_idx,
                "rater": "",  # 평가자 이름은 구글 시트 업로드 시 입력
                "task_id": tid,
                "task": it["task"],
                "task_easy": task_easy,
                "level": it["level"],
                "title": it["title"],
                "provider": it["provider"],
                "url": it["url"],
                "과정 소개 요약": it["과정 소개 요약"],
                "judgment": "",  # 평가자 입력란 (빈칸)
                "memo": ""       # 메모란 (빈칸)
            })

            # 키 행 (정답 및 검증 메타데이터 보관)
            key_rows.append({
                "item_id": item_idx,
                "row_id": row_id,
                "rater_slot": rater_slot,
                "task_id": tid,
                "level": it["level"],
                "course_uid": it["course_uid"],
                "title": it["title"],
                "provider": it["provider"],
                "side": it["side"],
                "is_retest": it["is_retest"],
                "retest_origin": it["retest_origin"],
                "existing_raters": it.get("existing_eval_raters", ""),
                "existing_judgments": it.get("existing_judgments", "")
            })

    df_sheet = pd.DataFrame(sheet_rows)
    df_key = pd.DataFrame(key_rows)

    # 6. 블라인드 누출 여부 전수 감사
    forbidden_terms = ["baseline", "candidate", "retest", "side", "기본", "개선안", "재판정"]
    for col in df_sheet.columns:
        assert not any(ft in col.lower() for ft in forbidden_terms), f"시트 열 이름에 side 정보 누출: {col}"

    print(f"- 블라인드 시트 행 수: {len(df_sheet)} (32개 항목 * 2인 평가)")
    print(f"- 정답 키 행 수: {len(df_key)} (시트와 1:1 매칭)")
    assert len(df_sheet) == len(df_key), "시트와 키의 행 수가 일치하지 않습니다!"

    OUT_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_sheet.to_csv(OUT_ITEMS_PATH, index=False, encoding="utf-8-sig")
    df_key.to_csv(OUT_KEY_PATH, index=False, encoding="utf-8-sig")

    print(f"[성공] 블라인드 평가 시트 저장: {OUT_ITEMS_PATH}")
    print(f"[성공] 정답 키 저장: {OUT_KEY_PATH}")


if __name__ == "__main__":
    make_eval_sheets()
