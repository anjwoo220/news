import json
import os

FEEDS_FILE = 'data/feeds.json'
if os.path.exists(FEEDS_FILE):
    with open(FEEDS_FILE, 'r') as f:
        feeds = json.load(f)
    print(f"Loaded {len(feeds)} feeds")
    for f in feeds:
        print(f" - {f}")
else:
    print("FEEDS_FILE not found")
