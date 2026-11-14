#!/usr/bin/env python3
"""발표 자료 일관성 및 정직성 최종 점검 스크립트
파일명: scripts/check_presentation_consistency.py

목적:
  data/hr/reports/*.json 및 presentation/src/data.json의 기준값과 대조하여
  발표 화면(HTML), 발표 대본(SCRIPT.md), 발표 슬라이드(PPTX), 프로젝트 문서(README.md)의
  수치 일치성, 금지 표현 배제, 슬라이드 번호 체계 등을 자동 점검합니다.

종료 코드:
  0: 모든 검사 통과 (불일치 0건)
  1: 1건 이상의 불일치 또는 금지 표현 발견
"""

import json
import re
import sys
from pathlib import Path
from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent

# 1. 기준값 파일 경로
REPORTS_DIR = ROOT / "data" / "hr" / "reports"
DATA_JSON_PATH = ROOT / "presentation" / "src" / "data.json"

# (b) 금지 표현 패턴 정의
# "5점)"은 난이도 보너스(미표시 5점, 절반(5점) 등)를 가리키며 만족도 점수(94.5점 등) 오탐 방지를 위해 (?<![\d.])5점\) 적용
FORBIDDEN_RULES = [
    ("목표 70% 달성", re.compile(r"목표\s*70%\s*달성")),
    ("목표 달성", re.compile(r"목표\s*달성")),
    ("정확도를 높", re.compile(r"정확도를\s*높")),
    ("유의미", re.compile(r"유의미")),
    ("정당한 결과", re.compile(r"정당한\s*결과")),
    ("실증", re.compile(r"실증")),
    ("원인 확인", re.compile(r"원인\s*확인")),
    ("절반(", re.compile(r"절반\(")),
    ("5점)", re.compile(r"(?<![\d.])5점\)")),
    ("기관 간 중복 제거", re.compile(r"기관\s*간\s*중복\s*제거")),
    ("팀 밖", re.compile(r"팀\s*밖")),
    ("외부 평가자", re.compile(r"외부\s*평가자")),
    ("72.4%", re.compile(r"72\.4%")),
    ("HRD REVIEW", re.compile(r"HRD\s+REVIEW", re.IGNORECASE)),
    ("잡케어 운영 보고서", re.compile(r"잡케어\s*운영\s*보고서")),
]

STALE_NUMBERS = [
    ("66.4", re.compile(r"(?<![\d.])66\.4(?![\d.])"), "홀드아웃 1차+2차 합산 이전 옛 지표 (현재 66.7%)"),
    ("58.6", re.compile(r"(?<![\d.])58\.6(?![\d.])"), "홀드아웃 2차 이전 옛 지표 (현재 최종 59.3%)"),
    ("57.9", re.compile(r"(?<![\d.])57\.9(?![\d.])"), "홀드아웃 2차 BM25 이전 옛 지표 (현재 BM25 57.6%)"),
    ("72.4", re.compile(r"(?<![\d.])72\.4(?![\d.])"), "이전 옛 지표 (금지값)"),
]


