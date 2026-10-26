import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full", app_title="3단계 | 언어모델 임베딩·의미 유사도")


@app.cell
def _():
    import sys

    import altair as alt
    import marimo as mo
    import numpy as np
    import pandas as pd
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer
    from sklearn.decomposition import PCA

    return BM25Okapi, PCA, SentenceTransformer, alt, mo, np, pd, sys


@app.cell
def _(mo):
    mo.md("""
    # 3단계: 한국어 언어모델 임베딩 & 의미 유사도

    2단계의 BM25는 **글자가 같아야** 강의를 찾습니다. 3단계에서는 한국어 언어모델이 문장의 **뜻**을 768개 숫자(벡터)로 바꾸고,
    벡터끼리의 각도(코사인 유사도)로 비슷한 강의를 찾습니다. 그래서 "월급"이라고 써도 "급여" 강의를 찾을 수 있습니다.

    - 기본 모델: `jhgan/ko-sroberta-multitask` — 한국어 문장 유사도(KorSTS·KorNLI)로 학습된 모델, 내 컴퓨터(CPU)에서 무료로 실행
    - 임베딩은 `scripts/run_stage3_embedding_pipeline.py`가 미리 계산해 `data/hr/output/embeddings/`에 저장합니다.
    """)
    return


@app.cell
def _(mo, sys):
    root_dir = mo.notebook_dir().parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from src.processors.course_text import build_kiwi, clean_courses, make_tokenizer

    return build_kiwi, clean_courses, make_tokenizer, root_dir


@app.cell
def _(clean_courses, mo, np, pd, root_dir):
    courses = clean_courses(pd.read_csv(root_dir / "data" / "processed" / "hr_courses_detailed_295.csv"))
    _emb_dir = root_dir / "data" / "hr" / "output" / "embeddings"
    _emb_path = _emb_dir / "course_embeddings_ko-sroberta.npy"
    mo.stop(
        not _emb_path.exists(),
        mo.md("임베딩 캐시가 없습니다. 먼저 `scripts/run_stage3_embedding_pipeline.py`를 실행하세요.").callout(kind="warn"),
    )
    _cached_ids = pd.read_csv(_emb_dir / "course_ids.csv")["id"].tolist()
    mo.stop(
        _cached_ids != courses["id"].tolist(),
        mo.md("임베딩 캐시의 과정 목록이 데이터와 다릅니다. `--rebuild` 옵션으로 다시 계산하세요.").callout(kind="warn"),
    )
    course_vectors = np.load(_emb_path)
    mo.md(f"**임베딩 로드:** {course_vectors.shape[0]}개 과정 × {course_vectors.shape[1]}차원")
    return course_vectors, courses


@app.cell
def _(SentenceTransformer):
    # 질의 문장 인코딩용 모델 (최초 1회 다운로드 후 로컬 캐시 사용)
    embed_model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")
    return (embed_model,)


@app.cell
def _(BM25Okapi, build_kiwi, courses, make_tokenizer):
    tokenize = make_tokenizer(build_kiwi())
    bm25 = BM25Okapi([tokenize(d) for d in courses["doc"]], k1=1.5, b=0.75)
    return bm25, tokenize


@app.cell
def _(mo):
    mo.md("""
    ## 1. 의미 검색 vs 키워드 검색

    같은 질문을 넣었을 때 언어모델(의미)과 BM25(키워드)가 어떤 강의를 찾는지 나란히 비교합니다.
    """)
    return


@app.cell
def _(mo):
    semantic_query = mo.ui.text(
        value="월급 계산이랑 퇴직금 법적 기준 배우고 싶어요",
        label="질문",
        full_width=True,
    )
    semantic_top_n = mo.ui.slider(3, 20, value=5, label="결과 개수", show_value=True)
    mo.hstack([semantic_query, semantic_top_n], widths=[4, 1])
    return semantic_query, semantic_top_n


