"""Register and integrate HR & General Affairs courses from 7 SQLite databases.
Databases:
- fastcampus_courses.db
- gseek_courses.db
- hunet_courses.db
- kfo_courses.db
- kma_courses.db
- kpc_courses.db
- multicampus_courses.db
"""
import sqlite3
import glob
import os
import sys
import re
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(".")
SQLITE_DIR = BASE_DIR / "data" / "SQLite"
PROCESSED_DIR = BASE_DIR / "data" / "hr" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 정밀 키워드 정의 (False Positive 방지)
HR_PATTERNS = [
    # 1. 인사 / HR / 채용 / HRD / HRM
    r"\bHR\b", r"\bHRD\b", r"\bHRM\b", r"인사관리", r"인사담당", r"인사실무", r"인사평가", r"인사기획", 
    r"채용", r"면접관", r"인재확보", r"온보딩", r"조직문화", r"평가보상", r"성과관리", r"연봉", r"인사노무",
    # 2. 노무 / 노동법 / 근로기준법
    r"노무관리", r"노무실무", r"근로기준법", r"노동법", r"취업규칙", r"노사관계", r"퇴직금", r"임금피크", r"주52시간",
    # 3. 총무 / 자산관리 / 비품
    r"총무", r"총무관리", r"총무기획", r"비품관리", r"자산관리", r"고정자산", r"재물조사", r"계약실무", r"사내행사",
    # 4. 사무행정 / 문서기획 / 보고서 / OA
    r"사무행정", r"문서작성", r"기획서", r"보고서 작성", r"비즈니스 글쓰기", r"보고의 기술", r"엑셀 실무", r"사무자동화",
    # 5. 비서 / 비즈니스 매너 / 에티켓
    r"비서", r"비즈니스 매너", r"비즈니스 에티켓", r"직장 예절", r"비즈니스 커뮤니케이션"
]

EXCLUDE_PATTERNS = [
    r"인문학", r"인문", r"인생", r"인사이트", r"개인사", r"시인", r"소설", r"철학", r"역사"
]

hr_regex = re.compile("|".join(HR_PATTERNS), re.IGNORECASE)
exclude_regex = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

def is_hr_course(title, desc="", cat=""):
    text = f"{title} {cat} {desc}"
    if hr_regex.search(text):
        # 제외 패턴만 단독으로 걸린 경우 방지 (예: '인문학'만 있고 '인사'가 아닌 경우)
        # title이나 cat에 직접 HR 키워드가 매칭되는지 확인
        if hr_regex.search(f"{title} {cat}"):
            return True
        # desc에만 매칭된 경우 제외 키워드 검사
        if not exclude_regex.search(title):
            return True
    return False

def classify_job_family(title, cat=""):
    t = f"{title} {cat}".lower()
    if any(k in t for k in ["채용", "면접", "온보딩", "인재확보"]):
        return "인사·채용관리"
    elif any(k in t for k in ["노무", "근로기준", "노동법", "노사", "취업규칙"]):
        return "노무관리"
    elif any(k in t for k in ["인사평가", "평가보상", "성과관리", "연봉"]):
        return "인사·평가보상"
    elif any(k in t for k in ["인사", "hr", "hrd", "hrm", "조직문화"]):
        return "인사·조직관리"
    elif any(k in t for k in ["자산", "비품", "고정자산", "재물조사"]):
        return "총무·자산관리"
    elif any(k in t for k in ["비서", "매너", "에티켓", "예절"]):
        return "비서·사무지원"
    elif any(k in t for k in ["총무"]):
        return "총무·일반사무"
    elif any(k in t for k in ["문서", "기획서", "보고서", "글쓰기", "엑셀", "사무행정"]):
        return "공통·사무기획"
    return "기타·인사총무"

