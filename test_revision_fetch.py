import toml
from google.oauth2 import service_account
from googleapiclient.discovery import build
import urllib.request
import csv

secrets = toml.load(".streamlit/secrets.toml")
creds_dict = secrets["connections"]["gsheets_news"]
creds = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/spreadsheets"]
)

try:
    drive_service = build('drive', 'v3', credentials=creds)
    file_id = "1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8"
    revisions = drive_service.revisions().list(fileId=file_id).execute().get('revisions', [])
    rev_id = revisions[-2]['id']
    
    import requests
    import os
    import google.auth.transport.requests

    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}/revisions/{rev_id}?alt=media"
    
    headers = {
        'Authorization': 'Bearer ' + creds.token
    }
    
    # Wait, exporting a Google Sheet revision isn't directly supported via alt=media.
    # We must use Google Drive export API but for revisions? The Drive v3 API does not support exporting a specific revision of a Google Workspace document. 
    # Actually, we can use the web URL with `access_token`
    url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid=0&revision={rev_id}"
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    print("Preview:", r.text[:200])

except Exception as e:
    import traceback
    traceback.print_exc()

