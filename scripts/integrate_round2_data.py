"""Step E: Integrate Round 1 & Round 2 Data and Validate Quality.
Standardizes schema, handles de-duplication, classifies jobs, maps competencies,
and generates integrated v2 datasets.
"""
import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(".")
RAW_DIR = BASE_DIR / "data" / "hr" / "raw"
ROUND2_RAW_DIR = RAW_DIR / "round2"
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"
OUTPUT_DIR = BASE_DIR / "data" / "hr" / "output" / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def clean_title(title):
    if not title:
        return ""
    t = re.sub(r"\[.*?\]|\(.*?\)", "", title)
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else title.strip()

def clean_inst(inst):
    if not inst:
        return ""
    inst = re.sub(r"\(주\)|주식회사|\(원격\)", "", inst)
    return re.sub(r"\s+", " ", inst).strip()

def run_integration():
    print("=" * 80)
    print(" [STEP E] 1차·2차 데이터 통합, 중복 제거 및 KSA 역량 매핑 재검증")
    print("=" * 80)

    # 1. 1차 정규화 데이터 로드
    df_courses_r1 = pd.read_csv(PROCESSED_DIR / "courses.csv", dtype=str)
    r1_keys = set(df_courses_r1["instance_key"])
    print(f"* 1차 마스터 데이터: {len(df_courses_r1)}건 (고유 키 {len(r1_keys)}개)")

    # 2. 2차 수집 원본 로드
    with open(ROUND2_RAW_DIR / "kmbc_round2_raw.json", "r", encoding="utf-8") as f:
        r2_kmbc = json.load(f)
    with open(ROUND2_RAW_DIR / "employer_round2_raw.json", "r", encoding="utf-8") as f:
        r2_emp = json.load(f)

    total_r2_raw = len(r2_kmbc) + len(r2_emp)
    print(f"* 2차 원본 레코드 수: KMBC {len(r2_kmbc)}건 + 사업주 {len(r2_emp)}건 = 총 {total_r2_raw}건")

    # 3. 2차 데이터 공통 스키마 표준화 및 회차 키 생성
    r2_records = []
    seen_r2_keys = set()
    r2_duplicate_within = 0
    r2_duplicate_with_r1 = 0

    for raw_list, src_name in [(r2_kmbc, "국민내일배움카드"), (r2_emp, "사업주훈련")]:
        for it in raw_list:
            c_id = str(it.get("trprId", "")).strip()
            turn = str(it.get("trprDegr", "1")).strip()
            key = f"{c_id}_{turn}"
            
            # 2차 수집 내 중복 (동일 강좌가 여러 키워드 검색에 수신됨)
            if key in seen_r2_keys:
                r2_duplicate_within += 1
                continue
            seen_r2_keys.add(key)

            # 1차 수집과의 중복
            if key in r1_keys:
                r2_duplicate_with_r1 += 1
                continue

            raw_title = it.get("title", "")
            std_title = clean_title(raw_title)
            raw_inst = it.get("subTitle", "")
            std_inst = clean_inst(raw_inst)
            ncs_cd = str(it.get("ncsCd", "")).strip().zfill(8) if it.get("ncsCd") else ""

            r2_records.append({
                "source_api": src_name,
                "course_id": c_id,
                "course_turn": turn,
                "instance_key": key,
                "course_name_raw": raw_title,
                "course_name_std": std_title,
                "institution_name_raw": raw_inst,
                "institution_name_std": std_inst,
                "ncs_classification_code": ncs_cd,
                "ncs_unit_code": np.nan,
                "ncs_lclas_cd": ncs_cd[:2] if len(ncs_cd) >= 2 else "",
                "ncs_mclas_cd": ncs_cd[2:4] if len(ncs_cd) >= 4 else "",
                "job_id": "",
                "job_clarity": "",
                "start_date": it.get("traStartDate"),
                "end_date": it.get("traEndDate"),
                "training_hours": np.nan,
                "credits": np.nan,
                "cost_total": float(it.get("courseMan") or 0),
                "cost_self": float(it.get("realMan") or 0),
                "capacity": int(it.get("yardMan") or 0),
                "region": it.get("address", ""),
                "edu_goal_text": np.nan,
                "edu_content_text": np.nan,
                "round": "2차",
                "_target_keyword": it.get("_target_keyword", "")
            })

    print(f"\n[중복 검증 결과]")
    print(f"  - 2차 수집 내 키워드 간 중복 제거: {r2_duplicate_within}건")
    print(f"  - 1차 수집본과 중복 제거: {r2_duplicate_with_r1}건")
    print(f"  - 신규 순수 추가 교육과정 수: {len(r2_records)}건")

    df_r2_new = pd.DataFrame(r2_records)

    # 4. 직무 분류 및 역량 매핑 (2차 수집본)
    # 2차 수집본은 우리가 정확히 타겟팅한 인사/총무 강좌들임
    classified_r2 = []
    mappings_r2 = []

    for _, r in df_r2_new.iterrows():
        title = r["course_name_std"]
        ncs_cd = r["ncs_classification_code"]
        key = r["instance_key"]

        job_id = "JOB_0201_GA"
        target_job = "총무·일반사무"
        status = "INCLUDED"
        comp_id = "COMP_GA_01"
        evidence = ""

        # A. 인력채용 (COMP_HR_01)
        if any(k in title for k in ["채용", "선발", "면접", "온보딩"]):
            job_id = "JOB_0202_HR"
            target_job = "인사·채용관리"
            comp_id = "COMP_HR_01"
            evidence = f"과정명 '{title}' 내 채용/선발/퇴직 실무 직결 확인"
        # B. 노무관리 및 근로기준법 (COMP_LABOR_01)
        elif any(k in title for k in ["근로기준법", "노무", "노사", "노동법", "취업규칙", "퇴직"]):
            job_id = "JOB_0203_LABOR"
            target_job = "노무관리"
            comp_id = "COMP_LABOR_01"
            evidence = f"과정명 '{title}' 내 근로기준법 및 노무관리 법률 실무 직결 확인"
        # C. 인사평가 및 보상 (COMP_HR_02)
        elif any(k in title for k in ["인사평가", "평가보상", "성과관리", "kpi", "연봉"]):
            job_id = "JOB_0202_HR"
            target_job = "인사·평가보상"
            comp_id = "COMP_HR_02"
            evidence = f"과정명 '{title}' 내 인사평가체계 및 성과관리 실무 직결 확인"
        # D. 일반 인사관리 (COMP_HR_01 / COMP_HR_02 복합)
        elif any(k in title for k in ["인사관리", "인사기획", "인사실무", "인사총무"]):
            job_id = "JOB_0202_HR"
            target_job = "인사·조직관리"
            comp_id = "COMP_HR_01"
            evidence = f"과정명 '{title}' 내 전략적 인사관리 및 조직운영 실무 직결 확인"
        # E. 비품 및 자산관리 (COMP_GA_02)
        elif any(k in title for k in ["자산관리", "비품", "재물조사", "총무기획", "총무자산"]):
            job_id = "JOB_0201_GA"
            target_job = "총무·자산관리"
            comp_id = "COMP_GA_02"
            evidence = f"과정명 '{title}' 내 총무기획 및 사내 자산관리 실무 직결 확인"
        # F. 총무 일반
        elif any(k in title for k in ["총무", "사무"]):
            job_id = "JOB_0201_GA"
            target_job = "총무·일반사무"
            comp_id = "COMP_GA_01"
            evidence = f"과정명 '{title}' 내 총무관리 실무 직결 확인"
        else:
            status = "REVIEW_NEEDED"
            target_job = "검토필요"
            comp_id = "COMP_UNMAPPED"
            evidence = "추가 확인 필요"

        r["job_id"] = job_id
        r["job_clarity"] = "CLEAR" if status == "INCLUDED" else "REVIEW_NEEDED"
        r["step3_status"] = status
        r["step3_target_job"] = target_job
        classified_r2.append(r)

        if status == "INCLUDED":
            mappings_r2.append({
                "instance_key": key,
                "course_name_std": title,
                "competency_id": comp_id,
                "mapping_status": "VERIFIED",
                "mapping_evidence": evidence,
                "eda_ready": "Y",
                "round": "2차"
            })

    df_r2_classified = pd.DataFrame(classified_r2)
    df_r2_mappings = pd.DataFrame(mappings_r2)

    # 5. 1차 마스터와 결합하여 v2 데이터셋 구축
    df_courses_r1["round"] = "1차"
    
    # 1차 확정 9건 매핑 로드
    df_ver_r1 = pd.read_csv(PROCESSED_DIR / "hr_mapping_verified.csv", dtype=str)
    df_ver_r1["round"] = "1차"

    # 전체 통합 교육과정 마스터 (1차 50건 + 2차 신규 고유건)
    df_all_v2 = pd.concat([df_courses_r1, df_r2_classified], ignore_index=True)
    df_all_v2.to_csv(PROCESSED_DIR / "hr_courses_integrated_v2.csv", index=False, encoding="utf-8-sig")

    # 매핑 테이블 통합
    df_ver_v2 = pd.concat([df_ver_r1, df_r2_mappings], ignore_index=True)
    df_ver_v2.to_csv(PROCESSED_DIR / "hr_mapping_verified_v2.csv", index=False, encoding="utf-8-sig")

    # 1차 확정(9건) + 2차 확정건 결합 -> EDA v2 데이터셋
    # 1차 EDA 데이터 로드
    df_eda_r1 = pd.read_csv(PROCESSED_DIR / "hr_courses_eda.csv", dtype=str)
    df_eda_r1["round"] = "1차"
    df_eda_r2 = df_r2_classified[df_r2_classified["step3_status"] == "INCLUDED"].copy()

    df_eda_v2 = pd.concat([df_eda_r1, df_eda_r2], ignore_index=True)
    
    # EDA v2에 필요한 파생변수 일괄 생성
    def calc_dur(row):
        start = row.get("start_date")
        end = row.get("end_date")
        if pd.notna(start) and pd.notna(end) and start != "" and end != "":
            try:
                days = (pd.to_datetime(end) - pd.to_datetime(start)).days + 1
                group = "1개월 (30~31일)" if days <= 31 else ("2개월 (59~60일)" if days <= 60 else "3개월 이상")
                return days, group
            except:
                pass
        return np.nan, "정보없음(UNKNOWN)"

    durs = df_eda_v2.apply(calc_dur, axis=1)
    df_eda_v2["duration_days"] = [d[0] for d in durs]
    df_eda_v2["duration_group"] = [d[1] for d in durs]

    def calc_level(name):
        n = str(name).lower()
        if any(k in n for k in ["초보", "첫걸음", "기초", "입문", "시작", "a to z", "꿀팁", "생존력", "빨리 배워", "알기 쉬운"]):
            return "입문/초급"
        elif any(k in n for k in ["관리사", "기사", "cmos", "전문가", "전략적", "고급"]):
            return "고급/전문"
        return "중급/실무"

    df_eda_v2["course_level_group"] = df_eda_v2["course_name_std"].apply(calc_level)
    df_eda_v2.to_csv(PROCESSED_DIR / "hr_courses_eda_v2.csv", index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print(f"[+] 1차 + 2차 데이터 통합 완료:")
    print(f"    - 통합 전체 마스터 건수: {len(df_all_v2)}건 (1차 {len(df_courses_r1)} + 2차 신규 {len(df_r2_new)})")
    print(f"    - 통합 EDA 확정 교육과정 수 (v2): {len(df_eda_v2)}건 (1차 {len(df_eda_r1)} + 2차 확정 {len(df_eda_r2)})")
    print(f"    - 통합 검증된 역량 매핑 수 (v2): {len(df_ver_v2)}건")
    print("=" * 80)

    # 6. 통합 감사 리포트 저장
    audit_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step": "STEP E 1차·2차 데이터 통합 및 재검증",
        "round1_count": len(df_courses_r1),
        "round2_raw_count": total_r2_raw,
        "round2_duplicates_internal": r2_duplicate_within,
        "round2_duplicates_with_round1": r2_duplicate_with_r1,
        "round2_new_unique_courses": len(df_r2_new),
        "total_integrated_master_count": len(df_all_v2),
        "eda_v1_count": len(df_eda_r1),
        "eda_v2_count": len(df_eda_v2),
        "eda_growth": f"+{len(df_eda_r2)}건 (+{len(df_eda_r2)/len(df_eda_r1)*100:.1f}%)",
        "verified_mappings_v2_count": len(df_ver_v2)
    }

    with open(OUTPUT_DIR / "round2_integration_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)

    return df_all_v2, df_eda_v2, df_ver_v2

if __name__ == "__main__":
    run_integration()
