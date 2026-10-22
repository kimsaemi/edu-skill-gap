import marimo

__generated_with = "0.25.1"
app = marimo.App(
    width="full",
    app_title="🌱 직업적 페르소나 발견 & 신규자(Lv1) 온보딩·승급 내비게이터"
)


@app.cell
def __():
    import json
    from pathlib import Path
    import altair as alt
    import marimo as mo
    import pandas as pd
    return Path, alt, json, mo, pd


@app.cell
def __(Path, json, pd):
    # 1. 아카이브 대시보드 데이터셋 계승 및 Fallback 보장 (읽기 전용 참조)
    hr_courses_file = Path("data/processed/hr_courses_30.json")
    hr_comp_file = Path("data/processed/hr_ncs_competencies.json")
    hr_gap_file = Path("data/processed/hr_gap_analysis.json")
    courses_295_file = Path("data/hr/output/text_analysis/course_keywords_clusters_k8.csv")

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

    if not hr_competencies:
        hr_competencies = {
            "인사(HR)": {
                "job_code": "020202",
                "description": "인적 자원을 확보·유지·개발·평가하고 관련 법규를 준수하여 인력 운영을 체계화하는 직무",
                "competencies": [
                    {"id": "HR_C1", "name": "채용관리", "level": "L1~L2", "desc": "채용 공고문 작성, 서류 접수 및 분류, 면접 일정 조율 실무 지원"},
                    {"id": "HR_C2", "name": "인사정보 관리", "level": "L1~L2", "desc": "인사기록카드 등록 및 변경, 근태/휴가 전산 등록, 4대보험 취득/상실 보조"},
                    {"id": "HR_C3", "name": "인사 관련 법규 이해", "level": "L1~L2", "desc": "근로기준법 기초, 최저임금법, 근로계약서 기재사항 확인 및 의무교육 운영"},
                    {"id": "HR_C4", "name": "인사 데이터 관리", "level": "L1~L2", "desc": "인사 통계 데이터 정제, 급여 계산 기초 데이터(수당, 공제) 정리 및 시각화"}
                ]
            },
            "총무·사무행정": {
                "job_code": "020203",
                "description": "사내 문서 작성 및 관리, 자산·비품 관리, 사무자동화 도구 활용 및 회의 지원을 수행하는 직무",
                "competencies": [
                    {"id": "GA_C1", "name": "문서작성", "level": "L1~L2", "desc": "표준 공문서 및 기안문, 사내 협조전, 보고서 서식을 규정에 맞게 작성"},
                    {"id": "GA_C2", "name": "문서관리", "level": "L1~L2", "desc": "접수 및 발송 문서 등록, 전자문서시스템(EDMS) 분류 편철, 보존 연한 관리"},
                    {"id": "GA_C3", "name": "자료관리", "level": "L1~L2", "desc": "사내 비품 및 소모품 수불 대장 관리, 고정자산 라벨링 및 구매 재고 관리"},
                    {"id": "GA_C4", "name": "사무자동화", "level": "L1~L2", "desc": "엑셀 함수 및 피벗테이블, PPT 슬라이드 디자인, 협업 툴 활용"},
                    {"id": "GA_C5", "name": "회의 운영·지원", "level": "L1~L2", "desc": "회의실 예약 및 장비 세팅, 회의 자료 배포, 회의록 작성 보조"}
                ]
            }
        }

    df_courses = pd.DataFrame(hr_courses_list)
    df_courses_295 = pd.read_csv(courses_295_file) if courses_295_file.exists() else pd.DataFrame()

    return df_courses, df_courses_295, hr_competencies, hr_courses_list, hr_gap_data


@app.cell
def __(mo):
    # 상단 미니멀 헤더 & 직무 선택기
    job_selector = mo.ui.radio(
        options=["인사(HR)", "총무·사무행정"],
        value="인사(HR)",
        label="🎯 **대상 직무 선택:**"
    )

    header_bar = mo.hstack([
        mo.md("## 🌱 **직무 역량 & 온보딩·승급 내비게이터**"),
        job_selector
    ], justify="space-between", align="center")

    return header_bar, job_selector


@app.cell
def __(mo):
    # Tab 1: 5대 직무 행동 표준(Standard) 멀티 선택 위젯
    persona_standards = mo.ui.multiselect(
        options=[
            "⚡ 마감 완결 (납기 준수·끝까지 책임)",
            "🔍 꼼꼼 품질 (오차 제로·철저 검수)",
            "🤝 소통 협업 (경청 배려·팀워크)",
            "🧭 자기 주도 (간섭 없이 대안 찾기)",
            "📐 체계 정리 (서식 템플릿·자료 정리)"
        ],
        value=[
            "⚡ 마감 완결 (납기 준수·끝까지 책임)",
            "🔍 꼼꼼 품질 (오차 제로·철저 검수)"
        ],
        label="📌 **내가 지향하는 업무 표준 (원하는 항목을 복수 선택하세요):**"
    )

    return (persona_standards,)


