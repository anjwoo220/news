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
    
    print(f"총 발견된 전체 리비전 수: {len(revisions)}")
    
    # Check the oldest non-empty revision
    for rev in revisions:
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid=0&revision={rev['id']}"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            csv_content = r.content.decode('utf-8')
            df = pd.read_csv(io.StringIO(csv_content))
            if 'date' in df.columns and not df.empty:
                df['date'] = df['date'].astype(str).str.strip().str.split('T').str[0].str.split(' ').str[0]
                unique_dates = [d for d in df['date'].unique() if d != 'nan']
                if unique_dates:
                    print(f"가장 처음 복원 가능한 시트의 수정일시 (Revision ID: {rev['id']}): {rev['modifiedTime']}")
                    print(f"그 안에 들어있는 날짜들: {unique_dates}")
                    break

if __name__ == "__main__":
    main()
