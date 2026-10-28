"""
분야(9개 인사 분야) ↔ 과정 연결 검수 시트를 만든다.

고객용 화면(scripts/build_customer_platform_data.py)은 과정명 키워드로 과정을 9개 분야에 연결한다.
이 연결은 사람이 검수하지 않았으므로, 팀원이 과정마다 판정을 입력할 수 있는 엑셀 시트를 만든다.

출력: data/hr/output/recommendation/domain_mapping_review_sheet.xlsx
  - 안내    : 입력 방법, 입력 예시
  - 검수    : 과정 1행 (확정 과정 212개, 같은 과정명 묶음). 노란 칸만 입력
  - 요약    : 진행률·판정 분포·분야별 일치율 (수식으로 자동 계산)
  - 분야 기준: 9개 분야와 연결 키워드

이미 입력된 시트를 덮어쓰지 않도록, 파일이 있으면 멈춘다. 다시 만들려면 --force.

실행: python scripts/build_domain_mapping_review_sheet.py [--force]
"""
import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_customer_platform_data import DOMAIN_KEYWORDS, load_courses  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "hr" / "output" / "recommendation" / "domain_mapping_review_sheet.xlsx"

DOMAIN_NAMES = {
    "DOM_01": "인사전략·인력기획", "DOM_02": "조직설계·직무분석", "DOM_03": "인재채용",
    "DOM_04": "온보딩·직원경험", "DOM_05": "성과평가·목표관리", "DOM_06": "보상·급여·복리후생",
    "DOM_07": "인재육성·사내교육", "DOM_08": "조직문화·사내소통", "DOM_09": "노사관계·노무",
}
REVIEWERS = ["팀원A", "팀원B", "팀원C", "팀원D"]
RELEVANCE = ["관련", "일부 관련", "무관"]
VERDICT = ["맞음", "일부 틀림", "틀림"]

FONT = "Arial"
F_BODY = Font(name=FONT, size=10)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=14, bold=True)
F_BOLD = Font(name=FONT, size=10, bold=True)
F_LINK = Font(name=FONT, size=10, color="0563C1", underline="single")
FILL_HEAD = PatternFill("solid", fgColor="1F4E78")
FILL_INPUT = PatternFill("solid", fgColor="FFF2CC")
FILL_AUTO = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")

# 검수 시트 열 정의: (머리글, 너비, 입력칸 여부)
COLUMNS = [
    ("번호", 6, False), ("배정", 8, False), ("과정ID", 26, False), ("과정명", 44, False),
    ("기관", 20, False), ("플랫폼", 18, False), ("링크", 10, False), ("기존 역량(키워드 분류)", 20, False),
    ("자동 연결 분야", 24, False), ("연결 근거 키워드", 18, False),
    ("① 인사·총무 관련 여부", 14, True), ("② 자동 연결 분야 판정", 14, True),
    ("③ 추가할 분야", 20, True), ("④ 뺄 분야", 20, True), ("메모", 30, True),
    ("검수자", 10, True), ("검수일", 12, True),
]
COL = {name: i + 1 for i, (name, _, _) in enumerate(COLUMNS)}


def letter(name):
    return get_column_letter(COL[name])


