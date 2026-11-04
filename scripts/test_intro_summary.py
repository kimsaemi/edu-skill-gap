# -*- coding: utf-8 -*-
"""
과정 소개 요약(course_intro_summary) 단위 및 회귀 테스트
- GSEEK·KPC·KMA·HUNET 4개 주요 기관에서 1개 이상의 요약이 비어있지 않은지 검증
- 모든 요약이 200자 이하인지 검증
- 요약이 원문(learning_goals, course_intro, curriculum)의 앞부분과 정확히 일치하는지 검증 (지어낸 문장 방지)
- 기관별 요약 누락(빈 문자열) 비율 통계 출력
"""

import re
import sys
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.customer.career_platform import courses, course_intro_summary

def main():
    print("=== [테스트] 과정 소개 요약(course_intro_summary) 검증 ===")
    df = courses()
    
    # 1. 200자 이하 및 원문 일치 검증
    checked_count = 0
    non_empty_count = 0
    
    for idx, row in df.iterrows():
        summary = course_intro_summary(row)
        assert len(summary) <= 200, f"요약 길이 200자 초과: {len(summary)}자 (UID: {row['course_uid']})"
        
        if summary:
            non_empty_count += 1
            # 원문 필드 중 하나와 정확히 매칭되는지 확인
            matched = False
            for col in ["learning_goals", "course_intro", "curriculum"]:
                raw_val = row.get(col)
                if pd.notna(raw_val) and raw_val is not None:
                    cleaned = re.sub(r"\s+", " ", str(raw_val)).strip()
                    if cleaned and cleaned.startswith(summary):
                        matched = True
                        break
            assert matched, f"요약이 원문의 앞부분과 일치하지 않음 (지어낸 문장 의심): {row['course_uid']}\n요약: {summary}"
        checked_count += 1
        
    print(f"[PASS] 전체 {checked_count:,}개 강좌 200자 이하 및 원문 일치성(Fidelity) 100% 통과")

    # 2. 4대 주요 기관(GSEEK, KPC, KMA, HUNET) 비어있지 않은 과정 존재 검증
    target_providers = {
        "GSEEK": "GSEEK",
        "KPC": "한국생산성본부",
        "KMA": "한국능률협회",
        "HUNET": "휴넷",
    }
    
    provider_stats = {}
    for short_name, prov_str in target_providers.items():
        sub = df[df["provider"].astype(str).str.contains(prov_str, case=False, na=False)]
        assert len(sub) > 0, f"기관 {prov_str}의 강좌를 찾을 수 없음"
        
        sub_summaries = [course_intro_summary(r) for _, r in sub.iterrows()]
        has_non_empty = any(s != "" for s in sub_summaries)
        assert has_non_empty, f"기관 {prov_str}의 요약이 모두 비어있음"
        
        empty_cnt = sum(s == "" for s in sub_summaries)
        total_cnt = len(sub_summaries)
        empty_ratio = (empty_cnt / total_cnt) * 100
        provider_stats[short_name] = {
            "total": total_cnt,
            "non_empty": total_cnt - empty_cnt,
            "empty": empty_cnt,
            "empty_ratio": empty_ratio,
        }
        print(f"[PASS] {short_name} ({prov_str}): {total_cnt - empty_cnt:,}개 요약 존재 확인 (빈 비율: {empty_ratio:.1f}%)")

    # 3. 기관별 요약 누락 비율 통계 출력
    print("\n=== [통계] 주요 기관별 과정 소개 요약 보유율 및 누락 비율 ===")
    print(f"{'기관명':<10} | {'전체 강좌':<8} | {'요약 보유':<8} | {'요약 비어있음':<8} | {'누락 비율(%)'}")
    print("-" * 55)
    for name, st in provider_stats.items():
        print(f"{name:<10} | {st['total']:<8} | {st['non_empty']:<8} | {st['empty']:<8} | {st['empty_ratio']:.1f}%")

    # 전체 코퍼스 통계
    all_empty = checked_count - non_empty_count
    print("-" * 55)
    print(f"{'전체 코퍼스':<10} | {checked_count:<8} | {non_empty_count:<8} | {all_empty:<8} | {all_empty/checked_count*100:.1f}%\n")
    print("🎉 과정 소개 요약 단위 및 회귀 테스트 전체 통과!")

if __name__ == "__main__":
    main()

