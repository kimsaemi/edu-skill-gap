"""
팀 고객용 대시보드(v2.1 HTML)에서 화면 콘텐츠만 뽑아 저장
파일명: scripts/extract_career_platform_master.py

가져오는 것 (팀이 작성한 콘텐츠)
  - grades  : 직급 5개 (연차, 미션, 자격증, 선배 조언, 승진 과제, 결과물 등)
  - domains : 분야 12개와 업무(과업) 102개 (숙련도 4단계 설명, 직급별 역할, 지식·기술·태도)
  - cats / catWhy / related : 공통 역량 분류
가져오지 않는 것
  - courses (2023~2024년 기준 과정 목록), 업무별 rec·rs (예전 추천 결과)
    → 고객용 Streamlit 앱은 최신 카탈로그와 추천 엔진으로 다시 계산합니다.

사용법:
  python scripts/extract_career_platform_master.py "C:/Users/.../hr_career_platform_v2_criteria_update.html"
출력:
  data/hr/processed/hr_career_platform_master.json
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "hr" / "processed" / "hr_career_platform_master.json"
DROP_TASK_KEYS = {"rec", "rs"}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    m = re.search(r"const DATA\s*=\s*", html)
    if not m:
        print("[FAIL] DATA 객체를 찾을 수 없습니다.")
        return 1
    data, _ = json.JSONDecoder().raw_decode(html[m.end():])

    domains = []
    for d in data["domains"]:
        d2 = {k: v for k, v in d.items() if k != "tasks"}
        d2["tasks"] = [{k: v for k, v in t.items() if k not in DROP_TASK_KEYS} for t in d.get("tasks", [])]
        domains.append(d2)
    master = {
        "source": f"팀 고객용 대시보드 v2.1 ({Path(sys.argv[1]).name})",
        "grades": data["grades"],
        "domains": domains,
        "cats": data.get("cats", {}),
        "catWhy": data.get("catWhy", {}),
        "related": data.get("related", {}),
    }
    OUT.write_text(json.dumps(master, ensure_ascii=False, indent=1), encoding="utf-8")
    n_tasks = sum(len(d["tasks"]) for d in domains)
    print(f"저장: {OUT.relative_to(ROOT)} | 직급 {len(master['grades'])}개, 분야 {len(domains)}개, 업무 {n_tasks}개")
    print("직급 항목:", list(master["grades"][0].keys()))
    print("분야 항목:", [k for k in domains[0].keys() if k != "tasks"])
    print("업무 항목:", list(domains[0]["tasks"][0].keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
