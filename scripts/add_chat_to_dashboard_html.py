"""
고객 대시보드 HTML(hr_career_platform_v2_*.html)에 '💬 AI 상담' 탭을 넣는다.

- 상담 코드: src/html_chat/chat_core.js(업무 연결·검색·추천 이유), src/html_chat/chat_ui.js(화면·이벤트)
- 브라우저 안에서만 계산한다(외부 호출·비용 없음). 업무 연결은 글자 2개 묶음 TF-IDF, 과정 검색은 BM25.
- 제외 목록(data/hr/processed/off_topic_exclusions.csv)에 오른 과정은 상담 결과에서 뺀다.
- 이미 넣은 파일에 다시 실행하면 상담 코드만 새로 바꾼다(여러 번 실행해도 결과가 같다).
- GSEEK 상세 링크 보정도 함께 적용한다(src/course_links.py).
- 오른쪽 아래 '📄 자료 질문' 패널(문서·직무 기준·교육과정에서 근거 찾기)도 넣는다:
  src/html_rag/(rag_docs.json, rag_engine.js, rag_ui.js, rag_panel.html, rag.css)

실행: python scripts/add_chat_to_dashboard_html.py [대상 html]   (생략하면 가장 최신 hr_career_platform_v2_*.html)
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.course_links import detail_url  # noqa: E402

START, END = "/* ==== AI_CHAT_START ==== */", "/* ==== AI_CHAT_END ==== */"
CSS_START, CSS_END = "/* ==== AI_CHAT_CSS_START ==== */", "/* ==== AI_CHAT_CSS_END ==== */"
CSS = """
  .chat-box { display: flex; flex-direction: column; gap: 14px; margin: 14px 0; }
  .chat-msg { display: flex; gap: 10px; align-items: flex-start; }
  .chat-msg > div { flex: 1; min-width: 0; }
  .chat-msg.user > div { background: var(--primary-soft); border-radius: 12px; padding: 10px 14px; font-weight: 700; }
  .chat-ico { font-size: 22px; line-height: 1.4; }
  .chat-input { display: flex; gap: 8px; flex-wrap: wrap; position: sticky; bottom: 0; background: var(--surface); padding: 10px 0; }
  .chat-input input { flex: 1; min-width: 200px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; font-size: 15px; background: var(--surface); color: inherit; }
