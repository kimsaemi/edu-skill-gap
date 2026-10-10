"""
수도권 직무교육 프로젝트 - 수집 데이터 전처리 및 표준화 파이프라인
위치: scripts/process_hr_courses.py

작업 내용:
  1. 원본 데이터 3종(국민내일배움카드, 사업주훈련, NCS 교육과정) 로드
  2. 공통 표준 스키마 정의 및 매핑
  3. NCS 분류코드 앞자리 0 보존 (str 타입 보존)
  4. 과정 ID와 개설 회차의 명확한 복합키 분리
  5. 날짜 포맷 표준화(YYYY-MM-DD) 및 훈련일수 계산
  6. 인사·총무 직무 체계적 분류 (명확한 행 vs 검토 대상 행 구분)
  7. 정제 전후 비교 및 감사(Audit) 보고서 생성
  8. data/hr/processed/ 에 CSV 및 JSON 저장
"""

import json
import re
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# 디렉토리 경로
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "hr" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 1. 인사·총무 직무 분류 함수
# ==============================================================================
def classify_hr_job(ncs_cd, title_or_name, text=""):
    """
    NCS 분류코드 및 과정명을 기반으로 직무를 분류.
    불명확한 행은 삭제하지 않고 '검토대상'으로 분류하여 보존.
    """
    cd = str(ncs_cd or "").strip()
    title = str(title_or_name or "").strip()
    full_text = f"{title} {str(text or '')}".strip()

    # 1. NCS 코드 기반 분류 (02: 경영·회계·사무)
    # 0202: 인사·조직
    if cd.startswith("0202"):
        return "인사·조직", "CLEAR"
    # 0203: 노무관리
    if cd.startswith("0203"):
        return "노무관리", "CLEAR"
    # 0201: 총무·일반사무
    if cd.startswith("0201") or cd.startswith("0204"):
        return "총무·일반사무", "CLEAR"

    # 2. 텍스트 키워드 기반 분류
    if any(k in full_text for k in ["인사관리", "채용", "인사평가", "HRD", "HRM", "인사노무"]):
        return "인사·조직", "CLEAR"
    if any(k in full_text for k in ["노무", "근로기준법", "임금", "노사관계"]):
        return "노무관리", "CLEAR"
    if any(k in full_text for k in ["총무", "비품관리", "자산관리", "사무행정", "비즈니스 매너", "비서"]):
        return "총무·일반사무", "CLEAR"

    # 3. 인접 직무 (경영기획, 프로젝트관리 등 인사/총무와 연관된 경우)
    if cd.startswith("0101") or "프로젝트" in full_text:
        return "경영·기획(인접)", "REVIEW_NEEDED"
    if cd.startswith("02"):
        return "경영·사무(일반)", "REVIEW_NEEDED"

    # 4. 불명확한 경우 -> 검토대상으로 보존
    return "검토대상(기타)", "REVIEW_NEEDED"


# ==============================================================================
# 2. 각 데이터셋별 정제 및 표준화
# ==============================================================================
def process_kmbc_data():
    raw_path = RAW_DIR / "kmbc_courses_raw.json"
    with open(raw_path, encoding="utf-8") as f:
        raw_list = json.load(f)

    processed_rows = []
    for item in raw_list:
        ncs_cd = str(item.get("ncsCd") or "").zfill(8) if item.get("ncsCd") else ""
        title = item.get("title", "")
        job_cat, clarity = classify_hr_job(ncs_cd, title)

        # 날짜 및 기간 계산
        st_dt = item.get("traStartDate")
        end_dt = item.get("traEndDate")
        duration_days = None
        if st_dt and end_dt:
            try:
                d1 = datetime.strptime(st_dt, "%Y-%m-%d")
                d2 = datetime.strptime(end_dt, "%Y-%m-%d")
                duration_days = (d2 - d1).days + 1
            except Exception:
                pass

        row = {
            "source_api": "국민내일배움카드",
            "course_id": str(item.get("trprId", "")),
            "course_turn": str(item.get("trprDegr", "")),
            "course_key": f"{item.get('trprId')}_{item.get('trprDegr')}",
            "course_name": title,
            "institution_name": item.get("subTitle", ""),
            "ncs_full_cd": ncs_cd,
            "ncs_lclas_cd": ncs_cd[:2] if len(ncs_cd) >= 2 else "",
            "ncs_mclas_cd": ncs_cd[2:4] if len(ncs_cd) >= 4 else "",
            "ncs_sclas_cd": ncs_cd[4:6] if len(ncs_cd) >= 6 else "",
            "ncs_subd_cd": ncs_cd[6:8] if len(ncs_cd) >= 8 else "",
            "hr_job_category": job_cat,
            "job_clarity": clarity,
            "start_date": st_dt,
            "end_date": end_dt,
            "duration_days": duration_days,
            "training_hours": None,  # 목록 API에는 총훈련시간 누락 (상세 API 조회 필요)
            "credits": None,
            "cost_total": float(item.get("courseMan") or 0),
            "cost_self": float(item.get("realMan") or 0),
            "capacity": int(item.get("yardMan") or 0),
            "region": item.get("address", ""),
            "training_target": item.get("trainTarget", "")
        }
        processed_rows.append(row)

    return pd.DataFrame(processed_rows), len(raw_list)


