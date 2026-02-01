
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import json
import os
from datetime import datetime, timedelta

# SPREADSHEET URL (Public/Shared)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8/edit?usp=sharing"

# Local cache file path
LOCAL_NEWS_CACHE = "data/news.json"

def load_local_news_cache(days=7):
    """
    [FAST] Loads news from local JSON file.
    Returns only recent N days for consistency with GSheets version.
    
    Returns: dict { "YYYY-MM-DD": [items] } or {} if file doesn't exist
    """
    if not os.path.exists(LOCAL_NEWS_CACHE):
        return {}
    
    try:
        with open(LOCAL_NEWS_CACHE, 'r', encoding='utf-8') as f:
            all_news = json.load(f)
        
        if not isinstance(all_news, dict):
            return {}
        
        # Filter to recent N days
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        recent_news = {k: v for k, v in all_news.items() if k >= cutoff_date}
        
        return recent_news
    except Exception as e:
        print(f"Error loading local news cache: {e}")
        return {}

# Connection Helper
def get_db_connection():
    """
    Returns the Google Sheets connection object using Streamlit's connection API.
    Uses 'gsheets_news' connection name defined in secrets.toml.
    """
    try:
        conn = st.connection("gsheets_news", type=GSheetsConnection)
        return conn
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

# --- NEWS CRUD OPERATIONS ---

def load_news_from_sheet(worksheet="news"):
    """
    Reads all news data from the specified worksheet.
    Returns a list of dictionaries (records).
    """
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        # Read as DataFrame (Explicitly pass spreadsheet to avoid config errors)
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet, ttl=0) # ttl=0 to always fetch fresh, or manage manually
        
        # Determine if data exists
        if df.empty:
            return {}

        # Expected Columns in Sheet:
        # date (YYYY-MM-DD), title, summary, link, source, category, impact_score, image_url, ...
        # JSON structure was: { "2024-01-01": [ {item}, {item} ] }
        
        # Convert DF to list of dicts
        records = df.to_dict(orient="records")
        
        # Transform back to Dict-by-Date structure for App compatibility
        news_by_date = {}
        for item in records:
            # Handle potential NaN/Nat
            if pd.isna(item.get('date')): continue
            
            # Robust Date Parsing (Handle '2024-01-01T...' and '2024-01-01 00:00:00')
            date_str = str(item['date']).split('T')[0].split(' ')[0] # Ensure YYYY-MM-DD string
            if date_str not in news_by_date:
                news_by_date[date_str] = []
            
            # Clean up NaN values in item
            clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}

            # Parse JSON fields if they are strings (GSHEETS stores list/dict as string)
            for field in ['references', 'related_topics']:
                if field in clean_item and isinstance(clean_item[field], str):
                     # Simple check if it looks like JSON list or dict
                    val = str(clean_item[field]).strip()
                    if val.startswith('[') or val.startswith('{'):
                        try:
                            clean_item[field] = json.loads(val)
                        except:
                            try:
                                import ast
                                clean_item[field] = ast.literal_eval(val)
                            except:
                                pass # Keep as string if all parse fails

            # Ensure 'link' exists for UI compatibility (Fallback to first reference)
            if not clean_item.get('link') or clean_item['link'] == "" or clean_item['link'] == "#":
                refs = clean_item.get('references')
                if isinstance(refs, list) and refs:
                    clean_item['link'] = refs[0].get('url', "#")
                elif isinstance(refs, str) and refs.startswith('http'):
                    clean_item['link'] = refs

            news_by_date[date_str].append(clean_item)
            
        return news_by_date

    except Exception as e:
        print(f"Error loading news from sheet: {e}")
        return {}

def load_recent_news(days=7):
    """
    [OPTIMIZED] Loads only recent N days of news with TTL caching.
    
    - Uses TTL=300 (5 min) to cache GSheets API results
    - Filters to only recent 'days' worth of data for faster processing
    - Falls back to full load if filtering fails
    
    Returns: dict { "YYYY-MM-DD": [items] }
    """
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        # TTL=300 (5 minutes) - Key optimization for repeat loads
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="news", ttl=300)
        
        if df.empty:
            return {}
        
        # Calculate cutoff date
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Convert to records
        records = df.to_dict(orient="records")
        
        # Transform to Dict-by-Date structure (same as original)
        news_by_date = {}
        for item in records:
            if pd.isna(item.get('date')): continue
            
            date_str = str(item['date']).split('T')[0].split(' ')[0]
            
            # Skip old dates (the optimization)
            if date_str < cutoff_date:
                continue
                
            if date_str not in news_by_date:
                news_by_date[date_str] = []
            
            # Clean up NaN values
            clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}

            # Parse JSON fields
            for field in ['references', 'related_topics']:
                if field in clean_item and isinstance(clean_item[field], str):
                    val = str(clean_item[field]).strip()
                    if val.startswith('[') or val.startswith('{'):
                        try:
                            clean_item[field] = json.loads(val)
                        except:
                            try:
                                import ast
                                clean_item[field] = ast.literal_eval(val)
                            except:
                                pass

            # Ensure 'link' exists
            if not clean_item.get('link') or clean_item['link'] == "" or clean_item['link'] == "#":
                refs = clean_item.get('references')
                if isinstance(refs, list) and refs:
                    clean_item['link'] = refs[0].get('url', "#")
                elif isinstance(refs, str) and refs.startswith('http'):
                    clean_item['link'] = refs

            news_by_date[date_str].append(clean_item)
            
        return news_by_date

    except Exception as e:
        print(f"Error loading recent news: {e}")
        # Fallback to full load on error
        return load_news_from_sheet()

