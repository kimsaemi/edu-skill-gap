"""
고객용 추천 흐름에 합성 리뷰·평점이 섞이지 않았는지 점검합니다.

- 합성 리뷰(48.2만 건, SYNTHETIC_UNVERIFIED)는 팀 분석용 화면에서만 사용합니다.
- 고객용 화면과 추천 점수에는 리뷰·평점을 쓰지 않습니다.

실행: python scripts/check_customer_no_synthetic_reviews.py
      (--runtime 옵션을 주면 실제 추천을 1회 실행해 결과 컬럼까지 확인합니다. 모델 로딩으로 느릴 수 있음)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 고객용 추천 흐름을 구성하는 소스 파일
CUSTOMER_FLOW_FILES = [
    ROOT / "customer_dashboard" / "streamlit_customer.py",
    ROOT / "customer_dashboard" / "app.py",
    ROOT / "src" / "assessment" / "recommendation_bridge.py",
    ROOT / "src" / "customer" / "career_platform.py",
    ROOT / "src" / "assessment" / "evaluator.py",
    ROOT / "src" / "recommendation" / "unified_hybrid_recommender.py",
]

# 합성 리뷰 데이터·모델 파일명과 평점 컬럼명
FORBIDDEN_PATTERNS = [
    r"reviews_integrated",
    r"course_review_summary",
    r"review_course_id_mapping",
    r"models_sentiment_classifiers",
    r"simulation_recommender",
    r"kfo_courses",
    r"average_rating",
    r"rating_score",
    r"sentiment",
]

# 결과 데이터프레임에 있으면 안 되는 컬럼
FORBIDDEN_COLUMNS = {"rating_score", "average_rating", "average_rating_calculated", "review_count", "sentiment_score"}


def check_sources() -> list:
    problems = []
    for path in CUSTOMER_FLOW_FILES:
        if not path.exists():
            problems.append(f"파일 없음: {path.relative_to(ROOT)}")
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pat in FORBIDDEN_PATTERNS:
                if re.search(pat, line, flags=re.IGNORECASE):
                    problems.append(f"{path.relative_to(ROOT)}:{lineno}: '{pat}' 참조 → {line.strip()[:100]}")
    return problems


def check_runtime() -> list:
    from src.recommendation.unified_hybrid_recommender import UnifiedHybridRecommender

    engine = UnifiedHybridRecommender()
    problems = []
    cases = [
        dict(query="급여 계산과 4대보험 실무", target_domain="인사", mode="general"),
        dict(target_domain="인사", competency_id="COMP_HR_01", mode="ksa"),
    ]
    for kwargs in cases:
        df, *_ = engine.recommend(top_n=5, **kwargs)
        bad = FORBIDDEN_COLUMNS & set(df.columns)
        if bad:
            problems.append(f"recommend({kwargs}) 결과에 평점 컬럼 포함: {sorted(bad)}")
    return problems


def main() -> int:
    problems = check_sources()
    if "--runtime" in sys.argv:
        problems += check_runtime()

    if problems:
        print("[FAIL] 고객용 추천 흐름에서 리뷰·평점 참조가 발견되었습니다:")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"[PASS] 고객용 추천 흐름 {len(CUSTOMER_FLOW_FILES)}개 파일에 합성 리뷰·평점 참조가 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
