import crawl_jobs
import os

print("Testing HanAsia...")
try:
    results = crawl_jobs.crawl_hanasia(max_pages=1)
    print(f"HanAsia found {len(results)} jobs")
except Exception as e:
    print(f"HanAsia failed: {e}")

print("\nTesting KyominThai...")
try:
    results = crawl_jobs.crawl_kyominthai(max_pages=1)
    print(f"KyominThai found {len(results)} jobs")
except Exception as e:
    print(f"KyominThai failed: {e}")

print("\nTesting JobThai...")
try:
    results = crawl_jobs.crawl_jobthai()
    print(f"JobThai found {len(results)} jobs")
except Exception as e:
    print(f"JobThai failed: {e}")

print("\nTesting Saramin...")
try:
    results = crawl_jobs.crawl_saramin()
    print(f"Saramin found {len(results)} jobs")
except Exception as e:
    print(f"Saramin failed: {e}")

# JobsDB usually takes time and needs playwright
print("\nTesting JobsDB...")
try:
    results = crawl_jobs.crawl_jobsdb()
    print(f"JobsDB found {len(results)} jobs")
except Exception as e:
    print(f"JobsDB failed: {e}")
