
import streamlit as st
import pandas as pd
from streamlit_gsheets_connection import GSheetsConnection

st.title("Google Sheets Connection Test")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.success("Connection Object Created!")
    
    st.write("Reading 'news' worksheet...")
    df = conn.read(worksheet="news", ttl=0)
    st.dataframe(df)
    
    if st.button("Add Test Row"):
        new_row = pd.DataFrame([{
            "date": "2024-01-01",
            "title": "Test Title",
            "summary": "Test Summary",
            "link": "http://test.com",
            "category": "Test"
        }])
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(worksheet="news", data=updated_df)
        st.success("Test Row Added! Please check your Google Sheet.")
        st.cache_data.clear()
        st.rerun()

except Exception as e:
    st.error(f"Connection Failed: {e}")
