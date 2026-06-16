# Architectural & Product Decisions

이 문서는 프로젝트의 주요 설계 및 제품 결정을 기록합니다.

## 1. 아키텍처 결정 (Architectural Decisions)

### 1.1. Serverless & Database-less (GSheets)
- **결정:** 별도의 RDBMS 없이 Google Sheets를 메인 데이터베이스로 사용.
- **이유:** 서버 유지 비용을 0으로 유지하고, 비개발자(관리자)도 데이터를 쉽게 확인하고 수정할 수 있도록 함.
- **추론(Inferred):** 초기 MVP 단계에서 빠른 데이터 조작과 비용 절감을 우선순위로 둠.

### 1.2. 하이브리드 캐싱 전략 (Hybrid Caching)
- **결정:** Google Sheets 연동의 느린 속도를 보완하기 위해 로컬 JSON 저장소와 `@st.cache_data`를 병행 사용.
- **이유:** Streamlit Cloud 환경에서 API 호출 횟수를 줄이고 응답 속도를 극대화하기 위함.

### 1.3. UI 고도화와 Streamlit 제한 우회
- **결정:** Streamlit의 기본 UI를 대폭 수정하기 위해 `utils.py` 내 `load_custom_css` 및 HTML 인젝션을 사용.
- **이유:** 일반적인 Streamlit 앱처럼 보이지 않게 하여 프리미엄 웹 서비스 느낌을 주기 위함 (Glassmorphism, Royal Gold 테마 적용).

### 1.4. AI 모델 선정 (Gemini 1.5 Flash)
- **결정:** 뉴스 요약 및 리뷰 분석에 Gemini 1.5 Flash 모델 사용.
- **이유:** 대량의 컨텍스트를 저렴하고 빠르게 처리하기에 최적화된 선택.

### 1.5. WordPress와 Streamlit 간의 로직 동기화 (Logic Synchronization)
- **결정:** 워드프레스 플러그인 또는 API 개발 시 랭킹 산정, 점수 계산 등의 핵심 로직은 반드시 Streamlit(`utils.py` 등)에 구현된 공식(Formula)과 100% 동일하게 구현한다.
- **이유:** 플랫폼 간 데이터 불일치(예: 실시간 인기 TOP 5 랭킹 차이)를 방지하고 사용자에게 일관된 기준의 랭킹을 제공하기 위함.

## 2. 제품 결정 (Product Decisions)

### 2.1. 다국어 지원 방식
- **결정:** 사용자의 브라우저 Accept-Language 헤더를 탐지하여 한국어/영어 자동 전환.
- **이유:** Travelpayouts 리뷰어 및 글로벌 사용자 대응 목적.

### 2.2. 수익화 지점 (Affiliate-First)
- **결정:** 별도의 유료 결제 기능을 구현하는 대신 Klook, Agoda 등 제휴사 예약 링크를 서비스 곳곳에 자연스럽게 배치.
- **이유:** 결제 시스템 유지 관리 부담을 줄이면서 수익을 창출하기 위함.

### 2.3. SEO 및 분석 도구 강제 주입
- **결정:** Streamlit이 공식적으로 지원하지 않는 Head 영역에 GA4 및 메타 태그를 JavaScript를 통해 강제 삽입.
- **이유:** 마케팅 성과 추적 및 검색 엔진 노출이 프로젝트 성장에 필수적임.

---
*Last Updated: 2026-03-16*
