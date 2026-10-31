"""
저장된 고용24 API 응답으로 2026년 사업주훈련 인사 교육 시장을 탐색한다. (API 호출·모델 불필요)

입력
- data/hr/raw/work24_2026/employer_2026_list_raw.json : 사업주훈련 목록 API, 2026년 회차, 인사 관련 키워드 15개로 검색
- data/hr/processed/official_satisfaction.csv          : 국민내일배움카드 목록 API의 공식 만족도
출력
- data/hr/reports/work24_employer_2026_eda.json
- data/hr/reports/work24_employer_2026_eda.md
실행: python scripts/eda_work24_employer_2026.py

주의: 키워드 검색 결과라 사업주훈련 전체가 아니라 '인사 관련 키워드에 걸린 과정'의 분포다.
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "hr" / "raw" / "work24_2026" / "employer_2026_list_raw.json"
SAT = ROOT / "data" / "hr" / "processed" / "official_satisfaction.csv"
OUT_JSON = ROOT / "data" / "hr" / "reports" / "work24_employer_2026_eda.json"
OUT_MD = ROOT / "data" / "hr" / "reports" / "work24_employer_2026_eda.md"

# 확인된 NCS 세분류 이름 (고용24 ncsCd·과정명 기준, data/hr/reference/hr_domain_ncs_crosswalk.csv 참고)
NCS_NAMES = {"02020201": "인사", "02020202": "노무관리", "02020101": "총무",
             "02020302": "사무행정", "02010101": "경영기획",
             "020202": "인사·조직 (세분류 없이 소분류 코드만)"}
HR_SCOPE = {"02020201", "02020202", "020202"}


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def main():
    r = pd.DataFrame(json.load(open(RAW, encoding="utf-8")))
    raw_rows = len(r)
    collected = date.fromtimestamp(RAW.stat().st_mtime).strftime("%m-%d")  # 파일을 저장한 날
    keywords = sorted(r["_kw"].dropna().unique().tolist())
    r = r.drop_duplicates(["trprId", "trprDegr"]).copy()  # 키워드가 겹쳐 같은 회차가 여러 번 잡힘
    r["fee"] = pd.to_numeric(r["realMan"], errors="coerce")
    r["cap"] = pd.to_numeric(r["yardMan"], errors="coerce")
    r["ncs_name"] = r["ncsCd"].map(NCS_NAMES).fillna("기타")
    r["month"] = r["traStartDate"].str[:7]
    courses = r.drop_duplicates("trprId")

    # 1) NCS 세분류별 과정·회차
    by_ncs = (r.groupby("ncs_name").agg(sessions=("trprId", "size"), courses=("trprId", "nunique"),
                                        institutions=("trainstCstId", "nunique"), fee_median=("fee", "median"))
              .sort_values("courses", ascending=False))
    by_ncs["course_pct"] = (by_ncs["courses"] / courses.shape[0] * 100).round(1)
    by_ncs["sessions_per_course"] = (by_ncs["sessions"] / by_ncs["courses"]).round(1)

    # 기타 안에서 과정이 많은 NCS 소분류(앞 6자리). 이름은 확인하지 못해 코드로만 적는다.
    other = courses[courses["ncs_name"] == "기타"]["ncsCd"].fillna("없음").str[:6].value_counts().head(5)

    # 2) 인사 범위(인사·노무관리·인사·조직 소분류) 기관 집중도
    hr = r[r["ncsCd"].isin(HR_SCOPE)]
    hr_courses = hr.drop_duplicates("trprId")
    inst = hr_courses["subTitle"].value_counts()
    top5 = inst.head(5)

    # 3) 회차 수 분포 (한 과정을 1년에 몇 번 여는가)
    spc = r.groupby("trprId").size()

    # 4) 월별 개강 회차 (인사 범위)
    monthly = hr.groupby("month").size()

    # 5) 공식 만족도 (국민내일배움카드)
    sat = pd.read_csv(SAT, dtype={"ncsCd": str})
    sat["score"] = pd.to_numeric(sat["satisfaction_official"], errors="coerce")
    sat["ncs_name"] = sat["ncsCd"].map(NCS_NAMES).fillna("기타")
    sat_by = sat.groupby("ncs_name")["score"].agg(["count", "median", "mean"]).round(1)
    sat_by = sat_by[sat_by["count"] > 0].sort_values("count", ascending=False)

    result = {
        "source": {"file": str(RAW.relative_to(ROOT)), "raw_rows": raw_rows, "sessions": len(r),
                   "courses": int(courses.shape[0]), "institutions": int(r["trainstCstId"].nunique()),
                   "keywords": keywords, "period": [r["traStartDate"].min(), r["traStartDate"].max()]},
        "by_ncs": by_ncs.reset_index().to_dict("records"),
        "other_ncs_top": {k: int(v) for k, v in other.items()},
        "hr_scope": {"courses": int(hr_courses.shape[0]), "sessions": int(len(hr)),
                     "institutions": int(hr["trainstCstId"].nunique()),
                     "labor_courses": int(courses["ncsCd"].eq("02020202").sum()),
                     "top5_institutions": [{"name": k, "courses": int(v)} for k, v in top5.items()],
                     "top5_course_pct": pct(int(top5.sum()), int(hr_courses.shape[0])),
                     "fee_median": float(hr["fee"].median()), "fee_p90": float(hr["fee"].quantile(0.9)),
                     "capacity_500plus_pct": pct(int((hr["cap"] >= 500).sum()), len(hr))},
        "sessions_per_course": {"median": float(spc.median()), "mean": round(float(spc.mean()), 1),
                                "ge12_pct": pct(int((spc >= 12).sum()), len(spc)), "max": int(spc.max())},
        "hr_monthly_sessions": {k: int(v) for k, v in monthly.items()},
        "satisfaction_by_ncs": sat_by.reset_index().to_dict("records"),
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    hs = result["hr_scope"]
    lines = [
        "# 고용24 사업주훈련 2026 인사 교육 시장 EDA",
        "",
        f"저장된 고용24 사업주훈련 목록 API 응답({collected} 수집, 인사 관련 키워드 {len(keywords)}개 검색, 원본 {raw_rows:,}행)으로 계산했다. "
        f"중복을 뺀 회차 {len(r):,}건, 과정 {courses.shape[0]:,}개, 기관 {result['source']['institutions']}곳이다. "
        "키워드 검색 결과라 사업주훈련 전체가 아니라 '인사 관련 키워드에 걸린 과정'의 분포다.",
        "",
        "## NCS 세분류별 과정",
        "",
        "| 세분류 | 과정 | 비중 | 회차 | 과정당 회차 | 기관 | 1인 훈련비 중앙값 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, x in by_ncs.iterrows():
        lines.append(f"| {name} | {int(x.courses):,} | {x.course_pct}% | {int(x.sessions):,} | {x.sessions_per_course} | {int(x.institutions)} | {x.fee_median:,.0f}원 |")
    lines += [
        "",
        "'기타'에서 과정이 많은 NCS 소분류 코드: " + ", ".join(f"{k} {v}개" for k, v in result["other_ncs_top"].items())
        + " (이름은 ncs.go.kr에서 확인 필요). 1인 훈련비는 목록 API의 realMan 값이다.",
        "",
        "## 인사 범위(인사·노무관리·인사·조직 소분류)",
        "",
        f"- 과정 {hs['courses']}개, 회차 {hs['sessions']:,}건, 기관 {hs['institutions']}곳. 그중 노무관리 과정은 {hs['labor_courses']}개뿐이다.",
        f"- 상위 5개 기관이 과정의 {hs['top5_course_pct']}%를 낸다: " + ", ".join(f"{x['name']} {x['courses']}개" for x in hs["top5_institutions"]) + ".",
        f"- 1인 훈련비 중앙값 {hs['fee_median']:,.0f}원, 상위 10% {hs['fee_p90']:,.0f}원 이상. 정원 500명 이상 회차가 {hs['capacity_500plus_pct']}%로 대부분 대규모 원격 과정이다.",
        "",
        "## 같은 과정을 여러 번 여는 구조",
        "",
        f"과정 하나가 1년에 여는 회차는 중앙값 {result['sessions_per_course']['median']:.0f}회, 평균 {result['sessions_per_course']['mean']}회다. "
        f"매월 이상(12회 이상) 여는 과정이 {result['sessions_per_course']['ge12_pct']}%다. 카탈로그에서 같은 제목이 여러 행으로 잡히는 이유와 같다.",
        "",
        "## 공식 만족도 (국민내일배움카드, NCS 세분류별)",
        "",
        "| 세분류 | 점수 있는 과정 | 중앙값 | 평균 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for x in result["satisfaction_by_ncs"]:
        lines.append(f"| {x['ncs_name']} | {int(x['count'])} | {x['median']} | {x['mean']} |")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
