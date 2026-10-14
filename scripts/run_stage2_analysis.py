"""
STEP 2 | 교육과정 텍스트 분석, 키워드 추출, 군집화 및 BM25 구축 스크립트
- 입력: data/processed/hr_courses_detailed_295.csv
- 처리: 
    1. 템플릿 커리큘럼 및 기관 홍보 문구 정제
    2. kiwipiepy 한국어 형태소 분석 + 복합명사 + 사용자 정의 도메인 사전
    3. TF-IDF 어휘 사전 구축 및 Top 20 대표 키워드 추출
    4. 개별 강좌별 Top 5 대표 키워드 태그 생성
    5. K-Means 군집화 (k=8) 및 클러스터별 대표 주제 요약
    6. BM25 검색 모델 구축 검증
- 출력: data/hr/output/text_analysis/
"""

import io
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import silhouette_score

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 1. 데이터 로드
data_path = Path("data/processed/hr_courses_detailed_295.csv")
courses_raw = pd.read_csv(data_path)
print(f"[1/6] 데이터 로드 완료: {len(courses_raw)}개 과정")

# 2. 텍스트 정제
template_marker = "핵심 프로세스 실습 // 실무 서식 작성"
boilerplate_min_titles = 3


def strip_session_suffix(title):
    return re.sub(r"\s*\([^()]*(\([^()]*\))?[^()]*\d+회차\)\s*$", "", title).strip()


def split_segments(text):
    parts = re.split(r"\s*(?:■|※|▶|●|◆|•|\[|\]|\s-\s|\d+\.\s|[.!?]\s)\s*", str(text))
    return [p.strip() for p in parts if len(p.strip()) >= 8]


courses = courses_raw.copy()
courses["base_title"] = courses["course_title"].map(strip_session_suffix)
courses["is_template_syllabus"] = courses["syllabus_text"].str.contains(template_marker, regex=False)

segment_titles = {}
for _title, _overview in zip(courses["base_title"], courses["overview"]):
    for _seg in set(split_segments(_overview)):
        segment_titles.setdefault(_seg, set()).add(_title)
boilerplate_segments = {s for s, t in segment_titles.items() if len(t) >= boilerplate_min_titles}


def clean_overview(text):
    return " ".join(s for s in split_segments(text) if s not in boilerplate_segments)


def clean_syllabus(text, is_template):
    if is_template:
        return ""
    text = re.sub(r"총시간\s*\(\s*\d+\s*시간\s*\)", " ", text)
    return re.sub(r"\(\s*\d+\s*시간\s*\)", " ", text).strip()


courses["overview_clean"] = courses["overview"].map(clean_overview)
courses["syllabus_clean"] = [
    clean_syllabus(t, f) for t, f in zip(courses["syllabus_text"], courses["is_template_syllabus"])
]
courses["doc"] = (
    (courses["base_title"] + " ") * 2 + courses["overview_clean"] + " " + courses["syllabus_clean"]
)
print(f"[2/6] 텍스트 정제 완료 (홍보성 상용구 {len(boilerplate_segments)}종 제거)")

# 3. 형태소 분석 (Kiwi)
kiwi = Kiwi()
hr_user_words = [
    "통상임금", "4대보험", "연말정산", "원천징수", "근로기준법", "주52시간", "퇴직급여", "퇴직연금",
    "인적자원관리", "인사노무", "다면평가", "성과관리", "역량면접", "온보딩", "컴활", "컴퓨터활용능력",
    "전산회계", "전산세무", "부가가치세", "재무제표", "고정자산", "비품관리", "공문서", "개인정보",
    "사무행정", "물류관리", "유통관리", "취업규칙", "임금대장", "연차휴가",
]
for _word in hr_user_words:
    kiwi.add_user_word(_word, "NNP")

noun_tags = {"NNG", "NNP"}
stopwords = set(
    """강의 강좌 과정 교육 훈련 실무 이해 학습 수강 수강생 기초 기본 활용 방법 내용 관련 필요 능력 역량
    업무 직무 직장인 실습 프로세스 목표 기대 효과 학습자 대상 분야 기술 지식 향상 습득 수행 제공 사례 실제
    중심 기반 대비 올인원 왕초보 초보 입문 마스터 정복 완전정복 노하우 개념 흐름 제고 기능 사용 시간 변화
    스킬 수립 시대 훈련생 프로그램 단계 설명 중요 중요성 포인트 강사 장비 배정 지정 실전 예제 상황 직장
    이론 방안 부분 다양 가능 이상 이후 핵심 완벽 최신 온라인 진행 운영 하나 가지 처음 누구 이제 지금
    모든 각종 전반 여러분 우리 자신 정도 경우 위주 구성 통해 위해 대한 수업 강화 체계 완성 노하우 비법 공략
    총시간 회차 인증 우수 기관 적용 파악 주요 정리 구체 의미 비교 문제 관리 plus up basic""".split()
)


