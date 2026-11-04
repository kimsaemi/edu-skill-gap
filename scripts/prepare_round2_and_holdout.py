# -*- coding: utf-8 -*-
"""
사람 평가용 2차 시트 (Round 2) 및 홀드아웃 후보 시트 생성 스크립트 (수정본)

원칙:
1. 업무명(task), 분야(domain), 과정명, 기관, URL은 절대 손으로 적지 않고,
   카탈로그(hr_task_catalog_90.json), 리랭커 결과, 과정 메타데이터에서 자동 로드합니다.
2. 판정(judgment) 및 메모(memo)는 사람이 평가하므로, 신규 항목은 무조건 빈 문자열("")로 둡니다.
3. 6대 자동 무결성 검증을 모두 통과한 경우에만 최종 파일로 저장합니다.
"""

import json
import sys
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.customer import career_platform as cp
from src.customer.career_platform import course_intro_summary

CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
EXCL_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
RERANK_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
EVAL_ORIG_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"

ROUND2_OUT_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_round2_items.csv"
HOLDOUT_OUT_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_items.csv"

# 1. 메타데이터 및 기준 데이터 로드
with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    cat = json.load(f)["tasks"]
catalog_tasks = {t["task_id"]: t for t in cat}

df_rerank = pd.read_csv(RERANK_PATH)
df_eval_orig = pd.read_csv(EVAL_ORIG_PATH)
df_excl = pd.read_csv(EXCL_PATH)
excl_uids = set(df_excl["course_uid"].astype(str))

df_courses = cp.courses().set_index("course_uid")

def get_course_info(uid):
    if uid in df_courses.index:
        c = df_courses.loc[uid]
        return str(c.get("title", "")), str(c.get("provider", "")), str(c.get("url", ""))
    return "", "", ""

print("=== 1. Round 2 평가 항목 구성 ===")

# 기존 10개 평가 슬롯의 rater 및 메타정보 추출 (item_no: 1 ~ 30)
slot_raters = {}
slot_keys = {}
for _, row in df_eval_orig.iterrows():
    ino = int(row["item_no"])
    slot_raters.setdefault(ino, []).append(row["rater"])
    slot_keys[ino] = (row["task_id"], row["level"], int(row["rank"]))

round2_rows = []
for ino in sorted(slot_keys.keys()):
    tid, level, rank = slot_keys[ino]
    t_meta = catalog_tasks[tid]
    domain = t_meta["domain_name"]
    task_name = t_meta["task_name"]
    raters = slot_raters[ino]

    # 리랭커 결과에서 해당 순위 강좌 조회
    sub = df_rerank[(df_rerank["task_id"] == tid) & (df_rerank["level"] == level) & (df_rerank["rank"] == rank)]
    if sub.empty:
        raise ValueError(f"리랭커 결과에 슬롯 없음: {tid}, {level}, #{rank}")
    r_item = sub.iloc[0]
    c_uid = str(r_item["course_uid"])
    title, provider, url = get_course_info(c_uid)
    if not title:
        title = str(r_item.get("title", ""))
    if not provider:
        provider = str(r_item.get("provider", ""))

    for rater in raters:
        past = df_eval_orig[
            (df_eval_orig["task_id"] == tid) &
            (df_eval_orig["level"] == level) &
            (df_eval_orig["course_uid"] == c_uid) &
            (df_eval_orig["rater"] == rater)
        ]
        if not past.empty:
            judg = str(past.iloc[0]["judgment"])
            memo = str(past.iloc[0]["memo"]) if pd.notna(past.iloc[0]["memo"]) else ""
        else:
            judg = ""
            memo = ""

        round2_rows.append({
            "item_no": ino,
            "rater": rater,
            "task_id": tid,
            "domain": domain,
            "task": task_name,
            "level": level,
            "rank": rank,
            "course_uid": c_uid,
            "title": title,
            "provider": provider,
            "url": url,
            "judgment": judg,
            "memo": memo,
            "과정 소개(요약)": course_intro_summary(c_uid),
        })

df_round2 = pd.DataFrame(round2_rows)

