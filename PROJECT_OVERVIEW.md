# Project Overview: Thai Today (Project Antigravity)

## 1. 개요 (Summary)
**Thai Today (오늘의 태국)**는 태국 여행객을 위한 올인원 AI 여행 가이드 플랫폼입니다. 원래 'Project Antigravity'라는 이름의 AI 뉴스룸 서비스로 시작했으나, 현재는 호텔/맛집 팩트체크, AI 투어 코디네이터, 택시 요금 계산기 등을 포함한 종합 여행 포털로 확장되었습니다.

## 2. 제품 목적 및 타겟 사용자
- **목적:** 태국의 실시간 정보(뉴스, 환율, 날씨)와 신뢰할 수 있는 장소 검증(AI 팩트체크)을 제공하여 여행의 불편함을 해소하고 가이드 역할을 수행함.
- **타겟 사용자:** 태국을 방문하는 한국인 및 영어권 여행자.

## 3. 핵심 기능 (Main Features)
- **📰 뉴스 브리핑:** Gemini 1.5 Flash를 사용하여 현지 뉴스를 수집, 번역 및 요약.
- **🏨/🍜 팩트체크:** Google Maps 리뷰 데이터를 AI가 분석하여 광고성 후기를 제외한 '진짜' 장단점을 분석.
- **🎒 AI 투어 코디네이터:** 사용자의 성향과 예산에 맞춰 맞춤형 투어 일정 추천.
- **🚕 택시 요금 계산기:** 경로별 적정 요금을 계산하여 바가지를 예방.
- **🎪 이벤트/축제:** 실시간 현지 행사 정보 제공.
- **🗣️ 여행자 게시판:** 사용자 간 정보 공유 커뮤니티.

## 4. 기술 스택 (Stack)
- **Frontend/Backend:** Python + Streamlit
- **AI Engine:** Google Gemini API (`gemini-2.5-flash`)
- **Database:** Google Sheets (메인 DB), GitHub/Local JSON (캐시 및 로그 저장)
- **Monitoring:** Google Analytics 4 (GA4)
- **Hosting:** Streamlit Cloud

## 5. 수익 모델 (Monetization)
- **Affiliate Marketing:** Klook, Agoda 제휴 링크를 통한 예약 수수료.
- **Ad Inventory:** Google AdSense 및 Travelpayouts 배너 연동.

## 6. 프로젝트 분류 (Project Structure)
### 활성 상태 (Active)
- `app.py`: 메인 애플리케이션 로직.
- `utils.py`: 다양한 비즈니스 로직 및 API 연동 유틸리티.
- `db_utils.py`: Google Sheets 및 JSON DB 접근 계층.
- `batch_job.py`: 주기적인 데이터 수집 및 AI 분석 자동화 배치.

### 실험 및 디버깅 (Experiments/Side)
- `debug_*.py`: 특정 API나 기능의 일회성 테스트 스크립트.
- `test_*.py`: 기능 검증용 스크립트 (정식 테스트 프레임워크 도입 전).
- `migrate_*.py`: 데이터 스키마 변경 시 사용된 일회성 마이그레이션 도구.

---
*Last Updated: 2026-03-16*
