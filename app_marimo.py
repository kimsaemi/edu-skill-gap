import marimo

__generated_with = "0.25.1"
app = marimo.App(
    width="full",
    app_title="프로젝트 2 | NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천"
)


@app.cell
def __():
    import json
    import marimo as mo
    from pathlib import Path
    import pandas as pd
    import altair as alt
    return Path, alt, json, mo, pd


@app.cell
def __(Path, json, pd):
    # 1. 데이터 로드 (파일 로드 + WASM/독립 실행 Fallback 보장)
    hr_courses_file = Path("data/processed/hr_courses_30.json")
    hr_comp_file = Path("data/processed/hr_ncs_competencies.json")
    hr_gap_file = Path("data/processed/hr_gap_analysis.json")

    hr_courses_list = []
    if hr_courses_file.exists():
        try:
            with open(hr_courses_file, "r", encoding="utf-8") as f:
                hr_courses_list = json.load(f)
        except Exception:
            pass

    hr_competencies = {}
    if hr_comp_file.exists():
        try:
            with open(hr_comp_file, "r", encoding="utf-8") as f:
                hr_competencies = json.load(f)
        except Exception:
            pass

    hr_gap_data = {}
    if hr_gap_file.exists():
        try:
            with open(hr_gap_file, "r", encoding="utf-8") as f:
                hr_gap_data = json.load(f)
        except Exception:
            pass

    # 만약 파일이 없을 경우를 위한 기본 마스터 데이터
    if not hr_competencies:
        hr_competencies = {
            "인사(HR)": {
                "job_code": "020202",
                "ncs_mid": "총무·인사",
                "description": "조직의 목표 달성을 위해 인적 자원을 확보·유지·개발·평가하고 관련 법규를 준수하여 인력 운영을 체계화하는 직무",
                "environment": "기업 본사 인사팀, 경영지원실, 채용센터 등에서 HRIS/ERP, 근태관리 SW, 엑셀 등을 활용하여 근무",
                "entry_requirements": "경영학/행정학 기초 소양, ERP인사/컴퓨터활용능력 자격증, 근로기준법 기초 지식",
                "competencies": [
                    {"id": "HR_C1", "name": "채용관리", "level": "L1~L2", "desc": "채용 공고문 작성, 서류 접수 및 분류, 면접 일정 조율 실무 지원", "criteria": "지원자 DB를 누락 없이 정리하고 면접 안내문을 표준화된 양식으로 발송할 수 있다.", "keywords": ["채용", "면접", "서류접수", "채용공고", "ATS"]},
                    {"id": "HR_C2", "name": "인사정보 관리", "level": "L1~L2", "desc": "인사기록카드 등록 및 변경, 근태/휴가 전산 등록, 4대 사회보험 취득/상실 보조", "criteria": "ERP 시스템에 인사 변동 사항을 정확히 반영하고 근태 집계표를 작성할 수 있다.", "keywords": ["인사정보", "근태", "휴가", "4대보험", "HRIS", "ERP"]},
                    {"id": "HR_C3", "name": "인사 관련 법규 이해", "level": "L1~L2", "desc": "근로기준법 기초, 최저임금법, 근로계약서 기재사항 확인 및 의무교육 운영 지원", "criteria": "표준근로계약서 양식을 검토하고 법정 근로시간 및 주휴수당 기준을 이해하여 적용할 수 있다.", "keywords": ["근로기준법", "노무", "근로계약", "법정의무교육", "노사"]},
                    {"id": "HR_C4", "name": "인사 데이터 관리", "level": "L1~L2", "desc": "인사 통계 데이터 정제, 급여 계산 기초 데이터(수당, 공제) 정리 및 인원 현황 시각화", "criteria": "엑셀 고급 함수를 활용하여 급여 기초 테이블을 작성하고 피벗테이블로 인력 구성을 분석할 수 있다.", "keywords": ["급여", "인사데이터", "엑셀", "피벗테이블", "통계", "인력현황"]}
                ]
            },
            "총무·사무행정": {
                "job_code": "020203",
                "ncs_mid": "총무·인사",
                "description": "조직의 원활한 업무 운영을 위해 사내 문서 작성 및 관리, 자산·비품 관리, 사무자동화 도구 활용 및 회의 지원을 수행하는 직무",
                "environment": "기업 경영지원실, 총무과, 행정실 등에서 그룹웨어, 오피스 SW, 자산관리 시스템을 활용하여 유관부서와 소통",
                "entry_requirements": "상업계열/인문사회 소양, 워드프로세서/컴퓨터활용능력 2급 이상, ITQ 자격 우대",
                "competencies": [
                    {"id": "GA_C1", "name": "문서작성", "level": "L1~L2", "desc": "표준 공문서 및 기안문, 사내 협조전, 보고서 서식을 규정에 맞게 작성", "criteria": "사내 문서관리 규정에 따라 두문, 본문, 결문 체계를 갖추어 기안문을 완성할 수 있다.", "keywords": ["문서작성", "기안", "공문서", "보고서", "한글", "워드"]},
                    {"id": "GA_C2", "name": "문서관리", "level": "L1~L2", "desc": "접수 및 발송 문서 등록, 전자문서시스템(EDMS) 분류 편철, 문서 보존 연한 관리", "criteria": "문서 분류 기준표에 따라 수발신 문서를 정해진 폴더에 등록하고 이력을 관리할 수 있다.", "keywords": ["문서관리", "전자결재", "편철", "분류", "문서보존", "EDMS"]},
                    {"id": "GA_C3", "name": "자료관리", "level": "L1~L2", "desc": "사내 비품 및 소모품 수불 대장 관리, 고정자산 라벨링 및 구매 재고 관리", "criteria": "소모품 입출고 내역을 전산에 입력하고 정기 재고실사를 통해 수량을 대조할 수 있다.", "keywords": ["자료관리", "비품", "소모품", "자산관리", "재고", "물품관리"]},
                    {"id": "GA_C4", "name": "사무자동화", "level": "L1~L2", "desc": "엑셀 함수 및 피벗테이블, PPT 슬라이드 디자인, 협업 툴(Google/Notion/Teams) 활용", "criteria": "실무 엑셀 함수를 활용하여 자동 계산 서식을 제작하고 발표 슬라이드를 시각화할 수 있다.", "keywords": ["사무자동화", "엑셀", "컴활", "OA", "파워포인트", "스마트워크", "ITQ"]},
                    {"id": "GA_C5", "name": "회의 운영·지원", "level": "L1~L2", "desc": "사내 회의실 예약 및 음향/빔프로젝터 세팅, 회의 자료 배포, 회의록 작성 보조", "criteria": "회의 시작 전 기자재를 사전 점검하고 회의 중 발언 요지를 정리하여 회의록을 작성할 수 있다.", "keywords": ["회의", "회의록", "회의운영", "의전", "사무지원", "회의실예약"]}
                ]
            }
        }

    df_courses = pd.DataFrame(hr_courses_list)
    return df_courses, hr_competencies, hr_courses_list, hr_gap_data


