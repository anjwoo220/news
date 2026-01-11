import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta
import time
import json
import os


# Helper: Check if article is within last N days
def is_recent(entry, days=3):
    if not hasattr(entry, 'published_parsed'):
        return True # Default to include if no date
    
    # published_parsed is a struct_time, convert to datetime
    pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
    limit_date = datetime.now() - timedelta(days=days)
    return pub_date >= limit_date

# 1. RSS Parsing (Balanced)
def fetch_balanced_rss(feeds_config):
    """
    Fetches RSS feeds and returns a balanced mix of items across categories.
    feeds_config: List of dicts [{'category': '...', 'url': '...'}, ...]
    """
    import requests
    
    # Using a typical browser User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    }
    
    category_buckets = {}
    MAX_PER_CATEGORY = 2  # User Limit
    
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


def fetch_full_content(url):
    """
    Attempts to scrape full article content.
    Returns truncated text (max 2000 chars) or None if failed.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        
        # Simple domain checks for known Paywalls if needed
        if "bangkokpost.com" in url or "thairath" in url or "khaosod" in url:
             pass 

        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Common Content Selectors (Bangkok Post, Thairath, etc.)
            selectors = [
                 "div.article-content", # Bangkok Post
                 "div.artcl-content",   # Bangkok Post variant
                 "div#content-body",
                 "div.news-detail",     # Thairath often uses this or similar
                 "div.entry-content",   # WordPress standard (Khaosod English)
                 "article"              # Semantic fallback
            ]
            
            content_text = ""
            for select in selectors:
                found = soup.select_one(select)
                if found:
                    # Remove scripts/styles
                    for script in found(["script", "style", "iframe", "div.ads"]):
                        script.decompose()
                    content_text = found.get_text(separator="\n", strip=True)
                    break
            
            # Fallback: Just grab all P tags if no container found
            if not content_text:
                ps = soup.find_all('p')
                # Filter out very short lines (nav items)
                content_text = "\n".join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 30])

            if content_text:
                return content_text[:3000] # Cap at 3000 chars for context window
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        
    return None

def analyze_news_with_gemini(news_items, api_key):
    if not news_items:
        return None, "No news items to analyze."
        
    genai.configure(api_key=api_key)
    
    # Limit to top 5 items to avoid Rate Limit (429) on Free Tier
    max_items = 5
    limited_news_items = news_items[:max_items]
    
    aggregated_topics = []
    total_items = len(limited_news_items)
    
    print(f"Starting sequential analysis for {total_items} items (with 10s delay)...")

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
        당신은 태국 방콕에 주재하는 '태국어와 영어에 모두 능통한 베테랑 한국 특파원'입니다.
        입력된 뉴스 기사(영어, 태국어 혼용 가능)를 한국 교민, 여행자들이 이해하기 쉬운 **완벽한 한국어 뉴스 기사**로 재작성하세요.

        [핵심 처리 규칙]
        1. **다국어 처리 (중요):** 
           - 기사 원문에 **태국어(Thai Script)**가 포함된 경우, 절대 생략하거나 원문 그대로 남겨두지 마세요.
           - **일반 문장:** 한국어로 의미를 번역하세요.
           - **고유명사(지명, 인명, 가게 이름):** 한국어 표준 외래어 표기법에 맞춰 **발음대로 표기**하세요. (예: ภู켓 -> 푸켓, สุขุมวิท -> 수쿰빗)
           - 만약 정확한 발음을 모를 경우에만 괄호 안에 원어를 병기하세요. 예: 왓 아룬(Wat Arun)

        2. **날짜/연도 변환 (매우 중요):**
           - 태국 불기 연도(BE)가 나오면 반드시 **서기(AD)**로 변환하세요.
           - 공식: **(불기) - 543 = (서기)**
           - 예: 2569년 1월 -> 2026년 1월, 2567년 -> 2024년.
           - 절대 25xx년 그대로 표기하지 마세요.

        3. **기자체 사용:** "~했습니다" 대신 "~했다", "~전망이다" 등 명료한 보도체 문장을 사용하세요.
        3. **불필요한 서술 제거:** "기사에 따르면", "다음은 번역입니다" 같은 AI 투의 문장은 삭제하고 바로 사실(Fact)부터 전달하세요.
        4. **독자 중심:** 주 독자는 태국 거주 한국인입니다. 그들에게 필요한 정보(위치, 날짜, 가격, 주의사항)를 강조하세요.

        [기사 정보]
        - Title: {item['title']}
        - Source: {item['source']}
        - Link: {item['link']}
        
        [기사 본문]
        {full_content}

        [작성 요구사항]
        1. **헤드라인:** 한국 독자의 눈길을 끄는 매력적인 한국어 제목을 뽑으세요.
        2. **핵심 요약:** 바쁜 현대인을 위해 핵심 내용을 3줄 이내의 개조식으로 명료하게 요약하세요.
        3. **분류:** 다음 중 하나를 선택: ["정치/사회", "경제", "여행/관광", "사건/사고", "엔터테인먼트", "기타"]
           - **Weather Rule:** 날씨, 기온, 홍수, 미세먼지 등 기상 관련 내용은 무조건 **'여행/관광'**으로 분류하세요.
           - 날씨 기사일 경우 본문의 구체적 온도(예: 38도)를 요약에 반드시 포함하세요.
        
        4. **[중요] 기사 전문 작성 (`full_translated`):**
           - 위 [기사 본문]을 바탕으로 완벽한 흐름의 한국어 기사를 새롭게 작성하세요. (단순 번역 X, 기사 작성 O)
           - 문단 나누기는 `\\n\\n`으로 명확히 하여 가독성을 높이세요.
           - 절대 원문의 내용을 생략하지 말고 충실히 전달하되, 문체는 완벽한 한국어 기자체여야 합니다.

        [출력 포맷 (JSON Only)]
        {{
          "topics": [
            {{
              "title": "작성된 기사 제목",
              "summary": "3줄 핵심 요약",
              "full_translated": "작성된 고품질 기사 전문 (Markdown 형식)",
              "category": "선택된 카테고리",
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
                result = json.loads(response.text)
                
                if 'topics' in result and result['topics']:
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

import requests
from bs4 import BeautifulSoup

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

def fetch_trend_hunter_items(api_key):
    """
    Aggregates trend/travel content from 4 sources:
    1. Wongnai (Restaurants)
    2. TheSmartLocal TH (Hotspots)
    3. Chillpainai (Local Travel)
    4. BK Magazine (BKK Life)
    
    Returns:
        list: shuffled list of dicts {title, desc, location, image_url, link, badge}
    """
    import random
    items = []
    
    print("Fetching Trend Hunter items...")
    
    # Common Headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }

    # Helper: Gemini Analyzer for Trend Content
    def analyze_trend_content(raw_inputs, source_type):
        """
        raw_inputs: List of dicts {raw_title, raw_link, raw_img, context}
        """
        if not raw_inputs: return []
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            # Batch Prompt
            prompt = f"""
            You are a Thai Travel Editor specialized in customizing content for Korean tourists.
            Analyze the following raw items from {source_type}.
            
            Input Data:
            {json.dumps(raw_inputs, ensure_ascii=False)}
            
            Task:
            1. Summarize the appeal of each place/activity in 1 line (Korean). Remove ads.
            2. Transliterate Thai/English names to Korean pronunciation (e.g. Thipsamai -> 팁사마이).
            3. Return a JSON list.
            
            Output JSON Format:
            [
                {{
                    "original_index": 0 (int),
                    "title": "Attractive Korean Title (e.g. '방콕 최고의 팟타이, 팁사마이')",
                    "location": "Rough Location (e.g. '방콕 구시가지')",
                    "desc": "1 line summary of why it is good.",
                }}
            ]
            """
            
            response = model.generate_content(prompt)
            text = response.text.strip()
            if "```json" in text: text = text.replace("```json", "").replace("```", "")
            if text.startswith("```"): text = text.replace("```", "")

            result = json.loads(text)
            
            processed = []
            for res in result:
                idx = res.get('original_index')
                if idx is not None and idx < len(raw_inputs):
                    original = raw_inputs[idx]
                    processed.append({
                        "title": res.get('title'),
                        "location": res.get('location'),
                        "desc": res.get('desc'),
                        "image_url": original.get('raw_img'),
                        "link": original.get('raw_link'),
                        "badge": source_type
                    })
            return processed
        except Exception as e:
            print(f"Trend Analysis Error ({source_type}): {e}")
            return []

    # ------------------------------------------------
    # B. TheSmartLocal TH (MZ Hotspots)
    # ------------------------------------------------
    try:
        url = "https://thesmartlocal.co.th/category/things-to-do/"
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        raw_tsl = []
        articles = soup.select("article")[:4] # Top 4
        for i, art in enumerate(articles):
            link_tag = art.find("a")
            # TSL images often in specialized div or noscript
            img_tag = art.find("img")
            
            if link_tag:
                 raw_link = link_tag['href']
                 raw_img = img_tag.get('src') if img_tag else ""
                 if not raw_img and img_tag: raw_img = img_tag.get('data-src') or img_tag.get('data-lazy-src')
                 
                 raw_tsl.append({
                     "raw_title": link_tag.get_text(strip=True),
                     "raw_link": raw_link,
                     "raw_img": raw_img,
                     "context": "Category: Things to do"
                 })
                 
        if raw_tsl:
            items.extend(analyze_trend_content(raw_tsl, "[MZ 핫플]"))
            
    except Exception as e:
        print(f"TSL Error: {e}")

    # ------------------------------------------------
    # C. Chillpainai (Local Travel)
    # ------------------------------------------------
    try:
        url = "https://www.chillpainai.com/scoop/"
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        raw_chill = []
        # Chillpainai Scoop Grid
        scoops = soup.select("div.scoop-content")[:4] 
        if not scoops: scoops = soup.select(".col-sm-4")[:4] 

        for i, sc in enumerate(scoops):
             link_tag = sc.find("a")
             img_tag = sc.find("img")
             title_tag = sc.find("h4") or sc.find("div", class_="title")
             
             if link_tag and img_tag:
                  raw_chill.append({
                      "raw_title": title_tag.get_text(strip=True) if title_tag else "Chillpainai Article",
                      "raw_link": link_tag['href'],
                      "raw_img": img_tag.get('src'),
                      "context": "Local Travel Guide"
                  })

        if raw_chill:
             items.extend(analyze_trend_content(raw_chill, "[현지인 추천]"))

    except Exception as e:
        print(f"Chillpainai Error: {e}")

    # ------------------------------------------------
    # D. BK Magazine (BKK Life)
    # ------------------------------------------------
    try:
        url = "https://bk.asia-city.com/things-to-do-bangkok"
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        raw_bk = []
        rows = soup.select("div.views-row")[:4]
        
        for i, row in enumerate(rows):
             title_div = row.select_one("div.views-field-title a")
             img_div = row.select_one("div.views-field-field-image img")
             
             if title_div and img_div:
                  link = "https://bk.asia-city.com" + title_div['href'] if title_div['href'].startswith("/") else title_div['href']
                  raw_bk.append({
                      "raw_title": title_div.get_text(strip=True),
                      "raw_link": link,
                      "raw_img": img_div.get('src'),
                      "context": "Bangkok Events/Lifestyle"
                  })

        if raw_bk:
             items.extend(analyze_trend_content(raw_bk, "[BKK 라이프]"))

    except Exception as e:
        print(f"BK Mag Error: {e}")

    # ------------------------------------------------
    # A. Wongnai (Articles)
    # ------------------------------------------------
    try:
        url = "https://www.wongnai.com/articles" 
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        raw_w = []
        cards = soup.select("div[class*='Card']")[:4]
        if not cards: cards = soup.find_all("a", href=True)[:10] 
        
        count = 0
        for c in cards:
             if count >= 4: break
             href = c['href']
             if "/articles/" in href:
                  img = c.find("img")
                  h = c.find("h3") or c.find("h2") or c.find("div", class_="title")
                  if img and h:
                       link = "https://www.wongnai.com" + href if href.startswith("/") else href
                       raw_w.append({
                           "raw_title": h.get_text(strip=True),
                           "raw_link": link,
                           "raw_img": img.get('src') or img.get('data-src'),
                           "context": "Food Guide/Review"
                       })
                       count += 1
        
        if raw_w:
             items.extend(analyze_trend_content(raw_w, "[Wongnai 미식]"))

    except Exception as e:
        print(f"Wongnai Error: {e}")

    # Shuffle for Magazine feel
    random.shuffle(items)
    return items
