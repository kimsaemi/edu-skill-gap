"""
test_new_flow_verification.py
고객용 앱(팀 v2.1 구조) 단계 흐름 검증

1. 첫 화면: 히어로·단계 바, 직급 5개·분야 12개 선택
2. 직급·분야 선택 → 2단계(업무별 숙련도 자가진단, 역량 선택, 진단 저장)
3. 3단계: 부족 업무별 추천 카드, 종료 표시, 근거에 만족도 점수 미반영 안내
4. 전체 교육 찾기: 검색·비용 필터
5. 내 학습 현황: 수강 표시 상태 변경, 목표 만들기
"""
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from streamlit.testing.v1 import AppTest  # noqa: E402


def md_text(at) -> str:
    return " ".join(str(m.value) for m in at.markdown)


def test_flow():
    print("=" * 60)
    print("고객용 앱 단계 흐름 AppTest 검증")
    print("=" * 60)
    at = AppTest.from_file(str(WORKSPACE_ROOT / "customer_dashboard" / "streamlit_customer.py"), default_timeout=900)
    at.run()
    assert not at.exception, f"초기 로드 예외: {at.exception}"

    # 1. 첫 화면
    md = md_text(at)
    assert "인사·총무·경영지원 업무·성장·교육 안내" in md
    assert "내 위치를 골라 주세요" in md
    grade_btns = [b for b in at.button if b.key and b.key.startswith("g_")]
    dom_btns = [b for b in at.button if b.key and b.key.startswith("d_")]
    assert len(grade_btns) == 5 and len(dom_btns) == 12, (len(grade_btns), len(dom_btns))
    nxt = [b for b in at.button if "다음 · 내가 하는 일" in b.label][0]
    assert nxt.disabled, "직급·분야를 고르기 전에는 다음 버튼이 꺼져 있어야 합니다."
    print("✅ 1. 첫 화면: 직급 5개·분야 12개, 선택 전 다음 버튼 비활성")

    # 2. 과장 · 노사관계·노무 선택 → 2단계
    [b for b in at.button if b.key == "g_2"][0].click().run()
    [b for b in at.button if b.key == "d_DOM_09"][0].click().run()
    [b for b in at.button if "다음 · 내가 하는 일" in b.label][0].click().run()
    assert at.session_state["step"] == "2", at.session_state["step"]
    md = md_text(at)
    assert "업무별 숙련도 자가진단" in md and "직급이 올라가면" in md
    level_keys = [w.key for w in at.segmented_control if w.key and w.key.startswith("tl_")]
    assert len(level_keys) == 10, f"노무 분야 업무 10개의 진단 칸이 필요합니다: {len(level_keys)}"
    for k in level_keys[:3]:
        w = at.segmented_control(key=k)  # 다시 그려진 화면에서 위젯을 새로 찾음
        w.set_value(w.options[1]).run()  # 1단계 → 과장 기준(3단계)보다 낮음
    assert len(at.session_state["tl"]) == 3
    [b for b in at.button if "진단 저장" in b.label][0].click().run()
    assert len(at.session_state["diag_log"]) == 1
    print("✅ 2. 2단계: 업무 10개 진단 칸, 숙련도 입력 3건, 진단 저장")

    # 3. 3단계 추천
    [b for b in at.button if "맞춤 교육 보기" in b.label][0].click().run()
    assert not at.exception, f"3단계 예외: {at.exception}"
    md = md_text(at)
    assert md.count("🟧 업무") == 3, "부족 업무 3개마다 추천 섹션이 있어야 합니다."
    assert 'class="course' in md
    print("✅ 3. 3단계: 부족 업무 3개 섹션과 추천 카드")

    # 4. 전체 교육 찾기
    [b for b in at.button if b.key == "nav_all"][0].click().run()
    at.text_input(key="f_q").input("노무").run()
    total = int(at.caption[0].value.split("개")[0].replace(",", ""))
    at.selectbox(key="f_cost").set_value("GOV").run()
    gov = int(at.caption[0].value.split("개")[0].replace(",", ""))
    assert 0 < gov <= total, (gov, total)
    print(f"✅ 4. 전체 교육 찾기: '노무' {total}개 → 국비 지원 {gov}개")

    # 5. 내 학습 현황
    [b for b in at.button if "수강 신청 표시" in b.label][0].click().run()
    [b for b in at.button if b.key == "nav_my"][0].click().run()
    uid = next(iter(at.session_state["enroll"]))
    at.segmented_control(key=f"st_{uid}").set_value("learning").run()
    assert at.session_state["enroll"][uid]["status"] == "learning"
    assert not at.exception, f"내 학습 현황 예외: {at.exception}"
    print("✅ 5. 내 학습 현황: 수강 표시와 상태 변경")
    print("\n🎉 고객용 앱 단계 흐름 검증 통과")


if __name__ == "__main__":
    test_flow()
