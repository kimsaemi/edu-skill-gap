"""
STEP 6: NCS·KSA 기반 머신러닝 직무역량 분류 모델 대시보드 컴포넌트
--------------------------------------------------------------------------------
기존 streamlit_integrated.py에 임베드하거나 독립 실행(streamlit run)할 수 있는 모듈
- Model A(TF-IDF) vs Model B(Ko-SRoBERTa) 비교
- 8대 KSA 역량 다중라벨 예측 확률 분포
- Weak Label(규칙 기반 매핑) 일치도 분석
- 오매핑 109건 및 불일치 강좌 인터랙티브 탐색
- 실시간 임의 강좌 역량 예측 시연
"""

import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import joblib

BASE_DIR = r"d:\26_강의자료\프로젝트2_교육"
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "hr", "output", "recommendation")

FILES = {
    "model": os.path.join(OUTPUT_DIR, "models_competency_classifiers.joblib"),
    "report_json": os.path.join(OUTPUT_DIR, "step6_ml_model_evaluation_report.json"),
    "predictions_parquet": os.path.join(OUTPUT_DIR, "course_competency_predictions_ml.parquet"),
    "mismatch_csv": os.path.join(OUTPUT_DIR, "mismatch_109_ml_predictions.csv"),
    "discrepancy_csv": os.path.join(OUTPUT_DIR, "rule_vs_ml_discrepancies.csv")
}

@st.cache_resource(show_spinner=False)
def load_ml_step6_resources():
    if not os.path.exists(FILES["model"]) or not os.path.exists(FILES["report_json"]):
        return None, None, None, None, None

    model_data = joblib.load(FILES["model"])
    with open(FILES["report_json"], "r", encoding="utf-8") as f:
        report_data = json.load(f)
    
    df_pred = pd.read_parquet(FILES["predictions_parquet"]) if os.path.exists(FILES["predictions_parquet"]) else pd.DataFrame()
    df_mismatch = pd.read_csv(FILES["mismatch_csv"]) if os.path.exists(FILES["mismatch_csv"]) else pd.DataFrame()
    df_discrepancy = pd.read_csv(FILES["discrepancy_csv"]) if os.path.exists(FILES["discrepancy_csv"]) else pd.DataFrame()

    return model_data, report_data, df_pred, df_mismatch, df_discrepancy