@app.cell
def __(job_selector, mo, persona_standards):
    # Tab 1 뷰: 5대 표준 가이드 & 복수 선택 기반 맞춤 캐릭터 합성
    _cur_job = job_selector.value

    # 5대 표준 사전
    _standards_dict = {
        "⚡ 마감 완결": {
            "name": "마감 완결",
            "tag": "#납기엄수",
            "phrase": "약속한 기한 내 완결",
            "tip": "50% 시점 초안 공유(Rough Draft)로 마감 리스크 제거",
            "comp": "ETH-01 성실·책임감, EXE-02 실행·완결성"
        },
        "🔍 꼼꼼 품질": {
            "name": "꼼꼼 품질",
            "tag": "#오차제로",
            "phrase": "오차 없는 철저한 품질 검증",
            "tip": "제출 전 '외관-숫자-수신자' 3단계 자체 검수 루틴",
            "comp": "PRO-02 직무도구, COM-01 명확한 문서작성"
        },
        "🤝 소통 협업": {
            "name": "소통 협업",
            "tag": "#팀워크",
            "phrase": "동료를 배려하는 원활한 협업",
            "tip": "회의 시 '상대 의견 1줄 요약 후 내 생각 덧붙이기'",
            "comp": "COM-02 경청·질문, COM-03 상호지원"
        },
        "🧭 자기 주도": {
            "name": "자기 주도",
            "tag": "#MinimumSupervision",
            "phrase": "지시 없는 능동적 대안 제시",
            "tip": "질문 전 '혼자 30분 고민 + 시도한 2가지 대안' 정리",
            "comp": "EXE-03 원인분석, LRN-03 자기개발"
        },
        "📐 체계 정리": {
            "name": "체계 정리",
            "tag": "#템플릿화",
            "phrase": "누구나 쓰기 편한 서식 표준화",
            "tip": "자주 쓰는 파일 네이밍 및 폴더 트리 표준화",
            "comp": "EXE-04 프로세스개선, LRN-01 디지털도구"
        }
    }

    # 선택된 표준 파싱
    _selected_keys = [k for k in _standards_dict.keys() if any(k in s for s in persona_standards.value)]

    if not _selected_keys:
        _archetype_title = "🌱 성장 준비형 실무자 (Aspiring Rookie)"
        _archetype_sub = "상단에서 내가 지향하는 표준 스타일을 1개 이상 선택해보세요."
        _badge_kind = "neutral"
        _pledge = "팀장님, 저는 팀의 기본 규범을 성실히 익히며 성장하는 팀원이 되겠습니다."
        _tips_text = "- 위의 표준 스타일을 선택하시면 맞춤 실천 팁이 생성됩니다."
        _comps_text = "직무 공통 기본 소양"
        _tags_text = "`#성장지향`"
    elif len(_selected_keys) == 1:
        _k = _selected_keys[0]
        _titles = {
            "⚡ 마감 완결": "⚡ 완결형 실행가 (The Focused Finisher)",
            "🔍 꼼꼼 품질": "🔍 정밀형 분석가 (The Precision Analyst)",
            "🤝 소통 협업": "🤝 협력형 조율가 (The Synergy Facilitator)",
            "🧭 자기 주도": "🧭 개척형 문제해결사 (The Agile Pioneer)",
            "📐 체계 정리": "📐 체계형 설계가 (The System Architect)"
        }
        _archetype_title = _titles[_k]
        _archetype_sub = f"{_standards_dict[_k]['phrase']}에 가장 강점을 지닌 단일 집중형 프로페셔널"
        _badge_kind = "info"
        _pledge = f"팀장님, 저는 우리 팀에서 **'{_standards_dict[_k]['phrase']}'**을(를) 확실히 책임지는 동료로 성장하겠습니다."
        _tips_text = f"- **{_k}**: {_standards_dict[_k]['tip']}"
        _comps_text = _standards_dict[_k]['comp']
        _tags_text = f"`{_standards_dict[_k]['tag']}`"
    elif len(_selected_keys) == 2:
        _k1, _k2 = _selected_keys[0], _selected_keys[1]
        _duo_map = {
            ("⚡ 마감 완결", "🔍 꼼꼼 품질"): "🛡️ 신뢰의 무결점 실행가 (The Meticulous Finisher)",
            ("⚡ 마감 완결", "🤝 소통 협업"): "🤝 든든한 협업 완결자 (The Collaborative Deliverer)",
            ("⚡ 마감 완결", "🧭 자기 주도"): "🚀 돌파형 액션 리더 (The Autonomous Achiever)",
            ("⚡ 마감 완결", "📐 체계 정리"): "📦 프로세스 완결 마스터 (The Systematic Finisher)",
            ("🔍 꼼꼼 품질", "🤝 소통 협업"): "💡 사려 깊은 품질 조율가 (The Diligent Facilitator)",
            ("🔍 꼼꼼 품질", "🧭 자기 주도"): "🔬 자립형 품질 분석가 (The Independent Analyst)",
            ("🔍 꼼꼼 품질", "📐 체계 정리"): "🏛️ 무결점 시스템 설계가 (The Precision Architect)",
            ("🤝 소통 협업", "🧭 자기 주도"): "🧭 능동적 팀 해결사 (The Proactive Collaborator)",
            ("🤝 소통 협업", "📐 체계 정리"): "🗂️ 조직의 프로세스 코디네이터 (The Team Organizer)",
            ("🧭 자기 주도", "📐 체계 정리"): "📐 자율형 구조화 혁신가 (The Self-Driving Architect)"
        }
        _pair_key = (_k1, _k2) if (_k1, _k2) in _duo_map else (_k2, _k1)
        _archetype_title = _duo_map.get(_pair_key, f"✨ {_standards_dict[_k1]['name']} & {_standards_dict[_k2]['name']} 융합형 인재")
        _archetype_sub = f"'{_standards_dict[_k1]['phrase']}'과(와) '{_standards_dict[_k2]['phrase']}'의 시너지를 내는 복합형 인재"
        _badge_kind = "success"
        _pledge = f"팀장님, 저는 우리 팀에서 **'{_standards_dict[_k1]['phrase']}'**과(와) **'{_standards_dict[_k2]['phrase']}'**을(를) 겸비한 든든한 동료가 되겠습니다."
        _tips_text = f"- **{_k1}**: {_standards_dict[_k1]['tip']}\n- **{_k2}**: {_standards_dict[_k2]['tip']}"
        _comps_text = f"{_standards_dict[_k1]['comp']}, {_standards_dict[_k2]['comp']}"
        _tags_text = f"`{_standards_dict[_k1]['tag']}` `{_standards_dict[_k2]['tag']}`"
    else:
        _archetype_title = "🌟 다재다능 올라운더 (The Versatile All-Rounder)"
        _names = [_standards_dict[k]["name"] for k in _selected_keys]
        _archetype_sub = f"3가지 이상의 핵심 표준({', '.join(_names)})을 고루 발휘하는 균형 잡힌 실무자"
        _badge_kind = "warn"
        _pledge = f"팀장님, 저는 우리 팀에서 **'{', '.join([_standards_dict[k]['phrase'] for k in _selected_keys])}'**을(를) 조화롭게 발휘하는 올라운더로 인정받겠습니다."
        _tips_text = "\n".join([f"- **{k}**: {_standards_dict[k]['tip']}" for k in _selected_keys])
        _comps_text = ", ".join([_standards_dict[k]['comp'] for k in _selected_keys])
        _tags_text = " ".join([f"`{_standards_dict[k]['tag']}`" for k in _selected_keys])

    _action_sheet = f"""============================================================
[나의 온보딩 1장 실행 카드 (My Onboarding Action Sheet)]
- 대상 직무: {_cur_job}
- 지향 캐릭터: {_archetype_title}
- 핵심 표준: {', '.join([_standards_dict[k]['name'] for k in _selected_keys]) if _selected_keys else '기본 소양'}
------------------------------------------------------------
1. [내일 출근 시 선언할 한 줄 (사수/팀장 공유용)]
   "{_pledge}"

2. [이번 주 내가 사수에게 물어볼 핵심 질문 1가지]
   "선배님, 저희 팀에서 주니어가 가장 빈번하게 저지르는 실수는 무엇이며,
    제가 이를 사전에 방지하려면 어떤 검수 루틴을 챙겨야 할까요?"

3. [이번 달(Day 30)까지 반드시 달성할 승급 자격 요건]
   - 팀 표준 도구(ERP/사무서식) 단독 조작 숙달 (사수 개입 최소화)
   - 마감 일정 지연 0건 및 결함 반려율 제로 달성
============================================================
"""

    _what_now_box = mo.callout(
        mo.vstack([
            mo.md("### 🚀 **그래서 내일부터 당장 무엇을 해야 하나요? (Action Plan)**"),
            mo.md(
                f"""
                페르소나와 표준을 확인하셨다면, **내일부터 다음 3가지를 순서대로 실천**하세요:

                1. **🗣️ Step 1. 선언하기 (내일 첫 1:1 티타임/면담)**
                   - 사수나 팀장님께 위의 **`1줄 선언문`**을 전달하세요.  
                   - *"선배님, 저는 이번 온보딩 동안 특히 **{', '.join([_standards_dict[k]['name'] for k in _selected_keys]) if _selected_keys else '기본기'}**에 집중해서 1인분을 해내고 싶습니다."*라고 말해두면, 선배가 그 기준에 맞추어 맞춤형 피드백을 줍니다.

                2. **⚙️ Step 2. 데일리 루틴 장치 걸기 (오늘 퇴근 전)**
                   - 내 모니터 메모지나 캘린더에 내 페르소나 맞춤 **'1일 1규칙'**을 걸어두세요:
{_tips_text}

                3. **🗺️ Step 3. 승급 로드맵과 연결하기 (지금 바로)**
                   - 상단 **`🗓️ 2. First 90 Days 스프린트`** 탭을 클릭하여 이번 달(Day 1~30) 달성해야 할 구체적 마일스톤을 확인하세요.
                   - 상단 **`🎖️ 3. 공식 승급 체크리스트`** 탭에서 독립 실무자(Lv2) 승급을 위해 내가 채워야 할 5대 필수 요건을 점검하세요!
                """
            ),
            mo.accordion({
                "📄 나만의 온보딩 1장 실행 카드 (사수 면담/복사용 텍스트 열기)": mo.md(f"```text\n{_action_sheet}\n```")
            })
        ]),
        kind="info"
    )

    tab1_content = mo.vstack([
        mo.md("### 📌 직무 행동 5대 표준 (Standard Framework)"),
        mo.md(
            """
            | 표준 항목 | 핵심 정의 (Short & Clear) | 행동 지표 |
            | :--- | :--- | :--- |
            | **⚡ 마감 완결 (Execution)** | 약속한 납기 엄수 & 끝까지 책임 완결 | 지연 없는 마감, 중간보고 습관 |
            | **🔍 꼼꼼 품질 (Quality)** | 오타·수치 오차 없는 철저한 자체 검수 | 자체 체크리스트 확인, 반려율 0% |
            | **🤝 소통 협업 (Collaboration)** | 경청과 배려로 시너지를 내는 팀워크 | 상대 맥락 파악, 질문과 공유 |
            | **🧭 자기 주도 (Autonomy)** | 간섭 없이 스스로 대안 모색 (Min. Supervision) | 30분 고민 후 대안을 들고 질문 |
            | **📐 체계 정리 (Organization)** | 파일과 서식을 재사용 가능한 템플릿화 | 폴더 정리, 문서 서식 표준화 |
            """
        ),
        mo.md("---"),
        persona_standards,
        mo.md("---"),
        mo.callout(
            mo.vstack([
                mo.md(f"### 🎉 합성된 나의 페르소나: **{_archetype_title}**"),
                mo.md(f"> *{_archetype_sub}*"),
                mo.md(f"**🏷️ 핵심 강점 태그**: {_tags_text}"),
                mo.md(f"**💡 핵심 실천 가이드**:\n{_tips_text}"),
                mo.md(f"**📚 연계 추천 직무 기본기**: {_comps_text}")
            ]),
            kind=_badge_kind
        ),
        mo.callout(
            mo.md(
                f"""
                #### 🗣️ **사수/팀장 1:1 온보딩 면담용 1줄 선언문 (Identity Pledge)**
                > *"{_pledge}"*
                *(위 문장을 복사하여 1:1 온보딩 면담 시 나의 업무 지향점으로 공유해보세요)*
                """
            ),
            kind="neutral"
        ),
        mo.md("---"),
        _what_now_box
    ])

    return (tab1_content,)


