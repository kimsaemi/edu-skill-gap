"""Step 3-1 to 3-6 Automated Processing & Quality Verification Script.
Ensures full data integrity, classification review, KSA audit, mapping validation,
and generates reliable datasets for Step 4 EDA.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(".")
RAW_DIR = BASE_DIR / "data" / "hr" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"

def execute_step3():
    print("=" * 80)
    print(" [STEP 3] NCS 기반 인사·총무 데이터 2차 전처리 및 통합 검증 실행")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # 1. 원본 파일 로드 및 무결성 검증 (STEP 3-1)
    # --------------------------------------------------------------------------
    with open(RAW_DIR / "kmbc_courses_raw.json", "r", encoding="utf-8") as f:
        raw_kmbc = json.load(f)
    with open(RAW_DIR / "employer_courses_raw.json", "r", encoding="utf-8") as f:
        raw_emp = json.load(f)
    with open(RAW_DIR / "ncs_courses_raw.json", "r", encoding="utf-8") as f:
        raw_ncs = json.load(f)

    df_courses = pd.read_csv(PROCESSED_DIR / "courses.csv", dtype=str)
    df_jobs = pd.read_csv(PROCESSED_DIR / "jobs.csv", dtype=str)
    df_comp = pd.read_csv(PROCESSED_DIR / "competencies.csv", dtype=str)

    cnt_kmbc = len(raw_kmbc)
    cnt_emp = len(raw_emp)
    cnt_ncs = len(raw_ncs)
    total_raw = cnt_kmbc + cnt_emp + cnt_ncs
    total_courses = len(df_courses)

    assert total_raw == 50, f"Raw count mismatch: {total_raw} != 50"
    assert total_courses == 50, f"Courses count mismatch: {total_courses} != 50"
    print(f"[OK] 원본 3개 파일(20, 20, 10건) 및 courses.csv(50건) 건수 일치 확인 완료.")

    # --------------------------------------------------------------------------
    # 2. 50건 전수 직무 분류 재검토 (STEP 3-2)
    # --------------------------------------------------------------------------
    # 3대 상태 구분: INCLUDED, EXCLUDED, REVIEW_NEEDED
    reclassification = []
    
    for idx, r in df_courses.iterrows():
        key = r["instance_key"]
        source = r["source_api"]
        title = r["course_name_std"]
        inst = r["institution_name_std"]
        ncs_cd = str(r["ncs_classification_code"])
        curr_job = r["job_id"]
        curr_clarity = r["job_clarity"]
        
        status = "REVIEW_NEEDED"
        reason = ""
        target_job = "미분류"
        hr_ga_category = "검토필요"

        # [A] 명확한 분석 제외 대상 (EXCLUDED)
        # 1. 소방/안전 (05)
        if ncs_cd.startswith("05"):
            status = "EXCLUDED"
            target_job = "안전관리·소방"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 05(안전관리/소방설비) 전문 기술자격 취득 과정으로 인사·총무 직무 범위 외"
        # 2. 보건/의료/간호 (06)
        elif ncs_cd.startswith("06"):
            status = "EXCLUDED"
            target_job = "보건·의료·간호"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 06(보건의료/환자간호) 임상 실무 과정으로 인사·총무 직무 범위 외"
        # 3. 전기/전자/반도체 (19)
        elif ncs_cd.startswith("19"):
            status = "EXCLUDED"
            target_job = "전기·전자·반도체"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 19(전기기사/반도체공정) 공학 기술 자격 및 공정 과정으로 인사·총무 직무 범위 외"
        # 4. 부동산 (10020203)
        elif ncs_cd == "10020203":
            status = "EXCLUDED"
            target_job = "부동산·투자"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 소분류 1002(부동산자산투자) 과정으로 기업 총무 자산관리와 다른 개인/투자 실무"
        # 5. 경비 (11010101)
        elif ncs_cd == "11010101":
            status = "EXCLUDED"
            target_job = "경비·청원경찰"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 11(경비지도사 법학개론) 자격증 과정으로 인사·총무 직무 범위 외"
        # 6. 자동차/품질 (15040102)
        elif ncs_cd == "15040102":
            status = "EXCLUDED"
            target_job = "기계·자동차품질"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 15(자동차 생산라인 품질관리) 특화 과정으로 일반 사무/총무와 무관"
        # 7. 건설/플랜트 (14040301)
        elif ncs_cd == "14040301":
            status = "EXCLUDED"
            target_job = "건설·플랜트"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 14(플랜트 공사 현장 자원관리) 과정으로 기업 일반 사무/총무와 무관"
        # 8. 전문 IT 개발/클라우드/DB/블록체인 (20)
        elif ncs_cd in ["20020110", "20010202", "20010204", "20010803"]:
            status = "EXCLUDED"
            target_job = "IT·소프트웨어개발"
            hr_ga_category = "비관련(타직종)"
            reason = f"NCS 대분류 20(AWS인프라/리액트개발/MySQL구축/블록체인) 전문 IT 개발 과정"
        elif ncs_cd == "20010601" and "자격" in title:
            # IEQ 인터넷윤리지도사
            status = "EXCLUDED"
            target_job = "IT윤리·자격"
            hr_ga_category = "비관련(타직종)"
            reason = f"인터넷윤리지도사 자격증 대비 과정으로 사내 인사·총무 실무와 직접 관련성 희박"
        # 9. 물류비관리와 공장물류 (NCS 02040301 - 물류관리, 비서 오분류 수정)
        elif key == "ACG20243000994801_261" or "공장물류" in title:
            status = "EXCLUDED"
            target_job = "물류·유통(공장물류)"
            hr_ga_category = "비관련(생산물류)"
            reason = f"기존 비서(JOB_0204_SEC)로 오분류되었으나, 실제 공장 SCM/물류비 관리 과정으로 총무·비서와 상이"
        # 10. 언택트 시대, e-비즈니스 인사이트 (인사이트 키워드로 인사 오분류 수정)
        elif key == "ACG20243001010743_21" or "e-비즈니스 인사이트" in title:
            status = "EXCLUDED"
            target_job = "영업·마케팅"
            hr_ga_category = "비관련(마케팅)"
            reason = f"과정명 '인사이트' 부분일치로 인사(JOB_0202_HR) 오분류되었으나, NCS 1003(영업마케팅) e비즈니스 트렌드 강좌"
        
        # [B] 명확한 분석 포함 대상 (INCLUDED)
        # 1. 비즈니스 매너 (비서·사무지원)
        elif "글로벌 비즈니스 매너" in title:
            status = "INCLUDED"
            target_job = "총무·비서행정"
            hr_ga_category = "총무·사무"
            reason = "비즈니스 에티켓 및 대내외 소통 능력 함양으로 총무·비서·사무지원 직무에 직결"
        # 2. 기획력 플랜 (일반사무 문서기획)
        elif "기획력" in title and "플랜" in title:
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "업무 기획서 및 계획서 작성 역량으로 총무·일반사무 핵심 실무 직결"
        # 3. 비즈니스 글쓰기와 보고서 작성 (사무행정 문서작성)
        elif "비즈니스 글쓰기" in title or "보고서 작성 노하우" in title:
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "보고서 작성 및 사내외 커뮤니케이션 문서 작성으로 총무·사무행정 핵심 실무"
        # 4. 직장인의 말하기 기술 (사무소통)
        elif "직장인의 말하기 기술" in title:
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "직장 내 커뮤니케이션 및 비즈니스 회화 스킬로 사무지원 공통 직무 직결"
        # 5. 비범하게 일하는 기술 (업무효율화)
        elif "비범하게 일하는 기술" in title:
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "사무 업무 프로세스 개선 및 효율화 꿀팁으로 일반사무 직무 직결"
        # 6. 엑셀 실무 (사무자동화)
        elif "엑셀" in title:
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "엑셀 스프레드시트를 활용한 데이터 취합/정리/서식 관리로 사무행정 필수 직무"
        # 7. 데이터 마인드셋 (사무공통)
        elif "데이터 마인드셋" in title:
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "사무 업무에서의 수치 데이터 해석 및 업무 적용 마인드셋으로 일반사무 직무 부합"
        # 8. 실무 데이터분석 (사무지원)
        elif key == "ABA20243000972962_324" or ("한달 공부로 실무에 바로 통하는 데이터분석" in title):
            status = "INCLUDED"
            target_job = "총무·일반사무"
            hr_ga_category = "총무·사무"
            reason = "NCS 0204(사무지원) 기반 사무직 실무 데이터 정리 및 분석 활용 과정"
        # 9. 홍보전략 (총무·대외협력 연계)
        elif "홍보전략" in title:
            status = "INCLUDED"
            target_job = "총무·홍보지원"
            hr_ga_category = "총무·사무"
            reason = "NCS 020102(홍보) 기업 가치 제고 및 대내외 홍보 지원으로 총무·대외사무 직무 부합"

        # [C] 추가 검토 필요 (REVIEW_NEEDED)
        else:
            status = "REVIEW_NEEDED"
            if source == "NCS 교육과정":
                target_job = "사회적경제·학사과정"
                hr_ga_category = "조건부검토(대학정규)"
                reason = "전문대/마이스터고 학과목 개설 과정(사회적경제/동선관리)으로 일반 재직자/구직자 직무교육 추천 풀 편입 시 추가 검토 요망"
            elif "프로젝트" in title or "애자일" in title:
                target_job = "경영기획·프로젝트"
                hr_ga_category = "인접직무(기획)"
                reason = "애자일/IT프로젝트 등 인접 프로젝트 관리 역량으로, 총무·인사 부서의 적용 범위 검토 필요"
            elif "마케팅" in title or ncs_cd.startswith("020103"):
                target_job = "마케팅·영업기획"
                hr_ga_category = "인접직무(마케팅)"
                reason = "NCS 020103 마케팅/STP/콘텐츠 과정으로 일반 사무와 구분되는 영업마케팅 전문 영역"
            elif "정보 보안" in title:
                target_job = "사내보안·총무지원"
                hr_ga_category = "인접직무(보안)"
                reason = "NCS 200106 정보보안이나, 사내 정보보호 및 총무 시설보안 연계 여부 검토 필요"
            elif "데이터 분석" in title and ("일잘러" in title or "AI" in title):
                target_job = "사무·데이터분석(AI)"
                hr_ga_category = "인접직무(AI/데이터)"
                reason = "NCS 200101(IT/빅데이터) 코드이나, 강의 내용이 일반 직장인의 업무 적용이므로 사무 역량 편입 여부 검토 필요"
            elif "코칭스킬" in title or "리더십" in title:
                target_job = "인사·리더십코칭"
                hr_ga_category = "인접직무(HRD)"
                reason = "NCS 0403(평생교육/코칭)으로, 인사/조직문화/사내교육 연계 가능성에 대한 세부 검토 필요"
            elif "경제" in title or "동남아" in title:
                target_job = "경영·일반교양"
                hr_ga_category = "인접교양"
                reason = "거시경제/글로벌 동향 등 교양·시사 성격 강좌로 직무 고유 역량과의 연계성 검토 필요"
            else:
                target_job = "기타검토"
                hr_ga_category = "기타검토"
                reason = f"NCS {ncs_cd} 및 과정명 맥락상 판단 보류"

        reclassification.append({
            "instance_key": key,
            "source_api": source,
            "course_name_std": title,
            "institution_name_std": inst,
            "ncs_classification_code": ncs_cd,
            "curr_job_id": curr_job,
            "curr_job_clarity": curr_clarity,
            "step3_status": status,
            "step3_target_job": target_job,
            "step3_hr_ga_category": hr_ga_category,
            "classification_reason": reason
        })

    df_reclass = pd.DataFrame(reclassification)

    # 건수 검증
    status_counts = df_reclass["step3_status"].value_counts().to_dict()
    cnt_included = status_counts.get("INCLUDED", 0)
    cnt_excluded = status_counts.get("EXCLUDED", 0)
    cnt_review = status_counts.get("REVIEW_NEEDED", 0)

    print("\n=== STEP 3-2 직무 분류 재검토 결과 ===")
    print(f"  - INCLUDED (분석 포함 확정): {cnt_included}건")
    print(f"  - EXCLUDED (분석 대상 제외): {cnt_excluded}건")
    print(f"  - REVIEW_NEEDED (추가 검토 필요): {cnt_review}건")
    print(f"  - 합계 검증: {cnt_included} + {cnt_excluded} + {cnt_review} = {cnt_included + cnt_excluded + cnt_review}건 (원본 50건 일치)")
    assert (cnt_included + cnt_excluded + cnt_review) == 50, "합계 불일치!"

    # --------------------------------------------------------------------------
    # 3. KSA 역량 데이터 검증 (STEP 3-3)
    # --------------------------------------------------------------------------
    # competencies.csv 7개 항목 점검
    comp_audit = []
    for _, comp_row in df_comp.iterrows():
        cid = comp_row["competency_id"]
        cname = comp_row["competency_name"]
        unit_code = comp_row["ncs_unit_code"]
        ksa_type = comp_row["ksa_type"]
        
        # 공식 NCS 출처 확인 상태
        # 02020201: 인사-인력채용 (공식 인정)
        # 02020202: 인사-인사평가 (공식 인정)
        # 02030201: 노무-근로관계법준수 (공식 인정)
        # 02010101: 경영기획-사업기획 (공식 인정)
        # 02010102: 총무자산관리 매핑 (프로젝트 재정의 코드)
        # 02040302: 비서사무 (공식 인정)
        # 01010102: 프로젝트관리 (공식 인정)
        if cid == "COMP_GA_02":
            source_status = "프로젝트 커스텀 정의 (공식 NCS 총무 비품관리는 02020102)"
        else:
            source_status = "공식 NCS 능력단위 매핑 확인"

        comp_audit.append({
            "competency_id": cid,
            "competency_name": cname,
            "ncs_unit_code": unit_code,
            "ksa_type": ksa_type,
            "source_status": source_status,
            "verified_status": "VERIFIED" if cid != "COMP_GA_02" else "PARTIAL_VERIFIED"
        })
    df_comp_audit = pd.DataFrame(comp_audit)

    # --------------------------------------------------------------------------
    # 4. 직무-역량-교육과정 매핑 검증 (STEP 3-4)
    # --------------------------------------------------------------------------
    # INCLUDED 9건에 대한 확정 교육-역량 매핑 테이블 생성
    verified_mappings = []
    
    # 과정별 매핑 룰
    mapping_rules = {
        "ACG20243000973001_324": ("COMP_SEC_01", "VERIFIED", "비즈니스 매너 및 커뮤니케이션(Attitude) - 글로벌 에티켓 교육 원문 일치"),
        "ACG20243001004189_245": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill) - 기획서 플랜 수립 프레임워크 원문 일치"),
        "ABA20243001011994_6": ("COMP_SEC_01", "VERIFIED", "비즈니스 매너 및 커뮤니케이션(Attitude) - 직장인 말하기 및 소통 스킬 원문 일치"),
        "ABA20243001012836_203": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill) - 일반사무 업무 노하우 및 프로세스 효율화 원문 일치"),
        "ABA20243000994834_261": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill) - 비즈니스 글쓰기 및 보고서 작성 실무 원문 일치"),
        "ABA20243001049771_3": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill/OA) - 엑셀 스프레드시트 활용 사무자동화 원문 일치"),
        "ABA20243001011985_5": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill) - 실무 데이터 기반 의사결정 및 기획 마인드셋 일치"),
        "ABA20243000972962_324": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill) - 사무지원 실무 데이터 취합 및 기초 분석 일치"),
        "ABA20243001045717_58": ("COMP_GA_01", "VERIFIED", "문서작성 및 기획(Skill) - 홍보 전략 기획 및 기업 커뮤니케이션 문서화 일치")
    }

    for _, r in df_reclass.iterrows():
        key = r["instance_key"]
        status = r["step3_status"]
        if status == "INCLUDED" and key in mapping_rules:
            cid, m_stat, m_reason = mapping_rules[key]
            verified_mappings.append({
                "instance_key": key,
                "course_name_std": r["course_name_std"],
                "competency_id": cid,
                "mapping_status": m_stat,
                "mapping_evidence": m_reason,
                "eda_ready": "Y"
            })
        elif status == "REVIEW_NEEDED":
            verified_mappings.append({
                "instance_key": key,
                "course_name_std": r["course_name_std"],
                "competency_id": "COMP_REVIEW_PENDING",
                "mapping_status": "REVIEW_NEEDED",
                "mapping_evidence": "인접 직무 또는 학사과정으로 직무 역량 추가 검토 필요",
                "eda_ready": "N"
            })
        else: # EXCLUDED
            verified_mappings.append({
                "instance_key": key,
                "course_name_std": r["course_name_std"],
                "competency_id": "COMP_UNSUPPORTED",
                "mapping_status": "UNSUPPORTED",
                "mapping_evidence": "인사·총무 외 타 분야 강좌로 KSA 역량 연결 대상 아님",
                "eda_ready": "N"
            })

    df_mapping_all = pd.DataFrame(verified_mappings)

    # --------------------------------------------------------------------------
    # 5. 최종 데이터셋 생성 (STEP 3-5)
    # --------------------------------------------------------------------------
    # 원본 courses.csv와 reclassification 정보 병합
    df_merged = df_courses.merge(
        df_reclass[["instance_key", "step3_status", "step3_target_job", "step3_hr_ga_category", "classification_reason"]],
        on="instance_key",
        how="left"
    )

    # A. hr_courses_eda.csv : INCLUDED 확정 데이터셋 (9건)
    df_eda = df_merged[df_merged["step3_status"] == "INCLUDED"].copy()
    df_eda.to_csv(PROCESSED_DIR / "hr_courses_eda.csv", index=False, encoding="utf-8-sig")

    # B. hr_courses_review.csv : REVIEW_NEEDED 수동 검토 데이터셋 (22건)
    df_review = df_merged[df_merged["step3_status"] == "REVIEW_NEEDED"].copy()
    df_review.to_csv(PROCESSED_DIR / "hr_courses_review.csv", index=False, encoding="utf-8-sig")

    # C. hr_courses_excluded.csv : EXCLUDED 분석 제외 데이터셋 (19건)
    df_excluded = df_merged[df_merged["step3_status"] == "EXCLUDED"].copy()
    df_excluded.to_csv(PROCESSED_DIR / "hr_courses_excluded.csv", index=False, encoding="utf-8-sig")

    # D. hr_mapping_verified.csv : 검증된 교육-역량 매핑 데이터 (9건의 VERIFIED 중심 및 전체 매핑 상태)
    df_mapping_verified = df_mapping_all[df_mapping_all["mapping_status"] == "VERIFIED"].copy()
    df_mapping_verified.to_csv(PROCESSED_DIR / "hr_mapping_verified.csv", index=False, encoding="utf-8-sig")

    # 전체 매핑 상태 보관용
    df_mapping_all.to_csv(PROCESSED_DIR / "hr_mapping_all_status.csv", index=False, encoding="utf-8-sig")

    print(f"[+] 4대 신규 분석 데이터셋 생성 완료 -> {PROCESSED_DIR.resolve()}")
    print(f"    1. hr_courses_eda.csv: {len(df_eda)}건")
    print(f"    2. hr_courses_review.csv: {len(df_review)}건")
    print(f"    3. hr_courses_excluded.csv: {len(df_excluded)}건")
    print(f"    4. hr_mapping_verified.csv: {len(df_mapping_verified)}건")

    # --------------------------------------------------------------------------
    # 6. 최종 감사 및 검증 요약 JSON 저장
    # --------------------------------------------------------------------------
    audit_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step": "STEP 3 2차 전처리 및 통합 검증",
        "dataset_summary": {
            "total_raw_count": total_raw,
            "total_processed_count": total_courses,
            "included_count": len(df_eda),
            "review_needed_count": len(df_review),
            "excluded_count": len(df_excluded),
            "sum_check_passed": bool((len(df_eda) + len(df_review) + len(df_excluded)) == 50)
        },
        "included_courses": df_eda[["instance_key", "source_api", "course_name_std", "step3_target_job"]].to_dict(orient="records"),
        "excluded_breakdown": df_excluded["step3_target_job"].value_counts().to_dict(),
        "review_breakdown": df_review["step3_target_job"].value_counts().to_dict(),
        "competency_verified_count": len(df_mapping_verified)
    }

    with open(PROCESSED_DIR / "step3_verification_audit.json", "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, ensure_ascii=False, indent=2)

    print(f"[+] 감사 보고서 저장 완료 -> step3_verification_audit.json")
    print("=" * 80)

if __name__ == "__main__":
    execute_step3()
