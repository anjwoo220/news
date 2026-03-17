# Backlog & Roadmap (TODO)

Prioritized tasks for the Thai Today repository.

## 🔴 Now (High Priority)
- [ ] **Repository Cleanup**: Move one-off scripts (`check_*.py`, `debug_*.py`, `migrate_*.py`, etc.) into a `/research` or `/scripts/one_off` directory.
- [ ] **Fix/Audit Clutter**: Inspect `app.py.bak` files and archive them properly.
- [ ] **Refactor `app.py`**: The main app file is becoming too large (250KB+). Extract tab-specific logic into separate modules (e.g., `tabs/news.py`, `tabs/jobs.py`).

## 🟡 Next (Medium Priority)
- [ ] **Job Filtering Enhancement**: Further filter job posts that have "Unknown" descriptions or broken URLs from KyominThai.
- [ ] **Image Fallbacks**: Improve the news thumbnail fallback system to use more diverse Thai travel images.
- [ ] **Premium Access Logic**: Finalize the Admin UI and Webhook API for managing premium user access (as identified in recent conversation context).

## 🟢 Later (Low Priority / Future)
- [ ] **Native Mobile App**: Consider a Flutter or React Native wrapper for better push notification support.
- [ ] **Expansion**: Add more Thai regions (Chiang Mai, Phuket) specific news/job channels.
- [ ] **Multi-provider AI**: Add support for Claude or GPT-4o as fallback summarizers.

## ⚪ Blocked / On Hold
- [ ] **Google News Source Safeguards**: Currently limited by Google News RSS formatting; waiting for better scraping techniques for missing source labels.

## Session Handoff
- **2026-03-16 Now**: Viewer UI redesigned around a unified app shell, simplified primary navigation, refreshed editorial card styling, fixed the THB/KRW exchange-rate fetch, and gated batch news updates so `data/news.json` is not written when Google Sheets sync fails.
- **2026-03-16 Next**: Validate the redesigned layout across the remaining high-traffic tabs (`뉴스`, `호텔`, `맛집`), continue reducing page-specific inline CSS, and investigate why the production news workflow is updating JSON while the `news` Google Sheet remains stuck at `2026-03-13`.
