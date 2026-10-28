"""
scripts/generate_30_review_sheet.py
인사·총무·경영지원 6개 시나리오 기반 30개 추천 항목 사람 검토표(Evaluation Sheet) 생성 스크립트
"""

import sys
from pathlib import Path
import pandas as pd
import json

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.assessment.evaluator import calculate_competency_scores, AssessmentEvaluationResult
from src.assessment.recommendation_bridge import get_recommendations_for_assessment, RecommendationFilterParams
from src.recommendation.ksa_master import KSA_COMPETENCIES_MASTER

def generate_review_sheet():
    out_dir = WORKSPACE_ROOT / "data" / "skills_taxonomy"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load cleaned courses to verify verbatim text exists
    p_courses = WORKSPACE_ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
    df_courses = pd.read_parquet(p_courses).set_index("course_uid")

    # Define 6 Scenarios across 3 Job Families (2 scenarios each)
    scenarios = [
        # HR Scenarios
        {
            "scenario_id": "SCENARIO_HR_01",
            "job_family": "인사",
            "name": "인사 실무자 채용 역량 집중 보완",
            "responses": {"Q_HR_01": 2, "Q_HR_02": 2, "Q_HR_03": 2, "Q_HR_04": 4, "Q_HR_05": 4, "Q_HR_06": 4, "Q_HR_07": 4, "Q_HR_08": 4, "Q_HR_09": 4},
            "targets": {"COMP_HR_01": 4.5, "COMP_HR_02": 4.0, "COMP_LABOR_01": 4.0},
            "user_tasks": ["TASK_HR_RECRUIT", "TASK_HR_ONBOARD"],
            "target_comp_id": "COMP_HR_01"
        },
        {
            "scenario_id": "SCENARIO_HR_02",
            "job_family": "인사",
            "name": "인사 실무자 성과평가·보상 및 노무 리스크 보완",
            "responses": {"Q_HR_01": 4, "Q_HR_02": 4, "Q_HR_03": 4, "Q_HR_04": 2, "Q_HR_05": 2, "Q_HR_06": 2, "Q_HR_07": 2, "Q_HR_08": 2, "Q_HR_09": 2},
            "targets": {"COMP_HR_01": 4.0, "COMP_HR_02": 4.5, "COMP_LABOR_01": 4.5},
            "user_tasks": ["TASK_HR_EVAL", "TASK_HR_COMP", "TASK_HR_LABOR_CONTRACT"],
            "target_comp_id": "COMP_HR_02"
        },
        # GA Scenarios
        {
            "scenario_id": "SCENARIO_GA_01",
            "job_family": "총무",
            "name": "총무 실무자 공문서·기획보고서 작성 역량 보완",
            "responses": {"Q_GA_01": 2, "Q_GA_02": 2, "Q_GA_03": 2, "Q_GA_04": 4, "Q_GA_05": 4, "Q_GA_06": 4, "Q_GA_07": 4, "Q_GA_08": 4},
            "targets": {"COMP_GA_01": 4.5, "COMP_GA_02": 3.5},
            "user_tasks": ["TASK_GA_DOC", "TASK_GA_REPORT"],
            "target_comp_id": "COMP_GA_01"
        },
        {
            "scenario_id": "SCENARIO_GA_02",
            "job_family": "총무",
            "name": "총무 실무자 사옥 시설·사무비품 및 고정자산 관리 보완",
            "responses": {"Q_GA_01": 4, "Q_GA_02": 4, "Q_GA_03": 4, "Q_GA_04": 2, "Q_GA_05": 2, "Q_GA_06": 2, "Q_GA_07": 2, "Q_GA_08": 2},
            "targets": {"COMP_GA_01": 3.5, "COMP_GA_02": 4.5},
            "user_tasks": ["TASK_GA_PURCHASE", "TASK_GA_ASSET", "TASK_GA_FACILITY"],
            "target_comp_id": "COMP_GA_02"
        },
        # MS Scenarios
        {
            "scenario_id": "SCENARIO_MS_01",
            "job_family": "경영지원",
            "name": "경영지원 비즈니스 소통 및 임원 의전 에티켓 보완",
            "responses": {"Q_MS_01": 2, "Q_MS_02": 2, "Q_MS_03": 2, "Q_MS_04": 4, "Q_MS_05": 4, "Q_MS_06": 4, "Q_MS_07": 4, "Q_MS_08": 4, "Q_MS_09": 4},
            "targets": {"COMP_SEC_01": 4.5, "COMP_MGMT_01": 3.5, "COMP_MGMT_02": 3.5},
            "user_tasks": ["TASK_MS_COMM", "TASK_MS_SCHEDULE"],
            "target_comp_id": "COMP_SEC_01"
        },
        {
            "scenario_id": "SCENARIO_MS_02",
            "job_family": "경영지원",
            "name": "경영지원 애자일 프로젝트 관리 및 기초 재무회계 보완",
            "responses": {"Q_MS_01": 4, "Q_MS_02": 4, "Q_MS_03": 4, "Q_MS_04": 2, "Q_MS_05": 2, "Q_MS_06": 2, "Q_MS_07": 2, "Q_MS_08": 2, "Q_MS_09": 2},
            "targets": {"COMP_SEC_01": 3.5, "COMP_MGMT_01": 4.5, "COMP_MGMT_02": 4.5},
            "user_tasks": ["TASK_MS_PROJECT", "TASK_MS_BUDGET"],
            "target_comp_id": "COMP_MGMT_01"
        }
    ]

    review_rows = []
    item_counter = 1

    for sc in scenarios:
        eval_res = calculate_competency_scores(
            job_family=sc["job_family"],
            responses=sc["responses"],
            target_levels=sc["targets"],
            user_task_ids=sc["user_tasks"]
        )

        bundle = get_recommendations_for_assessment(
            eval_result=eval_res,
            filter_params=RecommendationFilterParams(price_filter="ALL", edu_type="ALL"),
            top_n_per_comp=5
        )

        target_comp = sc["target_comp_id"]
        courses = bundle.courses_by_competency.get(target_comp, [])[:5]

        # If less than 5, pull from all courses deduped
        if len(courses) < 5:
            additional = [c for c in bundle.all_courses_deduped if c not in courses]
            courses.extend(additional[: 5 - len(courses)])

        for rank, card in enumerate(courses, 1):
            raw_course = df_courses.loc[card.course_uid] if card.course_uid in df_courses.index else None
            comp_master = KSA_COMPETENCIES_MASTER.get(target_comp, {})
            core_kws = comp_master.get("core_keywords", [])

            # Extract authentic verbatim excerpt from raw text
            raw_curric = str(raw_course.get("curriculum", "")).strip() if raw_course is not None else ""
            raw_intro = str(raw_course.get("course_intro", "")).strip() if raw_course is not None else ""
            raw_title = str(raw_course.get("title", "")).strip() if raw_course is not None else card.title

            verbatim_text = ""
            evidence_location = "UNAVAILABLE"

            if raw_curric and raw_curric != "None":
                curric_lines = [l.strip() for l in raw_curric.split("\n") if len(l.strip()) > 5 and not l.strip().startswith("| ---")]
                for kw in core_kws:
                    for cl in curric_lines:
                        if kw in cl:
                            verbatim_text = cl[:120]
                            evidence_location = "CURRICULUM"
                            break
                    if verbatim_text:
                        break
                if not verbatim_text and curric_lines:
                    verbatim_text = curric_lines[0][:120]
                    evidence_location = "CURRICULUM"

            if not verbatim_text and raw_intro and raw_intro != "None":
                intro_lines = [l.strip() for l in raw_intro.split("\n") if len(l.strip()) > 5]
                for kw in core_kws:
                    for il in intro_lines:
                        if kw in il:
                            verbatim_text = il[:120]
                            evidence_location = "INTRO"
                            break
                    if verbatim_text:
                        break
                if not verbatim_text and intro_lines:
                    verbatim_text = intro_lines[0][:120]
                    evidence_location = "INTRO"

            if not verbatim_text:
                verbatim_text = raw_title
                evidence_location = "TITLE"

            # Check verbatim presence in raw
            raw_full = f"{raw_curric} {raw_intro} {raw_title}"
            is_in_raw = (verbatim_text in raw_full)

            # Algorithmic Assessment against 6 criteria:
            matched_kws = [kw for kw in core_kws if kw in card.title or kw in raw_curric or kw in raw_intro]
            has_kw_match = len(matched_kws) > 0
            has_deep_curriculum = len(raw_curric) > 100
            is_domestic = card.provider in ["휴넷", "GSEEK", "한국능률협회(KMA)", "한국생산성본부(KPC)", "멀티캠퍼스", "고용24"]
            is_traceable = raw_course is not None and card.url.startswith("http")

            # Determine Automated Rule Verdict
            if has_kw_match and has_deep_curriculum and is_domestic and is_traceable:
                auto_verdict = "DIRECT"
                auto_rationale = f"핵심 키워드({', '.join(matched_kws[:3])})가 원문({evidence_location})에 실재하며, 상세 차시 목차(길이 {len(raw_curric)}자)가 존재하고 국내 실무 적용 가능성 및 원문 추적성이 확인됨."
            elif has_kw_match and is_domestic:
                auto_verdict = "PARTIAL"
                auto_rationale = f"직무 관련 핵심 키워드({', '.join(matched_kws[:2])})와 연계되나({evidence_location}), 커리큘럼 세부 목차가 다소 간략하여 개요 수준의 부분적 관련성으로 평가됨."
            elif not has_kw_match and is_domestic:
                auto_verdict = "INSUFFICIENT"
                auto_rationale = f"국내 직무 교육과정이나 본문({evidence_location}) 내 해당 역량과의 직접적인 키워드 및 행동 일치 근거가 다소 부족함."
            else:
                auto_verdict = "REJECTED"
                auto_rationale = "해당 KSA 역량의 실무 행동과 직접 연관되지 않는 비-직무성 강좌로 판정됨."

            review_rows.append({
                "item_no": item_counter,
                "scenario_id": sc["scenario_id"],
                "job_family": sc["job_family"],
                "scenario_name": sc["name"],
                "target_competency_id": target_comp,
                "target_competency_name": comp_master.get("name", ""),
                "rank": rank,
                "course_uid": card.course_uid,
                "course_title": card.title,
                "provider": card.provider,
                "price_display": card.price_display,
                "url": card.url,
                "evidence_location": evidence_location,
                "evidence_verbatim": verbatim_text,
                "is_evidence_in_raw": is_in_raw,
                "auto_preliminary_verdict": auto_verdict,
                "auto_rationale": auto_rationale,
                "review_status": "PENDING_HUMAN_REVIEW",
                # Empty fields for Human Expert Review
                "human_reviewer": "",
                "human_reviewed_at": "",
                "human_verdict": "",
                "human_review_note": ""
            })
            item_counter += 1

    df_sheet = pd.DataFrame(review_rows)
    csv_path = out_dir / "course_competency_30_review_sheet.csv"
    df_sheet.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Generate Markdown Evaluation Sheet
    md_path = out_dir / "course_competency_30_review_sheet.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 교육-역량 매핑 30선 사람 검토표 (Human Evaluation Sheet)\n\n")
        f.write("본 검토표는 인사, 총무, 경영지원 3대 직무군별 2개 시나리오(총 6개 시나리오)에서 도출된\n")
        f.write("상위 추천 강좌 각 5개씩, 총 30개 항목의 정합성을 사람 전문가가 직접 검증할 수 있도록 구성된 평가 시트입니다.\n\n")
        f.write("## 1. 6대 평가 기준\n")
        f.write("1. **학습내용 일치**: 교육의 주제와 내용이 대상 역량의 지식·기술과 부합하는가?\n")
        f.write("2. **실제 업무 행동 일치**: 사용자가 수행하는 실무 과업 행동을 지원하는가?\n")
        f.write("3. **내용의 깊이·비중**: 핵심 역량을 단편적으로 언급하는 수준을 넘어 충분한 차시 비중을 갖추었는가?\n")
        f.write("4. **대상·난이도**: 직무 재직자의 요구 수준(입문/실무)에 적절한가?\n")
        f.write("5. **국내 적용 가능성**: 국내 법규정 및 기업 실무 환경에 부합하는가?\n")
        f.write("6. **원문 추적 가능성**: 제공된 증거 발췌가 실제 크롤링 원문에 존재하며 바로가기 링크가 유효한가?\n\n")

        f.write("## 2. 판정 체계 원칙\n")
        f.write("- `DIRECT`: 직접 관련 (역량의 핵심 행동과 커리큘럼이 명확히 일치)\n")
        f.write("- `PARTIAL`: 부분 관련 (인접 스킬이거나 교양·개요 수준 포함)\n")
        f.write("- `INSUFFICIENT`: 근거 부족 (본문 설명이 빈약하여 정합성 입증 불가)\n")
        f.write("- `REJECTED`: 부적합 (해당 역량과 무관한 타 분야 과정 - *주의: 교육 자체의 삭제가 아니며 해당 역량-교육 관계에 대한 판정임*)\n\n")
        f.write("> **중요 알림**: 본 시트의 1차 판정(`auto_preliminary_verdict`)은 알고리즘에 의해 자동 제안된 초안이며,\n")
        f.write("> 현재 검토 상태는 `PENDING_HUMAN_REVIEW`(사람 검토 대기)입니다. 사람 전문가 검토 전까지 완료로 처리되지 않습니다.\n\n")

        f.write("## 3. 30선 검토 상세 목록\n\n")
        f.write("| 번호 | 직무 / 시나리오 | 대상 역량 | 순위 | 강좌명 (기관) | 원문 발췌 근거 | 자동 제안 판정 | 판정 사유 | 사람 검토 결과 (공란) |\n")
        f.write("| :---: | :--- | :--- | :---: | :--- | :--- | :---: | :--- | :---: |\n")
        for r in review_rows:
            f.write(f"| {r['item_no']} | {r['job_family']} ({r['scenario_id']}) | `{r['target_competency_name']}` | {r['rank']} | **[{r['course_title']}]({r['url']})**<br>({r['provider']}) | {r['evidence_verbatim']} | `{r['auto_preliminary_verdict']}` | {r['auto_rationale']} | `[검토자: ] [판정: ]` |\n")

    print(f"Generated 30 review items successfully: {csv_path} and {md_path}")
    return df_sheet

if __name__ == "__main__":
    generate_review_sheet()
