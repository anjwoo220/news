import json
import os
from db_utils import SPREADSHEET_URL, LOCAL_NEWS_CACHE, get_news_for_date, load_recent_news

l_cache = {}
if os.path.exists(LOCAL_NEWS_CACHE):
    with open(LOCAL_NEWS_CACHE, 'r', encoding='utf-8') as f:
        l_cache = json.load(f)

print(f"Local Cache Keys: {list(l_cache.keys())[:20]}")

rec = load_recent_news(days=7)
print(f"Recent News Keys: {list(rec.keys())}")

older = get_news_for_date("2026-03-09")
print(f"Older News (2026-03-09) Length: {len(older)}")
