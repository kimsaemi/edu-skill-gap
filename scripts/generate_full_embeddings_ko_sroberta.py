"""
8,645건 전체 교육과정 대상 Ko-SRoBERTa (768차원) 임베딩 생성 및 저장 스크립트
- 대상 코퍼스: data/hr/processed/education_courses_search_cleaned.parquet (8,645건)
- 모델: jhgan/ko-sroberta-multitask (768차원)
- 텍스트 구성: 강좌명 + 직무 카테고리 + 주요 커리큘럼/상세 설명 결합
- 배치 처리: GPU(CUDA) 감지 시 batch_size=64, CPU 대체 시 batch_size=32
- 메모리 누수 방지 및 중간 체크포인트 저장 (1,000건 단위)
- 결과물: data/hr/output/recommendation/embeddings_ko_sroberta_all.npy (8645, 768)
"""

import os
import sys
import time
import gc
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def compose_course_text(row):
    """
    강좌명 + 직무 카테고리 + 주요 커리큘럼/상세 설명 결합 함수
    """
    title = str(row.get("title", "")).strip() if pd.notna(row.get("title")) else ""
    
    # 1. 직무 카테고리 계층 결합
    cats = [
        str(row.get(c, "")).strip() 
        for c in ["category_depth1", "category_depth2", "category_depth3"] 
        if pd.notna(row.get(c)) and str(row.get(c, "")).strip()
    ]
    cat_text = " > ".join(cats) if cats else ""
    
    # 2. 주요 커리큘럼 및 상세 설명 (우선순위: clean_curriculum + clean_intro + clean_goals)
    desc_elements = []
    if pd.notna(row.get("clean_curriculum")) and str(row.get("clean_curriculum")).strip():
        desc_elements.append(f"커리큘럼: {str(row.get('clean_curriculum')).strip()[:300]}")
    if pd.notna(row.get("clean_intro")) and str(row.get("clean_intro")).strip():
        desc_elements.append(f"개요: {str(row.get('clean_intro')).strip()[:200]}")
    if pd.notna(row.get("clean_goals")) and str(row.get("clean_goals")).strip():
        desc_elements.append(f"목표: {str(row.get('clean_goals')).strip()[:150]}")
        
    if not desc_elements and pd.notna(row.get("clean_search_text")):
        desc_elements.append(str(row.get("clean_search_text")).strip()[:500])
        
    desc_text = " | ".join(desc_elements)
    
    # 3. 통합 결합 (강좌명 2회 반복 강조 + 직무 카테고리 + 주요 커리큘럼/상세 설명)
    parts = []
    if title:
        parts.append(f"과정명: {title} {title}")
    if cat_text:
        parts.append(f"직무분류: {cat_text}")
    if desc_text:
        parts.append(desc_text)
        
    return " | ".join(parts)

