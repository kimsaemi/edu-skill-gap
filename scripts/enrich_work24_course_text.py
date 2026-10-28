"""
고용24 과정 설명 보강 (과정 상세 페이지의 훈련목표·훈련내용·훈련대상·NCS 능력단위)
파일명: scripts/enrich_work24_course_text.py
(먼저 scripts/refresh_work24_courses_2026.py 로 고용24 과정을 최신화한 뒤 실행)

배경
  고용24 Open API는 과정 설명을 주지 않아 고용24 과정은 제목만 있었고, 추천 점수가 낮아 거의 노출되지 않았습니다.
  과정 상세 페이지(robots.txt 허용 경로 /hr/…)에 공개된 표에서 설명을 가져옵니다. 1초에 1페이지씩 요청합니다.

가져오는 항목 → 카탈로그 칸
  - 훈련목표                          → learning_goals
  - 훈련내용 (주로 사업주훈련)        → course_intro
  - NCS 능력단위(요소)와 시간         → curriculum ("급여지급(20시간), 퇴직업무지원(15시간)")
  - 훈련대상 요건(선수학습·직무경력·기취득자격, '해당 사항 없음' 제외) → target_audience
  - NCS 능력단위 수준(1~8)            → difficulty (1~2 초급 / 3~4 중급/실무 / 5 이상 고급/전문), 비어 있을 때만
  '훈련과정의 장점' 칸은 기관 홍보 문구라 가져오지 않습니다. 원본 HTML은 저장하지 않고 추출한 값만 보관합니다.

이어서 하는 일
  - 기존 정제 규칙(step5_2_clean_and_validate.py 의 clean_and_synthesize)으로 정제·품질등급 재계산
  - 바뀐 행만 토큰·임베딩·군집 다시 계산 (다른 행은 그대로)
  - 이후 실행: build_course_field_labels.py, build_hr_task_catalog.py --reuse-catalog

사용법:
  python scripts/enrich_work24_course_text.py
  python scripts/enrich_work24_course_text.py --dry-run --limit 5
"""

import argparse
import importlib.util
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROCESSED = ROOT / "data" / "hr" / "processed"
RECO = ROOT / "data" / "hr" / "output" / "recommendation"
CATALOG = PROCESSED / "education_courses_search_cleaned.parquet"
TOKENS = PROCESSED / "tokenized_corpus_cache.parquet"
EMB = RECO / "embeddings_ko_sroberta_all.npy"
CLUSTERS = RECO / "course_clusters_8645.parquet"
DETAIL_CSV = PROCESSED / "work24_course_details.csv"
EXTRACTED = ROOT / "data" / "hr" / "raw" / "work24_2026" / "work24_course_pages_extracted.json"
BACKUP_DIR = PROCESSED / "backup"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NONE_WORDS = re.compile(r"^(해당\s*사항\s*없음|없음|해당\s*없음|-)\.?$")


def cell_text(td):
    for br in td.find_all("br"):
        br.replace_with("\n")
    text = td.get_text(" ", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {"goals": "", "content": "", "target": [], "ncs_units": []}
    for th in soup.find_all("th"):
        key = th.get_text(" ", strip=True)
        td = th.find_next_sibling("td")
        if td is None:
            continue
        if key == "훈련목표" and not out["goals"]:
            out["goals"] = cell_text(td)
        elif key == "훈련내용" and not out["content"]:
            out["content"] = cell_text(td)
        elif key.startswith("훈련대상 요건") and "장점" not in key:
            value = cell_text(td)
            if value and not NONE_WORDS.match(value):
                label = key.replace("훈련대상 요건", "").strip()
                out["target"].append(f"{label}: {value}")
    cap = next((c for c in soup.find_all("caption") if "NCS능력단위(요소)시간" in c.get_text()), None)
    if cap is not None and cap.find_parent("table").find("tbody") is not None:
        level = None
        for tr in cap.find_parent("table").find("tbody").find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) == 4:  # 수준 칸이 있는 행 (rowspan으로 이후 행에는 없음)
                level, cells = cells[0], cells[1:]
            if len(cells) == 3 and cells[0] not in ("-", "") and cells[1] not in ("-", ""):
                out["ncs_units"].append({"level": level, "code": cells[0], "name": cells[1], "hours": cells[2]})
    return out


