import streamlit as st
import pandas as pd
from db_utils import SPREADSHEET_URL, get_db_connection

def dump():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect")
        return
    df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="news", ttl=0)
    print(df.head(10).to_json(orient='records', force_ascii=False, indent=2))

if __name__ == "__main__":
    dump()
