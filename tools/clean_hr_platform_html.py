"""
팀 대시보드(hr_career_platform_v2_criteria_update.html)의 내장 데이터와 표기를 정리해 새 파일로 저장합니다.
원본 파일은 수정하지 않습니다.

정리 내용
1. 강좌 데이터
   - '인사와 무관(기타)' 분류(cat=OTHER) 강좌 제외
   - 인사·총무 직무와 무관한 제목(공인중개사·요양·바리스타·코인 등) 제외
   - 엑셀 머리글 행('과정명') 제외, 같은 플랫폼의 같은 제목 중복 제거
   - 제목의 HTML 엔티티(&#39; 등) 복원
   - 플랫폼 이름 통일 (한국생산성본부 → 한국생산성본부(KPC), STEP → 한국기술교육대학교(STEP))
   - 기관명이 비어 있으면 플랫폼 이름으로 채움
2. 합성 리뷰 표기
   - SHOW_SYNTHETIC_REVIEW 스위치 추가 (기본값 false: 리뷰 기반 추천 영역을 숨김)
   - 켜더라도 '⭐ 리뷰 검증' 대신 '🧪 합성 리뷰 시뮬레이션' 배지와 안내를 표시
3. 키워드 매칭
   - '노무 법률' 역량의 매칭어에서 '인사'(거의 모든 HR 강좌에 걸림)와 '법'('방법'에 걸림) 제거
   - HR 분류 강좌를 모두 '노무'와 연결하던 예외 규칙 제거

실행: python tools/clean_hr_platform_html.py <원본.html> <출력.html>
"""

import html as htmllib
import json
import re
import sys
from collections import Counter
from pathlib import Path

OFF_TOPIC = re.compile(
    r"공인중개사|부동산학개론|부동산공법|부동산공시법|부동산세법|요양보호사|간호|사회복지사|사회복지조사|사회적경제|사회적기업"
    r"|애견|바리스타|미용사|네일|조리기능|제과|제빵|지게차|용접|드론|물류관리사|경비지도사|경호학|가상자산|코인|자동매매|생산운영|생산관리"
)
HEADER_TITLES = {"과정명", "강좌명", "교육과정명", "title"}
PLATFORM_ALIASES = {"한국생산성본부": "한국생산성본부(KPC)", "STEP": "한국기술교육대학교(STEP)"}

# (설명, 원문, 바꿀 문장) — 원문이 정확히 1번 나와야 적용
JS_PATCHES = [
    ("합성 리뷰 스위치",
     "CRITERIA = DATA.criteria || {};",
     "CRITERIA = SHOW_SYNTHETIC_REVIEW ? (DATA.criteria || {}) : {};"),
    ("리뷰 검증 배지",
     '<span class="tag direct">⭐ 리뷰 검증</span>',
     '<span class="tag common">🧪 합성 리뷰 시뮬레이션</span>'),
    ("리뷰 비율 라벨",
     "<p><b>리뷰 기반 4점 이상 비율</b>",
     "<p><b>합성 리뷰 기준 4점 이상 비율 (실제 후기 아님)</b>"),
    ("리뷰 더보기 제목",
     "🔎 이 직급의 다른 리뷰 기반 추천",
     "🧪 이 직급의 다른 합성 리뷰 시뮬레이션 추천"),
    ("역량별 추천 안내문",
     "일반 강좌와 리뷰 검증 강좌를 같은 기준으로 비교했어요.",
     "${SHOW_SYNTHETIC_REVIEW ? '일반 강좌와 합성 리뷰 시뮬레이션 강좌를 같은 기준으로 비교했어요(리뷰는 실제 후기가 아니에요).' : ''}"),
    ("노무 매칭어",
     "terms: ['노무', '인사', '법', '근로기준법', '취업규칙', '윤리', '준법']",
     "terms: ['노무', '노동법', '노사', '근로기준법', '취업규칙', '법률', '법령', '윤리', '준법']"),
    ("HR→노무 예외 규칙",
     "      if (c.cat === 'HR' && skillName.includes('노무')) return true;\n",
     ""),
    ("하단 안내문",
     "중복 회차를 묶어 ${C.length}개를 보여 줍니다.",
     "중복 회차를 묶고 인사·총무 직무와 무관한 ${DATA.excludedCount}개를 빼서 ${C.length}개를 보여 줍니다. 수강 후기·평점은 검증된 실제 데이터가 아니어서 기본 화면에 표시하지 않아요."),
]
SWITCH_DECL = (
    "// 합성 리뷰(실제 수강 후기 아님) 기반 추천 영역 표시 여부. 실제 리뷰를 확보하기 전까지 false 유지\n"
    "const SHOW_SYNTHETIC_REVIEW = false;\n"
)


def norm_title(t: str) -> str:
    return re.sub(r"[\s\[\]()（）\-_·.,!?~:/『』「」]+", "", t.lower())


def clean_courses(courses: list) -> tuple:
    kept, reasons, seen = [], Counter(), set()
    for c in courses:
        c = dict(c)
        c["t"] = htmllib.unescape(c.get("t") or "").strip()
        c["plat"] = PLATFORM_ALIASES.get(c.get("plat"), c.get("plat"))
        if not (c.get("inst") or "").strip():
            c["inst"] = c["plat"]
        if c["t"] in HEADER_TITLES:
            reasons["엑셀 머리글 행"] += 1
            continue
        if c.get("cat") == "OTHER" and not c.get("doms"):
            reasons["인사와 무관(기타) 분류"] += 1
            continue
        if OFF_TOPIC.search(c["t"]):
            reasons["직무와 무관한 제목"] += 1
            continue
        key = (norm_title(c["t"]), c["plat"])
        if key in seen:
            reasons["같은 플랫폼 중복"] += 1
            continue
        seen.add(key)
        kept.append(c)
    return kept, reasons


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    if src.resolve() == dst.resolve():
        print("[FAIL] 원본과 다른 출력 경로를 지정하세요.")
        return 1
    page = src.read_text(encoding="utf-8")

    m = re.search(r"const DATA\s*=\s*", page)
    data, end = json.JSONDecoder().raw_decode(page[m.end():])
    before = len(data["courses"])
    data["courses"], reasons = clean_courses(data["courses"])
    data["excludedCount"] = sum(v for k, v in reasons.items() if k != "같은 플랫폼 중복")
    data["platforms"] = sorted({c["plat"] for c in data["courses"]})
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = page[:m.end()] + payload + page[m.end() + end:]

    for name, old, new in JS_PATCHES:
        n = page.count(old)
        if n != 1:
            print(f"[FAIL] '{name}' 원문이 {n}번 발견되어 적용하지 않았습니다.")
            return 1
        page = page.replace(old, new)
    page = page.replace("const G = DATA.grades", SWITCH_DECL + "const G = DATA.grades", 1)

    dst.write_text(page, encoding="utf-8")
    print(f"강좌 {before} → {len(data['courses'])}개")
    for k, v in reasons.most_common():
        print(f"  - {k}: {v}")
    print(f"플랫폼 {len(data['platforms'])}개: {', '.join(data['platforms'])}")
    print(f"저장: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
