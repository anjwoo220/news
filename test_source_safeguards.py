import utils
import os
import json

def test_source_safeguards():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import toml
            secrets = toml.load(".streamlit/secrets.toml")
            api_key = secrets.get("GEMINI_API_KEY")
        except:
            pass
            
    if not api_key:
        print("GEMINI_API_KEY not found in environment or secrets.")
        return

    # Mock news items
    # 1. Low impact news with missing source (should be filtered)
    # 2. High impact news with missing source (should be included and sanitized)
    test_items = [
        {
            "title": "Minor traffic delays in Bangkok",
            "link": "https://example.com/traffic",
            "summary": "Some local streets are experiencing minor traffic delays this morning.",
            "source": "[MISSING_SOURCE]"
        },
        {
            "title": "URGENT: Major flooding predicted for Phuket tomorrow",
            "link": "https://example.com/flood",
            "summary": "Authorities warn of significant flooding in Phuket due to heavy monsoon rains. Tourists are advised to avoid low-lying areas.",
            "source": "[MISSING_SOURCE]"
        }
    ]

    print("Running analyze_news_with_gemini with test items...")
    result, error = utils.analyze_news_with_gemini(test_items, api_key, current_time="12:00")

    if error:
        print(f"Error: {error}")
        return

    print("\nAnalysis Result:")
    topics = result.get('topics', [])
    print(f"Total topics returned: {len(topics)}")
    
    for i, topic in enumerate(topics):
        print(f"[{i+1}] Title: {topic['title']}")
        print(f"    Score: {topic['tourist_impact_score']}")
        print(f"    References:")
        for ref in topic.get('references', []):
            print(f"      - Source: {ref.get('source')} | URL: {ref.get('url')}")
        
    # Check if low impact one was skipped and high impact one has sanitized source
    titles = [t['title'] for t in topics]
    skipped_low = not any("traffic" in t.lower() for t in titles)
    included_high = any("flood" in t.lower() for t in titles)
    
    sanitized = True
    for t in topics:
        for ref in t['references']:
            if ref['source'] in ['[MISSING_SOURCE]', 'None', None]:
                sanitized = False

    print("\n--- Summary ---")
    print(f"Skipped low impact: {skipped_low}")
    print(f"Included high impact: {included_high}")
    print(f"Sources sanitized: {sanitized}")

if __name__ == "__main__":
    test_source_safeguards()
