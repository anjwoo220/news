
from db_utils import save_news_to_sheet, load_news_from_sheet
from datetime import datetime

print("Testing Sheet Connection...")
try:
    current = load_news_from_sheet()
    print(f"Loaded {len(current)} dates from sheet.")
    
    # Create a dummy entry to test write
    today = datetime.now().strftime("%Y-%m-%d")
    dummy_item = {
        "title": "Test Entry " +  datetime.now().strftime("%H:%M:%S"),
        "date": today,
        "summary": "This is a connection test.",
        "link": "https://example.com",
        "source": "Tester"
    }
    
    if today not in current:
        current[today] = []
    
    current[today].insert(0, dummy_item)
    
    print("Attempting to save to sheet...")
    success = save_news_to_sheet(current)
    if success:
        print("Save SUCCESS!")
    else:
        print("Save FAILED.")
        
except Exception as e:
    print(f"Test Failed with Exception: {e}")
