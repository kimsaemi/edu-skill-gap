# -*- coding: utf-8 -*-
"""
신규 13개 Domain · 57개 Task 개편안 비교 검증 및 시범 추천 파이프라인
"""

import sys
import os
import json
from pathlib import Path
from collections import Counter
import pandas as pd
import numpy as np

# Set stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.new_57_tasks_definition import NEW_TASKS_57
from src.recommendation.hr_task_catalog import (
    task_semantic_query,
    task_keyword_query,
    task_anchor_query,
    passes_task_gate,
    GENERIC_TASK_TOKENS
)
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender

LEVELS = ["입문", "실무", "관리자·심화"]

# Paths
LEGACY_CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
LEGACY_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"

# Target Output Paths
OUT_COMPARISON_CSV = ROOT / "domain_task_90_vs_57_comparison.csv"
OUT_DOMAIN_TASK_57_CSV = ROOT / "hr_domain_task_57_draft.csv"
OUT_KSA_57_CSV = ROOT / "hr_task_ksa_57_draft.csv"
OUT_REC_PILOT_CSV = ROOT / "hr_task_57_recommendation_pilot.csv"
OUT_REPORT_MD = ROOT / "hr_task_revision_impact_report.md"

def build_90_vs_57_comparison(legacy_tasks, new_tasks):
    """
    기존 90개 업무와 신규 57개 업무의 상세 매핑 비교표 생성
    """
    rows = []
    
    # 1. Map legacy 90 tasks to new tasks
    # Build reverse lookup from legacy task to new tasks
    legacy_to_new = {}
    for nt in new_tasks:
        for lt_id in nt.get("mapped_legacy_task_ids", []):
            legacy_to_new.setdefault(lt_id, []).append(nt)

    for lt in legacy_tasks:
        lt_id = lt["task_id"]
        mapped_nts = legacy_to_new.get(lt_id, [])
        
        if mapped_nts:
            for nt in mapped_nts:
                rows.append({
                    "legacy_domain_id": lt["domain_id"],
                    "legacy_domain_name": lt["domain_name"],
                    "legacy_task_id": lt["task_id"],
                    "legacy_task_name": lt["task_name"],
                    "new_domain_id": nt["domain_id"],
                    "new_domain_name": nt["domain_name"],
                    "new_task_id": nt["task_id"],
                    "new_task_name": nt["task_name"],
                    "change_type": nt["change_type"],
                    "change_reason": nt["change_reason"],
                    "mapping_confidence": nt["mapping_confidence"],
                    "human_review_required": nt["human_review_required"]
                })
        else:
            # Legacy tasks without direct mapped_legacy_task_ids
            # Analyze business context for absorption or legacy retention
            dom_id = lt["domain_id"]
            t_name = lt["task_name"]
            
            # Contextual mapping rules for remaining legacy tasks
            if dom_id == "DOM_01":
                target_new = "HR03-01"
                c_type = "기존에만 존재하는 업무"
                c_reason = "기존 인력기획 세부 과업(단위 모델링 등)으로 신규 HR03 상위 기획업무에 포괄 흡수되거나 실무 체크리스트로 기존 유지 권고"
            elif dom_id == "DOM_02":
                target_new = "HR02-01"
                c_type = "기존에만 존재하는 업무"
                c_reason = "기존 직무조직 세부 기법 과업으로 신규 HR02 직무/조직분석 상위 과업에 흡수 권고"
            elif dom_id == "DOM_03":
                target_new = "HR04-05"
                c_type = "기존에만 존재하는 업무"
                c_reason = "채용 운영 세부 절차(소싱, 인터뷰 운영)로서 신규 HR04 채용 관리 및 분석에 포괄 흡수 권고"
            elif dom_id == "DOM_04":
                target_new = "HR01-04"
                c_type = "기존에만 존재하는 업무"
                c_reason = "온보딩 세부 마일스톤(30-60-90 등) 실행 과업으로 신규 HR01 적응도 점검에 포괄 흡수 권고"
            elif dom_id == "DOM_05":
                target_new = "HR05-03"
                c_type = "기존에만 존재하는 업무"
                c_reason = "성과평가 운영 세부 절차(모니터링, 피드백 체계)로서 신규 HR05 평가 시행 및 관리에 포괄 흡수 권고"
            elif dom_id == "DOM_06":
                target_new = "HR06-02"
                c_type = "기존에만 존재하는 업무"
                c_reason = "보상 세부 분석(시장 벤치마킹, 인상률 시뮬레이션)으로 신규 HR06 보상 설계에 흡수 권고"
            elif dom_id == "DOM_07":
                target_new = "HR09-02"
                c_type = "기존에만 존재하는 업무"
                c_reason = "교육 세부 실행(강사 양성, LMS 운영 등)으로 신규 HR09 교육과정 기획 및 운영에 포괄 흡수 권고"
            elif dom_id == "DOM_08":
                target_new = "HR08-04"
                c_type = "기존에만 존재하는 업무"
                c_reason = "조직문화 개별 이벤트/소통 채널로 신규 HR08 조직문화 프로그램에 통합 흡수 권고"
            elif dom_id == "DOM_09":
                target_new = "HR07-03"
                c_type = "기존에만 존재하는 업무"
                c_reason = "노무 세부 점검 및 교섭 활동으로 신규 HR07 법령 준수 및 분쟁 예방에 포괄 흡수 권고"
            else:
                target_new = "-"
                c_type = "검토 필요"
                c_reason = "도메인 귀속 재검토 필요"

            rows.append({
                "legacy_domain_id": lt["domain_id"],
                "legacy_domain_name": lt["domain_name"],
                "legacy_task_id": lt["task_id"],
                "legacy_task_name": lt["task_name"],
                "new_domain_id": target_new.split("-")[0] if target_new != "-" else "-",
                "new_domain_name": next((nt["domain_name"] for nt in new_tasks if nt["domain_id"] == target_new.split("-")[0]), "-"),
                "new_task_id": target_new,
                "new_task_name": next((nt["task_name"] for nt in new_tasks if nt["task_id"] == target_new), "-"),
                "change_type": c_type,
                "change_reason": c_reason,
                "mapping_confidence": "Medium",
                "human_review_required": True
            })

    # 2. Add purely new tasks in 57 that have no legacy task mapped
    for nt in new_tasks:
        if nt["change_type"] == "신규 추가" or not nt.get("mapped_legacy_task_ids"):
            rows.append({
                "legacy_domain_id": "-",
                "legacy_domain_name": "-",
                "legacy_task_id": "-",
                "legacy_task_name": "-",
                "new_domain_id": nt["domain_id"],
                "new_domain_name": nt["domain_name"],
                "new_task_id": nt["task_id"],
                "new_task_name": nt["task_name"],
                "change_type": "신규 추가",
                "change_reason": nt["change_reason"],
                "mapping_confidence": "High",
                "human_review_required": False
            })

    df = pd.DataFrame(rows)
    return df

