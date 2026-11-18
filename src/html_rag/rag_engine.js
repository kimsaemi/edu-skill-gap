/* 대시보드 내장 '자료 질문' 검색 엔진: 서버·API 키 없이 브라우저에서 동작 (글자 n-gram TF-IDF 코사인)
 * 고친 점 (2026-11-18)
 * - 흔한 말·어미 제거: '처음이에요', '싶어요' 같은 말이 엉뚱한 과정과 겹치지 않게 함
 * - 문서와 교육과정을 따로 점수 매김: 짧은 과정명이 문서 근거를 덮지 않게 하고, 각각 다른 기준값을 씀
 * - 교육과정은 같은 제목 1번만, 제외 목록(off_topic_exclusions.csv)·이벤트·할인 안내는 뺌
 * 기준값 근거: docs/html_rag_threshold_report.md (node scripts/check_html_rag.js)
 */
const RagEngine = (() => {
  const TOK = /[0-9a-z]+|[가-힣]+/g;
  const ENDING = /(이에요|예요|해요|어요|아요|했어요|해봐요|봐요|싶어요|싶어|해줘|줘요|인가요|나요|까요|ㄴ가요|합니다|입니다|이다|해야|하는|하고|하면|해서)$/;
  const JOSA = /(으로서|으로|에서|에게|이란|까지|부터|처럼|이나|이랑|이|가|은|는|을|를|의|에|와|과|도|로|만)$/;
  const STOP = new Set(['갖춰야', '해야', '할', '하는', '하고', '있는', '어떻게', '무엇', '뭐', '뭘', '어때', '알려줘', '알려', '주세요',
    '대한', '위한', '관련', '무엇인가요', '인가요', '어떤', '있나요', '추천', '필요한', '필요', '좀', '수', '것',
    '처음', '싶어', '싶어요', '잘하고', '잘하', '배우고', '배우', '궁금', '궁금해요', '방법', '해봐요', '해요', '찾아줘', '알아야', '알고',
    '교육', '과정', '강좌', '강의', '하고싶', '중인데', '검토', '고민', '모르겠어요', '복잡', '복잡해요', '정도']);
  const COURSE_BLOCK = /이벤트|event|할인/i;
  // 교육과정은 인사·업무 관련 단어가 있는 질문에만 보여 준다 (넷플릭스·주식 같은 질문에 과정이 걸리지 않게)
  const HR_WORDS = ['인사', '채용', '면접', '온보딩', '입사', '급여', '임금', '연봉', '보상', '평가', '성과', '복리후생', '4대보험', '보험',
    '근로', '노동', '노사', '노무', '퇴직', '연말정산', '훈련', '조직', '직무', '직급', '인력', '취업규칙', '연차', '휴가', '징계', '해고',
    '괴롭힘', '성희롱', '고충', '승진', '면담', 'hr', 'hrd', '엑셀', '보고서', '리더십', '코칭', '인재', '역량', '사원', '팀장',
    '주임', '대리', '과장', '차장', '부장', '원천징수', '급여계산', '교육과정', '사내교육', '직무급'];
  const GRADES = ['주임', '대리', '과장', '차장', '부장'];
  const hasHr = q => { const s = String(q).toLowerCase(); return HR_WORDS.some(w => s.includes(w)); };

  const normTok = tok => {
    if (/^[가-힣]{2,}$/.test(tok)) {
      tok = tok.replace(ENDING, '');
      if (tok.length >= 3) tok = tok.replace(JOSA, '');
    }
    return tok;
  };
  const gramsOf = text => {
    const m = new Map();
    for (let tok of (String(text).toLowerCase().match(TOK) || [])) {
      tok = normTok(tok);
      if (!tok || STOP.has(tok)) continue;
      const set = new Set([tok]);
      for (const n of [2, 3]) for (let i = 0; i + n <= tok.length; i++) set.add(tok.slice(i, i + n));
      for (const g of set) m.set(g, (m.get(g) || 0) + 1 + 0.5 * (g.length - 1));
    }
    return m;
  };

  function buildCorpus(docs, data, exclude) {
    const G = (data.grades || []).map(g => g.name);
    const ex = new Set(exclude || []);
    const out = docs.map(d => ({ kind: 'doc', t: d.t, d: d.d, p: d.p || 0, s: d.s || '', u: d.u || '' }));
    const seen = new Set();
    for (const c of data.courses || []) {
      if (ex.has(c.id) || COURSE_BLOCK.test(c.t)) continue;
      const key = String(c.t).toLowerCase().replace(/[^0-9a-z가-힣]/g, '').replace(/\d+$/, '');
      if (seen.has(key)) continue;
      seen.add(key);
      const ct = (data.cats || {})[c.cat];
      const cat = ct && typeof ct === 'object' ? (ct.name || c.cat) : (ct || c.cat || '');
      const target = (c.grades || []).map(i => G[i]).filter(Boolean).join(', ') || '전체';
      // 검색에는 과정명만 쓰고, 기관·분야·직급은 보여 주기용으로만 둔다 (공통 글자가 점수를 흐리지 않게)
      out.push({ kind: 'course', key: c.t, t: `교육과정: ${c.t}\n교육기관: ${c.inst}\n플랫폼: ${c.plat}\n분야: ${cat}\n추천 직급: ${target}`,
                 d: '대시보드 · 교육과정 목록', p: 0, s: `${c.plat} · ${cat}`, u: c.url || '' });
    }
    return out;
  }

  function buildIndex(corpus) {
    const build = items => {
      const df = new Map(), vecs = items.map(c => gramsOf(c.kind === 'course' ? c.key : c.t));
      vecs.forEach(v => v.forEach((_, g) => df.set(g, (df.get(g) || 0) + 1)));
      const N = items.length || 1, idf = g => Math.log(1 + N / (df.get(g) || 1));
      const post = new Map(), norms = new Float64Array(items.length);
      vecs.forEach((v, i) => {
        let s = 0;
        v.forEach((w, g) => { const x = w * idf(g); s += x * x; if (!post.has(g)) post.set(g, []); post.get(g).push([i, x]); });
        norms[i] = Math.sqrt(s) || 1;
      });
      return { items, post, norms, idf };
    };
    return { docs: build(corpus.filter(c => c.kind === 'doc')), courses: build(corpus.filter(c => c.kind === 'course')) };
  }

  function searchPart(part, query) {
    const q = gramsOf(query);
    let qn = 0; const qw = new Map();
    q.forEach((w, g) => { const x = w * part.idf(g); qw.set(g, x); qn += x * x; });
    qn = Math.sqrt(qn) || 1;
    const score = new Map();
    qw.forEach((x, g) => { for (const [i, y] of part.post.get(g) || []) score.set(i, (score.get(i) || 0) + x * y); });
    return [...score.entries()].map(([i, s]) => ({ ...part.items[i], score: s / (qn * part.norms[i]) })).sort((a, b) => b.score - a.score);
  }

  // topK: 전체 근거 개수, threshold: 문서 기준값, courseThreshold: 교육과정 기준값 (과정은 최대 3건)
  function search(index, query, topK, threshold, courseThreshold) {
    // 직급을 물으면 '직급별 성장 가이드'의 해당 직급 조각을 먼저 (점수 +0.3, 화면에 보이는 점수도 같이 올라감)
    const grade = GRADES.find(g => String(query).includes(g));
    const docs = searchPart(index.docs, query)
      .map(r => (grade && r.d.includes('직급별 성장 가이드') && String(r.s).includes(grade) ? { ...r, score: r.score + 0.3 } : r))
      .sort((a, b) => b.score - a.score)
      .filter(r => r.score >= threshold);
    const courses = hasHr(query) ? searchPart(index.courses, query).filter(r => r.score >= (courseThreshold ?? threshold)) : [];
    const nCourse = Math.min(3, courses.length, Math.max(1, topK - Math.min(docs.length, topK - 1)));
    return [...docs.slice(0, topK - nCourse), ...courses.slice(0, nCourse)];
  }
  return { buildCorpus, buildIndex, search, searchPart, gramsOf, hasHr };
})();
if (typeof window !== 'undefined') window.RagEngine = RagEngine;
if (typeof module !== 'undefined') module.exports = RagEngine;
