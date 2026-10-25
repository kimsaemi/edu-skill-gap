"""
인사·총무·경영지원 직무교육과 무관한 강좌를 추천 대상에서 빼기 위한 제외 목록을 만듭니다.

- 입력: data/hr/processed/education_courses_search_cleaned.parquet (8,645건)
- 출력: data/hr/processed/off_topic_exclusions.csv (course_uid, title, provider, reason)
- 추천 엔진(UnifiedHybridRecommender)이 이 목록을 읽어 후보에서 제외합니다.
- 원본 데이터는 수정하지 않습니다. 목록을 검토해 잘못 제외된 강좌는 ALLOW_UIDS에 추가하세요.

실행: python scripts/build_off_topic_exclusions.py
"""

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
OUT = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"

# (사유, 제목 정규식)
TITLE_RULES = [
    ("부동산·공인중개사 수험", r"공인중개사|부동산학개론|부동산공법|부동산공시법|부동산세법"),
    ("보건·요양·간호", r"요양보호사|간호"),
    ("사회복지 수험·학과 과정", r"사회복지사|사회복지조사|사회적경제|사회적기업"),
    ("서비스·기능직 자격", r"애견|바리스타|미용사|네일|조리기능|제과|제빵|지게차|용접|드론"),
    ("물류·경비·경호 수험", r"물류관리사|경비지도사|경호학"),
    ("투자·가상자산", r"가상자산|코인|자동매매"),
    ("생산·제조 운영", r"생산운영|생산관리"),
]
# 직무훈련이 아닌 학교 학과 교육과정 (고용24 NCS 교육과정 경유)
ACADEMIC_PROVIDER = r"전문대|마이스터고|학과"
HEADER_TITLES = {"과정명", "강좌명", "교육과정명", "title"}
# 검토 후 제외하지 않기로 한 강좌
ALLOW_UIDS: set = set()


def main() -> int:
    df = pd.read_parquet(SRC)
    title = df["title"].fillna("")
    provider = df["provider"].fillna("")
    rows = []
    for uid, t, p in zip(df["course_uid"], title, provider):
        if uid in ALLOW_UIDS:
            continue
        reason = None
        if t.strip() in HEADER_TITLES:
            reason = "엑셀 머리글 행 혼입"
        elif re.search(ACADEMIC_PROVIDER, p):
            reason = "학교 학과 교육과정 (직무훈련 아님)"
        else:
            for r, pat in TITLE_RULES:
                if re.search(pat, t):
                    reason = r
                    break
        if reason:
            rows.append({"course_uid": uid, "title": t, "provider": p, "reason": reason})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"제외 {len(out)}건 / 전체 {len(df)}건 → {OUT}")
    print(out["reason"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
