"""
고객용 HTML 화면 2개의 내장 데이터를 확정 과정 데이터로 다시 만든다.

대상
  hr_career_platform_v2.html   (3단계 안내형)   : const DATA = {...};
  hr_career_platform_easy.html (쉬운 설명형)    : const MASTER_DATA = {...};

입력
  data/hr/output/recommendation/hr_recommendation_candidates.csv
    확정 295건 + 고용24 공식 만족도(scripts/attach_work24_satisfaction.py)
    + 고용24 상세 링크(scripts/fix_work24_course_urls.py)

바꾸는 것 (2026-10-28 검토 결과)
  1. 과정 목록: 예전 팀원 295건(교육시간 기본값 40시간 포함) -> 확정 295건
     (890만 원 해외연수 1건, 주제 불일치 1건 제외. 사업주훈련은 실제 훈련비로 표시)
     같은 과정명은 한 장의 카드로 묶고 기관 수를 표시한다.
  2. easy 화면의 '지금 추천하는 교육' 92개 과정은 수집 데이터 어디에도 없는 과정명이었다
     -> 확정 과정 중 분야 키워드가 과정명에 들어 있는 실제 과정으로 교체 (없으면 비워 두고 '없음' 안내)
  3. 과정별 '수강 시 +2 Level, 직무 적합도 +35%p' 같은 효과 문구 삭제 (측정 근거 없음)
  4. easy 화면의 직급별 연봉 범위 삭제 (출처 없음)
  5. 고용24 만족도는 참고 정보로만 표시 (추천 순서에는 쓰지 않음)

분야-과정 연결은 과정명 키워드 일치 방식이며, 사람이 검수하지 않았다. 화면에도 그렇게 안내한다.

실행: python scripts/build_customer_platform_data.py
여러 번 실행해도 결과가 같다.
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "hr" / "output" / "recommendation" / "hr_recommendation_candidates.csv"
# 예전 HTML 고객 화면 (현재 고객 서비스는 customer_dashboard/streamlit_customer.py). 2026-10-29 legacy/로 옮김
V2_HTML = ROOT / "legacy" / "hr_career_platform_v2.html"
EASY_HTML = ROOT / "legacy" / "hr_career_platform_easy.html"
LEGACY_BANNER = (
    '<div id="legacy-banner" style="position:sticky;top:0;z-index:9999;background:#fff4ce;color:#5c4400;'
    'border-bottom:1px solid #e0c060;padding:8px 14px;font:13px/1.5 sans-serif;">'
    '예전 버전 화면입니다. 현재 고객 서비스는 Streamlit 고객 앱(customer_dashboard/streamlit_customer.py), '
    '발표 자료는 presentation/index.html입니다. 이 화면의 과정은 2026-10-28 확정 과정(인사 범위, 팀원 검수 반영) 기준입니다.</div>'
)


def add_legacy_banner(html):
    """<body> 바로 뒤에 예전 버전 안내를 한 번만 넣는다."""
    if 'id="legacy-banner"' in html:
        return html
    m = re.search(r"<body[^>]*>", html)
    return html[:m.end()] + "\n" + LEGACY_BANNER + html[m.end():] if m else LEGACY_BANNER + html

# 9개 인사 분야 -> 과정명 키워드 (영문은 소문자로 비교)
# '연봉'(예: '억대 연봉 작가'), '입사'(예: '입사에서 퇴사까지 노동법')처럼 다른 뜻으로 걸리는 단어는 뺐다.
DOMAIN_KEYWORDS = {
    "DOM_01": ["인력계획", "인력 계획", "인력운영", "정원", "인건비", "인사기획", "인사전략", "인력관리"],
    "DOM_02": ["직무분석", "직무기술서", "조직설계", "직무관리", "직무평가", "직무중심", "직무급"],
    "DOM_03": ["채용", "면접", "선발", "리크루팅", "헤드헌팅"],
    "DOM_04": ["온보딩", "신입사원", "신규입사", "리텐션"],
    "DOM_05": ["성과관리", "성과평가", "인사평가", "평가제도", "평가체계", "kpi", "okr", "mbo", "목표관리"],
    "DOM_06": ["보상", "연봉제", "급여", "임금", "4대보험", "연말정산", "원천징수", "퇴직금", "복리후생", "인센티브"],
    "DOM_07": ["hrd", "교육담당", "교육과정", "사내강사", "교수설계", "addie", "인재육성", "교육기획"],
    "DOM_08": ["조직문화", "조직활성화", "조직개발", "몰입", "핵심가치", "팀빌딩", "조직진단"],
    "DOM_09": ["노무", "노동법", "근로기준법", "노사", "취업규칙", "징계", "해고", "노동조합", "근로계약"],
}

PLATFORM_NAMES = {
    "고용24_국민내일배움카드": "고용24 국민내일배움카드",
    "고용24_사업주훈련": "고용24 사업주훈련",
    "HUNET": "휴넷", "KPC": "한국생산성본부(KPC)", "KMA": "한국능률협회(KMA)",
    "GSEEK": "경기도 GSEEK", "MULTICAMPUS": "멀티캠퍼스", "FASTCAMPUS": "패스트캠퍼스",
}

# v2 화면의 과정 분류. 프로젝트 범위가 '인사'로 정해져 총무(GA) 과정은 확정 데이터에서 제외되었다
# (scripts/apply_hr_scope_and_ncs_crosswalk.py). 인사 분야가 아닌 과정은 '공통 업무역량'으로 보여준다.
CATS = {
    "HR": "인사 직접 관련", "OFFICE": "엑셀·문서·사무", "DATA": "AI·데이터",
    "COMM": "소통·보고", "LEAD": "리더십·직장 기본기", "OTHER": "기타",
}
CAT_WHY = {
    "OFFICE": "자료 정리와 보고서 작성에 두루 쓰는 사무 도구",
    "DATA": "숫자와 데이터로 근거를 만드는 역량",
    "COMM": "구성원과 설득하고 소통하는 역량",
    "LEAD": "일하는 방식과 사람 관리의 기본기",
}
COMPETENCY_CAT = {
    "인력채용": "HR", "인사평가 및 보상": "HR", "근로관계 법률 준수": "HR",
    "문서작성 및 기획": "OFFICE", "비즈니스 매너 및 커뮤니케이션": "COMM",
}
DATA_WORDS = ["ai", "데이터", "chatgpt", "챗gpt", "파이썬", "엑셀", "자동화", "디지털", "dx"]
LEAD_WORDS = ["리더", "팀장", "관리자", "조직"]

COMMON_NOTICE = (
    "안내: 과정은 고용24·교육기관에서 수집한 실제 과정입니다(2025~2026년 수집). "
    "현재 개설 여부와 수강료는 각 과정 페이지에서 확인하세요. 분야와 과정의 연결은 팀원 4명이 검수했습니다"
    "(검수하지 않은 3개 과정은 과정명 키워드로 연결). 직급별 역할·승진 과제·조언은 팀이 만든 예시이며 공식 기준이 아닙니다."
)


def norm_title(t):
    return re.sub(r"\s+", " ", re.sub(r"^(EB24[A-Z0-9]+\s+)", "", str(t))).strip()


def load_courses():
    df = pd.read_csv(CANDIDATES, dtype=str)
    # 이상치(890만 원 해외연수)와 주제 불일치 과정(scripts/fix_work24_fee_and_scope.py) 제외
    df = df[~df["recommendation_readiness"].str.startswith("EXCLUDED")].copy()
    df["title_norm"] = df["course_name"].map(norm_title)
    df["sat"] = pd.to_numeric(df.get("satisfaction_official"), errors="coerce")
    df["hours"] = pd.to_numeric(df["training_hours"], errors="coerce")
    df["fee"] = pd.to_numeric(df["course_fee"], errors="coerce")
    # 사업주훈련은 수강비(courseMan) 대신 실제 훈련비(realMan)를 보여준다 (수강비 0원을 '무료'로 표시하던 오류 수정)
    df["is_employer"] = df["source_platform"].eq("고용24_사업주훈련")
    if "work24_training_cost" in df.columns:
        real = pd.to_numeric(df["work24_training_cost"], errors="coerce")
        df.loc[df["is_employer"] & real.notna(), "fee"] = real

    rows = []
    for title, g in df.groupby("title_norm", sort=False):
        first = g.iloc[0]
        lower = title.lower()
        doms = [d for d, kws in DOMAIN_KEYWORDS.items() if any(k in lower for k in kws)]
        # 팀원 검수 결과가 있으면 키워드 대신 검수 결과를 쓴다 (scripts/apply_domain_review_results.py)
        reviewed = first.get("domain_review_source") == "팀원 검수"
        if reviewed:
            rid = first.get("hr_domain_reviewed_id")
            doms = [x for x in str(rid).split("|") if x] if isinstance(rid, str) else []
        comp = first["primary_competency_name"]
        cat = "HR" if doms else COMPETENCY_CAT.get(comp, "OTHER")
        if reviewed and not doms and cat == "HR":
            cat = "OFFICE"  # 검수에서 '사무 일반'으로 본 과정은 인사 분야 과정으로 보여주지 않는다
        if cat == "OFFICE" and any(w in lower for w in DATA_WORDS):
            cat = "DATA"
        if cat in ("OFFICE", "OTHER") and any(w in lower for w in LEAD_WORDS):
            cat = "LEAD"

        insts = list(dict.fromkeys(g["institution_name"].dropna()))
        inst = insts[0] if len(insts) == 1 else f"{insts[0]} 외 {len(insts) - 1}곳"
        sats = g["sat"].dropna()
        if sats.empty:
            sat_text = ""
        elif sats.min() == sats.max():
            sat_text = f"고용24 만족도 {sats.iloc[0]:.1f}점(응답자 수 미공개, 2025년 회차)"
        else:
            sat_text = f"고용24 만족도 {sats.min():.1f}~{sats.max():.1f}점(기관별, 응답자 수 미공개, 2025년 회차)"
        hours = g["hours"].dropna()
        fees = g["fee"].dropna()
        if fees.empty:
            fee_text = "수강료 문의"
        elif fees.max() == 0:
            fee_text = "무료(0원)"
        elif fees.min() == fees.max():
            fee_text = f"{fees.iloc[0]:,.0f}원"
        else:
            fee_text = f"{fees.min():,.0f}~{fees.max():,.0f}원(기관별)"
        if g["is_employer"].all():
            fee_text = f"실제 훈련비 {fee_text} · 사업주훈련(사업주 부담 후 환급)"
        elif g["is_employer"].any():
            fee_text += " · 사업주훈련 포함(실제 훈련비 기준)"

        rows.append({
            "id": first["course_id"],
            "title": title,
            "inst": inst,
            "n_insts": len(insts),
            "platform": PLATFORM_NAMES.get(first["source_platform"], first["source_platform"]),
            "url": first["course_url"],
            "competency": comp,
            "doms": doms,
            "cat": cat,
            "hours": float(hours.iloc[0]) if not hours.empty else None,
            "fee_text": fee_text,
            "sat_text": sat_text,
        })
    return rows


def replace_const(html, name, data):
    pattern = re.compile(rf"(const {name} = )(\{{.*?\}})(;\s*\n)", re.S)
    m = pattern.search(html)
    if not m:
        raise ValueError(f"{name}를 찾지 못했습니다")
    return html[:m.start(2)] + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + html[m.end(2):]


def read_const(html, name):
    return json.loads(re.search(rf"const {name} = (\{{.*?\}});\s*\n", html, re.S).group(1))


def sub_once(html, old, new):
    """화면 문구 교체. 이미 바뀐 상태면 그대로 둔다(재실행 안전)."""
    if new in html:
        return html
    if html.count(old) != 1:
        raise ValueError(f"교체할 문구를 정확히 한 번 찾지 못했습니다: {old[:40]}")
    return html.replace(old, new)


def drop_old_notice(html):
    """예전 안내 문구(검수 전 버전)가 남아 있으면 지운다. 새 문구는 sub_once가 다시 넣는다."""
    return re.sub(r"\n?[ \t]*<p [^>]*>안내: [^<]*사람이 검수하지 않았습니다[^<]*</p>(\n[ \t]*)?", "\n", html, count=1)


def build_v2(courses):
    html = drop_old_notice(V2_HTML.read_text(encoding="utf-8"))
    data = read_const(html, "DATA")
    data["courses"] = [{
        "id": c["id"], "t": c["title"], "inst": c["inst"], "plat": c["platform"], "url": c["url"],
        "cat": c["cat"], "doms": c["doms"], "grades": [0, 1, 2, 3, 4],
        "fee": c["fee_text"], "hours": c["hours"], "sat": c["sat_text"],
    } for c in courses]
    data["cats"] = CATS
    data["catWhy"] = CAT_WHY
    # 분야별 '공통 역량' 분류는 기존 값을 유지하되, 확정 과정에 회계(ACCT) 과정이 없어 보상 분야만 바꾼다
    data["related"] = {d: [c if c in CATS else "DATA" for c in cats] for d, cats in data["related"].items()}
    data["rawCourseCount"] = len(courses)
    html = replace_const(html, "DATA", data)

    # 카드에 수강료·시간·만족도 표시 (만족도는 참고 정보)
    html = sub_once(
        html,
        "<div class=\"meta\">${esc(c.inst)} · ${esc(c.plat)}</div>",
        "<div class=\"meta\">${esc(c.inst)} · ${esc(c.plat)}</div>\n"
        "    <div class=\"meta\">${esc(c.fee || '수강료 문의')}${c.hours ? ' · ' + esc(String(c.hours)) + '시간' : ''}</div>\n"
        "    ${c.sat ? `<div class=\"sub\">참고 · ${esc(c.sat)}</div>` : ''}",
    )
    html = sub_once(
        html,
        "<p class=\"hint\">고용24와 인프런의 실제 과정 ${C.length}개를 분류했어요.",
        "<p class=\"hint\">고용24와 교육기관에서 수집한 확정 과정 ${C.length}개를 분류했어요(같은 과정명은 하나로 묶음).",
    )
    html = sub_once(
        html,
        "<h2>3단계 · ${esc(gr.name)} · ${esc(dom.short)}에 맞는 교육</h2>",
        "<h2>3단계 · ${esc(gr.name)} · ${esc(dom.short)}에 맞는 교육</h2>\n"
        "    <p class=\"sub\">" + COMMON_NOTICE + "</p>",
    )
    html = sub_once(
        html,
        "<div class=\"card\"><h4>다음 직급으로 가려면</h4>",
        "<div class=\"card\"><h4>다음 직급으로 가려면 <span class=\"sub\">(예시)</span></h4>",
    )
    V2_HTML.write_text(add_legacy_banner(html), encoding="utf-8")


def build_easy(courses):
    html = drop_old_notice(EASY_HTML.read_text(encoding="utf-8"))
    data = read_const(html, "MASTER_DATA")

    data["course_catalog"] = [{
        "id": c["id"], "course_title": c["title"], "institution": c["inst"], "platform": c["platform"],
        "training_hours": c["hours"], "cost_type": c["fee_text"], "url": c["url"],
        "domain_category": c["competency"],
        "impact_summary": c["sat_text"] or f"관련 역량: {c['competency']}",
    } for c in courses]
    data["metadata"]["total_courses"] = len(courses)
    data["metadata"]["course_source"] = "확정 과정(hr_recommendation_candidates.csv), 과정명 기준 묶음"
    # 예전 이름표('16대 HR 직무')를 실제 화면 데이터(인사 9개 분야)에 맞춘다
    data["metadata"]["standard"] = "인사 9개 분야 (NCS 인사·노무관리 기반, 대응표: data/hr/reference/hr_domain_ncs_crosswalk.csv)"
    data["metadata"].pop("total_jobs", None)
    data["metadata"]["total_domains"] = len(DOMAIN_KEYWORDS)
    data["metadata"]["scope"] = "인사"

    by_dom = {d: [c for c in courses if d in c["doms"]] for d in DOMAIN_KEYWORDS}
    ms = data["matrix_system"]
    for dom in ms["domains"]:
        picks = by_dom.get(dom["id"], [])[:3]
        real = [{"title": c["title"], "inst": c["inst"], "tag": c["competency"], "hours": c["hours"],
                 "can_do": "", "url": c["url"]} for c in picks]
        for task in dom["tasks"]:
            for cell in task["grades_cell"].values():
                cell["courses"] = real
    for step in ms["linear_career_pathway"]:
        step.pop("salary_band", None)
        step["recommended_tracks"] = []
    # 화면 코드가 쓰지 않는 16개 직무 데이터(jobs, domains)에는 출처 없는 연봉 범위, 수집 데이터에 없는
    # 추천 과정, '+15점 향상' 같은 효과 문구가 들어 있어 페이지에서 뺀다.
    data.pop("jobs", None)
    data.pop("domains", None)
    html = replace_const(html, "MASTER_DATA", data)

    # 연봉 표시 삭제
    html = re.sub(r"\n\s*<div style=\"font-size: 14px; font-weight: 800; color: #4338ca;\">\s*"
                  r"예상 연봉 밴드: \$\{currentStep\.salary_band\}\s*</div>", "", html)
    # 교육시간 기본값(16시간) 대신 정보 없음 표시
    html = html.replace("${course.hours || 16}시간", "${course.hours ? course.hours + '시간' : '시간 정보 없음'}")
    html = html.replace("⏱️${c.hours || 16}h", "⏱️${c.hours ? c.hours + 'h' : '-'}")
    html = html.replace("⏱️ ${course.training_hours || 16}시간",
                        "⏱️ ${course.training_hours ? course.training_hours + '시간' : '시간 정보 없음'} · ${course.cost_type || ''}")
    # 카탈로그: 과정명으로 고용24를 검색하던 링크 -> 실제 과정 페이지
    html = sub_once(html, "<a class=\"hrd-link-btn\" href=\"${realHrdUrl}\" target=\"_blank\">\n          고용24 HRD-Net 수강 신청 ➔",
                    "<a class=\"hrd-link-btn\" href=\"${course.url || realHrdUrl}\" target=\"_blank\">\n          과정 페이지 열기 ➔")
    html = sub_once(html, "<span style=\"color: #059669;\">${course.cost_type || '전액 무료'}</span>",
                    "<span style=\"color: #059669;\">${course.domain_category || ''}</span>")
    html = sub_once(html, "<b>이 업무에 맞는 교육을 찾는 중입니다.</b>",
                    "<b>수집된 과정 중 이 업무와 직접 맞는 교육이 아직 없습니다.</b>")
    # 근거 없는 전후 비교 문구에 예시 표시
    html = sub_once(html, "❌ 국비 교육 수강 전 (Before) 애로사항", "(예시) 교육 전에 흔히 겪는 어려움")
    html = sub_once(html, "✅ 국비 교육 수강 후 (After) 수행 가능 행동 (Can-Do)", "(예시) 교육 후 목표로 삼을 수 있는 행동")
    html = sub_once(html, "<li>피벗/자동화 매크로로 대량 인사 데이터를 10분 내 100% 무결점 완결</li>",
                    "<li>피벗/자동화 매크로로 대량 인사 데이터를 빠르고 정확하게 정리</li>")
    html = sub_once(
        html,
        "<div class=\"recommendation-head\"><h3>지금 추천하는 교육</h3>",
        "<p style=\"font-size:11.5px; color:#64748b; margin:10px 2px 0;\">" + COMMON_NOTICE + "</p>\n"
        "      <div class=\"recommendation-head\"><h3>지금 추천하는 교육</h3>",
    )
    # 수강료 필터: '0원' 글자 검색은 '47,520원' 같은 금액에도 걸리는 버그가 있어 정확히 무료만 고르게 수정.
    # 환급 필터는 사업주훈련 과정, K-Digital은 해당 과정이 없어 선택지에서 뺀다.
    html = sub_once(html,
                    "filtered = filtered.filter(c => (c.cost_type || '').includes('무료') || (c.cost_type || '').includes('0원'));",
                    "filtered = filtered.filter(c => (c.cost_type || '').startsWith('무료'));")
    html = sub_once(html,
                    "filtered = filtered.filter(c => (c.cost_type || '').includes('환급'));",
                    "filtered = filtered.filter(c => (c.cost_type || '').includes('사업주훈련'));")
    html = sub_once(html, "<option value=\"FREE\">0원 전액무료 (내일배움)</option>", "<option value=\"FREE\">무료(0원) 과정</option>")
    html = sub_once(html, "<option value=\"REFUND\">사업주 환급 훈련</option>", "<option value=\"REFUND\">사업주훈련(사업주 부담 후 환급)</option>")
    html = html.replace("        <option value=\"KDIGITAL\">K-Digital</option>\n", "")
    # 과정 수 표시를 실제 개수로, 직급별 과제·결과물은 예시로 표시
    n = len(courses)
    html = re.sub(r">\d+개 과정 보기</div>", f">{n}개 과정 보기</div>", html)
    html = re.sub(r"<h2>📚 \d+개 지원 교육 과정 추천</h2>", f"<h2>📚 수집된 교육 과정 {n}개</h2>", html)
    html = sub_once(html, "<small>다음에 해볼 일</small>", "<small>다음에 해볼 일 (예시)</small>")
    html = sub_once(html, "<small>완성하면 남는 결과물</small>", "<small>완성하면 남는 결과물 (예시)</small>")
    EASY_HTML.write_text(add_legacy_banner(html), encoding="utf-8")
    return by_dom


def main():
    courses = load_courses()
    build_v2(courses)
    by_dom = build_easy(courses)
    print(f"[완료] 과정 {len(courses)}개(과정명 기준 묶음)로 두 화면 데이터 갱신")
    print(pd.Series({c: sum(x['cat'] == c for x in courses) for c in CATS}).to_string())
    print("분야별 연결 과정 수:", {d: len(v) for d, v in by_dom.items()})


if __name__ == "__main__":
    main()
