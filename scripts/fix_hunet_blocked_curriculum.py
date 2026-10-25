"""
휴넷 강좌 커리큘럼에 저장된 '웹 방화벽 접속 차단 안내' 페이지 텍스트를 제거하고,
검색 토큰 캐시와 Ko-SRoBERTa 임베딩을 다시 만듭니다.

배경
- 상세 페이지 크롤링 때 휴넷 웹 방화벽이 요청을 막아, 실제 커리큘럼 대신
  "접속 차단 안내 (Blocked - Violation of Web Security Policy)" 페이지가 글자가 깨진 채 저장됨
- 해당 텍스트가 clean_search_text·BM25 토큰·임베딩에 그대로 들어가 휴넷 강좌끼리 비슷하게 묶이는 원인이 됨

처리
1. 원본 백업: data/hr/processed/backup/ 와 data/hr/output/recommendation/backup/ (최초 1회)
2. 차단 페이지가 든 행의 curriculum·clean_curriculum 비우기
3. step5_2_clean_and_validate.py 와 같은 규칙으로 clean_search_text·텍스트 길이·품질 등급 재계산
   (cleaning_actions 에 BLOCKED_PAGE_REMOVED 추가)
4. 전체 검색 토큰 캐시(tokenized_corpus_cache.parquet) 재생성
5. 영향받은 행만 임베딩 재계산 (generate_full_embeddings_ko_sroberta.py 와 같은 텍스트 구성·모델·정규화)
   - 재현성 확인: 영향 없는 행 일부를 다시 임베딩해 기존 값과 코사인 유사도 비교

실행: python scripts/fix_hunet_blocked_curriculum.py
"""

import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

PROC = ROOT / "data" / "hr" / "processed"
OUTR = ROOT / "data" / "hr" / "output" / "recommendation"
CORPUS = PROC / "education_courses_search_cleaned.parquet"
TOKENS = PROC / "tokenized_corpus_cache.parquet"
EMB = OUTR / "embeddings_ko_sroberta_all.npy"

BLOCK_PATTERN = re.compile(r"Violation of Web Security Policy|접속\s*차단|ì\s*ì\s*ì°¨ë")


def backup(path: Path) -> None:
    dst_dir = path.parent / "backup"
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / f"{path.stem}.before_hunet_block_fix{path.suffix}"
    if not dst.exists():
        shutil.copy2(path, dst)
        print(f"  백업: {dst.relative_to(ROOT)}")
    else:
        print(f"  백업 이미 있음: {dst.relative_to(ROOT)}")


def quality_status(clean_search_text: str, title: str) -> str:
    body = max(len(clean_search_text) - (len(title) * 2 + 1), 0)
    if body >= 200:
        return "RICH"
    if body >= 50:
        return "MODERATE"
    if body == 0:
        return "TITLE_ONLY"
    return "VERY_SHORT"


