/* '자료 질문' 패널 화면. rag_server.py(별도)가 같은 주소에서 떠 있고 API 키가 있을 때만 AI 답변, 아니면 내장 검색 결과를 보여 준다. */
(() => {
  const $ = id => document.getElementById(id);
  const fab = $('ragFab'), panel = $('ragPanel'), log = $('ragLog'), form = $('ragForm');
  const qIn = $('ragQ'), send = $('ragSend'), kIn = $('ragK'), tIn = $('ragT'), tVal = $('ragTv'), status = $('ragStatus');
  const NOT_FOUND = '제공된 자료에서 답을 찾지 못했습니다.';
  const LOCAL_THRESHOLD = 0.10;        // 문서 기준값 (docs/html_rag_threshold_report.md)
  const COURSE_THRESHOLD = 0.20;       // 교육과정 기준값
  const onLocalhost = ['127.0.0.1', 'localhost'].includes(location.hostname) && /^https?:$/.test(location.protocol);
  let index = null;       // 브라우저 내장 검색 인덱스 (첫 질문 때 한 번 생성)
  let server = null;      // rag_server.py 가 같이 떠 있고 API 키가 있으면 LLM 답변 사용

  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const scroll = () => { log.scrollTop = log.scrollHeight; };
  const add = (cls, text) => { const n = el('div', 'rag-msg ' + cls, text); log.appendChild(n); scroll(); return n; };
  const safeLink = u => /^https?:\/\//.test(u || '') ? u : '';

  function renderSources(sources) {
    if (!sources.length) return;
    const box = el('details', 'rag-src'); box.open = true;
    box.appendChild(el('summary', null, `참고한 자료 ${sources.length}건`));
    const ol = el('ol');
    sources.forEach(s => {
      const li = el('li'), head = el('div');
      head.appendChild(el('b', null, `[${s.n}] ${s.title}`));
      head.appendChild(el('span', 'score', `유사도 ${s.score.toFixed(3)}`));
      li.appendChild(head);
      const meta = [s.page ? `p.${s.page}` : null, s.section || null].filter(Boolean).join(' · ');
      if (meta) li.appendChild(el('div', 'meta', meta));
      const href = safeLink(s.url);
      if (href) {
        const a = el('a', null, '원문 링크 열기 ↗'); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
        const row = el('div', 'meta'); row.appendChild(a); li.appendChild(row);
      }
      li.appendChild(el('div', 'snip', s.snippet));
      ol.appendChild(li);
    });
    box.appendChild(ol); log.appendChild(box); scroll();
  }

  function ensureIndex() {
    if (!index) index = RagEngine.buildIndex(RagEngine.buildCorpus(RAG_DOCS, DATA, RAG_EXCLUDE));
    return index;
  }

  function askLocal(q, k, thr) {
    const hits = RagEngine.search(ensureIndex(), q, k, thr, Math.max(thr, COURSE_THRESHOLD));
    if (!hits.length) return { found: false, answer: NOT_FOUND, sources: [] };
    const sources = hits.map((h, i) => ({ n: i + 1, title: h.d, page: h.p || null, section: h.s, url: h.u, score: h.score,
      snippet: h.t.length > 300 ? h.t.slice(0, 300) + '…' : h.t }));
    const lines = hits.map((h, i) => `[${i + 1}] ` + h.t.replace(/\s*\n+\s*/g, ' · ').slice(0, 150) + (h.t.length > 150 ? '…' : ''));
    const nd = hits.filter(h => h.kind === 'doc').length, nc = hits.length - nd;
    const head = [nd ? `문서 근거 ${nd}건` : '', nc ? `관련 교육과정 ${nc}건` : ''].filter(Boolean).join(' · ');
    return { found: true, sources, answer: `자료에서 찾은 ${head}입니다. (검색 결과를 그대로 보여 드려요)\n\n` + lines.join('\n') };
  }

  async function askServer(q, k, thr) {
    const res = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, top_k: k, threshold: thr }) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  async function detectServer() {
    if (!onLocalhost) return;
    try {
      const res = await fetch('/api/status'); const s = await res.json();
      if (res.ok && s.llm_configured) { server = s; status.textContent = `AI 답변 모드 · ${s.documents}개 문서 · ${s.chunks.toLocaleString()}개 조각`; }
    } catch (e) { /* 서버 없음 → 내장 검색 모드 */ }
  }

  fab.addEventListener('click', () => {
    const open = panel.classList.toggle('open');
    fab.setAttribute('aria-expanded', String(open));
    if (open) qIn.focus();
  });
  $('ragClose').addEventListener('click', () => { panel.classList.remove('open'); fab.setAttribute('aria-expanded', 'false'); fab.focus(); });
  $('ragGear').addEventListener('click', () => $('ragSet').classList.toggle('open'));
  tIn.addEventListener('input', () => { tVal.textContent = Number(tIn.value).toFixed(2); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && panel.classList.contains('open')) $('ragClose').click(); });

  tIn.value = LOCAL_THRESHOLD; tVal.textContent = LOCAL_THRESHOLD.toFixed(2);
  status.textContent = `내장 검색 모드 · 문서 ${new Set(RAG_DOCS.map(d => d.d)).size}종 + 교육과정 ${DATA.courses.length.toLocaleString()}건 (서버·AI 호출 없음)`;
  add('bot', '안녕하세요. 이 대시보드에 담긴 문서·직무 기준·교육과정에서 근거를 찾아 알려 드립니다. 자료에 없는 내용은 추측하지 않고 "찾지 못했습니다"라고 답합니다.');
  detectServer();

  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const q = qIn.value.trim();
    if (!q) return;
    add('user', q); qIn.value = ''; send.disabled = true;
    const wait = add('bot', '자료를 검색하는 중…');
    const k = Math.max(1, Math.min(Number(kIn.value) || 5, 20)), thr = Number(tIn.value);
    try {
      let r;
      if (server) { try { r = await askServer(q, k, thr); } catch (e) { server = null; r = askLocal(q, k, thr); } }
      else { await new Promise(res => setTimeout(res, 0)); r = askLocal(q, k, thr); }
      wait.textContent = r.answer;
      if (!r.found) wait.classList.add('nf'); else renderSources(r.sources);
    } catch (e) {
      wait.textContent = '오류: ' + e.message; wait.classList.add('err');
    } finally { send.disabled = false; qIn.focus(); }
  });
})();