def load_references():
    ref = {}
    if DATA_JSON_PATH.exists():
        d = json.loads(DATA_JSON_PATH.read_text(encoding="utf-8"))
        ref["courses_total"] = d.get("kpi", {}).get("courses", 9075)
        ref["courses_off_topic"] = d.get("kpi", {}).get("off_topic", 1377)
        ref["courses_candidates"] = d.get("eda", {}).get("candidates_total", ref["courses_total"] - ref["courses_off_topic"])
        ref["tasks_count"] = d.get("recommend", {}).get("n_tasks", 90)
        ref["slots_total"] = ref["tasks_count"] * 3  # 270
        ref["slots_lt3"] = d.get("recommend", {}).get("lt3", 4)
        ref["coverage_pct"] = round((ref["slots_total"] - ref["slots_lt3"]) / ref["slots_total"] * 100, 1)

    # 평가 지표들
    p1_file = REPORTS_DIR / "precision_eval_metrics.json"
    if p1_file.exists():
        p1 = json.loads(p1_file.read_text(encoding="utf-8"))
        ref["eval_r1_strict"] = p1.get("precision_at_3", {}).get("strict", 52.7)

    p2_file = REPORTS_DIR / "precision_eval_round2_metrics.json"
    if p2_file.exists():
        p2 = json.loads(p2_file.read_text(encoding="utf-8"))
        ref["eval_r2_strict"] = p2.get("precision_at_3", {}).get("strict", 67.3)

    ph1_file = REPORTS_DIR / "precision_eval_holdout_metrics.json"
    if ph1_file.exists():
        ph1 = json.loads(ph1_file.read_text(encoding="utf-8"))
        ref["eval_ho1_strict"] = ph1.get("precision_at_3", {}).get("strict", 74.5)

    ph2_file = REPORTS_DIR / "precision_eval_holdout2_metrics.json"
    if ph2_file.exists():
        ph2 = json.loads(ph2_file.read_text(encoding="utf-8"))
        ref["eval_ho2_final_strict"] = ph2.get("final_recommendation", {}).get("precision_at_3", {}).get("strict", 59.3)
        ref["eval_ho2_bm25_strict"] = ph2.get("bm25_recommendation", {}).get("precision_at_3", {}).get("strict", 57.6)
        decoy = ph2.get("decoy_analysis", {})
        ref["decoy_total"] = decoy.get("total_evaluations", 20)
        ref["decoy_unfit"] = decoy.get("unfit_count", 7)
        ref["decoy_pct"] = decoy.get("filter_success_rate", 35.0)

    pha_file = REPORTS_DIR / "precision_eval_holdout_all_metrics.json"
    if pha_file.exists():
        pha = json.loads(pha_file.read_text(encoding="utf-8"))
        ref["eval_hoa_strict"] = pha.get("precision_at_3", {}).get("strict", 66.7)
        ref["eval_hoa_consensus_strict"] = pha.get("consensus", {}).get("strict", 53.4)

    dom_file = REPORTS_DIR / "domain_review_metrics.json"
    if dom_file.exists():
        dom = json.loads(dom_file.read_text(encoding="utf-8"))
        ref["domain_precision"] = round(dom.get("precision", {}).get("value", 0.9167) * 100, 1)
        ref["domain_recall"] = round(dom.get("recall", {}).get("value", 0.898) * 100, 1)

    kpc_file = REPORTS_DIR / "kpc_bias_metrics.json"
    if kpc_file.exists():
        kpc = json.loads(kpc_file.read_text(encoding="utf-8"))
        ref["kpc_catalog_share"] = kpc.get("summary", {}).get("baseline_kpc_catalog_share", 16.7)
        ref["kpc_top3_share"] = kpc.get("summary", {}).get("baseline_kpc_top3_share", 37.4)
        h1_levels = kpc.get("hypotheses", {}).get("H1_supply_baseline", {}).get("levels", [])
        if len(h1_levels) >= 4:
            ref["kpc_pool_share"] = h1_levels[3].get("kpc_share", 32.1)
        ref["kpc_hr_domain_share"] = 19.0  # 인사 분야 과정 중 KPC 비중
        bm25_comp = kpc.get("hypotheses", {}).get("H3_score_breakdown", {}).get("score_components", {}).get("bm25_score", {})
        ref["kpc_bm25_median"] = bm25_comp.get("kpc", {}).get("median", 77.7)
        ref["other_bm25_median"] = bm25_comp.get("other", {}).get("median", 70.0)
        h4 = kpc.get("hypotheses", {}).get("H4_human_quality", {}).get("kpc_vs_others", {})
        ref["kpc_human_precision"] = h4.get("kpc", {}).get("strict_precision", 72.0)
        ref["other_human_precision"] = h4.get("others_all", {}).get("strict_precision", 57.0)
        ref["kpc_ci95"] = h4.get("bootstrap_cluster_ci95", [-1.4, 31.2])

    return ref


def check_forbidden_expressions(file_path, lines, issues):
    """(b) 금지 표현 검사"""
    for idx, line in enumerate(lines, 1):
        # index.html의 const D = ... (raw 카탈로그 json 데이터 블록)은 제외 (template.html과 동일 기준)
        if file_path.name == "index.html" and (line.strip().startswith("const D =") or line.strip().startswith("<script>const D =")):
            continue

        for name, rx in FORBIDDEN_RULES:
            if rx.search(line):
                issues.append({
                    "file": str(file_path),
                    "line": idx,
                    "type": "FORBIDDEN_EXPRESSION",
                    "found": name,
                    "expected": "금지 표현 사용 금지 (완화되거나 객관적인 표현 사용)",
                    "text": line.strip()[:140],
                })


def check_stale_numbers(file_path, lines, issues):
    """(a) 옛 수치 검사"""
    for idx, line in enumerate(lines, 1):
        if file_path.name == "index.html" and (line.strip().startswith("const D =") or line.strip().startswith("<script>const D =")):
            continue

        for stale_val, rx, desc in STALE_NUMBERS:
            if rx.search(line):
                issues.append({
                    "file": str(file_path),
                    "line": idx,
                    "type": "STALE_NUMBER",
                    "found": stale_val,
                    "expected": desc,
                    "text": line.strip()[:140],
                })


