import streamlit as st
import pandas as pd
from db_utils import SPREADSHEET_URL, load_news_from_sheet
import json

def debug_sheet():
    print("Checking news data...")
    # We can't use st.connection() easily in a script, 
    # but we can try to use a local simulation if we have the JSON fallback logic
    # Wait, load_news_from_sheet will use the connection.
    # I'll just check data/news.json which is supposed to be what safe_deploy.py pushes.
    
    if os.path.exists('data/news.json'):
        with open('data/news.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        dates = sorted(data.keys(), reverse=True)
        for date in dates[:3]:
            print(f"\nDate: {date}")
            items = data[date]
            for i, item in enumerate(items[:2]):
                print(f"  Item {i}: {item.get('title')}")
                print(f"    link: {item.get('link')}")
                print(f"    references: {item.get('references')}")
    else:
        print("data/news.json not found")

if __name__ == "__main__":
    import os
    debug_sheet()
