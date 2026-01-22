import pandas as pd
import json
import os
from streamlit_gsheets import GSheetsConnection

# Mock Streamlit Secrets/Connection for a standalone script is tricky.
# I will use the service account JSON directly with gspread if I can, 
# or just look at the public CSV if it's public.
# The URL in secrets says '?usp=sharing'. Usually, anyone with a link can view.

import ssl
import certifi

import urllib.request

def check_sheet_public():
    # Bypass SSL issue
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    sheet_url = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8/export?format=csv&gid=0"
    try:
        with urllib.request.urlopen(sheet_url, context=ssl_context) as response:
            df = pd.read_csv(response)
        
        print(f"Loaded {len(df)} rows from public CSV export.")
        print(f"Loaded {len(df)} rows from public CSV export.")
        
        # Check for 'None' in source column (case-insensitive)
        none_mask = df['source'].astype(str).str.contains('None', case=False, na=False)
        none_rows = df[none_mask]
        
        if not none_rows.empty:
            print(f"Found {len(none_rows)} rows with 'None' in source:")
            for i, row in none_rows.iterrows():
                print(f"- Date: {row['date']} | Title: {row['title']} | Source: {row['source']}")
        else:
            print("No rows with literal 'None' in source column.")

        # Check for NaN as well
        nan_rows = df[df['source'].isna()]
        if not nan_rows.empty:
            print(f"Found {len(nan_rows)} rows with NaN source.")
            
    except Exception as e:
        print(f"Error checking public sheet: {e}")

if __name__ == "__main__":
    check_sheet_public()
