# -*- coding: utf-8 -*-
"""
업무-과정 짝 설명 입력 생성 스크립트
파일명: scripts/build_chat_explanation_inputs.py

목적:
- task_course_recommendations_90.csv 및 task_course_recommendations_90_reranked.csv의
  (업무 ID, course_uid) 짝 전체(중복 제거)를 추출
- 각 짝마다 업무 정보(업무명, 분야, 설명, KSA)와 과정 정보(과정명, 기관, 난이도, 소개 요약)를 결합
- 출력: data/hr/output/chatbot/explanation_inputs.jsonl
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.customer import career_platform as cp

REC_90_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"
REC_RERANKED_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
NCS_KSA_PATH = ROOT / "data" / "processed" / "ncs_ksa_master.csv"
OUT_DIR = ROOT / "data" / "hr" / "output" / "chatbot"
OUT_FILE = OUT_DIR / "explanation_inputs.jsonl"


def build_explanation_inputs():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 추천 파일 로드 및 유니크 (task_id, course_uid) 짝 추출
    df_rec = pd.read_csv(REC_90_PATH) if REC_90_PATH.exists() else pd.DataFrame()
    df_rerank = pd.read_csv(REC_RERANKED_PATH) if REC_RERANKED_PATH.exists() else pd.DataFrame()

    pairs_set = set()
    if not df_rec.empty:
        for _, r in df_rec.iterrows():
            pairs_set.add((str(r["task_id"]).strip(), str(r["course_uid"]).strip()))

    if not df_rerank.empty:
        for _, r in df_rerank.iterrows():
            pairs_set.add((str(r["task_id"]).strip(), str(r["course_uid"]).strip()))

    print(f"Total unique (task_id, course_uid) pairs extracted: {len(pairs_set)}")

    # 2. 90개 업무 메타데이터 로드
    tasks_meta = {}
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)
            t_list = cat.get("tasks", cat) if isinstance(cat, dict) else cat
            for t in t_list:
                # task_id (TASK_HR_D01_T01) 및 source_task_id (DOM_01_T01) 모두 매핑 지원
                tid = t.get("task_id", "")
                sid = t.get("source_task_id", "")
                tasks_meta[tid] = t
                if sid:
                    tasks_meta[sid] = t

    # 3. 강좌 메타데이터
    df_courses = cp.courses().set_index("course_uid", drop=False)

    records = []
    # 정렬하여 일관된 순서 유지
    sorted_pairs = sorted(list(pairs_set))

    for task_id, course_uid in sorted_pairs:
        t_info = tasks_meta.get(task_id, {})
        c_info = df_courses.loc[course_uid] if course_uid in df_courses.index else pd.Series()

        task_name = t_info.get("task_name", "")
        domain_name = t_info.get("domain_name", "")
        easy_desc = t_info.get("easy_description", "")
        k = t_info.get("knowledge", "")
        s = t_info.get("skill", "")
        a = t_info.get("attitude", "")

        ksa_summary = f"지식: {k} | 기술: {s} | 태도: {a}"

        title = str(c_info.get("title", ""))
        provider = str(c_info.get("provider", ""))
        difficulty = str(c_info.get("difficulty") or "미확인")
        intro_summary = cp.course_intro_summary(c_info if not c_info.empty else course_uid)

        item = {
            "pair_key": f"{task_id}|{course_uid}",
            "task_id": task_id,
            "source_task_id": t_info.get("source_task_id", ""),
            "domain_id": t_info.get("domain_id", ""),
            "domain_name": domain_name,
            "task_name": task_name,
            "easy_description": easy_desc,
            "ksa_knowledge": k,
            "ksa_skill": s,
            "ksa_attitude": a,
            "ksa_summary": ksa_summary,
            "course_uid": course_uid,
            "title": title,
            "provider": provider,
            "difficulty": difficulty,
            "intro_summary": intro_summary,
        }
        records.append(item)

    # 4. JSONL 저장
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Saved {len(records)} records to {OUT_FILE}")
    return len(records)


if __name__ == "__main__":
    count = build_explanation_inputs()
    print(f"Done. Pair count: {count}")
