# 인사 교육과정 추천 RAG 챗봇 스모크 테스트 (10개 질의)

- 실행 일시: 2026-11-16
- 테스트 환경: Python 3.12, Ko-SRoBERTa + BM25 1단계 하이브리드, Dongjin-kr/ko-reranker 2단계 리랭커
- API 키 상태: 환경변수 미설정 (검색 결과 표 전용 모드 동작 실측)
- 안내: 적합성 판정 칸(평가자 기입란)은 팀원 블라인드/직접 평가를 위해 비워 두었습니다. (판단을 지어내지 않음)

---

## Q1 (90개 업무 중 1): "급여 계산 및 4대보험 공제 실무"

- **검색 모드**: `TASK_MAPPING (매월 임직원 급여·상여 계산, 4대보험 공제 및 원천징수 급여 대장 마감, 유사도 0.74)`
- **연결된 업무**: 매월 임직원 급여·상여 계산, 4대보험 공제 및 원천징수 급여 대장 마감 / 보상·급여·복리후생 / 지식: 소득세법상 근로소득 간이세액표, 4대 사회보험 요율 및 정산 원리, 통상임금 수당 산정식, 기술: 급여 ERP 모듈 계산, 급여 이체 파일(CMS) 생성, 급여명세서 전자 교부, 태도: 임직원의 생계가 걸린 급여를 다루는 만큼 단 1원의 오차나 마감 지연도 용납하지 않는 철저함
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | 아파트빌딩인사회계XP-ERP실무 | 왕십리-한국아파트경리전문학원 | 중급/실무 | 76.1점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000518327&tracseTme=8&crseTracseSe=C0061&trainstCstmrId=500020062904) | [ ] |
| [2] | 급여&4대보험관리실무(급여계산+4대보험관리+원천징수+연말정산) | 하이컴퓨터그래픽전산회계학원 | 중급/실무 | 74.5점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20240000489459&tracseTme=2&crseTracseSe=C0061&trainstCstmrId=500020019063) | [ ] |
| [3] | 아파트빌딩인사회계XP-ERP훈련 | 왕십리-한국아파트경리전문학원 | 중급/실무 | 74.5점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000516330&tracseTme=6&crseTracseSe=C0061&trainstCstmrId=500020062904) | [ ] |
| [4] | 인사관리(급여관리,원천징수,4대보험,연말정산) | 안산여성인력개발센터 | 중급/실무 | 74.0점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000532286&tracseTme=7&crseTracseSe=C0061&trainstCstmrId=500020013526) | [ ] |
| [5] | 인사급여 실무(4대보험+급여관리+원천징수+연말정산) | 하이미디어IT인재개발학원 | 중급/실무 | 73.9점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20230000431377&tracseTme=2&crseTracseSe=C0061&trainstCstmrId=500020013370) | [ ] |

---

## Q2 (90개 업무 중 2): "신규 입사자 온보딩 프로그램 커리큘럼 기획"

