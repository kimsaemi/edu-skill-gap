"""
추천 3개를 못 채운 업무(빈자리)가 '공급 부족'인지 '후보 예비분 부족'인지 키워드로 확인한다. (모델 불필요)

- 추천 결과 파일은 업무×수준마다 상위 5개만 저장해, 제외 목록이 늘면 예비 후보가 없어 빈자리가 생긴다.
- 업무마다 핵심 키워드를 정하고, 추천 대상 카탈로그(제외 목록 뺀 과정)에서 제목에 그 키워드가 있는 과정을 센다.
  · 서로 다른 과정 제목 수가 3개 이상이면 → 모델로 다시 계산하면 채워질 가능성이 높음(예비분 부족)
  · 0~2개면 → 카탈로그에 그 업무를 직접 다루는 과정이 거의 없음(공급 부족)
  · 설명(소개·목표·커리큘럼)에만 키워드가 있는 과정 수도 함께 센다(일부 단원으로 다루는 과정)
- 출력: data/hr/reports/thin_task_supply.csv
실행: python scripts/analyze_thin_task_supply.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender as U  # noqa: E402

RECO = ROOT / "data" / "hr" / "output" / "recommendation"
PROCESSED = ROOT / "data" / "hr" / "processed"
OUT = ROOT / "data" / "hr" / "reports" / "thin_task_supply.csv"
LEVELS = ["입문", "실무", "관리자·심화"]

# 업무별 핵심 키워드 (제목 기준, 정규식)
TASK_KEYWORDS = {
    "TASK_HR_D01_T04": r"인건비",
    "TASK_HR_D01_T05": r"정원|인력운영|인력계획|인력 계획|요원",
    "TASK_HR_D01_T08": r"인적자본|노동생산성|HCVA|피플 ?애널리틱스|HR ?애널리틱스|인사 ?데이터",
    "TASK_HR_D02_T01": r"직무체계|직무분류|직무분석|Job Family",
    "TASK_HR_D02_T06": r"직무기술서|\bJD\b",
    "TASK_HR_D02_T07": r"직무평가|직무가치|직무급",
    "TASK_HR_D03_T01": r"채용 ?전략|채용 ?브랜딩|채용 ?채널|채용 ?트렌드",
    "TASK_HR_D04_T01": r"온보딩",
    "TASK_HR_D04_T03": r"온보딩",
    "TASK_HR_D04_T05": r"온보딩|오리엔테이션",
    "TASK_HR_D05_T03": r"평가 ?등급|상대평가|절대평가|평가제도|평가체계|평가시스템|Calibration",
    "TASK_HR_D05_T08": r"평가자|평가 ?오류|관대화|평가 ?면담",
    "TASK_HR_D06_T02": r"성과급|인센티브|성과배분",
    "TASK_HR_D06_T07": r"연말정산",
    "TASK_HR_D07_T01": r"교육체계|교육 ?계획|교육 ?기획|교육과정 ?기획|HRD ?전략",
    "TASK_HR_D07_T02": r"리더십 ?파이프라인|리더십 ?교육 ?체계|계층 ?교육|리더 ?육성",
    "TASK_HR_D07_T05": r"교육 ?운영|이러닝 ?운영|교육담당자|HRD ?담당자",
    "TASK_HR_D07_T10": r"LMS|학습 ?데이터|학습 ?분석",
    "TASK_HR_D08_T06": r"사내보|사보|사내 ?커뮤니케이션|사내 ?소통|내부 ?커뮤니케이션",
}


def main():
    rec = pd.read_csv(RECO / "task_course_recommendations_90.csv")
    tasks = {t["task_id"]: t for t in json.load(open(PROCESSED / "hr_task_catalog_90.json", encoding="utf-8"))["tasks"]}
    top3 = rec[rec["rank"] <= 3]
    idx = pd.MultiIndex.from_product([list(tasks), LEVELS])
    filled = top3.groupby(["task_id", "level"]).size().reindex(idx, fill_value=0)
    thin = filled[filled < 3]

    df = pd.read_parquet(PROCESSED / "education_courses_search_cleaned.parquet")
    off = set(pd.read_csv(PROCESSED / "off_topic_exclusions.csv", encoding="utf-8-sig")["course_uid"])
    cat = df[~df["course_uid"].isin(off)].copy()
    cat["norm"] = cat["title"].map(U.normalize_course_title)
    d = cat["difficulty"].fillna("").astype(str)
    cat["lvl"] = d.str.contains("초급|입문").map({True: "입문·초급", False: ""})
    cat.loc[d.str.contains("중급|고급"), "lvl"] = "중급 이상"

    rows = []
    for tid in dict.fromkeys(t for t, _ in thin.index):
        pat = TASK_KEYWORDS.get(tid)
        hit = cat[cat["title"].str.contains(pat, regex=True)] if pat else cat.iloc[0:0]
        titles = hit["norm"].nunique()
        in_text = cat[cat["clean_search_text"].fillna("").str.contains(pat, regex=True)] if pat else cat.iloc[0:0]
        shown = set(top3.loc[top3["task_id"] == tid, "title"].map(U.normalize_course_title))
        rows.append({
            "task_id": tid, "domain": tasks[tid]["domain_name"], "task": tasks[tid]["task_name"],
            "thin_levels": ", ".join(f"{lv}({filled[(tid, lv)]})" for lv in LEVELS if filled[(tid, lv)] < 3),
            "keywords": pat or "", "catalog_titles": titles,
            "text_titles": in_text["norm"].nunique(),
            "mid_plus_titles": hit.loc[hit["lvl"] == "중급 이상", "norm"].nunique(),
            "not_yet_recommended": len(set(hit["norm"]) - shown),
            "examples": " / ".join(hit.drop_duplicates("norm")["title"].head(4)) or "-",
            "판단": "공급 부족" if titles < 3 else "예비분 부족 (모델 재계산으로 채울 수 있음)",
        })
    out = pd.DataFrame(rows).sort_values(["catalog_titles", "task_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"빈자리 조합 {len(thin)}개 / 업무 {len(out)}개 → {OUT.relative_to(ROOT)}")
    print(out["판단"].value_counts().to_string())
    print(out[["task_id", "domain", "thin_levels", "catalog_titles", "text_titles", "mid_plus_titles", "not_yet_recommended", "판단"]].to_string(index=False))
    return out


if __name__ == "__main__":
    main()
