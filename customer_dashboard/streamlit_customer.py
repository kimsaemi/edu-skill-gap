"""
인사·총무·경영지원 업무·성장·교육 안내 (고객용 Streamlit 앱)
- 실행: streamlit run app.py  (또는 streamlit run customer_dashboard/streamlit_customer.py)
- 화면 구성은 팀 고객용 대시보드 v2.1과 같습니다.
    1. 👤 내 위치      : 직급 1개 + 관심 분야(여러 개)
    2. 🩺 진단 & 하는 일: 업무별 숙련도 자가진단(4단계), 보강하고 싶은 역량, 직급별 역할
    3. 📚 추천 교육    : 부족한 업무·역량마다 가장 잘 맞는 교육 1개 + 다른 후보
    🔎 전체 교육 찾기 / 📋 내 학습 현황(수강 표시·진단 이력·목표)
- 데이터: 최신 카탈로그와 추천 엔진 (src/customer/career_platform.py)
- 원칙: 공식 만족도는 정보로만 보여 주고 추천 순위·점수에 쓰지 않습니다.
        결측은 채워 넣지 않고 '미확인'으로 표시합니다. 일정이 지난 과정에는 종료 표시를 붙입니다.
"""

import sys
from datetime import date, datetime
from html import escape
from pathlib import Path

import streamlit as st

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.customer import career_platform as cp  # noqa: E402

st.set_page_config(page_title="인사·총무·경영지원 성장·교육 안내", page_icon="🧭", layout="wide")

