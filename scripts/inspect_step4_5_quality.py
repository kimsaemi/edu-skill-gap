import pandas as pd
import numpy as np

df_ver = pd.read_csv("data/hr/output/integration/hr_integrated_verified.csv")
df_map = pd.read_csv("data/hr/output/integration/hr_mapping_verified.csv")

print("=== 1. 매핑 다중성 분석 ===")
def find_competencies(name, desc):
    text = (str(name) + " " + str(desc)).lower()
    comps = []
    if any(k in text for k in ["채용", "면접", "인재선발", "인재확보", "온보딩", "헤드헌팅", "모집"]):
        comps.append(("COMP_HR_01", "인력채용"))
    if any(k in text for k in ["평가", "보상", "연봉", "성과관리", "mbo", "kpi", "인사고과"]):
        comps.append(("COMP_HR_02", "인사평가 및 보상"))
    if any(k in text for k in ["노무", "근로기준법", "노동법", "취업규칙", "퇴직", "해고", "임금", "통상임금", "근로계약", "노사"]):
        comps.append(("COMP_LABOR_01", "근로관계 법률 준수"))
    if any(k in text for k in ["문서", "기획", "보고서", "기획서", "사무문서", "비즈니스 글쓰기", "공문서", "엑셀", "오피스", "워드"]):
        comps.append(("COMP_GA_01", "문서작성 및 기획"))
    if any(k in text for k in ["자산", "비품", "시설", "고정자산", "계약", "구매", "물품"]):
        comps.append(("COMP_GA_02", "비품 및 자산관리"))
    if any(k in text for k in ["매너", "에티켓", "의전", "비서", "소통", "커뮤니케이션", "전화응대", "직장예절"]):
        comps.append(("COMP_SEC_01", "비즈니스 매너 및 커뮤니케이션"))
    if any(k in text for k in ["애자일", "스크럼", "프로젝트 관리", "pm", "pmo", "일정관리"]):
        comps.append(("COMP_MGMT_01", "애자일 프로젝트 관리"))
    return comps

df_ver["comps"] = [find_competencies(n, d) for n, d in zip(df_ver["course_name"], df_ver["course_description"])]
df_ver["c_len"] = df_ver["comps"].apply(len)

print("과정별 매핑 가능 역량 수 분포:")
print(df_ver["c_len"].value_counts().sort_index())

print("\n--- 0개 매칭 과정 (키워드 부족으로 강제 할당 의심 사례 33건 중 샘플) ---")
for _, r in df_ver[df_ver["c_len"] == 0][["course_name", "job_category"]].head(10).iterrows():
    print(f"[{r['job_category']}] {r['course_name']}")

print("\n--- 2개 이상 매칭 과정 (융합/다중 KSA 사례 47건 중 샘플) ---")
for _, r in df_ver[df_ver["c_len"] == 2][["course_name", "comps"]].head(10).iterrows():
    c_names = [c[1] for c in r["comps"]]
    print(f"{r['course_name']} -> {c_names}")

print("\n=== 2. 난이도 집계 정합성 확인 ===")
print("현재 course_level 값 분포:")
print(df_ver["course_level"].value_counts())
print("\njob_group x course_level 교차표:")
print(pd.crosstab(df_ver["job_group"], df_ver["course_level"]))

print("\n=== 3. 비용 및 교육시간 이상치 및 결측 점검 ===")
print("수강료 통계:")
print(df_ver["course_fee"].describe())
print("수강료 0원 건수:", (df_ver["course_fee"] == 0).sum())
print("수강료 > 100만원 건수:", (df_ver["course_fee"] > 1000000).sum())
print("수강료 Top 5:", df_ver["course_fee"].nlargest(5).tolist())

print("\n교육시간 통계:")
print(df_ver["training_hours"].describe())
print("교육시간 결측 건수:", df_ver["training_hours"].isna().sum())
print("교육일수(duration_days) 통계:")
print(df_ver["duration_days"].describe())