"""

# (바꿀 원문, 새 문장) - 원문이 정확히 1번 나와야 한다. 이미 바뀐 파일이면 건너뛴다.
PATCHES = [
    ("state.step = ['1', '2', '3', 'all', 'my'].includes(s) ? s : '1';",
     "state.step = ['1', '2', '3', 'all', 'my', 'chat'].includes(s) ? s : '1';"),
    ("const views = { '1': viewPick, '2': viewTasks, '3': viewCourses, all: viewAll, my: viewMy };",
     "const views = { '1': viewPick, '2': viewTasks, '3': viewCourses, all: viewAll, my: viewMy, chat: viewChat };"),
    ("if (!ready() || ['1', 'all', 'my'].includes(state.step)) { el.innerHTML = ''; return; }",
     "if (!ready() || ['1', 'all', 'my', 'chat'].includes(state.step)) { el.innerHTML = ''; return; }"),
    ("}).join('') + `<button type=\"button\" class=\"step ${state.step === 'my' ? 'on' : ''}\" data-act=\"step\" data-v=\"my\" style=\"margin-left:auto\">",
     "}).join('') + `<button type=\"button\" class=\"step ${state.step === 'chat' ? 'on' : ''}\" data-act=\"step\" data-v=\"chat\" style=\"margin-left:auto\"><span>💬</span><span>AI 상담</span></button>`"
     " + `<button type=\"button\" class=\"step ${state.step === 'my' ? 'on' : ''}\" data-act=\"step\" data-v=\"my\">"),
    ('<button type="button" data-act="step" data-v="my" id="heroMy">',
     '<button type="button" data-act="step" data-v="chat">💬 AI 상담</button><button type="button" data-act="step" data-v="my" id="heroMy">'),
]


RAG_START, RAG_END = "<!-- ==== RAG_PANEL_START ==== -->", "<!-- ==== RAG_PANEL_END ==== -->"
RAG_CSS_START, RAG_CSS_END = "/* ==== RAG_CSS_START ==== */", "/* ==== RAG_CSS_END ==== */"
# AI 상담 화면에서는 입력창과 겹치지 않게 '자료 질문' 버튼을 숨긴다
RAG_FAB_TOGGLE = """
(() => {
  const sync = () => { const f = document.getElementById('ragFab'); if (f) f.style.display = /(^|&)s=chat(&|$)/.test(location.hash.slice(1)) ? 'none' : ''; };
  window.addEventListener('hashchange', sync); sync();
})();
"""


LEGACY_RAG_SCRIPT_SIGNS = ("const RAG_DOCS", "const RagEngine", "'ragFab'", '"ragFab"')


def strip_legacy_rag(text: str) -> str:
    """마커 없이 들어간 예전 '자료 질문' 코드(11-18_rag판 형식)를 지운다.
    자료 질문에 속한 조각만 하나씩 지운다 (그 사이의 다른 코드는 남긴다):
      - <button ... id="ragFab"> ... </button>
      - <section ... id="ragPanel"> ... </section>
      - 내용에 RAG_DOCS·RagEngine·ragFab 이 들어 있는 <script> 블록 (문서 데이터·엔진·화면, 보통 3개)
      - <style> 안의 .rag-* 규칙"""
    n0 = len(text)
    text, n_btn = re.subn(r'\ufeff?<button\b[^>]*\bid=["\']ragFab["\'][^>]*>.*?</button>\s*', "", text, flags=re.S)
    text, n_sec = re.subn(r'\ufeff?<section\b[^>]*\bid=["\']ragPanel["\'][^>]*>.*?</section>\s*', "", text, flags=re.S)
    n_scr = 0

    def drop_script(m):
        nonlocal n_scr
        if any(sig in m.group(1) for sig in LEGACY_RAG_SCRIPT_SIGNS):
            n_scr += 1
            return ""
        return m.group(0)

    text = re.sub(r"\ufeff?<script\b[^>]*>(.*?)</script>\s*", drop_script, text, flags=re.S)
    if not (n_btn and n_sec and n_scr):
        raise SystemExit(f"예전 '자료 질문' 코드를 일부만 찾음(버튼 {n_btn}, 패널 {n_sec}, 스크립트 {n_scr}): 직접 확인 필요")
    if "readHash();" not in text or "const DATA = " not in text:
        raise SystemExit("대시보드 본 코드가 지워졌음: 중단")
    style_end = text.find("</style>")
    head, rest = text[:style_end], text[style_end:]
    kept, skip = [], False
    for line in head.split("\n"):
        st = line.strip()
        if st.startswith(".rag-") or (st.startswith("@media") and ".rag-" in st):
            skip = st.count("{") > st.count("}")
            continue
        if skip:
            skip = not st.endswith("}")
            continue
        kept.append(line)
    text = "\n".join(kept) + rest
    print(f"예전 자료 질문 코드 제거: 버튼 {n_btn}, 패널 {n_sec}, 스크립트 {n_scr}, {n0 - len(text):,}자")
    return text


def inject_rag(text: str, excl_in_html: list) -> str:
    rag = ROOT / "src" / "html_rag"
    # 예전 '자료 질문' 코드(마커 없이 들어간 것 포함)가 있으면 먼저 지운다
    text = re.sub(re.escape(RAG_START) + r".*?" + re.escape(RAG_END) + r"\n?", "", text, flags=re.S)
    text = re.sub(re.escape(RAG_CSS_START) + r".*?" + re.escape(RAG_CSS_END) + r"\n?", "", text, flags=re.S)
    if 'id="ragFab"' in text:
        text = strip_legacy_rag(text)
    css = (rag / "rag.css").read_text(encoding="utf-8")
    text = text.replace("</style>", f"{RAG_CSS_START}\n{css}{RAG_CSS_END}\n</style>", 1)
    docs = json.loads((rag / "rag_docs.json").read_text(encoding="utf-8"))
    block = "\n".join([
        RAG_START,
        (rag / "rag_panel.html").read_text(encoding="utf-8").strip(),
        "<script>",
        "const RAG_DOCS = " + json.dumps(docs, ensure_ascii=False, separators=(",", ":")) + ";",
        "const RAG_EXCLUDE = " + json.dumps(excl_in_html, ensure_ascii=False) + ";",
        (rag / "rag_engine.js").read_text(encoding="utf-8"),
        (rag / "rag_ui.js").read_text(encoding="utf-8"),
        RAG_FAB_TOGGLE,
        "</script>",
        RAG_END, ""])
    if text.count("</body>") != 1:
        raise SystemExit("</body>를 찾지 못함")
    return text.replace("</body>", block + "</body>")


def latest_html() -> Path:
    return sorted(ROOT.glob("hr_career_platform_v2_*.html"))[-1]


def main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # 1) GSEEK 상세 링크 보정 (DATA 안의 모든 GSEEK 과정 링크)
    pat = re.compile(r"https://www\.gseek\.kr/user/course/online/view\?s_sbjct_sn=\d+(?:&s_sbjct_cycl_sn=\d+)?")
    text, n_links = pat.subn(lambda m: detail_url(m.group(0)), text)

    # 2) 화면 연결 패치
    applied = 0
    for old, new in PATCHES:
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"패치 위치를 찾지 못함(대시보드 구조가 바뀜): {old[:60]}")
        text = text.replace(old, new)
        applied += 1

    # 3) CSS
    css_block = f"{CSS_START}{CSS}  {CSS_END}\n"
    text = re.sub(re.escape(CSS_START) + r".*?" + re.escape(CSS_END) + r"\n?", "", text, flags=re.S)
    text = text.replace("</style>", css_block + "</style>", 1)

    # 4) 상담 코드 (제외 목록은 이 HTML에 들어 있는 과정만 넣는다)
    data_start = re.search(r"const DATA = ", text).end()
    data, _ = json.JSONDecoder().raw_decode(text[data_start:])
    ids = {c["id"] for c in data["courses"]}
    excl = pd.read_csv(ROOT / "data/hr/processed/off_topic_exclusions.csv", dtype=str)["course_uid"]
    excl_in_html = sorted(ids & set(excl))
    core = (ROOT / "src/html_chat/chat_core.js").read_text(encoding="utf-8").replace(
        "__CHAT_EXCLUDE__", json.dumps(excl_in_html, ensure_ascii=False))
    ui = (ROOT / "src/html_chat/chat_ui.js").read_text(encoding="utf-8")
    block = f"{START}\nconst CHAT = {{ msgs: [], idx: null }};\n{core}\n{ui}\n{END}\n"
    text = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", "", text, flags=re.S)
    tail = "readHash();\nrender();\n</script>"
    if text.count(tail) != 1:
        raise SystemExit("마지막 실행 부분(readHash/render)을 찾지 못함")
    text = text.replace(tail, block + tail)

    # 5) '자료 질문' 패널
    text = inject_rag(text, excl_in_html)

    path.write_text(text, encoding="utf-8")
    print(f"{path.name}: GSEEK 링크 {n_links}개 확인, 화면 패치 {applied}개 적용, 상담 제외 과정 {len(excl_in_html)}개, 자료 질문 패널 포함")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else latest_html())
