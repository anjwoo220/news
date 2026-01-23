import utils
import json
import os
import time
from db_utils import load_news_from_sheet, save_news_to_sheet

def cleanup_translations():
    print("Starting translation cleanup for all existing news...")
    
    # Load from sheet to get full corpus
    news_data = load_news_from_sheet()
    if not news_data:
        print("No news data loaded.")
        return

    updated_count = 0
    total_dates = len(news_data)
    
    for d_idx, (date, items) in enumerate(news_data.items()):
        print(f"[{d_idx+1}/{total_dates}] Checking date: {date}")
        date_updated = False
        
        for item in items:
            # Check fields
            for field in ['title', 'summary']:
                text = item.get(field, "")
                if text and utils.is_thai(text):
                    print(f"  -> Translating {field}: {text[:30]}...")
                    
                    # Retry logic for Rate Limits
                    max_retries = 3
                    for attempt in range(max_retries):
                        translated = utils.translate_text(text)
                        
                        if "429" in translated or "quota" in translated.lower():
                            wait = 30 * (attempt + 1)
                            print(f"     !! Rate Limit hit. Waiting {wait}s...")
                            time.sleep(wait)
                            continue
                        
                        if translated != text:
                            item[field] = translated
                            # If it still has Thai characters, log it as a persistent issue
                            if utils.is_thai(translated):
                                print(f"     ?? Still contains Thai: {translated[:30]}")
                            else:
                                date_updated = True
                                updated_count += 1
                        break # Success or non-retryable failure
                    
                    time.sleep(1) # Base delay
        
        if date_updated:
            print(f"  -> Date {date} updated with new translations.")

    if updated_count > 0:
        print(f"Successfully updated {updated_count} fields across the database.")
        
        # ALWAYS save local news.json first to preserve progress
        try:
            with open('data/news.json', 'w', encoding='utf-8') as f:
                json.dump(news_data, f, ensure_ascii=False, indent=2)
            print("Successfully updated local data/news.json.")
        except Exception as e:
            print(f"Failed to save local news.json: {e}")

        # Then attempt GSheet sync
        print("Syncing cleaned data back to Google Sheets...")
        success = save_news_to_sheet(news_data)
        if success:
            print("Successfully synced cleaned data back to Google Sheets.")
        else:
            print("Failed to sync to Google Sheets. Progress is saved locally in data/news.json.")
    else:
        print("No Thai fields found (or all failed). Database is clean.")

if __name__ == "__main__":
    # Ensure local directory exists
    if not os.path.exists('data'):
        os.makedirs('data')
    cleanup_translations()
