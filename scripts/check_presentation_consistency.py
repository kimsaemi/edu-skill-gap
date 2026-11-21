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
    ("설명이 풍부해 의미 유사도가 높다(근거 없음)", re.compile(r"설명이\s*풍부해")),
    ("문체가 비슷한 것으로 보입니다(근거 없음)", re.compile(r"문체가\s*비슷한\s*것으로\s*보")),
    ("개선안 우위 단정", re.compile(r"개선안이\s*(?:더\s*)?(?:우수|정확|낫)")),
    ("개선 단정", re.compile(r"(?<!다시\s)(?<!표본이\s작아\s)개선(?:됐|되었)다(?!.*다시 확인할 예정)")),
]

STALE_NUMBERS = [
    ("66.4", re.compile(r"(?<![\d.])66\.4(?![\d.])"), "홀드아웃 1차+2차 합산 이전 옛 지표 (현재 66.1%, 1·2차 66.7%)"),
    ("58.6", re.compile(r"(?<![\d.])58\.6(?![\d.])"), "홀드아웃 2차 이전 옛 지표 (현재 최종 59.3%)"),
    ("57.9", re.compile(r"(?<![\d.])57\.9(?![\d.])"), "홀드아웃 2차 BM25 이전 옛 지표 (현재 BM25 57.6%)"),
    ("72.4", re.compile(r"(?<![\d.])72\.4(?![\d.])"), "이전 옛 지표 (금지값)"),
]