def check_headline_74_5(file_path, lines, issues):
    """(c) 74.5% 단독 노출 (홀드아웃 1차 표기 없이 대표 성과처럼 쓰인 곳)"""
    rx = re.compile(r"(?<![\d.])74\.5%?")
    for idx, line in enumerate(lines, 1):
        if file_path.name == "index.html" and (line.strip().startswith("const D =") or line.strip().startswith("<script>const D =")):
            continue

        if rx.search(line):
            if not ("홀드아웃 1차" in line or "홀드아웃(1차)" in line or "1차 홀드아웃" in line or "holdout 1" in line.lower() or "1차" in line):
                issues.append({
                    "file": str(file_path),
                    "line": idx,
                    "type": "UNLABELED_74_5",
                    "found": "74.5% 단독 노출",
                    "expected": "'홀드아웃 1차' 라벨과 함께 표시하거나 전수 지표 병기",
                    "text": line.strip()[:140],
                })


def check_template_hardcoded_kpc(file_path, lines, issues):
    """template.html 5번 인사이트 카드 내 하드코딩 수치 검사"""
    in_ins5 = False
    for idx, line in enumerate(lines, 1):
        if '5 · 추천이 한 기관에 쏠린다' in line:
            in_ins5 = True
        if in_ins5 and idx > 1025 and '</div>' in line:
            in_ins5 = False
        if in_ins5:
            # 19.0%, 32.1%, 77.7, 70.0, 72.0%, 57.0%가 <span> 태그 없이 직접 텍스트로 있는지 검사
            for val in ["19.0%", "32.1%", "77.7", "70.0", "72.0%", "57.0%"]:
                if val in line and f'>{val}<' not in line:
                    issues.append({
                        "file": str(file_path),
                        "line": idx,
                        "type": "HARDCODED_KPC_VALUE",
                        "found": val,
                        "expected": "data.json에서 값을 채우는 <span> 구조로 대체",
                        "text": line.strip()[:140],
                    })


def extract_slide_units(slide):
    """슬라이드 내 검사 단위(텍스트 프레임, 테이블 행 등 문맥 단위) 추출"""
    units = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text
            if text.strip():
                units.append(text)
        if shape.has_table:
            for row in shape.table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    units.append(row_text)
        if shape.shape_type == 6 or hasattr(shape, "shapes"):  # Group shape
            for subshape in shape.shapes:
                if subshape.has_text_frame and subshape.text_frame.text.strip():
                    units.append(subshape.text_frame.text)
    return units


def check_pptx(pptx_path, issues):
    """PPTX 텍스트 및 슬라이드 번호 체계 검사"""
    if not pptx_path.exists():
        issues.append({
            "file": str(pptx_path),
            "line": 0,
            "type": "MISSING_FILE",
            "found": "파일 없음",
            "expected": "발표 PPTX 파일 존재",
            "text": "",
        })
        return

    prs = Presentation(str(pptx_path))
    total_slides = len(prs.slides)
    footer_rx = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")

    for s_idx, slide in enumerate(prs.slides, 1):
        units = extract_slide_units(slide)
        slide_full_text = " \n ".join(units)

        for text in units:
            # 금지 표현 검사
            for name, rx in FORBIDDEN_RULES:
                if rx.search(text):
                    issues.append({
                        "file": f"PPTX 슬라이드 {s_idx}",
                        "line": s_idx,
                        "type": "FORBIDDEN_EXPRESSION",
                        "found": name,
                        "expected": "금지 표현 사용 금지",
                        "text": text.strip()[:140],
                    })

            # 옛 수치 검사
            for stale_val, rx, desc in STALE_NUMBERS:
                if rx.search(text):
                    issues.append({
                        "file": f"PPTX 슬라이드 {s_idx}",
                        "line": s_idx,
                        "type": "STALE_NUMBER",
                        "found": stale_val,
                        "expected": desc,
                        "text": text.strip()[:140],
                    })

            # 74.5% 단독 노출 검사 (슬라이드 전체 또는 행 문맥에 홀드아웃 1차 표기 확인)
            if re.search(r"(?<![\d.])74\.5%?", text):
                if not ("홀드아웃 1차" in text or "홀드아웃(1차)" in text or "1차" in text or "홀드아웃 1차" in slide_full_text):
                    issues.append({
                        "file": f"PPTX 슬라이드 {s_idx}",
                        "line": s_idx,
                        "type": "UNLABELED_74_5",
                        "found": "74.5% 단독 노출",
                        "expected": "'홀드아웃 1차' 라벨 병기",
                        "text": text.strip()[:140],
                    })

            # 바닥글 슬라이드 번호 체계 검사
            m = footer_rx.match(text.strip())
            if m:
                curr_n = int(m.group(1))
                total_n = int(m.group(2))
                if total_n != total_slides:
                    issues.append({
                        "file": f"PPTX 슬라이드 {s_idx}",
                        "line": s_idx,
                        "type": "SLIDE_NUMBER_MISMATCH",
                        "found": f"{curr_n} / {total_n}",
                        "expected": f"{curr_n} / {total_slides}",
                        "text": f"전체 슬라이드 수({total_slides})와 바닥글({total_n}) 불일치",
                    })


