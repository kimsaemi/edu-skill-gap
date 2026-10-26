"""
발표용 웹 대시보드(presentation/) 데이터 추출
파일명: scripts/build_presentation_data.py

현재 정제된 데이터에서 발표 페이지에 들어갈 숫자를 다시 계산해 presentation/src/data.json에 저장합니다.
(정정 전 결과가 남아 있는 군집 요약·상위 키워드 파일은 쓰지 않습니다.)

사용법:
  python scripts/build_presentation_data.py
  python scripts/build_presentation.py        # 데이터 + 템플릿 + 글꼴을 묶어 presentation/index.html 생성
"""

import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402  (src 패키지를 불러오기 위해)
sys.path.insert(0, str(ROOT))
PROCESSED = ROOT / "data" / "hr" / "processed"
RECO = ROOT / "data" / "hr" / "output" / "recommendation"
OUT = ROOT / "presentation" / "src" / "data.json"

FIELD_NAMES = {
    "HR": "인사·조직·직무 일반", "DATA_AI": "데이터·AI 활용", "IT_DEV": "IT·개발",
    "LANG": "외국어", "PROD": "생산·품질", "MKT": "마케팅·영업", "GA": "총무·사무행정",
    "FIN": "재무·회계", "MED": "의료·보건", "LEGAL_IP": "법무·지식재산",
}

# NCS 수요 분석 보고서(NCS_Demand_Analysis_Report.md)의 레벨 분포
NCS_DEMAND = [
    {"label": "입문 (L1~2)", "pct": 10},
    {"label": "주니어 실무 (L3~4)", "pct": 48},
    {"label": "중급 (L5~6)", "pct": 32},
    {"label": "시니어 (L7~8)", "pct": 10},
]

# 리서치에서 뽑은 공통 핵심 역량과 강좌 텍스트에서 찾을 키워드 (app/streamlit_research.py와 동일)
CORE_SKILLS = {
    "생성형 AI 활용": ["생성형", "chatgpt", "챗gpt", "프롬프트"],
    "데이터 분석·시각화": ["데이터", "시각화", "파이썬", "python", "sql", "대시보드"],
    "엑셀·업무 자동화": ["엑셀", "매크로", "vba", "자동화", "스프레드시트"],
    "노무·준법": ["노무", "근로기준", "준법", "개인정보", "4대보험", "노동법"],
    "문서·보고서 작성": ["보고서", "문서", "기획서", "공문서", "파워포인트"],
    "리더십·소통·협업": ["리더십", "협업", "커뮤니케이션", "팀워크"],
}


def pct(n, d):
    return round(n / d * 100, 1) if d else 0.0


MISSING_COLS = [
    ("title", "과정명"), ("provider", "교육기관"), ("price", "가격"), ("education_type", "교육 형태"),
    ("learning_goals", "학습 목표"), ("course_intro", "과정 소개"), ("curriculum", "커리큘럼"),
    ("difficulty", "난이도"), ("ncs_code", "NCS·역량 코드"), ("duration_hours", "총 교육시간"), ("start_date", "개강일"),
]
CLEAN_ACTIONS = [
    ("BLOCKED_PAGE_REMOVED", "차단 안내문 제거"),
    ("BOILERPLATE_REMOVED", "홍보 상용문구 제거"),
    ("IDENTICAL_GOALS_DEDUPED", "목표 중복 정리"),
    ("IDENTICAL_INTRO_DEDUPED", "소개 중복 정리"),
    ("BASE64_STRIPPED", "이미지 코드 제거"),
]
DOMAIN_TAU = 0.60  # 과업 설명과 과정 임베딩의 코사인 유사도가 이 값 이상이면 '이 영역에 맞는 과정'으로 셈


def is_missing(s):
    return s.isna() | s.astype(str).str.strip().isin(["", "nan", "None", "<NA>"])