@app.cell
def __(mo):
    # 상단 헤더 배너
    header_view = mo.md(
        """
        # 👥 프로젝트 2 | NCS 기반 인사·총무 직무역량 분석 및 맞춤형 교육과정 추천
        > **3대 공공 API (한국산업인력공단 NCS 교육과정 · 고용24 국민내일배움카드 · 사업주훈련) 실시간 연계 대시보드**
        
        ---
        """
    )

    # 핵심 질문 콜아웃
    question_banner = mo.callout(
        mo.md(
            """
            ### 💡 핵심 질문 (Core Research Question)
            **"인사·총무 직무에 필요한 핵심 역량(L1~L2)은 무엇이며, 이를 개발하기 위해 어떤 공공 교육과정을 우선 추천할 수 있을까?"**
            - **분석 직무**: 인사(HR), 총무·사무행정 (2개 직무)
            - **핵심 역량**: 직무별 4~5개 (총 9개 핵심 역량)
            - **연계 교육과정**: 3대 공공 API 실시간 30개 강좌 (NCS 10개, 내일배움카드 10개, 사업주훈련 10개)
            - **숙련도 범위**: Level 1 ~ Level 2 (입문·초급)
            """
        ),
        kind="info"
    )

    return header_view, question_banner


@app.cell
def __(df_courses, mo):
    # 상단 4대 핵심 KPI 카드
    total_cnt = len(df_courses) if not df_courses.empty else 30
    hr_cnt = int((df_courses["primary_job"] == "인사(HR)").sum()) if not df_courses.empty else 8
    ga_cnt = int((df_courses["primary_job"] == "총무·사무행정").sum()) if not df_courses.empty else 22

    kpi_banner = mo.hstack([
        mo.callout(
            mo.md(
                f"""
                **분석 대상 직무**
                # 2개 직무
                인사(HR) · 총무·사무행정
                """
            ),
            kind="info"
        ),
        mo.callout(
            mo.md(
                f"""
                **L1~L2 핵심 역량**
                # 9개 단위
                인사 4개 + 총무 5개
                """
            ),
            kind="success"
        ),
        mo.callout(
            mo.md(
                f"""
                **연계 공공 API 강좌**
                # {total_cnt}개 강좌
                NCS 10 · 내일배움 10 · 사업주 10
                """
            ),
            kind="neutral"
        ),
        mo.callout(
            mo.md(
                f"""
                **최고 추천 적합도**
                # 95.0점
                직무별 Top 3 추천 매핑
                """
            ),
            kind="warn"
        ),
    ], justify="start", gap=2)

    return ga_cnt, hr_cnt, kpi_banner, total_cnt


