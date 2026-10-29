"""
팀원 295건 데이터셋의 '실제 값이 아닌 값'을 결측(NaN)으로 되돌리는 정정 스크립트.

배경 (2026-10-25 데이터 검토):
- satisfaction_score_100: 295건 모두 실제 만족도가 아님.
  상세 HTML에서 만족도를 못 찾으면 80점, HTML 파일이 없으면 88점,
  인프런은 코드에 96점으로 고정 입력되어 있었음 (scripts/preprocess_and_enrich_295.py).
- rating_score_5:
  * 고용24 국민내일배움카드: 상세페이지에서 읽은 실제 평점. 단 0.0은 '리뷰 없음'이므로 결측 처리.
  * 고용24 사업주훈련: 기본 만족도(80/88점)를 20으로 나눈 값(4.0/4.4) → 결측 처리.
  * 인프런: 4.8로 고정 입력 → 결측 처리.
- training_hours: 고용24 목록 API 응답에는 교육시간 필드(totTraHours)가 없어
  수집 코드의 기본값 40시간이 들어갔고, 인프런은 15시간으로 고정 입력 → 결측 처리.
- cost: 인프런 45,000원은 고정 입력값 → 결측 처리.

원래 값은 *_original 컬럼에 남기지 않는다(오해 방지). 필요하면 git 이력에서 확인 가능.
여러 번 실행해도 결과가 같다.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

KMBC = "고용24 국민내일배움카드"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    is_kmbc = df["platform"].eq(KMBC)
    is_inflearn = df["platform"].str.contains("인프런", na=False)
    is_work24 = df["platform"].str.contains("고용24", na=False)

    # 1) 만족도(100점): 전부 기본값/고정값
    df["satisfaction_score_100"] = np.nan

    # 2) 평점(5점): 국민내일배움카드의 실제 평점(>0)만 유지
    rating = pd.to_numeric(df["rating_score_5"], errors="coerce")
    keep = is_kmbc & rating.gt(0)
    df["rating_score_5"] = rating.where(keep)
    df["rating_source"] = np.where(keep, "고용24 상세페이지 평점", "미확보")

    # 3) 교육시간: 고용24 기본값 40시간, 인프런 고정 15시간
    hours = pd.to_numeric(df["training_hours"], errors="coerce")
    fake_hours = (is_work24 & hours.eq(40)) | (is_inflearn & hours.eq(15))
    df["training_hours"] = hours.mask(fake_hours)

    # 4) 수강료: 인프런 고정 45,000원
    cost = pd.to_numeric(df["cost"], errors="coerce")
    df["cost"] = cost.mask(is_inflearn & cost.eq(45000))

    df["data_quality_note"] = (
        "만족도·교육시간은 미확보(기본값 제거)"
        + np.where(is_inflearn, ", 인프런 수강료 미확보", "")
    )
    return df


def main():
    for name in ["hr_courses_detailed_295", "hr_courses_nlp_ready_295"]:
        csv_path = PROCESSED / f"{name}.csv"
        df = clean(pd.read_csv(csv_path))
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[정정] {csv_path.relative_to(ROOT)}: {len(df)}건, "
              f"실제 평점 {df['rating_score_5'].notna().sum()}건, "
              f"교육시간 보유 {df['training_hours'].notna().sum()}건")

    json_path = PROCESSED / "hr_courses_detailed_295.json"
    records = json.loads(json_path.read_text(encoding="utf-8"))
    extra = {k: [r.pop(k, None) for r in records] for k in ["syllabus"]}
    df = clean(pd.DataFrame(records))
    df["syllabus"] = extra["syllabus"]
    out = json.loads(df.to_json(orient="records", force_ascii=False))
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[정정] {json_path.relative_to(ROOT)}: {len(out)}건")


if __name__ == "__main__":
    main()