@app.cell
def __(job_selector, mo):
    # Tab 2: 조직 가이드라인 & First 90 Days 스프린트
    _cur_job = job_selector.value

    _rules_box = mo.callout(
        mo.md(
            """
            ### 🧭 **조직이 Lv1에게 기대하는 4대 기본 행동 (Core Baseline)**
            1. **규범과 약속 (Rule)**: 근태, 기본 사규, 개인정보 보안, 일정 약속 엄수 (`VAL-01`)
            2. **소통과 질문 (Communication)**: 30분 룰(혼자 30분 고민 후 질문), 50% 시점 중간보고 습관 (`COL-01`)
            3. **사내 도구 익히기 (Tools)**: 메신저, 문서 도구, 직무 표준 시스템(ERP/엑셀) 기본 조작 (`PRO-02`)
            4. **완결 습관 (Finishing)**: 마감 기한 준수, 자체 검수 체크리스트 확인 후 제출 (`EXE-02`)
            """
        ),
        kind="info"
    )

    if _cur_job == "인사(HR)":
        _sprints = [
            mo.callout(
                mo.md(
                    """
                    #### 🚩 **Day 1 ~ 30: 적응과 관찰**
                    - 취업규칙/사규 정독 및 용어집 숙지
                    - 개인정보보호 서약 및 ERP 인사시스템 조회 권한 획득
                    - 모르는 법률 용어는 사수에게 질문 템플릿으로 확인
                    """
                ),
                kind="neutral"
            ),
            mo.callout(
                mo.md(
                    """
                    #### 🏃 **Day 31 ~ 60: 부분 수행과 피드백**
                    - 월간 근태/휴가 신청 집계 보조
                    - 4대보험 취득/상실 신고 대장 1회 단독 작성
                    - 작성 서류에 대해 사수에게 "틀리기 쉬운 포인트 1가지" 코칭 수렴
                    """
                ),
                kind="warn"
            ),
            mo.callout(
                mo.md(
                    """
                    #### 🎓 **Day 61 ~ 90: 1인분 독립 완결**
                    - 채용 서류 접수 및 전형단계 분류 단독 진행
                    - 급여 기초 테이블 자체 검수 및 오류 0건 달성
                    - 멘토의 `Lv1 온보딩 졸업 Sign-off` 서명 획득
                    """
                ),
                kind="success"
            )
        ]
    else:
        _sprints = [
            mo.callout(
                mo.md(
                    """
                    #### 🚩 **Day 1 ~ 30: 적응과 관찰**
                    - 사내 공문서/기안문 표준 서식집 숙지
                    - 비품 창고 수불 대장 및 그룹웨어 결재선 파악
                    - 기안문 작성 전 이전 우수 기안문 3건 검색
                    """
                ),
                kind="neutral"
            ),
            mo.callout(
                mo.md(
                    """
                    #### 🏃 **Day 31 ~ 60: 부분 수행과 피드백**
                    - 표준 공문서 및 협조전 두괄식 1회 작성
                    - 팀 정기회의 빔프로젝터/음향 세팅 및 회의록 공유
                    - 회의록 공유 후 팀장님께 "불필요한 문장 1개" 피드백 요청
                    """
                ),
                kind="warn"
            ),
            mo.callout(
                mo.md(
                    """
                    #### 🎓 **Day 61 ~ 90: 1인분 독립 완결**
                    - 월말 비품 수불 대장 실사 대조 및 재고 실사
                    - 소모품 견적 비교 및 발주 품의 단독 완결
                    - 문서 반려 0건 달성 후 `Lv1 온보딩 졸업 Sign-off` 서명 획득
                    """
                ),
                kind="success"
            )
        ]

    tab2_content = mo.vstack([
        mo.md(f"## 🗓️ {_cur_job} First 90 Days 온보딩 스프린트 로드맵"),
        mo.md("> 신규 입사자가 3개월 안에 방황하지 않고 독립적인 1인분(L2) 실무자로 자리 잡기 위한 타임라인입니다."),
        _rules_box,
        mo.md("---"),
        mo.md("### ⏱️ **월별 단계별 달성 마일스톤**"),
        mo.hstack(_sprints, gap=2)
    ])

    return (tab2_content,)


