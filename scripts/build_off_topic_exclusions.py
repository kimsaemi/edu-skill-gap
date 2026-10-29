"""
인사 직무교육과 무관한 강좌를 추천 대상에서 빼기 위한 제외 목록을 만듭니다.

2026-10-28 팀 결정으로 프로젝트 범위를 '인사'로 정해 아래 규칙을 더했습니다.
  - 고용24 공식 NCS 분류가 총무(020201…)인 과정: 인사 범위 밖 (data/hr/processed/work24_course_details.csv의 ncs_code)
  - 팀원 분야 검수에서 '인사 업무와 무관'으로 판정한 과정 (data/hr/output/recommendation/domain_mapping_review_results.csv)
  - 근로자·관리감독자 대상 법정 안전보건교육('채용 시'·'노무제공 시'가 채용·노무에 걸림), 마케팅·커머스 과정
2026-10-29 팀 결정으로 더한 규칙
  - 자격증 취득 과정(ITQ·컴활·OPIc·전산세무 등): 카탈로그에는 남기고 추천에서만 뺀다.
    인사 실무와 묶인 과정(ERP 인사, 인사급여 실무, 채용면접 자격 등)은 남긴다.
    엑셀·문서작성처럼 업무 활용이 목적인 과정은 '사무 일반'으로 남긴다.
  - 온보딩 기준: '인사 담당자가 온보딩을 설계·운영하는 데 도움이 되는가'.
    신입사원·경력입사자·신임 리더 본인이 듣는 적응 과정은 인사 담당자용이 아니라 뺀다.
  - 온보딩 분야 추천에 섞여 있던 인사와 무관한 과정(개발·재무회계·영업 등)
  - 다른 직무의 전문 과정(재무·회계·예산, 생산·구매·품질, 영업·홍보, IT 개발, 무역·외국어,
    프로젝트 관리)과 공식 NCS 코드가 없는 기관의 총무 과정. 제목에 인사 실무 단어가 있으면 남긴다.
    엑셀·보고서·생성형 AI 활용 같은 공통 업무 과정은 '사무 일반'으로 남긴다.
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
    ("신입·경력·신임자 본인 대상 적응 과정 (온보딩 담당 업무 아님)",
     r"신입사원|신입 온보딩|신규입사자의 온보딩|\[온보딩저니\] 경력사원|경력입사자 온보딩"
     r"|신임\s?(?:리더|팀장|임원|부장|차장|과장|대리)|사회초년생|김경일의 슬기로운 직장생활|셀프리더 루키"),
    ("온보딩 추천 점검: 인사 업무와 무관",
     r"Spring Framework|클로드 코드와 커서|^\[여의도\] 재무회계 기초$|영업사원 입문|금융 고객경험"
     r"|자립준비청년|퇴사를 준비하는 사람들"),
]
# 다른 직무의 전문 과정. 제목에 인사 실무 단어(NON_HR_KEEP)가 있으면 남긴다.
NON_HR_RULES = [
    ("다른 직무: 재무·회계·예산", r"예산관리|예산편성|예산회계|관리회계|원가회계|원가계산|원가관리|재무회계|재무제표|재무관리"
                             r"|기업가치평가|금융상품|세금 상식|사업 타당성|경영전략 및 사업혁신"),
    ("다른 직무: 생산·구매·품질", r"생산능력|생산성측정|공장|구매조직|구매협상|구매관리|외자구매|글로벌소싱|품질관리|공수계획|수요예측|재고관리"),
    ("다른 직무: 영업·홍보", r"영업전략|채널 입점|상품소개서|가격 전략|콘텐츠마케터|뉴스레터 영업|언론홍보|보도자료|저널리즘"),
    ("다른 직무: IT 개발·데이터 엔지니어링", r"ABAP|하둡|벡터DB|GraphDB|머신러닝을 활용한 빅데이터|파이썬을 활용한 머신러닝|데이터 엔지니어링|Python 라이브러리를 활용한 인공지능"),
    ("다른 직무: 무역·외국어", r"무역영어|수출입|비즈니스 영어"),
    ("다른 직무: 프로젝트 관리", r"프로젝트 관리|프로젝트관리|프로젝트 품질"),
    ("인사 범위 밖: 총무 과정 (NCS 코드 없는 기관)", r"총무"),
]
NON_HR_KEEP = r"인사|HR|노무|채용|급여|인건비|HRD|교육훈련|교육평가"

# 위 규칙에 걸려도 인사 담당자용이라 남기는 제목
KEEP_TITLE = r"온보딩 전략|인사·회계·법무 입문"

# 자격증 취득 과정. 제목에 인사 실무 단어가 함께 있으면 남긴다.
CERT_RULE = ("자격증 취득 과정 (인사 직무 자격 아님)",
             r"ITQ|컴퓨터활용능력|컴활|GTQ|\bMOS\b|워드프로세서|자격증|자격\s*취득|빅데이터분석기사|사회조사분석사"
             r"|전산세무|전산회계|재경관리사|정보관리기술사|정보처리기사|OPIc|토익|TOEIC|ADsP|SQLD")
CERT_HR_KEEP = r"HR|채용|면접|인사|노무|HRD|교육|인사평가|성과평가|급여|노동|직업상담|코칭"
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
                if re.search(pat, t) and not re.search(KEEP_TITLE, t):
                    reason = r
                    break
            if reason is None and re.search(CERT_RULE[1], t) and not re.search(CERT_HR_KEEP, t):
                reason = CERT_RULE[0]
            if reason is None and not re.search(NON_HR_KEEP, t):
                reason = next((r for r, pat in NON_HR_RULES if re.search(pat, t)), None)
        if reason:
            rows.append({"course_uid": uid, "title": t, "provider": p, "reason": reason})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"제외 {len(out)}건 / 전체 {len(df)}건 → {OUT}")
    print(out["reason"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
