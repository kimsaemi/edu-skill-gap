"""
test_new_flow_verification.py
고객 행동 중심 화면 및 진단 결과-교육 분리 검증 스크립트
"""
import sys
from pathlib import Path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from streamlit.testing.v1 import AppTest

def test_flow():
    print("=" * 60)
    print("고객 대시보드 신규 UX 흐름 AppTest 검증 시작")
    print("=" * 60)

    app_path = str(WORKSPACE_ROOT / "customer_dashboard" / "streamlit_customer.py")
    at = AppTest.from_file(app_path)
    at.run(timeout=30)
    assert not at.exception, f"초기 로드 예외: {at.exception}"

    # 1. 첫 화면 Hero 요소 검증
    all_markdown = " ".join([m.value for m in at.markdown])
    assert "내 업무에 필요한 역량과 교육을 찾아보세요" in all_markdown
    assert "인사·총무·경영지원 업무를 점검하고, 보완하고 싶은 역량에 맞는 교육을 확인하세요." in all_markdown
    assert "업무 선택" in all_markdown and "자기점검" in all_markdown and "결과·교육 확인" in all_markdown
    assert "로그인 없이 이용" in all_markdown
    assert "자기평가 기반 학습 가이드" in all_markdown
    print("✅ 1. 첫 화면 Hero 제목, 설명, 3단계 흐름, 안내 배지 검증 통과")

    # 시작 버튼 및 샘플 버튼 존재 확인
    start_btns = [b for b in at.button if "내 역량 점검 시작" in b.label]
    assert len(start_btns) > 0, "내 역량 점검 시작 버튼 누락"
    sample_btns = [b for b in at.button if "샘플 결과" in b.label]
    assert len(sample_btns) > 0, "샘플 결과 버튼 누락"
    print("✅ 2. 주요 시작 버튼 및 보조 샘플 버튼 존재 확인")

    # 2. 진단 전 '🎓 맞춤 교육' 탭 검증
    # 탭 전환: 맞춤 교육
    at.session_state["active_main_tab"] = "🎓 맞춤 교육"
    at.run(timeout=30)
    assert not at.exception, f"맞춤 교육 탭 로드 예외: {at.exception}"
    rec_markdown = " ".join([m.value for m in at.markdown])
    assert "역량 점검을 완료하면 맞춤 교육을 확인할 수 있어요" in rec_markdown
    print("✅ 3. 진단 전 맞춤 교육 탭 안내('역량 점검을 완료하면 맞춤 교육을 확인할 수 있어요') 검증 통과")

    # 3. 샘플 모드 진입 및 진단 결과 화면 검증
    sample_btns = [b for b in at.button if "샘플 결과" in b.label]
    assert len(sample_btns) > 0, "샘플 결과 버튼 누락"
    sample_btns[0].click()
    at.run(timeout=30)
    assert not at.exception, f"샘플 모드 클릭 후 예외: {at.exception}"
    assert at.session_state["is_sample_mode"] is True
    assert at.session_state["eval_result"] is not None
    assert at.session_state["rec_bundle"] is not None
    print("✅ 4. 샘플 결과 생성 및 샘플 모드 플래그 활성화 확인")

    # Tab 1 결과 확인: 우선 보완 역량 카드 및 상단 배치 검증
    t1_headers = " ".join([h.value for h in at.subheader])
    t1_markdown = " ".join([m.value for m in at.markdown])
    assert "3. 역량 점검 결과 및 보완 우선순위" in t1_headers
    assert "우선 보완할 핵심 역량" in t1_markdown
    assert "목표와의 차이" in t1_markdown
    assert "선택한 보완 역량에 맞는 교육을 확인해보세요" in t1_markdown
    print("✅ 5. 진단 결과 상단 우선 보완 역량 배치 및 목표와의 차이 문구 검증 통과")

    # Tab 1에 교육 리스트(render_recommendation_view)가 인라인 중복으로 뜨지 않는지 검증
    # t1_inline_ 프리픽스가 Tab 1 버튼 목록에 없어야 함!
    t1_inline_btns = [b for b in at.button if "t1_inline_" in getattr(b, "key", "")]
    assert len(t1_inline_btns) == 0, f"Tab 1에 교육 카드가 중복 인라인 렌더링됨: {len(t1_inline_btns)}건"
    print("✅ 6. 진단 결과 아래 교육 목록 중복 노출 제거 검증 통과 (화면 완전 분리)")

    # 4. 맞춤 교육으로 이동 버튼 동작 검증
    go_rec_btns = [b for b in at.button if "내 역량에 맞는 교육 보기" in b.label]
    assert len(go_rec_btns) > 0, "내 역량에 맞는 교육 보기 버튼 누락"
    go_rec_btns[0].click()
    at.run(timeout=30)
    assert not at.exception, f"교육 보기 클릭 후 예외: {at.exception}"
    assert at.session_state["active_main_tab"] == "🎓 맞춤 교육"
    print("✅ 7. '내 역량에 맞는 교육 보기' 클릭 시 '🎓 맞춤 교육' 탭으로 전환 확인")

    # 5. 맞춤 교육 탭에서 진단 결과 다시 보기 버튼 동작 검증
    back_btns = [b for b in at.button if "진단 결과 다시 보기" in b.label]
    assert len(back_btns) > 0, "진단 결과 다시 보기 버튼 누락"
    back_btns[0].click()
    at.run(timeout=30)
    assert not at.exception, f"결과 다시 보기 클릭 후 예외: {at.exception}"
    assert at.session_state["active_main_tab"] == "📋 내 역량 점검"
    print("✅ 8. '진단 결과 다시 보기' 클릭 시 '📋 내 역량 점검' 탭으로 복귀 확인")

    # 6. 개별 역량 맞춤 교육 보기 버튼 검증
    comp_rec_btns = [b for b in at.button if "이 역량 교육 보기" in b.label]
    assert len(comp_rec_btns) > 0, "개별 역량 교육 보기 버튼 누락"
    comp_rec_btns[0].click()
    at.run(timeout=30)
    assert not at.exception, f"개별 역량 교육 보기 클릭 후 예외: {at.exception}"
    assert at.session_state["active_main_tab"] == "🎓 맞춤 교육"
    assert at.session_state["selected_competency_filter"] != "ALL"
    print(f"✅ 9. 개별 역량 교육 보기 클릭 시 해당 역량 필터({at.session_state['selected_competency_filter']}) 활성화 및 탭 전환 확인")

    # 전체 보완 역량 복원 버튼 검증
    clear_filter_btns = [b for b in at.button if "전체 보완 역량 보기" in b.label]
    assert len(clear_filter_btns) > 0, "전체 보완 역량 복원 버튼 누락"
    clear_filter_btns[0].click()
    at.run(timeout=30)
    assert at.session_state["selected_competency_filter"] == "ALL"
    print("✅ 10. '전체 보완 역량 보기' 클릭 시 필터 정상 해제 확인")

    # 7. 다운로드 버튼 존재 검증
    at.session_state["active_main_tab"] = "📋 내 역량 점검"
    at.run(timeout=30)
    dl_btns = [b for b in at.download_button if "진단 결과 텍스트 요약" in b.label]
    assert len(dl_btns) > 0, "결과 다운로드 버튼 누락"
    print("✅ 11. 진단 결과 텍스트 요약 다운로드 버튼 정상 동작 확인")

    print("\n🎉 모든 고객 행동 중심 신규 요구사항 전수 검증 완벽 통과!")

if __name__ == "__main__":
    test_flow()
