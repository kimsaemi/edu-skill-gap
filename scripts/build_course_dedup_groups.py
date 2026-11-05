# -*- coding: utf-8 -*-
"""
과정 중복 군집화 스크립트
- 제외 목록 제외 후 문장 임베딩 코사인 거리 기반 군집화
- DBSCAN 및 AgglomerativeClustering (linkage='average') 비교
- eps 후보: 0.02, 0.03, 0.05, 0.08
- 검수용 표: data/hr/reports/dedup_pair_samples.csv (eps당 20쌍, random_state=42)
- 결과 저장: data/hr/processed/course_dedup_groups.csv (course_uid, group_id, group_size)
"""

import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, AgglomerativeClustering

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EMB_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "embeddings_ko_sroberta_all.npy"
COURSES_PATH = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
EXCL_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
OUT_SAMPLES_PATH = ROOT / "data" / "hr" / "reports" / "dedup_pair_samples.csv"
OUT_GROUPS_PATH = ROOT / "data" / "hr" / "processed" / "course_dedup_groups.csv"


def load_data():
    if not EMB_PATH.exists():
        raise FileNotFoundError(f"Embeddings not found: {EMB_PATH}")
    if not COURSES_PATH.exists():
        raise FileNotFoundError(f"Courses parquet not found: {COURSES_PATH}")

    embs = np.load(EMB_PATH)
    df_courses = pd.read_parquet(COURSES_PATH)

    if len(embs) != len(df_courses):
        raise ValueError(f"Length mismatch: embs={len(embs)}, courses={len(df_courses)}")

    excluded_uids = set()
    if EXCL_PATH.exists():
        df_excl = pd.read_csv(EXCL_PATH, dtype=str)
        excluded_uids = set(df_excl["course_uid"])

    valid_mask = ~df_courses["course_uid"].isin(excluded_uids)
    valid_df = df_courses[valid_mask].copy().reset_index(drop=True)
    valid_embs = embs[valid_mask.values]

    # Normalize embeddings
    norms = np.linalg.norm(valid_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    valid_embs = valid_embs / norms

    print(f"Total courses: {len(df_courses)}, Excluded: {len(excluded_uids)}, Valid: {len(valid_df)}")
    return df_courses, valid_df, valid_embs


def compute_clustering_stats(valid_df, labels, dist_matrix=None):
    """군집 결과에 대한 통계 계산"""
    series_labels = pd.Series(labels)
    clustered_counts = series_labels[series_labels != -1].value_counts()
    n_clusters = len(clustered_counts)
    clustered_courses = int(clustered_counts.sum())
    max_size = int(clustered_counts.max()) if n_clusters > 0 else 0

    same_p = 0
    diff_p = 0
    pairs = []

    for cid in clustered_counts.index:
        idxs = np.where(labels == cid)[0]
        sub_providers = valid_df.loc[idxs, "provider"].values
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                ia, ib = idxs[i], idxs[j]
                d = dist_matrix[ia, ib] if dist_matrix is not None else 0.0
                if sub_providers[i] == sub_providers[j]:
                    same_p += 1
                else:
                    diff_p += 1
                pairs.append((ia, ib, d))

    tot_pairs = same_p + diff_p
    sp_ratio = (same_p / tot_pairs * 100) if tot_pairs > 0 else 0.0
    dp_ratio = (diff_p / tot_pairs * 100) if tot_pairs > 0 else 0.0

    stats = {
        "n_clusters": n_clusters,
        "clustered_courses": clustered_courses,
        "max_size": max_size,
        "same_p_ratio": sp_ratio,
        "diff_p_ratio": dp_ratio,
        "total_pairs": tot_pairs,
    }
    return stats, pairs


def main():
    parser = argparse.ArgumentParser(description="Course Deduplication Clustering")
    parser.add_argument("--method", choices=["dbscan", "agglomerative"], default="dbscan",
                        help="Clustering method for output groups (default: dbscan)")
    parser.add_argument("--eps", type=float, default=0.02,
                        help="Epsilon or distance threshold for chosen method (default: 0.02)")
    args = parser.parse_args()

    df_all, valid_df, valid_embs = load_data()

    # Precompute pairwise cosine distance matrix
    print("Computing cosine distance matrix...")
    D = 1.0 - np.dot(valid_embs, valid_embs.T)
    np.clip(D, 0.0, None, out=D)
    np.fill_diagonal(D, 0.0)

    candidate_eps = [0.02, 0.03, 0.05, 0.08]

    # 1. Run and compare DBSCAN and Agglomerative across candidate eps
    print("\n=== DBSCAN (metric='cosine', min_samples=2) ===")
    db_results = {}
    db_pairs_by_eps = {}
    for eps in candidate_eps:
        db = DBSCAN(eps=eps, min_samples=2, metric="precomputed", n_jobs=-1).fit(D)
        stats, pairs = compute_clustering_stats(valid_df, db.labels_, D)
        db_results[eps] = (stats, db.labels_)
        db_pairs_by_eps[eps] = pairs
        print(f"eps={eps:0.2f} | 군집: {stats['n_clusters']}개, 묶인과정: {stats['clustered_courses']}개, "
              f"최대크기: {stats['max_size']} | 같은기관: {stats['same_p_ratio']:.1f}%, 다른기관: {stats['diff_p_ratio']:.1f}% "
              f"(총 쌍: {stats['total_pairs']})")

    print("\n=== AgglomerativeClustering (linkage='average') ===")
    agg_results = {}
    for eps in candidate_eps:
        agg = AgglomerativeClustering(n_clusters=None, distance_threshold=eps, metric="precomputed", linkage="average").fit(D)
        # Agglomerative treats singles as separate clusters; identify clusters with size > 1
        labels = agg.labels_
        counts = pd.Series(labels).value_counts()
        single_cids = set(counts[counts == 1].index)
        mod_labels = np.array([-1 if lbl in single_cids else lbl for lbl in labels])
        stats, _ = compute_clustering_stats(valid_df, mod_labels, D)
        agg_results[eps] = (stats, mod_labels)
        print(f"th={eps:0.2f}  | 군집: {stats['n_clusters']}개, 묶인과정: {stats['clustered_courses']}개, "
              f"최대크기: {stats['max_size']} | 같은기관: {stats['same_p_ratio']:.1f}%, 다른기관: {stats['diff_p_ratio']:.1f}% "
              f"(총 쌍: {stats['total_pairs']})")

    # 2. Build audit samples: dedup_pair_samples.csv (20 random pairs per eps, random_state=42)
    sample_rows = []
    for eps in candidate_eps:
        pairs = db_pairs_by_eps[eps]
        if len(pairs) == 0:
            continue
        rng = np.random.RandomState(42)
        n_sample = min(20, len(pairs))
        chosen_indices = rng.choice(len(pairs), size=n_sample, replace=False)
        for c_idx in chosen_indices:
            ia, ib, dist = pairs[c_idx]
            sample_rows.append({
                "eps": eps,
                "과정명 A": valid_df.loc[ia, "title"],
                "기관 A": valid_df.loc[ia, "provider"],
                "과정명 B": valid_df.loc[ib, "title"],
                "기관 B": valid_df.loc[ib, "provider"],
                "코사인 거리": round(float(dist), 4),
                "같은 과정?": ""  # 사람이 검수하도록 빈칸 유지
            })

    df_samples = pd.DataFrame(sample_rows)
    OUT_SAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_samples.to_csv(OUT_SAMPLES_PATH, index=False, encoding="utf-8-sig")
    print(f"\nSaved {len(df_samples)} sample pairs to {OUT_SAMPLES_PATH}")

    # 3. Produce course_dedup_groups.csv for chosen method & eps
    print(f"\nGenerating groups for method={args.method}, eps/threshold={args.eps}...")
    if args.method == "dbscan":
        chosen_labels = db_results[args.eps][1]
    else:
        chosen_labels = agg_results[args.eps][1]

    # Map labels to group_id
    # Unclustered courses (label == -1): group_id = course_uid, group_size = 1
    # Clustered courses: group_id = lowest course_uid in group or format G_{cid:04d}
    valid_df["cluster_label"] = chosen_labels
    cluster_sizes = valid_df["cluster_label"].value_counts().to_dict()

    group_id_map = {}
    for cid in valid_df["cluster_label"].unique():
        if cid == -1:
            continue
        sub_uids = valid_df.loc[valid_df["cluster_label"] == cid, "course_uid"].sort_values().tolist()
        # group_id represents the canonical representative (or lowest course_uid in group)
        canon_id = sub_uids[0]
        group_id_map[cid] = canon_id

    records = []
    for _, row in valid_df.iterrows():
        c_uid = row["course_uid"]
        cid = row["cluster_label"]
        if cid == -1:
            records.append({
                "course_uid": c_uid,
                "group_id": c_uid,
                "group_size": 1
            })
        else:
            records.append({
                "course_uid": c_uid,
                "group_id": group_id_map[cid],
                "group_size": cluster_sizes[cid]
            })

    # Add back excluded courses as independent singletons (group_size=1)
    valid_uids_set = set(valid_df["course_uid"])
    for _, row in df_all.iterrows():
        c_uid = row["course_uid"]
        if c_uid not in valid_uids_set:
            records.append({
                "course_uid": c_uid,
                "group_id": c_uid,
                "group_size": 1
            })

    df_out = pd.DataFrame(records)
    # Sort by course_uid
    df_out = df_out.sort_values(by="course_uid").reset_index(drop=True)
    OUT_GROUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUT_GROUPS_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df_out)} courses with group assignments to {OUT_GROUPS_PATH}")
    print(f"Number of distinct groups: {df_out['group_id'].nunique()}")
    print(f"Number of courses in multi-course groups: {(df_out['group_size'] > 1).sum()}")


if __name__ == "__main__":
    main()

