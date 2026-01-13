
import db_utils
from datetime import datetime
import pytz
import re
import sys

# Redirect output to file for easier reading
with open("verify_result.txt", "w") as log:
    def print_log(msg):
        print(msg)
        log.write(msg + "\n")

    try:
        print_log("Health Check: Accessing Google Sheets...")
        news_data = db_utils.load_news_from_sheet()
        
        if not news_data:
            print_log("❌ No data found in Google Sheets.")
        else:
            # Sort dates
            dates = sorted(news_data.keys(), reverse=True)
            latest_date = dates[0]
            print_log(f"✅ Latest Data Date: {latest_date}")
            
            items = news_data[latest_date]
            print_log(f"✅ Items on {latest_date}: {len(items)}")
            
            if items:
                latest_item = items[0]
                print_log(f"\n[Sample Item Check]")
                print_log(f"- Title: {latest_item.get('title')}")
                print_log(f"- Summary: {latest_item.get('summary')[:50]}...")
                
                # Check Korean characters
                title = latest_item.get('title', '')
                has_hangul = bool(re.search(r'[가-힣]', title))
                
                if has_hangul:
                    print_log("✅ Translation (Korean) detected in title.")
                else:
                    print_log("⚠️ Title does not strictly contain Korean. (Might be English news or failed translation?)")
                    
    except Exception as e:
        print_log(f"❌ Error during verification: {e}")
