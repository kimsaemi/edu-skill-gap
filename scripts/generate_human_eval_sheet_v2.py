"""
scripts/generate_human_eval_sheet_v2.py
인사·총무·경영지원 6개 시나리오 기반 30개 추천 항목 '사람 평가표 (Human Evaluation Sheet v2)' 생성
- 이전 검토표(course_competency_30_review_sheet.*) 보존
- 현재 커밋/추천 설정/매핑 구분(기존 역량 연결 vs 교육내용 검색) 반영
- 사용자 목표, 교육명, 역량, 원문 근거, URL, 매핑 구분 포함
- 판정(DIRECT/PARTIAL/INSUFFICIENT/REJECTED) 및 검토 사유는 사람이 입력하도록 공란 처리
- 두 평가자(Reviewer A, Reviewer B)가 독립적으로 작성할 수 있도록 컬럼 구성
"""
import sys
from pathlib import Path
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.assessment.evaluator import calculate_competency_scores, AssessmentEvaluationResult
from src.assessment.recommendation_bridge import get_recommendations_for_assessment, RecommendationFilterParams, get_shared_recommender
from src.recommendation.ksa_master import KSA_COMPETENCIES_MASTER

def generate_v2_sheet():
    out_dir = WORKSPACE_ROOT / "data" / "skills_taxonomy"
    out_dir.mkdir(parents=True, exist_ok=True)

    p_courses = WORKSPACE_ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
    df_courses = pd.read_parquet(p_courses).set_index("course_uid")

    engine = get_shared_recommender()
    ksa_pair_set = set(zip(engine.df_comp_long['course_uid'], engine.df_comp_long['competency_id'])) if not engine.df_comp_long.empty else set()

    scenarios = [
        # 인사 2개
        {
            "scenario_id": "SCEN_HR_01",
            "job_family": "인사",
            "scenario_name": "인사 실무자 채용·선발 및 온보딩 역량 보완",
            "user_goal": "구조화 면접 질문 설계 및 신규 입사자 온보딩 기획 능력 향상",
            "responses": {"Q_HR_01": 2, "Q_HR_02": 2, "Q_HR_03": 2, "Q_HR_04": 4, "Q_HR_05": 4, "Q_HR_06": 4, "Q_HR_07": 4, "Q_HR_08": 4, "Q_HR_09": 4},
            "target_comp_id": "COMP_HR_01"
        },
        {
            "scenario_id": "SCEN_HR_02",
            "job_family": "인사",
            "scenario_name": "인사 실무자 성과평가·보상 및 노무 리스크 관리",
            "user_goal": "KPI 지표 수립 및 근로기준법 준수, 취업규칙 개정 실무 보완",
            "responses": {"Q_HR_01": 4, "Q_HR_02": 4, "Q_HR_03": 4, "Q_HR_04": 2, "Q_HR_05": 2, "Q_HR_06": 2, "Q_HR_07": 2, "Q_HR_08": 2, "Q_HR_09": 2},
            "target_comp_id": "COMP_HR_02"
        },
        # 총무 2개
        {
            "scenario_id": "SCEN_GA_01",
            "job_family": "총무",
            "scenario_name": "총무 실무자 공문서·기획보고서 및 엑셀 데이터 운용",
            "user_goal": "경영진 기획보고서 프레임워크 작성 및 사내 문서 규정 체계화",
            "responses": {"Q_GA_01": 2, "Q_GA_02": 2, "Q_GA_03": 2, "Q_GA_04": 4, "Q_GA_05": 4, "Q_GA_06": 4, "Q_GA_07": 4, "Q_GA_08": 4},
            "target_comp_id": "COMP_GA_01"
        },
        {
            "scenario_id": "SCEN_GA_02",
            "job_family": "총무",
            "scenario_name": "총무 실무자 고정자산·사무비품 및 시설 안전관리",
            "user_goal": "비품 구매 계약 체결 및 고정자산 실사 대장 관리 역량 보완",
            "responses": {"Q_GA_01": 4, "Q_GA_02": 4, "Q_GA_03": 4, "Q_GA_04": 2, "Q_GA_05": 2, "Q_GA_06": 2, "Q_GA_07": 4, "Q_GA_08": 4},
            "target_comp_id": "COMP_GA_02"
        },
        # 경영지원 2개
        {
            "scenario_id": "SCEN_MS_01",
            "job_family": "경영지원",
            "scenario_name": "경영지원 실무자 비즈니스 매너 및 사내외 커뮤니케이션",
            "user_goal": "임원 의전, 부서 간 갈등 조정 및 비즈니스 이메일/대화법 개선",
            "responses": {"Q_MS_01": 2, "Q_MS_02": 2, "Q_MS_03": 2, "Q_MS_04": 4, "Q_MS_05": 4, "Q_MS_06": 4, "Q_MS_07": 4, "Q_MS_08": 4, "Q_MS_09": 4},
            "target_comp_id": "COMP_SEC_01"
        },
        {
            "scenario_id": "SCEN_MS_02",
            "job_family": "경영지원",
            "scenario_name": "경영지원 실무자 프로젝트 일정 관리 및 부서 협업",
            "user_goal": "WBS 작성, 애자일 칸반 보드 운용 및 프로젝트 리스크 관리 역량 확보",
            "responses": {"Q_MS_01": 4, "Q_MS_02": 4, "Q_MS_03": 4, "Q_MS_04": 2, "Q_MS_05": 2, "Q_MS_06": 2, "Q_MS_07": 4, "Q_MS_08": 4, "Q_MS_09": 4},
            "target_comp_id": "COMP_MGMT_01"
        }
    ]

    rows = []
    item_no = 1

    for sc in scenarios:
        res = calculate_competency_scores(
            job_family=sc["job_family"],
            responses=sc["responses"],
            learning_goal=sc["user_goal"]
        )
        bundle = get_recommendations_for_assessment(
            eval_result=res,
            filter_params=RecommendationFilterParams(price_filter="ALL", edu_type="ALL"),
            recommender=engine,
            top_n_per_comp=5
        )

        t_comp = sc["target_comp_id"]
        cards = bundle.courses_by_competency.get(t_comp, [])[:5]
        if len(cards) < 5:
            extras = [c for c in bundle.all_courses_deduped if c not in cards]
            cards.extend(extras[: 5 - len(cards)])

        comp_name = KSA_COMPETENCIES_MASTER.get(t_comp, {}).get("name", t_comp)

        for rank, card in enumerate(cards, start=1):
            raw_c = df_courses.loc[card.course_uid] if card.course_uid in df_courses.index else None
            is_pre = (card.course_uid, t_comp) in ksa_pair_set
            mapping_basis = "기존 역량 연결 정보 기반" if is_pre else "교육내용 검색으로 찾은 추가 후보"

            # 원문 발췌 근거
            curric = str(raw_c.get("curriculum", "")).strip() if raw_c is not None else ""
            intro = str(raw_c.get("course_intro", "")).strip() if raw_c is not None else ""
            evidence = ""
            if curric and curric != "None":
                evidence = curric[:150].replace("\n", " ")
            elif intro and intro != "None":
                evidence = intro[:150].replace("\n", " ")
            else:
                evidence = card.title

            rows.append({
                "item_no": item_no,
                "scenario_id": sc["scenario_id"],
                "job_family": sc["job_family"],
                "user_goal": sc["user_goal"],
                "target_competency_id": t_comp,
                "target_competency_name": comp_name,
                "rank": rank,
                "course_uid": card.course_uid,
                "course_title": card.title,
                "provider": card.provider,
                "price_display": card.price_display,
                "duration_display": card.duration_display,
                "education_type": card.education_type,
                "course_url": card.url,
                "mapping_basis": mapping_basis,
                "curriculum_evidence": evidence,
                # 평가자 A 판정 (사람 입력용 공란)
                "reviewer_A_verdict": "",  # DIRECT / PARTIAL / INSUFFICIENT / REJECTED 중 선택 입력
                "reviewer_A_rationale": "", # 평가 사유 직접 작성
                # 평가자 B 판정 (사람 입력용 공란)
                "reviewer_B_verdict": "",  # DIRECT / PARTIAL / INSUFFICIENT / REJECTED 중 선택 입력
                "reviewer_B_rationale": "", # 평가 사유 직접 작성
                # 최종 검토 상태
                "evaluation_status": "READY_FOR_HUMAN_EVALUATION"
            })
            item_no += 1

    df_out = pd.DataFrame(rows)
    csv_path = out_dir / "human_evaluation_sheet_30_v2.csv"
    md_path = out_dir / "human_evaluation_sheet_30_v2.md"

    df_out.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Generated CSV: {csv_path} ({len(df_out)} rows)")

    # Markdown export for review
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 교육 추천 결과 사람 평가표 (Evaluation Sheet v2)\n\n")
        f.write("> **안내**: 본 검토표는 Customer MVP 시험 운영을 위해 인사·총무·경영지원 6개 시나리오에서 도출된 30개 추천 항목입니다.\n")
        f.write("> 각 항목에 대해 독립된 두 평가자(Reviewer A, Reviewer B)가 원문 URL과 커리큘럼 근거를 확인하고 아래 기준에 따라 판정과 사유를 직접 기입합니다.\n\n")
        f.write("### 판정 기준 가이드\n")
        f.write("- **DIRECT**: 사용자 목표 및 역량 핵심 행동에 직접적으로 부합하는 실무 교육\n")
        f.write("- **PARTIAL**: 관련 역량 주제를 다루지만 기초 개요 수준이거나 부분적으로만 연계됨\n")
        f.write("- **INSUFFICIENT**: 일반 교양·시사이거나 해당 역량 행동을 실질적으로 다루지 못함\n")
        f.write("- **REJECTED**: 직무 범위 외 타 분야(IT 개발, 간호, 소방, 부동산 등) 강좌이거나 오매핑 강좌\n\n")
        f.write("---\n\n")

        for r in rows:
            f.write(f"### [항목 {r['item_no']:02d}] {r['scenario_id']} - {r['target_competency_name']} ({r['rank']}순위)\n")
            f.write(f"- **사용자 목표**: {r['user_goal']}\n")
            f.write(f"- **추천 교육과정**: **{r['course_title']}** ({r['provider']} | {r['price_display']} | {r['duration_display']} | {r['education_type']})\n")
            f.write(f"- **원문 링크**: [{r['course_url']}]({r['course_url']})\n")
            f.write(f"- **매핑 구분**: `{r['mapping_basis']}` *(사람 검토 완료 아님)*\n")
            f.write(f"- **원문 내용 발췌**: {r['curriculum_evidence']}\n\n")
            f.write("| 평가자 | 판정 (DIRECT / PARTIAL / INSUFFICIENT / REJECTED) | 검토 이유 및 피드백 |\n")
            f.write("|---|---|---|\n")
            f.write("| **Reviewer A** | *(미작성 - 사람 직접 입력)* | *(미작성 - 사람 직접 입력)* |\n")
            f.write("| **Reviewer B** | *(미작성 - 사람 직접 입력)* | *(미작성 - 사람 직접 입력)* |\n\n")

    print(f"Generated Markdown: {md_path}")

if __name__ == "__main__":
    generate_v2_sheet()
