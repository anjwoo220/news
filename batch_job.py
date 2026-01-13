import difflib
import json
import os
import utils
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Files
FEEDS_FILE = 'data/feeds.json'
NEWS_FILE = 'data/news.json'
PROCESSED_URLS_FILE = 'data/processed_urls.json'
EVENTS_FILE = 'data/events.json'

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

    # 2. Fetch RSS (Balanced)
    print("Fetching RSS feeds (Balanced Mode)...")
    all_news_items = utils.fetch_balanced_rss(feeds, processed_urls)
    
    # [NEW] Add Google News Backup
    print("Fetching Google News (Backup)...")
    google_news_items = utils.fetch_google_news_rss(query="Thailand Tourism")
    all_news_items.extend(google_news_items)
    
    print(f"Total items fetched: {len(all_news_items)}")
    
    # 3. Filter Duplicates (Strict Check + Similarity)
    recent_titles = []
    current_news = load_json(NEWS_FILE)
    if isinstance(current_news, dict):
        for date_key in sorted(current_news.keys(), reverse=True)[:3]: 
            for topic in current_news[date_key]:
                recent_titles.append(topic['title'])
                for ref in topic.get('references', []):
                    if ref.get('title'):
                        recent_titles.append(ref['title'])

    print(f"Loaded {len(recent_titles)} recent titles for similarity check.")

    processed_ids = set()
    for url in processed_urls:
        if 'bangkokpost.com' in url:
            parts = url.split('/')
            for p in parts:
                if p.isdigit() and len(p) >= 6:
                    processed_ids.add(p)

    new_items = []
    
    for item in all_news_items:
        # [NEW] Update Keyword Logic
        # If title contains 'Update', 'Solved', 'Safe', we force allow it (bypass strict dup checks)
        # We assume 2hr check is implicitly handled by RSS window or we trust the keyword.
        # Ideally, we should check timestamps, but we'll trust the Keyword + freshness of RSS.
        is_update_news = any(k in item['title'].lower() for k in ['(update)', 'update:', 'solved:', 'safe:', 'situation resolved'])
        
        # A. Exact Link Match
        if not is_update_news and item['link'] in processed_urls:
            continue
            
        # B. ID Match (Bangkok Post)
        is_dup_id = False
        if not is_update_news and 'bangkokpost.com' in item['link']:
            parts = item['link'].split('/')
            for p in parts:
                if p.isdigit() and len(p) >= 6:
                    if p in processed_ids:
                        is_dup_id = True
                        break
        if is_dup_id:
            print(f"Duplicate ID found, skipping: {item['title']}")
            continue

        # C. Similarity Check (Fuzzy Match)
        is_similar = False
        if not is_update_news:
            for existing_title in recent_titles:
                ratio = difflib.SequenceMatcher(None, item['title'].lower(), existing_title.lower()).ratio()
                if ratio > 0.6:
                    print(f"Skipping similar item ({ratio:.2f}):")
                    print(f" - New: {item['title']}")
                    print(f" - Old: {existing_title}")
                    is_similar = True
                    break
        
        if is_similar:
            continue

        new_items.append(item)

    print(f"Items after duplicate/similarity check: {len(new_items)}")

    if not new_items:
        print("No new items to process.")
        return

    # 4. Selection (Expanded for Score Filtering)
    # Give AI more candidates (10 usually covers 1 day of tourism news)
    target_items = new_items[:8] 
    print(f"Items selected for API call: {len(target_items)}")
    
    # 5. Extract Images
    for item in target_items:
        print(f" - Processing: {item['title']} [{item.get('suggested_category', '')}]")
        item['image_url'] = get_image_from_entry(item)
        if item['image_url']:
            print(f"   + Found Image: {item['image_url']}")

    # 6. API Call
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import toml
            secrets = toml.load(".streamlit/secrets.toml")
            api_key = secrets.get("GEMINI_API_KEY")
        except: pass
            
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return

    print("Calling Gemini API...")
    analysis_result, error_msg = utils.analyze_news_with_gemini(target_items, api_key)
    
    if error_msg:
        print(f"Analysis failed: {error_msg}")
        return
        
    # [NEW] Importance-Based Filtering
    # Logic: Keep Top 5. BUT if Score >= 7, keep them all (override limit).
    raw_topics = analysis_result.get('topics', [])
    filtered_topics = []
    
    # Sort by Score Descending
    # Handle missing score (default 5)
    raw_topics.sort(key=lambda x: x.get('tourist_impact_score', 5) or 5, reverse=True)
    
    for i, topic in enumerate(raw_topics):
        score = topic.get('tourist_impact_score', 0) or 0
        
        # Rule 1: Always keep High Impact (>=7)
        if score >= 7:
            filtered_topics.append(topic)
            continue
            
        # Rule 2: Keep Medium (4-6) only if we haven't hit quota of 5
        if len(filtered_topics) < 5 and score >= 4:
            filtered_topics.append(topic)
            
        # Rule 3: Drop Low Impact (<=3) unless we have practically nothing?
        # User implies filtering based on importance. Dropping 1-3 is safe.
        
    print(f"Filtered topics from {len(raw_topics)} to {len(filtered_topics)} based on scores.")
    
    # Allow saving filtered_topics
    analysis_result['topics'] = filtered_topics

    # 7. Save Logic (Daily Accumulation)
    # Use UTC+7 (Bangkok Time) for date key
    import pytz
    bkk_tz = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(bkk_tz)
    
    today_str = now_bkk.strftime("%Y-%m-%d")
    current_time_str = now_bkk.strftime("%H:%M")
    
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

    # 7-1. Cross-post Travel News to Events
    # Filter for '여행/관광' category
    # 7-1. Cross-post "Strict Events" to Events Tab
    # Now we only look for '축제/이벤트' which passed the strict verification in utils.py
    strict_events = [t for t in current_news[today_str] if t.get('category') == '축제/이벤트']
    
    if strict_events:
        print(f"Found {len(strict_events)} STRICT events. Cross-posting to {EVENTS_FILE}...")
        
        # Load Events
        if os.path.exists(EVENTS_FILE):
             events_data = load_json(EVENTS_FILE)
             if not isinstance(events_data, list): events_data = []
        else:
             events_data = []

        # Dedupe existing titles + Check similar dates/locations?
        existing_titles = set(e.get('title') for e in events_data)
        
        added_events = 0
        for item in strict_events:
            if item['title'] not in existing_titles:
                # Extract strict info
                evt_info = item.get('event_info', {})
                if not evt_info: continue # Double check
                
                new_event = {
                    "title": item['title'],
                    "date": evt_info.get('date', '날짜 미정'),
                    "location": evt_info.get('location', '장소 미정'),
                    "region": "방콕", # Default to Bangkok or infer from contents if possible? (Simplicity for now)
                    "image_url": item.get('image_url'),
                    "link": item.get('references', [{'url': '#'}])[0].get('url'),
                    "price": evt_info.get('price', '가격 정보 없음'),
                    "type": "축제/이벤트",
                    "description": item.get('summary', '')
                }
                
                # Prepend to top
                events_data.insert(0, new_event)
                existing_titles.add(item['title'])
                added_events += 1
        
        if added_events > 0:
            save_json(EVENTS_FILE, events_data)
            print(f"Cross-posted {added_events} strict events to {EVENTS_FILE}.")

    # 7-2. Update processed_urls.json (ONLY for successful items)
    # Collect URLs that were actually successfully turned into topics
    successful_urls = set()
    for topic in analysis_result.get('topics', []):
        for ref in topic.get('references', []):
            if ref.get('url'):
                successful_urls.add(ref['url'])
    
    # Also add items that were skipped or handled but didn't result in a topic? 
    # No, strict retry policy: if it failed to generate a topic (e.g. rate limit), retry next time.
    
    # However, Gemini might merge multiple source items into one topic.
    # We should mark *all* target_items as processed ONLY IF the API call was at least successful (not 0 topics).
    # But wait, if Rate Limit happened for Item 4 but Item 1,2,3 worked, aggregated_topics has 1,2,3.
    # Relying on references in the output is the safest way to know which input was "consumed".
    
    processed_count = 0
    for url in successful_urls:
        processed_urls.add(url)
        processed_count += 1
    
    if processed_count == 0 and len(target_items) > 0:
        print("Warning: No topics generated, NOT marking any URLs as processed to allow retry.")
    else:
        print(f"Marked {processed_count} URLs as processed.")
    
    save_json(PROCESSED_URLS_FILE, list(processed_urls))
    print(f"Updated {PROCESSED_URLS_FILE} with {len(target_items)} new URLs.")

    # 8. Update Twitter Trends
    print("Fetching Twitter Trends...")
    trend_result = utils.fetch_twitter_trends(api_key)
    if trend_result:
        try:
            with open('data/twitter_trends.json', 'w', encoding='utf-8') as f:
                json.dump(trend_result, f, ensure_ascii=False, indent=2)
            print("Twitter trends updated.")
        except Exception as e:
            print(f"Failed to save twitter trends: {e}")
    else:
        print("No critical twitter trends found or fetch failed.")

if __name__ == "__main__":
    main()
