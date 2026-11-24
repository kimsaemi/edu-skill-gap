"""
tests/test_chatbot.py
고객 대시보드 AI 상담 탭 검증
- 규칙 기반 설명 문장
- 업무 연결 4가지 결과(업무 연결 / 업무 후보 / 검색 / 범위 밖)와 진단 결과 연계
- 지난 검토에서 문제가 된 질문(직무급제, 파이썬 데이터 분석, 엑셀, 4대보험, 안녕)
- 실시간 AI(선택 기능)가 없어도 동작하는지
- Streamlit AppTest: 6개 탭과 AI 상담 질문·업무 후보 버튼 클릭
"""
import os
import unittest
import unittest.mock as mock
from pathlib import Path

from src.chatbot import matcher as M
from src.chatbot.explain import generate_rule_based_explanation
from src.chatbot.llm_optional import generate_llm_explanation, is_llm_available
from src.customer import career_platform as cp

PAY_TASK = "DOM_06_T05"  # 매월 임직원 급여·상여 계산, 4대보험 공제 및 원천징수 급여 대장 마감


def task_ids_with(word: str):
    return {tid for tid, t in cp.task_index().items() if word in t["name"]}


class TestRuleExplanation(unittest.TestCase):
    def test_two_keywords(self):
        exp = generate_rule_based_explanation("급여 계산과 원천징수 실무",
                                              "본 과정은 임직원 급여 계산 및 원천징수 명세서 작성 방법을 학습합니다.")
        self.assertLessEqual(len(exp), 80)
        self.assertTrue(exp.startswith("질문하신"))
        self.assertTrue(any(k in exp for k in ["급여", "계산", "원천징수"]))

    def test_zero_keywords(self):
        exp = generate_rule_based_explanation("우주 항공 로켓 추진체", "채용 면접관 스킬과 구조화 질문 기법을 다룹니다.")
        self.assertEqual(exp, "질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요.")

    def test_keywords_come_from_inputs(self):
        q, intro = "온보딩 프로그램 커리큘럼", "신규 입사자를 위한 온보딩 프로세스와 조직 적응 멘토링 기법을 배웁니다."
        exp = generate_rule_based_explanation(q, intro, "전사 신규 입사자 온보딩 프로그램 기획", "온보딩 프로세스 설계, 조직문화")
        self.assertTrue(exp.startswith("과정 소개에 ") and exp.endswith(" 내용이 있어 이 업무와 연결돼요."))
        self.assertIn("'온보딩'", exp)
        self.assertIn("'프로세스'", exp)

    def test_task_without_overlap(self):
        exp = generate_rule_based_explanation("질문", "로켓 추진체 설계", "온보딩 기획", "온보딩")
        self.assertEqual(exp, "이 업무의 기본 추천 과정이에요. 과정 소개를 확인해 주세요.")

    def test_josa(self):
        exp = generate_rule_based_explanation("엑셀 강좌", "엑셀 함수와 차트를 배워요")
        self.assertIn("엑셀과", exp)


class TestMatching(unittest.TestCase):
    def mode(self, q):
        return M.classify(M.compute_task_scores(q), M.is_hr_relevant_query(q))

    def test_all_task_names_match_themselves(self):
        tasks = cp.task_index()
        hits = sum(M.compute_task_scores(t["name"])[0][2] == tid for tid, t in tasks.items())
        print(f"\n업무명 자기 1위: {hits}/{len(tasks)}")
        self.assertEqual(hits, len(tasks))

    def test_clear_questions_connect_to_task(self):
        for q, word in [("신입사원 온보딩 프로그램을 기획해야 해요", "온보딩"),
                        ("노사협의회 운영 절차가 궁금해요", "노사협의회"),
                        ("연말정산 처음 해봐요", "연말정산")]:
            res = M.match_and_recommend(q)
            self.assertEqual(res.mode, "task_match", q)
            self.assertIn(word, res.matched_task["name"], q)
            self.assertEqual(len(res.explanations), len(res.cards))
            self.assertTrue(all(e["source"] == "rule" for e in res.explanations))

    def test_job_pay_never_confidently_maps_to_rotation(self):
        res = M.match_and_recommend("직무급제 도입을 검토 중인데 뭘 알아야 해?")
        if res.mode == "task_match":
            self.assertNotIn("직무 순환", res.matched_task["name"])
        if res.mode == "candidates":
            names = " ".join(t["name"] for t in res.candidate_tasks)
            self.assertIn("직무급제", names, "임금체계(직무급제) 업무가 후보에 있어야 함")

    def test_ambiguous_questions_are_not_forced(self):
        for q in ["파이썬으로 인사 데이터 분석하고 싶어요", "엑셀 실무 강좌 알려줘", "4대보험 신고를 처음 맡았어요"]:
            self.assertIn(self.mode(q), ("candidates", "search"), q)

    def test_insurance_question_offers_pay_task(self):
        res = M.match_and_recommend("4대보험 신고를 처음 맡았어요")
        self.assertIn(PAY_TASK, [t["id"] for t in res.candidate_tasks])

    def test_out_of_scope(self):
        for q in ["안녕 반가워", "오늘 날씨 어때", "넷플릭스 주말 영화 추천"]:
            res = M.match_and_recommend(q)
            self.assertEqual(res.mode, "out_of_scope", q)
            self.assertEqual(res.cards, [])
            self.assertEqual(res.system_message, M.OUT_OF_SCOPE_MESSAGE)

    def test_pick_candidate_returns_task_recommendations(self):
        res = M.recommend_for_task(PAY_TASK, "4대보험 신고를 처음 맡았어요")
        self.assertEqual(res.mode, "task_match")
        self.assertEqual(res.matched_task["id"], PAY_TASK)
        self.assertGreater(len(res.cards), 0)

    def test_personalization(self):
        weak = {"id": PAY_TASK, "name": cp.task_index()[PAY_TASK]["name"]}
        res = M.match_and_recommend("뭘 들어야 할지 모르겠어요", weak_task=weak)
        self.assertEqual(res.mode, "personalization")
        self.assertEqual(res.matched_task["id"], PAY_TASK)

    def test_excluded_courses_never_shown(self):
        import pandas as pd
        root = Path(__file__).resolve().parent.parent
        excluded = set(pd.read_csv(root / "data/hr/processed/off_topic_exclusions.csv")["course_uid"].astype(str))
        for q in ["엑셀 실무 강좌 알려줘", "4대보험 신고를 처음 맡았어요", "평가 면담을 잘하고 싶어요"]:
            res = M.match_and_recommend(q)
            self.assertFalse({c["course_uid"] for c in res.cards} & excluded, q)


