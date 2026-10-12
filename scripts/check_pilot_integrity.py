import pandas as pd

df_p = pd.read_parquet("data/hr/processed/pilot_courses_embedding_400.parquet")
print(f"Pilot total rows: {len(df_p)}")
print(f"Pilot unique UIDs: {df_p['course_uid'].nunique()}")
print(f"Duplicate rows: {len(df_p) - df_p['course_uid'].nunique()}")

print("\nProvider distribution:")
print(df_p["provider"].value_counts())

print("\nText quality status distribution:")
print(df_p["text_quality_status"].value_counts())

print("\nClean search text check:")
empty_texts = df_p["clean_search_text"].fillna("").str.strip().eq("").sum()
print(f"Empty search texts: {empty_texts}")
print(f"Mean text length: {df_p['clean_search_text'].str.len().mean():.1f} chars")
print(f"Min text length: {df_p['clean_search_text'].str.len().min()} chars")
print(f"Max text length: {df_p['clean_search_text'].str.len().max()} chars")

# Check alignment: ensure title is in clean_search_text
mismatch_count = 0
for idx, r in df_p.iterrows():
    if str(r["title"]) not in str(r["clean_search_text"]):
        mismatch_count += 1
print(f"Title-to-search_text alignment mismatches: {mismatch_count}")
