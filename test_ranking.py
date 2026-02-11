
import utils
import pandas as pd
import numpy as np

print("--- Testing Refined Ranking Algorithm ---")
results = utils.get_top_places('hotel')
for r in results:
    print(f"#{r['rank']}: {r['name']} - Score: {r['rating']} (Count: {r['count']})")
