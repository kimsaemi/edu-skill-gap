"""
수도권 직무교육 프로젝트 - 인사·총무 직무 교육과정 수집기
파일명: scripts/collect_hr_courses.py

수집 대상:
  1. 한국산업인력공단 NCS 교육과정 API (대분류 02: 경영·회계·사무 -> 중분류 02: 총무·인사)
  2. 고용24 (구 HRD-Net) 국민내일배움카드 훈련과정 API
  3. 고용24 (구 HRD-Net) 사업주훈련 훈련과정 API

원칙 준수:
  - 실제 API 데이터만 사용 (가상 Mock 데이터 생성 절대 금지)
  - 인증키 화면 미출력 (보안 준수)
  - 원본 응답 그대로 'data/hr/raw'에 JSON/XML 파일로 보관
  - 코드값 및 과정 ID의 문자열(str) 보존
  - 페이지네이션, 호출 제한(Sleep), 예외 처리, 인증 실패 대응
"""

import os
import sys
import time
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from dotenv import load_dotenv

# 1. 환경변수 로드
load_dotenv()

# 저장 디렉토리 설정 (data/hr/raw)
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "hr" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def mask_key(k: str) -> str:
    """인증키 마스킹 (보안 출력용)"""
    if not k:
        return "[미설정]"
    if len(k) <= 8:
        return "****"
    return f"{k[:3]}****{k[-4:]} (총 {len(k)}자)"


