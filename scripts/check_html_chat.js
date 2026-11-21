// 고객 대시보드 HTML의 AI 상담 탭 점검 (Node로 실행, 브라우저 없이 같은 코드로 계산)
// 실행: node scripts/check_html_chat.js [대상 html]
// - 업무명 90개 자기 1위, 인사 질문·무관 질문의 결과 종류를 계산해 docs/html_chat_threshold_report.md 에 쓴다
// - 점검 조건을 어기면 종료 코드 1
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const target = process.argv[2] || fs.readdirSync(ROOT).filter(f => /^hr_career_platform_v2_.*\.html$/.test(f)).sort().pop();
const html = fs.readFileSync(path.resolve(ROOT, target), 'utf8');

const dataStart = html.indexOf('const DATA = ') + 'const DATA = '.length;
const dataEnd = html.indexOf('\n', dataStart);
const DATA = JSON.parse(html.slice(dataStart, dataEnd).replace(/;\s*$/, ''));
const grab = name => { const m = html.match(new RegExp(`function ${name}\\([\\s\\S]*?\\r?\\n}\\r?\\n`)); if (!m) throw new Error('함수 없음: ' + name); return m[0]; };
const chat = html.slice(html.indexOf('/* ==== AI_CHAT_START ==== */'), html.indexOf('/* ==== AI_CHAT_END ==== */'));
const core = chat.slice(0, chat.indexOf('function viewChat'));

const HR = ['4대보험 신고를 처음 맡았어요', '4대보험 신고 처음이에요', '직무급제 도입을 검토 중인데 뭘 알아야 해?', '신입사원 온보딩 프로그램을 기획해야 해요',
  '노사협의회 운영 절차가 궁금해요', '파이썬으로 인사 데이터 분석하고 싶어요', '엑셀 실무 강좌 알려줘', '퇴직금 계산이 복잡해요',
  '성희롱 예방교육 법정의무교육 찾아줘', '평가 면담을 잘하고 싶어요', '채용 공고 쓰는 법을 배우고 싶어요', '연말정산 처음 해봐요'];
const NON = ['안녕 반가워', '오늘 날씨 어때', '점심 메뉴 추천해줘', '파이썬으로 웹크롤링하는 법', '토익 점수 올리는 꿀팁', '국내 주식 투자 전략',
  '주말에 드라이브 갈만한 코스', '헬스장 초보 분할 운동 루틴', '넷플릭스 주말 영화 추천', '스마트폰 요금제 알뜰폰 비교'];

const run = new Function('DATA', 'HR', 'NON', `
  const D = DATA.domains, C = DATA.courses;
  const TASK_INDEX = {}; D.forEach(d => (d.tasks || []).forEach(t => { TASK_INDEX[t.id] = { ...t, domId: d.id }; }));
  const COURSE_BY_ID = new Map(C.map(c => [c.id, c])); const REC_LEVEL = [0, 1, 1, 2, 2];
  const state = { g: null, tl: {}, budget: false }; const domOf = id => D.find(x => x.id === id);
  ${grab('diversify')}
  ${core.replace('const CHAT = { msgs: [], idx: null };', '')}
  const CHAT = { msgs: [], idx: null };
  const row = q => { const s = chatTaskScores(q); const a = chatAnswer(q);
    return { q, mode: a.mode, top: +s[0].s.toFixed(3), margin: +(s[0].s - s[1].s).toFixed(3), t1: s[0].t.name, t2: s[1].t.name, courses: a.courses.map(c => c.t) }; };
  const tasks = Object.values(TASK_INDEX);
  const selfTop = tasks.filter(t => chatTaskScores(t.name)[0].t.id === t.id).length;
  const selfModes = {}; tasks.forEach(t => { const m = chatClassify(chatTaskScores(t.name), t.name); selfModes[m] = (selfModes[m] || 0) + 1; });
  return { conf: CHAT_CONF, n: tasks.length, selfTop, selfModes, hr: HR.map(row), non: NON.map(row) };
`);
const r = run(DATA, HR, NON);

