
import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import json
from datetime import datetime

# SPREADSHEET URL (Public/Shared)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8/edit?usp=sharing"

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
