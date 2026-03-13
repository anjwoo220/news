import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
url = "https://www.hanasia.com/%EA%B5%AC%EC%9D%B8%EA%B5%AC%EC%A7%81"
resp = requests.get(url, headers=HEADERS, timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")
posts = soup.select(".tpl-forum-list-title a")
print(f"Total posts found: {len(posts)}")
for p in posts[:10]:
    print(f"Title: {p.get_text(strip=True)}")
