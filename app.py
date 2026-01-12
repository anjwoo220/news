import streamlit as st
import json
import os
import utils
from datetime import datetime
import plotly.express as px
from collections import Counter
import hashlib
import html
import pandas as pd
import time
from streamlit_gsheets import GSheetsConnection
import certifi
import ssl

# Fix SSL Certificate Issue on Mac
os.environ["SSL_CERT_FILE"] = certifi.where()


# --- Configuration ---
NEWS_FILE = 'data/news.json'
EVENTS_FILE = 'data/events.json'
BIG_EVENTS_FILE = 'data/big_events.json'
TRENDS_FILE = 'data/trends.json'
CONFIG_FILE = 'data/config.json'
COMMENTS_FILE = 'data/comments.json'
BOARD_FILE = 'data/board.json'

DEPLOY_URL = "https://thai-briefing.streamlit.app"

st.set_page_config(
    page_title="오늘의 태국 - 실시간 태국뉴스, 여행정보",
    page_icon="🇹🇭",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': 'https://forms.gle/B9RTDGJcCR9MnJvv5',
        'About': "### 오늘의 태국 \n 실시간 태국 여행 정보, 뉴스, 핫플을 한눈에! 태국 정보가 필요한 모든 분들께!"
    }
)

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
    html, body, [class*="css"] {
        font-family: "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, Roboto, "Helvetica Neue", "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", sans-serif;
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
            padding: 5px 5px 5px 5px !important;
            padding-top: env(safe-area-inset-top) !important; /* 아이폰 노치 영역 확보 */
            border-bottom: 1px solid #e0e0e0 !important;
            margin: 0 !important;
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            justify-content: space-between !important;
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

        /* Pad content TOP to avoid hiding behind nav */
        /* Remove extra bottom padding */
        .main .block-container {
            padding-top: 80px !important; 
            padding-bottom: 50px !important;
        }
        .stApp {
            padding-top: 80px !important;
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

    /* Dark Mode Support for Fixed Nav */
    [data-testid="stAppViewContainer"]:has(input[aria-checked="true"]) div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) {
        background: rgba(0, 0, 0, 0.9) !important;
        border-top: 1px solid #333 !important;
    }
    [data-testid="stAppViewContainer"]:has(input[aria-checked="true"]) div[data-testid="stHorizontalBlock"]:has(.mobile-only-trigger) button {
        color: #ddd !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Helper Functions (Load/Save) ---
# Separate cache for heavy news data
# Separate cache for heavy news data
# Update cache on file change by passing mtime
@st.cache_data(ttl=600)
def load_news_data(last_updated):
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

# --- Cached Wrappers for API Calls ---
@st.cache_data(ttl=1800) # Cache for 30 mins
def get_cached_air_quality(token):
    return utils.get_air_quality(token)

@st.cache_data(ttl=1800) # Cache for 30 mins
def get_cached_exchange_rate():
    return utils.get_thb_krw_rate()

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

@st.cache_data(ttl=3600, show_spinner=False)
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

# PC UI (Sidebar Bottom)
with st.sidebar:
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align: center; color: #666; font-size: 0.8em;">
        👀 Today: <b>{daily_val:,}</b> | Total: <b>{total_val:,}</b>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 💡 정보 & 지원")
    st.markdown(f"🔗 [고객 지원 (Get Help)](https://forms.gle/B9RTDGJcCR9MnJvv5)")
    with st.expander("ℹ️ 서비스 정보 (About)"):
        st.markdown("""
        **오늘의 태국**
        실시간 태국 여행 정보, 뉴스, 핫플을 한눈에! 
        태국 정보가 필요한 모든 분들을 위한 AI 기반 브리핑 서비스입니다.
        """)

# --- Comment System Helpers ---
def generate_news_id(title):
    """Generate MD5 hash from title to use as ID."""
    return hashlib.md5(title.encode()).hexdigest()

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

        data[news_id].append(new_comment)
        save_json(COMMENTS_FILE, data)

# --- Community Board Helpers (Google Sheets) ---
def load_board_data():
    """
    Load data from Google Sheets ('board_db').
    Returns a list of dicts: [{'created_at':..., 'nickname':..., 'content':..., 'password':...}]
    Sorted by 'created_at' descending (Latest first).
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
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

def save_board_post(nickname, content, password):
    """
    Append a new row to Google Sheets using Update (Read -> Concat -> Update).
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        existing_df = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1335tHFQH7wtp_CGsPcrKsf3525Bmf9mz-O6D3NtITWc/edit?usp=sharing", worksheet=0, ttl=0)
        
        new_row = pd.DataFrame([{
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "nickname": nickname if nickname else "익명",
            "content": content,
            "password": password
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
        conn = st.connection("gsheets", type=GSheetsConnection)
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
        conn = st.connection("gsheets", type=GSheetsConnection)
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
        conn = st.connection("gsheets", type=GSheetsConnection)
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
    if st.sidebar.button("🚪 관리자 모드 종료", use_container_width=True):
        st.query_params.clear()
        st.rerun()

    # Visitor Counter (Hidden in Admin, or optional)

    
    if check_password():
        st.success("관리자 모드 진입 성공") # Debugging: Confirmation
        st.title("🛠️ 통합 운영 관제탑 (Admin Console)")
        
        # Tabs for better organization
        # Tabs for better organization
        # Main Tab Layout
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["📊 상태/통계", "✏️ 뉴스 관리", "🛡️ 커뮤니티", "📢 설정/공지", "📡 RSS 관리", "🎉 이벤트/여행", "🏨 호텔 관리", "⚙️ 소스 관리", "🌴 매거진 관리"])
        
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
                        # Try secrets
                        try:
                            import toml
                            secrets = toml.load(".streamlit/secrets.toml")
                            api_key = secrets.get("GEMINI_API_KEY")
                        except: pass
                    
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
                news_data = load_json(NEWS_FILE)
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
                                save_json(NEWS_FILE, news_data)
                                st.success("저장되었습니다.")
                                st.rerun()
                                
                            if col_del.button("삭제", key=f"del_{selected_date_edit}_{i}"):
                                topics.pop(i)
                                if not topics:
                                    del news_data[selected_date_edit]
                                else:
                                    news_data[selected_date_edit] = topics
                                save_json(NEWS_FILE, news_data)
                                st.warning("삭제되었습니다.")
                                st.rerun()

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
                 api_key = st.secrets.get("google_maps_api_key")
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
                         gemini_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
                         analysis = utils.analyze_hotel_reviews(info['name'], info['rating'], info['reviews'], gemini_key)
                         st.json(analysis)


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
                             st.image(be['image_url'], use_container_width=True)
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

        # --- Tab 9: Magazine (Trend Hunter) Management ---
        with tab9:
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


        # --- Tab 8: Source Manager ---
        with tab8:
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
                use_container_width=True,
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
                use_container_width=True,
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

    st.title("🇹🇭 오늘의 태국")
    
    # Mobile Visitor Counter (Below Title for clean flow)
    st.markdown(f"""
    <div class="mobile-only-counter">
       Today: <b>{daily_val:,}</b> | Total: <b>{total_val:,}</b>
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("뉴스부터 여행까지, 가장 빠른 태국 소식")
        
    # Define Theme Colors based on Toggle
    if is_dark:
        # Dark Mode Styles (Pitch Black Override)
        card_bg = "#000000"
        text_main = "#ffffff"
        text_sub = "#e0e0e0"
        border_color = "#333"
        
        # Inject CSS for Dark Mode Overrides
        st.markdown("""
            <style>
            /* Global Background & Text for Dark Mode Override */
            [data-testid="stAppViewContainer"] {
                background-color: #000000;
                color: #ffffff;
            }
            [data-testid="stSidebar"] {
                background-color: #000000;
                border-right: 1px solid #333;
            }
            [data-testid="stHeader"] {
                background-color: rgba(0, 0, 0, 0.95);
            }
            
            /* Text Elements */
            p, h1, h2, h3, h4, h5, h6, li, label, .stMarkdown, .stCaption {
                color: #ffffff !important;
            }
            
            /* Inputs */
            div[data-baseweb="input"] > div, div[data-baseweb="base-input"] > div {
                background-color: #000000 !important;
                border-color: #333 !important;
                color: #ffffff !important;
            }
            input {
                color: #ffffff !important;
                caret-color: #ffffff !important;
            }
            
            /* Text Area */
            textarea {
                background-color: #000000 !important;
                color: #ffffff !important;
                caret-color: #ffffff !important;
            }
            div[data-baseweb="textarea"] > div {
                background-color: #000000 !important;
                border-color: #333 !important;
            }

            /* Selectbox & Dropdown */
            div[data-baseweb="select"] > div {
                background-color: #000000 !important;
                color: #ffffff !important;
                border-color: #333 !important;
            }
            div[data-baseweb="popover"], div[data-baseweb="menu"], ul[data-baseweb="menu"] {
                background-color: #000000 !important;
                color: #ffffff !important;
                border: 1px solid #333 !important;
            }
            li[data-baseweb="menu-item"] { 
                color: #ffffff !important; 
            }
            li[data-baseweb="menu-item"]:hover {
                background-color: #222 !important;
            }
            
            /* Buttons */
            button[data-testid="baseButton-secondary"], button[data-testid="baseButton-primary"] {
                background-color: #000000 !important;
                color: #ffffff !important;
                border: 1px solid #333 !important;
            }
            button[data-testid="baseButton-secondary"]:hover, button[data-testid="baseButton-primary"]:hover {
                border-color: #ff4b4b !important;
                color: #ff4b4b !important;
            }
            
            /* Tabs */
            button[data-baseweb="tab"] {
                 background-color: transparent !important;
            }
            button[data-baseweb="tab"] div {
                 color: #ffffff !important;
            }
            button[data-baseweb="tab"][aria-selected="true"] div {
                 color: #ff4b4b !important;
            }
            
            /* Calendar / Date Picker */
            div[data-baseweb="calendar"] {
                background-color: #000000 !important;
                color: #ffffff !important;
            }
            div[data-baseweb="calendar"] button {
                 color: #ffffff !important;
                 background-color: transparent !important;
            }
            div[data-baseweb="calendar"] button:hover {
                 background-color: #222 !important;
            }

            /* Category Pills - Fix using stButtonGroup */
            div[data-testid="stButtonGroup"] {
                background-color: transparent !important;
            }
            div[data-testid="stButtonGroup"] button {
                background-color: #000000 !important;
                color: #ffffff !important;
                border: 1px solid #333 !important;
            }
            div[data-testid="stButtonGroup"] button:hover {
                border-color: #ff4b4b !important;
                color: #ff4b4b !important;
            }
            div[data-testid="stButtonGroup"] button[data-testid="stBaseButton-pillsActive"] {
                background-color: #000000 !important;
                border-color: #ff4b4b !important;
                color: #ff4b4b !important;
            }
            div[data-testid="stButtonGroup"] button p {
                color: inherit !important;
            }
            
            /* Expander */
            div[data-testid="stExpander"] {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
                color: #ffffff !important;
            }
            div[data-testid="stExpander"] details {
                background-color: #000000 !important;
            }
            div[data-testid="stExpander"] summary {
                color: #ffffff !important;
            }
            div[data-testid="stExpander"] summary:hover {
                color: #ff4b4b !important;
            }

            /* Code Block & Share Text - Deep Override */
            .stCodeBlock, 
            .stCodeBlock > div, 
            .stCodeBlock pre, 
            .stCodeBlock code,
            div[data-testid="stCodeBlock"],
            div[data-testid="stCodeBlock"] * {
                 background-color: #000000 !important;
                 border-color: #333 !important;
            }
            .stCodeBlock code {
                 color: #ffffff !important;
            }
            
            /* Expander Header */
            div[data-testid="stExpander"] > details > summary {
                background-color: #000000 !important;
                color: #ffffff !important;
                border-bottom: 1px solid #333;
            }
            div[data-testid="stExpander"] > details > summary:hover {
                color: #ff4b4b !important;
            }

            /* Form Submit Button (Comments) */
            div[data-testid="stForm"] button[kind="secondaryFormSubmit"],
            div[data-testid="stForm"] button[data-testid="baseButton-secondary"] {
                 background-color: #000000 !important;
                 color: #ffffff !important;
                 border: 1px solid #333 !important;
            }
            div[data-testid="stForm"] button[kind="secondaryFormSubmit"]:hover,
            div[data-testid="stForm"] button[data-testid="baseButton-secondary"]:hover {
                border-color: #ff4b4b !important;
                color: #ff4b4b !important;
            }

            /* Toast */
            div[data-baseweb="toast"] {
                background-color: #000000 !important;
                color: #ffffff !important;
                border: 1px solid #333;
            }
            
            /* Metric */
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
                 color: #ffffff !important;
            }
            
            /* Alerts (Info, Success, Warning, Error) - Override backgrounds */
            div[data-baseweb="notification"], div[data-testid="stAlert"] {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
                color: #ffffff !important;
            }
            div[data-testid="stAlert"] > div {
                color: #ffffff !important;
            }
            
            /* Modal & Dialogs */
            div[data-baseweb="modal"] > div {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
                color: #ffffff !important;
            }
            
            /* File Uploader */
            [data-testid="stFileUploader"] {
                background-color: #000000 !important;
            }
            section[data-testid="stFileUploaderDropzone"] {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
            }
            
            /* Tables/DataFrames */
            [data-testid="stDataFrame"], [data-testid="stTable"] {
                background-color: #000000 !important;
            }

            /* --- CRITICAL FIXES FOR WHITE ELEMENTS --- */

            /* 1. General Popovers (Menus, Dropdowns, Tooltips) */
            div[data-baseweb="popover"] {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
            }
            div[data-baseweb="popover"] > div {
                background-color: #000000 !important;
                color: #ffffff !important;
            }

            /* 2. Calendar / Date Picker Popup Specifics */
            div[data-baseweb="calendar"] {
                background-color: #000000 !important;
                color: #ffffff !important;
            }
            div[data-baseweb="calendar"] div {
                 background-color: #000000 !important;
                 color: #ffffff !important;
            }
            /* Weekday Headers */
            div[data-baseweb="calendar"] div[aria-label^="weekday"] {
                 color: #888 !important; 
            }
            /* Day Buttons */
            div[data-baseweb="calendar"] button {
                 background-color: transparent !important;
                 color: #ffffff !important;
            }
            div[data-baseweb="calendar"] button:hover {
                 background-color: #333 !important;
            }
            /* Selected Day */
            div[data-baseweb="calendar"] button[aria-selected="true"] {
                 background-color: #ff4b4b !important;
                 color: #ffffff !important;
            }
            /* Month/Year Dropdowns in Calendar */
            div[data-baseweb="calendar"] div[data-baseweb="select"] div {
                 background-color: #000000 !important;
                 color: #ffffff !important;
            }

            /* 3. Expander Content (st.expander internal container) */
            div[data-testid="stExpanderDetails"] {
                background-color: #000000 !important;
                color: #ffffff !important;
            }
            div[data-testid="stExpander"] {
                background-color: #000000 !important;
                border: 1px solid #333 !important;
                color: #ffffff !important;
            }
            div[data-testid="stExpander"] > details > summary {
                color: #ffffff !important;
            }
            div[data-testid="stExpander"] > details > summary:hover {
                color: #ff4b4b !important;
            }
            
            /* 4. Streamlit JSON/Code/Raw Blocks */
            div[data-testid="stJson"] {
                background-color: #000000 !important;
                color: #ffffff !important;
            }

            /* 5. Tooltip/Help Text */
            div[data-baseweb="tooltip"] {
                 background-color: #333 !important;
                 color: #ffffff !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
    else:
        # Light Mode Styles (Native - No Overrides Needed)
        # Using Streamlit's forced "light" theme from config.toml
        card_bg = "rgba(255, 255, 255, 0.9)"
        text_main = "#000000"
        text_sub = "#333333"
        border_color = "#ddd"
        
        # Optional: Light Mode Polishing (Just minor tweaks if needed, but native should handle base)
        st.markdown("""
            <style>
            /* Ensure links are blue in light mode */
            .stMarkdown a {
                color: #0068c9 !important;
                text-decoration: none;
            }
            .stMarkdown a:hover {
                text-decoration: underline;
            }
            
            /* Expander Polish */
            div[data-testid="stExpander"] {
                border-radius: 8px !important;
            }
            </style>
        """, unsafe_allow_html=True)


    # --- Top Widgets (Exchange Rate & Air Quality) ---
    # Responsive layout: side‑by‑side on desktop, stacked on mobile
    st.markdown("""<style>
    .top-widgets {display:flex; flex-direction:row; gap:10px; width:100%;}
    .top-widgets > div {flex:1;}
    @media (max-width: 768px) {
        .top-widgets {flex-direction: column;}
        .top-widgets > div {width: 100%; margin-bottom: 10px;}
    }
    </style>""", unsafe_allow_html=True)

    # 1. Exchange Rate Widget
    @st.cache_data(ttl=3600)
    def get_cached_exchange_rate():
        return utils.get_thb_krw_rate()

    # 2. Air Quality Widget helper
    def render_air_quality():
        try:
            waqi_token = st.secrets.get("WAQI_API_KEY", "")
            aqi_data = get_cached_air_quality(waqi_token)
            if not aqi_data:
                return f"""
                <div style='padding:20px;border-radius:12px;background-color:{card_bg};border:1px solid {border_color};color:{text_sub};text-align:center;font-size:0.8rem;'>
                    🌫️ 공기질 데이터 없음
                </div>
                """
            aqi = aqi_data['aqi']
            if aqi <= 50:
                aqi_color, aqi_icon, aqi_text = "#00e400", "😊", "좋음"
            elif aqi <= 100:
                aqi_color, aqi_icon, aqi_text = "#ffff00", "😐", "보통"
            elif aqi <= 150:
                aqi_color, aqi_icon, aqi_text = "#ff7e00", "😷", "민감군 나쁨"
            else:
                aqi_color, aqi_icon, aqi_text = "#ff004c", "☠️", "나쁨"
            return f"""
<div style='padding:15px;border-radius:12px;background-color:{card_bg};border:1px solid {border_color};margin-bottom:0;display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(5px);box-shadow:0 4px 6px rgba(0,0,0,0.1);'>
    <div style='display:flex;flex-direction:column;'>
        <span style='font-weight:bold;color:{text_sub};font-size:0.9rem;'>🌫️ 방콕 공기 ({aqi_text})</span>
        <span style='font-size:0.75em;color:#888;'>실시간 PM 2.5</span>
    </div>
    <div style='font-size:1.2em;font-weight:bold;color:{aqi_color};'>
        {aqi_icon} {aqi}
    </div>
</div>
"""
        except Exception:
            return f"""
            <div style='padding:20px;border-radius:12px;background-color:{card_bg};border:1px solid {border_color};color:{text_sub};text-align:center;font-size:0.8rem;'>
                🌫️ 공기질 데이터 오류
            </div>
            """

    # Render combined widgets
    try:
        rate = get_cached_exchange_rate()
        now_str = datetime.now().strftime("%m/%d %H:%M")
        exchange_html = f"""
        <div style='padding:15px;border-radius:12px;background-color:{card_bg};border:1px solid {border_color};margin-bottom:0;display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(5px);box-shadow:0 4px 6px rgba(0,0,0,0.1);'>
            <div style='display:flex;flex-direction:column;'>
                <span style='font-weight:bold;color:{text_sub};font-size:0.9rem;'>💰 바트 환율</span>
                <span style='font-size:0.75em;color:#888;'>{now_str} 기준</span>
            </div>
            <div style='font-size:1.2em;font-weight:bold;color:{text_main};'>
                <span style='font-size:0.6em;color:#aaa;margin-right:3px;'>1 THB =</span>
                {rate:.2f} <span style='font-size:0.6em;color:#aaa;'>KRW</span>
            </div>
        </div>
        """
        aqi_html = render_air_quality()
        st.markdown(f"<div class='top-widgets'>{exchange_html}{aqi_html}</div>", unsafe_allow_html=True)
    except Exception:
        st.error("환율 로드 실패")

    # --- Navigation Logic (Dual Node: Sidebar & Top Pills) ---
    
    # Init Session State for Nav
    if "nav_mode" not in st.session_state:
        st.session_state["nav_mode"] = "📰 뉴스 브리핑"

    # Callbacks to keep them in sync
    def update_from_sidebar():
        st.session_state["nav_mode"] = st.session_state["nav_sidebar"]
        
    def update_from_top():
        st.session_state["nav_mode"] = st.session_state["nav_top"]

    # 1. Top Navigation (Pills)
    st.write("") # Spacer
    nav_options = ["📰 뉴스 브리핑", "🎉 콘서트/이벤트", "🏨 호텔 팩트체크", "🗣️ 게시판"]
    
    # Determine default index/selection from state
    current_mode = st.session_state["nav_mode"]
    if current_mode not in nav_options: current_mode = nav_options[0]

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
    
    # 3. Bottom Navigation (Mobile Only via CSS)
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    
    with b_col1:
        st.markdown('<div class="mobile-only-trigger"></div>', unsafe_allow_html=True)
        if st.button("📰 뉴스", key="btn_nav_news", use_container_width=True):
            st.session_state["nav_mode"] = "📰 뉴스 브리핑"
            st.rerun()
    with b_col2:
        st.markdown('<div class="mobile-only-trigger"></div>', unsafe_allow_html=True)
        if st.button("🎉 이벤트", key="btn_nav_events", use_container_width=True):
            st.session_state["nav_mode"] = "🎉 콘서트/이벤트"
            st.rerun()
    with b_col3:
        st.markdown('<div class="mobile-only-trigger"></div>', unsafe_allow_html=True)
        if st.button("🏨 호텔", key="btn_nav_hotel", use_container_width=True):
            st.session_state["nav_mode"] = "🏨 호텔 팩트체크"
            st.rerun()
    with b_col4:
        st.markdown('<div class="mobile-only-trigger"></div>', unsafe_allow_html=True)
        if st.button("🗣️ 게시판", key="btn_nav_board", use_container_width=True):
            st.session_state["nav_mode"] = "🗣️ 게시판"
            st.rerun()
    
    # Use the master state for rendering
    page_mode = st.session_state["nav_mode"]

    # --- Page 1: News ---
    
    # --- Page 1: News ---
    if page_mode == "📰 뉴스 브리핑":
        # --- Twitter Trend Alert (Real-time) ---
        twitter_file = 'data/twitter_trends.json'
        if os.path.exists(twitter_file):
            t_data = load_json(twitter_file)
            if t_data and t_data.get('reason'):
                severity = t_data.get('severity', 'info')
                icon = "🚨" if severity == 'warning' else "📢"
                msg = f"**[실시간 방콕 이슈]** {t_data.get('reason')} (#{t_data.get('topic')})"
                
                if severity == 'warning':
                    st.warning(f"{icon} {msg}")
                else:
                    st.info(f"{icon} {msg}")

        # --- Mobile Nav & Date Selection (Expander) ---
    
        # Data Loading (Moved up for init logic)
        try:
            mtime = os.path.getmtime(NEWS_FILE)
        except:
            mtime = 0
        news_data = load_news_data(mtime)
    
        # Calculate Valid Dates & Latest
        all_dates_str = sorted(news_data.keys())
        valid_dates = []
        latest_date_str = datetime.today().strftime("%Y-%m-%d") # Fallback
    
        if all_dates_str:
            latest_date_str = all_dates_str[-1] # Newest date with news
        
        for d_str in all_dates_str:
            try:
                valid_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
            except: continue
        
        if valid_dates:
            min_date = min(valid_dates)
            data_max = max(valid_dates)
            today_date = datetime.today().date()
            # Safety: Ensure max_date is the LATER of server-today or data-latest
            max_date = max(today_date, data_max) 
        else:
            min_date = max_date = datetime.today().date()
        
        # Init Session for Pagination & Search
        if "current_page" not in st.session_state:
            st.session_state["current_page"] = 1
        if "search_query" not in st.session_state:
            st.session_state["search_query"] = ""
        # Smart Date Init: Default to latest available date
        if "selected_date_str" not in st.session_state: 
            st.session_state["selected_date_str"] = latest_date_str

        # Expander for Controls
        with st.expander("🔍 날짜 검색 및 옵션", expanded=False):
            col_nav1, col_nav2 = st.columns([1, 1])
        
            with col_nav1:
                # Date Picker
                # Convert stored string back to date object for widget
                try:
                    curr_date_obj = datetime.strptime(st.session_state["selected_date_str"], "%Y-%m-%d").date()
                except:
                    curr_date_obj = datetime.today().date()
                
                # Double safety: clamp to valid range to prevent StreamlitAPIException
                curr_date_obj = max(min_date, min(max_date, curr_date_obj))

                new_date = st.date_input(
                    "📅 날짜 선택", 
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
                search_input = st.text_input("🔎 키워드 검색", value=st.session_state["search_query"])
                if search_input != st.session_state["search_query"]:
                    st.session_state["search_query"] = search_input
                    st.session_state["current_page"] = 1 # Reset page
                    st.rerun()

            # Reset Button (Full List / Clear Search)
            if st.session_state["search_query"]:
                if st.button("🔄 검색어 초기화", use_container_width=True):
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
            header_text = f"🔍 '{st.session_state['search_query']}' 검색 결과 ({len(found_topics)}건)"
    
        else:
            # Date Mode
            if selected_date_str in news_data:
                daily_topics = news_data[selected_date_str]
                # Show latest first
                filtered_topics_all = list(reversed(daily_topics))
            else:
                filtered_topics_all = []
            header_text = f"📅 {selected_date_str} 브리핑"

        # Category Filter (Only if not searching)
        if not is_search_mode and filtered_topics_all:
            categories_available = ["전체", "정치/사회", "경제", "여행/관광", "사건/사고", "엔터테인먼트", "기타"]
            try:
                selected_category = st.pills("카테고리", categories_available, default="전체", selection_mode="single")
                if not selected_category: selected_category = "전체"
            except AttributeError:
                selected_category = st.radio("카테고리", categories_available, horizontal=True)
        
            if selected_category != "전체":
                filtered_topics_all = [t for t in filtered_topics_all if t.get("category", "기타") == selected_category]
                # Reset page if category changes? 
                # Ideally yes, but pills don't trigger callback easily without key.
                # For simplicity, we assume user stays on page 1 or handles it.
                # To fix properly, we'd need key and callback. Let's keep it simple for now.

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

        # --- Share Helper (Top) ---
        if topics_to_show:
             with st.expander("📋 카톡 공유용 텍스트 생성 (현재 페이지)"):
                share_text = f"[🇹🇭 태국 뉴스룸 브리핑 - {header_text}]\n\n"
                for idx, item in enumerate(topics_to_show):
                    share_text += f"{idx+1}. {item['title']}\n"
                    share_text += f"- {item['summary'][:60]}...\n\n"
                share_text += f"👉 더 보기: {DEPLOY_URL}"
                st.code(share_text, language="text")

        # --- Main Content Render ---
        st.divider()
        st.header(header_text)
    
        # Empty State
        if not filtered_topics_all:
            if is_search_mode:
                 st.info("조건에 맞는 뉴스가 없습니다.")
            else:
                 st.info("😴 아직 업데이트된 뉴스가 없습니다. (잠시 후 다시 확인해주세요)", icon="⏳")

        # Render Cards
        all_comments_data = get_all_comments() # Load once
    
        for topic in topics_to_show:
            with st.container():
                col_badg, col_time = st.columns([1, 5])
                cat_text = topic.get("category", "기타")
                date_display = topic.get('date_str', selected_date_str) # Use selected date if not in topic
                time_display = topic.get('collected_at', '')
                meta_info = f"{date_display} {time_display}".strip()
            
                st.markdown(f"**🏷️ {cat_text}** <span style='color:grey'> | 🕒 {meta_info}</span>", unsafe_allow_html=True)
            
                st.subheader(f"{topic['title']}")
            
                if topic.get('image_url'):
                    st.image(topic['image_url'], use_container_width=True)
            
                # Highlight
                final_summary = highlight_text(topic['summary'])
                st.markdown(final_summary)

                # Drawers
                with st.expander("📄 기사 전문 보기"):
                    full_text = topic.get('full_translated', '⚠️ 이 기사는 요약본만 제공됩니다.')
                    st.markdown(full_text)
            
                with st.expander("🔗 관련 기사 & 공유"):
                     # Individual Share
                     ind_share = f"[태국 뉴스룸]\n{topic['title']}\n\n- {topic['summary']}\n\n👉 원문: {topic.get('references', [{'url':'#'}])[0].get('url')}\n🌐 뉴스룸: {DEPLOY_URL}"
                     st.code(ind_share, language="text")
                     st.markdown("---")
                     # Links
                     for ref in topic.get('references', []):
                        title = ref.get('title', 'No Title')
                        url = ref.get('url', '#')
                        source = ref.get('source', 'Unknown Source')
                        st.markdown(f"- [{title}]({url}) - *{source}*")

                # Comments
                news_id = generate_news_id(topic['title'])
                comments = all_comments_data.get(news_id, [])
            
                with st.expander(f"💬 댓글 ({len(comments)})"):
                    if not comments:
                        st.caption("아직 댓글이 없습니다.")
                    else:
                        for c in comments:
                            st.markdown(f"**{c['user']}**: {c['text']} <span style='color:grey; font-size:0.8em'>({c.get('date', '')})</span>", unsafe_allow_html=True)
                
                    # Comment Form
                    st.markdown("---")
                    with st.form(key=f"comm_form_{news_id}"):
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
                        if st.button("⬅️ 이전", use_container_width=True, key="p_prev"):
                            st.session_state["current_page"] -= 1
                            st.rerun()
                    else:
                        st.button("⬅️ 이전", disabled=True, use_container_width=True, key="p_prev_dis")
                        
                with col_info:
                    st.markdown(f"<div class='pagination-info' style='text-align:center; padding-top:10px;'><b>{st.session_state['current_page']} / {total_pages}</b></div>", unsafe_allow_html=True)
                    
                with col_next:
                    if st.session_state["current_page"] < total_pages:
                        if st.button("다음 ➡️", use_container_width=True, key="p_next"):
                            st.session_state["current_page"] += 1
                            st.rerun()
                    else:
                        st.button("다음 ➡️", disabled=True, use_container_width=True, key="p_next_dis")

    # --- Page 2: Concerts/Events ---
    elif page_mode == "🎉 콘서트/이벤트":
        st.caption("태국 전역의 축제, 콘서트, 핫플레이스 정보를 모았습니다. (매일 자동 업데이트)")

        # --- Big Match Section ---
        big_events = load_json(BIG_EVENTS_FILE, [])
        
        # User View: Filter for Confirmed Events Only
        # Hide if status is vague or date is TBD
        visible_big_events = []
        confirmed_keywords = ['개최확정', '티켓오픈', '매진', '판매중', 'd-', 'confirmed', 'ticket open']
        
        for e in big_events:
            # STRICT FILTER: Only show manually added/verified events
            # This hides auto-crawled events until admin approves/re-saves them as manual
            if e.get('source') == 'manual':
                 visible_big_events.append(e)
            
            # Old Logic (Commented out for Strict Manual Mode)
            # status = e.get('status', '').lower()
            # date_str = e.get('date', '').lower()
            # is_confirmed_status = any(k in status for k in confirmed_keywords)
            # is_tbd = '미정' in date_str or 'tbd' in date_str or '미정' in status
            # if is_confirmed_status and not is_tbd:
            #     visible_big_events.append(e)
            # elif not is_tbd and len(date_str) > 4: 
            #      visible_big_events.append(e)

        # Handle Empty State
        if not visible_big_events:
            with st.expander("🔥 놓치면 후회할 초대형 빅매치/페스티벌 미리보기", expanded=True):
                 st.info("📢 현재 확정된 대형 이벤트 정보를 집계 중입니다. 빠른 시일 내에 업데이트됩니다!")
                 

        try:
            with st.spinner("최신 여행 정보를 불러오는 중..."):
                events = get_cached_events()
                
            if not events:
                st.info("현재 예정된 주요 행사가 없습니다.")
            else:
                # --- Region Filter ---
                events = [e for e in events if isinstance(e, dict)]
                all_regions = ["전체 보기"] + sorted(list(set([e.get('region', '기타') for e in events])))
                
                c_filter, c_space = st.columns([1, 2])
                with c_filter:
                    selected_region = st.selectbox("🗺️ 지역별 보기", all_regions)
                    
                if selected_region != "전체 보기":
                    filtered_events = [e for e in events if e.get('region') == selected_region]
                else:
                    filtered_events = events
                    


                st.write(f"총 {len(filtered_events)}개의 행사가 있습니다.")

                # 2 Columns Grid
                cols = st.columns(2)
                for idx, event in enumerate(filtered_events):
                    with cols[idx % 2]:
                        with st.container(border=True):
                            # Image
                            if event.get('image_url'):
                                st.image(event['image_url'], use_container_width=True)
                            
                            # Badge & Title
                            region = event.get('region', '기타')
                            title = event.get('title', '행사명 없음')
                            st.markdown(f"#### <span style='color:#FF4B4B'>[🏝️ {region}]</span> {title}", unsafe_allow_html=True)
                            
                            # Meta Info
                            date = event.get('date', '날짜 미정')
                            loc = event.get('location', '장소 미정')
                            etype = event.get('type', '행사')
                            
                            st.markdown(f"**🗓️ {date}**")
                            st.markdown(f"📍 {loc} | 🕒 태국 현지 시간")
                            
                            # New: Booking & Price (Clearly Visible)
                            if event.get('booking_date') and len(event['booking_date']) > 2:
                                st.markdown(f"🎟 **예매 오픈:** :red[{event['booking_date']}]")
                            
                            if event.get('price') and len(event['price']) > 2:
                                st.markdown(f"💰 **가격:** :green[{event['price']}]")

                            st.caption(f"🏷️ {etype}")
                            
                            # Link Button
                            link = event.get('link', '#')
                            st.link_button("예매/자세히 보기 🔗", link, use_container_width=True)
                            
                            # Individual Share
                            with st.expander("📤 공유하기"):
                                one_event_share = f"[🇹🇭 오늘의 태국 - 추천 여행정보]\n\n"
                                one_event_share += f"🎈 {title}\n"
                                one_event_share += f"🗓 {date}\n"
                                one_event_share += f"📍 {loc}\n"
                                one_event_share += f"🔗 {link}\n\n"
                                one_event_share += f"👉 더 보기: {DEPLOY_URL}"
                                st.code(one_event_share, language="text")
                            
        except Exception as e:
            st.error(f"이벤트 정보를 불러오는 중 오류가 발생했습니다: {e}")

    # --- Page 3: Trend Hunter (Magazine) ---
    # --- Page 3: Hotel Fact Check ---
    elif page_mode == "🏨 호텔 팩트체크":
        st.header("🏨 호텔 팩트체크 (Hotel Check)")
        st.caption("광고 없는 '찐' 후기 분석! 구글 맵 리뷰를 냉철하게 검증해드립니다.")
        
        # 1. Search Input
        with st.container():
            c_city, c_name = st.columns([1, 2])
            with c_city:
                city_opts = ["Bangkok", "Pattaya", "Chiang Mai", "Phuket", "Krabi", "Koh Samui", "Hua Hin", "Pai", "기타 (직접 입력)"]
                selected_city = st.selectbox("지역 (City)", city_opts, key="user_city_select")
                
                if selected_city == "기타 (직접 입력)":
                    city = st.text_input("도시명 (영어)", placeholder="예: Siracha, Rayong", key="user_city_manual")
                else:
                    city = selected_city
                    
            with c_name:
                hotel_query = st.text_input("호텔 이름 (예: Amari, Hilton)", placeholder="호텔명 입력...", key="user_hotel_input")
        
        if hotel_query:
            if selected_city == "기타 (직접 입력)" and not city.strip():
                st.warning("⚠️ 도시 이름을 입력해주세요!")
            else:
                api_key = st.secrets.get("google_maps_api_key") or st.secrets.get("GOOGLE_MAPS_API_KEY")
                gemini_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
                
                if not api_key:
                    st.error("🚨 Google Maps API Key가 설정되지 않았습니다.")
                    # Debugging Aid
                    with st.expander("🛠️ 디버그: 로드된 Secret Key 목록"):
                        st.write(f"현재 로드된 Keys: {list(st.secrets.keys())}")
                        st.write("팁: secrets.toml을 수정한 후에는 앱을 완전히 재실행해야 할 수 있습니다.")
                elif not gemini_key:
                     st.error("🚨 Gemini API Key가 설정되지 않았습니다.")
                else:
                    # --- Step 1: Candidate Search ---
                    # We store candidates in session state to persist selection UI
                    search_key = f"search_{hotel_query}_{city}"
                    
                    # If this is a new search, clear previous state
                    if "last_search_key" not in st.session_state or st.session_state["last_search_key"] != search_key:
                        st.session_state["candidates"] = None
                        st.session_state["selected_hotel_id"] = None
                        st.session_state["last_search_key"] = search_key
                        
                        with st.spinner(f"🔍 '{hotel_query}' 후보 검색 중..."):
                            candidates = utils.fetch_hotel_candidates(hotel_query, city, api_key)
                            st.session_state["candidates"] = candidates

                    candidates = st.session_state.get("candidates")
                    target_place_id = None

                    if candidates is None:
                        pass # Error already shown in utils
                    elif len(candidates) == 0:
                        st.warning(f"🤔 '{hotel_query}'에 대한 검색 결과가 없습니다. (영어/태국어로 입력해보세요)")
                    elif len(candidates) == 1:
                        target_place_id = candidates[0]['id']
                    else:
                        # Multiple candidates found
                        st.info(f"🔎 총 {len(candidates)}개의 호텔이 검색되었습니다. 정확한 호텔을 선택해주세요.")
                        
                        # Create options map
                        options = {f"{c['name']} ({c['address']})": c['id'] for c in candidates}
                        selected_label = st.radio("분석할 호텔 선택:", list(options.keys()), key="hotel_radio_select")
                        
                        if st.button("선택한 호텔 분석하기 🚀", key="confirm_hotel_btn"):
                            target_place_id = options[selected_label]
                            st.session_state["selected_hotel_id"] = target_place_id
                        elif st.session_state.get("selected_hotel_id"):
                             # Persist selection if already made
                             target_place_id = st.session_state["selected_hotel_id"]

                    # --- Step 2: Fetch Details & Analyze ---
                    if target_place_id:
                         with st.spinner("📊 상세 정보 및 리뷰 분석 중..."):
                             info = utils.fetch_hotel_details(target_place_id, api_key)
                             
                             if info:
                                 # 2. Display Basic Info
                                 col_img, col_desc = st.columns([1, 1.5])
                                
                                 with col_img:
                                     if info.get('photo_url'):
                                         st.image(info['photo_url'], use_container_width=True, caption=info['name'])
                                     else:
                                         st.image("https://via.placeholder.com/400x300?text=No+Image", use_container_width=True)
                                        
                                 with col_desc:
                                     st.subheader(f"{info['name']}")
                                     st.markdown(f"📍 **주소:** {info['address']}")
                                     st.markdown(f"⭐ **구글 평점:** {info['rating']} ({info['review_count']:,}명 참여)")
                                
                                 st.divider()
                                
                                 # 3. Analyze Reviews (Gemini)
                                 analysis = utils.analyze_hotel_reviews(info['name'], info['rating'], info['reviews'], gemini_key)
                                
                                 if "error" in analysis:
                                     st.error(f"분석 중 오류 발생: {analysis['error']}")
                                 else:
                                     # 4. Display Analysis Result
                                    
                                     # One-line Verdict
                                     st.info(f"💡 **한 줄 요약:** {analysis.get('one_line_verdict', '정보 없음')}")
                                    
                                     # Recommendation Target
                                     st.markdown(f"🎯 **{analysis.get('recommendation_target', '')}**")
                                    
                                     # Pros & Cons
                                     c1, c2 = st.columns(2)
                                     with c1:
                                         st.success("✅ **장점 (Pros)**")
                                         for p in analysis.get('pros', []):
                                             st.markdown(f"- {p}")
                                            
                                     with c2:
                                         st.error("⚠️ **단점 (Cons)**")
                                         for c in analysis.get('cons', []):
                                             st.markdown(f"- {c}")
                                    
                                     # Detailed Analysis
                                     with st.expander("🔍 상세 분석 보기 (위치, 룸컨디션, 조식/부대시설)", expanded=True):
                                         st.markdown("### 📍 위치 및 동선")
                                         st.write(analysis.get('location_analysis', '-'))
                                        
                                         st.markdown("### 🛏️ 룸 컨디션")
                                         st.write(analysis.get('room_condition', '-'))
                                        
                                         st.markdown("### 🍽️ 서비스 & 조식")
                                         st.write(analysis.get('service_breakfast', '-'))
                                        
                                         st.markdown("### 🏊‍♂️ 수영장 & 부대시설")
                                         st.write(analysis.get('pool_facilities', '-'))
                                    
                                     # Scores
                                     scores = analysis.get('summary_score', {})
                                     if scores:
                                         st.markdown("### 📊 팩트체크 점수")
                                         sc1, sc2, sc3, sc4 = st.columns(4)
                                         sc1.metric("청결도", f"{scores.get('cleanliness', 0)}/5")
                                         sc2.metric("위치", f"{scores.get('location', 0)}/5")
                                         sc3.metric("편안함", f"{scores.get('comfort', 0)}/5")
                                         sc4.metric("가성비", f"{scores.get('value', 0)}/5")

    # --- Page 4: Community Board ---
    elif page_mode == "🗣️ 게시판":
        st.markdown("### 🗣️ 여행자 수다방")
        st.caption("여행 팁, 질문, 건의사항 등 자유롭게 이야기를 나눠보세요!")
        
        # 1. Notice Section
        st.success("👋 **오늘의 태국**은 여행자를 위한 실시간 정보 앱입니다. 뉴스, 핫플, 이벤트를 한눈에 확인하세요!", icon="📢")
        with st.container():
            col_notice, col_btn = st.columns([4, 1])
            with col_notice:
                st.info("💡 버그 제보, 광고 문의, 기능 제안은 여기로 보내주세요!", icon="📨")
            with col_btn:
                st.link_button("문의하기", "https://forms.gle/B9RTDGJcCR9MnJvv5", use_container_width=True)

        st.divider()

        # 2. Write Section
        with st.expander("✍️ 글쓰기 (여기를 눌러주세요)", expanded=True):
            with st.form("board_write_form", clear_on_submit=True):
                c_nick, c_pw = st.columns(2)
                b_nick = c_nick.text_input("닉네임", placeholder="닉네임을 입력하세요")
                b_pw = c_pw.text_input("비밀번호 (삭제용 숫자 4자리)", type="password", max_chars=4)
                b_content = st.text_area("내용", placeholder="욕설, 비방, 광고글은 통보 없이 삭제될 수 있습니다.", height=100)
                
                if st.form_submit_button("등록하기 📝", use_container_width=True):
                    if not b_content:
                        st.warning("내용을 입력해주세요.")
                    elif not b_pw:
                        st.warning("삭제를 위한 비밀번호를 입력해주세요.")
                    else:
                        with st.spinner("구글 시트에 저장 중..."):
                            if save_board_post(b_nick, b_content, b_pw):
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
                    
                    # Header: Nickname & Date
                    st.markdown(f"**{c_nick}** <span style='color:grey; font-size:0.8em'>| {c_date}</span>", unsafe_allow_html=True)
                    # Content
                    st.markdown(c_content)
                    
                    # Delete UI (Bottom Right)
                    with st.expander("🗑️ 삭제"):
                        del_pw = st.text_input("비밀번호 확인", type="password", key=f"del_pw_{i}", max_chars=4)
                        if st.button("삭제하기", key=f"btn_del_{i}"):
                            # Use created_at as ID for deletion
                            success, msg = delete_board_post(c_date, del_pw)
                            if success:
                                st.success(msg)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)




# --- Bottom Spacer for Pagination Visibility ---
st.markdown("""<div style="height: 150px; width: 100%;"></div>""", unsafe_allow_html=True)
