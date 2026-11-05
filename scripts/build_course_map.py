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
  - 미설치 시 TruncatedSVD(2)로 대체
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

FIELD_INFO = {
    "HR": {"name": "인사·조직·직무 일반", "color": "#2563eb"},
    "DATA_AI": {"name": "데이터·AI 활용", "color": "#7c3aed"},
    "IT_DEV": {"name": "IT·개발", "color": "#0284c7"},
    "LANG": {"name": "외국어", "color": "#059669"},
    "GA": {"name": "총무·사무행정", "color": "#d97706"},
    "PROD": {"name": "생산·품질", "color": "#ea580c"},
    "MKT": {"name": "마케팅·영업", "color": "#db2777"},
    "FIN": {"name": "재무·회계", "color": "#0891b2"},
    "MED": {"name": "의료·보건", "color": "#16a34a"},
    "LEGAL_IP": {"name": "법무·지식재산", "color": "#4f46e5"},
    "EXCLUDED": {"name": "추천 제외 과정", "color": "#cbd5e1"}
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
        print(f"[Warning] Failed to load SentenceTransformer ({e}). Using random projection fallback.")
        task_embs = np.random.randn(len(tasks), 768)
        task_embs = task_embs / np.linalg.norm(task_embs, axis=1, keepdims=True)

    return tasks, task_embs


def build_course_map():
    t0 = time.time()
    print("=== Building Course Map (2D Projection) ===")

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

    # 2. Load task catalog and encode
    tasks, task_embs = load_task_embeddings()

    # Determine tasks with thin slots (<3 recommendations) in reranked results
    thin_tasks = set()
    if REC_RERANKED_PATH.exists():
        df_rec = pd.read_csv(REC_RERANKED_PATH)
        slot_sizes = df_rec.groupby(["task_id", "level"]).size()
        for (tid, lvl), cnt in slot_sizes.items():
            if cnt < 3:
                thin_tasks.add(tid)
        # Also any task missing levels
        task_levels = df_rec.groupby("task_id")["level"].nunique()
        for tid, lcnt in task_levels.items():
            if lcnt < 3:
                thin_tasks.add(tid)
    print(f"Tasks with thin slots (< 3 courses): {len(thin_tasks)} tasks -> {sorted(thin_tasks)}")

    # Normalize course embs
    c_norms = np.linalg.norm(course_embs, axis=1, keepdims=True)
    c_norms[c_norms == 0] = 1.0
    norm_course_embs = course_embs / c_norms

    # Stack all embeddings
    all_embs = np.vstack([norm_course_embs, task_embs])
    n_courses = len(course_embs)
    n_tasks = len(tasks)
    print(f"Total points to project: {all_embs.shape[0]} ({n_courses} courses + {n_tasks} tasks)")

    # 3. Dimensionality reduction
    reduction_method = ""
    try:
        from umap import UMAP
        print("Running UMAP (n_neighbors=30, min_dist=0.1, metric='cosine', random_state=42)...")
        reducer = UMAP(n_neighbors=30, min_dist=0.1, metric="cosine", random_state=42)
        coords = reducer.fit_transform(all_embs)
        reduction_method = "UMAP (n_neighbors=30, min_dist=0.1, metric='cosine')"
    except Exception as e:
        print(f"[Notice] UMAP failed ({e}). Falling back to TruncatedSVD(n_components=2)...")
        from sklearn.decomposition import TruncatedSVD
        svd = TruncatedSVD(n_components=2, random_state=42)
        coords = svd.fit_transform(all_embs)
        reduction_method = "TruncatedSVD (2차원 선형 투영)"

    # Normalize coordinates to a comfortable view box (e.g. 0 to 1000 or -500 to 500)
    # Let's keep raw 2-decimal coordinates and also bounding box
    course_coords = coords[:n_courses]
    task_coords = coords[n_courses:]

    # Min-max normalize to [20, 980] for SVG/Canvas viewport of 1000x1000
    min_x, max_x = float(coords[:, 0].min()), float(coords[:, 0].max())
    min_y, max_y = float(coords[:, 1].min()), float(coords[:, 1].max())

    def scale_x(x):
        return round(float(20 + (x - min_x) / (max_x - min_x) * 960), 1)

    def scale_y(y):
        return round(float(20 + (y - min_y) / (max_y - min_y) * 960), 1)

    # 4. Build output data structure
    courses_out = []
    for i, row in df_courses.iterrows():
        c_uid = row["course_uid"]
        x = scale_x(course_coords[i, 0])
        y = scale_y(course_coords[i, 1])
        f_code = field_map.get(c_uid, "HR")
        is_excl = 1 if c_uid in excl_uids else 0
        courses_out.append([x, y, f_code, is_excl])

    tasks_out = []
    for i, t in enumerate(tasks):
        t_id = t["task_id"]
        x = scale_x(task_coords[i, 0])
        y = scale_y(task_coords[i, 1])
        t_name = t["task_name"]
        d_name = t.get("domain_name", "")
        has_thin = 1 if t_id in thin_tasks else 0
        tasks_out.append([x, y, t_name, d_name, has_thin, t_id])

    result = {
        "metadata": {
            "n_courses": n_courses,
            "n_tasks": n_tasks,
            "n_thin_tasks": len(thin_tasks),
            "method": reduction_method,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "domains": FIELD_INFO
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
    print(f"Reduction Method: {reduction_method}")
    print(f"Courses: {len(courses_out)}, Tasks: {len(tasks_out)}, Thin Tasks: {len(thin_tasks)}")
    return result


if __name__ == "__main__":
    build_course_map()

