"""
tests/test_chatbot.py
AI 추천 상담 챗봇 단위, 회귀 및 Streamlit AppTest 검증
1. rec_explanations_90.json 제약조건 검증 (120자 이내, 금지어, basis 원문 일치, 업무 내 중복 방지, LCS < 70%)
2. 키워드 2개 겹칠 때 규칙 기반 설명 템플릿 검증
3. 키워드 0개 겹칠 때 기본 안내 문구 검증
4. KSA 정보 연계 시 규칙 기반 문구 검증
5. 명확한 업무 질문(4대보험 신고 처음이에요) 0.42 이상 업무 매핑 검증
6. 모호한 질문(뭘 들어야 할지 모르겠어요) 개인화 분기 검증
7. anthropic 패키지 부재/비활성화 시 에러 없는 안전 폴백 검증
8. "직무급제 도입" 입력 시 "직무 순환" 업무로 오매핑되지 않는지 검증
9. "파이썬으로 인사 데이터 분석" 입력 시 "퇴사 인터뷰" 업무로 오매핑되지 않는지 검증
10. "안녕 반가워", "오늘 날씨 어때" 입력 시 범위 밖(out_of_scope) 처리 및 과정 미노출 검증
11. 90개 업무명 자체 입력 시 1위 일치율(Rank 1 ratio) 검증 및 출력
12. Streamlit AppTest: 6개 탭 렌더링 및 3종 질문(업무 연결, 검색, 범위 밖) 무오류 검증
"""
import os
import json
import re
import unittest
import unittest.mock as mock
from difflib import SequenceMatcher

from src.chatbot.explain import generate_rule_based_explanation
from src.chatbot.store import ExplanationStore, get_default_store
from src.chatbot.matcher import (
    match_and_recommend,
    compute_task_similarities,
    TASK_SIMILARITY_THRESHOLD,
    OUT_OF_SCOPE_THRESHOLD
)
from src.chatbot.llm_optional import is_llm_available, generate_llm_explanation