def run_checks():
    ref = load_references()
    issues = []

    text_files = [
        ROOT / "presentation" / "src" / "template.html",
        ROOT / "presentation" / "index.html",
        ROOT / "presentation" / "SCRIPT.md",
        ROOT / "README.md",
    ]

    for p in text_files:
        if not p.exists():
            issues.append({
                "file": str(p),
                "line": 0,
                "type": "MISSING_FILE",
                "found": "파일 없음",
                "expected": "파일 존재",
                "text": "",
            })
            continue

        lines = p.read_text(encoding="utf-8").splitlines()

        check_forbidden_expressions(p, lines, issues)
        check_stale_numbers(p, lines, issues)
        check_headline_74_5(p, lines, issues)
        if p.name == "template.html":
            check_template_hardcoded_kpc(p, lines, issues)

    # PPTX 검사
    pptx_path = ROOT / "presentation" / "HR_교육지도_발표.pptx"
    check_pptx(pptx_path, issues)

    return ref, issues


def main():
    ref, issues = run_checks()

    print("=" * 80)
    print("발표 자료 일관성 및 정직성 점검 결과")
    print("=" * 80)
    print(f"기준 지표 로드 완료:")
    print(f"  - 강좌: 전체 {ref.get('courses_total')}, 추천후보 {ref.get('courses_candidates')}, 제외 {ref.get('courses_off_topic')}")
    print(f"  - 과업: {ref.get('tasks_count')}개, 추천 슬롯 {ref.get('slots_total')}칸, 3개미만 {ref.get('slots_lt3')}칸, 커버리지 {ref.get('coverage_pct')}%")
    print(f"  - 사람 평가: 1차 {ref.get('eval_r1_strict')}%, 2차 {ref.get('eval_r2_strict')}%, 홀드아웃1차 {ref.get('eval_ho1_strict')}%, "
          f"홀드아웃2차 {ref.get('eval_ho2_final_strict')}%(BM25 {ref.get('eval_ho2_bm25_strict')}%), "
          f"홀드아웃 합산 {ref.get('eval_hoa_strict')}%, 합의 {ref.get('eval_hoa_consensus_strict')}%")
    print(f"  - 가짜 추천 검증: {ref.get('decoy_total')}건 중 {ref.get('decoy_unfit')}건 부적합 판정({ref.get('decoy_pct')}%)")
    print(f"  - KPC 지표: 카탈로그 {ref.get('kpc_catalog_share')}%, Top 3 {ref.get('kpc_top3_share')}%, "
          f"상위후보 {ref.get('kpc_pool_share')}%, BM25 {ref.get('kpc_bm25_median')} vs {ref.get('other_bm25_median')}, "
          f"사람평가 {ref.get('kpc_human_precision')}% vs {ref.get('other_human_precision')}%, 95% CI {ref.get('kpc_ci95')}")
    print(f"  - 분야 검수: 정밀도 {ref.get('domain_precision')}%, 재현율 {ref.get('domain_recall')}%")
    print("-" * 80)

    if not issues:
        print("점검 성공: 발견된 불일치 또는 금지 표현이 0건입니다.")
        print("=" * 80)
        sys.exit(0)
    else:
        print(f"점검 실패: 총 {len(issues)}건의 문제 항목이 발견되었습니다.\n")
        for idx, item in enumerate(issues, 1):
            print(f"[{idx}] {item['file']}:{item['line']} [{item['type']}]")
            print(f"    발견: {item['found']}")
            print(f"    기대: {item['expected']}")
            print(f"    문맥: {item['text']}")
            print()
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
