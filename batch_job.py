import json
import os
import utils
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Files
FEEDS_FILE = 'data/feeds.json'
NEWS_FILE = 'data/news.json'
PROCESSED_URLS_FILE = 'data/processed_urls.json'

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return [] if 'processed_urls' in file_path or 'news.json' in file_path else {}
    return [] if 'processed_urls' in file_path or 'news.json' in file_path else {}

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_image_from_entry(item):
    """
    Extracts image URL from RSS entry or falls back to scraping OG:IMAGE.
    """
    entry = item.get('_raw_entry')
    image_url = None

    # Step 1: Check RSS tags
    if entry:
        # Check 'media_content'
        if 'media_content' in entry:
            for media in entry.media_content:
                if 'url' in media and 'image' in media.get('type', ''):
                    return media['url']
        
        # Check 'media_thumbnail'
        if 'media_thumbnail' in entry:
            # Sometimes it's a list, sometimes dict
            if isinstance(entry.media_thumbnail, list) and len(entry.media_thumbnail) > 0:
                 return entry.media_thumbnail[0].get('url')
        
        # Check 'enclosure'
        if 'enclosures' in entry:
            for enc in entry.enclosures:
                if 'image' in enc.get('type', ''):
                    return enc.get('href')
        
        # Check 'links'
        if 'links' in entry:
            for link in entry.links:
                 if 'image' in link.get('type', ''):
                     return link.get('href')

    # Step 2: Scrape meta tag (Fallback)
    if not image_url and item.get('link'):
        try:
            print(f"   - Scraping for image: {item['link']}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            }
            # Timeout set to 5 seconds as requested
            response = requests.get(item['link'], headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                og_image = soup.find("meta", property="og:image")
                if og_image and og_image.get("content"):
                    return og_image["content"]
        except Exception as e:
            print(f"   - Image scrape failed: {e}")

    return None

def main():
    print("Starting batch job (Strict Mode + Images)...")
    
    # 1. Load State
    feeds = load_json(FEEDS_FILE)
    processed_urls = set(load_json(PROCESSED_URLS_FILE))
    # print(f"Loaded {len(processed_urls)} processed URLs.")
    
    if not feeds:
        print("No feeds found. Exiting.")
        return

    # 2. Fetch RSS (Get ALL items first)
    print("Fetching RSS feeds...")
    all_news_items = utils.fetch_and_filter_rss(feeds)
    print(f"Total items fetched: {len(all_news_items)}")
    
    # 3. Filter Duplicates (Strict Check)
    new_items = []
    for item in all_news_items:
        if item['link'] not in processed_urls:
            new_items.append(item)
    print(f"Items after duplicate check: {len(new_items)}")

    if not new_items:
        print("No new items to process.")
        return

    # 4. Filter (Top 5)
    target_items = new_items[:5]
    print(f"Items selected for API call (Max 5): {len(target_items)}")
    
    # 5. Extract Images (ONLY for top 5)
    for item in target_items:
        print(f" - Processing: {item['title']}")
        item['image_url'] = get_image_from_entry(item)
        if item['image_url']:
            print(f"   + Found Image: {item['image_url']}")

    # 6. API Call
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return

    print("Calling Gemini API...")
    # Clean _raw_entry before passing to utils/model to avoid serialization errors or huge prompts
    # Although utils.analyze extracts fields manually, it's safer to rely on utils handling.
    # utils.analyze_news_with_gemini uses item['summary'], item['title'], etc.
    
    analysis_result, error_msg = utils.analyze_news_with_gemini(target_items, api_key)
    
    if error_msg:
        print(f"Analysis failed: {error_msg}")
        return

    # 7. Save Logic (Daily Accumulation)
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_time_str = datetime.now().strftime("%H:%M")
    
    # Load current news (Expect Dict, fallback to empty dict if list/invalid)
    current_news = load_json(NEWS_FILE)
    if isinstance(current_news, list):
        current_news = {} # Migration: Reset if it was a list
        
    if today_str not in current_news:
        current_news[today_str] = []
        
    # Helper map: URL -> Image
    url_to_image = {item['link']: item.get('image_url') for item in target_items}

    # Extract topics and append to today's list
    new_topics_count = 0
    for topic in analysis_result.get('topics', []):
        # Inject metadata
        topic['collected_at'] = current_time_str
        
        # Inject images into references AND lift first image to topic level (for card UI)
        first_image = None
        for ref in topic.get('references', []):
            ref_url = ref.get('url')
            if ref_url in url_to_image and url_to_image[ref_url]:
                ref['image_url'] = url_to_image[ref_url]
                if not first_image:
                    first_image = ref['image_url']
        
        # If topic doesn't have an image, give it the first reference's image
        if 'image_url' not in topic and first_image:
            topic['image_url'] = first_image
            
        current_news[today_str].append(topic)
        new_topics_count += 1
        
    save_json(NEWS_FILE, current_news)
    print(f"Saved {new_topics_count} new topics to {NEWS_FILE} under key '{today_str}'")

    # 7-2. Update processed_urls.json
    for item in target_items:
        processed_urls.add(item['link'])
    
    save_json(PROCESSED_URLS_FILE, list(processed_urls))
    print(f"Updated {PROCESSED_URLS_FILE} with {len(target_items)} new URLs.")

if __name__ == "__main__":
    main()
