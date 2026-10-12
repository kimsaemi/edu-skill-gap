import pandas as pd
import re

df = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

# Find the 29 Base64 courses
b64_mask = df["course_intro"].fillna("").str.contains("base64,") | \
           df["learning_goals"].fillna("").str.contains("base64,") | \
           df["curriculum"].fillna("").str.contains("base64,")

df_b64 = df[b64_mask]
print(f"Total Base64 courses found: {len(df_b64)}")

def clean_course_text(intro, goals, curric, title):
    actions = []
    
    # 1. Base64 stripping
    def strip_b64(text):
        if not text:
            return ""
        # Match data:image...base64,... or [이미지]...base64,... or base64,[A-Za-z0-9+/=]+
        cleaned = re.sub(r'data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=\s]+', ' ', text)
        cleaned = re.sub(r'\[이미지\]\s*https?://[^\s]*base64,[A-Za-z0-9+/=\s]+', ' ', cleaned)
        cleaned = re.sub(r'base64,[A-Za-z0-9+/=\s]{100,}', ' ', cleaned)
        return cleaned

    orig_intro = intro
    orig_goals = goals
    orig_curric = curric
    
    c_intro = strip_b64(intro)
    c_goals = strip_b64(goals)
    c_curric = strip_b64(curric)
    
    if len(c_intro) < len(orig_intro) or len(c_goals) < len(orig_goals) or len(c_curric) < len(orig_curric):
        actions.append("BASE64_STRIPPED")
        
    # 2. HTML stripping
    def strip_html(text):
        if not text:
            return ""
        # Remove tags
        cleaned = re.sub(r'<[^>]+>', ' ', text)
        # HTML entities
        cleaned = re.sub(r'&nbsp;|&gt;|&lt;|&amp;|&quot;|&#39;', ' ', cleaned)
        return cleaned

    h_intro = strip_html(c_intro)
    h_goals = strip_html(c_goals)
    h_curric = strip_html(c_curric)
    if len(h_intro) < len(c_intro) or len(h_goals) < len(c_goals) or len(h_curric) < len(c_curric):
        actions.append("HTML_STRIPPED")
        
    c_intro, c_goals, c_curric = h_intro, h_goals, h_curric

    # 3. Boilerplate removal
    boilerplates = [
        r'귀\s*사는\s*중소기업이신가요\?.*?(?=\n|$)',
        r'\[수강신청하기\]\s*버튼이\s*보이지\s*않을\s*경우.*?(?=\n|$)',
        r'본\s*과정은\s*온오프라인\s*통합과정입니다.*?(?=\n|$)',
        r'\(주\)한국생산성본부는.*?(?=\n|$)',
        r'※\s*본\s*교육은.*?(?=\n|$)',
        r'문의처\s*:\s*.*?(?=\n|$)',
        r'\[이미지\]\s*https?://[^\s]+'
    ]
    for bp in boilerplates:
        c_intro = re.sub(bp, ' ', c_intro)
        c_goals = re.sub(bp, ' ', c_goals)
        c_curric = re.sub(bp, ' ', c_curric)

    # 4. Intro vs Goals deduplication
    clean_intro_s = re.sub(r'\s+', ' ', c_intro).strip()
    clean_goals_s = re.sub(r'\s+', ' ', c_goals).strip()
    clean_curric_s = re.sub(r'\s+', ' ', c_curric).strip()
    
    distinct_goals = ""
    if clean_goals_s:
        if clean_intro_s == clean_goals_s or clean_goals_s in clean_intro_s:
            actions.append("IDENTICAL_GOALS_DEDUPED")
        else:
            distinct_goals = clean_goals_s

    # 5. Build clean search text
    parts = [title]
    if clean_intro_s:
        parts.append(clean_intro_s)
    if distinct_goals:
        parts.append(distinct_goals)
    if clean_curric_s:
        parts.append(clean_curric_s)
        
    clean_search_text = " ".join(parts)
    clean_search_text = re.sub(r'\s+', ' ', clean_search_text).strip()
    
    return clean_search_text, clean_intro_s, distinct_goals, clean_curric_s, ";".join(actions)

# Test on 29 Base64 courses
print("\n--- Testing on Base64 courses ---")
for idx, r in df_b64.head(5).iterrows():
    orig_total_len = len(str(r["course_intro"] or "")) + len(str(r["learning_goals"] or "")) + len(str(r["curriculum"] or ""))
    c_text, c_intro, c_goals, c_curric, acts = clean_course_text(
        str(r["course_intro"] or ""),
        str(r["learning_goals"] or ""),
        str(r["curriculum"] or ""),
        str(r["title"] or "")
    )
    print(f"[{r['course_uid']}] {r['provider']} | {r['title']}")
    print(f"  - 원본 본문 길이: {orig_total_len:,}자 -> 정제 후: {len(c_text):,}자 (감소: {orig_total_len - len(c_text):,}자)")
    print(f"  - 적용 조치: {acts}")
    print(f"  - 보존된 교육 내용 미리보기: {c_text[:150]}...")
    print(f"  - 보존된 커리큘럼 미리보기: {c_curric[:100]}...")
    print("-" * 60)
