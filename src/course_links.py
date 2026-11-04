"""
강좌 상세 링크를 화면·평가표에 내보낼 때 쓰는 보정 함수. 원본 데이터의 URL은 바꾸지 않는다.

GSEEK(경기도 평생학습포털) 과정 링크는 데이터에 `.../user/course/online/view?s_sbjct_sn=번호` 형태로 들어 있다.
이 주소는 과정 목록 페이지로 넘어가서 평가자·고객이 과정 내용을 볼 수 없었다 ('판단 불가'의 주원인).
`s_sbjct_cycl_sn=1`을 붙이면 같은 과정의 상세 페이지로 넘어간다.
확인: 다른 PC에서 5개 과정의 페이지 제목을 데이터 제목과 비교해 모두 일치(scripts/suggest_gseek_url_update.py),
사용자가 브라우저로 s_sbjct_sn=5040('해결중심 상담기법')을 직접 열어 확인 (2026-11-04).
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

GSEEK_HOST = "www.gseek.kr"
GSEEK_VIEW_PATH = "/user/course/online/view"


def detail_url(url):
    """상세 페이지로 바로 가는 링크를 돌려준다. GSEEK 과정 링크에만 s_sbjct_cycl_sn=1을 붙이고,
    이미 붙어 있거나 다른 기관 링크·빈 값이면 그대로 돌려준다 (여러 번 적용해도 결과가 같다)."""
    if not isinstance(url, str) or not url:
        return url
    parts = urlsplit(url)
    if parts.netloc != GSEEK_HOST or parts.path != GSEEK_VIEW_PATH:
        return url
    query = parse_qsl(parts.query, keep_blank_values=True)
    keys = {k for k, _ in query}
    if "s_sbjct_sn" not in keys or "s_sbjct_cycl_sn" in keys:
        return url
    return urlunsplit(parts._replace(query=urlencode(query + [("s_sbjct_cycl_sn", "1")])))
