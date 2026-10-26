"""
발표용 웹 대시보드 빌드
파일명: scripts/build_presentation.py

presentation/src/template.html + presentation/src/data.json + presentation/fonts/*.woff2 를 묶어
인터넷 없이도 열리는 단일 파일 presentation/index.html 을 만듭니다. (Vercel 등 정적 호스팅에 그대로 배포 가능)

사용법:
  python scripts/build_presentation_data.py   # 데이터가 바뀌었을 때 먼저 실행
  python scripts/build_presentation.py
  python scripts/build_presentation.py --body-only OUT.html   # <html>/<head> 없이 본문만 (미리보기 게시용)
"""

import argparse
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "presentation" / "src"
FONTS = ROOT / "presentation" / "fonts"
OUT = ROOT / "presentation" / "index.html"

FONT_FACES = [
    ("Galmuri11", "Galmuri11.woff2", "normal"),
    ("Galmuri11 Bold", "Galmuri11-Bold.woff2", "normal"),
]


def font_css() -> str:
    rules = []
    for family, file, weight in FONT_FACES:
        b64 = base64.b64encode((FONTS / file).read_bytes()).decode("ascii")
        rules.append(
            f'@font-face{{font-family:"{family}";src:url(data:font/woff2;base64,{b64}) format("woff2");'
            f"font-weight:{weight};font-style:normal;font-display:swap}}"
        )
    return "\n".join(rules)


def build_body() -> str:
    template = (SRC / "template.html").read_text(encoding="utf-8")
    data = (SRC / "data.json").read_text(encoding="utf-8")
    # </script> 가 데이터 안에 있으면 스크립트가 끊기므로 이스케이프
    data = data.replace("</", "<\\/")
    assert "/*__FONTS__*/" in template and "/*__DATA__*/" in template, "템플릿 자리표시자가 없습니다."
    return template.replace("/*__FONTS__*/", font_css()).replace("/*__DATA__*/", data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-only", type=Path, help="본문만 담은 파일을 이 경로에 추가로 저장")
    args = parser.parse_args()

    body = build_body()
    page = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    OUT.write_text(page, encoding="utf-8")
    print(f"저장: {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f}KB)")
    if args.body_only:
        args.body_only.write_text(body, encoding="utf-8")
        print(f"본문만 저장: {args.body_only} ({args.body_only.stat().st_size / 1024:.0f}KB)")


if __name__ == "__main__":
    main()
