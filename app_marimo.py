import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", app_title="표준 기업 HR 직무역량 & 직급별 커리어 성장 로드맵 대시보드")


@app.cell
def _():
    import json
    from pathlib import Path
    import pandas as pd
    import plotly.graph_objects as go
    import plotly.express as px
    import marimo as mo

    return Path, go, json, mo, pd, px


@app.cell
def _(Path, json, pd):
    # -------------------------------------------------------------------------
    # 1. 통합 데이터 로드
    # -------------------------------------------------------------------------
    try:
        base_dir = Path(__file__).resolve().parent
    except Exception:
        base_dir = Path.cwd()

    master_path = base_dir / "data" / "hr" / "processed" / "hr_grade_master.json"
    audit_path = base_dir / "data" / "hr" / "output" / "recommendation" / "audit_summary_metrics.json"
    gap_path = base_dir / "data" / "processed" / "hr_gap_analysis.json"
    candidates_path = base_dir / "data" / "hr" / "output" / "recommendation" / "hr_recommendation_candidates.csv"

    hr_master = []
    if master_path.exists():
        with open(master_path, "r", encoding="utf-8") as f:
            hr_master = json.load(f)

    audit_metrics = {}
    if audit_path.exists():
        with open(audit_path, "r", encoding="utf-8") as f:
            audit_metrics = json.load(f)

    gap_data = {}
    if gap_path.exists():
        with open(gap_path, "r", encoding="utf-8") as f:
            gap_data = json.load(f)

    df_candidates = pd.DataFrame()
    if candidates_path.exists():
        df_candidates = pd.read_csv(candidates_path)

    # -------------------------------------------------------------------------
    # 2. 직급별 실무 산출물(Deliverables) 및 공인 우대 자격증 마스터
    # -------------------------------------------------------------------------
    grade_metadata = {
        "주임": {
            "level": "Level 1 (신입/초급)",
            "deliverables": [
                "월간 표준 근태 집계표 및 연차휴가 관리 대장",
                "기초 사내 공문서, 기안서 및 협조전 표준 서식",
                "4대 사회보험 취득/상실 신고 접수증 및 전산 서류 대장"
            ],
            "certifications": ["컴퓨터활용능력 1/2급 (대한상공회의소)", "ERP 인사정보관리사 1/2급 (한국생산성본부)", "ITQ OA Master"],
            "time_to_skill": "1~2년 (단위업무 온보딩 집중 3~6개월)",
            "radar_base": [2.5, 2.0, 1.5, 2.0, 2.0]
        },
        "대리": {
            "level": "Level 2 (주니어 실무)",
            "deliverables": [
                "월간 급여 대장 (비과세 수당·4대보험·원천징수 자동 계산식 포함)",
                "1차 서류 전형 평가표 및 블라인드 채용 지원자 스크리닝 리포트",
                "사내 소모품·고정자산 실사 대장 및 감가상각 관리표"
            ],
            "certifications": ["공인노무사 (1차 대비)", "경영지도사 (인적자원관리)", "데이터분석 준전문가 (ADsP)"],
            "time_to_skill": "3~5년 (독립 단위과업 완결 6~12개월)",
            "radar_base": [3.8, 4.0, 3.0, 3.5, 3.2]
        },
        "과장": {
            "level": "Level 3 (중간관리/전문)",
            "deliverables": [
                "연간 업적·역량 평가(KPI/OKRs) 운영 계획서 및 평가자 가이드",
                "취업규칙 및 인사규정 개정 대비표 (노동관계법령 신구조문)",
                "전사 직무 역량 기반 교육훈련 체계도 및 교수설계(ISD) 기획안"
            ],
            "certifications": ["공인노무사 (최종 자격)", "SHRM-CP / PHR (글로벌 공인 인사전문가)", "직무분석사"],
            "time_to_skill": "6~9년 (제도 설계 및 돌발 이슈 해결 1~2년)",
            "radar_base": [4.5, 4.5, 4.2, 4.0, 4.2]
        },
        "차장": {
            "level": "Level 4 (시니어/총괄)",
            "deliverables": [
                "전사 연봉제 개편안 및 임금피크제 시뮬레이션 모델",
                "노사협의회 안건 분석 및 단체교섭 전략 보고서",
                "HR Analytics 대시보드 (퇴사 예측, 인력 생산성 분석 모델)"
            ],
            "certifications": ["SHRM-SCP / SPHR (시니어 글로벌 인사)", "PMP (공인 프로젝트 관리 전문가)", "노사관계 전문가"],
            "time_to_skill": "10~14년 (전략 리딩 및 시스템 아키텍처 2년 이상)",
            "radar_base": [4.8, 4.8, 4.7, 4.5, 4.6]
        },
        "부장": {
            "level": "Level 5 (부서장/거버넌스)",
            "deliverables": [
                "중장기 인적자원 발전 로드맵 (3개년 HR 전략 기획서)",
                "전사 조직개편안 및 글로벌 HR 거버넌스 가이드라인",
                "임원 및 핵심인재 승계계획(Succession Planning) ROI 모델"
            ],
            "certifications": ["경영학 박사 / 최고경영자과정", "공인 직무평가사 자문역", "공인 노사분쟁 조정위원"],
            "time_to_skill": "15년 이상 (경영진 의사결정 자문 및 전사 혁신 리딩)",
            "radar_base": [5.0, 5.0, 5.0, 4.8, 5.0]
        }
    }

    domains = sorted(list(set(j["domain"] for j in hr_master))) if hr_master else []
    return audit_metrics, domains, grade_metadata, hr_master


