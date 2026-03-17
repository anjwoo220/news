# Project Overview: Thai Today (오늘의 태국)

A comprehensive real-time information service for travelers and residents in Thailand, powered by AI (Gemini) and hosted on Streamlit.

## 1. Product Purpose
The goal is to provide a "one-stop" platform for verified, AI-summarized Thai news, job listings, restaurant fact-checks, and travel guides, eliminating the need to browse multiple fragmented sources.

## 2. Target Users
- Korean travelers visiting Thailand (Bangkok, etc.)
- Korean expats living in Thailand.
- Job seekers looking for opportunities in Thailand.

## 3. Subprojects & Components

### 🟢 Core Web Application (Main App)
- **Files**: `app.py`, `style.css`, `utils.py`, `db_utils.py`
- **Purpose**: Interactive UI for users to browse news, hotels, restaurants, and jobs.
- **Stack**: Python, Streamlit, Pandas.
- **Maturity**: High. Full production-ready UI with multi-tab navigation.

### 🔵 News Intelligence Engine
- **Files**: `utils.py` (crawling/AI logic), `.github/workflows/update_news.yml`
- **Purpose**: Automated news collection (RSS), AI summarization (Gemini), and categorization.
- **Automation**: Runs via GitHub Actions to keep the news feed fresh.
- **Maturity**: Stable. Recently refined with specific translation rules (e.g., 정당명 번역).

### 🟠 Job Crawler System
- **Files**: `crawl_jobs.py`, `.github/workflows/crawl_jobs.yml`
- **Purpose**: Scrapes job listings from major Thai sources (Hanasia, KyominThai, JobThai).
- **Automation**: Uses Playwright for dynamic content.
- **Maturity**: Medium. Recently recovered from broken selectors; currently active.

### 🟡 Data & Storage Layer
- **Files**: `data/*.json`, Google Sheets (via `db_utils.py`)
- **Purpose**: Hybrid storage. Smaller configs/state in JSON files; historical news/jobs in persistent Google Sheets.
- **Maturity**: Stable. Uses `streamlit-gsheets` for seamless integration.

## 4. Repository Clutter & Abandoned Experiments
- **Clutter**: The root directory contains 50+ scripts (e.g., `check_dates.py`, `migrate_news.py`, `diag_sources.py`). These are mostly one-off migration or debugging tools.
- **Action**: These should eventually be moved to a `scripts/` or `archive/` folder to improve readability.

## 5. Technology Stack
- **Languages**: Python 3.11+
- **Frontend**: Streamlit
- **AI/LLM**: Google Gemini 1.5 Flash / 2.0 Flash
- **Infras**: GitHub Actions (Automation), Streamlit Cloud (Hosting)
- **Database**: Google Sheets (Persistence), local JSON (Cache)