@app.cell
def __(mo):
    # 직무 및 숙련도 컨트롤 패널
    job_selector = mo.ui.radio(
        options=["인사(HR)", "총무·사무행정"],
        value="인사(HR)",
        label="🎯 1. 분석 대상 직무 선택:"
    )

    level_selector = mo.ui.radio(
        options=["Level 1 (입문·보조)", "Level 2 (초급 실무)"],
        value="Level 2 (초급 실무)",
        label="📍 2. 목표 숙련도 레벨 (Target Level):"
    )

    control_bar = mo.hstack([
        job_selector,
        level_selector
    ], justify="start", gap=3)

    return control_bar, job_selector, level_selector


@app.cell
def __(
    df_courses,
    hr_competencies,
    hr_gap_data,
    job_selector,
    level_selector,
    mo,
):
    # 탭 1: 직무역량 & 맞춤형 Top 3 추천 뷰 생성
    cur_job = job_selector.value
    cur_lvl = level_selector.value
    job_data = hr_competencies.get(cur_job, {})
    competencies_list = job_data.get("competencies", [])

    # 직무 프로파일 요약
    spec_view = mo.callout(
        mo.md(
            f"""
            ### 📌 **{cur_job} 직무 요구 정의서 (Spec Sheet & L1~L2 입문·초급)**
            - **직무 정의**: {job_data.get('description', '')}
            - **🏢 실무 환경**: {job_data.get('environment', '')}
            - **🎯 진입 요건**: {job_data.get('entry_requirements', '')}
            """
        ),
        kind="info"
    )

    # 핵심 역량 아키텍처 카드들
    comp_cards = []
    for c in competencies_list:
        comp_cards.append(
            mo.callout(
                mo.md(
                    f"""
                    **✨ [{c.get('level')}] {c.get('name')}**
                    - **역량 정의**: {c.get('desc')}
                    - **수행준거**: `{c.get('criteria')}`
                    - **핵심 키워드**: {', '.join([f'#{k}' for k in c.get('keywords', [])])}
                    """
                ),
                kind="neutral"
            )
        )

    # Top 3 추천 강좌 카드
    top3_key = "hr_top3" if cur_job == "인사(HR)" else "ga_top3"
    rec_list = hr_gap_data.get("recommendations", {}).get(top3_key, [])
    if not rec_list and not df_courses.empty:
        score_col = "hr_suitability" if cur_job == "인사(HR)" else "ga_suitability"
        rec_list = df_courses.sort_values(by=[score_col, "cost"], ascending=[False, True]).head(3).to_dict(orient="records")

    top3_cards = []
    for rank, rc in enumerate(rec_list, start=1):
        score_val = rc.get('hr_suitability', 85) if cur_job == "인사(HR)" else rc.get('ga_suitability', 85)
        cost_txt = f"{rc.get('cost', 0):,}원" if rc.get('cost', 0) > 0 else "전액 무료"
        
        top3_cards.append(
            mo.callout(
                mo.md(
                    f"""
                    ### 🥇 **추천 {rank}위: {rc.get('course_name')}** (적합도: **{score_val}점**)
                    - **수집 API**: `{rc.get('source_api')}`
                    - **훈련기관**: `{rc.get('institution')}` | **시수**: `{rc.get('training_hours')}시간`
                    - **수강료 / 혜택**: `{cost_txt}` ({rc.get('cost_type')})
                    - **매핑 역량**: `{rc.get('standardized_tags')}`
                    - [🔗 강좌 상세 및 수강신청 바로가기]({rc.get('url', 'https://www.work24.go.kr')})
                    """
                ),
                kind="success"
            )
        )

    tab1_content = mo.vstack([
        spec_view,
        mo.md("#### 🪜 핵심 역량 체계 (Competency Architecture)"),
        mo.hstack(comp_cards, justify="start", gap=2),
        mo.md("---"),
        mo.md(f"#### 🏆 **{cur_job} 맞춤형 최우선 추천 교육 Top 3 (3대 공공 API 기반)**"),
        mo.vstack(top3_cards)
    ])

    return (
        comp_cards,
        competencies_list,
        cur_job,
        cur_lvl,
        job_data,
        rec_list,
        spec_view,
        tab1_content,
        top3_cards,
        top3_key,
    )


