import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta
import time
import json
import os
import requests
import re
from bs4 import BeautifulSoup



# Helper: Check if text contains Thai characters
def is_thai(text):
    import re
    if not text: return False
    return bool(re.search(r'[\u0E00-\u0E7F]', text))

# Helper: Convert Thai Buddhist year to Gregorian year
def convert_thai_year(text: str) -> str:
    import re
    def repl(match):
        year = int(match.group())
        if year > 2500:  # typical Buddhist year
            return str(year - 543)
        return match.group()
    return re.sub(r'\b\d{4}\b', repl, text)

# Helper: Translate text to Korean using Gemini
def translate_text(text: str, dest: str = "ko") -> str:
    """
    Translate Thai text to Korean using Gemini 2.0 Flash.
    Handles API key loading and ensures robust response.
    """
    # 1. Quick Check: Is it already Korean or just numbers?
    if not text or len(text.strip()) == 0:
        return ""
    
    # 2. Convert Thai Buddhist year first
    text = convert_thai_year(text)
    
    # 3. Use Gemini
    try:
        # Lazy load API key if needed (or assume configured globally in app)
        # But utils might be imported separately, so re-check/configure.
        import google.generativeai as genai
        import toml
        
        # Try to get key efficiently
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            try:
                secrets = toml.load(".streamlit/secrets.toml")
                api_key = secrets.get("GEMINI_API_KEY")
            except: pass
            
        if api_key:
            genai.configure(api_key=api_key)
            
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Translate the following Thai text to Korean.
        - Maintain the original tone (News/Formal).
        - Output ONLY the translated text. Do not add explanations.
        - If the text is already Korean, return it as is.
        
        Text:
        {text}
        """
        
        response = model.generate_content(prompt)
        translated = response.text.strip()
        return translated
        
    except Exception as e:
        print(f"Translation Error for '{text[:20]}...': {e}")
        return text


# Helper: Check if article is within last N days
def is_recent(entry, days=3):
    if not hasattr(entry, 'published_parsed'):
        return True # Default to include if no date
    
    # published_parsed is a struct_time, convert to datetime
    pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
    limit_date = datetime.now() - timedelta(days=days)
    return pub_date >= limit_date

# Helper: Check relevance to Thailand
def is_relevant_to_thailand(entry):
    """
    Determines if an article is relevant to Thailand based on keywords and script.
    Checks: Title, Summary (if available)
    """
    import re
    
    # 1. content to check
    text = (entry.title + " " + entry.get('summary', '')).lower()
    
    # 2. Check for Thai Characters (Script)
    if re.search(r'[\u0E00-\u0E7F]', text):
        return True
        
    # 3. Check for English Keywords
    keywords = [
        "thailand", "thai", "bangkok", "phuket", "pattaya", "chiang", 
        "samui", "krabi", "isan", "baht", "pheu thai", 
        "prime minister", "paetongtarn", "thaksin", "king", "royal",
        "cabinet", "govt", "police", "otp", "airport"
    ]
    
    for kw in keywords:
        if kw in text:
            return True
            
    return False

# 1. RSS Parsing (Balanced)
def fetch_balanced_rss(feeds_config, processed_urls=None):
    """
    Fetches RSS feeds and returns a balanced mix of items across categories.
    feeds_config: List of dicts [{'category': '...', 'url': '...'}, ...]
    processed_urls: Set of strings (optional) to skip already seen news.
    """
    import requests
    
    if processed_urls is None:
        processed_urls = set()
    
    # Using a typical browser User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    }
    
    category_buckets = {}
    MAX_PER_CATEGORY = 20  # Increased from 2 to allow checking more feeds
    
    for feed in feeds_config:
        category = feed.get('category', 'General')
        url = feed.get('url')
        
        if category not in category_buckets:
            category_buckets[category] = []
            
        # Check quota early
        if len(category_buckets[category]) >= MAX_PER_CATEGORY:
            print(f"Skipping feed {url} (Quota full for {category})")
            continue
            
        try:
            print(f"Fetching [{category}] {url}...")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"Failed to fetch {url}: Status {response.status_code}")
                continue
                
            feed_data = feedparser.parse(response.content)
            
            if feed_data.bozo:
                print(f"XML Parse Warning for {url}: {feed_data.bozo_exception}")
            
            print(f"Successfully parsed {url}: Found {len(feed_data.entries)} entries.")
            
            for entry in feed_data.entries:
                # Re-check quota inside loop
                if len(category_buckets[category]) >= MAX_PER_CATEGORY:
                    break
                
                # Filter: Relevance Check (Skip non-Thai news)
                if not is_relevant_to_thailand(entry):
                    # print(f"Skipping irrelevant: {entry.title}") 
                    continue

                # Filter: Skip already processed
                if entry.link in processed_urls:
                    # print(f"Skipping already processed: {entry.title}")
                    continue

                if is_recent(entry):
                    item = {
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", str(datetime.now())),
                        "summary": entry.get("summary", ""),
                        "source": feed_data.feed.get("title", url),
                        "suggested_category": category, # Hint for AI or logic
                        "_raw_entry": entry
                    }
                    category_buckets[category].append(item)
                    
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Interleave (Round-Robin) to create balanced list
    balanced_items = []
    max_items_per_cat = max(len(items) for items in category_buckets.values()) if category_buckets else 0
    
    categories = list(category_buckets.keys())
    
    for i in range(max_items_per_cat):
        for cat in categories:
            if i < len(category_buckets[cat]):
                balanced_items.append(category_buckets[cat][i])
                
    return balanced_items

# 2. Gemini Analysis
import re

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext


# --------------------------------------------------------------------------------
# Google News RSS Fetcher (Backup Source)
# --------------------------------------------------------------------------------
def fetch_google_news_rss(query="Thailand Tourism", period="24h"):
    """
    Fetches Google News RSS for a specific query.
    Returns: List of dicts matching news item structure.
    """
    import feedparser
    import urllib.parse
    import time
    
    encoded_query = urllib.parse.quote(query)
    # hl=en-TH, gl=TH ensures Thailand focus
    # when:24h = Last 24 hours
    # scoring=n = Sort by Date (Newest first)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:{period}&hl=en-TH&gl=TH&ceid=TH:en&scoring=n"
    
    print(f"Fetching Google News: {query}...")
    try:
        feed = feedparser.parse(rss_url)
        items = []
        for entry in feed.entries:
            # Standardize to our News Item format
            item = {
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', ''),
                'summary': entry.get('description', ''),
                'source': entry.get('source', {}).get('title', 'Google News'),
                '_raw_entry': entry # Keep for image extraction
            }
            items.append(item)
        print(f" -> Found {len(items)} items from Google News.")
        return items
    except Exception as e:
        print(f"Google News Fetch Error: {e}")
        return []

# Helper: Fetch Full Content from URL
def fetch_full_content(url):
    """
    Scrapes the main text content from a news URL.
    Returns: String (text) or None
    """
    import requests
    from bs4 import BeautifulSoup
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        # Timeout slightly longer for scraping
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
            
        # Extract text from p tags (most reliable for news)
        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text() for p in paragraphs])
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        if len(text) < 100: # Too short, likely failed
            return None
            
        return text[:3000] # Limit to 3000 chars
        
    except Exception as e:
        # print(f"Error scraping {url}: {e}")
        return None

def analyze_news_with_gemini(news_items, api_key):
    if not news_items:
        return {}, "No news items to analyze."
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Analyze ALL provided items (Filtering happens based on score later)
    # Limit max just in case (e.g. 10)
    limited_news_items = news_items[:10] 
    
    aggregated_topics = []
    total_items = len(limited_news_items)
    print(f"Starting sequential analysis for {total_items} items...")

    for idx, item in enumerate(limited_news_items):
        print(f"[{idx+1}/{total_items}] Processing: {item['title']}...")
        
        # 1. Try to get FULL content
        full_content = fetch_full_content(item['link'])
        
        if not full_content:
            print("   -> Scraping failed/empty, falling back to summary.")
            full_content = clean_html(item['summary'])[:800]
        else:
            print(f"   -> Scraped full content ({len(full_content)} chars).")

        # Single Item Prompt
        prompt = f"""
        당신은 태국 방콕에 주재하는 '베테랑 한국 특파원'입니다.
        입력된 기사를 분석하여 한국 여행자에게 필요한 정보를 추출하고 중요도를 평가하세요.

        [기사 정보]
        - Title: {item['title']}
        - Source: {item['source']}
        - Link: {item['link']}
        
        [기사 본문]
        {full_content}

        [작성 요구사항]
        1. **Tourist Impact Score (중요도 평가):** (1~10점)
           - **7~10점 (필수):** 여행객 안전 위협(시위, 홍수, 범죄), 비자/입국 규정 변경, 대형 축제, 공항 혼잡.
           - **4~6점 (보통):** 새로운 핫플, 일반적인 날씨, 소소한 규제, 흥미로운 로컬 뉴스.
           - **1~3점 (무시):** 단순 정치 싸움, 연예인 가십, 여행과 무관한 지역 사회 뉴스.
        
        2. **헤드라인 & 요약 (Strict Format):** 
           - **반드시 '3줄 요약' (Bullet Point) 형식**으로 작성하세요. (각 줄은 '- '로 시작)
           - 한국인이 관심 가질만한 핵심 내용만 간결하게 포함하세요.
           - **주의:** '중요도 점수'나 '여행객 영향'에 대한 메타 설명은 요약문에 절대 포함하지 마세요. (별도 필드 이용)

        3. **분류:** ["정치/사회", "경제", "여행/관광", "축제/이벤트", "사건/사고", "엔터테인먼트", "기타"]
           - 날씨/홍수는 무조건 '여행/관광' 또는 Safety 이슈면 '사건/사고'.
        
        4. **이벤트 상세 (만약 '축제/이벤트'라면):**
           - 장소, 날짜, 가격을 명확히 추출. 불확실하면 null.
           - `location_google_map_query`: 구글 맵 영어 검색어.

        [출력 포맷 (JSON Only)]
        {{
          "topics": [
            {{
              "title": "기사 제목",
              "summary": "3줄 요약",
              "full_translated": "기사 전문 (Markdown)",
              "category": "카테고리",
              "tourist_impact_score": 0,  // Integer
              "impact_reason": "점수 부여 사유",
              "event_info": {{
                  "date": "YYYY-MM-DD or Range",
                  "location": "...", 
                  "price": "...",
                  "location_google_map_query": "..."
              }},
              "references": [
                {{"title": "{item['title']}", "url": "{item['link']}", "source": "{item['source']}"}}
              ]
            }}
          ]
        }}
        """
        
        # Retry Logic with Safety Limits
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
                response = model.generate_content(prompt)
                # Force HTTPS for all URLs in the generated content (Markdown links, Image URLs, References)
                safe_text = response.text.replace("http://", "https://")
                result = json.loads(safe_text)
                
                if 'topics' in result and result['topics']:
                    # --- Python Verification (Strict Mode Enforcement) ---
                    for topic in result['topics']:
                        if topic.get('category') == '축제/이벤트':
                            evt = topic.get('event_info')
                            # Check strict conditions
                            if not evt or not evt.get('location') or not evt.get('date') or not evt.get('price'):
                                print(f"   -> [Strict Mode] Downgrading '{topic['title']}' from Event to Travel News (Missing Info)")
                                topic['category'] = '여행/관광'
                                topic['event_info'] = None # Clear it
                            elif evt.get('location') == 'Unknown' or evt.get('location') == 'null':
                                 print(f"   -> [Strict Mode] Downgrading '{topic['title']}' (Location Unknown)")
                                 topic['category'] = '여행/관관'
                                 topic['event_info'] = None

                    aggregated_topics.extend(result['topics'])
                    print(f"   -> Success. Topics so far: {len(aggregated_topics)}")
                    success = True
                else:
                    raise ValueError("Empty topics in response")
                
            except Exception as e:
                retry_count += 1
                wait_time = 2 ** retry_count # Exponential backoff: 2s, 4s, 8s
                print(f"   -> API Error for item {idx+1} (Attempt {retry_count}/{max_retries}): {e}")
                
                if "429" in str(e):
                    print("   -> Rate Limit Hit. Waiting longer...")
                    time.sleep(60) # Special wait for Rate Limit
                elif retry_count < max_retries:
                    print(f"   -> Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print("   -> Max retries reached. Skipping this item.")
            
        # Delay logic (except for the last one)
        if idx < total_items - 1:
            print("   -> Waiting 20 seconds to respect API rate limits...")
            time.sleep(20)

    return {"topics": aggregated_topics}, None


def load_local_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


# 3. Exchange Rate (THB -> KRW)
def get_thb_krw_rate():
    """
    Fetches the current THB to KRW exchange rate.
    Uses 'data/exchange_rate.json' for persistence.
    """
    RATE_FILE = 'data/exchange_rate.json'
    url = "https://api.frankfurter.app/latest?from=THB&to=KRW"
    
    # helper to save
    def save_rate(rate):
        try:
            with open(RATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"rate": rate, "updated_at": str(datetime.now())}, f)
        except: pass

    # helper to load
    def load_cached_rate():
        if os.path.exists(RATE_FILE):
            try:
                with open(RATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("rate")
            except: pass
        return None

    try:
        import requests
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rate = data.get('rates', {}).get('KRW')
            if rate:
                save_rate(rate)
                return rate
    except Exception as e:
        print(f"Exchange Rate Error: {e}")
    
    # Fallback to cached rate if live fetch fails
    cached = load_cached_rate()
    if cached:
        return cached
        
    # If absolutely no data (first run ever & fail), return None or handled by UI
    return 0.0

# 4. Air Quality (WAQI)
def get_air_quality(token):
    """
    Fetches real-time Air Quality (PM 2.5) for Bangkok.
    Returns:
        dict: {'aqi': int, 'status': str} or None if failed.
    """
    url = f"https://api.waqi.info/feed/bangkok/?token={token}"
    try:
        import requests
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok':
                aqi = data['data']['aqi']
                return {'aqi': aqi}
    except Exception as e:
        print(f"Air Quality Error: {e}")
    
    return None



def fetch_thai_events():
    """
    Fetches and parses event information from ThaiTicketMajor, BK Magazine, and TAT News using Gemini.
    Returns:
        list: A list of event dictionaries (title, date, location, region, image_url, link, type).
    """
    print("Fetching Thai Events (National)...")
    
    targets = [
        {
            "name": "ThaiTicketMajor",
            "url": "https://www.thaiticketmajor.com/concert/",
            "selector": "body"
        },
        {
            "name": "BK Magazine",
            "url": "https://bk.asia-city.com/things-to-do-bangkok",
            "selector": "div.view-content"
        },
        {
            "name": "TAT News",
            "url": "https://www.tatnews.org/category/events-festivals/",
            "selector": "body"
        }
    ]

    combined_html_context = ""

    for target in targets:
        try:
            print(f" - Requesting {target['name']}...")
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(target['url'], headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract relevant part
                content = soup.select_one(target['selector'])
                if not content:
                     content = soup.body
                
                # Kill scripts
                for s in content(["script", "style", "nav", "footer", "header"]):
                    s.extract()
                
                html_snippet = str(content)[:20000] # Increased limit for TAT
                
                combined_html_context += f"\n\n--- Source: {target['name']} ({target['url']}) ---\n{html_snippet}"
                
        except Exception as e:
            print(f"Error fetching {target['name']}: {e}")

    if not combined_html_context:
        return []

    # Gemini Processing
    try:
        # Load API Key (Handle Env vs Secrets)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
             try:
                import toml
                secrets = toml.load(".streamlit/secrets.toml")
                api_key = secrets.get("GEMINI_API_KEY")
             except:
                pass
        
        if not api_key:
            return []

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        prompt = f"""
        You are a helpful event curator for Korean tourists visiting Thailand.
        Analyze the following HTML snippets from event websites (ThaiTicketMajor, BK Magazine, TAT News).
        Extract a list of distinct events/festivals across Thailand.
        
        Current Date: {today_str}
        
        CRITICAL: Identify the **REGION** (City/Province) based on the location info.
        - If "Chiang Mai" -> "치앙마이"
        - If "Phuket" -> "푸켓"
        - If "Pattaya" -> "파타야"
        - If "Bangkok" -> "방콕"
        - If "Koh Samui" -> "코사무이"
        - If unknown or miscellaneous, default to "기타" (Others) or "방콕" if mostly likely Bangkok.
        
        Return the result ONLY as a JSON list of objects.
        
        JSON Format:
        [
            {{
                "title": "Event Name (Summarize in Korean, e.g. '송크란 축제')",
                "date": "YYYY-MM-DD or Date Range String (e.g. '2024-04-13 ~')",
                "location": "Venue Name (in Korean or English)",
                "region": "방콕/치앙마이/푸켓/파타야/기타",
                "image_url": "Full URL of the event poster/image",
                "link": "Full URL to booking page or article",
                "booking_date": "YYYY-MM-DD HH:MM (Ticket Open Time) or 'Now Open' or 'TBD'",
                "price": "Exact Price (e.g. '3,000 THB') or range",
                "type": "축제" or "콘서트" or "전시" or "기타"
            }}
        ]

        Rules:
        1. Select 8-12 diverse items (Mix of Concerts, Festivals, Exhibitions).
        2. CRITICAL: EXCLUDE events that ended BEFORE {today_str}. Only show current or future events.
        3. CRITICAL: If you see a date from a past year (e.g. 2024 if today is 2026, or 2017, 2018...), IGNORE IT. Do not output old events.
        4. Prefer events happening soon (next 45 days).
        3. Ensure image_url is absolute.
        4. Output strictly JSON.
        
        HTML Context:
        {combined_html_context}
        """
        
        print(" - Sending to Gemini...")
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        data = json.loads(text)
        print(f" - Parsed {len(data)} events with Region info.")
        return data

    except Exception as e:
        print(f"Gemini processing error: {e}")
        return []

def extract_event_from_url(url, api_key):
    """
    Scrapes a URL and uses Gemini to extract event details.
    Returns a dict with processed event info.
    """
    try:
        # 1. Scrape Content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
             'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Remove scripts/styles
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text_content = soup.get_text(separator=' ', strip=True)[:15000] # Limit context
        
        # Try to find OG Image
        og_image = ""
        meta_img = soup.find("meta", property="og:image")
        if meta_img:
            og_image = meta_img.get("content", "")
            
        title_guess = soup.title.string if soup.title else ""

        # 2. Gemini Analysis
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        Analyze the following webpage text and extract event information.
        
        URL: {url}
        Page Title: {title_guess}
        Text Content:
        {text_content}
        
        Goal: Extract details for a "Big Match" event (Festival/Concert).
        
        Output JSON Format:
        {{
            "title": "Event Name (Korean, e.g. '롤링라우드 태국 2024')",
            "date": "YYYY-MM-DD or Range (e.g. '2024-11-22 ~ 11-24')",
            "location": "Venue Name (Korean/English)",
            "region": "One of: ['방콕', '파타야', '치앙마이', '푸켓', '기타']",
            "type": "One of: ['축제', '콘서트', '전시', '클럽/파티', '기타']",
            "booking_date": "Ticket Open Date (YYYY-MM-DD HH:MM) or 'Now Open'",
            "price": "Exact Price (e.g. '3,000 THB') or Range",
            "status": "One of: ['티켓오픈', '개최확정', '매진', '정보없음']",
            "image_url": "Use existing OG Image if valid, or find one in text. If none, return empty string.",
            "description": "1 line summary in Korean"
        }}
        
        If image_url is missing in text, use this one: {og_image}
        
        Translate all text to natural Korean.
        If information is missing, use "정보없음" or "" (empty string).
        """
        
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        
        # Parse JSON
        if "```json" in text_response:
            text_response = text_response.replace("```json", "").replace("```", "")
        if text_response.startswith("```"): # Catch raw block
            text_response = text_response.replace("```", "")
        
        data = json.loads(text_response)
        data['link'] = url # Ensure link is set
        
        # Safety fallback for image
        if not data.get('image_url') and og_image:
            data['image_url'] = og_image
            
        return data, None
        
    except Exception as e:
        return None, str(e)

