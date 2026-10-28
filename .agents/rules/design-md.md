# DESIGN.md 기반 UI/웹 구현 규칙 (Design System Directive)

사용자가 **"먼저 DESIGN.md를 읽고, 이 규칙에 맞춰 구현해줘"**라고 요청하거나, 프로젝트 내에 `DESIGN.md` 파일이 존재할 경우 반드시 아래 절차와 원칙을 최우선으로 준수하여 웹/UI를 개발합니다.

---

## 1. 최우선 실행 절차 (Mandatory Workflow)

1. **DESIGN.md 선행 조회 및 분석**
   - 코드를 작성하거나 수정하기 전에 반드시 `DESIGN.md` 파일의 전체 내용을 읽고 분석합니다.
   - 프로젝트 내 특정 서브 디렉토리에 개별 `DESIGN.md`가 있을 경우, 작업 대상과 가장 가까운 경로의 명세를 적용합니다.

2. **디자인 토큰 및 시스템 추출**
   - `DESIGN.md`에서 아래 5대 핵심 요소를 파악하여 CSS 변수(`:root`) 또는 테마 토큰으로 먼저 정립합니다:
     1. **Color Palette**: 브랜드/배경/카드/텍스트/테두리/상태별 정확한 Hex / RGB / HSL 코드 및 투명도
     2. **Typography**: 지정된 폰트 패밀리(Google Fonts 등 @import), 제목 위계(h1~h6), 본문 크기, 행간(line-height), 자간(letter-spacing), 굵기(font-weight)
     3. **Components & States**: 버튼, 카드, 인풋, 네비게이션, 모달의 기본 형태 및 인터랙션 상태 (`:hover`, `:active`, `:focus-visible`, `:disabled`)
     4. **Spacing & Layout**: 여백 스케일(margin, padding), 컨테이너 최대 너비, 그리드/플렉스 정렬, Border Radius, Box Shadow(Elevation), 반응형 중단점
     5. **Dos & Don'ts**: `DESIGN.md`에 명시된 필수 규칙과 절대 사용하지 말아야 할 안티패턴

3. **구현 반영**
   - 제네릭한 기본 AI 스타일(어색한 기본 그라데이션, 제네릭 카드 박스, 일관성 없는 임의의 여백)을 일체 배제합니다.
   - `DESIGN.md`의 브랜드 감성(예: Apple의 미니멀/정교한 블러, Linear의 다크모드/샤프한 보더, Stripe의 세련된 타이포 등)을 100% 반영합니다.

---

## 2. 세부 준수 항목

### 🎨 색상 코드와 각 색상의 용도
- 명시된 컬러 토큰 외에 임의의 색상을 무분별하게 추가하지 않습니다.
- 배경색과 텍스트 간 명도 대비(Contrast Ratio, WCAG AA 이상)를 엄격히 검증합니다.
- CSS 변수를 활용하여 일관된 토큰 체계(`--bg-primary`, `--text-primary`, `--accent-color` 등)를 구축합니다.

### ✍️ 폰트, 글자 크기, 제목 위계
- 지정된 서체(San Francisco, Inter, Geist, Playfair 등)를 정확히 로드합니다.
- `h1`부터 `caption`까지의 계층 구조를 명확히 분리하고 일관된 폰트 크기/두께를 적용합니다.

### 🔘 인터랙션 및 상태 (Interactive States)
- 모든 클릭 가능한 요소(버튼, 링크, 인풋)는 부드러운 트랜지션(`transition: all 0.2s cubic-bezier(...)`)과 명확한 피드백을 제공합니다.
- 포커스 링(`outline`, `box-shadow`)을 적절히 구현하여 웹 접근성을 보장합니다.

### 📐 여백, 그리드, 그림자, 모바일 레이아웃
- 4px 또는 8px 기준의 그리드 시스템/스페이싱 규칙을 엄격하게 지킵니다.
- 모바일(320px~), 태블릿(768px~), 데스크톱(1024px~, 1440px~) 반응형 미디어 쿼리를 기본 지원합니다.

### 🚫 피해야 할 안티패턴
- `DESIGN.md`의 가이드라인과 충돌하는 불필요한 장식성 요소 배제
- 인라인 스타일 남발 금지 (디자인 토큰 기반 클래스 및 CSS 변수 사용)
