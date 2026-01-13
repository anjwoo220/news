
import streamlit as st
import json
import os
import pandas as pd
from db_utils import save_news_to_sheet

st.title("📂 News Data Migration Tool")
st.caption("Migrate local `data/news.json` to Google Sheets")

NEWS_FILE = 'data/news.json'

def load_local_json():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception as e:
                st.error(f"Failed to load JSON: {e}")
                return None
    return None

if st.button("🚀 Start Migration", type="primary"):
    st.info(f"Loading {NEWS_FILE}...")
    
    data = load_local_json()
    
    if not data:
        st.error("No data found in news.json or file missing.")
    else:
        # Check size
        total_days = len(data)
        total_items = sum(len(items) for items in data.values())
        
        st.write(f"Found {total_days} days of news, totaling {total_items} items.")
        
        with st.spinner("Uploading to Google Sheets... (This may take a moment)"):
            if save_news_to_sheet(data):
                st.success("✅ 이사가 완료되었습니다! (Migration Complete)")
                st.balloons()
            else:
                st.error("❌ Migration Failed. Check console logs.")