def fetch_big_events_by_keywords(keywords, api_key):
    """
    Crawls Google News RSS (Thailand Locale) for keywords and critically verifies details with Gemini.
    """
    import feedparser
    import urllib.parse
    
    found_events = []
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    for kw in keywords:
        print(f"Checking keyword: {kw}")
        encoded_kw = urllib.parse.quote(kw)
        # Use Thailand Locale (en-TH)
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-TH&gl=TH&ceid=TH:en"
        
        feed = feedparser.parse(rss_url)
        
        # Check top 2 entries (efficient)
        entries_to_check = feed.entries[:2]
        if not entries_to_check:
            continue
            
        # Aggregate text for analysis
        combined_text = f"Target Event: {kw}\n"
        for i, entry in enumerate(entries_to_check):
            combined_text += f"[{i+1}] Title: {entry.title}\nLink: {entry.link}\nSummary: {entry.get('summary','')}\nPubDate: {entry.get('published','')}\n\n"
            
        prompt = f"""
        Analyze these news search results for the event "{kw}" in Thailand.
        
        News Content:
        {combined_text}
        
        Goal: Determine if there is CONFIRMED information about the NEXT event date and venue.
        
        CRITICAL VALIDATION RULES:
        1. **CONFIRMED ONLY**: Do NOT extract if it's just a "rumor", "expected to be", "in talks", or from a past year.
        2. **Future Only**: Date must be in the future (2025-2027).
        3. **Specifics**: You must find BOTH a specific date (or confirmed month) AND a venue/city.
        
        If the event is NOT confirmed or is just a rumor:
        Return JSON: {{ "found": false, "reason": "Just a rumor or no data" }}

        If CONFIRMED:
        Return JSON:
        {{
            "found": true,
            "title": "Event Name (Korean)",
            "date": "YYYY-MM-DD or Range",
            "location": "Venue Name",
            "booking_date": "Ticket Open Date (YYYY-MM-DD HH:MM) or 'TBD'",
            "price": "Exact Price (e.g. '3,000 THB') or Range",
            "status": "개최확정", 
            "link": "Best Link URL from the news",
            "description": "1 line confirmed summary in Korean"
        }}
        """
        
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if "```json" in text:
                text = text.replace("```json", "").replace("```", "")
            if text.startswith("```"):
                text = text.replace("```", "")
                
            data = json.loads(text)
            
            if data.get('found'):
                # Basic validation
                if '201' in data.get('date',''): 
                     pass
                else:
                    found_events.append(data)
            else:
                print(f" -> {kw}: Not confirmed ({data.get('reason')})")
                    
        except Exception as e:
            print(f"Error analyzing {kw}: {e}")
            
    return found_events