def build_review_sheet(ws, courses):
    ws.title = "검수"
    for i, (name, width, is_input) in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=i, value=name)
        c.font, c.fill, c.border = F_HEAD, FILL_HEAD, BORDER
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[1].height = 32
    ws.cell(row=1, column=COL["② 자동 연결 분야 판정"]).comment = Comment(
        "자동 연결 분야가 비어 있으면: 정말 9개 분야 어디에도 안 맞으면 '맞음', 맞는 분야가 있으면 '틀림' + ③에 분야 입력", "검수 안내")

    for r, c in enumerate(courses, start=2):
        title_lower = c["title"].lower()
        kws = sorted({k for d in c["doms"] for k in DOMAIN_KEYWORDS[d] if k in title_lower})
        values = {
            "번호": r - 1, "배정": REVIEWERS[(r - 2) % len(REVIEWERS)], "과정ID": c["id"], "과정명": c["title"],
            "기관": c["inst"], "플랫폼": c["platform"], "링크": "열기" if c["url"] else "",
            "기존 역량(키워드 분류)": c["competency"],
            "자동 연결 분야": ", ".join(DOMAIN_NAMES[d] for d in c["doms"]) or "(없음)",
            "연결 근거 키워드": ", ".join(kws),
        }
        for name, (_, _, is_input) in zip(COL, COLUMNS):
            cell = ws.cell(row=r, column=COL[name], value=values.get(name))
            cell.font, cell.border, cell.alignment = F_BODY, BORDER, WRAP
            cell.fill = FILL_INPUT if is_input else FILL_AUTO
        if c["url"]:
            link = ws.cell(row=r, column=COL["링크"])
            link.hyperlink, link.font = c["url"], F_LINK

    last = len(courses) + 1
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{last}"

    def dropdown(options, col_name, prompt):
        dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True,
                            showErrorMessage=True, errorTitle="목록에서 고르세요", error=prompt)
        ws.add_data_validation(dv)
        dv.add(f"{letter(col_name)}2:{letter(col_name)}{last}")

    dropdown(RELEVANCE, "① 인사·총무 관련 여부", "관련 / 일부 관련 / 무관 중에서 고르세요")
    dropdown(VERDICT, "② 자동 연결 분야 판정", "맞음 / 일부 틀림 / 틀림 중에서 고르세요")
    dropdown(REVIEWERS, "검수자", "팀원A~D 중에서 고르세요")
    date_dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2026,1,1)", allow_blank=True,
                             showErrorMessage=True, error="날짜(예: 2026-10-30)를 입력하세요")
    ws.add_data_validation(date_dv)
    date_dv.add(f"{letter('검수일')}2:{letter('검수일')}{last}")
    for r in range(2, last + 1):
        ws.cell(row=r, column=COL["검수일"]).number_format = "yyyy-mm-dd"

    # 판정이 '틀림/일부 틀림'인데 ③·④가 모두 비어 있으면 빨간 글씨로 표시
    v, add, rm = letter("② 자동 연결 분야 판정"), letter("③ 추가할 분야"), letter("④ 뺄 분야")
    ws.conditional_formatting.add(
        f"{v}2:{v}{last}",
        FormulaRule(formula=[f'AND(OR({v}2="틀림",{v}2="일부 틀림"),{add}2="",{rm}2="")'],
                    font=Font(name=FONT, color="C00000", bold=True)))
    return last


