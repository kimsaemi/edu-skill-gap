import pandas as pd
import numpy as np
import json

df_t = pd.read_csv("data/hr/output/recommendation/search_results_tfidf_top10.csv")
df_b = pd.read_csv("data/hr/output/recommendation/search_results_bm25_top10.csv")

qids = df_t["query_id"].unique()

results = []
for qid in qids:
    sub_t = df_t[df_t["query_id"] == qid].sort_values("rank")
    sub_b = df_b[df_b["query_id"] == qid].sort_values("rank")
    
    t_top1 = sub_t.iloc[0]
    b_top1 = sub_b.iloc[0]
    
    uid_match = bool(t_top1["course_uid"] == b_top1["course_uid"])
    name_match = bool(t_top1["course_name"] == b_top1["course_name"])
    
    # uid sets
    t_uids = set(sub_t["course_uid"])
    b_uids = set(sub_b["course_uid"])
    inter_uids = len(t_uids & b_uids)
    union_uids = len(t_uids | b_uids)
    jaccard_uid = inter_uids / union_uids if union_uids > 0 else 0
    overlap_rate_uid = (inter_uids / 10.0) * 100
    
    # name sets (to account for multiple sessions of same course)
    t_names = set(sub_t["course_name"])
    b_names = set(sub_b["course_name"])
    inter_names = len(t_names & b_names)
    union_names = len(t_names | b_names)
    jaccard_name = inter_names / union_names if union_names > 0 else 0
    
    results.append({
        "query_id": qid,
        "query": t_top1["query"],
        "category": t_top1.get("category", ""),
        "tfidf_top1": {
            "uid": t_top1["course_uid"],
            "name": t_top1["course_name"],
            "score": round(float(t_top1["score"]), 4)
        },
        "bm25_top1": {
            "uid": b_top1["course_uid"],
            "name": b_top1["course_name"],
            "score": round(float(b_top1["score"]), 4)
        },
        "uid_match": uid_match,
        "name_match": name_match,
        "top10_overlap_count": inter_uids,
        "top10_overlap_pct": overlap_rate_uid,
        "top10_jaccard_uid": round(jaccard_uid, 4),
        "top10_jaccard_name": round(jaccard_name, 4)
    })

df_res = pd.DataFrame([
    {
        "query_id": r["query_id"],
        "query": r["query"],
        "tfidf_top1": f"{r['tfidf_top1']['name']} ({r['tfidf_top1']['score']})",
        "bm25_top1": f"{r['bm25_top1']['name']} ({r['bm25_top1']['score']})",
        "uid_match": r["uid_match"],
        "name_match": r["name_match"],
        "overlap_count": r["top10_overlap_count"],
        "jaccard_uid": r["top10_jaccard_uid"],
        "jaccard_name": r["top10_jaccard_name"]
    }
    for r in results
])

print(df_res.to_string(index=False))

total_uid_matches = sum(r["uid_match"] for r in results)
total_name_matches = sum(r["name_match"] for r in results)
mean_overlap = np.mean([r["top10_overlap_count"] for r in results])
mean_jaccard_uid = np.mean([r["top10_jaccard_uid"] for r in results])
mean_jaccard_name = np.mean([r["top10_jaccard_name"] for r in results])

print("\n" + "="*50)
print(f"Top 1 UID Match Rate: {total_uid_matches}/15 ({total_uid_matches/15*100:.2f}%)")
print(f"Top 1 Course Name Match Rate: {total_name_matches}/15 ({total_name_matches/15*100:.2f}%)")
print(f"Top 10 Average Overlap Count: {mean_overlap:.2f} / 10 ({mean_overlap*10:.1f}%)")
print(f"Top 10 Average Jaccard (by UID): {mean_jaccard_uid*100:.2f}%")
print(f"Top 10 Average Jaccard (by Name): {mean_jaccard_name*100:.2f}%")
print("="*50)

with open("data/hr/reports/recalculated_metrics.json", "w", encoding="utf-8") as f:
    json.dump({
        "summary": {
            "total_queries": len(results),
            "top1_uid_match_count": total_uid_matches,
            "top1_uid_match_rate": round(total_uid_matches / 15 * 100, 2),
            "top1_name_match_count": total_name_matches,
            "top1_name_match_rate": round(total_name_matches / 15 * 100, 2),
            "mean_overlap_count": round(float(mean_overlap), 2),
            "mean_jaccard_uid": round(float(mean_jaccard_uid) * 100, 2),
            "mean_jaccard_name": round(float(mean_jaccard_name) * 100, 2)
        },
        "query_details": results
    }, f, ensure_ascii=False, indent=2)
