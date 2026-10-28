"""
scripts/generate_schema_dictionary.py
최소 보완 데이터 스키마 정의 및 데이터 사전 생성 스크립트
"""

import json
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def generate_schema_docs():
    out_dir = WORKSPACE_ROOT / "data" / "skills_taxonomy"
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_dict = {
        "schemas": {
            "competency_master": {
                "table_name": "competency_master",
                "description": "8대 KSA 직무역량 마스터 및 거버넌스 메타데이터",
                "primary_key": ["competency_id"],
                "fields": {
                    "competency_id": {"type": "VARCHAR(20)", "nullable": False, "description": "역량 고유 식별자 (예: COMP_HR_01)"},
                    "competency_name": {"type": "VARCHAR(50)", "nullable": False, "description": "역량 공식 명칭"},
                    "job_family": {"type": "VARCHAR(30)", "nullable": False, "description": "소속 직무군 (인사, 총무, 경영지원)"},
                    "ksa_type": {"type": "VARCHAR(15)", "nullable": False, "enum": ["Knowledge", "Skill", "Attitude"], "description": "K/S/A 구분"},
                    "definition": {"type": "TEXT", "nullable": False, "description": "역량 공식 행동 정의문"},
                    "knowledge": {"type": "TEXT", "nullable": True, "description": "핵심 관련 지식 요소"},
                    "skill": {"type": "TEXT", "nullable": True, "description": "핵심 관련 기술/기법 요소"},
                    "attitude": {"type": "TEXT", "nullable": True, "description": "핵심 관련 태도/가치관 요소"},
                    "related_tasks": {"type": "JSON", "nullable": False, "description": "연계된 표준 수행 업무 태스크 ID 목록"},
                    "source": {"type": "VARCHAR(50)", "nullable": False, "default": "NCS_2016v3_AND_KSA_FRAMEWORK", "description": "기반 표준 출처"},
                    "version": {"type": "VARCHAR(10)", "nullable": False, "default": "v1.1", "description": "마스터 버전"},
                    "review_status": {"type": "VARCHAR(20)", "nullable": False, "enum": ["CONFIRMED_MASTER", "DRAFT", "ARCHIVED"], "description": "검토 상태"}
                }
            },
            "course_core": {
                "table_name": "course_core",
                "description": "교육과정 정제 코어 메타데이터",
                "primary_key": ["course_uid"],
                "fields": {
                    "course_uid": {"type": "VARCHAR(50)", "nullable": False, "description": "교육과정 전역 고유 식별자"},
                    "title": {"type": "VARCHAR(255)", "nullable": False, "description": "교육과정 원본 제목"},
                    "provider": {"type": "VARCHAR(50)", "nullable": False, "description": "교육기관/플랫폼 명칭"},
                    "course_intro": {"type": "TEXT", "nullable": True, "description": "과정 소개 요약문"},
                    "learning_goals": {"type": "TEXT", "nullable": True, "description": "학습 목표 및 기대 효과"},
                    "curriculum": {"type": "TEXT", "nullable": True, "description": "커리큘럼 상세 목차"},
                    "price": {"type": "INTEGER", "nullable": True, "description": "수강료 정수형 금액 (원) - 미확인 시 NULL"},
                    "duration_hours": {"type": "FLOAT", "nullable": True, "description": "총 교육시간 (시간) - 미확인 시 NULL"},
                    "education_type": {"type": "VARCHAR(30)", "nullable": False, "enum": ["온라인", "오프라인", "혼합", "미확인"], "description": "교육 진행 형태"},
                    "url": {"type": "VARCHAR(500)", "nullable": False, "description": "교육 상세 및 수강신청 링크"}
                }
            },
            "course_source_metadata": {
                "table_name": "course_source_metadata",
                "description": "교육과정 원천 수집 및 출처 이력 메타데이터 (동일 날짜 일괄 채우기 금지)",
                "primary_key": ["course_uid"],
                "foreign_keys": [{"column": "course_uid", "references": "course_core(course_uid)"}],
                "fields": {
                    "course_uid": {"type": "VARCHAR(50)", "nullable": False, "description": "교육과정 UID"},
                    "source_provider": {"type": "VARCHAR(50)", "nullable": False, "description": "수집 원천 식별자 (GSEEK, HUNET, KMA, KPC 등)"},
                    "source_url": {"type": "VARCHAR(500)", "nullable": False, "description": "수집 원천 웹 URL"},
                    "collected_at": {"type": "TIMESTAMP", "nullable": False, "description": "최초 메타데이터 수집 일시 (ISO-8601)"},
                    "source_updated_at": {"type": "TIMESTAMP", "nullable": True, "description": "원문 웹페이지 수정 일시 (크롤러 미수집 시 NULL 유지)"},
                    "last_verified_at": {"type": "TIMESTAMP", "nullable": True, "description": "사람/운영자 최종 사실 확인 일자 (확인 이력 없을 시 NULL 유지)"}
                }
            },
            "course_competency_mapping": {
                "table_name": "course_competency_mapping",
                "description": "교육과정-역량 연결 관계 및 텍스트 증거 (별도 매핑 테이블)",
                "primary_key": ["course_uid", "competency_id"],
                "foreign_keys": [
                    {"column": "course_uid", "references": "course_core(course_uid)"},
                    {"column": "competency_id", "references": "competency_master(competency_id)"}
                ],
                "fields": {
                    "mapping_id": {"type": "VARCHAR(60)", "nullable": False, "description": "매핑 고유 키 (course_uid + '_' + competency_id)"},
                    "course_uid": {"type": "VARCHAR(50)", "nullable": False, "description": "교육과정 UID"},
                    "competency_id": {"type": "VARCHAR(20)", "nullable": False, "description": "KSA 역량 ID"},
                    "relation_type": {"type": "VARCHAR(20)", "nullable": False, "enum": ["DIRECT", "PARTIAL", "INSUFFICIENT", "REJECTED"], "description": "연계 정합성 수준"},
                    "evidence_text": {"type": "TEXT", "nullable": True, "description": "원문에 실재하는 커리큘럼/본문 발췌 증거 (임의 생성 금지)"},
                    "evidence_location": {"type": "VARCHAR(30)", "nullable": False, "enum": ["CURRICULUM", "TITLE", "INTRO", "GOALS", "UNAVAILABLE"], "description": "증거 발견 위치"},
                    "mapping_method": {"type": "VARCHAR(30)", "nullable": False, "enum": ["HYBRID_EMBEDDING_BM25", "RULE_BASED", "MANUAL_CURATION"], "description": "매핑 생성 알고리즘"},
                    "mapping_confidence": {"type": "VARCHAR(10)", "nullable": False, "enum": ["HIGH", "MEDIUM", "LOW"], "description": "추정 신뢰도"},
                    "review_status": {"type": "VARCHAR(25)", "nullable": False, "enum": ["PENDING_HUMAN_REVIEW", "VERIFIED_BY_HUMAN", "REJECTED_BY_HUMAN"], "description": "검토 상태 (자동생성은 PENDING_HUMAN_REVIEW)"}
                }
            },
            "human_review_log": {
                "table_name": "human_review_log",
                "description": "사람 전문가 검토 거버넌스 로그",
                "primary_key": ["review_id"],
                "foreign_keys": [{"column": "mapping_id", "references": "course_competency_mapping(mapping_id)"}],
                "fields": {
                    "review_id": {"type": "VARCHAR(60)", "nullable": False, "description": "검토 일련번호"},
                    "mapping_id": {"type": "VARCHAR(60)", "nullable": False, "description": "대상 매핑 ID"},
                    "reviewer": {"type": "VARCHAR(50)", "nullable": True, "description": "사람 검토자 실명 또는 ID (미검토 시 NULL)"},
                    "reviewed_at": {"type": "TIMESTAMP", "nullable": True, "description": "검토 일시 (미검토 시 NULL)"},
                    "human_verdict": {"type": "VARCHAR(20)", "nullable": True, "enum": ["DIRECT", "PARTIAL", "INSUFFICIENT", "REJECTED", None], "description": "사람 최종 판정"},
                    "review_note": {"type": "TEXT", "nullable": True, "description": "사람 검토 의견 및 판정 근거 (미검토 시 NULL)"}
                }
            },
            "assessment_definition": {
                "table_name": "assessment_definition",
                "description": "역량 자기점검 진단 문항 및 평가 규격 정의",
                "primary_key": ["question_id"],
                "foreign_keys": [{"column": "competency_id", "references": "competency_master(competency_id)"}],
                "fields": {
                    "question_id": {"type": "VARCHAR(20)", "nullable": False, "description": "문항 고유 ID (예: Q_HR_01)"},
                    "job_family": {"type": "VARCHAR(30)", "nullable": False, "description": "소속 직무"},
                    "competency_id": {"type": "VARCHAR(20)", "nullable": False, "description": "측정 대상 KSA 역량 ID"},
                    "question_text": {"type": "TEXT", "nullable": False, "description": "행동 기반 자기점검 질문문"},
                    "behavior_example": {"type": "TEXT", "nullable": False, "description": "구체적 행동 지표 예시"},
                    "question_version": {"type": "VARCHAR(10)", "nullable": False, "default": "v1.0", "description": "문항 개정 버전"},
                    "scale_scoring_version": {"type": "VARCHAR(10)", "nullable": False, "default": "v1.0", "description": "1~5점 척도 및 정보부족(2문항 미만 제외) 계산 규격 버전"},
                    "review_status": {"type": "VARCHAR(30)", "nullable": False, "default": "DRAFT_SELF_ASSESSMENT", "description": "문항 검수 상태"}
                }
            }
        }
    }

    # Write schema JSON
    json_path = out_dir / "schema_definitions.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(schema_dict, f, ensure_ascii=False, indent=2)

    # Write Markdown Data Dictionary
    md_path = out_dir / "minimal_schema_data_dictionary.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 최소 보완 데이터 스키마 및 데이터 사전 (Data Dictionary)\n\n")
        f.write("본 규격은 `kimsaemi/edu-skill-gap` 대시보드의 역량 진단·교육 추천에 필요한 핵심 필드를 표준화하고,\n")
        f.write("출처 관리, 관계 분리, 사람 검토 거버넌스를 완결성 있게 보장하기 위한 최소 데이터 스키마입니다.\n\n")
        f.write("## 1. 설계 원칙\n")
        f.write("1. **기존 필드 의미 재사용**: 기존 데이터에 존재하는 필드는 불필요하게 이름을 변경하거나 중복 컬럼을 만들지 않고 온전히 계승합니다.\n")
        f.write("2. **관계 테이블 분리**: 교육과정 테이블에 역량 컬럼을 무리하게 욱여넣지 않고, `course_competency_mapping` 별도 관계로 관리합니다.\n")
        f.write("3. **출처 메타데이터 무결성**: 수집일(`collected_at`), 원문 수정일(`source_updated_at`), 최종 확인일(`last_verified_at`)을 절대 같은 값으로 채우지 않으며, 확인되지 않은 날짜와 검토자는 `NULL`로 보존합니다.\n")
        f.write("4. **텍스트 증거 무결성**: 원문에 실재하지 않는 텍스트 증거를 임의로 지어내지 않으며, 없을 경우 `UNAVAILABLE`로 기록합니다.\n\n")

        for s_name, s_info in schema_dict["schemas"].items():
            f.write(f"## 2. 테이블: `{s_name}`\n")
            f.write(f"- **설명**: {s_info['description']}\n")
            f.write(f"- **기본키(PK)**: `{', '.join(s_info['primary_key'])}`\n")
            if "foreign_keys" in s_info:
                f.write("- **외래키(FK)**:\n")
                for fk in s_info["foreign_keys"]:
                    f.write(f"  - `{fk['column']}` ➔ `{fk['references']}`\n")
            f.write("\n| 필드명 | 자료형 | Null 허용 | Enum / 기본값 | 필드 설명 및 비즈니스 규칙 |\n")
            f.write("| :--- | :--- | :---: | :--- | :--- |\n")
            for f_name, f_detail in s_info["fields"].items():
                null_str = "YES" if f_detail.get("nullable", True) else "**NO (필수)**"
                enum_str = ", ".join([str(x) for x in f_detail["enum"] if x is not None]) if "enum" in f_detail else f_detail.get("default", "-")
                f.write(f"| `{f_name}` | `{f_detail['type']}` | {null_str} | {enum_str} | {f_detail['description']} |\n")
            f.write("\n---\n\n")

    print(f"Generated schema docs at: {json_path} and {md_path}")

if __name__ == "__main__":
    generate_schema_docs()
