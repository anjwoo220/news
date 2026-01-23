import utils
import os
import google.generativeai as genai

def test_tough_translation():
    text = "태국 우타이타니, 찐다แดง 고추 가격 폭등: 돼지고기 가격 넘어섰다!"
    print(f"Original: {text}")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("API Key missing")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Aggressive Prompt
    prompt = f"""
    Translate all Thai script characters in the following text to Korean.
    - IMPORTANT: Every single Thai character (script) MUST be converted.
    - Use phonetic Hangul for names or terms if no direct translation exists (e.g., 'แดง' -> '댕').
    - The output must contain ZERO Thai script.
    - Maintain existing Korean text.
    
    Text: {text}
    """
    
    try:
        response = model.generate_content(prompt)
        print(f"Improved Plan Result: {response.text.strip()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_tough_translation()