@app.cell
def __(mo):
    # Tab 3: 승급(Level-Up) 자격 검증 체크리스트 컨트롤
    promo_check_1 = mo.ui.checkbox(
        label="[필수 1. 기본 규범 준수] 사규, 보안 수칙, 근태 규정 100% 준수 (결격·징계 0건)",
        value=True
    )
    promo_check_2 = mo.ui.checkbox(
        label="[필수 2. 단독 업무 완결] 표준 매뉴얼 기반 1인분 정기 루틴 업무 단독 무오류 완결 (사수 개입 없이 1회 성공)",
        value=False
    )
    promo_check_3 = mo.ui.checkbox(
        label="[필수 3. 기한 준수 & 중간보고] 지시받은 업무 기한 100% 준수 및 진척도 50% 시점 중간보고 습관 증빙",
        value=True
    )
    promo_check_4 = mo.ui.checkbox(
        label="[필수 4. 직무 교육과정 이수] 직무 연계 공공 추천 교육(또는 사내 필수 OJT) 40시간 이상 수료증 획득",
        value=False
    )
    promo_check_5 = mo.ui.checkbox(
        label="[최종 5. 멘토/사수 승인] 사수/팀장과의 1:1 역량 관찰 평가 통과 및 온보딩 졸업 Sign-off 서명 획득",
        value=False
    )

    return promo_check_1, promo_check_2, promo_check_3, promo_check_4, promo_check_5


