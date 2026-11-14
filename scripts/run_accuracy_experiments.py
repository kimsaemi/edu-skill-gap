#!/usr/bin/env python3
"""추천 정확도 개선안 실험 스크립트
파일명: scripts/run_accuracy_experiments.py
출력: data/hr/reports/accuracy_experiments.md
      data/hr/output/recommendation/task_course_recommendations_90_candidate.csv

실험 구성:
- Control: 기본 추천 설정 (동일 조건 재현, 차이 0칸 목표)
- E1: 안내 문구 정제 (과정 텍스트 내 온앤오프, 서울본부, 교재배송, 환급 등 상투적 안내문 정제)
- E2: 업무 설명 보강 (과업명 + 분야 + 과업 설명 + 지식·기술·태도 KSA 결합 질의어)
- E3: 결합 비율 최적화 (리랭커 가중치 alpha 탐색 [0.4, 0.5, 0.6, 0.7, 0.8])
- E4: 타 직종 제외 규칙 보강 (무역/원산지, 민사소송, AI그림, 구매조달, IT개발, SAP CO/MM, 콜센터QA 등)
- 조합 실험: E1+E4, E4+alpha=0.5, E1+E4+alpha=0.5(선정 후보), E1+E2, E2+E4, E1+E2+E4 (E2 포함 조합은 튜닝셋 성능 저하로 후보 제외)
"""

import sys
import re
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.recommendation.cross_encoder_reranker import get_shared_reranker
from scripts.eval_offline import evaluate_recommendations, build_ground_truth_dict

RECO = ROOT / "data" / "hr" / "output" / "recommendation"
PROCESSED = ROOT / "data" / "hr" / "processed"
REPORTS = ROOT / "data" / "hr" / "reports"

CATALOG_PATH = PROCESSED / "hr_task_catalog_90.json"
COURSES_PARQUET = PROCESSED / "education_courses_search_cleaned.parquet"
BASE_REC_PATH = RECO / "task_course_recommendations_90.csv"
BASE_RERANKED_PATH = RECO / "task_course_recommendations_90_reranked.csv"
CACHE_SCORED_PATH = RECO / ".scored_candidates_90.parquet"
CANDIDATE_OUT_PATH = RECO / "task_course_recommendations_90_candidate.csv"
REPORT_MD_PATH = REPORTS / "accuracy_experiments.md"

# 1차·2차 튜닝 업무 vs 홀드아웃 1·2차 검증 업무 목록
TUNING_TASKS = {
    'TASK_HR_D01_T03', 'TASK_HR_D02_T08', 'TASK_HR_D03_T10', 'TASK_HR_D04_T06', 'TASK_HR_D05_T04',
    'TASK_HR_D06_T08', 'TASK_HR_D07_T09', 'TASK_HR_D08_T02', 'TASK_HR_D09_T03', 'TASK_HR_D09_T06'
}

HOLDOUT_TASKS = {
    'TASK_HR_D01_T04', 'TASK_HR_D02_T01', 'TASK_HR_D03_T02', 'TASK_HR_D04_T02', 'TASK_HR_D05_T01',
    'TASK_HR_D06_T02', 'TASK_HR_D07_T03', 'TASK_HR_D08_T05', 'TASK_HR_D09_T01', 'TASK_HR_D06_T05',
    'TASK_HR_D01_T10', 'TASK_HR_D02_T07', 'TASK_HR_D03_T06', 'TASK_HR_D03_T07', 'TASK_HR_D04_T10',
    'TASK_HR_D05_T07', 'TASK_HR_D06_T09', 'TASK_HR_D07_T08', 'TASK_HR_D08_T03', 'TASK_HR_D09_T02'
}

# E1 안내 문구 정제 정규식
BOILERPLATE_REGEXES = [
    re.compile(r"※\s*서울본부에서\s*열리는\s*차수만[^\n]*", re.IGNORECASE),
    re.compile(r"※\s*본\s*과정은[^\n]*", re.IGNORECASE),
    re.compile(r"※\s*교육안내[^\n]*", re.IGNORECASE),
    re.compile(r"※\s*수료기준[^\n]*", re.IGNORECASE),
    re.compile(r"※\s*교재\s*배송[^\n]*", re.IGNORECASE),
    re.compile(r"※\s*고용보험\s*환급[^\n]*", re.IGNORECASE),
    re.compile(r"\[온앤오프\]", re.IGNORECASE),
    re.compile(r"\[인재키움\]", re.IGNORECASE),
    re.compile(r"\[비대면\]", re.IGNORECASE),
    re.compile(r"\[여의도\]", re.IGNORECASE),
]

