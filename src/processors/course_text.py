"""교육과정 텍스트 정제·형태소 분석 공통 모듈 (2·3단계 텍스트 분석에서 공유)

- 템플릿 커리큘럼 / 기관 홍보 상용구 / 회차 꼬리표 제거
- kiwipiepy 명사 추출 + 붙어 있던 명사 쌍 복합어 + 인사·총무 사용자 사전
"""

import re

import pandas as pd

TEMPLATE_MARKER = "핵심 프로세스 실습 // 실무 서식 작성"
BOILERPLATE_MIN_TITLES = 3

HR_USER_WORDS = [
    "통상임금", "4대보험", "연말정산", "원천징수", "근로기준법", "주52시간", "퇴직급여", "퇴직연금",
    "인적자원관리", "인사노무", "다면평가", "성과관리", "역량면접", "온보딩", "컴활", "컴퓨터활용능력",
    "전산회계", "전산세무", "부가가치세", "재무제표", "고정자산", "비품관리", "공문서", "개인정보",
]

NOUN_TAGS = {"NNG", "NNP"}

STOPWORDS = set(
    """강의 강좌 과정 교육 훈련 실무 이해 학습 수강 수강생 기초 기본 활용 방법 내용 관련 필요 능력 역량
    업무 직무 직장인 실습 프로세스 목표 기대 효과 학습자 대상 분야 기술 지식 향상 습득 수행 제공 사례 실제
    중심 기반 대비 올인원 왕초보 초보 입문 마스터 정복 완전정복 노하우 개념 흐름 제고 기능 사용 시간 변화
    스킬 수립 시대 훈련생 프로그램 단계 설명 중요 중요성 포인트 강사 장비 배정 지정 실전 예제 상황 직장
    이론 방안 부분 다양 가능 이상 이후 핵심 완벽 최신 온라인 진행 운영 하나 가지 처음 누구 이제 지금
    모든 각종 전반 여러분 우리 자신 정도 경우 위주 구성 통해 위해 대한 수업 강화 체계 완성 노하우 비법 공략
    총시간 회차 인증 우수 기관 적용 파악 주요 정리 구체 의미 비교 문제 관리 plus up basic""".split()
)


def strip_session_suffix(title):
    """'강의명 (기관명 2회차)' 형태의 회차 꼬리표 제거"""
    return re.sub(r"\s*\([^()]*(\([^()]*\))?[^()]*\d+회차\)\s*$", "", str(title)).strip()


def split_segments(text):
    """소개글을 문장/항목 단위로 분리"""
    parts = re.split(r"\s*(?:■|※|▶|●|◆|•|\[|\]|\s-\s|\d+\.\s|[.!?]\s)\s*", str(text))
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def clean_syllabus(text, is_template):
    if is_template:
        return ""
    text = re.sub(r"총시간\s*\(\s*\d+\s*시간\s*\)", " ", str(text))
    return re.sub(r"\(\s*\d+\s*시간\s*\)", " ", text).strip()


def clean_courses(courses_raw: pd.DataFrame) -> pd.DataFrame:
    """정제 컬럼(base_title, overview_clean, syllabus_clean, doc)을 추가한 사본 반환"""
    courses = courses_raw.copy()
    courses["base_title"] = courses["course_title"].map(strip_session_suffix)
    courses["is_template_syllabus"] = courses["syllabus_text"].str.contains(TEMPLATE_MARKER, regex=False)

    # 서로 다른 강의 여러 개에 반복되는 문장 = 기관 홍보 상용구
    segment_titles = {}
    for title, overview in zip(courses["base_title"], courses["overview"]):
        for seg in set(split_segments(overview)):
            segment_titles.setdefault(seg, set()).add(title)
    boilerplate = {s for s, t in segment_titles.items() if len(t) >= BOILERPLATE_MIN_TITLES}

    courses["overview_clean"] = [
        " ".join(s for s in split_segments(ov) if s not in boilerplate) for ov in courses["overview"]
    ]
    courses["syllabus_clean"] = [
        clean_syllabus(t, f) for t, f in zip(courses["syllabus_text"], courses["is_template_syllabus"])
    ]
    # 키워드 분석용 문서: 제목(가중치 ×2) + 정제 소개글 + 실제 커리큘럼
    courses["doc"] = (
        (courses["base_title"] + " ") * 2 + courses["overview_clean"] + " " + courses["syllabus_clean"]
    )
    return courses


def build_kiwi():
    from kiwipiepy import Kiwi

    kiwi = Kiwi()
    for word in HR_USER_WORDS:
        kiwi.add_user_word(word, "NNP")
    return kiwi


def make_tokenizer(kiwi):
    """명사·영문 추출 + 띄어쓰기 없이 붙어 있던 명사 쌍을 복합어로 추가하는 토크나이저"""

    def tokenize(text):
        tokens = []
        prev = None
        for tok in kiwi.tokenize(str(text)):
            is_noun = tok.tag in NOUN_TAGS
            if is_noun or tok.tag == "SL":
                form = tok.form.lower()
                if len(form) >= 2 and form not in STOPWORDS:
                    tokens.append(form)
            if is_noun and prev is not None and prev.start + prev.len == tok.start:
                compound = prev.form + tok.form
                if compound not in STOPWORDS:
                    tokens.append(compound)
            prev = tok if is_noun else None
        return tokens

    return tokenize
