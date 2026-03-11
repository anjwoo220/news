import toml
from google.oauth2 import service_account
from googleapiclient.discovery import build

secrets = toml.load(".streamlit/secrets.toml")
creds_dict = secrets["connections"]["gsheets_news"]
creds = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"]
)

try:
    drive_service = build('drive', 'v3', credentials=creds)
    # The sheet ID
    file_id = "1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8"
    revisions = drive_service.revisions().list(fileId=file_id).execute()
    print([r.get('modifiedTime') for r in revisions.get('revisions', [])][-10:])
except Exception as e:
    print("Drive API Error:", e)