def build_draft_catalogs(new_tasks):
    # hr_domain_task_57_draft.csv
    domain_task_rows = []
    for t in new_tasks:
        domain_task_rows.append({
            "domain_id": t["domain_id"],
            "domain_name": t["domain_name"],
            "task_id": t["task_id"],
            "task_name": t["task_name"],
            "easy_description": t["easy_description"],
            "primary_comp_id": t["primary_comp_id"],
            "ncs_subcategory_code": t["ncs_subcategory_code"],
            "ncs_subcategory_name": t["ncs_subcategory_name"],
            "ncs_unit_code": t["ncs_unit_code"],
            "ncs_unit_name": t["ncs_unit_name"],
            "ncs_status": t["ncs_status"]
        })
    df_domain_task = pd.DataFrame(domain_task_rows)

    # hr_task_ksa_57_draft.csv
    comp_names = {
        "COMP_HR_01": "인력채용·육성",
        "COMP_HR_02": "인사평가·보상",
        "COMP_LABOR_01": "노무관리·근로관계"
    }
    ksa_rows = []
    for t in new_tasks:
        ksa_rows.append({
            "domain_id": t["domain_id"],
            "domain_name": t["domain_name"],
            "task_id": t["task_id"],
            "task_name": t["task_name"],
            "knowledge": t["knowledge"],
            "skill": t["skill"],
            "attitude": t["attitude"],
            "competency_id": t["primary_comp_id"],
            "competency_name": comp_names.get(t["primary_comp_id"], "기타"),
            "ncs_subcategory_code": t["ncs_subcategory_code"],
            "ncs_subcategory_name": t["ncs_subcategory_name"],
            "ncs_unit_code": t["ncs_unit_code"],
            "ncs_unit_name": t["ncs_unit_name"],
            "validation_status": t["ncs_status"]
        })
    df_ksa = pd.DataFrame(ksa_rows)

    return df_domain_task, df_ksa

