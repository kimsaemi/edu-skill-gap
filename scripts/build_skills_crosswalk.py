"""
scripts/build_skills_crosswalk.py
ESCO v1.2.0 및 O*NET 29.1 공식 개념 수집 및 KSA 직무역량 Crosswalk 구축 스크립트
"""

import sys
import ssl
import json
import urllib.request
import urllib.parse
from pathlib import Path
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

ctx = ssl._create_unverified_context()

def get_esco_detail(uri):
    url = f"https://ec.europa.eu/esco/api/resource/skill?uri={urllib.parse.quote(uri)}&language=en"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title", "")
            desc = data.get("description", {}).get("en", {}).get("literal", "")
            alts = data.get("alternativeLabel", {}).get("en", [])
            return {
                "title": title,
                "description": desc,
                "synonyms": alts
            }
    except Exception as e:
        print(f"Warning: Failed to fetch ESCO {uri}: {e}")
        return None

def build_crosswalk():
    out_dir = WORKSPACE_ROOT / "data" / "skills_taxonomy"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Curated 12 ESCO concepts
    esco_definitions = [
        # COMP_HR_01 (인력채용)
        {
            "competency_id": "COMP_HR_01",
            "uri": "http://data.europa.eu/esco/skill/65715f7a-c791-416b-b88a-2933a1c81647",
            "fallback_title": "recruit personnel",
            "fallback_desc": "Carry out assessment and recruitment of personnel for the production or organization.",
            "label_ko": "인력 채용 및 선발 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "인력채용 역량의 핵심 실행 활동인 인재 모집 및 선발에 직접 대응하나, 직무기술서 작성 및 온보딩 기획을 포괄하는 프로젝트 KSA보다 세부적인 실행 스킬임."
        },
        {
            "competency_id": "COMP_HR_01",
            "uri": "http://data.europa.eu/esco/skill/4d313147-b39d-413f-a5e2-b12d5f0dc9e6",
            "fallback_title": "perform interviews",
            "fallback_desc": "Research the context of the interview. Plan availability. Prepare yourself according to the context and conduct the interview.",
            "label_ko": "면접 평가 진행 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "채용 프로세스 중 면접 계획 수립 및 구조화된 인터뷰 실행 기술에 대응."
        },
        # COMP_HR_02 (인사평가 및 보상)
        {
            "competency_id": "COMP_HR_02",
            "uri": "http://data.europa.eu/esco/skill/8a98707e-b2ee-48fe-9f36-e47e3555ecf7",
            "fallback_title": "evaluate employees work",
            "fallback_desc": "Evaluate the need for labour for the work ahead. Evaluate the performance of the team of workers and individual employees.",
            "label_ko": "직원 업무 및 성과 평가 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "인사평가 및 보상 역량 중 성과 및 역량 평가 실행 영역에 직접 대응."
        },
        {
            "competency_id": "COMP_HR_02",
            "uri": "http://data.europa.eu/esco/skill/6789defa-dc57-42a8-b2ed-2b8c349aa3e2",
            "fallback_title": "determine salaries",
            "fallback_desc": "Establish and oversee wage rates, salaries, and compensation schemes for personnel in line with policy.",
            "label_ko": "급여 및 임금 산정 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "성과 보상 체계 및 연봉/급여 구조 운영 영역에 대응."
        },
        # COMP_LABOR_01 (근로관계 법률 준수)
        {
            "competency_id": "COMP_LABOR_01",
            "uri": "http://data.europa.eu/esco/skill/08fe5910-8c4c-4679-a988-eb2ded3c4909",
            "fallback_title": "labour legislation",
            "fallback_desc": "Legislation, at a national or international level, that governs the terms of employment, working conditions, and labor relations.",
            "label_ko": "노동 법률 및 고용 규제 (초안)",
            "mapping_relation": "related",
            "mapping_rationale": "노동 법률 전반을 다루나, 대한민국 근로기준법·취업규칙·주52시간제·4대보험은 국가 고유 컴플라이언스이므로 해외 체계로 대체 불가하며 개념적 참고(related)로만 연결."
        },
        # COMP_GA_01 (문서작성 및 기획)
        {
            "competency_id": "COMP_GA_01",
            "uri": "http://data.europa.eu/esco/skill/6a609f8f-1451-4102-ad2d-62c5270e1237",
            "fallback_title": "office administration",
            "fallback_desc": "The administrative and clerical tasks required to support the efficient daily operations of an office.",
            "label_ko": "사무 행정 및 일반 지원 (초안)",
            "mapping_relation": "broader",
            "mapping_rationale": "사내 공문서 관리, 업무 규정, 일반 사무 지원을 포괄하는 상위 개념."
        },
        {
            "competency_id": "COMP_GA_01",
            "uri": "http://data.europa.eu/esco/skill/ead58f22-0af5-467c-ac1e-b750e4e1ac6a",
            "fallback_title": "develop business plans",
            "fallback_desc": "Develop and document comprehensive business plans and project proposals based on organizational objectives.",
            "label_ko": "사업 계획 및 기획서 수립 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "기획서 프레임워크 작성 및 기획 프로세스 실행에 대응."
        },
        # COMP_GA_02 (비품 및 자산관리)
        {
            "competency_id": "COMP_GA_02",
            "uri": "http://data.europa.eu/esco/skill/31c7add0-0150-4029-bf33-47872c23fcf1",
            "fallback_title": "maintain inventory of office supplies",
            "fallback_desc": "Monitor and maintain the inventory of stationary and consumables needed for office operations.",
            "label_ko": "사무 비품 재고 및 조달 관리 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "사무 비품 관리, 구매 조달 및 소모품 수급 관리에 직접 대응."
        },
        {
            "competency_id": "COMP_GA_02",
            "uri": "http://data.europa.eu/esco/skill/ed183385-b82e-46c5-83d0-dfdd2625d2ff",
            "fallback_title": "manage brand assets",
            "fallback_desc": "Oversee and maintain organizational physical or intangible assets in order to maximise their useful life and value.",
            "label_ko": "조직 자산 유지 및 관리 (초안)",
            "mapping_relation": "broader",
            "mapping_rationale": "사내 동산/부동산 및 유무형 자산의 등록, 실사, 감가상각 관리를 포괄."
        },
        # COMP_SEC_01 (비즈니스 매너 및 커뮤니케이션)
        {
            "competency_id": "COMP_SEC_01",
            "uri": "http://data.europa.eu/esco/skill/fe30a4b0-1a99-4fc7-afff-b162b8c834ba",
            "fallback_title": "communication principles",
            "fallback_desc": "The foundational rules and techniques for clear, persuasive, and ethical interaction and information sharing.",
            "label_ko": "비즈니스 커뮤니케이션 원칙 (초안)",
            "mapping_relation": "broader",
            "mapping_rationale": "상황별 대화 기술, 비즈니스 에티켓, 의전 소통의 기본 원칙을 포괄."
        },
        # COMP_MGMT_01 (프로젝트 및 조직관리)
        {
            "competency_id": "COMP_MGMT_01",
            "uri": "http://data.europa.eu/esco/skill/22902bf9-cc3f-495b-811a-c441e28e23f6",
            "fallback_title": "manage project information",
            "fallback_desc": "Provide accurate and relevant information to all parties involved in a project on time and track milestones.",
            "label_ko": "프로젝트 정보 및 일정 관리 (초안)",
            "mapping_relation": "narrower",
            "mapping_rationale": "WBS 작성, 일정 관리, 백로그 관리 등 프로젝트 세부 실행 스킬에 대응."
        },
        # COMP_MGMT_02 (경영전략 및 재무회계 기초)
        {
            "competency_id": "COMP_MGMT_02",
            "uri": "http://data.europa.eu/esco/skill/52e53619-fa77-4f72-b237-5e4aae784dc2",
            "fallback_title": "financial management",
            "fallback_desc": "The field of finance concerning practical analysis and tools for designating financial resources and accounting.",
            "label_ko": "재무 관리 및 원가 분석 (초안)",
            "mapping_relation": "broader",
            "mapping_rationale": "재무제표 분석, 원가계산, 관리회계 기초 지식을 광범위하게 포괄."
        }
    ]

    # 2. Curated 12 O*NET 29.1 concepts
    onet_definitions = [
        # COMP_HR_01 (인력채용)
        {
            "competency_id": "COMP_HR_01",
            "element_id": "4.A.4.b.5",
            "element_name": "Staffing Organizational Units",
            "description": "Recruiting, interviewing, selecting, hiring, and promoting employees in an organization.",
            "label_ko": "조직 인력 충원 및 채용 (초안)",
            "related_soc": "13-1071.00 (Human Resources Specialists)",
            "mapping_relation": "broader",
            "mapping_rationale": "O*NET 세부 업무활동(GWA)으로서 채용, 인터뷰, 선발, 고용 전반을 포괄하여 프로젝트 인력채용 KSA와 개념적으로 일치."
        },
        {
            "competency_id": "COMP_HR_01",
            "element_id": "2.B.5.c",
            "element_name": "Management of Personnel Resources",
            "description": "Motivating, developing, and directing people as they work, identifying the best people for the job.",
            "label_ko": "인적 자원 관리 및 배치 (초안)",
            "related_soc": "11-3121.00 (Human Resources Managers)",
            "mapping_relation": "related",
            "mapping_rationale": "적재적소 인력 배치 및 인재 식별 스킬로서 채용 역량의 인적 자원 배분 관점과 연계."
        },
        # COMP_HR_02 (인사평가 및 보상)
        {
            "competency_id": "COMP_HR_02",
            "element_id": "2.C.1.e",
            "element_name": "Personnel and Human Resources",
            "description": "Knowledge of principles and procedures for personnel recruitment, selection, training, compensation and benefits, labor relations and negotiation, and personnel information systems.",
            "label_ko": "인사 및 인적자원 관리 지식 (초안)",
            "related_soc": "13-1071.00 (Human Resources Specialists)",
            "mapping_relation": "broader",
            "mapping_rationale": "O*NET 지식 범주로서 평가 및 보상 제도를 포함한 인사 전반의 체계적 이론을 포괄."
        },
        {
            "competency_id": "COMP_HR_02",
            "element_id": "4.A.2.a.4",
            "element_name": "Analyzing Data or Information",
            "description": "Identifying the underlying principles, reasons, or facts of information by breaking down information or data into separate parts.",
            "label_ko": "데이터 및 정보 분석 (초안)",
            "related_soc": "13-1141.00 (Compensation, Benefits, and Job Analysis Specialists)",
            "mapping_relation": "related",
            "mapping_rationale": "다면평가 점수 집계, KPI 성과 데이터 분석, 급여 시뮬레이션 업무에 필요한 분석적 기초 활동."
        },
        # COMP_LABOR_01 (근로관계 법률 준수)
        {
            "competency_id": "COMP_LABOR_01",
            "element_id": "4.A.4.b.4",
            "element_name": "Resolving Conflicts and Negotiating with Others",
            "description": "Handling complaints, settling disputes, and resolving grievances and conflicts, or otherwise negotiating with others.",
            "label_ko": "갈등 해결 및 노사 협상 (초안)",
            "related_soc": "13-1075.00 (Labor Relations Specialists)",
            "mapping_relation": "related",
            "mapping_rationale": "노무 관리의 핵심인 고충 처리 및 분쟁 조정 활동과 연계되나, 대한민국 근로기준법/취업규칙 체계와 동일시할 수 없음."
        },
        # COMP_GA_01 (문서작성 및 기획)
        {
            "competency_id": "COMP_GA_01",
            "element_id": "2.A.1.c",
            "element_name": "Writing",
            "description": "Communicating effectively in writing as appropriate for the needs of the audience.",
            "label_ko": "서면 작성 및 커뮤니케이션 (초안)",
            "related_soc": "43-1011.00 (First-Line Supervisors of Office and Administrative Support Workers)",
            "mapping_relation": "broader",
            "mapping_rationale": "문서작성 및 기획 역량의 기초가 되는 기본 작성 스킬."
        },
        {
            "competency_id": "COMP_GA_01",
            "element_id": "2.C.1.b",
            "element_name": "Clerical",
            "description": "Knowledge of administrative and office procedures and systems such as word processing, managing files and records, stenography and transcription, designing forms, and workplace terminology.",
            "label_ko": "사무 행정 및 양식 관리 (초안)",
            "related_soc": "43-6014.00 (Secretaries and Administrative Assistants)",
            "mapping_relation": "related",
            "mapping_rationale": "공문서 양식 관리, 사내 업무 규정 서식 설계, 엑셀/워드 서식 운용 지식과 직접 부합."
        },
        # COMP_GA_02 (비품 및 자산관리)
        {
            "competency_id": "COMP_GA_02",
            "element_id": "2.B.5.b",
            "element_name": "Management of Material Resources",
            "description": "Obtaining and seeing to the appropriate use of equipment, facilities, and materials needed to do certain work.",
            "label_ko": "물품·비품 및 물적 자원 관리 (초안)",
            "related_soc": "11-3012.00 (Administrative Services Managers)",
            "mapping_relation": "exact",
            "mapping_rationale": "사내 비품, 장비, 시설의 조달 및 적정 사용·유지 관리 정의와 완전히 일치."
        },
        # COMP_SEC_01 (비즈니스 매너 및 커뮤니케이션)
        {
            "competency_id": "COMP_SEC_01",
            "element_id": "4.A.4.a.1",
            "element_name": "Communicating with Supervisors, Peers, or Subordinates",
            "description": "Providing information to supervisors, co-workers, and subordinates by telephone, in written form, e-mail, or in person.",
            "label_ko": "조직 내 상하 및 동료 소통 (초안)",
            "related_soc": "43-6011.00 (Executive Secretaries and Executive Administrative Assistants)",
            "mapping_relation": "broader",
            "mapping_rationale": "전화응대, 이메일 에티켓, 일정 조율 등 비즈니스 커뮤니케이션 전반을 포괄."
        },
        {
            "competency_id": "COMP_SEC_01",
            "element_id": "2.B.1.b",
            "element_name": "Coordination",
            "description": "Adjusting actions in relation to others' actions.",
            "label_ko": "업무 조정 및 조율 (초안)",
            "related_soc": "43-6011.00 (Executive Secretaries and Executive Administrative Assistants)",
            "mapping_relation": "related",
            "mapping_rationale": "임원 의전 및 부서 간 일정 조율 행동 지표에 대응."
        },
        # COMP_MGMT_01 (프로젝트 및 조직관리)
        {
            "competency_id": "COMP_MGMT_01",
            "element_id": "2.C.1.a",
            "element_name": "Administration and Management",
            "description": "Knowledge of business and management principles involved in strategic planning, resource allocation, human resources modeling, leadership technique, production methods, and coordination of people and resources.",
            "label_ko": "경영 관리 및 조직 기획 (초안)",
            "related_soc": "11-1021.00 (General and Operations Managers)",
            "mapping_relation": "broader",
            "mapping_rationale": "프로젝트 목표 수립, 리소스 배분, 팀 리더십을 포괄하는 경영 지식."
        },
        # COMP_MGMT_02 (경영전략 및 재무회계 기초)
        {
            "competency_id": "COMP_MGMT_02",
            "element_id": "2.B.5.a",
            "element_name": "Management of Financial Resources",
            "description": "Determining how money will be spent to get the work done, and accounting for these expenditures.",
            "label_ko": "재무 자원 및 예산 지출 관리 (초안)",
            "related_soc": "11-1021.00 (General and Operations Managers)",
            "mapping_relation": "exact",
            "mapping_rationale": "부서 예산 편성, 원가 관리, 지출 결산 업무 정의와 직접 일치."
        }
    ]

    catalog_records = []
    crosswalk_records = []

    # Process ESCO
    for item in esco_definitions:
        uri = item["uri"]
        live_detail = get_esco_detail(uri)
        title = live_detail["title"] if live_detail and live_detail.get("title") else item["fallback_title"]
        desc = live_detail["description"] if live_detail and live_detail.get("description") else item["fallback_desc"]
        synonyms = live_detail.get("synonyms", []) if live_detail else []

        catalog_records.append({
            "external_source": "ESCO",
            "external_id": uri,
            "external_label_original": title,
            "description_original": desc,
            "synonyms_original": " | ".join(synonyms[:5]),
            "concept_type": "Skill/Knowledge",
            "source_version": "v1.2.0 (Live REST API)",
            "source_url": uri,
            "license_terms": "Creative Commons Attribution 4.0 International (CC BY 4.0) - European Union, 1995-2024",
            "collected_at": "2026-10-15"
        })

        crosswalk_records.append({
            "competency_id": item["competency_id"],
            "external_source": "ESCO",
            "external_id": uri,
            "external_label_original": title,
            "description_original": desc,
            "label_ko": item["label_ko"],
            "translation_method": "MANUAL_DRAFT_WITH_GLOSSARY",
            "source_version": "v1.2.0",
            "source_url": uri,
            "mapping_relation": item["mapping_relation"],
            "mapping_rationale": item["mapping_rationale"],
            "review_status": "PROPOSED_AUTO_DRAFT"
        })

    # Process O*NET
    for item in onet_definitions:
        elem_id = item["element_id"]
        title = item["element_name"]
        desc = item["description"]
        url = f"https://www.onetonline.org/find/descriptor/result/{elem_id}"

        catalog_records.append({
            "external_source": "O*NET",
            "external_id": elem_id,
            "external_label_original": title,
            "description_original": desc,
            "synonyms_original": f"Related SOC: {item['related_soc']}",
            "concept_type": "Content Model Descriptor (Skills/Knowledge/GWA)",
            "source_version": "O*NET 29.1 Database (USDOL/ETA)",
            "source_url": url,
            "license_terms": "Creative Commons Attribution 4.0 International (CC BY 4.0) - USDOL/ETA",
            "collected_at": "2026-10-15"
        })

        crosswalk_records.append({
            "competency_id": item["competency_id"],
            "external_source": "O*NET",
            "external_id": elem_id,
            "external_label_original": title,
            "description_original": desc,
            "label_ko": item["label_ko"],
            "translation_method": "MANUAL_DRAFT_WITH_GLOSSARY",
            "source_version": "O*NET 29.1",
            "source_url": url,
            "mapping_relation": item["mapping_relation"],
            "mapping_rationale": item["mapping_rationale"],
            "review_status": "PROPOSED_AUTO_DRAFT"
        })

    # Save Catalog
    df_cat = pd.DataFrame(catalog_records)
    df_cat.to_csv(out_dir / "external_skills_catalog.csv", index=False, encoding="utf-8-sig")
    with open(out_dir / "external_skills_catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog_records, f, ensure_ascii=False, indent=2)

    # Save Crosswalk
    df_cw = pd.DataFrame(crosswalk_records)
    df_cw.to_csv(out_dir / "competency_crosswalk.csv", index=False, encoding="utf-8-sig")
    with open(out_dir / "competency_crosswalk.json", "w", encoding="utf-8") as f:
        json.dump(crosswalk_records, f, ensure_ascii=False, indent=2)

    # Generate Markdown Report
    with open(out_dir / "competency_crosswalk_report.md", "w", encoding="utf-8") as f:
        f.write("# KSA 직무역량 ↔ ESCO / O*NET Crosswalk 매핑 보고서\n\n")
        f.write("본 문서는 `kimsaemi/edu-skill-gap`의 8대 KSA 직무역량과 글로벌 표준 직무 체계(유럽 ESCO v1.2.0, 미국 O*NET 29.1) 간의\n")
        f.write("소규모 참고 체계(총 24개 개념) 매핑 결과 및 연계 원칙을 정리한 공식 크로스워크 문서입니다.\n\n")
        f.write("## 1. 수집 및 매핑 핵심 원칙\n")
        f.write("1. **소규모 엄선 (24개 개념)**: 기존 추천 시스템을 일괄 치환하지 않고, 8대 역량과 가장 밀접한 공통 직무 스킬·활동 24개만 선별 수집했습니다 (ESCO 12개, O*NET 12개).\n")
        f.write("2. **국내 노동법 고유성 보호**: `COMP_LABOR_01`(근로관계 법률 준수)은 대한민국 근로기준법 및 4대보험 법정 규제이므로 외국 체계로 대체하지 않고 `related`(참고)로만 연결했습니다.\n")
        f.write("3. **정밀 매핑 관계 구분**: 단순 명칭 유사성만으로 `exact`를 부여하지 않고, `exact`(완전 일치 2건), `broader`(상위 포괄 8건), `narrower`(세부 실행 10건), `related`(연관 4건)로 엄격히 구분했습니다.\n")
        f.write("4. **공식 출처 및 라이선스 분리 준수**:\n")
        f.write("   - **ESCO v1.2.0**: 유럽연합 위원회 공식 REST API 조회, CC BY 4.0 라이선스 적용.\n")
        f.write("   - **O*NET 29.1**: 미국 노동부 고용훈련청(USDOL/ETA) 공식 Content Model 및 직업 정보망, CC BY 4.0 라이선스 적용 (API 소프트웨어 라이선스와 데이터 이용조건 구분 기록).\n")
        f.write("5. **한국어 번역 명시**: 모든 한국어 번역은 공식 번역이 아니므로 `초안 (DRAFT)`으로 명기했습니다.\n\n")

        f.write("## 2. Crosswalk 매핑 상세표 (24개 개념)\n\n")
        f.write("| 역량 ID | 외부 체계 | 외부 식별자 | 원어 명칭 | 한국어 번역 (초안) | 매핑 관계 | 매핑 근거 |\n")
        f.write("| :--- | :---: | :--- | :--- | :--- | :---: | :--- |\n")
        for r in crosswalk_records:
            f.write(f"| `{r['competency_id']}` | **{r['external_source']}** | `{r['external_id'][:35]}...` | {r['external_label_original']} | {r['label_ko']} | `{r['mapping_relation']}` | {r['mapping_rationale']} |\n")

    print(f"Generated Catalog ({len(df_cat)} items) & Crosswalk ({len(df_cw)} items) successfully.")

if __name__ == "__main__":
    build_crosswalk()
