
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import json
import os
from datetime import datetime, timedelta
import utils

# SPREADSHEET URL (Public/Shared)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8/edit?usp=sharing"

# Local cache file paths
LOCAL_NEWS_CACHE = "data/news.json"
LATEST_NEWS_CACHE = "data/latest_news.json"
ARCHIVE_NEWS_CACHE = "data/archive_news.json"
GLOBAL_MIN_NEWS_COUNT = 9000  # Safety floor to prevent catastrophic data loss

def load_local_news_cache(days=30):
    """
    [MAIN] Loads news from local JSON file (data/news.json).
    Returns only recent N days (default 30).
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
        return utils.sanitize_news_dataset(recent_news)
    except Exception as e:
        print(f"Error loading main news cache: {e}")
        return {}

def load_latest_news_cache():
    """
    [ULTRA FAST] Loads only the most recent 7 days from latest_news.json.
    Target load time: < 100ms.
    """
    if not os.path.exists(LATEST_NEWS_CACHE):
        return {}
    
    try:
        with open(LATEST_NEWS_CACHE, 'r', encoding='utf-8') as f:
            latest_news = json.load(f)
            
        if not isinstance(latest_news, dict):
            return {}
            
        # Optional: check if data is truly recent
        cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        recent_only = {k: v for k, v in latest_news.items() if k >= cutoff_date}
        return utils.sanitize_news_dataset(recent_only)
    except Exception as e:
        print(f"Error loading latest news cache: {e}")
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
            date_str = str(item['date']).strip().split('T')[0].split(' ')[0] # Ensure YYYY-MM-DD string
            if date_str not in news_by_date:
                news_by_date[date_str] = []
            
            # Clean up NaN values in item
            clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}

            # Parse JSON fields if they are strings (GSHEETS stores list/dict as string)
            for field in ['references', 'related_topics', 'event_info', 'event_data']:
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

            news_by_date[date_str].append(utils.sanitize_news_topic(clean_item))
            
        return utils.sanitize_news_dataset(news_by_date)

    except Exception as e:
        print(f"Error loading news from sheet: {e}")
        return None

def load_recent_news(days=7):
    """
    [OPTIMIZED] Loads only recent N days of news using SQL query.
    
    - Uses st.connection("gsheets_news").query() to fetch only relevant rows.
    - Drastically reduces memory usage compared to loading the entire sheet.
    
    Returns: dict { "YYYY-MM-DD": [items] }
    """
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        # Calculate cutoff date
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # SQL Query: Fetch only recent rows
        # st-gsheets-connection uses duckdb-style SQL on the sheet data
        sql = f"SELECT * FROM news WHERE date >= '{cutoff_date}'"
        
        # TTL=300 (5 minutes)
        df = conn.query(sql=sql, ttl=300)
        
        if df is None or df.empty:
            return {}
        
        # Convert to records
        records = df.to_dict(orient="records")
        
        # Transform to Dict-by-Date structure
        news_by_date = {}
        for item in records:
            if pd.isna(item.get('date')): continue
            
            date_str = str(item['date']).strip().split('T')[0].split(' ')[0]
            
            if date_str not in news_by_date:
                news_by_date[date_str] = []
            
            # Clean up NaN values
            clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}

            # Parse JSON fields
            for field in ['references', 'related_topics', 'event_info', 'event_data']:
                if field in clean_item and isinstance(clean_item[field], str):
                    val = str(clean_item[field]).strip()
                    if val.startswith('[') or val.startswith('{'):
                        try:
                            import json
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

            news_by_date[date_str].append(utils.sanitize_news_topic(clean_item))
            
        return utils.sanitize_news_dataset(news_by_date)

    except Exception as e:
        print(f"Error loading recent news with SQL: {e}")
        # Fallback to load_news_from_sheet is not recommended if it causes OOM,
        # but let's just return empty for safety on major errors
        return {}

def load_news_by_date(target_date):
    """
    [ON-DEMAND] Loads news for a specific date only using SQL query.
    
    Used when user selects a date outside the recent window.
    
    Args:
        target_date: "YYYY-MM-DD" string
    
    Returns: list of news items for that date, or []
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        # SQL Query: Fetch only rows for the target date
        sql = f"SELECT * FROM news WHERE date = '{target_date}'"
        
        # TTL=600 (10 min) for specific date queries
        df = conn.query(sql=sql, ttl=600)
        
        if df is None or df.empty:
            return []
        
        # Convert to records
        records = df.to_dict(orient="records")
        items = []
        
        for item in records:
            if pd.isna(item.get('date')): continue
            
            # Clean up NaN values
            clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}

            # Parse JSON fields
            for field in ['references', 'related_topics', 'event_info', 'event_data']:
                if field in clean_item and isinstance(clean_item[field], str):
                    val = str(clean_item[field]).strip()
                    if val.startswith('[') or val.startswith('{'):
                        try:
                            import json
                            clean_item[field] = json.loads(val)
                        except:
                            pass

            # Ensure 'link' exists
            if not clean_item.get('link') or clean_item['link'] == "" or clean_item['link'] == "#":
                refs = clean_item.get('references')
                if isinstance(refs, list) and refs:
                    clean_item['link'] = refs[0].get('url', "#")

            items.append(utils.sanitize_news_topic(clean_item))
            
        return items

    except Exception as e:
        print(f"Error loading news for date {target_date} with SQL: {e}")
        return []

