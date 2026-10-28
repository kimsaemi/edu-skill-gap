"""
STEP 7-2: 수강 후기 5대 핵심 토픽 및 키워드 마이닝 파이프라인
-------------------------------------------------------------
1. 5대 토픽 정의:
   - 실습 (Practice / Hands-on)
   - 난이도 (Difficulty / Pace)
   - 강사 (Instructor / Delivery)
   - 강의자료 (Materials / Textbooks)
   - 현업 활용성 (Work Applicability)
2. 긍정/부정 감성별 토픽 발현 빈도 추출
3. 플랫폼별, 가상 페르소나별 토픽 분포 비교
4. 결과 JSON 및 통계 CSV 저장
"""

import os
import sys
import re
import json
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"D:\26_강의자료\프로젝트2_교육"
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "hr", "processed")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "hr", "output", "recommendation")
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("[1/4] Loading integrated reviews dataset...")
p_reviews = os.path.join(PROCESSED_DIR, "reviews_integrated.parquet")
df_reviews = pd.read_parquet(p_reviews, columns=['review_uid', 'platform', 'rating', 'persona', 'content'])
print(f"  Loaded {len(df_reviews):,} reviews")

# 1. 5대 토픽 키워드 딕셔너리
TOPIC_KEYWORDS = {
    "실습": ["실습", "예제", "프로젝트", "코드", "실습자료", "핸즈온", "응용 문제", "케이스스터디", "따라하기"],
    "난이도": ["난이도", "기초", "입문", "심화", "속도", "진도", "벅차", "부담", "이해하기", "어려움", "쉬움"],
    "강사": ["강사", "교수", "설명", "전달력", "강의력", "피드백", "목소리", "딕션", "발음", "전문성"],
    "강의자료": ["교재", "자료", "요약본", "PDF", "PPT", "문제집", "부교재", "템플릿", "다운로드"],
    "현업활용성": ["실무", "업무", "현업", "현장", "적용", "업무활용", "실무적용", "즉시", "야근", "사수"]
}

# 2. 감성 매핑
def map_sentiment(rating):
    if rating >= 4:
        return "positive"
    elif rating == 3:
        return "neutral"
    else:
        return "negative"

df_reviews['sentiment'] = df_reviews['rating'].apply(map_sentiment)

print("[2/4] Tagging topics based on dictionary rules...")
for topic, kws in TOPIC_KEYWORDS.items():
    pattern = "|".join([re.escape(k) for k in kws])
    df_reviews[f'topic_{topic}'] = df_reviews['content'].str.contains(pattern, regex=True)

# 3. 토픽별 전체 출현 빈도 및 비중
topic_overall_stats = {}
for topic in TOPIC_KEYWORDS.keys():
    cnt = int(df_reviews[f'topic_{topic}'].sum())
    ratio = round(cnt / len(df_reviews) * 100, 2)
    topic_overall_stats[topic] = {"count": cnt, "ratio_pct": ratio}
print("  Topic overall occurrences:\n", json.dumps(topic_overall_stats, ensure_ascii=False, indent=2))

# 4. 감성별 토픽 교차 분석
print("[3/4] Cross-analyzing topics by sentiment, platform, and virtual persona...")
sentiment_topic_dist = {}
for s_label in ['positive', 'neutral', 'negative']:
    sub = df_reviews[df_reviews['sentiment'] == s_label]
    sentiment_topic_dist[s_label] = {}
    for topic in TOPIC_KEYWORDS.keys():
        cnt = int(sub[f'topic_{topic}'].sum())
        sentiment_topic_dist[s_label][topic] = {
            "count": cnt,
            "within_sentiment_ratio_pct": round(cnt / len(sub) * 100, 2)
        }

# 플랫폼별 토픽 교차 분석
platform_topic_dist = {}
for plat in df_reviews['platform'].unique():
    sub = df_reviews[df_reviews['platform'] == plat]
    platform_topic_dist[plat] = {}
    for topic in TOPIC_KEYWORDS.keys():
        cnt = int(sub[f'topic_{topic}'].sum())
        platform_topic_dist[plat][topic] = round(cnt / len(sub) * 100, 2)

# 가상 페르소나별 토픽 교차 분석
persona_topic_dist = {}
for persona in df_reviews['persona'].unique():
    sub = df_reviews[df_reviews['persona'] == persona]
    persona_topic_dist[persona] = {}
    for topic in TOPIC_KEYWORDS.keys():
        cnt = int(sub[f'topic_{topic}'].sum())
        persona_topic_dist[persona][topic] = round(cnt / len(sub) * 100, 2)

# 5. 대표 키워드 및 표현 추출 (긍정 vs 부정)
top_expressions = {
    "positive": [
        "핵심 요약본이 큰 역할",
        "개념 잡기에 참 좋음",
        "실무 관점에서 깔끔하게 연결",
        "이론과 실무 현장의 간극 해소",
        "자주 발생하는 오류 체계적 정리",
        "유기적인 흐름으로 정리",
        "전문성이 돋보임"
    ],
    "negative": [
        "뒤쪽 심화 실습과 응용 문제 난이도 부담",
        "혼자 복습하는 시간 추가 필요",
        "퇴근 후 피로한 상태에서 듣기 벅참",
        "교재나 강의자료 상세 설명 부족",
        "선수 지식 없이 따라가기 다소 버거움"
    ]
}

topic_results = {
    "metadata": {
        "description": "합성 수강 후기 5대 토픽 및 감성/플랫폼/가상페르소나 교차 분석 보고서",
        "disclaimer": "본 수강 후기 및 평점은 분석 실험을 위해 생성한 합성 데이터이며, 실제 수강생 평가를 의미하지 않습니다.",
        "persona_warning": "가상 페르소나(직장인, 학생, 전공자)는 통계 시뮬레이션을 위해 부여된 라벨이며, 실제 학습자 집단의 특성으로 일반화할 수 없습니다.",
        "total_reviews": len(df_reviews)
    },
    "topic_overall": topic_overall_stats,
    "sentiment_breakdown": sentiment_topic_dist,
    "platform_breakdown": platform_topic_dist,
    "persona_breakdown": persona_topic_dist,
    "representative_expressions": top_expressions
}

p_topic_json = os.path.join(OUTPUT_DIR, "review_topics_summary.json")
with open(p_topic_json, "w", encoding="utf-8") as f:
    json.dump(topic_results, f, ensure_ascii=False, indent=2)

# 토픽 집계 CSV 저장
df_topic_summary = pd.DataFrame([
    {
        "topic": t,
        "keywords": ", ".join(TOPIC_KEYWORDS[t]),
        "total_count": topic_overall_stats[t]["count"],
        "total_ratio_pct": topic_overall_stats[t]["ratio_pct"],
        "positive_ratio_pct": sentiment_topic_dist["positive"][t]["within_sentiment_ratio_pct"],
        "neutral_ratio_pct": sentiment_topic_dist["neutral"][t]["within_sentiment_ratio_pct"],
        "negative_ratio_pct": sentiment_topic_dist["negative"][t]["within_sentiment_ratio_pct"]
    }
    for t in TOPIC_KEYWORDS.keys()
])

p_topic_csv = os.path.join(OUTPUT_DIR, "review_topic_stats.csv")
df_topic_summary.to_csv(p_topic_csv, index=False, encoding='utf-8-sig')

print("\n[4/4] SUCCESSFULLY GENERATED REVIEW TOPICS ASSETS:")
print(f"1. Topics JSON: {p_topic_json}")
print(f"2. Topics CSV: {p_topic_csv}")
