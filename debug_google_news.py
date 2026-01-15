
import utils

print("Testing Google News Fetch...")
items = utils.fetch_google_news_rss(query="Thailand Tourism")
print(f"Items found: {len(items)}")
if len(items) > 0:
    print(items[0])
