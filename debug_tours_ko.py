
import utils
import json
import streamlit as st
import os

# Mock streamlit session state
if 'language' not in st.session_state:
    st.session_state['language'] = 'Korean'

def debug_recommend_tours_ko():
    print("Debugging recommend_tours with Korean language...")
    who = "혼자"
    style = ["인생샷/사진"]
    budget = "적당함"
    region = "방콕"
    
    # Needs GEMINI_API_KEY to be set in environment or secrets
    # We want to see if the internal prompt construction is correct
    # I'll modify utils.py temporarily to print the prompt or just mock the call
    
    products_list = []
    # simulate load_tours
    t = {"id": 1, "name": "아유타야 선셋", "price": "45000", "type": ["역사"], "desc": "설명", "pros": "장점"}
    
    is_english = False
    p_name = t.get('name', 'Unknown')
    p_desc = t.get('desc', '')
    p_pros = t.get('pros', '')
    
    products_list.append(
        f"- ID {t['id']}. {p_name} (Price: {t['price']}): "
        f"Tag={t['type']}, Desc: {p_desc}, Pros: {p_pros}"
    )
    products_info = "\n".join(products_list)
    print("Products Info:")
    print(products_info)
    
    if not is_english:
        print("Korean Mode Prompt would be used.")

if __name__ == "__main__":
    debug_recommend_tours_ko()
