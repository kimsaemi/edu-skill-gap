"""
고객용 성장·교육 안내 서비스 (팀 v2.1 대시보드 구조를 Streamlit에서 쓰기 위한 데이터·추천 계층)

- 화면 콘텐츠: data/hr/processed/hr_career_platform_master.json
  (직급 5개, 분야 12개, 업무 102개. scripts/extract_career_platform_master.py 로 팀 v2.1 파일에서 추출)
- 교육 데이터: 최신 카탈로그 + 추천 엔진(UnifiedHybridRecommender)
- 업무별 추천: 인사 9개 분야 90개 업무는 미리 계산한 결과(task_course_recommendations_90.csv)를 쓰고,
  나머지 12개 업무(총무·경영지원·비서)는 같은 규칙으로 실행 중에 계산합니다.
- 원칙: 공식 만족도는 정보로만 보여 주고 추천 순위·점수에는 쓰지 않습니다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.assessment.recommendation_bridge import _common_card_fields, get_shared_recommender
from src.recommendation import hr_task_catalog as htc

ROOT = Path(__file__).resolve().parent.parent.parent
MASTER_PATH = ROOT / "data" / "hr" / "processed" / "hr_career_platform_master.json"
TASK_REC_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90.csv"
WORK24_DETAIL_PATH = ROOT / "data" / "hr" / "processed" / "work24_course_details.csv"
SATISFACTION_PATH = ROOT / "data" / "hr" / "processed" / "official_satisfaction.csv"

# 직급(주임·대리·과장·차장·부장) → 업무 숙련도 기준 단계, 추천 난이도
LEVEL_OF_GRADE = [0, 1, 2, 3, 3]
LEVEL_NAMES = ["보조 및 기본 실행", "단독으로 완결", "개선과 최적화", "전략 설계"]
ENGINE_LEVEL_OF_GRADE = ["입문", "실무", "실무", "관리자·심화", "관리자·심화"]
DOMAIN_TAU = 0.60  # 과정이 분야 업무와 '뜻이 가깝다'고 보는 의미 유사도 기준 (발표 대시보드 H2와 같은 값)

DOM_ICON = {"DOM_01": "📈", "DOM_02": "🗂️", "DOM_03": "🤝", "DOM_04": "🌱", "DOM_05": "🎯", "DOM_06": "💰",
            "DOM_07": "🎓", "DOM_08": "💬", "DOM_09": "⚖️", "DOM_10": "🗄️", "DOM_11": "📊", "DOM_12": "🗓️"}
# 엔진의 분야 값 (총무·경영지원·비서 분야만 다르게 줌)
ENGINE_DOMAIN = {"DOM_10": "총무", "DOM_11": "경영지원", "DOM_12": "경영지원"}

# 분야별 대표 실무 역량 (팀 v2.1 대시보드와 같은 목록)
DOMAIN_SKILLS = {
    "DOM_01": ["인력 정원/현원 갭 분석", "인건비 시뮬레이션 모델링", "중장기 인력 마스터플랜 수립", "결원 예측 회귀분석"],
    "DOM_02": ["직무 인터뷰 및 과업 도출", "표준 직무기술서(JD) 작성", "직무가치평가(점수법)", "조직구조 개편 및 통폐합"],
    "DOM_03": ["다이렉트 소싱(링크드인/인재풀)", "역량기반 구조화 면접(BEI) 설계", "채용 브랜딩(EB) 기획", "처우 협상 및 오퍼 제안"],
    "DOM_04": ["온보딩 30-60-90 체크리스트", "1on1 고충 면담 및 리텐션 코칭", "조기 퇴사율 정밀 분석", "조직 적응 가이드 제작"],
    "DOM_05": ["연간 성과목표(OKR/KPI) 합의", "평가 관대화/가혹화 통계 보정", "상시 피드백(CFR) 운영", "360도 다면평가 설계"],
    "DOM_06": ["급여계산 및 4대보험 원천징수", "연봉테이블(Pay Band) 인상 시뮬레이션", "성과급(인센티브) 기준 수식화", "통상임금/퇴직연금 법정 검토"],
    "DOM_07": ["사내 교육과정 개발(ADDIE)", "효과적인 강의 교안·PPT 제작", "고용보험 환급 행정 무결점", "직무역량체계 기반 LMS 구축"],
    "DOM_08": ["기업 핵심가치 컬처덱 편찬", "eNPS 조직몰입도 진단 분석", "사내 타운홀 미팅 기획·운영", "사내 소통 뉴스레터/콘텐츠"],
    "DOM_09": ["취업규칙 제개정 및 적법 신고", "직장 내 괴롭힘 조사·징계위 간사", "노사협의회 안건 협의·회의록", "노조 단체교섭 실무 및 분쟁 예방"],
    "DOM_10": ["문서·기안서 작성과 관리", "비품·자산 관리 및 구매", "행사·의전 운영", "사무 효율화와 업무 자동화"],
    "DOM_11": ["예산 편성과 집행 관리", "재무제표 읽기와 원가 분석", "프로젝트 일정·성과 관리", "경영전략·사업계획 기초"],
    "DOM_12": ["일정·회의 조율과 보고", "비즈니스 매너와 의전", "이메일·문서 커뮤니케이션", "임원 지원 업무 프로세스"],
}
DIGITAL_SKILLS = [
    {"name": "AI 프롬프트 & 생성형 AI 활용", "icon": "🤖"},
    {"name": "데이터 분석 & 시각화", "icon": "📊"},
    {"name": "엑셀 함수 & 피벗 매크로", "icon": "📑"},
    {"name": "반복 업무 자동화", "icon": "⚡"},
]
BIZ_SKILLS = [
    {"name": "기획서 & 보고서 구조화 작성", "icon": "✍️"},
    {"name": "대인 소통 & 설득 커뮤니케이션", "icon": "🗣️"},
    {"name": "과제 일정 & 프로젝트 실행 관리", "icon": "🧭"},
    {"name": "인건비 & 회계 재무 기초", "icon": "💵"},
    {"name": "노무 법률 & 컴플라이언스", "icon": "⚖️"},
]
FIELD_NAMES = {
    "HR": "인사·조직·직무", "GA": "총무·사무행정", "DATA_AI": "데이터·AI", "FIN": "재무·회계", "IT_DEV": "IT·개발",
    "LANG": "외국어", "MKT": "마케팅·영업", "PROD": "생산·품질", "MED": "의료·보건", "LEGAL_IP": "법무·지식재산",
}


# ---------------------------------------------------------------------------
# 데이터 적재
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def master() -> Dict[str, Any]:
    return json.loads(MASTER_PATH.read_text(encoding="utf-8"))


def grades() -> List[Dict[str, Any]]:
    return master()["grades"]


def domains() -> List[Dict[str, Any]]:
    return master()["domains"]


def domain(dom_id: str) -> Optional[Dict[str, Any]]:
    return next((d for d in domains() if d["id"] == dom_id), None)


def domain_tasks(dom_id: str) -> List[Dict[str, Any]]:
    d = domain(dom_id)
    return (d or {}).get("tasks", [])


@lru_cache(maxsize=1)
def task_index() -> Dict[str, Dict[str, Any]]:
    out = {}
    for d in domains():
        for t in d.get("tasks", []):
            out[t["id"]] = {**t, "dom_id": d["id"]}
    return out


@lru_cache(maxsize=1)
def review_task_ids() -> frozenset:
    """역량 연결 검토가 필요한 업무 (90개 업무 카탈로그의 needs_review + 팀 표시 rv)."""
    ids = {tid for tid, t in task_index().items() if t.get("rv")}
    for t in htc.get_hr_tasks():
        if t.get("needs_review"):
            ids.add(t["source_task_id"])
    return frozenset(ids)


def engine():
    return get_shared_recommender()


@lru_cache(maxsize=1)
def courses() -> pd.DataFrame:
    """엔진 코퍼스 + 분야 연결 + 고용24 상세(일정·자기부담금·만족도)."""
    eng = engine()
    df = eng.df_courses.copy()
    df["_idx"] = np.arange(len(df))
    df["off_topic"] = df["course_uid"].isin(eng.off_topic_uids)

    # 분야 연결: 분야 업무 설명과 의미 유사도가 DOMAIN_TAU 이상인 분야 (발표 대시보드 H2와 같은 계산)
    dom_ids, texts = [], []
    for tid, t in task_index().items():
        dom_ids.append(t["dom_id"])
        texts.append(f"{t['name']}. {t.get('easy', '')}")
    if eng.has_embeddings and eng.model is not None:
        tv = eng.model.encode(texts, normalize_embeddings=True)
        sims = tv @ eng.embeddings.T
        uniq = list(dict.fromkeys(dom_ids))
        best = np.vstack([sims[[i for i, x in enumerate(dom_ids) if x == d]].max(0) for d in uniq])
        df["doms"] = [[uniq[k] for k in np.where(best[:, j] >= DOMAIN_TAU)[0]] for j in range(len(df))]
    else:
        df["doms"] = [[] for _ in range(len(df))]

    # 고용24 상세: 운영 상태·다음 회차·자기부담금·공식 만족도
    sat = {}
    if SATISFACTION_PATH.exists():
        s = pd.read_csv(SATISFACTION_PATH, dtype={"trprId": str}).dropna(subset=["satisfaction_official"])
        sat.update(dict(zip(s["trprId"], s["satisfaction_official"])))
    det = pd.DataFrame()
    if WORK24_DETAIL_PATH.exists():
        det = pd.read_csv(WORK24_DETAIL_PATH, dtype={"trprId": str})
        if "satisfaction_official" in det.columns:
            d2 = det.dropna(subset=["satisfaction_official"])
            sat.update(dict(zip(d2["trprId"], d2["satisfaction_official"])))
    sid = df["source_course_id"].astype(str)
    df["sat"] = sid.map(sat)
    if not det.empty:
        det = det.set_index("course_uid")
        for col, new in [("running_status", "w24_status"), ("self_pay", "self_pay"), ("program", "w24_program")]:
            df[new] = df["course_uid"].map(det[col]) if col in det.columns else None
    return df


@lru_cache(maxsize=1)
def task_rec_table() -> pd.DataFrame:
    if not TASK_REC_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(TASK_REC_PATH)


# ---------------------------------------------------------------------------
# 카드
# ---------------------------------------------------------------------------
def platform_label(row: pd.Series) -> str:
    src = str(row.get("source_provider") or "")
    if src.startswith("고용24_"):
        return src.replace("고용24_", "")
    return str(row.get("provider") or "")


def make_card(row: pd.Series, why: str = "", match: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """카드 1장에 필요한 값. 가격·시간·일정·종료 표시는 공통 함수(_common_card_fields)를 그대로 씀."""
    base = _common_card_fields(row, 4.0)
    sat = row.get("sat")
    self_pay = row.get("self_pay")
    field = row.get("field")
    return {
        **base,
        "institution": str(row.get("provider") or ""),
        "platform": platform_label(row),
        "kind": "direct" if field in ("HR", "GA") else "common",
        "field_name": FIELD_NAMES.get(field, ""),
        "doms": list(row.get("doms") or []),
        "sat": float(sat) if pd.notna(sat) else None,
        "self_pay": int(self_pay) if pd.notna(self_pay) else None,
        "w24_status": row.get("w24_status") if isinstance(row.get("w24_status"), str) else None,
        "goals": str(row.get("clean_goals") or "")[:220],
        "curriculum": str(row.get("clean_curriculum") or "")[:260],
        "audience": str(row.get("target_audience") or "")[:160],
        "ncs": str(row.get("ncs_code") or ""),
        "match": match,  # {"final", "sem", "bm25", "lvl"}
        "why": why,
    }


def _row(uid: str) -> Optional[pd.Series]:
    df = courses()
    hit = df.index[df["course_uid"] == uid]
    return df.loc[hit[0]] if len(hit) else None


def _cards_from_engine(df_top: pd.DataFrame, why: str, limit: int, gate: bool = False) -> List[Dict[str, Any]]:
    cards = []
    base = courses().set_index("course_uid")
    for _, r in df_top.iterrows():
        if gate and not htc.passes_task_gate(float(r.get("semantic_score", 0)), float(r.get("anchor_score", 0)), r.get("field")):
            continue
        uid = r["course_uid"]
        if uid not in base.index:
            continue
        row = base.loc[uid].copy()
        row["course_uid"] = uid
        for k in ("final_score", "semantic_score", "bm25_score", "level_bonus"):
            row[k] = r.get(k)
        match = {"final": round(float(r.get("final_score", 0)), 1), "sem": round(float(r.get("semantic_score", 0)), 1),
                 "bm25": round(float(r.get("bm25_score", 0)), 1), "lvl": round(float(r.get("level_bonus", 0)), 1)}
        cards.append(make_card(row, why, match))
        if len(cards) >= limit:
            break
    return cards


# ---------------------------------------------------------------------------
# 추천
# ---------------------------------------------------------------------------
def _hr_task_id(source_task_id: str) -> str:
    """DOM_01_T01 → TASK_HR_D01_T01 (인사 90개 업무 카탈로그 ID)."""
    parts = source_task_id.split("_")
    return f"TASK_HR_D{parts[1]}_{parts[2]}" if len(parts) == 3 else source_task_id


@lru_cache(maxsize=512)
def task_recommendations(task_id: str, grade_idx: int, limit: int = 6) -> List[Dict[str, Any]]:
    """업무 1개에 맞는 교육. 직급 난이도를 먼저, 부족하면 다른 난이도 결과로 채움."""
    t = task_index().get(task_id)
    if not t:
        return []
    level = ENGINE_LEVEL_OF_GRADE[grade_idx]
    why = f"[{t['name'][:22]}{'…' if len(t['name']) > 22 else ''}] 업무 보완"
    tab = task_rec_table()
    hr_id = _hr_task_id(task_id)
    if not tab.empty and (tab["task_id"] == hr_id).any():
        sub = tab[tab["task_id"] == hr_id].copy()
        sub["_lv"] = (sub["level"] != level).astype(int)
        sub = sub.sort_values(["_lv", "rank"]).drop_duplicates("course_uid")
        return _cards_from_engine(sub, why, limit)
    # 미리 계산하지 않은 업무 (총무·경영지원·비서): 같은 규칙으로 계산
    task = {"task_name": t["name"], "easy_description": t.get("easy", ""), "knowledge": t.get("k", ""), "skill": t.get("s", "")}
    top, *_ = engine().recommend(
        query=htc.task_semantic_query(task), keyword_query=htc.task_keyword_query(task),
        keyword_stopwords=htc.GENERIC_TASK_TOKENS, anchor_query=htc.task_anchor_query(task),
        target_domain=ENGINE_DOMAIN.get(t["dom_id"], "인사"), user_level=level,
        cluster_boost=0.0, filter_mismatch_109=True, top_n=25, mode="general",
    )
    return _cards_from_engine(top, why, limit, gate=True)


@lru_cache(maxsize=256)
def domain_recommendations(dom_id: str, grade_idx: int, limit: int = 18) -> List[Dict[str, Any]]:
    """직급 × 분야 기본 추천 (분야 설명으로 검색)."""
    d = domain(dom_id)
    if not d:
        return []
    top, *_ = engine().recommend(
        query=f"{d.get('full', d['short'])} {d.get('brief', '')}", keyword_query=f"{d.get('search', '')} {d['short']}",
        target_domain=ENGINE_DOMAIN.get(dom_id, "인사"), user_level=ENGINE_LEVEL_OF_GRADE[grade_idx],
        cluster_boost=0.0, filter_mismatch_109=True, top_n=limit, mode="general",
    )
    return _cards_from_engine(top, f"{d['short']} 분야 기본 추천", limit)


@lru_cache(maxsize=256)
def skill_recommendations(skill: str, grade_idx: int, limit: int = 6) -> List[Dict[str, Any]]:
    top, *_ = engine().recommend(
        query=f"{skill} 실무 역량 강화 교육", keyword_query=skill, user_level=ENGINE_LEVEL_OF_GRADE[grade_idx],
        cluster_boost=0.0, filter_mismatch_109=True, top_n=limit * 2, mode="general",
    )
    return _cards_from_engine(top, f"'{skill}' 역량 보완", limit)


# ---------------------------------------------------------------------------
# 전체 교육 찾기
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def platform_series() -> pd.Series:
    """과정별 '교육기관·제도' 표시값 (고용24 과정은 국민내일배움카드·사업주훈련으로 묶음)."""
    df = courses()
    src = df["source_provider"].astype(str)
    return pd.Series(np.where(src.str.startswith("고용24_") & ~src.str.contains("NCS"), src.str.replace("고용24_", ""), df["provider"]), index=df.index)


def platform_options() -> List[str]:
    vc = platform_series()[~courses()["off_topic"]].value_counts()
    return [p for p, n in vc.items() if n >= 5]


def search_courses(q: str = "", field: str = "ALL", dom_id: str = "ALL", platform: str = "ALL", level: str = "ALL",
                   cost: str = "ALL", open_only: bool = False, sat_only: bool = False) -> pd.DataFrame:
    df = courses()
    m = ~df["off_topic"]
    if q.strip():
        ql = q.strip().lower()
        m &= df["title"].str.lower().str.contains(ql, regex=False, na=False) | df["provider"].str.lower().str.contains(ql, regex=False, na=False)
    if field != "ALL":
        m &= df["field"] == field
    if dom_id != "ALL":
        m &= df["doms"].map(lambda x: dom_id in x)
    if platform != "ALL":
        m &= platform_series() == platform
    if level != "ALL":
        dif = df["difficulty"].fillna("").astype(str)
        pat = {"초급": "초급|입문", "중급": "중급", "고급": "고급"}[level]
        m &= dif.str.contains(pat)
    if cost == "FREE":
        m &= df["price_status"] == "FREE"
    elif cost == "GOV":
        m &= df["price_type"].astype(str).str.contains("국비")
    elif cost == "U30":
        m &= (df["price_status"] == "FREE") | ((df["price_status"] == "PAID") & (df["numeric_price"] <= 300000))
    if open_only:
        today = pd.Timestamp.today().strftime("%Y-%m-%d")
        end = df["end_date"].fillna("").astype(str).str[:10]
        m &= (end == "") | (end >= today)
    if sat_only:
        m &= df["sat"].notna()
    # 정렬: 인사·총무 분야 우선, 그다음 설명이 충분한 과정 (만족도는 정렬에 쓰지 않음)
    out = df[m].copy()
    out["_k1"] = (~out["field"].isin(["HR", "GA"])).astype(int)
    out["_k2"] = (out["text_quality_status"] != "RICH").astype(int)
    return out.sort_values(["_k1", "_k2", "_idx"])
