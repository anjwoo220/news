import json
import os

def check_news():
    with open('data/news.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for date, items in data.items():
        for i, item in enumerate(items):
            refs = item.get('references')
            if refs is None:
                print(f"Date {date}, Item {i}: references is None")
            elif isinstance(refs, str):
                print(f"Date {date}, Item {i}: references is a string: {refs[:50]}")
            elif isinstance(refs, list):
                if not refs:
                    print(f"Date {date}, Item {i}: references is an empty list")
                else:
                    for j, ref in enumerate(refs):
                        if not isinstance(ref, dict):
                            print(f"Date {date}, Item {i}: ref {j} is not a dict: {ref}")
                        elif 'url' not in ref:
                            print(f"Date {date}, Item {i}: ref {j} is missing 'url'")
            else:
                print(f"Date {date}, Item {i}: references is unexpected type {type(refs)}")

if __name__ == "__main__":
    check_news()
