"""
대시보드용 텍스트 분석 결과 내보내기 (2단계 키워드·군집화)
- 배포 서버(Streamlit Cloud)에는 kiwipiepy·scikit-learn이 없으므로, 분석은 로컬에서 하고 결과만 CSV로 저장합니다.
- 입력: data/processed/hr_courses_detailed_295.csv
- 처리: 텍스트 정제 → kiwipiepy 토큰화 → TF-IDF → K-Means(k=8) → SVD 2차원 좌표 → LDA 토픽
- 출력: data/hr/output/dashboard/text_analysis/
    cleaning_summary.csv, keyword_top50.csv, k_selection.csv, cluster_summary.csv,
    lda_topics.csv, course_text_features.csv (과정별 키워드·군집·좌표·BM25용 토큰)
- 실행: .venv/Scripts/python.exe scripts/export_text_analysis_dashboard.py
"""

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation, TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.processors.course_text import build_kiwi, clean_courses, make_tokenizer  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_PATH = ROOT / "data" / "processed" / "hr_courses_detailed_295.csv"
OUT_DIR = ROOT / "data" / "hr" / "output" / "dashboard" / "text_analysis"
N_CLUSTERS = 8
N_TOPICS = 8


def main():
    courses_raw = pd.read_csv(DATA_PATH)
    courses = clean_courses(courses_raw)
    tokenize = make_tokenizer(build_kiwi())
    doc_tokens = [tokenize(d) for d in courses["doc"]]
    print(f"[1/5] 정제·토큰화 완료: {len(courses)}개 과정")

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
    dense = tfidf.toarray()
    print(f"[2/5] TF-IDF 완료: 어휘 {len(vocab):,}개")

    # 군집 수별 실루엣 점수
    k_rows = []
    models = {}
    for k in range(4, 13):
        models[k] = KMeans(n_clusters=k, n_init=10, random_state=42).fit(tfidf)
        k_rows.append(
            {
                "k": k,
                "silhouette": silhouette_score(tfidf, models[k].labels_, metric="cosine"),
                "inertia": models[k].inertia_,
            }
        )
    labels = models[N_CLUSTERS].labels_

    # 군집 대표 키워드: 군집 내 평균 TF-IDF가 높고 다른 군집에서는 낮은 단어
    cluster_rows = []
    for j in range(N_CLUSTERS):
        mask = labels == j
        score = dense[mask].mean(axis=0) - 0.5 * dense[~mask].mean(axis=0)
        top = [vocab[i] for i in np.argsort(-score)[:10]]
        cluster_rows.append(
            {
                "cluster": j,
                "cluster_label": " · ".join(top[:3]),
                "n_courses": int(mask.sum()),
                "top_keywords": ", ".join(top),
                "example_titles": " | ".join(courses.loc[mask, "base_title"].drop_duplicates().head(4)),
            }
        )
    cluster_summary = pd.DataFrame(cluster_rows).sort_values("n_courses", ascending=False)
    label_map = cluster_summary.set_index("cluster")["cluster_label"]
    print(f"[3/5] K-Means(k={N_CLUSTERS}) 완료")

    # LDA 토픽
    term_counts = CountVectorizer(**vectorizer_args).fit_transform(doc_tokens)
    lda = LatentDirichletAllocation(n_components=N_TOPICS, learning_method="batch", max_iter=50, random_state=42)
    doc_topic = lda.fit_transform(term_counts)
    topic_word = lda.components_ / lda.components_.sum(axis=1, keepdims=True)
    lda_topics = pd.DataFrame(
        {
            "topic": range(N_TOPICS),
            "n_main_courses": np.bincount(doc_topic.argmax(axis=1), minlength=N_TOPICS),
            "top_words": [", ".join(vocab[i] for i in np.argsort(-row)[:10]) for row in topic_word],
        }
    ).sort_values("n_main_courses", ascending=False)
    print(f"[4/5] LDA(토픽 {N_TOPICS}개) 완료")

    coords = TruncatedSVD(n_components=2, random_state=42).fit_transform(tfidf)
    top_idx = np.argsort(-dense, axis=1)[:, :5]
    vocab_set = set(vocab)
    features = pd.DataFrame(
        {
            "id": courses["id"],
            "course_title": courses["course_title"],
            "platform": courses["platform"],
            "institution": courses["institution"],
            "training_hours": courses["training_hours"],
            "cost": courses["cost"],
            "url": courses["url"],
            "top_keywords": [", ".join(vocab[j] for j in row if dense[i, j] > 0) for i, row in enumerate(top_idx)],
            "cluster": labels,
            "cluster_label": label_map.reindex(labels).to_numpy(),
            "main_topic": doc_topic.argmax(axis=1),
            "x": coords[:, 0].round(5),
            "y": coords[:, 1].round(5),
            # 대시보드 BM25 검색용 토큰 (어휘에 있는 단어만, 공백 구분)
            "tokens": [" ".join(t for t in toks if t in vocab_set) for toks in doc_tokens],
        }
    )

    keyword_top = (
        pd.DataFrame(
            {
                "keyword": vocab,
                "tfidf_sum": dense.sum(axis=0).round(4),
                "doc_freq": (dense > 0).sum(axis=0),
            }
        )
        .sort_values("tfidf_sum", ascending=False)
        .head(50)
    )

    cleaning_summary = pd.DataFrame(
        {
            "item": [
                "전체 과정",
                "템플릿 커리큘럼 (분석 제외)",
                "실제 커리큘럼 보유",
                "정제 후 소개글이 거의 빈 과정",
                "고유 강의명 (회차 통합)",
                "평균 소개글 길이 (정제 전)",
                "평균 소개글 길이 (정제 후)",
                "분석 어휘 수",
            ],
            "value": [
                len(courses),
                int(courses["is_template_syllabus"].sum()),
                int((~courses["is_template_syllabus"]).sum()),
                int((courses["overview_clean"].str.len() < 20).sum()),
                courses["base_title"].nunique(),
                round(courses["overview"].str.len().mean()),
                round(courses["overview_clean"].str.len().mean()),
                len(vocab),
            ],
        }
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "cleaning_summary.csv": cleaning_summary,
        "keyword_top50.csv": keyword_top,
        "k_selection.csv": pd.DataFrame(k_rows).round(5),
        "cluster_summary.csv": cluster_summary,
        "lda_topics.csv": lda_topics,
        "course_text_features.csv": features,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT_DIR / name, index=False, encoding="utf-8-sig")
    print(f"[5/5] 저장 완료: {OUT_DIR.relative_to(ROOT)} ({len(outputs)}개 파일)")
    print(cluster_summary[["cluster", "n_courses", "cluster_label"]].to_string(index=False))


if __name__ == "__main__":
    main()
