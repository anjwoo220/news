
import requests
import feedparser
import urllib.parse

query = "Thailand Tourism"
encoded_query = urllib.parse.quote(query)
rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:24h&hl=en-TH&gl=TH&ceid=TH:en&scoring=n"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
}

print(f"Fetching {rss_url} with headers...")
try:
    response = requests.get(rss_url, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        feed = feedparser.parse(response.content)
        print(f"Entries found: {len(feed.entries)}")
        if len(feed.entries) > 0:
            print(f"First entry: {feed.entries[0].title}")
    else:
        print("Failed to fetch.")
except Exception as e:
    print(f"Error: {e}")