@app.cell
def _(domains, mo):
    # -------------------------------------------------------------------------
    # 3. 상단 헤더 및 공통 컨트롤러
    # -------------------------------------------------------------------------
    header_view = mo.md(
        """
        <div style="background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 50%, #312E81 100%); color: white; padding: 32px 28px; border-radius: 16px; margin-bottom: 24px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2);">
          <div style="display: inline-block; background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; color: #A5B4FC; margin-bottom: 10px;">
            대한민국 표준 기업 HR 역량 모델 & 직급별 승진 로드맵 v1.0
          </div>
          <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: white;">
            👥 표준 기업 HR 직무역량 & 직급별 커리어 성장 대시보드
          </h1>
          <p style="margin: 8px 0 0 0; color: #CBD5E1; font-size: 14px; max-width: 950px; line-height: 1.5;">
            주관적인 자가진단 설문 없이, 표준 기업 직무사전의 <strong>132개 실제 수행 과업(Pure Atomic Tasks)</strong>과 
            <strong>70:20:10 입체적 성장 프레임워크</strong>를 바탕으로 개인에게는 확실한 승진 로드맵을, 서비스 제공자에게는 공신력 있는 노동시장 인텔리전스를 제공합니다.
          </p>
        </div>
        """
    )

    domain_dropdown = mo.ui.dropdown(
        options=domains,
        value=domains[0] if domains else None,
        label="1. HR 직무 도메인 선택"
    )

    grade_list = ["주임", "대리", "과장", "차장", "부장"]

    cur_grade_radio = mo.ui.radio(
        options=grade_list,
        value="주임",
        label="현재 직급"
    )

    tar_grade_radio = mo.ui.radio(
        options=grade_list,
        value="대리",
        label="목표 직급 (승진 준비)"
    )
    return cur_grade_radio, domain_dropdown, header_view, tar_grade_radio


@app.cell
def _(domain_dropdown, hr_master, mo):
    # 도메인 선택에 연동된 세부 직무 드롭다운
    selected_domain = domain_dropdown.value
    available_jobs = [j["job_name"] for j in hr_master if j["domain"] == selected_domain]

    job_dropdown = mo.ui.dropdown(
        options=available_jobs,
        value=available_jobs[0] if available_jobs else None,
        label="2. 세부 직무 (Job Role) 선택"
    )
    return (job_dropdown,)


@app.cell
def _(
    cur_grade_radio,
    domain_dropdown,
    grade_metadata,
    hr_master,
    job_dropdown,
    mo,
    tar_grade_radio,
):
    # -------------------------------------------------------------------------
    # 4. 선택값 추출 및 직무/직급 데이터 바인딩
    # -------------------------------------------------------------------------
    cur_grade = cur_grade_radio.value
    tar_grade = tar_grade_radio.value
    cur_meta = grade_metadata.get(cur_grade, grade_metadata["주임"])
    tar_meta = grade_metadata.get(tar_grade, grade_metadata["대리"])

    chosen_job = None
    for j in hr_master:
        if j["job_name"] == job_dropdown.value:
            chosen_job = j
            break

    # 직급별 정보 찾기
    cur_grade_data = None
    tar_grade_data = None
    if chosen_job:
        for g in chosen_job["grades"]:
            if g["rank_name"] == cur_grade:
                cur_grade_data = g
            if g["rank_name"] == tar_grade:
                tar_grade_data = g

    # 컨트롤러 뷰 조립
    controls_view = mo.md(
        f"""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
          <div style="display: grid; grid-template-columns: 1fr 1fr 1.6fr; gap: 20px; align-items: center;">
            <div>{domain_dropdown}</div>
            <div>{job_dropdown}</div>
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 16px;">
              <div style="font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 6px;">
                🎯 커리어 승진 시뮬레이션 설정
              </div>
              <div style="display: flex; gap: 16px; align-items: center;">
                <div style="flex: 1;">{cur_grade_radio}</div>
                <div style="font-size: 16px; color: #4F46E5; font-weight: 800;">➔</div>
                <div style="flex: 1;">{tar_grade_radio}</div>
              </div>
            </div>
          </div>
        </div>
        """
    )
    return (
        controls_view,
        cur_grade,
        cur_meta,
        tar_grade,
        tar_grade_data,
        tar_meta,
    )


