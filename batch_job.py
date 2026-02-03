import difflib
import json
import os
import utils
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

# Files
FEEDS_FILE = 'data/feeds.json'
NEWS_FILE = 'data/news.json'
PROCESSED_URLS_FILE = 'data/processed_urls.json'
EVENTS_FILE = 'data/events.json'
from db_utils import load_news_from_sheet, save_news_to_sheet

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
    
    # [TIME SETUP] Use UTC+7 (Bangkok Time)
    import pytz
    bkk_tz = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(bkk_tz)
    today_str = now_bkk.strftime("%Y-%m-%d")
    current_time_str = now_bkk.strftime("%H:%M")
    
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
    # Load current news from GSheets
    current_news = load_news_from_sheet()
    
    if isinstance(current_news, dict):
        # 24-Hour Comparison Window (Only compare with the most recent day)
        latest_date = sorted(current_news.keys(), reverse=True)[0] if current_news else None
        if latest_date:
            for topic in current_news[latest_date]:
                recent_titles.append(topic['title'])
                for ref in topic.get('references', []):
                    if isinstance(ref, dict) and ref.get('title'):
                        recent_titles.append(ref['title'])
                    elif isinstance(ref, str):
                         # If ref is just a URL string, we can't extract title lightly, but at least won't crash
                         pass

    print(f"Loaded {len(recent_titles)} recent titles for similarity check.")

    processed_ids = set()
    for url in processed_urls:
        if 'bangkokpost.com' in url:
            parts = url.split('/')
            for p in parts:
                if p.isdigit() and len(p) >= 6:
                    processed_ids.add(p)

    new_items_with_ratios = []
    
    for item in all_news_items:
        # [NEW] Update Keyword Logic
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

        # C. Similarity Check (Fuzzy Match / Refined)
        is_similar = False
        max_ratio = 0
        matching_title = ""
        
        # Determine threshold based on date (Today Priority)
        # item['published'] might vary in format, we check if it contains today's date string
        # If not easily parsed, we fallback to a safer check or default to higher for all freshly fetched items
        # For simplicity, if we pulled it just now and it looks like a today's item, we use 0.85
        is_today_item = today_str in (item.get('published', '') or '')
        threshold = 0.85 if is_today_item else 0.6
        
        if not is_update_news:
            for existing_title in recent_titles:
                ratio = difflib.SequenceMatcher(None, item['title'].lower(), existing_title.lower()).ratio()
                if ratio > max_ratio:
                    max_ratio = ratio
                    matching_title = existing_title
                    
                if ratio > threshold:
                    # [STRICT CHECK BYPASS] Numerical data update
                    nums_new = re.findall(r'\d+', item['title'])
                    nums_old = re.findall(r'\d+', existing_title)
                    if nums_new != nums_old:
                        continue 
                        
                    is_similar = True
                    break
        
        if is_similar:
            print(f"[{'TODAY' if is_today_item else 'PAST'}] Skipping similar item ({max_ratio:.2f}) > {threshold}:")
            print(f" - New: {item['title']}")
            print(f" - Match: {matching_title}")
            continue

        new_items_with_ratios.append({"item": item, "max_ratio": max_ratio})

    # Zero-Result Fallback (Minimum 2-3 items)
    if not new_items_with_ratios and all_news_items:
        print("⚠️ No news passed filtering. Reviving 3 least similar items...")
        # Recalculate max_ratio for all items if needed, or use what we collect
        # Let's filter out exact URL/ID matches first, then sort by ratio
        fallback_candidates = []
        for item in all_news_items:
            if item['link'] in processed_urls: continue
            
            m_ratio = 0
            for ext in recent_titles:
                r = difflib.SequenceMatcher(None, item['title'].lower(), ext.lower()).ratio()
                if r > m_ratio: m_ratio = r
            fallback_candidates.append({"item": item, "max_ratio": m_ratio})
            
        fallback_candidates.sort(key=lambda x: x['max_ratio'])
        new_items_with_ratios = fallback_candidates[:3]
        for f in new_items_with_ratios:
            print(f" - Revived (Ratio {f['max_ratio']:.2f}): {f['item']['title']}")

    new_items = [x['item'] for x in new_items_with_ratios]
    print(f"Items after duplicate/similarity check: {len(new_items)}")

    if not new_items:
        print("No new items to process.")
        return

    # 4. Selection (Expanded for Score Filtering)
    # Ensure items within the SAME batch are not too similar
    batch_deduped = []
    for candidate in new_items:
        is_internal_dup = False
        for chosen in batch_deduped:
            r = difflib.SequenceMatcher(None, candidate['title'].lower(), chosen['title'].lower()).ratio()
            if r > 0.85: # Very strict within the same batch
                is_internal_dup = True
                break
        if not is_internal_dup:
            batch_deduped.append(candidate)
            
    target_items = batch_deduped[:8] 
    print(f"Items selected for API call (after internal dedup): {len(target_items)}")
    
    # 5. API Call (Moved up to get categories/titles before images if needed, 
    # but currently batch_job needs full content so we keep sequential)
    # Actually, let's just make sure all candidates have images extracted now.

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
    analysis_result, error_msg = utils.analyze_news_with_gemini(target_items, api_key, recent_titles, current_time_str)
    
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
            
    # Rule 3: Fill up to 5 items if we have less (User Request)
    # If filtered_topics < 5, grab the highest scoring remaining items regardless of threshold
    if len(filtered_topics) < 5:
        remaining_slots = 5 - len(filtered_topics)
        # Find items not yet in filtered_topics
        filtered_ids = {t.get('title') for t in filtered_topics}
        
        candidates = [t for t in raw_topics if t.get('title') not in filtered_ids]
        # Sort by score desc (already sorted actually)
        # Add top candidates to fill slots
        filtered_topics.extend(candidates[:remaining_slots])
        print(f"Filled {min(len(candidates), remaining_slots)} extra items to meet minimum 5.")

    print(f"Filtered topics from {len(raw_topics)} to {len(filtered_topics)} based on scores & minimum quota.")
    
    # Allow saving filtered_topics
    analysis_result['topics'] = filtered_topics

    today_str = now_bkk.strftime("%Y-%m-%d")
    current_time_str = now_bkk.strftime("%H:%M")
    
    # Load current news (Expect Dict, fallback to empty dict if list/invalid)
    current_news = load_news_from_sheet()
    if isinstance(current_news, list):
        current_news = {} 
        
    if today_str not in current_news:
        current_news[today_str] = []
        
    # Deduplicate against results already in GSheets for TODAY
    existing_today_titles = {t['title'] for t in current_news[today_str]}
    
    # Helper map: URL -> Image
    url_to_image = {item['link']: item.get('image_url') for item in target_items}

    # Extract topics and append to today's list
    new_topics_count = 0
    for topic in analysis_result.get('topics', []):
        # 1. Title Duplication Check (Strict)
        if topic['title'] in existing_today_titles:
            print(f"Skipping storage of duplicate title for today: {topic['title']}")
            continue

        # 2. Inject metadata
        topic['collected_at'] = current_time_str
        
        # 3. Reference & Source Guarantee
        # If Gemini missed references, or they are empty, force-inject the original source
        if not topic.get('references'):
            # Find the original item to get link/source
            # Try to match by topic's title (fuzzy if needed) or just use the first item if link is lost
            # But better yet, analyze_news_with_gemini uses target_items sequentially
            # Since we only send one item at a time in the loop now, we can match it back.
            topic['references'] = []

        # Find the original entry from all_news_items or target_items to get source/link
        # We need to map the topic back to its original source item.
        # Since analyze_news_with_gemini is called with target_items, let's try to match.
        # Note: target_items were sent one by one in the loop inside analyze_news_with_gemini.
        
        # Actually, let's look at how references are handled in the storage loop.
        # ref_link = topic.get('references', [{}])[0].get('url')
        
        # [NEW SAFETY] Force original reference if missing
        if not topic.get('references'):
             # If we can't find it, we'll try to find any item in target_items that matches title roughly
             for ti in target_items:
                 if difflib.SequenceMatcher(None, topic['title'].lower(), ti['title'].lower()).ratio() > 0.8:
                     topic['references'] = [{'title': ti['title'], 'url': ti['link'], 'source': ti['source']}]
                     break

        # 4. Inject images into references AND lift first image to topic level (for card UI)
        first_image = None
        for ref in topic.get('references', []):
            ref_url = ref.get('url')
            # Ensure 'source' is not missing
            if not ref.get('source'):
                 # Try to find source from all_news_items
                 for ti in all_news_items:
                     if ti['link'] == ref_url:
                         ref['source'] = ti['source']
                         break
            
            img = url_to_image.get(ref_url)
            
            # Fallback extraction if it missed earlier (e.g. revived items or failed scraping)
            if not img:
                print(f"   -> Image missing for '{topic['title']}', attempting final extraction...")
                entry = next((i for i in all_news_items if i['link'] == ref_url), None)
                if entry:
                    img = get_image_from_entry(entry)
                    url_to_image[ref_url] = img # Cache it
            
            if img:
                ref['image_url'] = img
                if not first_image:
                    first_image = img
        
        # If topic doesn't have an image, give it the first reference's image
        if 'image_url' not in topic and first_image:
            topic['image_url'] = first_image
            
        current_news[today_str].append(topic)
        existing_today_titles.add(topic['title'])
        new_topics_count += 1
        
    save_news_to_sheet(current_news)
    save_json(NEWS_FILE, current_news) # Fix: Missing local save
    print(f"Saved {new_topics_count} new topics to Google Sheets under key '{today_str}'")
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