def need(d, *keys):
    """원본 결과 파일에서 값을 꺼낸다. 키가 없으면 고정값으로 대신하지 않고 실패한다."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            raise KeyError("원본 결과 파일에 값이 없음: " + " > ".join(keys))
        cur = cur[k]
    return cur

def load_references():
    ref = {}
    if DATA_JSON_PATH.exists():
        d = json.loads(DATA_JSON_PATH.read_text(encoding="utf-8"))
        ref["courses_total"] = need(d, "kpi", "courses")
        ref["courses_off_topic"] = need(d, "kpi", "off_topic")
        # 추천 후보 수 = 전체 − 제외 (data.json에 따로 저장된 값이 없어 계산한다)
        ref["courses_candidates"] = ref["courses_total"] - ref["courses_off_topic"]
        ref["tasks_count"] = need(d, "recommend", "n_tasks")
        ref["slots_total"] = ref["tasks_count"] * 3  # 270
        ref["slots_lt3"] = need(d, "recommend", "lt3")
        ref["coverage_pct"] = round((ref["slots_total"] - ref["slots_lt3"]) / ref["slots_total"] * 100, 1)

    # 평가 지표들
    p1_file = REPORTS_DIR / "precision_eval_metrics.json"
    if p1_file.exists():
        p1 = json.loads(p1_file.read_text(encoding="utf-8"))
        ref["eval_r1_strict"] = need(p1, "precision_at_3", "strict")

    p2_file = REPORTS_DIR / "precision_eval_round2_metrics.json"
    if p2_file.exists():
        p2 = json.loads(p2_file.read_text(encoding="utf-8"))
        ref["eval_r2_strict"] = need(p2, "precision_at_3", "strict")

    ph1_file = REPORTS_DIR / "precision_eval_holdout_metrics.json"
    if ph1_file.exists():
        ph1 = json.loads(ph1_file.read_text(encoding="utf-8"))
        ref["eval_ho1_strict"] = need(ph1, "precision_at_3", "strict")

    ph2_file = REPORTS_DIR / "precision_eval_holdout2_metrics.json"
    if ph2_file.exists():
        ph2 = json.loads(ph2_file.read_text(encoding="utf-8"))
        ref["eval_ho2_final_strict"] = need(ph2, "final_recommendation", "precision_at_3", "strict")
        ref["eval_ho2_bm25_strict"] = need(ph2, "bm25_recommendation", "precision_at_3", "strict")
        decoy = need(ph2, "decoy_analysis")
        ref["decoy_total"] = need(decoy, "total_evaluations")
        ref["decoy_unfit"] = need(decoy, "unfit_count")
        ref["decoy_pct"] = need(decoy, "filter_success_rate")

    pha_file = REPORTS_DIR / "precision_eval_holdout_all_metrics.json"
    if pha_file.exists():
        pha = json.loads(pha_file.read_text(encoding="utf-8"))
        ref["eval_hoa_strict"] = need(pha, "precision_at_3", "strict")
        ref["eval_hoa_consensus_strict"] = need(pha, "consensus", "strict")
        ref["eval_ho12_strict"] = need(pha, "holdout_12", "precision_at_3", "strict")

    ph3_file = REPORTS_DIR / "precision_eval_holdout3_metrics.json"
    if ph3_file.exists():
        ph3 = json.loads(ph3_file.read_text(encoding="utf-8"))
        if "baseline_recommendation" not in ph3:
            raise KeyError("precision_eval_holdout3_metrics.json 에 'baseline_recommendation' 키가 없습니다.")
        ref["eval_ho3_baseline_strict"] = ph3["baseline_recommendation"]["precision_at_3"]["strict"]
        if "candidate_recommendation" not in ph3:
            raise KeyError("precision_eval_holdout3_metrics.json 에 'candidate_recommendation' 키가 없습니다.")
        ref["eval_ho3_candidate_strict"] = ph3["candidate_recommendation"]["precision_at_3"]["strict"]
        decoy3 = need(ph3, "decoy_analysis")
        ref["decoy3_total"] = need(decoy3, "total_evaluations")
        ref["decoy3_unfit"] = need(decoy3, "unfit_count")
        ref["decoy3_pct"] = need(decoy3, "filter_success_rate")

    dom_file = REPORTS_DIR / "domain_review_metrics.json"
    if dom_file.exists():
        dom = json.loads(dom_file.read_text(encoding="utf-8"))
        ref["domain_precision"] = round(need(dom, "precision", "value") * 100, 1)
        ref["domain_recall"] = round(need(dom, "recall", "value") * 100, 1)

    kpc_file = REPORTS_DIR / "kpc_bias_metrics.json"
    if kpc_file.exists():
        kpc = json.loads(kpc_file.read_text(encoding="utf-8"))
        ref["kpc_catalog_share"] = need(kpc, "summary", "baseline_kpc_catalog_share")
        ref["kpc_top3_share"] = need(kpc, "summary", "baseline_kpc_top3_share")
        h1_levels = need(kpc, "hypotheses", "H1_supply_baseline", "levels")
        if len(h1_levels) < 3 or "kpc_share" not in h1_levels[2]:
            raise KeyError("kpc_bias_metrics.json H1 levels[2]['kpc_share'] (인사 분야 KPC 비중) 누락")
        ref["kpc_hr_domain_share"] = h1_levels[2]["kpc_share"]
        if len(h1_levels) >= 4:
            ref["kpc_pool_share"] = need(h1_levels[3], "kpc_share")
        bm25_comp = need(kpc, "hypotheses", "H3_score_breakdown", "score_components", "bm25_score")
        ref["kpc_bm25_median"] = need(bm25_comp, "kpc", "median")
        ref["other_bm25_median"] = need(bm25_comp, "other", "median")
        h4 = need(kpc, "hypotheses", "H4_human_quality", "kpc_vs_others")
        ref["kpc_human_precision"] = need(h4, "kpc", "strict_precision")
        ref["other_human_precision"] = need(h4, "others_all", "strict_precision")
        if "bootstrap_cluster_ci95" not in h4:
            raise KeyError("kpc_bias_metrics.json H4 'bootstrap_cluster_ci95' 누락")
        ref["kpc_ci95"] = h4["bootstrap_cluster_ci95"]

    return ref


def check_forbidden_expressions(file_path, lines, issues):
    """(b) 금지 표현 검사"""
    in_avoid_table = False
    for idx, line in enumerate(lines, 1):
        # index.html의 const D = ... (raw 카탈로그 json 데이터 블록)은 제외 (template.html과 동일 기준)
        if file_path.name == "index.html" and (line.strip().startswith("const D =") or line.strip().startswith("<script>const D =")):
            continue

        if file_path.name == "SCRIPT.md" and "## 발표에서 피할 표현" in line:
            in_avoid_table = True
        if in_avoid_table and line.startswith("## ") and "발표에서 피할 표현" not in line:
            in_avoid_table = False

        check_line = line
        if in_avoid_table and line.strip().startswith("|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                check_line = "|".join(parts[2:])

        for name, rx in FORBIDDEN_RULES:
            if rx.search(check_line):
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

        # 66.7%가 1·2차 문맥 없이 사용되었는지 검사 (30개 전체 대표값은 66.1%)
        if re.search(r"(?<![\d.])66\.7(?![\d.])", line):
            if "1·2차" not in line and "1, 2차" not in line and "1·2" not in line:
                issues.append({
                    "file": str(file_path),
                    "line": idx,
                    "type": "UNCONTEXTUALIZED_66_7",
                    "found": "66.7% (1·2차 문맥 누락)",
                    "expected": "전체 홀드아웃 합산은 66.1%이며, 66.7%는 '1·2차' 문맥과 함께 사용되어야 함",
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


def check_template_hardcoded_kpc(file_path, lines, issues, ref):
    """template.html 5번 인사이트 카드 내 하드코딩 수치 검사"""
    in_ins5 = False
    for idx, line in enumerate(lines, 1):
        if '5 · 추천이 한 기관에 쏠린다' in line:
            in_ins5 = True
        if in_ins5 and idx > 1025 and '</div>' in line:
            in_ins5 = False
        if in_ins5:
            # KPC 지표 값이 <span> 태그 없이 직접 텍스트로 박혀 있는지 검사 (값은 원본 결과 파일에서 읽음)
            kpc_vals = [f"{ref[k]:.1f}%" for k in ("kpc_hr_domain_share", "kpc_pool_share", "kpc_human_precision", "other_human_precision") if k in ref]
            kpc_vals += [f"{ref[k]:.1f}" for k in ("kpc_bm25_median", "other_bm25_median") if k in ref]
            for val in kpc_vals:
                if val in line and f'>{val}<' not in line:
                    issues.append({
                        "file": str(file_path),
                        "line": idx,
                        "type": "HARDCODED_KPC_VALUE",
                        "found": val,
                        "expected": "data.json에서 값을 채우는 <span> 구조로 대체",
                        "text": line.strip()[:140],
                    })


def check_data_json_values(ref, issues):
    """data.json 안의 지표가 ref(보고서 원본 지표)와 정확히 일치하는지 대조"""
    if not DATA_JSON_PATH.exists():
        issues.append({
            "file": str(DATA_JSON_PATH),
            "line": 0,
            "type": "MISSING_DATA_JSON",
            "found": "파일 없음",
            "expected": "presentation/src/data.json 존재",
            "text": "",
        })
        return

    data = json.loads(DATA_JSON_PATH.read_text(encoding="utf-8"))

    # 1. KPC 비중 및 지표
    kb = data.get("kpc_bias", {})
    checks = [
        ("kpc_bias.kpc_hr_pct", kb.get("kpc_hr_pct"), ref.get("kpc_hr_domain_share")),
        ("kpc_bias.catalog_share", kb.get("catalog_share"), ref.get("kpc_catalog_share")),
        ("kpc_bias.top3_share", kb.get("top3_share"), ref.get("kpc_top3_share")),
        ("kpc_bias.kpc_pool_pct", kb.get("kpc_pool_pct"), ref.get("kpc_pool_share")),
        ("kpc_bias.bm25_kpc", kb.get("bm25_kpc"), ref.get("kpc_bm25_median")),
        ("kpc_bias.bm25_other", kb.get("bm25_other"), ref.get("other_bm25_median")),
        ("kpc_bias.eval_kpc", kb.get("eval_kpc"), ref.get("kpc_human_precision")),
        ("kpc_bias.eval_other", kb.get("eval_other"), ref.get("other_human_precision")),
        ("kpc_bias.ci95_range", kb.get("ci95_range"), ref.get("kpc_ci95")),
    ]

    # 2. 사람 평가 지표
    hoa = data.get("human_eval_rounds", {}).get("holdout_all", {})
    if "eval_hoa_strict" in ref:
        checks.append(("human_eval_rounds.holdout_all.precision_at_3.strict",
                       hoa.get("precision_at_3", {}).get("strict"), ref.get("eval_hoa_strict")))
    if "eval_hoa_consensus_strict" in ref:
        checks.append(("human_eval_rounds.holdout_all.consensus.strict",
                       hoa.get("consensus", {}).get("strict"), ref.get("eval_hoa_consensus_strict")))

    ho = data.get("human_eval_rounds", {}).get("holdout", {})
    if "eval_ho1_strict" in ref:
        checks.append(("human_eval_rounds.holdout.precision_at_3.strict",
                       ho.get("precision_at_3", {}).get("strict"), ref.get("eval_ho1_strict")))

    ho2 = data.get("human_eval_holdout2", {})
    if "eval_ho2_final_strict" in ref:
        checks.append(("human_eval_holdout2.final_recommendation.precision_at_3.strict",
                       ho2.get("final_recommendation", {}).get("precision_at_3", {}).get("strict"), ref.get("eval_ho2_final_strict")))
    if "eval_ho2_bm25_strict" in ref:
        checks.append(("human_eval_holdout2.bm25_recommendation.precision_at_3.strict",
                       ho2.get("bm25_recommendation", {}).get("precision_at_3", {}).get("strict"), ref.get("eval_ho2_bm25_strict")))

    ho3 = data.get("human_eval_holdout3", {})
    if "eval_ho3_baseline_strict" in ref:
        checks.append(("human_eval_holdout3.baseline_recommendation.precision_at_3.strict",
                       ho3.get("baseline_recommendation", {}).get("precision_at_3", {}).get("strict"), ref.get("eval_ho3_baseline_strict")))
    if "eval_ho3_candidate_strict" in ref:
        checks.append(("human_eval_holdout3.candidate_recommendation.precision_at_3.strict",
                       ho3.get("candidate_recommendation", {}).get("precision_at_3", {}).get("strict"), ref.get("eval_ho3_candidate_strict")))

    for name, actual, expected in checks:
        if actual != expected:
            issues.append({
                "file": str(DATA_JSON_PATH),
                "line": 1,
                "type": "DATA_JSON_VALUE_MISMATCH",
                "found": f"{name} = {actual}",
                "expected": f"{expected}",
                "text": f"data.json 의 {name} 항목 값이 원본 지표({expected})와 불일치합니다.",
            })


def check_script_md_values(ref, file_path, lines, issues):
    """SCRIPT.md 본문 내에 ref의 주요 수치가 올바르게 들어있는지 검사"""
    full_text = "\n".join(lines)

    if "kpc_hr_domain_share" in ref:
        kpc_hr_str = f"{ref['kpc_hr_domain_share']:.1f}%"
        if kpc_hr_str not in full_text:
            issues.append({
                "file": str(file_path),
                "line": 0,
                "type": "SCRIPT_VALUE_MISSING",
                "found": f"{kpc_hr_str} 누락",
                "expected": f"SCRIPT.md 본문에 KPC 인사 분야 점유율 {kpc_hr_str} 표기 필요",
                "text": "인사 분야 과정 중 KPC 비중",
            })

    if "coverage_pct" in ref:
        coverage_str = f"{ref['coverage_pct']:.1f}%"
        if coverage_str not in full_text:
            issues.append({
                "file": str(file_path),
                "line": 0,
                "type": "SCRIPT_VALUE_MISSING",
                "found": f"{coverage_str} 누락",
                "expected": f"SCRIPT.md 본문에 추천 커버리지 {coverage_str} 표기 필요",
                "text": "업무마다 추천을 낸다 커버리지",
            })

    if "eval_hoa_strict" in ref:
        hoa_str = f"{ref['eval_hoa_strict']:.1f}%"
        if hoa_str not in full_text:
            issues.append({
                "file": str(file_path),
                "line": 0,
                "type": "SCRIPT_VALUE_MISSING",
                "found": f"{hoa_str} 누락",
                "expected": f"SCRIPT.md 본문에 홀드아웃 합산 정확도 {hoa_str} 표기 필요",
                "text": "홀드아웃 1·2·3차 30개 업무 합산",
            })


def check_pptx_values(ref, prs, issues):
    """PPTX 슬라이드 전체 텍스트에서 ref의 핵심 지표가 누락되거나 틀리지 않았는지 검사"""
    all_slide_texts = []
    for s in prs.slides:
        all_slide_texts.extend(extract_slide_units(s))
    joined_text = " \n ".join(all_slide_texts)

    if "kpc_hr_domain_share" in ref:
        kpc_hr_str = f"{ref['kpc_hr_domain_share']:.1f}%"
        if kpc_hr_str not in joined_text:
            issues.append({
                "file": "presentation/HR_교육지도_발표.pptx",
                "line": 0,
                "type": "PPTX_VALUE_MISSING",
                "found": f"{kpc_hr_str} 누락",
                "expected": f"PPTX 내에 KPC 인사 분야 점유율 {kpc_hr_str} 표기 필요",
                "text": "인사 과정 중 KPC 비중",
            })

    if "eval_hoa_strict" in ref:
        hoa_str = f"{ref['eval_hoa_strict']:.1f}%"
        if hoa_str not in joined_text:
            issues.append({
                "file": "presentation/HR_교육지도_발표.pptx",
                "line": 0,
                "type": "PPTX_VALUE_MISSING",
                "found": f"{hoa_str} 누락",
                "expected": f"PPTX 내에 홀드아웃 합산 정확도 {hoa_str} 표기 필요",
                "text": "홀드아웃 30개 업무 합산",
            })

    if "kpc_top3_share" in ref:
        top3_str = f"{ref['kpc_top3_share']:.1f}%"
        if top3_str not in joined_text:
            issues.append({
                "file": "presentation/HR_교육지도_발표.pptx",
                "line": 0,
                "type": "PPTX_VALUE_MISSING",
                "found": f"{top3_str} 누락",
                "expected": f"PPTX 내에 KPC Top 3 점유율 {top3_str} 표기 필요",
                "text": "최종 추천 Top 3 점유율",
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


def check_pptx(pptx_path, issues, ref=None):
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

    if ref:
        check_pptx_values(ref, prs, issues)

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

            # 66.7% 검사 (1·2차 문맥 확인)
            if re.search(r"(?<![\d.])66\.7(?![\d.])", text):
                if "1·2차" not in text and "1, 2차" not in text and "1·2" not in text and "1·2차" not in slide_full_text:
                    issues.append({
                        "file": f"PPTX 슬라이드 {s_idx}",
                        "line": s_idx,
                        "type": "UNCONTEXTUALIZED_66_7",
                        "found": "66.7% (1·2차 문맥 누락)",
                        "expected": "전체 홀드아웃 합산은 66.1%이며, 66.7%는 '1·2차' 문맥과 함께 사용되어야 함",
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

    # 1. data.json 직접 대조
    check_data_json_values(ref, issues)

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
        if p.name == "SCRIPT.md":
            check_script_md_values(ref, p, lines, issues)
        if p.name == "template.html":
            check_template_hardcoded_kpc(p, lines, issues, ref)

    # PPTX 검사
    pptx_path = ROOT / "presentation" / "HR_교육지도_발표.pptx"
    check_pptx(pptx_path, issues, ref=ref)

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
          f"홀드아웃3차 기본 {ref.get('eval_ho3_baseline_strict')}%, 개선안 {ref.get('eval_ho3_candidate_strict')}%, "
          f"홀드아웃 합산 {ref.get('eval_hoa_strict')}%(1·2차 {ref.get('eval_ho12_strict')}%), 합의 {ref.get('eval_hoa_consensus_strict')}%")
    print(f"  - 가짜 추천 검증: 2차 {ref.get('decoy_total')}건 중 {ref.get('decoy_unfit')}건 부적합({ref.get('decoy_pct')}%), "
          f"3차 {ref.get('decoy3_total')}건 중 {ref.get('decoy3_unfit')}건 부적합({ref.get('decoy3_pct')}%)")
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
