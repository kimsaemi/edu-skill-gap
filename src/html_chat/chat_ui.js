function viewChat() {
  const ex = ['4대보험 신고 처음이에요', '직무급제 도입 고민', '신입사원 온보딩 기획', '평가 면담을 잘하고 싶어요'];
  const msgs = CHAT.msgs.map((m, mi) => {
    if (m.role === 'user') return `<div class="chat-msg user"><span class="chat-ico">🙋</span><div>${esc(m.text)}</div></div>`;
    const a = m.a;
    const cands = (a.cands || []).map(t => `<button type="button" class="chip" data-act="chat-pick" data-t="${esc(t.id)}" data-mi="${mi}">📌 ${esc(t.name)}</button>`).join('');
    const cards = (a.courses || []).map(c => courseCard({ c, kind: c.cat === 'HR' ? 'direct' : 'common', why: chatWhy(a.q, c, a.task) + ' (자동 생성 문장)' })).join('');
    return `<div class="chat-msg bot"><span class="chat-ico">🤖</span><div><div>${esc(a.text)}</div>
      ${cands ? `<div class="chips" style="margin:8px 0">${cands}</div>` : ''}
      ${cards ? `<div class="grid" style="margin-top:10px">${cards}</div>` : ''}</div></div>`;
  }).join('');
  return `<div class="shead"><span class="badge">상담</span><h2>💬 AI 상담</h2></div>
    <p class="hint">업무 고민을 적으면 90개 인사 업무 중 가까운 업무를 찾아 실제 교육과정을 골라 드려요. 이 페이지 안에서만 계산하고 외부로 보내지 않아요. 추천 이유는 겹치는 단어로 만든 자동 생성 문장이에요.</p>
    <div class="chips" style="margin:8px 0">${ex.map(q => `<button type="button" class="chip" data-act="chat-q" data-v="${esc(q)}">${esc(q)}</button>`).join('')}</div>
    <div class="chat-box">${msgs || '<p class="sub">예시를 누르거나 아래에 질문을 적어 보세요.</p>'}</div>
    <div class="chat-input"><input type="text" id="chatIn" placeholder="업무 고민이나 배우고 싶은 내용을 입력하세요 (예: 연말정산 처음 해봐요)" aria-label="AI 상담 질문">
      <button type="button" class="btn primary" data-act="chat-send">보내기</button>
      ${CHAT.msgs.length ? '<button type="button" class="btn" data-act="chat-reset">대화 지우기</button>' : ''}</div>`;
}
function chatPush(q, a) {
  if (!a) return;
  CHAT.msgs.push({ role: 'user', text: q }, { role: 'bot', a });
  render();
  const boxes = document.querySelectorAll('.chat-msg.bot');
  if (boxes.length) boxes[boxes.length - 1].scrollIntoView({ block: 'start' });
}
function chatSend(q) { const qq = String(q || '').trim(); if (qq) chatPush(qq, chatAnswer(qq)); }
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-act^="chat-"]');
  if (!el) return;
  switch (el.dataset.act) {
    case 'chat-q': chatSend(el.dataset.v); break;
    case 'chat-send': { const inp = document.getElementById('chatIn'); chatSend(inp && inp.value); break; }
    case 'chat-pick': {
      const prev = CHAT.msgs[Number(el.dataset.mi)];
      const t = TASK_INDEX[el.dataset.t];
      if (t) chatPush('📌 ' + t.name, chatPick(t.id, prev && prev.a ? prev.a.q : t.name));
      break;
    }
    case 'chat-reset': CHAT.msgs = []; render(); break;
  }
});
document.addEventListener('keydown', ev => {
  if (ev.target.id === 'chatIn' && ev.key === 'Enter' && !ev.isComposing) { ev.preventDefault(); chatSend(ev.target.value); }
});