def process_employer_data():
    raw_path = RAW_DIR / "employer_courses_raw.json"
    with open(raw_path, encoding="utf-8") as f:
        raw_list = json.load(f)

    processed_rows = []
    for item in raw_list:
        ncs_cd = str(item.get("ncsCd") or "").zfill(8) if item.get("ncsCd") else ""
        title = item.get("title", "")
        job_cat, clarity = classify_hr_job(ncs_cd, title)

        st_dt = item.get("traStartDate")
        end_dt = item.get("traEndDate")
        duration_days = None
        if st_dt and end_dt:
            try:
                d1 = datetime.strptime(st_dt, "%Y-%m-%d")
                d2 = datetime.strptime(end_dt, "%Y-%m-%d")
                duration_days = (d2 - d1).days + 1
            except Exception:
                pass

        row = {
            "source_api": "사업주훈련",
            "course_id": str(item.get("trprId", "")),
            "course_turn": str(item.get("trprDegr", "")),
            "course_key": f"{item.get('trprId')}_{item.get('trprDegr')}",
            "course_name": title,
            "institution_name": item.get("subTitle", ""),
            "ncs_full_cd": ncs_cd,
            "ncs_lclas_cd": ncs_cd[:2] if len(ncs_cd) >= 2 else "",
            "ncs_mclas_cd": ncs_cd[2:4] if len(ncs_cd) >= 4 else "",
            "ncs_sclas_cd": ncs_cd[4:6] if len(ncs_cd) >= 6 else "",
            "ncs_subd_cd": ncs_cd[6:8] if len(ncs_cd) >= 8 else "",
            "hr_job_category": job_cat,
            "job_clarity": clarity,
            "start_date": st_dt,
            "end_date": end_dt,
            "duration_days": duration_days,
            "training_hours": None,
            "credits": None,
            "cost_total": float(item.get("courseMan") or 0),
            "cost_self": float(item.get("realMan") or 0),
            "capacity": int(item.get("yardMan") or 0),
            "region": item.get("address", ""),
            "training_target": item.get("trainTarget", "")
        }
        processed_rows.append(row)

    return pd.DataFrame(processed_rows), len(raw_list)


def process_ncs_data():
    raw_path = RAW_DIR / "ncs_courses_raw.json"
    with open(raw_path, encoding="utf-8") as f:
        raw_list = json.load(f)

    processed_rows = []
    for idx, item in enumerate(raw_list):
        l_cd = str(item.get("ncsLclasCd") or "").zfill(2)
        m_cd = str(item.get("ncsMclasCd") or "").zfill(2)
        s_cd = str(item.get("ncsSclasCd") or "").zfill(2)
        sub_cd = str(item.get("ncsSubdCd") or "").zfill(2)
        ncs_full = f"{l_cd}{m_cd}{s_cd}{sub_cd}"

        subj_name = item.get("asubjName", "")
        edu_text = item.get("eduText", "")
        job_cat, clarity = classify_hr_job(ncs_full, subj_name, edu_text)

        # 고유 식별자 생성
        c_id = f"NCS_{ncs_full}_{idx+1}"

        row = {
            "source_api": "NCS 교육과정",
            "course_id": c_id,
            "course_turn": "1",  # 표준 교육과정 단일 회차
            "course_key": f"{c_id}_1",
            "course_name": subj_name,
            "institution_name": f"{item.get('scholDstinCdnm', '')} {item.get('depttName', '')}".strip(),
            "ncs_full_cd": ncs_full,
            "ncs_lclas_cd": l_cd,
            "ncs_mclas_cd": m_cd,
            "ncs_sclas_cd": s_cd,
            "ncs_subd_cd": sub_cd,
            "hr_job_category": job_cat,
            "job_clarity": clarity,
            "start_date": None,
            "end_date": None,
            "duration_days": None,
            "training_hours": int(item.get("lssntimTime") or 0),
            "credits": int(item.get("point") or 0),
            "cost_total": 0.0,
            "cost_self": 0.0,
            "capacity": None,
            "region": item.get("scholDstinCdnm", ""),
            "training_target": item.get("hmfrcFosterType", "")
        }
        processed_rows.append(row)

    return pd.DataFrame(processed_rows), len(raw_list)


