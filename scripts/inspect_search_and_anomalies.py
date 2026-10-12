import pandas as pd
import numpy as np

# 1. Search Results Stats
df_t = pd.read_csv("data/hr/output/recommendation/search_results_tfidf_top10.csv")
df_b = pd.read_csv("data/hr/output/recommendation/search_results_bm25_top10.csv")

print("=" * 80)
print(" [1] 15개 질문별 실제 CSV 검색 결과 전수 대조")
print("=" * 80)

qids = df_t["query_id"].unique()
top1_matches = 0
top1_title_matches = 0
jaccards = []
overlap_counts = []

query_summary = []

for qid in qids:
    sub_t = df_t[df_t["query_id"] == qid]
    sub_b = df_b[df_b["query_id"] == qid]
    
    t_top1 = sub_t.iloc[0] if len(sub_t) > 0 else None
    b_top1 = sub_b.iloc[0] if len(sub_b) > 0 else None
    
    uid_match = (t_top1["course_uid"] == b_top1["course_uid"]) if (t_top1 is not None and b_top1 is not None) else False
    title_match = (t_top1["course_name"] == b_top1["course_name"]) if (t_top1 is not None and b_top1 is not None) else False
    
    if uid_match:
        top1_matches += 1
    if title_match:
        top1_title_matches += 1
        
    t_set = set(sub_t["course_uid"])
    b_set = set(sub_b["course_uid"])
    inter = len(t_set & b_set)
    union = len(t_set | b_set)
    j = inter / union if union > 0 else 0
    jaccards.append(j)
    overlap_counts.append(inter)
    
    q_text = sub_t["query"].iloc[0]
    t_title = t_top1["course_name"] if t_top1 is not None else "None"
    b_title = b_top1["course_name"] if b_top1 is not None else "None"
    t_score = t_top1["score"] if t_top1 is not None else 0
    b_score = b_top1["score"] if b_top1 is not None else 0
    
    query_summary.append({
        "qid": qid,
        "query": q_text,
        "uid_match": uid_match,
        "title_match": title_match,
        "overlap_count": inter,
        "jaccard": j,
        "tfidf_top1_uid": t_top1["course_uid"] if t_top1 is not None else None,
        "tfidf_top1_name": t_title,
        "tfidf_top1_score": t_score,
        "bm25_top1_uid": b_top1["course_uid"] if b_top1 is not None else None,
        "bm25_top1_name": b_title,
        "bm25_top1_score": b_score
    })
    print(f"[{qid}] UID일치: {uid_match} | 제목일치: {title_match} | Top10교집합: {inter}개 (Jaccard: {j*100:.1f}%)")
    print(f"   질문: {q_text}")
    print(f"   TF-IDF Top 1: {t_title} ({t_score}) [{t_top1['course_uid']}]")
    print(f"   BM25   Top 1: {b_title} ({b_score}) [{b_top1['course_uid']}]")

print("\n" + "=" * 80)
print(f"Top 1 완전 일치(course_uid): {top1_matches} / 15 ({top1_matches/15*100:.1f}%)")
print(f"Top 1 과정명 일치(course_name): {top1_title_matches} / 15 ({top1_title_matches/15*100:.1f}%)")
print(f"Top 10 평균 교집합 수: {np.mean(overlap_counts):.1f}개 / 10개")
print(f"Top 10 평균 Jaccard 유사도: {np.mean(jaccards)*100:.1f}%")
print("=" * 80)

# 2. Maximum Text Length & Anomalies Inspection
print("\n" + "=" * 80)
print(" [2] 코퍼스 내 270만 자 등 대용량 텍스트 이상값 정밀 추적")
print("=" * 80)

df_all = pd.read_parquet("data/hr/processed/education_courses_integrated.parquet")

intro_len = df_all["course_intro"].fillna("").str.len()
goals_len = df_all["learning_goals"].fillna("").str.len()
curric_len = df_all["curriculum"].fillna("").str.len()
total_body_len = intro_len + goals_len + curric_len

df_all["body_len"] = total_body_len

# Top 10 longest courses
longest = df_all.sort_values(by="body_len", ascending=False).head(10)
for idx, r in longest.iterrows():
    print(f"[{r['course_uid']}] {r['provider']} | {r['title']}")
    print(f"   총 본문 길이: {r['body_len']:,}자 (소개: {len(str(r['course_intro'] or '')):,}자, 목표: {len(str(r['learning_goals'] or '')):,}자, 커리큘럼: {len(str(r['curriculum'] or '')):,}자)")
    print(f"   커리큘럼 앞 200자 미리보기: {repr(str(r['curriculum'])[:200])}")
    print(f"   커리큘럼 뒤 200자 미리보기: {repr(str(r['curriculum'])[-200:])}")
    print("-" * 60)
