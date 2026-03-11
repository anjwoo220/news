import toml
import requests
import pandas as pd
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.auth.transport.requests

# DB Utils functions and classes are in db_utils.py. We'll use get_db_connection / save_news_to_sheet
from db_utils import SPREADSHEET_URL, load_news_from_sheet, save_news_to_sheet

def main():
    print("⏳ 구글 인증 정보 로드 중...")
    secrets = toml.load(".streamlit/secrets.toml")
    creds_dict = secrets["connections"]["gsheets_news"]
    
    # Needs drive.readonly to fetch revisions
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
    
    print("⏳ 시트의 전체 개정 기록(버전 내역) 검색 중...")
    revisions = drive_service.revisions().list(fileId=file_id).execute().get('revisions', [])
    
    headers = {
        'Authorization': 'Bearer ' + creds.token
    }
    
    past_df = None
    target_rev_id = None
    
    # Iterate backwards through revisions from newest to oldest
    print("⏳ 가장 적합한 과거(복원용) 데이타를 찾는 중...")
    found_past_data = False
    
    # Limit search to the last 20 revisions to save time
    search_revisions = revisions[-30:]
    search_revisions.reverse()
    
    for rev in search_revisions:
        rev_id = rev['id']
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv&gid=0&revision={rev_id}"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            csv_content = r.content.decode('utf-8')
            df = pd.read_csv(io.StringIO(csv_content))
            
            if 'date' in df.columns:
                # Clean up dates
                df['date'] = df['date'].astype(str).str.strip().str.split('T').str[0].str.split(' ').str[0]
                unique_dates = [d for d in df['date'].unique() if d != 'nan']
                
                # If we have multiple dates or dates older than today
                if any(d < "2026-03-11" for d in unique_dates):
                    print(f"✅ 유효한 과거 데이터를 찾았습니다! (버전: {rev.get('modifiedTime')}, 보존된 날짜들: {unique_dates})")
                    past_df = df
                    target_rev_id = rev_id
                    found_past_data = True
                    break

    if not found_past_data:
        print("❌ 유효한 과거 데이터를 찾지 못했습니다.")
        return

    print("⏳ 현재(오늘자) 뉴스를 안전하게 백업 시도 중...")
    current_news = load_news_from_sheet()
    if not current_news:
         current_news = {}
         
    # Ensure all data in past_df is put back into Dict-by-Date structure
    print("⏳ 과거 데이터와 오늘자 데이터를 안전하게 하나로 병합 중...")
    merged_news = {}
    
    # 1. Parse past_df back to dict
    records = past_df.to_dict(orient="records")
    for item in records:
        if pd.isna(item.get('date')): continue
        date_str = str(item['date'])
        
        if date_str not in merged_news:
             merged_news[date_str] = []
             
        # Clean NaNs
        clean_item = {k: (v if not pd.isna(v) else "") for k, v in item.items()}
        
        # Parse JSON fields
        for field in ['references', 'related_topics', 'event_info']:
            if field in clean_item and isinstance(clean_item[field], str):
                val = str(clean_item[field]).strip()
                if val.startswith('[') or val.startswith('{'):
                    try:
                        clean_item[field] = json.loads(val)
                    except:
                        try:
                            import ast
                            clean_item[field] = ast.literal_eval(val)
                        except: pass
        merged_news[date_str].append(clean_item)

    # 2. Add current_news (today) on top of past data
    for d, items in current_news.items():
         if d not in merged_news:
             merged_news[d] = items
         else:
             # Merge carefully to avoid duplicating
             existing_titles = {t['title'] for t in merged_news[d]}
             for current_item in items:
                 if current_item['title'] not in existing_titles:
                      merged_news[d].append(current_item)

    print(f"✅ 병합 완료! 총 추출된 날짜 수: {len(merged_news.keys())}")
    for d in sorted(merged_news.keys(), reverse=True):
         print(f"  - {d}: {len(merged_news[d])} 건")

    print("⏳ 구글 시트로 전체 데이터를 다시 업로드하고 덮어씌우는 중... (약 5-10초 소요)")
    success = save_news_to_sheet(merged_news)
    if success:
         print("🎉 복구 및 재-업로드가 성공적으로 완료되었습니다!")
         print("   이제 시스템의 뉴스 탭에서 과거 날짜를 정상적으로 선택하실 수 있습니다.")
    else:
         print("❌ 업로드 중 오류가 발생했습니다. (버그이거나 권한 문제일 수 있습니다)")

if __name__ == "__main__":
     main()
