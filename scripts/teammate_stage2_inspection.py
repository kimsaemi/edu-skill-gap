import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="2?④퀎 | ?ㅼ썙??遺꾩꽍쨌援먯쑁怨쇱젙 援곗쭛??)


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
    # 2?④퀎: ?ㅼ썙??遺꾩꽍, BM25 寃?? ?좏뵿 紐⑤뜽留? 援먯쑁怨쇱젙 援곗쭛??
    295媛?援먯쑁怨쇱젙???쒕ぉ쨌?뚭컻湲쨌而ㅻ━?섎읆 ?띿뒪?몃줈 **TF-IDF ?듭떖 ?ㅼ썙??*瑜?戮묎퀬,
    **BM25 寃??*??留뚮뱾怨? **LDA ?좏뵿 紐⑤뜽留?*怨?**K-Means 援곗쭛??*濡?鍮꾩듂??媛뺤쓽?쇰━ 臾띠뒿?덈떎.

    > ?ъ슜 ?쇱씠釉뚮윭由? kiwipiepy(?뺥깭??遺꾩꽍), scikit-learn(TF-IDF쨌LDA쨌K-Means쨌SVD), rank_bm25(BM25)
    """)
    return


@app.cell
def _(mo, pd):
    data_path = mo.notebook_dir().parent / "data" / "processed" / "hr_courses_detailed_295.csv"
    courses_raw = pd.read_csv(data_path)
    mo.md(f"**?먮낯 ?곗씠??** `{data_path.name}` ??{len(courses_raw)}媛?怨쇱젙, {courses_raw.shape[1]}媛?而щ읆")
    return (courses_raw,)


@app.cell
def _(mo):
    mo.md("""
    ## 1. ?띿뒪???뺤젣

    ?먮낯 ?띿뒪?몄뿉??媛뺤쓽 ?댁슜怨?臾닿???臾몄옣??留롮븘 洹몃?濡??곕㈃ 紐⑤뱺 媛뺤쓽媛 鍮꾩듂??蹂댁엯?덈떎.

    - **?쒗뵆由?而ㅻ━?섎읆 ?쒓굅:** ?뚢??듭떖 ?꾨줈?몄뒪 ?ㅼ뒿 // ?ㅻТ ?쒖떇 ?묒꽦 ?╉??뺥깭濡??먮룞 ?앹꽦??而ㅻ━?섎읆? ?ъ슜?섏? ?딆뒿?덈떎.
    - **湲곌? ?띾낫 臾멸뎄 ?쒓굅:** ?뚭컻湲??臾몄옣 ?⑥쐞濡?履쇨컿 ?? ?쒕줈 ?ㅻⅨ 媛뺤쓽 3媛??댁긽???묎컳???깆옣?섎뒗 臾몄옣(?덈젴湲곌? ?뚭컻, 痍⑥뾽吏???덈궡 ????吏?곷땲??
    - **?뚯감 ?쒓린 ?쒓굅:** `(?먮??⑥뼱 2?뚯감)` 媛숈? 瑗щ━?쒕? ?쇱뼱 媛숈? 媛뺤쓽瑜??섎굹???쒕ぉ?쇰줈 遊낅땲??
    - **遺꾩꽍 臾몄꽌 援ъ꽦:** ?쒕ぉ(媛以묒튂 횞2) + ?뺤젣???뚭컻湲 + ?ㅼ젣 而ㅻ━?섎읆(NCS ?λ젰?⑥쐞紐?
    - `target_audience`??220媛쒓? 媛숈? 臾몄옣?닿퀬, `learning_objectives`??220媛쒓? ?뚭컻湲怨??묎컳?꾩꽌 ?쒖쇅?⑸땲??
    """)
    return


@app.cell
def _(courses_raw, re):
    template_marker = "?듭떖 ?꾨줈?몄뒪 ?ㅼ뒿 // ?ㅻТ ?쒖떇 ?묒꽦"
    boilerplate_min_titles = 3

    def strip_session_suffix(title):
        """'媛뺤쓽紐?(湲곌?紐?2?뚯감)' ?뺥깭???뚯감 瑗щ━???쒓굅"""
        return re.sub(r"\s*\([^()]*(\([^()]*\))?[^()]*\d+?뚯감\)\s*$", "", title).strip()

    def split_segments(text):
        """?뚭컻湲??臾몄옣/??ぉ ?⑥쐞濡?遺꾨━"""
        parts = re.split(r"\s*(?:????????????\[|\]|\s-\s|\d+\.\s|[.!?]\s)\s*", str(text))
        return [p.strip() for p in parts if len(p.strip()) >= 8]

    courses = courses_raw.copy()
    courses["base_title"] = courses["course_title"].map(strip_session_suffix)
    courses["is_template_syllabus"] = courses["syllabus_text"].str.contains(template_marker, regex=False)

    # ?쒕줈 ?ㅻⅨ 媛뺤쓽 ?щ윭 媛쒖뿉 諛섎났?섎뒗 臾몄옣 = 湲곌? ?띾낫 ?곸슜援?    segment_titles = {}
    for _title, _overview in zip(courses["base_title"], courses["overview"]):
        for _seg in set(split_segments(_overview)):
            segment_titles.setdefault(_seg, set()).add(_title)
    boilerplate_segments = {s for s, t in segment_titles.items() if len(t) >= boilerplate_min_titles}

    def clean_overview(text):
        return " ".join(s for s in split_segments(text) if s not in boilerplate_segments)

    def clean_syllabus(text, is_template):
        if is_template:
            return ""
        text = re.sub(r"珥앹떆媛?s*\(\s*\d+\s*?쒓컙\s*\)", " ", text)
        return re.sub(r"\(\s*\d+\s*?쒓컙\s*\)", " ", text).strip()

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
            "??ぉ": [
                "?꾩껜 怨쇱젙",
                "?쒗뵆由?而ㅻ━?섎읆(?쒖쇅)",
                "?ㅼ젣 而ㅻ━?섎읆 蹂댁쑀",
                "?쒓굅???띾낫 ?곸슜援?臾몄옣 醫낅쪟",
                "?뺤젣 ???뚭컻湲??嫄곗쓽 鍮?怨쇱젙(20??誘몃쭔)",
                "怨좎쑀 媛뺤쓽紐??뚯감 ?듯빀)",
                "?됯퇏 ?뚭컻湲 湲몄씠: ?뺤젣 ??????,
            ],
            "媛?: [
                len(courses),
                int(courses["is_template_syllabus"].sum()),
                int((~courses["is_template_syllabus"]).sum()),
                len(boilerplate_segments),
                int((courses["overview_clean"].str.len() < 20).sum()),
                courses["base_title"].nunique(),
                f"{courses['overview'].str.len().mean():.0f}????{courses['overview_clean'].str.len().mean():.0f}??,
            ],
        }
    )
    mo.vstack([mo.md("### ?뺤젣 寃곌낵"), cleaning_summary])
    return


@app.cell
def _(mo):
    mo.md("""
    ## 2. ?뺥깭??遺꾩꽍怨?TF-IDF

    - **kiwipiepy**濡?紐낆궗(?쇰컲쨌怨좎쑀紐낆궗)? ?곷Ц ?⑥뼱留?戮묒뒿?덈떎. "?몄궗?몃Т愿由? ???몄궗 / ?몃Т / 愿由?    - ?뺥깭??遺꾩꽍湲곌? ?덈Т ?섍쾶 履쇨컻??臾몄젣("?먯쿇吏뺤닔" ???먯쿇 / 吏뺤닔)瑜?蹂댁셿?섎젮怨? **?꾩뼱?곌린 ?놁씠 遺숈뼱 ?덈뜕 紐낆궗 2媛쒕뒗 ?⑹튇 蹂듯빀?대룄 ?④퍡** ?ｌ뒿?덈떎 (?먯쿇吏뺤닔, ?곕쭚?뺤궛, ?몃Т愿由???.
    - ?몄궗쨌珥앸Т ?듭떖 ?⑹뼱(?듭긽?꾧툑, 4?蹂댄뿕, 洹쇰줈湲곗?踰??????ъ슜???ъ쟾???깅줉???섎굹???⑥뼱濡??몄떇?쒗궢?덈떎.
    - "媛뺤쓽, ?ㅻТ, 怨쇱젙, ?댄빐"泥섎읆 ?대뵒?먮굹 ?섏삤???⑥뼱??遺덉슜?대줈 鍮쇨퀬, 2媛?誘몃쭔 ?먮뒗 50% 珥덇낵 臾몄꽌???섏삤???⑥뼱???쒖쇅?⑸땲??
    - TF-IDF: scikit-learn `TfidfVectorizer(sublinear_tf=True)` ???⑥뼱鍮덈룄??濡쒓렇瑜??뚯슦怨?臾몄꽌蹂?L2 ?뺢퇋??    """)
    return


@app.cell
def _(Kiwi):
    kiwi = Kiwi()
    hr_user_words = [
        "?듭긽?꾧툑", "4?蹂댄뿕", "?곕쭚?뺤궛", "?먯쿇吏뺤닔", "洹쇰줈湲곗?踰?, "二?2?쒓컙", "?댁쭅湲됱뿬", "?댁쭅?곌툑",
        "?몄쟻?먯썝愿由?, "?몄궗?몃Т", "?ㅻ㈃?됯?", "?깃낵愿由?, "??웾硫댁젒", "?⑤낫??, "而댄솢", "而댄벂?고솢?⑸뒫??,
        "?꾩궛?뚭퀎", "?꾩궛?몃Т", "遺媛媛移섏꽭", "?щТ?쒗몴", "怨좎젙?먯궛", "鍮꾪뭹愿由?, "怨듬Ц??, "媛쒖씤?뺣낫",
    ]
    for _word in hr_user_words:
        kiwi.add_user_word(_word, "NNP")
    return (kiwi,)


@app.cell
def _(courses, kiwi):
    noun_tags = {"NNG", "NNP"}
    stopwords = set(
        """媛뺤쓽 媛뺤쥖 怨쇱젙 援먯쑁 ?덈젴 ?ㅻТ ?댄빐 ?숈뒿 ?섍컯 ?섍컯??湲곗큹 湲곕낯 ?쒖슜 諛⑸쾿 ?댁슜 愿???꾩슂 ?λ젰 ??웾
        ?낅Т 吏곷Т 吏곸옣???ㅼ뒿 ?꾨줈?몄뒪 紐⑺몴 湲곕? ?④낵 ?숈뒿?????遺꾩빞 湲곗닠 吏???μ긽 ?듬뱷 ?섑뻾 ?쒓났 ?щ? ?ㅼ젣
        以묒떖 湲곕컲 ?鍮??ъ씤???뺤큹蹂?珥덈낫 ?낅Ц 留덉뒪???뺣났 ?꾩쟾?뺣났 ?명븯??媛쒕뀗 ?먮쫫 ?쒓퀬 湲곕뒫 ?ъ슜 ?쒓컙 蹂??        ?ㅽ궗 ?섎┰ ?쒕? ?덈젴???꾨줈洹몃옩 ?④퀎 ?ㅻ챸 以묒슂 以묒슂???ъ씤??媛뺤궗 ?λ퉬 諛곗젙 吏???ㅼ쟾 ?덉젣 ?곹솴 吏곸옣
        ?대줎 諛⑹븞 遺遺??ㅼ뼇 媛???댁긽 ?댄썑 ?듭떖 ?꾨꼍 理쒖떊 ?⑤씪??吏꾪뻾 ?댁쁺 ?섎굹 媛吏 泥섏쓬 ?꾧뎄 ?댁젣 吏湲?        紐⑤뱺 媛곸쥌 ?꾨컲 ?щ윭遺??곕━ ?먯떊 ?뺣룄 寃쎌슦 ?꾩＜ 援ъ꽦 ?듯빐 ?꾪빐 ????섏뾽 媛뺥솕 泥닿퀎 ?꾩꽦 ?명븯??鍮꾨쾿 怨듬왂
        珥앹떆媛??뚯감 ?몄쬆 ?곗닔 湲곌? ?곸슜 ?뚯븙 二쇱슂 ?뺣━ 援ъ껜 ?섎? 鍮꾧탳 臾몄젣 愿由?plus up basic""".split()
    )

    def tokenize(text):
        """紐낆궗쨌?곷Ц 異붿텧 + 遺숈뼱 ?덈뜕 紐낆궗 ?띿쓣 蹂듯빀?대줈 異붽?"""
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
    # ?대? ?좏겙?붾맂 由ъ뒪?몃? 洹몃?濡??곕룄濡?tokenizer/preprocessor瑜???벑 ?⑥닔濡?吏??    _vectorizer_args = dict(
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
            x=alt.X("tfidf_sum:Q", title="TF-IDF ?⑷퀎"),
            y=alt.Y("keyword:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("keyword:N", title="?ㅼ썙??),
                alt.Tooltip("tfidf_sum:Q", title="TF-IDF ?⑷퀎", format=".2f"),
                alt.Tooltip("doc_freq:Q", title="?깆옣 臾몄꽌 ??),
                alt.Tooltip("idf:Q", title="IDF", format=".2f"),
            ],
        )
        .properties(title="?꾩껜 援먯쑁怨쇱젙 ?듭떖 ?ㅼ썙??Top 30 (TF-IDF ?⑷퀎)", width=500, height=560)
    )
    mo.vstack(
        [
            mo.md(
                f"### ?꾩껜 ?듭떖 ?ㅼ썙??n?댄쐶 {len(vocab):,}媛?쨌 ?ㅼ썙?쒓? ?섎굹???녿뒗 臾몄꽌 {int((tfidf.getnnz(axis=1) == 0).sum())}媛?
            ),
            top_keywords_chart,
        ]
    )
    return


@app.cell
def _(courses, np, pd, tfidf, vocab):
    # 怨쇱젙蹂?TF-IDF ?곸쐞 5媛??ㅼ썙??    _dense = tfidf.toarray()
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
    ## 3. BM25 寃??
    BM25(rank_bm25 `BM25Okapi`)??寃?됱뼱 ?⑥뼱媛 臾몄꽌???쇰쭏???먯＜ ?섏삤?붿?(?ы솕 泥섎━, `k1`)? 臾몄꽌 湲몄씠(`b`)瑜??④퍡 蹂댁젙???먯닔瑜?留ㅺ퉩?덈떎.
    寃?됱뼱??臾몄꽌? 媛숈? ?뺥깭??遺꾩꽍??嫄곗튂誘濡?"?몄궗?몃Т愿由?濡?寃?됲븯硫?"?몄궗", "?몃Т", "愿由?媛 ?ㅼ뼱媛?媛뺤쓽瑜?李얠뒿?덈떎.
    ?ㅻ쭔 **?⑥뼱媛 ?쇱튂?댁빞** 寃?됰맗?덈떎 (?살? 媛숈?留??⑥뼱媛 ?ㅻⅨ 寃쎌슦??3?④퀎 ?꾨쿋?⑹뿉???ㅻ９?덈떎).
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
        value="湲됱뿬 怨꾩궛 4?蹂댄뿕 ?곕쭚?뺤궛",
        label="寃?됱뼱",
        full_width=True,
    )
    search_top_n = mo.ui.slider(5, 30, value=10, label="寃곌낵 媛쒖닔")
    mo.hstack([search_query, search_top_n], widths=[4, 1])
    return search_query, search_top_n


@app.cell
def _(bm25, bm25_vocab, courses, mo, np, search_query, search_top_n, tokenize):
    _query_tokens = tokenize(search_query.value)
    _matched = [t for t in _query_tokens if t in bm25_vocab]
    mo.stop(
        not _matched,
        mo.md(f"寃?됱뼱 ?좏겙 `{_query_tokens}` 以?臾몄꽌???섏삤???⑥뼱媛 ?놁뒿?덈떎. ?ㅻⅨ ?⑥뼱濡?寃?됲빐 蹂댁꽭??"),
    )
    _scores = bm25.get_scores(_matched)
    _order = np.argsort(-_scores)[: search_top_n.value]
    _order = _order[_scores[_order] > 0]
    search_results = courses.iloc[_order][["id", "course_title", "platform", "institution", "training_hours"]].assign(
        bm25_score=_scores[_order].round(2)
    )
    mo.vstack(
        [
            mo.md(f"**?ъ슜??寃???좏겙:** {', '.join(_matched)} 쨌 ?쇱튂 怨쇱젙 {int((_scores > 0).sum())}媛?),
            search_results,
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## 4. LDA ?좏뵿 紐⑤뜽留?
    LDA??"媛?媛뺤쓽???щ윭 二쇱젣媛 ?욎씤 寃껋씠怨? 媛?二쇱젣???뱀젙 ?⑥뼱?ㅼ씠 ?먯＜ ?④퍡 ?섏삤??臾띠쓬"?대씪怨?蹂닿퀬 二쇱젣瑜?李얠븘?낅땲??
    K-Means媛 媛뺤쓽 ?섎굹瑜?援곗쭛 ?섎굹???ｋ뒗 寃껉낵 ?щ━, LDA??媛뺤쓽留덈떎 **二쇱젣蹂?鍮꾩쨷**(?? ?먭꺽利?70% + ?묒? 30%)??以띾땲??
    """)
    return


@app.cell
def _(mo):
    n_topics = mo.ui.slider(4, 12, value=8, label="?좏뵿 ??, show_value=True)
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
            mo.md(f"?⑥뼱鍮덈룄 ?됰젹 {term_counts.shape[0]}媛?臾몄꽌 횞 {term_counts.shape[1]:,}媛??⑥뼱濡??숈뒿"),
            topic_summary,
        ]
    )
    return (doc_topic,)


@app.cell
def _(mo):
    mo.md("""
    ## 5. K-Means 援곗쭛??
    - TF-IDF 踰≫꽣(L2 ?뺢퇋????scikit-learn `KMeans`(k-means++, 珥덇린媛?10??瑜??곸슜?⑸땲?? ?뺢퇋?붾맂 踰≫꽣???좏겢由щ뱶 嫄곕━??肄붿궗??嫄곕━? ?쒖꽌媛 媛숈뒿?덈떎.
    - 援곗쭛 ??k??**?ㅻ（???먯닔**(肄붿궗??嫄곕━ 湲곗?, 媛숈? 援곗쭛怨쇰뒗 媛源앷퀬 ?ㅻⅨ 援곗쭛怨쇰뒗 癒??뺣룄, -1~1)瑜?李멸퀬??怨좊쫭?덈떎.
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
    _base = alt.Chart(k_selection).encode(x=alt.X("k:O", title="援곗쭛 ??k"))
    k_selection_chart = alt.hconcat(
        _base.mark_line(point=True)
        .encode(y=alt.Y("silhouette:Q", title="?ㅻ（???먯닔"), tooltip=["k", alt.Tooltip("silhouette:Q", format=".4f")])
        .properties(title="?ㅻ（???먯닔 (?믪쓣?섎줉 醫뗭쓬)", width=320, height=220),
        _base.mark_line(point=True, color="#e45756")
        .encode(
            y=alt.Y("inertia:Q", title="援곗쭛 ??嫄곕━ ?쒓낢??, scale=alt.Scale(zero=False)),
            tooltip=["k", alt.Tooltip("inertia:Q", format=".1f")],
        )
        .properties(title="Elbow (??쓣?섎줉 ?묒쭛)", width=320, height=220),
    )
    k_selection_chart
    return (kmeans_models,)


@app.cell
def _(mo):
    n_clusters = mo.ui.slider(4, 12, value=8, label="援곗쭛 ??k", show_value=True)
    n_clusters
    return (n_clusters,)


@app.cell
def _(courses, kmeans_models, n_clusters, np, pd, tfidf, vocab):
    cluster_labels = kmeans_models[n_clusters.value].labels_
    _dense = tfidf.toarray()

    # 援곗쭛 ????ㅼ썙?? 援곗쭛 ???됯퇏 TF-IDF媛 ?믨퀬 ?ㅻⅨ 援곗쭛?먯꽌????? ?⑥뼱 (c-TF-IDF? ?좎궗??諛⑹떇)
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
    # TF-IDF ?됰젹??SVD濡?2李⑥썝 ?ъ쁺??援곗쭛 遺꾪룷瑜??쒓컖??    _coords = TruncatedSVD(n_components=2, random_state=42).fit_transform(tfidf)
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
            color=alt.Color("cluster:N", title="援곗쭛", scale=alt.Scale(scheme="tableau10")),
            tooltip=["course_title", "platform", "cluster"],
        )
        .properties(title="援먯쑁怨쇱젙 援곗쭛 遺꾪룷 (TF-IDF ??SVD 2李⑥썝)", width=720, height=460)
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
        label="援곗쭛 ?좏깮",
        full_width=True,
    )
    cluster_picker
    return (cluster_picker,)


@app.cell
def _(cluster_labels, cluster_picker, course_keywords, mo):
    mo.stop(cluster_picker.value is None, mo.md("援곗쭛???좏깮?섎㈃ ?뚯냽 媛뺤쓽 紐⑸줉??蹂댁뿬以띾땲??"))
    course_keywords[cluster_labels == cluster_picker.value]
    return


@app.cell
def _(mo):
    mo.md("""
    ## 6. 寃곌낵 ???    """)
    return


@app.cell
def _(mo):
    save_button = mo.ui.run_button(label="CSV濡????)
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
    mo.stop(not save_button.value, mo.md("踰꾪듉???꾨Ⅴ硫?`data/hr/output/text_analysis/`????ν빀?덈떎."))
    _out_dir = mo.notebook_dir().parent / "data" / "hr" / "output" / "text_analysis"
    _out_dir.mkdir(parents=True, exist_ok=True)
    course_keywords.assign(cluster=cluster_labels, main_topic=doc_topic.argmax(axis=1)).to_csv(
        _out_dir / f"course_keywords_clusters_k{n_clusters.value}.csv", index=False, encoding="utf-8-sig"
    )
    cluster_summary.to_csv(
        _out_dir / f"cluster_summary_k{n_clusters.value}.csv", index=False, encoding="utf-8-sig"
    )
    mo.md(f"????꾨즺: `{_out_dir}` (k={n_clusters.value})")
    return


@app.cell
def _(mo):
    mo.md("""
    ## 7. ?댁꽍怨??쒓퀎

    - **援곗쭛 媛?寃쎄퀎媛 ?쏀빀?덈떎.** ?ㅻ（???먯닔媛 ??븘(??李⑦듃 李멸퀬) 援곗쭛? "??듭쟻??二쇱젣 臾띠쓬"?쇰줈 ?댁꽍?댁빞 ?⑸땲??
      媛뺤쓽 ?뚭컻湲??吏㏐퀬, 220媛?怨쇱젙? ?ㅼ젣 而ㅻ━?섎읆 ?놁씠 ?쒕ぉ怨??뚭컻湲留??④린 ?뚮Ц?낅땲??
    - **怨꾪쉷?쒖쓽 4媛?援곗쭛(梨꾩슜쨌?몃Т쨌?됯?蹂댁긽쨌珥앸Т)? 洹몃?濡??섑??섏? ?딆뒿?덈떎.** ?곗씠???먯껜媛 珥앸Т쨌?щТ?됱젙 286媛?? ?몄궗 9媛쒕줈 移섏슦爾??덇퀬,
      ?ㅼ젣濡쒕뒗 ?먭꺽利?而댄솢쨌?꾩궛?뚭퀎쨌臾쇰쪟/?좏넻愿由ъ궗), OA쨌臾몄꽌?묒꽦, 由щ뜑??룹“吏? 留덉??끒룸뜲?댄꽣, 寃쎌젣쨌?щТ ?깆쑝濡?臾띠엯?덈떎.
    - **吏곷Т? 臾닿???媛뺤쓽媛 ?욎뿬 ?덉뒿?덈떎** (留덉??? 媛쒕컻, ?ъ＜ ?쒕퉬????. 援곗쭛 寃곌낵瑜?蹂닿퀬 異붿쿇 ??곸뿉???쒖쇅??援곗쭛???뺥븯?????쒖슜?????덉뒿?덈떎.
    - **BM25???⑥뼱媛 ?쇱튂?댁빞 李얠뒿?덈떎.** "?붽툒 怨꾩궛" ??"湲됱뿬" 媛숈? ?섎? 留ㅼ묶? 3?④퀎(?꾨쿋??媛 ?꾩슂?⑸땲??
    """)
    return


if __name__ == "__main__":
    app.run()
