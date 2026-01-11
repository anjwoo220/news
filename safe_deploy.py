import os
import json
import subprocess
import shutil

NEWS_FILE = 'data/news.json'
REMOTE_NEWS_FILE = 'data/news_remote.json'

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
    return {}

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def merge_news(local_data, remote_data):
    """
    Merges remote news into local news.
    Strategy: Union by (formatted_date, title).
    """
    merged = local_data.copy()
    
    count_new = 0
    
    for date_key, remote_items in remote_data.items():
        if date_key not in merged:
            merged[date_key] = []
            
        local_items = merged[date_key]
        # Create a set of local signatures for quick lookup
        local_sigs = set()
        for item in local_items:
            # Use Link or Title as signature
            sig = item.get('link') or item.get('title')
            local_sigs.add(sig)
            
        for item in remote_items:
            sig = item.get('link') or item.get('title')
            if sig not in local_sigs:
                # Found a new item from remote!
                merged[date_key].append(item)
                local_sigs.add(sig) # Prevent dupes within remote list if any
                count_new += 1
                
    return merged, count_new

def main():
    print("🚀 Starting Safe Deployment...")
    
    # 1. Fetch Remote
    print("\n1. Fetching latest remote changes...")
    try:
        run_command("git fetch origin main")
    except:
        print("Warning: git fetch failed. Check network.")
        return

    # 2. Extract Remote News
    print("\n2. Checking for remote news data...")
    has_remote_news = False
    try:
        # Try to get data/news.json from origin/main
        content = run_command("git show origin/main:data/news.json")
        with open(REMOTE_NEWS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        has_remote_news = True
    except:
        print("Remote news.json not found or could not be read. Skipping merge.")

    # 3. Merge Logic
    if has_remote_news:
        print("\n3. Merging remote stats into local...")
        local_news = load_json(NEWS_FILE)
        remote_news = load_json(REMOTE_NEWS_FILE)
        
        merged_news, added_count = merge_news(local_news, remote_news)
        
        if added_count > 0:
            print(f"✅ Found and restored {added_count} missing articles from remote!")
            save_json(NEWS_FILE, merged_news)
            
            # Clean up
            os.remove(REMOTE_NEWS_FILE)
            
            # Stage the update
            run_command(f"git add {NEWS_FILE}")
            run_command('git commit -m "Auto-merge: Synced news data from remote"')
        else:
            print("Already up-to-date with remote news.")
            if os.path.exists(REMOTE_NEWS_FILE):
                os.remove(REMOTE_NEWS_FILE)

    # 4. Push
    print("\n4. Committing and Pushing to GitHub...")
    try:
        # Stage all changes (Code + Data)
        run_command("git add .")
        
        # Commit if there are changes
        try:
             run_command('git commit -m "Feat: National Events, Sidebar UI, Region Filters"')
        except:
             print("No changes to commit or commit failed (maybe clean working dir).")

        # Pull with rebase first to be safe for code changes
        run_command("git pull --rebase origin main")
        run_command("git push origin main")
        print("\n🎉 Deployment Complete! Local and Remote are synced.")
    except Exception as e:
        print(f"\n❌ Push failed: {e}")
        print("Please resolve conflicts manually.")

if __name__ == "__main__":
    main()
