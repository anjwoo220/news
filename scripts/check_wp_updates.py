import sys
import requests
from datetime import datetime, timezone

WP_API_URL = "https://thai-today.com/wp-json/wp/v2/posts?per_page=1"
THRESHOLD_HOURS = 24

def check_wp_updates():
    print(f"🔍 Checking WordPress latest post at: {WP_API_URL}")
    try:
        response = requests.get(WP_API_URL, timeout=15)
        response.raise_for_status()
        posts = response.json()
        
        if not posts:
            print("❌ ERROR: No posts found in WordPress!")
            sys.exit(1)
            
        latest_post = posts[0]
        # WP date_gmt format: "2026-04-26T12:34:56"
        post_date_str = latest_post.get("date_gmt")
        if not post_date_str:
            print("❌ ERROR: Latest post has no date_gmt field!")
            sys.exit(1)
            
        post_date = datetime.fromisoformat(post_date_str).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        
        hours_diff = (now - post_date).total_seconds() / 3600
        
        print(f"📝 Latest post: {latest_post.get('title', {}).get('rendered', 'Unknown')}")
        print(f"⏰ Published at: {post_date_str} GMT")
        print(f"⏳ Time since latest post: {hours_diff:.2f} hours")
        
        if hours_diff > THRESHOLD_HOURS:
            print(f"\n❌ CRITICAL ALARM: The latest post is older than {THRESHOLD_HOURS} hours.")
            print("WordPress automatic updates might be broken or there's no news.")
            # Trigger GitHub Actions failure
            sys.exit(1)
            
        print(f"\n✅ All good! WordPress is up-to-date (under {THRESHOLD_HOURS} hours).")
        
    except Exception as e:
        print(f"❌ Exception occurred while checking WordPress: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_wp_updates()
