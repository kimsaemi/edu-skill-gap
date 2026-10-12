import pandas as pd
import numpy as np
import re
import json

# Read parquet
df = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

print("Total courses:", len(df))

# Check length distributions
text_cols = ['title', 'course_intro', 'learning_goals', 'curriculum', 'target_audience']
for col in text_cols:
    lens = df[col].fillna("").astype(str).str.len()
    print(f"[{col}] max: {lens.max():,}, min: {lens.min():,}, mean: {lens.mean():.1f}, median: {lens.median():.1f}, >100k: {(lens > 100000).sum()}, ==0: {(lens == 0).sum()}")

# Inspect the top 5 longest courses in total combined text
combined_lens = df[text_cols].fillna("").astype(str).sum(axis=1).str.len()
top_indices = combined_lens.nlargest(10).index

results = []
for idx in top_indices:
    row = df.loc[idx]
    c_len = combined_lens.loc[idx]
    results.append({
        "course_uid": row["course_uid"],
        "provider": row["provider"],
        "title": row["title"],
        "session_id": row.get("session_id", ""),
        "total_chars": int(c_len),
        "intro_len": len(str(row["course_intro"] or "")),
        "goals_len": len(str(row["learning_goals"] or "")),
        "curric_len": len(str(row["curriculum"] or "")),
    })

print("\n--- Top 10 Longest Courses ---")
for r in results:
    print(r)

# Let's inspect the longest record in detail:
longest_row = df.loc[top_indices[0]]
print(f"\nLongest record UID: {longest_row['course_uid']}")
print(f"Title: {longest_row['title']}")
print(f"Intro snippet (first 500 chars):\n{str(longest_row['course_intro'])[:500]}")
print(f"Curriculum snippet (first 500 chars):\n{str(longest_row['curriculum'])[:500]}")

# Why is it 2 million characters? Let's check for repetition or patterns:
intro_str = str(longest_row['course_intro'] or "")
print(f"Intro total length: {len(intro_str):,}")
# Check if there are repeated blocks:
# Count occurrences of some common phrase:
sample_phrase = intro_str[:50]
count = intro_str.count(sample_phrase)
print(f"Count of intro first 50 chars in intro: {count}")

# Check base64 images or embedded HTML
has_base64 = "base64" in intro_str or "data:image" in intro_str
print(f"Contains base64 image data: {has_base64}")
has_html = bool(re.search(r"<[a-zA-Z]+[^>]*>", intro_str))
print(f"Contains HTML tags: {has_html}")

# Check unique strings or repeated lines
lines = intro_str.split("\n")
print(f"Total lines in intro: {len(lines)}, Unique lines: {len(set(lines))}")
if len(lines) > 0:
    from collections import Counter
    line_counts = Counter(lines).most_common(5)
    print(f"Most common lines: {line_counts}")

# Save detailed analysis
with open("data/hr/reports/anomaly_inspection_debug.json", "w", encoding="utf-8") as f:
    json.dump({
        "top_10_longest": results,
        "sample_snippet": str(longest_row['course_intro'])[:2000]
    }, f, ensure_ascii=False, indent=2)

print("\nSaved anomaly debug to data/hr/reports/anomaly_inspection_debug.json")
