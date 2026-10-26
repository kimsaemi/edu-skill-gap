"""
고용24 과정 최신화: 운영이 끝난 2024년 승인 과정을 2026년 운영 과정으로 교체
파일명: scripts/refresh_work24_courses_2026.py

배경
  카탈로그의 고용24 과정(130행)은 모두 2025년에 마지막 회차가 끝났습니다. 고용24 과정 ID는 승인 연도마다
  새로 나오므로, 2026년에 개강 회차가 있는 과정을 다시 모아 교체합니다.

선정 기준
  - 2026-01-01 ~ 2026-12-31 에 개강하는 회차가 있고, 실행일 기준 운영 중이거나 개강 예정인 과정
  - 고용24가 붙인 공식 NCS 분류가 '총무·인사'(코드 0202…)인 과정만 (키워드 검색에 섞이는 무관한 과정 제외)
  - 같은 제목을 여러 훈련기관이 운영하면 하나로 묶고 대표 회차를 고름
    (운영 중 > 가장 가까운 개강 예정 > 가장 최근 회차 순, 같으면 국민내일배움카드 우선)

입력
  - data/hr/raw/satisfaction/kmbc_satisfaction_raw.json   (국민내일배움카드 목록, collect_official_satisfaction.py)
  - data/hr/raw/work24_2026/employer_2026_list_raw.json   (사업주훈련 목록, 이 스크립트가 없으면 새로 수집)

바꾸는 파일 (먼저 data/hr/processed/backup/ 에 백업)
  - education_courses_search_cleaned.parquet : 기존 고용24 행 삭제 + 새 행을 맨 뒤에 추가
  - embeddings_ko_sroberta_all.npy           : 기존 행 벡터는 그대로, 새 행만 같은 방식으로 계산해 이어 붙임
  - tokenized_corpus_cache.parquet           : 같은 방식
  - course_clusters_8645.parquet             : 새 행은 기존 군집 중심과 가장 가까운 군집으로
  - work24_course_details.csv                : 새 과정의 상세값·운영 상태로 다시 작성

이후 실행할 것
  python scripts/build_course_field_labels.py
  python scripts/build_off_topic_exclusions.py
  python scripts/build_hr_task_catalog.py
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

PROCESSED = ROOT / "data" / "hr" / "processed"
RECO = ROOT / "data" / "hr" / "output" / "recommendation"
CATALOG = PROCESSED / "education_courses_search_cleaned.parquet"
TOKENS = PROCESSED / "tokenized_corpus_cache.parquet"
EMB = RECO / "embeddings_ko_sroberta_all.npy"
CLUSTERS = RECO / "course_clusters_8645.parquet"
DETAIL_CSV = PROCESSED / "work24_course_details.csv"
KMBC_RAW = ROOT / "data" / "hr" / "raw" / "satisfaction" / "kmbc_satisfaction_raw.json"
RAW_DIR = ROOT / "data" / "hr" / "raw" / "work24_2026"
EMP_RAW = RAW_DIR / "employer_2026_list_raw.json"
DETAIL_RAW = RAW_DIR / "work24_2026_details_raw.json"
BACKUP_DIR = PROCESSED / "backup"

BASE = "https://www.work24.go.kr/cm/openApi/call/hr/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
YEAR_FROM, YEAR_TO = "2026-01-01", "2026-12-31"
TODAY = date.today().isoformat()
NCS_PREFIX = "0202"  # NCS 경영·회계·사무 > 총무·인사
KEYWORDS = ["인사", "총무", "노무", "인사관리", "채용", "근로기준법", "인사평가", "총무관리",
            "자산관리", "급여", "교육훈련", "조직관리", "사무", "비서", "문서"]
PROGRAMS = {
    "K": {"name": "국민내일배움카드", "source": "고용24_국민내일배움카드", "detail": "callOpenApiSvcInfo310L02.do", "key": "HRD_KMBC_API_KEY"},
    "E": {"name": "사업주훈련", "source": "고용24_사업주훈련", "detail": "callOpenApiSvcInfo311D01.do", "key": "HRD_EMPLOYER_TRAINING_API_KEY"},
}
TRPR_RE = r"A[A-Z]{2}\d{14}"


def get_text(url, params, tries=3):
    """연결 오류는 다시 시도. 오류 메시지에 인증키가 담긴 주소가 찍히지 않도록 예외를 감춤."""
    for attempt in range(tries):
        try:
            return requests.get(url, params=params, headers=HEADERS, timeout=25).text
        except requests.RequestException as e:
            print(f"    (연결 오류 {type(e).__name__}, {attempt + 1}/{tries}회)")
            time.sleep(2 * (attempt + 1))
    return ""


def norm_title(s):
    return re.sub(r"[\s\[\]\(\)【】<>·,.!?:~\-_\"']", "", str(s)).lower()


def collect_employer_list(delay):
    rows = []
    for kw in KEYWORDS:
        for page in range(1, 400):
            text = get_text(BASE + "callOpenApiSvcInfo311L01.do", {
                "authKey": os.getenv(PROGRAMS["E"]["key"]), "returnType": "XML", "outType": "1",
                "pageNum": str(page), "pageSize": "100", "srchTraStDt": YEAR_FROM.replace("-", ""),
                "srchTraEndDt": YEAR_TO.replace("-", ""), "srchTraProcessNm": kw,
            })
            if "<HRDNet" not in text[:300]:
                break
            root = ET.fromstring(text)
            items = root.findall(".//scn_list")
            for it in items:
                d = {c.tag: c.text for c in it}
                d["_kw"] = kw
                rows.append(d)
            if not items or page * 100 >= int(root.findtext("scn_cnt") or 0):
                break
            time.sleep(delay)
        print(f"  - 사업주훈련 [{kw}] 누적 {len(rows)}행")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_json(EMP_RAW, orient="records", force_ascii=False)
    return rows


def load_sessions(refresh_employer, delay):
    kmbc = pd.DataFrame(json.load(open(KMBC_RAW, encoding="utf-8")))
    emp_rows = collect_employer_list(delay) if (refresh_employer or not EMP_RAW.exists()) else json.load(open(EMP_RAW, encoding="utf-8"))
    emp = pd.DataFrame(emp_rows)
    frames = []
    for prog, df in (("K", kmbc), ("E", emp)):
        df = df.copy()
        df["program"] = prog
        df["ncsCd"] = df["ncsCd"].astype(str)
        df = df[df["traStartDate"].between(YEAR_FROM, YEAR_TO) & df["ncsCd"].str.startswith(NCS_PREFIX)]
        frames.append(df.drop_duplicates(["trprId", "trprDegr"]))
    s = pd.concat(frames, ignore_index=True)
    s["norm"] = s["title"].map(norm_title)
    return s


def pick_representatives(s):
    s = s.copy()
    running = (s["traStartDate"] <= TODAY) & (s["traEndDate"] >= TODAY)
    upcoming = s["traStartDate"] > TODAY
    s["rank"] = np.where(running, 0, np.where(upcoming, 1, 2))
    # 개강 예정은 가까운 순, 지난 회차는 최근 순으로 정렬되도록 키를 만든다
    s["date_key"] = np.where(s["rank"] == 2, -pd.to_datetime(s["traStartDate"]).astype("int64"), pd.to_datetime(s["traStartDate"]).astype("int64"))
    s["prog_key"] = (s["program"] != "K").astype(int)
    s = s.sort_values(["norm", "rank", "prog_key", "date_key"])
    reps = s.drop_duplicates("norm").copy()

    by_course = s.groupby("trprId")
    stats = pd.DataFrame({
        "n_sessions_2026": by_course.size(),
        "upcoming_sessions": by_course["traStartDate"].apply(lambda x: int((x > TODAY).sum())),
        "running_sessions": by_course.apply(lambda g: int(((g["traStartDate"] <= TODAY) & (g["traEndDate"] >= TODAY)).sum())),
        "last_session_end": by_course["traEndDate"].max(),
    })
    reps = reps.join(stats, on="trprId")
    reps["running_status"] = np.where(reps["running_sessions"] > 0, "운영 중",
                               np.where(reps["upcoming_sessions"] > 0, "개강 예정", "운영 종료"))
    reps["same_title_courses"] = reps["norm"].map(s.groupby("norm")["trprId"].nunique())
    return reps


def fetch_details(reps, delay):
    out = {}
    for r in reps.itertuples():
        p = PROGRAMS[r.program]
        text = get_text(BASE + p["detail"], {
            "authKey": os.getenv(p["key"]), "returnType": "XML", "outType": "2",
            "srchTrprId": r.trprId, "srchTrprDegr": r.trprDegr, "srchTorgId": r.trainstCstId,
        })
        d = {}
        if "<HRDNet" in text[:300]:
            root = ET.fromstring(text)
            for sec in ("inst_base_info", "inst_detail_info"):
                node = root.find(sec)
                if node is not None:
                    d.update({c.tag: c.text for c in node})
        out[f"{r.trprId}_{r.trprDegr}"] = d
        time.sleep(delay)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DETAIL_RAW.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def to_int(v):
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def build_rows(reps, details, columns):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, extra = [], []
    for r in reps.itertuples():
        d = details.get(f"{r.trprId}_{r.trprDegr}", {})
        hours = to_int(d.get("totTraingTime") or d.get("trtm"))
        days = to_int(d.get("totTraingDyct") or d.get("trDcnt"))
        fee = to_int(d.get("perTrco")) or to_int(r.realMan)
        title = str(r.title).strip()
        search_text = f"{title} {title}"
        uid = f"PUB_{r.trprId}_{r.trprDegr}"
        row = {c: "" for c in columns}
        row.update({
            "course_uid": uid, "provider": r.subTitle, "source_course_id": r.trprId, "title": title,
            "category_depth1": "총무·인사", "category_depth2": d.get("ncsNm") or "", "category_depth3": "",
            "education_type": "집합" if (days or 0) > 0 else "원격(온라인)", "difficulty": "",
            "duration_hours": float(hours) if hours else np.nan, "duration_days": days if (days or 0) > 0 else pd.NA,
            "price": fee if fee is not None else pd.NA, "price_type": "국비 지원/환급",
            "start_date": r.traStartDate, "end_date": r.traEndDate, "url": r.titleLink or "",
            "collected_at": now, "detail_crawled_at": now,
            "source_provider": PROGRAMS[r.program]["source"], "source_file": "work24_2026_refresh",
            "ncs_code": str(r.ncsCd), "mapping_confidence": "HIGH", "mapping_status": "VERIFIED",
            "clean_search_text": search_text, "raw_text_len": len(title), "clean_text_len": len(search_text),
            "chars_reduced": len(title) - len(search_text), "text_quality_status": "TITLE_ONLY",
            "is_base64_cleaned": False, "cleaning_actions": "NONE, work24_2026_refresh",
            "ncs_code_type": "OFFICIAL_NCS_CODE",
        })
        rows.append(row)
        extra.append({
            "course_uid": uid, "trprId": r.trprId, "program": PROGRAMS[r.program]["name"], "trprDegr": r.trprDegr,
            "trainstCstId": r.trainstCstId, "institution": r.subTitle, "title": title, "ncs_code": r.ncsCd,
            "ncs_name": d.get("ncsNm"), "training_hours": hours, "training_days": days, "fee_per_person": fee,
            "self_pay": to_int(d.get("tgcrGnrlTrneOwepAllt")), "gov_program": d.get("govBusiNm"),
            "method_code": d.get("traingMthCd"), "detail_status": "OK" if d else "DETAIL_NOT_FOUND",
            "rep_session_start": r.traStartDate, "rep_session_end": r.traEndDate,
            "n_sessions_2026": r.n_sessions_2026, "upcoming_sessions": r.upcoming_sessions,
            "running_status": r.running_status, "same_title_courses": r.same_title_courses,
            "satisfaction_official": (float(r.stdgScor) if r.program == "K" and to_int(r.stdgScor) else None),
            "course_url": r.titleLink, "checked_at": now,
        })
    return pd.DataFrame(rows), pd.DataFrame(extra)


META = RECO / "course_embeddings_metadata_all.parquet"
META_COLS = ["course_uid", "provider", "title", "category_depth1", "category_depth2", "category_depth3",
             "duration_hours", "price", "url"]


def write_embedding_metadata(catalog: pd.DataFrame):
    """임베딩 행 번호와 과정을 잇는 메타데이터를 카탈로그 순서대로 다시 씀."""
    meta = catalog[META_COLS].copy()
    meta["vector_index"] = np.arange(len(meta))
    meta.to_parquet(META, index=False)


def load_func(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-employer", action="store_true", help="사업주훈련 목록을 새로 수집")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--metadata-only", action="store_true", help="임베딩 메타데이터만 현재 카탈로그 순서로 다시 씀")
    args = parser.parse_args()

    if args.metadata_only:
        write_embedding_metadata(pd.read_parquet(CATALOG))
        print(f"메타데이터 저장: {META.relative_to(ROOT)}")
        return

    sessions = load_sessions(args.refresh_employer, args.delay)
    reps = pick_representatives(sessions)
    print(f"[1] 2026년 '총무·인사' 회차 {len(sessions)}개 → 과정 {sessions['trprId'].nunique()}개 → 제목 기준 대표 {len(reps)}개")
    print(reps.groupby(["program", "running_status"]).size().to_string())
    # 지금 운영 중이거나 개강 예정인 과정만 넣는다 (2026년에 열렸다가 이미 끝난 과정은 제외)
    reps = reps[reps["running_status"] != "운영 종료"]
    print(f"    운영 중·개강 예정만 남김 → {len(reps)}개 ({reps['program'].map({'K': '국민내일배움카드', 'E': '사업주훈련'}).value_counts().to_dict()})")

    df = pd.read_parquet(CATALOG)
    old_mask = df["source_course_id"].astype(str).str.fullmatch(TRPR_RE)
    print(f"[2] 카탈로그에서 교체할 기존 고용24 행: {int(old_mask.sum())}개")
    if args.dry_run:
        print("--dry-run: 파일을 바꾸지 않았습니다.")
        return

    print("[3] 대표 과정 상세정보 조회 (훈련시간·훈련비·훈련일수)")
    details = fetch_details(reps, args.delay)
    new_rows, extra = build_rows(reps, details, df.columns)
    print(f"    상세 확보 {int((extra['detail_status'] == 'OK').sum())}/{len(extra)}")

    # 같은 순서를 유지: 기존 행(고용24 제외) + 새 행
    keep = df[~old_mask].reset_index(drop=True)
    new_rows = new_rows.astype({c: df[c].dtype for c in df.columns}, errors="ignore")
    for c in ["price", "duration_days"]:
        new_rows[c] = pd.array(new_rows[c], dtype="Int64")
    out = pd.concat([keep, new_rows[df.columns]], ignore_index=True)
    assert out["course_uid"].is_unique, "course_uid 중복"

    print("[4] 새 행 토큰·임베딩 계산 (기존 행은 그대로)")
    from src.recommendation.text_preprocessor import HRTextPreprocessor
    prep = HRTextPreprocessor()
    tok = pd.read_parquet(TOKENS).set_index("course_uid")
    new_tok = pd.DataFrame({
        "course_uid": new_rows["course_uid"],
        "tokenized_text": [" ".join(prep.tokenize(t)) for t in new_rows["clean_search_text"]],
    })
    tok_out = pd.concat([tok.loc[keep["course_uid"]].reset_index(), new_tok], ignore_index=True)

    emb = np.load(EMB)
    assert len(emb) == len(df), "임베딩과 카탈로그 행 수가 다릅니다."
    gen = load_func(ROOT / "scripts" / "generate_full_embeddings_ko_sroberta.py", "gen_emb")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")
    texts = [gen.compose_course_text(r) for _, r in new_rows.iterrows()]
    new_emb = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(emb.dtype)
    emb_out = np.vstack([emb[~old_mask.values], new_emb])

    print("[5] 새 행 군집 배정 (기존 군집 중심과 코사인 유사도)")
    cl = pd.read_parquet(CLUSTERS)
    cl_keep = cl.set_index("course_uid").loc[keep["course_uid"]].reset_index()
    kept_emb = emb[~old_mask.values]
    cid = cl_keep["cluster_id"].values
    ids = np.unique(cid)
    cent = np.vstack([kept_emb[cid == i].mean(0) for i in ids])
    cent /= np.linalg.norm(cent, axis=1, keepdims=True)
    assign = ids[(new_emb @ cent.T).argmax(1)]
    labels = cl_keep.groupby("cluster_id")["topic_label"].first()
    cl_new = pd.DataFrame({c: [pd.NA] * len(new_rows) for c in cl.columns})
    for c in cl.columns:
        if c in new_rows.columns:
            cl_new[c] = new_rows[c].values
    cl_new["canonical_platform"] = new_rows["provider"].values
    cl_new["cluster_id"] = assign
    cl_new["topic_label"] = labels.reindex(assign).values
    cl_out = pd.concat([cl_keep, cl_new.astype(cl_keep.dtypes.to_dict(), errors="ignore")], ignore_index=True)
    print("    " + str(pd.Series(cl_new["topic_label"]).value_counts().to_dict()))

    # 백업 후 저장
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for p in [CATALOG, TOKENS, EMB, CLUSTERS, DETAIL_CSV, META]:
        if p.exists():
            shutil.copy2(p, BACKUP_DIR / f"{p.stem}.before_work24_2026_{stamp}{p.suffix}")
    out.to_parquet(CATALOG, index=False, compression="zstd", compression_level=9)
    write_embedding_metadata(out)
    tok_out.to_parquet(TOKENS, index=False)
    np.save(EMB, emb_out)
    cl_out.to_parquet(CLUSTERS, index=False)
    extra.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")
    print(f"[6] 저장 완료: 카탈로그 {len(df)} → {len(out)}행 (삭제 {int(old_mask.sum())}, 추가 {len(new_rows)}), 백업 {BACKUP_DIR.relative_to(ROOT)}/*{stamp}*")


if __name__ == "__main__":
    main()