print("=== 2. 홀드아웃(Holdout) 후보 10개 업무 평가 항목 구성 ===")
# 9개 분야 골고루 포함한 10개 업무 (기존 10개 평가 업무와 일체 중복 없음)
holdout_plan = [
    ("TASK_HR_D01_T04", "실무", ("김", "이")),
    ("TASK_HR_D02_T01", "실무", ("박", "홍")),
    ("TASK_HR_D03_T02", "입문", ("김", "박")),
    ("TASK_HR_D04_T02", "입문", ("이", "홍")),
    ("TASK_HR_D05_T01", "관리자·심화", ("김", "홍")),
    ("TASK_HR_D06_T02", "실무", ("이", "박")),
    ("TASK_HR_D07_T03", "실무", ("김", "이")),
    ("TASK_HR_D08_T05", "관리자·심화", ("박", "홍")),
    ("TASK_HR_D09_T01", "입문", ("김", "박")),
    ("TASK_HR_D06_T05", "실무", ("이", "홍")),
]

holdout_rows = []
h_item_no = 1
for tid, level, (r1, r2) in holdout_plan:
    t_meta = catalog_tasks[tid]
    domain = t_meta["domain_name"]
    task_name = t_meta["task_name"]

    sub = df_rerank[(df_rerank["task_id"] == tid) & (df_rerank["level"] == level)].sort_values("rank").head(3)
    if len(sub) < 3:
        raise ValueError(f"홀드아웃 업무 {tid}의 리랭커 추천 수가 3개 미만: {len(sub)}")

    for _, r_item in sub.iterrows():
        rk = int(r_item["rank"])
        c_uid = str(r_item["course_uid"])
        title, provider, url = get_course_info(c_uid)
        if not title:
            title = str(r_item.get("title", ""))
        if not provider:
            provider = str(r_item.get("provider", ""))

        for rater in [r1, r2]:
            holdout_rows.append({
                "item_no": h_item_no,
                "rater": rater,
                "task_id": tid,
                "domain": domain,
                "task": task_name,
                "level": level,
                "rank": rk,
                "course_uid": c_uid,
                "title": title,
                "provider": provider,
                "url": url,
                "judgment": "",
                "memo": "",
                "과정 소개(요약)": course_intro_summary(c_uid),
            })
        h_item_no += 1

df_holdout = pd.DataFrame(holdout_rows)

print("\n=== 3. 6대 자동 무결성 검증 (Strict Assertions) ===")

# 검증 1: (task_id, task)가 카탈로그의 업무명과 100% 일치
for df_chk, name in [(df_round2, "Round 2"), (df_holdout, "Holdout")]:
    for _, r in df_chk.iterrows():
        expected_task = catalog_tasks[r["task_id"]]["task_name"]
        expected_domain = catalog_tasks[r["task_id"]]["domain_name"]
        assert r["task"] == expected_task, f"[{name}] Task 이름 불일치: {r['task_id']} '{r['task']}' vs '{expected_task}'"
        assert r["domain"] == expected_domain, f"[{name}] Domain 불일치: {r['task_id']} '{r['domain']}' vs '{expected_domain}'"
print("[PASS] 검증 1: 두 평가표의 (task_id, task, domain)이 카탈로그와 100% 일치")

# 검증 2: (task_id, level, rank, course_uid)가 리랭커 결과와 100% 일치
for df_chk, name in [(df_round2, "Round 2"), (df_holdout, "Holdout")]:
    for _, r in df_chk.iterrows():
        match = df_rerank[
            (df_rerank["task_id"] == r["task_id"]) &
            (df_rerank["level"] == r["level"]) &
            (df_rerank["rank"] == r["rank"]) &
            (df_rerank["course_uid"] == r["course_uid"])
        ]
        assert not match.empty, f"[{name}] 리랭커 결과 불일치: {r['task_id']}, {r['level']}, Rank {r['rank']}, UID {r['course_uid']}"
print("[PASS] 검증 2: (task_id, level, rank, course_uid)가 리랭커 결과와 100% 일치")

