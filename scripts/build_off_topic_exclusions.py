"""
인사 직무교육과 무관한 강좌를 추천 대상에서 빼기 위한 제외 목록을 만듭니다.

2026-10-28 팀 결정으로 프로젝트 범위를 '인사'로 정해 아래 규칙을 더했습니다.
  - 고용24 공식 NCS 분류가 총무(020201…)인 과정: 인사 범위 밖 (data/hr/processed/work24_course_details.csv의 ncs_code)
  - 팀원 분야 검수에서 '인사 업무와 무관'으로 판정한 과정 (data/hr/output/recommendation/domain_mapping_review_results.csv)
  - 근로자·관리감독자 대상 법정 안전보건교육('채용 시'·'노무제공 시'가 채용·노무에 걸림), 마케팅·커머스 과정
  분야 기준과 NCS 대응표: data/hr/reference/hr_domain_ncs_crosswalk.csv, 검수 결과: data/hr/reports/domain_review_report.md

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
    # 근로자·관리감독자가 의무로 받는 법정 교육. '채용 시', '노무제공 시'가 채용·노무 업무 키워드에 걸린다.
    # 인사 담당자용인 '중대재해처벌법·산업안전보건법 해설' 과정은 남긴다.
    ("법정 안전보건교육(근로자·관리감독자 대상)", r"^2026 안전보건교육|안전보건 관리감독자 교육|관리감독자 우편통신 교육"),
    ("마케팅·커머스 (인사 업무 아님)", r"마케팅|커머스|소통판매"),
]
WORK24_DETAILS = ROOT / "data" / "hr" / "processed" / "work24_course_details.csv"
REVIEW_RESULTS = ROOT / "data" / "hr" / "output" / "recommendation" / "domain_mapping_review_results.csv"
NCS_GA_PREFIX = "020201"  # 총무·인사 > 총무


def norm_title(t: str) -> str:
    """검수 시트와 같은 기준: 앞의 고용24 관리코드(EB2xxx)와 여러 칸 공백을 정리"""
    return re.sub(r"\s+", " ", re.sub(r"^(EB[0-9A-Z]{4}\s+)", "", str(t))).strip()


def load_scope_rules():
    """인사 범위 밖(NCS 총무) 과정 ID와 팀원 검수 '무관' 과정명"""
    ga_uids = set()
    if WORK24_DETAILS.exists():
        d = pd.read_csv(WORK24_DETAILS, dtype=str)
        ga_uids = set(d.loc[d["ncs_code"].str.startswith(NCS_GA_PREFIX, na=False), "course_uid"])
    unrelated = set()
    if REVIEW_RESULTS.exists():
        rv = pd.read_csv(REVIEW_RESULTS, dtype=str).fillna("")
        unrelated = set(rv.loc[rv["가장 맞는 분야 (고르기)"] == "인사 업무와 무관", "과정명"].map(norm_title))
    return ga_uids, unrelated
# 직무훈련이 아닌 학교 학과 교육과정 (고용24 NCS 교육과정 경유)
ACADEMIC_PROVIDER = r"전문대|마이스터고|학과"
HEADER_TITLES = {"과정명", "강좌명", "교육과정명", "title"}
# 검토 후 제외하지 않기로 한 강좌
ALLOW_UIDS: set = set()


def main() -> int:
    df = pd.read_parquet(SRC)
    title = df["title"].fillna("")
    provider = df["provider"].fillna("")
    ga_uids, unrelated = load_scope_rules()
    rows = []
    for uid, t, p in zip(df["course_uid"], title, provider):
        if uid in ALLOW_UIDS:
            continue
        reason = None
        if uid in ga_uids:
            reason = "인사 범위 밖: 고용24 NCS 총무(020201) 과정"
        elif norm_title(t) in unrelated:
            reason = "팀원 검수: 인사 업무와 무관"
        elif t.strip() in HEADER_TITLES:
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