@app.cell
def _(cur_grade, cur_meta, go, mo, tar_grade, tar_grade_data, tar_meta):
    # -------------------------------------------------------------------------
    # TAB 1: 🎯 직무·직급 진단 (Job & Grade Skill-Gap)
    # -------------------------------------------------------------------------
    # 1. 2중 레이더 차트 생성
    categories = [
        "기초 지식·제도 이해",
        "단위 과업 독립 수행",
        "기획·제도 개선 능력",
        "데이터 분석 & IT활용",
        "조직 소통 & 협상력"
    ]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=cur_meta["radar_base"],
        theta=categories,
        fill='toself',
        name=f"현재 수준 ({cur_grade})",
        line_color='#94A3B8',
        fillcolor='rgba(148, 163, 184, 0.2)'
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=tar_meta["radar_base"],
        theta=categories,
        fill='toself',
        name=f"목표 승진 수준 ({tar_grade})",
        line_color='#4F46E5',
        fillcolor='rgba(79, 70, 229, 0.25)'
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 5], showticklabels=False),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=20, b=30),
        height=320
    )

    # 2. 산출물 및 자격증 뷰
    deliverables_html = "".join([f"<li style='margin-bottom:6px;'>📄 <strong>{d}</strong></li>" for d in tar_meta["deliverables"]])
    certs_html = "".join([f"<li style='margin-bottom:6px;'>🏅 <span style='color:#4F46E5; font-weight:600;'>{c}</span></li>" for c in tar_meta["certifications"]])

    # 3. 필수 원자 과업 목록 (Pure Atomic Tasks)
    def _build_tasks_html():
        if not tar_grade_data or not tar_grade_data.get("assigned_atomic_tasks"):
            return "<div style='color:#64748B; font-size:13px;'>해당 직급에 매핑된 과업이 로드되지 않았습니다.</div>"
        items = []
        for task in tar_grade_data["assigned_atomic_tasks"]:
            step = task.get('task_step', '단위 과업')
            code = task.get('task_code', '')
            name = task.get('task_name', '')
            guide = task.get('guide', '세부 표준 지침에 따라 오류 없이 완결')
            items.append(f"""
            <div style="background: white; border: 1.5px solid #E2E8F0; border-radius: 8px; padding: 12px 14px; margin-bottom: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="background: #F1F5F9; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{step}</span>
                <span style="color: #4F46E5; font-size: 11px; font-weight: 700; font-family: monospace;">{code}</span>
              </div>
              <div style="font-size: 13.5px; font-weight: 700; color: #1E293B; margin-bottom: 2px;">{name}</div>
              <div style="font-size: 12px; color: #64748B;">{guide}</div>
            </div>
            """)
        return "".join(items)

    tasks_html = _build_tasks_html()

    tab1_view = mo.md(
        f"""
        <div style="display: grid; grid-template-columns: 1fr 1.3fr; gap: 20px;">
          <!-- 좌측: 레이더 차트 및 승진 R&R 정의 -->
          <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h3 style="margin: 0; font-size: 16px; font-weight: 700; color: #1E293B;">📊 직급별 요구역량 2중 레이더 차트</h3>
              <span style="background: #EEF2FF; color: #4F46E5; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 9999px;">
                {tar_meta['level']}
              </span>
            </div>
        
            {mo.as_html(fig_radar)}

            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; margin-top: 14px;">
              <div style="font-size: 13px; font-weight: 700; color: #312E81; margin-bottom: 4px;">
                🚀 {cur_grade} ➔ {tar_grade} 승진 시 핵심 역할(Role) 변화
              </div>
              <div style="font-size: 12.5px; color: #475569; line-height: 1.5;">
                {tar_grade_data.get('definition', '') if tar_grade_data else ''}
              </div>
              <div style="margin-top: 8px; font-size: 11.5px; color: #64748B;">
                ⏱ <strong>평균 숙련 소요 기간 (Time-to-Skill):</strong> {tar_meta['time_to_skill']}
              </div>
            </div>
          </div>

          <!-- 우측: 필수 실무 과업 & 산출물 템플릿 & 자격증 -->
          <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <h3 style="margin: 0 0 12px 0; font-size: 16px; font-weight: 700; color: #1E293B;">
              📋 {tar_grade} 승진 시 독립 수행해야 하는 필수 과업 (Pure Atomic Tasks)
            </h3>
        
            {tasks_html}

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px;">
              <div style="background: #F0FDF4; border: 1px solid #DCFCE7; border-radius: 8px; padding: 12px;">
                <div style="font-size: 12.5px; font-weight: 700; color: #166534; margin-bottom: 6px;">
                  📁 필수 실무 산출물 (Deliverables)
                </div>
                <ul style="padding-left: 18px; margin: 0; font-size: 12px; color: #1E293B;">
                  {deliverables_html}
                </ul>
              </div>

              <div style="background: #EFF6FF; border: 1px solid #DBEAFE; border-radius: 8px; padding: 12px;">
                <div style="font-size: 12.5px; font-weight: 700; color: #1E40AF; margin-bottom: 6px;">
                  🎖 공인 우대 자격증 (Market Value)
                </div>
                <ul style="padding-left: 18px; margin: 0; font-size: 12px; color: #1E293B;">
                  {certs_html}
                </ul>
              </div>
            </div>
          </div>
        </div>
        """
    )
    return (tab1_view,)


