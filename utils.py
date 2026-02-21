import feedparser
import googlesearch
import google.generativeai as genai
from datetime import datetime, timedelta
import time
import json
import os
# import certifi
# os.environ["SSL_CERT_FILE"] = certifi.where()
import certifi
import os
os.environ["SSL_CERT_FILE"] = certifi.where()
import requests
import re
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import csv
from streamlit_gsheets import GSheetsConnection
import streamlit as st
import pathlib

# --- GA4 (Google Analytics 4) Injection ---
@st.cache_resource
def inject_ga(ga_id):
    """
    Injects Google Analytics 4 tracking code into the Streamlit 'index.html' file.
    Runs once per server session using @st.cache_resource.
    """
    try:
        # 1. Locate index.html path
        # Streamlit library usually resides in site-packages/streamlit
        import streamlit
        st_path = pathlib.Path(streamlit.__path__[0])
        index_path = st_path / "static" / "index.html"

        if not index_path.exists():
            return

        # 2. Read index.html content
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 3. Check for existing GA4 script
        if f"googletagmanager.com/gtag/js?id={ga_id}" in html_content:
            return

        # 4. Prepare GA4 script
        ga_script = f"""
    <!-- Global site tag (gtag.js) - Google Analytics -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        gtag('config', '{ga_id}');
    </script>
"""
        # 5. Inject script before </head> tag
        new_html_content = html_content.replace("</head>", f"{ga_script}</head>")

        # 6. Write back to index.html
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(new_html_content)

    except Exception:
        # Fail silently as per requirements
        pass

# --- 다국어 지원 (Multi-language Support) ---
UI_TEXT = {
    "main_title": {"ko": "오늘의 태국 🇹🇭", "en": "Thai Today 🇹🇭"},
    "main_subtitle": {"ko": "방콕 맛집, 뉴스, 여행 필수 앱", "en": "Your Essential Guide to Bangkok"},
    "nav_news": {"ko": "📰 뉴스", "en": "📰 News"},
    "nav_hotel": {"ko": "🏨 호텔", "en": "🏨 Hotel"},
    "nav_food": {"ko": "🍽️ 맛집", "en": "🍽️ Taste"},
    "nav_guide": {"ko": "📘 가이드", "en": "📘 Tour"},
    "nav_tour": {"ko": "🎒 투어", "en": "🎒 Tour"},
    "nav_taxi": {"ko": "🚕 택시", "en": "🚕 Taxi"},
    "nav_event": {"ko": "🎪 이벤트", "en": "🎪 Events"},
    "nav_board": {"ko": "🗣️ 게시판", "en": "🗣️ Board"},
    "sidebar_menu": {"ko": "📌 메뉴 선택", "en": "📌 Menu Selection"},
    "sidebar_info": {"ko": "💡 정보 & 지원", "en": "💡 Info & Support"},
    "sidebar_lang": {"ko": "🌐 언어 설정 (Language)", "en": "🌐 Language Settings"},
    "about_title": {"ko": "ℹ️ 서비스 정보 (About)", "en": "ℹ️ About Service"},
    "about_desc": {
        "ko": "실시간 태국 여행 정보, 뉴스, 핫플을 한눈에! 태국 정보가 필요한 모든 분들을 위한 AI 기반 브리핑 서비스입니다.",
        "en": "Real-time Thailand travel info, news, and hot spots at a glance! An AI-powered briefing service for everyone who needs info about Thailand."
    },
    "search_news": {"ko": "🔍 날짜 검색 및 옵션", "en": "🔍 Date Search & Options"},
    "search_keyword": {"ko": "🔎 키워드 검색", "en": "🔎 Keyword Search"},
    "search_date": {"ko": "📅 날짜 선택", "en": "📅 Select Date"},
    "reset_search": {"ko": "🔄 검색어 초기화", "en": "🔄 Reset Search"},
    "news_header": {"ko": "📅 {} 브리핑", "en": "📅 {} Briefing"},
    "air_quality": {"ko": "🌬️ 방콕 대기질", "en": "🌬️ Bangkok Air Quality"},
    "exchange_rate": {"ko": "💵 환율 (KRW/THB)", "en": "💵 Exchange Rate"},
    "weather_humidity": {"ko": "습도", "en": "Humidity"},
    "stat_today": {"ko": "오늘", "en": "Today"},
    "stat_total": {"ko": "전체", "en": "Total"},
    "hotel_fact": {"ko": "🏨 호텔 팩트체크", "en": "🏨 Hotel Fact Check"},
    "food_fact": {"ko": "🍜 맛집 팩트체크", "en": "🍜 Taste Fact Check"},
    "food_desc": {"ko": "인스타 맛집의 진실! 구글 맵 데이터로 진짜 맛집인지 판별합니다.", "en": "The truth about trending spots! Verify real restaurants using Google Maps data."},
    "search_rest": {"ko": "🔍 맛집 검색", "en": "🔍 Search Restaurant"},
    "rest_placeholder": {"ko": "예: 팁사마이, Thip Samai, Zabb One", "en": "e.g., Thip Samai, Zabb One"},
    "hotel_search": {"ko": "🏨 호텔 검색", "en": "🏨 Search Hotel"},
    "hotel_placeholder": {"ko": "예: 방콕 매리어트, 페닌슐라 방콕", "en": "e.g., Marriott Bangkok, Peninsula"},
    "analysis_btn": {"ko": "📊 팩트체크 분석 시작", "en": "📊 Start Fact Check Analysis"},
    "searching": {"ko": "🔍 검색 중...", "en": "🔍 Searching..."},
    "analyzing": {"ko": "🔍 데이터 분석 중...", "en": "🔍 Analyzing data..."},
    "no_results": {"ko": "검색 결과가 없습니다.", "en": "No results found."},
    "basic_info": {"ko": "ℹ️ 기본 정보", "en": "ℹ️ Basic Info"},
    "fact_report": {"ko": "✅ 팩트체크 리포트", "en": "✅ Fact Check Report"},
    "pros_cons": {"ko": "⚖️ 장단점 요약", "en": "⚖️ Pros & Cons"},
    "verdict": {"ko": "📢 요약 및 판정", "en": "📢 Verdict & Summary"},
    "best_review": {"ko": "💬 베스트 리뷰", "en": "💬 Best Review"},
    "share_btn": {"ko": "🔗 요약 결과 공유하기", "en": "🔗 Share Summary"},
    "rating_caption": {"ko": "5.0점 만점 · 리뷰 {num_reviews:,}개", "en": "Out of 5.0 · {num_reviews:,} reviews"},
    "recommend_menu": {"ko": "🔥 리뷰어들의 추천 메뉴", "en": "🔥 Recommended by Reviewers"},
    "photo_caption": {"ko": "📍 사진 출처: Google Maps 사용자 리뷰", "en": "📍 Source: Google Maps user reviews"},
    "price_range": {"ko": "💰 가격대", "en": "💰 Price Range"},
    "cuisine_type": {"ko": "🍽️ 요리 종류", "en": "🍽️ Cuisine"},
    "opening_status": {"ko": "🕐 영업상태", "en": "🕐 Status"},
    "photos": {"ko": "📸 사진", "en": "📸 Photos"},
    "hotel_city": {"ko": "지역 (City)", "en": "City"},
    "hotel_find": {"ko": "🔍 호텔 찾기", "en": "🔍 Find Hotel"},
    "hotel_select": {"ko": "검색된 호텔 선택", "en": "Select a hotel"},
    "hotel_back": {"ko": "⬅️ 검색 결과로 돌아가기", "en": "⬅️ Back to results"},
    "pros_title": {"ko": "✅ 장점", "en": "✅ Pros"},
    "cons_title": {"ko": "❌ 단점 & 주의사항", "en": "❌ Cons & Cautions"},
    "location_title": {"ko": "📍 위치 및 동선", "en": "📍 Location & Traffic"},
    "room_title": {"ko": "🛏️ 룸 컨디션", "en": "🛏️ Room Condition"},
    "service_title": {"ko": "🍽️ 서비스 & 조식", "en": "🍽️ Service & Breakfast"},
    "facility_title": {"ko": "🏊‍♂️ 수영장 & 부대시설", "en": "🏊‍♂️ Pool & Facilities"},
    "score_title": {"ko": "📊 팩트체크 점수", "en": "📊 Fact Check Score"},
    "cleanliness": {"ko": "청결도", "en": "Cleanliness"},
    "location": {"ko": "위치", "en": "Location"},
    "comfort": {"ko": "편안함", "en": "Comfort"},
    "value": {"ko": "가성비", "en": "Value"},
    "share_friend": {"ko": "📢 친구에게 공유하기 (복사)", "en": "📢 Share with friends (Copy)"},
    "share_caption": {"ko": "👆 위 텍스트 우측 상단 복사 버튼을 눌러 카톡에 붙여넣으세요!", "en": "👆 Click the copy button in the top right to share."},
    "hotel_desc": {"ko": "광고 없는 '찐' 후기 분석! 구글 맵 리뷰를 냉철하게 검증해드립니다.", "en": "Ad-free review analysis! Verifying Google Maps reviews with AI objectivity."},
    "issue_label": {"ko": "**[실시간 방콕 이슈]**", "en": "**[Real-time BKK Issue]**"},
    "as_of": {"ko": "{} 기준", "en": "as of {}"},
    "guide_title": {"ko": "📘 태국 여행 가이드", "en": "📘 Travel Guide"},
    "guide_desc": {"ko": "현지인처럼 여행하기! 실속 있는 태국 여행 꿀팁을 모았습니다.", "en": "Travel like a local! Essential tips for your Thailand trip."},
    "back_to_list": {"ko": "⬅️ 목록으로 돌아가기", "en": "⬅️ Back to list"},
    "share_help": {"ko": "📍 이 글이 도움이 되셨다면 공유해주세요!", "en": "📍 Share this if it was helpful!"},
    "no_guide": {"ko": "📝 아직 등록된 여행 가이드가 없습니다. 곧 유용한 글이 업데이트됩니다!", "en": "📝 No guides available yet. Stay tuned!"},
    "read_more": {"ko": "📖 자세히 보기", "en": "📖 Read More"},
    "taxi_title": {"ko": "🚕 택시/뚝뚝 요금 판독기", "en": "🚕 Taxi/TukTuk Fare Reader"},
    "taxi_desc": {"ko": "방콕 시내 교통비, 바가지인지 아닌지 1초 만에 판독해드립니다.", "en": "Check if your Bangkok taxi fare is fair in 1 second."},
    "route_set": {"ko": "📍 경로 설정 (장소 검색)", "en": "📍 Route Settings (Search)"},
    "from": {"ko": "출발지 (From)", "en": "From"},
    "to": {"ko": "도착지 (To)", "en": "To"},
    "search": {"ko": "🔍 검색", "en": "🔍 Search"},
    "calc_fare": {"ko": "💸 경로 및 요금 계산", "en": "💸 Calculate Fare"},
    "distance": {"ko": "📏 예상 거리", "en": "📏 Estimated Distance"},
    "duration": {"ko": "⏱️ 소요 시간", "en": "⏱️ Estimated Time"},
    "fare_table": {"ko": "💰 교통수단별 적정 요금표", "en": "💰 Fair Fare by Transport"},
    "tour_title": {"ko": "🎒 AI 투어 코디네이터", "en": "🎒 AI Travel Planner"},
    "tour_desc": {"ko": "당신의 취향에 딱 맞는 태국 여행을 설계해드립니다. 원하는 조건을 선택하세요!", "en": "Design a Thailand trip that fits your style. Select your preferences!"},
    "tour_who": {"ko": "누구와 함께 가시나요?", "en": "Who are you traveling with?"},
    "tour_style": {"ko": "어떤 스타일의 여행을 선호하시나요?", "en": "What is your travel style?"},
    "tour_budget": {"ko": "예산은 어느 정도 생각하시나요?", "en": "What is your budget?"},
    "tour_find_btn": {"ko": "🚀 나에게 맞는 투어 찾기", "en": "🚀 Find Tours for Me"},
    "tour_result_title": {"ko": "✨ AI 추천 투어 결과", "en": "✨ AI Recommended Tours"},
    "tour_reason": {"ko": "추천 이유", "en": "Why we recommend this"},
    "tour_pros": {"ko": "장점", "en": "Pros"},
    "tour_tip": {"ko": "꿀팁", "en": "Tip"},
    "tour_region_selector": {"ko": "떠나시는 여행지를 선택해주세요! 🇹🇭", "en": "Select your destination! 🇹🇭"},
    # Planner Options Mapping
    "who_alone": {"ko": "혼자", "en": "Alone"},
    "who_couple": {"ko": "연인/부부", "en": "Couple"},
    "who_friend": {"ko": "친구", "en": "Friends"},
    "who_child": {"ko": "가족(아이동반)", "en": "Family (with children)"},
    "who_parent": {"ko": "가족(부모님)", "en": "Family (with parents)"},
    "style_healing": {"ko": "힐링/마사지", "en": "Healing/Massage"},
    "style_photo": {"ko": "인생샷/사진", "en": "Photo-centric"},
    "style_history": {"ko": "역사/문화", "en": "History/Culture"},
    "style_activity": {"ko": "액티비티/스릴", "en": "Activity/Thrills"},
    "style_food": {"ko": "맛집/식도락", "en": "Food/Gourmet"},
    "style_night": {"ko": "야경/로맨틱", "en": "Night View/Romantic"},
    "style_unique": {"ko": "이색체험", "en": "Unique Experience"},
    "trip_duration": {"ko": "🗓️ 여행 기간", "en": "🗓️ Trip Duration"},
    "planner_title": {"ko": "📝 {} 자유여행 플래너", "en": "📝 {} DIY Trip Planner"},
    "planner_guide": {"ko": "위 목록에서 마음에 드는 투어를 '담기' 버튼으로 추가해보세요! AI가 일정을 짜드립니다. 🤖", "en": "Add tours you like from the list above using the 'Add' button! AI will create an itinerary for you. 🤖"},
    "planner_cart": {"ko": "🛒 내 여행 코스", "en": "🛒 My Trip Route"},
    "budget_low": {"ko": "가성비(저렴)", "en": "Economy (Budget)"},
    "budget_mid": {"ko": "적당함", "en": "Moderate"},
    "budget_high": {"ko": "럭셔리/프리미엄", "en": "Luxury (Premium)"},
    "tour_fail": {"ko": "AI 추천을 가져오는데 실패했습니다. 아래 전체 목록에서 직접 선택해주세요!", "en": "Failed to get AI recommendations. Please select from the list below!"},
    "added_to_cart": {"ko": "✅ 담기 완료", "en": "✅ Added"},
    "add_to_cart": {"ko": "➕ 일정에 담기", "en": "➕ Add to Trip"},
    "all_tours_title": {"ko": "{} 투어 전체 목록 ({}개)", "en": "All {} Tours ({} items)"},
    "board_title": {"ko": "🗣️ 여행자 수다방", "en": "🗣️ Traveler's Board"},
    "board_desc": {"ko": "여행 팁, 질문, 건의사항 등 자유롭게 이야기를 나눠보세요!", "en": "Share tips, ask questions, or suggest features!"},
    "write_btn": {"ko": "등록하기 📝", "en": "Post 📝"},
    "nickname": {"ko": "닉네임", "en": "Nickname"},
    "password": {"ko": "비밀번호 (삭제용 숫자 4자리)", "en": "Password (4 digits for deletion)"},
    "content": {"ko": "내용", "en": "Content"},
    "write_expander": {"ko": "✍️ 글쓰기 (여기를 눌러주세요)", "en": "✍️ Write a post (Click here)"},
    "prev": {"ko": "⬅️ 이전", "en": "⬅️ Previous"},
    "next": {"ko": "다음 ➡️", "en": "Next ➡️"},
    "other": {"ko": "기타 (직접 입력)", "en": "Other (Manual)"},
    "no_events": {"ko": "📝 아직 등록된 이벤트가 없습니다.", "en": "📝 No events scheduled yet."},
    "event_date": {"ko": "📅 진행 기간", "en": "📅 Duration"},
    "event_place": {"ko": "📍 장소", "en": "📍 Location"},
    "menu_info": {"ko": "🍽️ 메뉴 정보", "en": "🍽️ Menu Information"},
    "menu_search_btn": {"ko": "🍽️ 메뉴판 이미지 검색 (Google)", "en": "🍽️ Search Menu Images (Google)"},
    "menu_search_caption": {"ko": "✨ 구글 이미지 검색을 통해 메뉴판 사진들을 모아봅니다.", "en": "✨ Discover menu photos via Google Image search."},
    "clear_results": {"ko": "🗑️ 결과 지우기", "en": "🗑️ Clear Results"},
    "recent_history": {"ko": "🕒 최근 본 맛집 히스토리", "en": "🕒 Recent Restaurant History"},
    "delete_history": {"ko": "기록 삭제", "en": "Clear History"},
    "delete_post": {"ko": "삭제하기", "en": "Delete"},
    "confirm_pw": {"ko": "비밀번호 확인", "en": "Confirm Password"},
    "view_detail_again": {"ko": "🔍 상세 분석 다시보기", "en": "🔍 View Details Again"},
    "news_cat": {"ko": "카테고리", "en": "Category"},
    "all": {"ko": "전체", "en": "All"},
    "share_page": {"ko": "📋 카톡 공유용 텍스트 생성 (현재 페이지)", "en": "📋 Generate Share Text (Current Page)"},
    "no_news_results": {"ko": "조건에 맞는 뉴스가 없습니다.", "en": "No news matches the criteria."},
    "no_news_update": {"ko": "😴 아직 업데이트된 뉴스가 없습니다. (잠시 후 다시 확인해주세요)", "en": "😴 No news updates yet. Please check back later."},
    "view_full_article": {"ko": "📄 기사 전문 보기", "en": "📄 View Full Article"},
    "summary_only": {"ko": "⚠️ 이 기사는 요약본만 제공됩니다.", "en": "⚠️ This article only provides a summary."},
    "related_share": {"ko": "🔗 관련 기사 & 공유", "en": "🔗 Related Articles & Share"},
    "cat_politics": {"ko": "🏛️ 정치/사회", "en": "🏛️ Politics/Society"},
    "cat_economy": {"ko": "💼 경제", "en": "💼 Economy"},
    "cat_travel": {"ko": "✈️ 여행/관광", "en": "✈️ Travel/Tourism"},
    "cat_culture": {"ko": "🎭 문화/엔터", "en": "🎭 Culture/Ent"},
    # Status Dashboard Labels
    "weather_label": {"ko": "방콕 날씨", "en": "Bangkok Weather"},
    "air_quality_label": {"ko": "미세먼지", "en": "Air Quality"},
    "exchange_buy_label": {"ko": "환율 (살 때)", "en": "Rate (Buy)"},
    "exchange_sell_label": {"ko": "환율 (팔 때)", "en": "Rate (Sell)"},
    "currency_unit": {"ko": "원", "en": " KRW"},
    # AQI Status
    "aqi_good": {"ko": "좋음", "en": "Good"},
    "aqi_moderate": {"ko": "보통", "en": "Moderate"},
    "aqi_unhealthy": {"ko": "나쁨", "en": "Unhealthy"},
    "aqi_very_unhealthy": {"ko": "매우나쁨", "en": "Very Unhealthy"},
    "aqi_loading": {"ko": "로딩중", "en": "Loading"},
    "aqi_error": {"ko": "오류", "en": "Error"},
    # Tour Tab
    "tour_title": {"ko": "🎒 AI 여행 코디네이터", "en": "🎒 AI Travel Coordinator"},
    "tour_desc": {"ko": "여행 스타일을 알려주시면, 실패 없는 현지 투어를 추천해 드려요!", "en": "Tell us your travel style, and we'll recommend the best local tours!"},
    "tour_who": {"ko": "누구와 함께 하시나요?", "en": "Who are you traveling with?"},
    "tour_style": {"ko": "선호하는 스타일은?", "en": "What's your preferred style?"},
    "tour_budget": {"ko": "선호하는 가격대는?", "en": "Preferred price range?"},
    "tour_find_btn": {"ko": "✨ 내 취향에 딱 맞는 투어 찾기", "en": "✨ Find My Perfect Tour"},
    "tour_spinner": {"ko": "AI가 수천 개의 후기를 분석 중입니다... 🤖", "en": "AI is analyzing thousands of reviews... 🤖"},
    "tour_result_title": {"ko": "🎯 당신을 위한 AI 추천 투어", "en": "🎯 AI-Recommended Tours for You"},
    "tour_book_btn": {"ko": "👉 최저가 예약하기 (Klook)", "en": "👉 Book at Best Price (Klook)"},
    "tour_all_list": {"ko": "📋 투어 전체 목록 보기", "en": "📋 View All Tours"},
    "tour_fallback": {"ko": "🌏 클룩(Klook)에서 태국 투어 전체보기 (2,000개+)", "en": "🌏 Browse All Thailand Tours on Klook (2,000+)"},
    "tour_no_match": {"ko": "🤔 마음에 드는 투어가 없으신가요?", "en": "🤔 Didn't find what you're looking for?"},
    "tour_reason": {"ko": "💡 추천 이유", "en": "💡 Why We Recommend This"},
    "tour_tip": {"ko": "🎯 꿀팁", "en": "🎯 Pro Tip"},
    "tour_pros": {"ko": "👍 핵심 포인트", "en": "👍 Key Highlights"},
}

# --- Shared UI Constants ---
DURATION_OPTIONS = [
    "당일치기 (Day Trip)",
    "1박 2일 (1 Night 2 Days)",
    "2박 3일 (2 Nights 3 Days)",
    "3박 4일 (3 Nights 4 Days)",
    "4박 5일 (4 Nights 5 Days)",
    "5박 6일 (5 Nights 6 Days)",
    "1주일 이상 (1 Week+)",
    "장기 여행 (Long-term)"
]

def parse_trip_duration(duration_str):
    """
    Parses max days from duration string.
    e.g. "당일치기 (Day Trip)" -> 1
         "1박 2일 (1 Night 2 Days)" -> 2
         "3박 4일 (3 Nights 4 Days)" -> 4
    """
    import re
    if "당일" in duration_str or "Day Trip" in duration_str:
        return 1
    
    # Try to find "X일" or "X Days"
    match = re.search(r'(\d+)\s*일', duration_str)
    if match:
        return int(match.group(1))
    
    match_en = re.search(r'(\d+)\s*Days', duration_str, re.IGNORECASE)
    if match_en:
        return int(match_en.group(1))
    
    if "1주일" in duration_str or "1 Week" in duration_str:
        return 7
    if "장기" in duration_str or "Long-term" in duration_str:
        return 14
    
    return 3 # Default fallback