def write_news_caches(news_data_dict):
    """
    [UNIFIED WRITER] Splits news into Latest (7d) and Main (30d) tiers and saves them.
    """
    try:
        news_data_dict = utils.sanitize_news_dataset(news_data_dict)

        # 1. Prepare Latest (7d)
        cutoff_latest = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        latest_news = {k: v for k, v in news_data_dict.items() if k >= cutoff_latest}
        
        # 2. Prepare Main (30d)
        cutoff_main = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        main_news = {k: v for k, v in news_data_dict.items() if k >= cutoff_main}
        
        # Ensure data dir exists
        os.makedirs(os.path.dirname(LOCAL_NEWS_CACHE), exist_ok=True)
        
        # Save Latest
        with open(LATEST_NEWS_CACHE, 'w', encoding='utf-8') as f:
            json.dump(latest_news, f, ensure_ascii=False, indent=2)
            
        # Save Main
        with open(LOCAL_NEWS_CACHE, 'w', encoding='utf-8') as f:
            json.dump(main_news, f, ensure_ascii=False, indent=2)
            
        print(f"Caches updated: Latest({len(latest_news)} days), Main({len(main_news)} days)")
        return True
    except Exception as e:
        print(f"Error writing news caches: {e}")
        return False

# Archive cache file path is already defined at top

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
                return [utils.sanitize_news_topic(item) for item in all_news[target_date]]
        except Exception as e:
            print(f"Error reading local cache: {e}")
    
    # Step 2: 아카이브 캐시 확인
    if os.path.exists(ARCHIVE_NEWS_CACHE):
        try:
            with open(ARCHIVE_NEWS_CACHE, 'r', encoding='utf-8') as f:
                archive = json.load(f)
            if isinstance(archive, dict) and target_date in archive:
                return [utils.sanitize_news_topic(item) for item in archive[target_date]]
        except Exception as e:
            print(f"Error reading archive cache: {e}")
    
    # Step 3: GSheets에서 온디맨드 로드
    items = load_news_by_date(target_date)
    
    # Step 4: 아카이브에 저장 (재조회 최적화)
    if items:
        items = [utils.sanitize_news_topic(item) for item in items]
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
        news_data_dict = utils.sanitize_news_dataset(news_data_dict)

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

        # Verify that the write actually landed in the target worksheet.
        verify_df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet, ttl=0)
        if verify_df is None:
            print("Error saving news to sheet: verification read returned None")
            return False

        expected_total = len(all_records)
        actual_total = len(verify_df.index)
        expected_latest = max(news_data_dict.keys()) if news_data_dict else None

        def normalize_date(value):
            if pd.isna(value):
                return ""
            return str(value).strip().split('T')[0].split(' ')[0]

        if expected_total and actual_total < expected_total:
            print(
                f"Error saving news to sheet: verification row count mismatch "
                f"(expected at least {expected_total}, got {actual_total})"
            )
            return False

        if expected_latest:
            verify_latest_dates = {
                normalize_date(value) for value in verify_df.get("date", pd.Series(dtype=str)).tolist()
            }
            if expected_latest not in verify_latest_dates:
                print(
                    f"Error saving news to sheet: verification latest date mismatch "
                    f"(expected {expected_latest}, got {sorted(d for d in verify_latest_dates if d)[-3:] if verify_latest_dates else []})"
                )
                return False

        # Extra safety: check against global floor
        if actual_total < GLOBAL_MIN_NEWS_COUNT:
            print(f"CRITICAL ERROR: Sheet row count {actual_total} is below global floor {GLOBAL_MIN_NEWS_COUNT}. Rolling back/Aborting.")
            return False

        print(
            f"Verified news sheet write: worksheet={worksheet}, "
            f"rows={actual_total}, latest={expected_latest}"
        )
        
        # Update local caches synchronously
        write_news_caches(news_data_dict)

        # Clear Streamlit Cache to force reload next time
        st.cache_data.clear()
        return True

    except Exception as e:
        print(f"Error saving news to sheet: {e}")
        return False

