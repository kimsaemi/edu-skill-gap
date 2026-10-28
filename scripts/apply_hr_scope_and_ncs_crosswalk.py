"""
프로젝트 범위를 '인사'로 정하고, 역량 체계를 '인사 9개 분야' 하나로 맞춘다.

1. 대응표 저장: data/hr/reference/hr_domain_ncs_crosswalk.csv
   인사 9개 분야 -> NCS 세분류·능력단위 -> 기존 8개 역량 코드(COMP_*)
   NCS 세분류 코드 근거: 고용24 API 응답의 공식 ncsCd와 과정명(02020101 '총무기획과 총무자산관리',
   02020201 '인사평가체계 구축', 02020202 '근로기준법' 과정들). 능력단위 이름은 NCS 기반 직무기술서(2차 자료)로 확인했으며
   공식 NCS 사이트(ncs.go.kr)에서 최종 확인이 필요하다.

2. 확정 과정(hr_recommendation_candidates.csv)에 인사 범위 적용
   - hr_scope 컬럼: HR_CORE(인력채용, 인사평가 및 보상, 근로관계 법률 준수)
                    COMMON_SUPPORT(문서작성 및 기획, 비즈니스 매너 및 커뮤니케이션: 인사 담당자도 쓰는 공통 업무역량)
                    OUT_OF_SCOPE(총무)
   - 총무 과정은 recommendation_readiness = EXCLUDED_OUT_OF_SCOPE
     · primary_competency가 '비품 및 자산관리'(COMP_GA_02)
     · 고용24 공식 NCS 코드(ncsCd)가 총무 세분류(02020101)
   - ncs_code_official 컬럼: 고용24 과정의 공식 NCS 세분류 코드 (다른 기관 과정은 없음)

3. 역량·직무 마스터(data/hr/processed/competencies.csv, jobs.csv)의 NCS 코드 정정
   - 기존 ncs_unit_code(예: 02020201_16v3)는 세분류 코드에 버전을 붙인 값으로, 능력단위 코드가 아니었다.
     02020202를 '인사평가'로, 02030201을 '노무'로 적은 것도 맞지 않다(0203은 재무·회계 중분류).
   - 확인된 세분류 코드만 남기고, 확인하지 못한 코드는 비우고 ncs_note에 이유를 적는다.
   - hr_scope 컬럼 추가.

실행 순서: fix_work24_course_urls.py -> attach_work24_satisfaction.py -> fix_work24_fee_and_scope.py -> 이 스크립트
여러 번 실행해도 결과가 같다.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "hr" / "output" / "recommendation" / "hr_recommendation_candidates.csv"
PROCESSED = ROOT / "data" / "hr" / "processed"
CROSSWALK = ROOT / "data" / "hr" / "reference" / "hr_domain_ncs_crosswalk.csv"
RAW_FILES = [
    "data/hr/raw/kmbc_courses_raw.json",
    "data/hr/raw/employer_courses_raw.json",
    "data/hr/raw/round2/kmbc_round2_raw.json",
    "data/hr/raw/round2/employer_round2_raw.json",
]

NCS_HR = "02020201"      # 경영·회계·사무 > 총무·인사 > 인사·조직 > 인사
NCS_LABOR = "02020202"   # 인사·조직 > 노무관리 (고용24 ncsCd·과정명 기준)
NCS_GA = "02020101"      # 총무·인사 > 총무 > 총무 (인사 범위 밖)

# 인사 9개 분야 대응표. 분야 ID와 이름은 고객용 화면·검수 시트와 같다.
CROSSWALK_ROWS = [
    ("DOM_01", "인사전략·인력기획", NCS_HR, "인사", "인사기획", "", "직접"),
    ("DOM_02", "조직설계·직무분석", NCS_HR, "인사", "인사기획(직무관리 관련 단위는 확인 필요)", "", "부분"),
    ("DOM_03", "인재채용", NCS_HR, "인사", "인력채용", "COMP_HR_01", "직접"),
    ("DOM_04", "온보딩·직원경험", NCS_HR, "인사", "인력이동관리(일부)", "COMP_HR_01", "약함·NCS 외 현업 확장"),
    ("DOM_05", "성과평가·목표관리", NCS_HR, "인사", "인사평가", "COMP_HR_02", "직접"),
    ("DOM_06", "보상·급여·복리후생", NCS_HR, "인사", "임금관리", "COMP_HR_02", "직접"),
    ("DOM_07", "인재육성·사내교육", NCS_HR, "인사", "교육훈련", "", "직접"),
    ("DOM_08", "조직문화·사내소통", "", "", "직접 대응 없음", "", "NCS 외 현업 확장"),
    ("DOM_09", "노사관계·노무", NCS_LABOR, "노무관리", "노사관계계획, 노사협의회 운영 등", "COMP_LABOR_01", "직접"),
]

# 기존 8개 역량 코드 -> 인사 범위
COMPETENCY_SCOPE = {
    "COMP_HR_01": ("HR_CORE", NCS_HR, "세분류 '인사'의 능력단위 '인력채용'. 능력단위 코드는 확인 필요"),
    "COMP_HR_02": ("HR_CORE", NCS_HR, "세분류 '인사'의 능력단위 '인사평가'·'임금관리'. 능력단위 코드는 확인 필요"),
    "COMP_LABOR_01": ("HR_CORE", NCS_LABOR, "세분류 '노무관리'. 능력단위 코드는 확인 필요"),
    "COMP_GA_01": ("COMMON_SUPPORT", "", "인사 담당자도 쓰는 공통 업무역량. 기존 코드(02010101)는 경영기획 세분류라 맞지 않아 비움"),
    "COMP_SEC_01": ("COMMON_SUPPORT", "", "인사 담당자도 쓰는 공통 업무역량. 기존 코드는 확인되지 않아 비움"),
    "COMP_GA_02": ("OUT_OF_SCOPE", NCS_GA, "총무 세분류. 인사 범위 밖"),
    "COMP_MGMT_01": ("OUT_OF_SCOPE", "", "경영기획·프로젝트 관리. 인사 범위 밖, 코드 확인되지 않음"),
    "COMP_MGMT_02": ("OUT_OF_SCOPE", "", "경영전략·재무회계. 인사 범위 밖, 코드 확인되지 않음"),
}

JOB_SCOPE = {
    "JOB_0202_HR": ("IN", NCS_HR, ""),
    "JOB_0203_LABOR": ("IN", NCS_LABOR, "기존 ncs_code_prefix 0203은 재무·회계 중분류라 맞지 않음. 노무관리는 총무·인사 > 인사·조직 아래"),
    "JOB_0201_GA": ("OUT", NCS_GA, "기존 ncs_code_prefix 0201은 기획사무 중분류라 맞지 않음. 총무는 총무·인사 > 총무 아래"),
    "JOB_0204_SEC": ("OUT", "", "기존 ncs_code_prefix 0204는 생산·품질관리 중분류라 맞지 않음. 코드 확인되지 않음"),
    "JOB_0101_MGMT": ("OUT", "", "코드 확인되지 않음"),
    "JOB_9999_OTHER": ("OUT", "", ""),
}


def write_crosswalk():
    CROSSWALK.parent.mkdir(parents=True, exist_ok=True)
    cw = pd.DataFrame(CROSSWALK_ROWS, columns=[
        "domain_id", "domain_name", "ncs_subcategory_code", "ncs_subcategory_name",
        "ncs_units", "legacy_competency_id", "ncs_fit"])
    cw["ncs_verification"] = "세분류 코드: 고용24 ncsCd로 확인 / 능력단위 이름: 2차 자료, ncs.go.kr 확인 필요"
    cw.loc[cw["ncs_subcategory_code"].eq(""), "ncs_verification"] = "해당 없음"
    cw.to_csv(CROSSWALK, index=False, encoding="utf-8-sig")
    return cw


def load_ncs_codes():
    codes = {}
    for f in RAW_FILES:
        for it in json.loads((ROOT / f).read_text(encoding="utf-8")):
            codes[f"PUB_{it['trprId']}_{it['trprDegr']}"] = it.get("ncsCd")
    return codes


def apply_candidates():
    df = pd.read_csv(CANDIDATES, dtype=str)
    df["ncs_code_official"] = df["course_id"].map(load_ncs_codes())
    df["hr_scope"] = df["primary_competency_id"].map(lambda c: COMPETENCY_SCOPE.get(c, ("OUT_OF_SCOPE",))[0])

    out = df["primary_competency_id"].eq("COMP_GA_02") | df["ncs_code_official"].eq(NCS_GA)
    df.loc[out, "hr_scope"] = "OUT_OF_SCOPE"
    # 이미 다른 이유로 제외된 과정은 그 사유를 유지한다
    newly = out & ~df["recommendation_readiness"].str.startswith("EXCLUDED", na=False)
    df.loc[newly, "recommendation_readiness"] = "EXCLUDED_OUT_OF_SCOPE"
    df.loc[newly, "recommendation_note"] = "총무 과정으로 인사 범위 밖 (비품·자산관리 역량 또는 고용24 NCS 총무 세분류 02020101)"

    df.to_csv(CANDIDATES, index=False, encoding="utf-8-sig")
    active = df[~df["recommendation_readiness"].str.startswith("EXCLUDED", na=False)]
    print(f"[인사 범위] {CANDIDATES.relative_to(ROOT)}")
    print(f"  이번에 범위 밖으로 제외: {int(newly.sum())}건 / 남은 과정 {len(active)}건")
    print(active["hr_scope"].value_counts().to_string())
    print(df["recommendation_readiness"].value_counts().to_string())


def apply_masters():
    comp_path = PROCESSED / "competencies.csv"
    comp = pd.read_csv(comp_path, dtype=str)
    comp["hr_scope"] = comp["competency_id"].map(lambda c: COMPETENCY_SCOPE.get(c, ("OUT_OF_SCOPE", "", ""))[0])
    comp["ncs_unit_code"] = comp["competency_id"].map(lambda c: COMPETENCY_SCOPE.get(c, ("", "", ""))[1])
    comp["ncs_note"] = comp["competency_id"].map(lambda c: COMPETENCY_SCOPE.get(c, ("", "", "확인되지 않음"))[2])
    comp.to_csv(comp_path, index=False, encoding="utf-8-sig")

    jobs_path = PROCESSED / "jobs.csv"
    jobs = pd.read_csv(jobs_path, dtype=str)
    jobs["hr_scope"] = jobs["job_id"].map(lambda j: JOB_SCOPE.get(j, ("OUT", "", ""))[0])
    jobs["ncs_subcategory_code"] = jobs["job_id"].map(lambda j: JOB_SCOPE.get(j, ("", "", ""))[1])
    jobs["ncs_note"] = jobs["job_id"].map(lambda j: JOB_SCOPE.get(j, ("", "", ""))[2])
    jobs.to_csv(jobs_path, index=False, encoding="utf-8-sig")
    print(f"[NCS 정정] {comp_path.relative_to(ROOT)}, {jobs_path.relative_to(ROOT)}")
    print(comp[["competency_id", "competency_name", "hr_scope", "ncs_unit_code"]].to_string(index=False))


def main():
    cw = write_crosswalk()
    print(f"[대응표] {CROSSWALK.relative_to(ROOT)} ({len(cw)}개 분야)")
    apply_candidates()
    apply_masters()


if __name__ == "__main__":
    main()
