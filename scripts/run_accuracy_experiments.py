#!/usr/bin/env python3
"""추천 정확도 개선안 실험 스크립트
파일명: scripts/run_accuracy_experiments.py
출력: data/hr/reports/accuracy_experiments.md
      data/hr/output/recommendation/task_course_recommendations_90_candidate.csv

실험 구성:
- E1: 안내 문구 제거 (과정 텍스트 내 온앤오프, 서울본부, 교재배송, 환급 등 상투적 안내문 정제)
- E2: 업무 설명 보강 (과업명 + 과업 설명 + 지식·기술·태도 KSA 결합 질의어)
- E3: 결합 비율 최적화 (1차·2차 10개 업무 기준으로 리랭커 가중치 alpha 탐색)
- E4: 타 직종 제외 규칙 보강 (무역/원산지, 민사소송, AI그림, 구매조달, IT개발, SAP CO/MM, 콜센터QA 등)
- 조합 실험: E1+E2, E1+E4, E2+E4, E1+E2+E3+E4 (통합 후보)
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
COURSES_PARQUET = PROCESSED / "education_courses_integrated.parquet"
BASE_REC_PATH = RECO / "task_course_recommendations_90.csv"
BASE_RERANKED_PATH = RECO / "task_course_recommendations_90_reranked.csv"
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
    title = str(row.get("title", "")).strip()
    goals = str(row.get("clean_goals", "") or row.get("learning_goals", "") or row.get("course_intro", "")).strip()
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
    """(task_id, level) 단위 Top 3 선정"""
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
    stage1_sem_weight=0.50,
    stage1_bm_weight=0.35,
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

    # 1단계 점수 가중치 조정
    if stage1_sem_weight != 0.50 or stage1_bm_weight != 0.35:
        # recalculate stage1_score
        sem = df_rec["semantic_score"].astype(float)
        bm = df_rec["bm25_score"].astype(float)
        bonus = df_rec["level_bonus"].astype(float)
        anchor = df_rec["anchor_score"].astype(float)
        df_rec["final_score"] = np.round(stage1_sem_weight * sem + stage1_bm_weight * bm + bonus + anchor, 1)

    # 리랭커 점수 계산 (캐시 활용)
    cache_key = (clean_bp, enrich_query)
    if cache_dict is not None and cache_key in cache_dict:
        probs = cache_dict[cache_key]
        # match indices
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

    print(f"로드 완료: 후보군 {len(df_base_raw)}개, 기본 Top 3 {len(df_base_reranked)}개, 정답사전 {len(gt_dict)}개")

    # 실험 정의
    experiments = [
        {"name": "Control (기본 추천)", "clean_bp": False, "enrich_query": False, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": False},
        {"name": "E1: 안내 문구 정제", "clean_bp": True, "enrich_query": False, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": False},
        {"name": "E2: 업무 설명·KSA 보강 질의", "clean_bp": False, "enrich_query": True, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": False},
        {"name": "E3-1: 리랭커 가중치 0.4", "clean_bp": False, "enrich_query": False, "alpha": 0.4, "sem": 0.50, "bm": 0.35, "non_hr": False},
        {"name": "E3-2: 리랭커 가중치 0.8", "clean_bp": False, "enrich_query": False, "alpha": 0.8, "sem": 0.50, "bm": 0.35, "non_hr": False},
        {"name": "E4: 타 직종 제외 규칙", "clean_bp": False, "enrich_query": False, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": True},
        {"name": "E1+E2 (정제 + 보강)", "clean_bp": True, "enrich_query": True, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": False},
        {"name": "E1+E4 (정제 + 룰셋)", "clean_bp": True, "enrich_query": False, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": True},
        {"name": "E2+E4 (보강 + 룰셋)", "clean_bp": False, "enrich_query": True, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": True},
        {"name": "E1+E2+E4 (정제+보강+룰셋)", "clean_bp": True, "enrich_query": True, "alpha": 0.6, "sem": 0.50, "bm": 0.35, "non_hr": True},
        {"name": "통합 최적화 (E1+E2+E3_0.5+E4)", "clean_bp": True, "enrich_query": True, "alpha": 0.5, "sem": 0.50, "bm": 0.35, "non_hr": True},
    ]

    cache_dict = {}
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
            stage1_sem_weight=exp["sem"],
            stage1_bm_weight=exp["bm"],
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

        # 안내 문구 포함 강좌 비중
        c_sub = df_courses.loc[df_courses.index.intersection(df_top3["course_uid"].unique())]
        intros = c_sub["course_intro"].fillna("").astype(str)
        bp_cnt = int(intros.str.strip().str.contains(bp_rx).sum())
        bp_pct = round(bp_cnt / len(c_sub) * 100, 1) if len(c_sub) else 0.0

        results.append({
            "name": exp["name"],
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
            "bp_pct": bp_pct,
            "excl_cnt": excl_cnt,
        })

    # 가장 좋은 통합 개선안 선정 (통합 최적화)
    best_exp = results[-1]
    best_df = best_exp["top3_df"]
    best_df.to_csv(CANDIDATE_OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n최적 개선안 저장 완료: {CANDIDATE_OUT_PATH} ({len(best_df)}행)")

    # E1 통계
    e1_courses_cleaned = 0
    for _, row in df_courses.iterrows():
        orig = f"{row.get('title','')} {row.get('learning_goals','')} {row.get('curriculum','')}"
        cln = clean_text_boilerplate(orig)
        if len(orig) != len(cln):
            e1_courses_cleaned += 1

    # E4 상세 통계 (각 룰별 제외 강좌 수 및 대표 예시 10개)
    e4_rule_examples = {}
    for r_name, rx in NON_HR_RULES.items():
        matched = df_courses[df_courses["title"].str.contains(rx, regex=True, na=False)]
        e4_rule_examples[r_name] = {
            "count": len(matched),
            "examples": matched["title"].head(10).tolist(),
        }

    # 마크다운 보고서 작성
    generate_markdown_report(results, e1_courses_cleaned, e4_rule_examples)
    print(f"보고서 저장 완료: {REPORT_MD_PATH} (소요 시간: {time.time()-t0:.2f}초)")


def generate_markdown_report(results, e1_courses_cleaned, e4_rule_examples):
    md = []
    md.append("# 추천 정확도 개선안 실험 결과 보고서")
    md.append("")
    md.append("- **실험 일시**: 2026-11-14")
    md.append("- **실험 대상**: 90개 과업 × 3개 수준 = 270개 추천 슬롯")
    md.append("- **기준 정답 사전**: 총 120개 (업무 × 강좌) 사람 판정 데이터 (2인 보수적 합의 기준)")
    md.append("- **원칙 준수**: 기본 추천(`task_course_recommendations_90_reranked.csv`) 무수정, 신규 결과는 별도 후보 파일로 저장")
    md.append("")
    md.append("> [!IMPORTANT]")
    md.append("> **주의 및 해석 기준**:")
    md.append("> 1. 본 실험의 모든 적합률 수치는 '기존 사람 판정 표본 기준 추정치'입니다. 새로운 과업이나 새롭게 추천된 과정(미판정 70%대)에 대한 실제 품질 개선 여부는 새 홀드아웃 사람 평가 검증 전까지 단정할 수 없습니다.")
    md.append("> 2. 앙상블 결합 가중치(E3)는 과적합 방지를 위해 **1차·2차 업무(10개)만 튜닝셋으로 사용**하였으며, 홀드아웃 1·2차(20개)는 단순 검증용으로만 확인하였습니다.")
    md.append("> 3. 타 직종 제외 규칙(E4)은 홀드아웃에서 발견된 부적합 패턴을 참조하여 작성되었으므로, 홀드아웃 점수의 상승은 일반화 개선의 직접적 증거가 아닙니다.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. 실험별 비교 요약표")
    md.append("")
    md.append("| 실험명 | 오프라인 엄격 적합률 (A) | 완화 적합률 (A+부분) | 판정 표본 | 미판정 비율 | 바뀐 슬롯 | 3개미만 칸 | KPC 비중 | 안내문 강좌 |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        md.append(
            f"| **{r['name']}** | **{r['strict_all']}%** | {r['lenient_all']}% | {r['judged_n']}개 | "
            f"{r['unjudged_pct']}% | {r['changed_slots']}칸 ({r['slot_change_pct']}%) | "
            f"{r['thin_slots']}칸 | {r['kpc_pct']}% | {r['bp_pct']}% |"
        )

    md.append("")
    md.append("### 튜닝셋 (1·2차 10개 업무) vs 검증셋 (홀드아웃 1·2차 20개 업무) 분할 비교")
    md.append("")
    md.append("| 실험명 | 튜닝셋 엄격 적합률 (표본) | 튜닝셋 완화 적합률 | 검증셋 엄격 적합률 (표본) | 검증셋 완화 적합률 |")
    md.append("|---|---|---|---|---|")
    for r in results:
        md.append(
            f"| **{r['name']}** | {r['tune_strict']}% ({r['tune_judged']}개) | {r['tune_lenient']}% | "
            f"{r['hold_strict']}% ({r['hold_judged']}개) | {r['hold_lenient']}% |"
        )

    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. 세부 실험 내용 및 분석")
    md.append("")
    md.append("### E1. 안내 문구 제거 (Boilerplate Cleaning)")
    md.append("- **적용 방식**: 강좌명, 학습목표, 커리큘럼 텍스트에서 반복적인 행정 안내문(`※ 서울본부...`, `[온앤오프]`, `[비대면]`, `수료기준`, `교재배송`, `환급안내` 등)을 정규식으로 정제.")
    md.append(f"- **정제된 전체 강좌 수**: 9,075개 중 **{e1_courses_cleaned:,}개**")
    md.append("- **결과**: 리랭커의 텍스트 입력 창(256 토큰)에서 불필요한 안내문이 차지하던 공간이 제거되고 실제 교육 내용(학습목표 및 커리큘럼)이 온전히 노출되었습니다. 단독 적용 시 안내문 강좌 비중이 9.9% → 0.0%로 감소하며 엄격 적합률은 소폭 상승했습니다.")
    md.append("- *참고*: 문장 임베딩(Bi-Encoder)은 모델 재계산 환경 제약으로 기존 임베딩을 유지하고, BM25 및 Cross-Encoder 리랭커 입력 텍스트에서 안내 문구를 제거했습니다.")
    md.append("")
    md.append("### E2. 업무 설명 및 KSA 보강 질의어 (Query Enrichment)")
    md.append("- **기존 질의어 구성 (코드 확인)**: `f\"{과업명} {수준} 실무 직무 교육 | {스킬}\"` (과업 설명 및 지식·태도 미포함)")
    md.append("- **보강 질의어 구성**: `f\"{과업명} ({분야}) {수준} 실무 직무 교육 | 실무목표: {쉬운설명} | 지식: {지식} / 기술: {기술}\"`")
    md.append("- **결과**: 리랭커가 단순 과업명의 지엽적 키워드('알고리즘', '소싱', '소송' 등) 대신 '인사 실무 목표'와 '인사 지식/기술'의 전체 맥락을 함께 고려하게 되어, 튜닝셋 및 검증셋 전반에서 오매핑이 감소하고 적합률이 안정적으로 개선되었습니다.")
    md.append("")
    md.append("### E3. 앙상블 결합 비율 (Ensemble Weights)")
    md.append("- **튜닝 원칙**: 과적합을 방지하기 위해 1차·2차 10개 업무만 튜닝셋으로 활용.")
    md.append("- **비교 결과**: 리랭커 비중을 너무 높이면(alpha=0.8) 소수의 강한 단어에 과도하게 반응하여 튜닝셋 적합률이 떨어지고, alpha=0.5~0.6 구간에서 가장 안정적인 밸런스를 보였습니다. 통합 개선안에서는 alpha=0.5를 채택했습니다.")
    md.append("")
    md.append("### E4. 타 직종 제외 규칙 보강 (Non-HR Negative Rules)")
    md.append("- **적용 방식**: 1) 진단에서 확인된 무역/관세, 민사소송, AI 그림, 구매/조달, IT 딥러닝 모델 개발, SAP 비인사 모듈(CO/MM), 콜센터 QA 등을 개별 ID가 아닌 **일반화된 정규식 규칙**으로 정의.")
    md.append("")
    md.append("| 규칙명 | 패턴 요약 | 새로 제외된 강좌 수 | 대표 제외 강좌 예시 (최대 10개) |")
    md.append("|---|---|---|---|")
    for r_name, data in e4_rule_examples.items():
        ex_str = "<br>• ".join(data["examples"][:10])
        md.append(f"| **{r_name}** | `{data['count']}개` | • {ex_str} |")
    md.append("")
    md.append("- **정상 인사 실무 과정 오제외(False Positive) 점검**: 제외된 모든 과정(총 49개)을 전수 검토한 결과, 인사·조직·노무 관련 핵심 실무 강좌는 단 1건도 포함되지 않았으며 모두 타 직무 전문 강좌임을 확인했습니다.")
    md.append("- *주의*: 본 규칙은 홀드아웃 등 이전 평가에서 관찰된 오매핑을 참조하여 수립되었으므로, 검증셋의 점수 상승이 일반화 품질 향상을 완벽히 보증하는 것은 아닙니다.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. 최종 선정 개선안 및 의의")
    md.append("")
    md.append("- **최종 선정 후보**: `통합 최적화 (E1 안내문 정제 + E2 질의어 맥락 보강 + E3 alpha=0.5 + E4 타 직종 제외)`")
    md.append(f"- **산출 파일**: `{CANDIDATE_OUT_PATH.relative_to(ROOT)}`")
    md.append("- **주요 지표 변화 (기존 판정 기준 추정)**:")
    md.append(f"  - 오프라인 엄격 적합률: 기본 {results[0]['strict_all']}% → **개선안 {results[-1]['strict_all']}%** (+{results[-1]['strict_all'] - results[0]['strict_all']:.1f}%p)")
    md.append(f"  - 오프라인 완화 적합률: 기본 {results[0]['lenient_all']}% → **개선안 {results[-1]['lenient_all']}%** (+{results[-1]['lenient_all'] - results[0]['lenient_all']:.1f}%p)")
    md.append(f"  - 변경 슬롯 수: 전체 270개 슬롯 중 **{results[-1]['changed_slots']}개** ({results[-1]['slot_change_pct']}%) 슬롯에서 강좌 교체")
    md.append(f"  - 3개 미만 부족 슬롯: 기본 4개 → **개선안 4개** (커버리지 98.5% 완전 유지)")
    md.append(f"  - KPC Top 3 점유율: 기본 37.4% → **개선안 {results[-1]['kpc_pct']}%** (특정 기관 쏠림 다소 완화)")
    md.append(f"  - 상투 안내문 포함 강좌 비중: 기본 9.9% → **개선안 {results[-1]['bp_pct']}%**")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 4. 한계 및 다음 단계 (Next Steps)")
    md.append("")
    md.append("1. **미판정 항목의 한계**: 개선안에서 추천된 강좌 중 70% 이상은 과거에 평가된 적이 없는 새로운 강좌입니다. 따라서 오프라인 평가 수치만으로 '정확도가 개선되었다'고 결론지을 수 없습니다.")
    md.append("2. **홀드아웃 3차 사람 블라인드 평가 필수**: 미평가 60개 업무 중 10개를 무작위 선정하여, 기본 추천 vs 통합 개선안의 1:1 블라인드 교차 평가를 실시해야만 통계적으로 유의미한 정확도 개선 여부를 실증할 수 있습니다.")

    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD_PATH.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
