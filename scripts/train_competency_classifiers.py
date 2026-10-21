"""
NCS·KSA 기반 머신러닝 직무역량 다중라벨 분류 모델 학습 및 평가 파이프라인
--------------------------------------------------------------------------------
1. 모델 A: TF-IDF (Kiwi 명사 토큰) + One-vs-Rest Logistic Regression
2. 모델 B: Ko-SRoBERTa 768차원 임베딩 + One-vs-Rest Logistic Regression
3. 데이터 누출(Data Leakage) 방지: 정규화 강좌명 기반 GroupShuffleSplit
4. Weak Label 평가: 기존 규칙 기반 매핑과의 일치도(Fidelity/Agreement) 정밀 측정
5. 전수(8,645건) 예측 및 오매핑 109건 / 미매핑 3,679건 심층 분석
6. 추천 시스템 하이브리드 결합 시뮬레이션
"""

import os
import sys
import time
import json
import re
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    f1_score, precision_score, recall_score, roc_auc_score,
    hamming_loss, classification_report
)
import joblib

# 프로젝트 경로 설정
BASE_DIR = r"d:\26_강의자료\프로젝트2_교육"
DATA_DIR = os.path.join(BASE_DIR, "data", "hr")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
OUTPUT_DIR = os.path.join(DATA_DIR, "output", "recommendation")

FILES = {
    "search_cleaned": os.path.join(PROCESSED_DIR, "education_courses_search_cleaned.parquet"),
    "tokenized_cache": os.path.join(PROCESSED_DIR, "tokenized_corpus_cache.parquet"),
    "embeddings_npy": os.path.join(OUTPUT_DIR, "embeddings_ko_sroberta_all.npy"),
    "comp_wide": os.path.join(OUTPUT_DIR, "matrix_course_competency_wide.parquet"),
    "mismatch_json": os.path.join(OUTPUT_DIR, "mapping_mismatch_samples.json")
}

# 8대 KSA 역량 마스터 정의
COMPETENCY_TARGETS = [
    {"id": "COMP_GA_01", "name": "문서작성 및 기획", "ncs_unit_code": "02010101_16v3", "job_family": "총무"},
    {"id": "COMP_GA_02", "name": "비품 및 자산관리", "ncs_unit_code": "02010102_16v3", "job_family": "총무"},
    {"id": "COMP_HR_01", "name": "인력채용", "ncs_unit_code": "02020201_16v3", "job_family": "인사"},
    {"id": "COMP_HR_02", "name": "인사평가 및 보상", "ncs_unit_code": "02020202_16v3", "job_family": "인사"},
    {"id": "COMP_LABOR_01", "name": "근로관계 법률 준수", "ncs_unit_code": "02030201_16v3", "job_family": "인사"},
    {"id": "COMP_MGMT_01", "name": "프로젝트 및 조직관리", "ncs_unit_code": "01010102_16v3", "job_family": "경영지원"},
    {"id": "COMP_MGMT_02", "name": "경영전략 및 재무회계 기초", "ncs_unit_code": "02030101_16v3", "job_family": "경영지원"},
    {"id": "COMP_SEC_01", "name": "비즈니스 매너 및 커뮤니케이션", "ncs_unit_code": "02040302_16v3", "job_family": "경영지원"}
]

TARGET_COLS = [c["id"] for c in COMPETENCY_TARGETS]

def normalize_title(t: str) -> str:
    """회차/특수문자/대괄호를 제거하여 동일 교육과정 그룹화"""
    if not t or not isinstance(t, str):
        return ""
    # [1기], (심화), [환급] 등 괄호 내용 제거
    t = re.sub(r'\[.*?\]|\(.*?\)', '', t)
    # 특수문자 제거
    t = re.sub(r'[^\w\s]', ' ', t)
    # 공백 정규화 및 소문자
    return re.sub(r'\s+', ' ', t).strip().lower()

