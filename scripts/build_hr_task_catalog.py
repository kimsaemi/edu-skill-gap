"""
팀 v2.1 대시보드의 인사 세부 업무(Task) 90개를 고객용 서비스 데이터로 변환하고,
Task별 추천 교육을 하이브리드 추천 엔진으로 다시 계산합니다.

입력: hr_career_platform_v2.1_criteria.html (팀원 작성 대시보드, 내장 DATA.domains[].tasks)
출력:
  - data/hr/processed/hr_task_catalog_90.json
        Task 메타데이터 (분야, 단계, KSA, 숙련도 4단계, 직급별 역할, 연결 역량)
  - data/hr/output/recommendation/task_course_recommendations_90.csv
        Task × 숙련도(입문/실무/관리자·심화)별 추천 교육 Top 5 (엔진 점수 포함)
  - data/hr/output/recommendation/task_course_recommendations_90_summary.json
        커버리지·중복 사용 점검 요약

역량 연결 방식:
  Task 설명(업무명·쉬운 설명·K·S)과 인사 3대 역량 정의의 Ko-SRoBERTa 코사인 유사도에
  분야별 기본 연결(+0.05)을 더해 가장 가까운 역량에 연결합니다. 1·2위 차이가 작은 Task는
  needs_review=True로 표시합니다 (사람 검토 권장).

실행: python scripts/build_hr_task_catalog.py "C:/Users/.../hr_career_platform_v2.1_criteria.html"
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.recommendation.ksa_master import get_competency_by_id  # noqa: E402
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender  # noqa: E402

CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"
SUMMARY_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_summary.json"

HR_COMPETENCIES = ["COMP_HR_01", "COMP_HR_02", "COMP_LABOR_01"]
# 분야별 기본 연결 역량 (인력 수급·채용·온보딩 → 채용 / 직무·평가·보상 → 평가보상 / 노사 → 노무)
DOMAIN_PRIOR = {
    "DOM_01": "COMP_HR_01", "DOM_03": "COMP_HR_01", "DOM_04": "COMP_HR_01",
    "DOM_02": "COMP_HR_02", "DOM_05": "COMP_HR_02", "DOM_06": "COMP_HR_02",
    "DOM_09": "COMP_LABOR_01",
}
PRIOR_BONUS = 0.05
REVIEW_MARGIN = 0.03
LEVELS = ["입문", "실무", "관리자·심화"]
GRADE_NAMES = ["주임", "대리", "과장", "차장", "부장"]


def load_v21_data(html_path: Path) -> dict:
    html = html_path.read_text(encoding="utf-8")
    m = re.search(r"const DATA\s*=\s*", html)
    if not m:
        raise ValueError("DATA 객체를 찾을 수 없습니다.")
    data, _ = json.JSONDecoder().raw_decode(html[m.end():])
    return data


def build_catalog(data: dict) -> list:
    tasks = []
    for dom in data["domains"]:
        dom_num = dom["id"].split("_")[1]
        for t in dom.get("tasks", []):
            t_num = t["id"].split("_")[-1]
            roles = t.get("roles") or []
            tasks.append({
                "task_id": f"TASK_HR_D{dom_num}_{t_num}",
                "source_task_id": t["id"],
                "domain_id": dom["id"],
                "domain_name": dom.get("short", ""),
                "domain_full_name": dom.get("full", ""),
                "stage": t.get("stage", ""),
                "task_name": t["name"],
                "easy_description": t.get("easy", ""),
                "knowledge": t.get("k", ""),
                "skill": t.get("s", ""),
                "attitude": t.get("a", ""),
                "proficiency_levels": t.get("levels", []),
                "roles_by_grade": [
                    {"grade": GRADE_NAMES[i] if i < len(GRADE_NAMES) else str(i), "badge": r.get("badge", ""), "role": r.get("role", "")}
                    for i, r in enumerate(roles)
                ],
                "source": "팀 v2.1 대시보드 인사 세부 업무 초안 (NCS 공식 능력단위 아님)",
            })
    return tasks


from src.recommendation.hr_task_catalog import task_semantic_query as task_semantic_text  # noqa: E402
from src.recommendation.hr_task_catalog import task_keyword_query as task_keyword_text  # noqa: E402
from src.recommendation.hr_task_catalog import (  # noqa: E402
    GENERIC_TASK_TOKENS, passes_task_gate, task_anchor_query,
)


def map_competencies(tasks: list, model) -> None:
    comp_texts = []
    for cid in HR_COMPETENCIES:
        c = get_competency_by_id(cid)
        comp_texts.append(f"{c['name']}. {c['definition']} 지식: {c['knowledge']} 기술: {c['skill']}")
    comp_vecs = model.encode(comp_texts, normalize_embeddings=True)
    task_vecs = model.encode([task_semantic_text(t) for t in tasks], normalize_embeddings=True)
    sims = task_vecs @ comp_vecs.T
    for t, row in zip(tasks, sims):
        adjusted = row.copy()
        prior = DOMAIN_PRIOR.get(t["domain_id"])
        if prior:
            adjusted[HR_COMPETENCIES.index(prior)] += PRIOR_BONUS
        order = np.argsort(-adjusted)
        best, second = order[0], order[1]
        cid = HR_COMPETENCIES[best]
        t["primary_comp_id"] = cid
        t["primary_comp_name"] = get_competency_by_id(cid)["name"]
        t["ncs_unit_code"] = get_competency_by_id(cid)["ncs_unit_code"]
        t["comp_similarity"] = {HR_COMPETENCIES[i]: round(float(row[i]), 4) for i in range(len(HR_COMPETENCIES))}
        t["comp_mapping_margin"] = round(float(adjusted[best] - adjusted[second]), 4)
        t["needs_review"] = bool(adjusted[best] - adjusted[second] < REVIEW_MARGIN)
        t["comp_mapping_method"] = "Ko-SRoBERTa 유사도 + 분야 기본 연결(+0.05)" if prior else "Ko-SRoBERTa 유사도"


def recommend_for_tasks(tasks: list, engine: UnifiedHybridRecommender) -> pd.DataFrame:
    rows = []
    for i, t in enumerate(tasks, 1):
        for level in LEVELS:
            df, n_cand, *_ = engine.recommend(
                query=task_semantic_text(t),
                keyword_query=task_keyword_text(t),
                keyword_stopwords=GENERIC_TASK_TOKENS,
                anchor_query=task_anchor_query(t),
                target_domain="인사",
                user_level=level,
                cluster_boost=0.0,
                filter_mismatch_109=True,
                top_n=25,
                mode="general",
            )
            keep = [passes_task_gate(s, a, f) for s, a, f in zip(df["semantic_score"], df["anchor_score"], df["field"])]
            df = df[keep].head(5)
            for rank, (_, r) in enumerate(df.iterrows(), 1):
                rows.append({
                    "task_id": t["task_id"],
                    "domain_id": t["domain_id"],
                    "task_name": t["task_name"],
                    "level": level,
                    "rank": rank,
                    "course_uid": r["course_uid"],
                    "title": r["title"],
                    "provider": r.get("provider", ""),
                    "final_score": r["final_score"],
                    "semantic_score": r["semantic_score"],
                    "bm25_score": r["bm25_score"],
                    "level_bonus": r["level_bonus"],
                    "anchor_score": r["anchor_score"],
                    "field": r["field"],
                    "n_candidates": n_cand,
                })
        if i % 10 == 0:
            print(f"  - {i}/{len(tasks)} Task 계산 완료")
    return pd.DataFrame(rows)


def summarize(tasks: list, rec: pd.DataFrame) -> dict:
    top3 = rec[rec["rank"] <= 3]
    use = Counter(top3["course_uid"])
    per_task_level = top3.groupby(["task_id", "level"]).size()
    title_of = dict(zip(rec["course_uid"], rec["title"]))
    return {
        "task_count": len(tasks),
        "comp_distribution": dict(Counter(t["primary_comp_id"] for t in tasks)),
        "needs_review_count": sum(t["needs_review"] for t in tasks),
        "needs_review_tasks": [t["task_id"] + " " + t["task_name"] for t in tasks if t["needs_review"]],
        "top3_slots": int(len(top3)),
        "top3_distinct_courses": len(use),
        "top3_most_reused": [{"title": title_of[u], "count": n} for u, n in use.most_common(10)],
        "task_level_with_lt3_results": int((per_task_level < 3).sum()) + (len(tasks) * len(LEVELS) - len(per_task_level)),
        "top1_semantic_score_median": float(rec[rec["rank"] == 1]["semantic_score"].median()),
        "top1_semantic_score_min": float(rec[rec["rank"] == 1]["semantic_score"].min()),
        "low_confidence_tasks": sorted(set(rec[(rec["rank"] == 1) & (rec["semantic_score"] < 45)]["task_id"])),
        "note": ("합성 리뷰·평점은 사용하지 않았습니다. 점수 = 의미 유사도 50% + BM25 35%(범용 단어 제외, 업무명 핵심어 보정) "
                 "+ 난이도 적합 보너스. 노출 기준 = 의미 유사도 50 이상, 핵심어 1점 이상 또는 유사도 72 이상, "
                 "분야가 다른 강좌(개발·마케팅·의료·특허·생산·어학)는 핵심어 2점 이상"),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    data = load_v21_data(Path(sys.argv[1]))
    tasks = build_catalog(data)
    print(f"1. Task {len(tasks)}개 추출")

    engine = UnifiedHybridRecommender()
    if not (engine.has_embeddings and engine.model is not None):
        print("[FAIL] 임베딩 모델을 불러오지 못했습니다.")
        return 1

    map_competencies(tasks, engine.model)
    print("2. 역량 연결: " + str(dict(Counter(t["primary_comp_id"] for t in tasks))))

    print("3. Task × 숙련도별 추천 계산 중...")
    rec = recommend_for_tasks(tasks, engine)

    CATALOG_PATH.write_text(json.dumps({"version": "v2.1-import-1", "tasks": tasks}, ensure_ascii=False, indent=1), encoding="utf-8")
    rec.to_csv(REC_PATH, index=False, encoding="utf-8-sig")
    summary = summarize(tasks, rec)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"4. 저장 완료\n   {CATALOG_PATH}\n   {REC_PATH}\n   {SUMMARY_PATH}")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
