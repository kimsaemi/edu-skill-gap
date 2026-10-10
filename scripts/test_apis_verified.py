"""
수도권 직무교육 프로젝트 - 3대 교육과정 API 1페이지 호출 테스트 스크립트
대상 API:
  1. 국민내일배움카드 훈련과정 API (고용24 / HRD-Net)
  2. 사업주훈련 훈련과정 API (고용24 / HRD-Net)
  3. NCS 교육과정 API (한국산업인력공단 / 공공데이터포털)

보안 원칙: 인증키는 절대 화면이나 로그에 노출하지 않음 (마스킹 처리).
판정 원칙: 실제 유효한 데이터 응답(데이터 레코드 존재)을 확인하기 전에는 연동 성공으로 판정하지 않음.
"""

import os
import requests
import json
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# .env 로드
load_dotenv()

def mask_key(key: str) -> str:
    """인증키 마스킹 함수 (보안 준수)"""
    if not key:
        return "[미설정]"
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]} (총 {len(key)}자)"


def test_ncs_course_api() -> dict:
    """
    1. 한국산업인력공단 NCS 교육과정 API 테스트
    엔드포인트: http://apis.data.go.kr/B490007/ncsEduCource/openapi20
    """
    print("\n" + "="*70)
    print(" [테스트 1] 한국산업인력공단 NCS 교육과정 API")
    print("="*70)

    # Decoding 키 우선 사용 (requests 파라미터 전달 시)
    dec_key = os.getenv("NCS_COURSE_API_KEY_DECODING") or os.getenv("DATA_GO_KR_API_KEY_DECODING")
    enc_key = os.getenv("NCS_COURSE_API_KEY") or os.getenv("DATA_GO_KR_API_KEY_ENCODING")
    
    print(f"* 인증키 로드 상태: Decoding={mask_key(dec_key)}, Encoding={mask_key(enc_key)}")

    url = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
    
    # 필수 파라미터: ncsLclasCd (대분류코드: '02' 경영·회계·사무)
    params = {
        "serviceKey": dec_key,
        "pageNo": 1,
        "numOfRows": 5,
        "returnType": "json",
        "ncsLclasCd": "02"  # 경영·회계·사무 필수 파라미터
    }

    result = {
        "api_name": "한국산업인력공단 NCS 교육과정",
        "endpoint": url,
        "status": "미확인",
        "http_code": None,
        "record_count": 0,
        "fields": [],
        "sample_item": None,
        "error_message": None
    }

    if not dec_key:
        result["status"] = "실패 (인증키 누락)"
        print("[-] .env 파일에 NCS_COURSE_API_KEY_DECODING 또는 DATA_GO_KR_API_KEY_DECODING이 없습니다.")
        return result

    try:
        response = requests.get(url, params=params, timeout=10)
        result["http_code"] = response.status_code
        print(f"* HTTP 응답 코드: {response.status_code}")
        print(f"* 응답 Content-Type: {response.headers.get('Content-Type')}")

        if response.status_code == 200:
            try:
                data = response.json()
                data_info = data.get("dataInfo", {})
                code = data_info.get("code")
                msg = data_info.get("message")
                total_cnt = data_info.get("totCnt", 0)
                items = data.get("data", [])

                print(f"* API 내부 응답코드: {code} ({msg}), 총 건수: {total_cnt}, 수신 건수: {len(items)}")

                if code == "000" and len(items) > 0:
                    result["status"] = "성공 (실제 데이터 수신 확인)"
                    result["record_count"] = len(items)
                    result["fields"] = list(items[0].keys())
                    # 키는 포함되지 않은 일반 메타 정보만 샘플로 보관
                    result["sample_item"] = {
                        "ncsLclasCd": str(items[0].get("ncsLclasCd")),
                        "ncsLclasCdnm": items[0].get("ncsLclasCdnm"),
                        "ncsMclasCd": str(items[0].get("ncsMclasCd")),
                        "ncsMclasCdnm": items[0].get("ncsMclasCdnm"),
                        "asubjName": items[0].get("asubjName"),
                        "point": items[0].get("point"),
                        "theoryLctrYn": items[0].get("theoryLctrYn"),
                        "prctYn": items[0].get("prctYn")
                    }
                    print("[+] 연동 검증 성공: 실제 NCS 교육과정 레코드를 정상 수신했습니다.")
                    print(f"    - 샘플 과목: [{result['sample_item']['asubjName']}] (대분류: {result['sample_item']['ncsLclasCdnm']})")
                else:
                    result["status"] = f"실패 (API 오류코드: {code}, 메시지: {msg})"
                    print(f"[-] 연동 미완료: API 응답 코드가 정상이 아니거나 데이터가 0건입니다. ({code}: {msg})")
            except Exception as e_json:
                result["status"] = "실패 (JSON 파싱 에러)"
                result["error_message"] = str(e_json)
                print(f"[-] JSON 파싱 실패. 본문 일부: {response.text[:200]}")
        else:
            result["status"] = f"실패 (HTTP 상태 {response.status_code})"
            print(f"[-] HTTP 오류 발생: {response.text[:200]}")

    except Exception as e:
        result["status"] = "실패 (통신 예외)"
        result["error_message"] = str(e)
        print(f"[-] 요청 실패: {e}")

    return result


