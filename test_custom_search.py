import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import random

def custom_search_wongnai(restaurant_name):
    """
    Directly scrapes Google Search results to find Wongnai URL.
    More reliable than googlesearch-python in many environments.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    
    queries = [
        f"site:wongnai.com {restaurant_name}",
        f"wongnai {restaurant_name}"
    ]
    
    for query in queries:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded_query}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    if "wongnai.com/restaurants/" in href or "wongnai.com/r/" in href:
                        # Handle Google's redirection URL if necessary
                        if "/url?q=" in href:
                            href = href.split("/url?q=")[1].split("&")[0]
                        return href
            time.sleep(random.uniform(1, 2)) # Simple anti-throttle
        except Exception as e:
            print(f"Search error: {e}")
            
    return None

if __name__ == "__main__":
    print(f"URL: {custom_search_wongnai('Zabb One Ratchada Soi 5')}")
    print(f"URL: {custom_search_wongnai('Jeh O Chula')}")
