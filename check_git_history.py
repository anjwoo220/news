import json
import subprocess

for i in range(1, 40):
    try:
        out = subprocess.check_output(f"git show HEAD~{i}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
        d = json.loads(out)
        dates = list(d.keys())
        if len(dates) > 1 and "2026-02-27" in dates:
            print(f"HEAD~{i} - found older dates!")
            print(dates)
            break
        elif i % 10 == 0:
            print(f"Checked HEAD~{i}")
    except:
        pass