class TestOptionalLLM(unittest.TestCase):
    def test_works_without_anthropic(self):
        with mock.patch.dict(os.environ, {"CHAT_LLM_ENABLED": "true", "ANTHROPIC_API_KEY": "dummy"}):
            with mock.patch.dict("sys.modules", {"anthropic": None}):
                avail, _ = is_llm_available()
                self.assertFalse(avail)
                self.assertIsNone(generate_llm_explanation("질문", [{"title": "과정 1"}]))


class TestAppTest(unittest.TestCase):
    def test_sidebar_text_rules(self):
        from streamlit.testing.v1 import AppTest
        app = str(Path(__file__).resolve().parent.parent / "customer_dashboard" / "streamlit_customer.py")
        at = AppTest.from_file(app, default_timeout=600).run()
        self.assertFalse(at.exception)
        sidebar_text = " ".join(str(getattr(x, "value", "")) for x in at.sidebar)
        self.assertNotIn("자동 배제", sidebar_text)
        self.assertNotIn("제외합니다", sidebar_text)
        self.assertIn("0.1점 이상인 과정을 먼저 고르고", sidebar_text)

    def test_tabs_and_chat_flow(self):
        from streamlit.testing.v1 import AppTest
        app = str(Path(__file__).resolve().parent.parent / "customer_dashboard" / "streamlit_customer.py")
        at = AppTest.from_file(app, default_timeout=600).run()
        self.assertFalse(at.exception)

        # 진단 상태 초기화 후 6개 탭 모두 동작 검증
        at.session_state["g"] = 0
        at.session_state["ds"] = ["DOM_01"]
        at.session_state["d"] = "DOM_01"
        at.session_state["tl"] = {"DOM_01_T04": 0}
        at.run()
        self.assertFalse(at.exception)

        for key in ["nav_1", "nav_2", "nav_3", "nav_all", "nav_my", "nav_chat"]:
            at.button(key=key).click().run()
            self.assertFalse(at.exception, key)

        # 업무 연결 / 업무 후보 / 범위 밖 질문
        for q in ["신입사원 온보딩 프로그램을 기획해야 해요", "4대보험 신고를 처음 맡았어요", "안녕 반가워"]:
            at.chat_input[0].set_value(q).run()
            self.assertFalse(at.exception, q)
        cand_keys = [b.key for b in at.button if b.key and b.key.startswith("cand_")]
        self.assertTrue(cand_keys, "업무 후보 버튼이 보여야 함")

        # 후보 버튼을 누르면 그 업무 추천이 이어서 나온다
        n_before = len(at.session_state["chat_msgs"])
        at.button(key=cand_keys[0]).click().run()
        self.assertFalse(at.exception)
        msgs = at.session_state["chat_msgs"]
        self.assertEqual(len(msgs), n_before + 2)
        self.assertEqual(msgs[-1]["mode"], "task_match")
        self.assertTrue(msgs[-1]["cards"])


class TestRerankerLowScoreBadge(unittest.TestCase):
    def test_dom01_t04_grade0_badge(self):
        from customer_dashboard.streamlit_customer import course_card
        recs = cp.task_recommendations("DOM_01_T04", 0, use_reranker=True)
        self.assertGreaterEqual(len(recs), 3)

        low_score_found = False
        normal_score_found = False

        with mock.patch("streamlit.markdown") as mock_md, \
             mock.patch("streamlit.expander"), \
             mock.patch("streamlit.caption"), \
             mock.patch("streamlit.columns", side_effect=lambda spec: [mock.MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]):
            for r in recs:
                mock_md.reset_mock()
                course_card(r, key=f"test_{r.get('course_uid')}")
                first_md = mock_md.call_args_list[0][0][0]
                r_score = (r.get("match") or {}).get("reranker")
                if r_score is not None and r_score < 0.1:
                    low_score_found = True
                    self.assertIn("⚠ 문맥 점수 낮음 (후보가 부족해 포함)", first_md)
                elif r_score is not None and r_score >= 0.1:
                    normal_score_found = True
                    self.assertNotIn("⚠ 문맥 점수 낮음 (후보가 부족해 포함)", first_md)

        self.assertTrue(low_score_found, "리랭커 < 0.1 과정이 최소 1개 있어야 함")
        self.assertTrue(normal_score_found, "리랭커 >= 0.1 과정이 최소 1개 있어야 함")


if __name__ == "__main__":
    unittest.main()