# --------------------------------------------------------------------------------
# Trend Hunter (Magazine) Logic - 4 Sources
# --------------------------------------------------------------------------------

def fetch_trend_hunter_items(api_key, existing_links=None):
    """
    Aggregates trend/travel content via Google News RSS for 4 sources:
    1. Wongnai (Restaurants)
    2. TheSmartLocal TH (Hotspots)
    3. Chillpainai (Local Travel)
    4. BK Magazine (BKK Life)
    
    Returns:
        list: shuffled list of dicts {title, desc, location, image_url, link, badge}
    """
    import random
    import requests
    import feedparser
    
    print("Fetching Trend Hunter items via Google News RSS...")
    
    items = []
    if existing_links is None:
        existing_links = set()
    else:
        existing_links = set(existing_links)
        
    seen_links = set() # Local deduplication
    
    # Target Domains (Loaded from sources.json)
    SOURCES_FILE = 'data/sources.json'
    targets = []
    
    # 1. Try Loading from File
    if os.path.exists(SOURCES_FILE):
        try:
            with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                s_data = json.load(f)
                if s_data.get('magazine_targets'):
                    # Filter enabled only
                    targets = [t for t in s_data['magazine_targets'] if t.get('enabled', True)]
        except Exception as e:
            print(f"Error loading sources.json: {e}")
            
    # 2. Fallback if empty (Hardcoded defaults)
    if not targets:
        print("Using default magazine targets (Fallback).")
        targets = [
            {"name": "Wongnai", "domain": "wongnai.com", "tag": "[맛집랭킹]"},
            {"name": "Chillpainai", "domain": "chillpainai.com", "tag": "[로컬여행]"},
            {"name": "BK Magazine", "domain": "bk.asia-city.com", "tag": "[방콕라이프]"},
            {"name": "The Smart Local", "domain": "thesmartlocal.co.th", "tag": "[MZ핫플]"}
        ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Helper: Gemini Analyzer
    def analyze_rss_items(raw_inputs, source_tag):
        if not raw_inputs: return []
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            prompt = f"""
            You are a expert Korean Travel Editor acting as a **"Hotplace Detector"**.
            Your goal is to filter and rewrite RSS items into high-quality **Korean** magazine content.
            
            Input Data ({source_tag}):
            {json.dumps(raw_inputs, ensure_ascii=False)}
            
            **CRITICAL FILTERING RULES (Hotplace Detector)**:
            Analyze each item. If an item falls into any of these categories, **return null** for that item instead of a JSON object:
            1. **Not a specific visitable place**: General news, flight promos, "Thai Trip" general guides, or listicles without a clear focus.
            2. **Vague/Ad**: Content that sounds like a generic advertisement or lacks specific details.
            3. **No Image**: If you cannot infer a strong visual context or the input lacks an image.
            
            **REWRITE INSTRUCTIONS (For valid items)**:
            1. **LANGUAGE**: Natural, witty, trendy **Korean**.
            2. **INFERENCE**: Infer details (Vibe, Menu, Tips) from context.
            3. **FIELDS**:
               - "catchy_headline": Click-bait style 1-liner in Korean.
               - "desc": 2-3 sentences summary (Focus on why it's hot).
               - "location": Infer Area (e.g. 'Thong Lor', 'Siam').
               - "badge": Use "{source_tag}"
            
            Return JSON List of objects (excluding nulls).
            Example:
            [
                }},
                null,
                ...
            ]
            """
            
            response = model.generate_content(prompt)
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            
            processed = []
            for res in data:
                if not res: continue # Skip null items (filtered)
                
                idx = res.get('original_index')
                if idx is not None and idx < len(raw_inputs):
                    original = raw_inputs[idx]
                    res['image_url'] = original.get('raw_img') 
                    res['link'] = original.get('raw_link')
                    res['badge'] = source_tag
                    processed.append(res)
            return processed
        except Exception as e:
            print(f"Analysis Error ({source_tag}): {e}")
            return []

    # Main Loop
    for target in targets:
        try:
            # Google News RSS URL (Reduced restriction)
            rss_url = f"https://news.google.com/rss/search?q=site:{target['domain']}&hl=en-TH&gl=TH&ceid=TH:en"
            print(f"Reading RSS: {target['name']}...")
            
            resp = requests.get(rss_url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            
            raw_items = []
            # Check up to 10 entries to find 2 valid ones
            for entry in feed.entries[:10]:
                if len(raw_items) >= 2: break
                
                # 1. Deduplication (Link & Title)
                if entry.link in existing_links or entry.link in seen_links:
                    print(f"Skipping duplicate: {entry.title}")
                    continue
                
                # 2. Chillpainai Filter
                if target['name'] == "Chillpainai" and "Thai Trip" in entry.title:
                    print(f"Skipping Chillpainai 'Thai Trip': {entry.title}")
                    continue

                seen_links.add(entry.link)
                
                # Attempt to find image
                img_src = ""
                if 'media_content' in entry:
                    img_src = entry.media_content[0]['url']
                elif 'description' in entry:
                     import re
                     match = re.search(r'src="([^"]+)"', entry.description)
                     if match: img_src = match.group(1)
                
                raw_items.append({
                    "raw_title": entry.title,
                    "raw_link": entry.link,
                    "raw_img": img_src,
                    "context": f"Latest article from {target['name']}"
                })
            
            if raw_items:
                analyzed = analyze_rss_items(raw_items, target['tag'])
                items.extend(analyzed)
                
        except Exception as e:
            print(f"Error fetching {target['name']}: {e}")

    # Shuffle for Magazine feel
    random.shuffle(items)
    return items

def push_changes_to_github(files_to_commit, commit_message):
    """
    Commits and pushes specified files to GitHub.
    Requires GITHUB_TOKEN in secrets.toml or environment.
    """
    import subprocess
    import toml
    
    # 1. Get Token
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            secrets = toml.load(".streamlit/secrets.toml")
            token = secrets.get("GITHUB_TOKEN")
        except: pass
    
    if not token:
        return False, "GITHUB_TOKEN not found in secrets."

    # 2. Configure Git (If needed)
    # Check if user is set
    try:
        subprocess.run("git config user.name", shell=True, check=True, capture_output=True)
    except:
        subprocess.run('git config user.email "auto-deploy@streamlit.app"', shell=True)
        subprocess.run('git config user.name "Streamlit Admin"', shell=True)

    try:
        # 3. Add Files
        for f in files_to_commit:
            subprocess.run(f"git add {f}", shell=True, check=True)
            
        # 4. Commit
        subprocess.run(f'git commit -m "{commit_message}"', shell=True, check=True)
        
        # 5. Push
        # Use token in URL for auth
        repo_url = subprocess.check_output("git remote get-url origin", shell=True, text=True).strip()
        
        if "https://" in repo_url:
            auth_url = repo_url.replace("https://", f"https://{token}@")
        else:
            auth_url = repo_url
            
        subprocess.run(f"git push {auth_url} HEAD:main", shell=True, check=True)
        
        return True, "Successfully pushed to GitHub!"
        
    except subprocess.CalledProcessError as e:
        return False, f"Git Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


# --------------------------------------------------------------------------------
# Visitor Counter (counterapi.dev)
# --------------------------------------------------------------------------------

# --------------------------------------------------------------------------------
# Visitor Counter (counterapi.dev)
# --------------------------------------------------------------------------------

def get_visitor_stats():
    """
    Fetches both Total and Daily visitor counts.
    Returns: (total_count, daily_count)
    """
    try:
        import requests
        from datetime import datetime
        
        namespace = "today-thailand-app"
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Keys
        key_total = f"total"
        key_daily = f"date_{today_str}"
        
        # 1. Get Total
        total_val = 0
        try:
            url_total = f"https://api.counterapi.dev/v1/{namespace}/{key_total}"
            r1 = requests.get(url_total, timeout=2)
            if r1.status_code == 200:
                total_val = r1.json().get("count", 0)
        except: pass
        
        # 2. Get Daily
        daily_val = 0
        try:
            url_daily = f"https://api.counterapi.dev/v1/{namespace}/{key_daily}"
            r2 = requests.get(url_daily, timeout=2)
            if r2.status_code == 200:
                daily_val = r2.json().get("count", 0)
        except: pass
            
        return total_val, daily_val
        
    except:
        return 0, 0

def increment_visitor_stats():
    """
    Increments both Total and Daily counts (once per session).
    Returns: (new_total, new_daily)
    """
    try:
        import requests
        from datetime import datetime
        
        namespace = "today-thailand-app"
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Keys
        key_total = f"total"
        key_daily = f"date_{today_str}"
        
        # 1. Hit Total (+1)
        total_val = 0
        try:
            url_total = f"https://api.counterapi.dev/v1/{namespace}/{key_total}/up"
            r1 = requests.get(url_total, timeout=2)
            if r1.status_code == 200:
                total_val = r1.json().get("count", 0)
        except: pass
        
        # 2. Hit Daily (+1)
        daily_val = 0
        try:
            url_daily = f"https://api.counterapi.dev/v1/{namespace}/{key_daily}/up"
            r2 = requests.get(url_daily, timeout=2)
            if r2.status_code == 200:
                daily_val = r2.json().get("count", 0)
        except: pass
        
        return total_val, daily_val
        
    except:
        return 0, 0

# --------------------------------------------------------------------------------
# Twitter Trend Analyzer (trends24.in + Gemini)
# --------------------------------------------------------------------------------
def fetch_twitter_trends(api_key):
    """
    Scrapes trends24.in/thailand/ for top 10 hashtags and analyzes them with Gemini.
    Returns: dict { "topic": "...", "reason": "...", "severity": "info" } or None
    """
    import requests
    from bs4 import BeautifulSoup
    import google.generativeai as genai
    import json
    
    url = "https://trends24.in/thailand/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print("Fetching Twitter Trends from trends24.in...")
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # trends24 structure: .trend-card__list (first one is latest) -> li -> a
        trend_list = soup.select('.trend-card__list')
        
        if not trend_list:
            print("No trend list found.")
            return None
            
        # Get top 10 from the most recent hour (first list)
        top_trends = []
        for li in trend_list[0].find_all('li')[:10]:
            top_trends.append(li.get_text(strip=True))
            
        if not top_trends:
            return None
            
        print(f"Top 10 Trends: {top_trends}")
        
        # Analyze with Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        Analyze these real-time Thailand Twitter trends:
        {json.dumps(top_trends, ensure_ascii=False)}
        
        Goal: Identify if there is ANY critical or useful information for a FOREIGN TRAVELER in Bangkok/Thailand right now.
        
        Criteria:
        1.  **Critical**: Protests, Riots, Severe Weather (Floods), Transport Chaos (BTS/MRT breakdowns), Major Accidents.
        2.  **Useful**: K-Pop Star arrival (Airport crowds), Major Festival occurring NOW.
        3.  **Ignore**: Political gossip, Celebrity dating rumors, Fan-wars, TV show hashtags.
        
        Output JSON (Return null if nothing important):
        {{
            "topic": "Keyword or Hashtag",
            "reason": "1 simple sentence in KOREAN explaining the situation for a tourist. (e.g. '시위로 인해 시암 지역이 혼잡하니 피하세요')",
            "severity": "warning" (for danger/disruption) or "info" (for events/crowds)
        }}
        
        * If multiple issues, pick the MOST critical one.
        * If nothing relevant, return null.
        """
        
        response = model.generate_content(prompt)
        result_text = response.text.strip().replace("```json", "").replace("```", "")
        
        # specific handling for null
        if "null" in result_text.lower() and len(result_text) < 10:
             return None
             
        data = json.loads(result_text)
        
        # Add Collection Time (Bangkok Time)
        import pytz
        from datetime import datetime
        bkk = pytz.timezone('Asia/Bangkok')
        now_bkk = datetime.now(bkk)
        
        data['collected_at'] = now_bkk.strftime("%Y-%m-%d %H:%M:%S")
        
        return data


    except Exception as e:
        print(f"Twitter Trend Error: {e}")
        return None

# --------------------------------------------------------
# Hotel Fact Check Features
# --------------------------------------------------------
import streamlit as st # Added for user requested st.error/st.warning

def fetch_hotel_candidates(hotel_name, city, api_key):
    """
    Step 1: Search for potential hotels (Candidates).
    Returns: List of dicts [{'id':..., 'name':..., 'address':...}] or None
    """
    # 1. Query Expansion (Removed forced 'Hotel' suffix)
    # Why? 'Centara' + 'Hotel' -> strictly matches 'Centara Hotel' (budget branch),
    # obscuring 'Centara Grand Mirage' (Resort).
    # Google Places TextSearch handles "Brand in City" better without forced suffixes.
    
    hotel_name = hotel_name.strip()
    
    # 2. Construct Query
    # Detect Korean to optimize query structure
    import re
    is_korean = bool(re.search(r'[가-힣]', hotel_name))
    
    if is_korean:
         # 2-1. Brand Mapping (Korean -> English) for higher accuracy
         # Google Maps works significantly better with English brand names.
         brand_map = {
             "센타라": "Centara",
             "아마리": "Amari",
             "힐튼": "Hilton",
             "하얏트": "Hyatt",
             "메리어트": "Marriott",
             "쉐라톤": "Sheraton",
             "홀리데이인": "Holiday Inn",
             "아난타라": "Anantara",
             "아바니": "Avani",
             "두짓타니": "Dusit Thani",
             "노보텔": "Novotel",
             "르메르디앙": "Le Meridien",
             "소피텔": "Sofitel",
             "풀만": "Pullman",
             "인터컨티넨탈": "InterContinental",
             "반얀트리": "Banyan Tree",
             "샹그릴라": "Shangri-La",
             "켐핀스키": "Kempinski",
             "카펠라": "Capella",
             "포시즌스": "Four Seasons",
             "세인트레지스": "St. Regis",
             "더스탠다드": "The Standard"
         }
         
         # Check if hotel_name starts with or contains a known brand
         english_brand = None
         for kr_brand, en_brand in brand_map.items():
            if kr_brand in hotel_name:
                # Replace Korean Brand with English Brand in the query
                # e.g. "센타라" -> "Centara"
                # e.g. "센타라 그랜드" -> "Centara 그랜드" (Mixed is fine, but pure English is best)
                # Let's just switch to English mode if it's a pure brand query
                if hotel_name.strip() == kr_brand:
                    hotel_name = en_brand
                    is_korean = False # Switch to English Logic
                else:
                    # Mixed case: "센타라 리조트" -> replace '센타라' with 'Centara'
                    hotel_name = hotel_name.replace(kr_brand, en_brand)
                    # Keep is_korean = True for now unless we are sure, 
                    # but actually "Centara 리조트" is better searched as "Centara Resort" (English logic handles mixed okay?)
                    # Let's try to trust the English Logic if we have English Name now.
                    # Actually better to treat as English-ish if we injected English Brand.
                    pass 
                break
    
    if is_korean:
         # Korean Fallback: Revert to Broad Search (No 'Hotel Resort' force)
         # 'Hotel Resort' keyword excluded pure Hotels (e.g. Centara Nova).
         # Broad search 'Name City Thailand' is safest for unmapped brands.
         search_query = f"{hotel_name} {city} Thailand"
    else:
         # English (or Mapped English): Use 'in' logic
         search_query = f"{hotel_name} in {city}, Thailand"
    
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"
    }
    # Limit to 10 candidates
    payload = {
        "textQuery": search_query,
        "maxResultCount": 20
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            # st.error(f"🚨 API 호출 실패: {response.status_code}")
            return None
            
        data = response.json()
        
        if not data.get("places"):
            return [] 
            
        # Extract meaningful candidates (Increased to 10)
        candidates = []
        for p in data["places"][:10]:
            candidates.append({
                "id": p["id"],
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", "")
            })
        return candidates

    except Exception as e:
        st.error(f"시스템 오류 발생: {e}")
        return None

def fetch_hotel_details(place_id, api_key):
    """
    Step 2: Fetch full details for a specific Place ID.
    Returns: place_dict or None
    """
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews,photos"
    }
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            st.error(f"상세 정보 조회 실패: {resp.text}")
            return None
            
        place = resp.json()
        
        # Photo handling
        photo_url = None
        if place.get("photos"):
            photo_ref = place["photos"][0]["name"]
            photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=800&maxWidthPx=800&key={api_key}"

        return {
            "name": place.get("displayName", {}).get("text", "Unknown"),
            "address": place.get("formattedAddress", ""),
            "rating": place.get("rating", 0.0),
            "review_count": place.get("userRatingCount", 0),
            "reviews": place.get("reviews", []),
            "photo_url": photo_url
        }
    except Exception as e:
        st.error(f"상세 정보 처리 중 오류: {e}")
        return None

def analyze_hotel_reviews(hotel_name, rating, reviews, api_key):
    """
    Analyze hotel reviews using Gemini with a specific 'Cold Inspector' persona.
    """
    try:
        # 1. Prepare Review Text
        reviews_text = ""
        for r in reviews[:5]: # Use top 5 reviews
             text = r.get("text", {}).get("text", "")
             if text:
                 reviews_text += f"- {text}\n"

        # 2. Gemini Prompt
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})

        prompt = f"""
        너는 '냉철한 호텔 검증가'야. 사용자가 이 호텔을 **"실제로 예약할지 말지"** 결정할 수 있도록, 광고 멘트는 빼고 오직 **팩트와 실제 후기**에 기반해서 분석해줘.

        **[분석 대상]**
        * 호텔명: {hotel_name} (평점: {rating})
        * 구글 맵 최신 리뷰 데이터: {reviews_text}
        * **추가 지식:** 위 리뷰 외에도, 네가 이미 학습해서 알고 있는 이 호텔의 특징(위치, 브랜드 평판, 수영장, 조식 스타일 등)을 총동원해.

        **[단점(Cons) 작성 절대 규칙 - 위반 시 오답 처리]**
        1. 🔇 **'없음' 중계 금지:** "소음 관련 언급 없음", "수압 정보 부족", "조식 불만 없음" 같이 **데이터가 없다는 사실을 적지 마.** 사용자는 '진짜 문제점'만 궁금해해.
        2. 🎯 **오직 '존재하는 불만'만:** 실제 리뷰나 데이터에서 **"시끄럽다", "더럽다", "맛없다", "멀다"** 처럼 명확하게 지적된 부정적 키워드가 있을 때만 적어.
        3. 🛡️ **빈 칸 처리:** 만약 위 기준으로 분석했을 때 **명확한 단점이 하나도 없다면**, 억지로 만들어내지 말고 딱 한 줄만 적어:
           👉 "특별한 단점이 발견되지 않았습니다. (전반적으로 우수한 평가)"
        4. **금지 예시:** "위치 관련 정보 부족" (X), "한국인 입맛 확인 필요" (X)

        **[비추천(Not Recommended) 작성 가이드 - 기계적 멘트 금지]**
        1. 🚫 **금지 표현:** "단점에 예민한 사람", "완벽함을 추구하는 사람", "불편함을 싫어하는 사람" 같은 뻔한 말은 쓰지 마.
        2. ✅ **구체적 조건 명시:** 비추천 대상은 반드시 **가격, 소음, 위치, 감성** 등 구체적 이유와 연결돼야 해.
           - (소음) 👉 "잠귀가 밝거나 조용한 휴식을 최우선으로 하는 여행객"
           - (위치) 👉 "지하철역까지 도보 이동을 선호하는 뚜벅이 여행객"
           - (청결) 👉 "위생 상태에 민감하거나 아이와 함께하는 가족 여행객"
        3. **단점이 없을 때:** 억지로 단점을 찾지 말고 **'가격'**이나 **'여행 목적'**을 언급해.
           - (비싼 호텔) 👉 "가성비를 중요하게 생각하는 알뜰 여행객"
           - (파티 호텔) 👉 "조용한 힐링을 원하는 휴양 목적 여행객"

        **[출력 포맷 (JSON)]**
        응답은 반드시 아래 JSON 형식을 지켜줘.

        {{
            "name_eng": "Trip.com 등 OTA에서 사용하는 호텔의 '정식 영문 풀네임' (예: Centara Grand at CentralWorld)",
            "trip_keyword": "트립닷컴 검색용 '한국어' 핵심 키워드 (도시/국가명 제거, 브랜드+지점명만 남김. 예: 아마리 워터게이트)",
            "price_level": "💰 or 💰💰 or 💰💰💰 or 💰💰💰💰 (1~4단계, 저렴/보통/비쌈/초호화)",
            "price_range_text": "한국 원화 기준 예상 1박 요금 (예: 약 120,000원 ~ 180,000원, 시즌 변동 가능)",
            "one_line_verdict": "한 줄 결론 (예: 위치는 깡패지만 귀마개 필수인 가성비 호텔)",
            "recommendation_target": "추천: 긍정적인 서비스 경험을 중시하는 여행객, 비추천: 호텔의 성격(가격·분위기·위치)과 반대되는 여행자",
            "location_analysis": "위치 및 동선 (역과의 거리, 주변 편의점/마사지샵, 치안, 도보 난이도)",
            "room_condition": "객실 디테일 (청결도, 침구, 습기/냄새, 소음, 벌레, 뷰)",
            "service_breakfast": "서비스 및 조식 (직원 친절도, 조식 메뉴 구성 및 맛, 한국인 입맛 적합도)",
            "pool_facilities": "수영장 및 부대시설 (수영장 크기/수질/그늘 여부, 헬스장 등)",
            "pros": ["장점1 (구체적 근거)", "장점2", "장점3", "장점4", "장점5"],
            "cons": ["단점1 (치명적인 부분)", "단점2", "단점3", "단점4", "단점5"],
            "summary_score": {{
                "cleanliness": 0,  // 5점 만점 (정수)
                "location": 0,
                "comfort": 0,
                "value": 0
            }}
        }}
        """
        
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        return {"error": str(e)}

# --------------------------------------------------------------------------------
# Infographic Generator (PIL based)
# --------------------------------------------------------------------------------
def ensure_font_loaded():
    """
    Downloads NanumGothic font if not present.
    Returns path to font file.
    """
    FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
    FONT_PATH = "data/NanumGothic-Bold.ttf"
    
    if not os.path.exists(FONT_PATH):
        try:
            print("Downloading font for Infographic...")
            import requests
            r = requests.get(FONT_URL, timeout=10)
            with open(FONT_PATH, 'wb') as f:
                f.write(r.content)
            print("Font downloaded.")
        except Exception as e:
            print(f"Font download failed: {e}")
            return None # Fallback to default
            
    return FONT_PATH

def prettify_infographic_text(category, items, api_key):
    """
    Uses Gemini to shorten news into 'Emoji + One-liner' format.
    """
    if not items: return []
    
    # Cost optimization: If API Key missing, just use titles
    if not api_key:
        return [f"📰 {item['title']}" for item in items[:3]]

    import google.generativeai as genai
    import json
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Simplified inputs
    inputs = "\n".join([f"- {item['title']}" for item in items[:3]])
    
    prompt = f"""
    Convert these 3 news headlines into a "Social Media Infographic" style (Korean).
    Category: {category}
    
    Input:
    {inputs}
    
    Goal: Return a JSON list of strings. Each string must start with a relevant Emoji and be very short (max 20 chars).
    Example: ["🚨 시암 파라곤 총격 발생", "⛈️ 내일 방콕 홍수 주의", "🎉 송크란 축제 일정 발표"]
    
    Output JSON: {{ "lines": ["...", "...", "..."] }}
    """
    
    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip().replace("```json", "").replace("```", "")
        if text.startswith("```"): text = text.replace("```", "")
        data = json.loads(text)
        return data.get("lines", [])
    except:
        # Fallback
        return [f"📰 {item['title'][:18]}..." for item in items[:3]]

def generate_category_infographic(category, items, date_str, api_key):
    """
    Generates a social media image for a specific category.
    """
    from PIL import Image, ImageDraw, ImageFont
    import os
    
    # 1. Config Map (Color & Text)
    # Categories: "정치/사회", "경제", "여행/관광", "사건/사고", "축제/이벤트", "기타"
    theme_map = {
        "정치/사회": {"color": (59, 130, 246), "bg_file": "assets/bg_politics.png", "title": "POLITICS & SOCIAL"}, # Blue
        "경제": {"color": (34, 197, 94), "bg_file": "assets/bg_economy.png", "title": "ECONOMY"}, # Green
        "여행/관광": {"color": (249, 115, 22), "bg_file": "assets/bg_travel.png", "title": "TRAVEL NEWS"}, # Orange
        "사건/사고": {"color": (239, 68, 68), "bg_file": "assets/bg_safety.png", "title": "SAFETY ALERT"}, # Red
        "축제/이벤트": {"color": (236, 72, 153), "bg_file": "assets/bg_travel.png", "title": "THAI EVENTS"}, # Pink
        "기타": {"color": (107, 114, 128), "bg_file": "assets/template.png", "title": "DAILY NEWS"} # Gray
    }
    
    theme = theme_map.get(category, theme_map["기타"])
    
    # 2. Get AI Content
    lines = prettify_infographic_text(category, items, api_key)
    if not lines: return None

    # 3. Setup Canvas (1080x1080 Square for Instagram)
    W, H = 1080, 1080
    
    # Background
    if os.path.exists(theme['bg_file']):
        img = Image.open(theme['bg_file']).convert("RGB")
        img = img.resize((W, H))
    else:
        # Create solid color background with gradient-ish look (simple solid for now)
        img = Image.new('RGB', (W, H), theme['color'])
        # Add a subtle dark overlay for text contrast
        overlay = Image.new('RGBA', (W, H), (0,0,0, 50))
        img.paste(overlay, (0,0), mask=overlay)

    draw = ImageDraw.Draw(img)
    
    # Fonts
    font_path = ensure_font_loaded()
    if not font_path:
        # Emergency fallback (might fail on korean)
        font_cat = ImageFont.load_default()
        font_date = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_footer = ImageFont.load_default()
    else:
        font_cat = ImageFont.truetype(font_path, 60)
        font_date = ImageFont.truetype(font_path, 40)
        font_body = ImageFont.truetype(font_path, 55)
        font_footer = ImageFont.truetype(font_path, 30)
        
    # Draw logic
    # Header: Category Title (English) + Date
    draw.text((80, 80), theme['title'], font=font_cat, fill="white")
    draw.text((80, 160), date_str, font=font_date, fill=(255, 255, 255, 200)) # Alpha 200
    
    # Divider
    draw.line((80, 230, 1000, 230), fill="white", width=4)
    
    # Body Content (Centered vertically-ish)
    start_y = 350
    gap = 120
    
    for i, line in enumerate(lines):
        # Draw badge/bullet?
        # Just text
        draw.text((80, start_y + (i * gap)), line, font=font_body, fill="white")
        
    # Footer
    draw.text((80, 1000), "🇹🇭 오늘의 태국 (Thai Briefing)", font=font_footer, fill=(255, 255, 255, 150))
    
# --------------------------------------------------------------------------------
# Taxi Fare Calculator (Google Maps + Rush Hour Logic)
# --------------------------------------------------------------------------------
def get_route_estimates(origin, destination, api_key):
    """
    Get Distance & Duration using Google Routes API (Compute Routes v2).
    Replaces legacy Directions API.
    Returns: dist_km, dur_min, traffic_ratio, error_message
    """
    if not origin or not destination:
        return None, None, None, "출발지와 목적지를 입력해주세요."
        
    endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    # Prepare Origin/Dest objects
    def build_wp(val):
        if val.startswith("place_id:"):
            return {"placeId": val.split(":")[1]}
        else:
            return {"address": val}
            
    payload = {
        "origin": build_wp(origin),
        "destination": build_wp(destination),
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE", # Important for traffic data
        "computeAlternativeRoutes": False,
        "languageCode": "ko-KR",
        "units": "METRIC"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.staticDuration"
    }
    
    try:
        import requests
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        data = resp.json()
        
        if resp.status_code == 200:
            if not data.get("routes"):
                return None, None, None, "경로를 찾을 수 없습니다."
                
            route = data["routes"][0]
            
            # Distance (meters)
            dist_km = route.get("distanceMeters", 0) / 1000
            
            # Helper to parse "123s" string format
            def parse_duration(dur_str):
                if not dur_str: return 0
                return int(dur_str.replace("s", ""))
                
            # Duration (Real-time with TRAFFIC_AWARE)
            real_dur_sec = parse_duration(route.get("duration", "0s"))
            # Static Duration (No traffic)
            base_dur_sec = parse_duration(route.get("staticDuration", "0s"))
            
            dur_min = real_dur_sec / 60
            
            # Traffic Ratio
            traffic_ratio = 1.0
            if base_dur_sec > 0:
                traffic_ratio = real_dur_sec / base_dur_sec
            
            return dist_km, dur_min, traffic_ratio, None
            
        else:
            # API Error
            err_details = data.get("error", {})
            msg = err_details.get("message", "Unknown Error")
            status = err_details.get("status", resp.status_code)
            return None, None, None, f"Routes API 오류 ({status}): {msg}"
            
    except Exception as e:
        return None, None, None, f"시스템 오류: {e}"

def calculate_expert_fare(dist_km, dur_min, origin_txt="", dest_txt=""):
    """
    Calculates fair prices for various transport modes in Bangkok.
    Now includes Rush Hour Logic & Hell Zone Detection.
    
    Args:
        origin_txt (str): Name/Address of origin (for Hell Zone checking)
        dest_txt (str): Name/Address of dest
    """
    from datetime import datetime, time
    import pytz
    
    # 1. Check Rush Hour (Bangkok Time)
    tz_bkk = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(tz_bkk)
    current_time = now_bkk.time()
    
    is_rush_hour = False
    morning_start = time(7, 0)
    morning_end = time(9, 30)
    evening_start = time(16, 30)
    evening_end = time(20, 0)
    
    if (morning_start <= current_time <= morning_end) or \
       (evening_start <= current_time <= evening_end):
        is_rush_hour = True
        
    # 2. Check Hell Zone (Traffic Hell)
    hell_zones = ["Asok", "Sukhumvit", "Siam", "Sathorn", "Silom", "Thong Lo", "Phrom Phong"]
    chk_str = (str(origin_txt) + " " + str(dest_txt)).lower()
    is_hell_zone = any(z.lower() in chk_str for z in hell_zones)

    # 3. Base Meter Calculation
    # Note: 'dur_min' already includes traffic delay if Routes API works correclty.
    # Adjusted: Reduced time weight (2.5 -> 2.25) to be more realistic with modern traffic apps
    base_meter = 35 + (dist_km * 7) + (dur_min * 2.25)
    base_meter = int(base_meter)
    
    # 4. Multipliers
    # Tuned down Rush Hour Multiplier (1.5 -> 1.25) based on user feedback
    rush_mult = 1.25 if is_rush_hour else 1.0
    tuktuk_rush_mult = 1.2 if is_rush_hour else 1.0
    
    # Hell Zone Surcharge (1.1x) if applicable
    hell_mult = 1.1 if is_hell_zone else 1.0
    
    # Final App Multiplier (Combined)
    total_app_mult = rush_mult * hell_mult

    # Calculate raw prices (Adjusted down based on user feedback)
    # Target: Meter x (1.2 ~ 1.6 including surge)
    bolt_basic_raw = int(base_meter * 0.85 * total_app_mult)
    bolt_std_raw = int(base_meter * 1.0 * total_app_mult)
    grab_raw = int(base_meter * 1.1 * total_app_mult)
    
    # Grab Range (+- 10%)
    grab_min = int(grab_raw * 0.9)
    grab_max = int(grab_raw * 1.1)

    # Bike Range (+- 10%)
    bike_raw = 25 + (dist_km * 8)
    bike_min = int(bike_raw * 0.9)
    bike_max = int(bike_raw * 1.1)

    fares = {
        "bolt": {
            "label": "⚡ Bolt (통합)",
            "price": f"{bolt_basic_raw} ~ {bolt_std_raw}",
            "tag": "차 잡기 힘듦" if not is_rush_hour else "매우 힘듦 (Surge)",
            "color": "green" # Merged color
        },
        "grab_taxi": {
            "label": "💚 Grab (Standard)",
            "price": f"{grab_min} ~ {grab_max}",
            "tag": "안전/빠름" if not is_rush_hour else "매우 비쌈 (Surge)",
            "color": "blue"
        },
        "bike": {
            "label": "🏍️ 오토바이 (Win)",
            "price": f"{bike_min} ~ {bike_max}",
            "tag": "🚀 가장 빠름",
            "color": "orange",
            "warning_text": "⚠️ 사고 위험 높음 / 헬멧 필수 / 보험 확인"
        },
        "tuktuk": {
            "label": "🛺 뚝뚝 (TukTuk)",
            "tag": "협상 필수",
            "color": "red",
            "warning": True
        }
    }
    
    # Calc TukTuk Range
    tt_min = int(base_meter * 1.5 * tuktuk_rush_mult) 
    tt_max = int(base_meter * 2.0 * tuktuk_rush_mult)
    fares['tuktuk']['price'] = f"{tt_min} ~ {tt_max}"
    
    # ---------------------------------------------------------
    # 5. Intercity / Long Distance Logic (Flat Rate)
    # ---------------------------------------------------------
    is_intercity = False
    intercity_tip = None
    
    # Check Keywords (Priority)
    dest_lower = str(dest_txt).lower()
    
    flat_rates = {
        "pattaya": {"range": (1100, 1400), "tip": "🚌 에까마이 터미널에서 버스 타면 약 131바트!"},
        "hua hin": {"range": (2000, 2400), "tip": "🚆 기차나 미니밴을 이용하면 200~400바트!"},
        "ayutthaya": {"range": (900, 1200), "tip": "🚆 기차(20바트~)나 미니밴을 추천합니다!"},
        "suvarnabhumi": {"range": (400, 500), "tip": "🚆 공항철도(ARL)를 타면 시내까지 45바트 내외!"} # Airport special
    }
    
    matched_zone = None
    for key, data in flat_rates.items():
        if key in dest_lower:
            matched_zone = data
            is_intercity = True
            break
            
    # Generic Long Distance (> 60km)
    if not matched_zone and dist_km >= 60:
        is_intercity = True
        # Formula: 1200 + ((dist - 100) * 10)
        est_price = 1200 + ((dist_km - 100) * 10)
        est_min = int(est_price * 0.9)
        est_max = int(est_price * 1.1)
        
        matched_zone = {"range": (est_min, est_max), "tip": "🚌 장거리 이동은 버스/기차/미니밴 이용을 고려해보세요! (훨씬 저렴함)"}

    if is_intercity and matched_zone:
        r_min, r_max = matched_zone['range']
        price_str = f"{r_min} ~ {r_max}"
        intercity_tip = matched_zone['tip']
        
        # Override Fares
        fares['bolt']['price'] = price_str
        fares['grab_taxi']['price'] = price_str # Apps often follow market flat rates for long distance
        fares['tuktuk']['price'] = "운행 불가" # Tuktuk highly unlikely
        fares['bike']['price'] = "추천 안함"
    
    return base_meter, fares, is_rush_hour, is_hell_zone, intercity_tip

def search_places(query, api_key):
    """
    Search using Google Places Autocomplete API for better partial matching.
    Returns: {name, address, place_id}
    """
    if not query: return []
    
    # Use Autocomplete API as requested into order to support 'Top 10' predictions and 'components' filtering
    endpoint = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": api_key,
        "language": "ko",
        "components": "country:TH" # Strict Thailand restriction
    }
    
    try:
        import requests
        resp = requests.get(endpoint, params=params, timeout=5)
        data = resp.json()
        
        candidates = []
        if data.get('status') == 'OK':
            for p in data.get('predictions', [])[:10]:
                main_text = p.get('structured_formatting', {}).get('main_text', '')
                sec_text = p.get('structured_formatting', {}).get('secondary_text', '')
                full_text = p.get('description', '')
                
                candidates.append({
                    "name": main_text if main_text else full_text,
                    "address": sec_text,
                    "place_id": p.get('place_id')
                })
        return candidates
    except Exception as e:
        print(f"Autocomplete Error: {e}")
        return []
