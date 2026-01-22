import json
import os

def check_news():
    with open('data/news.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for date, items in data.items():
        for i, item in enumerate(items):
            refs = item.get('references')
            link = item.get('link')
            
            ref_url = None
            if isinstance(refs, list) and refs:
                if isinstance(refs[0], dict):
                    ref_url = refs[0].get('url')
                elif isinstance(refs[0], str):
                    ref_url = refs[0]
            
            if not ref_url or ref_url == '#':
                print(f"Date {date}, Item {i}: No ref_url. Link field: {link}")

if __name__ == "__main__":
    check_news()