@app.cell
def __(
    job_selector,
    mo,
    promo_check_1,
    promo_check_2,
    promo_check_3,
    promo_check_4,
    promo_check_5,
):
    # Tab 3 뷰: 실시간 승급 판정 & 게이지 & 공식 심사 신청서
    _cur_job = job_selector.value
    _target_stage = "🌱 Lv1 ➡️ Lv2 (독립 실무자 승급 & 1인분 안착)"

    _checks = [
        promo_check_1.value,
        promo_check_2.value,
        promo_check_3.value,
        promo_check_4.value,
        promo_check_5.value
    ]
    _pass_count = sum(_checks)
    _progress_pct = int((_pass_count / 5) * 100)
    _bar_filled = "■" * _pass_count
    _bar_empty = "□" * (5 - _pass_count)
    _progress_bar_text = f"[{_bar_filled}{_bar_empty}] {_progress_pct}% ({_pass_count}/5 필수 요건 충족)"

    if _pass_count == 5:
        _result_card = mo.callout(
            mo.md(
                f"""
                ### 🎉 **승급 자격 요건 100% 충족 완료! (승급 자격 획득)**
                - **심사 대상**: **{_cur_job}** | **목표**: **{_target_stage}**
                - **진척도**: `{_progress_bar_text}`
                - **최종 판정**: **PASS (공식 승급 심사 신청 가능)**
                - **안내**: 하단의 `[공식 승급 심사 신청서]`를 복사하여 팀장 및 인사팀에 제출하세요!
                """
            ),
            kind="success"
        )
    else:
        _result_card = mo.callout(
            mo.md(
                f"""
                ### ⏳ **승급 심사 요건 준비 진행 중 ({_pass_count}/5 완료)**
                - **심사 대상**: **{_cur_job}** | **목표**: **{_target_stage}**
                - **진척도**: `{_progress_bar_text}`
                - **최종 판정**: **IN PROGRESS (미충족 요건 {5 - _pass_count}건 남음)**
                - **안내**: 아직 완료되지 않은 필수 승급 기준을 달성한 후 체크박스를 활성화하세요.
                """
            ),
            kind="warn"
        )

    _application_doc = f"""
============================================================
           [공식 승급(Level-Up) 자격 심사 신청서]
============================================================
1. 신청인 정보
   - 성명: 본인 (신규/주니어 구성원)
   - 소속 직무: {_cur_job}
   - 신청 승급 단계: {_target_stage}
   - 신청 일자: 2026-10-17

2. 5대 필수 승급 요건 검증 결과 ({_pass_count}/5 충족):
   [1] 사규·보안·근태 100% 준수 (결격 0건): {'[V] 충족 완료' if promo_check_1.value else '[ ] 미충족'}
   [2] 표준 매뉴얼 기반 업무 단독 완결: {'[V] 충족 완료' if promo_check_2.value else '[ ] 미충족'}
   [3] 기한 준수 및 50% 시점 중간보고: {'[V] 충족 완료' if promo_check_3.value else '[ ] 미충족'}
   [4] 직무 연계 공공 추천 교육 수료: {'[V] 충족 완료' if promo_check_4.value else '[ ] 미충족'}
   [5] 사수/팀장 1:1 관찰평가 서명: {'[V] 충족 완료' if promo_check_5.value else '[ ] 미충족'}

3. 종합 승급 심사 의견:
   - 판정: {'★ 정규 승급 심사 적격 (QUALIFIED FOR PROMOTION)' if _pass_count == 5 else f'보완 진행 중 ({5 - _pass_count}개 요건 미비)'}
============================================================
"""

    tab3_content = mo.vstack([
        mo.md("## 🎖️ 공식 승급(Level-Up) 자격 검증 체크리스트 & 실시간 판정"),
        mo.md("> Lv1 온보딩의 최종 목표는 1인분 독립 실무자(Lv2)로 승급하는 것입니다. 5대 필수 요건을 직접 체크하여 승급 자격을 판정받으세요."),
        mo.callout(
            mo.vstack([
                mo.md("#### 📋 **5대 필수 승급 요건 체크리스트**"),
                promo_check_1,
                promo_check_2,
                promo_check_3,
                promo_check_4,
                promo_check_5
            ]),
            kind="neutral"
        ),
        _result_card,
        mo.accordion({
            "📄 공식 승급 심사 신청서(Sign-off Report) 템플릿 열기": mo.md(f"```text\n{_application_doc}\n```")
        })
    ])

    return (tab3_content,)


