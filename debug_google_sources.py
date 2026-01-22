import requests
import feedparser
import urllib.parse

def debug_google_news():
    query = "Thailand Tourism"
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:24h&hl=en-TH&gl=TH&ceid=TH:en&scoring=n"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=10)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            print(f"Found {len(feed.entries)} entries.")
            for i, entry in enumerate(feed.entries[:20]):
                source_dict = entry.get('source', {})
                source_title = source_dict.get('title')
                print(f"[{i}] Title: {entry.title[:50]}...")
                print(f"    Raw Source Dict: {source_dict}")
                print(f"    Source Title: {source_title}")
                if source_title is None:
                    print("    !!! DETECTED NULL SOURCE TITLE")
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_google_news()
