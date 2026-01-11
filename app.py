import streamlit as st
import json
import os
import utils
from datetime import datetime
import plotly.express as px
from collections import Counter
import time
import hashlib
import html

# --- Configuration ---
NEWS_FILE = 'data/news.json'
CONFIG_FILE = 'data/config.json'
COMMENTS_FILE = 'data/comments.json'
STATS_FILE = 'data/stats.json'
DEPLOY_URL = "https://thai-briefing.streamlit.app"

st.set_page_config(page_title="태국 뉴스 브리핑", page_icon="🇹🇭", layout="wide")

# UI 요소 완벽하게 숨기기 (모바일/PC 공통)
hide_streamlit_style = """
<style>
    /* 1. 상단 헤더 및 붉은색/무지개색 장식 줄 숨기기 */
    [data-testid="stDecoration"] {visibility: hidden !important; display: none !important;}
    [data-testid="stHeader"] {visibility: hidden !important; display: none !important;}
    header {visibility: hidden !important;}

    /* 2. 햄버거 메뉴 및 툴바 숨기기 */
    [data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
    #MainMenu {visibility: hidden !important; display: none !important;}
    
    /* 3. 하단 푸터(Hosted with Streamlit, profile) 숨기기 */
    [data-testid="stFooter"] {visibility: hidden !important; display: none !important;}
    footer {visibility: hidden !important; display: none !important;}

    /* 4. 배포 버튼 등 기타 요소 */
    .stDeployButton {display:none !important;}

    /* 5. 타이틀 반응형 글씨 크기 조절 (추가) */
    /* PC/기본: 기존 크기 유지 (Streamlit Default) */
    h1 {
        white-space: nowrap !important; /* 줄바꿈 방지 */
    }
    
    /* 모바일 (768px 이하) */
    @media screen and (max-width: 768px) {
        h1 {
            font-size: 26px !important; /* 모바일용 작은 크기 */
        }
    }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- Custom CSS ---
st.markdown("""
    <style>
    /* Hide Streamlit Anchor Links (Header Tooltips) */
    [data-testid="stHeaderAction"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Helper Functions (Load/Save) ---
# Separate cache for heavy news data
@st.cache_data(ttl=600)
def load_news_data():
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
    green_keywords = ["홍수", "침수", "미세먼지", "뎅기열", "주류 판매 금지", "시위"]
    for word in green_keywords:
        text = text.replace(word, f":green[**{word}**]")
        
    return text

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Visitor Counter Logic ---
def update_visit_stats():
    """Updates and returns visitor stats."""
    stats = load_json(STATS_FILE, {"total_visits": 0, "daily_visits": {}})
    
    # Check session state to avoid double counting on interaction
    if "visited" not in st.session_state:
        st.session_state["visited"] = True
        
        # Update Counts
        stats["total_visits"] += 1
        today = datetime.now().strftime("%Y-%m-%d")
        stats["daily_visits"][today] = stats["daily_visits"].get(today, 0) + 1
        
        save_json(STATS_FILE, stats)
        
    today = datetime.now().strftime("%Y-%m-%d")
    return stats["total_visits"], stats["daily_visits"].get(today, 0)

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
st.sidebar.title("🗂️ 태국 뉴스 브리핑")

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
    # Visitor Counter (Hidden in Admin, or optional)
    update_visit_stats() # Just ensure stats update if admin visits
    
    if check_password():
        st.success("관리자 모드 진입 성공") # Debugging: Confirmation
        st.title("🛠️ 통합 운영 관제탑 (Admin Console)")
        
        # Tabs for better organization
        # Tabs for better organization
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 상태/통계", "✏️ 뉴스 관리", "🛡️ 커뮤니티", "📢 설정/공지", "📡 RSS 관리"])
        
        # --- Tab 1: Stats & Health ---
        with tab1:
            st.subheader("시스템 상태")
            col1, col2 = st.columns(2)
            
            # File Check
            with col1:
                st.markdown("#### 📂 데이터 파일 상태")
                files_to_check = [NEWS_FILE, COMMENTS_FILE, STATS_FILE, CONFIG_FILE]
                for f in files_to_check:
                    if os.path.exists(f):
                        size = os.path.getsize(f) / 1024 # KB
                        st.markdown(f"- ✅ `{f}`: {size:.2f} KB")
                    else:
                        st.markdown(f"- ❌ `{f}`: 없음")

            # Visitor Stats
            with col2:
                st.markdown("#### 👥 방문자 현황")
                total_v, today_v = update_visit_stats()
                st.metric("총 방문자", f"{total_v:,}명")
                st.metric("오늘 방문자", f"{today_v:,}명")

        # --- Tab 2: News Management ---
        with tab2:
            st.subheader("뉴스 데이터 관리")
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
                            
                            col_del, col_save = st.columns([1, 1])
                            if col_save.button("수정 저장", key=f"save_{selected_date_edit}_{i}"):
                                topics[i]['title'] = new_title
                                topics[i]['summary'] = new_summary
                                topics[i]['category'] = new_category
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

        # --- Tab 3: Community Management ---
        with tab3:
            st.subheader("댓글 관리")
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
        
else:
    # --- Viewer Mode ---
    # Visitor Counter Logic & UI (Main Header)
    total_v, today_v = update_visit_stats()
    
    # --- Dark/Light Mode Toggle ---
    col_t1, col_t2 = st.columns([8, 2])
    with col_t1:
        st.title("🇹🇭 태국 뉴스 브리핑")
        st.caption("AI가 엄선한 태국의 주요 이슈를 매일 실시간 업데이트 하여 전해드립니다.")
    with col_t2:
        # Default False (Light Mode)
        is_dark = st.toggle("🌘 다크 모드", value=False)
        
    # Define Theme Colors based on Toggle
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

    # Visitor Counter & Exchange Rate
    # Dynamic Styling for Visitor Counter
    if is_dark:
        vc_bg = "#000000"
        vc_text = "#ffffff"
        vc_border = "1px solid #333"
    else:
        vc_bg = "#f0f2f6"
        vc_text = "#31333F"
        vc_border = "none"

    st.markdown(f"""
    <div style="text-align: right; margin-top: -30px; margin-bottom: 20px;">
        <span style="background-color: {vc_bg}; color: {vc_text}; border: {vc_border}; padding: 4px 10px; border-radius: 4px; font-size: 0.8em;">
            👀 Total: <b>{total_v:,}</b> / Today: <b>{today_v:,}</b>
        </span>
    </div>
    """, unsafe_allow_html=True)

    # --- Top Widgets (Exchange Rate & Air Quality) ---
    col_w1, col_w2 = st.columns(2)

    # 1. Exchange Rate Widget (Left)
    with col_w1:
        @st.cache_data(ttl=3600) # Cache for 1 hour
        def get_cached_exchange_rate():
            return utils.get_thb_krw_rate()

        try:
            # Use Cached Wrapper
            rate = get_cached_exchange_rate()
            now_str = datetime.now().strftime("%m/%d %H:%M")   
            
            st.markdown(f"""
            <div style="
                padding: 15px; 
                border-radius: 12px; 
                background-color: {card_bg}; 
                border: 1px solid {border_color}; 
                margin-bottom: 20px; 
                display: flex; 
                align-items: center; 
                justify-content: space-between;
                backdrop-filter: blur(5px);
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            ">
                <div style="display: flex; flex-direction: column;">
                    <span style="font-weight: bold; color: {text_sub}; font-size: 0.9rem;">💰 바트 환율</span>
                    <span style="font-size: 0.75em; color: #888;">{now_str} 기준</span>
                </div>
                <div style="font-size: 1.2em; font-weight: bold; color: {text_main};">
                    <span style="font-size: 0.6em; color: #aaa; margin-right: 3px;">1 THB =</span>
                    {rate:.2f} <span style="font-size: 0.6em; color: #aaa;">KRW</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.error("환율 로드 실패")
    
    # 2. Air Quality Widget (Right)
    with col_w2:
        try:
            waqi_token = st.secrets.get("WAQI_API_KEY", "")
            # Use Cached Wrapper
            aqi_data = get_cached_air_quality(waqi_token)
            
            if aqi_data:
                aqi = aqi_data['aqi']
                
                # Dynamic Styling based on AQI
                if aqi <= 50:
                    aqi_color = "#00e400" # Green (Good)
                    aqi_icon = "😊"
                    aqi_text = "좋음"
                elif aqi <= 100:
                    aqi_color = "#ffff00" # Yellow (Moderate)
                    aqi_icon = "😐"
                    aqi_text = "보통"
                elif aqi <= 150:
                    aqi_color = "#ff7e00" # Orange (Unhealthy for Sensitive)
                    aqi_icon = "😷"
                    aqi_text = "민감군 나쁨"
                else:
                    aqi_color = "#ff004c" # Red (Unhealthy)
                    aqi_icon = "☠️"
                    aqi_text = "나쁨"
                    
                st.markdown(f"""
                <div style="
                    padding: 15px; 
                    border-radius: 12px; 
                    background-color: {card_bg}; 
                    border: 1px solid {border_color}; 
                    margin-bottom: 20px; 
                    display: flex; 
                    align-items: center; 
                    justify-content: space-between;
                    backdrop-filter: blur(5px);
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                ">
                    <div style="display: flex; flex-direction: column;">
                        <span style="font-weight: bold; color: {text_sub}; font-size: 0.9rem;">🌫️ 방콕 공기 ({aqi_text})</span>
                        <span style="font-size: 0.75em; color: #888;">실시간 PM 2.5</span>
                    </div>
                    <div style="font-size: 1.2em; font-weight: bold; color: {aqi_color};">
                        {aqi_icon} {aqi}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # No Data / Error Placeholder
                st.markdown(f"""
                <div style="
                    padding: 20px; 
                    border-radius: 12px; 
                    background-color: {card_bg}; 
                    border: 1px solid {border_color}; 
                    color: {text_sub}; text-align: center; font-size: 0.8rem;
                ">
                    🌫️ 공기질 데이터 없음
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"AQI Error")

    # --- Mobile Control Panel (Always Visible) ---
    col_date, col_search = st.columns([1, 2], gap="small")
    
    # Data Preparation for Date Picker
    news_data = load_news_data()
    all_dates_str = sorted(news_data.keys())
    valid_dates = []
    for d_str in all_dates_str:
        try:
            valid_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
        except:
            continue
    
    if valid_dates:
        min_date = min(valid_dates)
        max_date = datetime.today().date()
        # Always default to TODAY, even if not in list yet
        default_date = datetime.today().date()
    else:
        min_date = datetime.today().date()
        max_date = datetime.today().date()
        default_date = datetime.today().date()

    # 1. Date Input
    with col_date:
        # If searching, date is visually 'disabled' or second class.
        # But in "Always Visible" UI, we handle search precedence in logic.
        if "search_query" not in st.session_state:
             st.session_state["search_query"] = ""
             
        is_searching = bool(st.session_state["search_query"])
        
        selected_date_obj = st.date_input(
            "날짜",
            value=default_date,
            min_value=min_date,
            max_value=max_date,
            label_visibility="collapsed",
            disabled=is_searching
        )
        selected_date = selected_date_obj.strftime("%Y-%m-%d")

    # 2. Search Input
    with col_search:
        search_query = st.text_input(
            "검색", 
            placeholder="키워드 검색 (예: 비자, 환율)", 
            key="search_query_mobile", 
            value=st.session_state["search_query"],
            label_visibility="collapsed"
        )
        
        # Sync Logic
        if search_query != st.session_state["search_query"]:
             st.session_state["search_query"] = search_query
             st.rerun()

    # Clear Search Button (Conditional)
    if is_searching:
        if st.button("🔄 검색 초기화 (전체 목록 보기)", use_container_width=True):
            st.session_state["search_query"] = ""
            st.rerun()

    # Logic to prepare topics based on selection
    daily_topics = []
    header_text = ""
    
    # Initialize all_comments_data properly
    all_comments_data = get_all_comments()

    if search_query:
        news_data = load_news_data()
        found_topics = []
        for d, topics in news_data.items():
            for t in topics:
                if search_query in t['title'] or search_query in t['summary']:
                    t_with_date = t.copy()
                    t_with_date['date_str'] = d
                    found_topics.append(t_with_date)
        found_topics.sort(key=lambda x: x.get('date_str', ''), reverse=True)
        daily_topics = found_topics
        header_text = f"🔍 '{search_query}' 검색 결과 (총 {len(found_topics)}건)"
        
    elif selected_date:
        news_data = load_news_data()
        if selected_date in news_data:
            daily_topics = news_data[selected_date]
            daily_topics = list(reversed(daily_topics))
        header_text = f"📅 {selected_date} 브리핑"

    # 2. Share Helper
    if daily_topics:
        with st.expander("📋 카톡 공유용 텍스트 생성 (전체 브리핑)"):
            share_text = f"[🇹🇭 태국 뉴스룸 브리핑 - {search_query if search_query else selected_date}]\n\n"
            target_list = daily_topics[:5]
            for idx, item in enumerate(target_list):
                share_text += f"{idx+1}. {item['title']}\n"
                share_text += f"- {item['summary'][:60]}...\n\n"
            share_text += f"👉 더 보기: {DEPLOY_URL}"
            st.code(share_text, language="text")

    if daily_topics:
        filtered_topics = []
        if not search_query: 
            st.write("")
            categories_available = ["전체", "정치/사회", "경제", "여행/관광", "사건/사고", "엔터테인먼트", "기타"]
            
            # Use st.pills for touch-friendly filter
            try:
                selected_category = st.pills("카테고리 필터", categories_available, default="전체", selection_mode="single")
                if not selected_category: # Handle None if unselected
                    selected_category = "전체"
            except AttributeError:
                # Fallback if older streamlit
                selected_category = st.radio("카테고리 필터", categories_available, horizontal=True, label_visibility="collapsed")
            
            if selected_category == "전체":
                filtered_topics = daily_topics
            else:
                filtered_topics = [t for t in daily_topics if t.get("category", "기타") == selected_category]
        else:
            filtered_topics = daily_topics

        st.divider()
        st.header(header_text)
        
        # Empty State for Selected Date (Today)
        if not daily_topics and not search_query:
             st.info("😴 아직 업데이트된 뉴스가 없습니다. (잠시 후 다시 확인해주세요)", icon="⏳")
        elif not filtered_topics:
            st.info("조건에 맞는 뉴스가 없습니다.")
        
        for topic in filtered_topics:

            with st.container():
                col_badg, col_time = st.columns([1, 5])
                cat_text = topic.get("category", "기타")
                date_display = topic.get('date_str', '')
                time_display = topic.get('collected_at', '')
                meta_info = f"{date_display} {time_display}".strip()
                
                st.markdown(f"**🏷️ {cat_text}** <span style='color:grey'> | 🕒 {meta_info}</span>", unsafe_allow_html=True)
                
                st.subheader(f"{topic['title']}")
                
                if topic.get('image_url'):
                    st.image(topic['image_url'], use_container_width=True)
                
                # 3. Highlight Keywords
                final_summary = highlight_text(topic['summary'])
                st.markdown(final_summary)

                # 3.5 Full Article View (NEW)
                with st.expander("📄 기사 전문 보기"):
                    full_text = topic.get('full_translated', '⚠️ 이 기사는 요약본만 제공됩니다. (다음 뉴스 업데이트부터 전문이 제공됩니다.)')
                    st.markdown(full_text)
                
                # 4. Individual Share (NEW)
                with st.expander("🔗 이 기사 공유하기"):
                    ind_share = f"[태국 뉴스룸]\n{topic['title']}\n\n- {topic['summary']}\n\n👉 원문: {topic.get('references', [{'url':'#'}])[0].get('url')}\n🌐 뉴스룸: {DEPLOY_URL}"
                    st.code(ind_share, language="text")

                with st.expander("🔗 관련 기사 원문 보기"):
                    for ref in topic.get('references', []):
                        title = ref.get('title', 'No Title')
                        url = ref.get('url', '#')
                        source = ref.get('source', 'Unknown Source')
                        st.markdown(f"- [{title}]({url}) - *{source}*")
                        
                # --- 댓글 기능 (Added) ---
                news_id = generate_news_id(topic['title'])
                comments = all_comments_data.get(news_id, [])
                
                with st.expander(f"💬 댓글 ({len(comments)})"):
                    # 1. Existing Comments
                    if not comments:
                        st.caption("아직 댓글이 없습니다. 첫 번째 댓글을 남겨보세요!")
                    else:
                        for c in comments:
                            st.markdown(f"**{c['user']}**: {c['text']} <span style='color:grey; font-size:0.8em'>({c.get('date', '')})</span>", unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # 2. New Comment Form
                    with st.form(key=f"comm_form_{news_id}"):
                        col1, col2 = st.columns([1, 3])
                        nick = col1.text_input("닉네임", placeholder="익명")
                        txt = col2.text_input("내용", placeholder="이 기사에 대한 의견을 남겨주세요")
                        submit = st.form_submit_button("등록")
                        
                        if submit and txt:
                            # 1. Spam Protection (Rate Limiting)
                            last_time = st.session_state.get("last_comment_time", 0)
                            current_time = time.time()
                            
                            if current_time - last_time < 60:
                                st.toast("🚫 도배 방지를 위해 1분 뒤에 다시 작성해주세요.", icon="🚫")
                            else:
                                # 2. XSS Prevention (Input Sanitization)
                                safe_nick = html.escape(nick)
                                safe_txt = html.escape(txt)
                                
                                save_comment(news_id, safe_nick, safe_txt)
                                
                                # Update last comment time
                                st.session_state["last_comment_time"] = current_time
                                
                                st.toast("댓글이 등록되었습니다!", icon="✅")
                                time.sleep(1) # delay
                                st.rerun()

                st.divider()

    else:
        if not daily_topics:
             st.info("📭 해당 날짜에는 수집된 뉴스가 없습니다.")
        else:
             st.info("👈 왼쪽 사이드바에서 날짜를 선택해주세요.")
