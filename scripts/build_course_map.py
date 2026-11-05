# -*- coding: utf-8 -*-
"""
발표용 인사 교육 지도(2D 임베딩 맵) 생성 스크립트
- 입력:
  - data/hr/output/recommendation/embeddings_ko_sroberta_all.npy (9,075개 과정 임베딩)
  - data/hr/processed/education_courses_search_cleaned.parquet
  - data/hr/output/recommendation/course_field_labels.csv (10개 분야 라벨)
  - data/hr/processed/off_topic_exclusions.csv (추천 제외 목록)
  - data/hr/processed/hr_task_catalog_90.json (90개 인사 과업)
  - data/hr/output/recommendation/task_course_recommendations_90_reranked.csv (추천 3개 미만 슬롯 확인)
- 방식: UMAP(n_neighbors=30, min_dist=0.1, metric='cosine', random_state=42)
  - 화면 범위를 과정 좌표의 1~99 백분위로 확대하여 중앙 밀집 완화
  - 범위 밖 과정은 생략하고 개수(N개)를 기록
- 출력: presentation/src/course_map.json
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EMB_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "embeddings_ko_sroberta_all.npy"
COURSES_PATH = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
FIELDS_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "course_field_labels.csv"
EXCL_PATH = ROOT / "data" / "hr" / "processed" / "off_topic_exclusions.csv"
TASK_CATALOG_PATH = ROOT / "data" / "hr" / "processed" / "hr_task_catalog_90.json"
REC_RERANKED_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / "task_course_recommendations_90_reranked.csv"
OUT_PATH = ROOT / "presentation" / "src" / "course_map.json"
CACHE_UMAP_PATH = ROOT / "data" / "hr" / "output" / "recommendation" / ".raw_umap_coords.npy"

# 9개 인사 과업 분야별 색상 (카탈로그 출현 순서대로 매핑)
TASK_DOMAIN_COLORS = [
    "#38bdf8", "#2dd4bf", "#34d399", "#a3e635", "#facc15",
    "#fb923c", "#c084fc", "#f472b6", "#fb7185"
]

# 10개 강좌 분류 분야 및 고유 색상
COURSE_DOMAINS = {
    "HR": {"name": "인사·조직·직무 일반", "color": "#38bdf8"},
    "DATA_AI": {"name": "데이터·AI 활용", "color": "#a855f7"},
    "IT_DEV": {"name": "IT·개발", "color": "#06b6d4"},
    "LANG": {"name": "외국어", "color": "#10b981"},
    "GA": {"name": "총무·사무행정", "color": "#f59e0b"},
    "PROD": {"name": "생산·품질", "color": "#ea580c"},
    "MKT": {"name": "마케팅·영업", "color": "#ec4899"},
    "FIN": {"name": "재무·회계", "color": "#14b8a6"},
    "MED": {"name": "의료·보건", "color": "#22c55e"},
    "LEGAL_IP": {"name": "법무·지식재산", "color": "#6366f1"},
    "EXCLUDED": {"name": "추천 제외 과정", "color": "#64748b"}
}


def load_task_embeddings():
    with open(TASK_CATALOG_PATH, "r", encoding="utf-8") as f:
        cat = json.load(f)
    tasks = cat.get("tasks", cat) if isinstance(cat, dict) else cat
    task_texts = [f"{t['task_name']}. {t.get('easy_description', '')}" for t in tasks]

    try:
        from sentence_transformers import SentenceTransformer
        print(f"Encoding {len(tasks)} task descriptions with jhgan/ko-sroberta-multitask...")
        model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")
        task_embs = model.encode(task_texts, normalize_embeddings=True, show_progress_bar=False)
    except Exception as e:
        print(f"[Warning] Failed to load SentenceTransformer ({e}). Using fallback.")
        task_embs = np.random.randn(len(tasks), 768)
        task_embs = task_embs / np.linalg.norm(task_embs, axis=1, keepdims=True)

    return tasks, task_embs


def build_course_map(force_recompute=False):
    t0 = time.time()
    print("=== Building Improved Course Map (2D Projection) ===")

    # 1. Load course embeddings and metadata
    course_embs = np.load(EMB_PATH)
    df_courses = pd.read_parquet(COURSES_PATH)
    if len(course_embs) != len(df_courses):
        raise ValueError(f"Course count mismatch: embs={len(course_embs)}, parquet={len(df_courses)}")

    df_fields = pd.read_csv(FIELDS_PATH)
    field_map = dict(zip(df_fields["course_uid"], df_fields["field"]))

    excl_uids = set()
    if EXCL_PATH.exists():
        excl_df = pd.read_csv(EXCL_PATH, dtype=str)
        excl_uids = set(excl_df["course_uid"])

    # 2. Load task catalog
    tasks, task_embs = load_task_embeddings()

    # Determine tasks with thin slots (<3 recommendations) in reranked results
    thin_tasks = set()
    if REC_RERANKED_PATH.exists():
        df_rec = pd.read_csv(REC_RERANKED_PATH)
        slot_sizes = df_rec.groupby(["task_id", "level"]).size()
        for (tid, lvl), cnt in slot_sizes.items():
            if cnt < 3:
                thin_tasks.add(tid)
        task_levels = df_rec.groupby("task_id")["level"].nunique()
        for tid, lcnt in task_levels.items():
            if lcnt < 3:
                thin_tasks.add(tid)
    print(f"Tasks with thin slots (< 3 courses): {len(thin_tasks)} tasks -> {sorted(thin_tasks)}")

    n_courses = len(course_embs)
    n_tasks = len(tasks)

    # 3. Dimensionality reduction (with caching for speed)
    reduction_method = "UMAP (n_neighbors=30, min_dist=0.1, metric='cosine')"
    if not force_recompute and CACHE_UMAP_PATH.exists():
        print(f"Loading cached raw UMAP coordinates from {CACHE_UMAP_PATH.name}...")
        coords = np.load(CACHE_UMAP_PATH)
    else:
        c_norms = np.linalg.norm(course_embs, axis=1, keepdims=True)
        c_norms[c_norms == 0] = 1.0
        norm_course_embs = course_embs / c_norms

        all_embs = np.vstack([norm_course_embs, task_embs])
        print(f"Total points to project: {all_embs.shape[0]} ({n_courses} courses + {n_tasks} tasks)")

        try:
            from umap import UMAP
            print("Running UMAP (n_neighbors=30, min_dist=0.1, metric='cosine', random_state=42)...")
            reducer = UMAP(n_neighbors=30, min_dist=0.1, metric="cosine", random_state=42)
            coords = reducer.fit_transform(all_embs)
        except Exception as e:
            print(f"[Notice] UMAP failed ({e}). Falling back to TruncatedSVD(2)...")
            from sklearn.decomposition import TruncatedSVD
            svd = TruncatedSVD(n_components=2, random_state=42)
            coords = svd.fit_transform(all_embs)
            reduction_method = "TruncatedSVD (2차원 선형 투영)"

        CACHE_UMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.save(CACHE_UMAP_PATH, coords)

    course_coords = coords[:n_courses]
    task_coords = coords[n_courses:]

    # 4. Viewport scaling: 1st to 99th percentile of course coordinates
    p1_x, p99_x = float(np.percentile(course_coords[:, 0], 1)), float(np.percentile(course_coords[:, 0], 99))
    p1_y, p99_y = float(np.percentile(course_coords[:, 1], 1)), float(np.percentile(course_coords[:, 1], 99))

    def scale_x(x):
        return round(float(30 + (x - p1_x) / (p99_x - p1_x) * 940), 1)

    def scale_y(y):
        return round(float(30 + (y - p1_y) / (p99_y - p1_y) * 940), 1)

    # Filter course points: keep inside [p1, p99]
    courses_out = []
    omitted_count = 0

    for i, row in df_courses.iterrows():
        raw_x = float(course_coords[i, 0])
        raw_y = float(course_coords[i, 1])

        # Check if inside 1~99 percentile range
        if raw_x < p1_x or raw_x > p99_x or raw_y < p1_y or raw_y > p99_y:
            omitted_count += 1
            continue

        c_uid = row["course_uid"]
        x = scale_x(raw_x)
        y = scale_y(raw_y)
        f_code = field_map.get(c_uid, "HR")
        is_excl = 1 if c_uid in excl_uids else 0
        courses_out.append([x, y, f_code, is_excl])

    print(f"Courses inside 1~99 percentile: {len(courses_out)}, Omitted outside: {omitted_count} (Total: {n_courses})")

    # Tasks: include all 90 tasks with domain_id and thin slot flag
    task_domains = {}
    color_idx = 0
    tasks_out = []
    thin_tasks_details = []
    for i, t in enumerate(tasks):
        t_id = t["task_id"]
        x = scale_x(float(task_coords[i, 0]))
        y = scale_y(float(task_coords[i, 1]))
        t_name = t["task_name"]
        d_name = t.get("domain_name", "")
        d_id = t.get("domain_id", "")

        if d_id and d_id not in task_domains:
            task_domains[d_id] = {
                "name": d_name,
                "color": TASK_DOMAIN_COLORS[color_idx % len(TASK_DOMAIN_COLORS)]
            }
            color_idx += 1

        has_thin = 1 if t_id in thin_tasks else 0
        tasks_out.append([x, y, t_name, d_name, has_thin, t_id, d_id])
        if has_thin:
            thin_tasks_details.append({
                "task_id": t_id,
                "task_name": t_name,
                "domain_name": d_name,
                "x": x,
                "y": y
            })

    result = {
        "metadata": {
            "n_courses": n_courses,
            "n_tasks": n_tasks,
            "n_thin_tasks": len(thin_tasks),
            "n_plotted_courses": len(courses_out),
            "n_omitted_courses": omitted_count,
            "percentile_range": [1, 99],
            "method": reduction_method,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task_domains": task_domains,
            "course_domains": COURSE_DOMAINS,
            "thin_tasks": thin_tasks_details
        },
        "courses": courses_out,
        "tasks": tasks_out
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = OUT_PATH.stat().st_size / 1024
    elapsed = time.time() - t0
    print(f"Saved: {OUT_PATH} ({size_kb:.1f} KB, elapsed: {elapsed:.2f}s)")
    return result


if __name__ == "__main__":
    build_course_map()