@app.cell
def __(mo):
    # Tab 4: 역량 자가진단 슬라이더 위젯들
    slider_s1 = mo.ui.slider(start=1, stop=5, step=1, value=2, label="1. 기초 규정 및 사규 준수 (VAL-01)")
    slider_s2 = mo.ui.slider(start=1, stop=5, step=1, value=1, label="2. 직무 도구 및 ERP/시스템 조작 (PRO-02)")
    slider_s3 = mo.ui.slider(start=1, stop=5, step=1, value=3, label="3. 명확한 질문 및 중간보고 (COL-01)")
    slider_s4 = mo.ui.slider(start=1, stop=5, step=1, value=2, label="4. 마감 기한 준수 및 완결 습관 (EXE-02)")
    return slider_s1, slider_s2, slider_s3, slider_s4


@app.cell
def __(alt, job_selector, mo, pd, slider_s1, slider_s2, slider_s3, slider_s4):
    # Tab 4 뷰: 스킬 갭(Skill Gap) 진단 및 Altair 시각화
    _cur_job = job_selector.value
    _names = ["1. 규정/사규 준수", "2. 도구/시스템 조작", "3. 질문/중간보고", "4. 마감/완결 습관"]
    _u_scores = [slider_s1.value, slider_s2.value, slider_s3.value, slider_s4.value]
    _t_scores = [4, 4, 4, 4]

    _records = []
    for _n, _u, _t in zip(_names, _u_scores, _t_scores):
        _records.append({"역량": _n, "점수": _t, "구분": "조직 기대 수준 (Target 4.0)"})
        _records.append({"역량": _n, "점수": _u, "구분": "나의 현재 수준 (Self-Check)"})

    _df_chart = pd.DataFrame(_records)

    _chart = (
        alt.Chart(_df_chart)
        .mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("역량:N", title="기본 역량 항목", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("점수:Q", title="숙련도 점수 (1~5)", scale=alt.Scale(domain=[0, 5])),
            color=alt.Color(
                "구분:N",
                scale=alt.Scale(
                    domain=["조직 기대 수준 (Target 4.0)", "나의 현재 수준 (Self-Check)"],
                    range=["#2563EB", "#F97316"]
                ),
                legend=alt.Legend(title="구분", orient="top")
            ),
            xOffset="구분:N",
            tooltip=[alt.Tooltip("역량:N"), alt.Tooltip("구분:N"), alt.Tooltip("점수:Q")]
        )
        .properties(width=520, height=250, title=f"📊 {_cur_job} 조직 기대치 vs 나의 현재 수준 스킬 갭")
    )

    _gaps = [_t - _u for _u, _t in zip(_u_scores, _t_scores)]
    _max_idx = int(pd.Series(_gaps).idxmax())
    _top_comp = _names[_max_idx]
    _top_gap = _gaps[_max_idx]

    _gap_alert = mo.callout(
        mo.md(
            f"""
            ### 🚨 **자가진단 결과: 최우선 보완 필요 기본기**
            - **1순위 집중 역량**: **{_top_comp}** (격차: `-{_top_gap}점`)
            - **실행 권고**: 현재 수준({_u_scores[_max_idx]}점)에서 독립 실무자(4점)에 안착하기 위해 5번 탭의 70:20:10 실천 플랜을 적용해보세요!
            """
        ),
        kind="warn" if _top_gap > 0 else "success"
    )

    tab4_content = mo.vstack([
        mo.md("## 📊 직무 기본 역량 자가진단 & 스킬 갭(Gap) 측정"),
        mo.md("> 나의 현재 수준을 조절하면, 독립 실무자 기준(4.0)과의 격차가 실시간 계산되어 시각화됩니다."),
        mo.hstack([
            mo.vstack([slider_s1, slider_s2, slider_s3, slider_s4]),
            mo.ui.altair_chart(_chart)
        ], gap=3),
        _gap_alert
    ])

    return (tab4_content,)