def build_guide(ws):
    ws.title = "안내"
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 90
    rows = [
        ("분야–과정 연결 검수 시트", None),
        (None, None),
        ("목적", "고객용 화면은 과정명 키워드로 과정을 9개 인사 분야에 자동 연결합니다. 이 연결이 맞는지 사람이 확인합니다."),
        ("대상", "확정 과정 212개(같은 과정명은 하나로 묶음). 출처: data/hr/output/recommendation/hr_recommendation_candidates.csv"),
        ("입력할 칸", "'검수' 시트의 노란 칸만 입력합니다. 회색 칸은 자동으로 채운 정보이니 고치지 마세요."),
        ("배정", "'배정' 열에 적힌 팀원이 그 행을 검수합니다(팀원A~D가 순서대로 나눔). 필터로 내 행만 볼 수 있습니다."),
        ("① 인사·총무 관련 여부", "과정 자체가 인사·총무 업무에 관련 있는지: 관련 / 일부 관련 / 무관"),
        ("② 자동 연결 분야 판정", "'자동 연결 분야'가 맞는지: 맞음 / 일부 틀림(일부만 맞음) / 틀림. "
                             "분야가 '(없음)'인데 맞는 분야가 있으면 '틀림'으로 고르고 ③에 적습니다."),
        ("③ 추가할 분야 / ④ 뺄 분야", "'분야 기준' 시트의 분야 이름을 그대로 적습니다. 여러 개면 쉼표로 구분합니다. "
                                   "②가 틀림·일부 틀림인데 ③·④가 비어 있으면 ②가 빨간 글씨로 표시됩니다."),
        ("판단 기준", "과정명만 보고 애매하면 '링크'를 열어 과정 소개를 확인합니다. 그래도 애매하면 메모에 이유를 적습니다."),
        ("결과 확인", "'요약' 시트에서 진행률과 판정 분포, 분야별 일치율이 자동으로 계산됩니다."),
        ("주의", "고용24 과정은 2025년 회차 기준이라 링크의 회차가 끝났을 수 있습니다. 검수는 과정 내용 기준으로 합니다."),
        (None, None),
        ("입력 예시 (검수 시트 형식)", None),
    ]
    for r, (a, b) in enumerate(rows, start=1):
        ca, cb = ws.cell(row=r, column=1, value=a), ws.cell(row=r, column=2, value=b)
        ca.font, cb.font = F_BOLD, F_BODY
        ca.alignment = cb.alignment = WRAP
    ws["A1"].font = F_TITLE

    example_head = ["과정명", "자동 연결 분야", "① 관련 여부", "② 판정", "③ 추가할 분야", "④ 뺄 분야", "메모"]
    example = ["채용에서 퇴직까지 인사노무관리 핵심실무", "인재채용, 노사관계·노무", "관련", "일부 틀림",
               "보상·급여·복리후생", "", "목차에 급여·퇴직금 계산 포함(링크 확인)"]
    start = len(rows) + 1
    # 예시는 2열 표로 보여준다 (항목 / 예시 값)
    for i, (h, v) in enumerate(zip(example_head, example)):
        hc = ws.cell(row=start + i, column=1, value=h)
        vc = ws.cell(row=start + i, column=2, value=v)
        hc.font, vc.font = F_BOLD, F_BODY
        hc.fill, vc.fill = FILL_AUTO if i < 2 else FILL_INPUT, FILL_AUTO if i < 2 else FILL_INPUT
        hc.border = vc.border = BORDER