def t(key):
    """
    Returns translated text based on st.session_state['language'].
    Defaults to 'ko' if not found or if session state is missing.
    """
    lang = st.session_state.get('language', 'Korean')
    lang_code = "en" if lang == "English" else "ko"
    
    if key in UI_TEXT:
        return UI_TEXT[key].get(lang_code, UI_TEXT[key].get("ko", key))
    return key

def detect_browser_language():
    """
    Detects the user's browser language from the Accept-Language header.
    Returns 'Korean' if Korean is detected, 'English' otherwise (default for non-Korean users).
    
    Uses st.context.headers which is available in Streamlit >= 1.37.0.
    Falls back to 'English' if headers cannot be read (for Travelpayouts reviewers).
    """
    try:
        # Streamlit >= 1.37.0: use st.context.headers
        headers = st.context.headers
        accept_lang = headers.get("Accept-Language", "")
        
        # Check if Korean is in the Accept-Language header
        if "ko" in accept_lang.lower():
            return "Korean"
        else:
            return "English"  # Default to English for non-Korean users
    except Exception:
        # Fallback: Default to English for international users / reviewers
        return "English"

import streamlit as st
import streamlit.components.v1 as components

# --- Scroll to Top Helper (Anchor 방식) ---
def scroll_to_top(key_suffix=None):
    """
    앵커 요소로 화면을 스크롤합니다.
    scrollIntoView 메서드를 사용하여 좌표 계산 없이 확실하게 이동.
    
    사용 전 페이지에 아래 앵커를 심어야 함:
    st.markdown('<div id="news-top-anchor"></div>', unsafe_allow_html=True)
    
    Args:
        key_suffix: HTML에 포함될 고유값 (매번 다른 값 필요)
    """
    import streamlit.components.v1 as components
    import time
    
    # key_suffix가 없으면 timestamp 사용
    if key_suffix is None:
        key_suffix = int(time.time() * 1000)
    
    # 약간의 딜레이(150ms)를 줘서 화면이 다 그려진 뒤 점프하도록 함
    js = f"""
    <!-- scroll_anchor_trigger_{key_suffix} -->
    <script>
        setTimeout(function() {{
            const anchor = window.parent.document.getElementById("news-top-anchor");
            if (anchor) {{
                anchor.scrollIntoView({{ behavior: "auto", block: "start" }});
            }}
        }}, 150);
    </script>
    """
    components.html(js, height=0, width=0)

# --- Head 태그 코드 주입 Helper ---
def inject_head_code(code_string):
    """
    HTML 코드를 부모 윈도우의 <head> 태그에 삽입합니다.
    Travelpayouts 등 제3자 서비스 인증 코드 삽입에 사용.
    
    Args:
        code_string: 삽입할 HTML 코드 (meta 태그, script 태그 등)
    
    Example:
        inject_head_code('<meta name="tp-verification" content="abc123" />')
    """
    import streamlit.components.v1 as components
    import time
    import html
    
    if not code_string or not code_string.strip():
        return
    
    # JavaScript에서 안전하게 사용하기 위해 escape 처리
    # 단, HTML 태그는 그대로 유지해야 하므로 줄바꿈/따옴표만 처리
    safe_code = code_string.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
    
    # 고유 key를 위한 timestamp
    unique_id = int(time.time() * 1000)
    
    js = f"""
    <!-- head_inject_{unique_id} -->
    <script>
        (function() {{
            // 이미 삽입되었는지 체크 (중복 방지)
            var existingMeta = window.parent.document.head.querySelector('[data-tp-injected]');
            if (existingMeta) return;
            
            // 코드를 head에 삽입
            var codeToInject = `{safe_code}`;
            var tempDiv = document.createElement('div');
            tempDiv.innerHTML = codeToInject;
            
            // 각 요소를 head에 추가
            while (tempDiv.firstChild) {{
                var node = tempDiv.firstChild;
                if (node.nodeType === 1) {{ // Element node
                    node.setAttribute('data-tp-injected', 'true');
                }}
                window.parent.document.head.appendChild(node);
            }}
        }})();
    </script>
    """
    components.html(js, height=0, width=0)

# --- SEO: Dynamic Page Title ---
def set_page_title(title):
    """
    Dynamically updates the browser tab title using JavaScript.
    Call this at the start of each tab/page to update the title for SEO.
    
    Args:
        title: The new page title to display in the browser tab
    """
    import streamlit.components.v1 as components
    import time
    
    # Escape special characters for JavaScript
    safe_title = title.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
    unique_id = int(time.time() * 1000)
    
    js = f"""
    <!-- page_title_{unique_id} -->
    <script>
        window.parent.document.title = "{safe_title}";
    </script>
    """
    components.html(js, height=0, width=0)

# --- SEO: Meta Description Injection ---
def inject_meta_description(description):
    """
    Injects or updates the <meta name="description"> tag for SEO.
    Call this early in app initialization for Google search result previews.
    
    Args:
        description: The meta description content (max ~155 chars recommended)
    """
    import streamlit.components.v1 as components
    import time
    
    safe_desc = description.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
    unique_id = int(time.time() * 1000)
    
    js = f"""
    <!-- meta_desc_{unique_id} -->
    <script>
        (function() {{
            var existingMeta = window.parent.document.querySelector('meta[name="description"]');
            if (existingMeta) {{
                existingMeta.setAttribute('content', "{safe_desc}");
            }} else {{
                var meta = document.createElement('meta');
                meta.name = 'description';
                meta.content = "{safe_desc}";
                window.parent.document.head.appendChild(meta);
            }}
        }})();
    </script>
    """
    components.html(js, height=0, width=0)

# --- SEO: Tab-specific Titles Dictionary ---
SEO_TITLES = {
    "nav_news": {
        "ko": "📰 태국 뉴스 브리핑 | 오늘의 태국",
        "en": "📰 Thailand News Briefing | Thai Today"
    },
    "nav_hotel": {
        "ko": "🏨 방콕 호텔 팩트체크 & 리뷰 | 오늘의 태국",
        "en": "🏨 Bangkok Hotel Real Reviews | Thai Today"
    },
    "nav_food": {
        "ko": "🍜 태국 맛집 팩트체크 & 리뷰 | 오늘의 태국",
        "en": "🍜 Thailand Food Fact Check & Reviews | Thai Today"
    },
    "nav_guide": {
        "ko": "📘 태국 여행 가이드 2026 | 오늘의 태국",
        "en": "📘 Thailand Travel Guide 2026 | Thai Today"
    },
    "nav_tour": {
        "ko": "🎒 AI 투어 추천 | 오늘의 태국",
        "en": "📘 Thailand Travel Guide 2026 | Thai Today"
    },
    "nav_taxi": {
        "ko": "🚕 방콕 택시 요금 계산기 | 오늘의 태국",
        "en": "🚕 Bangkok Taxi Fare Calculator | Thai Today"
    },
    "nav_event": {
        "ko": "🎪 태국 이벤트 & 축제 | 오늘의 태국",
        "en": "🎪 Thailand Events & Festivals | Thai Today"
    },
    "nav_board": {
        "ko": "🗣️ 태국 여행 커뮤니티 | 오늘의 태국",
        "en": "🗣️ Thailand Travel Community | Thai Today"
    }
}

def get_seo_title(nav_key):
    """
    Returns the SEO-optimized page title for a given navigation key.
    
    Args:
        nav_key: The navigation key (e.g., 'nav_news', 'nav_hotel')
    
    Returns:
        str: SEO-optimized page title based on current language
    """
    lang = st.session_state.get('language', 'Korean')
    lang_code = "en" if lang == "English" else "ko"
    
    if nav_key in SEO_TITLES:
        return SEO_TITLES[nav_key].get(lang_code, SEO_TITLES[nav_key].get("ko", "Thai Today"))
    
    # Fallback
    if lang_code == "en":
        return "Thailand Travel Fact Check - Thai Today"
    else:
        return "태국 여행 팩트체크 - 오늘의 태국"

# --- URL 정리 Helper (파라미터 제거) ---
def clean_url_bar():
    """
    URL에서 init_marker 등 추적 파라미터를 시각적으로 제거합니다.
    history.replaceState를 사용하므로 새로고침 없이 주소창만 깔끔해집니다.
    수익 추적 기능은 이미 실행된 후이므로 영향 없음.
    """
    import streamlit.components.v1 as components
    import time
    
    unique_id = int(time.time() * 1000)
    
    js = f"""
    <!-- clean_url_{unique_id} -->
    <script>
        // URL에 'init_marker'가 보이면 실행
        if (window.parent.location.search.indexOf('init_marker') > -1) {{
            // 파라미터를 뗀 깨끗한 주소 생성
            var clean_uri = window.parent.location.protocol + "//" + window.parent.location.host + window.parent.location.pathname;
            // 주소창 바꿔치기 (새로고침 안 됨)
            window.parent.history.replaceState({{}}, document.title, clean_uri);
        }}
    </script>
    """
    components.html(js, height=0, width=0)

# --- 아고다 제휴 링크 생성 ---
def generate_agoda_link(hotel_name: str) -> str:
    """
    아고다 파트너 검색 URL을 생성합니다.
    
    Args:
        hotel_name: 호텔 이름
    
    Returns:
        아고다 검색 URL (제휴 마커 포함)
    """
    import urllib.parse
    
    AGODA_MARKER_ID = "700591"  # Travelpayouts 마커 ID
    encoded_name = urllib.parse.quote(hotel_name)
    
    return f"https://www.agoda.com/search?cid={AGODA_MARKER_ID}&checkIn=&checkOut=&rooms=1&adults=2&children=0&childages=&searchrequestid=&priceCur=KRW&textToSearch={encoded_name}&travellerType=1&pageTypeId=1"

# ============================================
# 📰 Thai English News RSS Sources
# ============================================
THAI_ENGLISH_RSS = [
    "https://www.bangkokpost.com/rss/data/topstories.xml",  # Bangkok Post
    "https://thethaiger.com/feed",  # The Thaiger (popular with travelers)
    "https://www.khaosodenglish.com/feed/",  # Khaosod English
    "https://www.nationthailand.com/rss/306",  # Nation Thailand
]

# Fallback images for news without thumbnails (Thailand themed)
FALLBACK_NEWS_IMAGES = [
    "https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=400",  # Bangkok Temple
    "https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?w=400",  # Thai Street
    "https://images.unsplash.com/photo-1528181304800-259b08848526?w=400",  # Bangkok Skyline
    "https://images.unsplash.com/photo-1506665531195-3566af2b4dfa?w=400",  # Thai Beach
    "https://images.unsplash.com/photo-1534766555764-ce878a5e3a2b?w=400",  # Thai Food
]

import streamlit as st

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def fetch_combined_english_news(max_articles=15):
    """
    Fetches and combines English news from Thai RSS feeds.
    Returns a list of article dictionaries sorted by date (newest first).
    
    Returns:
        list: List of dicts with keys: title, summary, link, image_url, source, published_date
    """
    import random
    from datetime import datetime
    import time as time_module
    
    all_articles = []
    
    for rss_url in THAI_ENGLISH_RSS:
        try:
            feed = feedparser.parse(rss_url)
            source_name = feed.feed.get('title', 'Thai News')[:30]
            
            for entry in feed.entries[:10]:  # Max 10 per source
                # Extract title
                title = entry.get('title', 'Untitled')
                
                # Extract summary/description
                summary = entry.get('summary', entry.get('description', ''))
                # Clean HTML from summary
                if summary:
                    summary = BeautifulSoup(summary, 'html.parser').get_text()[:300]
                
                # Extract link
                link = entry.get('link', '')
                
                # Extract image (check multiple possible locations)
                image_url = None
                
                # 1. Check media_content
                if hasattr(entry, 'media_content') and entry.media_content:
                    for media in entry.media_content:
                        if media.get('url'):
                            image_url = media['url']
                            break
                
                # 2. Check media_thumbnail
                if not image_url and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                    for thumb in entry.media_thumbnail:
                        if thumb.get('url'):
                            image_url = thumb['url']
                            break
                
                # 3. Check enclosures
                if not image_url and hasattr(entry, 'enclosures') and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get('type', '').startswith('image'):
                            image_url = enc.get('url')
                            break
                
                # 4. Check content for img tags
                if not image_url:
                    content = entry.get('content', [{}])
                    if content:
                        content_value = content[0].get('value', '') if isinstance(content, list) else str(content)
                        soup = BeautifulSoup(content_value, 'html.parser')
                        img = soup.find('img')
                        if img and img.get('src'):
                            image_url = img['src']
                
                # 5. Fallback to random Thailand image
                if not image_url:
                    image_url = random.choice(FALLBACK_NEWS_IMAGES)
                
                # Extract publish date
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published_date = datetime(*entry.published_parsed[:6])
                    except:
                        pass
                if not published_date and hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    try:
                        published_date = datetime(*entry.updated_parsed[:6])
                    except:
                        pass
                if not published_date:
                    published_date = datetime.now()
                
                all_articles.append({
                    'title': title,
                    'summary': summary,
                    'link': link,
                    'image_url': image_url,
                    'source': source_name,
                    'published_date': published_date,
                    'category': 'TRAVEL'  # Default category for travel app
                })
                
        except Exception as e:
            print(f"Error fetching RSS from {rss_url}: {e}")
            continue
    
    # Sort by date (newest first)
    all_articles.sort(key=lambda x: x['published_date'], reverse=True)
    
    # Return top N articles
    return all_articles[:max_articles]


# ============================================
# 📋 Standard Category System
# ============================================
CATEGORY_MAPPING = {
    "POLITICS": ["Politics", "Society", "Crime", "Government", "정치", "사회", "정치/사회", "사건/사고", "법률", "General", "기타"],
    "BUSINESS": ["Economy", "Business", "Finance", "Stock", "경제", "금융", "부동산", "금융/경제"],
    "TRAVEL": ["Travel", "Tourism", "Food", "Weather", "여행", "관광", "여행/관광", "축제", "교통", "날씨", "맛집", "축제/이벤트"],
    "LIFESTYLE": ["Entertainment", "Culture", "K-Pop", "Life", "문화", "엔터테인먼트", "연예"]
}

DISPLAY_CATEGORIES = ["전체", "POLITICS", "BUSINESS", "TRAVEL", "LIFESTYLE"]
DISPLAY_LABELS = {
    "POLITICS": "🏛️ 정치/사회",
    "BUSINESS": "💼 경제",
    "TRAVEL": "✈️ 여행/관광",
    "LIFESTYLE": "🎭 문화/엔터"
}

def normalize_category(raw_category: str) -> str:
    """
    Normalizes any category string to one of the 4 standard categories.
    Weather/Traffic news → TRAVEL (priority for traveler safety)
    Unknown → POLITICS (fallback)
    """
    if not raw_category:
        return "POLITICS"
    
    raw_lower = raw_category.lower()
    
    # Priority: Weather/Traffic/Flood → TRAVEL (traveler safety)
    travel_keywords = ["날씨", "weather", "교통", "traffic", "홍수", "flood", "공항", "airport", "비자", "visa"]
    if any(kw in raw_lower for kw in travel_keywords):
        return "TRAVEL"
    
    # Match against known aliases
    for standard_cat, aliases in CATEGORY_MAPPING.items():
        if raw_category in aliases or raw_lower in [a.lower() for a in aliases]:
            return standard_cat
    
    return "POLITICS"  # Fallback for unknown categories

# --- Hotel Share Summary Generator (No API Call) ---
def extract_hotel_share_summary(hotel_name: str, analysis: dict) -> str:
    """
    이미 분석된 결과(analysis dict)에서 공유용 요약 텍스트를 생성합니다.
    Gemini API 호출 없이 순수 Python 파싱으로 처리합니다.
    
    Args:
        hotel_name: 호텔 이름
        analysis: 팩트체크 분석 결과 dict (summary_score, pros, cons 등 포함)
    
    Returns:
        공유용 요약 텍스트 (카카오톡/SNS 전송에 적합한 형식)
    """
    # 1. 점수 추출
    scores = analysis.get('summary_score', {})
    cleanliness = scores.get('cleanliness', 0)
    location = scores.get('location', 0)
    comfort = scores.get('comfort', 0)
    value = scores.get('value', 0)
    score_text = f"{cleanliness}/{location}/{comfort}/{value}"
    
    # 2. 장점 추출 (첫 번째 항목)
    pros_list = analysis.get('pros', [])
    pros_text = pros_list[0] if pros_list else "내용 확인 필요"
    # 너무 길면 자르기
    if len(pros_text) > 50:
        pros_text = pros_text[:47] + "..."
    
    # 3. 단점/주의사항 추출 (첫 번째 항목)
    cons_list = analysis.get('cons', [])
    cons_text = cons_list[0] if cons_list else "내용 확인 필요"
    # 너무 길면 자르기
    if len(cons_text) > 50:
        cons_text = cons_text[:47] + "..."
    
    # 4. 한줄평 추출
    one_line = analysis.get('one_line_verdict', '')
    if one_line and len(one_line) > 60:
        one_line = one_line[:57] + "..."
    
    # 5. 공유 텍스트 조립
    share_text = f"""🏨 [호텔 팩트체크] {hotel_name}
🛡️ 팩트점수: {score_text} (청결/위치/편안/가성비)
✅ 장점: {pros_text}
⚠️ 주의: {cons_text}
💡 한줄평: "{one_line}"
🔗 확인하기: thai-today.com"""
    
    return share_text

# --- Hotel Caching (Google Sheets) ---
def get_hotel_gsheets_client():
    """Authenticates gspread using secrets (GOOGLE_SHEETS_KEY or connections.gsheets_news)."""
    try:
        # 1. Try direct JSON string/dict from Railway/st.secrets
        creds_info = st.secrets.get("GOOGLE_SHEETS_KEY")
        
        # 2. Try nested connection config if direct key is missing
        if not creds_info:
            if "connections" in st.secrets and "gsheets_news" in st.secrets["connections"]:
                creds_info = st.secrets["connections"]["gsheets_news"]
            elif "gsheets_news" in st.secrets:
                creds_info = st.secrets["gsheets_news"]
            
        if not creds_info:
            print("GSheets Secret Missing: Please check GOOGLE_SHEETS_KEY or [connections.gsheets_news]")
            return None
             
        if isinstance(creds_info, str):
            # Parse if it's a stringified JSON
            try:
                creds_dict = json.loads(creds_info)
            except:
                # If it's just a file path (unlikely in Streamlit Cloud but possible)
                if os.path.exists(creds_info):
                    with open(creds_info, 'r') as f:
                        creds_dict = json.load(f)
                else: raise
        else:
            # If it's a dict or AttrDict from st.secrets
            creds_dict = dict(creds_info)
            
        # 3. Clean up dict for gspread (remove extra keys like 'spreadsheet' or 'worksheet')
        valid_keys = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "auth_uri", "token_uri",
            "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"
        ]
        gspread_creds = {k: v for k, v in creds_dict.items() if k in valid_keys}
            
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gspread_creds, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"GSheets Auth Error: {e}")
        return None

def get_hotel_cache(hotel_name, language="Korean"):
    """Checks if analysis for the given hotel already exists in GSheets (Language aware).
    Also searches across ALL language rows for agoda_url and myrealtrip_url."""
    client = get_hotel_gsheets_client()
    if not client: return None
    try:
        sh = client.open("hotel_cache_db")
        sheet = sh.get_worksheet(0)
        
        
        # Search for hotel_name
        cells = sheet.find(hotel_name, in_column=1)
        if cells:
             all_records = sheet.get_all_values()
             
             # 1단계: 모든 행에서 agoda_url과 myrealtrip_url 수집 (언어 무관)
             best_agoda = None
             best_myrealtrip = None
             for row in all_records:
                 if row[0] == hotel_name:
                     if len(row) > 4 and row[4] and row[4].strip():
                         best_agoda = row[4]
                     if len(row) > 6 and row[6] and row[6].strip():
                         best_myrealtrip = row[6]
             
             # 2단계: 언어가 일치하는 행 찾기
             for row in all_records:
                 if row[0] == hotel_name:
                     cached_lang = row[5].strip() if len(row) >= 6 and row[5].strip() else "Korean"
                     if cached_lang == language:
                        return {
                            "hotel_name": row[0],
                            "cached_date": row[1],
                            "ai_summary": row[2],
                            "raw_json": json.loads(row[3]),
                            "agoda_url": best_agoda,
                            "language": cached_lang,
                            "myrealtrip_url": best_myrealtrip
                        }
    except Exception as e:
        print(f"Cache Lookup Error: {e}")
    return None

def save_hotel_cache(hotel_name, ai_summary, raw_json_dict, agoda_url=None, language="Korean"):
    """Appends new analysis results to the hotel_cache_db GSheet."""
    client = get_hotel_gsheets_client()
    if not client: return
    try:
        sh = client.open("hotel_cache_db")
        sheet = sh.get_worksheet(0)
        
        # Header: [hotel_name, cached_date, ai_summary, raw_json, agoda_url, language, myrealtrip_url]
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        new_row = [
            hotel_name,
            now_str,
            ai_summary,
            json.dumps(raw_json_dict, ensure_ascii=False),
            agoda_url or "",
            language,
            ""  # myrealtrip_url (기본값 빈 문자열)
        ]
        sheet.append_row(new_row)
        print(f"✅ Cached ({language}) analysis for: {hotel_name}")
    except Exception as e:
        print(f"Cache Save Error: {e}")


def update_hotel_agoda_url(hotel_name, agoda_url):
    """
    특정 호텔의 아고다 직통 URL을 업데이트합니다.
    관리자가 직통 링크를 수동으로 입력할 때 사용.
    동일 호텔의 모든 행(한국어/영어 등)에 대해 일괄 업데이트합니다.
    """
    client = get_hotel_gsheets_client()
    if not client: return False
    try:
        sh = client.open("hotel_cache_db")
        sheet = sh.get_worksheet(0)
        
        # 모든 행에서 호텔명 검색 (다중 언어 행 모두 업데이트)
        all_values = sheet.get_all_values()
        updated_count = 0
        for idx, row in enumerate(all_values):
            if row and row[0] == hotel_name:
                # 5번째 컬럼(E열)에 URL 업데이트
                sheet.update_cell(idx + 1, 5, agoda_url)
                updated_count += 1
        
        if updated_count > 0:
            print(f"✅ Updated Agoda URL for: {hotel_name} ({updated_count} rows)")
            return True
        else:
            print(f"❌ Hotel not found: {hotel_name}")
            return False
    except Exception as e:
        print(f"Update Error: {e}")
        return False


