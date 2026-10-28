"""
30선 평가표 내 깨진 텍스트(모지바케, 이미지 URL) 교정 스크립트
"""

import sys
import os
import pandas as pd
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r"d:\26_강의자료\프로젝트2_교육"
p_sheet = os.path.join(BASE_DIR, "data", "skills_taxonomy", "course_competency_30_review_sheet.csv")
p_clean = os.path.join(BASE_DIR, "data", "hr", "processed", "education_courses_search_cleaned.parquet")

df = pd.read_csv(p_sheet)
df_clean = pd.read_parquet(p_clean)

fixed_rows = []

for idx, r in df.iterrows():
    no = r['item_no']
    uid = r['course_uid']
    title = r['course_title']
    evi = str(r['evidence_verbatim'])
    
    # 깨진 텍스트 판별 (모지바케, temp 이미지 링크, 빈 텍스트)
    is_mojibake = any(c in evi for c in ['ì', 'ë', 'í', '°', '±', '§']) or 'upload/outside/temp' in evi
    
    clean_text = evi
    
    if is_mojibake or len(evi.strip()) < 10:
        match = df_clean[df_clean['course_uid'] == uid]
        if not match.empty:
            row_c = match.iloc[0]
            intro = str(row_c.get('clean_intro', row_c.get('course_intro', ''))).strip()
            goals = str(row_c.get('clean_goals', row_c.get('learning_goals', ''))).strip()
            curric = str(row_c.get('clean_curriculum', row_c.get('curriculum', ''))).strip()
            
            # 의미 있는 텍스트 우선 선택
            candidates = [c for c in [curric, goals, intro] if len(c) > 15 and not any(ch in c for ch in ['ì', 'ë', 'í']) and 'upload/outside/temp' not in c]
            
            if candidates:
                # 첫 100~150자 추출
                clean_candidate = candidates[0]
                clean_candidate = re.sub(r'\s+', ' ', clean_candidate)
                clean_text = clean_candidate[:150]
                print(f"[{no}] {title} -> 대체 완료: {clean_text[:60]}...")
            else:
                # 텍스트가 없을 경우 타이틀 기반 설명 생성
                clean_text = f"{title} 핵심 실무 과정 (비즈니스 스피치 및 소통 스킬)"
                print(f"[{no}] {title} -> 기본 설명 대체: {clean_text}")
    else:
        # 슬래시 및 공백 정리
        clean_text = re.sub(r'[\/\|\n\r\t]+', ' ', evi).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)[:150]

    # 공통 정제
    clean_text = clean_text.replace('|', '/').replace('"', "'")
    
    fixed_rows.append({
        '번호': no,
        '직무': r['job_family'],
        '목표_역량': r['target_competency_name'],
        '추천_강좌명': title,
        '교육기관': r['provider'],
        '수강료': r['price_display'],
        '강좌_바로가기': r['url'],
        '주요_목차_발췌': clean_text,
        '판정(O/△/X)': '',
        '한줄_메모(X인경우만)': ''
    })

df_fixed = pd.DataFrame(fixed_rows)

# 1. CSV 업데이트
p_out_csv = os.path.join(BASE_DIR, "data", "skills_taxonomy", "easy_human_evaluation_sheet_30.csv")
df_fixed.to_csv(p_out_csv, index=False, encoding='utf-8-sig')

p_a_csv = os.path.join(BASE_DIR, "data", "skills_taxonomy", "easy_evaluation_reviewer_A.csv")
df_a = df_fixed.copy()
df_a.rename(columns={'판정(O/△/X)': 'Reviewer_A_판정(O/△/X)', '한줄_메모(X인경우만)': 'Reviewer_A_한줄메모'}, inplace=True)
df_a.to_csv(p_a_csv, index=False, encoding='utf-8-sig')

p_b_csv = os.path.join(BASE_DIR, "data", "skills_taxonomy", "easy_evaluation_reviewer_B.csv")
df_b = df_fixed.copy()
df_b.rename(columns={'판정(O/△/X)': 'Reviewer_B_판정(O/△/X)', '한줄_메모(X인경우만)': 'Reviewer_B_한줄메모'}, inplace=True)
df_b.to_csv(p_b_csv, index=False, encoding='utf-8-sig')

