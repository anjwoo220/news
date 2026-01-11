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
        
        clean_summary = clean_html(item['summary'])[:500] # Slightly more context per item
        
        # Single Item Prompt
        prompt = f"""
        당신은 태국 전문 뉴스 에디터입니다. 
        아래 제공된 뉴스 기사를 분석하여 한국어 브리핑 항목을 작성해주세요.

        [기사 정보]
        - Title: {item['title']}
        - Source: {item['source']}
        - Link: {item['link']}
        - Summary: {clean_summary}

        [요청 사항]
        1. 이 기사의 핵심 내용을 3~4문장의 한국어로 요약하세요.
        2. 다음 카테고리 중 하나를 선택하여 분류하세요: ["정치/사회", "경제", "여행/관광", "사건/사고", "엔터테인먼트", "기타"]
        
        [날씨/기온 요약 특별 지침]
        - 만약 뉴스 내용이 **날씨, 기온, 폭염, 한파**와 관련되어 있다면, 기사 원문에 포함된 **구체적인 온도(예: 35°C, 38도, 영하 2도 등)**를 찾아서 요약문에 반드시 숫자로 기입해라.
        - 단순히 '덥다', '기온이 오른다'라고만 하지 말고 **'방콕 최고 기온 39도 예상'** 처럼 수치를 명시해라.

        [분류 규칙 (중요)]
        - **Weather Rule:** 날씨, 기온, 홍수, 미세먼지 등 기상 관련 내용은 무조건 **'여행/관광'**으로 분류하세요.

        3. **[필수] 기사 전문 번역:**
        - 기사의 **전체 내용**을 빠짐없이 한국어로 번역하여 `full_translated` 필드에 넣으세요.
        - 중간에 내용을 생략하거나 요약하지 말고, 원문의 뉘앙스를 살려 **완벽하게 번역**하세요.
        - 문단 구분은 `\\n\\n`으로 명확히 해주세요.

        4. 결과는 반드시 아래 JSON 형식으로만 출력하세요. (Markdown 코드 블록 없이 순수 JSON만)

        [출력 JSON 포맷]
        {{
          "topics": [
            {{
              "title": "기사 제목 (한국어 번역)",
              "summary": "한국어 요약 내용",
              "full_translated": "기사 전문 번역 (Markdown 포맷 지원)",
              "category": "카테고리",
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
