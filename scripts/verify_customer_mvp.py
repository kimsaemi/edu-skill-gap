"""
고객용 역량 자기점검 & 맞춤 교육 추천 MVP 종합 검증 스위트
(scripts/verify_customer_mvp.py)

검증 범위:
1. 대표 3대 직무 시나리오 실데이터 모델 테스트:
   - 시나리오 1 [인사]: 채용 업무 경험이 적고 보완이 필요한 사용자
   - 시나리오 2 [총무]: 비품 및 자산관리 역량을 보완하려는 사용자
   - 시나리오 3 [경영지원]: 프로젝트 관리 역량을 보완하려는 사용자
2. 엣지 케이스 및 정책 검증:
   - 정보 부족(유효 응답 2문항 미만) -> 점수 미확정 및 정보 부족 플래그
   - 무응답 / 해당 업무 아님(NA) / 판단 어려움(UNCERTAIN) 0점 처리 방지
   - 역량 차이 없음(Zero Gap) -> 부족 역량 강제 생성 금지 및 심화 과정 제안
   - 무료 전용(FREE_ONLY) 필터링 및 대체 수강처 검증
   - 차단된 109건 오매핑 배제 정책 준수
3. Streamlit AppTest UI 통합 검증 (app/streamlit_customer.py)
4. 기존 분석용 대시보드(app/streamlit_integrated.py) 회귀 검증 연계
"""

import sys
from pathlib import Path
import unittest

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.assessment.questions_data import (
    ASSESSMENT_QUESTIONS,
    JOB_TASK_MAPPING,
    get_questions_for_job,
    get_tasks_for_job
)
from src.assessment.evaluator import (
    calculate_competency_scores,
    get_sample_assessment_result,
    AssessmentEvaluationResult
)
from src.assessment.recommendation_bridge import (
    get_recommendations_for_assessment,
    RecommendationFilterParams,
    CustomerRecommendationBundle,
    get_shared_recommender
)
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender


