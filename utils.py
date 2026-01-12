import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta
import time
import json
import os
import requests
import re
from bs4 import BeautifulSoup


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
            "reason": "1 simple sentence explaining the situation for a tourist. (e.g. 'Avoid Siam area due to heavy protest crowds')",
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
        return data


    except Exception as e:
        print(f"Twitter Trend Error: {e}")
        return None

# --------------------------------------------------------
# Hotel Fact Check Features
# --------------------------------------------------------

def fetch_hotel_info(hotel_name, api_key):
    """
    Search for a hotel using Google Places API (New) and fetch details + photos.
    """
    if not api_key:
        return None, "Google Maps API Key가 없습니다."

    try:
        # Step 1: Text Search (Find ID)
        search_url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"
        }
        payload = {
            "textQuery": hotel_name
        }
        
        resp = requests.post(search_url, json=payload, headers=headers)
        data = resp.json()
        
        # Debugging: Print raw response
        print(f"DEBUG: Places Search Response: {data}")

        if "error" in data:
            return None, f"Google API Error: {data['error'].get('message')} (Code: {data['error'].get('code')})"
        
        if not data.get("places"):
            return None, "호텔을 찾을 수 없습니다. (검색 결과 0건)"
        
        place_id = data["places"][0]["id"]
        
        # Step 2: Place Details
        details_url = f"https://places.googleapis.com/v1/places/{place_id}"
        headers_details = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews,photos"
        }
        
        resp_details = requests.get(details_url, headers=headers_details)
        place_details = resp_details.json()
        
        # Process Photos
        photo_url = None
        if place_details.get("photos"):
            photo_ref = place_details["photos"][0]["name"] # "places/PLACE_ID/photos/PHOTO_ID"
            # Construct Image URL (Max Width 800)
            photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=800&maxWidthPx=800&key={api_key}"
        
        return {
            "name": place_details.get("displayName", {}).get("text", hotel_name),
            "address": place_details.get("formattedAddress", ""),
            "rating": place_details.get("rating", 0.0),
            "review_count": place_details.get("userRatingCount", 0),
            "reviews": place_details.get("reviews", []),
            "photo_url": photo_url
        }, None

    except Exception as e:
        return None, f"API 오류: {str(e)}"

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

        **[작성 가이드라인 - 엄격 준수]**
        1. **추측 금지:** 모르는 구체적 수치(예: 정확한 디파짓 금액)는 억지로 쓰지 말고, 전반적인 '경향성(체계적이다/느리다)' 위주로 서술해.
        2. **비판적 시각:** "좋았다" 대신 "수압이 마사지 수준이다" 혹은 "배수가 느려 물이 고인다"처럼 구체적으로 묘사해.
        3. **한국인 맞춤:** 한국인이 민감한 '벌레', '샤워기 필터 변색', '방음', '조식 김치 유무' 등의 정보가 있다면 필수로 포함해.

        **[출력 포맷 (JSON)]**
        응답은 반드시 아래 JSON 형식을 지켜줘.

        {{
            "one_line_verdict": "한 줄 결론 (예: 위치는 깡패지만 귀마개 필수인 가성비 호텔)",
            "recommendation_target": "추천: [대상], 비추천: [대상] (예: 추천: 잠만 잘 혼행족, 비추천: 예민한 커플)",
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
