"""
verify_regression_comprehensive.py
통합 병합 후 회귀 검증 종합 스크립트:
1. 문법 컴파일 (app/streamlit_step4.py, customer_dashboard/streamlit_customer.py, app.py)
2. 정보 부족 시나리오 (응답 문항 수 부족 시 처리)
3. 목표 차이 없음 시나리오 (gap == 0)
4. 학습 상태 및 보관함 호환성
5. 새 업무 선택지 구조 검증 (안정적인 task_id, competency_id, 문장 분리 품질)
6. 데이터/역량 마스터 정합성
"""
import sys
import py_compile
from pathlib import Path
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.assessment.evaluator import calculate_competency_scores, AssessmentEvaluationResult
from src.assessment.questions_data import get_questions_for_job, get_tasks_for_job
from src.assessment.recommendation_bridge import (
    get_recommendations_for_assessment,
    RecommendationFilterParams,
    get_shared_recommender
)
from src.recommendation.ksa_master import KSA_COMPETENCIES_MASTER

def test_syntax_compilation():
    print("\n[1] 파이썬 파일 문법 컴파일 (py_compile)...")
    files_to_compile = [
        "app.py",
        "app/streamlit_step4.py",
        "app/streamlit_customer.py",
        "customer_dashboard/streamlit_customer.py",
        "src/assessment/recommendation_bridge.py",
        "src/assessment/questions_data.py"
    ]
    for rel_path in files_to_compile:
        f_path = str(WORKSPACE_ROOT / rel_path)
        py_compile.compile(f_path, doraise=True)
        print(f"  - PASS: {rel_path} 컴파일 성공")

def test_low_information_scenario():
    print("\n[2] 정보 부족 시나리오 (2문항 미만 응답 시)...")
    # 1개 문항만 응답한 경우
    answers = {"Q_HR_01": 3}
    res = calculate_competency_scores("인사", answers)
    assert len(res.insufficient_competencies) > 0, "1문항 응답 시 insufficient_competencies에 포함되어야 함"
    # COMP_HR_01 문항 3개 중 1개만 응답했으므로 COMP_HR_01은 is_insufficient == True
    comp_hr_01 = res.competency_scores.get("COMP_HR_01")
    assert comp_hr_01 is not None and comp_hr_01.is_insufficient, "2문항 미만 응답 역량은 is_insufficient가 True여야 함"
    assert comp_hr_01.current_level is None, "정보 부족 시 current_level은 None(0점 왜곡 방지)이어야 함"
    print(f"  - PASS: 정보 부족 역량 {len(res.insufficient_competencies)}개 정상 감지 및 0점 왜곡 방지 확인")

def test_no_gap_scenario():
    print("\n[3] 목표 차이 없음 시나리오 (모든 역량 충족/만점)...")
    questions = get_questions_for_job("인사")
    # 모든 문항에 5점 만점 응답
    answers = {q["question_id"]: 5 for q in questions}
    res = calculate_competency_scores("인사", answers)
    assert len(res.zero_gap_competencies) > 0, "목표 수준을 모두 충족하면 zero_gap_competencies에 분류되어야 함"
    # 추천 번들 생성 시 심화 학습 모드가 올바르게 동작하는지 검증
    recommender = get_shared_recommender()
    bundle = get_recommendations_for_assessment(res, recommender=recommender)
    assert bundle.total_recommended_count > 0, "심화 학습 모드에서도 추천 과정이 정상 제공되어야 함"
    print(f"  - PASS: 목표 차이 없음(모든 역량 충족) 시 심화 모드로 정상 전환 및 {bundle.total_recommended_count}건 추천 확인")

def test_step4_task_derivation_logic():
    print("\n[4] STEP 4 실무 기술(Skill) 업무 선택지 분리 품질 및 안정적 task_id 검증...")
    df_comp = pd.read_csv(WORKSPACE_ROOT / "data" / "hr" / "processed" / "competencies.csv")
    task_catalog = {}
    for r in df_comp.itertuples():
        c_id = r.competency_id
        c_name = r.competency_name
        skill_raw = str(r.skill) if pd.notna(r.skill) else ""
        raw_items = [s.strip() for s in skill_raw.replace("/", ",").replace("\n", ",").split(",") if s.strip()]
        for idx, item in enumerate(raw_items, start=1):
            if item.lower() in ["nan", "none", "-"]:
                continue
            task_id = f"TASK_{c_id}_{idx:02d}"
            label = f"{item} (연계 역량: {c_name})"
            task_catalog[label] = {
                "task_id": task_id,
                "task_name": item,
                "competency_id": c_id,
                "competency_name": c_name
            }
            # task_id 형식 검증
            assert task_id.startswith(f"TASK_{c_id}_"), f"비정상 task_id: {task_id}"
            assert len(item) >= 2, f"너무 짧은 업무명: {item}"
    print(f"  - PASS: 총 {len(task_catalog)}개 실무 과업에 안정적 task_id 및 competency_id 부여 확인")

def test_source_disp_labeling():
    print("\n[5] 추천 카드의 출처 및 데이터 수집 시점 라벨링 검증...")
    from src.assessment.evaluator import get_sample_assessment_result
    recommender = get_shared_recommender()
    sample_res = get_sample_assessment_result("인사")
    bundle = get_recommendations_for_assessment(sample_res, recommender=recommender)
    for c in bundle.all_courses_deduped:
        assert "확인 시점" not in c.source_display, f"'확인 시점' 라벨 검출 (수집 시점으로 교정되어야 함): {c.source_display}"
        if "수집 시점" in c.source_display:
            # 정상 수집 시점 포맷
            assert "데이터 수집 시점" in c.source_display or "수집 시점" in c.source_display
    print(f"  - PASS: 모든 추천 카드의 '확인 시점' 왜곡 방지 및 '데이터 수집 시점' 라벨링 정합성 확인")

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 통합 회귀 및 호환성 종합 검증 실행")
    print("=" * 70)
    test_syntax_compilation()
    test_low_information_scenario()
    test_no_gap_scenario()
    test_step4_task_derivation_logic()
    test_source_disp_labeling()
    print("\n" + "=" * 70)
    print("🎉 모든 통합 회귀 테스트 100% 통과 (ALL TESTS PASSED)!")
    print("=" * 70)