def register_sqlite_databases():
    print("=" * 80)
    print(" [데이터 등록] 7대 SQLite 데이터베이스 전수 등록 및 인사·총무 과정 통합")
    print("=" * 80)

    db_paths = sorted(glob.glob("data/SQLite/*.db"))
    catalog_info = []
    extracted_rows = []

    for db_path in db_paths:
        fname = os.path.basename(db_path)
        platform_id = fname.replace("_courses.db", "")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # 테이블 목록
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        
        # 메인 테이블 courses 확인
        if "courses" not in tables:
            print(f"[-] {fname}: 'courses' 테이블 없음 ({tables})")
            conn.close()
            continue

        df = pd.read_sql_query("SELECT * FROM courses", conn)
        conn.close()

        total_cnt = len(df)
        file_size_kb = os.path.getsize(db_path) // 1024

        # 각 플랫폼별 스키마 매핑
        platform_hr_count = 0
        for _, row in df.iterrows():
            cid = ""
            title = ""
            desc = ""
            cat = ""
            hours = ""
            days = ""
            price = ""
            url = ""

            if platform_id == "fastcampus":
                cid = str(row.get("id", ""))
                title = str(row.get("title", ""))
                desc = str(row.get("description", ""))
                cat = f"{row.get('category_name', '')} > {row.get('subcategory_name', '')}"
                price = str(row.get("sale_price", row.get("list_price", "")))
                url = str(row.get("url", ""))
            elif platform_id == "gseek":
                cid = str(row.get("course_sn", ""))
                title = str(row.get("title", ""))
                desc = str(row.get("description", ""))
                cat = f"{row.get('category_depth1', '')} > {row.get('category_depth2', '')}"
                price = "0"  # 경기도 무료
                url = str(row.get("url", ""))
            elif platform_id == "hunet":
                cid = str(row.get("goods_id", row.get("process_code", "")))
                title = str(row.get("title", ""))
                cat = f"{row.get('category_depth1', '')} > {row.get('category_depth2', '')} > {row.get('category_depth3', '')}"
                url = str(row.get("url", ""))
            elif platform_id == "kfo":
                cid = str(row.get("course_id", ""))
                title = str(row.get("title", ""))
                cat = f"{row.get('category', '')} > {row.get('subcategory', '')}"
                price = str(row.get("price_sale", ""))
                desc = str(row.get("curriculum_summary", ""))
                url = str(row.get("url", ""))
            elif platform_id == "kma":
                cid = str(row.get("crscd", row.get("crsseq_id", "")))
                title = str(row.get("title", ""))
                cat = str(row.get("category_name", ""))
                hours = str(row.get("hours", ""))
                days = str(row.get("days", ""))
                price = str(row.get("fee_regular", ""))
                url = str(row.get("url", ""))
            elif platform_id == "kpc":
                cid = str(row.get("ecno", row.get("cono", "")))
                title = str(row.get("title", ""))
                cat = str(row.get("category_name", ""))
                hours = str(row.get("hours", ""))
                days = str(row.get("days", ""))
                price = str(row.get("fee_general", ""))
                url = str(row.get("url", ""))
            elif platform_id == "multicampus":
                cid = str(row.get("course_code", ""))
                title = str(row.get("title", ""))
                cat = f"{row.get('category', '')} > {row.get('subcategory', '')}"
                hours = str(row.get("hours", ""))
                days = str(row.get("days", ""))
                price = str(row.get("fee", ""))
                url = str(row.get("url", ""))

            # 정밀 HR 필터링
            if is_hr_course(title, desc, cat):
                job_fam = classify_job_family(title, cat)
                platform_hr_count += 1
                extracted_rows.append({
                    "platform": platform_id.upper(),
                    "source_db": fname,
                    "course_id": cid,
                    "instance_key": f"SQLITE_{platform_id.upper()}_{cid}",
                    "course_name": title,
                    "category": cat,
                    "duration_hours": hours,
                    "duration_days": days,
                    "price_raw": price,
                    "url": url,
                    "description_snippet": desc[:120] if desc else "",
                    "job_family": job_fam
                })

        catalog_info.append({
            "platform_name": platform_id.upper(),
            "database_file": fname,
            "file_size_kb": file_size_kb,
            "total_courses": total_cnt,
            "hr_ga_courses_matched": platform_hr_count,
            "matching_rate": f"{platform_hr_count / total_cnt * 100:.1f}%"
        })
        print(f"[+] {platform_id.upper()} ({fname}): 전체 {total_cnt:,}건 중 인사·총무 부합 과정 {platform_hr_count:,}건 등록")

    df_extracted = pd.DataFrame(extracted_rows)
    
    # 중복 제거 (과정명 + 플랫폼 동일한 경우)
    dup_cnt = df_extracted.duplicated(subset=["platform", "course_name"]).sum()
    df_extracted_clean = df_extracted.drop_duplicates(subset=["platform", "course_name"]).copy()

    # CSV 저장
    out_csv = PROCESSED_DIR / "sqlite_hr_courses_integrated.csv"
    df_extracted_clean.to_csv(out_csv, index=False, encoding="utf-8-sig")

    # 메타 카탈로그 JSON 저장
    out_json = SQLITE_DIR / "sqlite_database_catalog.json"
    catalog_summary = {
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "total_databases": len(catalog_info),
        "total_courses_in_dbs": sum(c["total_courses"] for c in catalog_info),
        "total_hr_ga_extracted": len(df_extracted_clean),
        "duplicate_courses_removed": int(dup_cnt),
        "databases": catalog_info,
        "job_family_distribution": df_extracted_clean["job_family"].value_counts().to_dict(),
        "platform_distribution": df_extracted_clean["platform"].value_counts().to_dict()
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(catalog_summary, f, ensure_ascii=False, indent=2)

    # README.md 작성
    out_readme = SQLITE_DIR / "README.md"
    with open(out_readme, "w", encoding="utf-8") as f:
        f.write("# 7대 교육 플랫폼 SQLite 데이터베이스 카탈로그 및 등록 명세서\n\n")
        f.write(f"- **등록 일시**: {catalog_summary['registered_at']}\n")
        f.write(f"- **총 데이터베이스 수**: 7개 파일\n")
        f.write(f"- **전체 수록 교육과정 수**: **{catalog_summary['total_courses_in_dbs']:,}건**\n")
        f.write(f"- **인사·총무 부합 교육과정 수 (정제 후)**: **{len(df_extracted_clean):,}건**\n\n")
        f.write("## 1. 데이터베이스별 현황\n\n")
        f.write("| 플랫폼 | DB 파일명 | 파일 크기 | 전체 강좌 수 | 인사·총무 강좌 수 | 비중 (%) |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: |\n")
        for c in catalog_info:
            f.write(f"| **{c['platform_name']}** | `{c['database_file']}` | {c['file_size_kb']:,} KB | {c['total_courses']:,}건 | **{c['hr_ga_courses_matched']:,}건** | {c['matching_rate']} |\n")
        f.write("\n## 2. 직무별 분포\n\n")
        f.write("| 세부 직무 분야 | 강좌 수 | 비율 (%) |\n")
        f.write("| :--- | :---: | :---: |\n")
        for jf, count in df_extracted_clean["job_family"].value_counts().items():
            f.write(f"| **{jf}** | {count:,}건 | {count/len(df_extracted_clean)*100:.1f}% |\n")

    print("\n" + "=" * 80)
    print(f"[✓] 등록 완료:")
    print(f"    - 인사·총무 통합 추출 파일: {out_csv} ({len(df_extracted_clean):,}건)")
    print(f"    - 메타데이터 카탈로그: {out_json}")
    print(f"    - 문서화: {out_readme}")
    print("=" * 80)

    print("\n[직무별 분포]")
    print(df_extracted_clean["job_family"].value_counts())
    print("\n[플랫폼별 인사·총무 과정 분포]")
    print(df_extracted_clean["platform"].value_counts())

if __name__ == "__main__":
    register_sqlite_databases()
