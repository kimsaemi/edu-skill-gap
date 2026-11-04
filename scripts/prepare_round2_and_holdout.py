# -*- coding: utf-8 -*-
"""
사람 평가용 2차 시트 (Round 2) 및 홀드아웃 후보 시트 생성 스크립트
1. Round 2: 10개 대표 업무의 최신 Top 3 추출
   - 기존 평가 결과가 있는 (업무, 난이도, 강좌)는 기존 판정 유지
   - 새로 들어온 강좌는 judgment, memo를 빈칸("")으로 둠
2. Holdout: 9개 분야 골고루 선정한 신규 10개 업무의 Top 3 추출 (판정 전원 빈칸)
"""

import sys
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.customer import career_platform as cp

RERANK_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
EVAL_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_results.csv"

ROUND2_OUT_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_round2_items.csv"
HOLDOUT_OUT_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "precision_eval_holdout_items.csv"

df_rerank = pd.read_csv(RERANK_PATH)
df_eval = pd.read_csv(EVAL_PATH)
df_courses = cp.courses().set_index("course_uid")

def get_course_info(uid):
    if uid in df_courses.index:
        c = df_courses.loc[uid]
        return str(c.get("title", "")), str(c.get("provider", "")), str(c.get("url", ""))
    return "", "", ""

print("=== 1. Round 2 평가 항목 생성 ===")

# Task slot별 rater 매핑 (기존 precision_eval_results.csv 구조 그대로 유지)
# item_no 1~30에 대한 rater 쌍 매핑
slot_raters = {}
slot_tasks = {}
for _, row in df_eval.iterrows():
    ino = int(row["item_no"])
    slot_raters.setdefault(ino, []).append(row["rater"])
    slot_tasks[ino] = (row["task_id"], row["domain"], row["task"], row["level"], int(row["rank"]))

round2_rows = []
new_items_count = 0
reused_items_count = 0

for ino in sorted(slot_tasks.keys()):
    tid, domain, task_name, level, rank = slot_tasks[ino]
    raters = slot_raters[ino]
    
    # Reranked result에서 해당 (task_id, level, rank) 찾기
    sub = df_rerank[(df_rerank["task_id"] == tid) & (df_rerank["level"] == level) & (df_rerank["rank"] == rank)]
    if sub.empty:
        print(f"Warning: No reranked result for item {ino} ({tid}, {level}, #{rank})")
        continue
    r_item = sub.iloc[0]
    c_uid = r_item["course_uid"]
    title, provider, url = get_course_info(c_uid)
    if not title:
        title = r_item.get("title", "")
    if not provider:
        provider = r_item.get("provider", "")

    # 기존 평가 여부 확인
    for rater in raters:
        past = df_eval[(df_eval["task_id"] == tid) & (df_eval["level"] == level) & (df_eval["course_uid"] == c_uid) & (df_eval["rater"] == rater)]
        if not past.empty:
            judg = past.iloc[0]["judgment"]
            memo = past.iloc[0]["memo"] if pd.notna(past.iloc[0]["memo"]) else ""
            is_new = False
        else:
            judg = ""
            memo = ""
            is_new = True

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
        })
    
    # 2명 평가자 기준 신규 여부 체크
    past_any = df_eval[(df_eval["task_id"] == tid) & (df_eval["level"] == level) & (df_eval["course_uid"] == c_uid)]
    if past_any.empty:
        new_items_count += 1
    else:
        reused_items_count += 1

df_round2 = pd.DataFrame(round2_rows)
df_round2.to_csv(ROUND2_OUT_PATH, index=False, encoding="utf-8-sig")
print(f"Round 2 파일 저장 완료: {ROUND2_OUT_PATH}")
print(f"  - 총 평가 항목 수(item_no): {len(slot_tasks)}개 (총 평가 행: {len(df_round2)}행)")
print(f"  - 기존 평가 재사용 항목: {reused_items_count}개")
print(f"  - 신규 미평가 항목 (사람 판정 필요): {new_items_count}개")

# 신규 항목에 대한 평가자별 배정 수
unrated_df = df_round2[df_round2["judgment"] == ""]
print("  - 신규 항목 평가자별 배정 건수:")
print(unrated_df["rater"].value_counts().to_string())

print("\n=== 2. 홀드아웃 후보 10개 업무 평가표 생성 ===")

holdout_tasks_def = [
    ("TASK_HR_D01_T04", "인사전략·인력기획", "전사 총인건비 예산 편성 및 한도(Cap) 설정", "실무", ("김", "이")),
    ("TASK_HR_D02_T01", "조직설계·직무분석", "직무분석 및 직무기술서·직무명세서(JD/JS) 작성", "실무", ("박", "홍")),
    ("TASK_HR_D03_T02", "인재채용", "채용 브랜딩(EVP) 기획 및 채용 공고(JD) 카피라이팅", "입문", ("김", "박")),
    ("TASK_HR_D04_T02", "온보딩·직원경험", "신규 입사자 온보딩 프로그램(OJT/웰컴 세션) 기획 및 운영", "입문", ("이", "홍")),
    ("TASK_HR_D05_T01", "성과평가·목표관리", "전사 핵심성과지표(KPI/OKR) 목표 수립 및 연계 캐스케이딩", "관리자·심화", ("김", "홍")),
    ("TASK_HR_D06_T02", "보상·급여·복리후생", "월별 급여 계산 및 4대 보험 공제·납부 실무", "실무", ("이", "박")),
    ("TASK_HR_D07_T03", "인재육성·사내교육", "직급별·역할별 필수 역량 모델링 및 역량 강화 교육 기획", "실무", ("김", "이")),
    ("TASK_HR_D08_T05", "조직문화·사내소통", "조직문화 진단 설문(Pulse Survey) 설계 및 결과 분석", "관리자·심화", ("박", "홍")),
    ("TASK_HR_D09_T01", "노사관계·노무", "근로계약서·취업규칙 등 사규 제·개정 및 법적 리스크 검토", "입문", ("김", "박")),
    ("TASK_HR_D06_T05", "보상·급여·복리후생", "연말정산 실무 및 원천징수이행상황신고서 작성", "실무", ("이", "홍")),
]

holdout_rows = []
h_item_no = 1
for tid, domain, task_name, level, (r1, r2) in holdout_tasks_def:
    sub = df_rerank[(df_rerank["task_id"] == tid) & (df_rerank["level"] == level)].sort_values("rank").head(3)
    if len(sub) < 3:
        print(f"Warning: Holdout task {tid} has only {len(sub)} recommendations")
    for _, r_item in sub.iterrows():
        rk = int(r_item["rank"])
        c_uid = r_item["course_uid"]
        title, provider, url = get_course_info(c_uid)
        if not title:
            title = r_item.get("title", "")
        if not provider:
            provider = r_item.get("provider", "")
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
            })
        h_item_no += 1

df_holdout = pd.DataFrame(holdout_rows)
df_holdout.to_csv(HOLDOUT_OUT_PATH, index=False, encoding="utf-8-sig")
print(f"Holdout 파일 저장 완료: {HOLDOUT_OUT_PATH}")
print(f"  - 총 평가 항목 수(item_no): {h_item_no - 1}개 (총 평가 행: {len(df_holdout)}행)")
print(f"  - 평가자별 배정 건수:")
print(df_holdout["rater"].value_counts().to_string())

