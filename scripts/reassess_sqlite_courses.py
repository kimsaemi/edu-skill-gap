"""Task B: Audit and Reclassify the 413 SQLite courses into INCLUDED, REVIEW_NEEDED, EXCLUDED.
Outputs to data/hr/output/integration/sqlite_classification_review.csv.
"""
import sys
import re
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(".")
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"
OUTPUT_DIR = BASE_DIR / "data" / "hr" / "output" / "integration"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df_sqlite = pd.read_csv(PROCESSED_DIR / "sqlite_hr_courses_integrated.csv", dtype=str)
print(f"Total input SQLite courses: {len(df_sqlite)}")

# 제외 패턴 (IT개발, 반도체, 개인재테크, 어학 등)
EXCLUDE_TITLE_PATTERNS = [
    r"백엔드", r"웹개발", r"java", r"spring", r"파이썬", r"c\+\+", r"코딩", r"프로그래밍",
    r"반도체", r"cmos", r"제조 데이터", r"공정", r"스마트금융", r"주식", r"부동산", r"재테크",
    r"영어", r"ted", r"토익", r"외국어", r"청소년", r"시리즈", r"문학", r"소설", r"역사",
    r"자율주행", r"vehicle", r"cg vfx", r"영상/3d"
]
exclude_regex = re.compile("|".join(EXCLUDE_TITLE_PATTERNS), re.IGNORECASE)

# 인사/총무 핵심 확정 패턴
INCLUDED_HR_PATTERNS = [
    r"인사관리", r"인사담당", r"인사실무", r"인사기획", r"인사평가", r"평가보상", r"인재확보", r"채용", r"면접관",
    r"온보딩", r"근로기준법", r"노동법", r"노무관리", r"노무실무", r"취업규칙", r"노사", r"연봉", r"성과관리",
    r"총무관리", r"총무기획", r"총무실무", r"고정자산", r"자산 취득", r"비품관리", r"재물조사",
    r"보고서 작성", r"기획서", r"문서작성", r"비즈니스 글쓰기", r"비즈니스 매너", r"비즈니스 에티켓",
    r"hr tech", r"digital hr", r"hrd", r"hrm", r"교육과정 기획", r"인재육성"
]
included_regex = re.compile("|".join(INCLUDED_HR_PATTERNS), re.IGNORECASE)

audit_rows = []

for idx, r in df_sqlite.iterrows():
    platform = r["platform"]
    cid = r["course_id"]
    key = r["instance_key"]
    title = str(r["course_name"]).strip()
    cat = str(r["category"]).strip()
    desc = str(r["description_snippet"]).strip()
    url = str(r["url"]).strip()
    
    text_check = f"{title} {cat}"
    
    status = "REVIEW_NEEDED"
    reason = ""
    assigned_job_group = "기타/인접"
    assigned_job_cat = r["job_family"]

    # 1. 명확한 제외 대상
    if exclude_regex.search(text_check):
        status = "EXCLUDED"
        reason = f"IT개발/어학/제조/개인재테크 등 비관련 전문 분야로 판정 (매칭: {title})"
        assigned_job_group = "비관련(타분야)"
    # 2. 명확한 인사(HR) 및 총무·사무행정 포함 대상
    elif included_regex.search(title):
        status = "INCLUDED"
        if any(k in title for k in ["채용", "면접", "온보딩", "인재확보"]):
            assigned_job_group = "인사(HR)"
            assigned_job_cat = "인사·채용관리"
            reason = "기업 채용/선발/온보딩 프로세스 직무 실무 직결"
        elif any(k in title for k in ["근로기준법", "노동법", "노무", "노사", "취업규칙"]):
            assigned_job_group = "인사(HR)"
            assigned_job_cat = "노무관리"
            reason = "노동법 및 근로기준 준수, 노무관리 실무 직결"
        elif any(k in title for k in ["인사평가", "평가보상", "성과관리", "연봉", "kpi"]):
            assigned_job_group = "인사(HR)"
            assigned_job_cat = "인사·평가보상"
            reason = "인사평가체계 및 보상/성과관리 실무 직결"
        elif any(k in title for k in ["인사", "hr", "hrd", "hrm", "인재육성", "교육과정"]):
            assigned_job_group = "인사(HR)"
            assigned_job_cat = "인사·조직관리"
            reason = "기업 인사조직 및 인적자원개발(HRD) 실무 직결"
        elif any(k in title for k in ["고정자산", "자산 취득", "비품", "재물조사"]):
            assigned_job_group = "총무·사무행정"
            assigned_job_cat = "총무·자산관리"
            reason = "사내 비품 및 고정자산 취득·관리·처분 실무 직결"
        elif any(k in title for k in ["총무"]):
            assigned_job_group = "총무·사무행정"
            assigned_job_cat = "총무·일반사무"
            reason = "기업 총무관리 프로세스 및 실무 직결"
        elif any(k in title for k in ["보고서", "기획서", "문서작성", "글쓰기"]):
            assigned_job_group = "총무·사무행정"
            assigned_job_cat = "공통·사무기획"
            reason = "사내 비즈니스 문서작성 및 보고서 기획 실무 직결"
        elif any(k in title for k in ["매너", "에티켓"]):
            assigned_job_group = "총무·사무행정"
            assigned_job_cat = "비서·사무지원"
            reason = "비즈니스 에티켓 및 의전/사무소통 실무 직결"
        else:
            assigned_job_group = "인사·총무공통"
            reason = "인사·총무 부합 실무 강좌 확인"
    # 3. 추가 검토 필요 (리더십, AI 활용, 일반 업무스킬 등)
    else:
        status = "REVIEW_NEEDED"
        if any(k in title for k in ["리더", "코칭", "소통", "조직문화"]):
            assigned_job_group = "인접(리더십/조직)"
            reason = "리더십/조직문화/소통 강좌로, 인사(HRD) 부서 적용 범위 추가 검토 요망"
        elif any(k in title for k in ["ai", "chatgpt", "자동화", "생성형"]):
            assigned_job_group = "인접(디지털사무)"
            reason = "생성형 AI 및 엑셀 자동화 툴 강좌로, 사무행정 필수 직무 연계성 검토 요망"
        else:
            assigned_job_group = "인접(일반사무)"
            reason = "과정명 맥락상 인사·총무와의 직접 연계성 추가 검토 필요"

    audit_rows.append({
        "platform": platform,
        "source_course_id": cid,
        "instance_key": key,
        "course_name": title,
        "category": cat,
        "job_group": assigned_job_group,
        "job_category": assigned_job_cat,
        "classification_status": status,
        "classification_reason": reason,
        "course_url": url,
        "description_snippet": desc
    })

df_audit = pd.DataFrame(audit_rows)
out_csv = OUTPUT_DIR / "sqlite_classification_review.csv"
df_audit.to_csv(out_csv, index=False, encoding="utf-8-sig")

print(f"\n[+] SQLite 413건 직무 분류 재검토 완료 -> {out_csv}")
print("\n[상태별 분포]")
print(df_audit["classification_status"].value_counts())
print("\n[상위 직무 그룹별 분포]")
print(df_audit["job_group"].value_counts())
print("\n[세부 직무 카테고리별 분포 (INCLUDED 확정본)]")
print(df_audit[df_audit["classification_status"] == "INCLUDED"]["job_category"].value_counts())
