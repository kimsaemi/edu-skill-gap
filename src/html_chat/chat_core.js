// ===== AI 상담: 브라우저 안에서만 동작 (외부 호출·비용 없음) =====
// 업무 연결: 질문과 90개 업무(업무명·쉬운 설명·지식·기술)의 글자 2개 묶음(bigram) TF-IDF 코사인 유사도
// 과정 검색: 과정명·학습목표·커리큘럼 bigram BM25
// 기준값 근거: 저장소 docs/html_chat_threshold_report.md (질문 묶음이 작아 바뀔 수 있는 값)
const CHAT_CONF = { confident: 0.20, margin: 0.10, candidate: 0.10, outOfScope: 0.10 };
const CHAT_HR_WORDS = ['인사', '채용', '면접', '온보딩', '입사', '급여', '임금', '연봉', '보상', '평가', '성과', '복리후생', '4대보험', '보험',
  '근로', '노동', '노사', '노무', '퇴직', '연말정산', '교육', '훈련', '조직', '직무', '직급', '인력', '취업규칙', '연차', '휴가',
  '징계', '해고', '괴롭힘', '성희롱', '고충', '승진', '면담', 'hr', 'hrd', '엑셀', '보고서', '리더십', '코칭', '인재', '역량', '사원', '팀장'];
const CHAT_STOP = new Set(['알아야', '알아', '검토', '중인데', '고민', '모르겠어', '복잡', '찾아줘', '관리', '신규', '교재', '운영', '기본', '하고', '싶어', '싶어요', '해요', '어요', '에요', '알려', '알려줘', '처음', '궁금', '궁금해요', '배우', '배우고', '방법',
  '어떻게', '무엇', '뭘', '해야', '하는', '있는', '대한', '관련', '과정', '강좌', '교육', '추천', '추천해줘', '실무']);
// 저장소 제외 목록(off_topic_exclusions.csv)에 오른 과정과 이벤트·할인 안내는 상담 결과에서 뺀다
const CHAT_EXCLUDE = new Set(__CHAT_EXCLUDE__);
const chatOk = c => c && !CHAT_EXCLUDE.has(c.id) && !/이벤트|event|할인/i.test(c.t);
const CHAT_PERSONAL = [/내게\s*맞는/, /뭘\s*들어야/, /뭐부터/, /어디부터/, /진단\s*결과/, /나한테\s*맞는/];

function chatNorm(s) { return String(s || '').toLowerCase().replace(/[^0-9a-z가-힣]+/g, ' ').trim(); }
function chatBigrams(s) {
  const out = [];
  chatNorm(s).split(' ').forEach(w => {
    if (!w) return;
    if (w.length === 1) { out.push(w); return; }
    for (let i = 0; i < w.length - 1; i++) out.push(w.slice(i, i + 2));
  });
  return out;
}
function chatWords(s) {
  return chatNorm(s).split(' ').map(w => w.replace(/(이에요|예요|해요|어요|아요|해줘|이야|인데|해야)$/, '')).map(w => w.replace(/(으로|에서|에게|하고|이나|이랑|부터|까지|처럼|은|는|이|가|을|를|의|에|와|과|도|로|만)$/, ''))
    .filter(w => w.length >= 2 && !CHAT_STOP.has(w));
}

function chatQuery(q) { const w = chatWords(q); return w.length ? w.join(' ') : chatNorm(q); }

function chatIndex() {
  if (CHAT.idx) return CHAT.idx;
  // 업무 TF-IDF
  const tasks = Object.values(TASK_INDEX);
  const tdocs = tasks.map(t => chatBigrams([t.name, t.name, t.easy, t.k, t.s].join(' ')));
  const df = new Map();
  tdocs.forEach(toks => new Set(toks).forEach(x => df.set(x, (df.get(x) || 0) + 1)));
  const N = tdocs.length;
  const idf = x => Math.log((N + 1) / ((df.get(x) || 0) + 1)) + 1;
  const vec = toks => {
    const tf = new Map(); toks.forEach(x => tf.set(x, (tf.get(x) || 0) + 1));
    let norm = 0; const v = new Map();
    tf.forEach((f, x) => { const w = (1 + Math.log(f)) * idf(x); v.set(x, w); norm += w * w; });
    return { v, norm: Math.sqrt(norm) || 1 };
  };
  const tvecs = tdocs.map(vec);
  // 과정 BM25 (과정명 2배 + 학습목표 + 커리큘럼)
  const cdocs = C.map(c => chatBigrams([c.t, c.t, c.ev && c.ev.g, c.ev && c.ev.cu].filter(Boolean).join(' ')));
  const cdf = new Map(), ctf = [], clen = [];
  cdocs.forEach(toks => {
    const tf = new Map(); toks.forEach(x => tf.set(x, (tf.get(x) || 0) + 1));
    ctf.push(tf); clen.push(toks.length); tf.forEach((_, x) => cdf.set(x, (cdf.get(x) || 0) + 1));
  });
  const avg = clen.reduce((a, b) => a + b, 0) / (clen.length || 1);
  CHAT.idx = { tasks, tvecs, vec, ctf, clen, cdf, avg, CN: cdocs.length };
  return CHAT.idx;
}

function chatTaskScores(q) {
  const I = chatIndex();
  const qv = I.vec(chatBigrams(chatQuery(q)));
  return I.tasks.map((t, i) => {
    let dot = 0; const tv = I.tvecs[i];
    qv.v.forEach((w, x) => { const y = tv.v.get(x); if (y) dot += w * y; });
    return { t, s: dot / (qv.norm * tv.norm) };
  }).sort((a, b) => b.s - a.s);
}

