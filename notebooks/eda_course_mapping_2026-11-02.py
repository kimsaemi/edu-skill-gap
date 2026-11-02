import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import re
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl

    return Path, alt, json, mo, pl, re


@app.cell
def _(Path, json, mo, re):
    root = Path(__file__).resolve().parent.parent
    dashboard_path = sorted(root.glob("hr_career_platform_v2_*.html"))[-1]
    html_text = dashboard_path.read_text(encoding="utf-8")
    data_start = re.search(r"const DATA = ", html_text).end()
    dashboard_data, _ = json.JSONDecoder().raw_decode(html_text[data_start:])
    mo.md(f"""
    # 역량(업무)별 매핑 강좌 EDA

    분석 기준 파일: `{dashboard_path.name}`

    - 분야 {len(dashboard_data['domains'])}개, 업무 {sum(len(d['tasks']) for d in dashboard_data['domains'])}개, 강좌 {len(dashboard_data['courses']):,}개
    - **업무별 추천 강좌**: 업무마다 입문·실무·심화 3단계에 추천된 강좌
    - **분야 연결 강좌**: 강좌에 붙은 분야 표시(`doms`)
    """)
    return (dashboard_data,)


@app.cell
def _(dashboard_data, pl):
    course_df = pl.DataFrame(
        [
            {
                "course_id": c["id"],
                "title": c["t"],
                "platform": c["plat"],
                "category": c["cat"],
                "price_type": c.get("ct") or "미기재",
                "domain_count": len(c.get("doms", [])),
                "domains": c.get("doms", []),
            }
            for c in dashboard_data["courses"]
        ]
    )
    domain_names = {d["id"]: d["short"] for d in dashboard_data["domains"]}
    category_names = dashboard_data["cats"]
    level_names = ["입문", "실무", "심화"]

    task_rows = []
    for _domain in dashboard_data["domains"]:
        for _task in _domain["tasks"]:
            _levels = _task["rec"]
            _all_ids = {cid for lvl in _levels for cid in lvl}
            task_rows.append(
                {
                    "task_id": _task["id"],
                    "domain": _domain["short"],
                    "task": _task["name"],
                    "stage": _task["stage"],
                    "입문": len(_levels[0]),
                    "실무": len(_levels[1]),
                    "심화": len(_levels[2]),
                    "distinct_courses": len(_all_ids),
                    "review": bool(_task.get("rv")),
                }
            )
    task_df = pl.DataFrame(task_rows)
    return category_names, course_df, domain_names, level_names, task_df


@app.cell
def _(mo):
    mo.md("""
    ## 1. 분야별 강좌 수 (분야에 연결된 강좌)
    """)
    return


@app.cell
def _(alt, course_df, domain_names, pl):
    domain_course_df = (
        course_df.explode("domains")
        .drop_nulls("domains")
        .group_by("domains")
        .agg(pl.len().alias("courses"))
        .with_columns(pl.col("domains").replace_strict(domain_names).alias("domain"))
        .sort("courses")
    )
    alt.Chart(domain_course_df).mark_bar().encode(
        x=alt.X("courses:Q", title="연결된 강좌 수"),
        y=alt.Y("domain:N", sort="-x", title=None),
        color=alt.Color("courses:Q", scale=alt.Scale(scheme="blues"), legend=None),
        tooltip=["domain", "courses"],
    ).properties(title="분야별 연결 강좌 수", height=300, width=520)
    return


@app.cell
def _(mo):
    mo.md("""
    ## 2. 업무(역량)별 추천 강좌 수
    업무마다 서로 다른 강좌가 몇 개 추천됐는지 봅니다. 적을수록 해당 업무를 보완할 강좌가 부족하다는 뜻입니다.
    """)
    return


@app.cell
def _(alt, task_df):
    alt.Chart(task_df).mark_bar().encode(
        x=alt.X("distinct_courses:Q", title="서로 다른 추천 강좌 수"),
        y=alt.Y("task:N", sort="x", title=None, axis=alt.Axis(labelLimit=380)),
        color=alt.Color("domain:N", title="분야"),
        tooltip=["domain", "task", "입문", "실무", "심화", "distinct_courses", "review"],
    ).properties(title="업무별 추천 강좌 수 (적은 순)", height=1500, width=520)
    return


@app.cell
def _(mo, task_df):
    thin_df = task_df.filter(task_df["distinct_courses"] <= 6).sort("distinct_courses")
    mo.vstack(
        [
            mo.md(f"### 강좌가 부족한 업무 (추천 강좌 6개 이하, {thin_df.height}개)"),
            thin_df.select(["domain", "task", "입문", "실무", "심화", "distinct_courses", "review"]),
        ]
    )
    return


