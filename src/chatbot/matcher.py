"""
src/chatbot/matcher.py
사용자 질문 분석 및 90개 업무 매핑 모듈
- 기준값 근거: scripts/calibrate_chat_threshold.py 실측 결과 (docs/chat_threshold_report.md 참조)
  * 비관련 일상 질의 10건의 최고 유사도 점수는 0.3751 ('안녕 반가워')
  * 실제 인사 실무 자연어 질의 10건의 평균 유사도는 0.6932
  * 무관 질의 오매핑을 원천 차단하고 실무 질문을 안정적으로 포착하기 위해 TASK_SIMILARITY_THRESHOLD = 0.42 로 설정
  * 점수가 0.38 미만이며 HR 키워드가 포함되지 않은 경우 범위 밖(out_of_scope)으로 분기
- 흔한 단어(직무, 관리, 인사)에 대한 인위적 키워드 가산점 배제
- 질문 결과 3분기:
  1. 업무 연결 (task_match): 점수 >= 0.42
  2. 검색 (search): 점수 < 0.42 이지만 인사 관련 키워드/과정이 있는 경우
  3. 범위 밖 (out_of_scope): 점수 < 0.38 및 인사 관련 키워드 부재 -> 안내 문구만 표시하고 과정 미노출
"""
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import numpy as np

from src.customer import career_platform as cp
from src.chatbot.explain import generate_rule_based_explanation, get_preprocessor
from src.chatbot.store import get_default_store, ExplanationStore

# 기준값 근거: scripts/calibrate_chat_threshold.py 실측 결과(docs/chat_threshold_report.md)
# 무관 질의 최고점수(0.3751)를 상회하며 실무 질의를 안정적으로 수용하는 0.42 설정
TASK_SIMILARITY_THRESHOLD: float = 0.42
OUT_OF_SCOPE_THRESHOLD: float = 0.38

PERSONALIZATION_PATTERNS = [
    r"내게\s*맞는", r"뭘\s*들어야", r"부족한\s*것", r"어떤\s*걸", r"뭐부터",
    r"어디부터", r"진단\s*결과", r"나한테\s*맞는", r"추천해\s*줘"
]

HR_DOMAIN_KEYWORDS: Set[str] = {
    "인사", "채용", "면접", "온보딩", "급여", "임금", "보상", "평가", "성과", "복리후생",
    "4대보험", "근로기준법", "노동법", "노사", "퇴직", "퇴직금", "연말정산", "교육", "훈련",
    "조직문화", "직무", "직급", "인력", "취업규칙", "고용보험", "산재", "연차", "휴가",
    "jd", "ksa", "hr", "hrd", "hrm", "근로계약", "통상임금", "파견", "전보", "징계",
    "해고", "직무급", "호봉제", "연봉제", "다면평가", "역량평가", "노사협의회", "단체교섭",
    "고충처리", "괴롭힘", "성희롱", "인센티브", "스톡옵션", "노무", "인적자원", "데이터"
}

_TASK_CACHE: Optional[Dict[str, Any]] = None
_TASK_EMBEDDINGS: Optional[Dict[str, np.ndarray]] = None


@dataclass
class ChatRecommendationResult:
    query: str
    mode: str  # "task_match" | "personalization" | "search" | "out_of_scope"
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


def is_hr_relevant_query(query: str) -> bool:
    """질문에 인사·노무·교육 도메인 관련 키워드가 포함되어 있는지 판별"""
    ql = query.lower()
    for kw in HR_DOMAIN_KEYWORDS:
        if kw in ql:
            return True
    return False


def compute_task_similarities(query: str) -> List[Tuple[float, str, Dict[str, Any]]]:
    """사용자 질문과 90개 업무 간의 임베딩 유사도 계산 (흔한 단어 가산점 전면 배제)"""
    _init_task_cache()
    eng = cp.engine()

    q_clean = query.strip()
    if not q_clean:
        return []

    q_emb = eng.model.encode(q_clean, normalize_embeddings=True)

    scores = []
    for tid, t in _TASK_CACHE.items():
        t_emb = _TASK_EMBEDDINGS[tid]
        cos_sim = float(np.dot(q_emb, t_emb))

        # 업무명 전체가 질문에 포함되어 있을 때만 안전하게 소폭 가산 (+0.05)
        t_name = t.get("name", "")
        if t_name and t_name in q_clean:
            cos_sim = min(1.0, cos_sim + 0.05)

        scores.append((cos_sim, tid, t))

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
    사용자 질의를 분석하여 업무 매핑 / 검색 / 범위 밖 안내로 3분기 처리하고
    과정 카드 및 추천 이유를 반환합니다.
    """
    store = store or get_default_store()
    q = query.strip()
    if not q:
        return ChatRecommendationResult(
            query=query,
            mode="out_of_scope",
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
                    "source": "claude_draft"
                })
            else:
                rule_text = generate_rule_based_explanation(
                    q, c.get("intro_summary", ""), task_name, weak_task.get("k", "")
                )
                explanations.append({
                    "text": rule_text,
                    "source": "rule"
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

    has_hr_context = is_hr_relevant_query(q)

    # 3. 분기 1: 범위 밖 (점수 < 0.38 이며 인사 키워드 부재)
    if top1_score < OUT_OF_SCOPE_THRESHOLD and not has_hr_context:
        return ChatRecommendationResult(
            query=query,
            mode="out_of_scope",
            matched_task=None,
            similarity_score=top1_score,
            system_message="이 서비스는 인사 교육과정 추천용이에요. 예: '평가 면담을 잘하고 싶어요'",
            cards=[],
            explanations=[]
        )

    # 4. 분기 2: 업무 연결 (점수 >= 0.42)
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
                    "source": "claude_draft"
                })
            else:
                rule_text = generate_rule_based_explanation(
                    q, c.get("intro_summary", ""), top1_task["name"], top1_task.get("k", "")
                )
                explanations.append({
                    "text": rule_text,
                    "source": "rule"
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

    # 5. 분기 3: 검색 모드 (점수 < 0.42 이지만 인사 관련 질의인 경우)
    sys_msg = "특정 업무로 딱 좁혀지지 않아서, 입력하신 내용과 가장 가까운 과정을 찾아봤어요."
    df_res = cp.search_courses(q=q)
    cards = []
    if not df_res.empty:
        for _, row in df_res.head(3).iterrows():
            cards.append(cp.make_card(row))

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
            "source": "rule"
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