- **검색 모드**: `TASK_MAPPING (전사 신규 입사자 온보딩 프로그램(Bootcamp) 커리큘럼 기획, 유사도 0.85)`
- **연결된 업무**: 전사 신규 입사자 온보딩 프로그램(Bootcamp) 커리큘럼 기획 / 온보딩·직원경험 / 지식: 성인학습 이론, 온보딩 효과성 지표, 회사 히스토리 및 핵심가치 체계, 기술: 온보딩 커리큘럼 설계, 강의 기획, 입문 교육 교재 편찬, 태도: 신규 구성원을 따뜻하게 환영하고 소속감을 고취하려는 환대(Hospitality) 정신
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | 오늘 온 신입사원, 온보딩 전략 ON 하기 | 휴넷 | 초급 | 59.5점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00265996) | [ ] |
| [2] | 신규 회원 & 모든 회원 할인 EVENT | 한국직업방송(KFO) | 실무 | 58.6점 | [바로가기](https://kfo.ai/event_new/event_special_dc_2021.php?PHPSESSID=2e7067938700564075ab5adb8c4ad3f4) | [ ] |
| [3] | [온앤오프] HR·GA 온보딩 패키지 | 한국생산성본부(KPC) | 실무 | 57.4점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=46979&cono=157552) | [ ] |
| [4] | [HRethink] 일하고 싶은 회사의 비밀, Employee eXperience | 휴넷 | 초급 | 57.4점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00369600) | [ ] |
| [5] | HR, AI가 트렌드다 : 채용부터 퇴사까지 | GSEEK | 초급 | 56.7점 | [바로가기](https://www.gseek.kr/user/course/online/view?s_sbjct_sn=57049&s_sbjct_cycl_sn=1) | [ ] |

---

## Q3 (90개 업무 중 3): "표준 직무기술서(JD) 및 직무명세서 양식 체계화"

- **검색 모드**: `TASK_MAPPING (표준 직무기술서(JD) 및 직무명세서 양식 체계화, 유사도 0.93)`
- **연결된 업무**: 표준 직무기술서(JD) 및 직무명세서 양식 체계화 / 조직설계·직무분석 / 지식: 직무기술서(Job Description) 표준 구조, 자격요건 명세화 원리, 법적 리스크 배제 기준, 기술: JD 서식 템플릿 개발, 직무 분석 인터뷰 질문지 설계, 역량 정의서 작성, 태도: 현업의 언어를 인사 전문가의 표준 언어로 번역하고 구조화하는 명확성
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | [여의도] 급여담당자를 위한 급여관리 실무 | 한국능률협회(KMA) | 실무 | 56.7점 | [바로가기](https://www.kma.or.kr/usrs/eduRegMgnt/eduRegInfoDetailForm.do?p_edutype_cd=001&p_crscd=111447&p_crsseq_id=126378&p_ctgry_id=661&p_hmpgcd=30&mkey=37148) | [ ] |
| [2] | [온앤오프] 평가 및 보상제도 운영실무 | 한국생산성본부(KPC) | 실무 | 50.1점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=46990&cono=149679) | [ ] |

---

## Q4 (90개 업무 중 4): "핵심 직무역량 모델링 및 역량 사전 구축"

- **검색 모드**: `TASK_MAPPING (핵심 인재(Hi-Po) 선발 기준 및 승계 계획(Succession Planning) 수립, 유사도 0.72)`
- **연결된 업무**: 핵심 인재(Hi-Po) 선발 기준 및 승계 계획(Succession Planning) 수립 / 인재육성·사내교육 / 지식: 핵심 인재(Hi-Po: High Potential) 정의, 9-Block 매트릭스, 승계 계획(Succession Planning), 기술: 핵심 인재 다면 평가 기준표 설계, 승계 후보군 벤치 차트(Bench Chart) 작성, CDP 매핑, 태도: 외부 영입에 의존하지 않고 사내에서 미래 리더를 끈기 있게 키워내는 미래지향적 안목
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | [PO스쿨] IT 서비스의 성공을 만드는 프로덕트 오너 | 휴넷 | 중급 | 79.4점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00350959) | [ ] |
| [2] | 기업성공을 위한 조직관리와 인적자원관리 | (1st)인비원 평생교육원 | 실무 | 68.5점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=ACG20263001435047&tracseTme=67&crseTracseSe=C0031&trainstCstmrId=500044312625) | [ ] |
| [3] | 우수인재 선발을 위한 면접관 역량개발 | 한국생산성본부(KPC) | 실무 | 67.9점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=47011&cono=157556) | [ ] |
| [4] | [SSS급 인재] 팔리는 기획에는 이것이 있다, 비즈니스 오너십 | 휴넷 | 초급 | 61.2점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00381735) | [ ] |
| [5] | [여의도] AI를 활용한 스마트 리더십 전략 | 한국능률협회(KMA) | 실무 | 59.1점 | [바로가기](https://www.kma.or.kr/usrs/eduRegMgnt/eduRegInfoDetailForm.do?p_edutype_cd=001&p_crscd=111293&p_crsseq_id=127175&p_ctgry_id=570&p_hmpgcd=30&mkey=36338) | [ ] |

---

## Q5 (90개 업무 중 5): "노사협의회 정기 회의 진행 및 합의사항 도출"

- **검색 모드**: `TASK_MAPPING (노사협의회(근로자참여법상 분기 회의) 안건 취합, 회의 진행 및 합의사항 공고, 유사도 0.85)`
- **연결된 업무**: 노사협의회(근로자참여법상 분기 회의) 안건 취합, 회의 진행 및 합의사항 공고 / 노사관계·노무 / 지식: 근로자참여및협력증진에관한법률(근참법), 노사협의회 규정, 노사 안건 협의 프로세스, 기술: 노사협의회 회의록 작성, 안건 심의 보고서 작성, 노사 합의문 사내 공고, 태도: 노사의 다양한 목소리를 경청하고 합리적인 절충점을 찾아내는 뛰어난 중재력
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | [여의도] 안정적인 노사관계를 위한 노동법 및 노사협의회 운영 실무 | 한국능률협회(KMA) | 실무 | 69.9점 | [바로가기](https://www.kma.or.kr/usrs/eduRegMgnt/eduRegInfoDetailForm.do?p_edutype_cd=001&p_crscd=111450&p_crsseq_id=125998&p_ctgry_id=661&p_hmpgcd=30&mkey=37148) | [ ] |
| [2] | EB2FFU 채용에서 퇴직까지 인사노무관리 핵심실무 | 멀티캠퍼스 원격평생교육원 | 실무 | 61.6점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl2.do?tracseId=ABA20263001175322&tracseTme=9&crseTracseSe=C0041&trainstCstmrId=500020037820) | [ ] |
| [3] | 노동법 A to Z  근로계약부터 인사관리까지 핵심 총정리 | 한승원격평생교육원 | 실무 | 59.2점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl2.do?tracseId=ABA20263001500869&tracseTme=2&crseTracseSe=C0041&trainstCstmrId=500045928380) | [ ] |
| [4] | [온앤오프] [1Day] 주주총회 기획과 운영 실무 | 한국생산성본부(KPC) | 실무 | 57.1점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=47275&cono=151793) | [ ] |
| [5] | [온앤오프] 근로감독 대응실무 체크포인트 | 한국생산성본부(KPC) | 실무 | 57.0점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=47008&cono=156438) | [ ] |

