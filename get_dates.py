import toml
import gspread
from google.oauth2 import service_account

try:
    secrets = toml.load(".streamlit/secrets.toml")
    creds_dict = secrets["connections"]["gsheets_news"]
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(creds_dict["spreadsheet"]).worksheet("news")
    dates = sheet.col_values(1)[1:] # Assuming Date is col A
    from collections import Counter
    print("Dates count:", Counter(dates))
except Exception as e:
    import traceback
    traceback.print_exc()
