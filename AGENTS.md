# AI Agent Working Rules

This document provides persistent context and operating rules for AI agents (Codex, Antigravity, etc.) working on this repository to ensure continuity and prevent regression.

## 1. Minimal Destructive Edits
- **Rule**: Do not delete files or refactor large chunks of code without explicit confirmation.
- **Reason**: The root directory contains many "active" scripts for migration and data recovery. Moving them is preferred over deletion.

## 2. Documentation First
- **Rule**: Before making functional changes, update `DECISIONS.md` or `TODO.md` if the change affects architecture or long-term goals.
- **Rule**: When adding a new tab or feature to `app.py`, update `PROJECT_OVERVIEW.md`.

## 3. Localization Guardrails
- **Rule**: Always preserve the "Thai Today" tone (helpful, travel-focused, professional).
- **Rule**: Follow the specific translation rules in `utils.py` regarding political parties and Buddhist years.
- **Rule**: Output must maintain Korean as the primary display language.

## 4. Secret & Credential Handling
- **Rule**: Never hardcode API keys or GSheets service account JSONs.
- **Rule**: Use `st.secrets` or environment variables. Credentials for the service account are stored in `.json` files at the root (be careful not to expose them).

## 5. Continuity Checklist
- **Context Awareness**: Before starting work, read `PROJECT_OVERVIEW.md` and `DECISIONS.md`.
- **Sync Safety**: When modifying news processing, always test the synchronization between local `data/news.json` and Google Sheets.
- **Streamlit Specifics**: Use `@st.cache_data` and `@st.cache_resource` wisely to avoid unnecessary API calls to Google Sheets/Gemini.

## 6. Handoff Protocol
- At the end of a session, update `TODO.md` with "Now/Next" items to accurately reflect what was finished and what is still pending.
