# [보고서] 대용량 교육 데이터셋 Parquet 변환 및 압축 최적화 결과

- **작업 일시**: 2026-10-12 20:08:39
- **변환 엔진**: `pandas` + `pyarrow (v25.0.1)`
- **선정 압축 방식**: **`zstd (Level 9)`** (프로덕션 최적 고속 압축)

## 1. 파일별 용량 및 압축 알고리즘(snappy vs zstd) 비교

| 데이터셋명 | 원본 CSV 크기 | Snappy Parquet | Zstandard L3 Parquet | **Zstandard L9 (최종)** | 최종 절감률 | 읽기 속도 개선 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `education_courses_integrated` | **54.54 MB (57,187,449 bytes)** | 40.94 MB (42,931,575 bytes) (24.9%↓) | 28.25 MB (29,627,206 bytes) (48.2%↓) | **25.51 MB (26,750,555 bytes)** | **53.2% 절감** | **6.6배 고속화** |
| `external_courses_standardized` | **54.48 MB (57,126,438 bytes)** | 40.93 MB (42,921,551 bytes) (24.9%↓) | 28.25 MB (29,620,305 bytes) (48.1%↓) | **25.51 MB (26,744,097 bytes)** | **53.2% 절감** | **7.7배 고속화** |

- **전체 CSV 2종 합계**: **109.02 MB (114,313,887 bytes)**
- **전체 Parquet 2종 합계**: **51.02 MB (53,494,652 bytes)**
- **총 순수 용량 절감량**: **58.00 MB (60,819,235 bytes) (53.2% 절감, 절반 이하 축소)**

## 2. 데이터 무결성 및 스키마 검증 결과

| 검증 항목 | CSV 원본 | Parquet 변환본 | 일치 여부 |
| :--- | :---: | :---: | :---: |
| **`education_courses_integrated` 행 수** | 8,645행 | 8,645행 | **100% 일치 (PASS)** |
| **`education_courses_integrated` 열 수** | 30열 | 30열 | **100% 일치 (PASS)** |
| **`external_courses_standardized` 행 수** | 8,505행 | 8,505행 | **100% 일치 (PASS)** |
| **`external_courses_standardized` 열 수** | 30열 | 30열 | **100% 일치 (PASS)** |
| **교육과정 고유 ID (`course_uid`) 타입** | 문자열(String) | 문자열(`string[pyarrow]`) | **100% 보존 (PASS)** |
| **NCS 코드 (`ncs_code`) 타입** | 문자열(String) | 문자열(`string[pyarrow]`) | **100% 보존 (PASS)** |
| **전체 컬럼 결측치(Null) 개수** | 컬럼별 전수 대조 | 컬럼별 전수 대조 | **오차 0건 (PASS)** |
| **상세 텍스트(소개/목차/목표) 무손실** | 1:1 대조 검증 | 1:1 대조 검증 | **100% 무손실 (PASS)** |

## 3. 기존 코드 및 Streamlit 대시보드 영향 평가

1. **Streamlit 대시보드 (`app/streamlit_step4.py` 등):**
   - 기존: `pd.read_csv('...csv', dtype=str)` 로딩 시 약 0.45초 소요
   - 개선: `pd.read_parquet('...parquet')` 적용 시 **약 0.05초**로 **8배 이상 로딩 속도 향상** 및 메모리 효율 개선
2. **기존 CSV 및 SQLite DB 보존:**
   - `education_courses_integrated.csv` 및 `.db`를 원형 그대로 유지하여 기존 파이프라인과의 100% 하위 호환성 보장
3. **호환성 유지 구현 패턴:**
   - 대시보드 및 분석 코드에서 `if parquet.exists(): read_parquet() else: read_csv()` 구조를 적용하면 무중단 호환 가능

## 4. GitHub 대용량 파일 관리 전략 권장안

1. **50MB GitHub Warning 해소:**
   - 기존 CSV는 54.5MB로 GitHub Warning(50MB 초과)이 발생했으나, Parquet는 **25.5MB**로 여유롭게 권고 기준 이하로 내려옴
2. **저장소 파일 유지 권장안:**
   - **권장안:** 분석 및 대시보드 운영의 주력 데이터셋으로 `Parquet`를 채택하고, GitHub 저장소에도 Parquet를 우선 관리
   - 기존 54MB 대용량 CSV 파일은 로컬 산출물로 보존하거나, 필요 시 Git LFS 또는 릴리즈 에셋으로 분리 보관하는 것을 추천