def build_eda(df, off_topic, tasks_raw, top3, rec, summary, n):
    """발표 03~05장의 근거가 되는 탐색적 분석 값."""
    # 1) 주요 칼럼 결측률
    missing = [{"col": c, "label": lab, "pct": pct(is_missing(df[c]).sum(), n)} for c, lab in MISSING_COLS]

    # 2) 정제 규칙 적용 건수
    acts = df["cleaning_actions"].astype(str).str.split(r"[;,]\s*").explode().value_counts()
    cleaning = [{"key": k, "label": lab, "n": int(acts.get(k, 0))} for k, lab in CLEAN_ACTIONS]

    # 3) 인사 실무 9개 영역별 공급: 영역 과업 중 하나와 의미 유사도가 DOMAIN_TAU 이상인 과정 수
    from sentence_transformers import SentenceTransformer
    emb = np.load(RECO / "embeddings_ko_sroberta_all.npy")
    keep = ~df["course_uid"].isin(off_topic).values
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")
    tvec = model.encode([f"{t['task_name']}. {t.get('easy_description', '')}" for t in tasks_raw], normalize_embeddings=True)
    sims = tvec @ emb[keep].T
    doms = [t["domain_name"] for t in tasks_raw]
    dom_ids = {t["domain_name"]: t["domain_id"] for t in tasks_raw}
    top1 = rec[rec["rank"] == 1].groupby("domain_id")["semantic_score"].median()
    mid_plus_mask = df.loc[keep, "difficulty"].fillna("").astype(str).str.contains("중급|고급").values
    domain_supply = []
    for d in dict.fromkeys(doms):
        idx = [i for i, x in enumerate(doms) if x == d]
        hit = sims[idx].max(0) >= DOMAIN_TAU
        domain_supply.append({
            "label": d, "n": int(hit.sum()), "mid_plus": int((hit & mid_plus_mask).sum()),
            "top1_sem": round(float(top1.get(dom_ids[d], np.nan)), 1),
        })

    # 4) 추천의 기관 편중: 카탈로그 비중 vs 추천 Top 3 비중
    cat_share = df["provider"].value_counts(normalize=True)
    rec_share = top3["provider"].value_counts(normalize=True)
    provider_bias = [
        {"label": p, "catalog": round(float(cat_share.get(p, 0)) * 100, 1), "top3": round(float(rec_share.get(p, 0)) * 100, 1)}
        for p in rec_share.head(6).index
    ]

    # 5) 인사·총무 분야 과정의 비용·시간
    hrga = df[df["field"].isin(["HR", "GA"]) & ~df["course_uid"].isin(off_topic)]  # df에는 분야 라벨이 이미 붙어 있음
    price = pd.to_numeric(hrga["price"], errors="coerce")
    hours = pd.to_numeric(hrga["duration_hours"], errors="coerce")
    cost = {
        "n": int(len(hrga)), "free": int((price == 0).sum()), "unknown": int(price.isna().sum()),
        "paid_median": int(price[price > 0].median()), "hours_median": float(hours.median()),
        "hours_unknown": int(hours.isna().sum()),
    }

    # 6) 일정 정보의 최신성 (카탈로그 전체)
    today = date.today().isoformat()
    st = df["start_date"].fillna("").astype(str).str[:10]
    en = df["end_date"].fillna("").astype(str).str[:10]
    en = en.where(en != "", st)
    has = st.str.match(r"\d{4}-\d{2}-\d{2}")
    schedule = {
        "no_date": int((~has).sum()), "future": int((has & (st > today)).sum()),
        "ongoing": int((has & (st <= today) & (en >= today)).sum()), "past": int((has & (en < today)).sum()),
    }

    # 7) 장기 모니터링 지표 (대시보드용)
    combos = len(tasks_raw) * 3
    lt3 = int(summary.get("task_level_with_lt3_results", 0))
    w24 = df["source_course_id"].astype(str).str.fullmatch(r"A[A-Z]{2}\d{14}")
    w24_open = (en[w24] >= today).sum()
    bias_max = max(provider_bias, key=lambda x: x["top3"] - x["catalog"])
    monitor = {
        "coverage_pct": pct(combos - lt3, combos),
        "w24_open_pct": pct(w24_open, int(w24.sum())),
        "bias_provider": bias_max["label"], "bias_top3": bias_max["top3"], "bias_catalog": bias_max["catalog"],
        "top5_share": round(float(cat_share.head(5).sum()) * 100, 1),
    }
    robust = build_robustness(df, off_topic, tasks_raw, sims, keep, emb, model, top3, cat_share, rec_share)
    return {"missing": missing, "cleaning": cleaning, "domain_supply": domain_supply, "domain_tau": DOMAIN_TAU,
            "provider_bias": provider_bias, "cost": cost, "schedule": schedule, "monitor": monitor, "robust": robust}