def run_pilot_recommendations(new_tasks, engine):
    print("Running Unified Hybrid Recommendation Pilot for 57 tasks across 3 levels...")
    rec_rows = []

    for idx, t in enumerate(new_tasks, 1):
        sem_q = task_semantic_query(t)
        kw_q = task_keyword_query(t)
        anc_q = task_anchor_query(t)

        for level in LEVELS:
            df_rec, n_cand, *_ = engine.recommend(
                query=sem_q,
                keyword_query=kw_q,
                keyword_stopwords=GENERIC_TASK_TOKENS,
                anchor_query=anc_q,
                target_domain="인사",
                user_level=level,
                cluster_boost=0.0,
                filter_mismatch_109=True,
                top_n=25,
                mode="general"
            )

            # Apply gating safely
            if df_rec.empty:
                df_gated = pd.DataFrame()
            else:
                if "anchor_score" not in df_rec.columns:
                    df_rec["anchor_score"] = 0.0
                keep = [
                    passes_task_gate(s, a, f)
                    for s, a, f in zip(df_rec["semantic_score"], df_rec["anchor_score"], df_rec["field"])
                ]
                df_gated = df_rec[keep].head(3)

            for rank, (_, r) in enumerate(df_gated.iterrows(), 1):
                # Reason generation
                reason = (
                    f"[{r['provider']}] {level} 적합 과정. "
                    f"시맨틱 유사도 {r['semantic_score']:.1f}점 및 "
                    f"핵심어 매칭도 {r['bm25_score']:.1f}점 반영"
                )
                rec_rows.append({
                    "task_id": t["task_id"],
                    "domain_id": t["domain_id"],
                    "task_name": t["task_name"],
                    "level": level,
                    "rank": rank,
                    "course_uid": r["course_uid"],
                    "title": r["title"],
                    "provider": r.get("provider", ""),
                    "final_score": round(float(r["final_score"]), 1),
                    "semantic_score": round(float(r["semantic_score"]), 1),
                    "bm25_score": round(float(r["bm25_score"]), 1),
                    "anchor_score": round(float(r["anchor_score"]), 1),
                    "field": r.get("field", ""),
                    "price_display": r.get("price_display", "확인 필요"),
                    "duration_display": r.get("duration_display", "확인 필요"),
                    "url": r.get("url", ""),
                    "rec_reason": reason,
                    "n_candidates": n_cand
                })

        if idx % 10 == 0 or idx == len(new_tasks):
            print(f"  - Completed recommendations for {idx}/{len(new_tasks)} tasks")

    return pd.DataFrame(rec_rows)