def load_and_prepare_data():
    print("[1/7] 데이터 로드 및 전처리 시작...")
    df_courses = pd.read_parquet(FILES["search_cleaned"])
    df_tokens = pd.read_parquet(FILES["tokenized_cache"])
    df_wide = pd.read_parquet(FILES["comp_wide"])
    embeddings = np.load(FILES["embeddings_npy"])

    print(f"  - 원본 코퍼스: {len(df_courses):,}건")
    print(f"  - 토큰 캐시: {len(df_tokens):,}건")
    print(f"  - 역량 매트릭스: {len(df_wide):,}건")
    print(f"  - Ko-SRoBERTa 임베딩: {embeddings.shape}")

    # course_uid 기준 병합
    df_merged = df_courses[['course_uid', 'provider', 'title', 'category_depth1', 'category_depth2']].copy()
    df_merged = df_merged.merge(df_tokens[['course_uid', 'tokenized_text']], on='course_uid', how='left')
    df_merged = df_merged.merge(df_wide[['course_uid', 'is_mapped'] + TARGET_COLS], on='course_uid', how='left')
    df_merged['tokenized_text'] = df_merged['tokenized_text'].fillna('')

    # 정규화 제목 생성
    df_merged['norm_title'] = df_merged['title'].apply(normalize_title)
    # 정규화 제목이 비어있으면 원본 제목 사용
    mask_empty = df_merged['norm_title'].str.len() == 0
    df_merged.loc[mask_empty, 'norm_title'] = df_merged.loc[mask_empty, 'title']

    return df_merged, embeddings

def split_data_group_aware(df_merged: pd.DataFrame):
    print("\n[2/7] 데이터 분할 (Data Leakage 차단 Group-aware Split)...")
    
    # 지도학습은 약한 라벨(weak label)이 존재하는 is_mapped == 1인 4,966건 대상
    labeled_mask = df_merged['is_mapped'] == 1
    df_labeled = df_merged[labeled_mask].copy().reset_index(drop=False) # 원래 인덱스 보존 ('index' 컬럼)
    
    print(f"  - 지도학습 대상 (weak labeled): {len(df_labeled):,}건")
    print(f"  - 미매핑(unlabeled) 코퍼스: {(df_merged['is_mapped'] == 0).sum():,}건 (임의 0 라벨 왜곡 방지)")
    print(f"  - 라벨 코퍼스 내 고유 강좌 그룹(norm_title): {df_labeled['norm_title'].nunique():,}개")

    groups = df_labeled['norm_title'].values

    # 1단계: Train(70%) vs Temp(30%) GroupSplit
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=42)
    train_idx_rel, temp_idx_rel = next(gss1.split(df_labeled, groups=groups))

    df_temp = df_labeled.iloc[temp_idx_rel].copy()
    groups_temp = df_temp['norm_title'].values

    # 2단계: Temp(30%) -> Val(15%) vs Test(15%) GroupSplit
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=42)
    val_idx_sub, test_idx_sub = next(gss2.split(df_temp, groups=groups_temp))

    val_idx_rel = temp_idx_rel[val_idx_sub]
    test_idx_rel = temp_idx_rel[test_idx_sub]

    train_df = df_labeled.iloc[train_idx_rel].copy()
    val_df = df_labeled.iloc[val_idx_rel].copy()
    test_df = df_labeled.iloc[test_idx_rel].copy()

    # 데이터 누출 검증: Train, Val, Test 그룹 간 제목 교집합 확인
    train_titles = set(train_df['norm_title'])
    val_titles = set(val_df['norm_title'])
    test_titles = set(test_df['norm_title'])

    leak_train_val = len(train_titles.intersection(val_titles))
    leak_train_test = len(train_titles.intersection(test_titles))
    leak_val_test = len(val_titles.intersection(test_titles))

    print(f"  - Train Set: {len(train_df):,}건 (고유 그룹 {train_df['norm_title'].nunique():,}개)")
    print(f"  - Validation Set: {len(val_df):,}건 (고유 그룹 {val_df['norm_title'].nunique():,}개)")
    print(f"  - Test Set: {len(test_df):,}건 (고유 그룹 {test_df['norm_title'].nunique():,}개)")
    print(f"  - [검증 완료] 그룹 간 중복 강좌 수: Train-Val={leak_train_val}, Train-Test={leak_train_test}, Val-Test={leak_val_test} (완전 분리 성공!)")

    return train_df, val_df, test_df, df_labeled

