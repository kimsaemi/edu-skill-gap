import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="2단계 | 키워드 분석·교육과정 군집화")


@app.cell
def _():
    import re

    import altair as alt
    import marimo as mo
    import numpy as np
    import pandas as pd
    from kiwipiepy import Kiwi
    from rank_bm25 import BM25Okapi
    from sklearn.cluster import KMeans
    from sklearn.decomposition import LatentDirichletAllocation, TruncatedSVD
    from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
    from sklearn.metrics import silhouette_score

    return (
        BM25Okapi,
        CountVectorizer,
        KMeans,
        Kiwi,
        LatentDirichletAllocation,
        TfidfVectorizer,
        TruncatedSVD,
        alt,
        mo,
        np,
        pd,
        re,
        silhouette_score,
    )


@app.cell
def _(mo):
    mo.md("""
    # 2단계: 키워드 분석, BM25 검색, 토픽 모델링, 교육과정 군집화

    295개 교육과정의 제목·소개글·커리큘럼 텍스트로 **TF-IDF 핵심 키워드**를 뽑고,
    **BM25 검색**을 만들고, **LDA 토픽 모델링**과 **K-Means 군집화**로 비슷한 강의끼리 묶습니다.

    > 사용 라이브러리: kiwipiepy(형태소 분석), scikit-learn(TF-IDF·LDA·K-Means·SVD), rank_bm25(BM25)
    """)
    return


@app.cell
def _(mo, pd):
    data_path = mo.notebook_dir().parent / "data" / "processed" / "hr_courses_detailed_295.csv"
    courses_raw = pd.read_csv(data_path)
    mo.md(f"**원본 데이터:** `{data_path.name}` — {len(courses_raw)}개 과정, {courses_raw.shape[1]}개 컬럼")
    return (courses_raw,)


@app.cell
def _(mo):
    mo.md("""
    ## 1. 텍스트 정제

    원본 텍스트에는 강의 내용과 무관한 문장이 많아 그대로 쓰면 모든 강의가 비슷해 보입니다.

    - **템플릿 커리큘럼 제거:** 「… 핵심 프로세스 실습 // 실무 서식 작성 …」 형태로 자동 생성된 커리큘럼은 사용하지 않습니다.
    - **기관 홍보 문구 제거:** 소개글을 문장 단위로 쪼갠 뒤, 서로 다른 강의 3개 이상에 똑같이 등장하는 문장(훈련기관 소개, 취업지원 안내 등)을 지웁니다.
    - **회차 표기 제거:** `(에듀퓨어 2회차)` 같은 꼬리표를 떼어 같은 강의를 하나의 제목으로 봅니다.
    - **분석 문서 구성:** 제목(가중치 ×2) + 정제된 소개글 + 실제 커리큘럼(NCS 능력단위명)
    - `target_audience`는 220개가 같은 문장이고, `learning_objectives`는 220개가 소개글과 똑같아서 제외합니다.
    """)
    return


@app.cell
def _(courses_raw, re):
    template_marker = "핵심 프로세스 실습 // 실무 서식 작성"
    boilerplate_min_titles = 3

    def strip_session_suffix(title):
        """'강의명 (기관명 2회차)' 형태의 회차 꼬리표 제거"""
        return re.sub(r"\s*\([^()]*(\([^()]*\))?[^()]*\d+회차\)\s*$", "", title).strip()

    def split_segments(text):
        """소개글을 문장/항목 단위로 분리"""
        parts = re.split(r"\s*(?:■|※|▶|●|◆|•|\[|\]|\s-\s|\d+\.\s|[.!?]\s)\s*", str(text))
        return [p.strip() for p in parts if len(p.strip()) >= 8]

    courses = courses_raw.copy()
    courses["base_title"] = courses["course_title"].map(strip_session_suffix)
    courses["is_template_syllabus"] = courses["syllabus_text"].str.contains(template_marker, regex=False)

    # 서로 다른 강의 여러 개에 반복되는 문장 = 기관 홍보 상용구
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
    return boilerplate_segments, courses