def update_hotel_myrealtrip_url(hotel_name, myrealtrip_url):
    """
    특정 호텔의 마이리얼트립 URL을 업데이트합니다.
    관리자가 직통 링크를 수동으로 입력할 때 사용.
    동일 호텔의 모든 행(한국어/영어 등)에 대해 일괄 업데이트합니다.
    """
    client = get_hotel_gsheets_client()
    if not client: return False
    try:
        sh = client.open("hotel_cache_db")
        sheet = sh.get_worksheet(0)
        
        # 모든 행에서 호텔명 검색 (다중 언어 행 모두 업데이트)
        all_values = sheet.get_all_values()
        updated_count = 0
        for idx, row in enumerate(all_values):
            if row and row[0] == hotel_name:
                # 7번째 컬럼(G열)에 URL 업데이트 (행 인덱스는 1-based)
                sheet.update_cell(idx + 1, 7, myrealtrip_url)
                updated_count += 1
        
        if updated_count > 0:
            print(f"✅ Updated MyRealTrip URL for: {hotel_name} ({updated_count} rows)")
            return True
        else:
            print(f"❌ Hotel not found: {hotel_name}")
            return False
    except Exception as e:
        print(f"MyRealTrip Update Error: {e}")
        return False



def get_hotel_link(hotel_name, cached_agoda_url=None):
    """
    하이브리드 호텔 링크 생성.
    1. cached_agoda_url이 있고 유효하면 → 직통 링크에 CID 추가/교체 후 리턴
    2. 없으면 → 검색 링크 생성
    
    Args:
        hotel_name: 호텔 이름
        cached_agoda_url: 캐시된 직통 아고다 URL (선택)
    
    Returns:
        tuple: (url, is_direct) - URL과 직통 여부
    """
    import urllib.parse
    import re
    
    AGODA_MARKER_ID = "700591"
    
    # 1. 직통 링크가 있으면 사용 (URL 정화 + CID만 추가)
    if cached_agoda_url and cached_agoda_url.strip() and cached_agoda_url.startswith('http'):
        url = cached_agoda_url.strip()
        
        # URL 파싱
        parsed = urllib.parse.urlparse(url)
        
        # 모든 쿼리 파라미터 제거하고 Base URL만 추출
        # 내 CID만 깔끔하게 추가
        clean_url = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',  # params 제거
            f'cid={AGODA_MARKER_ID}',  # 내 CID만 추가
            ''   # fragment 제거
        ))
        
        return (clean_url, True)
    
    # 2. 없으면 검색 링크 생성
    encoded_name = urllib.parse.quote(hotel_name)
    search_url = f"https://www.agoda.com/search?cid={AGODA_MARKER_ID}&checkIn=&checkOut=&rooms=1&adults=2&children=0&priceCur=KRW&textToSearch={encoded_name}&travellerType=1&pageTypeId=1"
    
    return (search_url, False)


# --- 실시간 검색 랭킹 (Real-time Search Ranking) ---

SEARCH_LOG_FILE = "data/search_log.csv"

def log_search(name, rating, category):
    """
    사용자의 검색 내역을 Google Sheets 'search_log' 시트에 저장합니다.
    """
    try:
        client = get_hotel_gsheets_client()
        if not client:
            return

        sh = client.open("hotel_cache_db")
        
        # 'search_log' 워크시트 가져오기 또는 생성
        try:
            sheet = sh.worksheet("search_log")
        except:
            # 시트가 없으면 생성 (헤더 포함)
            sheet = sh.add_worksheet(title="search_log", rows="100", cols="4")
            sheet.append_row(['name', 'rating', 'category', 'timestamp'])
        
        # 데이터 추가
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([name, rating, category, now_str])
        
        print(f"✅ Logged search to GSheets: {name} ({category})")
    except Exception as e:
        print(f"❌ GSheets Logging Error: {e}")

@st.cache_data(ttl=600)  # 10분간 랭킹 캐시
def get_top_places(category, limit=10):
    """
    Google Sheets에서 검색 내역을 읽어와 스마트 랭킹 TOP 10을 반환합니다.
    """
    try:
        client = get_hotel_gsheets_client()
        if not client:
            return []

        sh = client.open("hotel_cache_db")
        try:
            sheet = sh.worksheet("search_log")
        except:
            return []

        # 모든 데이터 가져오기
        records = sheet.get_all_records()
        if not records:
            return []
            
        df = pd.DataFrame(records)
        
        # 카테고리 필터링
        df = df[df['category'] == category]
        if df.empty:
            return []
            
        # 1. 장소별 집계 (평균 평점, 검색 횟수)
        stats = df.groupby('name').agg({
            'rating': 'mean',
            'name': 'count'
        }).rename(columns={'name': 'search_count'}).reset_index()
        
        # 2. 필터링: 평점 3.5 미만 제외
        stats = stats[stats['rating'] >= 3.5]
        
        if stats.empty:
            return []
            
        # 3. 스코어 계산 (공식: 평점 * 10 + log(검색횟수 + 1))
        stats['score'] = stats['rating'] * 10 + np.log1p(stats['search_count'])
        
        # 4. 정렬 및 상위 N개 추출
        top_df = stats.sort_values(by='score', ascending=False).head(limit)
        
        results = []
        for i, (_, row) in enumerate(top_df.iterrows()):
            name = row['name']
            badge = ""
            if i == 0:
                badge = "🔥 믿고 가는 랭킹 1위"
            elif row['rating'] >= 4.8:
                badge = "💎 숨은 보석 (평점 4.8+)"
            elif row['search_count'] >= 5:
                badge = "👀 지금 가장 핫함"
            
            results.append({
                'rank': i + 1,
                'name': name,
                'rating': round(row['rating'], 1),
                'count': int(row['search_count']),
                'badge': badge
            })
            
        return results
    except Exception as e:
        print(f"❌ GSheets Ranking Analysis Error: {e}")
        return []

# ============================================
# 📘 Blog / Travel Guide Functions
# ============================================

def fetch_blog_posts():
    """
    블로그 게시글 목록을 Google Sheets에서 가져옵니다.
    최신 글이 위로 오도록 정렬합니다.
    
    Returns:
        list: 블로그 포스트 딕셔너리 리스트
    """
    client = get_hotel_gsheets_client()
    if not client:
        return []
    
    try:
        sh = client.open("blog_posts")
        sheet = sh.get_worksheet(0)
        
        # 모든 레코드 가져오기
        records = sheet.get_all_records()
        
        # 날짜 기준 내림차순 정렬 (최신 글이 위로)
        records.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return records
    except Exception as e:
        print(f"Blog Fetch Error: {e}")
        return []


def get_blog_post(post_id):
    """
    특정 ID의 블로그 포스트를 가져옵니다.
    
    Args:
        post_id: 게시글 ID
    
    Returns:
        dict or None: 게시글 데이터
    """
    client = get_hotel_gsheets_client()
    if not client:
        return None
    
    try:
        sh = client.open("blog_posts")
        sheet = sh.get_worksheet(0)
        
        # ID로 검색
        cell = sheet.find(str(post_id))
        if cell:
            row_data = sheet.row_values(cell.row)
            headers = sheet.row_values(1)
            
            # 딕셔너리로 변환
            post = {}
            for i, header in enumerate(headers):
                post[header] = row_data[i] if i < len(row_data) else ""
            return post
    except Exception as e:
        print(f"Blog Get Error: {e}")
    return None


def save_blog_post(post_data):
    """
    블로그 글을 저장합니다 (Upsert: 있으면 업데이트, 없으면 생성).
    
    Args:
        post_data: dict with keys: id, date, title, summary, content, image_url, author
    
    Returns:
        bool: 성공 여부
    """
    client = get_hotel_gsheets_client()
    if not client:
        print("Blog Save Error: No GSheets client")
        return False
    
    try:
        # 시트 열기 또는 생성
        try:
            sh = client.open("blog_posts")
        except:
            # 시트가 없으면 생성
            print("Creating new blog_posts spreadsheet...")
            sh = client.create("blog_posts")
            # 서비스 계정과 공유 (본인 이메일 추가 필요시 여기에)
            sh.share('', perm_type='anyone', role='reader')  # 읽기 권한 공개
        
        sheet = sh.get_worksheet(0)
        
        # 헤더가 없으면 추가
        first_row = sheet.row_values(1)
        if not first_row or first_row[0] != 'id':
            headers = ['id', 'date', 'title', 'summary', 'content', 'image_url', 'author']
            sheet.insert_row(headers, 1)
            print("Added header row to blog_posts")
        
        post_id = str(post_data.get('id', ''))
        
        # ID로 기존 행 검색
        existing_cell = None
        try:
            existing_cell = sheet.find(post_id)
        except:
            pass
        
        # 행 데이터 준비 (컬럼 순서: id, date, title, summary, content, image_url, author)
        row = [
            post_data.get('id', ''),
            post_data.get('date', ''),
            post_data.get('title', ''),
            post_data.get('summary', ''),
            post_data.get('content', ''),
            post_data.get('image_url', ''),
            post_data.get('author', '관리자')
        ]
        
        if existing_cell:
            # 업데이트
            for i, value in enumerate(row):
                sheet.update_cell(existing_cell.row, i + 1, value)
            print(f"✅ Blog post updated: {post_id}")
        else:
            # 새로 추가
            sheet.append_row(row)
            print(f"✅ Blog post created: {post_id}")
        
        return True
    except Exception as e:
        print(f"Blog Save Error: {e}")
        return False


def delete_blog_post(post_id):
    """
    블로그 글을 삭제합니다.
    
    Args:
        post_id: 삭제할 게시글 ID
    
    Returns:
        bool: 성공 여부
    """
    client = get_hotel_gsheets_client()
    if not client:
        return False
    
    try:
        sh = client.open("blog_posts")
        sheet = sh.get_worksheet(0)
        
        cell = sheet.find(str(post_id))
        if cell:
            sheet.delete_rows(cell.row)
            print(f"✅ Blog post deleted: {post_id}")
            return True
        else:
            print(f"❌ Blog post not found: {post_id}")
            return False
    except Exception as e:
        print(f"Blog Delete Error: {e}")
        return False

# ============================================
# 🍜 Restaurant Caching System (Google Sheets)
# ============================================

def get_cached_restaurants_sheet():
    """
    cached_restaurants 시트를 가져오거나 생성합니다.
    """
    client = get_hotel_gsheets_client()
    if not client:
        return None
    
    try:
        try:
            sh = client.open("cached_restaurants")
        except:
            # 시트 생성
            print("Creating cached_restaurants spreadsheet...")
            sh = client.create("cached_restaurants")
            sh.share('', perm_type='anyone', role='reader')
        
        sheet = sh.get_worksheet(0)
        
        expected_headers = ['location_id', 'name', 'rating', 'num_reviews', 'food_rating', 
                           'atmosphere_rating', 'location_rating', 'price_level', 'price',
                           'cuisines', 'hours', 'address', 'phone', 'web_url', 'photos', 'ranking', 'maps_url',
                           'editorial_summary', 'recommended_menu', 'analysis', 'weekday_text', 'language']
        
        first_row = sheet.row_values(1)
        if not first_row:
            sheet.insert_row(expected_headers, 1)
        elif first_row != expected_headers:
            # 기존 헤더와 다르면 (새 컬럼 추가 등) 부족한 부분 업데이트
            for i, header in enumerate(expected_headers):
                if i >= len(first_row) or first_row[i] != header:
                    sheet.update_cell(1, i + 1, header)
            print(f"✅ Google Sheets headers synchronized: {len(expected_headers)} columns")
        
        return sheet
    except Exception as e:
        print(f"Cache Sheet Error: {e}")
        return None


def search_cached_restaurants(keyword):
    """
    캐시된 식당 중에서 검색어와 일치하는 식당을 찾습니다.
    
    Args:
        keyword: 검색어
    
    Returns:
        list: 캐시된 식당 리스트
    """
    sheet = get_cached_restaurants_sheet()
    if not sheet:
        return []
    
    try:
        all_data = sheet.get_all_records()
        keyword_lower = keyword.lower()
        
        cached_results = []
        for row in all_data:
            name = str(row.get('name', '')).lower()
            if keyword_lower in name or name in keyword_lower:
                cached_results.append({
                    'location_id': str(row.get('location_id', '')),
                    'name': row.get('name', ''),
                    'address': row.get('address', '주소 정보 없음'),
                    'is_cached': True  # 캐시 표시
                })
        
        return cached_results
    except Exception as e:
        print(f"Search Cache Error: {e}")
        return []


def get_cached_restaurant_details(location_id, language="Korean"):
    """
    캐시에서 식당 상세 정보를 가져옵니다. (언어 인식)
    """
    sheet = get_cached_restaurants_sheet()
    if not sheet:
        return None
    
    try:
        # location_id로 검색 (동일 ID가 여러 언어로 있을 수 있음)
        all_records = sheet.get_all_records()
        for data in all_records:
            if str(data.get('location_id')) == str(location_id):
                # 언어가 명시되어 있고 현재 요청 언어와 같으면 반환
                # (구버전 캐시는 language가 비어있으므로 Korean으로 간주)
                cached_lang = data.get('language') or "Korean"
                if cached_lang == language:
                    # Parse logic...
                    import json
                    photos = []
                    if data.get('photos'):
                        try:
                            photos = json.loads(data['photos'])
                        except:
                            photos = data['photos'].split(',') if data['photos'] else []
                    
                    cuisines = []
                    if data.get('cuisines'):
                        try:
                            cuisines = json.loads(data['cuisines'])
                        except:
                            cuisines = data['cuisines'].split(',') if data['cuisines'] else []
                    
                    recommended_menu = []
                    if data.get('recommended_menu'):
                        try:
                            recommended_menu = json.loads(data['recommended_menu'])
                        except:
                            recommended_menu = []
                    
                    analysis = {}
                    if data.get('analysis'):
                        try:
                            analysis = json.loads(data['analysis'])
                        except:
                            analysis = {}

                    weekday_text = []
                    if data.get('weekday_text'):
                        try:
                            weekday_text = json.loads(data['weekday_text'])
                        except:
                            weekday_text = []

                    return {
                        'name': data.get('name', ''),
                        'rating': float(data.get('rating', 0) or 0),
                        'num_reviews': int(data.get('num_reviews', 0) or 0),
                        'food_rating': float(data.get('food_rating', 0) or 0),
                        'atmosphere_rating': float(data.get('atmosphere_rating', 0) or 0),
                        'location_rating': float(data.get('location_rating', 0) or 0),
                        'price_level': data.get('price_level', ''),
                        'price': data.get('price', ''),
                        'cuisines': cuisines,
                        'hours': data.get('hours', ''),
                        'weekday_text': weekday_text,
                        'address': data.get('address', ''),
                        'phone': data.get('phone', ''),
                        'web_url': data.get('web_url', ''),
                        'maps_url': data.get('maps_url', data.get('web_url', '')),
                        'photos': photos,
                        'ranking': data.get('ranking', ''),
                        'editorial_summary': data.get('editorial_summary', ''),
                        'recommended_menu': recommended_menu,
                        'analysis': analysis,
                        'language': cached_lang,
                        'is_cached': True
                    }
        return None
    except Exception as e:
        print(f"Get Cached Details Error: {e}")
        return None


def save_restaurant_to_cache(location_id, details):
    """
    식당 정보를 캐시에 저장합니다.
    
    Args:
        location_id: Google Places 위치 ID
        details: 식당 상세 정보
    """
    sheet = get_cached_restaurants_sheet()
    if not sheet:
        return False
    
    try:
        import json
        
        # 이미 존재하는지 확인
        existing = None
        try:
            existing = sheet.find(str(location_id))
        except:
            pass
        
        # 행 데이터 준비
        row = [
            str(location_id),
            details.get('name', ''),
            str(details.get('rating', 0)),
            str(details.get('num_reviews', 0)),
            str(details.get('food_rating', 0)),
            str(details.get('atmosphere_rating', 0)),
            str(details.get('location_rating', 0)),
            details.get('price_level', ''),
            details.get('price', ''),
            json.dumps(details.get('cuisines', []), ensure_ascii=False),
            details.get('hours', ''),
            details.get('address', ''),
            details.get('phone', ''),
            details.get('web_url', ''),
            json.dumps(details.get('photos', []), ensure_ascii=False),
            details.get('ranking', ''),
            details.get('maps_url', details.get('web_url', '')),
            details.get('editorial_summary', ''),
            json.dumps(details.get('recommended_menu', []), ensure_ascii=False),
            json.dumps(details.get('analysis', {}), ensure_ascii=False),
            json.dumps(details.get('weekday_text', []), ensure_ascii=False),
            details.get('language', 'Korean')
        ]
        
        if existing:
            # 업데이트
            for i, value in enumerate(row):
                sheet.update_cell(existing.row, i + 1, value)
            print(f"✅ Restaurant cache updated: {location_id}")
        else:
            # 새로 추가
            sheet.append_row(row)
            print(f"✅ Restaurant cached: {location_id}")
        
        return True
    except Exception as e:
        print(f"Save Cache Error: {e}")
        return False


# ============================================
# 🍜 Restaurant Fact Check (Google Places API)
# ============================================

# 한글-영문 맛집 매핑 (보조용 - Google은 한국어 검색 잘됨)
THAI_FOOD_MAPPING = {
    "빤타리": "반타리 방콕",
    "반타리": "반타리 방콕",
    "팁사마이": "팁사마이 방콕",
    "쩨파이": "제이파이 방콕",
    "제파이": "제이파이 방콕",
    "잡원": "Zabb One 방콕",
}

# 요리 종류 필터링을 위한 블랙리스트 및 매핑 사전
IGNORED_TYPES = ['establishment', 'point_of_interest', 'food', 'store', 'restaurant', 'meal_takeaway', 'meal_delivery']

CUISINE_MAPPING = {
    "thai_restaurant": "태국 음식점 🇹🇭",
    "seafood_restaurant": "해산물 전문 🦀",
    "cafe": "카페 ☕",
    "bar": "바/술집 🍺",
    "bakery": "베이커리 🥐",
    "noodle_shop": "국수 전문점 🍜",
    "korean_restaurant": "한식당 🇰🇷",
    "chinese_restaurant": "중식당 🇨🇳",
    "japanese_restaurant": "일식당 🇯🇵",
    "fast_food_restaurant": "패스트푸드 🍔",
    "vegan_restaurant": "비건 식당 🥗",
    "health_food_restaurant": "건강식",
    "breakfast_restaurant": "조식 맛집",
    "coffee_shop": "커피숍"
}


def get_menu_search_url(restaurant_name, address):
    """
    식당 이름과 주소를 조합하여 구글 이미지 검색(메뉴판) URL을 생성합니다.
    """
    import urllib.parse
    
    # 주소에서 검색에 도움이 될만한 정보 추출 (예: 방콕, 치앙마이 등 지역명)
    area = ""
    if "Bangkok" in address or "방콕" in address:
        area = "Bangkok"
    elif "Chiang Mai" in address or "치앙마이" in address:
        area = "Chiang Mai"
        
    query = f"{restaurant_name} {area} menu".strip()
    encoded_query = urllib.parse.quote(query)
    
    # tbm=isch 파라미터로 구글 이미지 검색 탭으로 바로 이동
    return f"https://www.google.com/search?q={encoded_query}&tbm=isch"


def analyze_reviews_for_menu(reviews, editorial_summary=""):
    """
    리뷰와 에디토리얼 요약문에서 추천 메뉴를 추출합니다.
    에디토리얼 요약문에 언급된 메뉴에는 가중치를 부여합니다.
    """
    MENU_KEYWORDS = {
        "팟타이": ["pad thai", "padthai", "팟타이"],
        "똠양꿍": ["tom yum", "tomyam", "tomyum", "똠양", "똠얌"],
        "푸팟퐁커리": ["poo pad pong", "crab curry", "푸팟퐁", "푸팟퐁커리"],
        "솜땀": ["som tum", "somtam", "som tam", "솜땀"],
        "스테이크": ["steak", "스테이크"],
        "버거": ["burger", "버거"],
        "피자": ["pizza", "피자"],
        "파스타": ["pasta", "파스타"],
        "망고밥": ["mango sticky rice", "mango rice", "망고밥", "망고 스티키"],
        "똠쌥": ["tom saep", "tom zab", "똠쌥", "똠잽"],
        "까이양": ["kai yang", "grilled chicken", "까이양"],
        "무삥": ["moo ping", "pork skewer", "무삥"],
        "카오팟": ["kao phad", "fried rice", "카오팟", "볶음밥"],
        "랭쌥": ["leng saeb", "pork bone soup", "랭쌥", "랭샙"],
        "해산물": ["seafood", "해산물", "씨푸드"],
        "똠얌국수": ["tom yum noodle", "똠얌국수", "똠얌누들"]
    }
    
    scores = {}
    all_reviews_text = " ".join([r.get('text', '').lower() for r in reviews])
    summary_text = editorial_summary.lower() if editorial_summary else ""
    
    for menu, keywords in MENU_KEYWORDS.items():
        score = 0
        # 리뷰 언급 횟수 (존재 여부로 우선 판단)
        for kw in keywords:
            if kw in all_reviews_text:
                score += 1
            if kw in summary_text:
                score += 3  # 에디토리얼 요약 가중치 3배
        
        if score > 0:
            scores[menu] = score
            
    # 점수 높은 순으로 추천 메뉴 선정
    sorted_menu = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [m[0] for m in sorted_menu[:5]]


