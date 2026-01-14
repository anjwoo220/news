import os
import google.generativeai as genai

def gemini_search_wongnai(restaurant_name, api_key):
    """
    Uses Gemini to identify the most likely Wongnai URL for a restaurant.
    Robust fallback when traditional search fails.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Please provide the MOST LIKELY Wongnai restaurant URL for the following restaurant name in Thailand:
    Restaurant Name: {restaurant_name}
    
    Rules:
    - Return ONLY the URL (string).
    - It must be a valid 'wongnai.com/restaurants/...' or 'wongnai.com/r/...' link.
    - If you are unsure, provide the most famous branch URL.
    - DO NOT include any other text, markdown, or explanation.
    """
    
    try:
        response = model.generate_content(prompt)
        url = response.text.strip()
        # Clean up in case Gemini provides markdown
        if "http" in url:
            url = url.split("http")[1].split()[0]
            url = "http" + url
        
        if "wongnai.com" in url:
            return url
        return None
    except Exception as e:
        print(f"Gemini search error: {e}")
        return None

if __name__ == "__main__":
    # Test with a mock key or just see the prompt logic
    # In real app, we would use the session key
    pass
