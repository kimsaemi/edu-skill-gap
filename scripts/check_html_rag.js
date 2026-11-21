// 고객 대시보드 HTML의 '📄 자료 질문' 패널 점검 (Node, 브라우저 없이 같은 엔진으로 계산)
// 실행: node scripts/check_html_rag.js [대상 html]
// - 질문 묶음 결과를 docs/html_rag_threshold_report.md 에 쓰고, 점검 조건을 어기면 종료 코드 1
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const target = process.argv[2] || fs.readdirSync(ROOT).filter(f => /^hr_career_platform_v2_.*\.html$/.test(f)).sort().pop();
const html = fs.readFileSync(path.resolve(ROOT, target), 'utf8');
const lineOf = prefix => { const i = html.indexOf(prefix); if (i < 0) throw new Error('없음: ' + prefix); const e = html.indexOf('\n', i); return JSON.parse(html.slice(i + prefix.length, e).replace(/;\s*$/, '')); };
const DATA = lineOf('const DATA = ');
const RAG_DOCS = lineOf('const RAG_DOCS = ');
const RAG_EXCLUDE = lineOf('const RAG_EXCLUDE = ');
const ui = fs.readFileSync(path.join(ROOT, 'src/html_rag/rag_ui.js'), 'utf8');
const DOC_T = Number(ui.match(/LOCAL_THRESHOLD = ([0-9.]+)/)[1]);
const COURSE_T = Number(ui.match(/COURSE_THRESHOLD = ([0-9.]+)/)[1]);
const R = require(path.join(ROOT, 'src/html_rag/rag_engine.js'));
const index = R.buildIndex(R.buildCorpus(RAG_DOCS, DATA, RAG_EXCLUDE));

const GRADE_Q = [['주임이 갖춰야 할 역량은?', '주임'], ['대리는 어떤 일을 하나요?', '대리'], ['과장 승진 기준이 뭐야?', '과장'], ['차장의 역할은?', '차장'], ['부장 미션 알려줘', '부장']];
const HR_Q = ['4대보험 신고 처음이에요', '평가 면담을 잘하고 싶어요', '직무급제 도입', '신입사원 온보딩 기획', '노사협의회 운영 절차가 궁금해요',
  '연말정산 교육 추천해줘', '엑셀 실무 강좌 알려줘', '취업규칙 개정 절차'];
const NON_Q = ['안녕 반가워', '오늘 날씨 어때', '점심 메뉴 추천해줘', '국내 주식 투자 전략', '넷플릭스 주말 영화 추천', '헬스장 초보 분할 운동 루틴',
  '토익 점수 올리는 꿀팁', '스마트폰 요금제 알뜰폰 비교', '주말에 드라이브 갈만한 코스', '제주도 여행 맛집 알려줘'];
// ('파이썬으로 웹크롤링하는 법'은 이 프로젝트의 크롤링 보고서가 근거로 나오는 것이 맞아서 무관 질문에서 뺐다)
const label = h => h.kind === 'doc' ? `문서 · ${h.d.replace('대시보드 · ', '')}${h.s ? ' / ' + h.s : ''}` : `과정 · ${h.key}`;
const run = q => R.search(index, q, 5, DOC_T, COURSE_T);

const fails = [];
const rows = [];
GRADE_Q.forEach(([q, g]) => { const h = run(q); rows.push([q, h]); if (!h.length || !(h[0].d.includes('직급별 성장 가이드') && String(h[0].s).includes(g))) fails.push(`직급 질문 1위가 ${g} 성장 가이드가 아님: ${q}`); });
HR_Q.forEach(q => { const h = run(q); rows.push([q, h]); if (!h.length) fails.push(`인사 질문에 근거 없음: ${q}`); });
const nonRows = NON_Q.map(q => [q, run(q)]);
nonRows.forEach(([q, h]) => { if (h.length) fails.push(`무관 질문에 근거가 나옴: ${q} → ${label(h[0])}`); });
const courseKeys = index.courses.items.map(c => c.key);
if (courseKeys.some(k => /이벤트|\bevent\b|할인/i.test(k))) fails.push('이벤트·할인 과정이 검색 대상에 남아 있음');

const md = ['# HTML 대시보드 \'자료 질문\' 기준값 점검', '',
  `\`node scripts/check_html_rag.js\` 실행 결과 (대상: \`${target}\`).`, '',
  '## 계산 방식',
  '- 브라우저 안에서만 계산합니다(서버·AI 호출 없음). 결과는 찾은 근거를 그대로 보여 줍니다.',
  `- 검색 대상: 문서 조각 ${RAG_DOCS.length}개(${new Set(RAG_DOCS.map(d => d.d)).size}종) + 교육과정 ${index.courses.items.length}개(같은 제목 1번, 제외 목록 ${RAG_EXCLUDE.length}개·이벤트 안내 제외)`,
  '- 글자 2·3개 묶음 TF-IDF 코사인. 흔한 말·어미(처음이에요, 싶어요 등)는 뺍니다.',
  '- 문서와 교육과정은 따로 점수를 매깁니다. 교육과정은 최대 3건, 인사·업무 관련 단어가 있는 질문에만 보여 줍니다.',
  '- 직급(주임~부장)을 물으면 직급별 성장 가이드의 해당 직급 조각에 +0.3을 줍니다.', '',
  '## 기준값', `- 문서 ≥ ${DOC_T} (설정 막대로 바꿀 수 있음), 교육과정 ≥ ${COURSE_T}`,
  '- 질문 수가 적어 확정값이 아닙니다.', '',
  '## 인사·직급 질문', '| 질문 | 근거 (점수) |', '| --- | --- |',
  ...rows.map(([q, h]) => `| ${q} | ${h.length ? h.map(x => `${label(x)} (${x.score.toFixed(2)})`).join('<br>') : '찾지 못함'} |`), '',
  '## 인사와 무관한 질문', '| 질문 | 결과 |', '| --- | --- |',
  ...nonRows.map(([q, h]) => `| ${q} | ${h.length ? label(h[0]) : '찾지 못함'} |`), '',
  '근거가 질문에 맞는지는 팀이 판단합니다(이 보고서는 판단을 적지 않습니다).', ''];
fs.writeFileSync(path.join(ROOT, 'docs/html_rag_threshold_report.md'), md.join('\n'));
rows.concat(nonRows).forEach(([q, h]) => console.log(q.padEnd(24), h.length ? label(h[0]).slice(0, 50) : '(찾지 못함)'));
if (fails.length) { console.error('점검 실패:\n- ' + fails.join('\n- ')); process.exit(1); }
console.log('점검 통과, 보고서: docs/html_rag_threshold_report.md');