def calculate_review_score(review):
    """
    리뷰의 품질 점수를 계산합니다.
    (길이, 최신성, 평점, 키워드 풍부함 등을 종합 고려)
    """
    import time as py_time
    score = 0
    text = review.get('text', '')
    rating = review.get('rating', 0)
    review_time = review.get('time', 0)
    
    if not text:
        return -100
        
    # (1) 길이 (Length) - 50자 미만은 감점, 최대 50점
    text_len = len(text)
    if text_len < 50:
        score += 0
    else:
        score += min(text_len * 0.1, 50)
        
    # (2) 최신성 (Recency) - 3개월(90일) 기준
    now = py_time.time()
    three_months_sec = 90 * 24 * 60 * 60
    one_year_sec = 365 * 24 * 60 * 60
    
    if review_time > 0:
        diff = now - review_time
        if diff < three_months_sec:
            score += 30
        elif diff > one_year_sec:
            score -= 10
            
    # (3) 평점 (Rating) - 4점 이상 우대
    if rating >= 4:
        score += 20
        
    # (4) 키워드 포함 (Rich Content)
    RICH_KEYWORDS = ["가격", "메뉴", "웨이팅", "서비스", "친절", "청결", "위생", 
                     "price", "taste", "queue", "service", "menu", "clean"]
    all_text_lower = text.lower()
    for kw in RICH_KEYWORDS:
        if kw in all_text_lower:
            score += 5
            
    # (5) 좋아요 (Likes/Helpful) - 구글 API는 공식적으로 likes를 안주지만 대응 로직
    likes = review.get('likes', 0) or review.get('helpful_votes', 0)
    if likes:
        score += int(likes) * 10
        
    return score


def analyze_restaurant_reviews(reviews, rating, price_level=0, name="", num_reviews=0, api_key=None, language="Korean"):
    """
    리뷰 텍스트를 분석하여 장점, 단점, 한줄평을 도출합니다. (다국어 지원)
    """
    is_english = (language == "English")
    
    if not reviews:
        return {
            'pros': ["No enough info" if is_english else "정보 부족으로 장점 도출 불가"],
            'cons': ["No enough info" if is_english else "정보 부족으로 단점 도출 불가"],
            'verdict': "No enough data to analyze." if is_english else "데이터가 부족하여 분석할 수 없습니다.",
            'one_line_verdict': "No enough data to analyze." if is_english else "데이터가 부족하여 분석할 수 없습니다.",
            'warnings': [],
            'best_review': None
        }

    # 1. Gemini AI Analysis (If API Key provided)
    ai_result = None
    if api_key:
        try:
            # [수다쟁이 우선 법칙] 리뷰를 길이(정보량) 순으로 정렬하여 상위 10개 선택
            sorted_reviews = sorted(reviews, key=lambda x: len(x.get('text', '')), reverse=True)
            
            reviews_text = ""
            for r in sorted_reviews[:10]:  # 상위 10개 참조
                text = r.get('text', '')
                r_rating = r.get('rating', 0)
                if text and len(text) > 10: # 최소 10자 이상
                    reviews_text += f"- [{r_rating}/5] {text}\n"

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})

            # 평점 및 언어 기반 지침
            if is_english:
                tone_instruction = f"Target Restaurant: {name}. Rating: {rating}. Be sharp and honest."
                if rating >= 4.5:
                    tone_instruction += " Highly recommended but finding subtle cons is mandatory."
                else:
                    tone_instruction += f" Lower rating ({rating}). Mention controversy or price issues."
                
                lang_instruction = "IMPORTANT: ALL JSON OUTPUT VALUES MUST BE IN ENGLISH."
                persona = "You are a sharp-tongued food critic expert on Bangkok."
            else:
                if rating >= 4.5:
                    tone_instruction = "이 식당은 평점 4.5 이상의 '강력 추천' 급입니다. 단, 단점이 있다면 그것도 반드시 언급하세요."
                elif rating >= 4.0:
                    tone_instruction = "이 식당은 평점 4.0~4.4의 '안정적인 선택'입니다. 장점과 단점을 균형 있게 서술하세요."
                else:
                    tone_instruction = f"⚠️ 주의: 이 식당은 평점 {rating}점으로 4.0 미만입니다. 아무리 유명해도 '강력 추천'이라고 절대 말하지 마세요."
                
                lang_instruction = "중요: 모든 JSON 출력값은 반드시 한국어로 작성하세요."
                persona = "당신은 방콕 현지 사정에 정통한 '독설가 음식 비평가'입니다."

            prompt = f"""
            {persona}
            Analyze the [Restaurant Info] and [Visitor Reviews] provided and write a sharp, factual report.
            {lang_instruction}

            -----
            ### 🚨 [Knowledge Augmentation]
            If the reviews are too short (e.g. "Good", "Delicious"), use your internal knowledge about {name} in Bangkok to provide detailed facts.
            (e.g., for Wattana Panich: mention the 50-year-old soup, no AC, mixed reviews on hygiene).

            -----
            ### [Guidelines]
            1. **One Line Verdict:** Sharp, high-impact sentence summarizing pros and cons.
            2. **Pros:** Specific food names, taste profiles, atmosphere. No generic terms.
            3. **Cons:** Mandatory even for high-rated places. Hygiene, wait, heat, price, service, location.
            4. **Warnings:** Practical tips (Cash only, No AC, Queue tips).

            -----
            [Restaurant Info]
            - Name: {name}
            - Rating: {rating}
            - Reviews Count: {num_reviews}

            [Review Data]
            {reviews_text}
            
            [Tone]: {tone_instruction}

            **[Output Format (JSON)]**
            {{
                "one_line_verdict": "string",
                "pros": ["string", "string"],
                "cons": ["string", "string"],
                "warnings": ["string", "string"]
            }}
            """
            
            response = model.generate_content(prompt)
            print(f"DEBUG: Gemini Restaurant Raw Response: {response.text}")
            
            # Clean JSON if wrapped in markdown
            text = response.text.strip()
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].split("```")[0].strip()
                
            ai_result = json.loads(text)
            print(f"DEBUG: Extracted AI Result: {ai_result}")
        except Exception as e:
            import traceback
            print(f"Gemini Restaurant Analysis Error: {e}")
            print(traceback.format_exc())
            ai_result = None
    else:
        print("[DEBUG] No API Key provided for Restaurant Analysis")

    # 2. Keyword-based Analysis (Fallback or Complement)
    PRO_KEYWORDS = {
        "맛있다": "확실한 맛 보장 😋", "최고": "방문객 만족도 높음 👍", "친절": "친절한 서비스 ✨",
        "가성비": "훌륭한 가성비 💰", "저렴": "부담 없는 가격", "깨끗": "청결한 위생 상태 🧼",
        "분위기": "분위기 맛집 🕯️", "깔끔": "깔끔한 상차림", "신선": "신선한 재료 사용 🥗",
        "좋아요": "전반적으로 호평", "delicious": "확실한 맛 보장 😋", "fresh": "신선한 재료 🥗",
        "cheap": "저렴한 가격", "kind": "친절한 서비스 ✨", "nice": "기분 좋은 방문"
    }
    
    CON_KEYWORDS = {
        "짜다": "간이 센 편 (Salty)", "짜요": "간이 센 편 (Salty)", "salty": "간이 센 편 (Salty)",
        "달다": "단맛이 강함 (Sweet)", "sweet": "단맛이 강함 (Sweet)", "맵다": "매운 편 (Spicy)",
        "spicy": "매운 편 (Spicy)", "웨이팅": "긴 대기 시간 주의 ⏳", "대기": "긴 대기 시간 주의 ⏳",
        "queue": "긴 대기 시간 주의 ⏳", "비싸": "가격대가 높음 💸", "expensive": "가격대가 높음 💸",
        "덥다": "내부가 더운 편 🌡️", "더워": "내부가 더운 편 🌡️", "hot": "내부가 더운 편 🌡️",
        "no ac": "에어컨 없음/약함", "불친절": "서비스 아쉬움 😕", "양 적음": "양이 적을 수 있음",
        "좁음": "공간이 협소함", "waiting": "대기 발생 가능"
    }

    pros = []
    cons = []
    ai_warnings = []  # AI가 추출한 경고 태그
    all_text = ""
    scored_reviews = []

    for r in reviews:
        text = r.get('text', '')
        if text:
            all_text += text.lower() + " "
            score = calculate_review_score(r)
            scored_reviews.append({
                'score': score,
                'review_data': {
                    'text': text,
                    'rating': r.get('rating', 0),
                    'relative_time': r.get('relative_time_description', '최근')
                }
            })

    # 베스트 리뷰 선정 (Top 3)
    best_reviews = []
    if scored_reviews:
        sorted_scored = sorted(scored_reviews, key=lambda x: x['score'], reverse=True)
        # Top 3 추출
        best_reviews = [item['review_data'] for item in sorted_scored[:3]]
    elif reviews:
        # 점수 계산이 안 된 경우 최신순 3개
        best_reviews = [{'text': r.get('text', ''), 'rating': r.get('rating', 0), 'relative_time': r.get('relative_time_description', '최근')} for r in reviews[:3]]

    # AI 결과가 있으면 사용, 없으면 키워드 기반
    if ai_result:
        ai_pros = ai_result.get('pros', [])
        ai_cons = ai_result.get('cons', [])
        ai_verdict = ai_result.get('one_line_verdict', '')
        ai_warnings = ai_result.get('warnings', [])
        
        pros = ai_pros if ai_pros else pros
        cons = ai_cons if ai_cons else cons
        verdict = ai_verdict if ai_verdict else ""
    else:
        # 키워드 기반 장단점 추출
        for kw, label in PRO_KEYWORDS.items():
            if kw in all_text and label not in pros:
                pros.append(label)
        
        for kw, label in CON_KEYWORDS.items():
            if kw in all_text and label not in cons:
                cons.append(label)
        
        verdict = ""

    # 기본 한줄평 산출 (AI 평이 없을 경우 사용) - 평점 기반 분기
    if not verdict:
        if rating >= 4.5:
            verdict = "실패 없는 현지인 추천 맛집 🏆"
        elif rating >= 4.0:
            if "웨이팅" in all_text or "대기" in all_text or "queue" in all_text:
                verdict = "안정적인 맛이지만 웨이팅은 각오해야 하는 곳 ⏳"
            elif price_level >= 3:
                verdict = "맛은 보장되지만 가격대가 있는 곳 💰"
            else:
                verdict = f"무난하게 즐길 수 있는 {name or '맛집'}"
        else:
            # 4.0 미만: 반드시 부정적 뉘앙스 포함
            if "웨이팅" in all_text or "대기" in all_text:
                verdict = f"유명세에 비해 평점이 낮고({rating}점), 웨이팅 지옥까지 각오해야 하는 곳 ⚠️"
            elif price_level >= 3:
                verdict = f"명성은 있지만 사악한 가격과 {rating}점대 평점이 아쉬운 곳 💸"
            else:
                verdict = f"호불호가 갈리는 곳 - 평점 {rating}점으로 기대치 조절 필요 ⚠️"

    warnings = []
    
    # 1. AI 기반 경고 태그 추가 (최우선)
    seen_warnings = set()
    if ai_warnings:
        for w in ai_warnings:
             # 너무 긴 것은 자르기 (10자 이내 권장했으나 예외 처리)
             w_clean = w[:15]
             warnings.append({'type': 'ai_alert', 'message': f'⚠️ {w_clean}', 'level': 'warning'})
             seen_warnings.add(w_clean)

    # 2. 키워드 기반 경고 추가 (중복 방지)
    if ("짜다" in all_text or "salty" in all_text) and "간이 셈" not in seen_warnings:
        warnings.append({'type': 'taste', 'message': '🧂 간이 센 편', 'level': 'warning'})
    if ("웨이팅" in all_text or "queue" in all_text) and "웨이팅" not in str(seen_warnings):
        warnings.append({'type': 'waiting', 'message': '⏳ 웨이팅 주의', 'level': 'info'})
    if ("더워" in all_text or "hot" in all_text) and "더움" not in seen_warnings:
        warnings.append({'type': 'hygiene', 'message': '🌡️ 내부 더움', 'level': 'warning'})
    
    # 평점 4.0 미만 경고 추가
    if rating < 4.0:
        warnings.append({'type': 'rating', 'message': f'📉 평점 {rating}점 (호불호)', 'level': 'error'})

    return {
        'pros': pros[:3] if pros else ["전반적으로 무난함"],
        'cons': cons[:3] if cons else ["특별한 단점 발견되지 않음 ✨"],
        'verdict': verdict,
        'one_line_verdict': verdict,
        'warnings': warnings,
        'best_review': best_reviews[0] if best_reviews else None, # Legacy support
        'best_reviews': best_reviews # New list support
    }



def extract_restaurant_share_summary(name, details):
    """
    맛집 분석 결과 공유용 텍스트 생성
    """
    analysis = details.get('analysis', {})
    cuisines = ", ".join(details.get('cuisines', []))
    pros = "\n- ".join(analysis.get('pros', ["전반적으로 무난함"]))
    cons = "\n- ".join(analysis.get('cons', ["특별한 단점 발견되지 않음"]))
    
    summary = f"""[🇹🇭 태국 맛집 팩트체크]

🍽️ 식당명: {name} ({cuisines})
⭐ 평점: {details.get('rating', 0)} / 5.0 (리뷰 {details.get('num_reviews', 0):,}개)
💰 가격대: {details.get('price_text', '정보 없음')}

🏆 한줄 평: "{analysis.get('verdict', '')}"

👍 장점:
- {pros}

👎 단점:
- {cons}

📍 구글맵 보기: {details.get('web_url', '')}
🔗 확인하기: thai-today.com"""
    return summary.strip()


def analyze_review_sentiment(reviews):
    """
    구형 호환성을 위한 래퍼 함수 (미래에는 analyze_restaurant_reviews로 통합 가능)
    """
    return analyze_restaurant_reviews(reviews, 4.0)


