import pandas as pd
import numpy as np

df = pd.read_parquet('data/hr/processed/education_courses_search_cleaned.parquet')

# Price
null_price = df['price'].isna()
num_price = pd.to_numeric(df['price'], errors='coerce')
is_free = (num_price == 0) & (~null_price)
df['is_free'] = is_free

# Online / Offline
is_online = df['education_type'].str.contains('온라인|사이버|원격|플립', na=False)
is_offline = df['education_type'].str.contains('오프라인|집체|현장', na=False)
df['is_online'] = is_online
df['is_offline'] = is_offline

# Difficulty
diff = df['difficulty'].fillna('실무') # or check values
print("Difficulty values:", df['difficulty'].value_counts(dropna=False))

# Scenario A: 무료 / 온라인 / 입문·실무
# Condition 1: without duration constraint
mask_A_nodur = (df['is_free']) & (df['is_online']) & (df['difficulty'].isin(['입문', '실무']) | df['difficulty'].isna())
print("Scenario A (no duration filter):", mask_A_nodur.sum())

# With duration != UNCONFIRMED:
num_dur = pd.to_numeric(df['duration_hours'], errors='coerce')
mask_A_dur_confirmed = mask_A_nodur & num_dur.notna()
print("Scenario A (duration confirmed only):", mask_A_dur_confirmed.sum())

# Scenario B: KPC/KMA / 오프라인 / 실무·심화 / <= 100만원
is_kpc_kma = df['source_provider'].isin(['KPC', 'KMA']) | df['provider'].str.contains('KPC|KMA|생산성본부|능률협회', na=False)
mask_B_1 = is_kpc_kma & df['is_offline'] & (num_price <= 1000000) & (df['difficulty'].isin(['실무', '관리자/심화', '심화']))
print("Scenario B (실무·심화):", mask_B_1.sum())

mask_B_2 = is_kpc_kma & df['is_offline'] & (num_price <= 1000000) & (df['difficulty'].isin(['입문', '실무', '관리자/심화', '심화']) | df['difficulty'].isna())
print("Scenario B (입문·실무·심화/전체난이도):", mask_B_2.sum())
