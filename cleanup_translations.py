import utils
import json
import os
import time
from db_utils import ARCHIVE_NEWS_CACHE, load_news_from_sheet, save_news_to_sheet, write_news_caches

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
            original_snapshot = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)

            # Translate Thai fields if needed
            for field in ['title', 'summary', 'full_translated']:
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
                        break # Success or non-retryable failure
                    
                    time.sleep(1) # Base delay

            utils.sanitize_news_topic(item)

            updated_snapshot = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if updated_snapshot != original_snapshot:
                date_updated = True
                updated_count += 1
        
        if date_updated:
            print(f"  -> Date {date} updated with new translations.")

    if updated_count > 0:
        print(f"Successfully updated {updated_count} fields across the database.")
        
        # Save local latest/main caches first to preserve progress
        try:
            write_news_caches(news_data)
            print("Successfully updated local latest/main news caches.")
        except Exception as e:
            print(f"Failed to save local caches: {e}")

        # Then attempt GSheet sync
        print("Syncing cleaned data back to Google Sheets...")
        success = save_news_to_sheet(news_data)
        if success:
            print("Successfully synced cleaned data back to Google Sheets.")
        else:
            print("Failed to sync to Google Sheets. Progress is saved locally in data/latest_news.json and data/news.json.")
    else:
        print("No Thai fields found (or all failed). Database is clean.")

    if os.path.exists(ARCHIVE_NEWS_CACHE):
        print("Checking local archive cache for year cleanup...")
        try:
            with open(ARCHIVE_NEWS_CACHE, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)

            before_snapshot = json.dumps(archive_data, ensure_ascii=False, sort_keys=True, default=str)
            utils.sanitize_news_dataset(archive_data)
            after_snapshot = json.dumps(archive_data, ensure_ascii=False, sort_keys=True, default=str)

            if before_snapshot != after_snapshot:
                with open(ARCHIVE_NEWS_CACHE, 'w', encoding='utf-8') as f:
                    json.dump(archive_data, f, ensure_ascii=False, indent=2)
                print("Archive cache year cleanup completed.")
            else:
                print("Archive cache was already clean.")
        except Exception as e:
            print(f"Failed to sanitize archive cache: {e}")

if __name__ == "__main__":
    # Ensure local directory exists
    if not os.path.exists('data'):
        os.makedirs('data')
    cleanup_translations()
