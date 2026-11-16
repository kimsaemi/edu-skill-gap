# -*- coding: utf-8 -*-
"""
챗봇 핵심 기능 단위 테스트 (tests/test_chatbot.py)

검증 항목:
1. API 키 부재 시 검색 결과 표 전용 모드 정상 동작 확인
2. 제외된 1,377개 비직무/오매핑 과정이 추천 후보에 전혀 노출되지 않는지 확인
3. 후보에 없는 번호[N] 또는 가짜 과정명(환각) 필터링 동작 확인 (Mock 응답 활용)
4. 업무 연결(Task Matching) 및 임계값(0.55) 분기 동작 확인
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

# 루트 경로 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.chatbot.generator import ChatbotGenerator
from src.chatbot.prompts import SYSTEM_PROMPT, format_user_prompt
from src.chatbot.retriever import ChatbotRetriever, TASK_SIMILARITY_THRESHOLD
from src.chatbot.validator import validate_and_filter_response


class TestChatbotRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 검색기 인스턴스 1회 초기화
        cls.retriever = ChatbotRetriever()
        # 1,377개 제외 목록 로드
        excl_path = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
        cls.excluded_uids = set(pd.read_csv(excl_path, encoding="utf-8-sig")["course_uid"].astype(str))

    def test_01_fallback_when_no_api_key(self):
        """1. API 키가 없을 때 검색 결과 표 전용 모드로 정상 동작하는지 검증"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            gen = ChatbotGenerator()
            self.assertFalse(gen.is_available, "API 키가 없으면 is_available은 False여야 함")

            # 후보 검색은 정상 수행되어 표 데이터를 확보할 수 있어야 함
            matched_task, candidates, mode = self.retriever.retrieve_candidates("급여 정산 실무", top_k=5)
            self.assertGreater(len(candidates), 0, "후보 강좌는 정상 검색되어야 함")

            # 생성기 호출 시 API 에러 없이 NO_API_KEY 상태로 None 반환
            resp, status, has_hal, rem = gen.generate(
                user_query="급여 정산 실무",
                linked_task_str="없음",
                candidates_str="[1] 과정명 | 기관 | 실무 | 소개 | url",
                candidates=candidates
            )
            self.assertIsNone(resp, "API 키가 없을 때는 AI 생성 텍스트가 None이어야 함")
            self.assertEqual(status, "NO_API_KEY", "상태값은 NO_API_KEY여야 함")
            self.assertFalse(has_hal)

    def test_02_excluded_courses_never_in_results(self):
        """2. 1,377개 제외 목록 강좌가 후보 결과에 전혀 포함되지 않는지 검증"""
        test_queries = [
            "4대보험 신고를 처음 맡았어요",
            "직무기술서 작성 방법",
            "부동산 공인중개사 자격증",  # 명백한 제외 규칙 대상 질의
            "커피 바리스타 실무",       # 서비스·기능직 제외 질의
            "파이썬 웹 크롤링 자동화"
        ]

        for q in test_queries:
            _, candidates, _ = self.retriever.retrieve_candidates(q, top_k=5)
            for c in candidates:
                uid = c["course_uid"]
                self.assertNotIn(
                    uid,
                    self.excluded_uids,
                    f"제외 목록에 포함된 강좌({uid}: {c['title']})가 추천 결과에 노출되었습니다."
                )

    def test_03_hallucination_detection_and_filtering(self):
        """3. 후보에 없는 [번호]나 위조된 과정명을 완벽히 걸러내는지 검증"""
        mock_candidates = [
            {"index": 1, "title": "4대보험 및 급여 실무 마스터", "provider": "한국생산성본부(KPC)", "difficulty": "실무"},
            {"index": 2, "title": "인사노무 핵심 법률과 실무 가이드", "provider": "중앙경제HRD", "difficulty": "실무"},
            {"index": 3, "title": "표준 직무기술서 작성 워크숍", "provider": "한국능률협회(KMA)", "difficulty": "실무"}
        ]

        # Case A: 정상 응답 (후보 번호와 과정명이 일치)
        valid_response = (
            "- 한 줄 요약: 4대보험 및 급여 신고 업무\n"
            "- 추천 과정 1: 4대보험 및 급여 실무 마스터 [1] — 한국생산성본부(KPC) / 실무 지침을 상세히 제공합니다.\n"
            "- 추천 과정 2: 인사노무 핵심 법률과 실무 가이드 [2] — 중앙경제HRD / 법적 리스크를 예방할 수 있습니다.\n"
            "- 함께 알아두면 좋은 점: 관할 공단 서식을 미리 확인하세요."
        )
        filtered, has_hal, removed = validate_and_filter_response(valid_response, mock_candidates)
        self.assertFalse(has_hal, "정상 응답에서 환각이 감지되면 안 됨")
        self.assertEqual(len(removed), 0)
        self.assertIn("[1]", filtered)
        self.assertIn("[2]", filtered)

        # Case B: 후보 범위를 벗어난 번호 ([4], [9] 등)
        out_of_range_response = (
            "- 한 줄 요약: 급여 업무 지원\n"
            "- 추천 과정 1: 4대보험 및 급여 실무 마스터 [1] — 한국생산성본부(KPC) / 적합합니다.\n"
            "- 추천 과정 2: 완전히 새로운 신설 과정 [4] — 가짜기관 / 번호가 범위를 벗어남.\n"
            "- 추천 과정 3: 엉뚱한 과정 [9] — 가짜기관 / 존재하지 않는 번호."
        )
        filtered, has_hal, removed = validate_and_filter_response(out_of_range_response, mock_candidates)
        self.assertTrue(has_hal, "범위 밖 번호는 환각으로 감지되어야 함")
        self.assertEqual(len(removed), 2, "2개의 비정상 문장이 제거되어야 함")
        self.assertIn("[1]", filtered, "정상 문장 [1]은 유지되어야 함")
        self.assertNotIn("[4]", filtered, "비정상 문장 [4]는 제거되어야 함")
        self.assertNotIn("[9]", filtered, "비정상 문장 [9]는 제거되어야 함")

        # Case C: 번호는 있지만 과정명이 후보와 완전히 다른 경우 (위조 과정명)
        fake_title_response = (
            "- 한 줄 요약: 업무 추천\n"
            "- 추천 과정 1: 4대보험 및 급여 실무 마스터 [1] — 한국생산성본부(KPC) / 정상 과정.\n"
            "- 추천 과정 2: 딥러닝 인공지능 엔지니어링 마스터 클래스 [2] — 중앙경제HRD / 2번이지만 제목이 가짜."
        )
        filtered, has_hal, removed = validate_and_filter_response(fake_title_response, mock_candidates)
        self.assertTrue(has_hal, "가짜 과정명은 환각으로 감지되어야 함")
        self.assertIn("[1]", filtered)
        self.assertNotIn("딥러닝 인공지능", filtered, "가짜 과정명 문장은 삭제되어야 함")

    def test_04_mock_ai_generator_integration(self):
        """4. Mock Anthropic Client를 활용한 생성기 환각 검증 통합 흐름 테스트"""
        mock_candidates = [
            {"index": 1, "title": "인사평가 및 KPI 도출 실무", "provider": "한국생산성본부(KPC)", "difficulty": "실무"}
        ]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-mock"}):
            gen = ChatbotGenerator()

            # 가짜 Anthropic API 응답 생성 (1번 후보에 엉뚱한 제목을 매핑한 환각 응답)
            fake_content_block = MagicMock()
            fake_content_block.type = "text"
            fake_content_block.text = (
                "- 한 줄 요약: KPI 평가 업무\n"
                "- 추천 과정 1: 자바 스프링 부트 풀스택 개발 [1] — 코딩아카데미 / 위조된 추천 문장"
            )

            mock_response = MagicMock()
            mock_response.content = [fake_content_block]

            with patch("anthropic.Anthropic") as mock_anthropic_cls:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_response
                mock_anthropic_cls.return_value = mock_client

                resp, status, has_hal, removed = gen.generate(
                    user_query="KPI 평가 설계",
                    linked_task_str="없음",
                    candidates_str="[1] 인사평가 및 KPI 도출 실무 | KPC | 실무",
                    candidates=mock_candidates
                )

                self.assertTrue(has_hal, "환각이 감지되어야 함")
                self.assertEqual(len(removed), 1)
                # 환각 문장이 제거되고 요약만 남거나 처리됨
                if resp:
                    self.assertNotIn("자바 스프링 부트", resp)

    def test_05_task_matching_threshold_logic(self):
        """5. 업무 매핑 임계값(0.55) 분기 검증"""
        # 1) 명확한 업무 질의 -> 0.55 이상으로 업무 매핑 성공
        task, sim = self.retriever.match_task("급여 정산 엑셀 실무")
        self.assertIsNotNone(task, "표준 업무와 밀접한 질의는 매핑 성공해야 함")
        self.assertGreaterEqual(sim, TASK_SIMILARITY_THRESHOLD)

        # 2) 무관한 일반 질의 -> 0.55 미만으로 매핑 실패 (자유 검색 분기)
        task_none, sim_none = self.retriever.match_task("오늘 점심 뭐 먹지")
        self.assertIsNone(task_none, "무관한 질의는 매핑 실패(None)해야 함")
        self.assertLess(sim_none, TASK_SIMILARITY_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