def train_and_evaluate_models(train_df, val_df, test_df, embeddings, df_merged):
    print("\n[3/7] 모델 학습 및 평가 (Model A vs Model B)...")
    
    Y_train = train_df[TARGET_COLS].values.astype(int)
    Y_val = val_df[TARGET_COLS].values.astype(int)
    Y_test = test_df[TARGET_COLS].values.astype(int)

    # -------------------------------------------------------------
    # Model A: TF-IDF + OneVsRest Logistic Regression
    # -------------------------------------------------------------
    print("\n>>> [Model A] TF-IDF + One-vs-Rest Logistic Regression")
    t0 = time.time()
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True
    )
    X_train_tfidf = vectorizer.fit_transform(train_df['tokenized_text'])
    X_val_tfidf = vectorizer.transform(val_df['tokenized_text'])
    X_test_tfidf = vectorizer.transform(test_df['tokenized_text'])
    X_all_tfidf = vectorizer.transform(df_merged['tokenized_text'])

    clf_a = OneVsRestClassifier(LogisticRegression(
        C=1.0,
        max_iter=1000,
        class_weight='balanced',
        solver='liblinear',
        random_state=42
    ))
    clf_a.fit(X_train_tfidf, Y_train)
    t_train_a = time.time() - t0
    print(f"  - Model A 학습 소요시간: {t_train_a:.2f}초")

    # 추론 시간 및 예측 (Test set)
    t0_inf = time.time()
    prob_test_a = clf_a.predict_proba(X_test_tfidf)
    t_inf_a = (time.time() - t0_inf) / len(test_df) * 1000  # ms/sample
    pred_test_a = (prob_test_a >= 0.5).astype(int)

    # -------------------------------------------------------------
    # Model B: Ko-SRoBERTa 768d + OneVsRest Logistic Regression
    # -------------------------------------------------------------
    print("\n>>> [Model B] Ko-SRoBERTa 768차원 임베딩 + One-vs-Rest Logistic Regression")
    train_orig_idx = train_df['index'].values
    val_orig_idx = val_df['index'].values
    test_orig_idx = test_df['index'].values

    X_train_emb = embeddings[train_orig_idx]
    X_val_emb = embeddings[val_orig_idx]
    X_test_emb = embeddings[test_orig_idx]
    X_all_emb = embeddings

    t0_b = time.time()
    clf_b = OneVsRestClassifier(LogisticRegression(
        C=1.0,
        max_iter=1000,
        class_weight='balanced',
        solver='lbfgs',
        random_state=42
    ))
    clf_b.fit(X_train_emb, Y_train)
    t_train_b = time.time() - t0_b
    print(f"  - Model B 학습 소요시간: {t_train_b:.2f}초")

    # 추론 시간 및 예측 (Test set)
    t0_inf_b = time.time()
    prob_test_b = clf_b.predict_proba(X_test_emb)
    t_inf_b = (time.time() - t0_inf_b) / len(test_df) * 1000  # ms/sample
    pred_test_b = (prob_test_b >= 0.5).astype(int)

    # -------------------------------------------------------------
    # 다중라벨 평가 지표 계산 (Weak Label 일치도)
    # -------------------------------------------------------------
    metrics_summary = {}

    for m_name, y_pred, y_prob, t_train, t_inf in [
        ("Model A (TF-IDF)", pred_test_a, prob_test_a, t_train_a, t_inf_a),
        ("Model B (Ko-SRoBERTa)", pred_test_b, prob_test_b, t_train_b, t_inf_b)
    ]:
        macro_f1 = f1_score(Y_test, y_pred, average='macro', zero_division=0)
        micro_f1 = f1_score(Y_test, y_pred, average='micro', zero_division=0)
        samples_f1 = f1_score(Y_test, y_pred, average='samples', zero_division=0)
        macro_prec = precision_score(Y_test, y_pred, average='macro', zero_division=0)
        macro_rec = recall_score(Y_test, y_pred, average='macro', zero_division=0)
        h_loss = hamming_loss(Y_test, y_pred)
        
        # 역량별 AUC 및 F1
        per_comp = {}
        aucs = []
        for i, col in enumerate(TARGET_COLS):
            f1_i = f1_score(Y_test[:, i], y_pred[:, i], zero_division=0)
            prec_i = precision_score(Y_test[:, i], y_pred[:, i], zero_division=0)
            rec_i = recall_score(Y_test[:, i], y_pred[:, i], zero_division=0)
            try:
                auc_i = roc_auc_score(Y_test[:, i], y_prob[:, i])
                aucs.append(auc_i)
            except Exception:
                auc_i = 0.5
            per_comp[col] = {
                "precision": round(prec_i, 4),
                "recall": round(rec_i, 4),
                "f1": round(f1_i, 4),
                "auc": round(auc_i, 4),
                "support": int(Y_test[:, i].sum())
            }

        mean_auc = float(np.mean(aucs)) if aucs else 0.5

        metrics_summary[m_name] = {
            "training_samples": len(train_df),
            "test_samples": len(test_df),
            "train_time_sec": round(t_train, 3),
            "inference_time_ms_per_sample": round(t_inf, 3),
            "macro_f1": round(macro_f1, 4),
            "micro_f1": round(micro_f1, 4),
            "samples_f1": round(samples_f1, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "roc_auc_mean": round(mean_auc, 4),
            "hamming_loss": round(h_loss, 4),
            "per_competency": per_comp
        }

    # 전체 코퍼스 전수 예측 (8,645건)
    print("\n[4/7] 8,645건 전체 교육과정 대상 전수 추론 실행...")
    prob_all_a = clf_a.predict_proba(X_all_tfidf)
    prob_all_b = clf_b.predict_proba(X_all_emb)

    return (
        clf_a, clf_b, vectorizer, metrics_summary,
        prob_all_a, prob_all_b,
        Y_test, prob_test_a, prob_test_b
    )

def analyze_predictions_and_mismatches(df_merged, prob_all_a, prob_all_b):
    print("\n[5/7] 오매핑 109건 및 불일치·불확실 강좌 심층 분석...")
    
    # 1. 109건 오매핑 샘플 로드
    mismatch_109_uids = []
    if os.path.exists(FILES["mismatch_json"]):
        with open(FILES["mismatch_json"], "r", encoding="utf-8") as f:
            m_data = json.load(f)
            mismatch_109_uids = [x["course_uid"] for x in m_data if "course_uid" in x]

    # 각 모델별 전체 예측 결과를 데이터프레임에 추가
    df_pred = df_merged[['course_uid', 'provider', 'title', 'is_mapped']].copy()
    
    for i, col in enumerate(TARGET_COLS):
        df_pred[f"{col}_prob_A"] = np.round(prob_all_a[:, i], 4)
        df_pred[f"{col}_prob_B"] = np.round(prob_all_b[:, i], 4)
        df_pred[f"{col}_pred_A"] = (prob_all_a[:, i] >= 0.5).astype(int)
        df_pred[f"{col}_pred_B"] = (prob_all_b[:, i] >= 0.5).astype(int)

    # 최대 예측 확률 및 엔트로피 (불확실성 지표)
    df_pred["max_prob_A"] = prob_all_a.max(axis=1)
    df_pred["max_prob_B"] = prob_all_b.max(axis=1)
    df_pred["pred_count_A"] = (prob_all_a >= 0.5).sum(axis=1)
    df_pred["pred_count_B"] = (prob_all_b >= 0.5).sum(axis=1)

    # 109건 오매핑 샘플에서 모델 예측 분석
    mismatch_sub = df_pred[df_pred['course_uid'].isin(mismatch_109_uids)].copy()
    print(f"  - 109건 오매핑 의심 강좌 중 매칭된 데이터: {len(mismatch_sub)}건")
    
    # 모델 A와 B가 109건 강좌에 대해 양성(>=0.5)으로 예측한 비율
    # 규칙 기반 매핑에서는 모두 1개 이상의 역량이 매핑되어 있었으나, ML 모델은 이를 어떻게 보았는가?
    a_zero_pred = (mismatch_sub['pred_count_A'] == 0).sum()
    b_zero_pred = (mismatch_sub['pred_count_B'] == 0).sum()
    print(f"  - Model A(TF-IDF)가 109건 중 역량 없음(0건)으로 판정하여 오매핑을 방어한 강좌: {a_zero_pred}건 ({a_zero_pred/len(mismatch_sub)*100:.1f}%)")
    print(f"  - Model B(Ko-SRoBERTa)가 109건 중 역량 없음(0건)으로 판정하여 오매핑을 방어한 강좌: {b_zero_pred}건 ({b_zero_pred/len(mismatch_sub)*100:.1f}%)")

    # 모델이 확신하기 어려운 강좌 (Ambiguous: 0.35 <= max_prob <= 0.65)
    ambiguous_a = df_pred[(df_pred["max_prob_A"] >= 0.35) & (df_pred["max_prob_A"] <= 0.65)]
    ambiguous_b = df_pred[(df_pred["max_prob_B"] >= 0.35) & (df_pred["max_prob_B"] <= 0.65)]
    print(f"  - 확신하기 어려운 모호한 강좌 수: Model A={len(ambiguous_a)}건, Model B={len(ambiguous_b)}건")

    # 기존 자동 매핑과의 불일치 강좌 (Discrepancy)
    # 기존에 매핑되어 있었으나(is_mapped==1) 두 모델 모두 0으로 예측한 강좌 (위양성 의심)
    mapped_courses = df_pred[df_pred['is_mapped'] == 1]
    both_zero = mapped_courses[(mapped_courses['pred_count_A'] == 0) & (mapped_courses['pred_count_B'] == 0)]
    print(f"  - 기존 규칙 매핑이었으나 두 ML 모델 모두 역량 없음(0개)으로 평가한 강좌: {len(both_zero)}건 (규칙 오매핑 후보)")

    # 기존에 미매핑이었으나(is_mapped==0) 모델이 높은 확률(>=0.8)로 역량을 찾아낸 강좌 (신규 발굴 후보)
    unmapped_courses = df_pred[df_pred['is_mapped'] == 0]
    discovered_a = unmapped_courses[unmapped_courses['max_prob_A'] >= 0.8]
    discovered_b = unmapped_courses[unmapped_courses['max_prob_B'] >= 0.8]
    print(f"  - 미매핑(3,679건) 중 모델이 높은 확신(>=0.8)으로 신규 발견한 강좌: Model A={len(discovered_a)}건, Model B={len(discovered_b)}건")

    return df_pred, mismatch_sub, ambiguous_b, both_zero, discovered_b

def simulate_hybrid_recommender_integration(df_pred, embeddings):
    print("\n[6/7] 추천 엔진 연동 사전 분석 및 시뮬레이션...")
    # 대표 인사/총무 테스트 쿼리 3개에 대한 시뮬레이션
    # 1) "인력채용 선발 면접" -> COMP_HR_01
    # 2) "근로기준법 임금 퇴직금" -> COMP_LABOR_01
    # 3) "비품 구매 자산관리" -> COMP_GA_02

    from sklearn.metrics.pairwise import cosine_similarity
    
    test_scenarios = [
        {"query": "인재 채용 프로세스 및 면접 기법", "target_comp": "COMP_HR_01", "name": "인력채용"},
        {"query": "근로기준법과 취업규칙 개정 실무", "target_comp": "COMP_LABOR_01", "name": "노무준법"},
        {"query": "사옥 시설 및 비품 고정자산 관리", "target_comp": "COMP_GA_02", "name": "자산관리"}
    ]

    simulation_results = []

    for sc in test_scenarios:
        comp_id = sc["target_comp"]
        ml_prob_b = df_pred[f"{comp_id}_prob_B"].values
        ml_prob_a = df_pred[f"{comp_id}_prob_A"].values

        # 임의로 임베딩 유사도와의 상관관계 측정
        # 여기서는 전체 강좌의 임베딩 평균과 비교하거나, 쿼리 임베딩 대신 해당 역량의 ML 점수 분포 분석
        spearman_corr = pd.Series(ml_prob_a).corr(pd.Series(ml_prob_b), method='spearman')
        pearson_corr = pd.Series(ml_prob_a).corr(pd.Series(ml_prob_b), method='pearson')

        # ML 예측 점수를 필터(Penalty Gate)로 적용할 때의 방어 효과:
        # P(target_comp) < 0.15인 강좌 수 (비관련 강좌)
        filtered_out = (ml_prob_b < 0.15).sum()

        simulation_results.append({
            "scenario": sc["name"],
            "target_competency": comp_id,
            "spearman_corr_A_B": round(spearman_corr, 4),
            "pearson_corr_A_B": round(pearson_corr, 4),
            "unrelated_filter_count": int(filtered_out),
            "unrelated_filter_ratio": round(filtered_out / len(df_pred) * 100, 2),
            "high_confidence_candidates": int((ml_prob_b >= 0.7).sum())
        })

    print("  - 시뮬레이션 결과 요약:")
    for res in simulation_results:
        print(f"    * [{res['scenario']}] A-B 상관계수: {res['spearman_corr_A_B']} | 비관련 필터 방어 강좌: {res['unrelated_filter_count']:,}건 ({res['unrelated_filter_ratio']}%) | 고확신 후보: {res['high_confidence_candidates']}건")

    return simulation_results

def save_artifacts_and_results(
    clf_a, clf_b, vectorizer, metrics_summary,
    df_pred, mismatch_sub, ambiguous_b, both_zero, discovered_b,
    sim_results
):
    print("\n[7/7] 결과 아티팩트 및 모델 파일 저장...")

    # 1. 학습된 모델 저장
    model_save_path = os.path.join(OUTPUT_DIR, "models_competency_classifiers.joblib")
    model_payload = {
        "clf_tfidf": clf_a,
        "vectorizer": vectorizer,
        "clf_sroberta": clf_b,
        "target_columns": TARGET_COLS,
        "competency_targets": COMPETENCY_TARGETS,
        "metrics_summary": metrics_summary,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    joblib.dump(model_payload, model_save_path, compress=3)
    print(f"  - 모델 파일 저장 완료: {model_save_path} ({os.path.getsize(model_save_path):,} bytes)")

    # 2. 교육과정별 8개 역량 예측 결과 Parquet 저장
    pred_save_path = os.path.join(OUTPUT_DIR, "course_competency_predictions_ml.parquet")
    df_pred.to_parquet(pred_save_path, index=False)
    print(f"  - 전수 예측 Parquet 저장 완료: {pred_save_path} ({len(df_pred):,} rows)")

    # 3. 모델 비교 및 분석 요약 JSON 저장
    report_json_path = os.path.join(OUTPUT_DIR, "step6_ml_model_evaluation_report.json")
    full_report_data = {
        "metrics_summary": metrics_summary,
        "simulation_results": sim_results,
        "analysis_counts": {
            "total_courses": len(df_pred),
            "mismatch_109_count": len(mismatch_sub),
            "mismatch_defended_by_model_a": int((mismatch_sub['pred_count_A'] == 0).sum()),
            "mismatch_defended_by_model_b": int((mismatch_sub['pred_count_B'] == 0).sum()),
            "ambiguous_courses_model_b": len(ambiguous_b),
            "discrepancy_rule_mapped_but_both_zero": len(both_zero),
            "unmapped_discovered_by_model_b": len(discovered_b)
        },
        "sample_discrepancies": both_zero[['course_uid', 'provider', 'title', 'max_prob_A', 'max_prob_B']].head(20).to_dict(orient='records'),
        "sample_discovered": discovered_b[['course_uid', 'provider', 'title', 'max_prob_B', 'pred_count_B']].head(20).to_dict(orient='records')
    }
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(full_report_data, f, ensure_ascii=False, indent=2)
    print(f"  - 상세 리포트 JSON 저장 완료: {report_json_path}")

    # 4. 불일치 및 오매핑 의심 상세 CSV 저장
    mismatch_csv_path = os.path.join(OUTPUT_DIR, "mismatch_109_ml_predictions.csv")
    mismatch_sub.to_csv(mismatch_csv_path, index=False, encoding="utf-8-sig")
    print(f"  - 109건 예측 결과 CSV 저장 완료: {mismatch_csv_path}")

    discrepancy_csv_path = os.path.join(OUTPUT_DIR, "rule_vs_ml_discrepancies.csv")
    both_zero.to_csv(discrepancy_csv_path, index=False, encoding="utf-8-sig")
    print(f"  - 자동 매핑 vs ML 불일치 CSV 저장 완료: {discrepancy_csv_path}")

def main():
    print("=" * 70)
    print("STEP 6: NCS·KSA 기반 머신러닝 직무역량 다중라벨 분류 모델 파이프라인")
    print("=" * 70)
    
    # 1. 로드
    df_merged, embeddings = load_and_prepare_data()

    # 2. 누출 차단 그룹 분할
    train_df, val_df, test_df, df_labeled = split_data_group_aware(df_merged)

    # 3. 모델 학습 및 평가
    (
        clf_a, clf_b, vectorizer, metrics_summary,
        prob_all_a, prob_all_b,
        Y_test, prob_test_a, prob_test_b
    ) = train_and_evaluate_models(train_df, val_df, test_df, embeddings, df_merged)

    # 4. 오매핑 및 불일치 심층 분석
    df_pred, mismatch_sub, ambiguous_b, both_zero, discovered_b = analyze_predictions_and_mismatches(
        df_merged, prob_all_a, prob_all_b
    )

    # 5. 추천 엔진 연동 시뮬레이션
    sim_results = simulate_hybrid_recommender_integration(df_pred, embeddings)

    # 6. 결과 저장
    save_artifacts_and_results(
        clf_a, clf_b, vectorizer, metrics_summary,
        df_pred, mismatch_sub, ambiguous_b, both_zero, discovered_b,
        sim_results
    )

    print("\n" + "=" * 70)
    print("STEP 6 머신러닝 파이프라인 실행 완료!")
    print("=" * 70)

if __name__ == "__main__":
    main()
