#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/build_candidate_diff_eval.py
기본 추천(Baseline) vs 통합 개선안(Candidate) 상위 3개 차이 목록 및 기존 평가 이력 매핑

목적:
1. task_course_recommendations_90_reranked.csv vs task_course_recommendations_90_candidate.csv 비교
2. 상위 3개(rank <= 3)를 (task_id, level, 과정명 정규화) 단위로 대조하여 상이 항목 추출
3. 기존 사람 평가 파일 5개와 대조하여 rater별 평가 이력 및 출처 기록
4. 판정이 2명 미만인 항목을 '판정 필요'로 표시
5. 배경 수치(다른 칸 17개, 업무 11개, side별 과정 22개, 미평가 50개 업무 차이 0개)를 검증하고 다르면 중단
6. 결과 저장: data/hr/output/recommendation/candidate_diff_items.csv
"""

import sys
import os
import re
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.course_links import detail_url

BASE_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
CAND_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_candidate.csv"
COURSES_PARQUET = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
OUTPUT_DIFF_CSV = ROOT / "data" / "hr" / "output" / "recommendation" / "candidate_diff_items.csv"

EVAL_FILES = [
    ("precision_eval_results", ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"),
    ("precision_eval_round2_results", ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_round2_results.csv"),
    ("precision_eval_holdout_results", ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_results.csv"),
    ("precision_eval_holdout2_results", ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout2_results.csv"),
    ("precision_eval_holdout3_results", ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout3_results.csv"),
]


def normalize_title(t: str) -> str:
    if not isinstance(t, str):
        return ""
    t = re.sub(r"\[.*?\]", "", t)
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def clean_summary_text(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    t = re.sub(r"\s+", " ", str(val)).strip()
    return t[:200]


def get_course_intro_summary(row: pd.Series) -> str:
    for col in ["learning_goals", "course_intro", "curriculum"]:
        val = row.get(col)
        if pd.notna(val) and val is not None:
            text = clean_summary_text(val)
            if text:
                return text
    return "과정 상세 소개 정보 제공 예정"


def build_candidate_diff():
    print("=== [1단계] 기본 추천 vs 개선안 Top 3 차이 목록 추출 및 검증 ===")
    assert BASE_REC_PATH.exists(), f"기본 추천 파일 없음: {BASE_REC_PATH}"
    assert CAND_REC_PATH.exists(), f"개선안 추천 파일 없음: {CAND_REC_PATH}"

    df_base = pd.read_csv(BASE_REC_PATH)
    df_cand = pd.read_csv(CAND_REC_PATH)

    b3 = df_base[df_base["rank"] <= 3].copy()
    c3 = df_cand[df_cand["rank"] <= 3].copy()

    b3["norm_title"] = b3["title"].apply(normalize_title)
    c3["norm_title"] = c3["title"].apply(normalize_title)

    # 1. 차이 칸 탐색
    all_slots = sorted(list(set(zip(b3["task_id"], b3["level"])) | set(zip(c3["task_id"], c3["level"]))))
    diff_cells = []
    diff_tasks = set()
    base_only_records = []
    cand_only_records = []

    for tid, lvl in all_slots:
        bg = b3[(b3["task_id"] == tid) & (b3["level"] == lvl)]
        cg = c3[(c3["task_id"] == tid) & (c3["level"] == lvl)]

        b_uids = set(bg["course_uid"])
        c_uids = set(cg["course_uid"])

        if b_uids != c_uids:
            diff_cells.append((tid, lvl))
            diff_tasks.add(tid)

            # baseline only
            for _, r in bg[bg["course_uid"].isin(b_uids - c_uids)].iterrows():
                base_only_records.append({
                    "task_id": tid,
                    "task": r["task_name"],
                    "level": lvl,
                    "course_uid": r["course_uid"],
                    "title": r["title"],
                    "provider": r["provider"],
                    "side": "baseline_only"
                })

            # candidate only
            for _, r in cg[cg["course_uid"].isin(c_uids - b_uids)].iterrows():
                cand_only_records.append({
                    "task_id": tid,
                    "task": r["task_name"],
                    "level": lvl,
                    "course_uid": r["course_uid"],
                    "title": r["title"],
                    "provider": r["provider"],
                    "side": "candidate_only"
                })

    n_diff_cells = len(diff_cells)
    n_diff_tasks = len(diff_tasks)
    n_base_only = len(base_only_records)
    n_cand_only = len(cand_only_records)

    print(f"- 다른 칸(task_id, level) 수: {n_diff_cells} (기준: 17)")
    print(f"- 다른 업무 수: {n_diff_tasks} (기준: 11)")
    print(f"- 기본에만 있는 과정 수: {n_base_only} (기준: 22)")
    print(f"- 개선안에만 있는 과정 수: {n_cand_only} (기준: 22)")

    # 엄격한 수치 검증: 다르면 즉시 중단
    if n_diff_cells != 17 or n_diff_tasks != 11 or n_base_only != 22 or n_cand_only != 22:
        print("[오류] 차이 수치가 배경 수치와 일치하지 않습니다. 작업을 중단합니다.", file=sys.stderr)
        sys.exit(1)

    # 2. 강좌 메타데이터(URL, 소개 요약) 결합
    print("\n강좌 상세 메타데이터(URL, 소개 요약) 결합 중...")
    course_meta = {}
    if COURSES_PARQUET.exists():
        df_parquet = pd.read_parquet(COURSES_PARQUET)
        for _, p_row in df_parquet.iterrows():
            c_uid = str(p_row.get("course_uid", ""))
            c_url = str(p_row.get("url", "")) or ""
            c_provider = str(p_row.get("provider", "")) or ""
            c_intro = get_course_intro_summary(p_row)
            d_url = detail_url(c_url) if c_url else ""
            course_meta[c_uid] = {
                "url": d_url,
                "intro_summary": c_intro
            }

    diff_items = base_only_records + cand_only_records
    for it in diff_items:
        meta = course_meta.get(str(it["course_uid"]), {})
        it["url"] = meta.get("url", "")
        it["과정 소개 요약"] = meta.get("intro_summary", "과정 상세 소개 정보 제공 예정")

    df_diff = pd.DataFrame(diff_items)
    df_diff["norm_title"] = df_diff["title"].apply(normalize_title)

    # 3. 기존 사람 평가 파일 5개와 대조
    print("\n기존 사람 평가 파일 5개와 대조 중...")
    loaded_evals = []
    evaluated_tasks_all = set()

    for name, fpath in EVAL_FILES:
        assert fpath.exists(), f"평가 파일 누락: {fpath}"
        edf = pd.read_csv(fpath)
        edf["source_file"] = name
        edf["norm_title"] = edf["title"].apply(normalize_title)
        loaded_evals.append((name, edf))
        evaluated_tasks_all.update(set(edf["task_id"]))

    print(f"- 기존 평가된 고유 업무 수: {len(evaluated_tasks_all)} (기준: 40)")
    assert len(evaluated_tasks_all) == 40, f"평가 업무 수 오류: {len(evaluated_tasks_all)} != 40"

    # 11개 차이 업무가 모두 기존 40개 평가 업무에 포함되는지 확인
    assert diff_tasks.issubset(evaluated_tasks_all), "11개 차이 업무 중 미평가 업무가 존재합니다!"
    all_90_tasks = set(df_base["task_id"])
    non_evaluated_50 = all_90_tasks - evaluated_tasks_all
    assert len(non_evaluated_50) == 50, f"미평가 업무 수 오류: {len(non_evaluated_50)} != 50"
    assert len(diff_tasks & non_evaluated_50) == 0, "미평가 50개 업무에서 두 추천이 일치하지 않습니다!"
    print("- 11개 차이 업무 모두 기존 40개 평가 업무 내 존재 확인 (미평가 50개 업무 차이 0 확인)")

    # 4. 각 차이 항목별 기존 평가 내역 결합
    for idx, r in df_diff.iterrows():
        matches = []
        for src_name, edf in loaded_evals:
            # (task_id, level, exact title) 또는 (task_id, level, norm_title)
            sub = edf[(edf["task_id"] == r["task_id"]) & (edf["level"] == r["level"]) & (edf["title"] == r["title"])]
            if len(sub) == 0:
                sub = edf[(edf["task_id"] == r["task_id"]) & (edf["level"] == r["level"]) & (edf["norm_title"] == r["norm_title"])]
            for _, sr in sub.iterrows():
                matches.append({
                    "source_file": src_name,
                    "rater": sr.get("rater", ""),
                    "judgment": sr.get("judgment", ""),
                    "memo": sr.get("memo", "")
                })

        df_diff.loc[idx, "judged_count"] = len(matches)
        df_diff.loc[idx, "eval_status"] = "판정 완료" if len(matches) >= 2 else "판정 필요"
        df_diff.loc[idx, "existing_eval_sources"] = ",".join(sorted(list(set(m["source_file"] for m in matches))))
        df_diff.loc[idx, "existing_eval_raters"] = ",".join([f"{m['rater']}:{m['judgment']}" for m in matches])
        df_diff.loc[idx, "existing_judgments"] = json.dumps(matches, ensure_ascii=False)

    df_diff["judged_count"] = df_diff["judged_count"].astype(int)
    n_need_eval = (df_diff["eval_status"] == "판정 필요").sum()
    n_already_eval = (df_diff["eval_status"] == "판정 완료").sum()

    print(f"\n- 기존 판정 완료 과정: {n_already_eval}개 (기본: {(df_diff[df_diff['eval_status']=='판정 완료']['side']=='baseline_only').sum()}개, 개선안: {(df_diff[df_diff['eval_status']=='판정 완료']['side']=='candidate_only').sum()}개)")
    print(f"- 신규 판정 필요 과정: {n_need_eval}개 (기본: {(df_diff[df_diff['eval_status']=='판정 필요']['side']=='baseline_only').sum()}개, 개선안: {(df_diff[df_diff['eval_status']=='판정 필요']['side']=='candidate_only').sum()}개)")

    assert n_need_eval == 22, f"판정 필요 수 오류: {n_need_eval} != 22"
    assert n_already_eval == 22, f"판정 완료 수 오류: {n_already_eval} != 22"

    # 열 순서 정리 (요청된 필수 열 선두 배치)
    cols = [
        "task_id", "task", "level", "course_uid", "title", "provider", "url", "과정 소개 요약",
        "side", "eval_status", "judged_count", "existing_eval_sources", "existing_eval_raters", "existing_judgments"
    ]
    df_diff = df_diff[cols]

    OUTPUT_DIFF_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_diff.to_csv(OUTPUT_DIFF_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[성공] 차이 목록 저장 완료: {OUTPUT_DIFF_CSV} ({len(df_diff)}행)")
    return df_diff


if __name__ == "__main__":
    build_candidate_diff()
