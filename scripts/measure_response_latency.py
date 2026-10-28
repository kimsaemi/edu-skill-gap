"""
scripts/measure_response_latency.py
Customer MVP 성능 측정 벤치마크 스크립트
측정 단계:
1. 첫 접속 (First Access / Streamlit 서버 가동 및 세션 초기화)
2. 모델 초기화 (Cold Start / SentenceTransformer 모델 가중치 및 코퍼스/임베딩 로드)
3. 첫 추천 (First Query / 질의 인코딩 + 시맨틱 유사도 + BM25 + KSA 매핑 + 필터링)
4. 반복 추천 (Warm Cache / 동일 질의 재추천 캐시 및 기로드 모델 추론)
"""
import time
import sys
from pathlib import Path
import numpy as np
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_latency_benchmark():
    results = []

    print("=" * 80)
    print("[Customer MVP Latency Benchmark]")
    print("=" * 80)

    # 1. 첫 접속 (First Access / Import 및 정적 리소스 로드)
    t0 = time.perf_counter()
    from src.assessment.evaluator import calculate_competency_scores, AssessmentEvaluationResult
    from src.assessment.recommendation_bridge import RecommendationFilterParams
    t_first_access = (time.perf_counter() - t0) * 1000
    results.append({
        "stage": "1. 첫 접속 (First Access)",
        "metric": "기본 모듈 import 및 평가기 초기화",
        "target_sla": "< 500 ms (미검증 목표)",
        "measured_ms": f"{t_first_access:.1f} ms",
        "raw_ms": t_first_access
    })
    print(f"[1] 첫 접속 (First Access): {t_first_access:.1f} ms")

    # 2. 모델 초기화 (Cold Start / SentenceTransformer 및 코퍼스/임베딩 로드)
    t0 = time.perf_counter()
    from src.assessment.recommendation_bridge import get_shared_recommender
    engine = get_shared_recommender()
    t_cold_start = (time.perf_counter() - t0) * 1000
    results.append({
        "stage": "2. 모델 초기화 (Cold Start)",
        "metric": "Ko-SRoBERTa 가중치 로드 + 8,645건 코퍼스/임베딩 메모리 적재",
        "target_sla": "< 2,000 ms (미검증 목표 SLA)",
        "measured_ms": f"{t_cold_start:.1f} ms",
        "raw_ms": t_cold_start
    })
    print(f"[2] 모델 초기화 (Cold Start): {t_cold_start:.1f} ms")

    # 3. 첫 추천 (First Query)
    eval_res = calculate_competency_scores(
        job_family="인사",
        responses={"Q_HR_01": 2, "Q_HR_02": 2, "Q_HR_03": 2, "Q_HR_04": 4, "Q_HR_05": 4, "Q_HR_06": 4, "Q_HR_07": 4, "Q_HR_08": 4, "Q_HR_09": 4},
        learning_goal="구조화 면접 질문 설계 및 선발 역량 보완"
    )
    filter_params = RecommendationFilterParams(
        price_filter="ALL",
        edu_type="ALL",
        weekly_hours=4.0
    )

    t0 = time.perf_counter()
    from src.assessment.recommendation_bridge import get_recommendations_for_assessment
    bundle_1 = get_recommendations_for_assessment(eval_res, filter_params, recommender=engine)
    t_first_query = (time.perf_counter() - t0) * 1000
    results.append({
        "stage": "3. 첫 추천 (First Query)",
        "metric": "질의 Ko-SRoBERTa 인코딩 + 시맨틱 내적 + BM25 + KSA 랭킹",
        "target_sla": "< 500 ms (미검증 목표)",
        "measured_ms": f"{t_first_query:.1f} ms",
        "raw_ms": t_first_query
    })
    print(f"[3] First Query: {t_first_query:.1f} ms ({len(bundle_1.all_courses_deduped)} courses)")

    # 4. 반복 추천 (Warm Cache / 후속 추천)
    t0 = time.perf_counter()
    bundle_2 = get_recommendations_for_assessment(eval_res, filter_params, recommender=engine)
    t_warm_query = (time.perf_counter() - t0) * 1000
    results.append({
        "stage": "4. 반복 추천 (Warm Cache)",
        "metric": "기로드 모델 및 메모리 캐시 기반 후속/반복 추천",
        "target_sla": "< 200 ms (미검증 목표)",
        "measured_ms": f"{t_warm_query:.1f} ms",
        "raw_ms": t_warm_query
    })
    print(f"[4] Warm Cache Query: {t_warm_query:.1f} ms ({len(bundle_2.all_courses_deduped)} courses)")

    print("=" * 80)
    print("Latency Benchmark Results Table")
    print("=" * 80)
    df_res = pd.DataFrame(results)[["stage", "metric", "target_sla", "measured_ms"]]
    print(df_res.to_string(index=False))

    out_csv = WORKSPACE_ROOT / "data" / "hr" / "reports" / "latency_benchmark_results.csv"
    df_res.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {out_csv}")

    return results

if __name__ == "__main__":
    run_latency_benchmark()
