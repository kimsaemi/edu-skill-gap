import pandas as pd
import numpy as np
import json
import os
import argparse
import sys

def parse_args():
    parser = argparse.ArgumentParser(description="교육 추천 시스템 팀원 평가 결과 분석 및 지표 산출")
    parser.add_argument("--eval_file", default="data/hr/output/recommendation/human_eval_sheet_blind_4members.csv",
                        help="팀원 4명이 작성한 블라인드 평가 시트 경로")
    parser.add_argument("--key_file", default="data/hr/output/recommendation/blind_evaluation_key.json",
                        help="블라인드 해제 매핑 키 JSON 경로")
    parser.add_argument("--output_report", default="data/hr/reports/human_evaluation_results_summary.md",
                        help="평가 집계 결과 보고서 출력 경로")
    return parser.parse_args()

def calculate_dcg(relevances, k=10):
    relevances = relevances[:k]
    dcg = 0.0
    for idx, rel in enumerate(relevances, 1):
        # 2^rel - 1 formulation
        gain = (2.0 ** rel) - 1.0
        discount = np.log2(idx + 1.0)
        dcg += gain / discount
    return dcg

def calculate_ndcg(relevances, k=10):
    actual_dcg = calculate_dcg(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    ideal_dcg = calculate_dcg(ideal_relevances, k)
    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg

def main():
    args = parse_args()
    
    print("=" * 80)
    print(" [STEP 5-1] 팀원 4인 블라인드 평가 결과 검증 및 지표 산출 스크립트")
    print("=" * 80)
    
    if not os.path.exists(args.eval_file):
        print(f"[오류] 평가 시트 파일을 찾을 수 없습니다: {args.eval_file}")
        sys.exit(1)
        
    df_eval = pd.read_csv(args.eval_file)
    print(f"[+] 평가 시트 로드 완료: {len(df_eval):,}개 평가 대상 행")
    
    score_col = "관련성 점수 (2/1/0/확인 불가)"
    if score_col not in df_eval.columns:
        print(f"[오류] 필수 컬럼 '{score_col}'이 파일에 존재하지 않습니다.")
        sys.exit(1)
        
    # Check populated rows
    valid_scores = df_eval[score_col].fillna("").astype(str).str.strip()
    non_empty_mask = valid_scores.ne("")
    filled_count = non_empty_mask.sum()
    total_count = len(df_eval)
    
    print(f"[+] 현재 입력된 평가 건수: {filled_count:,} / {total_count:,} ({filled_count/total_count*100:.1f}%)")
    
    # CRITICAL RULE: If evaluations are not completed, do NOT invent fake metrics or print PASS
    if filled_count == 0:
        print("\n" + "!" * 80)
        print(" [안내] 실제 팀원 평가 점수가 아직 입력되지 않은 대기 상태입니다.")
        print("   - 규칙에 따라 임의의 가짜 점수를 생성하거나 지표를 PASS로 처리하지 않습니다.")
        print("   - 팀원 4명이 'human_eval_sheet_blind_4members.csv' 파일의")
        print("     '관련성 점수 (2/1/0/확인 불가)' 및 '평가 판단 근거' 열을 작성한 후")
        print("     본 스크립트를 다시 실행하면 공식 지표(Precision@5, nDCG@10 등)가 자동 산출됩니다.")
        print("!" * 80)
        return
        
    if filled_count < total_count:
        print(f"\n[주의] 평가가 부분적으로 진행 중입니다 ({filled_count}/{total_count}건).")
        print("현재까지 입력된 데이터를 바탕으로 중간 점검 지표를 산출합니다.")
        
    # Load unblinding key
    with open(args.key_file, "r", encoding="utf-8") as f:
        blind_key = json.load(f)
        
    # Process scores: map "확인 불가" -> np.nan, "2" -> 2.0, "1" -> 1.0, "0" -> 0.0
    def parse_score(val):
        v = str(val).strip()
        if v in ["2", "2.0"]:
            return 2.0
        elif v in ["1", "1.0"]:
            return 1.0
        elif v in ["0", "0.0"]:
            return 0.0
        elif v in ["확인 불가", "확인불가", "unknown"]:
            return -1.0 # Unknown
        return np.nan

    df_eval["numeric_score"] = df_eval[score_col].apply(parse_score)
    unknown_count = (df_eval["numeric_score"] == -1.0).sum()
    
    print(f"\n[1] 점수 분포 집계:")
    print(f"  - 2점 (직접 관련): {(df_eval['numeric_score'] == 2.0).sum():,}건")
    print(f"  - 1점 (일부 관련): {(df_eval['numeric_score'] == 1.0).sum():,}건")
    print(f"  - 0점 (관련 없음): {(df_eval['numeric_score'] == 0.0).sum():,}건")
    print(f"  - 확인 불가 (상세내용 부족): {unknown_count:,}건")
    print(f"  - 미입력: {(df_eval['numeric_score'].isna()).sum():,}건")
    
    # 2. Inter-Annotator Disagreement Analysis (on Common Queries Q01, Q06, Q13)
    common_mask = df_eval["질문 배정 구분"].str.contains("공통")
    df_common = df_eval[common_mask & df_eval["numeric_score"].notna()]
    
    disagreements = []
    if len(df_common) > 0:
        # Group by blind candidate id
        grouped = df_common.groupby("블라인드 후보 ID")
        for cid, grp in grouped:
            scores = grp["numeric_score"].tolist()
            raters = grp["배정 평가자"].tolist()
            if len(set(scores)) > 1: # Scores disagree
                q_text = grp["검색 질문"].iloc[0]
                c_name = grp["과정명"].iloc[0]
                prov = grp["교육기관"].iloc[0]
                rater_scores = {r: s for r, s in zip(raters, scores)}
                disagreements.append({
                    "blind_candidate_id": cid,
                    "query": q_text,
                    "course_name": c_name,
                    "provider": prov,
                    "evaluator_scores": rater_scores,
                    "score_std": float(np.std(scores))
                })
                
    print(f"\n[2] 공통 질문(Q01, Q06, Q13) 평가자 간 불일치 사례: 총 {len(disagreements):,}건")
    for dis in disagreements[:5]:
        print(f"  - [{dis['blind_candidate_id']}] {dis['course_name']} ({dis['provider']}): 평가점수={dis['evaluator_scores']}")
        
    # 3. Algorithm Unblinding and Metrics Calculation (TF-IDF vs BM25)
    # Join key info
    eval_with_key = []
    for idx, row in df_eval.iterrows():
        cid = row["블라인드 후보 ID"]
        if cid in blind_key:
            k = blind_key[cid]
            r_dict = row.to_dict()
            r_dict.update({
                "origin_algorithm": k["origin_algorithm"],
                "tfidf_rank": k["tfidf_rank"],
                "tfidf_score": k["tfidf_score"],
                "bm25_rank": k["bm25_rank"],
                "bm25_score": k["bm25_score"],
            })
            eval_with_key.append(r_dict)
            
    df_joined = pd.DataFrame(eval_with_key)
    
    # Aggregate scores per candidate (average if multiple raters on common queries)
    def clean_score_for_agg(s):
        return np.nan if s == -1.0 else s
        
    df_joined["score_for_metric"] = df_joined["numeric_score"].apply(clean_score_for_agg)
    
    # Per algorithm Top 10 metrics
    qids = df_joined["질문 ID"].unique()
    
    tfidf_metrics = []
    bm25_metrics = []
    
    for qid in qids:
        q_data = df_joined[df_joined["질문 ID"] == qid]
        
        # TF-IDF Top 10
        t_candidates = q_data[q_data["tfidf_rank"].notna()].drop_duplicates("블라인드 후보 ID").sort_values("tfidf_rank")
        if len(t_candidates) > 0:
            t_scores = t_candidates["score_for_metric"].fillna(0.0).tolist()
            # Precision@5 (rel >= 1)
            t_p5 = sum(1 for s in t_scores[:5] if s >= 1.0) / 5.0
            t_p5_strict = sum(1 for s in t_scores[:5] if s == 2.0) / 5.0
            # Irrelevant in Top 5 (rel == 0)
            t_irrel5 = sum(1 for s in t_scores[:5] if s == 0.0) / 5.0
            # nDCG@10
            t_ndcg = calculate_ndcg(t_scores, k=10)
            tfidf_metrics.append({
                "qid": qid,
                "precision@5": t_p5,
                "precision@5_strict": t_p5_strict,
                "irrelevant@5_ratio": t_irrel5,
                "ndcg@10": t_ndcg
            })
            
        # BM25 Top 10
        b_candidates = q_data[q_data["bm25_rank"].notna()].drop_duplicates("블라인드 후보 ID").sort_values("bm25_rank")
        if len(b_candidates) > 0:
            b_scores = b_candidates["score_for_metric"].fillna(0.0).tolist()
            b_p5 = sum(1 for s in b_scores[:5] if s >= 1.0) / 5.0
            b_p5_strict = sum(1 for s in b_scores[:5] if s == 2.0) / 5.0
            b_irrel5 = sum(1 for s in b_scores[:5] if s == 0.0) / 5.0
            b_ndcg = calculate_ndcg(b_scores, k=10)
            bm25_metrics.append({
                "qid": qid,
                "precision@5": b_p5,
                "precision@5_strict": b_p5_strict,
                "irrelevant@5_ratio": b_irrel5,
                "ndcg@10": b_ndcg
            })

    print("\n" + "=" * 80)
    print(" [3] 알고리즘별 종합 평가 결과 비교 (블라인드 해제 후)")
    print("=" * 80)
    
    if tfidf_metrics and bm25_metrics:
        df_tm = pd.DataFrame(tfidf_metrics)
        df_bm = pd.DataFrame(bm25_metrics)
        
        print(f"| 지표 (평균) | TF-IDF | BM25 | 우수 모델 |")
        print(f"| :--- | :---: | :---: | :---: |")
        p5_t, p5_b = df_tm["precision@5"].mean(), df_bm["precision@5"].mean()
        winner_p5 = "TF-IDF" if p5_t > p5_b else ("BM25" if p5_b > p5_t else "동률")
        print(f"| Precision@5 (관련+일부) | {p5_t*100:.1f}% | {p5_b*100:.1f}% | {winner_p5} |")
        
        p5s_t, p5s_b = df_tm["precision@5_strict"].mean(), df_bm["precision@5_strict"].mean()
        winner_p5s = "TF-IDF" if p5s_t > p5s_b else ("BM25" if p5s_b > p5s_t else "동률")
        print(f"| Precision@5 (직접관련만) | {p5s_t*100:.1f}% | {p5s_b*100:.1f}% | {winner_p5s} |")
        
        irr_t, irr_b = df_tm["irrelevant@5_ratio"].mean(), df_bm["irrelevant@5_ratio"].mean()
        winner_irr = "TF-IDF(낮음)" if irr_t < irr_b else ("BM25(낮음)" if irr_b < irr_t else "동률")
        print(f"| Top 5 내 관련없는 과정 비율 | {irr_t*100:.1f}% | {irr_b*100:.1f}% | {winner_irr} |")
        
        ndcg_t, ndcg_b = df_tm["ndcg@10"].mean(), df_bm["ndcg@10"].mean()
        winner_ndcg = "TF-IDF" if ndcg_t > ndcg_b else ("BM25" if ndcg_b > ndcg_t else "동률")
        print(f"| nDCG@10 (순위반영) | {ndcg_t:.4f} | {ndcg_b:.4f} | {winner_ndcg} |")

if __name__ == "__main__":
    main()