# ==============================================================================
# [수집기 1] 한국산업인력공단 NCS 교육과정 API
# ==============================================================================
def collect_ncs_hr_courses(max_pages=10, delay_sec=0.5):
    """
    한국산업인력공단 NCS 교육과정 수집 (대분류 02: 경영·회계·사무)
    - 페이지네이션 지원 (pageNo 1부터 totalPage까지)
    - 원본 JSON 응답을 data/hr/raw/ncs_courses_page_{page}.json 및 통합본에 저장
    """
    print("\n" + "=" * 70)
    print("▶ [1/3] 한국산업인력공단 NCS 교육과정 API 수집 시작")
    print("=" * 70)

    dec_key = os.getenv("NCS_COURSE_API_KEY_DECODING") or os.getenv("DATA_GO_KR_API_KEY_DECODING")
    print(f"* 인증키 상태: {mask_key(dec_key)}")

    if not dec_key:
        print("[-] [인증 실패] NCS API 디코딩 인증키가 .env에 설정되어 있지 않습니다.")
        return {"success_count": 0, "fail_count": 1, "items": []}

    endpoint = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
    current_page = 1
    total_pages = 1
    all_raw_data = []
    success_pages = 0
    fail_pages = 0

    while current_page <= total_pages and current_page <= max_pages:
        params = {
            "serviceKey": dec_key,
            "pageNo": current_page,
            "numOfRows": 20,
            "returnType": "json",
            "ncsLclasCd": "02"  # 경영·회계·사무 대분류 (필수 파라미터, 2자리 문자열)
        }

        print(f"  - [{current_page}/{total_pages}] 페이지 호출 중... (대분류: 02)")
        try:
            res = requests.get(endpoint, params=params, timeout=10)
            
            # HTTP 상태 확인
            if res.status_code != 200:
                print(f"    [-] HTTP 오류 발생: {res.status_code}")
                fail_pages += 1
                break

            # JSON 파싱
            data = res.json()
            data_info = data.get("dataInfo", {})
            api_code = data_info.get("code")
            api_msg = data_info.get("message")

            # 인증키 만료나 파라미터 에러 등 대응
            if api_code != "000":
                print(f"    [-] API 오류 응답: 코드={api_code}, 메시지={api_msg}")
                fail_pages += 1
                break

            # 페이지 정보 갱신
            total_pages = int(data_info.get("totalPage", 1))
            tot_cnt = int(data_info.get("totCnt", 0))
            page_items = data.get("data", [])

            # 원본 응답 파일 저장 (수집 원본 그대로 보존)
            page_file = RAW_DIR / f"ncs_courses_page_{current_page}.json"
            with open(page_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            all_raw_data.extend(page_items)
            success_pages += 1
            print(f"    [+] {len(page_items)}건 수신 (누적 {len(all_raw_data)}/{tot_cnt}건) -> 원본 저장: {page_file.name}")

            current_page += 1
            time.sleep(delay_sec)  # API 호출 제한 방지 (Sleep)

        except requests.exceptions.Timeout:
            print("    [-] [타임아웃] 요청 시간이 초과되었습니다.")
            fail_pages += 1
            break
        except requests.exceptions.RequestException as e:
            print(f"    [-] [통신 오류] {e}")
            fail_pages += 1
            break
        except json.JSONDecodeError:
            print("    [-] [파싱 오류] JSON 응답을 해석할 수 없습니다.")
            fail_pages += 1
            break

    # 통합 원본 파일 저장
    combined_file = RAW_DIR / "ncs_courses_raw.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_raw_data, f, ensure_ascii=False, indent=2)

    # 인사·총무 관련 과정 필터링 확인 (NCS 중분류코드 '02' = 총무·인사)
    hr_candidates = []
    for item in all_raw_data:
        mclas_cd = str(item.get("ncsMclasCd", "")).zfill(2)
        mclas_nm = str(item.get("ncsMclasCdnm", ""))
        subj_name = str(item.get("asubjName", ""))
        edu_text = str(item.get("eduText", ""))

        # 중분류 02(총무·인사)이거나 관련 키워드가 포함된 경우
        if mclas_cd == "02" or any(kw in (subj_name + edu_text + mclas_nm) for kw in ["인사", "총무", "노무", "사무"]):
            hr_candidates.append(item)

    print(f"\n* NCS 교육과정 수집 결과:")
    print(f"  - 성공 페이지: {success_pages}개, 실패 페이지: {fail_pages}개")
    print(f"  - 수집된 전체 원본 건수: {len(all_raw_data)}건")
    print(f"  - 인사·총무·사무 관련 후보 건수: {len(hr_candidates)}건")

    return {
        "success_count": len(all_raw_data),
        "fail_count": fail_pages,
        "hr_candidate_count": len(hr_candidates),
        "raw_file": str(combined_file)
    }


# ==============================================================================
# [수집기 2] 고용24 국민내일배움카드 훈련과정 API (공식 엔드포인트)
# ==============================================================================
def collect_kmbc_hr_courses():
    print("\n" + "=" * 70)
    print("▶ [2/3] 국민내일배움카드 훈련과정 API 수집 시작 (고용24 공식 엔드포인트)")
    print("=" * 70)

    auth_key = os.getenv("HRD_KMBC_API_KEY")
    print(f"* 인증키 상태: {mask_key(auth_key)}")

    if not auth_key:
        print("[-] [인증 실패] HRD_KMBC_API_KEY가 .env에 설정되어 있지 않습니다.")
        return {"success_count": 0, "fail_count": 1}

    # 고용24 공식 최신 엔드포인트
    endpoint = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
    params = {
        "authKey": auth_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": "1",
        "pageSize": "20",
        "srchTraStDt": "20250101",
        "srchTraEndDt": "20251231",
        "srchTraProcess": "인사"  # 인사 관련 검색어
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        res = requests.get(endpoint, params=params, headers=headers, timeout=15)
        print(f"* HTTP 응답 코드: {res.status_code}")
        
        if res.status_code != 200:
            print(f"[-] HTTP 오류 발생: {res.status_code}")
            return {"success_count": 0, "fail_count": 1, "reason": f"HTTP {res.status_code}"}

        # 원본 XML 저장 (data/hr/raw/)
        raw_xml_file = RAW_DIR / "kmbc_courses_raw.xml"
        with open(raw_xml_file, "w", encoding="utf-8") as f:
            f.write(res.text)

        # XML 파싱 및 항목 추출
        root = ET.fromstring(res.text)
        scn_cnt = root.findtext("scn_cnt") or "0"
        items = root.findall(".//scn_list") or root.findall(".//item")
        
        print(f"[+] 연동 성공! 총 검색 건수: {scn_cnt}건 중 1페이지 {len(items)}건 수신 완료")
        print(f"    * 원본 XML 저장 완료: {raw_xml_file.name}")

        parsed_items = []
        for it in items:
            parsed_items.append({elem.tag: elem.text for elem in it})

        # JSON 형식으로도 보관
        raw_json_file = RAW_DIR / "kmbc_courses_raw.json"
        with open(raw_json_file, "w", encoding="utf-8") as f:
            json.dump(parsed_items, f, ensure_ascii=False, indent=2)

        return {"success_count": len(items), "fail_count": 0, "total_cnt": scn_cnt, "raw_file": str(raw_xml_file)}

    except Exception as e:
        print(f"[-] 요청 실패: {e}")
        return {"success_count": 0, "fail_count": 1, "reason": str(e)}


# ==============================================================================
# [수집기 3] 고용24 사업주훈련 훈련과정 API (공식 엔드포인트)
# ==============================================================================
def collect_employer_hr_courses():
    print("\n" + "=" * 70)
    print("▶ [3/3] 사업주훈련 훈련과정 API 수집 시작 (고용24 공식 엔드포인트)")
    print("=" * 70)

    auth_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY")
    print(f"* 인증키 상태: {mask_key(auth_key)}")

    if not auth_key:
        print("[-] [인증 실패] HRD_EMPLOYER_TRAINING_API_KEY가 .env에 설정되어 있지 않습니다.")
        return {"success_count": 0, "fail_count": 1}

    # 고용24 공식 최신 엔드포인트
    endpoint = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do"
    params = {
        "authKey": auth_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": "1",
        "pageSize": "20",
        "srchTraStDt": "20250101",
        "srchTraEndDt": "20251231",
        "srchTraProcess": "총무"  # 총무 관련 검색어
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        res = requests.get(endpoint, params=params, headers=headers, timeout=15)
        print(f"* HTTP 응답 코드: {res.status_code}")

        if res.status_code != 200:
            print(f"[-] HTTP 오류 발생: {res.status_code}")
            return {"success_count": 0, "fail_count": 1, "reason": f"HTTP {res.status_code}"}

        # 원본 XML 저장 (data/hr/raw/)
        raw_xml_file = RAW_DIR / "employer_courses_raw.xml"
        with open(raw_xml_file, "w", encoding="utf-8") as f:
            f.write(res.text)

        root = ET.fromstring(res.text)
        scn_cnt = root.findtext("scn_cnt") or "0"
        items = root.findall(".//scn_list") or root.findall(".//item")

        print(f"[+] 연동 성공! 총 검색 건수: {scn_cnt}건 중 1페이지 {len(items)}건 수신 완료")
        print(f"    * 원본 XML 저장 완료: {raw_xml_file.name}")

        parsed_items = []
        for it in items:
            parsed_items.append({elem.tag: elem.text for elem in it})

        raw_json_file = RAW_DIR / "employer_courses_raw.json"
        with open(raw_json_file, "w", encoding="utf-8") as f:
            json.dump(parsed_items, f, ensure_ascii=False, indent=2)

        return {"success_count": len(items), "fail_count": 0, "total_cnt": scn_cnt, "raw_file": str(raw_xml_file)}

    except Exception as e:
        print(f"[-] 요청 실패: {e}")
        return {"success_count": 0, "fail_count": 1, "reason": str(e)}


# ==============================================================================
# 메인 실행 진입점
# ==============================================================================
def main():
    print("=" * 70)
    print(" [수도권 직무교육] 인사·총무 직무 교육과정 데이터 수집 파이프라인")
    print(f" 저장 위치: {RAW_DIR}")
    print("=" * 70)

    # 1. 한국산업인력공단 NCS 교육과정 수집
    ncs_result = collect_ncs_hr_courses(max_pages=5, delay_sec=0.3)

    # 2. 국민내일배움카드 수집
    kmbc_result = collect_kmbc_hr_courses()

    # 3. 사업주훈련 수집
    emp_result = collect_employer_hr_courses()

    # 최종 결과 요약 출력
    print("\n" + "=" * 70)
    print(" [최종 데이터 수집 집계 보고서]")
    print("=" * 70)
    print(f"1. 한국산업인력공단 NCS 교육과정:")
    print(f"   - 수집 성공: {ncs_result['success_count']}건 (실제 데이터)")
    print(f"   - 수집 실패: {ncs_result['fail_count']}건")
    print(f"   - 인사·총무 관련 후보: {ncs_result.get('hr_candidate_count', 0)}건")
    print(f"   - 저장 파일: {ncs_result.get('raw_file', '-')}")

    print(f"\n2. 국민내일배움카드 훈련과정:")
    print(f"   - 수집 성공: {kmbc_result['success_count']}건")
    print(f"   - 수집 실패: {kmbc_result['fail_count']}건 ({kmbc_result.get('reason', '')})")

    print(f"\n3. 사업주훈련 훈련과정:")
    print(f"   - 수집 성공: {emp_result['success_count']}건")
    print(f"   - 수집 실패: {emp_result['fail_count']}건 ({emp_result.get('reason', '')})")

    print("-" * 70)
    print(f"* 전체 저장 경로: {RAW_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
