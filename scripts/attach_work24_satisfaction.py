"""
확정 295건 추천 후보 마스터에 고용24 공식 만족도(stdgScor)를 연결한다.

입력
  data/hr/output/recommendation/hr_recommendation_candidates.csv  (확정 295건, course_id = PUB_<trprId>_<회차>)
  data/hr/processed/work24_course_satisfaction.csv              (scripts/collect_hr_courses.py가 만든 과정별 만족도 표)

출력
  hr_recommendation_candidates.csv에 아래 컬럼을 추가(이미 있으면 새 값으로 교체)
    satisfaction_official : 고용24 공식 만족도(0~100). stdgScor > 0인 과정만 값이 있음
    satisfaction_status   : 점수 있음 / 설문 없음(0) / 제공 안 됨(사업주훈련) / 고용24 과정 아님 / 만족도 표에 없음
    satisfaction_source   : 출처와 주의사항 (응답자 수 미공개)
    satisfaction_last_end_date : 점수를 가져온 원본 회차들의 마지막 종료일 (자료 시점 확인용)

주의
  - 만족도는 화면에 참고 정보로만 보여주고 추천 점수에는 넣지 않는다.
    고용24 국민내일배움카드 과정에만 값이 있어, 점수에 넣으면 그 과정들만 유리해진다.
  - scripts/build_step4_5_recommendation_audit.py를 다시 실행하면 이 컬럼이 사라지므로 이 스크립트를 다시 실행한다.
  - 여러 번 실행해도 결과가 같다.

실행: python scripts/attach_work24_satisfaction.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "hr" / "output" / "recommendation" / "hr_recommendation_candidates.csv"
SATISFACTION = ROOT / "data" / "hr" / "processed" / "work24_course_satisfaction.csv"

NEW_COLS = ["satisfaction_official", "satisfaction_status", "satisfaction_source", "satisfaction_last_end_date"]


def attach(candidates: pd.DataFrame, satisfaction: pd.DataFrame) -> pd.DataFrame:
    out = candidates.drop(columns=[c for c in NEW_COLS if c in candidates.columns])
    is_work24 = out["course_id"].str.startswith("PUB_") & out["source_platform"].str.contains("고용24", na=False)
    trpr_id = out["course_id"].str.extract(r"^PUB_(.+)_[^_]+$")[0].where(is_work24)

    sat = satisfaction.set_index("trprId")
    matched = trpr_id.isin(sat.index)
    out["satisfaction_official"] = trpr_id.map(sat["satisfaction_official"])
    out["satisfaction_status"] = trpr_id.map(sat["satisfaction_status"])
    out.loc[is_work24 & ~matched, "satisfaction_status"] = "만족도 표에 없음"
    out.loc[~is_work24, "satisfaction_status"] = "고용24 과정 아님"
    out["satisfaction_source"] = trpr_id.map(sat["satisfaction_source"])
    out["satisfaction_last_end_date"] = trpr_id.map(sat["last_end_date"])
    return out


def main():
    candidates = pd.read_csv(CANDIDATES, dtype=str)
    satisfaction = pd.read_csv(SATISFACTION, dtype={"trprId": str})
    out = attach(candidates, satisfaction)

    assert len(out) == len(candidates), "행 수가 바뀌면 안 됨"
    out.to_csv(CANDIDATES, index=False, encoding="utf-8-sig")

    print(f"[저장] {CANDIDATES.relative_to(ROOT)} ({len(out)}건)")
    print(out["satisfaction_status"].value_counts().to_string())
    scored = out["satisfaction_official"].notna()
    if scored.any():
        vals = pd.to_numeric(out.loc[scored, "satisfaction_official"])
        print(f"\n점수 있음 {scored.sum()}건: 최소 {vals.min():.1f} / 중앙값 {vals.median():.1f} / 최대 {vals.max():.1f}")
        print(f"점수 원본 회차의 마지막 종료일: {out.loc[scored, 'satisfaction_last_end_date'].max()}")


if __name__ == "__main__":
    main()
