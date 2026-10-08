import json
import pandas as pd
from pathlib import Path

raw_dir = Path("data/hr/raw")

files = {
    "국민내일배움카드": raw_dir / "kmbc_courses_raw.json",
    "사업주훈련": raw_dir / "employer_courses_raw.json",
    "NCS 교육과정": raw_dir / "ncs_courses_raw.json"
}

summary = {}

for name, p in files.items():
    if not p.exists():
        print(f"File not found: {p}")
        continue
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # 결측률 계산
    null_counts = df.isnull().sum()
    null_rates = (null_counts / len(df) * 100).round(1)
    
    # 중복 후보 검토
    dup_all = df.duplicated().sum()
    
    # ID/코드 기준 중복 검토
    id_col = None
    for cand in ["trprId", "asubjName", "title"]:
        if cand in df.columns:
            id_col = cand
            break
            
    dup_id = df.duplicated(subset=[id_col]).sum() if id_col else 0
    
    summary[name] = {
        "rows": len(df),
        "cols": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "null_rates": {c: f"{null_rates[c]}% ({null_counts[c]}/{len(df)})" for c in df.columns if null_counts[c] > 0},
        "fully_null_cols": [c for c in df.columns if null_counts[c] == len(df)],
        "duplicate_rows": int(dup_all),
        "duplicate_by_primary_key": {id_col: int(dup_id)} if id_col else {},
        "sample_head": df.head(2).to_dict(orient="records")
    }

print(json.dumps(summary, ensure_ascii=False, indent=2))
with open("data/hr/raw/eda_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
