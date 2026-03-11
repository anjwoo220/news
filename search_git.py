import subprocess
import json
import sys

# We're going to scan commit history of data/news.json to find older dates
commits = subprocess.check_output("git log --pretty=format:%h data/news.json", shell=True).decode().split('\n')
print(f"Total commits modifying news.json: {len(commits)}")

oldest_date = "2026-03-31" # init with arbitrary future date
oldest_commit = None
dates_collected = set()

# sample every 5th commit to be fast, starting from most recent
for i in range(0, min(200, len(commits)), 10):
    commit = commits[i]
    try:
        out = subprocess.check_output(f"git show {commit}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
        d = json.loads(out.decode('utf-8'))
        dates = list(d.keys())
        dates_collected.update(dates)
    except Exception as e:
        pass

print(f"All dates ever found in sampled Git history:\n{sorted(list(dates_collected))}")
