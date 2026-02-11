import streamlit as st
import json
import os
import pytz
import utils
from datetime import datetime, timedelta
import plotly.express as px
from collections import Counter
import hashlib
import html
import pandas as pd
import time
from streamlit_gsheets import GSheetsConnection
import certifi
import ssl
import warnings
import base64

# --------------------------------------------------------------------------------
# 1. [Fix] Suppress Deprecation & Future Warnings (Log Cleanup)
# --------------------------------------------------------------------------------
# Suppress google.generativeai warning (FutureWarning)
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
# Suppress Streamlit Warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="streamlit")
# --------------------------------------------------------------------------------
from db_utils import load_news_from_sheet, save_news_to_sheet, load_recent_news, load_news_by_date, load_local_news_cache, get_news_for_date

# Fix SSL Certificate Issue on Mac
os.environ["SSL_CERT_FILE"] = certifi.where()

# [보안 패치] 브라우저에게 모든 HTTP 요청을 HTTPS로 강제 업그레이드하도록 명령
st.markdown(
    """
    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------------------------------------
# Travelpayouts 인증 및 Emerald 스크립트
# --------------------------------------------------------------------------------
import streamlit.components.v1 as components

TP_VERIFICATION_CODE = """
<script data-noptimize="1" data-cfasync="false" data-wpfc-render="false">
  (function () {
      var script = document.createElement("script");
      script.async = 1;
      script.src = 'https://emrldtp.cc/NDk0NDE0.js?t=494414';
      document.head.appendChild(script);
  })();
</script>
"""
# HTML 컴포넌트로 주입 (화면에 안 보이게 처리)
components.html(TP_VERIFICATION_CODE, height=0)



# --- Configuration ---
NEWS_FILE = 'data/news.json'
EVENTS_FILE = 'data/events.json'
BIG_EVENTS_FILE = 'data/big_events.json'
TRENDS_FILE = 'data/trends.json'
CONFIG_FILE = 'data/config.json'
COMMENTS_FILE = 'data/comments.json'
BOARD_FILE = 'data/board.json'

DEPLOY_URL = "https://thai-today.com"

# --- Language Initialization (Detect Browser Language) ---
if "language" not in st.session_state:
    # Auto-detect browser language on first visit
    # Returns 'Korean' for Korean browsers, 'English' for all others (international/reviewers)
    st.session_state["language"] = utils.detect_browser_language()

# --- SEO-optimized Default Page Title ---
default_page_title = "Thailand Travel Fact Check - Thai Today" if st.session_state.get('language') == 'English' else "태국 여행 팩트체크 - 오늘의 태국"

st.set_page_config(
    page_title=default_page_title,
    page_icon="🇹🇭",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': 'https://forms.gle/B9RTDGJcCR9MnJvv5',
        'About': f"### {utils.t('main_title')} \n {utils.t('about_desc')}"
    }
)

# --- API Keys Configuration (Robust & Centralized) ---
# 1. Google Maps API Key
# Priority: Env -> secrets["google_maps_api_key"] -> secrets["GOOGLE_MAPS_API_KEY"] -> secrets["googlemaps_api"] (Legacy)
google_maps_key = (
    os.environ.get("GOOGLE_MAPS_API_KEY") 
    or st.secrets.get("google_maps_api_key") 
    or st.secrets.get("GOOGLE_MAPS_API_KEY")
    or st.secrets.get("googlemaps_api")
)

# 2. Gemini API Key
# Priority: Env -> secrets["gemini_api_key"] -> secrets["GEMINI_API_KEY"]
gemini_key = (
    os.environ.get("GEMINI_API_KEY") 
    or st.secrets.get("gemini_api_key") 
    or st.secrets.get("GEMINI_API_KEY")
)

# --- Agoda Partner Verification ---
st.markdown('<meta name="agd-partner-manual-verification" />', unsafe_allow_html=True)

# --- SEO: Inject Meta Description ---
if st.session_state.get('language') == 'English':
    utils.inject_meta_description("Real-time fact checks on Bangkok hotels and restaurants. Avoid tourist traps and find hidden gems.")
else:
    utils.inject_meta_description("방콕 호텔 & 맛집 팩트체크. 실시간 후기 분석으로 맛집 검증!")

# 🚫 배포 환경 완벽 대응 UI 숨김 (Terminator Style)
hide_streamlit_style = """
<style>
    /* 1. 기본 헤더 및 햄버거 메뉴 숨기기 */
    #MainMenu {visibility: hidden !important; display: none !important;}
    header {visibility: hidden !important; display: none !important;}
    [data-testid="stHeader"] {visibility: hidden !important; display: none !important;}
    
    /* 2. 푸터(Made with Streamlit) 및 하단 여백 제거 */
    footer {visibility: hidden !important; display: none !important; height: 0px !important; pointer-events: none !important; z-index: -1 !important;}
    [data-testid="stFooter"] {visibility: hidden !important; display: none !important; height: 0px !important; pointer-events: none !important; z-index: -1 !important;}
    
    /* 3. 붉은색 장식 줄 및 툴바 제거 */
    [data-testid="stDecoration"] {visibility: hidden !important; display: none !important;}
    [data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
    
    /* 4. (중요) Streamlit Cloud 전용 요소 숨기기 */
    .stDeployButton {display: none !important;}
    [data-testid="stStatusWidget"] {visibility: hidden !important;}

    /* 2. 푸터 완벽 제거 (유령화) */
    footer, [data-testid="stFooter"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        pointer-events: none !important; /* 중요: 클릭 투과 */
        z-index: -1 !important;
    }
    
    /* 5. 콘텐츠 영역 여백 확보 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 80px !important; /* 탭 높이만큼 여백 확보 */
    }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- Custom CSS ---
st.markdown("""
    <style>
    /* --- 1. Global Font & Typography Settings --- */
    html, body, [class*="css"]:not([data-testid="stIcon"]):not([class*="st-"]):not(.material-icons) {
        font-family: "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
        word-break: keep-all !important; /* Prevent mid-word breaks */
        overflow-wrap: break-word;
    }

    /* --- 2. Mobile Optimization (max-width: 768px) --- */
    @media (max-width: 768px) {
        /* Typography Scaling */
        h1, .stHeading h1 { font-size: 1.7rem !important; }
        h2, .stHeading h2 { font-size: 1.4rem !important; }
        h3, .stHeading h3 { font-size: 1.1rem !important; }
        
        p, div, li {
            font-size: 1rem !important;
            line-height: 1.6 !important;
        }
        
        /* Metric Styling */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }

        /* Dark Mode Toggle: Right Align on Mobile */
        .stToggle {
            justify-content: flex-end !important;
        }
    }

    /* --- 3. Navigation & UI Fixes --- */
    /* Hide Streamlit Anchor Links */
    [data-testid="stHeaderAction"] { display: none !important; }
    
    /* Hide top pills on mobile */
    @media (max-width: 768px) {
        .st-key-nav_top { display: none !important; }
    }

    /* Hide mobile bottom buttons on PC */
    @media (min-width: 769px) {
        div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) {
            display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important;
        }
    }

    /* Fix buttons to TOP on Mobile */
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            background-color: white !important;
            z-index: 99999 !important;
            padding: 5px !important;
            padding-top: env(safe-area-inset-top) !important;
            border-bottom: 1px solid #e0e0e0 !important;
            margin: 0 !important;
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important; /* Allow 2 rows */
            align-items: center !important;
            justify-content: space-around !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) > div {
            flex: 1 1 0% !important;
            min-width: 0 !important;
            max-width: none !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #666 !important;
            font-size: 0.85rem !important;
            font-weight: 800 !important;
            padding: 5px !important;
            width: 100% !important;
            display: block !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) button:active,
        div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) button:focus {
            color: #FF4B4B !important;
        }

        /* Pad content TOP to avoid hiding behind nav (Increased for 2 rows) */
        .main .block-container {
            padding-top: 110px !important; 
            padding-bottom: 50px !important;
        }
        .stApp {
            padding-top: 110px !important;
        }
        
        /* Pagination Row Fixes */
        div[data-testid="stVerticalBlock"]:has(.pagination-container) div[data-testid="stHorizontalBlock"] {
            display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important;
            align-items: center !important; justify-content: space-between !important; gap: 5px !important;
        }
        div[data-testid="stVerticalBlock"]:has(.pagination-container) div[data-testid="stHorizontalBlock"] > div {
            min-width: 0 !important; flex: 1 1 0% !important;
        }
        div[data-testid="stVerticalBlock"]:has(.pagination-container) div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
            flex: 0.8 1 0% !important;
        }
        div[data-testid="stVerticalBlock"]:has(.pagination-container) button {
            padding: 2px 5px !important; font-size: 0.75rem !important; min-height: 2.2rem !important; white-space: nowrap !important;
        }
        .pagination-info {
            font-size: 0.85rem !important; padding-top: 5px !important;
        }
    }

    /* Dark Mode Support for Fixed Nav & General Elements */
    [data-testid="stAppViewContainer"]:has(input[aria-checked="true"]) div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) {
        background: #0E1117 !important; /* Streamlit Dark BG */
        border-bottom: 1px solid #333 !important;
    }
    
    /* GLOBAL DARK MODE OVERRIDES (Affecting Portals/Popovers/All Buttons) */
    /* Target BODY based on the specific Dark Mode toggle availability */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) {
        /* This selector is powerful but body styling might be restricted */
    }

    /* 1. Fix Hotel Region Selectbox (Portal/Popover) */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="popover"],
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="menu"],
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) ul[role="listbox"] {
        background-color: #262730 !important;
        color: white !important;
        border: 1px solid #444 !important;
    }
    
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) li[role="option"] {
        background-color: #262730 !important;
        color: white !important;
    }
    
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) li[role="option"][aria-selected="true"] {
        background-color: #FF4B4B !important;
        color: white !important;
    }

    /* 2. Fix All Buttons (Pagination, Inquiry, etc) in Dark Mode */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button {
        background-color: #262730 !important;
        color: white !important; 
        border: 1px solid #444 !important;
    }
    
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button:hover {
        border-color: #FF4B4B !important;
        color: #FF4B4B !important;
    }
    
    /* 3. Pagination Specifics (Streamlit Secondary Buttons) */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button[kind="secondary"] {
        background-color: transparent !important;
    }
    
    /* Active Pagination Button (Disabled state) */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button[disabled],
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button[disabled]:hover {
        background-color: #FF4B4B !important;
        color: white !important;
        border-color: #FF4B4B !important;
        opacity: 1 !important;
    }

    /* 4. Fix Input/Textarea Text Color */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) input,
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) textarea {
        color: white !important;
        background-color: #262730 !important;
    }
    /* Selectbox Main Display */
    body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="select"] > div {
        background-color: #262730 !important;
        color: white !important;
        border-color: #444 !important;
    }

    /* 5. Mobile Nav Button Text */
    [data-testid="stAppViewContainer"]:has(input[aria-checked="true"]) div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) button {
        color: #FAFAFA !important;
        background-color: transparent !important; /* Force transparent for nav buttons */
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Thai-Today.com Custom CSS Injection ---
# Load external style.css with Playfair Display, Kanit fonts, Glassmorphism, Royal Gold theme
utils.load_custom_css()

# --- Helper Functions (Load/Save) ---
# Separate cache for heavy news data
# [OPTIMIZED] Hybrid approach: Local cache first (instant), GSheets fallback
@st.cache_data(ttl=300)  # 5 min outer cache
def load_news_data():
    """
    Hybrid news loader for fast initial load:
    1. Try local JSON cache first (< 0.5s)
    2. Check if local data is fresh enough (contains today's or yesterday's news)
    3. Fall back to GSheets if local is empty or too old (8-10s)
    """
    # 1. Try local cache first
    local_data = load_local_news_cache(days=7)
    
    # 2. Check freshness
    is_fresh = False
    if local_data:
        import pytz
        now_bkk = datetime.now(pytz.timezone('Asia/Bangkok'))
        today_str = now_bkk.strftime("%Y-%m-%d")
        yesterday_str = (now_bkk - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # If local has today's or yesterday's news, it's "fresh enough" for fast load
        if today_str in local_data or yesterday_str in local_data:
            is_fresh = True
            
        # Also check file modification time as escape hatch
        if not is_fresh:
            try:
                mtime = os.path.getmtime(LOCAL_NEWS_CACHE)
                # If updated within last 6 hours, don't force GSheets (prevent API flood)
                if (datetime.now().timestamp() - mtime) < 21600:
                    is_fresh = True
            except: pass

    if local_data and is_fresh:
        return local_data
    
    # Fallback to GSheets (slower but always up-to-date)
    return load_recent_news(days=7)

# --- Cached Wrappers for API Calls ---
@st.cache_data(ttl=1800) # Cache for 30 mins
def get_cached_air_quality(token):
    return utils.get_air_quality(token)

@st.cache_data(ttl=1800) # Cache for 30 mins
def get_cached_exchange_rate():
    return utils.get_thb_krw_rate()

@st.cache_data(ttl=1800) # Cache for 30 mins
def get_cached_usd_exchange_rate():
    return utils.get_usd_thb_rate()

@st.cache_data(ttl=3600, show_spinner=False)
def load_events_data(mtime):
    """Loads events from JSON file."""
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

@st.cache_data(ttl=1800, show_spinner=False)
def load_trends_data(mtime):
    """Loads trends from JSON file."""
    if os.path.exists(TRENDS_FILE):
        with open(TRENDS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def update_trends_if_stale():
    """Checks if trends.json is stale (>24h) and updates it if needed."""
    is_stale = True
    if os.path.exists(TRENDS_FILE):
        mtime = os.path.getmtime(TRENDS_FILE)
        if time.time() - mtime < 86400: # 24 hours
            is_stale = False
            
    if is_stale:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
             try:
                import toml
                secrets = toml.load(".streamlit/secrets.toml")
                api_key = secrets.get("GEMINI_API_KEY")
             except: pass
             
        if api_key:
            new_items = utils.fetch_trend_hunter_items(api_key)
            if new_items:
                save_json(TRENDS_FILE, new_items)
                return len(new_items)
    return 0

def update_events_if_stale():
    """Checks if events.json is stale (>24h) and updates it if needed."""
    is_stale = True
    if os.path.exists(EVENTS_FILE):
        mtime = os.path.getmtime(EVENTS_FILE)
        if time.time() - mtime < 86400: # 24 hours
            is_stale = False
            
    if is_stale:
        new_events = utils.fetch_thai_events()
        if new_events:
            # Load existing
            if os.path.exists(EVENTS_FILE):
                with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                    try:
                        existing_events = json.load(f)
                    except:
                        existing_events = []
            else:
                existing_events = []
            
            # Merge Logic (Dedupe by Title + Date)
            existing_sigs = set((e.get('title'), e.get('date')) for e in existing_events)
            
            added_count = 0
            for event in new_events:
                sig = (event.get('title'), event.get('date'))
                if sig not in existing_sigs:
                    existing_events.append(event)
                    existing_sigs.add(sig)
                    added_count += 1
            
            # Save
            with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_events, f, ensure_ascii=False, indent=2)
                
            return added_count
    return 0

def is_event_active(date_str):
    """
    Checks if an event is active based on its date string.
    Returns True if:
    1. Date string is valid and >= Today.
    2. Date string contains a range, and end date >= Today.
    3. Date string is ambiguous but not clearly in the past.
    Returns False if event is definitely in the past or too old (e.g., < 2024).
    """
    if not date_str:
        return True # Keep if no date

    try:
        today = datetime.now().date()
        current_year = today.year
        
        # Quick Check for obviously old years in string
        # If "2017", "2018" etc found, reject immediately
        for old_year in range(2015, current_year):
            if str(old_year) in date_str:
                return False

        # Clean string
        
        # Clean string
        clean_date = date_str.replace('.', '-').strip()
        
        # Case A: Range "2024-01-01 ~ 2024-02-01"
        if '~' in clean_date:
            parts = clean_date.split('~')
            end_part = parts[1].strip()
            if not end_part: 
                start_part = parts[0].strip()
                # "2024-01-01 ~" -> Check start date? No, it implies ongoing.
                # Just check if start is not ancient? For now, assume active.
                return True
                
            try:
                # Try parsing end date
                end_dt = datetime.strptime(end_part, "%Y-%m-%d").date()
                return end_dt >= today
            except:
                pass # Parse fail, default True

        # Case B: Single Date "2024-01-01"
        try:
            dt = datetime.strptime(clean_date, "%Y-%m-%d").date()
            return dt >= today
        except:
             pass

    except:
        pass
        
    # Default to True if we differ parsing, to avoid hiding valid events with weird formats
    return True

def get_cached_events():
    """Wrapper that ensures file exists/is filtered, then loads."""
    update_events_if_stale()
    mtime = 0
    if os.path.exists(EVENTS_FILE):
        mtime = os.path.getmtime(EVENTS_FILE)
    
    events = load_events_data(mtime)
    
    # Python-side Filtering: Remove expired events
    valid_events = [e for e in events if is_event_active(e.get('date'))]
    
    return valid_events

def load_json(file_path, default=None):
    if default is None:
        default = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return default
    return default

def highlight_text(text):
    """Highlight keywords using Streamlit markdown syntax (for st.markdown)"""
    # 1. 위험 (Red) - 가장 강력한 경고
    red_keywords = ["사망", "살인", "체포", "총기", "마약", "야바", "폭발", "화재", "강도", "성범죄", "테러"]
    for word in red_keywords:
        text = text.replace(word, f":red[**{word}**]")
        
    # 2. 주의/경고 (Orange) - 비자, 법규, 벌금
    orange_keywords = ["추방", "블랙리스트", "입국거부", "단속", "벌금", "전자담배", "불법", "비자", "경고"]
    for word in orange_keywords:
        text = text.replace(word, f":orange[**{word}**]")
        
    # 3. 경제/정보 (Blue) - 돈, 수치 변화
    blue_keywords = ["인상", "하락", "폭등", "폭락", "환율", "사기", "바가지"]
    for word in blue_keywords:
        text = text.replace(word, f":blue[**{word}**]")

    # 4. 배경지식 (Green/Grey) - 환경, 질병
    green_keywords = ["홍수", "침수", "뎅기열", "주류 판매 금지", "시위"]
    for word in green_keywords:
        text = text.replace(word, f":green[**{word}**]")
        
    return text

def highlight_text_html(text):
    """Highlight keywords using HTML spans (for raw HTML rendering in news cards)"""
    # 1. 위험 (Red)
    red_keywords = ["사망", "살인", "체포", "총기", "마약", "야바", "폭발", "화재", "강도", "성범죄", "테러"]
    for word in red_keywords:
        text = text.replace(word, f"<span style='color:#FF4444;font-weight:bold;'>{word}</span>")
        
    # 2. 주의/경고 (Orange)
    orange_keywords = ["추방", "블랙리스트", "입국거부", "단속", "벌금", "전자담배", "불법", "비자", "경고"]
    for word in orange_keywords:
        text = text.replace(word, f"<span style='color:#FF8C00;font-weight:bold;'>{word}</span>")
        
    # 3. 경제/정보 (Blue)
    blue_keywords = ["인상", "하락", "폭등", "폭락", "환율", "사기", "바가지"]
    for word in blue_keywords:
        text = text.replace(word, f"<span style='color:#1E90FF;font-weight:bold;'>{word}</span>")

    # 4. 배경지식 (Green)
    green_keywords = ["홍수", "침수", "뎅기열", "주류 판매 금지", "시위"]
    for word in green_keywords:
        text = text.replace(word, f"<span style='color:#32CD32;font-weight:bold;'>{word}</span>")
        
    return text

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Visitor Counter (Session + API) ---
if 'visited_session' not in st.session_state:
    # First visit in this session -> Increment (Total + Daily)
    total_val, daily_val = utils.increment_visitor_stats()
    st.session_state['visited_session'] = True
else:
    # Already visited -> Just Read (Total + Daily)
    total_val, daily_val = utils.get_visitor_stats()

# PC UI (Sidebar Bottom) - Language selector moved to main header popover
with st.sidebar:
    st.markdown("---")
    # Language selector removed - now in main header popover
    
    st.markdown(f"""
    <div style="text-align: center; color: #666; font-size: 0.8em;">
        👀 {utils.t('stat_today')}: <b>{daily_val:,}</b> | {utils.t('stat_total')}: <b>{total_val:,}</b>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"### {utils.t('sidebar_info')}")
    st.markdown(f"🔗 [고객 지원 (Get Help)](https://forms.gle/B9RTDGJcCR9MnJvv5)")
    with st.expander(utils.t('about_title')):
        st.markdown(f"""
        **{utils.t('main_title')}**
        {utils.t('about_desc')}
        """)

# --- Comment System Helpers ---
def generate_news_id(title, summary=""):
    """Generate MD5 hash from title and partial summary to ensure uniqueness."""
    combined = f"{title}_{summary[:50]}"
    return hashlib.md5(combined.encode()).hexdigest()

def get_all_comments():
    """Load the entire comments database."""
    # Ensure file exists
    if not os.path.exists(COMMENTS_FILE):
        initial_data = {"blocked_users": []}
        save_json(COMMENTS_FILE, initial_data)
        return initial_data
    return load_json(COMMENTS_FILE, default={"blocked_users": []})

def save_comment(news_id, nickname, text):
    """Save a new comment to the JSON file with a spinner delay."""
    with st.spinner("댓글 저장 중..."):
        time.sleep(1.5) # Simulate network delay/give feedback
        data = get_all_comments()
        
        # Structure: {"news_id_hash": [List of comments], "blocked_users": []}
        if news_id not in data:
            data[news_id] = []
            
        new_comment = {
            "user": nickname if nickname else "익명",
            "text": text,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        data[news_id].append(new_comment)
        save_json(COMMENTS_FILE, data)

# --------------------------------------------------------------------------------
# ### KLOOK AFFILIATE BANNER ###
# --------------------------------------------------------------------------------

def render_klook_banner():
    """Render Klook affiliate banner with responsive HTML wrapper."""
    is_english = st.session_state.get('language') == 'English'
    
    # --- 1. Load and Base64 encode the local banner image ---
    banner_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "klook_banner.png")
    img_base64 = ""
    if os.path.exists(banner_img_path):
        with open(banner_img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode()
    
    # Text Localization
    title_text = "Thailand Travel Essentials" if is_english else "✈️ 태국 여행 필수 준비물"
    sim_title = "Thailand SIM/eSIM" if is_english else "태국 유심/eSIM"
    sim_desc = "Airport Pickup · Unlimited Data" if is_english else "공항 수령 · 데이터 무제한"
    taxi_title = "Airport Transfer" if is_english else "공항 픽업 예약"
    taxi_desc = "No Haggling · Comfortable Ride" if is_english else "흥정 없이 · 편안하게 이동"

    # --- 2. Render everything in a single responsive HTML block ---
    st.markdown(
        f"""
<div style="max-width: 500px; margin: 15px auto; width: 95%;">
    <a href="https://klook.tpx.li/KWvlLrap" target="_blank" style="text-decoration: none;">
        <img src="data:image/png;base64,{img_base64}" style="width: 100%; border-radius: 12px 12px 0 0; display: block;">
    </a>
    <div style="border-radius: 0 0 12px 12px; margin-top: -1px; box-shadow: 0 4px 12px rgba(255, 87, 34, 0.12); overflow: hidden; border: 1px solid #ffe0d0; background: #fff8f5; padding: 10px 12px 12px 12px;">
        <p style="color: #FF5722; font-size: 13px; margin: 0 0 8px 0; font-weight: 700; text-align: center; letter-spacing: -0.3px;">{title_text}</p>
        <div style="display: flex; gap: 8px;">
            <a href="https://klook.tpx.li/KWvlLrap" target="_blank" style="flex: 1; text-decoration: none; background: #fff; padding: 10px 6px; border-radius: 10px; text-align: center; border: 1px solid #ffe0d0; box-shadow: 0 1px 4px rgba(255,87,34,0.06);">
                <div style="font-size: 20px; margin-bottom: 4px;">📶</div>
                <div style="color: #FF5722; font-weight: 700; font-size: 12px; margin-bottom: 2px;">{sim_title}</div>
                <div style="color: #999; font-size: 10px; line-height: 1.2;">{sim_desc}</div>
            </a>
            <a href="https://klook.tpx.li/LBnlb1vU" target="_blank" style="flex: 1; text-decoration: none; background: #fff; padding: 10px 6px; border-radius: 10px; text-align: center; border: 1px solid #d4edda; box-shadow: 0 1px 4px rgba(76,175,80,0.06);">
                <div style="font-size: 20px; margin-bottom: 4px;">🚖</div>
                <div style="color: #4CAF50; font-weight: 700; font-size: 12px; margin-bottom: 2px;">{taxi_title}</div>
                <div style="color: #999; font-size: 10px; line-height: 1.2;">{taxi_desc}</div>
            </a>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True
    )

def render_dinner_cruise_banner():
    """Render Dinner Cruise & Food promotion banner with responsive HTML wrapper."""
    is_english = st.session_state.get('language') == 'English'
    
    # Text Localization
    title_main = "Looking for a special restaurant?" if is_english else "특별한 맛집을 찾으시나요?"
    subtitle = (
        "How about a <span style='color: #FFD700; font-weight: 700;'>Chao Phraya Dinner Cruise</span><br>with a stunning view of Bangkok?"
        if is_english else 
        "방콕 야경을 보며 즐기는<br><span style='color: #FFD700; font-weight: 700;'>짜오프라야 디너 크루즈</span>는 어떠신가요?"
    )
    book_btn = "🎫 Book Now" if is_english else "🎫 예약하기"
    
    card1_title = "Princess Cruise" if is_english else "프린세스 크루즈"
    card1_desc = "Buffet + Live Show" if is_english else "뷔페 + 라이브 공연"
    
    card2_title = "Bus Food Tour" if is_english else "버스 푸드 투어"
    card2_desc = "Gourmet on Wheels" if is_english else "버스타고 맛있는 음식을"
    
    card3_title = "Michelin Tour" if is_english else "미슐랭 투어"
    card3_desc = "Local Foodie Course" if is_english else "현지인 맛집 코스"

    st.markdown(
        f"""
        <div style="
            max-width: 500px;
            margin: 16px auto;
            width: 95%;
            border-radius: 14px;
            overflow: hidden;
            background: linear-gradient(135deg, #0c1445 0%, #1a237e 40%, #283593 100%);
            box-shadow: 0 4px 20px rgba(26, 35, 126, 0.3);
            border: 1px solid rgba(255, 215, 0, 0.2);
        ">
            <a href="https://klook.tpx.li/woQxAZ2X" target="_blank" style="text-decoration: none; display: block;">
                <div style="padding: 15px 15px 10px 15px; text-align: center;">
                    <div style="font-size: 28px; margin-bottom: 4px;">🚢✨🌃</div>
                    <div style="color: #FFD700; font-size: 16px; font-weight: 800; margin-bottom: 4px; letter-spacing: -0.5px;">
                        {title_main}
                    </div>
                    <div style="color: #E8EAF6; font-size: 12px; line-height: 1.5; margin-bottom: 10px;">
                        {subtitle}
                    </div>
                    <div style="
                        display: inline-block;
                        background: linear-gradient(135deg, #FFD700, #FFA000);
                        color: #1a237e;
                        padding: 8px 20px;
                        border-radius: 20px;
                        font-weight: 800;
                        font-size: 13px;
                        box-shadow: 0 2px 8px rgba(255, 215, 0, 0.4);
                    ">{book_btn}</div>
                </div>
            </a>
            <div style="display: flex; gap: 0; border-top: 1px solid rgba(255,255,255,0.1);">
                <a href="https://klook.tpx.li/woQxAZ2X" target="_blank" style="
                    flex: 1; text-decoration: none; padding: 10px 6px; text-align: center;
                    border-right: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-size: 16px; margin-bottom: 2px;">👑</div>
                    <div style="color: #FFD700; font-weight: 700; font-size: 11px;">{card1_title}</div>
                    <div style="color: #9FA8DA; font-size: 9px;">{card1_desc}</div>
                </a>
                <a href="https://klook.tpx.li/s0LqwqWT" target="_blank" style="
                    flex: 1; text-decoration: none; padding: 10px 6px; text-align: center;
                    border-right: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-size: 16px; margin-bottom: 2px;">🚌</div>
                    <div style="color: #FFD700; font-weight: 700; font-size: 11px;">{card2_title}</div>
                    <div style="color: #9FA8DA; font-size: 9px;">{card2_desc}</div>
                </a>
                <a href="https://klook.tpx.li/avHTRYf9" target="_blank" style="
                    flex: 1; text-decoration: none; padding: 10px 6px; text-align: center;">
                    <div style="font-size: 16px; margin-bottom: 2px;">⭐</div>
                    <div style="color: #FFD700; font-weight: 700; font-size: 11px;">{card3_title}</div>
                    <div style="color: #9FA8DA; font-size: 9px;">{card3_desc}</div>
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --------------------------------------------------------------------------------
# ### TAB RENDER FUNCTIONS ###
# --------------------------------------------------------------------------------

def render_tab_news():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_news"))
    # 🚩 앵커(깃발) 설치 - 스크롤 타겟
    st.markdown('<div id="news-top-anchor"></div>', unsafe_allow_html=True)
    
    # Klook 제휴 배너
    render_klook_banner()
    
    # --- Twitter Trend Alert (Real-time) ---
    twitter_file = 'data/twitter_trends.json'
    if os.path.exists(twitter_file):
        t_data = load_json(twitter_file)
        if t_data and t_data.get('reason'):
            severity = t_data.get('severity', 'info')
            icon = "🚨" if severity == 'warning' else "📢"
            issue_prefix = utils.t("issue_label")
            msg = f"{issue_prefix} {t_data.get('reason')} (#{t_data.get('topic')})"
            
            # Add Timestamp
            ts = t_data.get('collected_at', '')
            if ts:
                msg += f" _(" + utils.t("as_of").format(ts) + ")_"
            
            # Stale Check: Only show if collected TODAY (Bangkok Time)
            bkk_tz = pytz.timezone('Asia/Bangkok')
            today_str = datetime.now(bkk_tz).strftime("%Y-%m-%d")
            
            # collected_at format: YYYY-MM-DD HH:MM:SS or HH:MM (old)
            is_stale = False
            ts = t_data.get('collected_at', '')
            
            if ts:
                if len(ts) > 5: # Full datetime
                    if not ts.startswith(today_str):
                        is_stale = True
                else: # HH:MM only (Assume old data if not full format, or check file mod time? simpler to just hide old format)
                    # Actually, if we just deployed strict format, old data might be HH:MM.
                    # Let's hide if it doesn't look like today's full date for safety.
                    is_stale = True
            else:
                is_stale = True
            
            if not is_stale:
                if severity == 'warning':
                     st.error(f"{icon} {msg}") 
                else:
                     st.info(f"{icon} {msg}")

    # --- Language-based News Branching ---
    is_english_mode = st.session_state.get('language') == 'English'
    
    if is_english_mode:
        # ========== ENGLISH NEWS MODE (RSS Feeds) ==========
        st.markdown("### 📰 Thailand Headlines")
        st.caption("Latest news from Bangkok Post, The Thaiger, Khaosod, and Nation Thailand")
        
        with st.spinner("Loading latest English news..."):
            english_news = utils.fetch_combined_english_news(max_articles=12)
        
        if not english_news:
            st.warning("Unable to fetch English news at the moment. Please try again later.")
        else:
            # Display news in 2-column grid
            for i in range(0, len(english_news), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx < len(english_news):
                        article = english_news[idx]
                        with col:
                            st.markdown(f"""
                            <div style="border: 1px solid #e0e0e0; border-radius: 12px; padding: 15px; margin-bottom: 15px; background: white;">
                                <img src="{article['image_url']}" style="width: 100%; height: 150px; object-fit: cover; border-radius: 8px; margin-bottom: 10px;" onerror="this.style.display='none'">
                                <h4 style="margin: 0 0 8px 0; font-size: 1rem; line-height: 1.3;">{article['title'][:80]}{'...' if len(article['title']) > 80 else ''}</h4>
                                <p style="color: #666; font-size: 0.85rem; margin: 0 0 10px 0; line-height: 1.4;">{article['summary'][:120]}{'...' if len(article['summary']) > 120 else ''}</p>
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-size: 0.75rem; color: #999;">📰 {article['source']}</span>
                                    <a href="{article['link']}" target="_blank" style="font-size: 0.8rem; color: #4A90D9; text-decoration: none;">Read more →</a>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
        
        # Add refresh button
        if st.button("🔄 Refresh News", use_container_width=True):
            utils.fetch_combined_english_news.clear()
            st.rerun()
        
        # Initialize placeholder variables to prevent errors from code outside else block
        filtered_topics_all = []
        topics_to_show = []
        is_search_mode = False
        total_pages = 1
        ITEMS_PER_PAGE = 10
        header_text = ""
        selected_date_str = ""
        news_data = {}
    
    else:
        # ========== KOREAN NEWS MODE (Existing Logic) ==========
        # --- Mobile Nav & Date Selection (Expander) ---

        # Data Loading (Moved up for init logic)
        news_data = load_news_data()

        # Calculate Valid Dates & Latest
        all_dates_str = sorted(news_data.keys())
        valid_dates = []
        # [OPTIMIZED] Use latest available date from cache as default to prevent slow GSheets fetch on startup
        if all_dates_str:
            latest_date_str = all_dates_str[-1]
        else:
            latest_date_str = datetime.now(pytz.timezone('Asia/Bangkok')).strftime("%Y-%m-%d")
        
        for d_str in all_dates_str:
            try:
                valid_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
            except: continue
        
        if not valid_dates:
             min_date = max_date = datetime.now(pytz.timezone('Asia/Bangkok')).date()
             st.error("데이터를 불러올 수 없습니다. (잠시 후 다시 시도해주세요)")
        else:
             # [LAZY LOADING] 과거 날짜 접근 허용을 위해 min_date 하드코딩 (프로젝트 시작일)
             min_date = datetime(2025, 1, 9).date()
             data_max = max(valid_dates)
             today_date = datetime.now(pytz.timezone('Asia/Bangkok')).date()
             max_date = max(today_date, data_max)
        
        # Init Session for Pagination & Search
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 1
        if "search_query" not in st.session_state:
            st.session_state["search_query"] = ""
        # Smart Date Init: Default to latest available date
        if "selected_date_str" not in st.session_state: 
            st.session_state["selected_date_str"] = latest_date_str

        # Expander for Controls
        with st.expander(utils.t("search_news"), expanded=False):
            col_nav1, col_nav2 = st.columns([1, 1])
        
            with col_nav1:
                # Date Picker
                # Convert stored string back to date object for widget
                try:
                    curr_date_obj = datetime.strptime(st.session_state["selected_date_str"], "%Y-%m-%d").date()
                except:
                    curr_date_obj = datetime.now(pytz.timezone('Asia/Bangkok')).date()
                
                # Double safety: clamp to valid range to prevent StreamlitAPIException
                curr_date_obj = max(min_date, min(max_date, curr_date_obj))

                new_date = st.date_input(
                    utils.t("search_date"), 
                    value=curr_date_obj, 
                    min_value=min_date, 
                    max_value=max_date
                )
        
            # Logic: If date changed, reset page to 1
            new_date_str = new_date.strftime("%Y-%m-%d")
            if new_date_str != st.session_state["selected_date_str"]:
                st.session_state["selected_date_str"] = new_date_str
                st.session_state["current_page"] = 1 # Reset page
                st.rerun()

        with col_nav2:
            # Search Box
            search_input = st.text_input(utils.t("search_keyword"), value=st.session_state["search_query"])
            if search_input != st.session_state["search_query"]:
                st.session_state["search_query"] = search_input
                st.session_state["current_page"] = 1 # Reset page
                st.rerun()

        if st.session_state["search_query"]:
            if st.button(utils.t("reset_search"), width='stretch'):
                st.session_state["search_query"] = ""
                st.session_state["current_page"] = 1
                st.rerun()

        # --- Topic Preparation Logic ---
        daily_topics = []
        header_text = ""
        is_search_mode = bool(st.session_state["search_query"])
        selected_date_str = st.session_state["selected_date_str"]

        if is_search_mode:
            # Search Mode: Scan ALL dates
            found_topics = []
            for d, topics in news_data.items():
                for t in topics:
                    if st.session_state["search_query"] in t['title'] or st.session_state["search_query"] in t['summary']:
                        t_with_date = t.copy()
                        t_with_date['date_str'] = d
                        found_topics.append(t_with_date)
            found_topics.sort(key=lambda x: x.get('date_str', ''), reverse=True)
            filtered_topics_all = found_topics
            header_text = f"🔍 '{st.session_state['search_query']}' " + ("Results" if st.session_state.get('language') == 'English' else "검색 결과") + f" ({len(found_topics)})"

        else:
            # Date Mode
            if selected_date_str in news_data:
                daily_topics = news_data[selected_date_str]
                # Show latest first
                filtered_topics_all = list(reversed(daily_topics))
            else:
                # [ON-DEMAND] Load older dates not in the 7-day cache
                with st.spinner("📅 이전 날짜 데이터 로딩 중..."):
                    older_items = get_news_for_date(selected_date_str)
                    if older_items:
                        filtered_topics_all = list(reversed(older_items))
                    else:
                        filtered_topics_all = []
            header_text = utils.t("news_header").format(selected_date_str)

        if not is_search_mode and filtered_topics_all:
            # Use standardized categories from utils
            cat_p = utils.t("cat_politics")
            cat_e = utils.t("cat_economy")
            cat_t = utils.t("cat_travel")
            cat_c = utils.t("cat_culture")
            all_l = utils.t("all")
            
            category_labels = [all_l, cat_p, cat_e, cat_t, cat_c]
            label_to_standard = {
                cat_p: "POLITICS",
                cat_e: "BUSINESS", 
                cat_t: "TRAVEL",
                cat_c: "LIFESTYLE"
            }
            try:
                cat_label_translated = utils.t("news_cat")
                selected_category = st.pills(cat_label_translated, category_labels, default=all_l, selection_mode="single")
                if not selected_category: selected_category = all_l
            except AttributeError:
                selected_category = st.radio(utils.t("news_cat"), category_labels, horizontal=True)
        
            if selected_category != utils.t("all"):
                standard_cat = label_to_standard.get(selected_category, "POLITICS")
                # Filter using normalized category comparison
                filtered_topics_all = [
                    t for t in filtered_topics_all 
                    if utils.normalize_category(t.get("category", "")) == standard_cat
                ]

        # --- Pagination Slicing ---
        ITEMS_PER_PAGE = 10
        total_items = len(filtered_topics_all)
        total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

        # Ensure current_page is valid
        if st.session_state["current_page"] > total_pages:
            st.session_state["current_page"] = total_pages
        if st.session_state["current_page"] < 1:
            st.session_state["current_page"] = 1
        
        start_idx = (st.session_state["current_page"] - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
    
        # Get current page items
        topics_to_show = filtered_topics_all[start_idx:end_idx]
    
        # --- 페이지 변경 시 스크롤 맨 위로 ---
        # 이전 페이지 번호와 현재 페이지 번호 비교
        if "last_rendered_page" not in st.session_state:
            st.session_state["last_rendered_page"] = 1
        
        if st.session_state["current_page"] != st.session_state["last_rendered_page"]:
            # 페이지 번호 + timestamp로 절대 중복되지 않는 고유값 생성
            import time
            unique_key = f"{st.session_state['current_page']}_{int(time.time() * 1000)}"
            utils.scroll_to_top(key_suffix=unique_key)
            st.session_state["last_rendered_page"] = st.session_state["current_page"]

        if topics_to_show:
             with st.expander(utils.t("share_page")):
                share_text = f"[🇹🇭 태국 뉴스룸 브리핑 - {header_text}]\n\n"
                for idx, item in enumerate(topics_to_show):
                    share_text += f"{idx+1}. {item['title']}\n"
                    
                    # Unified Robust URL Extraction
                    ref_url = item.get('link') or "#"
                    if ref_url == "#":
                         refs = item.get('references')
                         if isinstance(refs, list) and refs:
                             ref_url = refs[0].get('url', '#')
                         elif isinstance(refs, str) and (str(refs).startswith('http') or str(refs).startswith('www')):
                              ref_url = refs
                    
                    share_text += f"- {item['summary'][:60]}...\n👉 원문: {ref_url}\n\n"
                share_text += f"🌐 뉴스룸: {DEPLOY_URL}"
                st.code(share_text, language="text")

        # --- Main Content Render ---
        st.divider()
        utils.render_custom_header(header_text, level=2)
    
        # Empty State
        if not filtered_topics_all:
            if is_search_mode:
                 st.info(utils.t("no_news_results"))
            else:
                 st.info(utils.t("no_news_update"), icon="⏳")

        # Render Cards
        all_comments_data = get_all_comments() # Load once
    
        for idx, topic in enumerate(topics_to_show):
            # Glass Card Wrapper - Thai-Today.com Design
            cat_text = topic.get("category", utils.t("other"))
            date_display = topic.get('date_str', selected_date_str)
            time_display = topic.get('collected_at', '')
            meta_info = f"{date_display} {time_display}".strip()
            
            # Map category to tag variant
            cat_variants = {
                "여행/관광": "travel",
                "사건/사고": "safety", 
                "경제": "economy",
                "맛집/음식": "food",
            }
            tag_variant = cat_variants.get(cat_text, "travel")
            
            # Build card HTML in one go (avoid multi-line issues)
            image_html = ""
            image_url = topic.get('image_url', '')
            if image_url and isinstance(image_url, str) and image_url.startswith('http'):
                safe_image_url = image_url.replace('http://', 'https://')
                image_html = f'<img src="{safe_image_url}" style="width:100%;border-radius:12px;margin-bottom:12px;object-fit:contain;max-height:400px;background-color:#f8f9fa;" alt="News" onerror="this.style.display=\'none\';" loading="lazy"/>'
            
            # Highlight summary using HTML version
            summary_html = highlight_text_html(topic.get('summary', ''))
            
            # Single HTML block
            card_html = f'''<div class="news-card glass-card">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
<span class="category-tag {tag_variant}">{cat_text}</span>
<span style="color:#888;font-size:0.85rem;font-family:Kanit,sans-serif;">🕒 {meta_info}</span>
</div>
<h3 style="font-family:\'Playfair Display\',Georgia,serif;margin-bottom:10px;">{topic['title']}</h3>
{image_html}
<p style="font-family:Kanit,sans-serif;line-height:1.7;color:inherit;">{summary_html}</p>
</div>'''
            
            st.markdown(card_html, unsafe_allow_html=True)

            # Drawers
            with st.expander(utils.t("view_full_article")):
                full_text = topic.get('full_translated', utils.t("summary_only"))
                st.markdown(full_text, unsafe_allow_html=True)
            
            with st.expander(utils.t("related_share")):
                # Safe Refs Logic
                refs = topic.get('references', [])
                if isinstance(refs, str):
                    # If it's a string, it might be a JSON string or a direct URL
                    if refs.startswith("[") or refs.startswith("{"):
                        try:
                            import json
                            refs = json.loads(refs)
                        except:
                            try:
                                import ast
                                refs = ast.literal_eval(refs)
                            except:
                                refs = []
                    elif refs.startswith("http"):
                        refs = [{'title': 'Original Content', 'url': refs, 'source': 'Source'}]
                    else:
                        refs = []
                
                if not isinstance(refs, list):
                    refs = []

                # Robust URL Extraction for Individual Share
                ref_url = topic.get('link') or "#"
                if ref_url == "#":
                    if refs and isinstance(refs[0], dict):
                        ref_url = refs[0].get('url', '#')
                    
                # Individual Share
                ind_share = f"[태국 뉴스룸]\n{topic['title']}\n\n- {topic['summary']}\n\n👉 원문: {ref_url}\n🌐 뉴스룸: {DEPLOY_URL}"
                st.code(ind_share, language="text")
                st.markdown("---")
                
                # Render Links with Robustness
                if not refs and ref_url != "#":
                    # Synthetic ref if main link exists but refs list is empty
                    refs = [{'title': 'Original Article', 'url': ref_url, 'source': topic.get('source', 'News Source')}]

                for ref in refs:
                    if isinstance(ref, dict):
                        url = ref.get('url', '#')
                        # Double check for broken URL
                        if url == "#" and ref_url != "#": url = ref_url
                        
                        source = ref.get('source', '')
                        source_display = f" ({source})" if source else ""
                        st.markdown(f"**원문**: {url}{source_display}")


            # Comments
            news_id = generate_news_id(topic['title'], topic.get('summary', ''))
            comments = all_comments_data.get(news_id, [])
        
            with st.expander(f"💬 댓글 ({len(comments)})"):
                if not comments:
                    st.caption("아직 댓글이 없습니다.")
                else:
                    for c in comments:
                        # Sanitize User Input
                        user_safe = html.escape(c['user'])
                        text_safe = c['text'].replace("http://", "https://")
                        
                        # Render Safely (Split User/Date from unsafe HTML if possible, or use escaped user)
                        # Using html.escape ensures <script> becomes &lt;script&gt;
                        st.markdown(f"**{user_safe}**: {text_safe} <span style='color:grey; font-size:0.8em'>({c.get('date', '')})</span>", unsafe_allow_html=True)
            
                # Comment Form
                st.markdown("---")
                # Use index to guarantee uniqueness even if ID collisions happen (safety first)
                with st.form(key=f"comm_form_{news_id}_{idx}"):
                    c1, c2 = st.columns([1, 3])
                    nick = c1.text_input("닉네임", placeholder="익명")
                    txt = c2.text_input("내용", placeholder="의견 남기기")
                    if st.form_submit_button("등록"):
                         # ... (Comment Save Logic same as before)
                         last_time = st.session_state.get("last_comment_time", 0)
                         current_time = time.time()
                         if current_time - last_time < 60:
                             st.toast("🚫 도배 방지: 1분 뒤 다시 시도해주세요.")
                         else:
                             safe_nick = html.escape(nick)
                             safe_txt = html.escape(txt)
                             save_comment(news_id, safe_nick, safe_txt)
                             st.session_state["last_comment_time"] = current_time
                             st.toast("댓글 등록 완료!")
                             time.sleep(1)
                             st.rerun()

            st.divider()

        # --- Pagination Footer ---
        if total_pages > 1:
            st.markdown("---")
            with st.container():
                st.markdown('<div class="pagination-container"></div>', unsafe_allow_html=True)
                col_prev, col_info, col_next = st.columns([1, 0.8, 1])
                
                with col_prev:
                    if st.session_state["current_page"] > 1:
                        if st.button(utils.t("prev"), width='stretch', key="p_prev"):
                            st.session_state["current_page"] -= 1
                            st.rerun()
                    else:
                        st.button(utils.t("prev"), disabled=True, width='stretch', key="p_prev_dis")
                        
                with col_info:
                    st.markdown(f"<div class='pagination-info' style='text-align:center; padding-top:10px;'><b>{st.session_state['current_page']} / {total_pages}</b></div>", unsafe_allow_html=True)
                    
                with col_next:
                    if st.session_state["current_page"] < total_pages:
                        if st.button(utils.t("next"), width='stretch', key="p_next"):
                            st.session_state["current_page"] += 1
                            st.rerun()
                    else:
                        st.button(utils.t("next"), disabled=True, width='stretch', key="p_next_dis")

def render_tab_taxi():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_taxi"))
    # Klook 제휴 배너
    render_klook_banner()
    utils.render_custom_header(utils.t("taxi_title"), level=2)
    st.caption(utils.t("taxi_desc"))

    # Input & Place Search Logic
    api_key = google_maps_key # Use centralized key
    
    # State Helpers
    def clear_origin_cands():
        if 'taxi_origin_cands' in st.session_state: del st.session_state['taxi_origin_cands']
    def clear_dest_cands():
        if 'taxi_dest_cands' in st.session_state: del st.session_state['taxi_dest_cands']

    with st.container(border=True):
        st.markdown(f"#### {utils.t('route_set')}")
        
        # --- Origin ---
        c_o1, c_o2 = st.columns([3, 1])
        with c_o1:
            origin_q = st.text_input(utils.t("from"), placeholder="e.g., Asok, Khaosan", key="taxi_origin_q", on_change=clear_origin_cands)
            st.write("")
            st.write("")
            if st.button(utils.t("search"), key="btn_search_orig") and origin_q and api_key:
                with st.spinner(".."):
                    st.session_state['taxi_origin_cands'] = utils.search_places(origin_q, api_key)

        # Origin Selection
        origin_val = origin_q
        if st.session_state.get('taxi_origin_cands'):
            opts = {f"{c['name']} ({c['address']})": c['place_id'] for c in st.session_state['taxi_origin_cands']}
            sel_o_key = st.selectbox(utils.t("from"), list(opts.keys()), key="sel_origin")
            origin_val = f"place_id:{opts[sel_o_key]}"

        st.divider()

        # --- Destination ---
        c_d1, c_d2 = st.columns([3, 1])
        with c_d1:
            dest_q = st.text_input(utils.t("to"), placeholder="e.g., Icon Siam", key="taxi_dest_q", on_change=clear_dest_cands)
            st.write("")
            st.write("")
            if st.button(utils.t("search"), key="btn_search_dest") and dest_q and api_key:
                with st.spinner(".."):
                    st.session_state['taxi_dest_cands'] = utils.search_places(dest_q, api_key)
        
        # Dest Selection
        dest_val = dest_q
        if st.session_state.get('taxi_dest_cands'):
            opts = {f"{c['name']} ({c['address']})": c['place_id'] for c in st.session_state['taxi_dest_cands']}
            sel_d_key = st.selectbox(utils.t("to"), list(opts.keys()), key="sel_dest")
            dest_val = f"place_id:{opts[sel_d_key]}"

        st.divider()
        
        # Quote
        quote_price = st.number_input("Price offered (THB, Optional)" if st.session_state.get('language') == 'English' else "기사가 부른 가격 (THB, 선택)", min_value=0, step=10)
        
        calc_btn = st.button(utils.t("calc_fare"), type="primary", width='stretch')

    if calc_btn:
        if not origin_val or not dest_val:
             st.warning("출발지와 도착지를 확인해주세요.")
        else:
             if not api_key:
                st.error("Google Maps API Key가 설정되지 않았습니다.")
             else:
                with st.spinner(utils.t("analyzing")):
                    dist_km, dur_min, traffic_ratio, error = utils.get_route_estimates(origin_val, dest_val, api_key)
                    
                    if error:
                        st.error(error)
                    else:
                        # Traffic Light UI
                        if traffic_ratio is not None:
                            if traffic_ratio >= 1.5:
                                st.error(f"🔴 정체 (혼잡도 {traffic_ratio:.1f}): 🚨 극심한 정체! (방콕 트래픽 잼). 오토바이이나 지하철 추천.")
                            elif traffic_ratio >= 1.1:
                                st.warning(f"🟡 서행 (혼잡도 {traffic_ratio:.1f}): 차가 조금 많습니다. 여유를 가지세요.")
                            else:
                                st.success(f"🟢 원활 (혼잡도 {traffic_ratio:.1f}): 도로가 뻥 뚫렸어요! 이동하기 좋습니다.")
                        
                        base_meter, fares, is_rush_hour, is_hell_zone, intercity_tip = utils.calculate_expert_fare(dist_km, dur_min, origin_txt=origin_q, dest_txt=dest_q)
                        
                        # Intercity / Long Distance Alert
                        if intercity_tip:
                            st.success("🚍 **도시 간 이동(Intercity)** 감지! (미터기 대신 정액제 요금이 적용됩니다)")
                            st.info(f"💡 **이동 꿀팁**: {intercity_tip}")
                        
                        # Hell Zone Alert (Prioritize)
                        if is_hell_zone:
                            st.error("👿 [교통 지옥 구역] 감지! (Asok/Siam/Sukhumvit 등)")
                            st.caption("💬 이 지역은 상습 정체 구역으로, 미터 택시 승차거부가 심하고 앱 호출 배차가 매우 오래 걸릴 수 있습니다. **지상철(BTS)/지하철(MRT)** 또는 **오토바이** 이용을 강력 추천합니다. 마음을 비우세요 🧘")

                        # Rush Hour Alert
                        if is_rush_hour:
                            st.warning("🚨 **현재는 \'러시아워\'입니다!** (앱 호출비/뚝뚝 할증)")
                            st.caption("💡 07:00-09:30 / 16:30-20:00은 교통체증이 심해 앱 호출비가 비쌉니다. (미터 택시가 그나마 저렴)")
                        
                        # 1. Route Info
                        st.info(f"📏 예상 거리: **{dist_km:.1f}km** | ⏱️ 소요 시간: **{int(dur_min)}분** (교통체증 반영)")
                        
                        # 2. Quote Analysis
                        if quote_price > 0:
                            # Parse Prices (Ranges: "min ~ max")
                            def parse_price(val):
                                try:
                                    if isinstance(val, int): return val, val
                                    parts = str(val).split('~')
                                    if len(parts) == 2:
                                        return int(parts[0].strip()), int(parts[1].strip())
                                    return int(str(val).replace('THB','').strip()), int(str(val).replace('THB','').strip())
                                except:
                                    return 9999, 9999

                            bolt_min, bolt_max = parse_price(fares.get('bolt', {}).get('price', 0))
                            grab_min, grab_max = parse_price(fares.get('grab_taxi', {}).get('price', 0))
                            tuktuk_min, tuktuk_max = parse_price(fares.get('tuktuk', {}).get('price', 0))

                            # Assessment Logic
                            if quote_price <= bolt_min:
                                 st.success(f"**{quote_price}바트**는 \'최저가\' 수준입니다! 바로 타세요. 👍")
                            elif quote_price <= grab_max:
                                 st.success(f"**{quote_price}바트**는 적절한 가격입니다. (Bolt/Grab 앱 호출 호가)")
                            elif quote_price <= tuktuk_min * 1.2:
                                 st.warning(f"**{quote_price}바트**는 조금 비쌉니다. (급할 때만 타세요)")
                            else:
                                 st.error(f"🚨 **{quote_price}바트**는 바가지입니다! (다른 수단 권장)")
                        
                        st.divider()
                        
                        # 3. Fare Table (Cards)
                        st.subheader("💰 교통수단별 적정 요금표")
                        st.caption("Disclaimer: 실제 교통상황/시간대에 따라 오차가 있을 수 있습니다.")
                        
                        cols = st.columns(4)
                        # Order: Bike, Bolt (Merged), Grab, TukTuk
                        keys = ['bike', 'bolt', 'grab_taxi', 'tuktuk']
                        
                        for i, k in enumerate(keys):
                            item = fares[k]
                            with cols[i]:
                                with st.container(border=True):
                                    st.markdown(f"**{item['label']}**")
                                    price_display = f"{item['price']} THB"
                                    
                                    color = item['color']
                                    st.markdown(f"<h3 style=\'color:{color}; margin:0;\'>{price_display}</h3>", unsafe_allow_html=True)
                                    
                                    tag_color = "#e5e7eb" # gray-200
                                    text_color = "#374151" # gray-700
                                    if color == "red": 
                                        tag_color = "#fee2e2"
                                        text_color = "#991b1b"
                                    if color == "green": 
                                        tag_color = "#dcfce7"
                                        text_color = "#166534"
                                    if color == "blue": 
                                        tag_color = "#dbeafe"
                                        text_color = "#1e40af"
                                    if color == "orange":
                                        tag_color = "#ffedd5"
                                        text_color = "#c2410c"
                                    
                                    st.markdown(f"<div style=\'background-color:{tag_color}; padding:4px; border-radius:4px; font-size:0.8em; text-align:center; color:{text_color}; margin-top:5px;\'>{item['tag']}</div>", unsafe_allow_html=True)
                                    
                                    if item.get("warning"):
                                        st.markdown(f"<div style=\'font-size:0.7em; color:red; margin-top:5px;\'>⚠️ " + ("Don\'t take if higher than this!" if st.session_state.get('language') == 'English' else "이 가격보다 비싸면 타지 마세요!") + "</div>", unsafe_allow_html=True)
                                        
                                    if item.get("warning_text"):
                                         st.caption(f"⚠️ {item['warning_text']}")

                        st.divider()
                        st.info("💡 " + ("Chiang Mai, Pattaya, etc. may be cheaper. Note that Phuket/Samui often use Flat Rate." if st.session_state.get('language') == 'English' else "치앙마이, 파타야 등 지방 도시는 위 요금보다 더 저렴할 수 있습니다. 단, \'푸켓\'과 \'코사무이\'는 미터기를 잘 안 켜고 담합 가격(Flat Rate)을 부르니 주의하세요!"))

def render_tab_event():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_event"))
    # Klook 제휴 배너
    render_klook_banner()
    st.markdown(f"### {utils.t('nav_event')}")
    st.info(f"💡 {utils.t('sidebar_info')}")
    
    events = get_cached_events()
    if not events:
        st.info(utils.t("no_events"))
    else:
        for i, ev in enumerate(events):
            with st.container(border=True):
                ec1, ec2 = st.columns([1, 4])
                with ec1:
                    if ev.get('image_url'):
                        st.image(ev['image_url'], use_container_width=True)
                    else:
                        st.markdown("### 🎪")
                with ec2:
                    st.markdown(f"#### {ev.get('title', 'Event')}")
                    st.markdown(f"{utils.t('event_date')}: {ev.get('date', 'TBA')}")
                    st.markdown(f"{utils.t('event_place')}: {ev.get('place', 'Bangkok')}")
                    
                    if ev.get('info'):
                        st.caption(ev['info'])
                    if ev.get('url'):
                        st.link_button(utils.t("read_more"), ev['url'], use_container_width=True)

def render_tab_hotel():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_hotel"))
    # Klook 제휴 배너
    render_klook_banner()
    utils.render_custom_header(utils.t("hotel_fact"), level=2)
    st.caption(utils.t("hotel_desc"))
    
    # 1. Search Input
    # Using global keys
    # 1. Search Input
    # Using global keys
    api_key = google_maps_key
    # gemini_key is already global


    # State Helpers
    def clear_hotel_cands():
        if 'hotel_candidates' in st.session_state: del st.session_state['hotel_candidates']
    
    # Init History
    if 'hotel_history' not in st.session_state:
        st.session_state['hotel_history'] = []

    # CRITICAL FIX: Ultra-flat UI to avoid delta path conflicts
    if not st.session_state.get('show_hotel_analysis'):
        # Area 1: Search inputs (No container, no columns)
        city_opts = ["Bangkok", "Pattaya", "Chiang Mai", "Phuket", "Krabi", "Koh Samui", "Hua Hin", "Pai", utils.t("other") if st.session_state.get('language') == 'English' else "기타 (직접 입력)"]
        selected_city = st.selectbox(utils.t("hotel_city"), city_opts, key="user_city_select", on_change=clear_hotel_cands)
        
        if selected_city == (utils.t("other") if st.session_state.get('language') == 'English' else "기타 (직접 입력)"):
            city = st.text_input("City Name (English)", placeholder="e.g., Siracha", key="user_city_manual")
        else:
            city = selected_city
            
        # --- 📊 실시간 호텔 랭킹 TOP 10 ---
        hotel_ranking = utils.get_top_places('hotel')
        if hotel_ranking:
            with st.expander("🔥 실시간 인기 호텔 TOP 5", expanded=False):
                for item in hotel_ranking[:5]:
                    r_col1, r_col2 = st.columns([0.8, 0.2])
                    with r_col1:
                        st.markdown(f"**{item['rank']}. {item['name']}** (팩트체크: {item['rating']}/5)  \n<small>{item['badge']}</small>", unsafe_allow_html=True)
                    with r_col2:
                        if st.button("보기", key=f"rank_h_{item['rank']}", use_container_width=True):
                            st.session_state['user_hotel_input'] = item['name']
                            if 'hotel_candidates' in st.session_state: del st.session_state['hotel_candidates']
                            st.rerun()
                st.caption("※ 사용자들의 실제 검색 데이터를 기반으로 한 스마트 랭킹입니다.")

        hotel_query = st.text_input(utils.t("hotel_search"), placeholder=utils.t("hotel_placeholder"), key="user_hotel_input", on_change=clear_hotel_cands)

        # Search Button
        if st.button(utils.t("hotel_find"), key="btn_hotel_search", type="primary", use_container_width=True):
            if not hotel_query:
                st.warning(utils.t("no_results") if st.session_state.get('language') == 'English' else "호텔 이름을 입력해주세요.")
            elif not api_key:
                st.error("Google Maps API Key Missing")
            else:
                with st.spinner(utils.t("searching")):
                    # [NEW] Check Cache First - Even before searching Maps
                    cached = utils.get_hotel_cache(hotel_query)
                    if cached:
                        st.success("📦 " + ("Found cached analysis!" if st.session_state.get('language') == 'English' else "기존 분석 데이터를 찾았습니다! 바로 결과를 보여드립니다."))
                        st.session_state['show_hotel_analysis'] = True
                        st.session_state['active_hotel_id'] = "CACHED"
                        st.session_state['_selected_hotel_label'] = hotel_query
                        st.rerun()

                    cands = utils.fetch_hotel_candidates(hotel_query, city, api_key)
                    if not cands: 
                        st.error(utils.t("no_results"))
                        if 'hotel_candidates' in st.session_state: del st.session_state['hotel_candidates']
                    else:
                        st.session_state['hotel_candidates'] = cands
                        st.session_state['show_hotel_analysis'] = False
                        st.session_state['active_hotel_id'] = None

        # Area 2: Selection (No columns)
        if st.session_state.get('hotel_candidates'):
            cands = st.session_state['hotel_candidates']
            options = {f"{c['name']} ({c['address']})": c['id'] for c in cands}
            
            sel_label = st.selectbox(utils.t("hotel_select"), list(options.keys()), key="sel_hotel_final")
            target_place_id = options[sel_label]
            
            st.session_state['_selected_hotel_id'] = target_place_id
            st.session_state['_selected_hotel_label'] = sel_label.split('(')[0].strip()
            
            st.info(f"{utils.t('hotel_select')}: **{sel_label.split('(')[0]}**")

            # Simply use a button with a clear rerun
            if st.button(utils.t("analysis_btn"), type="primary", use_container_width=True):
                st.session_state['show_hotel_analysis'] = True
                st.session_state['active_hotel_id'] = st.session_state['_selected_hotel_id']
                st.rerun()
    else:
        # Area 3: Analysis Results (No columns)
        if st.button(utils.t("hotel_back"), use_container_width=True):
            st.session_state['show_hotel_analysis'] = False
            st.rerun()

        active_id = st.session_state.get('active_hotel_id')
        if active_id:
            if not gemini_key or not api_key:
                 st.error("API Key Missing")
            else:
                 with st.spinner(utils.t("analyzing")):
                     # [NEW] Check GSheets Cache First to save API costs
                     hotel_name_to_check = st.session_state.get('_selected_hotel_label', '')
                     cached_result = utils.get_hotel_cache(hotel_name_to_check)
                     
                     info = None
                     analysis = None
                     
                     if cached_result:
                         st.success(f"📦 캐시된 분석 데이터를 발견했습니다! ({cached_result['cached_date']})")
                         cache_data = cached_result['raw_json']
                         info = cache_data.get('info')
                         analysis = cache_data.get('analysis')
                         
                         # 랭킹 데이터 기록 (캐시 히트 시에도 인기 장소이므로 기록)
                         if info and analysis:
                             # 팩트체크 점수 계산 (summary_score 평균)
                             scores = analysis.get('summary_score', {})
                             if scores:
                                 fact_score = sum(scores.values()) / len(scores) if scores else info['rating']
                                 utils.log_search(info['name'], fact_score, 'hotel')
                             else:
                                 utils.log_search(info['name'], info['rating'], 'hotel')
                         # 캐시된 아고다 URL 저장 (하이브리드 링크용)
                         if cached_result.get('agoda_url'):
                             st.session_state['cached_agoda_url'] = cached_result['agoda_url']
                         else:
                             st.session_state['cached_agoda_url'] = None
                     else:
                         # Cache Miss: Proceed with Google Maps + Gemini Analysis
                         info = utils.fetch_hotel_details(active_id, api_key)
                         
                         if info:
                             analysis = utils.analyze_hotel_reviews(info['name'], info['rating'], info['reviews'], gemini_key)
                             
                             # 랭킹 데이터 기록
                             if analysis and not isinstance(analysis, list) and "error" not in analysis:
                                 scores = analysis.get('summary_score', {})
                                 if scores:
                                     fact_score = sum(scores.values()) / len(scores) if scores else info['rating']
                                     utils.log_search(info['name'], fact_score, 'hotel')
                                 else:
                                     utils.log_search(info['name'], info['rating'], 'hotel')
                             else:
                                 utils.log_search(info['name'], info['rating'], 'hotel')
                            
                             # If successful, save to cache
                             if analysis and isinstance(analysis, dict) and "error" not in analysis:
                                 # Combine info and analysis for a complete cache hit next time
                                 full_cached_json = {"info": info, "analysis": analysis}
                                 summary = analysis.get('one_line_verdict', '')
                                 utils.save_hotel_cache(info['name'], summary, full_cached_json)
                             elif isinstance(analysis, list) and len(analysis) > 0:
                                 # Some versions might return a list
                                 full_cached_json = {"info": info, "analysis": analysis[0]}
                                 summary = analysis[0].get('one_line_verdict', '')
                                 utils.save_hotel_cache(info['name'], summary, full_cached_json)
                                 analysis = analysis[0]
                     
                     if info and analysis:
                         if isinstance(analysis, dict) and "error" in analysis:
                             st.error(f"분석 중 오류 발생: {analysis['error']}")
                         elif not isinstance(analysis, dict):
                             st.error(f"분석 결과 형식 오류: {str(analysis)}")
                         else:
                             # Flat Display (No columns)
                             if info.get('photo_url'):
                                 st.image(info['photo_url'], use_container_width=True, caption=info['name'])
                             
                             # 📷 투숙객 사진 갤러리 (가로 스크롤)
                             photo_urls = info.get('photo_urls', [])
                             if photo_urls and len(photo_urls) > 1:
                                 with st.expander(utils.t("photos"), expanded=True):
                                     # 가로 스크롤 갤러리 CSS + HTML
                                     gallery_html = """
                                     <style>
                                     .photo-gallery {
                                         display: flex;
                                         overflow-x: auto;
                                         gap: 12px;
                                         padding: 10px 0;
                                         scroll-snap-type: x mandatory;
                                         -webkit-overflow-scrolling: touch;
                                     }
                                     .photo-gallery::-webkit-scrollbar {
                                         height: 8px;
                                     }
                                     .photo-gallery::-webkit-scrollbar-thumb {
                                         background: #888;
                                         border-radius: 4px;
                                     }
                                     .photo-card {
                                         flex: 0 0 auto;
                                         scroll-snap-align: start;
                                         border-radius: 12px;
                                         overflow: hidden;
                                         box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                                         transition: transform 0.2s;
                                     }
                                     .photo-card:hover {
                                         transform: scale(1.02);
                                     }
                                     .photo-card img {
                                         height: 200px;
                                         width: auto;
                                         object-fit: cover;
                                     }
                                     </style>
                                     <div class="photo-gallery">
                                     """
                                     for idx, photo_url in enumerate(photo_urls):
                                         gallery_html += f'<div class="photo-card"><img src="{photo_url}" alt="호텔 사진 {idx+1}"></div>'
                                     gallery_html += "</div>"
                                     
                                     st.markdown(gallery_html, unsafe_allow_html=True)
                                     st.caption(utils.t("photo_caption"))
                             
                             st.subheader(f"{info['name']}")
                             st.markdown(f"📍 **{utils.t('location')}:** {info['address']}")
                             st.markdown(f"⭐ **" + ("Google Rating" if st.session_state.get('language') == 'English' else "구글 평점") + f":** {info['rating']} ({info['review_count']:,} " + ("reviews" if st.session_state.get('language') == 'English' else "명 참여") + ")")
                             
                             if analysis.get('price_level'):
                                 st.markdown(f"{analysis['price_level']} **{analysis.get('price_range_text', '')}**")
                             
                             st.divider()

                             # History logic
                             history_item = {
                                 "info": info,
                                 "analysis": analysis,
                                 "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                             }
                             st.session_state['hotel_history'] = [
                                 h for h in st.session_state['hotel_history'] 
                                 if h['info']['name'] != info['name']
                             ]
                             st.session_state['hotel_history'].insert(0, history_item)
                              
                             # --- 💰 수익화 버튼들 (아고다 & 트립닷컴) ---
                             st.divider()
                             st.caption("💰 지금 예약하면 특가 할인!")
                             
                             # 아고다 버튼 (하이브리드: 직통 링크 우선)
                             cached_agoda = analysis.get('agoda_url') or st.session_state.get('cached_agoda_url')
                             agoda_url, is_direct = utils.get_hotel_link(info.get('name', ''), cached_agoda)
                             
                             if is_direct:
                                 # 직통 링크가 있으면 더 강조
                                 st.link_button("🚀 아고다에서 바로 예약하기 (검증됨)", agoda_url, use_container_width=True, type="primary")
                             else:
                                 st.link_button("🏨 아고다에서 최저가 검색하기", agoda_url, use_container_width=True, type="primary")
                             
                             # Trip.com link
                             try:
                                 import urllib.parse
                                 trip_secrets = st.secrets.get("trip_com", {})
                                 aid = trip_secrets.get("alliance_id")
                                 sid = trip_secrets.get("sid")
                                 
                                 if aid and sid:
                                     raw_keyword = analysis.get('trip_keyword') or info.get('name', '')
                                     today_str = datetime.now().strftime("%Y-%m-%d")
                                     tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                                     encoded_keyword = urllib.parse.quote(f'"{raw_keyword}"')
                                     trip_url = (
                                         f"https://kr.trip.com/hotels/list?"
                                         f"searchType=KW&"
                                         f"keyword={encoded_keyword}&"
                                         f"searchText={encoded_keyword}&"
                                         f"checkIn={today_str}&checkOut={tomorrow_str}&"
                                         f"allianceid={aid}&sid={sid}"
                                     )
                                     st.link_button(f"🏨 트립닷컴에서도 비교하기", trip_url, use_container_width=True, type="secondary")
                             except: pass
                                 
                             st.info(f"💡 **" + ("Verdict" if st.session_state.get('language') == 'English' else "한 줄 요약") + f":** {analysis.get('one_line_verdict', 'N/A')}")
                             st.markdown(f"🎯 **{analysis.get('recommendation_target', '')}**")
                            
                             st.success(utils.t("pros_title"))
                             for p in analysis.get('pros', []):
                                 st.markdown(f"- {p}")
                                
                             st.error(utils.t("cons_title"))
                             for c in analysis.get('cons', []):
                                 st.markdown(f"- {c}")
                        
                         # Detailed Analysis
                         with st.expander(utils.t("searching") if st.session_state.get('language') == 'English' else "🔍 상세 분석 보기", expanded=True):
                             st.markdown(f"### {utils.t('location_title')}")
                             st.write(analysis.get('location_analysis', '-'))
                            
                             st.markdown(f"### {utils.t('room_title')}")
                             st.write(analysis.get('room_condition', '-'))
                            
                             st.markdown(f"### {utils.t('service_title')}")
                             st.write(analysis.get('service_breakfast', '-'))
                            
                             st.markdown(f"### {utils.t('facility_title')}")
                             st.write(analysis.get('pool_facilities', '-'))
                        
                         # Scores
                         scores = analysis.get('summary_score', {})
                         if scores:
                             st.markdown(f"### {utils.t('score_title')}")
                             sc1, sc2, sc3, sc4 = st.columns(4)
                             sc1.metric(utils.t("cleanliness"), f"{scores.get('cleanliness', 0)}/5")
                             sc2.metric(utils.t("location"), f"{scores.get('location', 0)}/5")
                             sc3.metric(utils.t("comfort"), f"{scores.get('comfort', 0)}/5")
                             sc4.metric(utils.t("value"), f"{scores.get('value', 0)}/5")
                         
                         # --- 📢 팩트체크 결과 공유하기 (즉시 표시) ---
                         st.divider()
                         # 분석 완료 시 바로 공유 텍스트 생성 (버튼 클릭 불필요)
                         hotel_name = info.get('name', '호텔')
                         share_summary = utils.extract_hotel_share_summary(hotel_name, analysis)
                         
                         with st.expander(utils.t("share_friend"), expanded=False):
                             st.code(share_summary, language=None)
                             st.caption(utils.t("share_caption"))
    
    # --- Value-Add: Search History ---
    if st.session_state.get('hotel_history'):
        st.divider()
        c_hist_title, c_hist_clear = st.columns([4, 1])
        with c_hist_title:
            st.subheader("🕒 최근 분석한 호텔 (History)")
        with c_hist_clear:
            if st.button("기록 전체 삭제", type="secondary", key="clear_hotel_hist"):
                st.session_state['hotel_history'] = []
                st.rerun()

        for idx, h_item in enumerate(st.session_state['hotel_history']):
            h_info = h_item['info']
            h_analysis = h_item['analysis']
            
            with st.expander(f"🏨 {h_info['name']} ({h_info['rating']}⭐) - {h_analysis.get('one_line_verdict', '')}"):
                # Simplified View for History
                hc1, hc2 = st.columns([1, 2])
                with hc1:
                    if h_info.get('photo_url'):
                         st.image(h_info['photo_url'], width='stretch')
                    st.caption(f"📍 {h_info['address']}")
                with hc2:
                    st.info(f"💡 {h_analysis.get('one_line_verdict', '')}")
                    st.markdown(f"🎯 **{h_analysis.get('recommendation_target', '')}**")
                    
                    # Tags
                    pros = h_analysis.get('pros', [])[:2] # Top 2 only
                    cons = h_analysis.get('cons', [])[:2]
                    st.success(f"😊 {', '.join(pros)}")
                    st.error(f"⚠️ {', '.join(cons)}")
                    
                # History Scores
                h_scores = h_analysis.get('summary_score', {})
                if h_scores:
                    st.markdown("---")
                    hc_s1, hc_s2, hc_s3, hc_s4 = st.columns(4)
                    hc_s1.metric("청결도", f"{h_scores.get('cleanliness', 0)}/5")
                    hc_s2.metric("위치", f"{h_scores.get('location', 0)}/5")
                    hc_s3.metric("편안함", f"{h_scores.get('comfort', 0)}/5")
                    hc_s4.metric("가성비", f"{h_scores.get('value', 0)}/5")

def render_tab_food():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_food"))
    # 맛집 전용: 디너 크루즈 배너
    render_dinner_cruise_banner()
    utils.render_custom_header(utils.t("food_fact"), level=2)
    st.caption(utils.t("food_desc"))
    
    # 세션 상태 초기화
    if "restaurant_search_results" not in st.session_state:
        st.session_state["restaurant_search_results"] = []
    if "restaurant_selected" not in st.session_state:
        st.session_state["restaurant_selected"] = None
    if "restaurant_details" not in st.session_state:
        st.session_state["restaurant_details"] = None
    if "food_history" not in st.session_state:
        st.session_state["food_history"] = []
    
    # --- 1단계: 검색 ---
    container = st.container(border=True)
    with container:
        # --- 📊 실시간 맛집 랭킹 TOP 10 ---
        food_ranking = utils.get_top_places('food')
        if food_ranking:
            with st.expander("🔥 실시간 인기 맛집 TOP 5", expanded=False):
                for item in food_ranking[:5]:
                    f_col1, f_col2 = st.columns([0.8, 0.2])
                    with f_col1:
                        st.markdown(f"**{item['rank']}. {item['name']}** ({item['rating']})  \n<small>{item['badge']}</small>", unsafe_allow_html=True)
                    with f_col2:
                        if st.button("보기", key=f"rank_f_{item['rank']}", use_container_width=True):
                            st.session_state['restaurant_input'] = item['name']
                            if "restaurant_search_results" in st.session_state: del st.session_state["restaurant_search_results"]
                            st.rerun()
                st.caption("※ 사용자들의 실제 검색 데이터를 기반으로 한 스마트 랭킹입니다.")

        r_name = st.text_input(utils.t("searching"), placeholder=utils.t("rest_placeholder"), key="restaurant_input")
        
        search_btn = st.button(utils.t("search_rest"), key="btn_r_search", type="primary", use_container_width=True)
        
        if search_btn:
            if not r_name:
                st.warning(utils.t("no_results") if st.session_state.get('language') == 'English' else "식당 이름을 입력해주세요.")
            else:
                with st.spinner(utils.t("searching")):
                    results = utils.search_restaurants(r_name)
                    st.session_state["restaurant_search_results"] = results
                    st.session_state["restaurant_selected"] = None
                    st.session_state["restaurant_details"] = None
    
    # --- 2단계: 검색 결과 표시 및 선택 ---
    search_results = st.session_state.get("restaurant_search_results", [])
    
    if search_results:
        st.divider()
        st.markdown(f"#### 🍜 " + (utils.t("no_results") if not search_results else ( "Search Results - Select a restaurant" if st.session_state.get('language') == 'English' else "검색 결과 - 식당을 선택하세요")))
        
        # Radio 옵션 생성
        options = [f"{r['name']} ({r['address']})" for r in search_results]
        
        selected_option = st.radio(
            utils.t("nav_food"),
            options,
            key="restaurant_radio",
            label_visibility="collapsed"
        )
        
        # 선택된 식당의 location_id 찾기
        selected_idx = options.index(selected_option) if selected_option else 0
        selected_restaurant = search_results[selected_idx]
        
        st.session_state["restaurant_selected"] = selected_restaurant
        
        # 팩트체크 시작 버튼
        if st.button(utils.t("analysis_btn"), key="btn_r_factcheck", type="primary", use_container_width=True):
            with st.spinner(utils.t("analyzing")):
                # Get Gemini Key for analysis
                # gemini_key is already global
                details = utils.get_restaurant_details(selected_restaurant['location_id'], gemini_api_key=gemini_key)
                
                if details:
                    # 랭킹 데이터 기록
                    utils.log_search(details['name'], details['rating'], 'food')
                
                if not details:
                    st.error(utils.t("error_loading_details"))
                    st.stop()
                    
                st.session_state["restaurant_details"] = details
                
                # 히스토리 추가 (중복 제거 및 최상단)
                history_item = {
                    'place_id': selected_restaurant['location_id'],
                    'name': details['name'],
                    'details': details
                }
                st.session_state['food_history'] = [h for h in st.session_state['food_history'] if h['place_id'] != selected_restaurant['location_id']]
                st.session_state['food_history'].insert(0, history_item)
                st.session_state['food_history'] = st.session_state['food_history'][:10] # 최대 10개
    
    elif st.session_state.get("restaurant_search_results") == []:
        # 검색했지만 결과 없음
        if st.session_state.get("restaurant_input"):
            st.info(utils.t("no_results"))
    
    # --- 3단계: 상세 분석 결과 표시 ---
    details = st.session_state.get("restaurant_details")
    if details:
        st.divider()
        
        # 종합 점수 헤더 (Google은 전체 평점만 있음 - 강조)
        rating = details.get('rating', 0)
        num_reviews = details.get('num_reviews', 0)
        price_text = details.get('price_text', '')
        hours_status = details.get('hours', '')
        
        # 평점 색상
        if rating >= 4.5:
            rating_color = "#00B894"  # 초록
            rating_emoji = "🏆"
        elif rating >= 4.0:
            rating_color = "#D4AF37"  # 금색
            rating_emoji = "⭐"
        elif rating >= 3.5:
            rating_color = "#FDCB6E"  # 노랑
            rating_emoji = "🤔"
        else:
            rating_color = "#E17055"  # 빨강
            rating_emoji = "⚠️"
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {rating_color}22 0%, {rating_color}11 100%);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            border: 2px solid {rating_color};
            margin-bottom: 20px;
        ">
            <h1 style="margin: 0; color: {rating_color}; font-size: 3rem;">{rating_emoji} {rating}</h1>
            <p style="font-size: 1.2rem; margin: 8px 0 0 0; color: #888;">{utils.t('rating_caption').format(num_reviews=num_reviews)}</p>
            <p style="font-size: 1rem; margin: 8px 0 0 0;">{price_text} {hours_status}</p>
        </div>
        """, unsafe_allow_html=True)

        # AI One-line Verdict (MICHELIN STYLE)
        analysis = details.get('analysis', {})
        verdict = analysis.get('one_line_verdict') or analysis.get('verdict')
        
        if verdict:
            st.info(f"🧐 **팩트체크 요약**: {verdict}")
        
        # 식당 기본 정보
        st.markdown(f"### 🍜 {details.get('name', '식당')}")
        
        # 구글 한 줄 소개 (Editorial Summary)
        if details.get('editorial_summary'):
            st.caption(f"✨ {details.get('editorial_summary')}")
        
        recommended_menu = details.get('recommended_menu', [])
        if recommended_menu:
            st.markdown(f"##### {utils.t('recommend_menu')}")
            menu_html = " ".join([f'<span style="background-color: #ffeaa7; padding: 4px 10px; border-radius: 12px; margin-right: 6px; font-weight: bold; color: #d63031;">#{m}</span>' for m in recommended_menu])
            st.markdown(menu_html, unsafe_allow_html=True)
            st.write("") # 간격
        
        # 🔔 주의사항 뱃지 (추천 메뉴 아래, 인라인 표시)
        warnings = details.get('analysis', {}).get('warnings', [])
        if warnings:
            warning_html = '<div style="display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0;">'
            for warn in warnings:
                if warn.get('level') == 'error':
                    badge_color = '#d63031' # Red (Strong Warning)
                    text_color = '#fff'
                elif warn.get('level') == 'warning':
                    badge_color = '#e17055' # Orange
                    text_color = '#fff'
                else:
                    badge_color = '#74b9ff' # Blue (Info)
                    text_color = '#fff'
                warning_html += f'<span style="background-color: {badge_color}; color: {text_color}; padding: 6px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500;">{warn["message"]}</span>'
            warning_html += '</div>'
            st.markdown(warning_html, unsafe_allow_html=True)
        
        # 사진 갤러리 (상단 배치)
        photos = details.get('photos', [])
        if photos:
            st.markdown("#### 📸 사진")
            gallery_html = '<div style="display: flex; overflow-x: auto; gap: 10px; padding: 10px 0;">'
            for photo in photos:
                if photo:
                    gallery_html += f'<img src="{photo}" style="height: 180px; border-radius: 12px; object-fit: cover; flex-shrink: 0;">'
            gallery_html += '</div>'
            st.markdown(gallery_html, unsafe_allow_html=True)
            st.caption(utils.t("photo_caption"))
        
        # 정보 요약 (Google은 세부 점수가 없으므로 바로 정보 표시)
        st.markdown(f"#### {utils.t('basic_info')}")
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            if details.get('price_text'):
                st.markdown(f"{utils.t('price_range')}: {details.get('price_text', '')}")
            if details.get('cuisines'):
                cuisines_text = ', '.join(details.get('cuisines', []))
                if cuisines_text:
                    st.markdown(f"{utils.t('cuisine_type')}: {cuisines_text}")
            if details.get('hours'):
                st.markdown(f"{utils.t('opening_status')}: {details.get('hours', '')}")
        
        with info_col2:
            if details.get('address'):
                st.markdown(f"📍 **주소:** {details.get('address', '')}")
            if details.get('phone'):
                st.markdown(f"📞 **전화:** {details.get('phone', '')}")
        
        # --- 💡 팩트체크 요약 섹션 (호텔 탭 스타일) ---
        st.markdown("#### 💡 팩트체크 요약")
        analysis = details.get('analysis', {})
        
        # 한줄추천 (Verdict)
        verdict = analysis.get('verdict', '방문해 볼 만한 곳입니다.')
        st.info(f"**{verdict}**")
        
        # 장점 & 단점 컬럼
        col_pros, col_cons = st.columns(2)
        
        with col_pros:
            st.markdown("##### 👍 장점")
            pros = analysis.get('pros', ["전반적으로 무난함"])
            for p in pros:
                st.success(f"**{p}**")
                
        with col_cons:
            st.markdown("##### 👎 단점")
            cons = analysis.get('cons', ["특별한 단점 발견되지 않음 ✨"])
            for c in cons:
                st.error(f"**{c}**")
        
        # (주의사항은 이제 추천 메뉴 아래 뱃지로 표시됨)
        
        # --- 💬 베스트 리뷰 섹션 ---

        # --- 💬 베스트 리뷰 섹션 (Top 3) ---
        best_reviews = analysis.get('best_reviews')
        
        # Fallback to single review if list is missing (Legacy)
        if not best_reviews:
            single = analysis.get('best_review')
            if single: best_reviews = [single]
            
        if best_reviews:
            st.markdown(f"#### 💬 베스트 리뷰 ({len(best_reviews)}개)")
            if len(best_reviews) > 1:
                st.caption("✨ AI가 선정한 가장 유용한 리뷰들입니다.")
            
            for i, br in enumerate(best_reviews):
                if isinstance(br, dict):
                    b_rating = br.get('rating', 0)
                    b_time = br.get('relative_time', '최근')
                    
                    # Create a card for each review
                    with st.container():
                        st.markdown(f"**Review #{i+1}** <span style='color:orange'>({b_rating}⭐)</span> <span style='color:grey; font-size:0.8em'>| {b_time}</span>", unsafe_allow_html=True)
                        st.info(f"\"{br.get('text', '')}\"")
                elif isinstance(br, str):
                    st.info(f"\"{br}\"") # Legacy string support
        
        # --- 🍽️ 메뉴 정보 섹션 ---
        menu_url = details.get('menu_url')
        if menu_url:
            st.markdown(f"#### {utils.t('menu_info')}")
            st.link_button(utils.t("menu_search_btn"), menu_url, use_container_width=True)
            st.caption(utils.t("menu_search_caption"))
            
        # --- 📢 팩트체크 결과 공유하기 ---
        st.divider()
        share_text = utils.extract_restaurant_share_summary(details.get('name', '식당'), details)
        with st.expander(utils.t("share_friend"), expanded=False):
            st.code(share_text, language=None)
            st.caption(utils.t("share_caption"))
        st.divider()
        
        # Google Maps 링크
        if details.get('web_url'):
            st.link_button("🗺️ " + ("View details on Google Maps" if st.session_state.get('language') == 'English' else "구글 지도에서 상세 정보 보기"), details.get('web_url'), use_container_width=True)
        
        st.divider()
        if st.button(utils.t("clear_results"), key="btn_clear_food"):
            st.session_state["restaurant_search_results"] = []
            st.session_state["restaurant_selected"] = None
            st.session_state["restaurant_details"] = None
            st.rerun()

    # --- 🕒 최근 본 맛집 (History) ---
    if st.session_state.get('food_history'):
        st.divider()
        h_col1, h_col2 = st.columns([4, 1])
        with h_col1:
            st.subheader(utils.t("recent_history"))
        with h_col2:
            if st.button(utils.t("delete_history"), key="clear_food_hist", type="secondary"):
                st.session_state['food_history'] = []
                st.rerun()
        
        for i, h_item in enumerate(st.session_state['food_history']):
            h_name = h_item['name']
            h_details = h_item['details']
            h_analysis = h_details.get('analysis', {})
            h_verdict = h_analysis.get('one_line_verdict') or h_analysis.get('verdict') or ""
            
            with st.expander(f"🍴 {h_name} ({h_details.get('rating', 0)}⭐) - {h_verdict}"):
                h_c1, h_c2 = st.columns([1, 2])
                with h_c1:
                    # 대표 사진 하나 표시
                    if h_details.get('photos'):
                        st.image(h_details['photos'][0], use_container_width=True)
                    st.caption(f"📍 {h_details.get('address', '')}")
                
                with h_c2:
                    st.info(f"🏆 {h_analysis.get('verdict', '')}")
                    
                    # 간단한 장/단점 요약
                    h_pros = ", ".join(h_analysis.get('pros', [])[:2])
                    h_cons = ", ".join(h_analysis.get('cons', [])[:2])
                    if h_pros: st.success(f"👍 {h_pros}")
                    if h_cons: st.error(f"👎 {h_cons}")
                    
                    if st.button(utils.t("view_detail_again"), key=f"btn_h_view_{i}", use_container_width=True):
                        st.session_state["restaurant_selected"] = h_item['place_id']
                        st.session_state["restaurant_details"] = h_details
                        st.rerun()

def render_tab_guide():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_guide"))
    # Klook 제휴 배너
    render_klook_banner()
    # 세션 상태 초기화
    if "guide_view" not in st.session_state:
        st.session_state["guide_view"] = "list"
    if "guide_post_id" not in st.session_state:
        st.session_state["guide_post_id"] = None
    
    # Header
    utils.render_custom_header(utils.t("guide_title"), level=2)
    st.caption(utils.t("guide_desc"))
    
    # 글 목록 가져오기 (언어별 분기)
    is_english_mode = st.session_state.get('language') == 'English'
    
    if is_english_mode:
        # English Mode: Import and use English articles
        try:
            from data_articles_en import ENGLISH_GUIDE_ARTICLES
            blog_posts = ENGLISH_GUIDE_ARTICLES
        except ImportError:
            blog_posts = []
    else:
        # Korean Mode: Use existing blog posts
        blog_posts = utils.fetch_blog_posts()
    
    # --- Detail View ---
    if st.session_state["guide_view"] == "detail" and st.session_state["guide_post_id"]:
        # 뒤로가기 버튼
        if st.button(utils.t("back_to_list"), key="btn_back_guide"):
            st.session_state["guide_view"] = "list"
            st.session_state["guide_post_id"] = None
            st.rerun()
        
        # 해당 포스트 찾기
        post = next((p for p in blog_posts if str(p.get('id')) == str(st.session_state["guide_post_id"])), None)
        
        if post:
            st.divider()
            
            # 대표 이미지
            if post.get('image_url'):
                st.image(post['image_url'], use_container_width=True)
            
            # 제목 & 메타
            st.markdown(f"## {post.get('title', '제목 없음')}")
            st.caption(f"📅 {post.get('date', '')} | ✍️ {post.get('author', '관리자')}")
            
            st.divider()
            
            # 본문 (Markdown 렌더링)
            content = post.get('content', '')
            st.markdown(content, unsafe_allow_html=True)
            
            st.divider()
            st.caption(utils.t("share_help"))
        else:
            st.error("게시글을 찾을 수 없습니다.")
            st.session_state["guide_view"] = "list"
    
    # --- List View ---
    else:
        if not blog_posts:
            st.info(utils.t("no_guide"))
        else:
            # 수직형 카드 리스트 (모바일 최적화)
            for post in blog_posts:
                with st.container():
                    # CSS 카드 스타일
                    card_html = f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
                        backdrop-filter: blur(10px);
                        border-radius: 16px;
                        overflow: hidden;
                        margin-bottom: 20px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                        border: 1px solid rgba(255,255,255,0.1);
                    ">
                        <img src="{post.get('image_url', '')}" style="
                            width: 100%;
                            height: 200px;
                            object-fit: cover;
                        " onerror="this.style.display='none'">
                        <div style="padding: 16px;">
                            <h3 style="margin: 0 0 8px 0; font-size: 1.2rem;">{post.get('title', '제목 없음')}</h3>
                            <p style="color: #888; font-size: 0.85rem; margin: 0 0 12px 0;">
                                📅 {post.get('date', '')} | ✍️ {post.get('author', '관리자')}
                            </p>
                            <p style="font-size: 0.95rem; line-height: 1.5; margin: 0;">
                                {post.get('summary', '')[:150]}{'...' if len(post.get('summary', '')) > 150 else ''}
                            </p>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    # 더 보기 버튼
                    if st.button(utils.t("read_more"), key=f"btn_guide_{post.get('id')}"):
                        st.session_state["guide_view"] = "detail"
                        st.session_state["guide_post_id"] = post.get('id')
                        st.rerun()
                    
                    st.markdown("<br>", unsafe_allow_html=True)

def render_tab_tour():
    """Render the AI Tour Coordinator tab (Korean mode replacement for Guide)."""
def render_tab_tour():
    """Render the AI Tour Coordinator tab (Korean mode replacement for Guide)."""
def render_tab_tour():
    """Render the AI Tour Coordinator tab (Korean mode replacement for Guide)."""
    # Use constants from utils
    REGION_OPTIONS = utils.REGION_OPTIONS
    REGION_LABEL_TO_KEY = utils.REGION_LABEL_TO_KEY
    TOURS = utils.load_tours()
    
    # Initialize Cart
    if 'my_cart' not in st.session_state:
        st.session_state['my_cart'] = []
    CITY_LINKS = utils.CITY_LINKS
    KLOOK_ALL_TOURS_LINK = utils.KLOOK_ALL_TOURS_LINK
    
    # SEO
    utils.set_page_title(utils.get_seo_title("nav_tour"))
    # Klook 제휴 배너
    render_klook_banner()
    
    utils.render_custom_header(utils.t("tour_title"), level=2)
    st.caption(utils.t("tour_desc"))
    
    # --- 0. 지역 선택 (Region Selector) ---
    selected_region_label = st.pills("떠나시는 여행지를 선택해주세요! 🇹🇭", REGION_OPTIONS, default=REGION_OPTIONS[0], key="tour_region_selector", on_change=lambda: st.session_state.pop("tour_recommendations", None))
    # Label to Key (e.g., "🏙️ 방콕" -> "방콕")
    selected_region = REGION_LABEL_TO_KEY.get(selected_region_label, "방콕")

    # --- 1. 사용자 취향 입력 (Input) ---
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        who_options = ["혼자", "연인/부부", "친구", "가족(아이동반)", "가족(부모님)"]
        who = st.radio(utils.t("tour_who"), who_options, key="tour_who_radio")
    with col2:
        style_options = ["힐링/마사지", "인생샷/사진", "역사/문화", "액티비티/스릴", "맛집/식도락", "야경/로맨틱", "이색체험"]
        style = st.multiselect(utils.t("tour_style"), style_options, default=["인생샷/사진"], key="tour_style_multi")
    
    budget_options = ["가성비(저렴)", "적당함", "럭셔리/프리미엄"]
    budget = st.select_slider(utils.t("tour_budget"), options=budget_options, value="적당함", key="tour_budget_slider")
    
    # --- 2. 추천 버튼 & 결과 (Output) ---
    if st.button(utils.t("tour_find_btn"), use_container_width=True, type="primary", key="tour_find_button"):
        with st.spinner(f"{selected_region} 투어를 분석 중입니다... 🤖"):
            ai_result = utils.recommend_tours(who, style, budget, region=selected_region)
        
        if ai_result and ai_result.get("recommendations"):
            st.session_state["tour_recommendations"] = ai_result["recommendations"]
        else:
            st.session_state["tour_recommendations"] = None
            st.warning("AI 추천을 가져오는데 실패했습니다. 아래 전체 목록에서 직접 선택해주세요!")
    
    # --- 추천 결과 표시 ---
    recs = st.session_state.get("tour_recommendations")
    if recs:
        st.markdown(f"### {utils.t('tour_result_title')}")
        st.markdown("---")
        
        for idx, rec in enumerate(recs):
            tour_name = rec.get("tour_name", "")
            reason = rec.get("reason", "")
            tip = rec.get("tip", "")
            
            # 매칭되는 투어 데이터 찾기
            matched_tour = next((t for t in TOURS if t["name"] == tour_name), None)
            
            if not matched_tour:
                # 부분 매칭 시도
                matched_tour = next((t for t in TOURS if tour_name in t["name"] or t["name"] in tour_name), None)
            
            if matched_tour:
                if idx == 0:
                    rank_emoji = "🏆"
                elif idx == 1:
                    rank_emoji = "🥈"
                elif idx == 2:
                    rank_emoji = "🥉"
                else:
                    rank_emoji = f"{idx + 1}."
                
                c_img, c_info = st.columns([1, 2])
                with c_img:
                    if matched_tour.get("image"):
                        st.image(matched_tour["image"], use_container_width=True)
                with c_info:
                    st.subheader(f"{rank_emoji} {matched_tour['name']}")
                    st.markdown(f"**{utils.t('tour_reason')}:** {reason}")
                    st.info(f"**{utils.t('tour_pros')}:** {matched_tour['pros']}")
                    if tip:
                        st.caption(f"{utils.t('tour_tip')}: {tip}")
                    st.markdown(f"**💰 {matched_tour['price']}**")
                    
                    
                    # Buttons Row
                    b_col1, b_col2 = st.columns(2)
                    with b_col1:
                        st.link_button(
                            utils.t("tour_book_btn"), 
                            matched_tour["link"], 
                            type="primary",
                            use_container_width=True
                        )
                    with b_col2:
                        if matched_tour['id'] in st.session_state['my_cart']:
                            st.button("✅ 담기 완료", disabled=True, key=f"btn_dis_rec_{matched_tour['id']}", use_container_width=True)
                        else:
                            if st.button("➕ 일정에 담기", key=f"btn_add_rec_{matched_tour['id']}", use_container_width=True):
                                st.session_state['my_cart'].append(matched_tour['id'])
                                st.rerun()
                
                st.markdown("---")
            else:
                # AI가 목록에 없는 이름을 반환한 경우
                st.markdown(f"**{rank_emoji if idx == 0 else '🥈'} {tour_name}**")
                st.markdown(f"**{utils.t('tour_reason')}:** {reason}")
                if tip:
                    st.caption(f"{utils.t('tour_tip')}: {tip}")
                st.markdown("---")
    
    # --- 3. 전체 목록 (Fallback) ---
    # Filter tours by region
    region_tours = [t for t in TOURS if t.get('region', '방콕') == selected_region]
    
    with st.expander(f"{selected_region} 투어 전체 목록 ({len(region_tours)}개)"):
        for t in region_tours:
            c1, c2 = st.columns([1, 3])
            with c1:
                if t.get("image"):
                    st.image(t["image"], use_container_width=True)
            with c2:
                st.markdown(f"**[{t['name']}]({t['link']})** — {t['price']}")
                st.caption(t['desc'])
                tags = " · ".join(t.get("type", []))
                st.markdown(f"<span style='color: #888; font-size: 0.8rem;'>🏷️ {tags}</span>", unsafe_allow_html=True)
                
                # Add to Cart Button (Small)
                if t['id'] in st.session_state['my_cart']:
                    st.caption("✅ 내 일정에 담김")
                else:
                    if st.button("➕ 일정에 담기", key=f"btn_add_list_{t['id']}"):
                        st.session_state['my_cart'].append(t['id'])
                        st.rerun()
            st.markdown("---")

    # --- 4. 나만의 자유여행 플래너 (DIY Trip Planner) ---
    st.markdown("---")
    st.header(f"📝 {selected_region} 자유여행 플래너")
    
    if not st.session_state['my_cart']:
        st.info("위 목록에서 마음에 드는 투어를 '담기' 버튼으로 추가해보세요! AI가 일정을 짜드립니다. 🤖")
    else:
        # Cart Items Display
        cart_tours = [t for t in TOURS if t['id'] in st.session_state['my_cart']]
        total_cost = 0
        
        st.markdown("##### 🛒 내 여행 코스")
        for ct in cart_tours:
            cc1, cc2, cc3 = st.columns([3, 1, 1])
            with cc1:
                st.write(f"**{ct['name']}**")
            with cc2:
                st.write(f"{ct['price']}")
                # Parse price for total calculation
                try:
                    import re
                    p_val = int(re.sub(r'[^0-9]', '', ct['price']))
                    total_cost += p_val
                except:
                    pass
            with cc3:
                if st.button("🗑️ 삭제", key=f"btn_del_{ct['id']}"):
                    st.session_state['my_cart'].remove(ct['id'])
                    st.rerun()
        
        st.divider()
        st.markdown(f"#### 💰 총 예상 비용: :orange[{total_cost:,}원]")
        
        # AI Itinerary Generation
        if len(cart_tours) >= 2:
            st.markdown("### 🤖 AI 트래블 메이커")
            if st.button("✨ AI로 최적 동선 & 일정표 만들기", type="primary", use_container_width=True):
                with st.spinner("AI가 최적의 여행 동선을 계산 중입니다... (약 10초 소요)"):
                    itinerary = utils.generate_tour_itinerary(cart_tours, region=selected_region)
                    st.session_state['generated_itinerary'] = itinerary
            
            if 'generated_itinerary' in st.session_state and st.session_state['generated_itinerary']:
                st.success("일정 생성 완료! 아래 타임테이블을 확인하세요.")
                st.markdown(st.session_state['generated_itinerary'])
                
                # Shareable Text Block
                share_text = f"""🇹🇭 [Thai Today] 나만의 {selected_region} 여행 계획

🗓️ 추천 일정:
{st.session_state['generated_itinerary']}

💰 총 예상 비용: {total_cost:,}원
(항공권/숙박 제외, 투어 비용 기준)

👇 예약하러 가기:
https://thai-today.com"""
                
                st.caption("👇 우측 상단 아이콘을 눌러 복사해서 카톡에 붙여넣으세요!")
                st.code(share_text, language=None)
                
                st.markdown("---")
                st.markdown("#### ✅ 예약 확정하러 가기 (Checklist)")
                st.caption("👇 아래 버튼을 눌러 각 상품을 예약하고 여행 준비를 완료하세요!")
                
                for ct in cart_tours:
                    bc1, bc2 = st.columns([3, 1])
                    with bc1:
                        st.write(f"**{ct['name']}** - {ct['price']}")
                    with bc2:
                        st.link_button("👉 예약하기 (Klook)", ct['link'], type="primary", use_container_width=True)
                
                st.divider()
                st.markdown(f"### 💰 총 예상 비용: :orange[{total_cost:,}원]")
        else:
            st.warning("투어를 2개 이상 담으시면 AI가 일정을 짜해드립니다!")
    
    # --- 4. 클룩 전체보기 (항상 표시) ---
    st.markdown("---")
    st.info(utils.t("tour_no_match"))
    
    city_link = CITY_LINKS.get(selected_region, KLOOK_ALL_TOURS_LINK)
    st.link_button(
        f"🌏 {selected_region} 투어 전체보기 (클룩)",
        city_link,
        use_container_width=True
    )

def render_tab_board():
    # SEO: Dynamic page title
    utils.set_page_title(utils.get_seo_title("nav_board"))
    # Klook 제휴 배너
    render_klook_banner()
    st.markdown(f"### {utils.t('board_title')}")
    st.caption(utils.t("board_desc"))
    
    # 1. Notice Section
    st.success("👋 **오늘의 태국**은 여행자를 위한 실시간 정보 앱입니다. 뉴스, 핫플, 이벤트를 한눈에 확인하세요!", icon="📢")
    with st.container():
        col_notice, col_btn = st.columns([4, 1])
        with col_notice:
            st.info("💡 버그 제보, 광고 문의, 기능 제안은 여기로 보내주세요!", icon="📨")
        with col_btn:
            st.link_button("Help" if st.session_state.get('language') == 'English' else "문의하기", "https://forms.gle/B9RTDGJcCR9MnJvv5", width='stretch')

    st.divider()

    # 2. Write Section
    with st.expander(utils.t("write_expander"), expanded=True):
        with st.form("board_write_form", clear_on_submit=True):
            c_nick, c_pw = st.columns(2)
            b_nick = c_nick.text_input(utils.t("nickname"), placeholder="Nickname...")
            b_pw = c_pw.text_input(utils.t("password"), type="password", max_chars=4)
            b_content = st.text_area(utils.t("content"), placeholder="..." if st.session_state.get('language') == 'English' else "욕설, 비방, 광고글은 통보 없이 삭제될 수 있습니다.", height=100)
            
            # [MOD] Secret Post Checkbox
            b_secret = st.checkbox("🔒 비밀글 (작성자와 관리자만 볼 수 있습니다)", key="board_secret")
            
            if st.form_submit_button(utils.t("write_btn"), width='stretch'):
                if not b_content:
                    st.warning("내용을 입력해주세요.")
                elif not b_pw:
                    st.warning("삭제를 위한 비밀번호를 입력해주세요.")
                else:
                    with st.spinner("구글 시트에 저장 중..."):
                        if save_board_post(b_nick, b_content, b_pw, is_secret=b_secret):
                            st.success("게시글이 등록되었습니다!")
                            st.rerun()

    st.markdown("---")

    # 3. Read Section
    board_data = load_board_data()
    
    if not board_data:
        st.info("아직 등록된 글이 없습니다. 첫 번째 글을 남겨보세요!")
    else:
        for i, post in enumerate(board_data):
            with st.container(border=True):
                # Data Mapping: created_at -> date (for display compatibility if needed, using created_at)
                c_date = post.get('created_at', 'Unknown Date')
                c_nick = post.get('nickname', '익명')
                c_content = post.get('content', '')
                
                # Sanitize
                c_nick_safe = html.escape(c_nick) # Escape HTML tags
                c_content_safe = c_content.replace("http://", "https://")

                # Header: Nickname & Date
                st.markdown(f"**{c_nick_safe}** <span style='color:grey; font-size:0.8em'>| {c_date}</span>", unsafe_allow_html=True)
                # Content (Render safely via markdown, replacing http with https)
                # [MOD] Secret Post Logic
                is_secret_val = post.get('is_secret', False)
                if isinstance(is_secret_val, str):
                    is_secret_val = is_secret_val.lower() == 'true'
                
                is_admin = st.session_state.get("password_correct", False)
                
                if is_secret_val:
                    if is_admin:
                        st.markdown(f"🔒 **[비밀글]** {c_content_safe}")
                    else:
                        # Check if unlocked
                        unlock_key = f"board_unlocked_{c_date}" # Use ID as key
                        if st.session_state.get(unlock_key):
                             st.info("🔓 비밀번호 확인됨")
                             st.markdown(c_content_safe)
                        else:
                             with st.expander("🔒 비밀글입니다 (클릭하여 확인)"):
                                  spw = st.text_input("비밀번호", type="password", key=f"secret_pw_{i}")
                                  if st.button("확인", key=f"btn_sec_{i}"):
                                       if str(spw) == str(post.get('password')):
                                            st.session_state[unlock_key] = True
                                            st.rerun()
                                       else:
                                            st.error("비밀번호가 일치하지 않습니다.")
                else:
                    st.markdown(c_content_safe)
                
                # Delete UI (Bottom Right)
                with st.expander("🗑️ " + utils.t("delete_post")):
                    del_pw = st.text_input(utils.t("confirm_pw"), type="password", key=f"del_pw_{i}", max_chars=4)
                    if st.button(utils.t("delete_post"), key=f"btn_del_{i}"):
                        # Use created_at as ID for deletion
                        success, msg = delete_board_post(c_date, del_pw)
                        if success:
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)

# --- Community Board Helpers (Google Sheets) ---
def load_board_data():
    """
    Load data from Google Sheets ('board_db').
    Returns a list of dicts: [{'created_at':..., 'nickname':..., 'content':..., 'password':...}]
    Sorted by 'created_at' descending (Latest first).
    """
    try:
        conn = st.connection("gsheets_board", type=GSheetsConnection)
        df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, ttl=0) # ttl=0 for fresh data
        # Check if df is empty
        if df.empty:
            return []
        
        # Sort by created_at desc
        if 'created_at' in df.columns:
            df = df.sort_values(by='created_at', ascending=False)
            
        return df.to_dict('records')
    except Exception as e:
        if "404" in str(e):
            try:
                sa_email = st.secrets["connections"]["gsheets"]["client_email"]
                st.error(f"🚨 구글 시트('board_db')를 찾을 수 없습니다.\n\n"
                         f"해당 시트가 서비스 계정 이메일(**{sa_email}**)과 공유되어 있는지 확인해주세요.")
            except:
                st.error("🚨 구글 시트('board_db')를 찾을 수 없습니다. 서비스 계정과 공유되었는지 확인해주세요.")
        else:
            st.error(f"게시판 데이터 로드 실패: {e}")
        return []

def save_board_post(nickname, content, password, is_secret=False):
    """
    Append a new row to Google Sheets using Update (Read -> Concat -> Update).
    """
    try:
        conn = st.connection("gsheets_board", type=GSheetsConnection)
        existing_df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, ttl=0)
        
        new_row = pd.DataFrame([{
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "nickname": nickname if nickname else "익명",
            "content": content,
            "password": password,
            "is_secret": is_secret
        }])
        # Concat
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        
        # Update Sheet
        conn.update(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, data=updated_df)
        st.cache_data.clear() # Clear specific data caches if any
        return True
    except Exception as e:
        if "404" in str(e):
             st.error("🚨 구글 시트를 찾을 수 없습니다. (공유 설정 확인 필요)")
        else:
             st.error(f"게시글 저장 실패: {e}")
        return False

def admin_update_board_post(created_at, new_nickname, new_content):
    """
    Admin: Update nickname/content of a post by created_at.
    """
    try:
        conn = st.connection("gsheets_board", type=GSheetsConnection)
        df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, ttl=0)
        
        if df.empty: return False

        # Find row by created_at (string comparison)
        mask = df['created_at'] == str(created_at)
        
        if not df[mask].empty:
            # Update specific row
            df.loc[mask, 'nickname'] = new_nickname
            df.loc[mask, 'content'] = new_content
            
            conn.update(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, data=df)
            st.cache_data.clear()
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"관리자 수정 실패: {e}")
        return False

def delete_board_post(created_at, password):
    """
    Delete a row based on 'created_at' and 'password' match.
    Note: 'created_at' is used as a unique ID here effectively.
    """
    try:
        conn = st.connection("gsheets_board", type=GSheetsConnection)
        df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, ttl=0)
        
        if df.empty:
            return False, "데이터가 없습니다."

        # Find match
        # Ensure string comparison
        df['created_at'] = df['created_at'].astype(str)
        df['password'] = df['password'].astype(str)
        
        mask = (df['created_at'] == str(created_at)) & (df['password'] == str(password))
        
        if not df[mask].empty:
            df = df[~mask] # Remove matched rows
            conn.update(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, data=df)
            st.cache_data.clear()
            return True, "삭제되었습니다."
        else:
            return False, "비밀번호가 일치하지 않거나 이미 삭제된 글입니다."
            
    except Exception as e:
        return False, f"삭제 오류: {e}"

