"""
인사 세부 업무(Task) 90개 카탈로그 조회 모듈

- 데이터: data/hr/processed/hr_task_catalog_90.json
  (scripts/build_hr_task_catalog.py 가 팀 v2.1 대시보드에서 변환·생성)
- 9개 인사 분야 × 분야별 10개 업무, 업무별 KSA·숙련도 4단계·직급별 역할 포함
- 각 업무는 자기점검 역량(COMP_HR_01 / COMP_HR_02 / COMP_LABOR_01) 1개에 연결됩니다.
- 출처: 팀 작성 실무 업무 초안이며 NCS 공식 능력단위가 아닙니다.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "hr" / "processed" / "hr_task_catalog_90.json"

CAREER_TO_GRADE_INDEX = {
    "1년 미만(신입)": 0,
    "1~3년차": 0,
    "3~5년차": 1,
    "5~10년차": 2,
    "10년 이상": 3,
}
# 직급(주임·대리·과장·차장·부장) → 업무 숙련도 4단계 인덱스
LEVEL_OF_GRADE = [0, 1, 2, 3, 3]
LEVEL_NAMES = ["보조·기본 실행", "단독 완결", "개선·최적화", "전략 설계"]
# 직급 → 추천 엔진 난이도
ENGINE_LEVEL_OF_GRADE = ["입문", "실무", "실무", "관리자·심화", "관리자·심화"]


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {"tasks": []}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def is_available() -> bool:
    return len(_load()["tasks"]) > 0


def get_hr_tasks(domain_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    tasks = _load()["tasks"]
    if domain_ids:
        tasks = [t for t in tasks if t["domain_id"] in domain_ids]
    return tasks


def get_hr_task(task_id: str) -> Optional[Dict[str, Any]]:
    return next((t for t in _load()["tasks"] if t["task_id"] == task_id), None)


def get_hr_domains() -> List[Dict[str, str]]:
    seen, domains = set(), []
    for t in _load()["tasks"]:
        if t["domain_id"] not in seen:
            seen.add(t["domain_id"])
            domains.append({"domain_id": t["domain_id"], "domain_name": t["domain_name"], "domain_full_name": t["domain_full_name"]})
    return domains


def grade_index_for_career(career_range: str) -> int:
    return CAREER_TO_GRADE_INDEX.get(career_range, 1)


def task_view_for_career(task: Dict[str, Any], career_range: str) -> Dict[str, Any]:
    """연차에 맞는 직급 역할·숙련도 설명을 함께 돌려줍니다."""
    g = grade_index_for_career(career_range)
    roles = task.get("roles_by_grade") or []
    levels = task.get("proficiency_levels") or []
    lv = LEVEL_OF_GRADE[min(g, len(LEVEL_OF_GRADE) - 1)]
    next_lv = min(lv + 1, len(levels) - 1) if levels else None
    return {
        "grade_index": g,
        "role": roles[g] if g < len(roles) else None,
        "level_index": lv,
        "level_name": LEVEL_NAMES[lv],
        "level_text": levels[lv] if lv < len(levels) else "",
        "next_level_name": LEVEL_NAMES[next_lv] if next_lv is not None and next_lv != lv else None,
        "next_level_text": levels[next_lv] if next_lv is not None and next_lv != lv else None,
        "engine_level": ENGINE_LEVEL_OF_GRADE[min(g, len(ENGINE_LEVEL_OF_GRADE) - 1)],
    }


def task_semantic_query(task: Dict[str, Any]) -> str:
    return f"{task['task_name']}. {task['easy_description']} 필요 지식: {task['knowledge']}. 필요 기술: {task['skill']}"


def task_keyword_query(task: Dict[str, Any]) -> str:
    return f"{task['task_name']} {task['knowledge']} {task['skill']}"


def task_anchor_query(task: Dict[str, Any]) -> str:
    """업무명의 핵심어 (범용 단어는 엔진에서 GENERIC_TASK_TOKENS로 제외)."""
    return task["task_name"]


# 업무 키워드 질의에서 뺄 범용 단어:
# 강좌 8,645건 중 대략 7% 이상에 나오면서 '무엇을 하는지'만 나타내고 분야를 구분하지 못하는 단어.
# 직무·평가·성과·조직·데이터·보고서·리더십·소통처럼 분야 의미가 있는 단어는 남깁니다.
GENERIC_TASK_TOKENS = frozenset("""
핵심 실무 분석 역량 관리 진행 업무 적용 전략 모듈 작성 기술 지식 구성 기반 환경 효과 시간 구조 가능 변화 정보
상황 프로세스 설계 기준 향상 역할 생성 유형 기업 체계 수립 중심 정리 운영 방안 단계 신청 개발 목표 해결 구축
스킬 자동 능력 사용 도출 요소 도구 기능 설정 개인 기획 관계 대응 개선 효율 결정 계획 사항 결과 기법 수행
필수 지원 정의 제작 시각 선택 처리 실제 경험 이론 질문 시스템 발생 원리 표준 양식 서식 템플릿 전사 이해 방법
마스터 연간 정기 분기 반기 대비 차이 최종 사전 이용 실시 연속 고도 체크 리스트 적합 검토 확정 유지 사실 전문 맞춤
공식 오프라인 온라인 디지털 프로그램 가이드 사이트 등록
the of in on it day per all sub
""".split())

# 업무 추천 노출 기준: 의미 유사도 하한, 핵심어가 없을 때 예외로 인정할 높은 유사도
TASK_MIN_SEMANTIC = 50.0
TASK_STRONG_SEMANTIC = 72.0
TASK_MIN_ANCHOR_SCORE = 1.0
# 인사 업무와 분야가 다른 강좌 (scripts/build_course_field_labels.py 의 분야 라벨)
OFF_FIELD_LABELS = frozenset({"IT_DEV", "MKT", "MED", "LEGAL_IP", "PROD", "LANG"})
OFF_FIELD_MIN_ANCHOR_SCORE = 2.0


def passes_task_gate(semantic_score: float, anchor_score: float, field: str = None) -> bool:
    """업무 추천에 보여 줄 강좌인지 판정합니다.
    1) 의미 유사도 50점 이상
    2) 분야가 다른 강좌(개발·마케팅·의료·특허·생산·어학)는 업무명 핵심어가 2점 이상 맞을 때만
    3) 업무명 핵심어가 1점 이상 맞거나, 의미 유사도가 72점 이상
    """
    if semantic_score < TASK_MIN_SEMANTIC:
        return False
    if field in OFF_FIELD_LABELS and anchor_score < OFF_FIELD_MIN_ANCHOR_SCORE:
        return False
    return anchor_score >= TASK_MIN_ANCHOR_SCORE or semantic_score >= TASK_STRONG_SEMANTIC
