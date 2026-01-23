import utils
import os
import json

def test_on_existing():
    titles = [
        "เฝ้าระวังจุดความร้อน พื้นที่นาข้าวพบมากสุด 3,561 จุด แนะสวมใส่หน้ากากอนามัย",
        "กัมพูชาส่งรายงานประเมินความเสียหายปราสาทพระวิหาร ยื่นยูเนสโก และองค์กรระหว่างประเทศตรวจสอบ",
        "태국 우타이타니, 찐다แดง 고추 가격 폭등: 돼지고기 가격 넘어섰다!"
    ]
    
    # Ensure API Key is available
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment.")
        return

    for title in titles:
        print(f"\nOriginal: {title}")
        is_thai = utils.is_thai(title)
        print(f"Is Thai detected: {is_thai}")
        
        if is_thai:
            translated = utils.translate_text(title)
            print(f"Translated: {translated}")
            if translated == title:
                print("!! Translation FAILED (returned original)")

if __name__ == "__main__":
    test_on_existing()