---

## Q6 (업무 목록 외 1): "4대보험 신고를 처음 맡았어요"

- **검색 모드**: `ADHOC_SEARCH (최고 유사도 0.38 < 0.55)`
- **연결된 업무**: 없음
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | 인사급여지급(급여계산/4대보험/연말정산),부가가치세신고실무 | 익산컴퓨터전문학원 | 중급/실무 | 25.0점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000531787&tracseTme=1&crseTracseSe=C0061&trainstCstmrId=500033315122) | [ ] |

---

## Q7 (업무 목록 외 2): "MZ세대 직원들과 소통이 어려운데 피드백 스킬 교육 있나요"

- **검색 모드**: `TASK_MAPPING (입사 1개월/3개월 차 체크인 미팅(Check-in 1:1) 및 정착 고충 상담, 유사도 0.70)`
- **연결된 업무**: 입사 1개월/3개월 차 체크인 미팅(Check-in 1:1) 및 정착 고충 상담 / 온보딩·직원경험 / 지식: 적극적 경청(Active Listening) 기법, 코칭 대화 모델(GROW), 심리 상담 기초, 기술: 1:1 심층 인터뷰, 고충 청취 및 피드백 전달, 부서장 면담 코칭, 태도: 선입견 없이 구성원의 입장에서 공감하고 해결책을 찾아주는 진정성
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | [비대면] 조직 갈등을 기회로! 코칭으로 배우는 해결의 기술 | 한국능률협회(KMA) | 실무 | 59.6점 | [바로가기](https://www.kma.or.kr/usrs/eduRegMgnt/eduRegInfoDetailForm.do?p_edutype_cd=001&p_crscd=111368&p_crsseq_id=125531&p_ctgry_id=560&p_hmpgcd=30&mkey=36328) | [ ] |
| [2] | 고충처리 실무(성희롱 · 괴롭힘) (feat. 조사보고서 작성까지) | 한국생산성본부(KPC) | 실무 | 59.2점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=47024&cono=149792) | [ ] |
| [3] | [여의도] 조직 갈등을 기회로: 코칭으로 푸는 해결의 기술 | 한국능률협회(KMA) | 실무 | 57.5점 | [바로가기](https://www.kma.or.kr/usrs/eduRegMgnt/eduRegInfoDetailForm.do?p_edutype_cd=001&p_crscd=112306&p_crsseq_id=128485&p_ctgry_id=560&p_hmpgcd=30&mkey=36328) | [ ] |
| [4] | 코칭 포유_끌리는 리더의 Coaching Secret | 휴넷 | 초급 | 57.3점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00342158) | [ ] |
| [5] | 리더를 부탁해, 코칭 솔루션 | 휴넷 | 중급 | 56.7점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00323310) | [ ] |