def render_step6_ml_dashboard():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1E1B4B 0%, #312E81 50%, #1E293B 100%); padding: 1.5rem 2rem; border-radius: 14px; margin-bottom: 1.5rem; color: white; border: 1px solid rgba(255,255,255,0.1);">
      <span style="background: rgba(99, 102, 241, 0.35); color: #C7D2FE; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.78rem; font-weight: 700;">PILOT EXPERIMENT</span>
      <h2 style="color: #FFFFFF; font-size: 1.65rem; font-weight: 800; margin: 0.5rem 0 0.3rem 0;">STEP 6. NCS·KSA 기반 머신러닝 직무역량 분류 파일럿</h2>
      <p style="color: #94A3B8; margin: 0; font-size: 0.9rem; line-height: 1.5;">
        TF-IDF 및 Ko-SRoBERTa 768차원 임베딩 기반 One-vs-Rest 로지스틱 회귀 모델을 통해 8대 KSA 직무역량을 다중라벨(Multi-label)로 분류하고, 
        약한 라벨(Weak Label) 일치도 및 오매핑 방어 잠재력을 검증합니다.
      </p>
    </div>
    """, unsafe_allow_html=True)

    model_data, report_data, df_pred, df_mismatch, df_discrepancy = load_ml_step6_resources()
    if model_data is None:
        st.warning("⚠️ STEP 6 머신러닝 모델 결과 파일이 존재하지 않습니다. 먼저 스크립트를 실행해 주세요.")
        return

    metrics = report_data["metrics_summary"]
    mod_a = metrics["Model A (TF-IDF)"]
    mod_b = metrics["Model B (Ko-SRoBERTa)"]

    # 주의 경고 배너
    st.info("""
    ℹ️ **평가 라벨 주의사항 (Weak Label Notice)**:  
    본 평가에 사용된 정답 라벨은 사람이 직접 검증한 Ground Truth가 아니며, 기존에 규칙 기반으로 생성된 **약한 라벨(Weak Label)**입니다.  
    따라서 표기된 Precision, Recall, F1 수치는 실제 직무역량 분류 절대 정확도가 아니라 **기존 자동 매핑 체계에 대한 머신러닝 모델의 일치도(Fidelity/Agreement)**를 나타냅니다.
    """)

    # 1. 상단 핵심 메트릭 비교
    st.subheader("1. 모델 성능 및 효율성 비교 (Model A vs Model B)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Model A Macro-F1", f"{mod_a['macro_f1']:.4f}", f"Micro: {mod_a['micro_f1']:.4f}")
    with col2:
        st.metric("Model B Macro-F1", f"{mod_b['macro_f1']:.4f}", f"Micro: {mod_b['micro_f1']:.4f}", delta_color="inverse")
    with col3:
        st.metric("Model A 학습시간", f"{mod_a['train_time_sec']:.2f}초", f"추론: {mod_a['inference_time_ms_per_sample']:.3f}ms/건")
    with col4:
        st.metric("Model B 학습시간", f"{mod_b['train_time_sec']:.2f}초", f"추론: {mod_b['inference_time_ms_per_sample']:.3f}ms/건", delta_color="normal")

    st.markdown("---")

    # 2. 8개 역량별 세부 일치도 비교 차트
    st.subheader("2. 8대 KSA 역량별 Weak Label 일치도 (Precision / Recall / F1)")
    
    comp_list = model_data["competency_targets"]
    comp_ids = [c["id"] for c in comp_list]
    comp_names = [f"{c['id']} ({c['name']})" for c in comp_list]

    chart_data = []
    for c in comp_list:
        cid = c["id"]
        cname = f"{cid}\n{c['name']}"
        ma = mod_a["per_competency"].get(cid, {})
        mb = mod_b["per_competency"].get(cid, {})
        chart_data.append({
            "역량": cname,
            "Model A (TF-IDF) F1": ma.get("f1", 0),
            "Model B (Ko-SRoBERTa) F1": mb.get("f1", 0),
            "Model A Precision": ma.get("precision", 0),
            "Model B Precision": mb.get("precision", 0),
            "Model A Recall": ma.get("recall", 0),
            "Model B Recall": mb.get("recall", 0),
            "평가 표본수(Support)": ma.get("support", 0)
        })
    df_chart = pd.DataFrame(chart_data)

    c_left, c_right = st.columns([3, 2])
    with c_left:
        fig_f1 = px.bar(
            df_chart,
            x="역량",
            y=["Model A (TF-IDF) F1", "Model B (Ko-SRoBERTa) F1"],
            barmode="group",
            title="역량별 F1-score 일치도 비교",
            color_discrete_sequence=["#6366F1", "#10B981"]
        )
        fig_f1.update_layout(yaxis_range=[0, 1.05], margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_f1, use_container_width=True)

    with c_right:
        st.markdown("**역량별 세부 지표 테이블**")
        st.dataframe(
            df_chart[["역량", "Model A (TF-IDF) F1", "Model B (Ko-SRoBERTa) F1", "평가 표본수(Support)"]],
            hide_index=True,
            use_container_width=True
        )

    st.markdown("---")

    # 3. 오매핑 의심 109건 및 불일치 분석
    st.subheader("3. 오매핑 의심 109건 및 불일치·신규 발굴 심층 분석")
    t1, t2, t3 = st.tabs([
        "🚨 오매핑 의심 109건 분석",
        "⚖️ 규칙 매핑 vs 머신러닝 불일치 (위양성 의심)",
        "✨ 미매핑 강좌 중 ML 신규 발굴 후보"
    ])

    with t1:
        st.markdown(f"**기존 규칙 매핑 오매핑 의심 강좌 ({len(df_mismatch)}건)**")
        st.caption("의료 문서, 소방안전, 기계 도면 등 기술/기능 자격 과정이 '문서', '관리' 등 단순 어휘로 인해 HR/총무 역량으로 오분류되었던 샘플")
        st.dataframe(
            df_mismatch[["course_uid", "provider", "title", "max_prob_A", "max_prob_B", "pred_count_A", "pred_count_B"]].head(30),
            hide_index=True,
            use_container_width=True
        )

    with t2:
        st.markdown(f"**규칙으로 매핑되었으나 머신러닝이 역량 없음(0건)으로 판정한 강좌 ({len(df_discrepancy)}건)**")
        st.caption("기존 자동 매핑의 키워드 편향으로 인해 잘못 매핑되었을 가능성이 높은 후보군")
        st.dataframe(
            df_discrepancy[["course_uid", "provider", "title", "max_prob_A", "max_prob_B"]].head(30),
            hide_index=True,
            use_container_width=True
        )

    with t3:
        unmapped = df_pred[df_pred["is_mapped"] == 0]
        discovered = unmapped[unmapped["max_prob_B"] >= 0.8]
        st.markdown(f"**규칙 매핑에서 누락(미매핑 3,679건)되었으나 ML이 고확신(≥0.8)으로 탐지한 강좌 ({len(discovered):,}건)**")
        st.caption("규칙 키워드 사전에 없는 유의어/문맥을 Ko-SRoBERTa 임베딩 모델이 일반화하여 포착한 잠재 강좌")
        st.dataframe(
            discovered[["course_uid", "provider", "title", "max_prob_B", "pred_count_B"]].head(30),
            hide_index=True,
            use_container_width=True
        )

    st.markdown("---")

    # 4. 실시간 임의 강좌 역량 예측기
    st.subheader("4. 🧪 실시간 임의 교육과정 직무역량 분류 시연기")
    st.caption("새로운 강의 제목과 커리큘럼을 입력하면 학습된 모델이 8대 KSA 역량 확률을 즉시 다중라벨로 산출합니다.")

    c_in1, c_in2 = st.columns([3, 1])
    with c_in1:
        sample_title = st.text_input("강의 제목 입력", value="2026 신임 팀장을 위한 핵심 인사평가 및 다면 피드백 실무 코칭")
    with c_in2:
        btn_predict = st.button("역량 다중라벨 분류 실행", type="primary")

    if sample_title:
        # TF-IDF 모델을 통한 즉시 분류 시연
        vec = model_data["vectorizer"]
        clf = model_data["clf_tfidf"]
        x_vec = vec.transform([sample_title])
        probs = clf.predict_proba(x_vec)[0]

        pred_res = []
        for i, c in enumerate(comp_list):
            pred_res.append({
                "역량 코드": c["id"],
                "역량명": c["name"],
                "직무군": c["job_family"],
                "NCS 코드": c["ncs_unit_code"],
                "예측 확률": round(probs[i] * 100, 1),
                "분류 판정 (≥50%)": "✅ 역량 해당" if probs[i] >= 0.5 else "❌ 미해당"
            })
        df_demo = pd.DataFrame(pred_res).sort_values("예측 확률", ascending=False)

        c_demo1, c_demo2 = st.columns([3, 2])
        with c_demo1:
            fig_demo = px.bar(
                df_demo,
                x="역량명",
                y="예측 확률",
                color="직무군",
                text="예측 확률",
                title=f"'{sample_title}' 역량별 소속 확률 (%)"
            )
            fig_demo.update_layout(yaxis_range=[0, 105])
            st.plotly_chart(fig_demo, use_container_width=True)
        with c_demo2:
            st.dataframe(df_demo, hide_index=True, use_container_width=True)

if __name__ == "__main__":
    st.set_page_config(page_title="STEP 6 ML Competency Dashboard", page_icon="🤖", layout="wide")
    render_step6_ml_dashboard()