const md = [
  '# HTML 대시보드 AI 상담 기준값 점검', '',
  `\`node scripts/check_html_chat.js\` 실행 결과 (대상: \`${target}\`).`, '',
  '## 계산 방식',
  '- 브라우저 안에서만 계산합니다(외부 호출 없음). 의미 유사도 모델은 쓰지 않습니다.',
  '- 업무 연결: 질문(흔한 말 제거)과 90개 업무(업무명 2배·쉬운 설명·지식·기술)의 글자 2개 묶음 TF-IDF 코사인 유사도',
  '- 과정 검색: 과정명(2배)·학습목표·커리큘럼 BM25, 인사 직접 관련 과정 ×1.15, 같은 과정명 1번만, 제외 목록·이벤트 안내 제외', '',
  '## 기준값',
  `- 업무 연결: 점수 ≥ ${r.conf.confident} 이고 1·2위 차이 ≥ ${r.conf.margin}`,
  `- 업무 후보 버튼: 점수 ≥ ${r.conf.candidate}`,
  `- 범위 밖: 점수 < ${r.conf.outOfScope} 이고 인사 관련 단어 없음`,
  '- 질문 수가 적어 확정값이 아닙니다. 애매하면 업무를 단정하지 않고 후보를 보여 주는 쪽으로 정했습니다.', '',
  '## 근거',
  `- 업무명 ${r.n}개를 그대로 넣었을 때 자기 업무 1위: ${r.selfTop}/${r.n}, 결과 종류: ${JSON.stringify(r.selfModes)}`,
  `- 인사와 무관한 질문 ${r.non.length}개 최고 점수: ${Math.max(...r.non.map(x => x.top))}`, '',
  '## 인사 질문', '| 질문 | 결과 | 점수 | 1·2위 차이 | 1위 업무 | 2위 업무 |', '| --- | --- | ---: | ---: | --- | --- |',
  ...r.hr.map(x => `| ${x.q} | ${x.mode} | ${x.top} | ${x.margin} | ${x.t1} | ${x.t2} |`), '',
  '## 인사와 무관한 질문', '| 질문 | 결과 | 점수 |', '| --- | --- | ---: |',
  ...r.non.map(x => `| ${x.q} | ${x.mode} | ${x.top} |`), '',
  '1위 업무가 질문 의도에 맞는지는 팀이 판단합니다(이 보고서는 판단을 적지 않습니다).', ''];
fs.writeFileSync(path.join(ROOT, 'docs/html_chat_threshold_report.md'), md.join('\n'));

const fails = [];
if (r.selfTop !== r.n) fails.push(`업무명 자기 1위 ${r.selfTop}/${r.n}`);
r.non.forEach(x => { if (x.mode !== 'out') fails.push(`무관 질문이 범위 밖이 아님: ${x.q} (${x.mode})`); });
r.hr.forEach(x => { if (x.mode === 'out') fails.push(`인사 질문이 범위 밖으로 처리됨: ${x.q}`); });
const job = r.hr.find(x => x.q.startsWith('직무급제'));
if (job.mode === 'task' && job.t1.includes('직무 순환')) fails.push('직무급제가 직무 순환으로 연결됨');
r.hr.forEach(x => { if (x.mode !== 'out' && !x.courses.length) fails.push(`과정이 없음: ${x.q}`); });
console.log(`업무명 자기 1위 ${r.selfTop}/${r.n}`);
r.hr.concat(r.non).forEach(x => console.log(x.mode.padEnd(6), x.top.toFixed(3), x.q, '->', x.mode === 'out' ? '' : x.t1));
if (fails.length) { console.error('점검 실패:\n- ' + fails.join('\n- ')); process.exit(1); }
console.log('점검 통과, 보고서: docs/html_chat_threshold_report.md');
