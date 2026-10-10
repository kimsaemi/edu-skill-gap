"""Inspect all 7 SQLite databases in data/SQLite/."""
import sqlite3
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

db_files = sorted(glob.glob("data/SQLite/*.db"))
print(f"Found {len(db_files)} SQLite files:\n")

total_courses_across_dbs = 0

for db_path in db_files:
    fname = os.path.basename(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    print(f"=== {fname} ===")
    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl});")
        cols = [c[1] for c in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        cnt = cur.fetchone()[0]
        total_courses_across_dbs += cnt
        print(f"  Table: {tbl} (Count: {cnt})")
        print(f"    Columns ({len(cols)}): {cols}")
        cur.execute(f"SELECT * FROM {tbl} LIMIT 1;")
        row = cur.fetchone()
        if row:
            sample_dict = dict(zip(cols, [str(v)[:50] if v is not None else "None" for v in row]))
            print(f"    Sample: {sample_dict}")
    conn.close()
    print()

print(f"Total rows across all tables: {total_courses_across_dbs}")