def admin_delete_board_post(created_at):
    """
    Admin delete (no password check).
    """
    try:
        conn = st.connection("gsheets_board", type=GSheetsConnection)
        df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, ttl=0)
        
        if df.empty: return False

        df['created_at'] = df['created_at'].astype(str)
        df = df[df['created_at'] != str(created_at)]
        
        conn.update(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"관리자 삭제 오류: {e}")
        return False

# --- AdSense Injection ---
def inject_adsense():
    adsense_id = st.secrets.get("GOOGLE_ADSENSE_ID", "ca-pub-XXXXXXXXXXXXXXXX")
    if adsense_id == "ca-pub-XXXXXXXXXXXXXXXX":
        pass

    # AdSense Script
    ad_script = f"""
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={adsense_id}"
     crossorigin="anonymous"></script>
    """
    st.components.v1.html(ad_script, height=0)

inject_adsense()

# --- Admin Authentication ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets.get("ADMIN_PASSWORD", "admin"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("관리자 비밀번호", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("관리자 비밀번호", type="password", on_change=password_entered, key="password")
        st.error("😕 비밀번호가 틀렸습니다.")
        return False
    else:
        return True

# --- Main Layout ---

# 0. Global Notice
config_data = load_json(CONFIG_FILE, {"notice": {"enabled": False, "text": ""}})
if config_data.get("notice", {}).get("enabled"):
    st.info(config_data["notice"]["text"], icon="📢")

