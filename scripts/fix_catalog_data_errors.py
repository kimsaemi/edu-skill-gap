"""
검색 카탈로그(education_courses_search_cleaned.parquet)의 가격·일정·시간 오류를 정정한다. (2026-10-31 데이터 검증)

1. 가격 0원인데 '정액 유료'로 표시된 한국생산성본부 과정
   - 제목에 '무료'·'설명회'가 있으면 → price_type '무료'
   - '두산_'으로 시작하는 두산 협력기업 전용 과정 → price_type '기업/유료 (문의)', price 비움
   - 그 밖에는 가격이 공개되지 않은 것으로 보고 → price_type '미기재 (문의)', price 비움
2. 시작일이 종료일보다 늦은 과정
   - 하루 안에 끝나는 과정(8시간 이하) → 종료일을 시작일로 맞춤
   - 그 밖에는 어느 날짜가 맞는지 알 수 없어 종료일을 비움
3. 교육 시간이 0 이하인 행 → 시간을 비움 (수강권처럼 과정이 아닌 행은 제외 목록에서 따로 뺌)

과정 문장은 바꾸지 않으므로 임베딩·BM25 색인은 다시 만들 필요가 없다. 여러 번 실행해도 결과가 같다.
실행: python scripts/fix_catalog_data_errors.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
LOG = ROOT / "data" / "hr" / "reports" / "catalog_data_fixes.csv"


def main():
    df = pd.read_parquet(CATALOG)
    log = []

    def note(i, col, old, new, why):
        log.append({"course_uid": df.at[i, "course_uid"], "title": df.at[i, "title"], "column": col,
                    "before": old, "after": new, "reason": why})

    # 1) 0원 + 정액 유료
    price = pd.to_numeric(df["price"], errors="coerce")
    bad = df.index[(price == 0) & (df["price_type"].fillna("") == "정액 유료")]
    for i in bad:
        t = str(df.at[i, "title"])
        if re.search(r"무료|설명회", t):
            new_type, new_price, why = "무료", 0, "제목에 무료 표시"
        elif t.startswith("두산_"):
            new_type, new_price, why = "기업/유료 (문의)", None, "두산 협력기업 전용 과정"
        else:
            new_type, new_price, why = "미기재 (문의)", None, "가격 비공개(0원으로 수집됨)"
        note(i, "price_type", "정액 유료", new_type, why)
        if new_price is None:
            note(i, "price", 0, "", why)
            df.at[i, "price"] = pd.NA
        df.at[i, "price_type"] = new_type

    # 2) 시작일 > 종료일
    st = df["start_date"].fillna("").astype(str).str[:10]
    en = df["end_date"].fillna("").astype(str).str[:10]
    hours = pd.to_numeric(df["duration_hours"], errors="coerce")
    rev = df.index[st.str.match(r"\d{4}-\d{2}-\d{2}") & en.str.match(r"\d{4}-\d{2}-\d{2}") & (st > en)]
    for i in rev:
        if hours[i] <= 8:
            note(i, "end_date", en[i], st[i], "하루 과정: 종료일을 시작일로")
            df.at[i, "end_date"] = df.at[i, "start_date"]
        else:
            note(i, "end_date", en[i], "", "시작일이 종료일보다 늦음: 맞는 날짜를 알 수 없어 비움")
            df.at[i, "end_date"] = None

    # 3) 시간 0 이하
    for i in df.index[hours <= 0]:
        note(i, "duration_hours", hours[i], "", "교육 시간 0 이하")
        df.at[i, "duration_hours"] = np.nan

    df.to_parquet(CATALOG, index=False, compression="zstd", compression_level=9)  # 원본과 같은 압축·용량 (약 30MB)
    out = pd.DataFrame(log)
    if LOG.exists() and len(out) == 0:
        print("이미 정정된 상태입니다. 바뀐 것 없음.")
        return
    out.to_csv(LOG, index=False, encoding="utf-8-sig")
    print(f"정정 {len(out)}건 → {LOG.relative_to(ROOT)}")
    print(out.groupby(["column", "reason"]).size().to_string())


if __name__ == "__main__":
    main()
