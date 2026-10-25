"""
Tab 3. 원격훈련 학습행태 통계 및 하이브리드 재교육 운영 모델 (주간 시간표 포함)
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def render_tab3(df_stats):
    st.subheader("📈 원격훈련 학습행태 통계 및 주간 하이브리드(블렌디드) 운영 시간표")
    st.write("원격훈련 통계에서 도출된 **'평일 야간/주말 집중'** 및 **'온라인 40시간 이탈선'**을 반영하여, 직장인이 실제 완주할 수 있는 주간 하이브리드 시간표를 제시합니다.")
    
    # 1. 훈련 시수별 수료율 추이 & 도넛 차트
    col1, col2 = st.columns(2)
    with col1:
        fig_trend = px.line(
            df_stats,
            x="total_hours",
            y="completion_rate",
            color="target_group",
            markers=True,
            title="온라인 훈련 시수(H) 증가에 따른 수료율(%) 낙차 추이",
            labels={"total_hours": "온라인 훈련 시수 (시간)", "completion_rate": "수료율 (%)", "target_group": "학습자 대상"}
        )
        fig_trend.add_vline(x=40, line_dash="dash", line_color="#EF4444", annotation_text="온라인 이탈 임계선 (40H)")
        st.plotly_chart(fig_trend, width="stretch")
        
    with col2:
        fig_donut = go.Figure(data=[go.Pie(
            labels=['온라인 K-MOOC (평일 야간 자율)', '대학평생교육원 실습 (격주 토요일)'],
            values=[60, 40],
            hole=.5,
            marker_colors=['#3B82F6', '#10B981']
        )])
        fig_donut.update_layout(title_text="하이브리드 황금 비율 (온라인 60% : 오프라인 40%)")
        st.plotly_chart(fig_donut, width="stretch")

    st.markdown("---")

    # 2. [추가] 재직자 맞춤형 주간 하이브리드 시간표 (Weekly Schedule Preview)
    st.markdown("### 📅 [생활밀착형 시뮬레이션] 재직자의 1주일 하이브리드 재교육 타임테이블")
    st.write("수도권 직장인이 퇴근 후와 주말을 활용하여 부담 없이 마이크로디그리를 이수할 수 있는 표준 주간 일정입니다.")

    # 주간 일정 데이터프레임 시각화
    schedule_data = [
        {"요일": "월요일 (평일)", "시간대": "20:30 ~ 22:00 (1.5H)", "방식": "🌐 온라인 (비동기)", "장소": "자택 / 모바일", "활동 내용": "K-MOOC 이론 강의 시청 (개념 이해)"},
        {"요일": "화요일 (평일)", "시간대": "20:30 ~ 21:30 (1.0H)", "방식": "🌐 온라인 (자율)", "장소": "자택", "활동 내용": "온라인 퀴즈 풀이 및 게시판 질의응답"},
        {"요일": "수요일 (평일)", "시간대": "20:30 ~ 22:00 (1.5H)", "방식": "🌐 온라인 (비동기)", "장소": "자택 / 모바일", "활동 내용": "사례 연구(Case Study) 동영상 학습"},
        {"요일": "목요일 (평일)", "시간대": "자율 학습", "방식": "휴식 / 자율", "장소": "-", "활동 내용": "주중 업무 집중 및 복습"},
        {"요일": "금요일 (평일)", "시간대": "20:30 ~ 21:30 (1.0H)", "방식": "🌐 온라인 (과제)", "장소": "자택", "활동 내용": "토요일 오프라인 실습 사전 준비 과제 제출"},
        {"요일": "토요일 (격주)", "시간대": "10:00 ~ 15:00 (4.0H)", "방식": "🏫 오프라인 (집체)", "장소": "대학평생교육원 컴퓨터 랩실", "활동 내용": "교수/전문가 멘토링, AI/전산 실습, 팀 프로젝트"},
        {"요일": "일요일 (주말)", "시간대": "전일", "방식": "재충전", "장소": "-", "활동 내용": "한 주 학습 마무리 및 휴식"}
    ]
    df_schedule = pd.DataFrame(schedule_data)

    st.dataframe(
        df_schedule,
        hide_index=True,
        width="stretch"
    )

    # 3. 시간표 핵심 포인트 카드
    c_card1, c_card2, c_card3 = st.columns(3)
    with c_card1:
        st.info("""
        **🌙 평일 야간 온라인 (총 5.0시간)**
        - 이동 시간 없는 자택 학습
        - 1.25~1.5배속 수강 지원
        - 평일 번아웃 방지 1.5H 이내 제한
        """)
    with c_card2:
        st.success("""
        **🏢 격주 토요일 평생교육원 (4.0시간)**
        - 수도권 지하철 접근성 활용
        - 컴퓨터 랩실 전산/AI 실습
        - 강사 1:1 대면 피드백
        """)
    with c_card3:
        st.warning("""
        **🎯 기대 효과 (수료율 90% 달성)**
        - 순수 온라인 대비 중도 탈락 방지
        - 직장 생활과 학습의 균형(Work-Study Balance)
        - 실무 포트폴리오 완성
        """)