def search_restaurants(keyword):
    """
    Google Places API로 식당을 검색합니다.
    캐시 우선: 먼저 캐시에서 검색 후 API 호출
    
    Args:
        keyword: 검색어 (식당 이름)
    
    Returns:
        list: 검색 결과 리스트 [{place_id, name, address, is_cached}, ...]
    """
    import requests
    
    # 1단계: 캐시에서 먼저 검색
    cached_results = search_cached_restaurants(keyword)
    
    # 2단계: Google Places Text Search API 호출
    api_results = []
    try:
        google_places_key = st.secrets.get("google_maps_api_key")
        if not google_places_key:
            # googlemaps_api 키로 폴백
            google_places_key = st.secrets.get("googlemaps_api")
        
        if google_places_key:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            
            # [FIX] Relax constraints to include cafes and places outside Bangkok
            # Original: query="... restaurant Bangkok Thailand", type="restaurant"
            params = {
                "query": f"{keyword} Thailand", 
                "language": "ko",
                "key": google_places_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            # Fallback: If no results with "Thailand", try just the keyword
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ZERO_RESULTS':
                    params["query"] = keyword
                    response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'OK':
                    results = data.get('results', [])
                    
                    # 캐시된 place_id 추출 (중복 방지)
                    cached_ids = {r.get('location_id', r.get('place_id', '')) for r in cached_results}
                    
                    for place in results[:10]:
                        place_id = place.get('place_id')
                        name = place.get('name', '')
                        
                        if place_id and name and place_id not in cached_ids:
                            api_results.append({
                                'place_id': place_id,
                                'location_id': place_id,  # 호환성
                                'name': name,
                                'address': place.get('formatted_address', '주소 정보 없음'),
                                'rating': place.get('rating', 0),
                                'is_cached': False
                            })
                else:
                    print(f"Google Places Search: {data.get('status')}")
            else:
                print(f"Google Places Error: {response.status_code}")
    except Exception as e:
        print(f"Google Places Search Error: {e}")
    
    # 캐시 결과를 먼저 보여주고, API 결과를 뒤에 추가
    combined = cached_results + api_results
    return combined[:10]  # 최대 10개


def get_restaurant_details(place_id, gemini_api_key=None, language="Korean"):
    # 1단계: 캐시에서 먼저 확인 (API 비용 0)
    cached = get_cached_restaurant_details(place_id, language=language)
    if cached:
        print(f"✅ Cache hit ({language}) for restaurant place_id: {place_id}")
        # 캐시 히트 시에도 인기 랭킹용 로그 기록
        log_search(cached['name'], cached['rating'], 'food')
        return cached
    
    # 2단계: Google Places Details API 호출 (비용 발생)
    try:
        google_places_key = st.secrets.get("google_maps_api_key")
        if not google_places_key:
            google_places_key = st.secrets.get("googlemaps_api")
        
        if not google_places_key:
            return None
        
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        # 필요한 필드만 요청 (비용 최적화 + 리뷰 포함)
        params = {
            "place_id": place_id,
            "fields": "name,rating,user_ratings_total,price_level,formatted_address,formatted_phone_number,opening_hours,photos,url,types,reviews,editorial_summary",
            "language": "ko",
            "key": google_places_key
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"Google Places Details Error: {response.status_code}")
            return None
        
        data = response.json()
        
        if data.get('status') != 'OK':
            print(f"Google Places Details: {data.get('status')}")
            return None
        
        result_data = data.get('result', {})
        
        # 상세 정보 파싱
        rating = float(result_data.get('rating', 0) or 0)
        num_reviews = int(result_data.get('user_ratings_total', 0) or 0)
        price_level = result_data.get('price_level', 0)  # 0-4
        
        # 가격대 텍스트 변환
        price_text = ""
        if price_level == 1:
            price_text = "💰 저렴"
        elif price_level == 2:
            price_text = "💰💰 보통"
        elif price_level == 3:
            price_text = "💰💰💰 비싼편"
        elif price_level == 4:
            price_text = "💰💰💰💰 고급"
        
        # 사진 URL 생성 (photo_reference 사용)
        photos = []
        for photo in result_data.get('photos', [])[:5]:
            photo_ref = photo.get('photo_reference')
            if photo_ref:
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={google_places_key}"
                photos.append(photo_url)
        
        # 영업시간
        opening_hours = result_data.get('opening_hours', {})
        is_open = opening_hours.get('open_now', None)
        weekday_text = opening_hours.get('weekday_text', [])
        
        hours_text = ""
        if is_open is True:
            hours_text = "🟢 영업중"
        elif is_open is False:
            hours_text = "🔴 영업종료"
        
        # 요리 종류 추출 (필터링 및 한글화 적용)
        types = result_data.get('types', [])
        cuisines = []
        for t in types:
            if t not in IGNORED_TYPES:
                # 매핑된 한글 명칭이 있으면 사용, 없으면 Pretty Print
                ko_name = CUISINE_MAPPING.get(t)
                if ko_name:
                    cuisines.append(ko_name)
                else:
                    cuisines.append(t.replace('_', ' ').title())
        
        # 만약 필터링 후 남은 게 없으면 기본값 설정
        if not cuisines:
            cuisines = ["일반 음식점"]
        
        # 리스트 중 가장 구체적인 1~2개만 사용
        cuisines = cuisines[:2]
        
        # [FIX] Define missing variables extracted from result_data
        reviews = result_data.get('reviews', [])
        name = result_data.get('name', '')
        # editorial_summary is a dict with 'text' and 'languageCode'
        editorial_summary = result_data.get('editorial_summary', {}).get('text', '')
        
        analysis = analyze_restaurant_reviews(reviews, rating, price_level, name, num_reviews=num_reviews, api_key=gemini_api_key, language=language)
        recommended_menu = analyze_reviews_for_menu(reviews, editorial_summary)
        
        result = {
            'language': language,
            'name': result_data.get('name', ''),
            'rating': rating,
            'num_reviews': num_reviews,
            'price_level': price_level,
            'price_text': price_text,
            'address': result_data.get('formatted_address', ''),
            'phone': result_data.get('formatted_phone_number', ''),
            'photos': photos,
            'hours': hours_text,
            'weekday_text': weekday_text,
            'is_open': is_open,
            'cuisines': cuisines[:3],
            'web_url': result_data.get('url', ''),
            'maps_url': result_data.get('url', ''),
            'menu_url': get_menu_search_url(result_data.get('name', ''), result_data.get('formatted_address', '')),
            'editorial_summary': editorial_summary,
            'recommended_menu': recommended_menu,
            # 팩트체크 리포트 데이터
            'analysis': analysis,
            # 호환성용
            'food_rating': rating,
            'atmosphere_rating': rating,
            'location_rating': rating,
        }
        
        # 3단계: 캐시에 저장 (다음엔 API 안 불러도 됨)
        save_restaurant_to_cache(place_id, result)
        
        return result
        
    except Exception as e:
        import traceback
        error_msg = f"Detailed Error: {str(e)}\n{traceback.format_exc()}"
        print(f"Google Places Details Error: {error_msg}")
        return None # Keep returning None, but print detailed traceback

# Helper: Load Custom CSS from file
def load_custom_css():
    """
    Loads custom CSS from style.css and injects it into the Streamlit app.
    This applies Thai-Today.com design spec: Playfair Display fonts, Kanit,
    Glassmorphism cards, Royal Gold theme, and Deep Silk Purple accents.
    """
    css_file = "style.css"
    if os.path.exists(css_file):
        with open(css_file, "r", encoding="utf-8") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    else:
        # Fallback inline CSS if file missing
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Kanit:wght@300;400;500&display=swap');
        h1, h2, h3 { font-family: 'Playfair Display', Georgia, serif !important; }
        body, p, div { font-family: 'Kanit', sans-serif !important; }
        </style>
        """, unsafe_allow_html=True)

# Helper: Render Hero Section with Glassmorphism
def render_hero_section(title="오늘의 태국", subtitle="실시간 태국 여행 정보 큐레이션", image_url=None):
    """
    Renders a premium hero banner at the top of the page.
    Uses the Thai-Today.com design spec: dark gradient overlay, Playfair Display title.
    """
    bg_style = ""
    if image_url:
        bg_style = f"background-image: url('{image_url}'); background-size: cover; background-position: center;"
    else:
        # Default gradient background
        bg_style = "background: linear-gradient(135deg, #2D2D2D 0%, #4B0082 50%, #D4AF37 100%);"
    
    hero_html = f"""
    <div class="hero-section" style="{bg_style}">
        <div class="hero-content">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
    </div>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

# Helper: Render Glass Card wrapper
def render_glass_card(content_html, custom_class=""):
    """
    Wraps content in a glassmorphism card container.
    """
    card_html = f"""
    <div class="glass-card {custom_class}">
        {content_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

# Helper: Render Category Tag
def render_category_tag(category, variant="travel"):
    """
    Renders a styled category tag badge.
    Variants: travel (gold), food (red), safety (purple), economy (green)
    """
    tag_html = f'<span class="category-tag {variant}">{category}</span>'
    return tag_html

# Helper: Render Custom Mobile-Optimized Header
def render_custom_header(text, level=1):
    """
    Renders a custom HTML header for SEO and Mobile UI optimization.
    - H1: 22px (Mobile Friendly)
    - H2: 18px
    - Adjusts margins to save space.
    """
    font_size = "22px" if level == 1 else "18px"
    margin = "10px 0 5px 0"
    color = "#333333" # Default dark grey, can be adjusted for dark mode via CSS variables if needed
    
    # Use CSS variable for text color to support Dark Mode automatically if desired,
    # or stick to fixed color. Let's use var(--text-color) for better adaptation.
    # But user requested #333333 specifically. Let's stick to user request but add dark mode support via Streamlit's theming if possible.
    # User said: "Color: #333333 (다크모드 대응 필요시 var(--text-color) 사용)"
    # Let's use var(--text-color) to be safe for dark mode which is active.
    
    st.markdown(
        f"""
        <{f'h{level}'} style='text-align: left; font-size: {font_size}; font-weight: 700; margin: {margin}; color: var(--text-color); line-height: 1.2;'>
            {text}
        </{f'h{level}'}>
        """,
        unsafe_allow_html=True
    )

# Helper: Check if text contains Thai characters
def is_thai(text):
    import re
    if not text: return False
    return bool(re.search(r'[\u0E00-\u0E7F]', text))

# Helper: Convert Thai Buddhist year to Gregorian year
def convert_thai_year(text: str) -> str:
    import re
    def repl(match):
        year = int(match.group())
        if year > 2500:  # typical Buddhist year
            return str(year - 543)
        return match.group()
    return re.sub(r'\b\d{4}\b', repl, text)

# Helper: Translate text to Korean using Gemini
def translate_text(text: str, dest: str = "ko") -> str:
    """
    Translate Thai text to Korean using Gemini 2.0 Flash.
    Handles API key loading and ensures robust response.
    """
    # 1. Quick Check: Is it already Korean or just numbers?
    if not text or len(text.strip()) == 0:
        return ""
    
    # 2. Convert Thai Buddhist year first
    text = convert_thai_year(text)
    
    # 3. Use Gemini
    try:
        # Lazy load API key if needed (or assume configured globally in app)
        # But utils might be imported separately, so re-check/configure.
        import google.generativeai as genai
        import toml
        
        # Try to get key efficiently
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            try:
                secrets = toml.load(".streamlit/secrets.toml")
                api_key = secrets.get("GEMINI_API_KEY")
            except: pass
            
        if api_key:
            genai.configure(api_key=api_key)
            
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Aggressive Prompt to ensure zero Thai script remains
        prompt = f"""
        Translate the following text to Korean.
        - IMPORTANT: Every single Thai character (script) MUST be converted/translated.
        - Use phonetic Hangul for names or terms if no direct translation exists (e.g., 'แดง' -> '댕').
        - The output must contain ZERO Thai script.
        - If the text is a mix of Thai and Korean, translate only the Thai parts while keeping the Korean.
        - Output ONLY the result. No explanations.
        
        Text:
        {text}
        """
        
        response = model.generate_content(prompt)
        translated = response.text.strip()
        
        # Double check: if it still has Thai, try one more time or just return it
        # But for now, the prompt should be enough.
        return translated
        
    except Exception as e:
        print(f"Translation Error for '{text[:20]}...': {e}")
        return text


# Helper: Check if article is within last N days
def is_recent(entry, days=3):
    if not hasattr(entry, 'published_parsed'):
        return True # Default to include if no date
    
    # published_parsed is a struct_time, convert to datetime
    pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
    limit_date = datetime.now() - timedelta(days=days)
    return pub_date >= limit_date

# Helper: Check relevance to Thailand
def is_relevant_to_thailand(entry):
    """
    Determines if an article is relevant to Thailand based on keywords and script.
    Checks: Title, Summary (if available)
    """
    import re
    
    # 1. content to check
    text = (entry.title + " " + entry.get('summary', '')).lower()
    
    # 2. Check for Thai Characters (Script)
    if re.search(r'[\u0E00-\u0E7F]', text):
        return True
        
    # 3. Check for English Keywords
    keywords = [
        "thailand", "thai", "bangkok", "phuket", "pattaya", "chiang", 
        "samui", "krabi", "isan", "baht", "pheu thai", 
        "prime minister", "paetongtarn", "thaksin", "king", "royal",
        "cabinet", "govt", "police", "otp", "airport"
    ]
    
    for kw in keywords:
        if kw in text:
            return True
            
    return False

# 1. RSS Parsing (Balanced)
def fetch_balanced_rss(feeds_config, processed_urls=None):
    """
    Fetches RSS feeds and returns a balanced mix of items across categories.
    feeds_config: List of dicts [{'category': '...', 'url': '...'}, ...]
    processed_urls: Set of strings (optional) to skip already seen news.
    """
    import requests
    
    if processed_urls is None:
        processed_urls = set()
    
    # Using a typical browser User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    }
    
    category_buckets = {}
    MAX_PER_CATEGORY = 80  # Increased from 20 to 80 to allow checking more feeds (e.g. Pattaya News)
    
    for feed in feeds_config:
        category = feed.get('category', 'General')
        url = feed.get('url')
        
        if category not in category_buckets:
            category_buckets[category] = []
            
        # Check quota early
        if len(category_buckets[category]) >= MAX_PER_CATEGORY:
            print(f"Skipping feed {url} (Quota full for {category})")
            continue
            
        try:
            print(f"Fetching [{category}] {url}...")
            import time
            time.sleep(1) # Add a 1 second delay to avoid rapid-fire requests
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"Failed to fetch {url}: Status {response.status_code}")
                continue
                
            feed_data = feedparser.parse(response.content)
            
            if feed_data.bozo:
                print(f"XML Parse Warning for {url}: {feed_data.bozo_exception}")
            
            print(f"Successfully parsed {url}: Found {len(feed_data.entries)} entries.")
            
            for entry in feed_data.entries:
                # Re-check quota inside loop
                if len(category_buckets[category]) >= MAX_PER_CATEGORY:
                    break
                
                # Filter: Relevance Check (Skip non-Thai news)
                if not is_relevant_to_thailand(entry):
                    # print(f"Skipping irrelevant: {entry.title}") 
                    continue

                # Filter: Skip already processed
                if entry.link in processed_urls:
                    # print(f"Skipping already processed: {entry.title}")
                    continue

                if is_recent(entry):
                    # Robust Source Extraction
                    raw_src = feed_data.feed.get("title", url)
                    if not raw_src or str(raw_src).lower() == 'none' or str(raw_src).strip() == '':
                        raw_src = "[MISSING_SOURCE]"
                    
                    item = {
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", str(datetime.now())),
                        "summary": entry.get("summary", ""),
                        "source": raw_src,
                        "suggested_category": category, # Hint for AI or logic
                        "_raw_entry": entry
                    }
                    category_buckets[category].append(item)
                    
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Interleave (Round-Robin) to create balanced list
    balanced_items = []
    max_items_per_cat = max(len(items) for items in category_buckets.values()) if category_buckets else 0
    
    categories = list(category_buckets.keys())
    
    for i in range(max_items_per_cat):
        for cat in categories:
            if i < len(category_buckets[cat]):
                balanced_items.append(category_buckets[cat][i])
                
    return balanced_items

# 2. Gemini Analysis
import re

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext


# --------------------------------------------------------------------------------
# Google News RSS Fetcher (Backup Source)
# --------------------------------------------------------------------------------
def fetch_google_news_rss(query="Thailand Tourism", period="24h"):
    """
    Fetches Google News RSS for a specific query.
    Returns: List of dicts matching news item structure.
    """
    import feedparser
    import urllib.parse
    import time
    import requests
    
    encoded_query = urllib.parse.quote(query)
    # hl=en-TH, gl=TH ensures Thailand focus
    # when:24h = Last 24 hours
    # scoring=n = Sort by Date (Newest first)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:{period}&hl=en-TH&gl=TH&ceid=TH:en&scoring=n"
    
    print(f"Fetching Google News: {query}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
    
    try:
        # [FIX] Use requests with User-Agent to avoid 403/Blocking
        response = requests.get(rss_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            items = []
            for entry in feed.entries:
                # [FIX] Robust Source Extraction for Google News
                raw_src = entry.get('source', {}).get('title')
                if not raw_src or str(raw_src).lower() == 'none' or str(raw_src).strip() == '':
                    raw_src = "[MISSING_SOURCE]"
                
                # Standardize to our News Item format
                item = {
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', ''),
                    'summary': entry.get('description', ''),
                    'source': raw_src,
                    '_raw_entry': entry # Keep for image extraction
                }
                items.append(item)
            print(f" -> Found {len(items)} items from Google News.")
            return items
        else:
            print(f"Google News Fetch Failed: Status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Google News Fetch Error: {e}")
        return []

# Helper: Fetch Full Content from URL
def fetch_full_content(url):
    """
    Scrapes the main text content from a news URL.
    Returns: String (text) or None
    """
    import requests
    from bs4 import BeautifulSoup
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        # Timeout slightly longer for scraping
        response = requests.get(url, headers=headers, timeout=5)
# Reverted Google Cache Fallback
        
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            script.decompose()
            
        # Extract text from p tags (most reliable for news)
        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text() for p in paragraphs])
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        # Remove Google Cache Header Artifacts (if any)
        if "Google's cache of" in text:
             text = text.replace("This is Google's cache of", "")
        
        if len(text) < 100: # Too short, likely failed
            return None
            
        return text[:3000] # Limit to 3000 chars
        
    except Exception as e:
        # print(f"Error scraping {url}: {e}")
        return None

def analyze_news_with_gemini(news_items, api_key, existing_titles=None, current_time=None):
    if not news_items:
        return {}, "No news items to analyze."
        
    genai.configure(api_key=api_key)
    
    # Analyze ALL provided items
    limited_news_items = news_items[:10] 
    
    aggregated_topics = []
    total_items = len(limited_news_items)
    print(f"Starting sequential analysis for {total_items} items...")

    # Format existing titles for context
    existing_context = "\n".join([f"- {t}" for t in (existing_titles or [])[:15]])

    for idx, item in enumerate(limited_news_items):
        print(f"[{idx+1}/{total_items}] Processing: {item['title']}...")
        
        full_content = fetch_full_content(item['link'])
        if not full_content:
            full_content = clean_html(item['summary'])[:800]

        # New Context-Aware Prompt
        prompt = f"""
# Role
당신은 태국 방콕을 여행하는 한국인 여행자를 위한 '실시간 뉴스 큐레이터'입니다.
현재 시각은 {current_time or '알 수 없음'} 이며, 아침/저녁 브리핑을 위해 뉴스를 선별 중입니다.

# Task
입력된 뉴스 기사들을 분석하여 여행자에게 필요한 정보를 선별하고 요약하세요.
**[CRITICAL] 모든 출력 텍스트(제목, 요약, 기사 전문 등)는 반드시 한국어(Korean)여야 합니다.** 태국어나 영어로 남겨두지 마세요.
이때, **'기계적인 중복'과 '의미 있는 업데이트'를 구분**하는 것이 가장 중요합니다.

# Input Data
1. **Candidate News:** 
   - Title: {item['title']}
   - Source: {item['source']}
   - Content Snippet: {full_content[:1500]}
2. **Existing News (최근 24시간 내 이미 게시된 기사들):**
{existing_context}

# 🔍 Filtering & Scoring Logic (3-Step)

## Step 1: '업데이트' 여부 판단 (Context Check)
기존 뉴스(Existing News)와 주제가 비슷하더라도, 아래 경우에는 **'새로운 뉴스'**로 취급하세요.
- **시간 경과:** 사건의 진행 상황이 변한 경우 (예: 시위 발생 -> 시위 해산, 사고 발생 -> 사상자 집계 완료)
- **일일 브리핑:** 날씨, 미세먼지(PM2.5), 환율 등 매일 변하는 수치는 어제와 제목이 비슷해도 **오늘 날짜 데이터라면 필수 게시(Score +3)**.
- **아침/저녁:** 'Morning Briefing' 또는 'Daily Update' 성격의 기사는 우선순위를 높임.

## Step 2: Scoring (1~10점)
- **7~10점 (필수):** 여행객 안전 위협(시위, 홍수, 범죄), 비자/입국 규정 변경, 대형 축제, 공항 혼잡.
- **4~6점 (보통):** 새로운 핫플, 일반적인 날씨, 소소한 규제, 흥미로운 로컬 뉴스.
- **1~3점 (무시):** 단순 정치 싸움, 연예인 가십, 여행과 무관한 뉴스.

# Constraints
- 이미 게시된 뉴스와 **내용이 100% 동일하면 제외**하세요.
- 하지만 **'상황이 업데이트' 되었다면 반드시 포함**하세요.
- 아침에는 '오늘의 예보/예정' 위주, 저녁에는 '오늘 발생한 사건/결과' 위주로 가중치를 두세요.
- **[CRITICAL] 출처가 '[MISSING_SOURCE]'인 기사는 'tourist_impact_score'가 8점 이상인 경우에만 결과에 포함하세요.** 7점 이하인 일반 기사는 과감히 제외하세요.
- 만약 출처가 '[MISSING_SOURCE]'인데 정보를 포함하기로 결정했다면, 출력 JSON의 `source` 필드에는 "Google News" 또는 기사 내용에서 추론된 실제 언론사 이름을 적으세요. 절대 "None"이나 "[MISSING_SOURCE]"라고 출력하지 마세요.
- **[CRITICAL - CATEGORY] 카테고리는 반드시 다음 4개 중 하나만 사용하세요: 'POLITICS', 'BUSINESS', 'TRAVEL', 'LIFESTYLE'. 다른 단어(예: '정치/사회', 'General', '기타')를 절대 사용하지 마세요.**
  - 날씨, 교통, 홍수, 공항, 비자 → TRAVEL
  - 정치, 사회, 사건/사고, 범죄 → POLITICS
  - 경제, 금융, 비즈니스 → BUSINESS
  - 문화, 엔터테인먼트, K-Pop → LIFESTYLE

# Output Format (JSON Only)
{{
  "topics": [
    {{
      "title": "기사 제목",
      "summary": "핵심 3줄 요약 (- 로 시작)",
      "full_translated": "기사 전문 (Markdown)",
      "category": "POLITICS | BUSINESS | TRAVEL | LIFESTYLE 중 하나",
      "tourist_impact_score": 0,
      "impact_reason": "점수 부여 및 업데이트 판단 근거",
      "event_info": {{
          "date": "YYYY-MM-DD",
          "location": "...", 
          "price": "...",
          "location_google_map_query": "..."
      }},
      "references": [
        {{"title": "{item['title']}", "url": "{item['link']}", "source": "{item['source']}"}}
      ]
    }}
  ]
}}
"""
        
        # Retry Logic with Safety Limits
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
                response = model.generate_content(prompt)
                # Force HTTPS for all URLs in the generated content (Markdown links, Image URLs, References)
                safe_text = response.text.replace("http://", "https://")
                result = json.loads(safe_text)
                
                if 'topics' in result and result['topics']:
                    # --- Python Post-Processing & Verification ---
                    filtered_topics = []
                    for topic in result['topics']:
                        # 0. Sanitize Source (Emergency fix if AI failed constraints)
                        for ref in topic.get('references', []):
                            src = str(ref.get('source', '')).strip()
                            if not src or src.lower() == 'none' or src == '[MISSING_SOURCE]':
                                ref['source'] = 'Google News'
                        
                        # 1. Strict Source Filtering Verification
                        is_missing_source = (item['source'] == '[MISSING_SOURCE]')
                        impact_score = topic.get('tourist_impact_score', 0)
                        
                        if is_missing_source and impact_score < 8:
                            print(f"   -> [Filtered] Skipping '{topic['title']}' (Missing source & Low score: {impact_score})")
                            continue
                            
                        # --- [NEW] Ingestion-Time Translation Safety ---
                        # If AI returned Thai, force manual translation before saving
                        for field in ['title', 'summary', 'full_translated']:
                            if field in topic and is_thai(topic[field]):
                                print(f"   -> [Safety] Missed translation in {field}, forcing manual translation...")
                                topic[field] = translate_text(topic[field])

                        # 2. Festival/Event Strict Mode
                        if topic.get('category') == '축제/이벤트':
                            evt = topic.get('event_info')
                            # Check strict conditions
                            if not evt or not evt.get('location') or not evt.get('date') or not evt.get('price'):
                                print(f"   -> [Strict Mode] Downgrading '{topic['title']}' from Event to Travel News (Missing Info)")
                                topic['category'] = 'TRAVEL'
                                topic['event_info'] = None # Clear it
                            elif evt.get('location') == 'Unknown' or evt.get('location') == 'null':
                                 print(f"   -> [Strict Mode] Downgrading '{topic['title']}' (Location Unknown)")
                                 topic['category'] = 'TRAVEL'
                                 topic['event_info'] = None
                        
                        # 3. Normalize Category (Fallback safety)
                        raw_cat = topic.get('category', '')
                        topic['category'] = normalize_category(raw_cat)
                        
                        filtered_topics.append(topic)

                    aggregated_topics.extend(filtered_topics)
                    print(f"   -> Success. Topics so far: {len(aggregated_topics)}")
                    success = True
                else:
                    raise ValueError("Empty topics in response")
                
            except Exception as e:
                retry_count += 1
                wait_time = 2 ** retry_count # Exponential backoff: 2s, 4s, 8s
                print(f"   -> API Error for item {idx+1} (Attempt {retry_count}/{max_retries}): {e}")
                
                if "429" in str(e):
                    print("   -> Rate Limit Hit. Waiting longer...")
                    time.sleep(60) # Special wait for Rate Limit
                elif retry_count < max_retries:
                    print(f"   -> Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print("   -> Max retries reached. Skipping this item.")
            
        # Delay logic (except for the last one)
        if idx < total_items - 1:
            print("   -> Waiting 20 seconds to respect API rate limits...")
            time.sleep(20)

    return {"topics": aggregated_topics}, None


def load_local_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}


# 3. Exchange Rate (THB -> KRW)
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 mins
def get_thb_krw_rate():
    """
    Fetches the current THB to KRW exchange rate.
    Uses 'data/exchange_rate.json' for persistence.
    """
    RATE_FILE = 'data/exchange_rate.json'
    url = "https://api.frankfurter.app/latest?from=THB&to=KRW"
    
    # helper to save
    def save_rate(rate):
        try:
            with open(RATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"rate": rate, "updated_at": str(datetime.now())}, f)
        except: pass

    # helper to load
    def load_cached_rate():
        if os.path.exists(RATE_FILE):
            try:
                with open(RATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("rate")
            except: pass
        return None

    try:
        # Increased timeout to 15s to prevent frequent timeouts
        import requests
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            rate = data.get('rates', {}).get('KRW')
            if rate:
                save_rate(rate)
                return rate
    except Exception as e:
        print(f"Exchange Rate Error: {e}")
    
    # Fallback to cached rate if live fetch fails
    cached = load_cached_rate()
    if cached:
        return cached
        
    # If absolutely no data (first run ever & fail), return None or handled by UI
    return 0.0

@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 mins
def get_usd_thb_rate():
    """
    Fetches the current USD to THB exchange rate.
    Uses 'data/exchange_rate_usd.json' for persistence.
    """
    RATE_FILE = 'data/exchange_rate_usd.json'
    url = "https://api.frankfurter.app/latest?from=USD&to=THB"
    
    # helper to save
    def save_rate(rate):
        try:
            with open(RATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"rate": rate, "updated_at": str(datetime.now())}, f)
        except: pass

    # helper to load
    def load_cached_rate():
        if os.path.exists(RATE_FILE):
            try:
                with open(RATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("rate")
            except: pass
        return None

    try:
        import requests
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            rate = data.get('rates', {}).get('THB')
            if rate:
                save_rate(rate)
                return rate
    except Exception as e:
        print(f"USD Exchange Rate Error: {e}")
    
    # Fallback to cached rate if live fetch fails
    cached = load_cached_rate()
    if cached:
        return cached
        
    # Default fallback rate (approx USD/THB)
    return 34.5

# 4. Air Quality (WAQI)
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 mins
def get_air_quality(token):
    """
    Fetches real-time Air Quality (PM 2.5) for Bangkok.
    Returns:
        dict: {'aqi': int, 'status': str} or None if failed.
    """
    url = f"https://api.waqi.info/feed/bangkok/?token={token}"
    try:
        import requests
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok':
                aqi = data['data']['aqi']
                return {'aqi': aqi}
    except Exception as e:
        print(f"Air Quality Error: {e}")
    
    return None



def fetch_thai_events():
    """
    Fetches and parses event information from ThaiTicketMajor, BK Magazine, and TAT News using Gemini.
    Returns:
        list: A list of event dictionaries (title, date, location, region, image_url, link, type).
    """
    print("Fetching Thai Events (National)...")
    
    targets = [
        {
            "name": "ThaiTicketMajor",
            "url": "https://www.thaiticketmajor.com/concert/",
            "selector": "body"
        },
        {
            "name": "BK Magazine",
            "url": "https://bk.asia-city.com/things-to-do-bangkok",
            "selector": "div.view-content"
        },
        {
            "name": "TAT News",
            "url": "https://www.tatnews.org/category/events-festivals/",
            "selector": "body"
        }
    ]

    combined_html_context = ""

    for target in targets:
        try:
            print(f" - Requesting {target['name']}...")
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(target['url'], headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract relevant part
                content = soup.select_one(target['selector'])
                if not content:
                     content = soup.body
                
                # Kill scripts
                for s in content(["script", "style", "nav", "footer", "header"]):
                    s.extract()
                
                html_snippet = str(content)[:20000] # Increased limit for TAT
                
                combined_html_context += f"\n\n--- Source: {target['name']} ({target['url']}) ---\n{html_snippet}"
                
        except Exception as e:
            print(f"Error fetching {target['name']}: {e}")

    if not combined_html_context:
        return []

    # Gemini Processing
    try:
        # Load API Key (Handle Env vs Secrets)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
             try:
                import toml
                secrets = toml.load(".streamlit/secrets.toml")
                api_key = secrets.get("GEMINI_API_KEY")
             except:
                pass
        
        if not api_key:
            return []

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        prompt = f"""
        You are a helpful event curator for Korean tourists visiting Thailand.
        Analyze the following HTML snippets from event websites (ThaiTicketMajor, BK Magazine, TAT News).
        Extract a list of distinct events/festivals across Thailand.
        
        Current Date: {today_str}
        
        CRITICAL: Identify the **REGION** (City/Province) based on the location info.
        - If "Chiang Mai" -> "치앙마이"
        - If "Phuket" -> "푸켓"
        - If "Pattaya" -> "파타야"
        - If "Bangkok" -> "방콕"
        - If "Koh Samui" -> "코사무이"
        - If unknown or miscellaneous, default to "기타" (Others) or "방콕" if mostly likely Bangkok.
        
        Return the result ONLY as a JSON list of objects.
        
        JSON Format:
        [
            {{
                "title": "Event Name (Summarize in Korean, e.g. '송크란 축제')",
                "date": "YYYY-MM-DD or Date Range String (e.g. '2024-04-13 ~')",
                "location": "Venue Name (in Korean or English)",
                "region": "방콕/치앙마이/푸켓/파타야/기타",
                "image_url": "Full URL of the event poster/image",
                "link": "Full URL to booking page or article",
                "booking_date": "YYYY-MM-DD HH:MM (Ticket Open Time) or 'Now Open' or 'TBD'",
                "price": "Exact Price (e.g. '3,000 THB') or range",
                "type": "축제" or "콘서트" or "전시" or "기타"
            }}
        ]

        Rules:
        1. Select 8-12 diverse items (Mix of Concerts, Festivals, Exhibitions).
        2. CRITICAL: EXCLUDE events that ended BEFORE {today_str}. Only show current or future events.
        3. CRITICAL: If you see a date from a past year (e.g. 2024 if today is 2026, or 2017, 2018...), IGNORE IT. Do not output old events.
        4. Prefer events happening soon (next 45 days).
        3. Ensure image_url is absolute.
        4. Output strictly JSON.
        
        HTML Context:
        {combined_html_context}
        """
        
        print(" - Sending to Gemini...")
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        data = json.loads(text)
        print(f" - Parsed {len(data)} events with Region info.")
        return data

    except Exception as e:
        print(f"Gemini processing error: {e}")
        return []

def extract_event_from_url(url, api_key):
    """
    Scrapes a URL and uses Gemini to extract event details.
    Returns a dict with processed event info.
    """
    try:
        # 1. Scrape Content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
             'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # Remove scripts/styles
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
            
        text_content = soup.get_text(separator=' ', strip=True)[:15000] # Limit context
        
        # Try to find OG Image
        og_image = ""
        meta_img = soup.find("meta", property="og:image")
        if meta_img:
            og_image = meta_img.get("content", "")
            
        title_guess = soup.title.string if soup.title else ""

        # 2. Gemini Analysis
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        Analyze the following webpage text and extract event information.
        
        URL: {url}
        Page Title: {title_guess}
        Text Content:
        {text_content}
        
        Goal: Extract details for a "Big Match" event (Festival/Concert).
        
        Output JSON Format:
        {{
            "title": "Event Name (Korean, e.g. '롤링라우드 태국 2024')",
            "date": "YYYY-MM-DD or Range (e.g. '2024-11-22 ~ 11-24')",
            "location": "Venue Name (Korean/English)",
            "region": "One of: ['방콕', '파타야', '치앙마이', '푸켓', '기타']",
            "type": "One of: ['축제', '콘서트', '전시', '클럽/파티', '기타']",
            "booking_date": "Ticket Open Date (YYYY-MM-DD HH:MM) or 'Now Open'",
            "price": "Exact Price (e.g. '3,000 THB') or Range",
            "status": "One of: ['티켓오픈', '개최확정', '매진', '정보없음']",
            "image_url": "Use existing OG Image if valid, or find one in text. If none, return empty string.",
            "description": "1 line summary in Korean"
        }}
        
        If image_url is missing in text, use this one: {og_image}
        
        Translate all text to natural Korean.
        If information is missing, use "정보없음" or "" (empty string).
        """
        
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        
        # Parse JSON
        if "```json" in text_response:
            text_response = text_response.replace("```json", "").replace("```", "")
        if text_response.startswith("```"): # Catch raw block
            text_response = text_response.replace("```", "")
        
        data = json.loads(text_response)
        data['link'] = url # Ensure link is set
        
        # Safety fallback for image
        if not data.get('image_url') and og_image:
            data['image_url'] = og_image
            
        return data, None
        
    except Exception as e:
        return None, str(e)

def fetch_big_events_by_keywords(keywords, api_key):
    """
    Crawls Google News RSS (Thailand Locale) for keywords and critically verifies details with Gemini.
    """
    import feedparser
    import urllib.parse
    
    found_events = []
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    for kw in keywords:
        print(f"Checking keyword: {kw}")
        encoded_kw = urllib.parse.quote(kw)
        # Use Thailand Locale (en-TH)
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-TH&gl=TH&ceid=TH:en"
        
        feed = feedparser.parse(rss_url)
        
        # Check top 2 entries (efficient)
        entries_to_check = feed.entries[:2]
        if not entries_to_check:
            continue
            
        # Aggregate text for analysis
        combined_text = f"Target Event: {kw}\n"
        for i, entry in enumerate(entries_to_check):
            combined_text += f"[{i+1}] Title: {entry.title}\nLink: {entry.link}\nSummary: {entry.get('summary','')}\nPubDate: {entry.get('published','')}\n\n"
            
        prompt = f"""
        Analyze these news search results for the event "{kw}" in Thailand.
        
        News Content:
        {combined_text}
        
        Goal: Determine if there is CONFIRMED information about the NEXT event date and venue.
        
        CRITICAL VALIDATION RULES:
        1. **CONFIRMED ONLY**: Do NOT extract if it's just a "rumor", "expected to be", "in talks", or from a past year.
        2. **Future Only**: Date must be in the future (2025-2027).
        3. **Specifics**: You must find BOTH a specific date (or confirmed month) AND a venue/city.
        
        If the event is NOT confirmed or is just a rumor:
        Return JSON: {{ "found": false, "reason": "Just a rumor or no data" }}

        If CONFIRMED:
        Return JSON:
        {{
            "found": true,
            "title": "Event Name (Korean)",
            "date": "YYYY-MM-DD or Range",
            "location": "Venue Name",
            "booking_date": "Ticket Open Date (YYYY-MM-DD HH:MM) or 'TBD'",
            "price": "Exact Price (e.g. '3,000 THB') or Range",
            "status": "개최확정", 
            "link": "Best Link URL from the news",
            "description": "1 line confirmed summary in Korean"
        }}
        """
        
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if "```json" in text:
                text = text.replace("```json", "").replace("```", "")
            if text.startswith("```"):
                text = text.replace("```", "")
                
            data = json.loads(text)
            
            if data.get('found'):
                # Basic validation
                if '201' in data.get('date',''): 
                     pass
                else:
                    found_events.append(data)
            else:
                print(f" -> {kw}: Not confirmed ({data.get('reason')})")
                    
        except Exception as e:
            print(f"Error analyzing {kw}: {e}")
            
    return found_events

# --------------------------------------------------------------------------------
# Trend Hunter (Magazine) Logic - 4 Sources
# --------------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 60 mins
def fetch_trend_hunter_items(api_key, existing_links=None):
    """
    Aggregates trend/travel content via Google News RSS for 4 sources:
    1. Wongnai (Restaurants)
    2. TheSmartLocal TH (Hotspots)
    3. Chillpainai (Local Travel)
    4. BK Magazine (BKK Life)
    
    Returns:
        list: shuffled list of dicts {title, desc, location, image_url, link, badge}
    """
    import random
    import requests
    import feedparser
    
    print("Fetching Trend Hunter items via Google News RSS...")
    
    items = []
    if existing_links is None:
        existing_links = set()
    else:
        existing_links = set(existing_links)
        
    seen_links = set() # Local deduplication
    
    # Target Domains (Loaded from sources.json)
    SOURCES_FILE = 'data/sources.json'
    targets = []
    
    # 1. Try Loading from File
    if os.path.exists(SOURCES_FILE):
        try:
            with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                s_data = json.load(f)
                if s_data.get('magazine_targets'):
                    # Filter enabled only
                    targets = [t for t in s_data['magazine_targets'] if t.get('enabled', True)]
        except Exception as e:
            print(f"Error loading sources.json: {e}")
            
    # 2. Fallback if empty (Hardcoded defaults)
    if not targets:
        print("Using default magazine targets (Fallback).")
        targets = [
            {"name": "Wongnai", "domain": "wongnai.com", "tag": "[맛집랭킹]"},
            {"name": "Chillpainai", "domain": "chillpainai.com", "tag": "[로컬여행]"},
            {"name": "BK Magazine", "domain": "bk.asia-city.com", "tag": "[방콕라이프]"},
            {"name": "The Smart Local", "domain": "thesmartlocal.co.th", "tag": "[MZ핫플]"}
        ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Helper: Gemini Analyzer
    def analyze_rss_items(raw_inputs, source_tag):
        if not raw_inputs: return []
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            prompt = f"""
            You are a expert Korean Travel Editor acting as a **"Hotplace Detector"**.
            Your goal is to filter and rewrite RSS items into high-quality **Korean** magazine content.
            
            Input Data ({source_tag}):
            {json.dumps(raw_inputs, ensure_ascii=False)}
            
            **CRITICAL FILTERING RULES (Hotplace Detector)**:
            Analyze each item. If an item falls into any of these categories, **return null** for that item instead of a JSON object:
            1. **Not a specific visitable place**: General news, flight promos, "Thai Trip" general guides, or listicles without a clear focus.
            2. **Vague/Ad**: Content that sounds like a generic advertisement or lacks specific details.
            3. **No Image**: If you cannot infer a strong visual context or the input lacks an image.
            
            **REWRITE INSTRUCTIONS (For valid items)**:
            1. **LANGUAGE**: Natural, witty, trendy **Korean**.
            2. **INFERENCE**: Infer details (Vibe, Menu, Tips) from context.
            3. **FIELDS**:
               - "catchy_headline": Click-bait style 1-liner in Korean.
               - "desc": 2-3 sentences summary (Focus on why it's hot).
               - "location": Infer Area (e.g. 'Thong Lor', 'Siam').
               - "badge": Use "{source_tag}"
            
            Return JSON List of objects (excluding nulls).
            Example:
            [
                {{
                    "catchy_headline": "방콕 통로의 숨겨진 보석, 이국적인 분위기의 루프탑 바!",
                    "desc": "통로의 야경을 한눈에 담을 수 있는 이 루프탑 바는 독특한 칵테일과 라이브 음악으로 완벽한 밤을 선사합니다. 친구들과 특별한 추억을 만들고 싶다면 이곳을 방문해보세요.",
                    "location": "Thong Lor"
                }},
                null,
                {{
                    "catchy_headline": "짜뚜짝 시장 근처, 현지인만 아는 가성비 맛집 발견!",
                    "desc": "주말 시장 구경 후 허기진 배를 채우기 좋은 곳. 신선한 해산물 요리와 태국 전통 음식을 저렴한 가격에 즐길 수 있습니다. 웨이팅은 필수!",
                    "location": "Chatuchak"
                }}
            ]
            """
            
            response = model.generate_content(prompt)
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            
            processed = []
            for res in data:
                if not res: continue # Skip null items (filtered)
                
                idx = res.get('original_index')
                if idx is not None and idx < len(raw_inputs):
                    original = raw_inputs[idx]
                    res['image_url'] = original.get('raw_img') 
                    res['link'] = original.get('raw_link')
                    res['badge'] = source_tag
                    processed.append(res)
            return processed
        except Exception as e:
            print(f"Analysis Error ({source_tag}): {e}")
            return []

    # Main Loop
    for target in targets:
        try:
            # Google News RSS URL (Reduced restriction)
            rss_url = f"https://news.google.com/rss/search?q=site:{target['domain']}&hl=en-TH&gl=TH&ceid=TH:en"
            print(f"Reading RSS: {target['name']}...")
            
            import time
            time.sleep(1) # Add delay to avoid rapid-fire requests
            resp = requests.get(rss_url, headers=headers, timeout=10)
            feed = feedparser.parse(resp.content)
            
            raw_items = []
            # Check up to 10 entries to find 2 valid ones
            for entry in feed.entries[:10]:
                if len(raw_items) >= 2: break
                
                # 1. Deduplication (Link & Title)
                if entry.link in existing_links or entry.link in seen_links:
                    print(f"Skipping duplicate: {entry.title}")
                    continue
                
                # 2. Chillpainai Filter
                if target['name'] == "Chillpainai" and "Thai Trip" in entry.title:
                    print(f"Skipping Chillpainai 'Thai Trip': {entry.title}")
                    continue

                seen_links.add(entry.link)
                
                # Attempt to find image
                img_src = ""
                if 'media_content' in entry:
                    img_src = entry.media_content[0]['url']
                elif 'description' in entry:
                     import re
                     match = re.search(r'src="([^"]+)"', entry.description)
                     if match: img_src = match.group(1)
                
                raw_items.append({
                    "raw_title": entry.title,
                    "raw_link": entry.link,
                    "raw_img": img_src,
                    "context": f"Latest article from {target['name']}"
                })
            
            if raw_items:
                analyzed = analyze_rss_items(raw_items, target['tag'])
                items.extend(analyzed)
                
        except Exception as e:
            print(f"Error fetching {target['name']}: {e}")

    # Shuffle for Magazine feel
    random.shuffle(items)
    return items

def push_changes_to_github(files_to_commit, commit_message):
    """
    Commits and pushes specified files to GitHub.
    Requires GITHUB_TOKEN in secrets.toml or environment.
    """
    import subprocess
    import toml
    
    # 1. Get Token
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            secrets = toml.load(".streamlit/secrets.toml")
            token = secrets.get("GITHUB_TOKEN")
        except: pass
    
    if not token:
        return False, "GITHUB_TOKEN not found in secrets."

    # 2. Configure Git (If needed)
    # Check if user is set
    try:
        subprocess.run("git config user.name", shell=True, check=True, capture_output=True)
    except:
        subprocess.run('git config user.email "auto-deploy@streamlit.app"', shell=True)
        subprocess.run('git config user.name "Streamlit Admin"', shell=True)

    try:
        # 3. Add Files
        for f in files_to_commit:
            subprocess.run(f"git add {f}", shell=True, check=True)
            
        # 4. Commit
        subprocess.run(f'git commit -m "{commit_message}"', shell=True, check=True)
        
        # 5. Push
        # Use token in URL for auth
        repo_url = subprocess.check_output("git remote get-url origin", shell=True, text=True).strip()
        
        if "https://" in repo_url:
            auth_url = repo_url.replace("https://", f"https://{token}@")
        else:
            auth_url = repo_url
            
        subprocess.run(f"git push {auth_url} HEAD:main", shell=True, check=True)
        
        return True, "Successfully pushed to GitHub!"
        
    except subprocess.CalledProcessError as e:
        return False, f"Git Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


# --------------------------------------------------------------------------------
# Visitor Counter (counterapi.dev)
# --------------------------------------------------------------------------------

# --------------------------------------------------------------------------------
# Visitor Counter (counterapi.dev)
# --------------------------------------------------------------------------------

def get_visitor_stats():
    """
    Fetches both Total and Daily visitor counts.
    Returns: (total_count, daily_count)
    """
    try:
        import requests
        from datetime import datetime
        
        namespace = "today-thailand-app"
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Keys
        key_total = f"total"
        key_daily = f"date_{today_str}"
        
        # 1. Get Total
        total_val = 0
        try:
            url_total = f"https://api.counterapi.dev/v1/{namespace}/{key_total}"
            r1 = requests.get(url_total, timeout=2)
            if r1.status_code == 200:
                total_val = r1.json().get("count", 0)
        except: pass
        
        # 2. Get Daily
        daily_val = 0
        try:
            url_daily = f"https://api.counterapi.dev/v1/{namespace}/{key_daily}"
            r2 = requests.get(url_daily, timeout=2)
            if r2.status_code == 200:
                daily_val = r2.json().get("count", 0)
        except: pass
            
        return total_val, daily_val
        
    except:
        return 0, 0

def is_bot_user():
    """
    Detects if the current user is a bot based on User-Agent.
    Returns True if a bot is detected.
    """
    try:
        import streamlit as st
        ua = st.context.headers.get("User-Agent", "").lower()
        bot_keywords = [
            "googlebot", "bingbot", "yandexbot", "baiduspider", "slurp", 
            "duckduckbot", "ia_archiver", "facebot", "facebookexternalhit",
            "twitterbot", "rogerbot", "linkedinbot", "embedly", "quora link preview",
            "showyoubot", "outbrain", "pinterest/0.", "naverbot", "telegrambot",
            "whatsapp", "viber", "skypeuri", "health check"
        ]
        return any(bot in ua for bot in bot_keywords)
    except:
        return False

def increment_visitor_stats():
    """
    Increments both Total and Daily counts (once per session).
    Returns: (new_total, new_daily)
    """
    try:
        import requests
        from datetime import datetime
        
        # [NEW] Bot Filtering: skip increment if bot
        is_bot = is_bot_user()
        
        namespace = "today-thailand-app"
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Keys
        key_total = f"total"
        key_daily = f"date_{today_str}"
        
        # 1. Hit Total
        total_val = 0
        try:
            url_total = f"https://api.counterapi.dev/v1/{namespace}/{key_total}/"
            # Append 'up' only for humans
            url_total += "up" if not is_bot else "get"
            r1 = requests.get(url_total, timeout=2)
            if r1.status_code == 200:
                total_val = r1.json().get("count", 0)
        except: pass
        
        # 2. Hit Daily
        daily_val = 0
        try:
            url_daily = f"https://api.counterapi.dev/v1/{namespace}/{key_daily}/"
            # Append 'up' only for humans
            url_daily += "up" if not is_bot else "get"
            r2 = requests.get(url_daily, timeout=2)
            if r2.status_code == 200:
                daily_val = r2.json().get("count", 0)
        except: pass
        
        return total_val, daily_val
        
    except:
        return 0, 0
        return 0, 0

# --------------------------------------------------------------------------------
# Twitter Trend Analyzer (trends24.in + Gemini)
# --------------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 mins
def fetch_twitter_trends(api_key):
    """
    Scrapes trends24.in/thailand/ for top 10 hashtags and analyzes them with Gemini.
    Returns: dict { "topic": "...", "reason": "...", "severity": "info" } or None
    """
    import requests
    from bs4 import BeautifulSoup
    import google.generativeai as genai
    import json
    
    url = "https://trends24.in/thailand/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print("Fetching Twitter Trends from trends24.in...")
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # trends24 structure: .trend-card__list (first one is latest) -> li -> a
        trend_list = soup.select('.trend-card__list')
        
        if not trend_list:
            print("No trend list found.")
            return None
            
        # Get top 10 from the most recent hour (first list)
        top_trends = []
        for li in trend_list[0].find_all('li')[:10]:
            text = li.get_text(strip=True)
            # Pre-filter: Explicitly skip "Q+number" + "shooting" patterns (Drama schedule)
            import re
            if re.search(r'Q\d+', text, re.IGNORECASE) and re.search(r'shooting', text, re.IGNORECASE):
                print(f"Skipping Drama Shooting Trend: {text}")
                continue
            top_trends.append(text)
            
        if not top_trends:
            print("No valid trends after filtering.")
            return None
            
        print(f"Top 10 Trends (Filtered): {top_trends}")
        
        # Analyze with Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = f"""
        # Role
        You are a 'Security and Safety Analyst' for Bangkok, Thailand.

        # Context
        Thai Twitter trends are 80% dominated by **BL dramas (Y-Series), celebrity fandoms, and TV shows**.
        Words like 'Shooting', 'Attack', 'Fire' often appear but are **NOT real disasters** - they are drama titles or plot descriptions.
        Specifically, 'Q1 Shooting', 'Q2 Shooting' refers to "Queue" (Filming session) schedules, NOT gun violence.

        # Task
        Analyze these real-time Thailand Twitter trends:
        {json.dumps(top_trends, ensure_ascii=False)}
        
        Strictly determine if any trend represents a **'Real-world Physical Danger'** vs **'Media Content'**.

        # Critical Rules (MUST FOLLOW)
        1. **Drama/Movie Check:** If hashtag contains 'EP', 'Series', 'TheMovie', 'OnAir', 'Q1'~'Q99' with 'Shooting', actor names, or looks like a show title → **ALWAYS return null**.
        2. **Cross-Verification:** For "Shooting" or "Fire" to be valid, there MUST be a **specific location name** (Siam Paragon, Central World, etc.) or **clear situation description**.
        3. **Default to Ignore:** If unsure whether it's a real event or drama → **return null**. False alarms are MORE dangerous than missing info.
        4. **Still Useful:** K-Pop arrivals (airport crowds), Protests with location, Severe Weather with location → valid.

        # Few-shot Examples
        - "#TheFireQ8Shooting" → null (Reason: Q8 is episode/queue code for drama filming)
        - "#StarQ1Shooting" → null (Reason: Drama filming schedule)
        - "#SiamParagonShooting" → {{"severity": "warning", "reason": "시암 파라곤 쇼핑몰에서 총격 신고가 접수됨"}}
        - "#BrightWinEP10" → null (BL drama episode)
        - "#ม็อบราชประสงค์" → {{"severity": "warning", "reason": "라차쁘라송 사거리에서 시위 중, 교통 혼잡 예상"}}

        # Output Format (JSON)
        Return ONLY one of these:
        - null (if nothing relevant or uncertain)
        - {{"topic": "Keyword", "reason": "1 sentence in KOREAN for tourist", "severity": "warning" or "info"}}
        """
        
        response = model.generate_content(prompt)
        result_text = response.text.strip().replace("```json", "").replace("```", "")
        
        # specific handling for null
        if "null" in result_text.lower() and len(result_text) < 10:
             return None
             
        data = json.loads(result_text)
        
        # Add Collection Time (Bangkok Time)
        import pytz
        from datetime import datetime
        bkk = pytz.timezone('Asia/Bangkok')
        now_bkk = datetime.now(bkk)
        
        data['collected_at'] = now_bkk.strftime("%Y-%m-%d %H:%M:%S")
        
        return data


    except Exception as e:
        print(f"Twitter Trend Error: {e}")
        return None

# --------------------------------------------------------
# Hotel Fact Check Features
# --------------------------------------------------------
import streamlit as st # Added for user requested st.error/st.warning

def fetch_hotel_candidates(hotel_name, city, api_key):
    """
    Step 1: Search for potential hotels (Candidates).
    Returns: List of dicts [{'id':..., 'name':..., 'address':...}] or None
    """
    # 1. Query Expansion (Removed forced 'Hotel' suffix)
    # Why? 'Centara' + 'Hotel' -> strictly matches 'Centara Hotel' (budget branch),
    # obscuring 'Centara Grand Mirage' (Resort).
    # Google Places TextSearch handles "Brand in City" better without forced suffixes.
    
    hotel_name = hotel_name.strip()
    
    # 2. Construct Query
    # Detect Korean to optimize query structure
    import re
    is_korean = bool(re.search(r'[가-힣]', hotel_name))
    
    if is_korean:
         # 2-1. Brand Mapping (Korean -> English) for higher accuracy
         # Google Maps works significantly better with English brand names.
         brand_map = {
             "센타라": "Centara",
             "아마리": "Amari",
             "힐튼": "Hilton",
             "하얏트": "Hyatt",
             "메리어트": "Marriott",
             "쉐라톤": "Sheraton",
             "홀리데이인": "Holiday Inn",
             "아난타라": "Anantara",
             "아바니": "Avani",
             "두짓타니": "Dusit Thani",
             "노보텔": "Novotel",
             "르메르디앙": "Le Meridien",
             "소피텔": "Sofitel",
             "풀만": "Pullman",
             "인터컨티넨탈": "InterContinental",
             "반얀트리": "Banyan Tree",
             "샹그릴라": "Shangri-La",
             "켐핀스키": "Kempinski",
             "카펠라": "Capella",
             "포시즌스": "Four Seasons",
             "세인트레지스": "St. Regis",
             "더스탠다드": "The Standard"
         }
         
         # Check if hotel_name starts with or contains a known brand
         english_brand = None
         for kr_brand, en_brand in brand_map.items():
            if kr_brand in hotel_name:
                # Replace Korean Brand with English Brand in the query
                # e.g. "센타라" -> "Centara"
                # e.g. "센타라 그랜드" -> "Centara 그랜드" (Mixed is fine, but pure English is best)
                # Let's just switch to English mode if it's a pure brand query
                if hotel_name.strip() == kr_brand:
                    hotel_name = en_brand
                    is_korean = False # Switch to English Logic
                else:
                    # Mixed case: "센타라 리조트" -> replace '센타라' with 'Centara'
                    hotel_name = hotel_name.replace(kr_brand, en_brand)
                    # Keep is_korean = True for now unless we are sure, 
                    # but actually "Centara 리조트" is better searched as "Centara Resort" (English logic handles mixed okay?)
                    # Let's try to trust the English Logic if we have English Name now.
                    # Actually better to treat as English-ish if we injected English Brand.
                    pass 
                break
    
    if is_korean:
         # Korean Fallback: Revert to Broad Search (No 'Hotel Resort' force)
         # 'Hotel Resort' keyword excluded pure Hotels (e.g. Centara Nova).
         # Broad search 'Name City Thailand' is safest for unmapped brands.
         search_query = f"{hotel_name} {city} Thailand"
    else:
         # English (or Mapped English): Use 'in' logic
         search_query = f"{hotel_name} in {city}, Thailand"
    
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress"
    }
    # Limit to 10 candidates
    payload = {
        "textQuery": search_query,
        "maxResultCount": 20
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            # st.error(f"🚨 API 호출 실패: {response.status_code}")
            return None
            
        data = response.json()
        
        if not data.get("places"):
            return [] 
            
        # Extract meaningful candidates (Increased to 10)
        candidates = []
        for p in data["places"][:10]:
            candidates.append({
                "id": p["id"],
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", "")
            })
        return candidates

    except Exception as e:
        st.error(f"시스템 오류 발생: {e}")
        return None

def fetch_hotel_details(place_id, api_key):
    """
    Step 2: Fetch full details for a specific Place ID.
    Returns: place_dict or None
    """
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "id,displayName,formattedAddress,rating,userRatingCount,reviews,photos"
    }
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            st.error(f"상세 정보 조회 실패: {resp.text}")
            return None
            
        place = resp.json()
        
        # Photo handling - 단일 대표 사진
        photo_url = None
        # Photo gallery - 최대 10장
        photo_urls = []
        
        if place.get("photos"):
            photos = place["photos"][:10]  # 최대 10장
            for photo in photos:
                photo_ref = photo.get("name")
                if photo_ref:
                    gallery_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=400&maxWidthPx=600&key={api_key}"
                    photo_urls.append(gallery_url)
            
            # 첫 번째 사진을 대표 사진으로
            if photos:
                photo_ref = photos[0]["name"]
                photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=800&maxWidthPx=800&key={api_key}"

        return {
            "name": place.get("displayName", {}).get("text", "Unknown"),
            "address": place.get("formattedAddress", ""),
            "rating": place.get("rating", 0.0),
            "review_count": place.get("userRatingCount", 0),
            "reviews": place.get("reviews", []),
            "photo_url": photo_url,
            "photo_urls": photo_urls  # 갤러리용 사진 리스트
        }
    except Exception as e:
        st.error(f"상세 정보 처리 중 오류: {e}")
        return None

def analyze_hotel_reviews(hotel_name, rating, reviews, api_key, language="Korean"):
    """
    Analyze hotel reviews using Gemini with a specific 'Cold Inspector' persona.
    (Supports English and Korean)
    """
    is_english = (language == "English")
    try:
        # 1. Prepare Review Text
        reviews_text = ""
        for r in reviews[:5]: # Use top 5 reviews
             text = r.get("text", {}).get("text", "")
             if text:
                 reviews_text += f"- {text}\n"

        # 2. Gemini Prompt
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})

        if is_english:
            lang_instruction = "IMPORTANT: ALL JSON OUTPUT VALUES MUST BE IN ENGLISH."
            persona = "You are a 'Cold Hotel Inspector'. Provide a blunt, factual analysis of the hotel based on facts and data, avoiding marketing fluff."
            cons_instruction = "List only real issues like noise, dirt, bad breakfast, far location. If none, write: 'No significant drawbacks found. (Overall excellent evaluation)'"
        else:
            lang_instruction = "중요: 모든 JSON 출력값은 반드시 한국어로 작성하세요."
            persona = "너는 '냉철한 호텔 검증가'야. 사용자가 이 호텔을 **'실제로 예약할지 말지'** 결정할 수 있도록, 광고 멘트는 빼고 오직 **팩트와 실제 후기**에 기반해서 분석해줘."
            cons_instruction = "명확하게 지적된 부정적 키워드가 있을 때만 적어. 단점이 하나도 없다면: '특별한 단점이 발견되지 않았습니다. (전반적으로 우수한 평가)'라고 적어."

        prompt = f"""
        {persona}
        {lang_instruction}

        **[Information]**
        * Hotel: {hotel_name} (Rating: {rating})
        * Recent Reviews: {reviews_text}
        * **Augment:** Use your internal knowledge about {hotel_name}'s location, brand, breakfast, and pool.

        **[Rules for Cons]**
        1. Don't say 'No information about X'.
        2. {cons_instruction}

        **[Not Recommended Guide]**
        Must be specific to Price, Noise, Location, or Mood. (e.g., 'Budget travelers seeking value' or 'Guests who prefer walking to BTS')

        **[Output Format (JSON)]**
        {{
            "name_eng": "Official English name (e.g. Centara Grand at CentralWorld)",
            "trip_keyword": "Korean keyword for Trip.com search (city omitted, e.g. 아마리 워텔게이트)",
            "price_level": "💰 step (1~4)",
            "price_range_text": "Price range in KRW (e.g. 약 120,000원 ~ 180,000원)",
            "one_line_verdict": "string",
            "recommendation_target": "string",
            "location_analysis": "string",
            "room_condition": "string",
            "service_breakfast": "string",
            "pool_facilities": "string",
            "pros": ["string", "string", "string"],
            "cons": ["string", "string", "string"],
            "summary_score": {{
                "cleanliness": integer 1-5, "location": integer 1-5, "comfort": integer 1-5, "value": integer 1-5
            }}
        }}
        """
        
        response = model.generate_content(prompt)
        return json.loads(response.text)

    except Exception as e:
        return {"error": str(e)}

# --------------------------------------------------------------------------------
# Infographic Generator (PIL based)
# --------------------------------------------------------------------------------
def ensure_font_loaded():
    """
    Downloads NanumGothic font if not present.
    Returns path to font file.
    """
    FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
    FONT_PATH = "data/NanumGothic-Bold.ttf"
    
    if not os.path.exists(FONT_PATH):
        try:
            print("Downloading font for Infographic...")
            import requests
            r = requests.get(FONT_URL, timeout=10)
            with open(FONT_PATH, 'wb') as f:
                f.write(r.content)
            print("Font downloaded.")
        except Exception as e:
            print(f"Font download failed: {e}")
            return None # Fallback to default
            
    return FONT_PATH

def prettify_infographic_text(category, items, api_key):
    """
    Uses Gemini to shorten news into 'Emoji + One-liner' format.
    """
    if not items: return []
    
    # Cost optimization: If API Key missing, just use titles
    if not api_key:
        return [f"📰 {item['title']}" for item in items[:3]]

    import google.generativeai as genai
    import json
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Simplified inputs
    inputs = "\n".join([f"- {item['title']}" for item in items[:3]])
    
    prompt = f"""
    Convert these 3 news headlines into a "Social Media Infographic" style (Korean).
    Category: {category}
    
    Input:
    {inputs}
    
    Goal: Return a JSON list of strings. Each string must start with a relevant Emoji and be very short (max 20 chars).
    Example: ["🚨 시암 파라곤 총격 발생", "⛈️ 내일 방콕 홍수 주의", "🎉 송크란 축제 일정 발표"]
    
    Output JSON: {{ "lines": ["...", "...", "..."] }}
    """
    
    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip().replace("```json", "").replace("```", "")
        if text.startswith("```"): text = text.replace("```", "")
        data = json.loads(text)
        result = data.get("lines", [])
        if not result:
            raise ValueError("Empty lines from AI")
        return result
    except Exception as e:
        print(f"Infographic AI Error: {e}")
        # Fallback to simple titles
        return [f"📰 {item['title'][:18]}..." for item in items[:3]]

def generate_category_infographic(category, items, date_str, api_key):
    """
    Generates a social media image for a specific category.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        import streamlit as st
        st.error(f"Pillow Library Missing: {e}")
        return None

    try:
        import os
        
        # 1. Config Map (Color & Text)
        # Categories: "정치/사회", "경제", "여행/관광", "사건/사고", "축제/이벤트", "기타"
        theme_map = {
            "정치/사회": {"color": (59, 130, 246), "bg_file": "assets/bg_politics.png", "title": "POLITICS & SOCIAL"}, # Blue
            "경제": {"color": (34, 197, 94), "bg_file": "assets/bg_economy.png", "title": "ECONOMY"}, # Green
            "여행/관광": {"color": (249, 115, 22), "bg_file": "assets/bg_travel.png", "title": "TRAVEL NEWS"}, # Orange
            "사건/사고": {"color": (239, 68, 68), "bg_file": "assets/bg_safety.png", "title": "SAFETY ALERT"}, # Red
            "축제/이벤트": {"color": (236, 72, 153), "bg_file": "assets/bg_travel.png", "title": "THAI EVENTS"}, # Pink
            "기타": {"color": (107, 114, 128), "bg_file": "assets/template.png", "title": "DAILY NEWS"} # Gray
        }
        
        theme = theme_map.get(category, theme_map["기타"])
        
        # 2. Get AI Content
        lines = prettify_infographic_text(category, items, api_key)
        if not lines: return None

        # 3. Setup Canvas (1080x1080 Square for Instagram)
        # 3. Setup Canvas (1080x1080 Square for Instagram)
        W, H = 1080, 1080
        
        # Try Dynamic Background (Use Image from first news item)
        bg_img = None
        
        # Find first item with valid image
        target_img_url = None
        for item in items:
            if item.get("image_url") and item["image_url"].startswith("http"):
                target_img_url = item["image_url"]
                break
                
        if target_img_url:
            try:
                import requests
                from io import BytesIO
                
                # Download Image
                # print(f"Downloading BG: {target_img_url}")
                resp = requests.get(target_img_url, timeout=5)
                if resp.status_code == 200:
                    raw_img = Image.open(BytesIO(resp.content)).convert("RGB")
                    
                    # Resize & Center Crop to cover 1080x1080
                    # logic: Scale shortest side to 1080, then crop center
                    img_w, img_h = raw_img.size
                    ratio = max(W/img_w, H/img_h)
                    new_size = (int(img_w * ratio), int(img_h * ratio))
                    raw_img = raw_img.resize(new_size, Image.LANCZOS)
                    
                    # Center Crop
                    left = (new_size[0] - W)/2
                    top = (new_size[1] - H)/2
                    right = (new_size[0] + W)/2
                    bottom = (new_size[1] + H)/2
                    
                    bg_img = raw_img.crop((left, top, right, bottom))
                    
                    # Apply Dimming (Black Overlay 60%)
                    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 150))
                    bg_img.paste(overlay, (0, 0), mask=overlay)
                    
            except Exception as e:
                # print(f"BG Image Error: {e}")
                bg_img = None

        # Fallback to Theme Background if Dynamic failed
        if not bg_img:
            if os.path.exists(theme['bg_file']):
                bg_img = Image.open(theme['bg_file']).convert("RGB")
                bg_img = bg_img.resize((W, H))
            else:
                # Create solid color background with gradient-ish look (simple solid for now)
                bg_img = Image.new('RGB', (W, H), theme['color'])
                # Add a subtle dark overlay for text contrast
                overlay = Image.new('RGBA', (W, H), (0,0,0, 50))
                bg_img.paste(overlay, (0,0), mask=overlay)
                
        img = bg_img
        
        draw = ImageDraw.Draw(img)
        
        # Fonts
        font_path = ensure_font_loaded()
        if not font_path:
            # Emergency fallback (might fail on korean)
            font_cat = ImageFont.load_default()
            font_date = ImageFont.load_default()
            font_body = ImageFont.load_default()
            font_footer = ImageFont.load_default()
        else:
            font_cat = ImageFont.truetype(font_path, 60)
            font_date = ImageFont.truetype(font_path, 40)
            font_body = ImageFont.truetype(font_path, 55)
            font_footer = ImageFont.truetype(font_path, 30)
            
        # Draw logic
        # Header: Category Title (English) + Date
        draw.text((80, 80), theme['title'], font=font_cat, fill="white")
        draw.text((80, 160), date_str, font=font_date, fill=(255, 255, 255, 200)) # Alpha 200
        
        # Divider
        draw.line((80, 230, 1000, 230), fill="white", width=4)
        
        # Body Content (Centered vertically-ish)
        start_y = 350
        gap = 120
        
        for i, line in enumerate(lines):
            # Draw badge/bullet?
            # Just text
            draw.text((80, start_y + (i * gap)), line, font=font_body, fill="white")
            
        # Footer
        draw.text((80, 1000), "🇹🇭 오늘의 태국 (Thai Briefing)", font=font_footer, fill=(255, 255, 255, 150))
        
        return img

    except Exception as e:
        import streamlit as st
        st.error(f"Infographic Error ({category}): {e}")
        return None
    
