"""
추천 대상 카탈로그(제외 목록을 뺀 과정)의 데이터 품질과 회차 중복의 영향을 점검한다. (모델·API 불필요)

출력: data/hr/reports/data_validation_summary.json
실행: python scripts/validate_catalog.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender as U  # noqa: E402

PROCESSED = ROOT / "data" / "hr" / "processed"
RECO = ROOT / "data" / "hr" / "output" / "recommendation"
OUT = ROOT / "data" / "hr" / "reports" / "data_validation_summary.json"


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def main():
    df = pd.read_parquet(PROCESSED / "education_courses_search_cleaned.parquet")
    off = set(pd.read_csv(PROCESSED / "off_topic_exclusions.csv", encoding="utf-8-sig")["course_uid"])
    a = df[~df["course_uid"].isin(off)].copy()
    rec = pd.read_csv(RECO / "task_course_recommendations_90.csv")
    top3 = rec[rec["rank"] <= 3].copy()

    price = pd.to_numeric(a["price"], errors="coerce")
    hours = pd.to_numeric(a["duration_hours"], errors="coerce")
    st = a["start_date"].fillna("").astype(str).str[:10]
    en = a["end_date"].fillna("").astype(str).str[:10]
    has = st.str.match(r"\d{4}-\d{2}-\d{2}")
    today = date.today().isoformat()

    checks = {
        "추천 대상 과정": len(a),
        "과정 ID 중복": int(df["course_uid"].duplicated().sum()),
        "링크 빈칸": int(a["url"].fillna("").astype(str).str.strip().eq("").sum()),
        "Base64 노이즈 남음": int((a["title"].fillna("") + " " + a["clean_search_text"].fillna(""))
                                .str.contains(r"[A-Za-z0-9+/]{80,}={0,2}", regex=True).sum()),
        "추천 결과에 제외 과정": int(rec["course_uid"].isin(off).sum()),
        "추천 결과에 카탈로그 없는 과정": int((~rec["course_uid"].isin(df["course_uid"])).sum()),
        "가격 0원인데 '정액 유료'": int(((price == 0) & a["price_type"].fillna("").eq("정액 유료")).sum()),
        "시작일 > 종료일": int((has & en.str.match(r"\d{4}-\d{2}-\d{2}") & (st > en)).sum()),
        "교육 시간 0 이하": int((hours <= 0).sum()),
        "가격 500만 원 초과 (해외 연수·임원 과정, 오류 아님)": int((price > 5_000_000).sum()),
        "설명 없이 제목만": int(a["text_quality_status"].eq("TITLE_ONLY").sum()),
        "일정이 지난 과정": int((has & (en.where(en != "", st) < today)).sum()),
        "일정이 있는 과정": int(has.sum()),
    }

    # 회차 중복: 같은 기관에 같은 제목(정규화)으로 여러 번 등록
    a["norm"] = a["title"].map(U.normalize_course_title)
    g = a.groupby("provider").agg(rows=("norm", "size"), titles=("norm", "nunique"))
    g = g[g["rows"] >= 100]
    top3["norm"] = top3["title"].map(U.normalize_course_title)
    share = top3["provider"].value_counts(normalize=True) * 100
    rows_per_title = a.groupby("norm").size()
    top3["catalog_rows"] = top3["norm"].map(rows_per_title)
    providers = [{
        "provider": p, "rows": int(x.rows), "titles": int(x.titles), "rows_per_title": round(x.rows / x.titles, 2),
        "row_share": pct(x.rows, len(a)), "title_share": pct(x.titles, a["norm"].nunique()),
        "top3_share": round(float(share.get(p, 0)), 1),
    } for p, x in g.sort_values("rows", ascending=False).iterrows()]
    dup = {
        "duplicate_rows": int(len(a) - a.drop_duplicates(["provider", "norm"]).shape[0]),
        "distinct_titles": int(a["norm"].nunique()),
        "providers": providers,
        "top3_multi_row_pct": pct(int((top3["catalog_rows"] >= 2).sum()), len(top3)),
        "catalog_multi_row_title_pct": pct(int((rows_per_title >= 2).sum()), len(rows_per_title)),
        "same_title_in_one_slot": int(top3.groupby(["task_id", "level"])["norm"].apply(lambda s: s.duplicated().sum()).sum()),
        "top3_distinct_titles": int(top3["norm"].nunique()),
        "top3_slots": len(top3),
    }
    out = {"checked": today, "checks": checks, "duplicates": dup}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in checks.items():
        print(f"{k:45s} {v:,}")
    print(pd.DataFrame(providers).to_string(index=False))
    print({k: v for k, v in dup.items() if k != "providers"})


if __name__ == "__main__":
    main()
