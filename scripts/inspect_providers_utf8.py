import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')
print("=== source_provider value counts ===")
print(df['source_provider'].value_counts())

print("\n=== top 15 providers ===")
print(df['provider'].value_counts().head(15))

print("\n=== source_provider vs provider cross-tab ===")
ct = pd.crosstab(df['source_provider'], df['provider'].head(10))
print(df.groupby(['source_provider', 'provider']).size())