function chatClassify(scores, q) {
  const top = scores[0] ? scores[0].s : 0, second = scores[1] ? scores[1].s : 0;
  const ql = chatNorm(q);
  const hr = CHAT_HR_WORDS.some(w => ql.includes(w));
  if (top < CHAT_CONF.outOfScope && !hr) return 'out';
  if (top >= CHAT_CONF.confident && top - second >= CHAT_CONF.margin) return 'task';
  if (top >= CHAT_CONF.candidate) return 'cand';
  return 'search';
}

function chatSearch(q, n = 3) {
  const I = chatIndex();
  const qs = [...new Set(chatBigrams(chatQuery(q)))];
  const idf = x => { const m = I.cdf.get(x) || 0; return Math.log(1 + (I.CN - m + 0.5) / (m + 0.5)); };
  const scored = [];
  I.ctf.forEach((tf, i) => {
    let s = 0;
    qs.forEach(x => { const f = tf.get(x); if (f) s += idf(x) * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * I.clen[i] / I.avg)); });
    if (s > 0 && chatOk(C[i])) scored.push({ c: C[i], s });
  });
  // 인사 직접 관련 과정에 작은 가산, 같은 과정명은 1번만
  scored.forEach(x => { if (x.c.cat === 'HR') x.s *= 1.15; });
  scored.sort((a, b) => b.s - a.s);
  const seen = new Set(), out = [];
  for (const x of scored) { const k = chatNorm(x.c.t).replace(/ /g, '').replace(/\d+$/, ''); if (seen.has(k)) continue; seen.add(k); out.push(x.c); if (out.length >= 12) break; }
  // 비용순 재정렬(prefer)은 쓰지 않고 관련도 순서를 지키며 같은 기관만 몰리지 않게 한다
  return diversify(out, c => c.plat).slice(0, n);
}

function chatTaskCourses(t, n = 3) {
  const lv = REC_LEVEL[state.g !== null ? state.g : 1];
  const rec = t.rec || [[], [], []];
  const ids = [...new Set([...(rec[lv] || []), ...(rec[1] || []), ...(rec[0] || []), ...(rec[2] || [])])];
  const seen = new Set();
  return ids.map(id => COURSE_BY_ID.get(id)).filter(c => { if (!chatOk(c)) return false; const k = chatNorm(c.t).replace(/ /g, '').replace(/\d+$/, ''); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, n);
}

// 추천 이유: 과정명·학습목표·커리큘럼에 실제로 나오는 단어만 쓴다
function chatWhy(q, c, t) {
  const text = chatNorm([c.t, c.ev && c.ev.g, c.ev && c.ev.cu].filter(Boolean).join(' '));
  const src = [q, t ? t.name : '', t ? t.k : '', t ? t.s : ''].join(' ');
  const hits = [...new Set(chatWords(src))].filter(w => text.includes(w)).sort((a, b) => b.length - a.length).slice(0, 2);
  if (!hits.length) return t ? '이 업무의 기본 추천 과정이에요. 과정 소개를 확인해 주세요.' : '질문과 가까운 과정으로 검색됐어요. 과정 소개를 확인해 주세요.';
  return t ? `과정 정보에 ${hits.map(h => `'${h}'`).join('·')} 내용이 있어 이 업무와 연결돼요.` : `질문하신 ${hits.join('·')} 관련 내용이 과정 정보에 있어요.`;
}

function chatAnswer(q) {
  const qq = String(q || '').trim();
  if (!qq) return null;
  const weak = typeof weakTasks === 'function' ? weakTasks() : [];
  if (weak.length && CHAT_PERSONAL.some(r => r.test(qq))) {
    const t = TASK_INDEX[weak[0].id] || weak[0];
    return { mode: 'personal', q: qq, task: t, text: `진단 결과에서 숙련도 차이가 가장 큰 업무 [${t.name}] 기준으로 골랐어요.`, courses: chatTaskCourses(t) };
  }
  const scores = chatTaskScores(qq);
  const mode = chatClassify(scores, qq);
  if (mode === 'out') return { mode, q: qq, text: "이 서비스는 인사 교육과정 추천용이에요. 예: '평가 면담을 잘하고 싶어요'", courses: [] };
  if (mode === 'task') {
    const t = scores[0].t;
    return { mode, q: qq, task: t, score: scores[0].s, text: `이 업무로 이해했어요: [${domOf(t.domId).short}] ${t.name}`, courses: chatTaskCourses(t) };
  }
  const courses = chatSearch(qq);
  if (mode === 'cand') {
    return { mode, q: qq, cands: scores.slice(0, 2).map(x => x.t), score: scores[0].s,
      text: '어느 업무에 가까운지 골라 주세요. 그 사이 질문과 가까운 과정을 먼저 찾아봤어요.' + (courses.length ? '' : ' (검색 결과가 없어요)'), courses };
  }
  return { mode, q: qq, score: scores[0] ? scores[0].s : 0,
    text: courses.length ? '특정 업무로 좁혀지지 않아서, 질문과 가까운 과정을 찾아봤어요.' : '맞는 과정을 찾지 못했어요. 업무를 조금 더 구체적으로 적어 주세요.', courses };
}

function chatPick(taskId, q) {
  const t = TASK_INDEX[taskId];
  if (!t) return null;
  return { mode: 'task', q, task: t, text: `이 업무로 이해했어요: [${domOf(t.domId).short}] ${t.name}`, courses: chatTaskCourses(t) };
}