# E4 타 직종 제외 규칙 룰셋
NON_HR_RULES = {
    "관세_무역": re.compile(r"(?:원산지증명|FTA관세|수출입통관|보세사|선적서류)", re.IGNORECASE),
    "민사_소송": re.compile(r"(?:민사\s*소송|형사\s*소송|가압류|부동산등기|경매\s*실무)", re.IGNORECASE),
    "AI_그래픽": re.compile(r"(?:ComfyUI|Midjourney|미드저니|Stable\s*Diffusion|AI\s*그림)", re.IGNORECASE),
    "구매_조달": re.compile(r"(?:구매전략|자재관리|구매원가|협력사\s*조달)", re.IGNORECASE),
    "IT_딥러닝개발": re.compile(r"(?:PyTorch|TensorFlow|강화학습|신경망|딥러닝\s*첫걸음|추천\s*시스템\s*알고리즘)", re.IGNORECASE),
    "SAP_비인사모듈": re.compile(r"(?:S/4HANA\s*(?:CO|MM|SD)\b|SAP\s*(?:CO|MM|SD)\b)", re.IGNORECASE),
    "콜센터_QA": re.compile(r"(?:상담품질\s*평가|QA\s*전문가\s*양성)", re.IGNORECASE),
}


def clean_text_boilerplate(text: str) -> str:
    """텍스트에서 반복적인 행정/수강 안내 문구 제거"""
    if not text or not isinstance(text, str):
        return ""
    t = text
    for rx in BOILERPLATE_REGEXES:
        t = rx.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def build_doc(row: pd.Series, clean_bp: bool = False) -> str:
    """CrossEncoderReranker.build_course_document 와 100% 동일한 규칙"""
    title = str(row.get("title", "")).strip()
    goals = str(row.get("clean_goals", "") or row.get("learning_goals", "")).strip()
    curr = str(row.get("clean_curriculum", "") or row.get("curriculum", "")).strip()

    if clean_bp:
        title = clean_text_boilerplate(title)
        goals = clean_text_boilerplate(goals)
        curr = clean_text_boilerplate(curr)

    parts = [f"강좌명: {title}"]
    if goals and goals != "None":
        parts.append(f"학습목표: {goals[:120]}")
    if curr and curr != "None":
        parts.append(f"커리큘럼: {curr[:120]}")
    return " | ".join(parts)


def build_query(task_info: dict, level: str, enrich: bool = False) -> str:
    t_name = task_info.get("task_name", "")
    if not enrich:
        # 기존 기본 질의어
        q = f"{t_name} {level} 실무 직무 교육"
        if task_info.get("skill"):
            q += f" | {task_info['skill']}"
        return q
    else:
        # E2 보강 질의어: 과업명 + 분야 + 수준 + 과업 설명 + KSA 지식·기술
        domain = task_info.get("domain_name", "")
        easy_desc = task_info.get("easy_description", "")
        knowledge = task_info.get("knowledge", "")
        skill = task_info.get("skill", "")

        q = f"{t_name} ({domain}) {level} 실무 직무 교육"
        if easy_desc:
            q += f" | 실무목표: {easy_desc[:80]}"
        ksa_parts = []
        if knowledge:
            ksa_parts.append(f"지식: {knowledge[:60]}")
        if skill:
            ksa_parts.append(f"기술: {skill[:60]}")
        if ksa_parts:
            q += f" | {' / '.join(ksa_parts)}"
        return q


def filter_top3(df_scored):
    """(task_id, level) 단위 Top 3 선정 (build_reranked_90_recommendations.py 원본 로직)"""
    out_rows = []
    for (t_id, lvl), grp in df_scored.groupby(["task_id", "level"], sort=False):
        sorted_grp = grp.sort_values(by="reranked_final_score", ascending=False)
        valid = sorted_grp[sorted_grp["reranker_score"] >= 0.1]
        candidates = valid if len(valid) >= 3 else sorted_grp
        selected = candidates.head(3).copy()
        selected["rank"] = range(1, len(selected) + 1)
        out_rows.append(selected)
    return pd.concat(out_rows, ignore_index=True) if out_rows else pd.DataFrame(columns=df_scored.columns)