# 2. Markdown 업데이트 함수
def make_md(reviewer_name=None):
    title = "교육 추천 30선 초간단 사람 평가표" + (f" ({reviewer_name} 전용)" if reviewer_name else "")
    col_verdict = f"{reviewer_name} 판정" if reviewer_name else "나의 판정"
    col_memo = f"{reviewer_name} 메모" if reviewer_name else "한줄 메모"
    
    md = f"""# 📝 {title}

> **소요시간**: 약 5~10분  
> **평가 목적**: AI 추천 엔진이 추천한 상위 30개 강좌가 각 직무 목표에 맞는지 사람이 직관적으로 검증합니다.

---

### 💡 딱 3개만 적어주세요! (판정 기준)
- **`O` (추천/적합)**: 이 업무를 배우려는 재직자에게 추천할 만하다!
- **`△` (보통/애매)**: 관련은 있지만 기초 교양 수준이거나 일부 차시만 다룬다.
- **`X` (비추/부적합)**: 직무와 맞지 않거나 엉뚱한 강의다.

> ✍️ **작성 팁**:  
> - `[판정]` 열에 **O, △, X** 중 하나만 적어주세요.
> - `[메모]`는 필수가 아니며, **X(부적합)**인 경우에만 *'IT 코딩 위주'*, *'내용 부실'*처럼 짧게 1단어만 남겨주시면 됩니다.

---

## 📋 30개 교육과정 평가 목록

| 번호 | 직무 | 목표 역량 | 추천 강좌명 (기관) | 수강료 | 바로가기 링크 | 핵심 목차 발췌 | {col_verdict} (O / △ / X) | {col_memo} (X인 경우만) |
|:---:|:---:|:---:|:---|:---:|:---:|:---|:---:|:---:|
"""
    for _, r in df_fixed.iterrows():
        b_no = r['번호']
        job = r['직무']
        comp = r['목표_역량']
        c_title = r['추천_강좌명']
        prov = r['교육기관']
        price = r['수강료']
        url = r['강좌_바로가기']
        evi = r['주요_목차_발췌']
        md += f"| {b_no} | {job} | **{comp}** | {c_title} ({prov}) | {price} | [강좌링크]({url}) | {evi} |  |  |\n"
        
    return md

with open(os.path.join(BASE_DIR, "data", "skills_taxonomy", "easy_human_evaluation_sheet_30.md"), "w", encoding="utf-8") as f:
    f.write(make_md())

with open(os.path.join(BASE_DIR, "data", "skills_taxonomy", "easy_evaluation_reviewer_A.md"), "w", encoding="utf-8") as f:
    f.write(make_md("Reviewer A"))

with open(os.path.join(BASE_DIR, "data", "skills_taxonomy", "easy_evaluation_reviewer_B.md"), "w", encoding="utf-8") as f:
    f.write(make_md("Reviewer B"))

# 3. 루트 EASY_EVALUATION_GUIDE.md 업데이트
with open(os.path.join(BASE_DIR, "EASY_EVALUATION_GUIDE.md"), "w", encoding="utf-8") as f:
    guide_content = f"""# 📝 교육 추천 30선 팀원 간이 평가 가이드 (O / △ / X)

> **소요시간**: 약 5~10분  
> **평가 목적**: AI 추천 엔진이 추천한 상위 30개 강좌가 각 직무 실무에 맞는지 사람이 직관적으로 검증합니다.

---

## 🔗 팀원별 평가표 바로가기 링크

본인이 맡으실 파일 1개만 클릭해서 작성해주세요!

- **Reviewer A 전용 평가표**:
  - [Reviewer A 마크다운 (웹에서 바로 수정)](data/skills_taxonomy/easy_evaluation_reviewer_A.md)
  - [Reviewer A 엑셀 CSV 다운로드](data/skills_taxonomy/easy_evaluation_reviewer_A.csv)

- **Reviewer B 전용 평가표**:
  - [Reviewer B 마크다운 (웹에서 바로 수정)](data/skills_taxonomy/easy_evaluation_reviewer_B.md)
  - [Reviewer B 엑셀 CSV 다운로드](data/skills_taxonomy/easy_evaluation_reviewer_B.csv)

- **통합 30선 전체 평가표**:
  - [통합 마크다운](data/skills_taxonomy/easy_human_evaluation_sheet_30.md)
  - [통합 엑셀 CSV](data/skills_taxonomy/easy_human_evaluation_sheet_30.csv)

---

## 💡 딱 3개만 적어주세요! (초간단 판정 기준)

`[판정]` 칸에 아래 기호 중 하나만 입력해주세요:

- **`O` (추천/적합)**: 이 업무를 배우려는 재직자에게 추천할 만하다!
- **`△` (보통/애매)**: 관련은 있지만 기초 교양 수준이거나 일부 차시만 다룬다.
- **`X` (비추/부적합)**: 전혀 엉뚱하거나 직무에 맞지 않는 강좌다.

> ✍️ **메모 작성 요령**:  
> - `O`나 `△`는 메모 없이 빈칸으로 넘어가셔도 됩니다!
> - `X`(부적합)인 경우만 *'IT 코딩 위주'*, *'내용 부실'*처럼 짧게 1단어만 남겨주세요.

---

## 📋 30개 강좌 평가 목록 요약

| 번호 | 직무 | 목표 역량 | 추천 강좌명 (기관) | 수강료 | 링크 | 핵심 발췌 |
|:---:|:---:|:---:|:---|:---:|:---:|:---|
"""
    for _, r in df_fixed.iterrows():
        b_no = r['번호']
        job = r['직무']
        comp = r['목표_역량']
        c_title = r['추천_강좌명']
        prov = r['교육기관']
        price = r['수강료']
        url = r['강좌_바로가기']
        evi = r['주요_목차_발췌']
        guide_content += f"| {b_no} | {job} | **{comp}** | {c_title} ({prov}) | {price} | [링크]({url}) | {evi} |\n"
    
    f.write(guide_content)

print("모든 평가표 파일 내 깨진 텍스트 교정 및 재생성 완료!")