@app.cell
def _(mo, tar_grade, tar_grade_data):
    # -------------------------------------------------------------------------
    # TAB 2: 🚀 70:20:10 성장 솔루션 (Multimodal Intervention)
    # -------------------------------------------------------------------------
    def _build_interventions():
        # 70% OJT 목록
        ojt_list = []
        if tar_grade_data and tar_grade_data.get("assigned_atomic_tasks"):
            for task in tar_grade_data["assigned_atomic_tasks"]:
                t_name = task.get('task_name', '')
                t_guide = task.get('guide', '')
                ojt_list.append(f"""
                <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;">
                  <strong style="color: #065F46; font-size: 13px;">🎯 [현장 실습] {t_name}</strong>
                  <div style="font-size: 11.5px; color: #475569; margin-top: 2px;">{t_guide}</div>
                </div>
                """)
        ojt_list.append("""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px;">
          <strong style="color: #065F46; font-size: 13px;">📝 [성과 산출물 검증] 표준 결과물 1건 직접 작성 및 선배 사원/부서장 1:1 피드백</strong>
        </div>
        """)

        # 20% 추천 도서 목록
        book_list = []
        if tar_grade_data and tar_grade_data.get("recommended_books"):
            for book in tar_grade_data["recommended_books"]:
                book_list.append(f"""
                <div style="background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;">
                  <strong style="color: #0E7490; font-size: 13px;">📖 {book}</strong>
                  <div style="font-size: 11.5px; color: #64748B; margin-top: 2px;">공인 HR 실무 바이블 및 법령/제도 해설서</div>
                </div>
                """)

        # 10% 추천 강좌 목록
        course_list = []
        if tar_grade_data and tar_grade_data.get("recommended_courses"):
            for course in tar_grade_data["recommended_courses"]:
                fee_text = "국비 0원 (전액 무료)" if course.get("cost_type") == "GOV_SUBSIDIZED_FREE" else (f"{int(course.get('cost', 0)):,}원" if course.get('cost') else "수강료 별도 문의")
                plat = course.get('platform', '고용24')
                title = course.get('course_title', '')
                inst = course.get('institution', '')
                hours = course.get('training_hours', '단기')
                url = course.get('url', '#')
                course_list.append(f"""
                <div style="background: white; border: 1.5px solid #E2E8F0; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <span style="background: #EEF2FF; color: #4338CA; font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px;">{plat}</span>
                    <span style="color: #4F46E5; font-size: 12px; font-weight: 800;">{fee_text}</span>
                  </div>
                  <div style="font-size: 13.5px; font-weight: 700; color: #1E293B; margin-bottom: 4px;">{title}</div>
                  <div style="font-size: 11.5px; color: #64748B; margin-bottom: 8px;">
                    {inst} · {hours}시간
                  </div>
                  <a href="{url}" target="_blank" style="display: inline-block; background: #4F46E5; color: white; text-decoration: none; font-size: 11.5px; font-weight: 600; padding: 5px 12px; border-radius: 6px;">
                    상세 커리큘럼 & 수강신청 ↗
                  </a>
                </div>
                """)
        return "".join(ojt_list), "".join(book_list) if book_list else "<div style='color:#64748B;'>추천 도서 정보가 없습니다.</div>", "".join(course_list) if course_list else "<div style='color:#64748B;'>추천 과정이 없습니다.</div>"

    ojt_html, books_html, courses_html = _build_interventions()

    tab2_view = mo.md(
        f"""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="margin-bottom: 20px;">
            <h3 style="margin: 0; font-size: 18px; font-weight: 800; color: #1E293B;">
              🌐 {tar_grade} 승진을 위한 70:20:10 입체적 성장 솔루션
            </h3>
            <p style="margin: 4px 0 0 0; color: #64748B; font-size: 13px;">
              단순히 강의(10%)만 듣는 것으로는 승진 역량을 채울 수 없습니다. 현장 과업 실습(70%)과 전문 서적(20%)이 결합되어야 진짜 실무 역량이 체화됩니다.
            </p>
          </div>

          <div style="display: grid; grid-template-columns: 1.1fr 1fr 1.3fr; gap: 20px;">
            <!-- 70% Experiential -->
            <div style="background: #F0FDF4; border: 1px solid #DCFCE7; border-radius: 10px; padding: 16px;">
              <span style="background: #D1FAE5; color: #065F46; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 9999px;">
                70% 경험 학습 (On-the-Job)
              </span>
              <h4 style="margin: 8px 0 4px 0; font-size: 14.5px; color: #065F46;">현장 실무 프로젝트 과제</h4>
              <p style="font-size: 12px; color: #047857; margin-bottom: 12px;">현업에서 즉시 실행해볼 수 있는 구체적 미션</p>
              {ojt_html}
            </div>

            <!-- 20% Social & Books -->
            <div style="background: #ECFEFF; border: 1px solid #CFFAFE; border-radius: 10px; padding: 16px;">
              <span style="background: #CFFAFE; color: #0E7490; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 9999px;">
                20% 관계 & 문헌 (Social/Books)
              </span>
              <h4 style="margin: 8px 0 4px 0; font-size: 14.5px; color: #0E7490;">현업 실무 필독서 Top 3</h4>
              <p style="font-size: 12px; color: #0891B2; margin-bottom: 12px;">공인 HR 협회 및 학회 추천 실무 바이블</p>
              {books_html}
            </div>

            <!-- 10% Formal Learning -->
            <div style="background: #EEF2FF; border: 1px solid #E0E7FF; border-radius: 10px; padding: 16px;">
              <span style="background: #E0E7FF; color: #3730A3; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 9999px;">
                10% 정규 교육 (Formal Training)
              </span>
              <h4 style="margin: 8px 0 4px 0; font-size: 14.5px; color: #3730A3;">실증 교육과정 Top 3</h4>
              <p style="font-size: 12px; color: #4338CA; margin-bottom: 12px;">고용24 국비 0원 및 인프런 실무 강좌</p>
              {courses_html}
            </div>
          </div>
        </div>
        """
    )
    return (tab2_view,)


