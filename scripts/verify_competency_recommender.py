"""
STEP 5-4: NCS·KSA 직무역량 기반 맞춤 교육 추천 엔진 자동 검증 스크립트
- 12대 현실 실무 시나리오 전수 실행 및 품질 감사
- 산출물: data/hr/reports/competency_recommendation_scenarios.csv
"""

import sys
import json
import time
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.recommendation.competency_recommender import CompetencyRecommender, KSA_COMPETENCIES_MASTER

def run_scenarios_audit():
    print("=" * 80)
    print("STEP 5-4: 직무역량 기반 맞춤 추천 12대 시나리오 자동 검증 시작")
    print("=" * 80)

    t0 = time.time()
    recommender = CompetencyRecommender()
    print(f"추천 엔진 로드 완료 ({time.time() - t0:.2f}초)")

    TEST_SCENARIOS = [
        {
            "id": "SC_01",
            "name": "신입 인사담당자의 채용·온보딩",
            "job_family": "인사",
            "competency_id": "COMP_HR_01",
            "user_level": "입문",
            "duration_type": "전체",
            "max_budget": "전체",
            "edu_type": "온라인",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_02",
            "name": "인사 실무자의 근로기준법 및 노무관리",
            "job_family": "인사",
            "competency_id": "COMP_LABOR_01",
            "user_level": "실무",
            "duration_type": "전체",
            "max_budget": 500000,
            "edu_type": "전체",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_03",
            "name": "인사 관리자의 성과평가·보상체계 설계",
            "job_family": "인사",
            "competency_id": "COMP_HR_02",
            "user_level": "관리자·심화",
            "duration_type": "중기 (10~40시간)",
            "max_budget": "전체",
            "edu_type": "오프라인",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_04",
            "name": "신임 총무담당자의 자산·비품 관리 (무료 온라인)",
            "job_family": "총무",
            "competency_id": "COMP_GA_02",
            "user_level": "입문",
            "duration_type": "전체",
            "max_budget": 0,
            "edu_type": "온라인",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_05",
            "name": "총무담당자의 공문서 및 기획서 작성 실무 (단기 집중)",
            "job_family": "총무",
            "competency_id": "COMP_GA_01",
            "user_level": "실무",
            "duration_type": "단기 (<10시간)",
            "max_budget": "전체",
            "edu_type": "전체",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_06",
            "name": "경영지원 담당자의 사업계획 및 재무회계 기초 (예산 100만 이하)",
            "job_family": "경영지원",
            "competency_id": "COMP_MGMT_02",
            "user_level": "실무",
            "duration_type": "전체",
            "max_budget": 1000000,
            "edu_type": "전체",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_07",
            "name": "경영지원 담당자의 프로젝트 및 조직관리",
            "job_family": "경영지원",
            "competency_id": "COMP_MGMT_01",
            "user_level": "실무",
            "duration_type": "전체",
            "max_budget": "전체",
            "edu_type": "온라인",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_08",
            "name": "신입사원 비즈니스 매너 및 커뮤니케이션 (무료)",
            "job_family": "경영지원",
            "competency_id": "COMP_SEC_01",
            "user_level": "입문",
            "duration_type": "전체",
            "max_budget": 0,
            "edu_type": "온라인",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_09",
            "name": "총무/자산관리 입문 + KPC/KMA 기관 지정 오프라인",
            "job_family": "총무",
            "competency_id": "COMP_GA_02",
            "user_level": "입문",
            "duration_type": "전체",
            "max_budget": 1000000,
            "edu_type": "오프라인",
            "platforms": ["한국생산성본부(KPC)", "한국능률협회(KMA)"],
            "top_n": 5
        },
        {
            "id": "SC_10",
            "name": "인사담당자 노무관리 핵심 단기 집중과정",
            "job_family": "인사",
            "competency_id": "COMP_LABOR_01",
            "user_level": "실무",
            "duration_type": "단기 (<10시간)",
            "max_budget": "전체",
            "edu_type": "전체",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_11",
            "name": "총무 비품관리 (오매핑 109건 IT 코딩 과정 차단 집중 검증)",
            "job_family": "총무",
            "competency_id": "COMP_GA_02",
            "user_level": "실무",
            "duration_type": "전체",
            "max_budget": "전체",
            "edu_type": "전체",
            "platforms": None,
            "top_n": 5
        },
        {
            "id": "SC_12",
            "name": "필터 결과가 0건인 극단 조건 (GSEEK 오프라인 ➔ 0건 안내 검증)",
            "job_family": "인사",
            "competency_id": "COMP_HR_01",
            "user_level": "실무",
            "duration_type": "전체",
            "max_budget": "전체",
            "edu_type": "오프라인",
            "platforms": ["GSEEK"],
            "top_n": 5
        }
    ]

    all_scenario_results = []
    summary_rows = []

    for sc in TEST_SCENARIOS:
        sc_id = sc["id"]
        sc_name = sc["name"]
        
        top_df, n_candidates, msg = recommender.recommend(
            job_family=sc["job_family"],
            competency_id=sc["competency_id"],
            user_level=sc["user_level"],
            duration_type=sc["duration_type"],
            max_budget=sc["max_budget"],
            edu_type=sc["edu_type"],
            platforms=sc["platforms"],
            top_n=sc["top_n"]
        )

        n_returned = len(top_df)
        violations = 0
        violation_details = []

        # 감사 1: 극단 조건 0건 처리 검증
        if sc_id == "SC_12":
            if n_returned != 0:
                violations += 1
                violation_details.append(f"0건 조건에서 {n_returned}건 억지 반환됨")
        else:
            if n_returned == 0 and n_candidates > 0:
                violations += 1
                violation_details.append("후보가 있음에도 반환 0건")

        # 감사 2: 반환 강좌 조건 일치 여부 감사
        if n_returned > 0:
            for _, row in top_df.iterrows():
                # 플랫폼 위반 검사
                if sc["platforms"] and row["provider"] not in sc["platforms"]:
                    violations += 1
                    violation_details.append(f"플랫폼 위반: {row['provider']}")

                # 예산 위반 검사
                if sc["max_budget"] == 0:
                    if row["price_display"] != "무료":
                        violations += 1
                        violation_details.append(f"무료 위반: {row['price_display']}")
                elif sc["max_budget"] != "전체" and sc["max_budget"] is not None:
                    # 유료 강좌 금액 파싱
                    price_val = recommender.df_courses.loc[
                        recommender.df_courses['course_uid'] == row['course_uid'], 'numeric_price'
                    ].values[0]
                    if pd.notna(price_val) and price_val > sc["max_budget"]:
                        violations += 1
                        violation_details.append(f"예산 초과: {price_val}원 > {sc['max_budget']}원")

                # 교육 형태 위반 검사
                if sc["edu_type"] == "온라인":
                    if not any(k in row["education_type"] for k in ["온라인", "사이버", "원격", "플립"]):
                        violations += 1
                        violation_details.append(f"온라인 형태 위반: {row['education_type']}")
                elif sc["edu_type"] == "오프라인":
                    if not any(k in row["education_type"] for k in ["오프라인", "집체", "현장"]):
                        violations += 1
                        violation_details.append(f"오프라인 형태 위반: {row['education_type']}")

                # 109건 오매핑 누출 감사
                if row["course_uid"] in recommender.mismatch_109_uids:
                    violations += 1
                    violation_details.append(f"109건 오매핑 의심 강좌 누출: {row['title']}")

                # 중복 감사
                # (top_df 내부 고유성)
            dup_cnt = top_df['title'].duplicated().sum()
            if dup_cnt > 0:
                violations += dup_cnt
                violation_details.append(f"동일 제목 중복 강좌 {dup_cnt}건 검출")

        status = "PASS" if violations == 0 else "FAIL"
        top1_title = top_df['title'].iloc[0] if n_returned > 0 else "N/A (0건 정상 반환)"
        top1_score = top_df['final_score'].iloc[0] if n_returned > 0 else 0.0

        print(f"[{sc_id}] {sc_name}")
        print(f"  - 후보군: {n_candidates:,}건 | 반환: {n_returned}건 | 위반: {violations}건 ➔ 판정: {status}")
        if n_returned > 0:
            print(f"  - Top 1: ({top_df['provider'].iloc[0]}) {top1_title} ({top1_score}점)")
            print(f"    추천 사유: {top_df['recommendation_reason'].iloc[0]}")
        else:
            print(f"  - 안내 메시지: {msg}")

        summary_rows.append({
            "scenario_id": sc_id,
            "scenario_name": sc_name,
            "job_family": sc["job_family"],
            "competency_name": KSA_COMPETENCIES_MASTER[sc["competency_id"]]["name"],
            "user_level": sc["user_level"],
            "candidate_count": n_candidates,
            "returned_count": n_returned,
            "violations_count": violations,
            "status": status,
            "top1_title": top1_title,
            "top1_score": top1_score,
            "notes": " / ".join(violation_details) if violation_details else "전수 조건 및 추천 품질 통과"
        })

        if n_returned > 0:
            top_df_export = top_df.copy()
            top_df_export["scenario_id"] = sc_id
            top_df_export["scenario_name"] = sc_name
            all_scenario_results.append(top_df_export)

    # 1. 시나리오 요약 결과 저장
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(WORKSPACE_ROOT / "data" / "hr" / "reports" / "competency_recommendation_scenarios.csv", index=False, encoding="utf-8-sig")

    # 2. 전체 반환 강좌 상세 목록 저장
    if all_scenario_results:
        df_all_results = pd.concat(all_scenario_results, ignore_index=True)
        df_all_results.to_csv(WORKSPACE_ROOT / "data" / "hr" / "output" / "recommendation" / "competency_recommendation_all_results.csv", index=False, encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print(f"전체 12개 시나리오 자동 검증 완료! (총 소요 시간: {time.time() - t0:.2f}초)")
    pass_cnt = (df_summary['status'] == 'PASS').sum()
    print(f" - 검증 결과: {pass_cnt} / {len(df_summary)} 시나리오 PASS (합격률: {pass_cnt/len(df_summary)*100:.1f}%)")
    print(f" - CSV 저장 완료: data/hr/reports/competency_recommendation_scenarios.csv")
    print("=" * 80)

if __name__ == '__main__':
    run_scenarios_audit()
