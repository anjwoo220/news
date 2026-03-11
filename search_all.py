import json
import subprocess

for i in range(1, 100):
    try:
        out = subprocess.check_output(f"git show HEAD~{i}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
        d = json.loads(out)
        dates = list(d.keys())
        # Print minimum date found
        if dates:
            min_date = min(dates)
            if min_date < "2026-02-28":
                print(f"HEAD~{i}: Found dates earlier than 02-28. Earliest is {min_date}")
                break
    except:
        pass
