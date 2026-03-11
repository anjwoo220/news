import subprocess
import json
import sys

commits = subprocess.check_output("git log --pretty=format:%h data/news.json", shell=True).decode().split('\n')
dates_collected = set()

for commit in commits[300:700]:
    try:
        out = subprocess.check_output(f"git show {commit}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
        d = json.loads(out.decode('utf-8'))
        dates_collected.update(d.keys())
    except:
        pass

all_dates = sorted(list(dates_collected))
print(f"Oldest date found in commits 300 to 700: {all_dates[0] if all_dates else 'None'}")