def main() -> int:
    print("[1] 백업")
    for p in (CORPUS, TOKENS, EMB):
        backup(p)

    df = pd.read_parquet(CORPUS)
    hit = df["curriculum"].fillna("").astype(str).str.contains(BLOCK_PATTERN) | \
          df["clean_curriculum"].fillna("").astype(str).str.contains(BLOCK_PATTERN)
    idx = np.where(hit.values)[0]
    print(f"[2] 차단 페이지 포함 행: {len(idx)}건 / 제공기관: {df.loc[hit, 'provider'].value_counts().to_dict()}")
    if len(idx) == 0:
        print("  정리할 행이 없습니다 (이미 처리됨).")
        return 0
    before_quality = df.loc[hit, "text_quality_status"].value_counts().to_dict()

    for i in idx:
        title = str(df.at[i, "title"] or "").strip()
        intro = str(df.at[i, "clean_intro"] or "").strip() if pd.notna(df.at[i, "clean_intro"]) else ""
        goals = str(df.at[i, "clean_goals"] or "").strip() if pd.notna(df.at[i, "clean_goals"]) else ""
        parts = [title, title] + [p for p in (intro, goals) if p]
        cst = re.sub(r"\s+", " ", " ".join(parts)).strip()
        df.at[i, "curriculum"] = ""
        df.at[i, "clean_curriculum"] = ""
        df.at[i, "clean_search_text"] = cst
        df.at[i, "clean_text_len"] = len(cst)
        df.at[i, "chars_reduced"] = int(df.at[i, "raw_text_len"]) - len(cst) if pd.notna(df.at[i, "raw_text_len"]) else None
        df.at[i, "text_quality_status"] = quality_status(cst, title)
        actions = str(df.at[i, "cleaning_actions"] or "NONE")
        actions = "BLOCKED_PAGE_REMOVED" if actions in ("", "NONE", "nan") else actions + ";BLOCKED_PAGE_REMOVED"
        df.at[i, "cleaning_actions"] = actions

    after_quality = df.loc[hit, "text_quality_status"].value_counts().to_dict()
    print(f"    품질 등급 변화: {before_quality} → {after_quality}")
    remain = sum(df[c].fillna("").astype(str).str.contains(BLOCK_PATTERN).sum() for c in ["curriculum", "clean_curriculum", "clean_search_text"])
    assert remain == 0, f"차단 문구가 {remain}건 남아 있습니다"
    df.to_parquet(CORPUS, index=False)
    print(f"    저장: {CORPUS.relative_to(ROOT)}")

    print("[3] 검색 토큰 캐시 재생성 (전체)")
    from src.recommendation.text_preprocessor import HRTextPreprocessor
    prep = HRTextPreprocessor()
    tokens = []
    for txt in df["clean_search_text"]:
        toks = prep.tokenize(txt)
        tokens.append(" ".join(toks) if toks else "기초")
    old_tok = pd.read_parquet(TOKENS)
    new_tok = pd.DataFrame({"course_uid": df["course_uid"], "tokenized_text": tokens})
    changed = (old_tok.set_index("course_uid")["tokenized_text"] != new_tok.set_index("course_uid")["tokenized_text"]).sum()
    new_tok.to_parquet(TOKENS, compression="zstd")
    print(f"    토큰이 바뀐 행: {changed}건 (차단 행 {len(idx)}건)")

    print("[4] 임베딩 재계산 (영향받은 행)")
    from sentence_transformers import SentenceTransformer
    from generate_full_embeddings_ko_sroberta import compose_course_text
    emb = np.load(EMB)
    assert emb.shape[0] == len(df), "임베딩 행 수가 코퍼스와 다릅니다"
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")

    # 재현성 확인: 영향 없는 행 50건
    rng = np.random.RandomState(7)
    ctrl = rng.choice(np.where(~hit.values)[0], size=50, replace=False)
    ctrl_vec = model.encode([compose_course_text(df.iloc[i]) for i in ctrl], normalize_embeddings=True, batch_size=32)
    ctrl_cos = (ctrl_vec * emb[ctrl]).sum(axis=1)
    print(f"    재현성(영향 없는 50건) 코사인: 최소 {ctrl_cos.min():.4f}, 평균 {ctrl_cos.mean():.4f}")
    if ctrl_cos.min() < 0.99:
        print("[FAIL] 기존 임베딩과 같은 방식으로 재현되지 않습니다. 임베딩을 바꾸지 않고 중단합니다.")
        return 1

    texts = [compose_course_text(df.iloc[i]) for i in idx]
    new_vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True).astype(np.float32)
    shift = (new_vecs * emb[idx]).sum(axis=1)
    emb[idx] = new_vecs
    np.save(EMB, emb)
    print(f"    {len(idx)}건 갱신, 기존 벡터와의 코사인: 중앙 {np.median(shift):.3f} (낮을수록 많이 바뀜)")

    # 차단 행끼리 얼마나 뭉쳐 있었는지 비교
    old_emb = np.load(EMB.parent / "backup" / f"{EMB.stem}.before_hunet_block_fix{EMB.suffix}")
    sample = idx[rng.choice(len(idx), size=min(300, len(idx)), replace=False)]

    def mean_pairwise(m):
        s = m @ m.T
        n = len(m)
        return (s.sum() - n) / (n * (n - 1))
    print(f"    차단 행끼리 평균 유사도: 정리 전 {mean_pairwise(old_emb[sample]):.3f} → 정리 후 {mean_pairwise(emb[sample]):.3f}")
    print("완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