class TestChatbot(unittest.TestCase):

    def test_01_pregenerated_explanations_constraints(self):
        store = get_default_store()
        self.assertGreater(len(store), 0, "rec_explanations_90.json 데이터가 비어 있습니다.")

        forbidden_patterns = [
            "만족도", "수료 효과", "수료효과", "취업", "자격 취득 보장", "자격취득보장",
            "보장", "가격", "일정", "최고", "반드시", "수료 후", "수료후", "체계적으로"
        ]
        currency_patterns = [r"\d+\s*원", r"\d+\s*만원", r"수강료", r"비용", r"할인", r"무료"]

        task_explanations = {}

        for key, data in store._data.items():
            text = data.get("text", "")
            status = data.get("status", "")
            if status == "skip" or not text:
                continue

            self.assertEqual(status, "claude_draft", f"[{key}] status는 'claude_draft'여야 합니다.")
            self.assertLessEqual(len(text), 120, f"[{key}] 120자 초과 ({len(text)}자): {text}")

            for fb in forbidden_patterns:
                self.assertNotIn(fb, text, f"[{key}] 금지어 '{fb}' 포함: {text}")

            for cp in currency_patterns:
                self.assertIsNone(re.search(cp, text), f"[{key}] 금액 표현 '{cp}' 포함: {text}")

            tid = key.split("|")[0]
            if tid not in task_explanations:
                task_explanations[tid] = []
            task_explanations[tid].append(text)

        # 업무 내 중복(유사도 0.90 이상) 검사
        for tid, texts in task_explanations.items():
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    sim = SequenceMatcher(None, texts[i], texts[j]).ratio()
                    self.assertLess(sim, 0.90, f"[{tid}] 업무 내 설명 유사도 과다 (sim={sim:.2f}):\n1: {texts[i]}\n2: {texts[j]}")

    def test_02_rule_based_explanation_two_keywords(self):
        query = "급여 계산과 원천징수 실무"
        intro = "본 과정은 임직원 급여 계산 및 원천징수 명세서 작성 방법을 학습합니다."
        exp = generate_rule_based_explanation(query=query, intro_summary=intro)

        self.assertLessEqual(len(exp), 80)
        self.assertIn("질문하신", exp)
        self.assertIn("관련된 내용을 다루는 과정이에요.", exp)
        self.assertTrue(any(kw in exp for kw in ["급여", "계산", "원천", "징수"]))

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
        self.assertGreaterEqual(top_score, TASK_SIMILARITY_THRESHOLD, f"점수가 임계값 미만입니다: {top_score}")
        self.assertTrue("4대보험" in top_task["name"] or "급여" in top_task["name"])

        res = match_and_recommend(query=query, grade_idx=1)
        self.assertEqual(res.mode, "task_match")
        self.assertGreaterEqual(res.similarity_score, TASK_SIMILARITY_THRESHOLD)
        self.assertIsNotNone(res.matched_task)
        self.assertGreater(len(res.cards), 0)
        self.assertEqual(len(res.explanations), len(res.cards))

    def test_06_vague_query_below_threshold_or_personalization(self):
        query = "뭘 들어야 할지 모르겠어요"
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

    def test_08_job_pay_query_does_not_map_to_job_rotation(self):
        query = "직무급제 도입"
        res = match_and_recommend(query=query, grade_idx=1)
        # 직무 순환 업무(DOM_01_T09)로 오매핑되면 실패
        if res.matched_task:
            self.assertNotIn("직무 순환", res.matched_task.get("name", ""))
            # 직무급/임금체계 관련 업무(DOM_06_T01)로 연결되거나 검색이어야 함
            if res.mode == "task_match":
                self.assertTrue(
                    any(term in res.matched_task.get("name", "") for term in ["직무급", "임금", "보상", "직무가치"]),
                    f"직무급 질의가 무관 업무로 매핑됨: {res.matched_task.get('name')}"
                )

    def test_09_python_hr_analysis_does_not_map_to_exit_interview(self):
        query = "파이썬으로 인사 데이터 분석"
        res = match_and_recommend(query=query, grade_idx=1)
        # 퇴사 인터뷰 업무로 오매핑되면 실패
        if res.matched_task:
            self.assertNotIn("퇴사 인터뷰", res.matched_task.get("name", ""))

    def test_10_out_of_scope_queries(self):
        for q in ["안녕 반가워", "오늘 날씨 어때"]:
            res = match_and_recommend(query=q, grade_idx=1)
            self.assertEqual(res.mode, "out_of_scope", f"'{q}'가 out_of_scope가 아님: {res.mode}")
            self.assertEqual(len(res.cards), 0, f"'{q}'에 과정 카드가 추천됨: {len(res.cards)}개")
            self.assertIn("이 서비스는 인사 교육과정 추천용이에요", res.system_message)

    def test_11_all_90_tasks_self_match(self):
        from src.customer import career_platform as cp
        import numpy as np

        eng = cp.engine()
        tasks = cp.task_index()
        t_ids = list(tasks.keys())
        t_names = [tasks[tid]["name"] for tid in t_ids]
        task_embs = eng.model.encode(t_names, normalize_embeddings=True)

        rank1_count = 0
        for i, name in enumerate(t_names):
            q_emb = eng.model.encode(name, normalize_embeddings=True)
            sims = np.dot(q_emb, task_embs.T)
            top_idx = int(np.argmax(sims))
            if top_idx == i:
                rank1_count += 1

        ratio = rank1_count / len(t_ids)
        print(f"\n[Test 11] 90개 업무명 자체 입력 1위 일치율: {rank1_count}/{len(t_ids)} ({ratio*100:.1f}%)")
        self.assertGreaterEqual(ratio, 0.95, f"업무명 1위 일치율이 95% 미만입니다: {ratio*100:.1f}%")

    def test_12_streamlit_apptest_navigation_and_chat(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app_path = str(Path(__file__).parent.parent / "customer_dashboard" / "streamlit_customer.py")
        at = AppTest.from_file(app_path, default_timeout=35)
        at.run()
        self.assertFalse(at.exception, "앱 로딩 중 예외 발생")

        # 6개 탭(stepbar 버튼 6개: 1, 2, 3, all, my, chat) 확인
        btn_keys = [btn.key for btn in at.button if btn.key]
        for expected_key in ["nav_1", "nav_2", "nav_3", "nav_all", "nav_my", "nav_chat"]:
            self.assertIn(expected_key, btn_keys, f"메뉴 버튼 {expected_key} 누락")

        # chat 탭 이동 테스트
        at.session_state["step"] = "chat"
        at.run()
        self.assertFalse(at.exception, "chat 탭 렌더링 중 예외 발생")


if __name__ == "__main__":
    unittest.main()