def generate_embeddings():
    start_time = time.time()
    workspace_root = Path(__file__).resolve().parent.parent
    data_path = workspace_root / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
    out_dir = workspace_root / "data" / "hr" / "output" / "recommendation"
    ckpt_dir = out_dir / "checkpoints"
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" [STEP 1] 8,645건 전체 교육과정 대상 Ko-SRoBERTa 임베딩 전수 확장")
    print("=" * 80)

    # 1. 하드웨어 디바이스 감지
    device = "cuda" if torch.cuda.is_available() else "cpu"
    batch_size = 64 if device == "cuda" else 32
    print(f"[1] 하드웨어 감지: {device.upper()}")
    if device == "cuda":
        print(f"    - GPU 모델명: {torch.cuda.get_device_name(0)}")
        print(f"    - 배치 크기: {batch_size} (GPU 가속 모드)")
        print(f"    - 현재 VRAM 사용량: {torch.cuda.memory_allocated(0)/(1024**2):.1f} MB")
    else:
        print(f"    - CPU 모드 작동 (배치 크기: {batch_size})")

    # 2. 데이터셋 로드
    print(f"\n[2] 대상 코퍼스 로드 중: {data_path}")
    df_courses = pd.read_parquet(data_path)
    total_count = len(df_courses)
    print(f"    - 전체 강좌 수: {total_count:,}건")

    # 3. 텍스트 합성
    print("\n[3] 임베딩용 텍스트 합성 중 (강좌명 + 직무 카테고리 + 커리큘럼/상세설명)...")
    texts = [compose_course_text(row) for _, row in df_courses.iterrows()]
    print(f"    - 합성 완료: {len(texts):,}건 (예시 1번 길이: {len(texts[0]):,}자)")
    print(f"    - 샘플 텍스트: {texts[0][:150]}...")

    # 4. 모델 로드
    model_name = "jhgan/ko-sroberta-multitask"
    print(f"\n[4] Ko-SRoBERTa 모델 로드 중 ({model_name})...")
    t0_load = time.time()
    model = SentenceTransformer(model_name, device=device)
    print(f"    - 모델 로드 완료 ({time.time() - t0_load:.2f}초)")

    # 5. 배치 추론 및 체크포인트 저장
    print(f"\n[5] 전체 {total_count:,}건 임베딩 연산 시작...")
    embeddings_list = []
    checkpoint_step = 1000 # 1,000건 단위 체크포인트

    num_batches = (total_count + batch_size - 1) // batch_size
    pbar = tqdm(range(0, total_count, batch_size), desc="Ko-SRoBERTa 임베딩", total=num_batches)

    with torch.no_grad():
        for i in pbar:
            batch_texts = texts[i:i + batch_size]
            batch_emb = model.encode(
                batch_texts,
                batch_size=len(batch_texts),
                show_progress_bar=False,
                normalize_embeddings=True, # L2 정규화 적용 (내적=코사인유사도)
                device=device
            )
            embeddings_list.append(batch_emb)

            current_processed = min(i + batch_size, total_count)

            # 주기적 VRAM 캐시 비우기 및 가비지 컬렉션
            if device == "cuda" and (i // batch_size) % 10 == 0:
                torch.cuda.empty_cache()
                gc.collect()

            # 체크포인트 저장 (1,000건 단위 경계 넘을 때)
            if current_processed % checkpoint_step < batch_size or current_processed == total_count:
                ckpt_current = np.vstack(embeddings_list)
                ckpt_path = ckpt_dir / f"checkpoint_emb_{current_processed}.npy"
                np.save(ckpt_path, ckpt_current)
                # 이전 체크포인트는 삭제하여 디스크 절약
                for old_ckpt in ckpt_dir.glob("checkpoint_emb_*.npy"):
                    if old_ckpt.name != ckpt_path.name:
                        try:
                            old_ckpt.unlink()
                        except Exception:
                            pass

    # 6. 최종 결합 및 저장
    all_embeddings = np.vstack(embeddings_list).astype(np.float32)
    final_emb_path = out_dir / "embeddings_ko_sroberta_all.npy"
    np.save(final_emb_path, all_embeddings)

    # 메타데이터 인덱스 매핑 저장
    meta_df = df_courses[[
        "course_uid", "provider", "title", "category_depth1", "category_depth2",
        "category_depth3", "duration_hours", "price", "url"
    ]].copy()
    meta_df["vector_index"] = np.arange(len(meta_df))
    meta_path = out_dir / "course_embeddings_metadata_all.parquet"
    meta_df.to_parquet(meta_path, compression="zstd")

    # 체크포인트 디렉토리 정리
    for f in ckpt_dir.glob("checkpoint_emb_*.npy"):
        try:
            f.unlink()
        except Exception:
            pass
    try:
        ckpt_dir.rmdir()
    except Exception:
        pass

    total_time = time.time() - start_time
    print("\n" + "=" * 80)
    print(f" [완료] Ko-SRoBERTa 전수 임베딩 생성 및 검증 완료!")
    print(f"  - 최종 임베딩 파일: {final_emb_path}")
    print(f"  - 메타데이터 파일: {meta_path}")
    print(f"  - 임베딩 행렬 Shape: {all_embeddings.shape}")
    print(f"  - 총 소요 시간: {total_time:.2f}초 ({total_time/60:.2f}분)")
    print(f"  - 강좌당 평균 추론 시간: {total_time/total_count*1000:.2f}ms")
    print("=" * 80)

    return all_embeddings.shape

if __name__ == "__main__":
    shape = generate_embeddings()