# 영역별 키워드 (의미 기준과 비교하는 두 번째 방법. '소통'처럼 넓은 단어는 뺌)
DOMAIN_KEYWORDS = {
    "인사전략·인력기획": "인사전략|인력계획|인력운영|HR전략|인건비",
    "조직설계·직무분석": "조직설계|직무분석|직무설계|조직구조|직무기술서|직무관리",
    "인재채용": "채용|면접|인재선발|구인",
    "온보딩·직원경험": "온보딩|입문교육|신입사원|직원경험",
    "성과평가·목표관리": "인사평가|성과평가|성과관리|KPI|OKR|목표관리|평가제도|역량평가",
    "보상·급여·복리후생": "급여|임금|보상|연봉|퇴직금|복리후생|연말정산|4대보험|원천징수",
    "인재육성·사내교육": "HRD|교육기획|교육훈련|사내강사|인재육성|교육체계|교수설계",
    "조직문화·사내소통": "조직문화|조직개발|조직활성화|사내소통|구성원 몰입",
    "노사관계·노무": "노무|노사|근로기준|노동법|취업규칙|해고|징계|근로계약|노동조합",
}
MAIN_PROVIDERS = ["GSEEK", "휴넷", "한국능률협회(KMA)", "한국생산성본부(KPC)", "멀티캠퍼스"]


