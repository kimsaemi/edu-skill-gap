"""
src/chatbot/matcher.py
사용자 질문 → 90개 업무 연결 → 과정 추천

업무 점수 = 의미 유사도(업무명 임베딩 코사인) + LEX_WEIGHT × BM25(업무명·쉬운 설명·K·S)
- BM25는 90개 업무 안에서 드문 단어(4대보험, 연말정산 등)에 높은 가중치를 주고,
  '직무'·'관리'처럼 흔한 단어에는 낮은 가중치를 주므로 별도 키워드 가산점을 두지 않는다.

질문 결과 4가지:
1. task_match  : 업무가 분명할 때 → 그 업무의 기본 추천 3개
2. candidates  : 업무 후보는 있지만 1·2위가 비슷할 때 → 업무 후보 버튼 2개 + 질문 검색 결과
3. search      : 업무 후보가 약할 때 → 질문 검색 결과만
4. out_of_scope: 인사와 무관해 보일 때 → 안내 문구만 (과정 카드 없음)

기준값 근거: scripts/calibrate_chat_threshold.py → docs/chat_threshold_report.md
(질문 묶음이 작아서 바뀔 수 있는 값이다. 질문을 늘리면 다시 계산한다.)
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from src.chatbot.explain import generate_rule_based_explanation, get_preprocessor
from src.customer import career_platform as cp

# 업무 점수 = 의미 유사도 + LEX_WEIGHT × BM25
LEX_WEIGHT: float = 0.03
# 업무가 분명하다고 보는 조건: 점수 ≥ CONFIDENT_SCORE 이거나, 점수 ≥ CANDIDATE_SCORE 이면서 1·2위 차이 ≥ CONFIDENT_MARGIN
CONFIDENT_SCORE: float = 0.80
CONFIDENT_MARGIN: float = 0.15
# 업무 후보 버튼을 보여 줄 최소 점수 (이보다 낮으면 검색 결과만)
CANDIDATE_SCORE: float = 0.50
# 의미 유사도 최고값이 이보다 낮고 인사 관련 단어도 없으면 범위 밖
OUT_OF_SCOPE_SEM: float = 0.38

PERSONALIZATION_PATTERNS = [
    r"내게\s*맞는", r"뭘\s*들어야", r"부족한\s*것", r"뭐부터", r"어디부터",
    r"진단\s*결과", r"나한테\s*맞는",
]

HR_DOMAIN_KEYWORDS: Set[str] = {
    "인사", "채용", "면접", "온보딩", "급여", "임금", "보상", "평가", "성과", "복리후생",
    "4대보험", "근로기준법", "노동법", "노사", "퇴직", "연말정산", "교육", "훈련",
    "조직문화", "직무", "직급", "인력", "취업규칙", "고용보험", "산재", "연차", "휴가",
    "근로계약", "통상임금", "징계", "해고", "호봉", "연봉", "노무", "인적자원",
    "괴롭힘", "성희롱", "고충", "승진", "면담", "hr", "hrd", "엑셀",
}

OUT_OF_SCOPE_MESSAGE = "이 서비스는 인사 교육과정 추천용이에요. 예: '평가 면담을 잘하고 싶어요'"

_TASK_IDS: Optional[List[str]] = None
_TASK_EMB: Optional[np.ndarray] = None
_TASK_BM25 = None


@dataclass
class ChatRecommendationResult:
    query: str
    mode: str  # task_match | candidates | search | out_of_scope | personalization
    matched_task: Optional[Dict[str, Any]] = None
    similarity_score: float = 0.0
    candidate_tasks: List[Dict[str, Any]] = field(default_factory=list)
    system_message: str = ""
    cards: List[Dict[str, Any]] = field(default_factory=list)
    explanations: List[Dict[str, str]] = field(default_factory=list)


def _task_doc(t: Dict[str, Any]) -> str:
    return " ".join(str(t.get(k, "")) for k in ("name", "easy", "k", "s"))


def _init_task_index():
    global _TASK_IDS, _TASK_EMB, _TASK_BM25
    if _TASK_IDS is not None:
        return
    from rank_bm25 import BM25Okapi

    tasks = cp.task_index()
    ids = list(tasks)
    model = cp.engine().model
    _TASK_EMB = np.asarray(model.encode([tasks[i]["name"] for i in ids], normalize_embeddings=True))
    prep = get_preprocessor()
    _TASK_BM25 = BM25Okapi([prep.tokenize(_task_doc(tasks[i])) or ["_"] for i in ids])
    _TASK_IDS = ids


def is_hr_relevant_query(query: str) -> bool:
    ql = query.lower()
    return any(kw in ql for kw in HR_DOMAIN_KEYWORDS)


def compute_task_scores(query: str) -> List[Tuple[float, float, str]]:
    """(업무 점수, 의미 유사도, 업무 ID) 목록을 점수 높은 순으로 반환"""
    q = query.strip()
    if not q:
        return []
    _init_task_index()
    q_emb = np.asarray(cp.engine().model.encode([q], normalize_embeddings=True))[0]
    sem = _TASK_EMB @ q_emb
    toks = get_preprocessor().tokenize(q)
    lex = np.asarray(_TASK_BM25.get_scores(toks)) if toks else np.zeros(len(_TASK_IDS))
    score = sem + LEX_WEIGHT * lex
    order = np.argsort(-score)
    return [(float(score[i]), float(sem[i]), _TASK_IDS[i]) for i in order]


def classify(scores: List[Tuple[float, float, str]], has_hr_context: bool) -> str:
    """점수 목록만으로 4가지 결과 중 하나를 고른다 (테스트·보정 스크립트에서도 같은 함수를 쓴다)"""
    if not scores:
        return "out_of_scope"
    top, top_sem, _ = scores[0]
    second = scores[1][0] if len(scores) > 1 else 0.0
    max_sem = max(s for _, s, _ in scores)
    if max_sem < OUT_OF_SCOPE_SEM and not has_hr_context:
        return "out_of_scope"
    if top >= CONFIDENT_SCORE or (top >= CANDIDATE_SCORE and top - second >= CONFIDENT_MARGIN):
        return "task_match"
    if top >= CANDIDATE_SCORE:
        return "candidates"
    return "search"


def _rule_explanations(query: str, cards: List[Dict[str, Any]], task: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    out = []
    for c in cards:
        if task:
            text = generate_rule_based_explanation(query, c.get("intro_summary", ""), task.get("name"), task.get("k", ""))
        else:
            text = generate_rule_based_explanation(query, c.get("intro_summary", ""))
        out.append({"text": text, "source": "rule"})
    return out


def _search_cards(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """질문 검색: 과정명에 질문이 그대로 들어간 과정이 있으면 그것을, 없으면 기존 1단계 추천 엔진(의미+BM25)을 쓴다.
    제외 목록(off_topic)에 오른 과정은 어느 경우에도 보여 주지 않는다."""
    df = cp.search_courses(q=query)
    if df is not None and not df.empty:
        return [cp.make_card(row) for _, row in df.head(limit).iterrows()]
    try:
        top, *_ = cp.engine().recommend(query=query, cluster_boost=0.0, top_n=limit * 7, mode="general")
    except Exception:
        return []
    base = cp.courses().set_index("course_uid")
    allowed = set(base.index[~base["off_topic"].astype(bool)])
    top = top[top["course_uid"].isin(allowed)]
    return cp._cards_from_engine(top, "", limit)


def recommend_for_task(task_id: str, query: str, grade_idx: int = 1, use_reranker: bool = True,
                       message: Optional[str] = None) -> ChatRecommendationResult:
    """업무를 정한 뒤(분명한 연결 또는 사용자가 후보 버튼 선택) 그 업무의 기본 추천 3개를 반환"""
    task = cp.task_index()[task_id]
    dom = cp.domain(task.get("dom_id", ""))
    dom_name = dom.get("short", "") if dom else task.get("dom_id", "")
    cards = cp.task_recommendations(task_id, grade_idx, limit=3, use_reranker=use_reranker)
    return ChatRecommendationResult(
        query=query,
        mode="task_match",
        matched_task=task,
        system_message=message or f"이 업무로 이해했어요: [{dom_name}] {task['name']}",
        cards=cards,
        explanations=_rule_explanations(query, cards, task),
    )


def match_and_recommend(query: str, grade_idx: int = 1, use_reranker: bool = True,
                        weak_task: Optional[Dict[str, Any]] = None) -> ChatRecommendationResult:
    q = query.strip()
    if not q:
        return ChatRecommendationResult(query=query, mode="out_of_scope", system_message="질문 내용을 입력해 주세요.")

    # 막연한 질문 + 진단 결과가 있으면 부족 업무 1순위로 연결
    if weak_task and any(re.search(p, q) for p in PERSONALIZATION_PATTERNS):
        tid = weak_task.get("id") or weak_task.get("task_id", "")
        res = recommend_for_task(
            tid, q, grade_idx, use_reranker,
            message=f"진단 결과에서 숙련도 차이가 가장 큰 업무 [{weak_task.get('name', '')}] 기준으로 골랐어요.",
        )
        res.mode = "personalization"
        return res

    scores = compute_task_scores(q)
    mode = classify(scores, is_hr_relevant_query(q))
    top_score = scores[0][0] if scores else 0.0

    if mode == "out_of_scope":
        return ChatRecommendationResult(query=query, mode=mode, similarity_score=top_score,
                                        system_message=OUT_OF_SCOPE_MESSAGE)

    if mode == "task_match":
        res = recommend_for_task(scores[0][2], q, grade_idx, use_reranker)
        res.similarity_score = top_score
        return res

    cards = _search_cards(q)
    tasks = cp.task_index()
    if mode == "candidates":
        cands = [tasks[tid] for _, _, tid in scores[:2]]
        msg = "어느 업무에 가까운지 골라 주세요. 그 사이 질문과 가까운 과정을 먼저 찾아봤어요."
    else:
        cands = []
        msg = "특정 업무로 좁혀지지 않아서, 질문과 가까운 과정을 찾아봤어요."
    if not cards:
        msg += " (검색 결과가 없어요. 업무를 조금 더 구체적으로 적어 주세요.)"
    return ChatRecommendationResult(
        query=query, mode=mode, similarity_score=top_score, candidate_tasks=cands,
        system_message=msg, cards=cards, explanations=_rule_explanations(q, cards),
    )
