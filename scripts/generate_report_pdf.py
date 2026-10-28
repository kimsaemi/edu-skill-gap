import sys
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 1. 한글 폰트 등록 (맑은 고딕)
# Windows는 맑은 고딕, 그 외 환경은 설치된 한글 글꼴을 순서대로 시도한다.
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"),
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
]
FONT_REGULAR, FONT_BOLD = next(
    (r, b) for r, b in FONT_CANDIDATES if os.path.exists(r) and os.path.exists(b)
)

pdfmetrics.registerFont(TTFont("Malgun", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("Malgun-Bold", FONT_BOLD))

# PDF 저장 경로 (저장소 루트)
OUTPUT_PDF = Path(__file__).resolve().parents[1] / "NCS_Demand_Analysis_Report.pdf"

# Page layout callback for headers and footers
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Malgun", 8.5)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Top line & title)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(36, 842 - 36, 595 - 36, 842 - 36)
        self.drawString(36, 842 - 30, "NCS 전체 데이터 기반 요구 역량 EDA 분석 및 대시보드 구축 보고서")
        
        # Footer (Bottom line & page numbers)
        self.line(36, 45, 595 - 36, 45)
        self.drawString(36, 30, "수도권 대학평생교육원 기반 기본직무 마이크로디그리 설계 프로젝트")
        page_str = f"페이지 {self._pageNumber} / {page_count}"
        self.drawRightString(595 - 36, 30, page_str)
        self.restoreState()

def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=50,
        bottomMargin=55
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_title = ParagraphStyle(
        "DocTitle",
        fontName="Malgun-Bold",
        fontSize=20,
        leading=26,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=6
    )
    
    style_subtitle = ParagraphStyle(
        "DocSubtitle",
        fontName="Malgun",
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceAfter=15
    )
    
    style_h1 = ParagraphStyle(
        "Heading1_Custom",
        fontName="Malgun-Bold",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#1E40AF"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    style_h2 = ParagraphStyle(
        "Heading2_Custom",
        fontName="Malgun-Bold",
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    style_body = ParagraphStyle(
        "Body_Custom",
        fontName="Malgun",
        fontSize=9.5,
        leading=14.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )

    style_bullet = ParagraphStyle(
        "Bullet_Custom",
        fontName="Malgun",
        fontSize=9.2,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=12,
        spaceAfter=4
    )

    style_cell = ParagraphStyle(
        "TableCell",
        fontName="Malgun",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B")
    )

    style_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Malgun-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0F172A")
    )

    style_cell_header = ParagraphStyle(
        "TableHeader",
        fontName="Malgun-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.white,
        alignment=1
    )

    story = []

    # Document Header Title
    story.append(Paragraph("NCS 전체 데이터 기반 요구 역량 EDA 분석 및 대시보드 보고서", style_title))
    story.append(Paragraph("산업/직무별 요구 역량 인터랙티브 대시보드 구축과 직업교육·HRD·취업준비생 시사점 도출", style_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=12))

    # 2026-10-25 정정 안내
    story.append(Paragraph("<b>[2026-10-25 정정 안내] 먼저 읽어 주세요</b>", style_h2))
    for _line in [
        "이 보고서는 data/processed/ncs_1360_units.csv(원래 dashboard.html에 들어 있던 데이터)를 근거로 작성되었습니다. 이 데이터는 <b>공식 NCS가 아니라</b>, 271개 직무에 같은 틀(레벨 1~5, 똑같은 기술·태도 문구, 고정 권장시간)을 적용해 만든 <b>예시 데이터</b>입니다.",
        "• 데이터에는 Level 1~5만 있고 각 레벨이 정확히 20%입니다. 이전 판의 레벨 비중(10% / 48% / 32% / 10%)과 Level 6~8 내용은 데이터로 뒷받침되지 않아 정정했습니다.",
        "• 산업별 레벨 비중 차이도 데이터에서 확인되지 않습니다(모든 직무가 같은 구조).",
        "• KSA 표, 공통·특화 역량, 학습 로드맵, '온라인 60% + 오프라인 40%', '40시간 이탈 한계선' 등은 데이터 분석 결과가 아니라 팀의 기획 가설입니다.",
        "• 공식 NCS 능력단위·능력단위요소·KSA를 다시 수집한 뒤 재분석해야 합니다.",
    ]:
        story.append(Paragraph(_line, style_bullet if _line.startswith("•") else style_body))
    story.append(Spacer(1, 10))

    # Section 1
    story.append(Paragraph("1. 🏛️ 산업군(대분류 24개 분야) 역량 프로파일 분석", style_h1))
    story.append(Paragraph("아래 표는 레벨 구간별 역할 정의와 팀의 교육 설계 가설입니다. <b>비중 열은 데이터로 확인할 수 없어 '확인 불가'로 정정</b>했습니다(사용한 데이터는 Level 1~5가 각각 20%인 예시 데이터).", style_body))

    # Table 1: Level Distribution
    t1_data = [
        [
            Paragraph("레벨 구분", style_cell_header),
            Paragraph("난이도 및 역할 정의", style_cell_header),
            Paragraph("비중", style_cell_header),
            Paragraph("주요 특징 및 시사점", style_cell_header)
        ],
        [
            Paragraph("Level 1~2", style_cell_bold),
            Paragraph("단순 보조 및 입문 실무", style_cell),
            Paragraph("확인 불가", style_cell),
            Paragraph("(가설) 업무 자동화(RPA/AI) 도입으로 단독 과정 수요 감소", style_cell)
        ],
        [
            Paragraph("Level 3~4", style_cell_bold),
            Paragraph("<b>독립적 실무 수행 (주니어)</b>", style_cell),
            Paragraph("확인 불가", style_cell),
            Paragraph("<b>직업교육 및 하이브리드 재교육의 핵심 공략 구간 (30~45H)</b>", style_cell)
        ],
        [
            Paragraph("Level 5~6", style_cell_bold),
            Paragraph("<b>복합 문제 해결 및 기획 (중급)</b>", style_cell),
            Paragraph("확인 불가", style_cell),
            Paragraph("기업 HRD 재직자 딥스킬링(Upskilling) 및 마이크로디그리 타겟", style_cell)
        ],
        [
            Paragraph("Level 7~8", style_cell_bold),
            Paragraph("전략 수립 및 최고 전문가 (시니어)", style_cell),
            Paragraph("확인 불가 (데이터에 Level 6~8 없음)", style_cell),
            Paragraph("(가설) 최고경영진/R&D 전략 과정으로 소수 정예 과정 운영", style_cell)
        ]
    ]

    t1 = Table(t1_data, colWidths=[70, 140, 45, 268])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E40AF")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F8FAFC"), colors.white]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # Sub-item: Industry Profile Characteristics
    story.append(Paragraph("산업군별 프로파일 특성:", style_h2))
    story.append(Paragraph("• <strike><b>기술 집약형 산업 (정보통신, 전기·전자, 바이오)</b>: Level 4~6 비율이 70% 이상</strike> → <b>정정: 데이터에서 확인되지 않음</b> (모든 직무가 Level 1~5 각 1개 단위로 동일한 구조)", style_bullet))
    story.append(Paragraph("• <b>기본 직무 및 서비스 산업 (경영·회계, 유통·물류, 마케팅, 인사)</b>: Level 3~4 중심의 실무 단위가 다수 분포하며, 최근 디지털 전환(DX) 및 AI 융합 리스킬링(Reskilling) 요구가 급증하고 있습니다.", style_bullet))
    story.append(Spacer(1, 12))

    # Section 2
    story.append(Paragraph("2. 🔠 지식·기술·태도(KSA) 텍스트 마이닝 분석", style_h1))
    story.append(Paragraph("NCS 세부 능력단위 요소의 KSA 텍스트 데이터를 마이닝하여 3대 핵심 구조로 분류하였습니다.", style_body))

    t2_data = [
        [Paragraph("구분", style_cell_header), Paragraph("핵심 구성 요소 및 마이닝 결과", style_cell_header)],
        [
            Paragraph("지식 (Knowledge)", style_cell_bold),
            Paragraph("• 근로기준법 및 노무 법령 지식<br/>• 기업 세무회계 및 원천징수 기준<br/>• WMS/SCM 물류 체계 및 ROAS 산출 공식<br/>• 생성형 AI 프롬프트 원리 및 데이터 구조", style_cell)
        ],
        [
            Paragraph("기술 (Skill)", style_cell_bold),
            Paragraph("• Python / SQL 기반 데이터 분석 및 처리<br/>• Excel BI 실무 대시보드 자동화 구축<br/>• 생성형 AI 활용 기획서 및 스마트 보고서 작성<br/>• SNS 숏폼 영상 기획 및 컷편집", style_cell)
        ],
        [
            Paragraph("태도 (Attitude)", style_cell_bold),
            Paragraph("• 객관적 데이터에 기반한 의사결정 태도<br/>• 세법 및 노무 관련 규정·윤리 준수 의지<br/>• 타 부서와의 유연한 커뮤니케이션 및 협업 태도", style_cell)
        ]
    ]

    t2 = Table(t2_data, colWidths=[120, 403])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F8FAFC"), colors.white]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 12))

    # Section 3
    story.append(Paragraph("3. 🌐 산업 간 공통 핵심 역량(Cross-Industry) vs 도메인 특화 역량", style_h1))
    story.append(Paragraph("분석 결과, 전 산업군을 관통하는 <b>범용 디지털 역량(Cross-Industry Core Skills)</b>과 <b>도메인 고유 역량</b>이 명확히 구별됩니다.", style_body))

    t3_data = [
        [Paragraph("구분", style_cell_header), Paragraph("공통 핵심 역량 (Cross-Industry)", style_cell_header), Paragraph("도메인 특화 역량 (Domain-Specific)", style_cell_header)],
        [
            Paragraph("개념", style_cell_bold),
            Paragraph("24개 대분류 산업군 전반에 공통 적용되는 융합 스킬", style_cell),
            Paragraph("특정 직무 수행에만 필수적인 고유 실무 역량", style_cell)
        ],
        [
            Paragraph("주요 항목", style_cell_bold),
            Paragraph("• 생성형 AI 활용 및 프롬프트 엔지니어링<br/>• 데이터 시각화 및 BI 대시보드 구축<br/>• 노무/개인정보보호 준법(Compliance)", style_cell),
            Paragraph("• (회계) 부가가치세 전산 모의 신고<br/>• (마케팅) ROAS 최적화 세팅<br/>• (물류) 풀필먼트 WMS 동선 최적화", style_cell)
        ],
        [
            Paragraph("교육 적용", style_cell_bold),
            Paragraph("온라인 K-MOOC 공통 기초 모듈 연계 (온라인 60%)", style_cell),
            Paragraph("평생교육원 오프라인 실습 & 케이스 스터디 (오프라인 40%)", style_cell)
        ]
    ]

    t3 = Table(t3_data, colWidths=[70, 226, 227])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2563EB")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F8FAFC"), colors.white]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t3)
    story.append(Spacer(1, 12))

    # Section 4
    story.append(Paragraph("4. 🗺️ 직무별 역량 체계도 & 학습 로드맵 (Curriculum Roadmap)", style_h1))
    story.append(Paragraph("학습자의 직무 숙련도와 목적에 맞춘 2-Track 스택형 학위 로드맵 모델입니다.", style_body))

    story.append(Paragraph("• <b>주니어 Track (Level 3~4: 30~40시간 단기 모듈)</b>", style_h2))
    story.append(Paragraph("  - <b>목표</b>: 기본 직무 입문 및 실무 즉시 투입 능력 확보<br/>  - <b>구성</b>: 온라인 60% (KSA 이론) + 오프라인 40% (평생교육원 실습 & 템플릿 제작)<br/>  - <b>결과물</b>: 소단위 마이크로 크레덴셜 (Micro-credential) 이수증 발급", style_bullet))

    story.append(Paragraph("• <b>시니어/리더 Track (Level 5~6: 60~80시간 심화 과정)</b>", style_h2))
    story.append(Paragraph("  - <b>목표</b>: 데이터 기반 전략 수립 및 리더십 구축<br/>  - <b>구성</b>: 비즈니스 데이터 분석 케이스 스터디 + 기업 현장 문제 해결 프로젝트<br/>  - <b>결과물</b>: 대학 평생교육원 학점인정 마이크로디그리 (Micro-degree)", style_bullet))
    story.append(Spacer(1, 12))

    # Section 5
    story.append(Paragraph("5. 💡 최종 결론 및 시사점 (Actionable Strategy)", style_h1))
    
    t4_data = [
        [Paragraph("타겟 대상", style_cell_header), Paragraph("핵심 시사점 및 전략 과제 (Action Plan)", style_cell_header)],
        [
            Paragraph("🎓 직업교육 기획자<br/>(대학 평생교육원)", style_cell_bold),
            Paragraph("<b>[하이브리드 재교육 모델 표준화]</b><br/>성인학습자의 40시간 이탈 한계선을 극복하기 위해 <b>'온라인 60%(평일 야간) + 오프라인 40%(격주 토요일 실습)'</b> 혼합 모델을 공식 표준으로 채택하고, NCS L3~L4 기반 K-MOOC 자원 연계를 확장해야 합니다.", style_cell)
        ],
        [
            Paragraph("🏢 기업 인재개발<br/>(HRD 담당자)", style_cell_bold),
            Paragraph("<b>[Cross-Industry Skill 기반 Reskilling]</b><br/>부서별 개별 교육 대신 생성형 AI, 데이터 시각화, 노무 준법 등 전 직무 공통 스킬 교육을 표준화하여 조직 전체의 생산성을 제고할 수 있습니다.", style_cell)
        ],
        [
            Paragraph("🎯 취업준비생 및 재직자<br/>(Learners)", style_cell_bold),
            Paragraph("<b>[Targeted Skill Gap 학습]</b><br/>NCS Level 3~4 실무 단위 중심의 단기 모듈을 이수함으로써 최소 시간 내 포트폴리오를 완성하고 실무 적합성을 입증할 수 있습니다.", style_cell)
        ]
    ]

    t4 = Table(t4_data, colWidths=[130, 393])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F8FAFC"), colors.white]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('TOPPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t4)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF Successfully generated at: {OUTPUT_PDF}")

if __name__ == "__main__":
    build_pdf()
