"""
scripts/merge_human_eval_results.py
독립 평가된 Reviewer A와 Reviewer B의 30건 검토표를 evaluation_id 기준으로 안정적으로 병합하는 스크립트
- 입력:
  * data/skills_taxonomy/human_evaluation_sheet_30_reviewer_A.csv
  * data/skills_taxonomy/human_evaluation_sheet_30_reviewer_B.csv
- 기능:
  * evaluation_id (EVAL_01 ~ EVAL_30) 기준 1:1 조인
  * 판정 일치율(Agreement Rate) 계산
  * 불일치 항목 플래그(is_discrepancy) 생성
  * 병합 파일 출력: data/skills_taxonomy/human_evaluation_merged_results.csv
"""
import sys
from pathlib import Path
import pandas as pd

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def merge_eval_results():
    data_dir = WORKSPACE_ROOT / "data" / "skills_taxonomy"
    path_A = data_dir / "human_evaluation_sheet_30_reviewer_A.csv"
    path_B = data_dir / "human_evaluation_sheet_30_reviewer_B.csv"
    out_csv = data_dir / "human_evaluation_merged_results.csv"

    if not path_A.exists() or not path_B.exists():
        print(f"[ERROR] 평가 파일이 존재하지 않습니다. A: {path_A.exists()}, B: {path_B.exists()}")
        return

    df_A = pd.read_csv(path_A, encoding="utf-8-sig")
    df_B = pd.read_csv(path_B, encoding="utf-8-sig")

    print(f"Reviewer A 로드: {len(df_A)}건")
    print(f"Reviewer B 로드: {len(df_B)}건")

    # evaluation_id 기준 매합
    cols_B = ["evaluation_id", "reviewer_B_verdict", "reviewer_B_rationale"]
    df_merged = pd.merge(df_A, df_B[cols_B], on="evaluation_id", how="inner")

    # 일치 여부 판별
    v_a = df_merged["reviewer_A_verdict"].fillna("").str.strip().str.upper()
    v_b = df_merged["reviewer_B_verdict"].fillna("").str.strip().str.upper()

    completed_mask = (v_a != "") & (v_b != "")
    agree_mask = completed_mask & (v_a == v_b)
    discrepancy_mask = completed_mask & (v_a != v_b)

    df_merged["agreement_status"] = "PENDING"
    df_merged.loc[agree_mask, "agreement_status"] = "AGREED"
    df_merged.loc[discrepancy_mask, "agreement_status"] = "DISCREPANCY"

    df_merged.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n병합 파일 저장 완료: {out_csv}")
    print(f"총 항목 수: {len(df_merged)}건")
    print(f"양측 모두 작성 완료 건수: {completed_mask.sum()}건")
    if completed_mask.sum() > 0:
        agreement_rate = (agree_mask.sum() / completed_mask.sum()) * 100
        print(f"판정 일치 건수: {agree_mask.sum()}건 ({agreement_rate:.1f}%)")
        print(f"불일치 건수: {discrepancy_mask.sum()}건")
    else:
        print("현재 두 평가자의 판정이 아직 입력되지 않았습니다. (READY_FOR_HUMAN_EVALUATION)")

if __name__ == "__main__":
    merge_eval_results()
