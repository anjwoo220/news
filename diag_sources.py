import utils
import json
import os

def diag():
    feeds_file = 'data/feeds.json'
    with open(feeds_file, 'r') as f:
        feeds = json.load(f)
    
    print("Fetching Balanced RSS...")
    balanced_items = utils.fetch_balanced_rss(feeds)
    
    print("\nChecking Balanced Items for 'None' source:")
    for item in balanced_items:
        if item.get('source') is None or str(item.get('source')).lower() == 'none':
            print(f"!!! Found None Source in Balanced Item: {item['title']} ({item['link']})")

    print("\nFetching Google News...")
    google_items = utils.fetch_google_news_rss(query="Thailand Tourism")
    
    print("\nChecking Google News Items for all sources:")
    for item in google_items:
        src = item.get('source')
        print(f"Source: {src} | Title: {item['title'][:50]}...")
        if src is None or str(src).lower() == 'none' or not src:
            print(f"!!! ALERT: Found None or empty Source in Google Item: {item['title']} ({item['link']})")

if __name__ == "__main__":
    diag()
