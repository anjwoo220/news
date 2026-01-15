import os
import json
import utils
import db_utils
from datetime import datetime
import pytz

def dry_run():
    print("--- News Update Dry Run ---")
    
    # 1. Load config
    FEEDS_FILE = 'data/feeds.json'
    PROCESSED_URLS_FILE = 'data/processed_urls.json'
    
    with open(FEEDS_FILE, 'r') as f:
        feeds = json.load(f)
    
    with open(PROCESSED_URLS_FILE, 'r') as f:
        processed_urls = set(json.load(f))
    
    print(f"Loaded {len(processed_urls)} processed URLs.")
    
    # 2. Fetch
    print("Fetching RSS feeds...")
    all_news_items = utils.fetch_balanced_rss(feeds, processed_urls)
    
    print("Fetching Google News (Backup)...")
    google_news_items = utils.fetch_google_news_rss(query="Thailand Tourism")
    all_news_items.extend(google_news_items)
    
    print(f"Total items fetched (before dedup): {len(all_news_items)}")
    
    # Filter out already processed
    new_items = [item for item in all_news_items if item['link'] not in processed_urls]
    
    print(f"New items found: {len(new_items)}")
    for i, item in enumerate(new_items[:5]):
        print(f" [{i+1}] {item['title']} - {item['link']}")
        
    if not new_items:
        print("No NEW items found since last run.")
    else:
        print(f"\nThere are {len(new_items)} potential items to process.")

if __name__ == "__main__":
    dry_run()
