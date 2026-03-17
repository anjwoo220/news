# Architectural Decisions Record

This document records the key architectural and product decisions made during the development of Thai Today.

## 1. Google Sheets as Primary Database
- **Status**: Decided
- **Context**: Needed a low-latency, free, and human-readable/editable database for news and job listings.
- **Decision**: Use Google Sheets via `streamlit-gsheets` connection.
- **Consequence**: Data is easily accessible via Google Sheets UI for manual fixes, but large datasets (e.g., >10MB local cache) require careful synchronization logic (`db_utils.py`).

## 2. Gemini for Localization and Summarization
- **Status**: Decided
- **Context**: Content is largely in Thai/English, while target users are Korean. Traditional translation is often inaccurate for local context (e.g., political party names).
- **Decision**: Use Gemini (1.5 Flash / 2.0 Flash) with recursive prompts and specific translation rules (e.g., 'People's Party' -> '국민당').
- **Consequence**: High quality, context-aware translation; dependent on Gemini API availability and cost management.

## 3. GitHub Actions for Scheduled Tasks
- **Status**: Decided
- **Context**: Need real-time news and job updates without a dedicated 24/7 server.
- **Decision**: Use GitHub Actions for periodic crawling and AI processing.
- **Consequence**: "Serverless" automation; processing is restricted by GitHub runner limits and job frequencies.

## 4. Local JSON for Caching
- **Status**: Decided
- **Context**: GSheets API can be slow or encounter limits on frequent reads.
- **Decision**: Store a flattened version of recent data in `data/news.json` for the Streamlit app to read near-instantly.
- **Consequence**: Fast UI performance; requires robust sync between the local cache and GSheets source of truth.

## 5. Standardized News Categories
- **Status**: Decided
- **Context**: Different news sources use varying tags.
- **Decision**: Normalize everything into `POLITICS`, `BUSINESS`, `TRAVEL`, `LIFESTYLE`.
- **Consequence**: Simplified UI filtering for travelers.

## 6. Political Party Translation (Specific)
- **Status**: Decided
- **Context**: 'People's Party' was being translated to '국민의힘' (Korean party) instead of '국민당'.
- **Decision**: Forced Gemini to use '국민당' through specific prompt constraints.
- **Consequence**: Accurate representation of Thai political landscape in the Korean app.

## 7. Korean-First Editorial UI System
- **Status**: Decided
- **Context**: The viewer experience had grown inconsistent due to mixed font systems, duplicated navigation patterns, and fragmented inline/CSS styling across the app.
- **Decision**: Standardize the viewer UI around a Korean-first editorial design system with a unified app shell, simplified primary navigation, shared card styling, and centralized visual tokens in `style.css`.
- **Consequence**: The product feels more coherent and easier to maintain visually, while future UI work should prefer extending shared styles/components instead of adding more page-specific inline CSS.

## 8. Fail Closed on News Sync Mismatch
- **Status**: Decided
- **Context**: The news update pipeline was able to commit refreshed `data/news.json` even when Google Sheets sync did not advance, causing local/deployed behavior to diverge depending on which data source was used.
- **Decision**: Treat Google Sheets persistence as a required gate in the batch news job. If saving to Sheets fails, abort before writing the local JSON cache so the pipeline fails closed instead of publishing partial state.
- **Consequence**: News updates are less likely to drift between JSON cache and GSheets, and sync failures should surface immediately in automation instead of becoming silent data inconsistencies.

## 9. Fail-Safe Year Normalization for Thai News
- **Status**: Decided
- **Context**: Thai news sources often use Buddhist Era years (`25xx`, `พ.ศ.`, `B.E.`), and Gemini occasionally mistranslated them into incorrect future Gregorian years like `2069`, which then leaked into cached/localized Korean news.
- **Decision**: Enforce a shared Python-side year sanitizer across the news pipeline. Gemini prompts should still instruct year conversion, but localized news must also pass through deterministic post-processing before being cached, displayed, or written back to Google Sheets/JSON.
- **Consequence**: Date localization becomes more reliable even when model output drifts, and old cached articles can be repaired with the same sanitizer instead of relying on prompt quality alone.
