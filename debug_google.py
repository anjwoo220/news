import googlesearch

def debug_search(query):
    print(f"Searching for: {query}")
    try:
        results = googlesearch.search(query, num_results=5)
        for i, url in enumerate(results):
            print(f"{i+1}: {url}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 30)

if __name__ == "__main__":
    debug_search("Zabb One Ratchada Soi 5")
    debug_search("wongnai Jeh O Chula")
    debug_search("python tutorial")