def load_news_by_date(target_date):
    """
    [ON-DEMAND] Loads news for a specific date only.
    
    Used when user selects a date outside the recent window.
    Cached per-date to avoid repeat fetches.
    
    Args:
        target_date: "YYYY-MM-DD" string
    
    Returns: list of news items for that date, or []
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        # TTL=600 (10 min) for specific date queries
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="news", ttl=600)
        
        if df.empty:
            return []
        
        # Filter to target date only
        records = df.to_dict(orient="records")
        items = []
        
        for item in records:
            if pd.isna(item.get('date')): continue
            
            date_str = str(item['date']).split('T')[0].split(' ')[0]
            
            if date_str != target_date:
                continue
            
            # Clean up NaN values
            clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}

            # Parse JSON fields
            for field in ['references', 'related_topics']:
                if field in clean_item and isinstance(clean_item[field], str):
                    val = str(clean_item[field]).strip()
                    if val.startswith('[') or val.startswith('{'):
                        try:
                            clean_item[field] = json.loads(val)
                        except:
                            pass

            # Ensure 'link' exists
            if not clean_item.get('link') or clean_item['link'] == "" or clean_item['link'] == "#":
                refs = clean_item.get('references')
                if isinstance(refs, list) and refs:
                    clean_item['link'] = refs[0].get('url', "#")

            items.append(clean_item)
            
        return items

    except Exception as e:
        print(f"Error loading news for date {target_date}: {e}")
        return []

# Archive cache file path
ARCHIVE_NEWS_CACHE = "data/archive_news.json"

def get_news_for_date(target_date: str) -> list:
    """
    [LAZY LOADING] 특정 날짜의 뉴스를 가져옵니다.
    
    1. 로컬 전체 캐시(news.json)에서 먼저 확인 (0.01s)
    2. 아카이브 캐시에서 확인 (0.01s)  
    3. 없으면 GSheets에서 해당 날짜만 쿼리 (2-3s)
    4. 가져온 데이터를 아카이브에 저장 (재조회 최적화)
    
    Args:
        target_date: "YYYY-MM-DD" 형식 문자열
    
    Returns: list of news items for that date
    """
    # Step 1: 로컬 메인 캐시 확인 (전체 파일에서 해당 날짜만)
    if os.path.exists(LOCAL_NEWS_CACHE):
        try:
            with open(LOCAL_NEWS_CACHE, 'r', encoding='utf-8') as f:
                all_news = json.load(f)
            if isinstance(all_news, dict) and target_date in all_news:
                return all_news[target_date]
        except Exception as e:
            print(f"Error reading local cache: {e}")
    
    # Step 2: 아카이브 캐시 확인
    if os.path.exists(ARCHIVE_NEWS_CACHE):
        try:
            with open(ARCHIVE_NEWS_CACHE, 'r', encoding='utf-8') as f:
                archive = json.load(f)
            if isinstance(archive, dict) and target_date in archive:
                return archive[target_date]
        except Exception as e:
            print(f"Error reading archive cache: {e}")
    
    # Step 3: GSheets에서 온디맨드 로드
    items = load_news_by_date(target_date)
    
    # Step 4: 아카이브에 저장 (재조회 최적화)
    if items:
        try:
            archive = {}
            if os.path.exists(ARCHIVE_NEWS_CACHE):
                with open(ARCHIVE_NEWS_CACHE, 'r', encoding='utf-8') as f:
                    archive = json.load(f)
                if not isinstance(archive, dict):
                    archive = {}
            archive[target_date] = items
            with open(ARCHIVE_NEWS_CACHE, 'w', encoding='utf-8') as f:
                json.dump(archive, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving to archive cache: {e}")
    
    return items

def save_news_to_sheet(news_data_dict, worksheet="news"):
    """
    Overwrites the 'news' worksheet with the provided news_data_dict.
    news_data_dict format: { "YYYY-MM-DD": [ {title, link...}, ... ] }
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        # Flatten Dict to List of Records
        all_records = []
        for date_key, items in news_data_dict.items():
            for item in items:
                # Ensure 'date' field is explicit
                item['date'] = date_key 
                all_records.append(item)
        
        if not all_records:
            # If empty, maybe just clear sheet? but better not to break structure
            # Create empty DF with columns
            df = pd.DataFrame(columns=["date", "title", "summary", "link", "source", "category", "tourist_impact_score", "full_translated", "image_url"])
        else:
            df = pd.DataFrame(all_records)
            
        # Ensure common columns exist to avoid schema errors if some items miss keys
        expected_cols = ["date", "title", "summary", "link", "source", "category", "tourist_impact_score", "full_translated"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""

        # Write to Sheet
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=worksheet, data=df)
        
        # Clear Streamlit Cache to force reload next time
        st.cache_data.clear()
        return True

    except Exception as e:
        print(f"Error saving news to sheet: {e}")
        return False

def append_news_items_to_sheet(new_items_list, worksheet="news"):
    """
    Appends a list of news items (dicts) to the sheet.
    Useful for crawlers to add without reading everything first?
    Actually, 'update()' overlaps. 'write()' overwrites.
    st-gsheets-connection usually does overwrite on 'update' if passed full DF.
    To append, we assume we might need to Read -> Append -> Write.
    """
    # For safety/simplicity in this app (data size < 10k rows), 
    # Read-Modify-Write is safer to maintain consistency.
    # So we can just use load -> append in memory -> save.
    pass
