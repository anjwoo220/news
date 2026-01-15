import os
import json
import toml
import utils
import google.generativeai as genai
from datetime import datetime

def diag():
    print("--- News Update Diagnostic ---")
    
    # 1. Check API Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            secrets = toml.load(".streamlit/secrets.toml")
            api_key = secrets.get("GEMINI_API_KEY")
        except: pass
    
    if not api_key:
        print("[FAIL] GEMINI_API_KEY not found in env or secrets.toml")
    else:
        print("[OK] GEMINI_API_KEY found.")

    # 2. Test Gemini Connection
    print("\n[Testing Gemini API Connection...]")
    try:
        genai.configure(api_key=api_key)
        # Try gemini-1.5-flash as a baseline
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello")
        print(f"[OK] Gemini 1.5 Flash responded: {response.text.strip()}")
        
        # Try gemini-2.0-flash (used in app)
        try:
            model2 = genai.GenerativeModel('gemini-2.0-flash')
            response2 = model2.generate_content("Hello")
            print(f"[OK] Gemini 2.0 Flash responded: {response2.text.strip()}")
        except Exception as e2:
            print(f"[WARN] Gemini 2.0 Flash failed: {e2}")
    except Exception as e:
        print(f"[FAIL] Gemini API error: {e}")

    # 3. Test RSS Fetching
    print("\n[Testing RSS Fetching...]")
    try:
        feeds_file = 'data/feeds.json'
        with open(feeds_file, 'r') as f:
            feeds = json.load(f)
        
        # Test just the first feed
        test_feed = feeds[:1]
        print(f"Fetching from: {test_feed[0]['url']}")
        items = utils.fetch_balanced_rss(test_feed, set())
        print(f"[OK] Fetched {len(items)} items from first RSS feed.")
        
        # Test Google News
        print("Testing Google News Fetch...")
        g_items = utils.fetch_google_news_rss(query="Thailand Tourism")
        print(f"[OK] Fetched {len(g_items)} items from Google News.")
        
        if not items and not g_items:
            print("[FAIL] No news items could be fetched.")
    except Exception as e:
        print(f"[FAIL] RSS fetching error: {e}")

    # 4. Check GSheets Connection
    print("\n[Checking GSheets Connection...]")
    try:
        from db_utils import load_news_from_sheet
        try:
            news = load_news_from_sheet()
            print(f"[OK] Successfully loaded {len(news)} dates from GSheets.")
            if news:
                dates = sorted(news.keys())
                print(f"Dates in sheet: {dates}")
                latest_date = dates[-1]
                print(f"\nContent for {latest_date}:")
                items = news.get(latest_date, [])
                print(f"Found {len(items)} items.")
                for i, item in enumerate(items[:3]):
                    print(f" [{i+1}] {item.get('title')} (Source: {item.get('source')}, Time: {item.get('collected_at')})")
            else:
                print("[WARN] Sheet is empty.")
        except Exception as e_gs:
            print(f"[WARN] GSheets load test (standalone) failed: {e_gs}")
    except Exception as e:
        print(f"[FAIL] Import db_utils error: {e}")

if __name__ == "__main__":
    diag()
