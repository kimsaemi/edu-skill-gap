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

    data = {
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
