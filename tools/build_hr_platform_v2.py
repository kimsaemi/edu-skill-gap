"""원본 HR 커리어 플랫폼 HTML에서 데이터를 꺼내 정리하고, v2 템플릿에 끼워 넣어 단일 HTML을 만든다.

사용법: python tools/build_hr_platform_v2.py [원본.html] [출력.html]
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "hr_enterprise_career_platform_easy.html"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "hr_career_platform_v2.html"
TEMPLATE = ROOT / "tools" / "hr_platform_v2_template.html"

GRADE_SHORT = ["주임", "대리", "과장", "차장", "부장"]
LEVEL_KEYS = ["Level 1 (보조)", "Level 2 (단독)", "Level 3 (개선)", "Level 4 (전략)"]

DOMAIN_INFO = {
    "DOM_01": ("인사전략·인력기획", "필요한 인원을 계산하고 계획해요", "인력 계획"),
    "DOM_02": ("조직설계·직무분석", "조직 구조와 직무를 정리해요", "직무분석"),
    "DOM_03": ("인재채용", "사람을 뽑고 평가해요", "채용 면접"),
    "DOM_04": ("온보딩·직원경험", "새 직원이 잘 적응하게 도와요", "신입사원 온보딩"),
    "DOM_05": ("성과평가·목표관리", "성과를 평가하고 목표를 관리해요", "성과관리"),
    "DOM_06": ("보상·급여·복리후생", "급여와 보상, 복리후생을 다뤄요", "인사 급여"),
    "DOM_07": ("인재육성·사내교육", "교육을 기획하고 운영해요", "인적자원개발"),
    "DOM_08": ("조직문화·사내소통", "조직문화를 만들고 소통해요", "조직문화"),
    "DOM_09": ("노사관계·노무", "노사관계와 노동법 대응을 해요", "인사노무"),
}

# 분야별로 함께 들으면 좋은 공통 역량 분류 (앞에 있을수록 우선)
RELATED = {
    "DOM_01": ["DATA", "OFFICE"],
    "DOM_02": ["COMM", "OFFICE"],
    "DOM_03": ["COMM", "LEAD"],
    "DOM_04": ["COMM", "OFFICE"],
    "DOM_05": ["DATA", "LEAD"],
    "DOM_06": ["ACCT", "OFFICE"],
    "DOM_07": ["LEAD", "COMM"],
    "DOM_08": ["COMM", "LEAD"],
    "DOM_09": ["COMM", "LEAD"],
}

CATS = {
    "HR": "인사 직접 관련",
    "OFFICE": "엑셀·문서·사무",
    "DATA": "AI·데이터",
    "ACCT": "회계·재무",
    "COMM": "소통·보고",
    "LEAD": "리더십·직장 기본기",
    "OTHER": "인사와 무관(기타)",
}
CAT_WHY = {
    "OFFICE": "자료 정리와 보고서 작성에 두루 쓰는 사무 도구",
    "DATA": "숫자와 데이터로 근거를 만드는 역량",
    "ACCT": "인건비·급여 같은 숫자를 다루는 기초",
    "COMM": "구성원과 설득하고 소통하는 역량",
    "LEAD": "일하는 방식과 사람 관리의 기본기",
}

# 인사 업무와 직접 관련된 과정: (제목 정규식, 연결 분야)
HR_RULES = [
    (r"인사노무|노무|준법", ["DOM_09"]),
    (r"인사급여|급여계산|4대보험", ["DOM_06"]),
    (r"면접|인재 확보|채용", ["DOM_03"]),
    (r"온보딩|신입사원", ["DOM_04"]),
    (r"HR전문가", ["DOM_02", "DOM_05", "DOM_06"]),
    (r"인사관리 실무", ["DOM_01", "DOM_02"]),
    (r"인사와 HRD", ["DOM_07", "DOM_01"]),
    (r"인적자원관리", ["DOM_01", "DOM_07"]),
    (r"조직문화|공유리더십|팀워크|팀 빌딩|팀원", ["DOM_08"]),
]

# 순서대로 처음 맞는 분류를 쓴다
CAT_RULES = [
    ("OTHER", r"마케팅|마케터|광고|SNS|브랜드|브랜딩|카피|물류|무역|통관|유통|생산|품질|TPM|구매|영업|(?<![A-Za-z])CS(?![A-Za-z])|고객|VOC|영어|캠브리지|간호|의사들|의료|자동차|ISO|Linux|리눅스|Spring|GitOps|Jenkins|Valkey|바이브|정보처리|SQLP|CPPG|임베딩|LLM|주식|사주|트렌드|소비|경제|인도|메타버스|ESG|RE100|미드저니|AI 디자인|삼국지|조선왕조|독서경영|인문학|비즈니스 모델|미래비즈니스|마켓|글로벌|Claude Code|Hermes|단테랩스|AntiGravity|빅데이터 분석기사|엔지니어|신규 사업|시장을|제품\(생산\)|창의|두뇌"),
    ("ACCT", r"전산세무|전산회계|세무|회계|재무|원가|예산|결산|경리|ERP|IFRS|부가가치세"),
    ("DATA", r"데이터|AI|챗GPT|Chat GPT|GPT|자동화|분석적|시각화"),
    ("COMM", r"커뮤니케이션|소통|보고|스피치|글쓰기|경청|설득|문해력|프레젠테이션|PT|대화|협상|언어술사|기획력|문서작성|문서 스킬|비즈니스 매너|공감|메신저|말은"),
    ("OFFICE", r"엑셀|Excel|파워포인트|워드|ITQ|컴활|컴퓨터활용|컴퓨터기초|OA|오피스|Office|사무|총무|스프레드시트|PPT|노션|앱시트|입찰|IT기기|행사|경영기초"),
    ("LEAD", r"리더십|리더|셀프|팔로워|중간관리자|핵심실무자|코칭|직장생활|일잘러|일 잘하는|업무력|관계|동기부여|의사결정|문제해결|목표관리|시간관리|핵심역량|멘토링|Followership|비즈니스 역량|꼰대|일취월장|직무 효율성|직무 향상|경영지원"),
]

BEGINNER = r"기초|입문|초보|왕초보|첫걸음|ITQ|2급|Basic|신입|컴퓨터기초"
SENIOR = r"중간관리자|리더십|MBA|전략|협상|꼰대|핵심리더|코칭|관리자|감성 커뮤니케이션|리더의"
JUNIOR_LEAD = r"셀프|팔로워|핵심실무자"

SIMPLE = [
    (r"도메인", "분야"), (r"매트릭스", "한눈에 보기"), (r"전사", "회사 전체"), (r"현업", "실제 업무"),
    (r"컴플라이언스", "법규 준수"), (r"거버넌스", "운영 체계"), (r"프로세스", "절차"),
    (r"퍼실리테이션", "회의 진행"), (r"얼라인먼트", "의견 맞추기"), (r"마일스톤", "목표"),
    (r"인사이트", "의미 있는 결과"), (r"C-Level", "임원진"),
]


def simple(text):
    if not isinstance(text, str):
        return text
    for pat, rep in SIMPLE:
        text = re.sub(pat, rep, text)
    return text


def load_master():
    html = SRC.read_text(encoding="utf-8")
    m = re.search(r"(?:const|var|let)\s+MASTER_DATA\s*=\s*", html)
    data, _ = json.JSONDecoder().raw_decode(html[m.end():])
    return data


def base_title(title):
    t = re.sub(r"\s*\((?:[^()]*|\([^()]*\)[^()]*)회차\)\s*$", "", title)
    t = re.sub(r"\s*\(\(1st\)[^)]*$", "", t)
    return t.strip()


def classify(title):
    doms = []
    for pat, ds in HR_RULES:
        if re.search(pat, title):
            doms.extend(d for d in ds if d not in doms)
    if doms:
        return "HR", doms
    for cat, pat in CAT_RULES:
        if re.search(pat, title):
            return cat, []
    return "OTHER", []


def grade_fit(title, cat):
    if re.search(r"온보딩|신입사원", title):
        return [0, 1]
    if re.search(r"면접관", title):
        return [1, 2, 3, 4]
    if re.search(r"MBA|전략적 준법", title):
        return [3, 4]
    if re.search(JUNIOR_LEAD, title) or re.search(BEGINNER, title):
        return [0, 1]
    if re.search(SENIOR, title):
        return [2, 3, 4]
    return [0, 1, 2, 3, 4]


def build_courses(raw):
    seen, out = set(), []
    for c in raw:
        title = base_title(c["course_title"])
        if title in seen:
            continue
        seen.add(title)
        url = c.get("url", "")
        if not url.startswith("https://"):
            continue
        cat, doms = classify(title)
        plat = c["platform"]
        platform = "사업주훈련" if "사업주" in plat else "인프런" if "인프런" in plat else "국민내일배움카드"
        out.append({
            "id": c["id"],
            "t": title,
            "inst": c.get("institution", ""),
            "plat": platform,
            "url": url,
            "cat": cat,
            "doms": doms,
            "grades": grade_fit(title, cat),
        })
    return out


def build_domains(master):
    out = []
    for dom in master["matrix_system"]["domains"]:
        short, brief, search = DOMAIN_INFO[dom["id"]]
        task = dom["tasks"][0]
        roles = []
        for col in master["matrix_system"]["metadata"]["columns"]:
            cell = task["grades_cell"].get(col, {})
            roles.append({
                "badge": re.sub(r"^[^\w가-힣]+", "", cell.get("role_badge", "")).strip(),
                "role": simple(cell.get("role", "")),
            })
        ksa = task.get("ksa", {})
        out.append({
            "id": dom["id"],
            "short": short,
            "brief": brief,
            "search": search,
            "full": dom["name"],
            "task": {
                "name": simple(task["task_name"]),
                "easy": simple(task.get("easy_desc", "")),
                "k": simple(ksa.get("knowledge", "")),
                "s": simple(ksa.get("skill", "")),
                "a": simple(ksa.get("attitude", "")),
                "levels": [simple(task["can_do_levels"].get(k, "")) for k in LEVEL_KEYS],
                "roles": roles,
            },
        })
    return out


def build_grades(master):
    out = []
    for i, step in enumerate(master["matrix_system"]["linear_career_pathway"]):
        years = re.search(r"\((.+?)\)", step["grade_name"])
        out.append({
            "name": GRADE_SHORT[i],
            "years": years.group(1) if years else "",
            "mission": simple(step["core_mission"]),
            "summary": simple(step["key_role_summary"]),
            "gate": simple(re.sub(r"^[^\[\w가-힣]*\[[^\]]*\]\s*", "", step["gate_project"])),
            "milestone": simple(step["can_do_milestone"]),
            "cert": step["recommended_cert"],
            "capstone": simple(step["capstone_deliverable"]),
            "advice": simple(step["senior_advice"]),
        })
    return out


def main():
    master = load_master()
    courses = build_courses(master["course_catalog"])
    data = {
        "grades": build_grades(master),
        "domains": build_domains(master),
        "courses": courses,
        "cats": CATS,
        "catWhy": CAT_WHY,
        "related": RELATED,
        "rawCourseCount": len(master["course_catalog"]),
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)
    OUT.write_text(html, encoding="utf-8")

    count = collections.Counter(c["cat"] for c in courses)
    print(f"출력: {OUT} ({OUT.stat().st_size / 1024:.0f}KB)")
    print(f"과정: 원본 {len(master['course_catalog'])} → 중복 제거 {len(courses)}")
    print({CATS[k]: v for k, v in count.items()})
    for d in data["domains"]:
        n = sum(1 for c in courses if d["id"] in c["doms"])
        print(f"{d['id']} {d['short']}: 직접 관련 {n}개")


if __name__ == "__main__":
    main()
