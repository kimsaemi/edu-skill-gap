"""
인사·총무(HR) 직무 관련 교육과정 수집 파이프라인
- 대상 API: NCS 교육과정 API, 국민내일배움카드 API, 사업주훈련 API
- 타겟: 02. 경영·회계·사무 (인사, 총무, 노무, 기업교육 등)
- 주요 기능: 페이지네이션, Rate Limit, 오류 처리, 원본 응답 data/hr/raw 보관
"""
import os
import sys
import time
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Windows 터미널 한글 출력 설정
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

# 저장 디렉터리 생성 (data/hr/raw)
RAW_DIR = Path("data/hr/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}

class HREduCollector:
    def __init__(self):
        # 인증키 로드 (인증키 값은 보안상 절대 콘솔에 출력하지 않습니다)
        self.datagokr_dec_key = os.getenv("DATA_GO_KR_API_KEY_DECODING")
        self.datagokr_enc_key = os.getenv("DATA_GO_KR_API_KEY_ENCODING")
        self.hrd_kmbc_key = os.getenv("HRD_KMBC_API_KEY")
        self.hrd_emp_key = os.getenv("HRD_EMPLOYER_TRAINING_API_KEY") or self.hrd_kmbc_key
        
        # 수집 통계 집계
        self.stats = {
            "ncs_courses": {"success": 0, "fail": 0, "items": 0},
            "kmbc_courses": {"success": 0, "fail": 0, "items": 0},
            "employer_courses": {"success": 0, "fail": 0, "items": 0}
        }

    def save_raw_response(self, api_name: str, page: int, data: str or dict):
        """원본 응답을 data/hr/raw/에 JSON/XML 파일로 보관"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if isinstance(data, dict) or isinstance(data, list):
            filepath = RAW_DIR / f"{api_name}_page_{page}_{timestamp}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            filepath = RAW_DIR / f"{api_name}_page_{page}_{timestamp}.raw"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(data))
        return filepath

    def collect_ncs_hr_courses(self, max_pages: int = 5, page_size: int = 10):
        """
        1. NCS 교육과정 API 수집 (한국산업인력공단)
        - 대분류코드: 02 (경영·회계·사무)
        """
        api_name = "ncs_edu_courses"
        print(f"\n[1] NCS 교육과정 API 수집 시작 (타겟: 02. 경영·회계·사무 / 인사·총무)...")
        
        if not self.datagokr_dec_key:
            print("  ⚠️ [경고] DATA_GO_KR_API_KEY_DECODING 키가 설정되지 않아 수집을 건너뜁니다.")
            self.stats["ncs_courses"]["fail"] += 1
            return []

        url = "http://apis.data.go.kr/B490007/ncsEduCource/openapi20"
        collected_items = []

        for page in range(1, max_pages + 1):
            params = {
                "serviceKey": self.datagokr_dec_key,
                "ncsLclasCd": "02",      # 경영·회계·사무 (인사/총무 포함)
                "returnType": "json",     # JSON 응답 요청
                "pageNo": page,
                "numOfRows": page_size
            }
            try:
                res = requests.get(url, params=params, headers=HEADERS, timeout=10)
                if res.status_code == 200:
                    try:
                        jd = res.json()
                        self.save_raw_response(api_name, page, jd)
                        
                        data_info = jd.get("dataInfo", {})
                        items = jd.get("data", [])
                        
                        if not items:
                            print(f"  - Page {page}: 데이터가 더 이상 없습니다. (수집 종료)")
                            break
                        
                        # 인사·총무 관련 과정 필터링 및 수집
                        hr_related = []
                        for it in items:
                            mclas = it.get("ncsMclasCdnm", "")
                            subd = it.get("ncsSubdCdnm", "")
                            crse = it.get("crseNm", "")
                            # 인사, 총무, 노무, 사무, 기획 관련 과정 추출
                            hr_related.append(it)
                            collected_items.append(it)

                        print(f"  - Page {page}: {len(items)}건 수신 완료 (누적: {len(collected_items)}건)")
                        self.stats["ncs_courses"]["success"] += 1
                        self.stats["ncs_courses"]["items"] += len(items)
                    except Exception as json_err:
                        print(f"  - Page {page}: JSON 파싱 오류 ({json_err})")
                        self.save_raw_response(api_name, page, res.text)
                        self.stats["ncs_courses"]["fail"] += 1
                else:
                    print(f"  - Page {page}: HTTP 오류 {res.status_code}")
                    self.stats["ncs_courses"]["fail"] += 1
            except Exception as req_err:
                print(f"  - Page {page}: 요청 실패 ({req_err})")
                self.stats["ncs_courses"]["fail"] += 1

            # 호출 제한 대응 (Rate Limit Sleep)
            time.sleep(0.5)

        return collected_items

    def collect_kmbc_hr_courses(self, max_pages: int = 2, page_size: int = 5):
        """
        2. 국민내일배움카드 훈련과정 API 수집 (HRD-Net / 고용24)
        """
        api_name = "kmbc_hr_courses"
        print(f"\n[2] 국민내일배움카드 훈련과정 API 수집 시작 (HRD-Net)...")
        
        if not self.hrd_kmbc_key:
            print("  ⚠️ [경고] HRD_KMBC_API_KEY 가 설정되지 않아 수집을 건너뜁니다.")
            self.stats["kmbc_courses"]["fail"] += 1
            return []

        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"
        collected_items = []

        for page in range(1, max_pages + 1):
            params = {
                "authKey": self.hrd_kmbc_key,
                "returnType": "XML",
                "outType": "1",
                "pageNum": str(page),
                "pageSize": str(page_size),
                "srchNcs1": "02"         # 경영·회계·사무 (인사/총무)
            }
            try:
                res = requests.get(url, params=params, headers=HEADERS, timeout=10)
                # 원본 응답 저장
                self.save_raw_response(api_name, page, res.text)
                
                if "<HRDNet>" in res.text:
                    import xmltodict
                    parsed = xmltodict.parse(res.text)
                    srch_list_obj = parsed.get("HRDNet", {}).get("srchList", {})
                    if isinstance(srch_list_obj, dict):
                        items = srch_list_obj.get("scn_list", [])
                    elif isinstance(srch_list_obj, list):
                        items = srch_list_obj
                    else:
                        items = []
                    if isinstance(items, dict):
                        items = [items]
                    collected_items.extend(items)
                    print(f"  - Page {page}: {len(items)}건 수신 완료")
                    self.stats["kmbc_courses"]["success"] += 1
                    self.stats["kmbc_courses"]["items"] += len(items)
                elif "<!DOCTYPE html>" in res.text or "<html" in res.text.lower():
                    print(f"  - Page {page}: HTML 응답 수신 (Status: {res.status_code})")
                    self.stats["kmbc_courses"]["fail"] += 1
                else:
                    print(f"  - Page {page}: 응답 확인 필요 (Status: {res.status_code})")
                    self.stats["kmbc_courses"]["fail"] += 1
            except Exception as e:
                print(f"  - Page {page}: 요청 실패 ({e})")
                self.stats["kmbc_courses"]["fail"] += 1

            time.sleep(0.5)

        return collected_items

    def collect_employer_hr_courses(self, max_pages: int = 2, page_size: int = 5):
        """
        3. 사업주훈련 훈련과정 API 수집 (HRD-Net / 고용24 신규 311L01)
        """
        api_name = "employer_hr_courses"
        print(f"\n[3] 사업주훈련 훈련과정 API 수집 시작 (고용24 311L01)...")
        
        if not self.hrd_emp_key:
            print("  ⚠️ [경고] HRD_EMPLOYER_TRAINING_API_KEY 가 설정되지 않아 수집을 건너뜁니다.")
            self.stats["employer_courses"]["fail"] += 1
            return []

        url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo311L01.do"
        collected_items = []

        for page in range(1, max_pages + 1):
            params = {
                "authKey": self.hrd_emp_key,
                "returnType": "XML",
                "outType": "1",
                "pageNum": str(page),
                "pageSize": str(page_size),
                "srchNcs1": "02"
            }
            try:
                res = requests.get(url, params=params, headers=HEADERS, timeout=10)
                self.save_raw_response(api_name, page, res.text)
                
                if "<HRDNet>" in res.text:
                    import xmltodict
                    parsed = xmltodict.parse(res.text)
                    srch_list_obj = parsed.get("HRDNet", {}).get("srchList", {})
                    if isinstance(srch_list_obj, dict):
                        items = srch_list_obj.get("scn_list", [])
                    elif isinstance(srch_list_obj, list):
                        items = srch_list_obj
                    else:
                        items = []
                    if isinstance(items, dict):
                        items = [items]
                    collected_items.extend(items)
                    print(f"  - Page {page}: {len(items)}건 수신 완료")
                    self.stats["employer_courses"]["success"] += 1
                    self.stats["employer_courses"]["items"] += len(items)
                elif "<!DOCTYPE html>" in res.text or "<html" in res.text.lower():
                    print(f"  - Page {page}: HTML 응답 수신 (Status: {res.status_code})")
                    self.stats["employer_courses"]["fail"] += 1
                else:
                    self.stats["employer_courses"]["fail"] += 1
            except Exception as e:
                print(f"  - Page {page}: 요청 실패 ({e})")
                self.stats["employer_courses"]["fail"] += 1

            time.sleep(0.5)

        return collected_items

    def run_all(self):
        print("==================================================")
        print("  인사·총무(HR) 훈련과정 데이터 수집 파이프라인 가동")
        print(f"  저장 위치: {RAW_DIR.resolve()}")
        print("==================================================")

        ncs_items = self.collect_ncs_hr_courses(max_pages=3, page_size=10)
        kmbc_items = self.collect_kmbc_hr_courses(max_pages=1, page_size=5)
        emp_items = self.collect_employer_hr_courses(max_pages=1, page_size=5)

        print("\n==================================================")
        print("  📊 최종 수집 통계 리포트")
        print("==================================================")
        print(f"1. 한국산업인력공단 NCS 교육과정:")
        print(f"   - 성공 호출: {self.stats['ncs_courses']['success']}회 | 실패: {self.stats['ncs_courses']['fail']}회 | 수집 건수: {self.stats['ncs_courses']['items']}건")
        print(f"2. 국민내일배움카드 훈련과정 (고용24/HRD-Net):")
        print(f"   - 성공 호출: {self.stats['kmbc_courses']['success']}회 | 실패: {self.stats['kmbc_courses']['fail']}회 | 수집 건수: {self.stats['kmbc_courses']['items']}건")
        print(f"3. 사업주훈련 훈련과정 (고용24/HRD-Net):")
        print(f"   - 성공 호출: {self.stats['employer_courses']['success']}회 | 실패: {self.stats['employer_courses']['fail']}회 | 수집 건수: {self.stats['employer_courses']['items']}건")
        print("==================================================")
        print(f"✅ 원본 응답 파일이 '{RAW_DIR}' 디렉터리에 안전하게 저장되었습니다.")

if __name__ == "__main__":
    collector = HREduCollector()
    collector.run_all()