def build_domains(ws):
    ws.title = "분야 기준"
    heads = ["분야 ID", "분야 이름", "연결 키워드(과정명에 포함되면 연결)"]
    widths = [10, 22, 90]
    for i, (h, w) in enumerate(zip(heads, widths), start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font, c.fill, c.border = F_HEAD, FILL_HEAD, BORDER
        ws.column_dimensions[get_column_letter(i)].width = w
    for r, (d, kws) in enumerate(DOMAIN_KEYWORDS.items(), start=2):
        for i, v in enumerate([d, DOMAIN_NAMES[d], ", ".join(kws)], start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.font, c.border = F_BODY, BORDER


def build_summary(ws, last):
    ws.title = "요약"
    ws.column_dimensions["A"].width = 26
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 13
    rv = f"검수!${letter('① 인사·총무 관련 여부')}$2:${letter('① 인사·총무 관련 여부')}${last}"
    vd = f"검수!${letter('② 자동 연결 분야 판정')}$2:${letter('② 자동 연결 분야 판정')}${last}"
    dm = f"검수!${letter('자동 연결 분야')}$2:${letter('자동 연결 분야')}${last}"
    asg = f"검수!${letter('배정')}$2:${letter('배정')}${last}"

    def put(cell, value, font=F_BODY, fmt=None):
        ws[cell] = value
        ws[cell].font = font
        ws[cell].border = BORDER
        if fmt:
            ws[cell].number_format = fmt

    ws["A1"] = "검수 요약 (자동 계산)"
    ws["A1"].font = F_TITLE

    put("A3", "전체 과정 수", F_BOLD); put("B3", f"=COUNTA(검수!$C$2:$C${last})")
    put("A4", "판정 입력 완료", F_BOLD); put("B4", f"=COUNTA({vd})")
    put("A5", "진행률", F_BOLD); put("B5", "=IF(B3=0,0,B4/B3)", fmt="0.0%")

    put("A7", "② 판정", F_BOLD); put("B7", "건수", F_BOLD); put("C7", "비율", F_BOLD)
    for i, v in enumerate(VERDICT):
        r = 8 + i
        put(f"A{r}", v); put(f"B{r}", f'=COUNTIF({vd},A{r})'); put(f"C{r}", f"=IF($B$4=0,0,B{r}/$B$4)", fmt="0.0%")

    put("A12", "① 관련 여부", F_BOLD); put("B12", "건수", F_BOLD)
    for i, v in enumerate(RELEVANCE):
        r = 13 + i
        put(f"A{r}", v); put(f"B{r}", f'=COUNTIF({rv},A{r})')

    put("A17", "분야별", F_BOLD)
    for i, h in enumerate(["자동 연결 과정", "검수 완료", "맞음", "일치율"], start=2):
        put(f"{get_column_letter(i)}17", h, F_BOLD)
    for i, d in enumerate(DOMAIN_KEYWORDS):
        r = 18 + i
        name = DOMAIN_NAMES[d]
        put(f"A{r}", name)
        put(f"B{r}", f'=COUNTIF({dm},"*"&A{r}&"*")')
        put(f"C{r}", f'=COUNTIFS({dm},"*"&A{r}&"*",{vd},"<>")')
        put(f"D{r}", f'=COUNTIFS({dm},"*"&A{r}&"*",{vd},"맞음")')
        put(f"E{r}", f"=IF(C{r}=0,0,D{r}/C{r})", fmt="0.0%")
    r = 18 + len(DOMAIN_KEYWORDS)
    put(f"A{r}", "(없음)")
    put(f"B{r}", f'=COUNTIF({dm},"(없음)")')
    put(f"C{r}", f'=COUNTIFS({dm},"(없음)",{vd},"<>")')
    put(f"D{r}", f'=COUNTIFS({dm},"(없음)",{vd},"맞음")')
    put(f"E{r}", f"=IF(C{r}=0,0,D{r}/C{r})", fmt="0.0%")
    ws[f"A{r + 1}"] = "일치율 = 검수 완료 중 '맞음' 비율. '(없음)'의 맞음은 '9개 분야 어디에도 안 맞음'이 맞다는 뜻."
    ws[f"A{r + 1}"].font = Font(name=FONT, size=9, italic=True)

    base = r + 3
    put(f"A{base}", "팀원별", F_BOLD); put(f"B{base}", "배정", F_BOLD); put(f"C{base}", "완료", F_BOLD); put(f"D{base}", "진행률", F_BOLD)
    for i, m in enumerate(REVIEWERS):
        rr = base + 1 + i
        put(f"A{rr}", m)
        put(f"B{rr}", f'=COUNTIF({asg},A{rr})')
        put(f"C{rr}", f'=COUNTIFS({asg},A{rr},{vd},"<>")')
        put(f"D{rr}", f"=IF(B{rr}=0,0,C{rr}/B{rr})", fmt="0.0%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="이미 있는 시트를 덮어쓰기 (입력 내용이 사라짐)")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        sys.exit(f"[중단] {OUT.relative_to(ROOT)}가 이미 있습니다. 입력 내용을 지우고 다시 만들려면 --force를 붙이세요.")

    courses = load_courses()
    wb = Workbook()
    build_guide(wb.active)
    last = build_review_sheet(wb.create_sheet(), courses)
    build_summary(wb.create_sheet(), last)
    build_domains(wb.create_sheet())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"[저장] {OUT.relative_to(ROOT)}: 과정 {len(courses)}개, 팀원별 약 {len(courses) // len(REVIEWERS)}개")


if __name__ == "__main__":
    main()