# ---------------------------------------------------------------------------
# 스타일 (v2.1 대시보드의 색·카드 형태)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
:root { --primary:#4f46e5; --primary-soft:#eef2ff; --teal:#0f766e; --teal-soft:#f0fdfa; --amber:#d97706;
  --amber-soft:#fffbeb; --rose:#be123c; --rose-soft:#fff1f2; --line:#e2e8f0; --ink:#0f172a; --sub:#334155; --muted:#64748b; }
html, body, [class*="css"], .stApp { font-family: Pretendard, -apple-system, "Malgun Gothic", sans-serif; }
.block-container { max-width: 1120px; padding-top: 1.6rem; }
.hero { background: linear-gradient(135deg,#eef2ff 0%,#f0fdfa 100%); border:1px solid var(--line); border-radius:18px; padding:22px 24px; margin-bottom:14px; }
.hero h1 { font-size:26px; margin:0 0 6px; color:var(--ink); }
.hero p { margin:0; color:var(--sub); }
.hero .cnt { display:inline-block; margin-top:10px; background:#fff; border:1px solid var(--line); border-radius:999px; padding:4px 12px; font-size:13px; color:var(--sub); }
.shead { display:flex; align-items:center; gap:10px; margin:6px 0 4px; }
.shead .badge { background:var(--primary); color:#fff; border-radius:999px; padding:3px 10px; font-size:12.5px; font-weight:700; }
.shead h2 { margin:0; font-size:22px; color:var(--ink); }
.hint { color:var(--muted); font-size:14px; }
.summary { background:var(--primary-soft); border-radius:12px; padding:9px 14px; color:var(--sub); font-size:14px; margin-bottom:10px; }
.focus { background:#0f172a; color:#f1f5f9; border-radius:16px; padding:18px 20px; margin:6px 0 16px; }
.focus .eyebrow { font-size:12.5px; color:#a5b4fc; font-weight:700; }
.focus h3 { color:#fff; margin:6px 0 10px; font-size:19px; }
.fgrid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
.fitem { background:rgba(255,255,255,.07); border-radius:10px; padding:9px 12px; }
.fitem small { display:block; color:#94a3b8; font-size:12px; } .fitem strong { font-size:14.5px; }
.pbar { height:8px; background:rgba(255,255,255,.12); border-radius:99px; margin-top:12px; overflow:hidden; }
.pbar span { display:block; height:100%; background:linear-gradient(90deg,#818cf8,#2dd4bf); }
.task-head { display:flex; justify-content:space-between; gap:8px; align-items:center; flex-wrap:wrap; margin-top:4px; }
.stage { font-size:11.5px; border-radius:6px; padding:2px 7px; font-weight:700; margin-right:6px; }
.stage.plan { background:#eef2ff; color:#4338ca; } .stage.do { background:#ecfdf5; color:#047857; } .stage.see { background:#fff7ed; color:#c2410c; }
.flag { font-size:12px; border-radius:999px; padding:2px 9px; font-weight:700; }
.flag.weak { background:var(--amber-soft); color:var(--amber); } .flag.ok { background:var(--teal-soft); color:var(--teal); } .flag.none { color:var(--muted); }
.alert { border-radius:12px; padding:11px 14px; font-size:14px; margin:10px 0; }
.alert.up { background:var(--amber-soft); color:#92400e; } .alert.match { background:var(--teal-soft); color:#115e59; } .alert.high { background:var(--primary-soft); color:#3730a3; }
.report { background:#1e1b4b; color:#e0e7ff; border-radius:16px; padding:16px 18px; margin:14px 0; }
.report h4 { color:#fff; margin:0 0 10px; }
.pill { display:inline-block; background:rgba(255,255,255,.12); border-radius:999px; padding:3px 10px; margin:2px 4px 2px 0; font-size:13px; }
.course { border:1px solid var(--line); border-radius:16px; padding:14px 16px 6px; background:#fff; margin:6px 0 2px; }
.course.direct { border-left:5px solid var(--teal); } .course.common { border-left:5px solid #a5b4fc; }
.course .title { font-size:16.5px; font-weight:700; color:var(--ink); margin:6px 0 4px; line-height:1.45; }
.course .meta { color:var(--sub); font-size:13.5px; margin-bottom:4px; }
.course .info { display:flex; flex-wrap:wrap; gap:6px 12px; font-size:13px; color:var(--sub); background:#f8fafc; border:1px solid var(--line); border-radius:10px; padding:7px 10px; margin:6px 0; }
.course .why { font-size:13.5px; color:#4338ca; margin:4px 0 6px; }
.tag { display:inline-block; font-size:12px; font-weight:700; border-radius:999px; padding:2px 9px; margin-right:4px; }
.tag.direct { background:var(--teal-soft); color:var(--teal); } .tag.common { background:var(--primary-soft); color:#4338ca; }
.tag.closed { background:var(--rose-soft); color:var(--rose); } .tag.open { background:#ecfdf5; color:#047857; } .tag.review { background:var(--amber-soft); color:var(--amber); }
.sat { display:inline-block; margin-left:8px; font-size:12.5px; color:#92400e; background:var(--amber-soft); border-radius:999px; padding:1px 8px; }
.flow-item { border:1px solid var(--line); border-radius:12px; padding:9px 12px; margin:6px 0; }
.flow-item.cur { border-color:var(--primary); background:var(--primary-soft); }
.flow-item .gn { font-weight:700; color:var(--ink); } .flow-item .bd { font-size:12.5px; color:var(--teal); font-weight:700; }
.sec-title { font-size:17px; font-weight:800; color:var(--ink); margin:18px 0 6px; }
.notice { background:#f8fafc; border:1px dashed #cbd5e1; border-radius:12px; padding:12px 14px; color:var(--sub); font-size:14px; }
.track { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:8px 0 14px; }
.track div { background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 12px; }
.track small { color:var(--muted); display:block; } .track strong { font-size:20px; color:var(--ink); }
@media (max-width: 760px) { .fgrid, .track { grid-template-columns:repeat(2,minmax(0,1fr)); } }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="교육 데이터와 추천 엔진을 준비하고 있어요...")
def load_platform():
    return len(cp.courses())


N_COURSES = load_platform()
G = cp.grades()
DOMS = cp.domains()
LEVEL_NAMES = cp.LEVEL_NAMES
ST_LABEL = {"interested": "관심", "learning": "수강중", "done": "수료", "paused": "중단"}
GOAL_TYPES = {
    "promo": ("🚀", "승진 준비", "다음 직급의 승진 요건을 채워요"),
    "job": ("🧳", "이직 준비", "이력서·포트폴리오·면접을 준비해요"),
    "switch": ("🔄", "직무 전환", "다른 분야로 옮길 준비를 해요"),
    "skill": ("💪", "역량 강화", "부족한 역량을 채우고 숙련도를 올려요"),
}


# ---------------------------------------------------------------------------
# 상태
# ---------------------------------------------------------------------------
def init_state():
    defaults = {
        "step": "1", "g": None, "ds": [], "d": None, "tl": {}, "skills": [], "open_task": None,
        "enroll": {}, "diag_log": [], "goals": [], "limit": 12, "more": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()
S = st.session_state


def ready() -> bool:
    return S.g is not None and len(S.ds) > 0 and S.d is not None


def go(step: str):
    S.step = step


def std_level() -> int:
    return cp.LEVEL_OF_GRADE[S.g if S.g is not None else 0]


def eff_level() -> int:
    vals = list(S.tl.values())
    if vals:
        return min(3, round(sum(vals) / len(vals)))
    return std_level()


def weak_tasks():
    std = std_level()
    out = []
    idx = cp.task_index()
    for tid, lv in S.tl.items():
        t = idx.get(tid)
        if t and lv < std and t["dom_id"] in S.ds:
            out.append({**t, "cur": lv, "std": std, "gap": std - lv})
    return sorted(out, key=lambda x: -x["gap"])


def icon(dom_id: str) -> str:
    return cp.DOM_ICON.get(dom_id, "📌")


def dom_short(dom_id: str) -> str:
    d = cp.domain(dom_id)
    return d["short"] if d else dom_id


def stage_cls(stage: str) -> str:
    return "do" if stage == "운영·실행" else "see" if stage == "분석·개선" else "plan"


# ---------------------------------------------------------------------------
# 공통 화면 요소
# ---------------------------------------------------------------------------
def hero():
    st.markdown(f"""<div class="hero"><h1>🧭 인사·총무·경영지원 업무·성장·교육 안내</h1>
      <p>직급과 분야를 고르고 업무별 숙련도를 진단하면, 부족한 업무마다 맞는 교육을 골라 드려요.</p>
      <span class="cnt">📚 실제 교육 과정 {N_COURSES:,}개 · 업무 {len(cp.task_index())}개 기준</span></div>""", unsafe_allow_html=True)


def stepbar():
    n = len(S.enroll)
    defs = [("1", "👤 1. 내 위치"), ("2", "🩺 2. 진단 & 하는 일"), ("3", "📚 3. 추천 교육"),
            ("all", "🔎 전체 교육 찾기"), ("my", f"📋 내 학습 현황{f' ({n})' if n else ''}")]
    cols = st.columns([1, 1.25, 1, 1.15, 1.25])
    for col, (key, label) in zip(cols, defs):
        disabled = key in ("2", "3") and not ready()
        col.button(label, key=f"nav_{key}", use_container_width=True, disabled=disabled,
                   type="primary" if S.step == key else "secondary", on_click=go, args=(key,))
    if ready() and S.step in ("2", "3"):
        doms = " · ".join(f"{icon(x)} {escape(dom_short(x))}" for x in S.ds)
        badge = f" · 부족 업무 {len(weak_tasks())}개 · 보강 역량 {len(S.skills)}개"
        st.markdown(f'<div class="summary">지금 선택 · <b>{escape(G[S.g]["name"])}</b> · <b>{doms}</b>{badge}</div>', unsafe_allow_html=True)


def toggle_enroll(card: dict, for_what: str = ""):
    uid = card["course_uid"]
    if uid in S.enroll:
        del S.enroll[uid]
        st.toast("내 학습 목록에서 뺐어요.")
    else:
        S.enroll[uid] = {
            "title": card["title"], "inst": card["institution"], "plat": card["platform"], "url": card["url"],
            "status": "interested", "progress": 0, "for": for_what,
            "startedAt": datetime.now().isoformat(timespec="minutes"), "updatedAt": datetime.now().isoformat(timespec="minutes"),
        }
        st.toast("내 학습 현황에 '관심'으로 담았어요.")


def course_card(card: dict, key: str, for_what: str = "", note: str = ""):
    """교육 카드 1장. 공식 만족도는 정보로만 보여 주고 점수에는 넣지 않습니다."""
    tags = f'<span class="tag {card["kind"]}">{"✅ 직접 관련" if card["kind"] == "direct" else "🧰 공통 역량"}</span>'
    if card.get("schedule_badge"):
        tags += f'<span class="tag closed">⏹ {escape(card["schedule_badge"])}</span>'
    elif card.get("w24_status") in ("운영 중", "개강 예정"):
        tags += f'<span class="tag open">● {escape(card["w24_status"])}</span>'
    sat = (f'<span class="sat" title="고용24 수강생 설문 만족도. 응답자 수가 공개되지 않아 추천 순위에는 쓰지 않아요.">'
           f'⭐ 공식 만족도 {card["sat"]:g}</span>') if card.get("sat") is not None else ""
    info = [f"💰 {escape(card['price_display'])}"]
    if card.get("self_pay") is not None and card["platform"] == "국민내일배움카드":
        info.append(f"🧾 자기부담 약 {card['self_pay']:,}원")
    info += [f"⏱️ {escape(card['duration_display'])}", f"💻 {escape(card['education_type'])}"]
    if card.get("difficulty") and card["difficulty"] != "미확인":
        info.append(f"📈 {escape(card['difficulty'])}")
    info.append(f"🗓️ {escape(card['schedule_display'])}")
    why = f'<div class="why">💡 {escape(card["why"])}</div>' if card.get("why") else ""
    st.markdown(f"""<div class="course {card['kind']}">{tags}
      <div class="title">{escape(card['title'])}</div>
      <div class="meta">🏢 {escape(card['institution'])}{' · ' + escape(card['platform']) if card['platform'] and card['platform'] != card['institution'] else ''}{sat}</div>
      <div class="info">{''.join(f'<span>{x}</span>' for x in info)}</div>{why}</div>""", unsafe_allow_html=True)
    if note:
        st.caption(note)
    with st.expander("🔍 추천 근거 보기"):
        m = card.get("match")
        if m:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("추천 점수", f"{m['final']:g}")
            c2.metric("업무와 뜻이 가까운 정도", f"{m['sem']:g}")
            c3.metric("핵심 단어 일치", f"{m['bm25']:g}")
            c4.metric("난이도 맞춤 가점", f"+{m['lvl']:g}")
            st.caption("추천 점수 = 뜻이 가까운 정도 × 0.5 + 핵심 단어 일치 × 0.35 + 난이도 가점(0~10). 수강생 만족도는 점수에 넣지 않아요.")
        rows = []
        if card.get("audience"):
            rows.append(("대상자", card["audience"]))
        if card.get("goals"):
            rows.append(("학습목표", card["goals"] + ("…" if len(card["goals"]) >= 220 else "")))
        if card.get("curriculum"):
            rows.append(("커리큘럼", card["curriculum"] + ("…" if len(card["curriculum"]) >= 260 else "")))
        if card.get("doms"):
            rows.append(("연결 분야", " · ".join(dom_short(x) for x in card["doms"][:4])))
        if card.get("sat") is not None:
            rows.append(("공식 만족도", f"고용24 수강생 설문 {card['sat']:g}점 (응답자 수 미공개 · 참고용)"))
        rows.append(("출처", card.get("source_display", "")))
        for k, v in rows:
            st.markdown(f"**{k}** · {escape(str(v))}")
        if card.get("text_richness_warning"):
            st.caption(card["text_richness_warning"])
    b1, b2 = st.columns([1, 1])
    enrolled = card["course_uid"] in S.enroll
    b1.button(f"✓ {ST_LABEL[S.enroll[card['course_uid']]['status']]} · 내 학습에 있음" if enrolled else "＋ 수강 신청 표시",
              key=f"enr_{key}", use_container_width=True, on_click=toggle_enroll, args=(card, for_what))
    if str(card.get("url", "")).startswith("https://"):
        b2.link_button("상세 보기 ↗", card["url"], use_container_width=True)


# ---------------------------------------------------------------------------
# 1단계 · 내 위치
# ---------------------------------------------------------------------------
def pick_grade(i: int):
    S.g = i


def toggle_domain(dom_id: str):
    if dom_id in S.ds:
        S.ds = [x for x in S.ds if x != dom_id]
    else:
        S.ds = S.ds + [dom_id]
    S.d = S.d if S.d in S.ds else (S.ds[0] if S.ds else None)


def load_sample():
    """처음 보는 사람을 위한 예시: 대리 · 인재채용 + 보상·급여, 업무 몇 개를 기준보다 낮게 진단."""
    S.g, S.ds, S.d = 1, ["DOM_03", "DOM_06"], "DOM_03"
    S.tl = {"DOM_03_T01": 0, "DOM_03_T02": 1, "DOM_03_T03": 0, "DOM_06_T01": 0, "DOM_06_T02": 1}
    S.skills = ["역량기반 구조화 면접(BEI) 설계", "데이터 분석 & 시각화"]
    S.step = "3"


def view_pick():
    st.markdown('<div class="shead"><span class="badge">1단계</span><h2>👤 내 위치를 골라 주세요</h2></div>', unsafe_allow_html=True)
    st.markdown('<p class="hint">직급 하나와 관심 분야(여러 개 가능)를 고르면 바로 안내해 드려요. 나중에 언제든 바꿀 수 있어요.</p>', unsafe_allow_html=True)
    st.markdown("#### ① 연차에 가까운 직급")
    cols = st.columns(len(G))
    for i, (col, g) in enumerate(zip(cols, G)):
        col.button(f"{i + 1}. {g['name']}  \n{g['years']}", key=f"g_{i}", use_container_width=True,
                   type="primary" if S.g == i else "secondary", on_click=pick_grade, args=(i,))
    st.markdown(f"#### ② 알고 싶은 분야 <span class='hint'>(여러 개 선택 가능 · {len(S.ds)}개 선택됨)</span>", unsafe_allow_html=True)
    for row_start in range(0, len(DOMS), 3):
        cols = st.columns(3)
        for col, d in zip(cols, DOMS[row_start:row_start + 3]):
            sel = d["id"] in S.ds
            col.button(f"{icon(d['id'])} {d['short']}  \n{d.get('brief', '')}", key=f"d_{d['id']}", use_container_width=True,
                       type="primary" if sel else "secondary", on_click=toggle_domain, args=(d["id"],))
    c1, c2, _ = st.columns([1.4, 1.2, 2])
    c1.button("다음 · 내가 하는 일 보기 →", type="primary", disabled=not ready(), use_container_width=True, on_click=go, args=("2",))
    c2.button("👀 샘플로 둘러보기", use_container_width=True, on_click=load_sample)
    if not ready():
        st.caption("직급 1개와 분야를 1개 이상 골라 주세요.")


# ---------------------------------------------------------------------------
# 2단계 · 진단 & 하는 일
# ---------------------------------------------------------------------------
def set_task_level(task_id: str, key: str):
    v = S.get(key)
    if v is None or v == "모름":
        S.tl.pop(task_id, None)
    else:
        S.tl[task_id] = int(v[0]) - 1


def set_skills(key: str, pool: list):
    chosen = set(S.get(key) or [])
    S.skills = [s for s in S.skills if s not in pool] + [s for s in pool if s in chosen]


def preset_skills():
    pool = cp.DOMAIN_SKILLS.get(S.d, [])[:2] + [cp.DIGITAL_SKILLS[0]["name"]]
    S.skills = list(dict.fromkeys(S.skills + pool))
    for k in list(S.keys()):
        if str(k).startswith("sk_"):
            del S[k]


def clear_skills():
    S.skills = []
    for k in list(S.keys()):
        if str(k).startswith("sk_"):
            del S[k]


def save_diag():
    S.diag_log.append({"at": datetime.now().isoformat(timespec="minutes"), "g": S.g, "ds": list(S.ds),
                       "lvl": eff_level(), "skills": list(S.skills), "tl": dict(S.tl)})
    st.toast("진단을 저장했어요. '내 학습 현황'에서 보완 진행을 추적할 수 있어요.")


def set_open_task(key: str):
    S.open_task = S.get(key)


def switch_domain(key: str):
    v = S.get(key)
    if v:
        if v not in S.ds:
            S.ds = S.ds + [v]
        S.d = v


def view_tasks():
    dom = cp.domain(S.d)
    gr = G[S.g]
    tasks = dom.get("tasks", [])
    std = std_level()
    st.markdown('<div class="shead"><span class="badge">2단계</span><h2>🩺 현재 역량 진단 & 업무 역할 안내</h2></div>', unsafe_allow_html=True)
    if len(S.ds) > 1:
        st.segmented_control("선택한 분야", options=S.ds, format_func=lambda x: f"{icon(x)} {dom_short(x)}",
                             key="dom_tab", default=S.d, on_change=lambda: setattr(S, "d", S.dom_tab or S.d), label_visibility="collapsed")
    t = next((x for x in tasks if x["id"] == S.open_task), tasks[0] if tasks else None)
    role = (t["roles"][S.g] if t and S.g < len(t["roles"]) else {"badge": dom["short"], "role": dom.get("brief", "")})
    assessed = [x for x in tasks if x["id"] in S.tl]
    weak_here = [x for x in assessed if S.tl[x["id"]] < std]
    cur = eff_level()
    st.markdown(f"""<div class="focus"><div class="eyebrow">{icon(dom['id'])} 현재 선택 · {escape(gr['name'])} · {escape(dom['short'])}</div>
      <h3>{escape(role['role'])}</h3>
      <div class="fgrid"><div class="fitem"><small>지금 직급 역할</small><strong>{escape(role['badge'])}</strong></div>
        <div class="fitem"><small>자가진단 숙련도</small><strong>{cur + 1}단계 · {LEVEL_NAMES[cur]}</strong></div>
        <div class="fitem"><small>부족 업무 · 보강 역량</small><strong>{len(weak_tasks())}개 · {len(S.skills)}개</strong></div></div>
      <div class="pbar"><span style="width:{(S.g + 1) / len(G) * 100:.0f}%"></span></div></div>""", unsafe_allow_html=True)

    st.markdown(f'<div class="sec-title">🩺 1. 업무별 숙련도 자가진단 <span class="hint">· {len(assessed)}/{len(tasks)}개 진단 · 보강 필요 {len(weak_here)}개</span></div>', unsafe_allow_html=True)
    st.markdown(f'<p class="hint">각 업무에서 지금 어느 단계까지 해낼 수 있나요? {escape(gr["name"])} 기준은 <b>{std + 1}단계 ({LEVEL_NAMES[std]})</b>이고, '
                '기준보다 낮게 고른 업무가 <b>부족 업무</b>로 모여 3단계에서 맞춤 교육으로 연결돼요. 모르는 업무는 건너뛰어도 괜찮아요.</p>', unsafe_allow_html=True)
    options = ["모름"] + [f"{i + 1}단계 · {nm}" for i, nm in enumerate(LEVEL_NAMES)]
    for x in tasks:
        lv = S.tl.get(x["id"])
        if lv is None:
            flag = '<span class="flag none">아직 진단 전</span>'
        elif lv < std:
            flag = f'<span class="flag weak">기준보다 {std - lv}단계 낮아요</span>'
        else:
            flag = f'<span class="flag ok">{"기준 달성" if lv == std else "기준 이상"}</span>'
        review = '<span class="tag review">역량 연결 확인 중</span>' if x["id"] in cp.review_task_ids() else ""
        st.markdown(f'<div class="task-head"><span><span class="stage {stage_cls(x.get("stage", ""))}">{escape(x.get("stage", ""))}</span>'
                    f'<b>{escape(x["name"])}</b> {review}</span>{flag}</div>', unsafe_allow_html=True)
        key = f"tl_{x['id']}"
        if key not in S:
            S[key] = options[lv + 1] if lv is not None else "모름"
        st.segmented_control(x["name"], options=options, key=key, on_change=set_task_level, args=(x["id"], key), label_visibility="collapsed")
        levels = x.get("levels") or []
        shown = lv if lv is not None else std
        if shown < len(levels):
            st.caption(f"{'지금' if lv is not None else '직급 기준'} {shown + 1}단계: {levels[shown]}")

    if assessed:
        if cur < std:
            st.markdown(f'<div class="alert up">⚠️ <b>역량 집중 보강 권장</b> · {escape(gr["name"])}의 기대 수준({LEVEL_NAMES[std]})에 닿으려면 실무 자립 역량을 집중 보완해야 해요. 3단계에서 맞춤 교육을 확인해 보세요.</div>', unsafe_allow_html=True)
        elif cur == std:
            st.markdown(f'<div class="alert match">✅ <b>표준 역량 부합</b> · {escape(gr["name"])}의 기대 역할({LEVEL_NAMES[std]})에 맞게 일하고 있어요. 다음 단계를 위한 차별화 역량을 골라 보세요.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert high">🚀 <b>우수 역량 도달</b> · 이미 상위 직급 수준({LEVEL_NAMES[cur]})의 역량을 보이고 있어요.</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="sec-title">🚨 2. 추가로 보강하고 싶은 역량 <span class="hint">(선택 · {len(S.skills)}개 선택됨)</span></div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1.2, 1, 3])
    c1.button("✨ 권장 역량 3개 자동선택", on_click=preset_skills, use_container_width=True)
    c2.button("🔄 전체 해제", on_click=clear_skills, use_container_width=True)
    groups = [
        (f"🎯 {dom['short']} 실무 핵심 역량", "sk_dom", list(dict.fromkeys(s for x in S.ds for s in cp.DOMAIN_SKILLS.get(x, [])))),
        ("🤖 AI·데이터 & 업무 자동화", "sk_dig", [f"{x['icon']} {x['name']}" for x in cp.DIGITAL_SKILLS]),
        ("💼 기획·소통·재무·노무 기본기", "sk_biz", [f"{x['icon']} {x['name']}" for x in cp.BIZ_SKILLS]),
    ]
    for label, key, pool in groups:
        names = [p.split(" ", 1)[1] if key != "sk_dom" else p for p in pool]
        label_of = dict(zip(names, pool))
        if key not in S:
            S[key] = [n for n in names if n in S.skills]
        st.pills(label, options=names, format_func=lambda n, m=label_of: m[n], selection_mode="multi", key=key,
                 on_change=set_skills, args=(key, names))

    weak = weak_tasks()
    weak_pills = "".join(f'<span class="pill">⚠ {escape(w["name"][:22])}</span>' for w in weak[:8]) or "<span class='pill'>업무별 숙련도를 진단하면 여기에 모여요</span>"
    skill_pills = "".join(f'<span class="pill">✓ {escape(s)}</span>' for s in S.skills) or "<span class='pill'>아직 선택한 역량이 없어요</span>"
    st.markdown(f"""<div class="report"><h4>📋 나의 현재 역량 진단 요약</h4>
      <div>진단 직급·분야 · <b>{escape(gr['name'])} ({escape(gr['years'])}) · {escape(dom['short'])}</b></div>
      <div>종합 수행 수준 · <b>{cur + 1}단계 ({LEVEL_NAMES[cur]})</b></div>
      <div style="margin-top:8px">보강이 필요한 업무 ({len(weak)}개)<br>{weak_pills}</div>
      <div style="margin-top:8px">선택한 보강 역량 ({len(S.skills)}개)<br>{skill_pills}</div></div>""", unsafe_allow_html=True)
    st.button("💾 이 진단 저장하고 추적하기", type="primary", on_click=save_diag)

    if tasks:
        st.markdown('<div class="sec-title">📌 업무 상세 · 직급이 올라가면 이 일은 이렇게 달라져요</div>', unsafe_allow_html=True)
        if "open_task_sel" not in S or S.open_task_sel not in [x["id"] for x in tasks]:
            S.open_task_sel = t["id"]
        st.selectbox("업무 선택", options=[x["id"] for x in tasks], format_func=lambda i: cp.task_index()[i]["name"],
                     key="open_task_sel", on_change=set_open_task, args=("open_task_sel",))
        t = cp.task_index()[S.open_task_sel]
        st.markdown(f"**{escape(t['name'])}** — {escape(t.get('easy', ''))}")
        for i, g in enumerate(G):
            r = t["roles"][i] if i < len(t["roles"]) else {"badge": "", "role": ""}
            cur_cls = "cur" if i == S.g else ""
            tag = " · 지금" if i == S.g else " · 다음" if i == S.g + 1 else ""
            st.markdown(f'<div class="flow-item {cur_cls}"><span class="gn">{i + 1}. {escape(g["name"])}</span> '
                        f'<span class="hint">{escape(g["years"])}{tag}</span><br><span class="bd">{escape(r["badge"])}</span> · {escape(r["role"])}</div>', unsafe_allow_html=True)
        with st.expander("📚 더 알아보기 · 지식·기술·태도(KSA), 자격증, 선배 조언"):
            st.markdown(f"**지식** · {t.get('k', '')}  \n**기술** · {t.get('s', '')}  \n**태도** · {t.get('a', '')}")
            st.markdown(f"**📜 도움이 되는 자격증** · {gr.get('cert', '')}  \n**🗣️ 선배 조언** · {gr.get('advice', '')}")
            st.markdown(f"**🎯 직급 공통 승진 과제** · {gr.get('gate', '')}  \n**🏁 공통 결과물** · {gr.get('capstone', '')}")

    st.markdown('<div class="sec-title">🧭 다른 분야로 바꿔서 보기</div>', unsafe_allow_html=True)
    st.pills("분야", options=[d["id"] for d in DOMS], format_func=lambda x: f"{icon(x)} {dom_short(x)}", key="switch_dom",
             on_change=switch_domain, args=("switch_dom",), label_visibility="collapsed")
    c1, c2, _ = st.columns([1, 1.8, 1.5])
    c1.button("← 내 위치 다시 고르기", on_click=go, args=("1",), use_container_width=True)
    c2.button(f"다음 · 맞춤 교육 보기 ({len(weak) + len(S.skills)}개) →", type="primary", on_click=go, args=("3",), use_container_width=True)


# ---------------------------------------------------------------------------
# 3단계 · 추천 교육
# ---------------------------------------------------------------------------
def view_courses():
    dom = cp.domain(S.d)
    gr = G[S.g]
    st.markdown(f'<div class="shead"><span class="badge">3단계</span><h2>📚 {escape(gr["name"])} · {escape(dom["short"])} 맞춤 교육 추천</h2></div>', unsafe_allow_html=True)
    weak = weak_tasks()
    used = set()
    if weak or S.skills:
        st.markdown('<div class="sec-title">🎯 내 부족 항목별 추천 교육</div>', unsafe_allow_html=True)
        st.markdown('<p class="hint">진단에서 기준보다 낮게 고른 업무와 선택한 역량마다 가장 잘 맞는 교육 1개를 골랐어요. '
                    '업무 설명과 교육 내용의 뜻·핵심 단어·난이도로 자동 계산한 참고용 추천이에요.</p>', unsafe_allow_html=True)
        n = 0
        for w in weak:
            n += 1
            cards = [c for c in cp.task_recommendations(w["id"], S.g) if c["course_uid"] not in used]
            st.markdown(f"##### {n}. 🟧 업무 · {escape(w['name'])} <span class='hint'>현재 {w['cur'] + 1}단계 → 기준 {w['std'] + 1}단계</span>", unsafe_allow_html=True)
            note = "⚠ 이 업무의 NCS 역량 연결은 팀에서 확인 중이에요. 추천은 업무 설명으로 계산해 참고할 수 있어요." if w["id"] in cp.review_task_ids() else ""
            if cards:
                used.add(cards[0]["course_uid"])
                course_card(cards[0], f"t{n}_{cards[0]['course_uid']}", for_what=w["name"], note=note)
                if len(cards) > 1:
                    with st.expander(f"다른 교육 {len(cards) - 1}개 보기"):
                        for c in cards[1:]:
                            course_card(c, f"t{n}a_{c['course_uid']}", for_what=w["name"])
            else:
                st.markdown(f'<div class="notice">이 업무에 딱 맞는 교육을 찾지 못했어요. 고용24에서 "{escape(w["name"].split()[0])}"(으)로 검색해 보세요.</div>', unsafe_allow_html=True)
        for sk in S.skills:
            n += 1
            cards = [c for c in cp.skill_recommendations(sk, S.g) if c["course_uid"] not in used]
            st.markdown(f"##### {n}. 🟦 역량 · {escape(sk)}")
            if cards:
                used.add(cards[0]["course_uid"])
                course_card(cards[0], f"s{n}_{cards[0]['course_uid']}", for_what=sk)
                if len(cards) > 1:
                    with st.expander(f"다른 교육 {len(cards) - 1}개 보기"):
                        for c in cards[1:]:
                            course_card(c, f"s{n}a_{c['course_uid']}", for_what=sk)
            else:
                st.markdown('<div class="notice">이 역량에 딱 맞는 교육을 찾지 못했어요.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="notice">💡 2단계에서 업무별 숙련도를 진단하면, 부족한 업무마다 맞는 교육 1개를 골라 드려요.</div>', unsafe_allow_html=True)
        st.button("← 2단계에서 진단하기", on_click=go, args=("2",))

    base = cp.domain_recommendations(S.d, S.g)
    top, rest = base[:4], base[4:]
    with st.expander(f"⭐ {gr['name']} · {dom['short']} 기본 추천", expanded=not (weak or S.skills)):
        for c in top:
            course_card(c, f"b_{c['course_uid']}", for_what=dom["short"])
    if S.g + 1 < len(G):
        nxt = G[S.g + 1]
        nxt_cards = [c for c in cp.domain_recommendations(S.d, S.g + 1) if c["course_uid"] not in {x["course_uid"] for x in top}][:2]
        if nxt_cards:
            with st.expander(f"🔭 {nxt['name']}을 준비한다면"):
                for c in nxt_cards:
                    course_card({**c, "why": f"{nxt['name']} 준비 · {c['why']}"}, f"n_{c['course_uid']}", for_what=f"{nxt['name']} 준비")
    if rest:
        with st.expander(f"같이 보면 좋은 교육 ({len(rest)}개)"):
            for c in rest:
                course_card(c, f"r_{c['course_uid']}", for_what=dom["short"])
    c1, c2, c3, _ = st.columns([1.3, 1, 1, 1])
    c1.button("← 진단 다시 보기", on_click=go, args=("2",), use_container_width=True)
    c2.button("내 위치 바꾸기", on_click=go, args=("1",), use_container_width=True)
    c3.button("전체 교육 찾기 →", on_click=go, args=("all",), use_container_width=True)


# ---------------------------------------------------------------------------
# 전체 교육 찾기
# ---------------------------------------------------------------------------
def more_results():
    S.limit += 12


def reset_limit():
    S.limit = 12


def view_all():
    st.markdown('<div class="shead"><span class="badge">전체</span><h2>🔎 전체 교육 찾기</h2></div>', unsafe_allow_html=True)
    st.markdown(f'<p class="hint">고용24·휴넷·KPC·KMA·멀티캠퍼스·GSEEK 등에서 모은 과정 {N_COURSES:,}개 중 직무교육 과정을 찾아요. '
                '정렬은 인사·총무 분야와 설명이 충분한 과정을 먼저 보여 주고, 만족도는 정렬에 쓰지 않아요.</p>', unsafe_allow_html=True)
    q = st.text_input("🔍 과정명이나 기관명으로 검색", key="f_q", on_change=reset_limit)
    fields = ["ALL", "HR", "GA", "DATA_AI", "FIN", "IT_DEV", "LANG", "MKT", "PROD"]
    field = st.pills("분야", options=fields, format_func=lambda x: "전체" if x == "ALL" else cp.FIELD_NAMES[x], key="f_field",
                     default="ALL", on_change=reset_limit) or "ALL"
    c1, c2, c3, c4 = st.columns(4)
    dom_id = c1.selectbox("업무 분야", ["ALL"] + [d["id"] for d in DOMS], format_func=lambda x: "모든 업무 분야" if x == "ALL" else f"{dom_short(x)}에 맞는 과정", key="f_dom", on_change=reset_limit)
    plat = c2.selectbox("교육기관·제도", ["ALL"] + cp.platform_options(), format_func=lambda x: "모든 기관" if x == "ALL" else x, key="f_plat", on_change=reset_limit)
    level = c3.selectbox("난이도", ["ALL", "초급", "중급", "고급"], format_func=lambda x: "모든 난이도" if x == "ALL" else x, key="f_level", on_change=reset_limit)
    cost = c4.selectbox("비용", ["ALL", "FREE", "U30", "GOV"], format_func=lambda x: {"ALL": "모든 비용", "FREE": "무료", "U30": "30만 원 이하", "GOV": "국비 지원"}[x], key="f_cost", on_change=reset_limit)
    c5, c6 = st.columns(2)
    open_only = c5.checkbox("지난 일정 제외 (운영 중·예정·일정 미확인만)", key="f_open", on_change=reset_limit)
    sat_only = c6.checkbox("⭐ 고용24 공식 만족도가 있는 과정만", key="f_sat", on_change=reset_limit)
    res = cp.search_courses(q, field, dom_id, plat, level, cost, open_only, sat_only)
    st.caption(f"{len(res):,}개 과정")
    if res.empty:
        st.markdown('<div class="notice">조건에 맞는 과정이 없어요. 검색어나 조건을 바꿔 보세요.</div>', unsafe_allow_html=True)
    for i, (_, row) in enumerate(res.head(S.limit).iterrows()):
        course_card(cp.make_card(row), f"all{i}_{row['course_uid']}")
    if len(res) > S.limit:
        st.button("더 보기", on_click=more_results)
    st.button("← 내 위치부터 안내받기", on_click=go, args=("1",))


# ---------------------------------------------------------------------------
# 내 학습 현황
# ---------------------------------------------------------------------------
def set_enroll_status(uid: str, key: str):
    v = S.get(key)
    if v and uid in S.enroll:
        S.enroll[uid]["status"] = v
        S.enroll[uid]["updatedAt"] = datetime.now().isoformat(timespec="minutes")
        if v == "done":
            S.enroll[uid]["progress"] = 100


def set_progress(uid: str, key: str):
    if uid in S.enroll:
        S.enroll[uid]["progress"] = S.get(key, 0)


def del_enroll(uid: str):
    S.enroll.pop(uid, None)


def skill_progress(name: str) -> int:
    hits = [e for e in S.enroll.values() if e.get("for") == name and e["status"] != "interested"]
    if not hits:
        return 0
    return round(sum(100 if e["status"] == "done" else 0 if e["status"] == "paused" else e.get("progress", 0) for e in hits) / len(hits))


def add_goal(gtype: str, title: str, deadline, reqs: list):
    S.goals.append({"type": gtype, "title": title or GOAL_TYPES[gtype][1], "deadline": deadline.isoformat() if deadline else "",
                    "reqs": [{"label": r, "done": False} for r in reqs]})
    st.toast("목표를 만들었어요.")


def toggle_req(gi: int, ri: int, key: str):
    S.goals[gi]["reqs"][ri]["done"] = bool(S.get(key))


def del_goal(gi: int):
    S.goals.pop(gi)


def reset_track():
    S.enroll, S.diag_log, S.goals = {}, [], []


def goal_candidates(gtype: str) -> list:
    g0 = S.g if S.g is not None else 0
    out = [f"부족 역량 보완 · {s}" for s in S.skills] + [f"업무 숙련도 · {w['name']} ({w['cur'] + 1}→{w['std'] + 1}단계)" for w in weak_tasks()]
    if gtype == "promo" and g0 + 1 < len(G):
        nxt = G[g0 + 1]
        out += [f"승진 과제 · {nxt['gate']}", f"공통 결과물 · {nxt['capstone']}", f"역할 기준 · {nxt['milestone']}"]
        out += [f"자격증 · {c.strip()}" for c in nxt["cert"].split(",")]
    elif gtype == "job":
        out += ["이력서·경력기술서 최신화", "대표 성과 3가지를 숫자로 정리", "목표 직무 채용공고 5건 분석", "인사 직무 면접 예상 질문 답변 준비"]
    elif gtype == "switch":
        others = [d for d in DOMS if d["id"] not in S.ds][:1]
        if others:
            out += [f"전환 분야 역량 · {s}" for s in cp.DOMAIN_SKILLS.get(others[0]["id"], [])]
    else:
        out += [f"자격증 · {c.strip()}" for c in G[g0]["cert"].split(",")]
    return list(dict.fromkeys(out))


def view_my():
    st.markdown('<div class="shead"><span class="badge">내 학습</span><h2>📋 내 학습 현황 & 역량 보완 추적</h2></div>', unsafe_allow_html=True)
    st.markdown('<p class="hint">진단 결과와 수강 표시는 지금 열린 화면(세션)에만 저장돼요. 새로고침하거나 창을 닫으면 사라져요.</p>', unsafe_allow_html=True)
    items = sorted(S.enroll.items(), key=lambda kv: kv[1].get("updatedAt", ""), reverse=True)
    cnt = lambda k: sum(1 for _, e in items if e["status"] == k)  # noqa: E731
    learning = [e for _, e in items if e["status"] == "learning"]
    avg = round(sum(e.get("progress", 0) for e in learning) / len(learning)) if learning else 0
    st.markdown(f'<div class="track"><div><small>수강중</small><strong>{cnt("learning")}</strong></div><div><small>수료</small><strong>{cnt("done")}</strong></div>'
                f'<div><small>관심</small><strong>{cnt("interested")}</strong></div><div><small>수강중 평균 진도</small><strong>{avg}%</strong></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-title">🎯 내 목표</div>', unsafe_allow_html=True)
    if not S.goals:
        st.markdown('<div class="notice">아직 목표가 없어요. 승진·이직·직무 전환·역량 강화 중 하나를 골라 요건을 고르면 진행률을 추적해 드려요.</div>', unsafe_allow_html=True)
    for gi, goal in enumerate(S.goals):
        ic, name, _ = GOAL_TYPES[goal["type"]]
        done = sum(r["done"] for r in goal["reqs"])
        pct = round(done / len(goal["reqs"]) * 100) if goal["reqs"] else 0
        dday = ""
        if goal["deadline"]:
            days = (date.fromisoformat(goal["deadline"]) - date.today()).days
            dday = f" · D-{days}" if days > 0 else " · D-Day" if days == 0 else f" · 기한 {-days}일 지남"
        with st.container(border=True):
            st.markdown(f"**{ic} {name} · {escape(goal['title'])}**{dday}")
            st.progress(pct / 100, text=f"{pct}% · 요건 {done}/{len(goal['reqs'])}개 달성")
            for ri, r in enumerate(goal["reqs"]):
                k = f"req_{gi}_{ri}"
                st.checkbox(r["label"], value=r["done"], key=k, on_change=toggle_req, args=(gi, ri, k))
            st.button("목표 삭제", key=f"gdel_{gi}", on_click=del_goal, args=(gi,))
    if len(S.goals) < 3:
        with st.expander("＋ 새 목표 만들기"):
            gtype = st.radio("목표 종류", list(GOAL_TYPES), format_func=lambda k: f"{GOAL_TYPES[k][0]} {GOAL_TYPES[k][1]} · {GOAL_TYPES[k][2]}", key="goal_type")
            c1, c2 = st.columns([2, 1])
            title = c1.text_input("목표 이름 (비워 두면 자동)", key="goal_title")
            deadline = c2.date_input("기한", value=None, key="goal_deadline")
            cands = goal_candidates(gtype)
            reqs = st.multiselect("달성할 요건 고르기", cands, default=[c for c in cands if c.startswith(("부족 역량", "업무 숙련도"))], key="goal_reqs")
            st.button("목표 저장", type="primary", on_click=add_goal, args=(gtype, title, deadline, reqs), disabled=not reqs)

    st.markdown('<div class="sec-title">🩺 나의 진단 결과</div>', unsafe_allow_html=True)
    if not S.diag_log:
        st.markdown('<div class="notice">아직 저장한 진단이 없어요. 2단계에서 진단한 뒤 "이 진단 저장하고 추적하기"를 눌러 주세요.</div>', unsafe_allow_html=True)
    else:
        last = S.diag_log[-1]
        lg, std = G[last["g"]], cp.LEVEL_OF_GRADE[last["g"]]
        gap = (f"직급 기준({std + 1}단계)보다 {std - last['lvl']}단계 낮아 집중 보완이 필요해요" if last["lvl"] < std
               else "직급 기준에 맞는 수준이에요" if last["lvl"] == std else "직급 기준보다 높은 수준이에요")
        overall = round(sum(skill_progress(s) for s in last["skills"]) / len(last["skills"])) if last["skills"] else 0
        st.markdown(f"""<div class="focus"><div class="eyebrow">마지막 저장 진단 · {last['at'][:10]}</div>
          <h3>{escape(lg['name'])} · {', '.join(escape(dom_short(x)) for x in last['ds'])}</h3>
          <div class="fgrid"><div class="fitem"><small>자가진단 숙련도</small><strong>{last['lvl'] + 1}단계 · {LEVEL_NAMES[last['lvl']]}</strong></div>
          <div class="fitem"><small>직급 기준 비교</small><strong>{gap}</strong></div><div class="fitem"><small>부족 역량 보완율</small><strong>{overall}%</strong></div></div>
          <div class="pbar"><span style="width:{overall}%"></span></div></div>""", unsafe_allow_html=True)
        for s in last["skills"]:
            p = skill_progress(s)
            st.progress(p / 100, text=f"🎯 {s} · 보완 진행률 {p}%{'' if p else ' · 이 역량으로 담은 교육을 수강중으로 바꾸면 추적돼요'}")
        if len(S.diag_log) > 1:
            with st.expander(f"🕘 진단 이력 ({len(S.diag_log)}회)"):
                for d in reversed(S.diag_log):
                    st.markdown(f"- {d['at'][:16].replace('T', ' ')} · {G[d['g']]['name']} · {d['lvl'] + 1}단계 · 보강 역량 {', '.join(d['skills']) or '없음'}")

    st.markdown(f'<div class="sec-title">📚 내 수강 목록 ({len(items)})</div>', unsafe_allow_html=True)
    if not items:
        st.markdown('<div class="notice">아직 담은 교육이 없어요. 교육 카드의 "＋ 수강 신청 표시"를 누르면 여기서 진도를 관리할 수 있어요.</div>', unsafe_allow_html=True)
    for uid, e in items:
        with st.container(border=True):
            st.markdown(f"**{escape(e['title'])}**  \n<span class='hint'>🏢 {escape(e['inst'])} · {escape(e['plat'])} · 담은 날 {e['startedAt'][:10]}"
                        f"{' · ' + escape(e['for']) + ' 보완용' if e.get('for') else ''}</span>", unsafe_allow_html=True)
            k = f"st_{uid}"
            if k not in S:
                S[k] = e["status"]
            st.segmented_control("상태", list(ST_LABEL), format_func=lambda x: ST_LABEL[x], key=k, on_change=set_enroll_status, args=(uid, k), label_visibility="collapsed")
            if e["status"] == "learning":
                pk = f"pg_{uid}"
                if pk not in S:
                    S[pk] = e.get("progress", 0)
                st.slider("진도율", 0, 100, step=5, key=pk, on_change=set_progress, args=(uid, pk))
            c1, c2, _ = st.columns([1, 1, 3])
            if str(e.get("url", "")).startswith("https://"):
                c1.link_button("강의 이동 ↗", e["url"], use_container_width=True)
            c2.button("삭제", key=f"del_{uid}", on_click=del_enroll, args=(uid,), use_container_width=True)
    if items or S.diag_log or S.goals:
        st.button("기록 전체 삭제", on_click=reset_track)


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
# 주소에 ?demo=1 을 붙이면 샘플 진단 결과(3단계)로 바로 열림 (발표·시연용)
if st.query_params.get("demo") == "1" and not S.get("_demo_loaded"):
    S._demo_loaded = True
    load_sample()
hero()
stepbar()
if S.step in ("2", "3") and not ready():
    S.step = "1"
{"1": view_pick, "2": view_tasks, "3": view_courses, "all": view_all, "my": view_my}[S.step]()
st.markdown("---")
st.caption("교육 정보는 각 교육기관과 고용24의 공개 정보를 모은 것이에요. 수강료·일정은 바뀔 수 있으니 신청 전 교육기관에서 확인해 주세요. "
           "공식 만족도는 고용24 수강생 설문 점수로, 응답자 수가 공개되지 않아 추천 순위에는 쓰지 않아요.")
