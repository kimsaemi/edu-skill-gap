"""
교육과정 8,645건 코퍼스 및 원본 SQLite DB, Parquet, CSV 대상
실제 수강 후기 및 수강생 평점 데이터 전수 조사 감사 스크립트
"""

import sys
import os
import sqlite3
import glob
import json
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"d:\26_강의자료\프로젝트2_교육"

KEYWORDS = [
    'review', 'rating', 'star', 'score', 'satisf', 'comment',
    'feedback', 'eval', 'survey', 'opinion', 'grade',
    '후기', '평점', '만족도', '평가', '리뷰', '별점', '의견', '만족', '설문'
]

def check_keyword_match(name: str) -> bool:
    name_lower = name.lower()
    return any(k in name_lower for k in KEYWORDS)

def inspect_sqlite_db(db_path: str):
    results = {
        "db_path": db_path,
        "tables": [],
        "review_columns": []
    }
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view');")
        tables = cursor.fetchall()
        
        for tbl_name, tbl_type in tables:
            if tbl_name.startswith("sqlite_"):
                continue
            
            # 테이블 정보 조회
            cursor.execute(f"PRAGMA table_info('{tbl_name}')")
            cols_info = cursor.fetchall()
            col_names = [c[1] for c in cols_info]
            
            # 행 수
            try:
                cursor.execute(f"SELECT COUNT(*) FROM '{tbl_name}'")
                row_count = cursor.fetchone()[0]
            except Exception:
                row_count = -1
                
            tbl_meta = {
                "name": tbl_name,
                "type": tbl_type,
                "row_count": row_count,
                "columns": col_names
            }
            results["tables"].append(tbl_meta)
            
            # 컬럼 중 키워드 매칭
            for c_idx, c_name, c_type, c_notnull, c_dflt, c_pk in cols_info:
                if check_keyword_match(c_name):
                    # 실제 값 통계 조회
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM '{tbl_name}' WHERE \"{c_name}\" IS NOT NULL AND TRIM(CAST(\"{c_name}\" AS TEXT)) != ''")
                        non_null_count = cursor.fetchone()[0]
                        cursor.execute(f"SELECT DISTINCT \"{c_name}\" FROM '{tbl_name}' WHERE \"{c_name}\" IS NOT NULL AND TRIM(CAST(\"{c_name}\" AS TEXT)) != '' LIMIT 5")
                        samples = [str(r[0])[:100] for r in cursor.fetchall()]
                    except Exception as e:
                        non_null_count = -1
                        samples = [f"Error: {e}"]
                        
                    results["review_columns"].append({
                        "table": tbl_name,
                        "column": c_name,
                        "type": c_type,
                        "total_rows": row_count,
                        "non_null_count": non_null_count,
                        "null_or_empty_count": (row_count - non_null_count) if row_count >= 0 and non_null_count >= 0 else -1,
                        "null_pct": round((row_count - non_null_count) / row_count * 100, 2) if row_count > 0 and non_null_count >= 0 else 0,
                        "samples": samples
                    })
        conn.close()
    except Exception as e:
        results["error"] = str(e)
        
    return results

def inspect_parquet_file(pq_path: str):
    res = {
        "file_path": pq_path,
        "row_count": 0,
        "review_columns": []
    }
    try:
        df = pd.read_parquet(pq_path)
        res["row_count"] = len(df)
        res["all_columns"] = df.columns.tolist()
        
        for col in df.columns:
            if check_keyword_match(col):
                series = df[col]
                # non null & non empty
                non_null_mask = series.notna() & (series.astype(str).str.strip() != '') & (series.astype(str).str.strip().str.lower() != 'none') & (series.astype(str).str.strip().str.lower() != 'nan')
                non_null_cnt = int(non_null_mask.sum())
                samples = series[non_null_mask].head(5).tolist()
                samples = [str(s)[:100] for s in samples]
                
                res["review_columns"].append({
                    "column": col,
                    "dtype": str(series.dtype),
                    "total_rows": len(df),
                    "non_null_count": non_null_cnt,
                    "null_or_empty_count": len(df) - non_null_cnt,
                    "null_pct": round((len(df) - non_null_cnt) / len(df) * 100, 2) if len(df) > 0 else 0,
                    "samples": samples
                })
    except Exception as e:
        res["error"] = str(e)
    return res

def inspect_csv_file(csv_path: str):
    res = {
        "file_path": csv_path,
        "row_count": 0,
        "review_columns": []
    }
    try:
        # 인코딩 시도
        try:
            df = pd.read_csv(csv_path, nrows=5000)
        except Exception:
            df = pd.read_csv(csv_path, encoding='cp949', nrows=5000)
            
        res["row_count"] = len(df)
        res["all_columns"] = df.columns.tolist()
        for col in df.columns:
            if check_keyword_match(col):
                series = df[col]
                non_null_mask = series.notna() & (series.astype(str).str.strip() != '') & (series.astype(str).str.strip().str.lower() != 'none') & (series.astype(str).str.strip().str.lower() != 'nan')
                non_null_cnt = int(non_null_mask.sum())
                samples = series[non_null_mask].head(5).tolist()
                samples = [str(s)[:100] for s in samples]
                
                res["review_columns"].append({
                    "column": col,
                    "dtype": str(series.dtype),
                    "total_rows": len(df),
                    "non_null_count": non_null_cnt,
                    "null_or_empty_count": len(df) - non_null_cnt,
                    "null_pct": round((len(df) - non_null_cnt) / len(df) * 100, 2) if len(df) > 0 else 0,
                    "samples": samples
                })
    except Exception as e:
        res["error"] = str(e)
    return res