# --------------------------------------------------------------------------------
# Taxi Fare Calculator (Google Maps + Rush Hour Logic)
# --------------------------------------------------------------------------------
def get_route_estimates(origin, destination, api_key):
    """
    Get Distance & Duration using Google Routes API (Compute Routes v2).
    Replaces legacy Directions API.
    Returns: dist_km, dur_min, traffic_ratio, error_message
    """
    if not origin or not destination:
        return None, None, None, "출발지와 목적지를 입력해주세요."
        
    endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    # Prepare Origin/Dest objects
    def build_wp(val):
        if val.startswith("place_id:"):
            return {"placeId": val.split(":")[1]}
        else:
            return {"address": val}
            
    payload = {
        "origin": build_wp(origin),
        "destination": build_wp(destination),
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE", # Important for traffic data
        "computeAlternativeRoutes": False,
        "languageCode": "ko-KR",
        "units": "METRIC"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.staticDuration"
    }
    
    try:
        import requests
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        data = resp.json()
        
        if resp.status_code == 200:
            if not data.get("routes"):
                return None, None, None, "경로를 찾을 수 없습니다."
                
            route = data["routes"][0]
            
            # Distance (meters)
            dist_km = route.get("distanceMeters", 0) / 1000
            
            # Helper to parse "123s" string format
            def parse_duration(dur_str):
                if not dur_str: return 0
                return int(dur_str.replace("s", ""))
                
            # Duration (Real-time with TRAFFIC_AWARE)
            real_dur_sec = parse_duration(route.get("duration", "0s"))
            # Static Duration (No traffic)
            base_dur_sec = parse_duration(route.get("staticDuration", "0s"))
            
            dur_min = real_dur_sec / 60
            
            # Traffic Ratio
            traffic_ratio = 1.0
            if base_dur_sec > 0:
                traffic_ratio = real_dur_sec / base_dur_sec
            
            return dist_km, dur_min, traffic_ratio, None
            
        else:
            # API Error
            err_details = data.get("error", {})
            msg = err_details.get("message", "Unknown Error")
            status = err_details.get("status", resp.status_code)
            return None, None, None, f"Routes API 오류 ({status}): {msg}"
            
    except Exception as e:
        return None, None, None, f"시스템 오류: {e}"