@app.cell
def _(boilerplate_segments, courses, mo, pd):
    cleaning_summary = pd.DataFrame(
        {
            "항목": [
                "전체 과정",
                "템플릿 커리큘럼(제외)",
                "실제 커리큘럼 보유",
                "제거된 홍보 상용구 문장 종류",
                "정제 후 소개글이 거의 빈 과정(20자 미만)",
                "고유 강의명(회차 통합)",
                "평균 소개글 길이: 정제 전 → 후",
            ],
            "값": [
                len(courses),
                int(courses["is_template_syllabus"].sum()),
                int((~courses["is_template_syllabus"]).sum()),
                len(boilerplate_segments),
                int((courses["overview_clean"].str.len() < 20).sum()),
                courses["base_title"].nunique(),
                f"{courses['overview'].str.len().mean():.0f}자 → {courses['overview_clean'].str.len().mean():.0f}자",
            ],
        }
    )
    mo.vstack([mo.md("### 정제 결과"), cleaning_summary])
    return


@app.cell
def _(mo):
    mo.md("""
    ## 2. 형태소 분석과 TF-IDF

    - **kiwipiepy**로 명사(일반·고유명사)와 영문 단어만 뽑습니다. "인사노무관리" → 인사 / 노무 / 관리
    - 형태소 분석기가 너무 잘게 쪼개는 문제("원천징수" → 원천 / 징수)를 보완하려고, **띄어쓰기 없이 붙어 있던 명사 2개는 합친 복합어도 함께** 넣습니다 (원천징수, 연말정산, 노무관리 …).
    - 인사·총무 핵심 용어(통상임금, 4대보험, 근로기준법 등)는 사용자 사전에 등록해 하나의 단어로 인식시킵니다.
    - "강의, 실무, 과정, 이해"처럼 어디에나 나오는 단어는 불용어로 빼고, 2개 미만 또는 50% 초과 문서에 나오는 단어도 제외합니다.
    - TF-IDF: scikit-learn `TfidfVectorizer(sublinear_tf=True)` — 단어빈도에 로그를 씌우고 문서별 L2 정규화
    """)
    return


@app.cell
def _(Kiwi):
    kiwi = Kiwi()
    hr_user_words = [
        "통상임금", "4대보험", "연말정산", "원천징수", "근로기준법", "주52시간", "퇴직급여", "퇴직연금",
        "인적자원관리", "인사노무", "다면평가", "성과관리", "역량면접", "온보딩", "컴활", "컴퓨터활용능력",
        "전산회계", "전산세무", "부가가치세", "재무제표", "고정자산", "비품관리", "공문서", "개인정보",
    ]
    for _word in hr_user_words:
        kiwi.add_user_word(_word, "NNP")
    return (kiwi,)


@app.cell
def _(courses, kiwi):
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
        """명사·영문 추출 + 붙어 있던 명사 쌍을 복합어로 추가"""
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
    return doc_tokens, tokenize


@app.cell
def _(CountVectorizer, TfidfVectorizer, doc_tokens):
    # 이미 토큰화된 리스트를 그대로 쓰도록 tokenizer/preprocessor를 항등 함수로 지정
    _vectorizer_args = dict(
        tokenizer=lambda toks: toks,
        preprocessor=lambda toks: toks,
        lowercase=False,
        token_pattern=None,
        min_df=2,
        max_df=0.5,
    )
    tfidf_vectorizer = TfidfVectorizer(sublinear_tf=True, **_vectorizer_args)
    tfidf = tfidf_vectorizer.fit_transform(doc_tokens)
    count_vectorizer = CountVectorizer(**_vectorizer_args)
    term_counts = count_vectorizer.fit_transform(doc_tokens)
    vocab = tfidf_vectorizer.get_feature_names_out()
    return term_counts, tfidf, tfidf_vectorizer, vocab


@app.cell
def _(alt, mo, np, pd, tfidf, tfidf_vectorizer, vocab):
    keyword_stats = pd.DataFrame(
        {
            "keyword": vocab,
            "tfidf_sum": np.asarray(tfidf.sum(axis=0)).ravel(),
            "doc_freq": np.asarray((tfidf > 0).sum(axis=0)).ravel(),
            "idf": tfidf_vectorizer.idf_,
        }
    ).sort_values("tfidf_sum", ascending=False)

    top_keywords_chart = (
        alt.Chart(keyword_stats.head(30))
        .mark_bar()
        .encode(
            x=alt.X("tfidf_sum:Q", title="TF-IDF 합계"),
            y=alt.Y("keyword:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("keyword:N", title="키워드"),
                alt.Tooltip("tfidf_sum:Q", title="TF-IDF 합계", format=".2f"),
                alt.Tooltip("doc_freq:Q", title="등장 문서 수"),
                alt.Tooltip("idf:Q", title="IDF", format=".2f"),
            ],
        )
        .properties(title="전체 교육과정 핵심 키워드 Top 30 (TF-IDF 합계)", width=500, height=560)
    )
    mo.vstack(
        [
            mo.md(
                f"### 전체 핵심 키워드\n어휘 {len(vocab):,}개 · 키워드가 하나도 없는 문서 {int((tfidf.getnnz(axis=1) == 0).sum())}개"
            ),
            top_keywords_chart,
        ]
    )
    return


