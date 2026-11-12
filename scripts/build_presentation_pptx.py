# -*- coding: utf-8 -*-
"""
Build submission PPTX presentation deck for '인사 교육 지도 (HR Education Skill-Gap Recommender)'.
All metrics are loaded dynamically from presentation/src/data.json and data/hr/reports/*.json.
Output: presentation/HR_교육지도_발표.pptx
"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ==========================================
# 1. Load Data (No Hardcoded Numbers)
# ==========================================
DATA_PATH = "presentation/src/data.json"
R1_PATH = "data/hr/reports/precision_eval_metrics.json"
R2_PATH = "data/hr/reports/precision_eval_round2_metrics.json"
HO_PATH = "data/hr/reports/precision_eval_holdout_metrics.json"
SCRIPT_PATH = "presentation/SCRIPT.md"
OUT_PPTX = "presentation/HR_교육지도_발표.pptx"
CHART_DIR = "presentation/charts"

os.makedirs(CHART_DIR, exist_ok=True)

with open(DATA_PATH, encoding="utf-8") as f:
    data = json.load(f)
with open(R1_PATH, encoding="utf-8") as f:
    r1_metrics = json.load(f)
with open(R2_PATH, encoding="utf-8") as f:
    r2_metrics = json.load(f)
with open(HO_PATH, encoding="utf-8") as f:
    ho_metrics = json.load(f)

has_script = os.path.exists(SCRIPT_PATH)

# ==========================================
# 2. Dashboard Color Palette (from template.html)
# ==========================================
C_PAPER = RGBColor(242, 238, 228)      # --paper: #F2EEE4
C_PAPER2 = RGBColor(232, 226, 210)     # --paper-2: #E8E2D2
C_CARD = RGBColor(255, 252, 245)       # --card: #FFFCF5
C_INK = RGBColor(27, 29, 34)           # --ink: #1B1D22
C_BODY = RGBColor(58, 61, 69)          # --body: #3A3D45
C_DIM = RGBColor(104, 108, 117)        # --dim: #686C75
C_LINE = RGBColor(214, 206, 187)       # --line: #D6CEBB

C_HUD = RGBColor(23, 25, 31)           # --hud: #17191F
C_HUD2 = RGBColor(33, 36, 44)          # --hud-2: #21242C
C_HUD_INK = RGBColor(241, 235, 216)    # --hud-ink: #F1EBD8
C_HUD_DIM = RGBColor(154, 160, 169)    # --hud-dim: #9AA0A9
C_HUD_LINE = RGBColor(57, 62, 73)      # --hud-line: #393E49

C_YEL = RGBColor(246, 196, 49)         # --yel: #F6C431
C_TEAL = RGBColor(31, 143, 120)        # --teal: #1F8F78
C_TEAL_LT = RGBColor(76, 217, 184)     # --teal-lt: #4CD9B8
C_RUST = RGBColor(211, 84, 46)         # --rust: #D3542E
C_BLUE = RGBColor(91, 141, 203)        # --blue: #5B8DCB
C_WARN_BG = RGBColor(251, 227, 217)    # --warn-bg: #FBE3D9
C_WARN_INK = RGBColor(143, 53, 32)     # --warn-ink: #8F3520

FONT_NAME = "Malgun Gothic"
DASHBOARD_URL = "https://hr-edu-map.vercel.app"
GITHUB_URL = "https://github.com/kimsaemi/edu-skill-gap"


# ==========================================
# 3. Generate Matplotlib Charts from data.json
# ==========================================
def generate_data_charts():
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False

    # Chart 1: Cleaning steps
    cleaning = data["eda"]["cleaning"]
    labels = [c["label"] for c in cleaning][::-1]
    vals = [c["n"] for c in cleaning][::-1]

    fig, ax = plt.subplots(figsize=(6.2, 3.4), dpi=260)
    fig.patch.set_facecolor("#FFFCF5")
    ax.set_facecolor("#FFFCF5")
    bars = ax.barh(labels, vals, color="#1F8F78", height=0.58)
    ax.set_xlim(0, max(vals) * 1.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D6CEBB")
    ax.spines["bottom"].set_color("#D6CEBB")
    ax.tick_params(colors="#1B1D22", labelsize=10)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#D6CEBB")
    ax.set_axisbelow(True)
    for bar in bars:
        w = bar.get_width()
        ax.text(w + max(vals)*0.02, bar.get_y() + bar.get_height()/2,
                f"{int(w):,}건", va="center", ha="left", fontsize=10, fontweight="bold", color="#1B1D22")
    ax.set_title("정제 규칙별 적용 건수 (clean_and_synthesize)", fontsize=11, fontweight="bold", color="#1B1D22", pad=10)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "chart_cleaning.png"), dpi=260)
    plt.close()

    # Chart 2: Missingness rates
    missing = data["eda"]["missing"]
    m_labels = [m["label"] for m in missing][::-1]
    m_vals = [m["pct"] for m in missing][::-1]
    colors = ["#D3542E" if v >= 35 else ("#F6C431" if v >= 20 else "#1F8F78") for v in m_vals]

    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=260)
    fig.patch.set_facecolor("#FFFCF5")
    ax.set_facecolor("#FFFCF5")
    bars = ax.barh(m_labels, m_vals, color=colors, height=0.62)
    ax.set_xlim(0, 58)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D6CEBB")
    ax.spines["bottom"].set_color("#D6CEBB")
    ax.tick_params(colors="#1B1D22", labelsize=9.5)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#D6CEBB")
    ax.set_axisbelow(True)
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 1.0, bar.get_y() + bar.get_height()/2,
                f"{w:.1f}%", va="center", ha="left", fontsize=9.5, fontweight="bold", color="#1B1D22")
    ax.set_title(f"주요 컬럼별 결측률 (전체 {data['kpi']['courses']:,}개 기준)", fontsize=11, fontweight="bold", color="#1B1D22", pad=10)
    plt.tight_layout()
    plt.savefig(os.path.join(CHART_DIR, "chart_missing.png"), dpi=260)
    plt.close()


generate_data_charts()


# ==========================================
# 4. Presentation Helper Functions
# ==========================================
prs = pptx.Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def style_shape(shape, fill_color, border_color=None, border_pt=1.0):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(border_pt)
    else:
        shape.line.fill.background()


def add_slide_base(title_text, section_tag=None, subtitle_text=None, is_dark=False, slide_num=None):
    slide = prs.slides.add_slide(BLANK)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    style_shape(bg, C_HUD if is_dark else C_PAPER)

    # Top accent bar
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.08))
    style_shape(bar, C_YEL if is_dark else C_TEAL)

    # Title + small section tag right beside title
    tb = slide.shapes.add_textbox(Inches(0.65), Inches(0.32), Inches(12.03), Inches(0.55))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    r1 = p.add_run()
    r1.text = title_text + "  "
    r1.font.name = FONT_NAME
    r1.font.size = Pt(21)
    r1.font.bold = True
    r1.font.color.rgb = C_HUD_INK if is_dark else C_INK

    if section_tag:
        r2 = p.add_run()
        r2.text = f"[{section_tag}]"
        r2.font.name = FONT_NAME
        r2.font.size = Pt(11.5)
        r2.font.bold = True
        r2.font.color.rgb = C_YEL if is_dark else C_TEAL

    if subtitle_text:
        sb = slide.shapes.add_textbox(Inches(0.65), Inches(0.95), Inches(12.0), Inches(0.38))
        stf = sb.text_frame
        stf.word_wrap = True
        stf.margin_left = stf.margin_top = stf.margin_right = stf.margin_bottom = 0
        sp = stf.paragraphs[0]
        sp.text = subtitle_text
        sp.font.name = FONT_NAME
        sp.font.size = Pt(12)
        sp.font.color.rgb = C_HUD_DIM if is_dark else C_DIM

    # Footer
    if slide_num is not None:
        ft = slide.shapes.add_textbox(Inches(0.65), Inches(7.08), Inches(12.03), Inches(0.28))
        ftf = ft.text_frame
        ftf.margin_left = ftf.margin_top = ftf.margin_right = ftf.margin_bottom = 0
        fp = ftf.paragraphs[0]
        fp.text = f"인사 교육 지도 (kimsaemi/edu-skill-gap)  |  {DASHBOARD_URL}  |  {slide_num} / 20"
        fp.alignment = PP_ALIGN.RIGHT
        fp.font.name = FONT_NAME
        fp.font.size = Pt(9.5)
        fp.font.color.rgb = C_HUD_DIM if is_dark else C_DIM

    return slide


def add_card(slide, x, y, w, h, is_dark=False, fill=None, border=None, border_pt=1.0):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = 0.03
    f = fill if fill else (C_HUD2 if is_dark else C_CARD)
    b = border if border else (C_HUD_LINE if is_dark else C_LINE)
    style_shape(shp, f, b, border_pt)
    return shp


def add_text_lines(slide, x, y, w, h, lines, font_size=13, color=C_BODY, bold_first=False, line_spacing=1.25):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    for idx, line in enumerate(lines):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.line_spacing = line_spacing
        p.space_after = Pt(5)
        if isinstance(line, tuple):
            lead, rest = line
            r1 = p.add_run()
            r1.text = lead
            r1.font.name = FONT_NAME
            r1.font.size = Pt(font_size)
            r1.font.bold = True
            r1.font.color.rgb = color
            r2 = p.add_run()
            r2.text = rest
            r2.font.name = FONT_NAME
            r2.font.size = Pt(font_size)
            r2.font.color.rgb = color
        else:
            p.text = line
            p.font.name = FONT_NAME
            p.font.size = Pt(font_size)
            p.font.bold = (bold_first and idx == 0)
            p.font.color.rgb = color
    return tb


def add_kpi_card(slide, x, y, w, h, big_val, label, sub_text, accent=C_TEAL, is_dark=False):
    add_card(slide, x, y, w, h, is_dark=is_dark)
    # Top color strip
    strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.07))
    style_shape(strip, accent)
    # Big number
    tb = slide.shapes.add_textbox(Inches(x + 0.2), Inches(y + 0.22), Inches(w - 0.4), Inches(0.85))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.text = big_val
    p.font.name = FONT_NAME
    p.font.size = Pt(34)
    p.font.bold = True
    p.font.color.rgb = accent if is_dark else C_INK

    # Label
    ltb = slide.shapes.add_textbox(Inches(x + 0.2), Inches(y + 1.05), Inches(w - 0.4), Inches(0.4))
    ltf = ltb.text_frame
    ltf.word_wrap = True
    ltf.margin_left = ltf.margin_top = ltf.margin_right = ltf.margin_bottom = 0
    lp = ltf.paragraphs[0]
    lp.text = label
    lp.font.name = FONT_NAME
    lp.font.size = Pt(13)
    lp.font.bold = True
    lp.font.color.rgb = C_HUD_INK if is_dark else C_INK

    # Sub
    stb = slide.shapes.add_textbox(Inches(x + 0.2), Inches(y + 1.48), Inches(w - 0.4), Inches(h - 1.62))
    stf = stb.text_frame
    stf.word_wrap = True
    stf.margin_left = stf.margin_top = stf.margin_right = stf.margin_bottom = 0
    sp = stf.paragraphs[0]
    sp.text = sub_text
    sp.font.name = FONT_NAME
    sp.font.size = Pt(11)
    sp.font.color.rgb = C_HUD_DIM if is_dark else C_DIM


def style_table(table, header_bg=C_HUD, header_fg=C_HUD_INK, body_bg=C_CARD, body_fg=C_BODY, font_size=11):
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.06)
            cell.margin_bottom = Inches(0.06)
            cell.fill.solid()
            if r_idx == 0:
                cell.fill.fore_color.rgb = header_bg
            else:
                cell.fill.fore_color.rgb = body_bg if r_idx % 2 == 1 else C_PAPER2
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT_NAME
                p.font.size = Pt(font_size)
                if r_idx == 0:
                    p.font.bold = True
                    p.font.color.rgb = header_fg
                else:
                    p.font.color.rgb = body_fg


# ==========================================
# Extract Key Variables from data.json
# ==========================================
kpi = data["kpi"]
dm = data["dashboard_mapping"]
rec = data["recommend"]
eda = data["eda"]
ho = data["human_eval_rounds"]["holdout"]
r2 = data["human_eval_rounds"]["round2"]
r1 = r1_metrics

cost_levels = {c["label"]: c for c in eda["robust"]["cost_by_level"]}
mid_price = cost_levels["중급"]["paid_median"]
mid_gov_pct = eda["robust"]["mid_gov_pct"]

dom_supply = {d["label"]: d for d in eda["domain_supply"]}
labor_n = dom_supply["노사관계·노무"]["n"]
labor_mid = dom_supply["노사관계·노무"]["mid_plus"]
comp_n = dom_supply["보상·급여·복리후생"]["n"]
cult_mid = dom_supply["조직문화·사내소통"]["mid_plus"]
hrd_n = dom_supply["인재육성·사내교육"]["n"]

h1_all_pct = eda["robust"]["h1_scenarios"][0]["pct"]
h1_no_gh_pct = eda["robust"]["h1_scenarios"][4]["pct"]

sat_pct = data["satisfaction"]["catalog_scored_pct"]
sat_med = data["satisfaction"]["median"]

bias_top3 = rec["stage1"]["bias_top3_final"]
bias_cat = eda["monitor"]["bias_catalog"]
top5_share = eda["monitor"]["top5_share"]
past_n = eda["schedule"]["past"]

prob_scores = ", ".join(str(x) for x in rec["weak_slots"]["probation_reranker_scores"])
lt01_slots = rec["weak_slots"]["lt01_slots"]
total_slots = rec["weak_slots"]["total_slots"]


# ==========================================
# SLIDE 1: 표지 (Dark Theme)
# ==========================================
s1 = prs.slides.add_slide(BLANK)
bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
style_shape(bg1, C_HUD)
bar1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.22), Inches(7.5))
style_shape(bar1, C_TEAL)

add_text_lines(s1, 0.9, 1.3, 11.5, 0.5, ["NCS 인사 실무 과업 기반 직무교육 추천 프로젝트"], font_size=15, color=C_YEL, bold_first=True)
add_text_lines(s1, 0.9, 1.9, 11.5, 1.6, [
    "인사 교육 지도 (HR Skill-Gap Map)",
    f"기관마다 다른 {kpi['courses']:,}개 교육 과정을 90개 인사 실무 과업으로 연결하다"
], font_size=34, color=C_HUD_INK, bold_first=True)
# Adjust 2nd line size
s1.shapes[-1].text_frame.paragraphs[1].font.size = Pt(18)
s1.shapes[-1].text_frame.paragraphs[1].font.color.rgb = C_HUD_DIM

add_card(s1, 0.9, 4.3, 11.4, 1.8, is_dark=True)
add_text_lines(s1, 1.2, 4.55, 10.8, 1.4, [
    ("팀명: ", "[팀 작성 필요]"),
    ("데이터 기준일: ", f"{data['generated']}  (고용24 2026년 운영 과정 반영)"),
    ("발표 대시보드: ", DASHBOARD_URL),
    ("GitHub 저장소: ", GITHUB_URL),
], font_size=14, color=C_HUD_INK)


# ==========================================
# SLIDE 2: 요약 1장 (대시보드 '요약' 화면 숫자 4개 + 결론)
# ==========================================
s2 = add_slide_base(
    "요약: 숫자 네 개와 세 줄 결론",
    section_tag="핵심 요약",
    subtitle_text="대시보드 '요약' 화면의 핵심 수치와 검증 결과를 한눈에 정리했습니다.",
    slide_num=2
)

cand_n = kpi["courses"] - kpi["off_topic"]
cov_pct = eda["monitor"]["coverage_pct"]
filled_slots = dm["slots_total"] - dm["thin_slots"]
ho_p3 = ho["precision_at_3"]["strict"]
ho_ci = ho["precision_at_3"]["ci95_cluster_bootstrap"]
ho_cons = ho["consensus"]["strict"]

add_kpi_card(s2, 0.65, 1.5, 2.85, 2.2, f"{kpi['courses']:,}개", "교육 데이터",
             f"정제 카탈로그 (추천 후보 {cand_n:,}개)\n제공 기관 {kpi['providers']}곳 · 기준 {data['generated']}", C_TEAL)
add_kpi_card(s2, 3.7, 1.5, 2.85, 2.2, f"{cov_pct:.1f}%", "추천 커버리지",
             f"목표 95% · 270개 슬롯 중 {filled_slots}칸 3개 채움", C_BLUE)
add_kpi_card(s2, 6.75, 1.5, 2.85, 2.2, f"{ho_p3:.1f}%", "사람 평가 (홀드아웃)",
             f"목표 70% · 95% 범위 {ho_ci[0]:.0f}~{ho_ci[1]:.0f}%\n두 사람 합의 기준 {ho_cons:.1f}%", C_YEL)
add_kpi_card(s2, 9.8, 1.5, 2.85, 2.2, "0건", "합성 후기·평점",
             "가짜 후기·평점 전면 제거 (목표 0건)", C_RUST)

add_card(s2, 0.65, 4.0, 12.0, 2.75)
add_text_lines(s2, 0.9, 4.2, 11.5, 2.4, [
    "핵심 결론",
    f"• 인사 교육은 많지만, 노무({labor_n}개)·보상({comp_n}개) 실무 과정은 부족하고 중급 유료 가격 중앙값은 {mid_price:,}원으로 비쌉니다.",
    f"• NCS 과업 {kpi['tasks']}개 기준으로 기관을 가리지 않고 {cov_pct:.1f}% 조합에 맞춤 추천 Top 3를 제공합니다.",
    f"• 처음 보는 업무 10개(홀드아웃) 사람 평가에서 {ho_p3:.1f}% 적합 판정을 받았으며(합의 기준 {ho_cons:.1f}%), 평점 대신 업무 적합도와 근거를 보여 줍니다."
], font_size=14, color=C_INK, bold_first=True)


# ==========================================
# SLIDE 3: ① 문제정의 & 가설 - 3C 분석
# ==========================================
s3 = add_slide_base(
    "문제는 교육의 양이 아니라, 연결 기준의 부재",
    section_tag="① 문제정의 & 가설",
    subtitle_text="3C 분석 (main 대시보드 02장 기준)",
    slide_num=3
)

c3_data = [
    ("Customer · 인사 담당자", C_TEAL, [
        "업무가 생기면 교육을 찾지만, 내 업무와 수준에 맞는지 판단할 근거가 없습니다.",
        "시간과 예산이 빠듯해 여러 기관을 비교할 여유도 없습니다."
    ]),
    ("Competitor · 기관 포털·고용24 검색", C_RUST, [
        "기관별로 분류가 다르고 키워드 검색 위주입니다.",
        f"상위 5개 기관이 과정의 {kpi['hr_field_pct']:.1f}% 이상(전체 {top5_share:.1f}%)을 차지하지만 서로 연결돼 있지 않고, 평점은 없거나 기준이 제각각입니다."
    ]),
    ("Company · 우리 서비스", C_BLUE, [
        f"NCS 과업 {kpi['tasks']}개를 공통 기준으로 삼아 기관을 가리지 않고 과정을 읽습니다.",
        "추천마다 근거(뜻·키워드·난이도)를 함께 보여 줍니다."
    ])
]
# Note: Use exact main template.html text for Competitor:
c3_data[1] = ("Competitor · 기관 포털·고용24 검색", C_RUST, [
    "기관별로 분류가 다르고 키워드 검색 위주입니다.",
    f"상위 5개 기관이 과정의 {top5_share:.1f}%를 차지하지만 서로 연결돼 있지 않고, 평점은 없거나 기준이 제각각입니다."
])

for idx, (head, col, lines) in enumerate(c3_data):
    x = 0.65 + idx * 4.1
    add_card(s3, x, 1.5, 3.85, 3.7)
    top = s3.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.5), Inches(3.85), Inches(0.48))
    style_shape(top, col)
    add_text_lines(s3, x + 0.18, 1.6, 3.5, 0.35, [head], font_size=14, color=C_CARD, bold_first=True)
    add_text_lines(s3, x + 0.22, 2.2, 3.4, 2.7, lines, font_size=14, color=C_BODY, line_spacing=1.4)

add_card(s3, 0.65, 5.45, 12.0, 1.25, fill=C_HUD, border=C_HUD_LINE)
add_text_lines(s3, 0.9, 5.65, 11.5, 0.9, [
    "핵심 문제 정의",
    "\"인사 담당자가 자기 업무와 숙련도에 맞는 교육을 찾는 데 드는 탐색 비용이 크고, 찾은 교육이 실제로 맞는지 확인할 근거도 부족하다.\""
], font_size=14, color=C_HUD_INK, bold_first=True)


# ==========================================
# SLIDE 4: ① 문제정의 & 가설 - 가설과 북극성 지표
# ==========================================
s4 = add_slide_base(
    "가설 3가지와 북극성 지표 (Precision@3 목표 70%)",
    section_tag="① 문제정의 & 가설",
    subtitle_text="실무자 중심의 문제 검증 및 북극성 지표 설계",
    slide_num=4
)

add_card(s4, 0.65, 1.45, 4.4, 2.2, fill=C_HUD, border=C_TEAL, border_pt=1.5)
add_text_lines(s4, 0.85, 1.65, 4.0, 1.85, [
    "북극성 지표 (North Star Metric)",
    "과업 적합 추천률 (Precision@3)",
    f"목표: 70.0% 이상 (현재 홀드아웃 {ho_p3:.1f}%)",
    "보조 KPI: 커버리지 · 1위 유사도 · 근거 품질 · 다양성"
], font_size=13.5, color=C_HUD_INK, bold_first=True)

add_card(s4, 5.3, 1.45, 7.35, 2.2)
add_text_lines(s4, 5.55, 1.65, 6.9, 1.85, [
    "타겟 고객 (인사 담당자 3단계)",
    "• 입문 (신입~1년차): 업무 용어·절차 학습, 무료·단기 온라인 선호",
    f"• 실무 (2~5년차): 급여·평가·노무 처리, 중급 가격 부담(중앙값 {mid_price:,}원) 가장 큰 핵심층",
    "• 관리자 (팀장급): 제도 설계 및 조직 운영, 전략·심화 과정 탐색"
], font_size=13, color=C_BODY, bold_first=True)

tbl_s4 = s4.shapes.add_table(4, 4, Inches(0.65), Inches(3.9), Inches(12.0), Inches(2.85)).table
tbl_s4.columns[0].width = Inches(3.3)
tbl_s4.columns[1].width = Inches(3.4)
tbl_s4.columns[2].width = Inches(2.6)
tbl_s4.columns[3].width = Inches(2.7)

rows_s4 = [
    ["가설", "도메인 근거", "검증 방법", "검증 결과"],
    ["H1. 입문·초급 편중으로 실무자 교육 부족", "수강생 많은 입문 과정 다수 제작", "기관 구성별 난이도·비용 비교", f"부분 채택 (전체 {h1_all_pct:.1f}%, 대형 이러닝 제외 시 {h1_no_gh_pct:.1f}%)"],
    ["H2. 노무·보상·조직문화 교육 공급 부족", "법 개정 잦고 전문 강사 수급 어려움", f"과업 의미 유사도 {eda['domain_tau']} 이상 과정 수", f"부분 채택 (노무 {labor_n}개·보상 {comp_n}개, 인재육성 {hrd_n}개 대비 소수)"],
    ["H3. 평점·후기는 추천 근거로 부적합", "일부 기관에만 존재, 고점 편향", "공식 만족도 보유율 및 분포 확인", f"채택 (보유 {sat_pct:.1f}% · 중앙값 {sat_med:.1f}점)"]
]
for r_i, row in enumerate(rows_s4):
    for c_i, val in enumerate(row):
        tbl_s4.cell(r_i, c_i).text = val
style_table(tbl_s4, font_size=11.5)


# ==========================================
# SLIDE 5: ② 데이터 구조 설명 - 출처 3곳 & 과업 90개 구조
# ==========================================
s5 = add_slide_base(
    f"데이터 출처 3곳과 인사 {kpi['tasks']}개 실무 과업 체계",
    section_tag="② 데이터 구조 설명",
    subtitle_text=f"교육기관 {kpi['providers']}곳의 과정 {kpi['courses']:,}개를 9개 분야 × 10과업 × 3수준 = {dm['slots_total']}개 슬롯으로 연결",
    slide_num=5
)

tbl_s5 = s5.shapes.add_table(5, 3, Inches(0.65), Inches(1.5), Inches(12.0), Inches(2.6)).table
tbl_s5.columns[0].width = Inches(3.6)
tbl_s5.columns[1].width = Inches(3.8)
tbl_s5.columns[2].width = Inches(4.6)

rows_s5 = [
    ["데이터 소스", "확보 방법", "주요 수집 내용"],
    ["민간 교육기관 6곳 (GSEEK, 휴넷, KMA, KPC, 멀티캠퍼스, KFO)", "공개 과정 페이지 수집 → 기관별 DB", "과정명, 소개, 목표, 커리큘럼, 가격, 시간, 형태"],
    ["고용24 Open API (내일배움카드·사업주훈련)", "목록·상세·일정 API + 상세 페이지", f"2026년 운영 과정 {kpi['work24_courses']:,}개, 훈련비, NCS 코드, 공식 만족도"],
    ["공공데이터포털 NCS API", "NCS 교육과정 Open API", "NCS 분류 및 능력단위, 과업 연결 기준"],
    ["인사 실무 과업 목록 (팀 정의)", "NCS 기반 9개 영역 × 10개 과업 설계", "과업명, 쉬운 설명, KSA, 3단계 수준(입문·실무·관리자)"]
]
for r_i, row in enumerate(rows_s5):
    for c_i, val in enumerate(row):
        tbl_s5.cell(r_i, c_i).text = val
style_table(tbl_s5, font_size=11.5)

add_card(s5, 0.65, 4.35, 5.85, 2.35)
add_text_lines(s5, 0.88, 4.52, 5.4, 2.0, [
    "인사 실무 9대 영역 (각 10개 과업 = 총 90개)",
    "1. 인사전략·인력기획   2. 조직설계·직무분석   3. 인재채용",
    "4. 온보딩·직원경험     5. 성과평가·목표관리   6. 보상·급여·복리후생",
    "7. 인재육성·사내교육   8. 조직문화·사내소통   9. 노사관계·노무"
], font_size=12.5, color=C_BODY, bold_first=True)

add_card(s5, 6.8, 4.35, 5.85, 2.35, fill=C_HUD, border=C_HUD_LINE)
add_text_lines(s5, 7.05, 4.52, 5.4, 2.0, [
    f"추천 매핑 단위: {dm['slots_total']}개 슬롯",
    f"• {kpi['domains']}개 분야 × 10개 과업 × 3개 수준(입문·실무·관리자·심화)",
    f"• 대시보드 연결 강좌 {dm['courses']:,}개 (추천 후보 {cand_n:,}개 중 선별)",
    f"• 모든 과정은 42개 표준 컬럼 스키마로 통합 관리"
], font_size=12.5, color=C_HUD_INK, bold_first=True)


# ==========================================
# SLIDE 6: ② 데이터 구조 설명 - 주요 컬럼 표
# ==========================================
s6 = add_slide_base(
    "42개 통합 스키마 중 핵심 분석 컬럼 구조",
    section_tag="② 데이터 구조 설명",
    subtitle_text="기관마다 다른 포맷을 단일 표준 스키마(education_courses_search_cleaned.parquet)로 통일",
    slide_num=6
)

tbl_s6 = s6.shapes.add_table(8, 4, Inches(0.65), Inches(1.5), Inches(12.0), Inches(4.5)).table
tbl_s6.columns[0].width = Inches(2.5)
tbl_s6.columns[1].width = Inches(2.2)
tbl_s6.columns[2].width = Inches(3.8)
tbl_s6.columns[3].width = Inches(3.5)

rows_s6 = [
    ["컬럼명", "데이터 타입", "설명", "추천·분석 활용처"],
    ["course_id / title", "문자열", "고유 ID 및 과정명 (결측 0.0%)", "중복 제거 및 결과 표시 기준"],
    ["provider", "문자열", f"교육기관명 (총 {kpi['providers']}곳, 결측 0.0%)", "기관 편중 모니터링 및 필터"],
    ["course_intro / goals / curriculum", "텍스트", "과정 소개·학습목표·커리큘럼", "Ko-SRoBERTa 임베딩 및 BM25 텍스트"],
    ["difficulty", "범주형", "입문·초급 / 중급 / 고급 / 미확인", "사용자 수준별 난이도 보너스(0~10점)"],
    ["price / education_type", "수치 / 범주", "수강료 및 온·오프라인 형태", "비용 장벽 분석 및 고객 필터"],
    ["duration_hours / start_date", "수치 / 날짜", "총 교육시간 및 개강일", "운영 종료 필터 및 신선도 체크"],
    ["ncs_code / stdgScor", "문자열 / 수치", "8자리 NCS 코드 및 고용24 공식 만족도", "직무 매핑 및 H3 평점 한계 검증"]
]
for r_i, row in enumerate(rows_s6):
    for c_i, val in enumerate(row):
        tbl_s6.cell(r_i, c_i).text = val
style_table(tbl_s6, font_size=11.5)

add_card(s6, 0.65, 6.18, 12.0, 0.65)
add_text_lines(s6, 0.88, 6.32, 11.5, 0.4, [
    f"텍스트 품질: 설명이 충분한 과정 {kpi['rich_pct']:.1f}%  |  과정명만 있는 과정 {kpi['title_only_pct']:.1f}% (결측은 임의로 채우지 않고 '미확인' 유지)"
], font_size=12.5, color=C_INK, bold_first=True)


# ==========================================
# SLIDE 7: ③ 전처리 과정 & 결측/이상치 처리 - 정제 5단계 & 제외 1,377개
# ==========================================
s7 = add_slide_base(
    f"표준 정제 5단계와 직무 무관 과정 {kpi['off_topic']:,}개 제외",
    section_tag="③ 전처리 과정 & 결측/이상치 처리",
    subtitle_text="모든 과정에 동일 정제 규칙(clean_and_synthesize)을 적용하고 이력을 기록했습니다.",
    slide_num=7
)

s7.shapes.add_picture(os.path.join(CHART_DIR, "chart_cleaning.png"), Inches(0.65), Inches(1.5), width=Inches(6.5))

add_card(s7, 7.4, 1.5, 5.25, 2.55)
add_text_lines(s7, 7.62, 1.68, 4.8, 2.2, [
    f"직무 무관 과정 {kpi['off_topic']:,}개 제외",
    f"• 전체 {kpi['courses']:,}개 중 {kpi['off_topic']:,}개를 추천 후보에서 제외 → {cand_n:,}개 후보 확보",
    "• 제외 대상: 취미·교양, 대학 학과 과목, 자격시험 대비, SAP·QA·전산회계 등 타 직종 특화 과정",
    "• 단, '급여·원천징수 실무' 과정이 빠지지 않도록 제외 규칙 범위 정밀 조정"
], font_size=12.5, color=C_BODY, bold_first=True)

add_card(s7, 7.4, 4.25, 5.25, 2.45, fill=C_HUD, border=C_HUD_LINE)
add_text_lines(s7, 7.62, 4.42, 4.8, 2.1, [
    "핵심 품질 보완 내역",
    "• 합성으로 만든 가짜 후기·평점 전면 제거 (점검 결과 0건)",
    f"• 2024년 승인 종료된 고용24 130개 → 2026년 과정 {kpi['work24_courses']:,}개로 교체 및 상세 텍스트 보강",
    "• GSEEK 1,991개 상세 링크 보정 (목록 페이지 → 상세 페이지)"
], font_size=12.5, color=C_HUD_INK, bold_first=True)


# ==========================================
# SLIDE 8: ③ 전처리 과정 & 결측/이상치 처리 - 결측률 & 이상치
# ==========================================
s8 = add_slide_base(
    "컬럼별 결측률과 가격·날짜·코드 이상치 처리",
    section_tag="③ 전처리 과정 & 결측/이상치 처리",
    subtitle_text="결측을 추정해 채우지 않고 '미확인'으로 명시하며, 수집 오류를 원천 교정했습니다.",
    slide_num=8
)

s8.shapes.add_picture(os.path.join(CHART_DIR, "chart_missing.png"), Inches(0.65), Inches(1.48), width=Inches(6.6))

add_card(s8, 7.45, 1.48, 5.2, 5.22)
add_text_lines(s8, 7.68, 1.68, 4.75, 4.85, [
    "결측 및 이상치 정제 원칙",
    ("1. 결측 미확인 원칙: ", "가격·시간 결측을 0원(무료)으로 처리하지 않고 '미확인'으로 구분"),
    ("2. 가격 이상치 (59건): ", "사업주훈련 비용 0원 오류를 상세 API 실제 1인당 훈련비로 교체"),
    ("3. 날짜·운영종료 필터: ", f"개강일 미기재 {eda['schedule']['no_date']:,}건, 과거 일정 {past_n:,}건 분리 · '운영 종료' 배지 표기"),
    ("4. NCS 코드 복원 (140건): ", "숫자형 저장으로 앞자리 0 손실(02020201 → 2020201.0) → 8자리 문자열 복원 (130/130 일치)"),
    ("5. 교육 형태 분리 (130건): ", "일괄 '혼합' 입력 오류를 공식 훈련일수 기준 원격/집합으로 분리")
], font_size=12.5, color=C_BODY, bold_first=True, line_spacing=1.22)


# ==========================================
# SLIDE 9: ④ 핵심 분석 지표 설명 - 2단계 추천 파이프라인
# ==========================================
s9 = add_slide_base(
    "2단계 하이브리드 추천 파이프라인 및 Top 3 선정 규칙",
    section_tag="④ 핵심 분석 지표 설명",
    subtitle_text="의미 + 키워드 + 난이도 1차 스코어링 후 Cross-Encoder 리랭커로 정밀 재정렬",
    slide_num=9
)

steps_s9 = [
    ("1단계: 1차 후보 스코어링", C_TEAL, [
        "• 의미 유사도 (50%): Ko-SRoBERTa 768차원 임베딩 코사인 유사도",
        "• 키워드 일치 (35%): Kiwi 형태소 기반 BM25 점수",
        "• 난이도 보너스 (최대 +10점): 사용자 수준 일치 +10점, 난이도 미표기는 절반(+5점)"
    ]),
    ("중간 필터: 제외 규칙", C_BLUE, [
        f"• 인사 업무와 무관한 과정 {kpi['off_topic']:,}개를 추천 후보에서 제외 (자격시험·타 직종 등, 규칙 목록으로 관리)",
        "• 같은 제목의 다른 회차·기관 중복 제거는 실험했지만 빈 칸이 늘어 채택하지 않음",
        "• 운영이 끝난 과정은 추천에서 빼지 않고 화면에 '운영 종료' 배지로 표시"
    ]),
    ("2단계: Cross-Encoder 리랭커 → Top 3", C_YEL, [
        "• 모델: Dongjin-kr/ko-reranker (업무 설명과 과정 설명을 한 쌍으로 동시 판독)",
        f"• 최종 출력: {dm['slots_total']}개 슬롯 중 {filled_slots}칸({cov_pct:.1f}%)에 Top 3 추천",
        f"• 제목 전용 과정 비율: 전체 {rec['title_only_all_pct']}% → 최종 Top 3 내 {rec['title_only_top3_pct']}%로 감소"
    ])
]

for idx, (st_title, col, st_lines) in enumerate(steps_s9):
    y = 1.5 + idx * 1.8
    add_card(s9, 0.65, y, 12.0, 1.58)
    badge = s9.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(y), Inches(0.18), Inches(1.58))
    style_shape(badge, col)
    add_text_lines(s9, 1.05, y + 0.16, 11.3, 1.3, [st_title] + st_lines, font_size=13, color=C_INK if idx != 2 else C_INK, bold_first=True)


# ==========================================
# SLIDE 10: ④ 핵심 분석 지표 설명 - Precision@3 A/B/C 정의
# ==========================================
s10 = add_slide_base(
    "사람 평가 지표 정의 (Precision@3 A/B/C)와 검증 결과",
    section_tag="④ 핵심 분석 지표 설명",
    subtitle_text="팀원 4명이 2인 1조 블라인드 교차 평가 수행 (판단 불가는 분모에서 제외)",
    slide_num=10
)

defs = [
    ("A · 판정 건 적합률", f"{ho_p3:.1f}% (홀드아웃)", "평가자가 내린 개별 판정 중 '적합' 비율.\n95% 신뢰구간(클러스터 부트스트랩): " + f"{ho_ci[0]:.1f}~{ho_ci[1]:.1f}%"),
    ("B · 항목 합의 적합률", f"{ho_cons:.1f}% (보수적)", "같은 항목을 본 두 사람 판정이 다를 때 낮은 쪽을 채택한 엄격 기준."),
    ("C · 평가자 일치율", f"{ho['agreement']['pct']:.1f}% (κ={ho['agreement']['cohen_kappa']:.3f})", "두 평가자가 동일한 판정을 내린 비율과 우연 보정 일치도(Cohen's Kappa).")
]
for idx, (d_t, d_v, d_d) in enumerate(defs):
    x = 0.65 + idx * 4.1
    add_card(s10, x, 1.48, 3.85, 2.05)
    add_text_lines(s10, x + 0.2, 1.65, 3.45, 1.75, [d_t, d_v, d_d], font_size=12, color=C_BODY, bold_first=True)
    s10.shapes[-1].text_frame.paragraphs[1].font.size = Pt(18)
    s10.shapes[-1].text_frame.paragraphs[1].font.bold = True
    s10.shapes[-1].text_frame.paragraphs[1].font.color.rgb = C_TEAL

tbl_s10 = s10.shapes.add_table(4, 6, Inches(0.65), Inches(3.8), Inches(12.0), Inches(2.85)).table
tbl_s10.columns[0].width = Inches(2.8)
tbl_s10.columns[1].width = Inches(1.4)
tbl_s10.columns[2].width = Inches(2.4)
tbl_s10.columns[3].width = Inches(2.2)
tbl_s10.columns[4].width = Inches(1.8)
tbl_s10.columns[5].width = Inches(1.4)

rows_s10 = [
    ["평가 라운드", "판정 수(A)", "판정 적합률 A (95% CI)", "합의 적합률 B", "일치율 C (카파)", "1위 적합률"],
    ["1차 (규칙 개선 전 10개)", f"{r1['precision_at_3']['n']}건",
     f"{r1['precision_at_3']['strict']:.1f}% ({r1['precision_at_3']['ci95_cluster_bootstrap'][0]:.1f}~{r1['precision_at_3']['ci95_cluster_bootstrap'][1]:.1f}%)",
     f"{r1['consensus']['strict']:.1f}%", f"{r1['agreement']['pct']:.1f}% ({r1['agreement']['cohen_kappa']:.3f})", f"{r1['by_rank']['1']['strict']:.1f}%"],
    ["2차 (개선 후 동일 10개)", f"{r2['precision_at_3']['n']}건",
     f"{r2['precision_at_3']['strict']:.1f}% ({r2['precision_at_3']['ci95_cluster_bootstrap'][0]:.1f}~{r2['precision_at_3']['ci95_cluster_bootstrap'][1]:.1f}%)",
     f"{r2['consensus']['strict']:.1f}%", f"{r2['agreement']['pct']:.1f}% ({r2['agreement']['cohen_kappa']:.3f})", f"{r2['by_rank']['1']['strict']:.1f}%"],
    ["홀드아웃 (새 업무 10개)", f"{ho['precision_at_3']['n']}건",
     f"{ho['precision_at_3']['strict']:.1f}% ({ho_ci[0]:.1f}~{ho_ci[1]:.1f}%)",
     f"{ho['consensus']['strict']:.1f}%", f"{ho['agreement']['pct']:.1f}% ({ho['agreement']['cohen_kappa']:.3f})", f"{ho['by_rank']['1']['strict']:.1f}%"]
]
for r_i, row in enumerate(rows_s10):
    for c_i, val in enumerate(row):
        tbl_s10.cell(r_i, c_i).text = val
style_table(tbl_s10, font_size=11.5)


# ==========================================
# SLIDE 11: ⑤ 대시보드 시각화 공유 - 오차막대 & 인사 교육 지도
# ==========================================
s11 = add_slide_base(
    "대시보드 시각화 ①: 사람 평가 오차막대와 인사 교육 지도",
    section_tag="⑤ 대시보드 시각화 공유",
    subtitle_text=f"라이브 대시보드 확인: {DASHBOARD_URL}/#human-eval  |  {DASHBOARD_URL}/#course-map-fig",
    slide_num=11
)

add_card(s11, 0.65, 1.48, 6.2, 5.28, is_dark=True)
s11.shapes.add_picture(os.path.join(CHART_DIR, "dash_human_eval_errorbar.png"), Inches(0.8), Inches(1.62), width=Inches(5.9))
add_text_lines(s11, 0.85, 5.45, 5.8, 1.15, [
    "사람 평가 Precision@3 오차막대 (#human-eval)",
    f"• 1차 {r1['precision_at_3']['strict']:.1f}% → 2차 {r2['precision_at_3']['strict']:.1f}% → 홀드아웃 {ho_p3:.1f}%로 목표 70% 달성",
    "• 표본이 작아(10개 업무) 95% 신뢰구간이 넓어 추가 평가 필요"
], font_size=11.5, color=C_HUD_INK, bold_first=True)

add_card(s11, 7.05, 1.48, 5.6, 5.28, is_dark=True)
s11.shapes.add_picture(os.path.join(CHART_DIR, "dash_course_map.png"), Inches(7.85), Inches(1.58), height=Inches(4.0))
add_text_lines(s11, 7.25, 5.7, 5.2, 0.98, [
    "인사 교육 지도 UMAP 2차원 투영 (#course-map-fig)",
    f"• {kpi['courses']:,}개 과정과 {kpi['tasks']}개 과업을 배치, 빨간 별은 추천 3개 미만 슬롯({dm['thin_slots']}개)"
], font_size=11.5, color=C_HUD_INK, bold_first=True)


# ==========================================
# SLIDE 12: ⑤ 대시보드 시각화 공유 - 기관 쏠림 & 급여 담당자 사례
# ==========================================
s12 = add_slide_base(
    "대시보드 시각화 ②: 기관 쏠림과 실무 사례 '급여 담당자'",
    section_tag="⑤ 대시보드 시각화 공유",
    subtitle_text=f"라이브 대시보드 확인: {DASHBOARD_URL}/#ch-bias  |  {DASHBOARD_URL}/#explorer",
    slide_num=12
)

add_card(s12, 0.65, 1.48, 5.9, 5.28, is_dark=True)
s12.shapes.add_picture(os.path.join(CHART_DIR, "dash_provider_skew.png"), Inches(0.8), Inches(1.85), width=Inches(5.6))
add_text_lines(s12, 0.85, 4.75, 5.5, 1.85, [
    "기관 편중: 카탈로그 vs 추천 (#ch-bias)",
    f"• 한국생산성본부(KPC)는 카탈로그의 {bias_cat:.1f}%지만 추천 Top 3의 {bias_top3:.1f}% 차지",
    "• 회차 중복 제거·길이 보정 비교에도 편중 지속 → 원인 분석 과제 도출"
], font_size=12, color=C_HUD_INK, bold_first=True)

add_card(s12, 6.75, 1.48, 5.9, 5.28, is_dark=True)
s12.shapes.add_picture(os.path.join(CHART_DIR, "dash_salary_case.png"), Inches(7.45), Inches(1.58), height=Inches(4.25))
add_text_lines(s12, 6.95, 5.95, 5.5, 0.72, [
    "과업별 추천 탐색기: 급여·상여·4대보험 마감 실무 (#explorer)",
    "• 홀드아웃 평가에서 두 평가자 모두 Top 3 전 과정을 '적합' 판정한 사례"
], font_size=11.5, color=C_HUD_INK, bold_first=True)


# ==========================================
# SLIDE 13: ⑥ 비즈니스 인사이트 도출 - 인사이트 1 & 2
# ==========================================
s13 = add_slide_base(
    "인사이트 ①: 중급 비용 장벽과 노무·보상·조직문화 공백",
    section_tag="⑥ 비즈니스 인사이트 도출",
    subtitle_text="대시보드 05장 인사이트 카드 1~2 (데이터 기반 발견 → 의미 → 전략)",
    slide_num=13
)

ins12 = [
    ("1 · 중급 과정의 비용 장벽", C_TEAL, [
        ("발견: ", f"난이도 표기 과정의 {h1_all_pct:.1f}%가 입문·초급(기관 구성 따라 차이). 인사 중급 유료 가격 중앙값은 {mid_price:,}원."),
        ("의미: ", "2~5년차 실무자가 다음 단계 교육을 고를 때 비용 부담이 크고, 국비 외 저비용 선택지가 적습니다."),
        ("전략: ", f"실무·관리자 선택 시 중급 이상 가점, 중급 이상의 {mid_gov_pct:.1f}%인 국비 과정 우선 노출. 공백 구간은 30~45시간 마이크로디그리 기획 근거로 활용.")
    ]),
    ("2 · 노무·보상·조직문화 공백", C_RUST, [
        ("발견: ", f"의미 유사도 기준 노무 과정 {labor_n}개(중급+ {labor_mid}개), 조직문화 중급+ {cult_mid}개. 보상은 급여 계산 위주이며 설계 과정 부족."),
        ("의미: ", "법 개정 대응처럼 틀리면 리스크가 큰 업무일수록 현업에 맞는 교육이 비어 있습니다."),
        ("전략: ", "고용24 노무 과정 및 노무사회·경영자단체 교육으로 공급처 확대. 공백 목록을 교육기관 제휴·콘텐츠 기획 제안서로 활용.")
    ])
]

for idx, (title, col, items) in enumerate(ins12):
    x = 0.65 + idx * 6.1
    add_card(s13, x, 1.5, 5.85, 5.15)
    hdr = s13.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.5), Inches(5.85), Inches(0.55))
    style_shape(hdr, col)
    add_text_lines(s13, x + 0.22, 1.63, 5.4, 0.35, [title], font_size=15, color=C_CARD, bold_first=True)
    add_text_lines(s13, x + 0.25, 2.28, 5.35, 4.15, items, font_size=13.5, color=C_BODY, line_spacing=1.35)


# ==========================================
# SLIDE 14: ⑥ 비즈니스 인사이트 도출 - 인사이트 3, 4, 5
# ==========================================
s14 = add_slide_base(
    "인사이트 ②: 평점 한계·데이터 노후화·기관 쏠림",
    section_tag="⑥ 비즈니스 인사이트 도출",
    subtitle_text="대시보드 05장 인사이트 카드 3~5 (KPC 쏠림은 '원인 미확인' 유지)",
    slide_num=14
)

ins345 = [
    ("3 · 평점 대신 업무 적합도", C_BLUE, [
        ("발견: ", f"공식 만족도는 카탈로그 {sat_pct:.1f}%에만 있고 중앙값 {sat_med:.1f}점으로 변별력 없음."),
        ("의미: ", "평점 기반 정렬은 일부 과정만 노출해 공정성과 품질을 해칩니다."),
        ("전략: ", "업무 적합도 점수와 근거 문장을 유지하고, 수강 후 '업무 도움 여부' 짧은 피드백을 모아 순위에 반영합니다.")
    ]),
    ("4 · 데이터는 1년이면 낡는다", C_YEL, [
        ("발견: ", f"고용24 2024년 승인 130개 전량 운영 종료. 타 기관 {past_n:,}개도 일정 경과."),
        ("의미: ", "추천이 맞아도 신청할 수 없으면 사용자는 즉시 이탈합니다."),
        ("전략: ", "고용24 과정 월 1회 자동 갱신 및 일정 경과 과정 '운영 종료' 배지 표시(적용 완료). 신선도를 상시 지표로 관리합니다.")
    ]),
    ("5 · 추천이 한 기관에 쏠린다", C_RUST, [
        ("발견: ", f"한국생산성본부(KPC)가 카탈로그 {bias_cat:.1f}%인데 Top 3의 {bias_top3:.1f}% 점유. 회차 중복이나 길이 효과 제거 후에도 지속돼 원인은 아직 미확인."),
        ("의미: ", "사용자가 다른 기관의 더 적합한 과정을 놓칠 수 있습니다."),
        ("전략: ", "기관 상한(최대 2개) 적용 시 3개 미만 슬롯이 4→25개로 급증. 억지 상한 대신 문체·주제 분포 원인 분석 후 보정.")
    ])
]

for idx, (title, col, items) in enumerate(ins345):
    x = 0.65 + idx * 4.1
    add_card(s14, x, 1.5, 3.85, 5.15)
    hdr = s14.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.5), Inches(3.85), Inches(0.52))
    style_shape(hdr, col)
    add_text_lines(s14, x + 0.18, 1.62, 3.5, 0.35, [title], font_size=13.5, color=C_CARD if col != C_YEL else C_INK, bold_first=True)
    add_text_lines(s14, x + 0.2, 2.22, 3.45, 4.25, items, font_size=12.5, color=C_BODY, line_spacing=1.32)


# ==========================================
# SLIDE 15: ⑦ 개선 제안 & 액션 플랜 - So What -> Now What 5개
# ==========================================
s15 = add_slide_base(
    "개선 제안 & 액션 플랜 (So What → Now What)",
    section_tag="⑦ 개선 제안 & 액션 플랜",
    subtitle_text="발견된 5가지 인사이트에 대한 구체적 실행 계획 및 기대 효과",
    slide_num=15
)

tbl_s15 = s15.shapes.add_table(6, 4, Inches(0.65), Inches(1.5), Inches(12.0), Inches(5.15)).table
tbl_s15.columns[0].width = Inches(2.2)
tbl_s15.columns[1].width = Inches(3.3)
tbl_s15.columns[2].width = Inches(3.8)
tbl_s15.columns[3].width = Inches(2.7)

rows_s15 = [
    ["영역 (구분)", "문제 인식 (So What)", "실행 과제 (Now What)", "기대 효과"],
    ["1. 비용·수준", f"중급 유료 교육비 부담(중앙값 {mid_price:,}원)", f"실무·관리자 선택 시 국비({mid_gov_pct:.1f}%) 우선 추천, 30~45h 과정 기획", "비용 장벽 완화 및 공백 해소"],
    ["2. 공백 공급처", f"노무({labor_n}개)·조직문화({cult_mid}개) 과정 부족", "노무사회·경영자단체·고용24 노무 공급처 확대 및 제휴 제안", "법·제도 실무 교육 커버리지 강화"],
    ["3. 평점·피드백", f"공식 만족도 {sat_pct:.1f}%·변별력 한계", "업무 적합도 근거 제시 유지 + 수강 후 업무 도움 피드백 루프 구축", "평점 없이도 순위 지속 개선"],
    ["4. 데이터 신선도", f"고용24 종료 130건·일정 경과 {past_n:,}건", "고용24 월 1회 자동 갱신 파이프라인 및 '운영 종료' 표시 상시화", "신청 가능한 최신 과정만 제공"],
    ["5. 모델·다양성", f"KPC Top 3 점유 {bias_top3:.1f}%·반복 추천", "문체·주제 분포 기반 편중 원인 규명, 반복 감점·NCS 능력단위 확장", "기관 다양성 및 추천 정확도 향상"]
]
for r_i, row in enumerate(rows_s15):
    for c_i, val in enumerate(row):
        tbl_s15.cell(r_i, c_i).text = val
style_table(tbl_s15, font_size=11.5)


# ==========================================
# SLIDE 16: ⑦ 개선 제안 & 액션 플랜 - 남은 한계 및 고도화 계획
# ==========================================
s16 = add_slide_base(
    "시스템의 남은 한계와 검증 고도화 계획",
    section_tag="⑦ 개선 제안 & 액션 플랜",
    subtitle_text="대시보드 06장 '읽을 때 알아 둘 것' 기반 솔직한 한계 명시",
    slide_num=16
)

add_card(s16, 0.65, 1.5, 5.85, 5.15, fill=C_WARN_BG, border=C_RUST)
add_text_lines(s16, 0.88, 1.72, 5.4, 4.7, [
    "현재 시스템의 남은 한계 (주의사항)",
    f"• 약한 추천 칸: '수습 평가 기준표' 업무(실무)는 리랭커 점수가 {prob_scores}로 관련 낮은 과정이 채워짐 ({total_slots}개 슬롯 중 0.1 미만 포함 {lt01_slots}개)",
    f"• 팀 내부 평가 한계: 팀원 4명 평가라 후하게 판정됐을 가능성 존재 (표본 10개 업무, 신뢰구간 {ho_ci[0]:.0f}~{ho_ci[1]:.0f}%)",
    f"• 난이도 표기 편차: 미표기 {data['difficulty']['unlabeled']:,}개({data['difficulty']['unlabeled_pct']}%)는 KMA·KPC 위주이며 표기 기준 기관별 상이",
    f"• 반복 추천 및 NCS 미연결: 과업 {rec['needs_review']}개는 임시 역량 연결, 과정 {rec['reused5_courses']}개가 5개+ 과업에 반복({rec['reused5_slot_pct']}%)"
], font_size=12.5, color=C_WARN_INK, bold_first=True, line_spacing=1.28)

add_card(s16, 6.75, 1.5, 5.9, 5.15, fill=C_HUD, border=C_HUD_LINE)
add_text_lines(s16, 7.0, 1.72, 5.4, 4.7, [
    "향후 고도화 로드맵",
    "1. 평가 신뢰도 강화: 처음 보는 업무 10개 추가 평가(홀드아웃 2차) — 키워드 검색(BM25) 추천과 블라인드 비교, 가짜 추천을 섞어 평가자가 걸러내는지 확인",
    "2. 데이터 파이프라인 자동화: 민간 기관 시간·가격 결측 보완 및 고용24 월간 자동 갱신 배치",
    f"3. 추천 모델 정교화: 반복 추천 감점 도입, 기관 편중 보정, 미연결 과업 {rec['needs_review']}개용 NCS 능력단위 보강",
    "4. 사용자 피드백 루프: 수강 후 '업무 적용 도움 여부' 데이터 수집 → 대시보드 지표 자동 반영"
], font_size=12.5, color=C_HUD_INK, bold_first=True, line_spacing=1.28)


# ==========================================
# SLIDE 17: ⑧ 회고 - 팀 협업 및 역할 분담 ([팀 작성 필요])
# ==========================================
s17 = add_slide_base(
    "팀 협업 및 역할 분담",
    section_tag="⑧ 회고",
    subtitle_text="팀원별 담당 영역과 협업 방식 (작성 대기 빈 틀)",
    slide_num=17
)

for idx in range(4):
    x = 0.65 + idx * 3.05
    add_card(s17, x, 1.55, 2.85, 3.2, border=C_TEAL, border_pt=1.5)
    add_text_lines(s17, x + 0.2, 1.8, 2.45, 2.7, [
        f"팀원 {idx + 1}: [팀 작성 필요]",
        "• 담당 영역: [팀 작성 필요]",
        "• 주요 기여: [팀 작성 필요]",
        "• 사용 기술: [팀 작성 필요]"
    ], font_size=12.5, color=C_BODY, bold_first=True, line_spacing=1.45)

add_card(s17, 0.65, 5.0, 12.0, 1.65, border=C_LINE)
add_text_lines(s17, 0.9, 5.2, 11.5, 1.25, [
    "팀 협업 프로세스 & 소통 방식",
    "[팀 작성 필요] — Git 브랜치 전략, 주간 회의, 데이터·평가 교차 검증 협업 방식을 작성해 주세요."
], font_size=13.5, color=C_DIM, bold_first=True)


# ==========================================
# SLIDE 18: ⑧ 회고 - 3칸 빈 틀 ([팀 작성 필요])
# ==========================================
s18 = add_slide_base(
    "프로젝트 회고: 협업 · 어려웠던 점 · 배운 점",
    section_tag="⑧ 회고",
    subtitle_text="프로젝트를 마치며 팀원들이 직접 작성할 회고 공간입니다.",
    slide_num=18
)

retro_boxes = [
    ("1. 팀 협업에서 잘된 점", C_TEAL),
    ("2. 프로젝트 중 어려웠던 점 & 극복", C_RUST),
    ("3. 프로젝트를 통해 배운 점 & 다음 목표", C_BLUE)
]

for idx, (r_title, col) in enumerate(retro_boxes):
    x = 0.65 + idx * 4.1
    add_card(s18, x, 1.55, 3.85, 5.1, border=col, border_pt=1.5)
    hdr = s18.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.55), Inches(3.85), Inches(0.55))
    style_shape(hdr, col)
    add_text_lines(s18, x + 0.2, 1.68, 3.45, 0.35, [r_title], font_size=14, color=C_CARD, bold_first=True)
    add_text_lines(s18, x + 0.25, 2.4, 3.35, 3.8, [
        "[팀 작성 필요]",
        "",
        "• 내용 1:",
        "• 내용 2:",
        "• 내용 3:"
    ], font_size=14, color=C_DIM, bold_first=True, line_spacing=1.5)


# ==========================================
# SLIDE 19: 부록 - 용어 풀이 표 (Glossary)
# ==========================================
s19 = add_slide_base(
    "부록: 핵심 용어 풀이",
    section_tag="부록 · 용어 정리",
    subtitle_text="발표 대시보드 '용어 정리' 기준",
    slide_num=19
)

tbl_s19 = s19.shapes.add_table(9, 2, Inches(0.65), Inches(1.48), Inches(12.0), Inches(5.25)).table
tbl_s19.columns[0].width = Inches(3.2)
tbl_s19.columns[1].width = Inches(8.8)

rows_s19 = [
    ["용어", "쉬운 설명"],
    ["Precision@3", "추천 상위 3개 중 사람이 '업무에 맞다'고 판정한 비율 (목표 70%)"],
    ["홀드아웃 (Holdout)", "규칙을 만들 때 보지 않은 새로운 업무 10개로 다시 시험한 결과"],
    ["의미 유사도 & 임베딩", "문장의 뜻을 768차원 숫자 묶음으로 바꿔 의미가 비슷한 정도를 0~100점으로 나타낸 값"],
    ["BM25 (키워드 일치)", "업무 설명에 나온 단어가 과정 설명에 얼마나 들어 있는지 계산한 점수"],
    ["리랭커 (Reranker)", "1차로 뽑은 후보를 업무 설명과 한 쌍씩 다시 읽고 순서를 재정렬하는 Cross-Encoder 모델"],
    ["커버리지 (Coverage)", f"업무×수준 {dm['slots_total']}개 조합 중 추천을 3개 다 채운 비율 (현재 {cov_pct:.1f}%)"],
    ["신뢰구간 (95% CI)", "평가를 다시 하면 결과가 나올 수 있는 통계적 범위 (부트스트랩 10,000회 기준)"],
    ["NCS / KSA / 슬롯", f"국가직무능력표준(NCS), 지식·기술·태도(KSA), 업무 하나×수준 하나의 추천 칸({dm['slots_total']}개)"]
]
for r_i, row in enumerate(rows_s19):
    for c_i, val in enumerate(row):
        tbl_s19.cell(r_i, c_i).text = val
style_table(tbl_s19, font_size=12)


# ==========================================
# SLIDE 20: 마무리 - Q&A & 링크 (Dark Theme)
# ==========================================
s20 = add_slide_base(
    "감사합니다 · Q&A",
    section_tag="마무리",
    subtitle_text="인사 교육 지도 프로젝트 결과물 및 소스 코드 안내",
    is_dark=True,
    slide_num=20
)

add_card(s20, 0.65, 1.7, 12.0, 2.7, is_dark=True, border=C_TEAL, border_pt=1.5)
add_text_lines(s20, 1.0, 2.0, 11.3, 2.1, [
    "프로젝트 링크 안내",
    ("• 인터랙티브 발표 대시보드: ", DASHBOARD_URL),
    ("• GitHub 저장소: ", GITHUB_URL),
    ("• 생성 스크립트: ", "scripts/build_presentation_pptx.py  (presentation/src/data.json 기반 자동 생성)")
], font_size=16, color=C_HUD_INK, bold_first=True, line_spacing=1.5)

add_card(s20, 0.65, 4.7, 12.0, 1.7, is_dark=True)
add_text_lines(s20, 1.0, 4.98, 11.3, 1.2, [
    "질의응답 (Q&A)",
    "데이터 수집·전처리, 2단계 추천 알고리즘, 사람 평가 검증 과정에 대해 궁금하신 점을 질문해 주세요."
], font_size=15, color=C_YEL, bold_first=True, line_spacing=1.4)
s20.shapes[-1].text_frame.paragraphs[1].font.color.rgb = C_HUD_INK


# ==========================================
# 5. Speaker Notes Check (Empty if SCRIPT.md absent)
# ==========================================
if has_script:
    with open(SCRIPT_PATH, encoding="utf-8") as sf:
        script_text = sf.read()
    # Future hook if SCRIPT.md is added
else:
    for slide in prs.slides:
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = ""

# Save Presentation
prs.save(OUT_PPTX)
print(f"Successfully generated {OUT_PPTX} with {len(prs.slides)} slides.")
