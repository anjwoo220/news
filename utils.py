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

# 1. RSS Parsing
def fetch_and_filter_rss(feed_urls):
    news_items = []
    # Using a typical browser User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    }
    
    import requests
    
    for url in feed_urls:
        try:
            print(f"Fetching {url}...")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"Failed to fetch {url}: Status {response.status_code}")
                continue
                
            # Parse the raw content
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                print(f"XML Parse Warning for {url}: {feed.bozo_exception}")
            
            print(f"Successfully parsed {url}: Found {len(feed.entries)} entries.")
            
            for entry in feed.entries:
                if is_recent(entry):
                    item = {
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", str(datetime.now())),
                        "summary": entry.get("summary", ""),
                        "source": feed.feed.get("title", url),
                        "_raw_entry": entry
                    }
                    news_items.append(item)
                    
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            
    return news_items

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
        당신은 태국 방콕에 주재하는 '베테랑 한국 특파원'입니다. 
        당신의 임무는 영문 기사를 한국 사람들이 이해하기 쉬운 '완벽한 한국 뉴스 기사'로 작성하는 것입니다.

        [번역 및 작성 원칙]
        1. **직역 금지:** 영어식 문장 구조(수동태, 긴 수식어)를 피하고, 한국어의 자연스러운 어순과 문맥에 맞춰 의역하세요.
        2. **기자체 사용:** "~했습니다", "~입니다" 보다는 뉴스 보도 스타일의 "~했다", "~로 밝혀졌다", "~전망이다" 등 전문적인 어미를 사용하세요.
        3. **불필요한 서술 제거:** "기사에 따르면", "이 문서는 말한다" 같은 AI스러운 표현을 절대 쓰지 마세요. 바로 사실(Fact)부터 전달하세요.
        4. **용어의 현지화:** 태국 지명이나 인명은 한국에서 통용되는 표기법을 따르세요. (예: Sukhumvit -> 수쿰빗)
        5. **독자 중심:** 주 독자는 '태국 거주 한국인, 태국 여행하려는 한국인'입니다. 그들에게 미칠 영향이나 중요 포인트를 잘 살려주세요.

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