def test_kmbc_training_api() -> dict:
    """
    2. 국민내일배움카드 훈련과정 API 테스트 (고용24 / HRD-Net)
    """
    print("\n" + "="*70)
    print(" [테스트 2] 국민내일배움카드 훈련과정 API (고용24 / HRD-Net)")
    print("="*70)

    auth_key = os.getenv("HRD_KMBC_API_KEY")
    print(f"* 인증키 로드 상태: {mask_key(auth_key)}")

    # 기존 설정 엔드포인트
    endpoint = "https://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp"
    
    params = {
        "authKey": auth_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": "1",
        "pageSize": "5",
        "srchTraStDt": "20250101",
        "srchTraEndDt": "20250630",
        "sort": "DESC",
        "sortCol": "TR_ST_DT"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    result = {
        "api_name": "국민내일배움카드 훈련과정 (HRD-Net)",
        "endpoint": endpoint,
        "status": "미확인",
        "http_code": None,
        "record_count": 0,
        "fields": [],
        "error_message": None
    }

    if not auth_key:
        result["status"] = "실패 (인증키 누락)"
        print("[-] .env 파일에 HRD_KMBC_API_KEY가 없습니다.")
        return result

    try:
        # allow_redirects=False 로 리다이렉션 여부 감지
        resp_check = requests.get(endpoint, params=params, headers=headers, timeout=10, allow_redirects=False)
        result["http_code"] = resp_check.status_code
        print(f"* 최초 요청 HTTP 코드: {resp_check.status_code}")
        
        if resp_check.status_code in (301, 302):
            redirect_url = resp_check.headers.get("Location")
            print(f"[-] 도메인 이전 감지: {endpoint} -> {redirect_url} 로 리다이렉트됨.")
            print("    [진단] 고용24 개편으로 구 HRD-Net 엔드포인트가 고용24 메인으로 301 리디렉션 처리되었습니다.")
            result["status"] = f"연동 실패 (도메인 이전 301 리다이렉트 -> {redirect_url})"
            result["error_message"] = "구 엔드포인트 폐기됨. 공공데이터포털 또는 고용24 최신 오픈API 엔드포인트로 갱신 필요."
            return result

        # 리디렉션 따라간 실제 응답 확인
        response = requests.get(endpoint, params=params, headers=headers, timeout=10)
        content_type = response.headers.get("Content-Type", "")
        print(f"* 최종 수신 Content-Type: {content_type}")

        if "text/html" in content_type:
            result["status"] = "연동 실패 (HTML 웹페이지 반환 - API 엔드포인트 비활성)"
            result["error_message"] = "API 응답(XML/JSON) 대신 고용24 포털 HTML 페이지가 반환됨."
            print("[-] 연동 실패: 데이터 포맷(XML)이 아닌 HTML 웹페이지가 반환되었습니다.")
            return result

        # XML 파싱 시도
        try:
            root = ET.fromstring(response.text)
            items = root.findall(".//scn_list") or root.findall(".//item")
            if items:
                result["status"] = "성공 (실제 데이터 수신 확인)"
                result["record_count"] = len(items)
                result["fields"] = [elem.tag for elem in items[0]]
                print(f"[+] 연동 성공: {len(items)}개 과정 수신 확인.")
            else:
                result["status"] = "실패 (데이터 0건 또는 오류 응답)"
                result["error_message"] = response.text[:200]
        except Exception as e_xml:
            result["status"] = "실패 (XML 파싱 불가)"
            result["error_message"] = str(e_xml)

    except Exception as e:
        result["status"] = "실패 (네트워크 오류)"
        result["error_message"] = str(e)
        print(f"[-] 요청 실패: {e}")

    return result


def test_employer_training_api() -> dict:
    """
    3. 사업주훈련 훈련과정 API 테스트 (고용24 / HRD-Net)
    """
    print("\n" + "="*70)
    print(" [테스트 3] 사업주훈련 훈련과정 API (고용24 / HRD-Net)")
    print("="*70)

    auth_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY")
    print(f"* 인증키 로드 상태: {mask_key(auth_key)}")

    endpoint = "https://www.hrd.go.kr/jsp/HRDP/HRDPO00/HRDPOA60/HRDPOA60_1.jsp"
    
    params = {
        "authKey": auth_key,
        "returnType": "XML",
        "outType": "1",
        "pageNum": "1",
        "pageSize": "5",
        "srchTraStDt": "20250101",
        "srchTraEndDt": "20250630",
        "srchTraGbn": "02"  # 사업주 훈련 구분 코드
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    result = {
        "api_name": "사업주훈련 훈련과정 (HRD-Net)",
        "endpoint": endpoint,
        "status": "미확인",
        "http_code": None,
        "record_count": 0,
        "fields": [],
        "error_message": None
    }

    if not auth_key:
        result["status"] = "실패 (인증키 누락)"
        print("[-] .env 파일에 HRD_EMPLOYER_TRAINING_API_KEY가 없습니다.")
        return result

    try:
        resp_check = requests.get(endpoint, params=params, headers=headers, timeout=10, allow_redirects=False)
        result["http_code"] = resp_check.status_code
        print(f"* 최초 요청 HTTP 코드: {resp_check.status_code}")

        if resp_check.status_code in (301, 302):
            redirect_url = resp_check.headers.get("Location")
            print(f"[-] 도메인 이전 감지: {endpoint} -> {redirect_url} 로 리다이렉트됨.")
            result["status"] = f"연동 실패 (도메인 이전 301 리다이렉트 -> {redirect_url})"
            result["error_message"] = "구 엔드포인트 폐기됨. 공공데이터포털 또는 고용24 최신 오픈API 엔드포인트로 갱신 필요."
            return result

        response = requests.get(endpoint, params=params, headers=headers, timeout=10)
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            result["status"] = "연동 실패 (HTML 웹페이지 반환 - API 엔드포인트 비활성)"
            result["error_message"] = "API 응답(XML/JSON) 대신 고용24 포털 HTML 페이지가 반환됨."
            print("[-] 연동 실패: 데이터 포맷(XML)이 아닌 HTML 웹페이지가 반환되었습니다.")
            return result

    except Exception as e:
        result["status"] = "실패 (네트워크 오류)"
        result["error_message"] = str(e)
        print(f"[-] 요청 실패: {e}")

    return result


if __name__ == "__main__":
    print("="*70)
    print(" [수도권 직무교육 프로젝트] 3대 교육과정 API 연동 실측 테스트 실행")
    print(" (원칙: 인증키 비노출, 실제 응답 데이터 검증 전 연동 성공 판단 금지)")
    print("="*70)

    ncs_res = test_ncs_course_api()
    kmbc_res = test_kmbc_training_api()
    emp_res = test_employer_training_api()

    print("\n" + "="*70)
    print(" [최종 테스트 요약 결과]")
    print("="*70)
    for r in [ncs_res, kmbc_res, emp_res]:
        print(f"1. API명: {r['api_name']}")
        print(f"   - 엔드포인트: {r['endpoint']}")
        print(f"   - HTTP 상태: {r['http_code']}")
        print(f"   - 판정 결과: {r['status']}")
        if r.get("record_count"):
            print(f"   - 수신 건수: {r['record_count']}건")
        if r.get("sample_item"):
            print(f"   - 샘플 데이터: {r['sample_item']}")
        if r.get("error_message"):
            print(f"   - 오류/원인: {r['error_message']}")
        print("-" * 50)