@app.cell
def _(
    bm25,
    course_vectors,
    courses,
    embed_model,
    mo,
    np,
    semantic_query,
    semantic_top_n,
    tokenize,
):
    mo.stop(not semantic_query.value.strip(), mo.md("질문을 입력하세요."))
    _cols = ["course_title", "platform", "institution"]

    _q_vec = embed_model.encode([semantic_query.value], normalize_embeddings=True)
    _sem_scores = (course_vectors @ _q_vec.T).ravel()
    _sem_top = np.argsort(-_sem_scores)[: semantic_top_n.value]
    semantic_results = courses.iloc[_sem_top][_cols].assign(similarity=(_sem_scores[_sem_top] * 100).round(1))

    _tokens = tokenize(semantic_query.value)
    _bm25_scores = np.asarray(bm25.get_scores(_tokens))
    _bm25_top = np.argsort(-_bm25_scores)[: semantic_top_n.value]
    _bm25_top = _bm25_top[_bm25_scores[_bm25_top] > 0]
    keyword_results = courses.iloc[_bm25_top][_cols].assign(bm25=_bm25_scores[_bm25_top].round(2))

    mo.hstack(
        [
            mo.vstack([mo.md("### 언어모델 (의미 유사도 %)"), semantic_results]),
            mo.vstack([mo.md(f"### BM25 (키워드: {', '.join(_tokens) or '없음'})"), keyword_results]),
        ],
        widths="equal",
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## 2. 검색 방식 평가

    강의 제목과 **다른 단어로 바꿔 쓴 질문 12개**(예: "표 계산 프로그램" → 엑셀 강의)로 각 방식을 채점했습니다.
    정답은 "제목에 관련 단어가 들어간 강의"로 정했습니다.

    - **Hit@5**: 상위 5개 안에 정답이 하나라도 있는 비율
    - **Precision@5**: 상위 5개 중 정답 비율
    - **MRR@10**: 첫 정답이 몇 등에 나왔는지 (1등이면 1.0, 2등이면 0.5 …)
    """)
    return


@app.cell
def _(alt, mo, pd, root_dir):
    _summary_path = root_dir / "data" / "hr" / "output" / "semantic" / "retrieval_eval_summary.csv"
    mo.stop(not _summary_path.exists(), mo.md("평가 결과가 없습니다. 파이프라인 스크립트를 먼저 실행하세요."))
    eval_summary = pd.read_csv(_summary_path)
    _long = eval_summary.melt(id_vars="method", var_name="metric", value_name="score")
    eval_chart = (
        alt.Chart(_long)
        .mark_bar()
        .encode(
            x=alt.X("method:N", title=None, sort=list(eval_summary["method"]), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("score:Q", title="점수", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("method:N", legend=None),
            column=alt.Column("metric:N", title=None),
            tooltip=["method", "metric", alt.Tooltip("score:Q", format=".3f")],
        )
        .properties(width=220, height=240)
    )
    mo.vstack([eval_summary, eval_chart])
    return


@app.cell
def _(mo):
    mo.md("""
    ## 3. 비슷한 강의 찾기

    강의 하나를 고르면 의미가 가장 가까운 강의를 보여줍니다 (같은 강의의 다른 회차는 제외).
    추천 화면의 "이 강의와 비슷한 강의"에 그대로 쓸 수 있습니다.
    """)
    return


@app.cell
def _(courses, mo):
    course_picker = mo.ui.dropdown(
        options=dict(zip(courses["course_title"], range(len(courses)))),
        value=courses["course_title"].iat[11],
        label="기준 강의",
        full_width=True,
        searchable=True,
    )
    course_picker
    return (course_picker,)


@app.cell
def _(course_picker, course_vectors, courses, np):
    _i = course_picker.value
    _sims = course_vectors @ course_vectors[_i]
    _same = (courses["base_title"] == courses["base_title"].iat[_i]).to_numpy()
    _order = [j for j in np.argsort(-_sims) if not _same[j]][:10]
    courses.iloc[_order][["course_title", "platform", "institution"]].assign(
        similarity=(_sims[_order] * 100).round(1)
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## 4. 강의 의미 지도

    768차원 벡터를 PCA로 2차원에 펼친 그림입니다. 가까이 있는 점일수록 언어모델이 "뜻이 비슷하다"고 본 강의입니다.
    색은 2단계 K-Means 군집(k=8)입니다.
    """)
    return


@app.cell
def _(PCA, alt, course_vectors, courses, pd, root_dir):
    _coords = PCA(n_components=2, random_state=42).fit_transform(course_vectors)
    _cluster_path = root_dir / "data" / "hr" / "output" / "text_analysis" / "course_keywords_clusters_k8.csv"
    _clusters = (
        pd.read_csv(_cluster_path).set_index("id")["cluster"].reindex(courses["id"]).astype("Int64").astype(str).to_numpy()
        if _cluster_path.exists()
        else ["-"] * len(courses)
    )
    semantic_map = pd.DataFrame(
        {
            "x": _coords[:, 0],
            "y": _coords[:, 1],
            "stage2_cluster": _clusters,
            "course_title": courses["course_title"],
            "platform": courses["platform"],
        }
    )
    (
        alt.Chart(semantic_map)
        .mark_circle(size=70, opacity=0.75)
        .encode(
            x=alt.X("x:Q", title="PCA 1"),
            y=alt.Y("y:Q", title="PCA 2"),
            color=alt.Color("stage2_cluster:N", title="2단계 군집", scale=alt.Scale(scheme="tableau10")),
            tooltip=["course_title", "platform", "stage2_cluster"],
        )
        .properties(title="언어모델 임베딩 기반 강의 의미 지도", width=720, height=460)
        .interactive()
    )
    return


if __name__ == "__main__":
    app.run()