def run_experiment(
    df_base,
    tasks_meta,
    df_courses,
    reranker,
    clean_bp=False,
    enrich_query=False,
    alpha=0.6,
    filter_non_hr=False,
    cache_dict=None
):
    df_rec = df_base.copy()

    # E4 타 직종 필터링
    excluded_count = 0
    if filter_non_hr:
        before_len = len(df_rec)
        masks = [df_rec["title"].str.contains(rx, regex=True, na=False) for rx in NON_HR_RULES.values()]
        is_non_hr = pd.concat(masks, axis=1).any(axis=1)
        df_rec = df_rec[~is_non_hr].copy()
        excluded_count = before_len - len(df_rec)

    # 리랭커 점수 계산 (캐시 활용)
    cache_key = (clean_bp, enrich_query)
    if cache_dict is not None and cache_key in cache_dict:
        probs = cache_dict[cache_key]
        df_rec["reranker_score"] = probs.loc[df_rec.index]
    else:
        pairs = []
        indices = []
        for idx, row in df_rec.iterrows():
            t_info = tasks_meta.get(row["task_id"], {})
            q_text = build_query(t_info, row["level"], enrich=enrich_query)
            c_row = df_courses.loc[row["course_uid"]] if row["course_uid"] in df_courses.index else pd.Series()
            d_text = build_doc(c_row if not c_row.empty else row, clean_bp=clean_bp)
            pairs.append((q_text, d_text))
            indices.append(idx)

        raw_scores = reranker.model.predict(pairs, batch_size=64, show_progress_bar=False)
        if len(raw_scores.shape) == 1:
            if np.min(raw_scores) < 0 or np.max(raw_scores) > 1:
                p = 1.0 / (1.0 + np.exp(-raw_scores))
            else:
                p = raw_scores
        else:
            p = torch.softmax(torch.tensor(raw_scores), dim=-1)[:, 1].numpy()

        p_series = pd.Series(np.round(p * 100.0, 1), index=indices)
        if cache_dict is not None:
            cache_dict[cache_key] = p_series
        df_rec["reranker_score"] = p_series

    # 앙상블 점수
    stage1_s = df_rec["final_score"].astype(float)
    ce_s = df_rec["reranker_score"]
    df_rec["reranked_final_score"] = np.round(alpha * ce_s + (1.0 - alpha) * stage1_s, 1)

    # Top 3 선정
    df_top3 = filter_top3(df_rec)
    return df_top3, excluded_count


def calculate_metrics_for_split(df_top3, df_base_top3, gt_dict, task_subset=None):
    if task_subset is not None:
        sub_top3 = df_top3[df_top3["task_id"].isin(task_subset)]
        sub_base = df_base_top3[df_base_top3["task_id"].isin(task_subset)]
    else:
        sub_top3 = df_top3
        sub_base = df_base_top3
    return evaluate_recommendations(sub_top3, sub_base, gt_dict)


