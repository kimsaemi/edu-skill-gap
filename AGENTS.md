# AI Assistant Guidelines for Project

## 1. DESIGN.md 기반 UI/웹 구현 규칙 (Awesome Design MD 연동)

사용자가 **"먼저 DESIGN.md를 읽고, 이 규칙에 맞춰 구현해줘"**라고 요청하거나 워크스페이스에 `DESIGN.md`가 존재할 경우:

1. **사전 분석 필수**: 코드를 작성하기 전에 반드시 `DESIGN.md` 파일의 전체 내용을 읽고 분석합니다.
2. **토큰 추출 및 적용**:
   - 색상 시스템 (Brand, Background, Surface, Text, Border, Accent, Semantic 상태 색상)
   - 타이포그래피 (폰트 패밀리, 폰트 크기 스케일, 제목 위계 H1~H6, 자간 및 행간)
   - 컴포넌트 & 인터랙션 상태 (버튼, 카드, 인풋, 모달 및 Hover/Focus/Active/Disabled 상태)
   - 공간 시스템 (Padding, Margin, 그리드, Border Radius, 그림자 및 모바일 반응형 규칙)
   - 준수 사항 및 피해야 할 안티패턴(Dos & Don'ts)
3. **일관성 유지**: 제네릭한 AI 기본 스타일을 배제하고 `DESIGN.md`에 명시된 고유의 디자인 시스템을 정확하게 구현합니다.

---

## 2. 프로젝트 개발 가이드 (Data Science & Web)
- 데이터 시각화 및 대시보드 개발 시 모던 웹 표준과 높은 심미성을 유지합니다.
- marimo 노트북 수정 시에는 기존 marimo reactive 규칙을 준수합니다.

---

## 3. Lucian UX/UI Prompt 기반 컴포넌트 & 인터랙션 구현 규칙
- UI 컴포넌트, 인터랙션, 차트, 애니메이션, 알림/모달/폼 제작 시 [Lucian UX/UI Prompt](https://lucianlabs.dev/uxui-prompt/) (200개 템플릿)를 우선적으로 참고하여 구현합니다.
- 사용자가 특정 UI를 요청할 때 `.agents/skills/lucian-uxui/scripts/lucian-uxui.py`를 통해 갤러리 검색(`search`) 및 코드(`get`)를 조회하여 정교한 인터랙션과 `--ux-*` 토큰을 프로젝트 스타일에 접목합니다.