def append_news_to_sheet(new_items_list, worksheet="news"):
    """
    [APPEND ONLY] Appends a list of news items (dicts) to the bottom of the worksheet.
    Efficiently handles growing data without full sheet overwrites.
    """
    if not new_items_list:
        return True

    conn = get_db_connection()
    if not conn:
        return False

    try:
        # 1. Access the underlying gspread client via conn.client
        # Streamlit-gsheets wraps the GSheetsServiceAccountClient
        gs_client = conn.client._client
        ss = gs_client.open_by_url(SPREADSHEET_URL)
        ws = ss.worksheet(worksheet)
        
        # 2. Get headers to ensure correct column alignment
        headers = ws.row_values(1)
        if not headers:
            # Fallback headers if sheet was somehow totally cleared
            headers = ["title", "summary", "full_translated", "category", "tourist_impact_score", "impact_reason", "event_info", "references", "collected_at", "image_url", "date", "link", "source"]

        # 3. Map dict items to row lists
        rows_to_append = []
        for item in new_items_list:
            row = []
            for h in headers:
                val = item.get(h, "")
                # Handle nested dicts/lists for GSHEETS (convert to JSON string)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                elif pd.isna(val):
                    val = ""
                row.append(val)
            rows_to_append.append(row)

        # 4. Perform append operation
        if rows_to_append:
            # value_input_option='USER_ENTERED' allows formulas and numeric conversion
            ws.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            print(f"Successfully appended {len(rows_to_append)} rows to worksheet '{worksheet}'.")
            
        # 5. Clear Streamlit Cache to force reload next time
        st.cache_data.clear()
        return True

    except Exception as e:
        print(f"Error appending news to sheet: {e}")
        return False

def update_local_caches_with_new_topics(new_topics, date_str):
    """
    [APPEND ONLY] Syncs new topics into local JSON caches without full sheet downloads.
    Keeps Latest (7d) and Main (30d) tiers updated.
    """
    for file_path, limit_days in [(LATEST_NEWS_CACHE, 7), (LOCAL_NEWS_CACHE, 30)]:
        try:
            # Load existing
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except:
                        data = {}
            else:
                data = {}
            
            if not isinstance(data, dict): data = {}
            
            # Ensure day key exists
            if date_str not in data:
                data[date_str] = []
            
            # Simple title-based deduplication per day
            existing_titles = {t.get('title') for t in data[date_str]}
            added_count = 0
            for t in new_topics:
                if t.get('title') not in existing_titles:
                    data[date_str].append(utils.sanitize_news_topic(t))
                    added_count += 1
            
            # Trim to prescribed limits
            cutoff = (datetime.now() - timedelta(days=limit_days)).strftime("%Y-%m-%d")
            recent_data = {k: v for k, v in data.items() if k >= cutoff}
            
            # Save back
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(recent_data, f, ensure_ascii=False, indent=2)
                
            print(f"Cache {os.path.basename(file_path)} updated: +{added_count} items (Limit {limit_days}d)")
                
        except Exception as e:
            print(f"Error updating local cache {file_path}: {e}")

# --- VISITOR STATS (GSheets Backend) ---