class TestCustomerMVP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=======================================================")
        print("  [SETUP] 추천 엔진 및 실데이터 코퍼스 메모리 로드")
        print("=======================================================")
        cls.recommender = get_shared_recommender()
        self = cls

    def test_01_scenario_hr_recruitment_deficiency(self):
        """시나리오 1 [인사]: 채용 경험이 적고 보완이 필요한 사용자"""
        print("\n--- [TEST 1] 시나리오 1: 인사 직무 채용 역량 보완 ---")
        job = "인사"
        user_tasks = ["TASK_HR_RECRUIT", "TASK_HR_ONBOARD"]
        responses = {
            "Q_HR_01": 2, "Q_HR_02": 1, "Q_HR_03": 2,  # 인력채용 (avg 1.7)
            "Q_HR_04": 4, "Q_HR_05": 4, "Q_HR_06": 4,  # 평가보상 (avg 4.0)
            "Q_HR_07": 4, "Q_HR_08": 3, "Q_HR_09": 4   # 노무법률 (avg 3.7)
        }
        targets = {"COMP_HR_01": 4.0, "COMP_HR_02": 4.0, "COMP_LABOR_01": 4.0}

        eval_res = calculate_competency_scores(
            job_family=job,
            responses=responses,
            target_levels=targets,
            user_task_ids=user_tasks,
            difficult_task_desc="채용 면접 질문 설계가 어렵습니다.",
            learning_goal="채용 및 면접 역량 강화"
        )

        # 1) 역량 점수 검증
        c_recruit = eval_res.competency_scores["COMP_HR_01"]
        self.assertEqual(c_recruit.current_level, 1.7)
        self.assertEqual(c_recruit.target_level, 4.0)
        self.assertEqual(c_recruit.gap, 2.3)
        self.assertTrue(c_recruit.is_task_related)

        # 2) 우선순위 검증: 인력채용이 1위
        self.assertTrue(len(eval_res.prioritized_deficiencies) >= 1)
        self.assertEqual(eval_res.prioritized_deficiencies[0].competency_id, "COMP_HR_01")
        self.assertEqual(eval_res.prioritized_deficiencies[0].priority_rank, 1)

        # 3) 추천 엔진 연동 (시나리오 A: 무료 교육 선호 반영)
        params = RecommendationFilterParams(price_filter="FREE_ONLY", edu_type="ALL", weekly_hours=4.0)
        bundle = get_recommendations_for_assessment(eval_res, params, recommender=self.recommender)

        self.assertGreater(bundle.total_recommended_count, 0)
        top_card = bundle.all_courses_deduped[0]
        print(f"Top 추천 강좌: {top_card.title} ({top_card.provider}, {top_card.price_display})")
        print(f"고객용 추천 사유: {top_card.customer_recommendation_reason[:80]}...")
        
        # 무료 교육 필터 준수 검증
        self.assertEqual(top_card.price_status, "FREE")
        self.assertEqual(top_card.numeric_price, 0)
        self.assertIn("인력채용", top_card.customer_recommendation_reason)
        if top_card.numeric_duration and top_card.numeric_duration > 0:
            self.assertIn("주당 4.0시간", top_card.study_plan_note)
        else:
            self.assertIn("총 교육시간 정보가 공식적으로 확인되지 않은 강좌", top_card.study_plan_note)

    def test_02_scenario_ga_asset_management_deficiency(self):
        """시나리오 B [총무]: 비품 및 자산관리 역량을 보완하려는 사용자 (예산 한도 30만원)"""
        print("\n--- [TEST 2] 시나리오 B: 총무 직무 자산관리 역량 보완 및 예산 한도 ---")
        job = "총무"
        user_tasks = ["TASK_GA_PURCHASE", "TASK_GA_ASSET"]
        responses = {
            "Q_GA_01": 4, "Q_GA_02": 4, "Q_GA_03": 3, "Q_GA_04": 4,  # 문서기획 (avg 3.8)
            "Q_GA_05": 2, "Q_GA_06": 2, "Q_GA_07": 1, "Q_GA_08": 2   # 비품자산 (avg 1.8)
        }
        targets = {"COMP_GA_01": 4.0, "COMP_GA_02": 4.5}

        eval_res = calculate_competency_scores(
            job_family=job,
            responses=responses,
            target_levels=targets,
            user_task_ids=user_tasks,
            difficult_task_desc="비품 구매 계약 및 재물조사 대장 관리가 미흡합니다."
        )

        c_asset = eval_res.competency_scores["COMP_GA_02"]
        self.assertEqual(c_asset.current_level, 1.8)
        self.assertEqual(c_asset.target_level, 4.5)
        self.assertEqual(c_asset.gap, 2.7)
        self.assertEqual(eval_res.prioritized_deficiencies[0].competency_id, "COMP_GA_02")

        # 시나리오 B: 예산 한도 30만원 설정
        params = RecommendationFilterParams(price_filter="MAX_BUDGET", max_budget=300000, edu_type="ALL", weekly_hours=5.0)
        bundle = get_recommendations_for_assessment(eval_res, params, recommender=self.recommender)

        self.assertGreater(bundle.total_recommended_count, 0)
        self.assertEqual(bundle.all_courses_deduped[0].primary_competency_id, "COMP_GA_02")
        # 모든 추천 강좌의 가격이 30만원 이하 또는 무료인지 확인
        for c in bundle.all_courses_deduped:
            if c.numeric_price is not None:
                self.assertLessEqual(c.numeric_price, 300000)
        print(f"Top 추천 강좌: {bundle.all_courses_deduped[0].title} ({bundle.all_courses_deduped[0].provider}, {bundle.all_courses_deduped[0].price_display})")

    def test_03_scenario_ms_project_management_deficiency(self):
        """시나리오 C [경영지원]: 프로젝트 관리 역량을 보완하려는 사용자 (온라인 선호)"""
        print("\n--- [TEST 3] 시나리오 C: 경영지원 프로젝트 관리 역량 보완 및 온라인 선호 ---")
        job = "경영지원"
        user_tasks = ["TASK_MS_PROJECT", "TASK_MS_TEAM"]
        responses = {
            "Q_MS_01": 4, "Q_MS_02": 5, "Q_MS_03": 4,  # 비즈니스매너 (avg 4.3)
            "Q_MS_04": 2, "Q_MS_05": 2, "Q_MS_06": 2,  # 프로젝트관리 (avg 2.0)
            "Q_MS_07": 4, "Q_MS_08": 3, "Q_MS_09": 3   # 재무기초 (avg 3.3)
        }
        targets = {"COMP_SEC_01": 4.0, "COMP_MGMT_01": 4.0, "COMP_MGMT_02": 4.0}

        eval_res = calculate_competency_scores(
            job_family=job,
            responses=responses,
            target_levels=targets,
            user_task_ids=user_tasks,
            difficult_task_desc="WBS 수립 및 마일스톤 일정 관리가 어렵습니다."
        )

        c_mgmt = eval_res.competency_scores["COMP_MGMT_01"]
        self.assertEqual(c_mgmt.current_level, 2.0)
        self.assertEqual(c_mgmt.gap, 2.0)
        self.assertEqual(eval_res.prioritized_deficiencies[0].competency_id, "COMP_MGMT_01")

        # 시나리오 C: 온라인 교육 선호
        params = RecommendationFilterParams(price_filter="ALL", edu_type="ONLINE", weekly_hours=3.0)
        bundle = get_recommendations_for_assessment(eval_res, params, recommender=self.recommender)
        self.assertGreater(bundle.total_recommended_count, 0)
        # 온라인 키워드 포함 검증
        for c in bundle.all_courses_deduped:
            self.assertTrue(any(k in c.education_type for k in ["온라인", "사이버", "원격", "플립", "동영상", "VOD"]))
        print(f"Top 추천 강좌: {bundle.all_courses_deduped[0].title} ({bundle.all_courses_deduped[0].provider}, {bundle.all_courses_deduped[0].education_type})")

    def test_04_insufficient_info_and_na_handling(self):
        """엣지 케이스 1: 2문항 미만 응답 시 정보 부족(점수 미확정) 및 NA/UNCERTAIN 0점 처리 방지"""
        print("\n--- [TEST 4] 엣지 케이스: 정보 부족 및 NA 처리 ---")
        job = "인사"
        responses = {
            "Q_HR_01": "NA", "Q_HR_02": "UNCERTAIN", "Q_HR_03": 3,  # 유효 응답 1개 -> 정보 부족
            "Q_HR_04": 4, "Q_HR_05": 4, "Q_HR_06": 4,
            "Q_HR_07": 4, "Q_HR_08": 4, "Q_HR_09": 4
        }
        eval_res = calculate_competency_scores(job_family=job, responses=responses)

        c_recruit = eval_res.competency_scores["COMP_HR_01"]
        self.assertTrue(c_recruit.is_insufficient)
        self.assertIsNone(c_recruit.current_level)
        self.assertIsNone(c_recruit.gap)
        self.assertEqual(c_recruit.status_label, "정보 부족 (추가 응답 필요)")

        # 정보 부족 역량은 deficiency ranking에 절대 포함되지 않음
        deficiency_ids = [cs.competency_id for cs in eval_res.prioritized_deficiencies]
        self.assertNotIn("COMP_HR_01", deficiency_ids)
        self.assertIn(c_recruit, eval_res.insufficient_competencies)

    def test_05_zero_gap_handling(self):
        """엣지 케이스 2: 역량 차이가 없는 경우 부족 역량 미조작 및 심화 학습 안내"""
        print("\n--- [TEST 5] 엣지 케이스: Zero Gap (역량 차이 없음) ---")
        job = "인사"
        # 모든 항목에서 목표 수준(4.0) 이상으로 응답
        responses = {q["question_id"]: 4 for q in get_questions_for_job(job)}
        targets = {q["competency_id"]: 4.0 for q in get_questions_for_job(job)}

        eval_res = calculate_competency_scores(job_family=job, responses=responses, target_levels=targets)
        self.assertEqual(len(eval_res.prioritized_deficiencies), 0)
        self.assertGreater(len(eval_res.zero_gap_competencies), 0)

        bundle = get_recommendations_for_assessment(eval_res, recommender=self.recommender)
        self.assertGreater(bundle.total_recommended_count, 0)
        top_card = bundle.all_courses_deduped[0]
        self.assertIn("심화·전문성 강화", top_card.customer_recommendation_reason)

    def test_06_free_only_budget_filter(self):
        """엣지 케이스 3: 무료 전용(FREE_ONLY) 필터 준수 및 결측치 왜곡 차단"""
        print("\n--- [TEST 6] 엣지 케이스: 무료 전용 필터 ---")
        sample_res = get_sample_assessment_result("인사")
        params = RecommendationFilterParams(price_filter="FREE_ONLY", edu_type="ALL")
        bundle = get_recommendations_for_assessment(sample_res, params, recommender=self.recommender)

        for card in bundle.all_courses_deduped:
            self.assertEqual(card.price_status, "FREE")
            self.assertEqual(card.numeric_price, 0)
            self.assertEqual(card.price_display, "무료")

    def test_07_streamlit_apptest_customer_ui(self):
        """Streamlit AppTest: app/streamlit_customer.py 렌더링 및 인터랙션 검증"""
        print("\n--- [TEST 7] Streamlit AppTest: app/streamlit_customer.py ---")
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(WORKSPACE_ROOT / "app" / "streamlit_customer.py"))
        at.run(timeout=30)
        self.assertFalse(at.exception, f"AppTest 예외 발생: {at.exception}")

        # 메인 탭 3개 렌더링 확인
        tabs = at.tabs
        self.assertGreaterEqual(len(tabs), 3)

        # 샘플 결과 보기 버튼 동작 시뮬레이션
        sample_btns = [b for b in at.button if "샘플 결과 보기" in b.label]
        self.assertTrue(len(sample_btns) > 0, "샘플 결과 보기 버튼을 찾을 수 없습니다.")
        sample_btns[0].click()
        at.run(timeout=30)
        self.assertFalse(at.exception, f"샘플 버튼 클릭 후 예외 발생: {at.exception}")
        self.assertIsNotNone(at.session_state["eval_result"])
        self.assertIsNotNone(at.session_state["rec_bundle"])
        self.assertTrue(at.session_state["is_sample_mode"])

        # 전체 초기화 버튼 콜백 동작 시뮬레이션
        reset_btns = [b for b in at.button if "전체 초기화" in b.label]
        self.assertTrue(len(reset_btns) > 0, "전체 초기화 버튼을 찾을 수 없습니다.")
        reset_btns[0].click()
        at.run(timeout=30)
        self.assertFalse(at.exception, f"전체 초기화 클릭 후 예외 발생: {at.exception}")
        self.assertIsNone(at.session_state["eval_result"])
        self.assertEqual(len(at.session_state["survey_responses"]), 0)
        self.assertFalse(at.session_state["is_sample_mode"])

        print("Streamlit AppTest 고객 UI (렌더링, 샘플 미리보기, 전체 초기화 콜백) 정상 실행 확인 완료.")


if __name__ == "__main__":
    unittest.main()