@app.cell
def _(courses, np, pd, tfidf, vocab):
    # 과정별 TF-IDF 상위 5개 키워드
    _dense = tfidf.toarray()
    _top_idx = np.argsort(-_dense, axis=1)[:, :5]
    course_keywords = pd.DataFrame(
        {
            "id": courses["id"],
            "course_title": courses["course_title"],
            "platform": courses["platform"],
            "top_keywords": [
                ", ".join(vocab[j] for j in row if _dense[i, j] > 0) for i, row in enumerate(_top_idx)
            ],
        }
    )
    course_keywords
    return (course_keywords,)


@app.cell
def _(mo):
    mo.md("""
    ## 3. BM25 검색

    BM25(rank_bm25 `BM25Okapi`)는 검색어 단어가 문서에 얼마나 자주 나오는지(포화 처리, `k1`)와 문서 길이(`b`)를 함께 보정해 점수를 매깁니다.
    검색어도 문서와 같은 형태소 분석을 거치므로 "인사노무관리"로 검색하면 "인사", "노무", "관리"가 들어간 강의를 찾습니다.
    다만 **단어가 일치해야** 검색됩니다 (뜻은 같지만 단어가 다른 경우는 3단계 임베딩에서 다룹니다).
    """)
    return


@app.cell
def _(BM25Okapi, doc_tokens):
    bm25 = BM25Okapi(doc_tokens, k1=1.5, b=0.75)
    bm25_vocab = {t for toks in doc_tokens for t in toks}
    return bm25, bm25_vocab


@app.cell
def _(mo):
    search_query = mo.ui.text(
        value="급여 계산 4대보험 연말정산",
        label="검색어",
        full_width=True,
    )
    search_top_n = mo.ui.slider(5, 30, value=10, label="결과 개수")
    mo.hstack([search_query, search_top_n], widths=[4, 1])
    return search_query, search_top_n


