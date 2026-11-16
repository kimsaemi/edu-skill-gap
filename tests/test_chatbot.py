"""
tests/test_chatbot.py
AI 추천 상담 챗봇 단위 및 회귀 테스트
1. 사전 제작 설명 JSON(rec_explanations_90.json) 제약조건 검증 (120자 이내, 금지어 미포함)
2. 키워드 2개 겹칠 때 규칙 기반 설명 템플릿 검증
3. 키워드 0개 겹칠 때 기본 안내 문구 검증
4. KSA 정보 연계 시 규칙 기반 문구 검증
5. 명확한 업무 질문(예: '4대보험 신고 처음이에요') 입력 시 0.55 이상 업무 매핑 검증
6. 모호한 질문(예: '뭘 들어야 할지 모르겠어요') 입력 시 0.55 미만 또는 개인화 분기 검증
7. anthropic 패키지 부재/비활성화 시 에러 없는 안전 폴백 검증
"""
import os
import json
import re
import unittest
import unittest.mock as mock

from src.chatbot.explain import generate_rule_based_explanation
from src.chatbot.store import ExplanationStore, get_default_store
from src.chatbot.matcher import (
    match_and_recommend,
    compute_task_similarities,
    TASK_SIMILARITY_THRESHOLD
)
from src.chatbot.llm_optional import is_llm_available, generate_llm_explanation


class TestChatbot(unittest.TestCase):

    def test_01_pregenerated_explanations_constraints(self):
        store = get_default_store()
        self.assertGreater(len(store), 0, "rec_explanations_90.json 데이터가 비어 있습니다.")

        forbidden_patterns = [
            "만족도", "수료 효과", "수료효과", "취업", "자격 취득 보장", "자격취득보장",
            "가격", "일정", "최고", "반드시", "수료 후", "수료후"
        ]
        currency_patterns = [r"\d+\s*원", r"\d+\s*만원", r"수강료", r"비용", r"할인", r"무료"]

        for key, data in store._data.items():
            text = data.get("text", "")
            status = data.get("status", "")
            if status == "skip" or not text:
                continue

            # 120자 이내
            self.assertLessEqual(len(text), 120, f"[{key}] 120자 초과 ({len(text)}자): {text}")

            # 금지어 미포함
            for fb in forbidden_patterns:
                self.assertNotIn(fb, text, f"[{key}] 금지어 '{fb}' 포함: {text}")

            for cp in currency_patterns:
                self.assertIsNone(re.search(cp, text), f"[{key}] 금액 표현 '{cp}' 포함: {text}")

    def test_02_rule_based_explanation_two_keywords(self):
        query = "급여 계산과 원천징수 실무"
        intro = "본 과정은 임직원 급여 계산 및 원천징수 명세서 작성 방법을 학습합니다."
        exp = generate_rule_based_explanation(query=query, intro_summary=intro)

        self.assertLessEqual(len(exp), 80)
        self.assertIn("질문하신", exp)
        self.assertIn("관련된 내용을 다루는 과정이에요.", exp)
        self.assertTrue("원천징수" in exp or "급여" in exp)

    def test_03_rule_based_explanation_zero_keywords(self):
        query = "우주 항공 공학 로켓 추진체"
        intro = "본 과정은 채용 면접관 스킬과 구조화 질문 기법을 다룹니다."
        exp = generate_rule_based_explanation(query=query, intro_summary=intro)

        self.assertEqual(exp, "질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요.")

    def test_04_rule_based_explanation_with_task_and_ksa(self):
        query = "온보딩 프로그램 커리큘럼"
        intro = "신규 입사자를 위한 온보딩 프로세스와 조직 적응 멘토링 기법을 배웁니다."
        task_name = "전사 신규 입사자 온보딩 프로그램 기획"
        ksa_text = "지식: 온보딩 프로세스 설계, 조직문화 | 기술: 커리큘럼 개발"

        exp = generate_rule_based_explanation(
            query=query,
            intro_summary=intro,
            task_name=task_name,
            ksa_text=ksa_text
        )

        self.assertLessEqual(len(exp), 80)
        self.assertIn(task_name[:10], exp)
        self.assertIn("온보딩", exp)
        self.assertTrue(exp.endswith("내용을 다뤄요."))

    def test_05_clear_task_query_maps_above_threshold(self):
        query = "4대보험 신고 처음이에요"
        sims = compute_task_similarities(query)
        self.assertGreater(len(sims), 0)

        top_score, top_tid, top_task = sims[0]
        self.assertGreaterEqual(top_score, TASK_SIMILARITY_THRESHOLD, f"점수가 0.55 미만입니다: {top_score}")
        self.assertTrue("4대보험" in top_task["name"] or "급여" in top_task["name"])

        res = match_and_recommend(query=query, grade_idx=1)
        self.assertEqual(res.mode, "task_match")
        self.assertGreaterEqual(res.similarity_score, TASK_SIMILARITY_THRESHOLD)
        self.assertIsNotNone(res.matched_task)
        self.assertGreater(len(res.cards), 0)
        self.assertEqual(len(res.explanations), len(res.cards))

    def test_06_vague_query_below_threshold_or_personalization(self):
        query = "뭘 들어야 할지 모르겠어요"

        # 1. weak_task가 없을 때: 임계값 미만으로 search 모드 분기
        res_search = match_and_recommend(query=query, grade_idx=1, weak_task=None)
        self.assertEqual(res_search.mode, "search")
        self.assertLess(res_search.similarity_score, TASK_SIMILARITY_THRESHOLD)
        self.assertIn("특정 업무로 딱 좁혀지지 않아서", res_search.system_message)

        # 2. weak_task가 있을 때: 개인화 모드로 분기
        mock_weak = {
            "id": "DOM_06_T05",
            "name": "매월 임직원 급여·상여 계산, 4대보험 공제 및 원천징수 급여 대장 마감",
            "k": "4대보험 요율, 통상임금"
        }
        res_personal = match_and_recommend(query=query, grade_idx=1, weak_task=mock_weak)
        self.assertEqual(res_personal.mode, "personalization")
        self.assertIn("역량 갭이 가장 큰", res_personal.system_message)
        self.assertIn("급여·상여 계산", res_personal.system_message)

    def test_07_optional_llm_without_anthropic(self):
        with mock.patch.dict(os.environ, {"CHAT_LLM_ENABLED": "true", "ANTHROPIC_API_KEY": "test_key"}):
            with mock.patch.dict("sys.modules", {"anthropic": None}):
                avail, reason = is_llm_available()
                self.assertFalse(avail)
                self.assertTrue("라이브러리 미설치" in reason or "미설정" in reason)

                res = generate_llm_explanation("질문", [{"title": "과정 1"}])
                self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
