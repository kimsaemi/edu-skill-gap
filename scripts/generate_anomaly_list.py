import pandas as pd
import numpy as np
import re

df = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

anomalies = []

for idx, r in df.iterrows():
    uid = r["course_uid"]
    provider = r["provider"]
    title = str(r["title"] or "")
    intro = str(r["course_intro"] or "")
    goals = str(r["learning_goals"] or "")
    curric = str(r["curriculum"] or "")
    
    total_len = len(intro) + len(goals) + len(curric)
    
    # 1. Base64 embedded image
    has_b64 = "base64," in intro or "base64," in goals or "base64," in curric
    
    # 2. Extreme length (> 100,000 chars)
    is_extreme_len = total_len > 100000
    
    # 3. Intro == Goals duplication (when len > 50)
    is_intro_goals_dup = (intro == goals) and (len(intro) > 50)
    
    # 4. Title only (total body == 0 or < 50 chars)
    is_title_only = total_len == 0
    is_very_short = (0 < total_len < 50)
    
    # 5. Marketing/HTML/Boilerplate repetition
    has_boilerplate = "중소기업이신가요?" in intro or "수강신청하기" in intro or "우선지원대상기업" in intro
    
    # 6. HTML or raw URL spam in text
    has_html_tags = bool(re.search(r"<[a-zA-Z]+[^>]*>", intro + goals + curric))
    
    anomaly_types = []
    if has_b64:
        anomaly_types.append("BASE64_IMAGE_EMBEDDED")
    if is_extreme_len:
        anomaly_types.append("EXTREME_TEXT_LENGTH")
    if is_intro_goals_dup:
        anomaly_types.append("INTRO_GOALS_IDENTICAL")
    if is_title_only:
        anomaly_types.append("TITLE_ONLY_ZERO_BODY")
    elif is_very_short:
        anomaly_types.append("VERY_SHORT_BODY_UNDER_50")
    if has_boilerplate:
        anomaly_types.append("REPETITIVE_MARKETING_NOTICE")
    if has_html_tags:
        anomaly_types.append("RAW_HTML_TAGS")
        
    if anomaly_types:
        anomalies.append({
            "course_uid": uid,
            "provider": provider,
            "title": title,
            "total_body_len": total_len,
            "intro_len": len(intro),
            "goals_len": len(goals),
            "curric_len": len(curric),
            "anomaly_types": ";".join(anomaly_types),
            "has_base64": has_b64,
            "is_extreme_len": is_extreme_len,
            "is_intro_goals_dup": is_intro_goals_dup,
            "is_title_only": is_title_only,
            "has_boilerplate": has_boilerplate,
            "detail_snippet": intro[:200].replace("\n", " ") if intro else curric[:200].replace("\n", " ")
        })

df_anomalies = pd.DataFrame(anomalies)
df_anomalies.to_csv("data/hr/output/recommendation/anomalous_texts_list.csv", index=False, encoding="utf-8-sig")

print(f"Total anomaly courses detected: {len(df_anomalies):,} / {len(df):,}")
print("\nAnomaly Breakdown:")
print(f" - Base64 Image Embedded: {df_anomalies['has_base64'].sum():,}건")
print(f" - Extreme Length (>100k chars): {df_anomalies['is_extreme_len'].sum():,}건")
print(f" - Intro == Goals Identical (>50 chars): {df_anomalies['is_intro_goals_dup'].sum():,}건")
print(f" - Title Only (0 chars body): {df_anomalies['is_title_only'].sum():,}건")
print(f" - Repetitive Boilerplate Notice: {df_anomalies['has_boilerplate'].sum():,}건")
