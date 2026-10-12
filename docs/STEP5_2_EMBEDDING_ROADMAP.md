# [기획서] STEP 5-2: 로컬 한국어 임베딩 모델 비교 및 시맨틱 검색 도입 계획서

> **문서 버전**: v1.0  
> **작성 일시**: 2026-10-12  
> **상위 프로젝트**: NCS 기반 부서·부서원 맞춤형 교육 추천 시스템 (`kimsaemi/edu-skill-gap`)  
> **대상 코퍼스**: 통합 교육과정 8,645건 (`education_courses_integrated.parquet`)  
> **주의 사항**: 본 단계에서는 모델을 다운로드하거나 전체 임베딩을 생성하지 않으며, 사전 환경 및 기술 설계를 확정합니다.

---

## 1. 추진 배경 및 목표

STEP 5-1에서는 어휘 기반 검색 알고리즘인 **TF-IDF**(단어 빈도-역문서 빈도)와 **BM25**(단어 빈도 포화 및 문서 길이 정규화)를 적용하여 15대 실무 질의에 대한 검색 성능을 검증하고, 동일 과정 다회차 중복 제거(Deduplication on Display) 및 4인 블라인드 평가 체계를 구축했습니다.

그러나 어휘 기반 검색은 다음과 같은 본질적 한계를 지닙니다:
1. **어휘 불일치 문제 (Vocabulary Mismatch)**: '온보딩'을 검색했을 때 '신입사원 조기적응' 또는 'OJT 입문' 과정이 매칭되지 않음.
2. **동의어/문맥 파악 불가**: '취업규칙 작성' 검색 시 '인사규정 제개정 실무'의 의미적 관련성을 직접 포착하지 못함.

이에 STEP 5-2에서는 사전 학습된 한국어 언어 모델을 활용한 **밀집 벡터 임베딩(Dense Vector Embedding)** 기반 시맨틱 유사도 검색을 도입하고, 어휘 검색과의 하이브리드(Hybrid Search) 앙상블 체계를 준비합니다.

---

## 2. 비교 대상 2대 임베딩 모델

| 비교 항목 | 모델 1: `klue/bert-base` | 모델 2: 한국어 문장 유사도 특화 모델 (`jhgan/ko-sroberta-multitask`) |
| :--- | :--- | :--- |
| **모델 유형** | 범용 사전학습 언어 모델 (Pre-trained LM) | 문장 임베딩 특화 bi-encoder 모델 (Sentence Transformer) |
| **파라미터 수** | 약 110M (1억 1천만 파라미터) | 약 111M (RoBERTa-base 기반) |
| **학습 데이터** | 한국어 위키, 뉴스, 청와대 국민청원 등 대규모 원시 텍스트 | KLUE NLI + KorNLI (문장 추론) + KorSTS (문장 유사도) 파인튜닝 |
| **임베딩 생성 방식** | 마지막 은닉층의 토큰 벡터들을 **Mean Pooling** 또는 `[CLS]` 추출 | 문장 간 코사인 유사도를 직접 최적화하도록 학습된 **Mean Pooling** |
| **코사인 유사도 적합성** | 원래 문장 간 벡터 거리를 직접 학습한 것이 아니므로 비등방성(Anisotropy) 현상이 발생할 수 있음 | 코사인 유사도가 인간의 의미적 유사도 점수와 직접 일치하도록 훈련됨 |
| **예상 장점** | 한국어 문법·어휘에 대한 일반화 표현력 우수 | 검색/추천 성능(MRR, nDCG)에서 즉각적인 고품질 시맨틱 매칭 발휘 |

---

## 3. 로컬 실행 환경 및 하드웨어 요구사항

### 3.1 소프트웨어 의존성 (`requirements.txt`)
```text
torch>=2.1.0
transformers>=4.35.0
sentence-transformers>=2.2.2
faiss-cpu>=1.7.4
accelerate>=0.24.0
scikit-learn>=1.3.0
numpy>=1.24.0
pandas>=2.0.0
pyarrow>=14.0.0
```

