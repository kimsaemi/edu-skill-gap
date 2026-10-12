import sqlite3
import glob
import os
import json

courses_dir = r"data\courses"
dbs = sorted(glob.glob(os.path.join(courses_dir, "*.db")))
print(f"Found {len(dbs)} databases in {courses_dir}:")

report = {}

for db in dbs:
    base_name = os.path.basename(db)
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    
    db_info = {
        "size_bytes": os.path.getsize(db),
        "tables": {}
    }
    
    print("=" * 60)
    print(f"DB: {base_name} ({os.path.getsize(db):,} bytes)")
    
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info({t})")
        cols = [{"name": c[1], "type": c[2], "notnull": c[3], "pk": c[5]} for c in cur.fetchall()]
        
        # sample row
        cur.execute(f"SELECT * FROM {t} LIMIT 1")
        sample = cur.fetchone()
        sample_dict = {}
        if sample:
            for idx, c in enumerate(cols):
                val = sample[idx]
                sample_dict[c["name"]] = str(val)[:50] if val is not None else None

        db_info["tables"][t] = {
            "count": cnt,
            "columns": cols,
            "sample": sample_dict
        }
        print(f"  Table [{t}]: {cnt:,} rows")
        col_names = [c["name"] for c in cols]
        print(f"    Columns ({len(cols)}): {col_names}")
    
    report[base_name] = db_info
    conn.close()

with open("data/courses/inspection_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\nSaved inspection report to data/courses/inspection_report.json")
