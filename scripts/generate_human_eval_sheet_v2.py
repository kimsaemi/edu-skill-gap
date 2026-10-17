"""
scripts/generate_human_eval_sheet_v2.py
인사·총무·경영지원 6개 시나리오 기반 30개 추천 항목 '사람 평가표 (Human Evaluation Sheet v2)' 생성
- 이전 검토표(course_competency_30_review_sheet.*) 보존
- 안정적인 evaluation_id (EVAL_01 ~ EVAL_30) 부여
- 개정된 판정 기준 적용:
  * DIRECT: 목표 업무를 핵심 내용으로 직접 다룸
  * PARTIAL: 관련 내용 일부만 다룸
  * INSUFFICIENT: 정보 부족으로 관련성 판단 불가
  * REJECTED: 확인한 내용이 목표 업무와 맞지 않음
  * 주의: 분야 이름(IT, 경영 등)만으로 예단하지 말고 실제 커리큘럼 목차를 보고 판정
- A/B 평가자 독립 평가를 위해 상대 판정을 볼 수 없는 개별 파일 생성:
  * reviewer_A 파일: reviewer_B 판정/사유 컬럼 완전 제외
  * reviewer_B 파일: reviewer_A 판정/사유 컬럼 완전 제외
  * v2 마스터 템플릿 파일
"""
import sys
from pathlib import Path
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

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
            "scenario_name": "총무 실무자 공문서·기획보고서 및 사내 규정 체계화",
            "user_goal": "경영진 기획보고서 프레임워크 작성 및 사내 문서 규정 체계화",
            "responses": {"Q_GA_01": 2, "Q_GA_02": 2, "Q_GA_03": 2, "Q_GA_04": 4, "Q_GA_05": 4, "Q_GA_06": 4, "Q_GA_07": 4, "Q_GA_08": 4},
            "target_comp_id": "COMP_GA_01"
        },
        {
            "scenario_id": "SCEN_GA_02",
            "job_family": "총무",
            "scenario_name": "총무 실무자 자산관리 및 용역 계약·외주 구매 관리",
            "user_goal": "사옥 시설물 유지보수 및 용역계약 체결, 고정자산 실사 관리 역량 강화",
            "responses": {"Q_GA_01": 4, "Q_GA_02": 4, "Q_GA_03": 4, "Q_GA_04": 2, "Q_GA_05": 2, "Q_GA_06": 2, "Q_GA_07": 4, "Q_GA_08": 4},
            "target_comp_id": "COMP_GA_02"
        },
        # 경영지원 2개
        {
            "scenario_id": "SCEN_MGMT_01",
            "job_family": "경영지원",
            "scenario_name": "경영지원 실무자 경영계획 수립 및 재무제표 분석 역량",
            "user_goal": "사업계획서 작성, 손익분기점(BEP) 분석 및 재무제표 기본 분석 능력 배양",
            "responses": {"Q_MS_01": 4, "Q_MS_02": 4, "Q_MS_03": 4, "Q_MS_04": 4, "Q_MS_05": 4, "Q_MS_06": 4, "Q_MS_07": 2, "Q_MS_08": 2, "Q_MS_09": 2},
            "target_comp_id": "COMP_MGMT_02"
        },
        {
            "scenario_id": "SCEN_MGMT_02",
            "job_family": "경영지원",
            "scenario_name": "경영지원 실무자 애자일 프로젝트 관리 및 사내 갈등 조정",
            "user_goal": "협업 툴(노션, 지라) 기반 프로젝트 일정 관리 및 부서 간 협업 조율 능력 향상",
            "responses": {"Q_MS_01": 4, "Q_MS_02": 4, "Q_MS_03": 4, "Q_MS_04": 2, "Q_MS_05": 2, "Q_MS_06": 2, "Q_MS_07": 4, "Q_MS_08": 4, "Q_MS_09": 4},
            "target_comp_id": "COMP_MGMT_01"
        }
    ]

    all_rows = []
    item_no = 1

    for sc in scenarios:
        eval_res = calculate_competency_scores(
            job_family=sc["job_family"],
            responses=sc["responses"],
            learning_goal=sc["user_goal"]
        )

        filter_params = RecommendationFilterParams(
            price_filter="ALL",
            edu_type="ALL",
            weekly_hours=4.0
        )

        bundle = get_recommendations_for_assessment(
            eval_result=eval_res,
            filter_params=filter_params,
            recommender=engine,
            top_n_per_comp=5
        )

        t_comp = sc["target_comp_id"]
        cards = bundle.courses_by_competency.get(t_comp, [])
        if not cards:
            cards = bundle.all_courses_deduped[:5]
        else:
            cards = cards[:5]

        comp_name = KSA_COMPETENCIES_MASTER.get(t_comp, {}).get("name", t_comp)

        for rank, card in enumerate(cards, 1):
            eval_id = f"EVAL_{item_no:02d}"
            uid = card.course_uid
            is_premapped = (uid, t_comp) in ksa_pair_set
            mapping_basis = "기존 역량 연결 정보 기반" if is_premapped else "교육내용 검색으로 찾은 추가 후보"

            raw_c = df_courses.loc[uid] if uid in df_courses.index else None
            curric = str(raw_c.get("curriculum", "")).strip() if raw_c is not None else ""
            intro = str(raw_c.get("course_intro", "")).strip() if raw_c is not None else ""
            evidence = ""
            if curric and curric != "None":
                evidence = curric[:150].replace("\n", " ")
            elif intro and intro != "None":
                evidence = intro[:150].replace("\n", " ")
            else:
                evidence = card.title

            base_info = {
                "evaluation_id": eval_id,
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
            }
            all_rows.append(base_info)
            item_no += 1

    # 1. 마스터 데이터프레임 (Reviewer A & B 컬럼 모두 포함)
    master_rows = []
    for r in all_rows:
        row_copy = dict(r)
        row_copy["reviewer_A_verdict"] = ""
        row_copy["reviewer_A_rationale"] = ""
        row_copy["reviewer_B_verdict"] = ""
        row_copy["reviewer_B_rationale"] = ""
        row_copy["evaluation_status"] = "READY_FOR_HUMAN_EVALUATION"
        master_rows.append(row_copy)

    df_master = pd.DataFrame(master_rows)
    master_csv = out_dir / "human_evaluation_sheet_30_v2.csv"
    master_md = out_dir / "human_evaluation_sheet_30_v2.md"
    df_master.to_csv(master_csv, index=False, encoding="utf-8-sig")

    # 2. Reviewer A 독립 평가 데이터프레임 (Reviewer B 컬럼 배제)
    rows_A = []
    for r in all_rows:
        row_A = dict(r)
        row_A["reviewer_A_verdict"] = ""  # DIRECT / PARTIAL / INSUFFICIENT / REJECTED 중 기입
        row_A["reviewer_A_rationale"] = ""
        rows_A.append(row_A)
    df_A = pd.DataFrame(rows_A)
    csv_A = out_dir / "human_evaluation_sheet_30_reviewer_A.csv"
    md_A = out_dir / "human_evaluation_sheet_30_reviewer_A.md"
    df_A.to_csv(csv_A, index=False, encoding="utf-8-sig")

    # 3. Reviewer B 독립 평가 데이터프레임 (Reviewer A 컬럼 배제)
    rows_B = []
    for r in all_rows:
        row_B = dict(r)
        row_B["reviewer_B_verdict"] = ""  # DIRECT / PARTIAL / INSUFFICIENT / REJECTED 중 기입
        row_B["reviewer_B_rationale"] = ""
        rows_B.append(row_B)
    df_B = pd.DataFrame(rows_B)
    csv_B = out_dir / "human_evaluation_sheet_30_reviewer_B.csv"
    md_B = out_dir / "human_evaluation_sheet_30_reviewer_B.md"
    df_B.to_csv(csv_B, index=False, encoding="utf-8-sig")

    # 가이드 텍스트 공통 작성 함수
    def write_eval_markdown(path, rows_data, reviewer_name=None):
        with open(path, "w", encoding="utf-8") as f:
            title_suffix = f" - {reviewer_name} 독립 평가용" if reviewer_name else " (Master Template)"
            f.write(f"# 교육 추천 결과 사람 평가표 (Evaluation Sheet v2){title_suffix}\n\n")
            f.write("> **안내**: 본 검토표는 Customer MVP 시험 운영을 위해 인사·총무·경영지원 6개 시나리오에서 도출된 30개 추천 항목입니다.\n")
            f.write("> 각 항목에 대해 독립적으로 원문 URL과 커리큘럼 근거를 확인하고 아래 기준에 따라 판정과 사유를 직접 기입합니다.\n\n")
            f.write("### 판정 기준 가이드\n")
            f.write("- **DIRECT**: 목표 업무를 핵심 내용으로 직접 다룸\n")
            f.write("- **PARTIAL**: 관련 내용 일부만 다룸\n")
            f.write("- **INSUFFICIENT**: 정보 부족으로 관련성 판단 불가\n")
            f.write("- **REJECTED**: 확인한 내용이 목표 업무와 맞지 않음\n\n")
            f.write("> ⚠️ **평가 시 주의 사항**: 분야 이름(IT, 경영, 어학 등)이나 강좌명만으로 예단하여 판정하지 마십시오. 반드시 실제 커리큘럼 목차와 내용을 확인하여 사용자의 목표 업무에 실질적으로 부합하는지를 객관적으로 판정합니다.\n\n")
            f.write("---\n\n")

            for r in rows_data:
                f.write(f"### [{r['evaluation_id']}] {r['scenario_id']} - {r['target_competency_name']} ({r['rank']}순위)\n")
                f.write(f"- **사용자 목표**: {r['user_goal']}\n")
                f.write(f"- **추천 교육과정**: **{r['course_title']}** ({r['provider']} | {r['price_display']} | {r['duration_display']} | {r['education_type']})\n")
                f.write(f"- **원문 링크**: [{r['course_url']}]({r['course_url']})\n")
                f.write(f"- **매핑 구분**: `{r['mapping_basis']}` *(사람 검토 완료 아님)*\n")
                f.write(f"- **원문 내용 발췌**: {r['curriculum_evidence']}\n\n")

                if reviewer_name == "Reviewer A":
                    f.write("| 평가자 | 판정 (DIRECT / PARTIAL / INSUFFICIENT / REJECTED) | 검토 이유 및 피드백 |\n")
                    f.write("|---|---|---|\n")
                    f.write("| **Reviewer A** | *(미작성 - 직접 입력)* | *(미작성 - 직접 입력)* |\n\n")
                elif reviewer_name == "Reviewer B":
                    f.write("| 평가자 | 판정 (DIRECT / PARTIAL / INSUFFICIENT / REJECTED) | 검토 이유 및 피드백 |\n")
                    f.write("|---|---|---|\n")
                    f.write("| **Reviewer B** | *(미작성 - 직접 입력)* | *(미작성 - 직접 입력)* |\n\n")
                else:
                    f.write("| 평가자 | 판정 (DIRECT / PARTIAL / INSUFFICIENT / REJECTED) | 검토 이유 및 피드백 |\n")
                    f.write("|---|---|---|\n")
                    f.write("| **Reviewer A** | *(미작성 - 직접 입력)* | *(미작성 - 직접 입력)* |\n")
                    f.write("| **Reviewer B** | *(미작성 - 직접 입력)* | *(미작성 - 직접 입력)* |\n\n")

    write_eval_markdown(master_md, all_rows, reviewer_name=None)
    write_eval_markdown(md_A, rows_A, reviewer_name="Reviewer A")
    write_eval_markdown(md_B, rows_B, reviewer_name="Reviewer B")

    print(f"Generated Master: {master_csv} & {master_md}")
    print(f"Generated Reviewer A: {csv_A} & {md_A}")
    print(f"Generated Reviewer B: {csv_B} & {md_B}")

if __name__ == "__main__":
    generate_v2_sheet()