# ==============================================================================
# 메인 전처리 및 감사 리포트 파이프라인
# ==============================================================================
def main():
    print("=" * 70)
    print(" [전처리] 3대 수집 원본 데이터 표준화 및 직무 분류 파이프라인 실행")
    print("=" * 70)

    # 1. 개별 전처리
    df_kmbc, raw_cnt_kmbc = process_kmbc_data()
    df_emp, raw_cnt_emp = process_employer_data()
    df_ncs, raw_cnt_ncs = process_ncs_data()

    # 2. 통합 데이터프레임 구성
    df_integrated = pd.concat([df_kmbc, df_emp, df_ncs], ignore_index=True)

    # 문자열 타입 강제 보존 (앞자리 0 보호)
    code_cols = ["course_id", "course_turn", "course_key", "ncs_full_cd", "ncs_lclas_cd", "ncs_mclas_cd", "ncs_sclas_cd", "ncs_subd_cd"]
    for col in code_cols:
        df_integrated[col] = df_integrated[col].astype(str)

    # 3. CSV 저장
    df_kmbc.to_csv(PROCESSED_DIR / "kmbc_courses_processed.csv", index=False, encoding="utf-8-sig")
    df_emp.to_csv(PROCESSED_DIR / "employer_courses_processed.csv", index=False, encoding="utf-8-sig")
    df_ncs.to_csv(PROCESSED_DIR / "ncs_courses_processed.csv", index=False, encoding="utf-8-sig")
    df_integrated.to_csv(PROCESSED_DIR / "hr_courses_integrated.csv", index=False, encoding="utf-8-sig")

    print(f"[+] 개별 및 통합 CSV 저장 완료 -> {PROCESSED_DIR.resolve()}")

    # 4. 정제 전후 감사(Audit) 통계 계산
    audit_report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_raw_rows": raw_cnt_kmbc + raw_cnt_emp + raw_cnt_ncs,
            "total_processed_rows": len(df_integrated),
            "deleted_rows": 0,  # 원칙: 데이터 임의 삭제 0건
            "data_retention_rate": "100.0%"
        },
        "by_source": {
            "국민내일배움카드": {
                "raw_count": raw_cnt_kmbc,
                "processed_count": len(df_kmbc),
                "deleted": 0,
                "job_distribution": df_kmbc["hr_job_category"].value_counts().to_dict(),
                "clarity_distribution": df_kmbc["job_clarity"].value_counts().to_dict()
            },
            "사업주훈련": {
                "raw_count": raw_cnt_emp,
                "processed_count": len(df_emp),
                "deleted": 0,
                "job_distribution": df_emp["hr_job_category"].value_counts().to_dict(),
                "clarity_distribution": df_emp["job_clarity"].value_counts().to_dict()
            },
            "NCS 교육과정": {
                "raw_count": raw_cnt_ncs,
                "processed_count": len(df_ncs),
                "deleted": 0,
                "job_distribution": df_ncs["hr_job_category"].value_counts().to_dict(),
                "clarity_distribution": df_ncs["job_clarity"].value_counts().to_dict()
            }
        },
        "total_job_distribution": df_integrated["hr_job_category"].value_counts().to_dict(),
        "total_clarity_distribution": df_integrated["job_clarity"].value_counts().to_dict(),
        "review_needed_samples": df_integrated[df_integrated["job_clarity"] == "REVIEW_NEEDED"][
            ["source_api", "course_name", "ncs_full_cd", "hr_job_category"]
        ].to_dict(orient="records")
    }

    # 감사 리포트 JSON 저장
    with open(PROCESSED_DIR / "preprocessing_audit_report.json", "w", encoding="utf-8") as f:
        json.dump(audit_report, f, ensure_ascii=False, indent=2)

    # 콘솔 출력
    print("\n" + "=" * 70)
    print(" [정제 전후 감사(Audit) 결과 보고]")
    print("=" * 70)
    print(f"- 원본 수집 건수: {audit_report['summary']['total_raw_rows']}건")
    print(f"- 정제 완료 건수: {audit_report['summary']['total_processed_rows']}건 (보존율: 100%, 삭제: 0건)")
    print("\n[직무 분류 집계]")
    for cat, count in audit_report["total_job_distribution"].items():
        print(f"  * {cat}: {count}건")
    print("\n[직무 명확도 판정]")
    for clarity, count in audit_report["total_clarity_distribution"].items():
        print(f"  * {clarity} (명확/검토대상): {count}건")
    print(f"\n* 직무 검토 대상(REVIEW_NEEDED) 보존 건수: {len(audit_report['review_needed_samples'])}건")
    print("=" * 70)


if __name__ == "__main__":
    main()
