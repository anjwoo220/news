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
        
        [분류 규칙 (중요)]
        - **Weather Rule:** 날씨, 기온, 홍수, 미세먼지 등 기상 관련 내용은 무조건 **'여행/관광'**으로 분류하세요.

        3. 결과는 반드시 아래 JSON 형식으로만 출력하세요. (Markdown 코드 블록 없이 순수 JSON만)

        [출력 JSON 포맷]
        {{
          "topics": [
            {{
              "title": "기사 제목 (한국어 번역)",
              "summary": "한국어 요약 내용",
              "category": "카테고리",
              "references": [
                {{"title": "{item['title']}", "url": "{item['link']}", "source": "{item['source']}"}}
              ]
            }}
          ]
        }}
        """
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            response = model.generate_content(prompt)
            result = json.loads(response.text)
            
            if 'topics' in result and result['topics']:
                aggregated_topics.extend(result['topics'])
                print(f"   -> Success. Topics so far: {len(aggregated_topics)}")
            
        except Exception as e:
            print(f"   -> API Error for item {idx+1}: {e}")
            print("   -> Skipping this item and continuing...")
            # Continue to next item without stopping
            
        # Delay logic (except for the last one)
        if idx < total_items - 1:
            print("   -> Waiting 10 seconds to respect API rate limits...")
            time.sleep(10)

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
    Returns:
        float: The current rate (e.g., 38.5)
        float: 0.0 if failed (change (today - yesterday) can be calculated in app if needed, 
               but for now just simple fetch)
    """
    url = "https://api.frankfurter.app/latest?from=THB&to=KRW"
    try:
        import requests
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('rates', {}).get('KRW', 39.50)
    except Exception as e:
        print(f"Exchange Rate Error: {e}")
    
    return 39.50 # Default fallback
