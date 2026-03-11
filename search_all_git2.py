import subprocess
import json

commits = subprocess.check_output("git log --pretty=format:%h data/news.json", shell=True).decode().split('\n')
dates_collected = set()

for commit in commits:
    try:
        out = subprocess.check_output(f"git show {commit}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
        d = json.loads(out.decode('utf-8'))
        dates_collected.update(d.keys())
    except:
        pass

all_dates = sorted(list(dates_collected))
import json
with open("recovered_git_news.json", "w") as f:
    json.dump(list(dates_collected), f)

print(f"Total unique dates found across ALL git history: {len(all_dates)}")
print(f"Oldest: {all_dates[0] if all_dates else 'None'}, Newest: {all_dates[-1] if all_dates else 'None'}")