def tokenize(text):
    tokens = []
    prev = None
    for tok in kiwi.tokenize(str(text)):
        is_noun = tok.tag in noun_tags
        if is_noun or tok.tag == "SL":
            form = tok.form.lower()
            if len(form) >= 2 and form not in stopwords:
                tokens.append(form)
        if is_noun and prev is not None and prev.start + prev.len == tok.start:
            compound = prev.form + tok.form
            if compound not in stopwords:
                tokens.append(compound)
        prev = tok if is_noun else None
    return tokens


doc_tokens = [tokenize(d) for d in courses["doc"]]
print(f"[3/6] Kiwi 형태소 분석 완료 (전체 문서 토큰화)")

# 4. TF-IDF 어휘 행렬
vectorizer_args = dict(
    tokenizer=lambda toks: toks,
    preprocessor=lambda toks: toks,
    lowercase=False,
    token_pattern=None,
    min_df=2,
    max_df=0.5,
)
tfidf_vec = TfidfVectorizer(sublinear_tf=True, **vectorizer_args)
tfidf = tfidf_vec.fit_transform(doc_tokens)
vocab = tfidf_vec.get_feature_names_out()
print(f"[4/6] TF-IDF 변환 완료: 어휘 수 = {len(vocab):,}개, 행렬 크기 = {tfidf.shape}")

# 전체 상위 20개 키워드
tfidf_sum = np.asarray(tfidf.sum(axis=0)).ravel()
top20_idx = np.argsort(-tfidf_sum)[:20]
print("\n" + "=" * 65)
print(" 🏆 [2단계 결과] 전체 295개 교육과정 핵심 직무 키워드 Top 20 (TF-IDF)")
print("=" * 65)
for rank, idx in enumerate(top20_idx, 1):
    dfreq = int((tfidf[:, idx] > 0).sum())
    print(f" {rank:2d}위: {vocab[idx]:<12} | TF-IDF 합계: {tfidf_sum[idx]:6.2f} | 등장 강좌수: {dfreq}개")
print("=" * 65)

# 개별 강좌별 Top 5 키워드
dense = tfidf.toarray()
top_idx = np.argsort(-dense, axis=1)[:, :5]
courses["top_keywords"] = [
    ", ".join(vocab[j] for j in row if dense[i, j] > 0) for i, row in enumerate(top_idx)
]

# 5. K-Means 군집화 (k=8)
kmeans = KMeans(n_clusters=8, n_init=10, random_state=42).fit(tfidf)
cluster_labels = kmeans.labels_
courses["cluster"] = cluster_labels
sil = silhouette_score(tfidf, cluster_labels, metric="cosine")
print(f"\n[5/6] K-Means 군집화 완료 (k=8, 실루엣 점수 = {sil:.4f})")

# 군집 요약
cluster_rows = []
for j in range(8):
    mask = cluster_labels == j
    score = dense[mask].mean(axis=0) - 0.5 * dense[~mask].mean(axis=0)
    top_words = [vocab[i] for i in np.argsort(-score)[:8]]
    cluster_rows.append({
        "cluster": j,
        "n_courses": int(mask.sum()),
        "top_keywords": ", ".join(top_words),
        "example_titles": " | ".join(courses.loc[mask, "base_title"].drop_duplicates().head(3).str[:30]),
    })
df_cluster_summary = pd.DataFrame(cluster_rows).sort_values("n_courses", ascending=False)

print("\n" + "=" * 65)
print(" 📁 [2단계 결과] 8대 세부 군집별 대표 키워드 및 예시 강의")
print("=" * 65)
for _, r in df_cluster_summary.iterrows():
    print(f"▶ 군집 {r['cluster']} ({r['n_courses']}개 강좌)")
    print(f"   - 핵심 키워드: {r['top_keywords']}")
    print(f"   - 대표 강좌  : {r['example_titles']}")
print("=" * 65)

# 6. BM25 검색 모델 구축
bm25 = BM25Okapi(doc_tokens, k1=1.5, b=0.75)
test_query = "급여 계산 4대보험 연말정산 통상임금"
query_tokens = [t for t in tokenize(test_query) if t in set(vocab)]
bm25_scores = bm25.get_scores(query_tokens)
top_bm25_idx = np.argsort(-bm25_scores)[:3]

print(f"\n[6/6] BM25 검색 검증 질의: '{test_query}'")
for rank, idx in enumerate(top_bm25_idx, 1):
    c = courses.iloc[idx]
    print(f"  {rank}위 (점수 {bm25_scores[idx]:.2f}): {c['course_title']} ({c['platform']})")

# 결과 파일 저장
out_dir = Path("data/hr/output/text_analysis")
out_dir.mkdir(parents=True, exist_ok=True)
courses[[
    "id", "course_title", "platform", "institution", "training_hours", "cost", "cost_type",
    "top_keywords", "cluster"
]].to_csv(out_dir / "course_keywords_clusters_k8.csv", index=False, encoding="utf-8-sig")
df_cluster_summary.to_csv(out_dir / "cluster_summary_k8.csv", index=False, encoding="utf-8-sig")
print(f"\n[저장 완료] 산출물이 {out_dir} 에 저장되었습니다.")