@app.cell
def _(bm25, bm25_vocab, courses, mo, np, search_query, search_top_n, tokenize):
    _query_tokens = tokenize(search_query.value)
    _matched = [t for t in _query_tokens if t in bm25_vocab]
    mo.stop(
        not _matched,
        mo.md(f"검색어 토큰 `{_query_tokens}` 중 문서에 나오는 단어가 없습니다. 다른 단어로 검색해 보세요."),
    )
    _scores = bm25.get_scores(_matched)
    _order = np.argsort(-_scores)[: search_top_n.value]
    _order = _order[_scores[_order] > 0]
    search_results = courses.iloc[_order][["id", "course_title", "platform", "institution", "training_hours"]].assign(
        bm25_score=_scores[_order].round(2)
    )
    mo.vstack(
        [
            mo.md(f"**사용된 검색 토큰:** {', '.join(_matched)} · 일치 과정 {int((_scores > 0).sum())}개"),
            search_results,
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## 4. LDA 토픽 모델링

    LDA는 "각 강의는 여러 주제가 섞인 것이고, 각 주제는 특정 단어들이 자주 함께 나오는 묶음"이라고 보고 주제를 찾아냅니다.
    K-Means가 강의 하나를 군집 하나에 넣는 것과 달리, LDA는 강의마다 **주제별 비중**(예: 자격증 70% + 엑셀 30%)을 줍니다.
    """)
    return


@app.cell
def _(mo):
    n_topics = mo.ui.slider(4, 12, value=8, label="토픽 수", show_value=True)
    n_topics
    return (n_topics,)


@app.cell
def _(LatentDirichletAllocation, mo, n_topics, np, pd, term_counts, vocab):
    lda = LatentDirichletAllocation(n_components=n_topics.value, learning_method="batch", max_iter=50, random_state=42)
    doc_topic = lda.fit_transform(term_counts)
    _topic_word = lda.components_ / lda.components_.sum(axis=1, keepdims=True)
    topic_summary = pd.DataFrame(
        {
            "topic": range(n_topics.value),
            "n_main_courses": np.bincount(doc_topic.argmax(axis=1), minlength=n_topics.value),
            "top_words": [", ".join(vocab[i] for i in np.argsort(-row)[:10]) for row in _topic_word],
        }
    ).sort_values("n_main_courses", ascending=False)
    mo.vstack(
        [
            mo.md(f"단어빈도 행렬 {term_counts.shape[0]}개 문서 × {term_counts.shape[1]:,}개 단어로 학습"),
            topic_summary,
        ]
    )
    return (doc_topic,)


@app.cell
def _(mo):
    mo.md("""
    ## 5. K-Means 군집화

    - TF-IDF 벡터(L2 정규화)에 scikit-learn `KMeans`(k-means++, 초기값 10회)를 적용합니다. 정규화된 벡터의 유클리드 거리는 코사인 거리와 순서가 같습니다.
    - 군집 수 k는 **실루엣 점수**(코사인 거리 기준, 같은 군집과는 가깝고 다른 군집과는 먼 정도, -1~1)를 참고해 고릅니다.
    """)
    return


@app.cell
def _(KMeans, alt, pd, silhouette_score, tfidf):
    k_candidates = list(range(4, 13))
    kmeans_models = {k: KMeans(n_clusters=k, n_init=10, random_state=42).fit(tfidf) for k in k_candidates}
    k_selection = pd.DataFrame(
        {
            "k": k_candidates,
            "silhouette": [silhouette_score(tfidf, kmeans_models[k].labels_, metric="cosine") for k in k_candidates],
            "inertia": [kmeans_models[k].inertia_ for k in k_candidates],
        }
    )
    _base = alt.Chart(k_selection).encode(x=alt.X("k:O", title="군집 수 k"))
    k_selection_chart = alt.hconcat(
        _base.mark_line(point=True)
        .encode(y=alt.Y("silhouette:Q", title="실루엣 점수"), tooltip=["k", alt.Tooltip("silhouette:Q", format=".4f")])
        .properties(title="실루엣 점수 (높을수록 좋음)", width=320, height=220),
        _base.mark_line(point=True, color="#e45756")
        .encode(
            y=alt.Y("inertia:Q", title="군집 내 거리 제곱합", scale=alt.Scale(zero=False)),
            tooltip=["k", alt.Tooltip("inertia:Q", format=".1f")],
        )
        .properties(title="Elbow (낮을수록 응집)", width=320, height=220),
    )
    k_selection_chart
    return (kmeans_models,)


@app.cell
def _(mo):
    n_clusters = mo.ui.slider(4, 12, value=8, label="군집 수 k", show_value=True)
    n_clusters
    return (n_clusters,)


@app.cell
def _(courses, kmeans_models, n_clusters, np, pd, tfidf, vocab):
    cluster_labels = kmeans_models[n_clusters.value].labels_
    _dense = tfidf.toarray()

    # 군집 대표 키워드: 군집 내 평균 TF-IDF가 높고 다른 군집에서는 낮은 단어 (c-TF-IDF와 유사한 방식)
    _rows = []
    for _j in range(n_clusters.value):
        _mask = cluster_labels == _j
        _score = _dense[_mask].mean(axis=0) - 0.5 * _dense[~_mask].mean(axis=0)
        _top = [vocab[i] for i in np.argsort(-_score)[:10]]
        _rows.append(
            {
                "cluster": _j,
                "n_courses": int(_mask.sum()),
                "top_keywords": ", ".join(_top),
                "example_titles": " | ".join(courses.loc[_mask, "base_title"].drop_duplicates().head(4).str[:28]),
                "platforms": ", ".join(
                    f"{p}({c})" for p, c in courses.loc[_mask, "platform"].value_counts().items()
                ),
            }
        )
    cluster_summary = pd.DataFrame(_rows).sort_values("n_courses", ascending=False)
    cluster_summary
    return cluster_labels, cluster_summary


@app.cell
def _(TruncatedSVD, alt, cluster_labels, cluster_summary, courses, pd, tfidf):
    # TF-IDF 행렬을 SVD로 2차원 투영해 군집 분포를 시각화
    _coords = TruncatedSVD(n_components=2, random_state=42).fit_transform(tfidf)
    _label_names = {
        r.cluster: f"{r.cluster}: {', '.join(r.top_keywords.split(', ')[:3])}" for r in cluster_summary.itertuples()
    }
    projection = pd.DataFrame(
        {
            "x": _coords[:, 0],
            "y": _coords[:, 1],
            "cluster": [_label_names[c] for c in cluster_labels],
            "course_title": courses["course_title"],
            "platform": courses["platform"],
        }
    )
    cluster_scatter = (
        alt.Chart(projection)
        .mark_circle(size=70, opacity=0.75)
        .encode(
            x=alt.X("x:Q", title="SVD 1"),
            y=alt.Y("y:Q", title="SVD 2"),
            color=alt.Color("cluster:N", title="군집", scale=alt.Scale(scheme="tableau10")),
            tooltip=["course_title", "platform", "cluster"],
        )
        .properties(title="교육과정 군집 분포 (TF-IDF → SVD 2차원)", width=720, height=460)
        .interactive()
    )
    cluster_scatter
    return


@app.cell
def _(cluster_summary, mo):
    cluster_picker = mo.ui.dropdown(
        options={
            f"{r.cluster}: {', '.join(r.top_keywords.split(', ')[:4])} ({r.n_courses})": r.cluster
            for r in cluster_summary.itertuples()
        },
        value=None,
        label="군집 선택",
        full_width=True,
    )
    cluster_picker
    return (cluster_picker,)


@app.cell
def _(cluster_labels, cluster_picker, course_keywords, mo):
    mo.stop(cluster_picker.value is None, mo.md("군집을 선택하면 소속 강의 목록을 보여줍니다."))
    course_keywords[cluster_labels == cluster_picker.value]
    return


@app.cell
def _(mo):
    mo.md("""
    ## 6. 결과 저장
    """)
    return


@app.cell
def _(mo):
    save_button = mo.ui.run_button(label="CSV로 저장")
    save_button
    return (save_button,)


@app.cell
def _(
    cluster_labels,
    cluster_summary,
    course_keywords,
    doc_topic,
    mo,
    n_clusters,
    save_button,
):
    mo.stop(not save_button.value, mo.md("버튼을 누르면 `data/hr/output/text_analysis/`에 저장합니다."))
    _out_dir = mo.notebook_dir().parent / "data" / "hr" / "output" / "text_analysis"
    _out_dir.mkdir(parents=True, exist_ok=True)
    course_keywords.assign(cluster=cluster_labels, main_topic=doc_topic.argmax(axis=1)).to_csv(
        _out_dir / f"course_keywords_clusters_k{n_clusters.value}.csv", index=False, encoding="utf-8-sig"
    )
    cluster_summary.to_csv(
        _out_dir / f"cluster_summary_k{n_clusters.value}.csv", index=False, encoding="utf-8-sig"
    )
    mo.md(f"저장 완료: `{_out_dir}` (k={n_clusters.value})")
    return


@app.cell
def _(mo):
    mo.md("""
    ## 7. 해석과 한계

    - **군집 간 경계가 약합니다.** 실루엣 점수가 낮아(위 차트 참고) 군집은 "대략적인 주제 묶음"으로 해석해야 합니다.
      강의 소개글이 짧고, 220개 과정은 실제 커리큘럼 없이 제목과 소개글만 남기 때문입니다.
    - **계획서의 4개 군집(채용·노무·평가보상·총무)은 그대로 나타나지 않습니다.** 데이터 자체가 총무·사무행정 286개 대 인사 9개로 치우쳐 있고,
      실제로는 자격증(컴활·전산회계·물류/유통관리사), OA·문서작성, 리더십·조직, 마케팅·데이터, 경제·재무 등으로 묶입니다.
    - **직무와 무관한 강의가 섞여 있습니다** (마케팅, 개발, 사주 서비스 등). 군집 결과를 보고 추천 대상에서 제외할 군집을 정하는 데 활용할 수 있습니다.
    - **BM25는 단어가 일치해야 찾습니다.** "월급 계산" → "급여" 같은 의미 매칭은 3단계(임베딩)가 필요합니다.
    """)
    return


if __name__ == "__main__":
    app.run()
