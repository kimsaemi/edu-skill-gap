---
name: design-md
description: Reads, parses, and applies design specifications from DESIGN.md (such as awesome-design-md templates including Apple, Linear, Stripe, Notion, Vercel styles) to generate pixel-perfect, cohesive web UI and components. Triggered whenever the user requests "먼저 DESIGN.md를 읽고", "DESIGN.md 기반으로", or when a DESIGN.md file is provided for front-end styling.
---

# DESIGN.md Workflow & Implementation Skill

이 스킬은 `awesome-design-md` 포맷의 `DESIGN.md` 문서를 바탕으로 웹 페이지, 대시보드, UI 컴포넌트를 정교하게 구현하기 위한 전문 가이드입니다.

## 핵심 역할
사용자가 **"먼저 DESIGN.md를 읽고, 이 규칙에 맞춰 구현해줘"**라고 요청하거나 스타일 가이드가 지정되었을 때:
1. `DESIGN.md`를 즉시 열어 규칙을 추출합니다.
2. 지정된 디자인 토큰(Color, Typography, Spacing, Shadow, Components, Interactions)을 CSS 변수 시스템으로 매핑합니다.
3. 명세된 규칙과 피해야 할 패턴(Dos & Don'ts)을 100% 준수하여 구현합니다.

---

## 1. 사전 분석 체크리스트

`DESIGN.md`를 읽은 후 다음 5개 영역을 정리합니다:

1. **Color Tokens**:
   - Backgrounds (기본 배경, 카드/서피스 배경, 오버레이)
   - Text Colors (High Contrast, Muted/Secondary, Disabled)
   - Brand & Accent Colors
   - Border & Divider Colors
   - Status/Functional Colors (Success, Error, Warning, Info)

2. **Typography System**:
   - Primary Font Family, Monospace Font Family (필요시 Google Fonts 링크 삽입)
   - Type Scale (H1, H2, H3, Body-lg, Body-md, Body-sm, Caption)
   - Font Weights, Line Heights, Letter Spacings

3. **Spatial & Visual Tokens**:
   - Spacing Scale (예: 4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px)
   - Border Radius (None, sm, md, lg, xl, full)
   - Shadows & Elevations (Flat, subtle border, multi-layered shadows)
   - Glassmorphism / Blur effects (if applicable)

4. **Component Patterns**:
   - Buttons (Primary, Secondary, Ghost, Outline) + Hover/Active/Focus States
   - Input fields & Form controls
   - Cards, Containers & Dividers
   - Navigation & Badges

5. **Dos & Don'ts**:
   - 반드시 준수해야 할 디자인 뉘앙스
   - 절대 사용하지 말아야 할 색상, 여백, 폰트 효과 등

---

## 2. 코드 구조화 표준 (CSS Variables 패턴)

모든 스타일링의 시작점으로 `:root`에 `DESIGN.md`의 토큰을 변수화합니다:

```css
:root {
  /* Colors from DESIGN.md */
  --color-bg-base: #...;
  --color-bg-surface: #...;
  --color-text-primary: #...;
  --color-text-secondary: #...;
  --color-accent: #...;
  --color-border: #...;

  /* Typography */
  --font-family-base: ...;
  --font-size-h1: ...;
  --font-weight-bold: ...;
  --line-height-base: ...;

  /* Spacing & Radius */
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --radius-base: ...;
  --shadow-base: ...;
}
```

---

## 3. 검증 및 자체 리뷰 (Self-Check)

구현 완료 후 다음 사항을 스스로 점검합니다:
- [ ] `DESIGN.md`에 명시된 폰트와 컬러 코드가 오차 없이 사용되었는가?
- [ ] 임의의 제네릭 AI 기본 색상(촌스러운 기본 그라데이션 등)이 섞여 들어가지 않았는가?
- [ ] 버튼과 링크 등 인터랙티브 요소에 Hover/Active 상태 스타일이 정의되어 있는가?
- [ ] 모바일 및 반응형 뷰포트에서 레이아웃이 깨지지 않는가?
- [ ] `DESIGN.md`의 Don'ts 목록에 있는 패턴을 사용하지 않았는가?