### 3.2 하드웨어 자원 사양 및 추론 성능 비교

| 구분 | CPU 전용 환경 (최소 사양) | GPU 가속 환경 (권장 사양) |
| :--- | :--- | :--- |
| **하드웨어** | Intel Core i5/i7 (8코어 이상) / 16GB RAM | NVIDIA RTX 3060 / 4060 이상 (VRAM 8GB 이상) |
| **배치 크기 (Batch Size)** | `batch_size = 16` | `batch_size = 64` (FP16 Mixed Precision) |
| **8,645건 임베딩 소요 시간** | 약 **12분 ~ 18분** | 약 **1분 ~ 2분** |
| **실시간 질의 임베딩 속도** | 약 **15ms ~ 30ms** (충분히 대화형 지원 가능) | 약 **3ms ~ 8ms** |
| **메모리 점유율** | RAM 약 2.5GB | VRAM 약 1.8GB, 시스템 RAM 2.0GB |

> **실행 전략**: 로컬 환경에 GPU가 없는 팀원의 경우 CPU로도 8,645건의 1회 일괄 생성이 15분 내에 완료되므로, 사전 생성된 임베딩 파일(`.npy`)을 저장소나 아티팩트로 공유하여 재활용합니다.

---

## 4. 긴 텍스트(Long Text) 처리 및 토큰 절단 전략

BERT 계열 모델은 최대 입력 길이가 **512 토큰**으로 제한되어 있습니다. 교육 데이터의 70%가 500자 이상이며, 일부 강좌는 상세 목차가 길기 때문에 무작정 앞부분만 자르면 핵심 커리큘럼이 유실될 위험이 있습니다.

### 4.1 데이터 정제 및 이상값 차단 (선결 조건)
- STEP 5-1에서 발견된 29건의 **Base64 이미지 문자열**(`base64,iVBOR...`) 및 반복 마케팅 공지문("중소기업이신가요?")을 정규식으로 사전 제거합니다.

### 4.2 계층적 정보 가중 합성 (Structured Text Synthesis)
512 토큰 내에 가장 중요한 정보를 압축 배치하기 위해 다음과 같이 텍스트를 구성합니다:

$$\text{Input Text} = [\text{과정명}] \times 2 \ + \ [\text{학습목표 핵심 150자}] \ + \ [\text{교육소개 150자}] \ + \ [\text{커리큘럼 핵심 모듈 목차 200자}]$$

```python
def compose_course_semantic_text(row):
    title = str(row["title"] or "").strip()
    intro = clean_text(str(row["course_intro"] or ""))[:150]
    goals = clean_text(str(row["learning_goals"] or ""))[:150]
    curric = clean_text(str(row["curriculum"] or ""))[:200]
    
    # 과정명에 2배 가중치를 주기 위해 앞단에 강조 배치
    return f"과정명: {title}. 핵심 목표: {goals}. 교육 내용: {intro}. 주요 목차: {curric}"
```

### 4.3 초장문 분할 및 풀링 (Chunking & Mean Pooling)
커리큘럼이 30개 모듈 이상으로 구성된 초장문 강좌(전체의 약 3.5%)의 경우:
1. 문서를 300 토큰 단위 청크(Chunk)로 분할 (모듈 1~3, 모듈 4~6 등).
2. 각 청크별 768차원 임베딩을 계산.
3. 문서 전체 임베딩은 청크 벡터들의 평균(Average Pooling) 또는 최대값(Max Pooling)으로 집계합니다.

---

## 5. 임베딩 벡터 저장 방식

8,645개 교육과정의 768차원 `float32` 임베딩 행렬 크기는 다음과 같습니다:

$$8,645 \times 768 \times 4 \text{ bytes} \approx 26,557,440 \text{ bytes} \approx \mathbf{25.33 \text{ MB}}$$

