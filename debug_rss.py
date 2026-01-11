import utils
import json
import os
from datetime import datetime

# Files
FEEDS_FILE = 'data/feeds.json'
PROCESSED_URLS_FILE = 'data/processed_urls.json'
NEWS_FILE = 'data/news.json'

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def main():
    print("Debug: Starting RSS Check...")
    
    # 1. Load State
    feeds = load_json(FEEDS_FILE)
    processed_urls = set(load_json(PROCESSED_URLS_FILE))
    print(f"Loaded {len(feeds)} feeds.")
    print(f"Loaded {len(processed_urls)} processed URLs.")
    
    # 2. Fetch RSS
    print("Fetching RSS feeds...")
    try:
        all_news_items = utils.fetch_and_filter_rss(feeds)
        print(f"Total items fetched from RSS: {len(all_news_items)}")
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return

    # 3. Filter Duplicates
    new_items = []
    for item in all_news_items:
        if item['link'] not in processed_urls:
            new_items.append(item)
            
    print(f"Items after processed_url check: {len(new_items)}")
    
    if new_items:
        print("Top 5 new items candidates:")
        for i, item in enumerate(new_items[:5]):
            print(f"{i+1}. {item['title']}")
            print(f"   Link: '{item['link']}'")
            # Check for near matches in processed_urls
            for p_url in processed_urls:
                if item['link'] == p_url:
                    print(f"   MATCH FOUND (Logic Error): {p_url}")
                elif item['link'] in p_url or p_url in item['link']:
                     print(f"   NEAR MATCH: {p_url}")
            
    # Check current news.json status
    news_data = load_json(NEWS_FILE)
    if isinstance(news_data, dict):
        today = datetime.now().strftime("%Y-%m-%d")
        if today in news_data:
            print(f"news.json has {len(news_data[today])} items for today ({today}).")
        else:
            print(f"news.json has NO items for today ({today}). Available keys: {list(news_data.keys())}")
    else:
        print("news.json is not a dict.")

if __name__ == "__main__":
    main()
