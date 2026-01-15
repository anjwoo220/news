
from db_utils import save_news_to_sheet, load_news_from_sheet
from datetime import datetime

print("Cleaning up test entry...")
try:
    current = load_news_from_sheet()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if today in current:
        original_len = len(current[today])
        # Remove items with title starting with "Test Entry"
        current[today] = [item for item in current[today] if not item['title'].startswith("Test Entry")]
        new_len = len(current[today])
        
        if original_len != new_len:
            print(f"Removed {original_len - new_len} test entries.")
            save_news_to_sheet(current)
            print("Cleanup Saved.")
        else:
            print("No test entries found.")
    else:
        print("No entries for today.")

except Exception as e:
    print(f"Cleanup Failed: {e}")