def difficulty_from_levels(units):
    levels = [int(u["level"]) for u in units if str(u.get("level", "")).isdigit()]
    if not levels:
        return ""
    lv = max(levels)
    return "초급" if lv <= 2 else ("중급/실무" if lv <= 4 else "고급/전문")


def load_cleaner():
    """step5_2_clean_and_validate.py 의 clean_and_synthesize 함수만 읽어 와 같은 정제 규칙을 씀."""
    src = (ROOT / "scripts" / "step5_2_clean_and_validate.py").read_text(encoding="utf-8")
    start = src.index("def clean_and_synthesize(row):")
    end = src.index("# Apply to all", start)
    ns = {"re": re, "pd": pd, "np": np}
    exec(compile(src[start:end], "clean_and_synthesize", "exec"), ns)
    return ns["clean_and_synthesize"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--reuse-extracted", action="store_true", help="이미 추출한 JSON을 다시 씀 (페이지 재요청 없음)")
    args = parser.parse_args()

    det = pd.read_csv(DETAIL_CSV, dtype=str)
    det = det[det["course_url"].fillna("").str.startswith("https://www.work24.go.kr/hr/")]
    if args.limit:
        det = det.head(args.limit)

    existing = json.load(open(EXTRACTED, encoding="utf-8")) if EXTRACTED.exists() else {}
    by_trpr_id = {}
    for k, v in existing.items():
        parts = k.split("_")
        if len(parts) >= 2 and "error" not in v and (v.get("goals") or v.get("content") or v.get("ncs_units")):
            by_trpr_id[parts[1]] = v

    extracted = dict(existing)
    need_fetch = []
    for r in det.itertuples():
        if r.course_uid in extracted and "error" not in extracted[r.course_uid]:
            continue
        tid = getattr(r, "trprId", "") or (r.course_uid.split("_")[1] if "_" in r.course_uid else "")
        if tid in by_trpr_id:
            extracted[r.course_uid] = by_trpr_id[tid]
        elif not args.reuse_extracted:
            need_fetch.append(r)

    if need_fetch:
        print(f"  - 신규 미추출 과정 {len(need_fetch)}개 웹 페이지 수집 진행", flush=True)
        for i, r in enumerate(need_fetch, 1):
            try:
                html = requests.get(r.course_url, headers=HEADERS, timeout=30).text
                extracted[r.course_uid] = parse_page(html)
            except requests.RequestException as e:
                extracted[r.course_uid] = {"error": type(e).__name__}
            if i % 25 == 0 or i == len(need_fetch):
                print(f"  - {i}/{len(need_fetch)} 페이지", flush=True)
            time.sleep(args.delay)

    if not args.dry_run and need_fetch:
        EXTRACTED.write_text(json.dumps(extracted, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = {u: e for u, e in extracted.items() if "error" not in e}
    n_goals = sum(bool(e["goals"]) for e in ok.values())
    n_content = sum(bool(e["content"]) for e in ok.values())
    n_units = sum(bool(e["ncs_units"]) for e in ok.values())
    print(f"[1] 페이지 {len(extracted)}개 (오류 {len(extracted) - len(ok)}) | 훈련목표 {n_goals}, 훈련내용 {n_content}, NCS 능력단위 {n_units}", flush=True)

    df = pd.read_parquet(CATALOG)
    idx_of = {u: i for i, u in enumerate(df["course_uid"])}
    targets = [u for u in ok if u in idx_of and (ok[u]["goals"] or ok[u]["content"] or ok[u]["ncs_units"])]
    clean = load_cleaner()
    changed = []
    for uid in targets:
        e = ok[uid]
        i = idx_of[uid]
        row = df.loc[i].copy()
        row["learning_goals"] = e["goals"]
        row["course_intro"] = e["content"]
        row["curriculum"] = ", ".join(f"{u['name']}({u['hours'].replace(' ', '')})" for u in e["ncs_units"])
        row["target_audience"] = " / ".join(e["target"])
        if not str(row["difficulty"] or "").strip():
            row["difficulty"] = difficulty_from_levels(e["ncs_units"])
        res = clean(row)
        prev_actions = str(df.at[i, "cleaning_actions"] or "")
        res["cleaning_actions"] = ", ".join(x for x in [prev_actions, "work24_page_text"] if x)
        for c in ["learning_goals", "course_intro", "curriculum", "target_audience", "difficulty"]:
            df.at[i, c] = row[c]
        for c, v in res.items():
            df.at[i, c] = v
        changed.append(i)
    q = df.loc[changed, "text_quality_status"].value_counts().to_dict()
    print(f"[2] 설명 보강 {len(changed)}행 → 텍스트 품질 {q}")
    print(f"    난이도 채움: {df.loc[changed, 'difficulty'].value_counts().to_dict()}")
    if args.dry_run:
        sample = df.loc[changed[:2], ["title", "learning_goals", "curriculum", "difficulty", "text_quality_status"]]
        print(sample.to_string()[:1500])
        print("--dry-run: 파일을 바꾸지 않았습니다.")
        return

    print("[3] 바뀐 행만 토큰·임베딩·군집 다시 계산")
    from src.recommendation.text_preprocessor import HRTextPreprocessor
    from sentence_transformers import SentenceTransformer
    spec = importlib.util.spec_from_file_location("gen_emb", ROOT / "scripts" / "generate_full_embeddings_ko_sroberta.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    tok = pd.read_parquet(TOKENS)
    emb = np.load(EMB)
    cl = pd.read_parquet(CLUSTERS)
    assert len(tok) == len(emb) == len(df) and (tok["course_uid"].values == df["course_uid"].values).all()

    prep = HRTextPreprocessor()
    for i in changed:
        tok.at[i, "tokenized_text"] = " ".join(prep.tokenize(df.at[i, "clean_search_text"]))
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")
    texts = [gen.compose_course_text(df.loc[i]) for i in changed]
    new_vecs = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(emb.dtype)
    emb[changed] = new_vecs

    cl_idx = cl.set_index("course_uid")
    unchanged_mask = ~df["course_uid"].isin(df.loc[changed, "course_uid"]).values
    cid_all = cl_idx.loc[df["course_uid"], "cluster_id"].values
    ids = np.unique(cid_all[unchanged_mask])
    cent = np.vstack([emb[unchanged_mask & (cid_all == k)].mean(0) for k in ids])
    cent /= np.linalg.norm(cent, axis=1, keepdims=True)
    assign = ids[(new_vecs @ cent.T).argmax(1)]
    labels = cl.groupby("cluster_id")["topic_label"].first()
    uids = df.loc[changed, "course_uid"].values
    pos = cl.reset_index(drop=True).index[cl["course_uid"].isin(uids)]
    order = {u: k for k, u in enumerate(uids)}
    for p in pos:
        k = order[cl.at[p, "course_uid"]]
        cl.at[p, "cluster_id"] = assign[k]
        cl.at[p, "topic_label"] = labels.get(assign[k])
        cl.at[p, "difficulty"] = df.at[changed[k], "difficulty"] if "difficulty" in cl.columns else None
    print("    군집: " + str(pd.Series(labels.reindex(assign).values).value_counts().to_dict()))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for p in [CATALOG, TOKENS, EMB, CLUSTERS]:
        shutil.copy2(p, BACKUP_DIR / f"{p.stem}.before_work24_text_{stamp}{p.suffix}")
    df.to_parquet(CATALOG, index=False, compression="zstd", compression_level=9)
    tok.to_parquet(TOKENS, index=False)
    np.save(EMB, emb)
    cl.to_parquet(CLUSTERS, index=False)
    print(f"[4] 저장 완료 (백업 {BACKUP_DIR.relative_to(ROOT)}/*{stamp}*)")


if __name__ == "__main__":
    main()
