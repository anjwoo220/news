import subprocess
import json

def get_unique_dates():
    commits = subprocess.check_output("git log --pretty=format:%h data/news.json", shell=True).decode().split('\n')
    all_dates = set()
    print(f"Scanning {len(commits)} commits...")
    
    # Sample every 50 commits to get a quick overview of the range
    for i in range(0, len(commits), 50):
        commit = commits[i]
        try:
            out = subprocess.check_output(f"git show {commit}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
            d = json.loads(out.decode('utf-8'))
            all_dates.update(d.keys())
        except:
            pass
            
    # Also check the very first and last commits
    for commit in [commits[0], commits[-1]]:
        try:
            out = subprocess.check_output(f"git show {commit}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
            d = json.loads(out.decode('utf-8'))
            all_dates.update(d.keys())
        except:
            pass

    return sorted(list(all_dates))

if __name__ == "__main__":
    dates = get_unique_dates()
    print(f"Found {len(dates)} unique dates.")
    print(f"Range: {dates[0]} to {dates[-1]}")
    print(f"Sample dates: {dates[:10]} ... {dates[-10:]}")