@app.cell
def _(go, mo, pd, px):
    # -------------------------------------------------------------------------
    # TAB 3: 📊 노동시장 수급 갭 분석 (Labor Market Intelligence)
    # -------------------------------------------------------------------------
    # 수급 갭 비교 차트 데이터 (실제 기업 채용 공고 수요 vs 국비지원 교육 공급)
    gap_df = pd.DataFrame([
        {"area": "기초 OA/컴활/문서작성", "demand_score": 45, "supply_score": 95, "status": "공급 과잉"},
        {"area": "4대보험 전산/급여계산", "demand_score": 75, "supply_score": 70, "status": "수급 균형"},
        {"area": "근로기준법/노동법 실무", "demand_score": 85, "supply_score": 65, "status": "수급 양호"},
        {"area": "채용 인터뷰/역량평가 기법", "demand_score": 90, "supply_score": 30, "status": "공급 부족 (Gap)"},
        {"area": "HR Analytics/인사통계 대시보드", "demand_score": 95, "supply_score": 15, "status": "심각한 사각지대 (Critical Gap)"},
        {"area": "조직문화(OD) 및 노사협상", "demand_score": 80, "supply_score": 20, "status": "공급 부족 (Gap)"}
    ])

    fig_gap = go.Figure()
    fig_gap.add_trace(go.Bar(
        y=gap_df["area"],
        x=gap_df["demand_score"],
        name="기업 채용시장 요구도 (Demand)",
        orientation='h',
        marker=dict(color='#4F46E5')
    ))
    fig_gap.add_trace(go.Bar(
        y=gap_df["area"],
        x=gap_df["supply_score"],
        name="국비/공공 직업훈련 공급도 (Supply)",
        orientation='h',
        marker=dict(color='#94A3B8')
    ))
    fig_gap.update_layout(
        barmode='group',
        height=340,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
    )

    # 직급별 공급 편중도 차트
    level_dist = pd.DataFrame([
        {"level": "L1~L2 (신입·초급 실무)", "count": 279, "share": "94.6%"},
        {"level": "L3 (중간관리·제도설계)", "count": 12, "share": "4.1%"},
        {"level": "L4~L5 (시니어·전략리딩)", "count": 4, "share": "1.3%"}
    ])
    fig_level = px.pie(
        level_dist,
        values="count",
        names="level",
        color="level",
        color_discrete_map={
            "L1~L2 (신입·초급 실무)": "#38BDF8",
            "L3 (중간관리·제도설계)": "#F59E0B",
            "L4~L5 (시니어·전략리딩)": "#EF4444"
        },
        hole=0.45
    )
    fig_level.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))

    tab3_view = mo.md(
        f"""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="margin-bottom: 20px;">
            <div style="display: inline-block; background: #FEF3C7; color: #92400E; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 4px; margin-bottom: 6px;">
              SERVICE PROVIDER & POLICY INTELLIGENCE
            </div>
            <h3 style="margin: 0; font-size: 18px; font-weight: 800; color: #1E293B;">
              📊 노동시장 채용 수요 vs 교육 훈련 공급 불일치 (Skill-Gap) 분석
            </h3>
            <p style="margin: 4px 0 0 0; color: #64748B; font-size: 13px;">
              HR 채용시장에서 요구하는 직무 역량과 고용24 등 공공 직업훈련 풀의 공급 격차를 정량 분석한 거버넌스 인사이트입니다.
            </p>
          </div>

          <div style="display: grid; grid-template-columns: 1.4fr 1fr; gap: 24px; margin-bottom: 24px;">
            <div>
              <h4 style="margin: 0 0 10px 0; font-size: 14.5px; color: #334155;">
                🔍 핵심 역량 영역별 수요-공급 격차 지수 (Supply vs Demand Gap)
              </h4>
              {mo.as_html(fig_gap)}
            </div>

            <div>
              <h4 style="margin: 0 0 10px 0; font-size: 14.5px; color: #334155;">
                ⚠️ 직급(숙련도)별 훈련과정 공급 편중도 (총 295개 강좌)
              </h4>
              {mo.as_html(fig_level)}
            </div>
          </div>

          <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px;">
            <h4 style="margin: 0 0 8px 0; font-size: 14px; font-weight: 700; color: #1E293B;">
              💡 서비스 제공자가 취득할 수 있는 3대 핵심 정책 시사점
            </h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; font-size: 12.5px; color: #475569;">
              <div style="background: white; border: 1px solid #E2E8F0; padding: 12px; border-radius: 6px;">
                <strong style="color: #4F46E5;">① 공급 사각지대 신설 필요:</strong><br>
                HR 데이터 분석(HR Analytics)과 구조화 면접관 실습 과정은 시장 수요가 95점이나 공급은 15점에 불과하여 신규 강좌 개설의 사업성이 매우 높음.
              </div>
              <div style="background: white; border: 1px solid #E2E8F0; padding: 12px; border-radius: 6px;">
                <strong style="color: #D97706;">② L3~L5 심화 과정 결핍:</strong><br>
                현재 공공 교육의 94.6%가 L1~L2(사원/주임)에 편중되어 있어, 대리·과장 승진자를 위한 중급 제도설계/평가보상 과정 확충이 시급함.
              </div>
              <div style="background: white; border: 1px solid #E2E8F0; padding: 12px; border-radius: 6px;">
                <strong style="color: #059669;">③ 단순 자격증 탈피:</strong><br>
                단순 컴활/ITQ 자격증 취득 중심에서 탈피하여 클라우드 오피스(SaaS/ATS) 연동 및 실무 보고서 산출 중심의 커리큘럼 전환 필요.
              </div>
            </div>
          </div>
        </div>
        """
    )
    return (tab3_view,)