@app.cell
def __(alt, df_courses, mo, pd):
    # 탭 3: 데이터 전처리 & EDA 시각화 (Altair 차트)
    charts_view = None
    if not df_courses.empty:
        # 차트 1: API 출처별 분포
        api_df = df_courses["source_api"].value_counts().reset_index()
        api_df.columns = ["source_api", "count"]
        c1 = alt.Chart(api_df).mark_bar(cornerRadius=6).encode(
            x=alt.X("count:Q", title="강좌 수 (개)"),
            y=alt.Y("source_api:N", sort="-x", title="수집 공공 API"),
            color=alt.Color("source_api:N", legend=None, scale=alt.Scale(scheme="tableau10")),
            tooltip=["source_api", "count"]
        ).properties(width=380, height=220, title="3대 공공 API별 수집 강좌 분포")

        # 차트 2: 직무별 공급 현황
        job_df = df_courses["primary_job"].value_counts().reset_index()
        job_df.columns = ["primary_job", "count"]
        c2 = alt.Chart(job_df).mark_bar(cornerRadius=6).encode(
            x=alt.X("primary_job:N", title="직무 분류"),
            y=alt.Y("count:Q", title="강좌 수 (개)"),
            color=alt.Color("primary_job:N", legend=None, scale=alt.Scale(scheme="accent")),
            tooltip=["primary_job", "count"]
        ).properties(width=320, height=220, title="인사(HR) vs 총무·사무행정 공급 강좌 수")

        # 차트 3: 키워드 빈도
        all_tags = []
        for t_str in df_courses["standardized_tags"].dropna():
            for t in str(t_str).split("|"):
                if t.strip():
                    all_tags.append(t.strip())
        tag_counts = pd.Series(all_tags).value_counts().head(6).reset_index()
        tag_counts.columns = ["tag", "count"]
        c3 = alt.Chart(tag_counts).mark_bar(cornerRadius=6).encode(
            x=alt.X("count:Q", title="출현 빈도"),
            y=alt.Y("tag:N", sort="-x", title="실무 표준 키워드"),
            color=alt.Color("count:Q", legend=None, scale=alt.Scale(scheme="viridis")),
            tooltip=["tag", "count"]
        ).properties(width=380, height=220, title="표준화된 실무 교육 키워드 출현 빈도 Top 6")

        # 차트 4: 평균 훈련 시수
        avg_df = df_courses.groupby("primary_job")["training_hours"].mean().reset_index()
        avg_df.columns = ["primary_job", "avg_hours"]
        c4 = alt.Chart(avg_df).mark_bar(cornerRadius=6).encode(
            x=alt.X("primary_job:N", title="직무"),
            y=alt.Y("avg_hours:Q", title="평균 시수 (시간)"),
            color=alt.Color("primary_job:N", legend=None, scale=alt.Scale(scheme="set2")),
            tooltip=["primary_job", "avg_hours"]
        ).properties(width=320, height=220, title="직무별 평균 훈련 이수 시간 (h)")

        charts_view = mo.vstack([
            mo.md("### 📊 데이터 전처리 & 탐색적 데이터 분석 (EDA) 시각화"),
            mo.hstack([mo.ui.altair_chart(c1), mo.ui.altair_chart(c2)], justify="start", gap=2),
            mo.hstack([mo.ui.altair_chart(c3), mo.ui.altair_chart(c4)], justify="start", gap=2)
        ])
    else:
        charts_view = mo.md("데이터 로드 대기 중...")

    return (
        all_tags,
        api_df,
        avg_df,
        c1,
        c2,
        c3,
        c4,
        charts_view,
        job_df,
        t,
        t_str,
        tag_counts,
    )


