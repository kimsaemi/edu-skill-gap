"""
강좌별 '분야' 라벨을 만듭니다 (업무별 추천에서 분야 밖 강좌를 걸러내는 데 사용).

방법: 분야별 대표 설명 문장 10개를 Ko-SRoBERTa로 임베딩하고, 각 강좌 임베딩과 가장 가까운 분야를 고릅니다
      (학습 데이터 없이 쓰는 프로토타입 분류). 1·2위 차이(margin)가 작으면 판정이 애매하다는 뜻입니다.
입력: embeddings_ko_sroberta_all.npy (임베딩을 다시 만들면 이 스크립트도 다시 실행하세요)
출력: data/hr/output/recommendation/course_field_labels.csv (course_uid, title, field, field_margin)

실행: python scripts/build_course_field_labels.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "hr" / "processed" / "education_courses_search_cleaned.parquet"
EMB = ROOT / "data" / "hr" / "output" / "recommendation" / "embeddings_ko_sroberta_all.npy"
OUT = ROOT / "data" / "hr" / "output" / "recommendation" / "course_field_labels.csv"

FIELD_PROTOTYPES = {
    "HR": "인사관리 채용 면접 온보딩 인사평가 성과관리 보상 급여 임금 노무관리 근로기준법 노사관계 인재육성 사내교육 HRD 조직문화 직무분석 교육과정",
    "GA": "총무 사무행정 비품 자산관리 문서작성 보고서 기획서 비서 의전 비즈니스 매너 커뮤니케이션 리더십 팀장 조직관리 프로젝트 관리",
    "FIN": "회계 재무 세무 예산 원가 결산 재무제표 경영전략 사업계획",
    "DATA_AI": "데이터 분석 엑셀 통계 시각화 생성형 AI 챗GPT 업무 자동화 디지털 전환",
    "IT_DEV": "프로그래밍 소프트웨어 개발자 코딩 자바스크립트 파이썬 웹개발 앱개발 서버 데이터베이스 LLM 에이전트 개발 클라우드 인프라",
    "MKT": "마케팅 광고 브랜드 SNS 콘텐츠 마케터 퍼포먼스 마케팅 이커머스 판매 상품 입점 고객 유치",
    "MED": "의료 병원 간호 환자 보건 요양 의료기관 인증",
    "LEGAL_IP": "특허 상표 지식재산권 출원 명세서 변리",
    "PROD": "생산 제조 품질관리 공정 설비 TPM 물류 구매 조달 공급망",
    "LANG": "영어 회화 외국어 토익 OPIc 일본어 중국어 비즈니스 영어",
}


def main() -> int:
    from sentence_transformers import SentenceTransformer

    df = pd.read_parquet(CORPUS, columns=["course_uid", "title"])
    emb = np.load(EMB)
    if len(emb) != len(df):
        print("[FAIL] 임베딩과 코퍼스 행 수가 다릅니다.")
        return 1
    model = SentenceTransformer("jhgan/ko-sroberta-multitask", device="cpu")
    names = list(FIELD_PROTOTYPES)
    proto = model.encode([FIELD_PROTOTYPES[k] for k in names], normalize_embeddings=True)
    sims = emb @ proto.T
    order = np.sort(sims, axis=1)
    df["field"] = np.array(names)[sims.argmax(axis=1)]
    df["field_margin"] = np.round(order[:, -1] - order[:, -2], 4)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"저장: {OUT}")
    print(df["field"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