def compare_rec_results(df_rec_57, legacy_rec_path):
    print("Comparing 57 pilot recommendation results with legacy 90 recommendations...")
    df_rec_90 = pd.read_csv(legacy_rec_path)
    
    # Analyze coverage
    req_slots = len(NEW_TASKS_57) * len(LEVELS) * 3 # 57 * 3 * 3 = 513
    actual_slots = len(df_rec_57)
    
    # Group by task_id and level
    slot_counts = df_rec_57.groupby(["task_id", "level"]).size().reset_index(name="count")
    thin_tasks = slot_counts[slot_counts["count"] < 3]
    missing_tasks = []
    
    for t in NEW_TASKS_57:
        tid = t["task_id"]
        for lv in LEVELS:
            sub = df_rec_57[(df_rec_57["task_id"] == tid) & (df_rec_57["level"] == lv)]
            if len(sub) == 0:
                missing_tasks.append((tid, t["task_name"], lv, 0))
            elif len(sub) < 3:
                missing_tasks.append((tid, t["task_name"], lv, len(sub)))

    # Semantic score distribution
    med_sem_57 = df_rec_57[df_rec_57["rank"] == 1]["semantic_score"].median()
    med_sem_90 = df_rec_90[df_rec_90["rank"] == 1]["semantic_score"].median()
    
    # Overlap of recommended course UIDs
    uids_57 = set(df_rec_57["course_uid"])
    uids_90 = set(df_rec_90["course_uid"])
    overlap_uids = uids_57.intersection(uids_90)
    new_distinct_courses = uids_57 - uids_90

    comp_summary = {
        "required_top3_slots": req_slots,
        "actual_recommended_slots": actual_slots,
        "fill_rate_percent": round(actual_slots / req_slots * 100, 1),
        "median_top1_semantic_57": float(med_sem_57),
        "median_top1_semantic_90": float(med_sem_90),
        "distinct_courses_57": len(uids_57),
        "distinct_courses_90": len(uids_90),
        "overlap_courses_count": len(overlap_uids),
        "newly_discovered_courses_count": len(new_distinct_courses),
        "thin_or_empty_slots_count": len(missing_tasks),
        "thin_tasks_details": missing_tasks
    }
    return comp_summary

def main():
    print("=== Starting 57-Task Revision & Pilot Recommendation Pipeline ===")
    
    # 1. Load legacy 90 tasks
    with open(LEGACY_CATALOG_PATH, "r", encoding="utf-8") as f:
        legacy_catalog = json.load(f)
    legacy_tasks = legacy_catalog["tasks"]
    print(f"Loaded {len(legacy_tasks)} legacy tasks.")
    print(f"Loaded {len(NEW_TASKS_57)} new tasks.")

    # 2. Build 90 vs 57 comparison
    df_comparison = build_90_vs_57_comparison(legacy_tasks, NEW_TASKS_57)
    df_comparison.to_csv(OUT_COMPARISON_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_COMPARISON_CSV.name} ({len(df_comparison)} rows)")

    # 3. Build Draft Catalogs
    df_domain_task_57, df_ksa_57 = build_draft_catalogs(NEW_TASKS_57)
    df_domain_task_57.to_csv(OUT_DOMAIN_TASK_57_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_DOMAIN_TASK_57_CSV.name} ({len(df_domain_task_57)} rows)")
    df_ksa_57.to_csv(OUT_KSA_57_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_KSA_57_CSV.name} ({len(df_ksa_57)} rows)")

    # 4. Initialize Recommender and Run Pilot
    engine = UnifiedHybridRecommender()
    df_rec_57 = run_pilot_recommendations(NEW_TASKS_57, engine)
    df_rec_57.to_csv(OUT_REC_PILOT_CSV, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_REC_PILOT_CSV.name} ({len(df_rec_57)} rows)")

    # 5. Compare with legacy recommendation
    comp_summary = compare_rec_results(df_rec_57, LEGACY_REC_PATH)

    print("\n=== Pilot Recommendation Summary ===")
    print(f"- Required Slots: {comp_summary['required_top3_slots']}")
    print(f"- Actual Recommended Slots: {comp_summary['actual_recommended_slots']} ({comp_summary['fill_rate_percent']}%)")
    print(f"- Top-1 Median Semantic Score: {comp_summary['median_top1_semantic_57']:.1f} (vs Legacy 90: {comp_summary['median_top1_semantic_90']:.1f})")
    print(f"- Distinct Courses: {comp_summary['distinct_courses_57']} (Overlap with 90: {comp_summary['overlap_courses_count']})")
    print(f"- Thin/Under-supplied Slots: {comp_summary['thin_or_empty_slots_count']}")

    # Save summary stats to a temporary json for report writing
    summary_path = ROOT / "data" / "hr" / "reports" / "revision_pilot_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(comp_summary, f, ensure_ascii=False, indent=2)
    print(f"Summary metrics saved to {summary_path.name}")

if __name__ == "__main__":
    main()