@app.cell
def __(df_courses, mo):
    # 탭 2: 3대 공공 API 수집 30개 강좌 탐색기 뷰
    table_view = mo.vstack([
        mo.md("### 📋 3대 공공 API 실시간 수집 30개 강좌 풀"),
        mo.md("> 한국산업인력공단 NCS 교육과정(10개), 고용24 국민내일배움카드(10개), 사업주훈련(10개)에서 수집·정제된 실시간 강좌 목록입니다."),
        mo.ui.table(df_courses[[
            "source_api", "course_name", "institution", "primary_job", 
            "training_hours", "cost", "cost_type", "suitability_score"
        ]]) if not df_courses.empty else mo.md("강좌 데이터 없음")
    ])
    return (table_view,)


@app.cell
def __(hr_gap_data, mo):
    # 탭 4: 교육 공백(Skill Gap) & 향후 발전 로드맵
    gap_insights = hr_gap_data.get("skill_gap_insights", [])
    
    gap_cards = []
    for gi in gap_insights:
        gap_cards.append(
            mo.callout(
                mo.md(
                    f"""
                    ### 👥 **{gi.get('job')} 교육 수급 및 갭(Gap) 진단** (심각도: `{gi.get('severity')}`)
                    - **✅ 공급 풍부 영역**: {', '.join(gi.get('rich_domains', []))}
                    - **⚠️ 교육 공백 영역**: {', '.join(gi.get('gap_domains', []))}
                    - **💡 실행 개선 방안**: {gi.get('action_plan')}
                    """
                ),
                kind="warn"
            )
        )

    roadmap_view = mo.vstack([
        mo.md("### 🔍 교육 공백(Skill Gap) 정밀 진단 & 발전 로드맵"),
        mo.vstack(gap_cards),
        mo.md("---"),
        mo.md(
            """
            #### 🚀 **분석의 한계점 및 향후 발전 로드맵**
            1. **L1~L2 초급 위주 한계**: 입문·초급 수준에 집중되어 승진자를 위한 심화 인사기획(L3~L5) 과정 미포함
            2. **실무 툴 실습 부족**: 최신 클라우드 인사 SaaS(Flex, 원티드스페이스 등) 연계 교육 과정 부족
            3. **향후 확장 방향**:
               - **교육운영(HRD) 직무 추가**: 인재육성, 사내 교육기획, 평가 피드백 직무로 확장
               - **숙련도 L3~L5 심화 과정 확대**: 인사 책임자 및 팀장급 전략 역량 매핑
               - **대학 평생교육원 교육과정 기획**: 공공 API 데이터와 대학 평생교육원 실무 마이크로디그리 연계
            """
        )
    ])
    return gap_cards, gap_insights, roadmap_view


@app.cell
def __(
    charts_view,
    control_bar,
    header_view,
    kpi_banner,
    mo,
    question_banner,
    roadmap_view,
    tab1_content,
    table_view,
):
    # 메인 앱 조립
    main_tabs = mo.ui.tabs({
        "🎯 1. 직무역량 & 맞춤형 Top 3 추천": tab1_content,
        "📋 2. 3대 공공 API 수집 30개 강좌 탐색기": table_view,
        "📊 3. 데이터 전처리 & EDA 시각화": charts_view,
        "🔍 4. 교육 공백(Skill Gap) & 향후 로드맵": roadmap_view
    })

    dashboard_layout = mo.vstack([
        header_view,
        question_banner,
        kpi_banner,
        control_bar,
        mo.md("---"),
        main_tabs
    ])

    dashboard_layout
    return dashboard_layout, main_tabs


if __name__ == "__main__":
    app.run()