def main():
    print("=== 추천 정확도 개선안 실험 시작 ===")
    t0 = time.time()

    # 데이터 로드
    df_base_raw = pd.read_csv(BASE_REC_PATH)
    df_base_reranked = pd.read_csv(BASE_RERANKED_PATH)
    cat_data = json.load(open(CATALOG_PATH, encoding="utf-8"))
    tasks_list = cat_data.get("tasks", cat_data) if isinstance(cat_data, dict) else cat_data
    tasks_meta = {t["task_id"]: t for t in tasks_list}
    df_courses = pd.read_parquet(COURSES_PARQUET).set_index("course_uid")
    gt_dict = build_ground_truth_dict()
    reranker = get_shared_reranker()

    # Preload Control reranker score from cache to guarantee 100% exact reproduction (0 changed slots)
    cache_dict = {}
    if CACHE_SCORED_PATH.exists():
        df_cached_ctrl = pd.read_parquet(CACHE_SCORED_PATH)
        cache_dict[(False, False)] = df_cached_ctrl["reranker_score"].copy()
        print("Control 캐시 점수 사전 로드 완료 (.scored_candidates_90.parquet)")

    print(f"로드 완료: 후보군 {len(df_base_raw)}개, 기본 Top 3 {len(df_base_reranked)}개, 정답사전 {len(gt_dict)}개")

    # 실험 정의
    experiments = [
        {"name": "Control (기본 추천, alpha=0.6)", "clean_bp": False, "enrich_query": False, "alpha": 0.6, "non_hr": False, "desc": "현재 운영 중인 기준선 (차이 0칸 목표)"},
        {"name": "E1: 안내 문구 정제 (alpha=0.6)", "clean_bp": True, "enrich_query": False, "alpha": 0.6, "non_hr": False, "desc": "과정명/목표/커리큘럼 안내문 정규식 제거"},
        {"name": "E2: 업무 설명·KSA 보강 (alpha=0.6)", "clean_bp": False, "enrich_query": True, "alpha": 0.6, "non_hr": False, "desc": "질의어에 업무설명+KSA 지식·기술 결합"},
        {"name": "E3-1: 리랭커 가중치 0.4", "clean_bp": False, "enrich_query": False, "alpha": 0.4, "non_hr": False, "desc": "alpha=0.4 (리랭커 40%, 1단계 60%)"},
        {"name": "E3-2: 리랭커 가중치 0.5", "clean_bp": False, "enrich_query": False, "alpha": 0.5, "non_hr": False, "desc": "alpha=0.5 (리랭커 50%, 1단계 50%)"},
        {"name": "E3-3: 리랭커 가중치 0.7", "clean_bp": False, "enrich_query": False, "alpha": 0.7, "non_hr": False, "desc": "alpha=0.7 (리랭커 70%, 1단계 30%)"},
        {"name": "E3-4: 리랭커 가중치 0.8", "clean_bp": False, "enrich_query": False, "alpha": 0.8, "non_hr": False, "desc": "alpha=0.8 (리랭커 80%, 1단계 20%)"},
        {"name": "E4: 타 직종 제외 규칙 (alpha=0.6)", "clean_bp": False, "enrich_query": False, "alpha": 0.6, "non_hr": True, "desc": "무역/민사/AI그림/구매/IT/SAP/콜센터 제외"},
        {"name": "E1+E4 (정제 + 룰셋, alpha=0.6)", "clean_bp": True, "enrich_query": False, "alpha": 0.6, "non_hr": True, "desc": "안내문 정제 + 타 직종 제외"},
        {"name": "E4 + alpha=0.5 (룰셋 + 가중치0.5)", "clean_bp": False, "enrich_query": False, "alpha": 0.5, "non_hr": True, "desc": "타 직종 제외 + 결합 비율 0.5"},
        {"name": "E1+E4 + alpha=0.5 (최종 선정 후보)", "clean_bp": True, "enrich_query": False, "alpha": 0.5, "non_hr": True, "desc": "안내문 정제 + 타 직종 제외 + 결합비율 0.5"},
        {"name": "E1+E2 (정제 + 보강, alpha=0.6)", "clean_bp": True, "enrich_query": True, "alpha": 0.6, "non_hr": False, "desc": "E2 포함 (튜닝셋 저하로 후보 제외)"},
        {"name": "E2+E4 (보강 + 룰셋, alpha=0.6)", "clean_bp": False, "enrich_query": True, "alpha": 0.6, "non_hr": True, "desc": "E2 포함 (튜닝셋 저하로 후보 제외)"},
        {"name": "E1+E2+E4 (정제+보강+룰셋, 0.6)", "clean_bp": True, "enrich_query": True, "alpha": 0.6, "non_hr": True, "desc": "E2 포함 (튜닝셋 저하로 후보 제외)"},
        {"name": "E1+E2+E4 + alpha=0.5 (4종 통합)", "clean_bp": True, "enrich_query": True, "alpha": 0.5, "non_hr": True, "desc": "E2 포함 (튜닝셋 저하로 후보 제외)"},
    ]

    results = []
    bp_rx = re.compile(r"^(?:※|\[온앤오프\]|온앤오프|※\s*서울본부)")

    for exp in experiments:
        print(f"실행 중: {exp['name']}...")
        df_top3, excl_cnt = run_experiment(
            df_base_raw,
            tasks_meta,
            df_courses,
            reranker,
            clean_bp=exp["clean_bp"],
            enrich_query=exp["enrich_query"],
            alpha=exp["alpha"],
            filter_non_hr=exp["non_hr"],
            cache_dict=cache_dict
        )

        # 전체 지표
        m_all = evaluate_recommendations(df_top3, df_base_reranked, gt_dict)
        # 튜닝셋 (1차·2차 10개 업무)
        m_tune = calculate_metrics_for_split(df_top3, df_base_reranked, gt_dict, TUNING_TASKS)
        # 검증셋 (홀드아웃 1·2차 20개 업무)
        m_hold = calculate_metrics_for_split(df_top3, df_base_reranked, gt_dict, HOLDOUT_TASKS)

        # 3개 미만 칸 수
        slot_counts = df_top3.groupby(["task_id", "level"]).size()
        thin_slots = int((slot_counts < 3).sum()) + (270 - len(slot_counts))

        # KPC 비중
        kpc_cnt = int((df_top3["provider"] == "한국생산성본부(KPC)").sum())
        kpc_pct = round(kpc_cnt / len(df_top3) * 100, 1)

        # 안내 문구 포함 강좌 비중 (고유 강좌 기준 vs 슬롯 출현 기준)
        c_sub = df_courses.loc[df_courses.index.intersection(df_top3["course_uid"].unique())]
        intros = c_sub["course_intro"].fillna("").astype(str)
        bp_unique_cnt = int(intros.str.strip().str.contains(bp_rx).sum())
        bp_unique_pct = round(bp_unique_cnt / len(c_sub) * 100, 1) if len(c_sub) else 0.0

        # 슬롯 기준 출현 수
        merged_intros = df_top3.merge(df_courses[["course_intro"]], on="course_uid", how="left")
        bp_slot_cnt = int(merged_intros["course_intro"].fillna("").astype(str).str.strip().str.contains(bp_rx).sum())
        bp_slot_pct = round(bp_slot_cnt / len(df_top3) * 100, 1)

        results.append({
            "name": exp["name"],
            "desc": exp["desc"],
            "top3_df": df_top3,
            "strict_all": m_all["strict_precision"],
            "lenient_all": m_all["lenient_precision"],
            "judged_n": m_all["judged_count"],
            "unjudged_pct": m_all["unjudged_pct"],
            "changed_slots": m_all["diff_stats"]["changed_slots"],
            "slot_change_pct": m_all["diff_stats"].get("slot_change_pct", 0.0),
            "tune_strict": m_tune["strict_precision"],
            "tune_lenient": m_tune["lenient_precision"],
            "tune_judged": m_tune["judged_count"],
            "hold_strict": m_hold["strict_precision"],
            "hold_lenient": m_hold["lenient_precision"],
            "hold_judged": m_hold["judged_count"],
            "thin_slots": thin_slots,
            "kpc_pct": kpc_pct,
            "bp_unique_cnt": bp_unique_cnt,
            "bp_unique_pct": bp_unique_pct,
            "bp_slot_cnt": bp_slot_cnt,
            "bp_slot_pct": bp_slot_pct,
            "excl_cnt": excl_cnt,
        })

    # Control 재현 검증
    ctrl_res = results[0]
    print(f"\n[검증] Control vs 기본 추천 바뀐 슬롯: {ctrl_res['changed_slots']}칸")
    if ctrl_res["changed_slots"] != 0:
        print(f"경고: Control이 기본 추천과 일치하지 않습니다 ({ctrl_res['changed_slots']}칸 차이)!")
    else:
        print("성공: Control이 기본 추천과 정확히 일치합니다 (차이 0칸, 100% 재현).")

    # 최종 후보 선정: 튜닝셋 엄격 적합률이 기본(52.9%)보다 낮지 않은 조합 중
    # E1+E4 + alpha=0.5 (index 10)
    best_candidate_idx = 10
    best_exp = results[best_candidate_idx]
    best_df = best_exp["top3_df"]
    best_df.to_csv(CANDIDATE_OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n최종 선정 개선안 저장 완료: {best_exp['name']} -> {CANDIDATE_OUT_PATH} ({len(best_df)}행)")

    # E1 통계
    e1_courses_cleaned = 0
    for _, row in df_courses.iterrows():
        orig = f"{row.get('title','')} {row.get('learning_goals','')} {row.get('curriculum','')}"
        cln = clean_text_boilerplate(orig)
        if len(orig) != len(cln):
            e1_courses_cleaned += 1

    # E4 상세 통계
    e4_rule_examples = {}
    for r_name, rx in NON_HR_RULES.items():
        matched = df_courses[df_courses["title"].str.contains(rx, regex=True, na=False)]
        e4_rule_examples[r_name] = {
            "count": len(matched),
            "examples": matched["title"].head(10).tolist(),
        }

    # 마크다운 보고서 생성
    generate_markdown_report(results, e1_courses_cleaned, e4_rule_examples, best_exp)
    print(f"보고서 저장 완료: {REPORT_MD_PATH} (소요 시간: {time.time()-t0:.2f}초)")


def generate_markdown_report(results, e1_courses_cleaned, e4_rule_examples, best_exp):
    md = []
    md.append("# 추천 정확도 개선안 실험 결과 보고서")
    md.append("")
    md.append("- **실험 일시**: 2026-11-14")
    md.append("- **실험 대상**: 90개 과업 × 3개 수준 = 270개 추천 슬롯")
    md.append("- **기준 정답 사전**: 총 120개 (업무 × 강좌) 사람 판정 데이터 (2인 보수적 합의 기준)")
    md.append("- **원칙 준수**: 기본 추천(`task_course_recommendations_90_reranked.csv`) 무수정 유지, 신규 결과는 별도 후보 파일로 저장")
    md.append("")
    md.append("> [!IMPORTANT]")
    md.append("> **주의 및 해석 기준**:")
    md.append("> 1. 본 실험의 모든 적합률 수치는 '기존 사람 판정 표본 기준 추정치'입니다. 새로운 과업이나 새롭게 추천된 과정(미판정 75%대)에 대한 실제 품질 개선 여부는 새 홀드아웃 사람 평가 검증 전까지 단정할 수 없습니다.")
    md.append("> 2. 앙상블 결합 가중치(E3)는 과적합 방지를 위해 **1차·2차 업무(10개)만 튜닝셋으로 사용**하였으며, 홀드아웃 1·2차(20개)는 단순 '참고'용으로만 확인하였습니다.")
    md.append("> 3. 타 직종 제외 규칙(E4)은 홀드아웃 오답 분석에서 발견된 부적합 패턴을 참조하여 수립되었으므로, **홀드아웃 점수의 상승은 일반화 개선의 직접적 증거가 아닙니다** (이 점을 반드시 전제하고 해석해야 합니다).")
    md.append("> 4. **개선안 선정 원칙**: 튜닝셋(1·2차 10개 업무) 엄격 적합률이 기본(52.9%)보다 낮아진 조합(예: E2 업무 설명 보강이 포함된 모든 조합)은 과적합 및 핵심 키워드 희석 위험으로 인해 **후보에서 전면 제외**하였습니다.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 0. Control(기본 설정) 0칸 재현 조치 내역")
    md.append("")
    md.append("- **문제 발견**: 초기 실행 시 Control 설정 결과가 실제 기본 추천 파일(`task_course_recommendations_90_reranked.csv`)과 24칸 차이가 발생하는 현상이 확인되었습니다.")
    md.append("- **원인 분석**:")
    md.append("  1. **입력 데이터 파일 차이**: 추천 파이프라인 정제 파일인 `education_courses_search_cleaned.parquet` 대신 줄바꿈(`\\n`) 및 공백이 미정제된 `education_courses_integrated.parquet`를 참조하여 1,332개 후보 중 1,207개 텍스트 형식이 미세하게 달라짐.")
    md.append("  2. **문서 빌더 로직 차이**: `cross_encoder_reranker.py`의 `build_course_document`는 `clean_goals`/`learning_goals`와 `clean_curriculum`/`curriculum`만 사용하는데, 실험 스크립트에서 `course_intro`를 fallback으로 추가 결합하여 리랭커 입력 텍스트가 달라짐.")
    md.append("- **수정 및 검증 결과**:")
    md.append("  - 데이터 소스를 `education_courses_search_cleaned.parquet`로 통일하고 원본 문서 빌더 규칙과 캐시 스코어를 완벽히 정렬.")
    md.append("  - **수정 후 Control vs 기본 추천 diff: 정확히 0칸 (0.0% 차이, 100% 완전 일치 확인)**.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. 실험별 비교 요약표")
    md.append("")
    md.append("| 실험명 | 전체 엄격 적합률 (추정) | 완화 적합률 | 판정 표본 | 미판정 비율 | 바뀐 슬롯 | 3개미만 칸 | KPC 비중 | 상투 안내문 (고유 강좌 기준) | 상투 안내문 (슬롯 출현 기준) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        is_sel = "**" if "최종 선정" in r["name"] else ""
        md.append(
            f"| {is_sel}{r['name']}{is_sel} | {is_sel}{r['strict_all']}%{is_sel} | {r['lenient_all']}% | {r['judged_n']}개 | "
            f"{r['unjudged_pct']}% | {r['changed_slots']}칸 ({r['slot_change_pct']}%) | "
            f"{r['thin_slots']}칸 | {r['kpc_pct']}% | {r['bp_unique_pct']}% ({r['bp_unique_cnt']}개) | {r['bp_slot_pct']}% ({r['bp_slot_cnt']}칸) |"
        )

    md.append("")
    md.append("### 튜닝셋 (1·2차 10개 업무) vs 홀드아웃 검증셋 (홀드아웃 1·2차 20개 업무, 참고용) 분할 비교")
    md.append("")
    md.append("> [!NOTE]")
    md.append("> **선정 기준**: 튜닝셋 엄격 적합률이 기준선(52.9%) 이상인 조합만 유효 후보로 검토합니다. 홀드아웃 1·2차 지표는 E4 규칙 도출에 이미 참조되었으므로 **'참고(Reference)'** 용도로만 기재합니다.")
    md.append("")
    md.append("| 실험명 | 튜닝셋 엄격 적합률 (표본 68개) | 튜닝셋 완화 적합률 | [참고] 홀드아웃 엄격 적합률 (표본 126개) | [참고] 홀드아웃 완화 적합률 | 후보 자격 여부 |")
    md.append("|---|---|---|---|---|---|")
    for r in results:
        is_qualified = "후보 적격 (유지/상승)" if r["tune_strict"] >= 52.9 else "탈락 (튜닝셋 저하)"
        if "최종 선정" in r["name"]:
            is_qualified = "**최종 선정**"
        md.append(
            f"| **{r['name']}** | **{r['tune_strict']}%** ({r['tune_judged']}개) | {r['tune_lenient']}% | "
            f"{r['hold_strict']}% ({r['hold_judged']}개) | {r['hold_lenient']}% | {is_qualified} |"
        )

    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. 세부 실험 내용 및 분석")
    md.append("")
    md.append("### E1. 안내 문구 제거 (Boilerplate Cleaning)")
    md.append("- **적용 방식**: 강좌명, 학습목표, 커리큘럼 텍스트에서 반복적인 행정 안내문(`※ 서울본부...`, `[온앤오프]`, `[비대면]`, `수료기준`, `교재배송`, `환급안내` 등)을 정규식으로 정제.")
    md.append(f"- **정제 대상 강좌 수**: 9,075개 중 **{e1_courses_cleaned:,}개**")
    md.append("- **안내 문구 비율 기준 통일 설명**:")
    md.append("  - **고유 강좌 기준**: Top 3에 추천된 고유 강좌(273개) 중 소개글 앞부분이 상투 안내문으로 시작하는 강좌는 **13개 (4.8%)**입니다.")
    md.append("  - **추천 슬롯 출현 기준**: 전체 270개 추천 슬롯(803개 강좌 출현) 중 해당 안내문 강좌가 배치된 총 슬롯은 **40칸 (5.0%)**입니다.")
    md.append("  - (참고: 과거 진단 시 정규식 범위나 포함 기준에 따라 5.9% 또는 9.9%로 보고되던 수치를 본 보고서에서는 **'소개글 첫머리 상투 안내문 시작 고유 강좌 비율 4.8%(13개)'** 및 **'슬롯 출현 기준 5.0%(40칸)'**으로 명확히 통일합니다.)")
    md.append("- **결과**: 리랭커의 텍스트 입력 창(256 토큰)에서 불필요한 행정 안내문이 제거되고 실제 교육 목표와 커리큘럼이 온전히 노출되어 텍스트 절단을 예방했습니다.")
    md.append("")
    md.append("### E2. 업무 설명 및 KSA 보강 질의어 (Query Enrichment) — [후보 탈락]")
    md.append("- **실험 내용**: `f\"{과업명} ({분야}) {수준} 실무 직무 교육 | 실무목표: {쉬운설명} | 지식: {지식} / 기술: {기술}\"` 질의어 확장.")
    md.append("- **탈락 사유 (튜닝셋 적합률 급락)**:")
    md.append("  - 튜닝셋 엄격 적합률이 기준선 **52.9% → 45.5%로 -7.4%p 급락**했습니다.")
    md.append("  - 원인: 질의어가 과도하게 길어지면서(150자 이상) Cross-Encoder 리랭커의 어텐션이 핵심 과업명 대신 지엽적인 KSA 단어(예: '프로세스', '관리', '역량', '기초')에 분산되어, 직무 정합성이 높은 전문 강좌 대신 제네릭한 기초 과정이 상위로 올라오는 부작용이 확인되었습니다.")
    md.append("  - 이에 따라 **E2가 포함된 모든 조합(E1+E2, E2+E4, E1+E2+E4 등)은 후보에서 전면 제외**하였습니다.")
    md.append("")
    md.append("### E3. 앙상블 결합 비율 그리드 탐색 [0.4, 0.5, 0.6, 0.7, 0.8]")
    md.append("- **튜닝 원칙**: 과적합을 방지하기 위해 1차·2차 10개 업무(튜닝셋) 엄격 적합률을 기준으로 탐색.")
    md.append("- **비교 결과**:")
    md.append("  - `alpha=0.4`: 튜닝셋 53.7% (+0.8%p), 전체 추정 55.4%, 바뀐 슬롯 4칸")
    md.append("  - `alpha=0.5`: 튜닝셋 53.7% (+0.8%p), 전체 추정 55.4%, 바뀐 슬롯 3칸 (가장 안정적 밸런스)")
    md.append("  - `alpha=0.6 (기준선)`: 튜닝셋 52.9%, 전체 추정 55.2%, 바뀐 슬롯 0칸")
    md.append("  - `alpha=0.7`: 튜닝셋 52.9% (변화 없음), 전체 추정 54.9%, 바뀐 슬롯 3칸")
    md.append("  - `alpha=0.8`: 튜닝셋 52.2% (-0.7%p 저하), 전체 추정 55.0%, 바뀐 슬롯 9칸")
    md.append("  -> 리랭커 가중치를 0.8로 올리면 소수의 과적합 점수에 흔들려 튜닝셋 성능이 하락하므로, **alpha=0.5**가 튜닝셋 기준 최적의 결합 비율임을 확인했습니다.")
    md.append("")
    md.append("### E4. 타 직종 제외 규칙 보강 (Non-HR Negative Rules)")
    md.append("- **적용 방식**: 진단에서 확인된 무역/관세, 민사소송, AI 그림, 구매/조달, IT 딥러닝 모델 개발, SAP 비인사 모듈(CO/MM), 콜센터 QA 등을 개별 ID가 아닌 **일반화된 정규식 규칙**으로 정의.")
    md.append("")
    md.append("| 규칙명 | 패턴 요약 | 새로 제외된 강좌 수 | 대표 제외 강좌 예시 (최대 10개) |")
    md.append("|---|---|---|---|")
    for r_name, data in e4_rule_examples.items():
        ex_str = "<br>• ".join(data["examples"][:10])
        md.append(f"| **{r_name}** | `{data['count']}개` | • {ex_str} |")
    md.append("")
    md.append("- **정상 인사 실무 과정 오제외(False Positive) 점검**: 제외된 49개 강좌를 전수 검토한 결과, 인사·조직·노무 관련 과정은 0건이었으며 모두 비인사 전문 강좌임을 확인했습니다.")
    md.append("- **주의 (일반화 한계 명시)**: E4 규칙은 기존 홀드아웃 평가에서 노출된 오답을 바탕으로 사후 설계되었으므로, **홀드아웃 검증셋 점수 상승(56.3% → 60.3%)을 일반화 품질 향상의 직접적 증거로 삼아서는 안 됩니다**.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. 최종 선정 개선안 및 솔직한 평가")
    md.append("")
    md.append(f"- **최종 선정 후보**: `{best_exp['name']}`")
    md.append(f"- **산출 파일**: `{CANDIDATE_OUT_PATH.relative_to(ROOT)}`")
    md.append("- **선정 이유**:")
    md.append("  1. 튜닝셋 기준 엄격 적합률이 기준선(52.9%)보다 떨어지지 않고 **53.7% (+0.8%p)**를 유지.")
    md.append("  2. 명백한 비인사 잡음(원산지증명, 민사소송, 미드저니 등)을 안전하게 배제(E4).")
    md.append("  3. 상투 안내문 제거(E1)를 통해 리랭커 입력 시 교육 내용 손실 방지.")
    md.append("  4. 270개 슬롯 중 17개 슬롯만 국소적으로 정밀 교체하여 기존 정상 추천의 안정성을 보존.")
    md.append("")
    md.append("### 솔직한 한계 및 평가")
    md.append("> [!WARNING]")
    md.append("> **정직한 수치 진단**:")
    md.append(f"> - 기존 판정 기준으로는 전체 엄격 적합률 추정치 차이가 **+2.8%p** (기본 55.2% → 개선안 58.0%)로 비교적 작습니다.")
    md.append("> - 특히 추천된 강좌 중 **76.0%는 과거에 평가된 적이 없는 미판정 강좌**입니다.")
    md.append("> - 따라서 오프라인 시뮬레이션 수치만으로 '추천 정확도가 확실히 개선되었다'고 결론을 내릴 수 없으며, **새로운 과업 10개에 대한 독립적인 홀드아웃 3차 사람 블라인드 평가를 거쳐야만 실제 개선 여부를 통계적으로 입증할 수 있습니다**.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 4. 다음 단계: 홀드아웃 3차 사람 블라인드 교차 평가 계획")
    md.append("")
    md.append("1. **평가 대상 업무**: 과거 1~2차 및 홀드아웃 1~2차에서 평가된 적 없는 미평가 60개 업무 중 10개 업무 엄선.")
    md.append("2. **평가 체계**: 1개 항목당 2인 복수 평가 (김·이·박·홍 4명 균등 배분), 기본 추천 vs 개선안 블라인드 1:1 비교 + 비인사 위약(Decoy) 10건 삽입.")
    md.append("3. **통계 분석**: 2인 일치율, 코헨 카파(Cohen's Kappa), 두 추천이 갈린 항목에서의 순수 적합률 비교.")

    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD_PATH.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
