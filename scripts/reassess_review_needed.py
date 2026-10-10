"""Step B: Detailed Reassessment of the 22 REVIEW_NEEDED Courses.
Generates data/hr/output/reports/review_reassessment.csv.
"""
import json
import os
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(".")
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"
OUTPUT_DIR = BASE_DIR / "data" / "hr" / "output" / "reports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def reassess_22_reviews():
    df_review = pd.read_csv(PROCESSED_DIR / "hr_courses_review.csv", dtype=str)
    print(f"Total review-needed courses to reassess: {len(df_review)}")

    reassessment_rows = []

    for idx, r in df_review.iterrows():
        key = r["instance_key"]
        source = r["source_api"]
        title = r["course_name_std"]
        inst = r["institution_name_std"]
        ncs_cd = r["ncs_classification_code"]
        prev_reason = r["classification_reason"]
        
        new_status = "REVIEW_NEEDED"
        reassess_reason = ""
        mapped_comp = "미매핑"

        # 1. 전문 마케팅 강좌 (3건) -> 인사·총무 직무 범위 외로 EXCLUDED 재분류
        if "마케팅" in title:
            new_status = "EXCLUDED"
            reassess_reason = "SNS/블로그/콘텐츠 마케팅 전문 실무 강좌로, 일반 사무/총무/인사 직무와 구분되는 영업마케팅 영역임"
        # 2. 일반 시사교양/생활경제 (3건) -> 직무 전문 역량 외로 EXCLUDED 재분류
        elif title in ["한국경제의미래", "돈 공부의 첫 걸음, 박정호의 의식주 경제", "포스트 차이나 시대-동남아에서 미래를 찾다!"]:
            new_status = "EXCLUDED"
            reassess_reason = "거시경제/해외지역학/생활경제 등 교양·시사 교양 성격으로 기업 직무역량 교육으로 부적합"
        # 3. 사내 정보보안 (1건) -> 전사 총무/보안 규정 교육으로 INCLUDED 편입
        elif "사내 정보 보안" in title:
            new_status = "INCLUDED"
            reassess_reason = "기업 임직원의 사내 정보보호, 보안 규정 준수 및 총무 자산보호 실무와 직결됨"
            mapped_comp = "COMP_GA_01"  # 사무행정 규정 및 문서관리 연계
        # 4. 애자일 프로젝트 실무(입문) (1건) -> COMP_MGMT_01 매핑 가능하여 INCLUDED 편입
        elif "애자일 프로젝트 실무" in title:
            new_status = "INCLUDED"
            reassess_reason = "기존 7대 핵심 역량 중 COMP_MGMT_01(애자일 프로젝트 관리)에 정확히 부합하는 실무 입문 교육임"
            mapped_comp = "COMP_MGMT_01"
        # 5. 리더십 및 코칭스킬 (1건) -> 인사/조직문화 연계 검토 (INCLUDED 편입)
        elif "코칭스킬" in title:
            new_status = "INCLUDED"
            reassess_reason = "조직 내 커리어 관리, 코칭 스킬 및 리더십 함양 교육으로 인사(HRD) 및 조직관리 직무에 부합"
            mapped_comp = "COMP_HR_02"  # 인사평가/코칭 연계
        # 6. AI 시대 일잘러 데이터분석 (2건) -> 사무행정 데이터 활용 (INCLUDED 편입)
        elif "일잘러의 필수 역량! 데이터 분석" in title:
            new_status = "INCLUDED"
            reassess_reason = "일반 직장인의 실무 데이터 취합/분석 및 사무 프로세스 적용 교육으로 일반사무 역량에 부합"
            mapped_comp = "COMP_GA_01"
        # 7. 일잘러를 위한 IT 프로젝트 (1건) -> REVIEW_NEEDED 유지
        elif "IT 프로젝트" in title:
            new_status = "REVIEW_NEEDED"
            reassess_reason = "IT 개발 부서와의 협업 프로젝트 관리로 일반 총무/인사 범위와의 연계성 추가 검토 필요"
        # 8. 대학 학사과정 (10건) -> REVIEW_NEEDED 유지
        elif source == "NCS 교육과정":
            new_status = "REVIEW_NEEDED"
            reassess_reason = "전문대/마이스터고 학과목 개설 정규 학사 교과목(사회적경제/동선관리)으로 일반 재직자/구직자 직무교육 추천 풀 편입 시 신중 검토 요망"
        else:
            new_status = "REVIEW_NEEDED"
            reassess_reason = "추가 확인 필요"

        reassessment_rows.append({
            "instance_key": key,
            "source_api": source,
            "course_name_std": title,
            "institution_name_std": inst,
            "ncs_classification_code": ncs_cd,
            "prev_status": "REVIEW_NEEDED",
            "prev_reason": prev_reason,
            "reassessed_status": new_status,
            "reassessed_reason": reassess_reason,
            "mapped_competency_id": mapped_comp
        })

    df_out = pd.DataFrame(reassessment_rows)
    out_file = OUTPUT_DIR / "review_reassessment.csv"
    df_out.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"[+] Reassessment saved to {out_file}")
    print("\n[Reassessment Summary]")
    print(df_out["reassessed_status"].value_counts())
    return df_out

if __name__ == "__main__":
    reassess_22_reviews()
