import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

def get_gsheet_client():
    creds_path = "board-484107-65691b0765f5.json"
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return gspread.authorize(creds)

client = get_gsheet_client()
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8"
spreadsheet = client.open_by_url(SPREADSHEET_URL)
worksheet = spreadsheet.worksheet("Jobs")
data = worksheet.get_all_values()
print(f"Total rows in Jobs: {len(data)}")
if len(data) > 1:
    print("Last 3 rows:")
    for row in data[-3:]:
        print(row)
