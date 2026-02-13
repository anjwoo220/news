import sys
sys.path.append('/Users/jaewoo/Documents/news project')
import utils
import pandas as pd
import os

CSV_FILE = "data/search_log.csv"

if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    if not df.empty:
        client = utils.get_hotel_gsheets_client()
        if client:
            sh = client.open("hotel_cache_db")
            try:
                sheet = sh.worksheet("search_log")
                # Get existing to avoid duplicates if possible, or just append
                existing = sheet.get_all_records()
                existing_names = set([r['name'] + r['timestamp'] for r in existing])
                
                rows_to_add = []
                for _, row in df.iterrows():
                    sig = str(row['name']) + str(row['timestamp'])
                    if sig not in existing_names:
                        rows_to_add.append([row['name'], row['rating'], row['category'], row['timestamp']])
                
                if rows_to_add:
                    sheet.append_rows(rows_to_add)
                    print(f"✅ Migrated {len(rows_to_add)} rows from local CSV to GSheets.")
                else:
                    print("ℹ️ No new rows to migrate.")
            except Exception as e:
                print(f"❌ Migration Error: {e}")
else:
    print("ℹ️ No local CSV found.")
