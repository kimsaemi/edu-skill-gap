"""
NCS 인사·총무 교육 텍스트 전처리기 모듈
- Kiwi 형태소 분석기 기반 한국어 토큰화
- 인사·총무 도메인 전문 용어 사전 탑재 및 보존
- 특수문자/HTML 정제 및 실무형 불용어 필터링
"""
import re
from typing import List, Dict
from kiwipiepy import Kiwi

class HRTextPreprocessor:
    def __init__(self):
        self.kiwi = Kiwi()
        self._register_user_words()
        self.stopwords = {
            '교육', '과정', '강의', '학습', '수강', '방법', '이해', '기초', '입문', '기본',
            '안내', '소개', '개요', '위한', '통한', '대해', '관한', '에서', '으로', '부터',
            '까지', '있다', '하다', '되다', '이다', '대해', '관련', '모든', '것', '수',
            '등', '및', '의', '을', '를', '에', '와', '과', '로', '은', '는', '이', '가',
            '함께', '통해', '배우는', '알아보는', '따라하는', '완성하는', '알기'
        }

    def _register_user_words(self):
        """인사·총무 도메인 핵심 전문 용어 사용자 사전에 등록"""
        hr_terms = [
            ('근로기준법', 'NNP'), ('근로계약서', 'NNG'), ('자산관리', 'NNG'), ('비품관리', 'NNG'),
            ('취업규칙', 'NNG'), ('연말정산', 'NNG'), ('4대보험', 'NNG'), ('채용관리', 'NNG'),
            ('직무분석', 'NNG'), ('노사관계', 'NNG'), ('인사평가', 'NNG'), ('복리후생', 'NNG'),
            ('퇴직금', 'NNG'), ('통상임금', 'NNG'), ('평균임금', 'NNG'), ('성과관리', 'NNG'),
            ('조직문화', 'NNG'), ('피플애널리틱스', 'NNG'), ('온보딩', 'NNG'), ('인적자원', 'NNG'),
            ('인력운영', 'NNG'), ('급여계산', 'NNG'), ('임금체계', 'NNG'), ('고용보험', 'NNG'),
            ('국민연금', 'NNG'), ('건강보험', 'NNG'), ('산재보험', 'NNG'), ('주휴수당', 'NNG'),
            ('해고예고', 'NNG'), ('부당해고', 'NNG'), ('총무기획', 'NNG'), ('사무행정', 'NNG'),
            ('문서관리', 'NNG'), ('계약관리', 'NNG'), ('비즈니스매너', 'NNG'), ('보고서작성', 'NNG')
        ]
        for word, tag in hr_terms:
            try:
                self.kiwi.add_user_word(word, tag)
            except Exception:
                pass

    def clean_text(self, text: str) -> str:
        """HTML 태그, 이메일, URL, 특수기호 제거 및 공백 정규화"""
        if not text or not isinstance(text, str):
            return ""
        # 1. HTML 태그 제거
        text = re.sub(r'<[^>]+>', ' ', text)
        # 2. URL 및 이메일 제거
        text = re.sub(r'http\S+|www\.\S+|\S+@\S+', ' ', text)
        # 3. 특수문자 제거 (한글, 영문, 숫자, 공백 보존)
        text = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text)
        # 4. 다중 공백 정규화
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def tokenize(self, text: str, pos_filter=('NNG', 'NNP', 'SL')) -> List[str]:
        """한국어 형태소 분석 및 의미 있는 품사 토큰 추출"""
        cleaned = self.clean_text(text)
        if not cleaned:
            return []
        
        tokens = []
        try:
            res = self.kiwi.tokenize(cleaned)
            for token in res:
                # 지정된 품사(일반명사, 고유명사, 외래어 등) 필터링
                if token.tag in pos_filter:
                    word = token.form.lower()
                    if len(word) >= 2 and word not in self.stopwords:
                        tokens.append(word)
        except Exception:
            # Kiwi 예외 시 공백 분리 폴백
            tokens = [w.lower() for w in cleaned.split() if len(w) >= 2 and w not in self.stopwords]
            
        return tokens

    def extract_top_keywords(self, tokens: List[str], top_n: int = 8) -> List[str]:
        """토큰 리스트에서 빈도 기반 상위 키워드 추출"""
        if not tokens:
            return []
        from collections import Counter
        counts = Counter(tokens)
        return [word for word, _ in counts.most_common(top_n)]
