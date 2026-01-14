import sys
sys.path.append('.')
import utils
import googlesearch

def verify_search(name):
    print(f"Testing search for: {name}")
    url = utils.search_wongnai_restaurant(name)
    if url:
        print(f"✅ Success! Found URL: {url}")
    else:
        print("❌ Failed to find URL.")
    print("-" * 30)

if __name__ == "__main__":
    # Test cases
    verify_search("Zabb One Ratchada Soi 5")
    verify_search("Jeh O Chula")
    verify_search("Hilton Sukhumvit")
