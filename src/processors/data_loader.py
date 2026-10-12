"""Unified Course Data Loader for edu-skill-gap.

Principles:
1. Parquet prioritized: Attempts to read .parquet first for maximum speed (~0.05s).
2. CSV fallback: Seamlessly falls back to .csv if .parquet is missing.
3. Explicit error: Raises FileNotFoundError with clear guidance if neither exists.
4. Preserves string types: Keeps course_uid, source_course_id, ncs_code as strings with leading zeros intact.
5. Scope separation: Distinguishes between new integrated master (8,645 courses) and legacy verified analysis (295 courses).
"""

import os
from pathlib import Path
from typing import Optional, Literal
import pandas as pd
import numpy as np

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

PROCESSED_DIR = WORKSPACE_ROOT / "data" / "hr" / "processed"
INTEG_OUTPUT_DIR = WORKSPACE_ROOT / "data" / "hr" / "output" / "integration"

STRING_COLUMNS = [
    "course_uid", "provider", "source_course_id", "title",
    "category_depth1", "category_depth2", "category_depth3",
    "course_intro", "target_audience", "learning_goals", "curriculum",
    "education_type", "difficulty", "price_type", "start_date", "end_date",
    "url", "collected_at", "detail_crawled_at", "source_provider", "source_file",
    "ncs_code", "ksa_knowledge", "ksa_skill", "ksa_attitude",
    "mapping_confidence", "mapping_status"
]

NUMERIC_COLUMNS = ["duration_hours", "duration_days", "price"]

def load_integrated_courses(
    scope: Literal["all", "verified_only", "hr_ga_only"] = "all",
    force_csv: bool = False
) -> pd.DataFrame:
    """Loads the 8,645 integrated master course dataset.
    
    Priority:
    1. data/hr/processed/education_courses_integrated.parquet
    2. data/hr/processed/education_courses_integrated.csv
    
    Args:
        scope:
            - 'all': All 8,645 courses (default)
            - 'verified_only': 3,595 courses with rule-based auto-matched NCS/KSA mapping.
              ※ 주의: 본 수치는 사람의 육안 전수 검수 완료가 아닌, 키워드/규칙 기반 고신뢰도 자동 매핑(Auto-matched) 결과입니다.
              (신규 6개 DB 3,499건 + 기존 공공 API 96건 = 총 3,595건)
            - 'hr_ga_only': Courses mapped to HR, GA, or MGMT domains (including REVIEW_NEEDED)
        force_csv: If True, bypasses Parquet and reads CSV directly.
        
    Returns:
        pd.DataFrame with normalized types and preserved ID strings.
    """
    parquet_path = PROCESSED_DIR / "education_courses_integrated.parquet"
    csv_path = PROCESSED_DIR / "education_courses_integrated.csv"
    
    df: Optional[pd.DataFrame] = None
    source_used: str = ""

    if not force_csv and parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path, engine="pyarrow")
            source_used = "PARQUET"
        except Exception as e:
            # Fallback to CSV if parquet read fails
            print(f"[Warning] Failed to load Parquet ({e}), falling back to CSV.")
            df = None

    if df is None:
        if csv_path.exists():
            dtype_map = {col: "str" for col in STRING_COLUMNS}
            df = pd.read_csv(csv_path, dtype=dtype_map, keep_default_na=False)
            source_used = "CSV"
        else:
            raise FileNotFoundError(
                f"통합 교육과정 데이터셋을 찾을 수 없습니다.\n"
                f"- Parquet 경로: {parquet_path}\n"
                f"- CSV 경로: {csv_path}\n"
                f"먼저 'python scripts/integrate_external_courses_pipeline.py'를 실행해 데이터를 생성하세요."
            )

    # Post-processing for data type consistency
    for col in ["course_uid", "source_course_id", "ncs_code"]:
        if col in df.columns:
            df[col] = df[col].astype("string")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Scope filtering
    if scope == "verified_only":
        df = df[df["mapping_status"] == "VERIFIED"].copy()
    elif scope == "hr_ga_only":
        df = df[df["mapping_status"].isin(["VERIFIED", "REVIEW_NEEDED"])].copy()

    # Attach provenance metadata
    df.attrs["data_source_type"] = source_used
    df.attrs["scope"] = scope
    return df

def load_standardized_courses(force_csv: bool = False) -> pd.DataFrame:
    """Loads the 8,505 standardized external course dataset."""
    parquet_path = PROCESSED_DIR / "external_courses_standardized.parquet"
    csv_path = PROCESSED_DIR / "external_courses_standardized.csv"

    if not force_csv and parquet_path.exists():
        df = pd.read_parquet(parquet_path, engine="pyarrow")
    elif csv_path.exists():
        dtype_map = {col: "str" for col in STRING_COLUMNS}
        df = pd.read_csv(csv_path, dtype=dtype_map, keep_default_na=False)
    else:
        raise FileNotFoundError(f"표준화 데이터를 찾을 수 없습니다: {parquet_path} 또는 {csv_path}")

    for col in ["course_uid", "source_course_id", "ncs_code"]:
        if col in df.columns:
            df[col] = df[col].astype("string")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

def load_legacy_verified_courses() -> pd.DataFrame:
    """Loads the legacy STEP 4 verified dataset (295 courses) to ensure 100% backward compatibility.
    
    Source: data/hr/output/integration/hr_integrated_verified.csv
    """
    path = INTEG_OUTPUT_DIR / "hr_integrated_verified.csv"
    if not path.exists():
        raise FileNotFoundError(f"기존 검증 데이터셋을 찾을 수 없습니다: {path}")
    df = pd.read_csv(path, dtype=str)
    for col in ["training_hours", "duration_days", "course_fee"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