### 5.1 저장 포맷 비교
1. **Numpy Memory-Mapped Binary (`.npy`) [권장]**:
   - 경로: `data/hr/output/recommendation/course_embeddings_ko_sroberta.npy`
   - 장점: 25.3MB로 매우 가볍고, `np.load(..., mmap_mode='r')`로 디스크에서 수 밀리초 만에 메모리 매핑 로드 가능.
   - 메타데이터 매핑: `course_embeddings_metadata.parquet`에 행 인덱스(`int32`)와 `course_uid`를 1:1 보존.
2. **FAISS 인덱스 바이너리 (`.index`)**:
   - 경로: `data/hr/output/recommendation/course_index_faiss.index`
   - L2 정규화가 완료된 Inner Product 인덱스를 파일로 직접 저장.

---

## 6. 코사인 유사도 검색 및 인덱싱 방법

임베딩 벡터를 미리 단위 길이(Unit Norm, L2 정규화)로 만들어 두면, **내적(Inner Product) 연산이 곧 코사인 유사도**가 됩니다:

$$\text{Cosine Similarity}(q, d) = \frac{q \cdot d}{\|q\| \|d\|} = \hat{q} \cdot \hat{d}$$

### 6.1 FAISS 기반 실시간 검색 구현 설계
```python
import faiss
import numpy as np

# 1. 8,645건 사전 임베딩 행렬 L2 정규화
embeddings = np.load("data/hr/output/recommendation/course_embeddings_ko_sroberta.npy")
faiss.normalize_L2(embeddings)

# 2. FAISS IndexFlatIP (내적 = 코사인 유사도) 구축
dimension = 768
index = faiss.IndexFlatIP(dimension)
index.add(embeddings) # 8,645건 인덱싱 완료 (1ms 미만)

# 3. 실시간 질의 검색
def search_semantic(query_text, top_k=10):
    q_vec = model.encode([query_text]) # 1 x 768
    faiss.normalize_L2(q_vec)
    scores, indices = index.search(q_vec, top_k)
    return scores[0], indices[0]
```

---

## 7. TF-IDF·BM25와의 공정한 비교 검증 체계

임베딩 모델 도입의 효과를 객관적으로 입증하기 위해, **동일한 질의 및 평가 프로토콜**을 100% 동일하게 적용합니다:

1. **동일 15대 실무 질의 적용**:
   - 인사(Q01~Q05), 총무(Q06~Q10), 경영지원(Q11~Q15) 15개 질문 그대로 입력.
2. **동일 다회차 중복 제거(Deduplication on Display) 규칙 적용**:
   - 동일 기관 내 동일 강좌의 다회차 개설건은 대표 1건만 노출하고 유니크 과정 10건 선발.
3. **통합 4-Way 블라인드 평가**:
   - TF-IDF, BM25, `klue/bert-base`, `ko-sroberta` 4개 알고리즘의 결과를 합쳐 블라인드 후보로 출제.
4. **객관적 정량 지표 4대 축 비교**:
   - **Precision@5 (관련성 1점 이상 비율)**
   - **Precision@5 Strict (직접 관련 2점 비율)**
   - **nDCG@10 (상위 랭킹 정확도 반영 지표)**
   - **Top 5 내 관련 없는 과정(0점) 비율 (False Positive 저감율)**

---

## 8. STEP 5-2 실행 체크리스트

- [ ] STEP 5-1 팀원 4인 실제 평가 완료 및 점수 집계 확인
- [ ] Base64 및 마케팅 노이즈 제거된 텍스트 전처리 모듈 확장
- [ ] `klue/bert-base` vs `jhgan/ko-sroberta-multitask` 샘플 추론 테스트 (50건 파일럿)
- [ ] 8,645건 전체 임베딩 일괄 생성 및 `.npy` 저장
- [ ] FAISS 인덱스 구축 및 15개 질의 검색 결과 도출
- [ ] TF-IDF/BM25와 임베딩 간 하이브리드 RRF(Reciprocal Rank Fusion) 앙상블 모듈 개발
