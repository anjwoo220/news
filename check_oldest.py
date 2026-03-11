import toml
import requests
import pandas as pd
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.auth.transport.requests

def main():
    secrets = toml.load(".streamlit/secrets.toml")
    creds_dict = secrets["connections"]["gsheets_news"]
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
    )
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    
    drive_service = build('drive', 'v3', credentials=creds)
    file_id = "1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8"
    revisions = drive_service.revisions().list(fileId=file_id).execute().get('revisions', [])
    
    headers = {'Authorization': 'Bearer ' + creds.token}
    
    first_meaningful_rev = None
    if len(revisions) > 1:
        # Check first 5 revisions to find the oldest non-empty one
        for i in range(1, min(6, len(revisions))):
            rev = revisions[i]
            url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid=0&revision={rev['id']}"
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                csv_content = r.content.decode('utf-8')
                df = pd.read_csv(io.StringIO(csv_content))
                if 'date' in df.columns and not df.empty:
                    from db_utils import load_news_from_sheet
                    current = load_news_from_sheet()
                    df['date'] = df['date'].astype(str).str.strip().str.split('T').str[0].str.split(' ').str[0]
                    unique_dates = [d for d in df['date'].unique() if d != 'nan']
                    print(f"가장 오래된 버전 기록 (수정일: {rev['modifiedTime']}):\n{unique_dates}")
                    print(f"현재 시트에 총 탑재된 날짜 목록 (최신순):\n{sorted(current.keys(), reverse=True)}")
                    return
    print("No valid oldest data found.")

if __name__ == "__main__":
    main()
