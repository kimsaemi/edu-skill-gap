# -*- coding: utf-8 -*-
"""
[제안용 스크립트 - 실제 적용 금지]
GSEEK 과정의 레거시 URL(s_sbjct_sn만 있는 형태)을
공개 상세 페이지로 정상 리다이렉트되는 형태(&s_sbjct_cycl_sn=1 추가)로 변환하는 제안 스크립트.

배경:
  - 기존: https://www.gseek.kr/user/course/online/view?s_sbjct_sn=57110
    -> GSEEK 서버에서 차수 파라미터 누락으로 목록 페이지(/user/course/online)로 리다이렉트되어 상세 확인 불가.
  - 개선안: https://www.gseek.kr/user/course/online/view?s_sbjct_sn=57110&s_sbjct_cycl_sn=1
    -> GSEEK 서버가 최신 시맨틱 상세 URL(/course/online/life/...)로 자동 302 리다이렉트하여 로그인 없이 상세 조회 가능.
"""

import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

def fix_gseek_url(url: str) -> str:
    if not isinstance(url, str):
        return url
    if "gseek.kr" in url and "s_sbjct_sn=" in url and "s_sbjct_cycl_sn=" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}s_sbjct_cycl_sn=1"
    return url

def main():
    print("=== GSEEK URL 개선 제안 시뮬레이션 ===")
    sample_urls = [
        "https://www.gseek.kr/user/course/online/view?s_sbjct_sn=57110",
        "https://www.gseek.kr/user/course/online/view?s_sbjct_sn=57124",
        "https://www.gseek.kr/user/course/online/view?s_sbjct_sn=5045",
    ]
    for u in sample_urls:
        print(f"기존: {u}\n개선: {fix_gseek_url(u)}\n")
    print("주의: 이 스크립트는 제안용이며 본 프로젝트 규칙에 따라 데이터 원본에는 적용하지 않습니다.")

if __name__ == "__main__":
    main()