def main():
    print("=" * 80)
    print("전수 조사: 실제 수강 후기 및 평점 데이터 포함 여부 감사")
    print("=" * 80)
    
    # 1. 원본 SQLite DB 점검
    print("\n--- 1. 원본 SQLite 데이터베이스 전수 점검 ---")
    sqlite_files = glob.glob(os.path.join(BASE_DIR, "data", "**", "*.db"), recursive=True)
    sqlite_results = []
    for db_f in sorted(sqlite_files):
        rel_path = os.path.relpath(db_f, BASE_DIR)
        print(f"\n[DB] {rel_path} ({os.path.getsize(db_f):,} bytes)")
        res = inspect_sqlite_db(db_f)
        sqlite_results.append(res)
        
        for t in res.get("tables", []):
            print(f"  - Table '{t['name']}': {t['row_count']:,} rows, {len(t['columns'])} cols")
            
        if res.get("review_columns"):
            print("  ⭐ 후기/평점 관련 컬럼 발견:")
            for rc in res["review_columns"]:
                print(f"    * [{rc['table']}.{rc['column']}] type={rc['type']}, non_null={rc['non_null_count']:,} / {rc['total_rows']:,} (Null: {rc['null_pct']}%), samples={rc['samples']}")
        else:
            print("  ❌ 후기/평점 관련 컬럼 없음.")

    # 2. 핵심 Parquet 파일 점검
    print("\n\n--- 2. 핵심 Parquet 파일 전수 점검 ---")
    target_parquets = [
        os.path.join(BASE_DIR, "data", "hr", "processed", "education_courses_integrated.parquet"),
        os.path.join(BASE_DIR, "data", "hr", "processed", "education_courses_search_cleaned.parquet"),
        os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "matrix_course_competency_wide.parquet"),
        os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "course_clusters_8645.parquet")
    ]
    parquet_results = []
    for pq_f in target_parquets:
        if os.path.exists(pq_f):
            rel_path = os.path.relpath(pq_f, BASE_DIR)
            print(f"\n[Parquet] {rel_path} ({os.path.getsize(pq_f):,} bytes)")
            res = inspect_parquet_file(pq_f)
            parquet_results.append(res)
            print(f"  - Total rows: {res['row_count']:,}")
            print(f"  - Total columns: {len(res.get('all_columns', []))}")
            if res.get("review_columns"):
                print("  ⭐ 후기/평점 관련 컬럼 발견:")
                for rc in res["review_columns"]:
                    print(f"    * [{rc['column']}] dtype={rc['dtype']}, non_null={rc['non_null_count']:,} / {rc['total_rows']:,} (Null: {rc['null_pct']}%), samples={rc['samples']}")
            else:
                print("  ❌ 후기/평점 관련 컬럼 없음.")
                
    # 3. CSV 및 JSON 중 review 관련 파일 점검
    print("\n\n--- 3. CSV/JSON 중 review 관련 파일 점검 ---")
    rev_files = glob.glob(os.path.join(BASE_DIR, "data", "**", "*review*.*"), recursive=True)
    rev_files += glob.glob(os.path.join(BASE_DIR, "data", "**", "*rating*.*"), recursive=True)
    rev_files = sorted(list(set(rev_files)))
    
    csv_results = []
    for rf in rev_files:
        rel_path = os.path.relpath(rf, BASE_DIR)
        print(f"\n[File] {rel_path} ({os.path.getsize(rf):,} bytes)")
        if rf.endswith('.csv'):
            res = inspect_csv_file(rf)
            csv_results.append(res)
            print(f"  - Rows: {res.get('row_count')}, Cols: {len(res.get('all_columns', []))}")
            for rc in res.get("review_columns", []):
                print(f"    * [{rc['column']}] non_null={rc['non_null_count']:,} / {rc['total_rows']:,}, samples={rc['samples']}")
        elif rf.endswith('.json'):
            with open(rf, 'r', encoding='utf-8') as f:
                try:
                    jdata = json.load(f)
                    if isinstance(jdata, list):
                        print(f"  - JSON List items: {len(jdata):,} items")
                        if jdata:
                            print(f"  - Keys in sample item: {list(jdata[0].keys())}")
                    elif isinstance(jdata, dict):
                        print(f"  - JSON Dict keys: {list(jdata.keys())[:10]}")
                except Exception as e:
                    print(f"  - JSON Error: {e}")

    # 4. 종합 감사 결과 요약 JSON 저장
    audit_summary = {
        "sqlite_results": sqlite_results,
        "parquet_results": parquet_results,
        "review_specific_files": [os.path.relpath(rf, BASE_DIR) for rf in rev_files]
    }
    out_json = os.path.join(BASE_DIR, "data", "hr", "output", "recommendation", "course_reviews_audit_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, ensure_ascii=False, indent=2)
    print(f"\n\n감사 요약 JSON 저장 완료: {out_json}")

if __name__ == "__main__":
    main()