def get_visitor_stats_gsheets(worksheet="stats"):
    """
    [READ] Google Sheets에서 방문자 통계를 가져옵니다. (gspread 직접 연동으로 안정성 확보)
    Returns: { "total": int, "date_YYYY-MM-DD": int }
    """
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        import toml

        # 1. Load secrets for gspread
        secrets = toml.load(".streamlit/secrets.toml")
        conn_info = secrets["connections"]["gsheets_news"]
        spreadsheet_url = conn_info["spreadsheet"]
        
        creds_dict = {
            "type": "service_account",
            "project_id": conn_info["project_id"],
            "private_key_id": conn_info["private_key_id"],
            "private_key": conn_info["private_key"].replace('\\n', '\n'),
            "client_email": conn_info["client_email"],
            "client_id": conn_info["client_id"],
            "auth_uri": conn_info["auth_uri"],
            "token_uri": conn_info["token_uri"],
            "auth_provider_x509_cert_url": conn_info["auth_provider_x509_cert_url"],
            "client_x509_cert_url": conn_info["client_x509_cert_url"]
        }

        # 2. Authenticate
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 3. Open and Read
        sh = client.open_by_url(spreadsheet_url)
        ws = sh.worksheet(worksheet)
        data = ws.get_all_records()
        
        if not data:
            return {"total": 0}
            
        # Convert to dict with safe int conversion
        stats_dict = {}
        for row in data:
            key = str(row.get('key', '')).strip()
            val = row.get('count', 0)
            try:
                stats_dict[key] = int(float(val))
            except:
                stats_dict[key] = 0
                
        return stats_dict

    except Exception as e:
        print(f"Visitor stats read error (gspread): {e}")
        # Fallback to Streamlit Connection if gspread fails
        try:
            conn = get_db_connection()
            if not conn: return {"total": 0}
            df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet, ttl=0)
            if df is None or df.empty: return {"total": 0}
            return dict(zip(df['key'], df['count']))
        except:
            return {"total": 0}

def increment_visitor_stats_gsheets(worksheet="stats"):
    """
    [WRITE] Google Sheets의 'total' 및 '오늘 날짜' 카운트를 1씩 증가시킵니다.
    Returns: (new_total, new_daily)
    """
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        import toml
        from datetime import datetime
        import pytz

        # 1. Load existing stats (via our new robust reader)
        stats = get_visitor_stats_gsheets(worksheet)
        
        # 2. Prepare keys
        bkk_tz = pytz.timezone('Asia/Bangkok')
        today_str = datetime.now(bkk_tz).strftime("%Y-%m-%d")
        
        key_total = "total"
        key_daily = f"date_{today_str}"
        
        # 3. Increment
        new_total = stats.get(key_total, 0) + 1
        new_daily = stats.get(key_daily, 0) + 1
        
        stats[key_total] = new_total
        stats[key_daily] = new_daily
        
        # 4. Save via gspread
        secrets = toml.load(".streamlit/secrets.toml")
        conn_info = secrets["connections"]["gsheets_news"]
        spreadsheet_url = conn_info["spreadsheet"]
        
        creds_dict = {
            "type": "service_account",
            "project_id": conn_info["project_id"],
            "private_key_id": conn_info["private_key_id"],
            "private_key": conn_info["private_key"].replace('\\n', '\n'),
            "client_email": conn_info["client_email"],
            "client_id": conn_info["client_id"],
            "auth_uri": conn_info["auth_uri"],
            "token_uri": conn_info["token_uri"],
            "auth_provider_x509_cert_url": conn_info["auth_provider_x509_cert_url"],
            "client_x509_cert_url": conn_info["client_x509_cert_url"]
        }

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sh = client.open_by_url(spreadsheet_url)
        ws = sh.worksheet(worksheet)
        
        # Prepare rows for update
        new_rows = [['key', 'count']]
        for k, v in stats.items():
            new_rows.append([k, v])
            
        # Bulk update
        ws.update(values=new_rows, range_name='A1')
        
        return new_total, new_daily
        
    except Exception as e:
        print(f"Error incrementing visitor stats (gspread): {e}")
        # Final fallback to 0,0 to avoid crashing app
        return 0, 0
