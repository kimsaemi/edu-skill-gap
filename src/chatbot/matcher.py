"""
src/chatbot/matcher.py
사용자 질문 분석 및 90개 업무 매핑 모듈
- 임계값: TASK_SIMILARITY_THRESHOLD = 0.55
  (이유: 사전 테스트에서 0.55 미만은 질문이 특정 업무에 꽂히지 않고 막연한 경우가 많아 키워드 검색으로 넘기는 편이 과정 추천의 폭이 넓음)
- Ko-SRoBERTa 의미 유사도 + 도메인 핵심 명사 가중치 결합
- 업무 매핑(0.55 이상) / 키워드 검색(0.55 미만) / 진단 결과 기반 개인화 분기 지원
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

from src.customer import career_platform as cp
from src.chatbot.explain import generate_rule_based_explanation, get_preprocessor
from src.chatbot.store import get_default_store, ExplanationStore

# 임계값: TASK_SIMILARITY_THRESHOLD = 0.55
# 이유: 사전 테스트에서 0.55 미만은 질문이 특정 업무에 꽂히지 않고 막연한 경우가 많아 키워드 검색으로 넘기는 편이 과정 추천의 폭이 넓음
TASK_SIMILARITY_THRESHOLD: float = 0.55

PERSONALIZATION_PATTERNS = [
    r"내게\s*맞는", r"뭘\s*들어야", r"부족한\s*것", r"어떤\s*걸", r"뭐부터",
    r"어디부터", r"진단\s*결과", r"나한테\s*맞는", r"추천해\s*줘"
]

_TASK_CACHE: Optional[Dict[str, Any]] = None
_TASK_EMBEDDINGS: Optional[Dict[str, np.ndarray]] = None


@dataclass
class ChatRecommendationResult:
    query: str
    mode: str  # "task_match" | "personalization" | "search"
    matched_task: Optional[Dict[str, Any]] = None
    similarity_score: float = 0.0
    alternative_task: Optional[Dict[str, Any]] = None
    system_message: str = ""
    cards: List[Dict[str, Any]] = field(default_factory=list)
    explanations: List[Dict[str, str]] = field(default_factory=list)


def _init_task_cache():
    global _TASK_CACHE, _TASK_EMBEDDINGS
    if _TASK_CACHE is not None and _TASK_EMBEDDINGS is not None:
        return
    tasks = cp.task_index()
    eng = cp.engine()
    embeddings = {}
    for tid, t in tasks.items():
        text = t.get("name", "")
        emb = eng.model.encode(text, normalize_embeddings=True)
        embeddings[tid] = emb
    _TASK_CACHE = tasks
    _TASK_EMBEDDINGS = embeddings


def compute_task_similarities(query: str) -> List[Tuple[float, str, Dict[str, Any]]]:
    """사용자 질문과 90개 업무 간의 유사도 점수 계산"""
    _init_task_cache()
    eng = cp.engine()
    prep = get_preprocessor()

    q_clean = query.strip()
    if not q_clean:
        return []

    q_emb = eng.model.encode(q_clean, normalize_embeddings=True)
    # 범용 단어(실무, 강좌 등)는 특정 업무 가산점에서 제외
    generic_words = {"실무", "역량", "기초", "입문", "전문가", "과정", "담당자", "업무", "관리", "강좌", "교육"}
    q_nouns = [w for w in prep.tokenize(q_clean) if len(w) >= 2 and w not in generic_words]

    scores = []
    for tid, t in _TASK_CACHE.items():
        t_emb = _TASK_EMBEDDINGS[tid]
        cos_sim = float(np.dot(q_emb, t_emb))

        # 핵심 키워드/명사 일치 보너스
        kw_bonus = 0.0
        t_name = t.get("name", "")
        t_k = t.get("k", "")
        t_easy = t.get("easy", "")

        for n in q_nouns:
            if n in t_name:
                kw_bonus = max(kw_bonus, 0.28)
            elif n in t_k or n in t_easy:
                kw_bonus = max(kw_bonus, 0.15)

        total_score = min(1.0, cos_sim + kw_bonus)
        scores.append((total_score, tid, t))

    scores.sort(key=lambda x: x[0], reverse=True)
    return scores


def match_and_recommend(
    query: str,
    grade_idx: int = 1,
    use_reranker: bool = True,
    weak_task: Optional[Dict[str, Any]] = None,
    store: Optional[ExplanationStore] = None
) -> ChatRecommendationResult:
    """
    사용자 질의를 분석하여 업무 매핑 또는 키워드 검색을 수행하고
    Top 3 과정 카드와 설명을 조립합니다.
    """
    store = store or get_default_store()
    q = query.strip()
    if not q:
        return ChatRecommendationResult(
            query=query,
            mode="search",
            system_message="질문 내용을 입력해 주세요.",
            cards=[],
            explanations=[]
        )

    # 1. 개인화 의도 검사 ("내게 맞는 것", "뭘 들어야 해?" 등)
    is_personalization = any(re.search(p, q) for p in PERSONALIZATION_PATTERNS)
    if is_personalization and weak_task:
        tid = weak_task.get("id") or weak_task.get("task_id", "")
        task_name = weak_task.get("name", "")
        sys_msg = f"현재 진단 결과에서 역량 갭이 가장 큰 [{task_name}] 기준으로 추천해 드려요."
        
        cards = cp.task_recommendations(tid, grade_idx, limit=3, use_reranker=use_reranker)
        explanations = []
        for c in cards:
            c_uid = c.get("course_uid", "")
            exp_data = store.get_explanation(tid, c_uid)
            if exp_data:
                explanations.append({
                    "text": exp_data["text"],
                    "source": "① 미리 만든 설명"
                })
            else:
                rule_text = generate_rule_based_explanation(
                    q, c.get("intro_summary", ""), task_name, weak_task.get("k", "")
                )
                explanations.append({
                    "text": rule_text,
                    "source": "② 규칙 기반 설명"
                })

        return ChatRecommendationResult(
            query=query,
            mode="personalization",
            matched_task=weak_task,
            similarity_score=1.0,
            system_message=sys_msg,
            cards=cards,
            explanations=explanations
        )

    # 2. 90개 업무 유사도 계산
    sims = compute_task_similarities(q)
    top1_score, top1_tid, top1_task = sims[0] if sims else (0.0, None, None)
    top2_score, top2_tid, top2_task = sims[1] if len(sims) > 1 else (0.0, None, None)

    # 3. 임계값(0.55) 이상: 업무 매핑
    if top1_score >= TASK_SIMILARITY_THRESHOLD and top1_task:
        dom_info = cp.domain(top1_task.get("dom_id", ""))
        dom_name = dom_info.get("short", "") if dom_info else top1_task.get("dom_id", "")
        sys_msg = f"이 업무로 이해했어요: [{dom_name}] {top1_task['name']}"

        alt_task = top2_task if top2_score >= TASK_SIMILARITY_THRESHOLD else None

        cards = cp.task_recommendations(top1_tid, grade_idx, limit=3, use_reranker=use_reranker)
        explanations = []
        for c in cards:
            c_uid = c.get("course_uid", "")
            exp_data = store.get_explanation(top1_tid, c_uid)
            if exp_data:
                explanations.append({
                    "text": exp_data["text"],
                    "source": "① 미리 만든 설명"
                })
            else:
                rule_text = generate_rule_based_explanation(
                    q, c.get("intro_summary", ""), top1_task["name"], top1_task.get("k", "")
                )
                explanations.append({
                    "text": rule_text,
                    "source": "② 규칙 기반 설명"
                })

        return ChatRecommendationResult(
            query=query,
            mode="task_match",
            matched_task=top1_task,
            similarity_score=top1_score,
            alternative_task=alt_task,
            system_message=sys_msg,
            cards=cards,
            explanations=explanations
        )

    # 4. 임계값 미만: 키워드 과정 검색
    sys_msg = "특정 업무로 딱 좁혀지지 않아서, 입력하신 내용과 가장 가까운 과정을 찾아봤어요."
    df_res = cp.search_courses(q=q)
    cards = []
    if not df_res.empty:
        for _, row in df_res.head(3).iterrows():
            cards.append(cp.make_card(row))

    # 검색 결과가 0건이면 하이브리드 엔진 검색 폴백
    if not cards:
        try:
            top_eng, *_ = cp.engine().recommend(query=q, top_n=3, cluster_boost=0.0)
            cards = [cp.make_card(r) for _, r in top_eng.iterrows()]
        except Exception:
            cards = []

    explanations = []
    for c in cards:
        rule_text = generate_rule_based_explanation(q, c.get("intro_summary", ""))
        explanations.append({
            "text": rule_text,
            "source": "② 규칙 기반 설명"
        })

    return ChatRecommendationResult(
        query=query,
        mode="search",
        matched_task=None,
        similarity_score=top1_score,
        system_message=sys_msg,
        cards=cards,
        explanations=explanations
    )
