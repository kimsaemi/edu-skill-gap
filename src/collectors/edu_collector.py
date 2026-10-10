"""
API 데이터 수집 기본 모듈
한국산업인력공단 NCS 교육과정, 원격훈련모니터링 통계, K-MOOC API 연동 인터페이스
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class EduDataCollector:
    def __init__(self):
        self.decoding_key = os.getenv("DATA_GO_KR_API_KEY_DECODING")
        self.encoding_key = os.getenv("DATA_GO_KR_API_KEY_ENCODING")
        
        # 고용24 / HRD-Net / 워크넷 인증키
        self.hrd_kmbc_key = os.getenv("HRD_KMBC_API_KEY")
        self.hrd_kmbc_detail_key = os.getenv("HRD_KMBC_DETAIL_API_KEY") or self.hrd_kmbc_key
        self.hrd_kmbc_sched_key = os.getenv("HRD_KMBC_SCHED_API_KEY") or self.hrd_kmbc_key
        
        self.hrd_employer_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY")
        self.hrd_employer_detail_key = os.getenv("HRD_EMPLOYER_DETAIL_API_KEY") or self.hrd_employer_key
        self.hrd_employer_sched_key = os.getenv("HRD_EMPLOYER_SCHED_API_KEY") or self.hrd_employer_key
        
        self.hrd_work_study_key = os.getenv("HRD_WORK_STUDY_API_KEY")
        self.worknet_job_key = os.getenv("WORKNET_JOB_INFO_API_KEY")
        self.worknet_major_key = os.getenv("WORKNET_MAJOR_INFO_API_KEY")
        self.worknet_occupation_key = os.getenv("WORKNET_OCCUPATION_INFO_API_KEY")
        
    def fetch_ncs_courses(self, ncs_lclas_cd="02", params=None):
        """
        한국산업인력공단 NCS 교육과정 API 호출
        - ncs_lclas_cd: NCS 대분류코드 2자리 (필수 파라미터, 예: '01' 사업관리, '02' 경영·회계·사무 등)
        - 문자열(str) 형식 보존 필수
        """
        url = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
        default_params = {
            "serviceKey": self.decoding_key,
            "pageNo": 1,
            "numOfRows": 20,
            "returnType": "json",
            "ncsLclasCd": str(ncs_lclas_cd).zfill(2)
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            if res.status_code != 200:
                return {"error": f"HTTP {res.status_code}", "raw": res.text[:200]}
            data = res.json()
            return data
        except Exception as e:
            return {"error": str(e)}

    def fetch_ncs_job_base(self, endpoint_url=None, params=None):
        """한국산업인력공단 NCS 직업기초능력 API 호출"""
        url = endpoint_url or "https://apis.data.go.kr/B490007/ncsJobBase"
        default_params = {
            "serviceKey": os.getenv("NCS_JOB_BASE_API_KEY_DECODING") or self.decoding_key,
            "pageNo": 1,
            "numOfRows": 20
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_ncs_standard(self, endpoint_url=None, params=None):
        """한국산업인력공단 NCS 기준정보 조회 API 호출"""
        url = endpoint_url or "https://apis.data.go.kr/B490007/hrdkapi"
        default_params = {
            "serviceKey": os.getenv("NCS_STANDARD_API_KEY_DECODING") or self.decoding_key,
            "pageNo": 1,
            "numOfRows": 20
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_ncs_position_link(self, endpoint_url=None, params=None):
        """한국산업인력공단 NCS 직급연계 정보 API 호출"""
        url = endpoint_url or "https://apis.data.go.kr/B490007/ncsPositionLink"
        default_params = {
            "serviceKey": os.getenv("NCS_POSITION_LINK_API_KEY_DECODING") or self.decoding_key,
            "pageNo": 1,
            "numOfRows": 20
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_remote_training_stats(self, endpoint_url=None, params=None):
        """원격훈련 모니터링시스템 통계 API 호출"""
        url = endpoint_url or "http://apis.data.go.kr/B490007/emonService/ipStatService/ipStatInfo"
        default_params = {
            "serviceKey": self.decoding_key,
            "pageNo": 1,
            "numOfRows": 20
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_kmooc_courses(self, endpoint_url, params=None):
        """K-MOOC 강좌정보 API 호출"""
        default_params = {
            "serviceKey": self.decoding_key,
            "pageNo": 1,
            "numOfRows": 20
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(endpoint_url, params=default_params, timeout=10)
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_seoul_lifelong_courses(self, service_name="SeoulLifelongEduProgDesc", start_idx=1, end_idx=20):
        """서울시 평생학습포털 강좌정보 API 호출 (서울 열린데이터광장)"""
        seoul_key = os.getenv("SEOUL_LIFELONG_API_KEY")
        if not seoul_key:
            return {"error": "SEOUL_LIFELONG_API_KEY not found in .env"}
        url = f"http://openapi.seoul.go.kr:8088/{seoul_key}/json/{service_name}/{start_idx}/{end_idx}/"
        try:
            res = requests.get(url, timeout=10)
            return res.json()
        except Exception as e:
            return {"error": str(e)}

    def fetch_gyeonggi_data(self, service_name, params=None):
        """경기데이터드림 API 호출 (data.gg.go.kr)"""
        gg_key = os.getenv("GG_DATA_DREAM_API_KEY")
        if not gg_key:
            return {"error": "GG_DATA_DREAM_API_KEY not found in .env"}
        url = f"https://openapi.gg.go.kr/{service_name}"
        default_params = {
            "KEY": gg_key,
            "Type": "json",
            "pIndex": 1,
            "pSize": 20
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            return res.json()
        except Exception as e:
            return {"error": str(e)}

    def fetch_hrd_courses(self, auth_key, params=None, endpoint_url=None):
        """고용24 (HRD-Net) 훈련과정 공통 API 호출 (XML 응답 반환)"""
        if not auth_key:
            return {"error": "API Key is required"}
        # 고용24 공식 엔드포인트 기본값 (국민내일배움카드)
        url = endpoint_url or "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
        default_params = {
            "authKey": auth_key,
            "returnType": "XML",
            "outType": "1",
            "pageNum": "1",
            "pageSize": "20",
            "srchTraStDt": "20250101",
            "srchTraEndDt": "20251231",
            "sort": "DESC",
            "sortCol": "TR_ST_DT"
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(url, params=default_params, timeout=10)
            if "text/html" in res.headers.get("Content-Type", ""):
                return {
                    "error": "INVALID_CONTENT_TYPE",
                    "status_code": res.status_code,
                    "message": "XML 데이터가 아닌 웹페이지 HTML이 반환되었습니다. 엔드포인트 주소를 확인하세요."
                }
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_kmbc_courses(self, params=None):
        """국민내일배움카드 훈련과정 API 호출 (고용24 공식 엔드포인트)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
        return self.fetch_hrd_courses(self.hrd_kmbc_key, params=params, endpoint_url=url)

    def fetch_employer_training_courses(self, params=None):
        """사업주훈련 훈련과정 API 호출 (고용24 공식 엔드포인트)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do"
        return self.fetch_hrd_courses(self.hrd_employer_key, params=params, endpoint_url=url)

    def fetch_work_study_courses(self, params=None):
        """일학습병행 훈련과정 API 호출 (고용24 공식 엔드포인트)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo313L01.do"
        return self.fetch_hrd_courses(self.hrd_work_study_key, params=params, endpoint_url=url)

    def fetch_hrd_course_detail(self, auth_key, trpr_id, trpr_degr, endpoint_url=None):
        """고용24 (HRD-Net) 훈련과정 상세정보 API 호출 및 정밀 진단"""
        if not auth_key:
            return {
                "status": "FAILED",
                "error_type": "AUTH_KEY_MISSING",
                "message": "인증키가 설정되지 않았습니다 (.env 파일 확인 필요)."
            }
        if not trpr_id or not trpr_degr:
            return {
                "status": "FAILED",
                "error_type": "PARAMS_MISSING",
                "message": "훈련과정 ID(srchTrprId)와 회차(srchTrprDegr)가 필요합니다."
            }

        url = endpoint_url or "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L02.do"
        params = {
            "authKey": auth_key,
            "returnType": "XML",
            "outType": "1",
            "srchTrprId": str(trpr_id),
            "srchTrprDegr": str(trpr_degr)
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            status_code = res.status_code
            content_type = res.headers.get("Content-Type", "")
            raw_text = res.text.strip()

            # 1. HTTP 404
            if status_code == 404:
                return {
                    "status": "FAILED",
                    "http_code": 404,
                    "error_type": "404_NOT_FOUND",
                    "url": url,
                    "message": "요청한 상세조회 엔드포인트 URL이 고용24 서버에 존재하지 않습니다."
                }

            # 2. HTML 에러/리다이렉트 (INVALID_CONTENT_TYPE)
            if "text/html" in content_type or "<!DOCTYPE html>" in raw_text or "<html" in raw_text:
                return {
                    "status": "FAILED",
                    "http_code": status_code,
                    "error_type": "HTML_EXCEPTION_REDIRECT",
                    "url": url,
                    "message": "XML 대신 고용24 시스템 예외 HTML 페이지가 반환되었습니다 (서비스 미지원 또는 세션/방화벽 제약)."
                }

            # 3. XML 내 <error> 태그
            if "<error>" in raw_text:
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(raw_text)
                    err_msg = root.findtext("error") or "인증/권한 오류"
                except Exception:
                    err_msg = "XML 에러 태그 감지"
                return {
                    "status": "FAILED",
                    "http_code": status_code,
                    "error_type": "AUTH_PERMISSION_ERROR",
                    "url": url,
                    "message": f"고용24 API 인증/권한 오류: '{err_msg}' (목록조회 전용 키로 상세조회 서비스 미인가)"
                }

            # 4. XML 정상 수신 및 필드 파싱
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw_text)
            
            # 공식 XML 응답에서 실제 필드 추출
            parsed_data = {
                "training_goal": root.findtext(".//trprTarget") or root.findtext(".//traGoal") or "",
                "course_contents": root.findtext(".//contents") or root.findtext(".//trprChapList") or "",
                "total_hours": root.findtext(".//totTraTime") or root.findtext(".//traTime") or "",
                "total_days": root.findtext(".//totTraDays") or root.findtext(".//traDays") or "",
                "raw_fields": [elem.tag for elem in root.iter()][:20]
            }

            return {
                "status": "SUCCESS",
                "http_code": status_code,
                "error_type": None,
                "url": url,
                "data": parsed_data,
                "raw_xml": raw_text
            }

        except Exception as e:
            return {
                "status": "FAILED",
                "http_code": None,
                "error_type": "NETWORK_EXCEPTION",
                "message": f"API 호출 중 통신 예외 발생: {str(e)}"
            }

    def fetch_kmbc_course_detail(self, trpr_id, trpr_degr):
        """국민내일배움카드 훈련과정 상세정보(과정/기관) API 호출 (310L02.do)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L02.do"
        return self.fetch_hrd_course_detail(self.hrd_kmbc_detail_key, trpr_id, trpr_degr, endpoint_url=url)

    def fetch_kmbc_schedule(self, trpr_id, trpr_degr):
        """국민내일배움카드 훈련일정 API 호출 (310L03.do)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L03.do"
        return self.fetch_hrd_schedule(self.hrd_kmbc_sched_key, trpr_id, trpr_degr, endpoint_url=url)

    def fetch_employer_course_detail(self, trpr_id, trpr_degr):
        """사업주훈련 훈련과정 상세정보(과정/기관) API 호출 (311D01.do)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311D01.do"
        return self.fetch_hrd_course_detail(self.hrd_employer_detail_key, trpr_id, trpr_degr, endpoint_url=url)

    def fetch_employer_schedule(self, trpr_id, trpr_degr):
        """사업주훈련 훈련일정 API 호출 (311D02.do)"""
        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311D02.do"
        return self.fetch_hrd_schedule(self.hrd_employer_sched_key, trpr_id, trpr_degr, endpoint_url=url)

    def fetch_hrd_schedule(self, auth_key, trpr_id, trpr_degr, endpoint_url=None):
        """고용24 (HRD-Net) 훈련일정 API 호출 및 정밀 진단"""
        if not auth_key:
            return {
                "status": "FAILED",
                "error_type": "AUTH_KEY_MISSING",
                "message": "인증키가 설정되지 않았습니다 (.env 파일 확인 필요)."
            }
        if not trpr_id or not trpr_degr:
            return {
                "status": "FAILED",
                "error_type": "PARAMS_MISSING",
                "message": "훈련과정 ID(srchTrprId)와 회차(srchTrprDegr)가 필요합니다."
            }

        url = endpoint_url or "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L03.do"
        params = {
            "authKey": auth_key,
            "returnType": "XML",
            "outType": "1",
            "srchTrprId": str(trpr_id),
            "srchTrprDegr": str(trpr_degr)
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            status_code = res.status_code
            content_type = res.headers.get("Content-Type", "")
            raw_text = res.text.strip()

            # 1. HTTP 404
            if status_code == 404:
                return {
                    "status": "FAILED",
                    "http_code": 404,
                    "error_type": "404_NOT_FOUND",
                    "url": url,
                    "message": "요청한 훈련일정 엔드포인트 URL이 고용24 서버에 존재하지 않습니다."
                }

            # 2. HTML 에러/리다이렉트
            if "text/html" in content_type or "<!DOCTYPE html>" in raw_text or "<html" in raw_text:
                return {
                    "status": "FAILED",
                    "http_code": status_code,
                    "error_type": "HTML_EXCEPTION_REDIRECT",
                    "url": url,
                    "message": "XML 대신 고용24 시스템 예외 HTML 페이지가 반환되었습니다 (서비스 미지원 또는 세션/방화벽 제약)."
                }

            # 3. XML 내 <error> 태그
            if "<error>" in raw_text:
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(raw_text)
                    err_msg = root.findtext("error") or "인증/권한 오류"
                except Exception:
                    err_msg = "XML 에러 태그 감지"
                return {
                    "status": "FAILED",
                    "http_code": status_code,
                    "error_type": "AUTH_PERMISSION_ERROR",
                    "url": url,
                    "message": f"고용24 API 인증/권한 오류: '{err_msg}' (훈련일정 서비스 신청 및 승인 필요)"
                }

            # 4. XML 정상 수신 및 일정 파싱
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw_text)

            schedules = []
            target_items = root.findall(".//scn_list") or root.findall(".//scnList") or root.findall(".//srchList") or root.findall(".//item")
            for item in target_items:
                schedules.append({
                    "start_dt": item.findtext("trStaDt") or item.findtext("traStartDate") or item.findtext("trprStDt") or "",
                    "end_dt": item.findtext("trEndDt") or item.findtext("traEndDate") or item.findtext("trprEndDt") or "",
                    "degr": item.findtext("trprDegr") or "",
                    "course_name": item.findtext("trprNm") or "",
                    "total_cost": item.findtext("totTrco") or "",
                    "capacity": item.findtext("totFxnum") or "",
                    "tra_time": item.findtext("traTime") or item.findtext("totTraTime") or "",
                    "inst_id": item.findtext("instIno") or ""
                })

            parsed_data = {
                "schedule_count": len(schedules),
                "schedules": schedules,
                "raw_fields": [elem.tag for elem in root.iter()][:20]
            }

            return {
                "status": "SUCCESS",
                "http_code": status_code,
                "error_type": None,
                "url": url,
                "data": parsed_data,
                "raw_xml": raw_text
            }

        except Exception as e:
            return {
                "status": "FAILED",
                "http_code": None,
                "error_type": "NETWORK_EXCEPTION",
                "message": f"API 호출 중 통신 예외 발생: {str(e)}"
            }

    def fetch_worknet_info(self, auth_key, endpoint_url, params=None):
        """워크넷 (직무/학과/직업 등) API 호출"""
        if not auth_key:
            return {"error": "API Key is required"}
        default_params = {
            "authKey": auth_key,
            "returnType": "XML"
        }
        if params:
            default_params.update(params)
        try:
            res = requests.get(endpoint_url, params=default_params, timeout=10)
            return res.text
        except Exception as e:
            return {"error": str(e)}

    def fetch_job_info(self, endpoint_url, params=None):
        """직무정보 API 호출"""
        return self.fetch_worknet_info(self.worknet_job_key, endpoint_url, params=params)

    def fetch_major_info(self, endpoint_url, params=None):
        """학과정보 API 호출"""
        return self.fetch_worknet_info(self.worknet_major_key, endpoint_url, params=params)

    def fetch_occupation_info(self, endpoint_url, params=None):
        """직업정보 API 호출"""
        return self.fetch_worknet_info(self.worknet_occupation_key, endpoint_url, params=params)

if __name__ == "__main__":
    collector = EduDataCollector()
    print("Testing NCS API call...")
    print(collector.fetch_ncs_courses())
    print("\nTesting Seoul Lifelong API call...")
    print(collector.fetch_seoul_lifelong_courses())