def calculate_expert_fare(dist_km, dur_min, origin_txt="", dest_txt=""):
    """
    Calculates fair prices for various transport modes in Bangkok.
    Now includes Rush Hour Logic & Hell Zone Detection.
    
    Args:
        origin_txt (str): Name/Address of origin (for Hell Zone checking)
        dest_txt (str): Name/Address of dest
    """
    from datetime import datetime, time
    import pytz
    
    # 1. Check Rush Hour (Bangkok Time)
    tz_bkk = pytz.timezone('Asia/Bangkok')
    now_bkk = datetime.now(tz_bkk)
    current_time = now_bkk.time()
    
    is_rush_hour = False
    morning_start = time(7, 0)
    morning_end = time(9, 30)
    evening_start = time(16, 30)
    evening_end = time(20, 0)
    
    if (morning_start <= current_time <= morning_end) or \
       (evening_start <= current_time <= evening_end):
        is_rush_hour = True
        
    # 2. Check Hell Zone (Traffic Hell)
    hell_zones = ["Asok", "Sukhumvit", "Siam", "Sathorn", "Silom", "Thong Lo", "Phrom Phong"]
    chk_str = (str(origin_txt) + " " + str(dest_txt)).lower()
    is_hell_zone = any(z.lower() in chk_str for z in hell_zones)

    # 3. Base Meter Calculation
    # Note: 'dur_min' already includes traffic delay if Routes API works correclty.
    # Adjusted: Reduced time weight (2.5 -> 2.25) to be more realistic with modern traffic apps
    base_meter = 35 + (dist_km * 7) + (dur_min * 2.25)
    base_meter = int(base_meter)
    
    # 4. Multipliers
    # Tuned down Rush Hour Multiplier (1.5 -> 1.25) based on user feedback
    rush_mult = 1.25 if is_rush_hour else 1.0
    tuktuk_rush_mult = 1.2 if is_rush_hour else 1.0
    
    # Hell Zone Surcharge (1.1x) if applicable
    hell_mult = 1.1 if is_hell_zone else 1.0
    
    # Final App Multiplier (Combined)
    total_app_mult = rush_mult * hell_mult

    # Calculate raw prices (Adjusted down based on user feedback)
    # Target: Meter x (1.2 ~ 1.6 including surge)
    bolt_basic_raw = int(base_meter * 0.85 * total_app_mult)
    bolt_std_raw = int(base_meter * 1.0 * total_app_mult)
    grab_raw = int(base_meter * 1.1 * total_app_mult)
    
    # Grab Range (+- 10%)
    grab_min = int(grab_raw * 0.9)
    grab_max = int(grab_raw * 1.1)

    # Bike Range (+- 10%)
    bike_raw = 25 + (dist_km * 8)
    bike_min = int(bike_raw * 0.9)
    bike_max = int(bike_raw * 1.1)

    fares = {
        "bolt": {
            "label": "⚡ Bolt (통합)",
            "price": f"{bolt_basic_raw} ~ {bolt_std_raw}",
            "tag": "차 잡기 힘듦" if not is_rush_hour else "매우 비쌈",
            "color": "green" # Merged color
        },
        "grab_taxi": {
            "label": "💚 Grab (Standard)",
            "price": f"{grab_min} ~ {grab_max}",
            "tag": "안전/빠름" if not is_rush_hour else "매우 비쌈",
            "color": "blue"
        },
        "bike": {
            "label": "🏍️ 오토바이 (Win)",
            "price": f"{bike_min} ~ {bike_max}",
            "tag": "🚀 가장 빠름",
            "color": "orange",
            "warning_text": "⚠️ 사고 위험 높음 / 헬멧 필수 / 보험 확인"
        },
        "tuktuk": {
            "label": "🛺 뚝뚝 (TukTuk)",
            "tag": "협상 필수",
            "color": "red",
            "warning": True
        }
    }
    
    # Calc TukTuk Range
    tt_min = int(base_meter * 1.5 * tuktuk_rush_mult) 
    tt_max = int(base_meter * 2.0 * tuktuk_rush_mult)
    fares['tuktuk']['price'] = f"{tt_min} ~ {tt_max}"
    
    # ---------------------------------------------------------
    # 5. Intercity / Long Distance Logic (Flat Rate)
    # ---------------------------------------------------------
    is_intercity = False
    intercity_tip = None
    
    # Check Keywords (Priority)
    dest_lower = str(dest_txt).lower()
    
    flat_rates = {
        "pattaya": {"range": (1100, 1400), "tip": "🚌 에까마이 터미널에서 버스 타면 약 131바트!"},
        "hua hin": {"range": (2000, 2400), "tip": "🚆 기차나 미니밴을 이용하면 200~400바트!"},
        "ayutthaya": {"range": (900, 1200), "tip": "🚆 기차(20바트~)나 미니밴을 추천합니다!"},
        "suvarnabhumi": {"range": (400, 500), "tip": "🚆 공항철도(ARL)를 타면 시내까지 45바트 내외!"} # Airport special
    }
    
    matched_zone = None
    for key, data in flat_rates.items():
        if key in dest_lower:
            matched_zone = data
            is_intercity = True
            break
            
    # Generic Long Distance (> 60km)
    if not matched_zone and dist_km >= 60:
        is_intercity = True
        # Formula: 1200 + ((dist - 100) * 10)
        est_price = 1200 + ((dist_km - 100) * 10)
        est_min = int(est_price * 0.9)
        est_max = int(est_price * 1.1)
        
        matched_zone = {"range": (est_min, est_max), "tip": "🚌 장거리 이동은 버스/기차/미니밴 이용을 고려해보세요! (훨씬 저렴함)"}

    if is_intercity and matched_zone:
        r_min, r_max = matched_zone['range']
        price_str = f"{r_min} ~ {r_max}"
        intercity_tip = matched_zone['tip']
        
        # Override Fares
        fares['bolt']['price'] = price_str
        fares['grab_taxi']['price'] = price_str # Apps often follow market flat rates for long distance
        fares['tuktuk']['price'] = "운행 불가" # Tuktuk highly unlikely
        fares['bike']['price'] = "추천 안함"
    
    return base_meter, fares, is_rush_hour, is_hell_zone, intercity_tip

