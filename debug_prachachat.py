
import requests
from bs4 import BeautifulSoup

url = "https://www.prachachat.net/politics/news-1950895"

print(f"Testing Session Request to: {url}")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,th;q=0.8',
    'Referer': 'https://www.google.com/',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}
session.headers.update(headers)

try:
    # First visit homepage to get cookies?
    print("Visiting homepage...")
    session.get("https://www.prachachat.net/", timeout=5)
    
    print("Visiting article...")
    resp = session.get(url, timeout=10)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.content, 'html.parser')
        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text() for p in paragraphs])
        print(f"Extracted Text Length: {len(text)}")
        print(f"Preview: {text[:200]}")
    else:
        print(f"Headers: {resp.headers}")
except Exception as e:
    print(f"Session Request failed: {e}")