# Sidebar
st.sidebar.markdown("### 🗂️ 오늘의 태국")

# Mode Selection
# Mode Selection Logic (Secret Door)
app_mode = "Viewer 모드" # Default

# Check query params for admin mode
query_params = st.query_params
if query_params.get("mode") == "admin":
    st.sidebar.markdown("---")
    st.sidebar.caption("🔒 관리자 접근")
    # If password correct, switch mode
    if check_password():
        app_mode = "Admin Console"

if app_mode == "Admin Console":
    # Exit Button
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 관리자 모드 종료", width='stretch'):
        st.query_params.clear()
        st.rerun()

    # Visitor Counter (Hidden in Admin, or optional)

    
    if check_password():
        st.success("관리자 모드 진입 성공") # Debugging: Confirmation
        utils.render_custom_header("🛠️ 통합 운영 관제탑 (Admin Console)", level=1)
        
        # Tabs for better organization
        # Tabs for better organization
        # Main Tab Layout
        # Main Tab Layout
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs(["📊 상태/통계", "✏️ 뉴스 관리", "🛡️ 커뮤니티", "📢 설정/공지", "📡 RSS 관리", "🎉 이벤트/여행", "🏨 호텔 관리", "📘 가이드 관리", "⚙️ 소스 관리", "🌴 매거진 관리", "🎨 인포그래픽", "🎒 투어 관리"])
        
        # --- Tab 1: Stats & Health ---
        with tab1:
            st.subheader("시스템 상태")
            col1, col2 = st.columns(2)
            
            # File Check
            with col1:
                st.markdown("#### 📂 데이터 파일 상태")
                files_to_check = [NEWS_FILE, COMMENTS_FILE, CONFIG_FILE]
                for f in files_to_check:
                    if os.path.exists(f):
                        size = os.path.getsize(f) / 1024 # KB
                        st.markdown(f"- ✅ `{f}`: {size:.2f} KB")
                    else:
                        st.markdown(f"- ❌ `{f}`: 없음")

            # Visitor Stats
            with col2:
                st.markdown("#### 👥 방문자 현황")
                # Visitor Stats (Admin)
                current_total, current_daily = utils.get_visitor_stats()
                st.metric("총 방문자 (API)", f"{current_total:,}명")
                st.metric("오늘 방문자 (API)", f"{current_daily:,}명")

        # --- Tab 2: News Management ---
        with tab2:
            st.subheader("뉴스 데이터 관리")
            
            # Twitter Trend Manual Update
            if st.button("🐦 실시간 트위터 트렌드 업데이트 (Twitter Trends)"):
                with st.spinner("트위터 트렌드 분석 중... (Gemini)"):
                    api_key = os.environ.get("GEMINI_API_KEY")
                    if not api_key:
                        if not gemini_key:
                            # Fallback for local manual config check if global failed (Safety)
                            try:
                                import toml
                                secrets = toml.load(".streamlit/secrets.toml")
                                api_key = secrets.get("GEMINI_API_KEY")
                            except: api_key = None
                    else:
                        api_key = gemini_key
                    
                    if api_key:
                        result = utils.fetch_twitter_trends(api_key)
                        if result:
                            # Save to common file
                            with open('data/twitter_trends.json', 'w', encoding='utf-8') as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                            
                            # Push
                            utils.push_changes_to_github(['data/twitter_trends.json'], "Update Twitter Trends")
                            st.success(f"업데이트 완료: {result.get('topic')}")
                        else:
                            st.warning("특이 사항이 없거나 수집 실패.")
                    else:
                        st.error("API Key Missing")
            
            st.divider()
            try:
                news_data = load_news_data()
            except Exception as e:
                st.error(f"뉴스 로드 실패: {e}")
                news_data = {}

            if not news_data:
                st.warning("등록된 뉴스가 없습니다.")
            else:
                selected_date_edit = st.selectbox("날짜 선택", sorted(news_data.keys(), reverse=True))
                if selected_date_edit:
                    topics = news_data[selected_date_edit]
                    st.write(f"총 {len(topics)}개의 기사")
                    
                    for i, topic in enumerate(topics):
                        with st.expander(f"#{i+1} {topic['title']}"):
                            new_title = st.text_input("제목", topic['title'], key=f"edit_title_{selected_date_edit}_{i}")
                            new_summary = st.text_area("요약", topic['summary'], key=f"edit_sum_{selected_date_edit}_{i}")
                            
                            # Category Editing
                            categories = ["정치/사회", "경제", "여행/관광", "사건/사고", "엔터테인먼트", "기타"]
                            current_cat = topic.get('category', "기타")
                            if current_cat not in categories:
                                categories.append(current_cat) # Keep original if not in list
                            
                            new_category = st.selectbox("카테고리", categories, 
                                                      index=categories.index(current_cat), 
                                                      key=f"edit_cat_{selected_date_edit}_{i}")
                            
                            # Full Text Edit
                            new_full = st.text_area("본문 (Markdown)", topic.get('full_translated',''), height=200, key=f"edit_full_{selected_date_edit}_{i}")

                            col_del, col_save = st.columns([1, 1])
                            if col_save.button("수정 저장", key=f"save_{selected_date_edit}_{i}"):
                                topics[i]['title'] = new_title
                                topics[i]['summary'] = new_summary
                                topics[i]['category'] = new_category
                                topics[i]['full_translated'] = new_full
                                news_data[selected_date_edit] = topics
                                news_data[selected_date_edit] = topics
                                if save_news_to_sheet(news_data):
                                    st.success("데이터베이스(Google Sheets)에 저장되었습니다.")
                                    st.rerun()
                                else:
                                    st.error("저장 실패")
                                
                            if col_del.button("삭제", key=f"del_{selected_date_edit}_{i}"):
                                topics.pop(i)
                                if not topics:
                                    del news_data[selected_date_edit]
                                else:
                                    news_data[selected_date_edit] = topics
                                
                                if save_news_to_sheet(news_data):
                                    st.warning("삭제 후 저장되었습니다.")
                                    st.rerun()
                                else:
                                    st.error("삭제 저장 실패")

        # --- Tab 7: Hotel Management ---
        with tab7:
            st.subheader("호텔 검색 기능 테스트 & 관리")
            
            st.info("Google Places API 및 Gemini 분석을 테스트할 수 있는 공간입니다.")
            
            ac1, ac2 = st.columns([1, 2])
            with ac1:
                admin_city = st.selectbox("도시", ["Bangkok", "Pattaya", "Chiang Mai", "Phuket"], key="admin_city_select")
            with ac2:
                 admin_hotel_query = st.text_input("호텔 검색 테스트 (Admin)", key="admin_hotel_search")
                 
            if st.button("검색 및 분석 테스트", key="admin_hotel_btn"):
                 api_key = google_maps_key
                 if not api_key:
                     st.error("Google Maps API Key 없음")
                 else:
                     candidates = utils.fetch_hotel_candidates(admin_hotel_query, admin_city, api_key)
                     if candidates:
                         st.success(f"검색 성공: {len(candidates)}건")
                         st.json(candidates)
                         
                         # Test with first one for simplicity in Admin
                         info = utils.fetch_hotel_details(candidates[0]['id'], api_key)
                         st.json(info)
                         
                         st.divider()
                         st.info("Gemini 분석 시작...")
                         # Using global gemini_key
                         analysis = utils.analyze_hotel_reviews(info['name'], info['rating'], info['reviews'], gemini_key)
                         st.json(analysis)
            
            st.divider()
            
            # --- 아고다 직통 링크 관리 ---
            st.subheader("🔗 아고다 직통 링크 관리")
            st.info("""
            **사용법:** 호텔 이름(정확히 캐시된 이름)과 아고다 직통 URL을 입력하면 
            Google Sheets에 저장됩니다. 이후 해당 호텔 분석 시 "🚀 바로 예약하기" 버튼이 표시됩니다.
            
            💡 **팁:** 아고다에서 호텔 페이지 URL을 그대로 복사해서 붙여넣으세요. 
            파트너 ID(cid=700591)는 자동으로 추가됩니다!
            """)
            
            col_h, col_u = st.columns([1, 2])
            with col_h:
                agoda_hotel_name = st.text_input("호텔 이름 (캐시된 이름)", key="agoda_hotel_name", placeholder="예: Siam Kempinski Hotel Bangkok")
            with col_u:
                agoda_direct_url = st.text_input("아고다 직통 URL", key="agoda_direct_url", placeholder="https://www.agoda.com/ko-kr/...")
            
            if st.button("💾 직통 링크 저장", key="save_agoda_url"):
                if not agoda_hotel_name or not agoda_direct_url:
                    st.error("호텔 이름과 URL을 모두 입력해주세요.")
                elif not agoda_direct_url.startswith('http'):
                    st.error("올바른 URL 형식이 아닙니다. (http로 시작해야 함)")
                else:
                    with st.spinner("Google Sheets 업데이트 중..."):
                        success = utils.update_hotel_agoda_url(agoda_hotel_name.strip(), agoda_direct_url.strip())
                        if success:
                            st.success(f"✅ '{agoda_hotel_name}' 호텔의 아고다 직통 링크가 저장되었습니다!")
                            st.balloons()
                        else:
                            st.error(f"❌ '{agoda_hotel_name}' 호텔을 찾을 수 없습니다. 정확한 캐시된 이름을 입력해주세요.")
        # --- Tab 3: Community Management ---
        with tab3:
            st.subheader("🛡️ 커뮤니티 관리")
            
            tab3_1, tab3_2 = st.tabs(["💬 뉴스 댓글", "🗣️ 게시판 글"])
            
            with tab3_1:
                st.markdown("#### 뉴스 댓글 관리")
                try:
                    comments_data = get_all_comments()
                except Exception as e:
                    st.error(f"댓글 로드 실패: {e}")
                    comments_data = {"blocked_users": []}

                # List all comments flatly for review
                all_flat_comments = []
                for news_id, com_list in comments_data.items():
                    if news_id == "blocked_users": continue
                    for c in com_list:
                        c['news_id'] = news_id
                        all_flat_comments.append(c)
                
                # Sort by date descending (assuming date string is comparable)
                all_flat_comments.sort(key=lambda x: x.get('date', ''), reverse=True)
                
                if not all_flat_comments:
                    st.info("작성된 댓글이 없습니다.")
                else:
                    for idx, c in enumerate(all_flat_comments[:20]): # Show last 20
                        with st.container(border=True):
                            st.markdown(f"**{c['user']}**: {c['text']}")
                            st.caption(f"{c['date']} | ID: {c['news_id']}")
                            if st.button("삭제", key=f"adm_del_com_{idx}"):
                                # Logic to Delete
                                original_list = comments_data[c['news_id']]
                                # Find index in original list to delete
                                # Simple match by text and date
                                for i, orig in enumerate(original_list):
                                    if orig['text'] == c['text'] and orig['date'] == c['date']:
                                        original_list.pop(i)
                                        break
                                save_json(COMMENTS_FILE, comments_data)
                                st.success("삭제됨")
                                st.rerun()

            with tab3_2:
                st.markdown("#### 자유게시판 글 관리")
                board_posts = load_board_data()
                if not board_posts:
                    st.info("게시글이 없습니다.")
                else:
                    for i, post in enumerate(board_posts):
                        # Unique Key using created_at
                        unique_key = post.get('created_at', str(i))
                        
                        # Use Expander for Edit Mode
                        with st.expander(f"📝 {post['nickname']} - {unique_key}"):
                            # Verify created_at is valid for logic
                            if 'created_at' not in post:
                                st.warning("⚠️ 날짜 정보(ID)가 없는 게시물입니다.")
                                
                            edit_nick = st.text_input("닉네임", post['nickname'], key=f"adm_nick_{i}")
                            edit_content = st.text_area("내용", post['content'], height=150, key=f"adm_cont_{i}")
                            
                            c1, c2 = st.columns([1, 1])
                            with c1:
                                if st.button("수정 저장", key=f"adm_save_{i}"):
                                    if admin_update_board_post(unique_key, edit_nick, edit_content):
                                        st.success("수정되었습니다.")
                                        st.rerun()
                            with c2:
                                if st.button("삭제 🗑️", key=f"adm_bd_del_{i}"):
                                    if admin_delete_board_post(unique_key):
                                        st.success("삭제되었습니다.")
                                        st.rerun()

        # --- Tab 4: Settings ---
        with tab4:
            st.subheader("전역 공지 설정")
            current_config = load_json(CONFIG_FILE, {"notice": {"enabled": False, "text": ""}})
            
            with st.form("notice_form"):
                enable_notice = st.checkbox("공지 노출 켜기", value=current_config.get("notice", {}).get("enabled", False))
                notice_text = st.text_input("공지 내용", value=current_config.get("notice", {}).get("text", ""))
                
                if st.form_submit_button("설정 저장"):
                    current_config["notice"] = {"enabled": enable_notice, "text": notice_text}
                    save_json(CONFIG_FILE, current_config)
                    st.success("설정이 저장되었습니다.")
                    st.rerun()

        # --- Tab 5: RSS Management ---
        with tab5:
            st.subheader("RSS 피드 관리")
            st.info("뉴스 수집 대상이 되는 RSS 피드 목록입니다. (feeds.json)")
            
            feeds_file = 'data/feeds.json'
            current_feeds = load_json(feeds_file, [])
            
            # 1. Add New Feed
            with st.form("add_feed_form"):
                new_feed_url = st.text_input("새로운 RSS URL 추가", placeholder="https://example.com/rss")
                if st.form_submit_button("추가"):
                    if new_feed_url:
                        if new_feed_url not in current_feeds:
                            current_feeds.append(new_feed_url)
                            save_json(feeds_file, current_feeds)
                            st.success(f"추가되었습니다: {new_feed_url}")
                            st.rerun()
                        else:
                            st.warning("이미 존재하는 URL입니다.")
                    else:
                        st.warning("URL을 입력해주세요.")
            
            st.divider()
            
            # 2. List & Delete Feeds
            if not current_feeds:
                st.warning("등록된 RSS 피드가 없습니다.")
            else:
                st.write(f"총 {len(current_feeds)}개의 피드")
                for idx, url in enumerate(current_feeds):
                    col_url, col_del = st.columns([4, 1])
                    with col_url:
                        st.code(url, language="text")
                    with col_del:
                        if st.button("삭제", key=f"del_feed_{idx}"):
                            current_feeds.pop(idx)
                            save_json(feeds_file, current_feeds)
                            st.success("삭제되었습니다.")
                            st.rerun()

        # --- Tab 6: Event Management ---
        with tab6:
            st.subheader("이벤트 & 여행 정보 관리")

            # 6-A. General Events (events.json)
            st.markdown("### 1. 일반 이벤트 관리 (events.json)")
            events_data = load_json(EVENTS_FILE, [])

            # --- AI Auto Registration (General) ---
            with st.expander("🔗 AI 일반 이벤트 등록 (URL 분석)", expanded=True):
                st.caption("뉴스 기사, 티켓멜론 등 URL을 입력하면 자동으로 정보를 추출합니다.")
                gen_url = st.text_input("일반 이벤트 URL", placeholder="https://...", key="gen_event_url")
                
                if st.button("✨ 분석 및 일반 등록", key="btn_gen_ai"):
                    if not gen_url:
                        st.error("URL을 입력해주세요.")
                    else:
                        with st.spinner("AI가 분석 중입니다..."):
                            api_key = os.environ.get("GEMINI_API_KEY")
                            if not api_key:
                                try:
                                    import toml
                                    secrets = toml.load(".streamlit/secrets.toml")
                                    api_key = secrets.get("GEMINI_API_KEY")
                                except: pass
                            
                            if api_key:
                                new_data, err = utils.extract_event_from_url(gen_url, api_key)
                                if err:
                                    st.error(f"오류: {err}")
                                elif new_data:
                                    # Ensure defaults for General Events
                                    if not new_data.get('type'): new_data['type'] = '기타'
                                    if not new_data.get('region'): new_data['region'] = '기타'
                                    
                                    events_data.insert(0, new_data)
                                    save_json(EVENTS_FILE, events_data)
                                    st.success(f"추가 성공! [{new_data['title']}]")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("데이터 추출 실패")
                            else:
                                st.error("API 키 없음")
            if not events_data:
                st.warning("등록된 일반 이벤트가 없습니다.")
            else:
                st.info(f"총 {len(events_data)}개의 일반 이벤트/핫이슈가 있습니다.")
                
                # Filter/Search for Admin
                filter_txt = st.text_input("이벤트 검색", key="evt_search")
                filtered_evts = [e for e in events_data if filter_txt.lower() in e.get('title','').lower()] if filter_txt else events_data

                for i, evt in enumerate(filtered_evts[:30]): # Cap at 30 for perf
                    with st.expander(f"{evt.get('title')} ({evt.get('date')})"):
                        c1, c2 = st.columns([3,1])
                        with c1:
                            new_title = st.text_input("제목", evt.get('title'), key=f"evt_t_{i}")
                            new_date = st.text_input("날짜", evt.get('date'), key=f"evt_d_{i}")
                            new_booking = st.text_input("예매일", evt.get('booking_date',''), key=f"evt_bd_{i}")
                            new_price = st.text_input("가격", evt.get('price',''), key=f"evt_pr_{i}")
                            new_loc = st.text_input("장소", evt.get('location'), key=f"evt_l_{i}")
                            new_type = st.text_input("타입", evt.get('type','기타'), key=f"evt_ty_{i}")
                            
                            if st.button("수정 저장", key=f"evt_save_{i}"):
                                evt['title'] = new_title
                                evt['date'] = new_date
                                evt['booking_date'] = new_booking
                                evt['price'] = new_price
                                evt['location'] = new_loc
                                evt['type'] = new_type
                                save_json(EVENTS_FILE, events_data) # Check if we need to map back to original index if filtered. 
                                # Actually filtered_evts contains references to dicts in events_data, so modding evt works.
                                st.success("저장됨")
                        
                        with c2:
                            st.error("삭제 주의")
                            if st.button("삭제 ❌", key=f"evt_del_{i}"):
                                events_data.remove(evt) # Remove object by ref
                                save_json(EVENTS_FILE, events_data)
                                st.success("삭제됨")
                                st.rerun()

            st.divider()

            # 6-B. Big Match (big_events.json)
            st.markdown("### 2. 빅매치/페스티벌 관리 (big_events.json)")
            big_events_data = load_json(BIG_EVENTS_FILE, [])

            st.markdown("### 2. 빅매치/페스티벌 관리 (big_events.json)")
            big_events_data = load_json(BIG_EVENTS_FILE, [])

            # --- Keyword Auto Crawler (New) ---
            with st.expander("🤖 키워드 기반 자동 수집 (Beta)", expanded=False):
                st.caption("구글 뉴스에서 초대형 페스티벌 정보를 자동으로 찾습니다.")
                
                
                # Load Keywords from sources.json (Robust Loading)
                SOURCES_FILE = 'data/sources.json'
                
                # Default fallback
                default_keywords = [
                    "Rolling Loud Thailand 2026",
                    "Tomorrowland Thailand",
                    "Summer Sonic Bangkok", 
                    "Creamfields Thailand",
                    "Songkran Festival 2026"
                ]

                # Try loading custom sources
                if os.path.exists(SOURCES_FILE):
                     try:
                         with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                             s_data = json.load(f)
                             if s_data.get('event_keywords'):
                                 # Use enabled keywords
                                 custom_kws = [k['keyword'] for k in s_data['event_keywords'] if k.get('enabled', True)]
                                 if custom_kws:
                                     default_keywords = custom_kws
                     except: pass
                
                kw_input = st.text_area("수집 키워드 (줄바꿈으로 구분)", value="\n".join(default_keywords), height=100)
                kw_list = [k.strip() for k in kw_input.split('\n') if k.strip()]
                
                if st.button("🚀 키워드 기반 정보 업데이트 (30초 소요)"):
                    with st.spinner(f"{len(kw_list)}개 키워드로 정보를 수집 중입니다..."):
                        api_key = os.environ.get("GEMINI_API_KEY")
                        if not api_key:
                            try:
                                import toml
                                secrets = toml.load(".streamlit/secrets.toml")
                                api_key = secrets.get("GEMINI_API_KEY")
                            except: pass
                        
                        if not api_key:
                            st.error("API Key Not Found")
                        else:
                            found_items = utils.fetch_big_events_by_keywords(kw_list, api_key)
                            
                            new_count = 0
                            for item in found_items:
                                # Check duplicate (Simple Title Check)
                                if not any(existing.get('title') == item.get('title') for existing in big_events_data):
                                    item['source'] = 'auto' # Mark as auto-crawled
                                    big_events_data.insert(0, item)
                                    new_count += 1
                            
                            save_json(BIG_EVENTS_FILE, big_events_data)
                            
                            if new_count > 0:
                                st.success(f"{new_count}개의 새로운 이벤트를 발견하여 추가했습니다!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.info("새로운 정보를 찾지 못했습니다. (이미 등록됨 or 정보 없음)")

            # --- AI Auto Registration (New) ---
            with st.expander("🔗 AI 자동 등록 (URL 분석)", expanded=True):
                st.caption("링크만 넣으면 AI가 정보를 추출해서 등록합니다. (Ticketmelon, 뉴스, 페북 등)")
                analyze_url = st.text_input("이벤트 페이지 URL", placeholder="https://...")
                
                if st.button("✨ 분석 및 등록"):
                    if not analyze_url:
                        st.error("URL을 입력해주세요.")
                    else:
                        with st.spinner("AI가 페이지를 분석 중입니다... (약 5-10초)"):
                            api_key = os.environ.get("GEMINI_API_KEY")
                            if not api_key:
                                # Fallback secrets
                                try:
                                    import toml
                                    secrets = toml.load(".streamlit/secrets.toml")
                                    api_key = secrets.get("GEMINI_API_KEY")
                                except: pass
                            
                            if not api_key:
                                st.error("API 키가 없습니다.")
                            else:
                                new_event_data, err = utils.extract_event_from_url(analyze_url, api_key)
                                if err:
                                    st.error(f"분석 실패: {err}")
                                elif new_event_data:
                                    # Append to list
                                    new_event_data['source'] = 'manual' # AI-extracted but User initiated = Manual
                                    big_events_data.insert(0, new_event_data)
                                    save_json(BIG_EVENTS_FILE, big_events_data)
                                    
                                    # Persistence
                                    with st.spinner("GitHub에 저장 중..."):
                                        ok, msg = utils.push_changes_to_github([BIG_EVENTS_FILE], f"Add Big Event (AI): {new_event_data.get('title')}")
                                        if ok: st.toast("✅ GitHub 저장 완료")
                                        else: st.error(f"GitHub 저장 실패: {msg}")

                                    st.success(f"✅ 등록 성공! [{new_event_data.get('title')}]")
                                    st.rerun()
                                else:
                                    st.error("데이터를 추출하지 못했습니다.")

            # --- Manual Add ---
            with st.expander("➕ 수동 등록"):
                with st.form("add_big_event"):
                    n_title = st.text_input("행사명")
                    n_date = st.text_input("날짜 (YYYY-MM-DD or 2026 (미정))")
                    n_loc = st.text_input("장소")
                    n_booking = st.text_input("예매일")
                    n_price = st.text_input("가격")
                    n_status = st.text_input("상태 (예: 티켓오픈, 개최확정, D-100)")
                    n_link = st.text_input("링크", value="#")
                    n_img = st.text_input("이미지 URL")
                    n_desc = st.text_input("설명")
                    
                    if st.form_submit_button("추가"):
                        new_item = {
                            "title": n_title, "date": n_date, "location": n_loc,
                            "booking_date": n_booking, "price": n_price,
                            "status": n_status, "link": n_link, "image_url": n_img,
                            "description": n_desc,
                            "source": "manual" # Explicitly Manual
                        }
                        big_events_data.insert(0, new_item)
                        save_json(BIG_EVENTS_FILE, big_events_data)
                        
                        # Persistence
                        with st.spinner("GitHub에 저장 중..."):
                            ok, msg = utils.push_changes_to_github([BIG_EVENTS_FILE], f"Add Big Event: {n_title}")
                            if ok: st.toast("✅ GitHub 저장 완료")
                            else: st.error(f"GitHub 저장 실패: {msg}")

                        st.success("추가되었습니다.")
                        st.rerun()
            
            # List Existing
            for i, be in enumerate(big_events_data):
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.markdown(f"#### {be.get('title')}")
                        e_title = st.text_input("행사명", be.get('title'), key=f"be_t_{i}")
                        e_date = st.text_input("날짜", be.get('date'), key=f"be_d_{i}")
                        e_booking = st.text_input("예매일", be.get('booking_date',''), key=f"be_bd_{i}")
                        e_price = st.text_input("가격", be.get('price',''), key=f"be_pr_{i}")
                        e_status = st.text_input("상태", be.get('status'), key=f"be_s_{i}")
                        e_img = st.text_input("이미지 URL", be.get('image_url', ''), key=f"be_img_{i}")
                        if e_img: st.image(e_img, width=150)
                        
                        if st.button("변경 저장", key=f"be_save_{i}"):
                           be['title'] = e_title
                           be['date'] = e_date
                           be['booking_date'] = e_booking
                           be['price'] = e_price
                           be['status'] = e_status
                           be['image_url'] = e_img
                           save_json(BIG_EVENTS_FILE, big_events_data)
                           
                           # Persistence
                           with st.spinner("GitHub에 저장 중..."):
                               ok, msg = utils.push_changes_to_github([BIG_EVENTS_FILE], f"Update Big Event: {e_title}")
                               if ok: st.toast("✅ GitHub 저장 완료")
                               else: st.error(f"GitHub 저장 실패: {msg}")

                           st.success("저장됨")
                    
                    with c2:
                        if be.get('image_url'):
                             st.image(be['image_url'], width='stretch')
                        if st.button("삭제", key=f"be_del_{i}"):
                            big_events_data.pop(i)
                            save_json(BIG_EVENTS_FILE, big_events_data)
                            
                            # Persistence
                            with st.spinner("GitHub에 저장 중..."):
                                ok, msg = utils.push_changes_to_github([BIG_EVENTS_FILE], f"Delete Big Event Index {i}")
                                if ok: st.toast("✅ GitHub 저장 완료")
                                else: st.error(f"GitHub 저장 실패: {msg}")

                            st.rerun()
            
            st.divider()
            if st.button("🗑️ 빅매치 데이터 전체 초기화 (Reset)", type="primary"):
                save_json(BIG_EVENTS_FILE, [])
                
                # Persistence
                with st.spinner("GitHub에 저장 중..."):
                    ok, msg = utils.push_changes_to_github([BIG_EVENTS_FILE], "Reset Big Events")
                    if ok: st.toast("✅ GitHub 저장 완료")
                    else: st.error(f"GitHub 저장 실패: {msg}")

                st.warning("초기화되었습니다.")
                st.rerun()

            # --- Taxi Fare Test ---
            st.divider()
            st.markdown("### 🚖 교통비 로직 테스트 (Taxi Fare)")
            st.info("구글 맵 API와 요금 계산 로직을 테스트합니다.")
            
            t_col1, t_col2 = st.columns(2)
            t_origin = t_col1.text_input("출발지 (From)", value="BKK Airport", key="adm_taxi_orig")
            t_dest = t_col2.text_input("도착지 (To)", value="Asok", key="adm_taxi_dest")
            
            if st.button("계산 테스트 실행", key="adm_taxi_calc"):
                api_key = google_maps_key
                if not api_key: st.error("No API Key")
                else:
                    dist, dur, err = utils.get_route_estimates(t_origin, t_dest, api_key)
                    if err: st.error(err)
                    else:
                        st.write(f"거리: {dist}km, 시간: {dur}분")
                        base, fares, is_rh = utils.calculate_expert_fare(dist, dur)
                        st.json(fares)
                        st.write(f"Base Meter: {base} | Rush Hour: {is_rh}")

        # --- Tab 10: Magazine (Trend Hunter) Management ---
        with tab10:
            st.subheader("🌴 핫플 매거진 관리 (트렌드 헌터)")
            st.info("4대 소스(Wongnai, TSL, Chillpainai, BK Mag)에서 수집된 트렌드 정보를 관리합니다.")
            
            # File
            MAGAZINE_FILE = 'data/magazine_content.json'
            
            # 1. Manual Fetch
            col_m1, col_m2 = st.columns([1, 4])
            with col_m1:
                if st.button("🚀 최신 트렌드 수집 (Update)", type="primary"):
                    with st.spinner("최신 정보를 수집하고 분석 중입니다... (약 30초 소요)"):
                        api_key = os.environ.get("GEMINI_API_KEY")
                        if not api_key:
                             # Try secrets
                             try:
                                import toml
                                secrets = toml.load(".streamlit/secrets.toml")
                                api_key = secrets.get("GEMINI_API_KEY")
                             except: pass
                        
                        if api_key:
                            # Load existing for deduplication context
                            existing_items = load_json(MAGAZINE_FILE, [])
                            existing_links = [item['link'] for item in existing_items if item.get('link')]
                            
                            new_items = utils.fetch_trend_hunter_items(api_key, existing_links=existing_links)
                            
                            if new_items:
                                # Safe Merge: Load existing -> Append -> Deduplicate
                                item_map = {item['link']: item for item in existing_items if item.get('link')}
                                for item in new_items:
                                    if item.get('link'):
                                        item_map[item['link']] = item 
                                
                                merged_list = list(item_map.values())
                                import random
                                random.shuffle(merged_list)
                                
                                save_json(MAGAZINE_FILE, merged_list)
                                
                                # Persistence
                                with st.spinner("GitHub에 저장 중..."):
                                    ok, msg = utils.push_changes_to_github([MAGAZINE_FILE], "Update Magazine Content (AI)")
                                    if ok: st.toast("✅ GitHub 저장 완료")
                                    else: st.error(f"GitHub 저장 실패: {msg}")

                                st.success(f"업데이트 완료! (신규 {len(new_items)}개 추가, 총 {len(merged_list)}개)")
                                st.rerun()
                            else:
                                st.error("새로운 데이터를 가져오지 못했습니다. (RSS 응답 없음)")
                        else:
                            st.error("API Key Missing")

            st.markdown("---")
            
            # 2. Manage Existing Items (CRUD)
            st.subheader("📋 매거진 콘텐츠 편집/삭제")
            
            mag_items = load_json(MAGAZINE_FILE, [])
            
            if not mag_items:
                st.info("등록된 매거진 콘텐츠가 없습니다.")
            else:
                for i, item in enumerate(mag_items):
                    with st.expander(f"#{i+1} {item.get('catchy_headline', item.get('title', 'No Title'))}"):
                        with st.form(key=f"mag_form_{i}"):
                            c1, c2 = st.columns([1, 1])
                            m_title = c1.text_input("제목 (Title)", item.get('title', ''))
                            m_headline = c2.text_input("헤드라인 (Catchy)", item.get('catchy_headline', ''))
                            
                            m_summary = st.text_area("요약 (Summary)", item.get('summary', ''), height=100)
                            
                            c3, c4 = st.columns(2)
                            m_tags = c3.text_input("태그 (쉼표로 구분)", ", ".join(item.get('vibe_tags', [])))
                            m_badge = c4.text_input("뱃지 (예: [맛집랭킹])", item.get('badge', ''))
                            
                            c5, c6 = st.columns(2)
                            m_must = c5.text_input("추천 메뉴 (Must Eat)", item.get('must_eat', ''))
                            m_price = c6.text_input("가격대 (Price)", item.get('price_level', ''))
                            
                            m_tip = st.text_input("꿀팁 (Pro Tip)", item.get('pro_tip', ''))
                            m_img = st.text_input("이미지 URL", item.get('image_url', ''))
                            if m_img: st.image(m_img, width=200)
                            
                            m_link = st.text_input("원본 링크", item.get('link', ''))

                            # Actions
                            col_save, col_del = st.columns([1, 5])
                            saved = col_save.form_submit_button("💾 저장")
                            
                            if saved:
                                mag_items[i]['title'] = m_title
                                mag_items[i]['catchy_headline'] = m_headline
                                mag_items[i]['summary'] = m_summary
                                mag_items[i]['vibe_tags'] = [t.strip() for t in m_tags.split(",") if t.strip()]
                                mag_items[i]['badge'] = m_badge
                                mag_items[i]['must_eat'] = m_must
                                mag_items[i]['price_level'] = m_price
                                mag_items[i]['pro_tip'] = m_tip
                                mag_items[i]['image_url'] = m_img
                                mag_items[i]['link'] = m_link
                                
                                save_json(MAGAZINE_FILE, mag_items)
                                
                                with st.spinner("GitHub에 저장 중..."):
                                    ok, msg = utils.push_changes_to_github([MAGAZINE_FILE], f"Edit Magazine Item #{i}")
                                    if ok: st.toast("✅ 저장 완료")
                                
                                st.rerun()

                        # Delete Button (Outside Form to avoid validation issues)
                        if st.button("🗑️ 삭제", key=f"del_mag_{i}"):
                            mag_items.pop(i)
                            save_json(MAGAZINE_FILE, mag_items)
                            
                            with st.spinner("삭제 후 GitHub 반영 중..."):
                                ok, msg = utils.push_changes_to_github([MAGAZINE_FILE], f"Delete Magazine Item #{i}")
                                if ok: st.toast("✅ 삭제 완료")
                            
                            st.rerun()


        # --- Tab 8: Blog/Guide Management ---
        with tab8:
            st.subheader("📘 여행 가이드 관리")
            st.info("블로그 글을 작성하고 수정할 수 있습니다. Google Sheets의 'blog_posts' 시트에 저장됩니다.")
            
            blog_mode = st.radio("모드 선택", ["📝 새 글 작성", "✏️ 기존 글 수정/삭제"], horizontal=True, key="admin_blog_mode")
            
            if blog_mode == "📝 새 글 작성":
                st.markdown("#### 📝 새 여행 가이드 작성")
                
                with st.form("new_blog_form"):
                    pass
                    import uuid
                    
                    new_id = str(uuid.uuid4())[:8]
                    new_date = st.date_input("📅 게시일", value=datetime.now())
                    new_title = st.text_input("📌 제목", placeholder="예: 방콕 카오산로드 완벽 가이드")
                    new_summary = st.text_area("📋 요약 (리스트에 표시됨)", height=80, placeholder="2-3줄로 핵심 내용 요약")
                    new_image = st.text_input("🖼️ 대표 이미지 URL", placeholder="https://...")
                    new_content = st.text_area("📝 본문 (Markdown 지원)", height=300, placeholder="## 소제목\n\n본문 내용...")
                    new_author = st.text_input("✍️ 작성자", value="관리자")
                    
                    submitted = st.form_submit_button("💾 저장하기")
                    
                    if submitted:
                        if not new_title:
                            st.error("제목을 입력해주세요.")
                        else:
                            post_data = {
                                "id": new_id,
                                "date": new_date.strftime("%Y-%m-%d"),
                                "title": new_title,
                                "summary": new_summary,
                                "content": new_content,
                                "image_url": new_image,
                                "author": new_author
                            }
                            success = utils.save_blog_post(post_data)
                            if success:
                                st.success(f"✅ 글이 저장되었습니다! (ID: {new_id})")
                                st.balloons()
                            else:
                                st.error("❌ 저장 실패. Google Sheets 연결을 확인해주세요.")
            
            else:  # 수정/삭제 모드
                st.markdown("#### ✏️ 기존 글 수정/삭제")
                
                # 기존 글 목록 가져오기
                existing_posts = utils.fetch_blog_posts()
                
                if not existing_posts:
                    st.warning("📭 등록된 글이 없습니다. 먼저 글을 작성해주세요.")
                else:
                    # Selectbox로 글 선택
                    post_options = {f"{p.get('title', 'No Title')} ({p.get('date', '')})": p for p in existing_posts}
                    selected_title = st.selectbox("수정할 글 선택", list(post_options.keys()))
                    selected_post = post_options[selected_title]
                    
                    st.divider()
                    
                    with st.form("edit_blog_form"):
                        edit_id = selected_post.get('id', '')
                        edit_date = st.text_input("📅 게시일", value=selected_post.get('date', ''))
                        edit_title = st.text_input("📌 제목", value=selected_post.get('title', ''))
                        edit_summary = st.text_area("📋 요약", value=selected_post.get('summary', ''), height=80)
                        edit_image = st.text_input("🖼️ 이미지 URL", value=selected_post.get('image_url', ''))
                        edit_content = st.text_area("📝 본문", value=selected_post.get('content', ''), height=300)
                        edit_author = st.text_input("✍️ 작성자", value=selected_post.get('author', '관리자'))
                        
                        col_save, col_del = st.columns(2)
                        with col_save:
                            save_btn = st.form_submit_button("💾 수정 저장")
                        with col_del:
                            delete_btn = st.form_submit_button("🗑️ 삭제", type="secondary")
                        
                        if save_btn:
                            post_data = {
                                "id": edit_id,
                                "date": edit_date,
                                "title": edit_title,
                                "summary": edit_summary,
                                "content": edit_content,
                                "image_url": edit_image,
                                "author": edit_author
                            }
                            success = utils.save_blog_post(post_data)
                            if success:
                                st.success("✅ 수정되었습니다!")
                            else:
                                st.error("❌ 수정 실패")
                        
                        if delete_btn:
                            success = utils.delete_blog_post(edit_id)
                            if success:
                                st.success("✅ 삭제되었습니다!")
                                st.rerun()
                            else:
                                st.error("❌ 삭제 실패")

        # --- Tab 9: Source Manager ---
        with tab9:
            st.subheader("⚙️ 크롤링 소스 관리 (Source Manager)")
            st.info("크롤링 대상 사이트와 검색 키워드를 관리합니다. 변경 후 반드시 '저장' 버튼을 눌러주세요.")
            
            SOURCES_FILE = 'data/sources.json'
            sources_data = load_json(SOURCES_FILE)
            
            if not sources_data:
                sources_data = {"magazine_targets": [], "event_keywords": []}
                
            # 1. Magazine Targets
            st.markdown("#### 1. 🌴 매거진 타겟 (Magazine Targets)")
            st.caption("활성화(Enabled)된 소스만 '매거진 수집' 시 크롤링합니다.")
            
            mag_df = pd.DataFrame(sources_data.get('magazine_targets', []))
            
            # Configure Column Config
            mag_edited = st.data_editor(
                mag_df,
                num_rows="dynamic",
                column_config={
                    "enabled": st.column_config.CheckboxColumn("활성", default=True),
                    "name": st.column_config.TextColumn("표시명", required=True),
                    "domain": st.column_config.TextColumn("도메인 (Domain)", required=True),
                    "tag": st.column_config.TextColumn("태그 (Badge)", required=True),
                },
                width='stretch',
                key="editor_magazine"
            )
            
            st.divider()
            
            # 2. Event Keywords
            st.markdown("#### 2. 🎉 빅매치/이벤트 키워드 (Event Keywords)")
            st.caption("여기서 '활성' 체크된 키워드들이 '이벤트 수집' 시 기본값으로 사용됩니다.")
            
            evt_df = pd.DataFrame(sources_data.get('event_keywords', []))
            
            evt_edited = st.data_editor(
                evt_df,
                num_rows="dynamic",
                column_config={
                    "enabled": st.column_config.CheckboxColumn("활성", default=True),
                    "keyword": st.column_config.TextColumn("검색 키워드", required=True),
                    "category": st.column_config.SelectboxColumn("분류", options=["Concert", "Festival", "Exhibition", "Sports"], required=True),
                },
                width='stretch',
                key="editor_events"
            )
            
            st.markdown("---")
            
            # Save Button
            if st.button("💾 변경사항 저장 (Save Changes)", type="primary"):
                # Convert DF back to list of dicts
                updated_mag = mag_edited.to_dict(orient="records")
                updated_evt = evt_edited.to_dict(orient="records")
                
                new_sources = {
                    "magazine_targets": updated_mag,
                    "event_keywords": updated_evt
                }
                
                save_json(SOURCES_FILE, new_sources)
                
                # Persistence
                with st.spinner("GitHub에 저장 중..."):
                    ok, msg = utils.push_changes_to_github([SOURCES_FILE], "Update Crawling Sources")
                    if ok: st.toast("✅ 설정이 저장 및 동기화되었습니다.")
                    else: st.error(f"저장 실패: {msg}")
                
                st.rerun()
        

        # --- Tab 11: Infographic ---
        with tab11:
            st.subheader("🎨 오늘의 뉴스 인포그래픽 생성")
            st.info("오늘 수집된 뉴스를 바탕으로 인스타그램용 요약 이미지를 생성합니다.")
            
            # Load News Data
            news_data = load_news_data()
            avail_dates = sorted(news_data.keys(), reverse=True)
            if not avail_dates:
                st.warning("데이터 없음")
            else:
                target_date = st.selectbox("날짜 선택 (인포그래픽)", avail_dates)
                items = news_data[target_date]
                
                # 2. Preview Groups
                st.write(f"총 {len(items)}개 기사 로드됨.")
                
                if st.button("이미지 생성 시작 (PIL + Gemini)", type="primary"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Grouping
                    groups = {}
                    for item in items:
                        cat = item.get('category', '기타')
                        if cat not in groups: groups[cat] = []
                        groups[cat].append(item)
                    
                    generated_images = []
                    
                    # Generate
                    api_key = gemini_key
                    total_cats = len(groups)
                    
                    cols = st.columns(3)
                    
                    import io
                    import zipfile
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for idx, (cat, cat_items) in enumerate(groups.items()):
                            status_text.text(f"Generating {cat}...")
                            img = utils.generate_category_infographic(cat, cat_items, target_date, api_key)
                            
                            if img:
                                # Save to Buffer for ZIP
                                img_bytes = io.BytesIO()
                                img.save(img_bytes, format='PNG')
                                img_bytes.seek(0)
                                filename = f"{target_date}_{cat}.png"
                                zf.writestr(filename, img_bytes.getvalue())
                                
                                generated_images.append(cat) # Track success
                                
                                # Display
                                with cols[idx % 3]:
                                    st.image(img, caption=cat)
                                
                            progress_bar.progress((idx + 1) / total_cats)
                    
                    status_text.text("완료!")
                    
                    # Fix: Ensure buffer is ready for reading
                    zip_buffer.seek(0)
                    
                    if not generated_images:
                        st.warning("⚠️ 생성된 이미지가 없습니다. 뉴스가 충분하지 않거나 오류가 발생했을 수 있습니다.")
                    else:
                        st.success(f"총 {len(generated_images)}장의 인포그래픽이 생성되었습니다!")
                        # Download Button
                        st.download_button(
                            label="📦 전체 이미지 다운로드 (ZIP)",
                            data=zip_buffer,
                            file_name=f"infographics_{target_date}.zip",
                            mime="application/zip"
                        )

        # --- Tab 12: Tour Management (New) ---
        with tab12:
            st.subheader("🎒 투어 상품 데이터 관리")
            st.info("데이터는 `data/tours.json` 파일에 저장됩니다.")
            
            try:
                TOURS = utils.load_tours()
                REGION_OPTIONS = utils.REGION_OPTIONS
                import json
                import pandas as pd
                import time

                # 1. 목록 보기
                st.markdown("#### 📋 등록된 투어 목록")
                if TOURS:
                    df_tours = pd.DataFrame(TOURS)
                    st.dataframe(df_tours[['id', 'name', 'price', 'type']], use_container_width=True)
                else:
                    st.info("등록된 투어가 없습니다.")
                
                # 2. 추가/수정/삭제
                st.markdown("---")
                tour_action = st.radio("작업 선택", ["➕ 새 투어 추가", "✏️ 기존 투어 수정", "🗑️ 투어 삭제 (ID)"], horizontal=True, key="admin_tour_action")
                
                if tour_action == "➕ 새 투어 추가":
                    with st.form("add_tour_form"):
                        new_id = max([t['id'] for t in TOURS]) + 1 if TOURS else 1
                        st.caption(f"새 투어 ID: {new_id} (자동 생성)")
                        
                        n_region = st.selectbox("지역 (필수)", REGION_OPTIONS) # [NEW]
                        n_name = st.text_input("투어명")
                        n_price = st.text_input("가격 (예: 약 50,000원)")
                        n_link = st.text_input("Klook 링크")
                        n_image = st.text_input("이미지 URL")
                        n_type = st.text_input("태그 (콤마로 구분, 예: 역사,야경)")
                        n_desc = st.text_area("설명")
                        n_pros = st.text_input("장점/특징")
                        
                        if st.form_submit_button("저장"):
                            new_tour = {
                                "id": new_id,
                                "region": n_region.split(" ", 1)[1], # [NEW]
                                "name": n_name,
                                "type": [t.strip() for t in n_type.split(",") if t.strip()],
                                "price": n_price,
                                "desc": n_desc,
                                "pros": n_pros,
                                "link": n_link,
                                "image": n_image
                            }
                            TOURS.append(new_tour)
                            
                            # Save via utils
                            utils.save_tours(TOURS)
                            
                            st.success("새 투어가 추가되었습니다!")
                            time.sleep(1)
                            st.rerun()

                elif tour_action == "✏️ 기존 투어 수정":
                    edit_id = st.number_input("수정할 투어 ID 입력", min_value=1, step=1, key="edit_tour_id")
                    target_tour = next((t for t in TOURS if t['id'] == edit_id), None)
                    
                    if target_tour:
                        with st.form("edit_tour_form"):
                            st.caption(f"수정 중: {target_tour['name']}")
                            
                            # Find current region index
                            curr_reg = target_tour.get('region', '방콕')
                            curr_reg_idx = 0
                            for idx, opt in enumerate(REGION_OPTIONS):
                                if curr_reg in opt:
                                    curr_reg_idx = idx
                                    break
                            
                            e_region = st.selectbox("지역", REGION_OPTIONS, index=curr_reg_idx) # [NEW]
                            e_name = st.text_input("투어명", value=target_tour['name'])
                            e_price = st.text_input("가격", value=target_tour['price'])
                            e_link = st.text_input("Klook 링크", value=target_tour['link'])
                            e_image = st.text_input("이미지 URL", value=target_tour['image'])
                            e_type = st.text_input("태그", value=",".join(target_tour['type']))
                            e_desc = st.text_area("설명", value=target_tour['desc'])
                            e_pros = st.text_input("장점/특징", value=target_tour['pros'])
                            
                            if st.form_submit_button("수정 내용 저장"):
                                target_tour['region'] = e_region.split(" ", 1)[1] # [NEW]
                                target_tour['name'] = e_name
                                target_tour['price'] = e_price
                                target_tour['link'] = e_link
                                target_tour['image'] = e_image
                                target_tour['type'] = [t.strip() for t in e_type.split(",") if t.strip()]
                                target_tour['desc'] = e_desc
                                target_tour['pros'] = e_pros
                                
                                # Save via utils
                                utils.save_tours(TOURS)
                                
                                st.success("투어 정보가 수정되었습니다!")
                                time.sleep(1)
                                st.rerun()
                    else:
                        st.warning("해당 ID의 투어를 찾을 수 없습니다.")

                elif tour_action == "🗑️ 투어 삭제 (ID)":
                    del_id = st.number_input("삭제할 투어 ID 입력", min_value=1, step=1, key="del_tour_id")
                    confirm_del = st.checkbox("정말 삭제하시겠습니까?")
                    
                    if st.button("삭제 실행", type="primary") and confirm_del:
                        initial_len = len(TOURS)
                        TOURS = [t for t in TOURS if t['id'] != del_id]
                        
                        if len(TOURS) < initial_len:
                            # Save via utils
                            utils.save_tours(TOURS)
                            
                            st.success(f"ID {del_id} 투어가 삭제되었습니다.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("해당 ID의 투어를 찾을 수 없습니다.")

            except Exception as e:
                st.error(f"오류 발생: {e}")

else:
    # --- Viewer Mode ---
    # Visitor Counter Logic & UI (Main Header)

    
    # --- Dark/Light Mode Toggle ---
    # --- Dark/Light Mode Toggle (Relocated to Top-Left above Title) ---

    # CSS to reduce toggle size and text
    st.markdown("""
    <style>
    /* Compact Toggle above Title */
    .compact-toggle {
        display: flex;
        align-items: center;
        margin-bottom: -15px !important; /* Pull title closer */
    }
    .compact-toggle .stToggle {
        transform: scale(0.8); /* Scale down widget */
        transform-origin: left center;
        margin-right: -10px !important;
    }
    .compact-toggle label {
        font-size: 0.8rem !important; /* Smaller text */
        color: gray !important;
    }
    
    /* Mobile Visitor Counter styling adjustments */
    @media (max-width: 768px) {
        .mobile-only-counter {
            font-size: 0.7rem;
            color: gray;
            line-height: 1.2;
            margin-top: 5px;
            text-align: left; /* Align left alongside/below title */
        }
    }
    @media (min-width: 769px) {
        .mobile-only-counter { display: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    # Layout: Toggle -> Title -> Caption
    c_toggle, c_counter = st.columns([1, 1]) # Minimal columns for alignment if needed, or just container
    
    # Just standard stacking since we want it "Right above title, left aligned"
    is_dark = st.toggle("🌘 다크 모드", value=False)
    
    # --- Language Selector (Right below dark mode) ---
    lang_options = ["🇰🇷 KR", "🇺🇸 EN"]
    current_idx = 0 if st.session_state.get('language') == 'Korean' else 1
    try:
        selected = st.pills("🌐 Language", lang_options, default=lang_options[current_idx], selection_mode="single", label_visibility="collapsed")
    except AttributeError:
        selected = st.radio("Language", lang_options, index=current_idx, horizontal=True, label_visibility="collapsed")
    
    if selected:
        new_lang = "Korean" if "KR" in selected else "English"
        if new_lang != st.session_state.get('language'):
            st.session_state['language'] = new_lang
            st.rerun()
    
    # Apply custom class via JS injection or wrapping? 
    # Streamlit doesn't support class wrapping easily for widgets.
    # We rely on CSS selecting .stToggle which applies generally, causing potential Side Effects?
    # No, we can use container specific selection if we wrap it.
    
    # Actually, simpler: just render it. The CSS above targeting .stToggle globally might affect others?
    # Let's scope it to the first toggle if possible or just apply globally as it's the main toggle.
    # User said "Reduce text and toggle size". Global reduction for this app might be fine or we target specifically.
    
    # Let's wrap in a container to target
    # st.container() doesn't add class. 
    # Use :first-of-type semantics in CSS usually works for the Header toggle.
    
    st.markdown("""
    <style>
    /* Specific targeting for the first toggle in the main block */
    .stApp > .main .block-container > div:first-of-type .stToggle {
         transform: scale(0.8);
         transform-origin: left center;
    }
    .stApp > .main .block-container > div:first-of-type .stToggle label p {
         font-size: 0.8rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # --- Main Title (Language-specific) ---
    if st.session_state.get('language') == 'English':
        # English Mode: Agoda review-friendly marketing text
        utils.render_custom_header("🇹🇭 Thai Today: Travel Guide & Fact Check", level=1)
        st.caption(f"Today: {daily_val:,} | Total: {total_val:,} • Real-time Local News, Hotel Reviews, and Smart Travel Tips in Thailand.")
    else:
        # Korean Mode: Original title
        utils.render_custom_header("🇹🇭 오늘의 태국", level=1)
        # [MOD] Structured caption with line break
        st.markdown(f"<small style='color: grey;'>Today: {daily_val:,} | Total: {total_val:,}<br>태국 여행의 모든 것, 뉴스부터 맛집 팩트체크까지</small>", unsafe_allow_html=True)
        
    # --- Dark Mode Logic (CSS-based to prevent layout thrashing) ---
    # We inject the CSS always. The styles trigger only when the toggle is checked via :has() selector.
    st.markdown("""
        <style>
            /* --- DARK MODE SELECTORS --- */
            /* These apply ONLY when the Dark Mode toggle (side effect of st.toggle being checked) is present */
            
            /* Global Body Override */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) {
                /* Can't easily set bg color on body due to Streamlit wrapping, but helps context */
            }

            /* Main App Background & Text */
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) {
                background-color: #0E1117;
                color: #FAFAFA;
            }
            [data-testid="stHeader"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]),
            [data-testid="stSidebar"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) {
                background-color: #262730;
                color: #FAFAFA;
            }

            /* --- CRITICAL FIXES FOR WHITE ELEMENTS --- */

            /* 1. General Popovers (Menus, Dropdowns, Tooltips) */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="popover"],
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="menu"],
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) ul[role="listbox"] {
                background-color: #262730 !important;
                border: 1px solid #444 !important;
            }
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) li[role="option"] {
                 background-color: #262730 !important;
                 color: #FAFAFA !important;
            }
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) li[aria-selected="true"] {
                 background-color: #FF4B4B !important;
                 color: #ffffff !important;
            }

            /* 2. Fix All Buttons & Link Buttons (Inquiry, Next, Booking) */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) a[data-testid="stLinkButton"] {
                background-color: #262730 !important;
                color: #FAFAFA !important;
                border: 1px solid #444 !important;
            }
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button:hover,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) a[data-testid="stLinkButton"]:hover {
                border-color: #FF4B4B !important;
                color: #FF4B4B !important;
            }

            /* 3. Pagination Specifics (Secondary Buttons) */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button[kind="secondary"] {
                background-color: transparent !important;
            }
            /* Active Pagination (Disabled) */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button[disabled],
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) button[disabled]:hover {
                background-color: #FF4B4B !important;
                color: white !important;
                border-color: #FF4B4B !important;
                opacity: 1 !important;
            }

            /* 4. Input/Textarea Text Color */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) input,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) textarea {
                color: white !important;
                background-color: #262730 !important;
            }
            /* Selectbox Display */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="select"] > div {
                 background-color: #262730 !important;
                 color: white !important;
                 border-color: #444 !important;
            }

            /* 5. Mobile Nav Button Text */
            [data-testid="stAppViewContainer"]:has(input[aria-checked="true"]) div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) {
                background: #0E1117 !important;
                border-bottom: 1px solid #333 !important;
            }
            [data-testid="stAppViewContainer"]:has(input[aria-checked="true"]) div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) button {
                color: #FAFAFA !important;
                background-color: transparent !important;
                border: none !important;
            }
            
            /* 6. Expander & Other Containers */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stExpander"] {
                background-color: #0E1117 !important;
                border: 1px solid #333 !important;
                color: white !important;
            }
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stExpanderDetails"] {
                background-color: #0E1117 !important; 
                color: white !important;
            }

            /* 7. Toast & Alerts */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="toast"],
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-baseweb="notification"], 
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stAlert"] {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
                color: #ffffff !important;
            }
            
            /* 8. Light Mode Defaults (ensure links are blue when NOT dark) */
            .stMarkdown a {
                color: #0068c9;
                text-decoration: none;
            }
            .stMarkdown a:hover {
                text-decoration: underline;
            }
            
            /* Dark Mode Link override */
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) .stMarkdown a {
                 color: #4da6ff !important;
            }

            /* --- NEW GLOBAL DARK MODE VISIBILITY FIXES --- */
            
            /* A. Widget Labels & Help Text */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stWidgetLabel"] label p,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stWidgetLabel"] p {
                color: white !important;
            }
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) .stSelectbox label, 
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) .stMultiSelect label,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) .stTextInput label,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) .stNumberInput label,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) .stDateInput label {
                color: white !important;
            }

            /* B. Bordered Containers & Vertical Blocks */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stVerticalBlockBorder"] {
                background-color: #1a1c24 !important;
                border: 1px solid #333 !important;
                padding: 15px !important;
                border-radius: 10px !important;
            }
            
            /* C. Metric Labels & Values */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) [data-testid="stMetricLabel"] p,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) [data-testid="stMetricValue"] div {
                color: white !important;
            }

            /* D. General Text Inheritance */
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) p,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) span,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) li,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) strong,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) h1,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) h2,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) h3,
            [data-testid="stAppViewContainer"]:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) h4 {
                color: #FAFAFA !important;
            }
            
            /* E. Special Fix for Info/Success/Warning/Error text in Dark Mode */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stAlert"] p,
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stAlert"] li {
                color: white !important;
            }

            /* F. Caption Fix (gray text in dark mode) */
            body:has(input[aria-label="🌘 다크 모드"][aria-checked="true"]) div[data-testid="stCaptionContainer"] {
                color: #A0A0A0 !important;
            }

            /* G. st.pills Visibility & Layout Fix (Definitive) */
            /* Force DARK text on selected pills to beat Dark Mode global p/span styles */
            div[data-testid="stPills"] button[data-testid="stBaseButton-pillsActive"] *,
            div[data-testid="stPills"] button[data-selected="true"] *,
            button[data-testid="stBaseButton-pillsActive"] * {
                color: #31333F !important;
                font-weight: 700 !important;
                visibility: visible !important;
                opacity: 1 !important;
            }

            /* Prevent pills from collapsing into small circles */
            div[data-testid="stPills"] button[data-testid^="stBaseButton-pills"],
            button[data-testid^="stBaseButton-pills"] {
                min-width: max-content !important;
                width: auto !important;
                flex-shrink: 0 !important;
            }

            /* Ensure internal markdown container allows expansion */
            button[data-testid^="stBaseButton-pills"] div[data-testid="stMarkdownContainer"] {
                width: auto !important;
                overflow: visible !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- Theme Configuration (Variables for Widgets) ---
    if is_dark:
        # Dark Theme Vars for Python-based HTML generation
        card_bg = "rgba(0, 0, 0, 0.7)"
        text_main = "#ffffff"
        text_sub = "#aaaaaa"
        border_color = "#333"
    else:
        # Light Theme Vars
        card_bg = "rgba(255, 255, 255, 0.9)"
        text_main = "#000000"
        text_sub = "#333333"
        border_color = "#ddd"


    # --- Status Dashboard (Mobile-First: 4 columns on PC, 2x2 grid on Mobile) ---
    # Get weather data (Bangkok)
    def get_weather_data():
        """Fetch weather from OpenWeatherMap or fallback"""
        try:
            # Use a simple approach for now
            return {"temp": 32, "desc": "맑음", "icon": "☀️"}  # Default sunny
        except:
            return {"temp": "--", "desc": "로딩중", "icon": "🌡️"}
    
    # Cache exchange rate
    @st.cache_data(ttl=3600)
    def get_cached_exchange_rate():
        return utils.get_thb_krw_rate()
    
    # Get air quality
    def get_aqi_data():
        try:
            waqi_token = st.secrets.get("WAQI_API_KEY", "")
            aqi_data = get_cached_air_quality(waqi_token)
            if not aqi_data:
                return {"aqi": "--", "status": utils.t("aqi_loading"), "icon": "🌫️", "color": "#888"}
            aqi = aqi_data['aqi']
            if aqi <= 50:
                return {"aqi": aqi, "status": utils.t("aqi_good"), "icon": "😊", "color": "#00e400"}
            elif aqi <= 100:
                return {"aqi": aqi, "status": utils.t("aqi_moderate"), "icon": "😐", "color": "#ffff00"}
            elif aqi <= 150:
                return {"aqi": aqi, "status": utils.t("aqi_unhealthy"), "icon": "😷", "color": "#ff7e00"}
            else:
                return {"aqi": aqi, "status": utils.t("aqi_very_unhealthy"), "icon": "☠️", "color": "#ff004c"}
        except:
            return {"aqi": "--", "status": utils.t("aqi_error"), "icon": "⚠️", "color": "#888"}
    
    # Fetch data
    weather = get_weather_data()
    aqi_info = get_aqi_data()
    
    # Language-specific exchange rate
    is_english_mode = st.session_state.get('language') == 'English'
    
    if is_english_mode:
        # English Mode: USD to THB rate
        usd_thb_rate = get_cached_usd_exchange_rate()
        exchange_display = f"1 USD = {usd_thb_rate:.2f} THB" if usd_thb_rate else "N/A"
        exchange_label = "💵 USD/THB Rate"
    else:
        # Korean Mode: THB to KRW rate (buy/sell)
        exchange_rate = get_cached_exchange_rate()
        buy_rate = exchange_rate * 1.02 if exchange_rate else 0  # 2% markup for buying THB
        sell_rate = exchange_rate * 0.98 if exchange_rate else 0  # 2% markdown for selling THB
    
    # Build Status Dashboard HTML
    weather_label = utils.t("weather_label")
    air_quality_label = utils.t("air_quality_label")
    
    if is_english_mode:
        # English Mode: Single card for USD/THB
        status_dashboard_html = f"""
        <div class="status-dashboard">
            <div class="status-card">
                <span class="label">🌡️ {weather_label}</span>
                <span class="value">{weather['icon']} {weather['temp']}°C</span>
            </div>
            <div class="status-card">
                <span class="label">🌫️ {air_quality_label}</span>
                <span class="value" style="color: {aqi_info['color']};">{aqi_info['icon']} {aqi_info['status']}</span>
            </div>
            <div class="status-card" style="grid-column: span 2;">
                <span class="label">{exchange_label}</span>
                <span class="value">{exchange_display}</span>
            </div>
        </div>
        """
    else:
        # Korean Mode: Buy/Sell rates for KRW/THB
        exchange_buy_label = utils.t("exchange_buy_label")
        exchange_sell_label = utils.t("exchange_sell_label")
        currency_unit = utils.t("currency_unit")
        
        status_dashboard_html = f"""
        <div class="status-dashboard">
            <div class="status-card">
                <span class="label">🌡️ {weather_label}</span>
                <span class="value">{weather['icon']} {weather['temp']}°C</span>
            </div>
            <div class="status-card">
                <span class="label">🌫️ {air_quality_label}</span>
                <span class="value" style="color: {aqi_info['color']};">{aqi_info['icon']} {aqi_info['status']}</span>
            </div>
            <div class="status-card">
                <span class="label">💵 {exchange_buy_label}</span>
                <span class="value">{buy_rate:.1f}{currency_unit}</span>
            </div>
            <div class="status-card">
                <span class="label">💴 {exchange_sell_label}</span>
                <span class="value">{sell_rate:.1f}{currency_unit}</span>
            </div>
        </div>
        """
    
    st.markdown(status_dashboard_html, unsafe_allow_html=True)


    # --- Navigation Logic (Dual Node: Sidebar & Top Pills) ---
    
    # Init Session State for Nav
    if "nav_mode" not in st.session_state:
        st.session_state["nav_mode"] = None # Will be initialized below based on language
    
    if "wongnai_result" not in st.session_state:
        st.session_state["wongnai_result"] = None

    # Callbacks to keep them in sync
    def update_from_sidebar():
        st.session_state["nav_mode"] = st.session_state["nav_sidebar"]
        
    def update_from_top():
        st.session_state["nav_mode"] = st.session_state["nav_top"]

    # 1. Top Navigation (Pills)
    st.write("") # Spacer
    # [MOD] Conditionally hide Wongnai for Production deployment
    # Check both Secrets and file-path heuristic for robustness
    is_prod = (st.secrets.get("DEPLOY_ENV") == "prod") or (not os.path.abspath(__file__).startswith("/Users/jaewoo/"))
    
    # [MOD] Language-aware tab ordering
    is_english = st.session_state.get('language') == 'English'
    if is_prod:
        if is_english:
            nav_options = [
                utils.t("nav_guide"), utils.t("nav_hotel"), utils.t("nav_food"), 
                utils.t("nav_taxi"), utils.t("nav_news"), utils.t("nav_board")
            ]
        else:
            # Korean Mode: Use Tour tab instead of Guide
            nav_options = [
                utils.t("nav_news"), utils.t("nav_hotel"), utils.t("nav_tour"), 
                utils.t("nav_food"), utils.t("nav_taxi"), utils.t("nav_board")
            ]
    else:
        if is_english:
            nav_options = [
                utils.t("nav_guide"), utils.t("nav_hotel"), utils.t("nav_food"), 
                utils.t("nav_taxi"), utils.t("nav_event"), utils.t("nav_news"), utils.t("nav_board")
            ]
        else:
            # Korean Mode: Use Tour tab instead of Guide
            nav_options = [
                utils.t("nav_news"), utils.t("nav_hotel"), utils.t("nav_tour"), 
                utils.t("nav_food"), utils.t("nav_taxi"), utils.t("nav_event"), utils.t("nav_board")
            ]
    
    # [MOD] Ensure nav_mode is valid for current language
    if st.session_state["nav_mode"] not in nav_options:
        st.session_state["nav_mode"] = nav_options[0]
    
    current_mode = st.session_state["nav_mode"]

    try:
        # Note: 'default' only works on init. We use 'key' to bind state? 
        # Actually st.pills with a key binds to that key in session_state.
        # But we want to separate widget keys to avoid duplicate id errors if we used same key.
        # So we use different keys and sync them.
        
        # However, updating one widget's key in session state from another's callback 
        # is the standard way to sync.
        
        # If we manually set nav_top/nav_sidebar in state before render, it updates the widget.
        if "nav_top" not in st.session_state or st.session_state["nav_top"] != current_mode:
             st.session_state["nav_top"] = current_mode
             
        # [MOD] Mobile Horizontal Scroll for Navigation
        st.markdown("""
        <style>
        @media (max-width: 768px) {
            div[data-testid="stButtonGroup"] > div,
            div[data-testid="stPills"] > div > div {
                flex-wrap: nowrap !important;
                overflow-x: auto !important;
                white-space: nowrap !important;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
                padding-bottom: 4px;
                mask-image: linear-gradient(to right, black 85%, transparent 100%);
                -webkit-mask-image: linear-gradient(to right, black 85%, transparent 100%);
            }
            div[data-testid="stButtonGroup"] > div::-webkit-scrollbar,
            div[data-testid="stPills"] > div > div::-webkit-scrollbar {
                display: none;
            }
        }
        </style>
        """, unsafe_allow_html=True)

        st.pills("이동", nav_options, selection_mode="single", 
                key="nav_top", on_change=update_from_top, label_visibility="collapsed")
                
    except AttributeError:
        # Fallback
        if "nav_top" not in st.session_state or st.session_state["nav_top"] != current_mode:
             st.session_state["nav_top"] = current_mode
             
        st.radio("이동", nav_options, horizontal=True, 
                key="nav_top", on_change=update_from_top, label_visibility="collapsed")

    # 2. Sidebar Navigation (Restored for PC users)
    with st.sidebar:
        st.markdown("### 📌 메뉴 선택")
        
        # Sync state to widget
        if "nav_sidebar" not in st.session_state or st.session_state["nav_sidebar"] != current_mode:
            st.session_state["nav_sidebar"] = current_mode
            
        # Custom CSS to hide Nav Radio on Mobile (Screens < 768px)
        st.markdown("""
            <style>
            @media (max-width: 768px) {
                div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:nth-child(2) {
                    display: none !important;
                }
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.radio("이동", nav_options, 
                key="nav_sidebar", on_change=update_from_sidebar, label_visibility="collapsed")
    
    # 3. Navigation Bar (Mobile Only via CSS)
    # [MOD] Dinamically generated columns and indices
    num_cols = len(nav_options)
    b_cols = st.columns(num_cols)
    nav_indices = {i: (nav_options[i], nav_options[i]) for i in range(num_cols)}

    for i, col in b_cols.items() if hasattr(b_cols, 'items') else enumerate(b_cols):
        label, target = nav_indices[i]
        with col:
            st.markdown('<div class="mobile-only-trigger"></div>', unsafe_allow_html=True)
            if st.button(label, key=f"btn_nav_{i}", width='stretch'):
                st.session_state["nav_mode"] = target
                st.rerun()
    
    # Use the master state for rendering
    page_mode = st.session_state["nav_mode"]

    # --- Page 1: News ---
    
    # --- Page 1: News ---
    # --- Dynamic Page Rendering ---
    if page_mode == utils.t("nav_news"):
        render_tab_news()
    elif page_mode == utils.t("nav_hotel"):
        render_tab_hotel()
    elif page_mode == utils.t("nav_food"):
        render_tab_food()
    elif page_mode == utils.t("nav_guide"):
        render_tab_guide()
    elif page_mode == utils.t("nav_tour"):
        render_tab_tour()
    elif page_mode == utils.t("nav_taxi"):
        render_tab_taxi()
    elif page_mode == utils.t("nav_event"):
        render_tab_event()
    elif page_mode == utils.t("nav_board"):
        render_tab_board()




# --- Bottom Spacer for Pagination Visibility ---
st.markdown("""<div style="height: 150px; width: 100%;"></div>""", unsafe_allow_html=True)

# --- URL 정리 (Travelpayouts init_marker 제거) ---
utils.clean_url_bar()