def build_robustness(df, off_topic, tasks_raw, sims, keep, emb, model, top3, cat_share, rec_share):
    """2~5번 추가 검증: 기관 편중 원인, 영역 공급 민감도, 결측 편향, 비용×수준."""
    import importlib.util
    from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender as U

    dk = df[keep].reset_index(drop=True)
    norm = dk["title"].map(U.normalize_course_title)
    doms = [t["domain_name"] for t in tasks_raw]

    # (3) 영역별 공급 민감도: 의미 기준 3가지 기준값 + 제목 중복 제거 + 키워드 기준
    text = dk["title"].fillna("") + " " + dk["clean_search_text"].fillna("")
    rows = []
    for d in dict.fromkeys(doms):
        best = sims[[i for i, x in enumerate(doms) if x == d]].max(0)
        rows.append({
            "label": d,
            "s055": int((best >= 0.55).sum()), "s060": int((best >= 0.60).sum()), "s065": int((best >= 0.65).sum()),
            "s060_titles": int(norm[best >= 0.60].nunique()),
            "keyword": int(text.str.contains(DOMAIN_KEYWORDS[d], regex=True).sum()),
        })
    sens = pd.DataFrame(rows).set_index("label")
    ranks = sens.rank(method="min").astype(int)  # 1 = 가장 적음
    sensitivity = [{"label": d, **{k: int(v) for k, v in sens.loc[d].items()}, "ranks": {k: int(v) for k, v in ranks.loc[d].items()}}
                   for d in sens.index]

    # (2) 기관 편중 분해: 카탈로그 → 의미 상위 50 후보 → 제목 중복 제거 후보 → 추천 Top 3
    spec = importlib.util.spec_from_file_location("btc", ROOT / "scripts" / "build_hr_task_catalog.py")
    btc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(btc)
    qv = model.encode([btc.task_semantic_text(t) for t in tasks_raw], normalize_embeddings=True)
    sem_all = qv @ emb.T
    norm_all = df["title"].map(U.normalize_course_title).values
    prov_all = df["provider"].values
    pool, pool_dedup = [], []
    for i in range(len(tasks_raw)):
        order = np.argsort(-sem_all[i])
        pool += list(prov_all[order[:50]])
        seen = set()
        for j in order:
            if norm_all[j] in seen:
                continue
            seen.add(norm_all[j])
            pool_dedup.append(prov_all[j])
            if len(seen) == 50:
                break
    p1 = pd.Series(pool).value_counts(normalize=True)
    p2 = pd.Series(pool_dedup).value_counts(normalize=True)
    g = df.groupby("provider")
    bias_steps = [{
        "label": p,
        "catalog": round(float(cat_share.get(p, 0)) * 100, 1), "pool": round(float(p1.get(p, 0)) * 100, 1),
        "pool_dedup": round(float(p2.get(p, 0)) * 100, 1), "top3": round(float(rec_share.get(p, 0)) * 100, 1),
        "rows_per_title": round(float(g.size()[p] / g["title"].nunique()[p]), 2),
    } for p in ["한국생산성본부(KPC)", "한국능률협회(KMA)", "GSEEK", "휴넷", "멀티캠퍼스"]]

    # (4) 결측 편향: 기관별 결측률, 난이도 표기 과정의 기관 구성, H1 초급 비율 시나리오
    def miss(s):
        return s.isna() | s.astype(str).str.strip().isin(["", "nan", "None", "<NA>", "난이도"])
    w24 = df["source_course_id"].astype(str).str.fullmatch(r"A[A-Z]{2}\d{14}")
    grp = np.where(w24, "고용24", np.where(df["provider"].isin(MAIN_PROVIDERS), df["provider"], "기타"))
    gm = df.assign(grp=grp).groupby("grp")
    missing_by_provider = [{
        "label": k, "n": int(len(v)),
        **{c: round(float(miss(v[c]).mean()) * 100, 1) for c in ["difficulty", "duration_hours", "price", "start_date"]},
    } for k, v in gm if k != "기타"]
    d = df["difficulty"].fillna("").astype(str)
    lvl = np.select([d.str.contains("초급|입문"), d.str.startswith("중급"), d.str.startswith("고급")], ["초급", "중급", "고급"], "")
    lab = df.assign(grp=grp, lvl=lvl)
    lab = lab[lab["lvl"] != ""]

    def beg(x):
        return round(float((x["lvl"] == "초급").mean()) * 100, 1)
    hrga = lab["field"].isin(["HR", "GA"]) & ~lab["course_uid"].isin(off_topic)
    h1_scenarios = [
        {"label": "전체", "pct": beg(lab), "n": int(len(lab))},
        {"label": "인사·총무 분야만", "pct": beg(lab[hrga]), "n": int(hrga.sum())},
        {"label": "휴넷 제외", "pct": beg(lab[lab["grp"] != "휴넷"]), "n": int((lab["grp"] != "휴넷").sum())},
        {"label": "GSEEK 제외", "pct": beg(lab[lab["grp"] != "GSEEK"]), "n": int((lab["grp"] != "GSEEK").sum())},
        {"label": "GSEEK·휴넷 제외", "pct": beg(lab[~lab["grp"].isin(["GSEEK", "휴넷"])]), "n": int((~lab["grp"].isin(["GSEEK", "휴넷"])).sum())},
    ]
    label_share = (lab["grp"].value_counts(normalize=True) * 100).round(1)
    label_source = [{"label": k, "pct": float(v)} for k, v in label_share.items() if v >= 1]

    # (5) 비용 × 수준 (인사·총무 분야, 직무 무관 제외)
    h = df.assign(lvl=lvl)
    h = h[h["field"].isin(["HR", "GA"]) & ~h["course_uid"].isin(off_topic)]
    p = pd.to_numeric(h["price"], errors="coerce")
    hrs = pd.to_numeric(h["duration_hours"], errors="coerce")
    cost_by_level = []
    for name in ["초급", "중급", "고급"]:
        m = (h["lvl"] == name).values
        pp, hh = p[m], hrs[m]
        known = pp.notna()
        cost_by_level.append({
            "label": name, "n": int(m.sum()), "paid_median": int(pp[pp > 0].median()) if (pp > 0).any() else None,
            "under30_pct": round(float(((pp <= 300000) & known).sum() / max(1, known.sum())) * 100, 1),
            "hours_median": float(hh.median()) if hh.notna().any() else None,
            "gov_pct": round(float(h.loc[m, "price_type"].astype(str).str.contains("국비").mean()) * 100, 1),
        })
    mid = h["lvl"].isin(["중급", "고급"])
    mid_gov = int(h.loc[mid, "price_type"].astype(str).str.contains("국비").sum())
    return {
        "sensitivity": sensitivity, "bias_steps": bias_steps, "missing_by_provider": missing_by_provider,
        "h1_scenarios": h1_scenarios, "label_source": label_source, "cost_by_level": cost_by_level,
        "mid_total": int(mid.sum()), "mid_gov": mid_gov, "mid_gov_pct": pct(mid_gov, int(mid.sum())),
    }


