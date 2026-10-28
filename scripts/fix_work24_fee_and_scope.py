"""
확정 과정 추천 후보(hr_recommendation_candidates.csv)의 고용24 수강료 표시와 범위 오류를 고친다.

1. 사업주훈련 수강료
   - 기존 course_fee는 API의 courseMan(수강비)만 사용했다. 사업주훈련 50건 중 44건이 0원이어서
     '국비 전액 환급 또는 무료(0원)'로 분류되었지만, 같은 응답의 realMan(실제 훈련비)은 26,730원~60만 원이다.
     사업주훈련은 사업주가 훈련비를 부담하고 환급받는 과정이므로 '무료'로 표시하면 안 된다.
   - 국민내일배움카드는 courseMan과 realMan이 모든 행에서 같아 바뀌는 것이 없다.
   - 추가 컬럼: work24_course_fee(courseMan, 수강비), work24_training_cost(realMan, 실제 훈련비)
   - 사업주훈련 행은 fee_type을 EMPLOYER_TRAINING으로, fee_desc를 두 금액을 함께 적은 문구로 바꾼다.
     course_fee 값 자체는 그대로 둔다(기존 분석과의 비교를 위해).
   - 정확한 항목 정의는 고용24 Open API 가이드에서 확인이 필요하다.

2. 주제가 맞지 않는 과정 제외
   - '농협은행 자산관리 전문역 양성'(한국금융연수원, 실제 훈련비 14,876,000원)은 은행 금융자산관리 과정인데
     '자산관리' 키워드로 총무 '비품 및 자산관리' 역량에 들어왔다 -> recommendation_readiness = EXCLUDED_OFF_TOPIC

실행 순서: fix_work24_course_urls.py -> attach_work24_satisfaction.py -> 이 스크립트
(build_step4_5_recommendation_audit.py를 다시 실행하면 세 스크립트를 다시 실행해야 한다.)
여러 번 실행해도 결과가 같다.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "hr" / "output" / "recommendation" / "hr_recommendation_candidates.csv"
RAW_FILES = [
    "data/hr/raw/kmbc_courses_raw.json",
    "data/hr/raw/employer_courses_raw.json",
    "data/hr/raw/round2/kmbc_round2_raw.json",
    "data/hr/raw/round2/employer_round2_raw.json",
]
OFF_TOPIC = {
    "농협은행 자산관리 전문역 양성": "은행 금융자산관리 과정으로 총무 비품·자산관리와 무관 (키워드 '자산관리' 오분류)",
}


def load_raw_fees():
    fees = {}
    for f in RAW_FILES:
        for it in json.loads((ROOT / f).read_text(encoding="utf-8")):
            fees[f"PUB_{it['trprId']}_{it['trprDegr']}"] = (it.get("courseMan"), it.get("realMan"))
    return fees


def won(x):
    return f"{x:,.0f}원"


def main():
    df = pd.read_csv(CANDIDATES, dtype=str)
    fees = load_raw_fees()
    course_fee = df["course_id"].map(lambda k: fees.get(k, (None, None))[0])
    real_cost = df["course_id"].map(lambda k: fees.get(k, (None, None))[1])
    df["work24_course_fee"] = pd.to_numeric(course_fee, errors="coerce")
    df["work24_training_cost"] = pd.to_numeric(real_cost, errors="coerce")

    emp = df["source_platform"].eq("고용24_사업주훈련") & df["work24_training_cost"].notna()
    df.loc[emp, "fee_type"] = "EMPLOYER_TRAINING"
    df.loc[emp, "fee_desc"] = [
        f"사업주훈련 · 수강비 {won(c)} / 실제 훈련비 {won(r)} (사업주 부담 후 환급, 개인 부담은 기관에 확인)"
        for c, r in zip(df.loc[emp, "work24_course_fee"], df.loc[emp, "work24_training_cost"])
    ]

    for name, reason in OFF_TOPIC.items():
        hit = df["course_name"].eq(name)
        df.loc[hit, "recommendation_readiness"] = "EXCLUDED_OFF_TOPIC"
        df.loc[hit, "recommendation_note"] = reason

    df.to_csv(CANDIDATES, index=False, encoding="utf-8-sig")
    print(f"[정정] {CANDIDATES.relative_to(ROOT)}")
    print(f"  사업주훈련 수강료 표시 수정: {emp.sum()}건 (그중 수강비 0원 {(emp & df['work24_course_fee'].eq(0)).sum()}건)")
    print(f"  국민내일배움카드 수강비=실제 훈련비: "
          f"{(df.loc[df['source_platform'].eq('고용24_국민내일배움카드'), 'work24_course_fee'] == df.loc[df['source_platform'].eq('고용24_국민내일배움카드'), 'work24_training_cost']).all()}")
    print(f"  주제 불일치로 제외: {df['recommendation_readiness'].eq('EXCLUDED_OFF_TOPIC').sum()}건")
    print(df["recommendation_readiness"].value_counts().to_string())


if __name__ == "__main__":
    main()