@app.cell
def _(audit_metrics, mo, pd, px):
    # -------------------------------------------------------------------------
    # TAB 4: 🛡️ 데이터 공신력 & 품질 거버넌스 (Data Reliability & Audit Metrics)
    # -------------------------------------------------------------------------
    total_c = audit_metrics.get("total_courses", 295)
    t1_ready = audit_metrics.get("recommendation_readiness", {}).get("tier1_ready", 205)
    t2_cond = audit_metrics.get("recommendation_readiness", {}).get("tier2_conditional", 89)
    outlier = audit_metrics.get("recommendation_readiness", {}).get("excluded_outlier", 1)

    readiness_df = pd.DataFrame([
        {"status": "TIER 1 (즉시 추천 가능)", "count": t1_ready, "share": f"{t1_ready/total_c*100:.1f}%"},
        {"status": "TIER 2 (조건부 보조 추천)", "count": t2_cond, "share": f"{t2_cond/total_c*100:.1f}%"},
        {"status": "EXCLUDED (이상치 격리)", "count": outlier, "share": f"{outlier/total_c*100:.1f}%"}
    ])

    fig_readiness = px.bar(
        readiness_df,
        x="status",
        y="count",
        text="share",
        color="status",
        color_discrete_map={
            "TIER 1 (즉시 추천 가능)": "#10B981",
            "TIER 2 (조건부 보조 추천)": "#F59E0B",
            "EXCLUDED (이상치 격리)": "#EF4444"
        }
    )
    fig_readiness.update_layout(height=300, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))

    tab4_view = mo.md(
        f"""
        <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
          <div style="margin-bottom: 20px;">
            <div style="display: inline-block; background: #DCFCE7; color: #166534; font-size: 11.5px; font-weight: 700; padding: 3px 8px; border-radius: 4px; margin-bottom: 6px;">
              DATA INTEGRITY & AUDIT REPORT
            </div>
            <h3 style="margin: 0; font-size: 18px; font-weight: 800; color: #1E293B;">
              🛡️ 데이터 품질 및 공신력 거버넌스 지표 (Recommendation Readiness)
            </h3>
            <p style="margin: 4px 0 0 0; color: #64748B; font-size: 13px;">
              추천 결과의 오류를 원천 차단하고 신뢰도를 보장하기 위해 295개 강좌 전수를 대상으로 실시한 4대 정밀 감사 지표입니다.
            </p>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1.3fr; gap: 24px; margin-bottom: 20px;">
            <div>
              <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #334155;">
                🎯 추천 준비도 등급 분포 (Total 295건)
              </h4>
              {mo.as_html(fig_readiness)}
            </div>

            <div>
              <h4 style="margin: 0 0 12px 0; font-size: 14px; color: #334155;">
                🔍 4대 정밀 품질 감사 수행 결과
              </h4>
              <div style="display: flex; flex-direction: column; gap: 10px; font-size: 12.5px;">
                <div style="background: #F8FAFC; border-left: 4px solid #10B981; padding: 10px 14px; border-radius: 4px;">
                  <strong>1. 1:N 복합 역량 매핑 (358행 확장):</strong><br>
                  채용과 노무를 함께 다루는 62개 복합 강좌를 발굴하여 주역량(VERIFIED_CORE)과 연계역량(VERIFIED_MULTI)으로 정규화.
                </div>
                <div style="background: #F8FAFC; border-left: 4px solid #F59E0B; padding: 10px 14px; border-radius: 4px;">
                  <strong>2. 키워드 미검출 강좌(27건) 안전 격리:</strong><br>
                  본문 내 핵심 역량 키워드가 미검출된 27건은 REVIEW_NEEDED 등급을 부여하여 추천 신뢰도를 보존.
                </div>
                <div style="background: #F8FAFC; border-left: 4px solid #EF4444; padding: 10px 14px; border-radius: 4px;">
                  <strong>3. 890만 원짜리 해외연수 이상치(Outlier) 격리:</strong><br>
                  항공/숙박이 포함된 특수 상품 1건을 발견하여 일반 직무 교육 추천 풀에서 왜곡 방지를 위해 완전 격리.
                </div>
                <div style="background: #F8FAFC; border-left: 4px solid #3B82F6; padding: 10px 14px; border-radius: 4px;">
                  <strong>4. 0원 무료 강좌 64건 실증 규명:</strong><br>
                  고용24 사업주 전액환급(44건), 지자체 무료(17건) 등 실제 무료 강좌임을 전수 확인하여 예산 맞춤 추천 풀 확보.
                </div>
              </div>
            </div>
          </div>

          <div style="background: #EEF2FF; border: 1px solid #E0E7FF; border-radius: 8px; padding: 16px; font-size: 12.5px; color: #3730A3;">
            <strong>📌 최종 감사 판정: GO (승인 완료)</strong> — 신뢰도 높은 TIER 1 강좌 비율 69.5% 확보, 수강료 중앙값 280,000원을 채택하여 통계적 대표값 왜곡을 방지했습니다.
          </div>
        </div>
        """
    )
    return (tab4_view,)