def main():
    df = pd.read_parquet(PROCESSED / "education_courses_search_cleaned.parquet")
    fields = pd.read_csv(RECO / "course_field_labels.csv")
    df = df.merge(fields[["course_uid", "field"]], on="course_uid", how="left")
    off_topic = set(pd.read_csv(PROCESSED / "off_topic_exclusions.csv", encoding="utf-8-sig")["course_uid"].astype(str))
    n = len(df)

    # 1) 공급처
    prov = df["provider"].value_counts()
    top_prov = [{"label": k, "n": int(v)} for k, v in prov.head(6).items()]
    top_prov.append({"label": f"기타 {prov.size - 6}개 기관", "n": int(prov.iloc[6:].sum())})

    # 2) 텍스트 품질
    tq_names = {"RICH": "상세 설명 있음 (200자 이상)", "MODERATE": "요약 소개만", "VERY_SHORT": "아주 짧음", "TITLE_ONLY": "제목만"}
    tq = df["text_quality_status"].value_counts()
    text_quality = [{"key": k, "label": tq_names.get(k, k), "n": int(tq.get(k, 0))} for k in ["RICH", "MODERATE", "VERY_SHORT", "TITLE_ONLY"]]

    # 3) 교육 형태·비용
    et = df["education_type"].fillna("").str.strip()
    edu_type = [
        {"label": "온라인·이러닝", "n": int(et.isin(["온라인", "이러닝"]).sum())},
        {"label": "집합(오프라인)", "n": int((et.str.contains("집합") & ~et.str.contains("혼합")).sum())},
        {"label": "집합·원격 혼합", "n": int(et.str.contains("혼합").sum())},
        {"label": "전화외국어", "n": int((et == "전화외국어").sum())},
    ]
    edu_type.append({"label": "미기재", "n": n - sum(x["n"] for x in edu_type)})
    pt = df["price_type"].fillna("")
    price = [
        {"label": "유료 (정가 공개)", "n": int((pt == "정액 유료").sum())},
        {"label": "무료", "n": int(pt.str.startswith("무료").sum())},
        {"label": "기업·문의", "n": int(pt.str.contains("문의").sum())},
        {"label": "국비 지원·환급", "n": int(pt.str.contains("국비").sum())},
    ]

    # 4) 분야
    fc = df["field"].value_counts()
    field_dist = [{"key": k, "label": FIELD_NAMES.get(k, k), "n": int(v)} for k, v in fc.items()]

    # 5) 난이도 공급 vs NCS 수요
    d = df["difficulty"].fillna("").str.strip()
    supply_counts = {
        "입문·초급": int(d.str.contains("초급|입문").sum()),
        "중급": int(d.str.startswith("중급").sum()),
        "고급": int(d.str.startswith("고급").sum()),
    }
    labeled = sum(supply_counts.values())
    supply = [{"label": k, "n": v, "pct": pct(v, labeled)} for k, v in supply_counts.items()]
    unlabeled_mask = ~(d.str.contains("초급|입문") | d.str.startswith("중급") | d.str.startswith("고급"))
    unlabeled_prov = df.loc[unlabeled_mask, "provider"].value_counts()
    difficulty = {
        "supply": supply, "labeled": labeled, "unlabeled": n - labeled,
        "unlabeled_pct": pct(n - labeled, n),
        "unlabeled_top": [{"label": k, "n": int(v)} for k, v in unlabeled_prov.head(2).items()],
        "demand": NCS_DEMAND,
    }

    # 6) 핵심 역량 키워드 포함 비율
    text = (df["title"].fillna("") + " " + df["clean_search_text"].fillna("")).str.lower()
    core = []
    for name, kws in CORE_SKILLS.items():
        hit = text.str.contains("|".join(re.escape(k) for k in kws))
        core.append({"label": name, "n": int(hit.sum()), "pct": pct(hit.sum(), n), "keywords": kws})

    # 7) 추천 과업·결과
    tasks_raw = json.load(open(PROCESSED / "hr_task_catalog_90.json", encoding="utf-8"))["tasks"]
    rec = pd.read_csv(RECO / "task_course_recommendations_90.csv")
    summary = json.load(open(RECO / "task_course_recommendations_90_summary.json", encoding="utf-8"))
    top3 = rec[rec["rank"] <= 3]
    domains, tasks = [], []
    for t in tasks_raw:
        if t["domain_name"] not in domains:
            domains.append(t["domain_name"])
        recs = {}
        for lvl, g in top3[top3["task_id"] == t["task_id"]].groupby("level"):
            recs[lvl] = [
                {
                    "title": r.title, "provider": r.provider, "final": round(float(r.final_score), 1),
                    "sem": round(float(r.semantic_score), 1), "bm25": round(float(r.bm25_score), 1),
                    "lvl": round(float(r.level_bonus), 1),
                }
                for r in g.sort_values("rank").itertuples()
            ]
        tasks.append({
            "id": t["task_id"], "domain": t["domain_name"], "stage": t.get("stage"),
            "name": t["task_name"], "desc": t.get("easy_description", ""),
            "ncs": t.get("ncs_unit_code"), "comp": t.get("primary_comp_name"),
            "review": bool(t.get("needs_review")), "recs": recs,
        })
    n_cand = rec["n_candidates"]
    reuse = top3.groupby("course_uid")["task_id"].nunique()
    heavy = reuse[reuse >= 5].index
    title_only = set(df.loc[df["text_quality_status"] == "TITLE_ONLY", "course_uid"])
    recommend = {
        "reused5_courses": int(len(heavy)),
        "reused5_slot_pct": pct(top3["course_uid"].isin(heavy).sum(), len(top3)),
        "title_only_top3_pct": pct(top3["course_uid"].isin(title_only).sum(), len(top3)),
        "title_only_all_pct": pct(len(title_only), n),
        "domains": domains, "tasks": tasks,
        "n_tasks": len(tasks), "needs_review": int(summary["needs_review_count"]),
        "lt3": int(summary.get("task_level_with_lt3_results", 0)),
        "top1_sem_median": round(float(summary["top1_semantic_score_median"]), 1),
        "top1_sem_min": round(float(summary["top1_semantic_score_min"]), 1),
        "top3_slots": int(summary["top3_slots"]), "top3_distinct": int(summary["top3_distinct_courses"]),
        "most_reused": summary["top3_most_reused"][:5],
        "candidates": {"min": int(n_cand.min()), "max": int(n_cand.max())},
        "off_topic": len(off_topic),
    }

    # 8) 고용24 공식 만족도
    sat = pd.read_csv(PROCESSED / "official_satisfaction.csv")
    sat_sum = json.load(open(PROCESSED / "official_satisfaction_summary.json", encoding="utf-8"))
    scores = sat["satisfaction_official"].dropna()
    bins = list(range(0, 101, 10))
    hist, _ = np.histogram(scores, bins=bins)
    # 카탈로그의 고용24 과정 중 공식 만족도가 있는 과정 (목록 API stdgScor, 0은 설문 없음)
    work24_ids = df.loc[df["source_course_id"].astype(str).str.fullmatch(r"A[A-Z]{2}\d{14}"), "source_course_id"].astype(str)
    score_by_id = sat.dropna(subset=["satisfaction_official"]).set_index("trprId")["satisfaction_official"].to_dict()
    detail_path = PROCESSED / "work24_course_details.csv"
    if detail_path.exists():
        det = pd.read_csv(detail_path, dtype={"trprId": str})
        if "satisfaction_official" in det.columns:
            score_by_id.update(det.dropna(subset=["satisfaction_official"]).set_index("trprId")["satisfaction_official"].to_dict())
    satisfaction = {
        "courses": int(len(sat)), "scored": int(scores.size), "unscored": int(len(sat) - scores.size),
        "mean": round(float(scores.mean()), 1), "median": round(float(scores.median()), 1),
        "hist": [{"label": f"{b}~{b + 10}", "n": int(h)} for b, h in zip(bins[:-1], hist)],
        "catalog_matched": int(work24_ids.nunique()),
        "catalog_scored": int(sum(1 for t in work24_ids.unique() if t in score_by_id)),
        "catalog_scored_pct": pct(sum(1 for t in work24_ids.unique() if t in score_by_id), n),
        "period": sat_sum.get("period"),
    }

    # 9) 검색용 과정 목록 (제목·기관·분야)
    prov_list = prov.index.tolist()
    field_keys = list(FIELD_NAMES)
    search = {
        "providers": prov_list,
        "fields": [FIELD_NAMES[k] for k in field_keys],
        "rows": [
            [title, prov_list.index(p), field_keys.index(f) if f in field_keys else -1, int(uid in off_topic)]
            for title, p, f, uid in zip(df["title"], df["provider"], df["field"], df["course_uid"])
        ],
    }

    eda = build_eda(df, off_topic, tasks_raw, top3, rec, summary, n)

    data = {
        "eda": eda,
        "generated": date.today().isoformat(),
        "kpi": {
            "courses": n, "providers": int(prov.size), "rich_pct": pct(tq.get("RICH", 0), n),
            "title_only_pct": pct(tq.get("TITLE_ONLY", 0), n), "off_topic": len(off_topic),
            "work24_courses": int(work24_ids.size),
            "tasks": len(tasks), "domains": len(domains), "sat_scored": int(scores.size),
            "sat_courses": int(len(sat)), "hr_field_pct": pct(fc.get("HR", 0) + fc.get("GA", 0), n),
        },
        "providers": top_prov, "text_quality": text_quality, "edu_type": edu_type, "price": price,
        "fields": field_dist, "difficulty": difficulty, "core_skills": core,
        "recommend": recommend, "satisfaction": satisfaction, "search": search,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"저장: {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f}KB)")
    print(json.dumps({k: data[k] for k in ["kpi", "providers", "text_quality", "edu_type", "price", "fields", "difficulty", "core_skills"]}, ensure_ascii=False, indent=1))
    print("satisfaction", {k: v for k, v in satisfaction.items() if k != "hist"}, satisfaction["hist"])
    print("recommend", {k: v for k, v in recommend.items() if k not in ("tasks", "domains")})


if __name__ == "__main__":
    main()