def search_places(query, api_key):
    """
    Search using Google Places Autocomplete API for better partial matching.
    Returns: {name, address, place_id}
    """
    if not query: return []
    
    # Use Autocomplete API as requested into order to support 'Top 10' predictions and 'components' filtering
    endpoint = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": api_key,
        "language": "ko",
        "components": "country:TH" # Strict Thailand restriction
    }
    
    try:
        import requests
        resp = requests.get(endpoint, params=params, timeout=5)
        data = resp.json()
        
        candidates = []
        if data.get('status') == 'OK':
            for p in data.get('predictions', [])[:10]:
                main_text = p.get('structured_formatting', {}).get('main_text', '')
                sec_text = p.get('structured_formatting', {}).get('secondary_text', '')
                full_text = p.get('description', '')
                
                candidates.append({
                    "name": main_text if main_text else full_text,
                    "address": sec_text,
                    "place_id": p.get('place_id')
                })
        return candidates
    except Exception as e:
        print(f"Autocomplete Error: {e}")
        return []

# --------------------------------------------------------------------------------
# Wongnai Restaurant Analyzer
# --------------------------------------------------------------------------------
def search_wongnai_restaurant(restaurant_name, api_key=None):
    """
    Search for a restaurant on Wongnai using Google search.
    Tries legacy search first, and always falls back to Gemini if it fails or returns nothing.
    """
    found_url = None
    
    # 1. Try legacy search (might be throttled or throw exceptions)
    queries = [
        f"site:wongnai.com {restaurant_name}",
        f"wongnai {restaurant_name}"
    ]
    
    try:
        for query in queries:
            results = googlesearch.search(query, num_results=3)
            for url in results:
                if "wongnai.com/restaurants/" in url or "wongnai.com/r/" in url:
                    found_url = url
                    break
            if found_url: break
    except Exception as e:
        print(f"Legacy search failed: {e}")
        pass # Ignore legacy errors and move to Gemini fallback
    
    if found_url:
        return found_url
    
    # 2. Strong Fallback: Gemini Search
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Find the Wongnai restaurant URL for: {restaurant_name}. Return ONLY the direct URL starting with https://www.wongnai.com/restaurants/ or https://www.wongnai.com/r/"
            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Extract URL more robustly
            match = re.search(r'(https?://(?:www\.)?wongnai\.com/(?:restaurants|r)/[^\s]+)', raw_text)
            if match:
                return match.group(1).rstrip('.')
        except Exception as e:
            print(f"Gemini fallback search error: {e}")
            
    return None

def scrape_wongnai_restaurant(url):
    """
    Scrape restaurant data from a Wongnai URL.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"error": f"현시점 웡나이 접속이 원활하지 않습니다 (Code: {response.status_code})"}

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Name (Wongnai uses dynamic classes sometimes, but h1 is fairly stable)
        name_tag = soup.find('h1')
        name = name_tag.get_text(strip=True) if name_tag else "Unknown Restaurant"
        
        # 2. Score
        # Typically in a span or div with specific class patterns
        score_tag = soup.find(string=re.compile(r'^\d\.\d$')) # Looks for "4.5" etc.
        score = score_tag.strip() if score_tag else "데이터 없음"
        
        # 3. Price
        price_tag = soup.find(string=re.compile(r'^[฿]+$')) # Looks for "฿฿", "฿฿฿"
        price = price_tag.strip() if price_tag else "데이터 없음"
        
        # 4. Photo
        # Find first large image
        photo_url = None
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            if 'wongnai.com' in src and '/static2/' not in src: # Avoid icons/loaders
                photo_url = src
                break
        
        # 5. Reviews
        reviews = []
        # Wongnai reviews are often in complex structures
        # We try to grab text blocks that look like reviews
        review_texts = soup.find_all(['p', 'span', 'div'], string=re.compile(r'.{20,}'))
        count = 0
        for rt in review_texts:
            text = rt.get_text(strip=True)
            if len(text) > 40 and count < 10:
                reviews.append(text)
                count += 1
            
        return {
            "name": name,
            "score": score,
            "price": price,
            "photo_url": photo_url,
            "reviews": reviews,
            "url": url
        }
    except Exception as e:
        return {"error": f"데이터 수집 중 오류: {str(e)}"}

def analyze_wongnai_data(restaurant_data, api_key):
    """
    Analyze Wongnai data using Gemini AI.
    """
    if "error" in restaurant_data:
        return restaurant_data

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    reviews_text = "\n".join([f"- {r[:200]}..." for r in restaurant_data['reviews']])
    
    prompt = f"""
    태국 현지인 맛집 사이트 'Wongnai'의 데이터를 기반으로 이 식당을 한국인 여행객 관점에서 분석해줘.

    [식당 정보]
    - 이름: {restaurant_data['name']}
    - 웡나이 별점: {restaurant_data['score']}
    - 태국 현지 가격대: {restaurant_data['price']}
    
    [현지 리뷰 데이터 요약]
    {reviews_text}

    [분석 결과 필수 포함 사항 (한국어로 작성)]:
    1. ⭐ 현지인 별점 분위기 (점수가 높은지, 로컬 사람들에게 인기 있는 곳인지)
    2. 🍽️ 추천 메뉴 (리뷰에서 가장 많이 칭찬받는 음식 또는 대표 메뉴)
    3. 🇰🇷 한국인 입맛 적합도 (맵기, 향신료 강도, 한국인이 좋아할 만한 포인트)
    4. 💰 체감 물가 (태국 로컬 물가 대비 어느 정도 수준인지)
    5. 🚫 주의사항 (웨이팅 여부, 위치적 특징, 서비스 관련 지적 등)

    친절하고 신뢰감 있는 말투로 요약해서 답변해줘. 마크다운 형식을 사용하여 가독성 있게 작성할 것.
    """
    
    try:
        response = model.generate_content(prompt)
        return {
            "summary": response.text,
            "info": restaurant_data
        }
    except Exception as e:
        return {"error": f"Gemini 분석 실패: {e}"}


# ============================================
# 🎒 AI Tour Recommendation Engine
# ============================================

def recommend_tours(who, style, budget, region="방콕", language="Korean"):
    """
    사용자 입력을 바탕으로 Gemini AI가 투어를 추천하는 함수.
    
    Args:
        who: 동행인 (예: "혼자", "연인/부부", "가족(아이동반)")
        style: 선호 스타일 리스트 (예: ["인생샷/사진", "역사/문화"])
        budget: 예산 선호 (예: "가성비(저렴)", "적당함", "럭셔리/프리미엄")
        region: 여행 지역 (예: "방콕", "파타야", "치앙마이")
        language: 출력 언어 ("Korean" or "English")
    
    Returns:
        dict: {"recommendations": [{"tour_name": ..., "reason": ..., "tip": ...}, ...]}
        None: on failure
    """
    import google.generativeai as genai
    
    # Get API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import toml
            secrets = toml.load(".streamlit/secrets.toml")
            api_key = secrets.get("GEMINI_API_KEY")
        except:
            pass
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except:
            pass
    
    if not api_key:
        print("❌ GEMINI_API_KEY not found for tour recommendation")
        return None
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Load tours
        TOURS = load_tours()
        
        # Filter tours by region
        filtered_tours = [t for t in TOURS if t.get('region', '방콕') == region]
        
        if not filtered_tours:
            return {"recommendations": []} # No tours for this region

        # Build product catalog for prompt
        is_english = (language == "English")
        
        products_list = []
        for t in filtered_tours:
            # Always include Korean for context, and English if available
            p_name_kr = t.get('name', 'Unknown')
            p_desc_kr = t.get('desc', '')
            p_pros_kr = t.get('pros', '')
            
            p_name_en = t.get('name_en', '')
            p_desc_en = t.get('desc_en', '')
            p_pros_en = t.get('pros_en', '')
            
            p_info = f"- ID {t['id']}. KR_Name: {p_name_kr}, KR_Desc: {p_desc_kr}, KR_Pros: {p_pros_kr}"
            if p_name_en:
                p_info += f" | EN_Name: {p_name_en}, EN_Desc: {p_desc_en}, EN_Pros: {p_pros_en}"
            
            products_list.append(p_info)
        
        products_info = "\n".join(products_list)
        
        style_str = ", ".join(style) if style else ("No specific preference" if is_english else "특별한 선호 없음")

        if is_english:
            prompt = f"""
You are a 'Thailand Travel AI Coordinator' expert on {region}.
Analyze the user's travel style and recommend the **top 6 perfect products** from the [Product Catalog] below.

[User Info]
- Region: {region}
- With: {who}
- Style: {style_str}
- Budget/Other: {budget}

[Product Catalog ({region} only)]
{products_info}

[Output Format - JSON]
- Output MUST be in the following JSON format ONLY. 
- ALL OUTPUT VALUES MUST BE IN ENGLISH.
- If the [Product Catalog] only has Korean info for a product, you MUST translate the Product Name and Pros into natural, persuasive English.
- 'reason' should be 2-3 sentences, friendly, and include emojis.

{{
    "recommendations": [
        {{
            "tour_id": "Product ID (integer)",
            "tour_name_en": "Natural English Product Name (Translate from KR if EN is missing)",
            "reason": "Why we recommend this (In English)",
            "pros_en": "Key Highlights/Pros (Natural English, Translate from KR if EN is missing)",
            "tip": "One useful tip (In English)"
        }},
        ... (Total 6 recommendations)
    ]
}}
"""
        else:
            prompt = f"""
당신은 태국 {region} 여행 전문 'AI 투어 코디네이터'입니다.
사용자의 여행 스타일을 분석하여, 아래 [상품 목록] 중 **가장 완벽한 상품 6개**를 추천해주세요.

[사용자 정보]
- 여행 지역: {region}
- 동행인: {who}
- 선호 스타일: {style_str}
- 예산/기타: {budget}

[상품 목록 ({region} 전용)]
{products_info}

[출력 형식 - JSON]
- 반드시 아래 JSON 형식으로만 출력하세요. 
- 출력되는 모든 텍스트(이유, 꿀팁 등)는 반드시 **한국어**로 작성하세요. 영어 사용을 금지합니다.
- 설명은 친근하게, 이모지를 사용해주세요.
- 사용자의 동행인과 스타일에 맞춰서 개인화된 추천 이유를 작성하세요.

{{
    "recommendations": [
        {{
            "tour_id": "상품 ID (숫자)",
            "tour_name": "상품명 (KR_Name과 정확히 일치)",
            "reason": "추천 이유 (반드시 한국어로 작성)",
            "tip": "꿀팁 한줄 (반드시 한국어로 작성)"
        }},
        ... (총 6개의 추천 항목)
    ]
}}
"""
        
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        return result
        
    except Exception as e:
        print(f"❌ Tour recommendation error: {e}")
        return None

# --- 3. 데이터 로드 및 저장 (Data Handling) ---

# 구글 시트 URL (투어 데이터베이스)
TOURS_SHEET_URL = "https://docs.google.com/spreadsheets/d/186j6qGv1PYmaxUhVDihErGjlFvQfSHERt-4udzrxsHQ/edit?usp=sharing"
TOURS_SHEET_NAME = "시트1"

def load_tours_from_sheet():
    """
    Load tours from Google Sheets.
    Returns: List of tour dictionaries or None on failure.
    """
    try:
        conn = st.connection("gsheets_tours", type=GSheetsConnection)
        df = conn.read(spreadsheet=TOURS_SHEET_URL, worksheet=TOURS_SHEET_NAME)
        
        # Convert DataFrame to list of dicts
        tours = df.to_dict('records')
        
        # Post-process: 'type' column (string -> list)
        for t in tours:
            if isinstance(t.get('type'), str):
                t['type'] = [x.strip() for x in t['type'].split(',') if x.strip()]
            elif not t.get('type'):
                t['type'] = []
                
            # Ensure ID is int
            if 'id' in t:
                try:
                    t['id'] = int(t['id'])
                except:
                    pass
            
            # Ensure price is string (sometimes read as float/int)
            if 'price' in t:
                t['price'] = str(t['price'])

        return tours
    except Exception as e:
        st.error(f"구글 시트 로드 실패: {e}")
        print(f"Error loading tours from sheet: {e}")
        return None

def save_tours_to_sheet(tours_data):
    """
    Save tours to Google Sheets.
    Args:
        tours_data: List of tour dictionaries
    """
    try:
        # Convert list back to DataFrame
        df = pd.DataFrame(tours_data)
        
        # Pre-process: 'type' list -> string
        if 'type' in df.columns:
            df['type'] = df['type'].apply(lambda x: ",".join(x) if isinstance(x, list) else str(x))
            
        conn = st.connection("gsheets_tours", type=GSheetsConnection)
        conn.update(spreadsheet=TOURS_SHEET_URL, worksheet=TOURS_SHEET_NAME, data=df)
        return True
    except Exception as e:
        st.error(f"구글 시트 저장 실패: {e}")
        print(f"Error saving tours to sheet: {e}")
        return False

def load_tours():
    """Load tours from Google Sheets (primary) or local JSON (fallback)"""
    # 1. Try Google Sheets
    sheet_tours = load_tours_from_sheet()
    if sheet_tours:
        # Update local cache (Disabled to prevent app restart during session)
        # save_tours_local(sheet_tours)
        return sheet_tours
        
    # 2. Fallback to Local
    print("Fallback to local tours.json")
    return load_tours_local()

def load_tours_local():
    """Load tours from data/tours.json"""
    try:
        with open('data/tours.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_tours(tours):
    """Save tours to Google Sheets AND local JSON"""
    # 1. Save to Sheet
    success = save_tours_to_sheet(tours)
    
    # 2. Save to Local (Cache - Only if Sheet fails and on Localhost)
    # Writing to source files causes Streamlit to restart, clearing sessions.
    if not success:
        save_tours_local(tours)
        print("Warning: Failed to save to Google Sheet, but saved locally.")

def save_tours_local(tours):
    """Save tours to data/tours.json"""
    try:
        os.makedirs(os.path.dirname('data/tours.json'), exist_ok=True)
        with open('data/tours.json', 'w', encoding='utf-8') as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving local tours: {e}")

# 지역별 클룩 제휴 링크 (상수)
CITY_LINKS = {
    "방콕": "https://klook.tpx.li/X9VgSPk8",
    "파타야": "https://klook.tpx.li/Te6TSv6q",
    "치앙마이": "https://klook.tpx.li/yPsMZRxS",
    "푸켓": "https://klook.tpx.li/FDM1ZPlZ",
    "코사무이": "https://klook.tpx.li/PjbJR2GU",
    "끄라비": "https://klook.tpx.li/WoWJSmgF",
}

# UI에서 사용하는 지역 옵션 (이모지 포함)
# 지역별 옵션 및 매핑 (Localization 지원)
def get_region_options():
    lang = st.session_state.get('language', 'Korean')
    if lang == 'English':
        return ["🏙️ Bangkok", "🏖️ Pattaya", "🐘 Chiang Mai", "🏝️ Phuket", "🌴 Koh Samui", "⛵ Krabi"]
    else:
        return ["🏙️ 방콕", "🏖️ 파타야", "🐘 치앙마이", "🏝️ 푸켓", "🌴 코사무이", "⛵ 끄라비"]

def get_region_label_to_key():
    lang = st.session_state.get('language', 'Korean')
    if lang == 'English':
        return {
            "🏙️ Bangkok": "방콕",
            "🏖️ Pattaya": "파타야",
            "🐘 Chiang Mai": "치앙마이",
            "🏝️ Phuket": "푸켓",
            "🌴 Koh Samui": "코사무이",
            "⛵ Krabi": "끄라비"
        }
    else:
        return {
            "🏙️ 방콕": "방콕",
            "🏖️ 파타야": "파타야",
            "🐘 치앙마이": "치앙마이",
            "🏝️ 푸켓": "푸켓",
            "🌴 코사무이": "코사무이",
            "⛵ 끄라비": "끄라비"
        }

# Klook 전체보기 링크
KLOOK_ALL_TOURS_LINK = "https://klook.tpx.li/P3FlPqvh"

def generate_tour_itinerary(tours, region="방콕", duration="당일치기 (Day Trip)"):
    """
    Generate a multi-day itinerary using the selected tours and specified duration.
    Args:
        tours: List of tour dictionaries (id, name, type, etc.)
        region: City name
        duration: Selected trip duration string
    Returns:
        str: Markdown formatted itinerary
    """
    import google.generativeai as genai
    
    # Get API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import toml
            secrets = toml.load(".streamlit/secrets.toml")
            api_key = secrets.get("GEMINI_API_KEY")
        except:
            pass
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except:
            pass
            
    if not api_key:
        return "❌ API Key Missing"

    try:
        max_days = parse_trip_duration(duration)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Determine Current Season in Thailand
        current_month = datetime.now().month
        # Typical Thailand: Rainy (Jun-Oct), Dry/Cool (Nov-May)
        is_rainy_season = 6 <= current_month <= 10
        season_str = "우기(비가 자주 옴)" if is_rainy_season else "건기(여행하기 좋음)"

        # Format tour list for prompt
        tour_list_str = "\n".join([f"- {t['name']} (태그: {', '.join(t.get('type', [])) if isinstance(t.get('type'), list) else t.get('type', '일반')}, 설명: {t.get('desc', '')})" for t in tours])
        
        prompt = f"""
        당신은 태국 {region} 여행 전문가입니다. 
        현재는 **{current_month}월({season_str})**입니다. 
        사용자가 장바구니에 담은 아래 투어 상품들을 조합하여 가장 현실적이고 여유로운 **'최적의 여행 일정표'**를 작성해주세요.
        
        [선택한 투어 목록]
        {tour_list_str}
        
        [여행 기간]
        사용자의 여행 기간은 **{duration}** (최대 **{max_days}일**) 입니다.
        
        [CRITICAL RULE]
        1. **Hard Limit (절대 준수)**: 일정은 반드시 **{max_days}일**을 초과해서는 안 됩니다. (예: 2박 3일이면 Day 3에서 반드시 종료)
        2. **우선순위 배치**: 만약 선택한 상품들이 {max_days}일 안에 모두 소화하기 너무 많다면, 물리적 거리와 테마가 가까운 순서대로 주요 일정에 배치하고 나머지는 과감히 생략하세요.
        3. **제외 항목 표시**: {max_days}일 안에 배치하지 못한 남은 상품들은 일정표 맨 마지막에 **"⚠️ 시간 부족으로 제외된 곳 (Skipped)"** 섹션을 만들어 리스트업하고, 왜 제외되었는지 짧게(예: 동선 멀음, 시간 부족 등) 이유를 적어주세요.

        [필수 고려사항]
        1. **일정 배치 및 기간 최적화**:
           - 선택한 투어 상품들을 사용자의 여행 기간(**{duration}**)에 맞춰서 무리하지 않게 적절히 분배해서 배치해주세요.
           - 절대 추가적인 날짜(Day {max_days + 1} 등)를 생성하지 마세요.
           - 상품 태그에 **'전일투어'**, **'종일'**이 있거나, 혹은 태그가 없더라도 **아유타야(Ayutthaya), 칸차나부리(Kanchanaburi), 카오야이(Khao Yai) 등 외곽 지역 투어**와 같이 일반적으로 하루가 꼬박 소요되는 '널리 알려진 투어 상품'인 경우, 하루 전체(8~10시간)를 소요하는 것으로 간주하여 그날은 다른 큰 일정을 잡지 마세요.
           - **'반일투어'** 태그가 있거나 시내 사원 투어, 쿠킹 클래스 등 일반적으로 4시간 내외인 상품은 오전 또는 오후 중 하나에 배치하고, 남는 시간에는 가벼운 자유 일정이나 다른 짧은 코스를 결합하세요.
        2. **계절 및 날씨 (중요)**: 
           - 현재가 **우기**인 경우, 상품 태그에 '실내'가 포함된 상품을 우선적으로 배치하거나 비가 내릴 때를 대비한 플랜B를 제안하세요.
           - **건기**인 경우, 야외 활동과 풍경 감상을 최대한 즐길 수 있도록 배치하세요.
        3. **교통 체증 및 이동 시간**: {region}의 교통 체증(트래픽 잼)을 고려하여 일정 사이의 이동 시간을 매우 넉넉하게(최소 1~1.5시간 이상) 배치하세요.
        4. **체력 및 피로도**: 여행자의 체력을 고려하여 하루에 너무 많은 투어를 몰아넣지 마세요. '느긋하고 여유로운 여행(Slow Travel)'이 되도록 배치하세요.
        5. **식사 및 휴식**: 매일 적절한 점심, 저녁 식사 시간과 중간 휴식 시간을 반드시 포함하세요.
        
        [출력 형식]
        - 날짜별로 구분하여 출력하세요 (예: Day 1, Day 2...).
        - 깔끔한 마크다운(Markdown) 리스트 또는 표 형식을 사용하세요.
        - 전문적인 팁(복장, 준비물, 맛집 등)을 날씨에 맞게 한 줄씩 추가하세요.
        - 서론과 결론은 생략하고 바로 일정표 내용만 출력하세요. 친근한 말투(해요체)를 사용하세요.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ 일정 생성 중 오류 발생: {str(e)}"


