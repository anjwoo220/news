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
    
    # Convert list to string for prompt
    news_text = ""
    for idx, item in enumerate(limited_news_items):
        clean_summary = clean_html(item['summary'])[:300] # Strip HTML and truncate
        news_text += f"{idx+1}. [{item['source']}] {item['title']} - {item['link']}\n   Summary: {clean_summary}...\n\n"
        
    prompt = f"""
    당신은 태국 전문 뉴스 에디터입니다. 
    아래 제공된 최근 3일간의 태국 뉴스 기사 목록을 분석하여 한국어 브리핑 리포트를 작성해주세요.

    [요청 사항]
    1. 뉴스 기사들을 유사한 주제(Topic)끼리 그룹화하세요.
    2. 각 주제별로 핵심 내용을 3~4문장의 한국어로 요약하세요.
    3. 각 주제 하단에 관련 기사의 원본 링크(제목과 URL)를 포함하세요.
    4. 각 주제에 대해 다음 카테고리 중 하나를 선택하여 분류하세요: ["정치/사회", "경제", "여행/관광", "사건/사고", "엔터테인먼트", "기타"]
    
    [분류 규칙 (중요)]
    - **Weather Rule:** 기사의 핵심 주제가 **날씨(Weather), 기온(Temperature), 폭염(Heatwave), 추위(Cold), 장마/호우(Rain/Flood), 미세먼지(PM2.5)** 등 기상 상황과 관련되어 있다면, 주저하지 말고 **'여행/관광'** 카테고리로 분류하세요.
    - 이유: 날씨 정보는 여행자들의 일정에 가장 큰 영향을 미치는 요소이기 때문입니다.
    - 입력 텍스트에 'weather', 'degrees', 'storm', 'heat index' 등의 키워드가 포함될 경우 이 규칙을 우선 적용하세요.

    5. 결과는 반드시 아래 JSON 형식으로만 출력하세요. (Markdown 코드 블록 없이 순수 JSON만)

    [입력 뉴스 데이터]
    {news_text}

    [출력 JSON 포맷]
    {{
      "start_date": "YYYY-MM-DD", 
      "end_date": "YYYY-MM-DD",
      "total_articles": {len(news_items)},
      "topics": [
        {{
          "title": "주제 제목 (한국어)",
          "summary": "주제 요약 내용 (한국어)",
          "category": "카테고리 (예: 정치/사회)",
          "references": [
            {{"title": "기사 제목", "url": "URL", "source": "매체명"}}
          ]
        }}
      ]
    }}
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        response = model.generate_content(prompt)
        return json.loads(response.text), None
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None, str(e)


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