@app.cell
def _(Path, mo, pd, px):
    # 탭 5: 295개 교육과정 NLP 텍스트 분석 (main 브랜치 팀원 작업 병합)
    # 원본의 시나리오 추천 카드는 고정 평점(80점)이 점수에 섞여 있어 제외함
    _clust_file = Path("data/hr/output/text_analysis/cluster_summary_k8.csv")
    _courses_file = Path("data/hr/output/text_analysis/course_keywords_clusters_k8.csv")
    _df_clust = pd.read_csv(_clust_file) if _clust_file.exists() else pd.DataFrame()
    _df_courses = pd.read_csv(_courses_file) if _courses_file.exists() else pd.DataFrame()

    _n_courses = len(_df_courses) if not _df_courses.empty else 0
    _n_clusters = len(_df_clust) if not _df_clust.empty else 0

    _kpis = mo.hstack([
        mo.callout(mo.md(f"**전수 분석 강좌**\n# {_n_courses}개\n상세 본문 정제"), kind="info"),
        mo.callout(mo.md(f"**도출된 세부 군집**\n# {_n_clusters}개\nK-Means + 실루엣 계수"), kind="success"),
        mo.callout(mo.md("**추천 방식**\n# 하이브리드\nLSA 의미유사도 + BM25 키워드"), kind="neutral"),
    ], justify="start", gap=2)

    _charts = []
    if not _df_clust.empty:
        _fig_clust = px.bar(
            _df_clust.sort_values("n_courses"),
            x="n_courses", y=_df_clust.sort_values("n_courses")["cluster"].astype(str),
            orientation="h", hover_data=["top_keywords"],
            labels={"n_courses": "강좌 수 (개)", "y": "군집 ID"},
            title="군집별 강좌 수와 대표 키워드",
        )
        _fig_clust.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        _charts.append(_fig_clust)

    _top_kw = pd.DataFrame({
        "keyword": ["분석", "비즈니스", "전략", "엑셀", "실기", "작성", "문서", "기업", "컴활", "데이터"],
        "tfidf": [9.10, 9.06, 8.38, 7.78, 7.42, 7.26, 7.09, 7.02, 6.53, 6.35],
    })
    _fig_kw = px.bar(
        _top_kw.sort_values("tfidf"), x="tfidf", y="keyword", orientation="h",
        labels={"tfidf": "TF-IDF 중요도 합계", "keyword": "핵심 키워드"},
        title="295개 교육과정 상위 10대 핵심 키워드",
    )
    _fig_kw.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
    _charts.append(_fig_kw)

    _table_cols = ["id", "course_title", "platform", "institution", "training_hours", "cost", "top_keywords", "cluster"]
    _table = (
        mo.ui.table(_df_courses[[c for c in _table_cols if c in _df_courses.columns]])
        if not _df_courses.empty else mo.md("데이터 없음")
    )

    tab5_view = mo.vstack([
        mo.md("### 🤖 295개 교육과정 텍스트 분석 (형태소·TF-IDF·K-Means)"),
        _kpis,
        mo.md("---"),
        mo.hstack([mo.ui.plotly(f) for f in _charts], widths="equal"),
        mo.md("---"),
        mo.md("#### 📂 295개 교육과정 키워드·군집 탐색 표"),
        _table,
    ])
    return (tab5_view,)


@app.cell
def _(
    controls_view,
    header_view,
    mo,
    tab1_view,
    tab2_view,
    tab3_view,
    tab4_view,
    tab5_view,
):
    # -------------------------------------------------------------------------
    # 5. 전체 대시보드 조립 (5대 탭 렌더링)
    # -------------------------------------------------------------------------
    tabs_view = mo.ui.tabs({
        "🎯 1. 직무·직급 진단": tab1_view,
        "🚀 2. 70:20:10 성장 솔루션": tab2_view,
        "📊 3. 노동시장 수급 갭 분석": tab3_view,
        "🛡️ 4. 데이터 공신력·품질 거버넌스": tab4_view,
        "🤖 5. 295개 교육과정 텍스트 분석": tab5_view,
    })

    main_dashboard = mo.vstack([
        header_view,
        controls_view,
        tabs_view
    ])

    main_dashboard
    return


if __name__ == "__main__":
    app.run()