# 검증 3: 제외 목록에 있는 과정이 평가표에 0개
for df_chk, name in [(df_round2, "Round 2"), (df_holdout, "Holdout")]:
    in_excl = df_chk["course_uid"].isin(excl_uids)
    assert in_excl.sum() == 0, f"[{name}] 제외 목록 과정 포함됨: {df_chk[in_excl]['course_uid'].tolist()}"
print("[PASS] 검증 3: 제외 목록 과정 0건 검증 완료")

# 검증 4: 재사용한 판정이 precision_eval_results.csv 원본과 100% 일치
reused_cnt = 0
for _, r in df_round2.iterrows():
    if r["judgment"] != "":
        orig_match = df_eval_orig[
            (df_eval_orig["task_id"] == r["task_id"]) &
            (df_eval_orig["level"] == r["level"]) &
            (df_eval_orig["course_uid"] == r["course_uid"]) &
            (df_eval_orig["rater"] == r["rater"])
        ]
        assert not orig_match.empty, f"원본에 없는 판정값: {r}"
        assert orig_match.iloc[0]["judgment"] == r["judgment"], f"판정값 불일치: {r}"
        reused_cnt += 1
print(f"[PASS] 검증 4: 재사용된 판정 {reused_cnt}건이 원본과 100% 일치")

# 검증 5: 새 항목의 judgment·memo가 모두 비어 있음
new_in_round2 = df_round2[df_round2["judgment"] == ""]
for _, r in new_in_round2.iterrows():
    assert r["judgment"] == "", f"새 항목 judgment 비어있지 않음: {r}"
    assert r["memo"] == "", f"새 항목 memo 비어있지 않음: {r}"
for _, r in df_holdout.iterrows():
    assert r["judgment"] == "", f"홀드아웃 judgment 비어있지 않음: {r}"
    assert r["memo"] == "", f"홀드아웃 memo 비어있지 않음: {r}"
print(f"[PASS] 검증 5: 신규 항목(Round2 {len(new_in_round2)}행, Holdout {len(df_holdout)}행)의 judgment/memo가 모두 빈칸임")

# 검증 6: 항목(item_no)마다 서로 다른 평가자 2명
for df_chk, name in [(df_round2, "Round 2"), (df_holdout, "Holdout")]:
    for ino, grp in df_chk.groupby("item_no"):
        raters = list(grp["rater"])
        assert len(raters) == 2, f"[{name}] item {ino} 평가자 수가 2명이 아님 ({len(raters)}명)"
        assert raters[0] != raters[1], f"[{name}] item {ino} 동일 평가자 중복 배정 ({raters})"
print("[PASS] 검증 6: 모든 항목에 서로 다른 평가자 2인 교차 배정 확인")

# 4. 검증 통과 후 파일 저장
df_round2.to_csv(ROUND2_OUT_PATH, index=False, encoding="utf-8-sig")
df_holdout.to_csv(HOLDOUT_OUT_PATH, index=False, encoding="utf-8-sig")

print(f"\n파일 저장 완료:")
print(f"  1. {ROUND2_OUT_PATH.name} ({len(df_round2)}행)")
print(f"  2. {HOLDOUT_OUT_PATH.name} ({len(df_holdout)}행)")

# 5. 통계 요약 출력
print("\n=== [통계 요약] ===")
print(f"Round 2:")
print(f"  - 총 항목(item_no): {df_round2['item_no'].nunique()}개")
print(f"  - 기존 판정 유지 항목: {len(df_round2[df_round2['judgment'] != '']) // 2}개")
print(f"  - 신규 평가 대상 항목: {len(new_in_round2) // 2}개 ({len(new_in_round2)} 평가 건수)")
print(f"  - 신규 평가 대상 평가자별 배정: {dict(new_in_round2['rater'].value_counts())}")

print(f"\nHoldout:")
print(f"  - 총 항목(item_no): {df_holdout['item_no'].nunique()}개 (총 60 평가 행)")
print(f"  - 평가자별 배정 건수: {dict(df_holdout['rater'].value_counts())}")