@app.cell
def _(alt, level_names, pl, task_df):
    level_df = (
        task_df.group_by("domain")
        .agg([pl.col(name).mean().alias(name) for name in level_names])
        .unpivot(index="domain", variable_name="level", value_name="avg_courses")
    )
    alt.Chart(level_df).mark_rect().encode(
        x=alt.X("level:N", sort=level_names, title="단계"),
        y=alt.Y("domain:N", title=None),
        color=alt.Color("avg_courses:Q", scale=alt.Scale(scheme="yelloworangered"), title="평균 추천 수"),
        tooltip=["domain", "level", alt.Tooltip("avg_courses:Q", format=".1f")],
    ).properties(title="분야 × 단계별 평균 추천 강좌 수", width=260, height=300)
    return


@app.cell
def _(mo):
    mo.md("""
    ## 3. 카테고리별 강좌 수와 부족한 분야
    카테고리(인사 직접 관련·엑셀/문서·AI/데이터·회계/재무·소통·리더십)별로 어느 분야가 얇은지 봅니다.
    """)
    return


@app.cell
def _(alt, category_names, course_df, pl):
    category_df = (
        course_df.group_by("category")
        .agg(pl.len().alias("courses"))
        .with_columns(pl.col("category").replace_strict(category_names).alias("category_name"))
        .sort("courses")
    )
    alt.Chart(category_df).mark_bar().encode(
        x=alt.X("courses:Q", title="강좌 수"),
        y=alt.Y("category_name:N", sort="-x", title=None),
        tooltip=["category_name", "courses"],
    ).properties(title="카테고리별 강좌 수", height=240, width=520)
    return


@app.cell
def _(alt, category_names, course_df, domain_names, pl):
    cross_df = (
        course_df.explode("domains")
        .drop_nulls("domains")
        .group_by(["domains", "category"])
        .agg(pl.len().alias("courses"))
        .with_columns(
            pl.col("domains").replace_strict(domain_names).alias("domain"),
            pl.col("category").replace_strict(category_names).alias("category_name"),
        )
    )
    heat = alt.Chart(cross_df).mark_rect().encode(
        x=alt.X("category_name:N", title="카테고리"),
        y=alt.Y("domain:N", title=None),
        color=alt.Color("courses:Q", scale=alt.Scale(scheme="blues"), title="강좌 수"),
        tooltip=["domain", "category_name", "courses"],
    )
    text = alt.Chart(cross_df).mark_text(fontSize=11).encode(
        x="category_name:N", y="domain:N", text="courses:Q"
    )
    (heat + text).properties(title="분야 × 카테고리 강좌 수 (비어 있는 칸 = 부족)", width=480, height=300)
    return (cross_df,)


@app.cell
def _(category_names, cross_df, domain_names, mo, pl):
    full_grid = pl.DataFrame(
        [
            {"domain": dom_name, "category_name": cat_name}
            for dom_name in domain_names.values()
            for cat_name in category_names.values()
        ]
    )
    shortage_df = (
        full_grid.join(
            cross_df.select(["domain", "category_name", "courses"]),
            on=["domain", "category_name"],
            how="left",
        )
        .with_columns(pl.col("courses").fill_null(0))
        .sort("courses")
        .head(15)
    )
    mo.vstack([mo.md("### 분야 × 카테고리에서 강좌가 가장 적은 15칸"), shortage_df])
    return


@app.cell
def _(mo):
    mo.md("""
    ## 4. 제공 기관·가격 유형별 강좌 수
    """)
    return


@app.cell
def _(alt, course_df, pl):
    platform_df = (
        course_df.group_by("platform").agg(pl.len().alias("courses")).sort("courses")
    )
    platform_chart = alt.Chart(platform_df).mark_bar().encode(
        x=alt.X("courses:Q", title="강좌 수"),
        y=alt.Y("platform:N", sort="-x", title=None),
        tooltip=["platform", "courses"],
    ).properties(title="기관별 강좌 수", height=320, width=420)
    price_df = course_df.group_by("price_type").agg(pl.len().alias("courses"))
    price_chart = alt.Chart(price_df).mark_arc(innerRadius=50).encode(
        theta="courses:Q",
        color=alt.Color("price_type:N", title="가격 유형"),
        tooltip=["price_type", "courses"],
    ).properties(title="가격 유형(free=무료, paid=유료, biz=기업문의, gov=국비)", height=260, width=260)
    platform_chart | price_chart
    return


@app.cell
def _(mo):
    mo.md("""
    ## 5. 자주 추천되는 강좌 (쏠림)
    같은 강좌가 여러 업무에 반복 추천되면 다양성이 떨어집니다.
    """)
    return


@app.cell
def _(course_df, dashboard_data, pl):
    reuse_rows = [
        {"course_id": cid, "task_id": _task["id"]}
        for _domain in dashboard_data["domains"]
        for _task in _domain["tasks"]
        for cid in {c for lvl in _task["rec"] for c in lvl}
    ]
    reuse_df = (
        pl.DataFrame(reuse_rows)
        .group_by("course_id")
        .agg(pl.len().alias("tasks_recommended_for"))
        .join(course_df.select(["course_id", "title", "platform"]), on="course_id")
        .sort("tasks_recommended_for", descending=True)
        .head(15)
    )
    reuse_df
    return


if __name__ == "__main__":
    app.run()