@app.cell
def __(mo):
    # Tab 5: 70:20:10 실천 플래너 드롭다운 위젯
    action_dropdown = mo.ui.dropdown(
        options=[
            "인사 관련 법규 이해 (인사)",
            "채용관리 (인사)",
            "인사정보 관리 (인사)",
            "인사 데이터 관리 (인사)",
            "문서작성 (총무)",
            "문서관리 (총무)",
            "자료관리 (총무)",
            "사무자동화 (총무)",
            "회의 운영·지원 (총무)"
        ],
        value="인사 관련 법규 이해 (인사)",
        label="🎯 **집중 실천할 역량 선택:**"
    )
    return (action_dropdown,)


@app.cell
def __(action_dropdown, mo):
    # Tab 5 뷰: 70:20:10 실천 플래너
    _action_catalog = {
        "채용관리 (인사)": {
            "70": "채용 지원자 현황 시트에 지원 경로/일자/전형단계를 누락 없이 분류하고, 면접 일정 조율 안내 메일 초안을 작성하여 사수 피드백 받기",
            "20": "'선배님, 서류 전형 분류 시 저희 팀에서 가장 눈여겨보는 비공식 체크포인트나 탈락 기준이 무엇인가요?'",
            "10": "채용 공고문 작성 및 면접 일정 조율 실무 지원 (NCS 02020201)",
            "tags": ["#채용", "#서류접수", "#면접안내", "#ATS"]
        },
        "인사정보 관리 (인사)": {
            "70": "이번 달 입·퇴사자 4대보험 취득/상실 신고 체크리스트를 만들어 전산 등록 전 항목별 대조 1회 완결하기",
            "20": "'근태/휴가 신청 승인 시 예외 처리(병가, 경조사 등) 승인 라인은 어떻게 규정되어 있나요?'",
            "10": "실무자를 위한 인사급여지급 (급여계산+4대보험관리+원천징수)",
            "tags": ["#4대보험", "#근태관리", "#인사기록", "#ERP"]
        },
        "인사 관련 법규 이해 (인사)": {
            "70": "우리 회사 표준근로계약서 양식을 출력하여 근로기준법 필수 기재사항 7가지가 빠짐없이 들어있는지 조항별 형광펜 체크해보기",
            "20": "'선배님, 주휴수당과 연장근로수당 계산 시 우리 회사 취업규칙에서 특별히 주의해야 할 특약 조항이 있나요?'",
            "10": "인사노무 핵심 법규 및 근로계약서 실무 검토 가이드",
            "tags": ["#근로기준법", "#주휴수당", "#근로계약", "#취업규칙"]
        },
        "인사 데이터 관리 (인사)": {
            "70": "인사 원천 데이터에서 피벗 테이블을 활용해 부서별/직급별 인원 구성 현황표를 1장짜리 시각화 보고서로 만들어보기",
            "20": "'월별 인사 통계 보고서 작성할 때 임원진이 가장 먼저 확인하는 핵심 지표(KPI)는 무엇인가요?'",
            "10": "엑셀 데이터 분석과 대시보드 시각화 실무",
            "tags": ["#피벗테이블", "#인력통계", "#엑셀", "#대시보드"]
        },
        "문서작성 (총무)": {
            "70": "이번 주 기안할 협조전이나 품의서를 두괄식(1페이지 핵심 요약 + 3단 본문 구조)으로 작성하고 사수에게 퇴고 요청하기",
            "20": "'저희 회사 기안문에서 자주 반려되는 표현이나 양식상 오류는 주로 어떤 것들인가요?'",
            "10": "쉽게 쓰고 편하게 읽히는 2page 보고서 만들기 (윈스펙)",
            "tags": ["#기안문", "#품의서", "#두괄식", "#1페이지보고서"]
        },
        "문서관리 (총무)": {
            "70": "팀 공용 드라이브 폴더의 파일 네이밍 규칙(YYYYMMDD_문서명_버전_작성자)을 정비하고 오래된 문서 5건 편철 정리하기",
            "20": "'계약서 및 대외 공문서의 법적 보존 연한(3년/5년/영구) 기준표는 어디서 확인할 수 있나요?'",
            "10": "전자문서시스템(EDMS) 및 사내 문서 편철 실무",
            "tags": ["#문서분류", "#EDMS", "#보존연한", "#문서보안"]
        },
        "자료관리 (총무)": {
            "70": "사무실 비품 및 소모품 수불 대장을 실사 대조하여 재고 부족 품목 리스트업 및 자동 주문 수량 계산식 적용하기",
            "20": "'비품 구매 시 단가 비교 견적서(2곳 이상) 징구 기준 금액과 정기 구매 주기는 어떻게 되나요?'",
            "10": "총무 실무자를 위한 자산·소모품 재고관리",
            "tags": ["#비품관리", "#재고실사", "#소모품", "#자산라벨"]
        },
        "사무자동화 (총무)": {
            "70": "매주 반복하는 정산/취합 업무에 엑셀 VLOOKUP/XLOOKUP 또는 조건부 서식을 적용해 수작업 시간 30분 단축하기",
            "20": "'선배님이 실무에서 가장 자주 쓰시는 사내 엑셀 템플릿이나 단축키 노하우가 있다면 공유 부탁드려도 될까요?'",
            "10": "컴퓨터활용능력 2급 자격증 실기 & 엑셀 실무 (더조은)",
            "tags": ["#엑셀실무", "#VLOOKUP", "#사무자동화", "#컴활"]
        },
        "회의 운영·지원 (총무)": {
            "70": "주간 정기회의 1시간 전 회의실 기자재(마이크, 빔, 화상회의 링크)를 사전 리허설하고, 회의 종료 후 당일 내 액션 아이템 회의록 공유하기",
            "20": "'임원 회의 진행 시 의전이나 회의 자료 인쇄 배포 시 사전에 꼭 챙겨야 할 주의사항이 있을까요?'",
            "10": "스마트한 회의 운영과 비즈니스 의전 실무",
            "tags": ["#회의록", "#의전", "#회의실세팅", "#화상회의"]
        }
    }

    _selected = _action_catalog.get(action_dropdown.value, _action_catalog["인사 관련 법규 이해 (인사)"])

    tab5_content = mo.vstack([
        mo.md("## 📋 70:20:10 나만의 현업 실천 플래너"),
        mo.md("> 성장의 70%는 현업 과제에서, 20%는 선배의 피드백에서, 10%는 정규 교육에서 일어납니다."),
        action_dropdown,
        mo.md("---"),
        mo.hstack([
            mo.callout(
                mo.md(
                    f"""
                    #### 💼 **70% 현업 마이크로 실험 (내일 업무)**
                    {_selected['70']}
                    """
                ),
                kind="info"
            ),
            mo.callout(
                mo.md(
                    f"""
                    #### 🗣️ **20% 멘토/사수 1:1 질문**
                    > {_selected['20']}
                    *(사수에게 그대로 물어보세요)*
                    """
                ),
                kind="success"
            ),
            mo.callout(
                mo.md(
                    f"""
                    #### 📚 **10% 추천 연계 공공 강좌**
                    - **추천 과정**: **{_selected['10']}**
                    - **키워드**: {' '.join(_selected['tags'])}
                    """
                ),
                kind="warn"
            )
        ], gap=2)
    ])

    return (tab5_content,)


