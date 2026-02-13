import sys
sys.path.append('/Users/jaewoo/Documents/news project')
import utils
import json
import pandas as pd
from datetime import datetime

def backfill():
    client = utils.get_hotel_gsheets_client()
    if not client:
        print("❌ No GSheets client")
        return

    # --- 1. Load Hotel Cache ---
    print("⏳ Loading Hotel Cache...")
    sh_hotel = client.open("hotel_cache_db")
    hotel_cache_sheet = sh_hotel.get_worksheet(0)
    hotel_data = hotel_cache_sheet.get_all_values()
    
    hotel_logs = []
    # Skip header
    for row in hotel_data[1:]:
        if len(row) >= 4:
            name = row[0]
            cached_date = row[1]
            try:
                raw_json = json.loads(row[3])
                rating = raw_json.get('info', {}).get('rating', 0.0)
                hotel_logs.append([name, rating, 'hotel', cached_date])
            except:
                continue
    print(f"✅ Found {len(hotel_logs)} hotel cache entries.")

    # --- 2. Load Restaurant Cache ---
    print("⏳ Loading Restaurant Cache...")
    try:
        sh_rest = client.open("cached_restaurants")
        rest_cache_sheet = sh_rest.get_worksheet(0)
        rest_data = rest_cache_sheet.get_all_records()
        
        rest_logs = []
        for row in rest_data:
            name = row.get('name')
            rating = row.get('rating')
            # Use 'analysis' field existence as a proxy for a meaningful "search"
            # though any entry in cache is a search.
            if name and rating:
                # Use current time or some default if date not available in rest cache
                # Based on get_cached_restaurants_sheet, there's no date column.
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rest_logs.append([name, rating, 'food', timestamp])
        print(f"✅ Found {len(rest_logs)} restaurant cache entries.")
    except Exception as e:
        print(f"⚠️ Restaurant cache skip: {e}")
        rest_logs = []

    # --- 3. Append to search_log ---
    print("⏳ Appending to search_log...")
    try:
        log_sheet = sh_hotel.worksheet("search_log")
        existing_data = log_sheet.get_all_records()
        existing_sigs = set([f"{r['name']}|{r['category']}" for r in existing_data])
        
        rows_to_add = []
        for log in hotel_logs + rest_logs:
            sig = f"{log[0]}|{log[2]}"
            if sig not in existing_sigs:
                rows_to_add.append(log)
        
        if rows_to_add:
            # GSheets append_rows can handle chunks if too large, but these caches are small (<100)
            log_sheet.append_rows(rows_to_add)
            print(f"🚀 Successfully backfilled {len(rows_to_add)} entries to search_log!")
        else:
            print("ℹ️ All cache entries already exist in search_log.")
            
    except Exception as e:
        print(f"❌ Backfill Error: {e}")

if __name__ == "__main__":
    backfill()
