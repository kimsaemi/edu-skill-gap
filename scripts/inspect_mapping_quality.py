import pandas as pd
import json

df = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

print("Total courses:", len(df))
print("\nMapping Status Breakdown:")
print(df["mapping_status"].value_counts())

# Check how ncs_code is populated
print("\nUnique ncs_code values (Top 20):")
print(df["ncs_code"].value_counts().head(20))

# Distinguish official NCS codes vs Project Custom KSA IDs:
def classify_code_type(code):
    if not code or code.strip() == "":
        return "NONE"
    code = str(code).strip()
    if code.startswith("COMP_"):
        return "PROJECT_CUSTOM_KSA_ID"
    # Check if numeric (official NCS code, e.g. 02020101, 2020201)
    cleaned_num = code.replace(".0", "").replace(".", "").replace("-", "")
    if cleaned_num.isdigit():
        return "OFFICIAL_NCS_CODE"
    return "OTHER"

df["code_type"] = df["ncs_code"].apply(classify_code_type)
print("\nCode Type Distribution:")
print(df["code_type"].value_counts())

# Inspect VERIFIED courses:
# Are there any potential false positives? e.g. IT/Software, Cooking, Beauty, Welding, Health courses mapped to COMP_HR, COMP_GA, COMP_MGMT?
suspicious_keywords = [
    "요리", "제과", "제빵", "바리스타", "뷰티", "미용", "헤어", "네일",
    "용접", "지게차", "전기기사", "위험물", "도배", "타일", "간호", "의료",
    "보육", "사회복지", "유치원", "파이썬", "자바", "C언어", "웹개발",
    "머신러닝", "딥러닝", "코딩", "클라우드", "AWS", "정보처리기사"
]

mismatches = []
for idx, r in df.iterrows():
    title = str(r["title"] or "")
    ncs = str(r["ncs_code"] or "")
    status = r["mapping_status"]
    
    # Check if title has suspicious non-HR/GA keywords but mapped to HR/GA/Labor/Sec
    for kw in suspicious_keywords:
        if kw in title and (ncs.startswith("COMP_HR") or ncs.startswith("COMP_GA") or ncs.startswith("COMP_LABOR") or ncs.startswith("COMP_SEC")):
            mismatches.append({
                "course_uid": r["course_uid"],
                "provider": r["provider"],
                "title": title,
                "ncs_code": ncs,
                "mapping_status": status,
                "confidence": r.get("mapping_confidence", 0),
                "matched_suspicious_keyword": kw,
                "reason": f"기술/IT/기능/자격증 과정('{kw}')이 HR/총무 역량({ncs})으로 자동 분류됨"
            })
            break

print(f"\nPotential False Positive Auto-Mappings detected: {len(mismatches)} courses")
for m in mismatches[:10]:
    print(f"[{m['course_uid']}] {m['provider']} | {m['title']} -> {m['ncs_code']} ({m['mapping_status']}) [사유: {m['reason']}]")

with open("data/hr/output/recommendation/mapping_mismatch_samples.json", "w", encoding="utf-8") as f:
    json.dump(mismatches, f, ensure_ascii=False, indent=2)
