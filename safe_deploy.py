import os
import json
import subprocess
import shutil

NEWS_FILE = 'data/news.json'
EVENTS_FILE = 'data/events.json'
REMOTE_NEWS_FILE = 'data/news_remote.json'
REMOTE_EVENTS_FILE = 'data/events_remote.json'

def run_command(cmd):
    """Runs a shell command and raises error if it fails."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise Exception(f"Command failed: {cmd}")
    return result.stdout.strip()

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {} # Return empty dict if not dict structure expected, but events is list.
    # Note: load_json needs to handle LIST for events.json and DICT for news.json
    # Wait, news.json IS a dict {date: []}.
    # events.json IS a LIST [{}].
    # I should adjust load_json to be generic or just use generic exception.

def load_json_generic(file_path, default_type=dict):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return default_type()
    return default_type()

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def merge_news(local_data, remote_data):
    """
    Merges local news into remote news (Remote is Truth).
    Strategy: Start with Remote. Add Local only if invalid/missing in Remote.
    But actually, we want to KEEP Remote versions of same items.
    So: Base = Remote. Append Local items that don't exist in Remote.
    """
    merged = remote_data.copy()
    count_new = 0
    
    # 1. Index Remote Signatures
    remote_sigs = set()
    for date_key, items in merged.items():
        for item in items:
            sig = item.get('link') or item.get('title')
            remote_sigs.add(sig)
            
    # 2. Scan Local for New Items
    for date_key, local_items in local_data.items():
        if date_key not in merged:
            merged[date_key] = []
            
        for item in local_items:
            sig = item.get('link') or item.get('title')
            if sig not in remote_sigs:
                # This is a NEW item from local (e.g. fresh crawl)
                merged[date_key].append(item)
                remote_sigs.add(sig)
                count_new += 1
                
    return merged, count_new

def merge_events(local_list, remote_list):
    """
    Merges local events into remote events (Remote is Truth).
    Strategy: Base = Remote. Add Local if new.
    """
    merged = list(remote_list) # Start with Remote
    count_new = 0
    
    remote_sigs = set((e.get('title'), e.get('date')) for e in merged)
    
    for item in local_list:
        sig = (item.get('title'), item.get('date'))
        if sig not in remote_sigs:
            merged.append(item)
            remote_sigs.add(sig)
            count_new += 1
            
    return merged, count_new

def main():
    print("🚀 Starting Safe Deployment (News + Events)...")
    
    # 1. Fetch Remote
    print("\n1. Fetching latest remote changes...")
    try:
        run_command("git fetch origin main")
    except:
        print("Warning: git fetch failed. Check network.")
        return

    # 2. Sync News
    print("\n2. Syncing News Data...")
    has_remote_news = False
    try:
        content = run_command("git show origin/main:data/news.json")
        with open(REMOTE_NEWS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        has_remote_news = True
    except:
        print("Remote news.json not found. Skipping.")

    if has_remote_news:
        local_news = load_json_generic(NEWS_FILE, dict)
        remote_news = load_json_generic(REMOTE_NEWS_FILE, dict)
        
        merged_news, added_count = merge_news(local_news, remote_news)
        
        if added_count > 0:
            print(f"✅ Restored {added_count} news articles from remote!")
            save_json(NEWS_FILE, merged_news)
        if os.path.exists(REMOTE_NEWS_FILE):
             os.remove(REMOTE_NEWS_FILE)

    # 3. Sync Events
    print("\n3. Syncing Events Data...")
    has_remote_events = False
    try:
        content = run_command("git show origin/main:data/events.json")
        with open(REMOTE_EVENTS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        has_remote_events = True
    except:
        print("Remote events.json not found (first time?). Skipping.")

    if has_remote_events:
        local_events = load_json_generic(EVENTS_FILE, list)
        remote_events = load_json_generic(REMOTE_EVENTS_FILE, list)
        
        merged_events, added_count = merge_events(local_events, remote_events)
        
        if added_count > 0:
            print(f"✅ Restored {added_count} events from remote!")
            save_json(EVENTS_FILE, merged_events)
        if os.path.exists(REMOTE_EVENTS_FILE):
             os.remove(REMOTE_EVENTS_FILE)

    # 3-B. Sync Big Events (big_events.json)
    print("\n3-B. Syncing Big Match Data...")
    BIG_EVENTS_FILE = 'data/big_events.json'
    REMOTE_BIG_EVENTS_FILE = 'data/big_events_remote.json'
    
    has_remote_big = False
    try:
        content = run_command("git show origin/main:data/big_events.json")
        with open(REMOTE_BIG_EVENTS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        has_remote_big = True
    except:
        print("Remote big_events.json not found. Skipping.")

    if has_remote_big:
        local_big = load_json_generic(BIG_EVENTS_FILE, list)
        remote_big = load_json_generic(REMOTE_BIG_EVENTS_FILE, list)
        
        # Reuse merge_events logic as structure is similar (Title/Date/etc)
        merged_big, added_count = merge_events(local_big, remote_big)
        
        if added_count > 0:
            print(f"✅ Restored {added_count} big events from remote!")
            save_json(BIG_EVENTS_FILE, merged_big)
        if os.path.exists(REMOTE_BIG_EVENTS_FILE):
             os.remove(REMOTE_BIG_EVENTS_FILE)

    # 3-C. Sync Trends (Magazine)
    print("\n3-C. Syncing Trend Data...")
    TRENDS_FILE = 'data/trends.json'
    REMOTE_TRENDS_FILE = 'data/trends_remote.json'
    
    has_remote_trends = False
    try:
        content = run_command("git show origin/main:data/trends.json")
        with open(REMOTE_TRENDS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        has_remote_trends = True
    except:
        print("Remote trends.json not found. Skipping.")
        
    if has_remote_trends:
        local_trends = load_json_generic(TRENDS_FILE, list)
        remote_trends = load_json_generic(REMOTE_TRENDS_FILE, list)
        
        # Merge logic for Trends: Remote Priority
        def merge_trends_local(local_list, remote_list):
            merged = list(remote_list) # Base = Remote
            count_new = 0
            remote_sigs = set((t.get('title'), t.get('link')) for t in merged)
            
            for item in local_list:
                sig = (item.get('title'), item.get('link'))
                if sig not in remote_sigs:
                    merged.append(item)
                    remote_sigs.add(sig)
                    count_new += 1
            return merged, count_new

        merged_trends, added_count = merge_trends_local(local_trends, remote_trends)
        
        if added_count > 0:
            print(f"✅ Restored {added_count} trends from remote!")
            save_json(TRENDS_FILE, merged_trends)
        if os.path.exists(REMOTE_TRENDS_FILE):
             os.remove(REMOTE_TRENDS_FILE)

    # 4. Push
    print("\n4. Committing and Pushing to GitHub...")
    try:
        # Force add data files to ensure they are tracked (if they exist)
        files_to_add = []
        for fpath in ["data/news.json", "data/events.json", "data/big_events.json", "data/trends.json"]:
            if os.path.exists(fpath):
                files_to_add.append(fpath)
        
        if files_to_add:
            run_command(f"git add -f {' '.join(files_to_add)}")
            
        run_command("git add .")
        try:
             run_command('git commit -m "Auto-Sync: News & Events"')
        except:
             print("No changes to commit from sync.")

        # CRITICAL: Use -Xtheirs to ensure OUR local (merged) version wins in rebase conflicts.
        # We have already manually merged the data content in Python, so our file is the source of truth.
        print("Pulling with rebase (preferring local changes)...")
        run_command("git pull --rebase -Xtheirs origin main")
        
        run_command("git push origin main")
        print("\n🎉 Deployment Complete! Local and Remote are synced.")
    except Exception as e:
        print(f"\n❌ Push failed: {e}")
        print("Please resolve conflicts manually.")

if __name__ == "__main__":
    main()