@app.cell
def __(df_courses, df_courses_295, mo):
    # Tab 6: 아카이브 공공 강좌 및 295개 전수 탐색기 계승
    tab6_content = mo.vstack([
        mo.md("## 📂 공공 교육과정 탐색기 & 295개 전수 키워드 데이터"),
        mo.md("> 3대 공공 API 실측 30개 강좌 및 NLP 텍스트 정제 295개 강좌 전수 목록입니다."),
        mo.ui.table(df_courses[[
            "source_api", "course_name", "institution", "primary_job", 
            "training_hours", "cost", "suitability_score"
        ]]) if not df_courses.empty else mo.md("30개 강좌 로딩 대기"),
        mo.md("---"),
        mo.md("#### 🤖 295개 전수 강좌 NLP 군집 및 키워드 테이블"),
        mo.ui.table(df_courses_295[[
            "id", "course_title", "platform", "institution", 
            "training_hours", "cost", "top_keywords", "cluster"
        ]]) if not df_courses_295.empty else mo.md("295개 강좌 로딩 대기")
    ])
    return (tab6_content,)


@app.cell
def __(
    header_bar,
    mo,
    tab1_content,
    tab2_content,
    tab3_content,
    tab4_content,
    tab5_content,
    tab6_content,
):
    # 메인 앱 조립: 불필요한 상단 스크롤 영역을 없애고 탭이 바로 보이도록 최적화
    navigator_tabs = mo.ui.tabs({
        "🎭 1. 워크 페르소나 (일하는 캐릭터)": tab1_content,
        "🗓️ 2. First 90 Days 스프린트": tab2_content,
        "🎖️ 3. 공식 승급(Lv1 ➡️ Lv2) 체크리스트": tab3_content,
        "📊 4. 직무역량 스킬 갭(Gap) 진단": tab4_content,
        "📋 5. 70:20:10 실천 플래너": tab5_content,
        "📂 6. 공공 교육과정 탐색기": tab6_content
    })

    main_dashboard_layout = mo.vstack([
        header_bar,
        mo.md("---"),
        navigator_tabs
    ], gap=1)

    main_dashboard_layout
    return main_dashboard_layout, navigator_tabs


if __name__ == "__main__":
    app.run()