---

## Q8 (업무 목록 외 3): "팀원 연차 촉진제도와 수당 정산 어떻게 관리하나요"

- **검색 모드**: `TASK_MAPPING (연차유급휴가 사용 촉진 및 연차미사용수당 정산 운영, 유사도 0.78)`
- **연결된 업무**: 연차유급휴가 사용 촉진 및 연차미사용수당 정산 운영 / 보상·급여·복리후생 / 지식: 근로기준법상 연차휴가 발생 및 사용 촉진 요건, 통상임금 기준 미사용수당 계산법, 기술: 연차 촉진 전자 서명 시스템 운영, 잔여 연차 일수 정산, 수당 지급 대장 작성, 태도: 법적 절차를 빈틈없이 준수하여 회사의 수당 지급 의무 면제와 직원의 휴식권을 보장하는 치밀함
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | 공동주택전산인사 | 노원-한국아파트경리전문학원 | 중급/실무 | 68.7점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000506792&tracseTme=10&crseTracseSe=C0061&trainstCstmrId=500020027722) | [ ] |
| [2] | [인재키움] 근로기준법실무 | 한국생산성본부 | 실무 | 68.0점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl2.do?tracseId=ABA20263001503061&tracseTme=1&crseTracseSe=C0041&trainstCstmrId=500020024372) | [ ] |
| [3] | 아파트xperp인사 | 노원-한국아파트경리전문학원 | 중급/실무 | 65.7점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000506781&tracseTme=10&crseTracseSe=C0061&trainstCstmrId=500020027722) | [ ] |
| [4] | 노동법 쟁점 88선 해설 | 한국생산성본부(KPC) | 실무 | 64.1점 | [바로가기](https://www.kpc.or.kr/PTWED003_dtil_view.do?ecno=47016&cono=149794) | [ ] |
| [5] | 아파트빌딩인사회계XP-ERP실무 | 왕십리-한국아파트경리전문학원 | 중급/실무 | 62.7점 | [바로가기](https://www.work24.go.kr/hr/a/a/3100/selectTracseDetl.do?tracseId=AIG20250000518327&tracseTme=8&crseTracseSe=C0061&trainstCstmrId=500020062904) | [ ] |

---

## Q9 (인사 무관 1): "파이썬으로 주식 자동매매 프로그램 만드는 법"

- **검색 모드**: `ADHOC_SEARCH (최고 유사도 0.34 < 0.55)`
- **연결된 업무**: 없음
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | 데이터 분석부터 업무자동화까지, 파이썬 뿌시기 | GSEEK | 초급 | 26.7점 | [바로가기](https://www.gseek.kr/user/course/online/view?s_sbjct_sn=51914&s_sbjct_cycl_sn=1) | [ ] |

---

## Q10 (인사 무관 2): "오늘 점심 메뉴 추천해줘"

- **검색 모드**: `ADHOC_SEARCH (최고 유사도 0.24 < 0.55)`
- **연결된 업무**: 없음
- **AI 모델 상태**: `NO_API_KEY`

### 챗봇 응답 (검색 결과 표 전용 모드)
> ℹ️ `ANTHROPIC_API_KEY` 환경변수가 설정되지 않아 AI 요약 설명 없이 2단계 하이브리드 검색 근거 과정 표를 표시합니다.

### 도출된 근거 과정 (Top Candidates)

| 번호 | 과정명 | 교육기관 | 난이도 | 점수 | 상세 링크 | 팀원 판정 (적합 / 부분 / 부적합) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| [1] | [북러닝] 플랫폼 경제와 공짜 점심(도서 제공) | 휴넷 | 초급 | 17.7점 | [바로가기](https://hbs.hunet.co.kr/Education/Detail?gid=Y00185074) | [ ] |

---
