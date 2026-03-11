import pandas as pd
sheet_url = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8/export?format=csv&gid=0"
try:
    df = pd.read_csv(sheet_url)
    print("Dates in CSV:", df['date'].unique())
except Exception as e:
    print("Failed to read CSV:", e)
