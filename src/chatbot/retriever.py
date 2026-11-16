# -*- coding: utf-8 -*-
"""
인사 교육과정 검색 및 업무 연결 모듈 (Retrieval & Task Matching)

1. 업무 연결 (Task Matching):
   - 질문을 90개 인사 실무 업무(hr_task_catalog_90.json / ncs_ksa_master.csv)와 Ko-SRoBERTa 임베딩으로 비교
   - 코사인 유사도가 TASK_SIMILARITY_THRESHOLD 이상이면 해당 업무의 기존 검증 추천 3~5건(task_course_recommendations_90.csv)을 우선 반환
2. 직접 검색 (Ad-hoc Search):
   - 충분히 비슷한 업무가 없으면 2단계 하이브리드 추천 엔진을 직접 호출:
     1단계: Ko-SRoBERTa(50%) + BM25(35%) + 난이도 보너스(10점) (UnifiedHybridRecommender)
     2단계: Cross-Encoder 2단계 리랭킹 (0.6 * CE + 0.4 * Stage1) (KoreanCrossEncoderReranker)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.course_links import detail_url
from src.recommendation.cross_encoder_reranker import get_shared_reranker
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
HR_DATA_DIR = DATA_DIR / "hr"
PROCESSED_DIR = HR_DATA_DIR / "processed"
OUTPUT_DIR = HR_DATA_DIR / "output" / "recommendation"

# -----------------------------------------------------------------------------
# 업무 매핑 기준 유사도 상수
# -----------------------------------------------------------------------------
# 근거: Ko-SRoBERTa(jhgan/ko-sroberta-multitask) 코사인 유사도 실측 분석:
# 1) 90개 표준 업무 명칭/정의와 직결되는 질의(예: '급여 정산 엑셀', '채용 면접 질문지 작성')는
#    유사도가 0.65 ~ 0.85 구간에 집중됨.
# 2) 특정 업무로 단정하기 어려운 일반 질문이나 실무 고민(예: '4대보험 신고 처음 맡음', '어떤 교육부터 들을까요')은
#    0.35 ~ 0.54 구간에 위치함.
# 3) 비-HR 질문('오늘 점심 뭐 먹지', '파이썬 웹 크롤링')은 0.15 ~ 0.35 수준에 머묾.
# 따라서 0.55를 기준으로 삼아:
# - 0.55 이상: 사전에 정밀하게 검증된 90개 업무별 Top 3/5 추천(task_course_recommendations_90.csv)을 정확하게 연결.
# - 0.55 미만: 무리하게 업무를 단정하지 않고, 사용자의 자연어 입력 전체를 2단계 하이브리드 검색 코퍼스로 직접 전달.
TASK_SIMILARITY_THRESHOLD: float = 0.55


class ChatbotRetriever:
    """챗봇용 2단계 검색 및 업무 연결기"""

    def __init__(self, uhr: Optional[UnifiedHybridRecommender] = None):
        # 1. 기존 추천 엔진 및 리랭커 재사용 (신규 작성 배제)
        self.uhr = uhr or UnifiedHybridRecommender()
        self.reranker = get_shared_reranker()

        # 2. 강좌 마스터 데이터 및 90개 업무 카탈로그 로드
        self._load_reference_data()

    def _load_reference_data(self):
        # 9,075건 정제 강좌 코퍼스 (상세 정보 조회용)
        self.df_courses = self.uhr.df_courses.set_index("course_uid", drop=False)

        # 90개 업무 카탈로그 로드 (hr_task_catalog_90.json)
        cat_path = PROCESSED_DIR / "hr_task_catalog_90.json"
        self.tasks: List[Dict[str, Any]] = []
        if cat_path.exists():
            with open(cat_path, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
                self.tasks = cat_data.get("tasks", []) if isinstance(cat_data, dict) else cat_data

        # NCS KSA 마스터 파일(data/processed/ncs_ksa_master.csv) 로드 확인
        ncs_ksa_path = DATA_DIR / "processed" / "ncs_ksa_master.csv"
        self.has_ncs_ksa = ncs_ksa_path.exists()
        if self.has_ncs_ksa:
            self.df_ncs_ksa = pd.read_csv(ncs_ksa_path)
        else:
            self.df_ncs_ksa = pd.DataFrame()

        # 90개 업무 사전 추천 결과(task_course_recommendations_90.csv) 로드
        rec90_path = OUTPUT_DIR / "task_course_recommendations_90.csv"
        if rec90_path.exists():
            self.df_rec90 = pd.read_csv(rec90_path)
        else:
            self.df_rec90 = pd.DataFrame()

        # 90개 업무 임베딩 사전 인코딩 (Ko-SRoBERTa)
        self._init_task_embeddings()

    def _init_task_embeddings(self):
        """90개 업무의 대표 텍스트 벡터 사전 생성 (질의 시점 초고속 O(1) 비교)"""
        self.task_texts = []
        for t in self.tasks:
            text = f"{t.get('task_name', '')} {t.get('domain_name', '')} {t.get('easy_description', '')}"
            k = t.get("knowledge", "")
            s = t.get("skill", "")
            if k or s:
                text += f" | {k} {s}"
            self.task_texts.append(text)

        if self.uhr.model is not None and self.task_texts:
            self.task_embeddings = self.uhr.model.encode(
                self.task_texts,
                normalize_embeddings=True,
                device=self.uhr.device
            )
        else:
            self.task_embeddings = np.zeros((len(self.task_texts), 768), dtype=np.float32)

    def match_task(self, query: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        사용자 질의와 가장 가까운 90개 표준 업무를 검색합니다.
        유사도가 TASK_SIMILARITY_THRESHOLD 이상일 때만 매핑된 업무를 반환합니다.
        """
        if not query or not query.strip() or self.uhr.model is None or len(self.task_embeddings) == 0:
            return None, 0.0

        q_clean = query.strip()
        q_vec = self.uhr.model.encode(q_clean, normalize_embeddings=True, device=self.uhr.device)
        sims = np.dot(self.task_embeddings, q_vec)

        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        if best_sim >= TASK_SIMILARITY_THRESHOLD:
            return self.tasks[best_idx], best_sim
        return None, best_sim

    def retrieve_candidates(
        self,
        query: str,
        top_k: int = 5,
        user_level: str = "실무"
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        질의에 적합한 후보 강좌 5개를 추출합니다.
        1) 90개 업무 중 높은 유사도(>=0.55)의 업무가 있으면 해당 업무의 기존 추천을 우선 반환
        2) 없으면 질문 문장으로 직접 2단계 하이브리드 검색 실행
        """
        matched_task, sim_score = self.match_task(query)

        candidates: List[Dict[str, Any]] = []

        if matched_task is not None and not self.df_rec90.empty:
            # 1. 업무 매핑 성공: 기존 검증 추천 3~5개 추출 (task_course_recommendations_90.csv)
            t_id = matched_task["task_id"]
            # 해당 업무 및 실무(또는 사용자 지정) 레벨 후보 추출
            task_rows = self.df_rec90[
                (self.df_rec90["task_id"] == t_id) & (self.df_rec90["level"] == user_level)
            ].sort_values(by="rank").head(top_k)

            # 만약 해당 레벨이 없으면 전체 레벨에서 추출
            if task_rows.empty:
                task_rows = self.df_rec90[self.df_rec90["task_id"] == t_id].sort_values(by="rank").head(top_k)

            for idx, (_, row) in enumerate(task_rows.iterrows(), 1):
                uid = str(row["course_uid"])
                # 원본 메타데이터 결합
                c_info = self.df_courses.loc[uid] if uid in self.df_courses.index else pd.Series()
                intro = str(c_info.get("clean_intro") or c_info.get("course_intro") or "")[:150].strip()
                diff = str(c_info.get("difficulty") or row.get("level") or "실무")
                raw_url = str(c_info.get("url") or "#")
                final_url = detail_url(raw_url)

                candidates.append({
                    "index": idx,
                    "course_uid": uid,
                    "title": str(row["title"]),
                    "provider": str(row["provider"]),
                    "difficulty": diff,
                    "intro": intro,
                    "url": final_url,
                    "score": float(row.get("final_score", 0.0)),
                    "source": "precomputed_task_rec"
                })

            retrieval_mode = f"TASK_MAPPING ({matched_task['task_name']}, 유사도 {sim_score:.2f})"

        else:
            # 2. 업무 매핑 실패 또는 임계값 미달: 2단계 하이브리드 실시간 검색
            # 1단계: Ko-SRoBERTa(50%) + BM25(35%) + 난이도보너스(10점) (UnifiedHybridRecommender)
            # cluster_boost=0.0 (기본 모드)
            df_cands, _, _, _, _ = self.uhr.recommend(
                query=query,
                target_domain=None,
                user_level=user_level,
                top_n=20,
                cluster_boost=0.0
            )

            if df_cands.empty:
                return None, [], "NO_CANDIDATES"

            # 2단계: Cross-Encoder 2단계 리랭킹 (0.6 * CE + 0.4 * Stage1)
            # min_relevance_threshold=0.01로 극단적 노이즈를 제외하고 Top-K 반환
            df_reranked = self.reranker.rerank(
                query=query,
                candidates_df=df_cands,
                top_k=top_k,
                min_relevance_threshold=0.01
            )

            for idx, (_, row) in enumerate(df_reranked.iterrows(), 1):
                uid = str(row["course_uid"])
                intro = str(row.get("clean_intro") or row.get("course_intro") or "")[:150].strip()
                diff = str(row.get("difficulty") or user_level)
                raw_url = str(row.get("url") or "#")
                final_url = detail_url(raw_url)
                score = float(row.get("reranked_final_score", row.get("final_score", 0.0)))

                candidates.append({
                    "index": idx,
                    "course_uid": uid,
                    "title": str(row["title"]),
                    "provider": str(row["provider"]),
                    "difficulty": diff,
                    "intro": intro,
                    "url": final_url,
                    "score": score,
                    "source": "adhoc_hybrid_reranked"
                })

            retrieval_mode = f"ADHOC_SEARCH (최고 유사도 {sim_score:.2f} < {TASK_SIMILARITY_THRESHOLD})"

        return matched_task, candidates, retrieval_mode

    @staticmethod
    def format_candidates_for_prompt(candidates: List[Dict[str, Any]]) -> str:
        """
        <후보과정>[1] 과정명 | 기관 | 난이도 | 소개 앞부분 | URL ... [5]</후보과정>
        형식으로 포맷팅
        """
        if not candidates:
            return "후보 과정 없음"

        parts = []
        for c in candidates:
            idx = c["index"]
            title = c["title"]
            prov = c["provider"]
            diff = c["difficulty"]
            intro = c["intro"] or "소개 정보 없음"
            url = c["url"]
            parts.append(f"[{idx}] {title} | {prov} | {diff} | {intro} | {url}")

        return " ".join(parts)

    @staticmethod
    def format_linked_task_for_prompt(task: Optional[Dict[str, Any]]) -> str:
        """
        <연결된업무>업무명 / 분야 / KSA 요약 (없으면 "없음")</연결된업무>
        형식으로 포맷팅
        """
        if not task:
            return "없음"

        name = task.get("task_name", "")
        domain = task.get("domain_name", "")
        k = task.get("knowledge", "")
        s = task.get("skill", "")
        a = task.get("attitude", "")

        ksa_parts = []
        if k:
            ksa_parts.append(f"지식: {k}")
        if s:
            ksa_parts.append(f"기술: {s}")
        if a:
            ksa_parts.append(f"태도: {a}")
        ksa_str = ", ".join(ksa_parts) if ksa_parts else "KSA 정보 없음"

        return f"{name} / {domain} / {ksa_str}"
