
import utils
import os
import toml

# Setup API Key
if os.path.exists(".streamlit/secrets.toml"):
    with open(".streamlit/secrets.toml", "r") as f:
        secrets = toml.load(f)
        os.environ["google_maps_api_key"] = secrets.get("google_maps_api_key", "")

api_key = os.environ.get("google_maps_api_key")

print("--- Final Verification of Brand Mapping ---")
city = "Pattaya"
name_kr = "센타라"

print(f"Calling utils.fetch_hotel_candidates('{name_kr}', '{city}')...")
res = utils.fetch_hotel_candidates(name_kr, city, api_key)
names = [r['name'] for r in res] if res else []

print(f"Found {len(names)} items:")
for n in names:
    print(f"- {n}")

targets = ["Centara Life Maris Resort Jomtien", "Centara Nova Hotel"]
print("\nChecking Targets:")
for t in targets:
    found = any(t.lower() in n.lower() for n in names)
    print(f" - '{t}': {'✅ Found' if found else '❌ Missing'}")
