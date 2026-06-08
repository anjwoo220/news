#!/usr/bin/env python3
"""
🕷️ 태국 한국인 채용 공고 크롤러
====================================
타겟 사이트:
  1. HanAsia (한아시아)       - https://www.hanasia.com/구인구직
  2. KyominThai (교민잡지)    - http://kyominthai.com (구인 게시판)
  3. Saramin (사람인 해외)    - https://m.saramin.co.kr (태국 지역)
  4. JobThai (잡타이)         - https://www.jobthai.com (Korean 키워드)
  5. JobsDB Thailand          - https://th.jobsdb.com (Korean 키워드)

Gemini API로 영어/태국어→한국어 번역·요약 → Google Sheets "Jobs" 워크시트에 저장
로컬 실행 또는 GitHub Actions로 자동화 가능
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import json
import re
import os
from datetime import datetime

# ── Google Sheets (gspread) ──────────────────────────────────
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ── Gemini API ───────────────────────────────────────────────
import google.generativeai as genai


# ============================================================
# 설정 (Configuration)
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 시트 컬럼 순서
SHEET_COLUMNS = [
    "카테고리", "게시일", "출처", "직무명", "회사명", "급여",
    "위치", "업무요약", "자격요건", "원본링크", "수집일시"
]


def _sleep():
    """요청 사이 랜덤 대기 (크롤링 차단 방지)"""
    time.sleep(random.uniform(2.0, 4.0))


def convert_buddhist_era(date_str):
    """
    태국 불기(Buddhist Era) 연도를 서기(CE)로 변환.
    예: 2569 → 2026, 25/02/2569 → 25/02/2026
    """
    if not date_str:
        return date_str
    # 4자리 연도가 25xx이면 불기로 간주
    def _convert_year(match):
        year = int(match.group(0))
        if 2500 <= year <= 2600:
            return str(year - 543)
        return match.group(0)
    return re.sub(r'\b2[5][0-9]{2}\b', _convert_year, date_str)


# ============================================================
# 1. HanAsia 크롤러
# ============================================================

def crawl_hanasia(max_pages=1):
    """
    한아시아(hanasia.com) 구인구직 게시판에서 채용 글 수집.
    JS 렌더링이 필요하므로 Playwright 사용.
    """
    jobs = []
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [HanAsia] playwright 미설치, 건너뜀")
        return jobs

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            
            base_url = "https://www.hanasia.com/%EA%B5%AC%EC%9D%B8%EA%B5%AC%EC%A7%81"
            
            for p_num in range(1, max_pages + 1):
                url = f"{base_url}?page={p_num}" if p_num > 1 else base_url
                print(f"  [HanAsia] 페이지 {p_num} 크롤링: {url}")
                
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(3) # 추가 렌더링 대기
                
                # 게시물 추출
                raw_posts = page.evaluate("""() => {
                    const links = document.querySelectorAll('.tpl-forum-list-title a');
                    return Array.from(links).map(a => ({
                        title: a.textContent.trim(),
                        href: a.href
                    }));
                }""")
                
                for post in raw_posts:
                    title = post["title"]
                    href = post["href"]
                    
                    # 채용 관련 글 필터
                    job_keywords = ["구인", "채용", "모집", "직원", "스탭", "인턴", "매니저", "recruit", "hiring"]
                    if not any(kw in title.lower() for kw in job_keywords):
                        continue
                    
                    jobs.append({
                        "출처": "HanAsia",
                        "직무명": title[:100],
                        "회사명": "",
                        "급여": "",
                        "위치": "태국",
                        "업무요약": "",
                        "자격요건": "",
                        "원본링크": href,
                        "게시일": "",
                    })
            
            browser.close()
    except Exception as e:
        print(f"  [HanAsia] 크롤링 오류: {e}")

    print(f"  [HanAsia] 총 {len(jobs)}건 수집")
    return jobs


# ============================================================
# 2. KyominThai 크롤러
# ============================================================

def crawl_kyominthai(max_pages=1):
    """
    교민잡지(kyominthai.com) 구인 게시판 수집.
    직접 쿼리 스트링을 사용하여 검색 필터링된 페이지 접근.
    """
    jobs = []
    # 한글 검색어 "구인"을 포함한 URL (인코딩됨)
    base_url = "http://kyominthai.com/sub/sub08.php?board=30&board_search_headword=%EA%B5%AC%EC%9D%B8"

    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}&board_page={page}"
            print(f"  [KyominThai] 페이지 {page} 크롤링: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # 새로운 구조: section.box.feature 내부의 h2.board_title
            items = soup.select("section.box.feature, article.box.feature")
            if not items:
                # 레거시 구조 대응
                items = soup.select("table tr, div.board-list li, div.list-item")

            for item in items:
                link_tag = item.select_one("h2.board_title a, a[href*='board_mode=view']")
                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                href = link_tag.get("href", "")

                # 절대 URL 변환 (기존 /sub/ 가 포함되어 있으면 도메인만 붙임)
                if href and not href.startswith("http"):
                    href = "http://kyominthai.com" + href

                # 날짜 추출: h2 다음의 p 태그 또는 특정 클래스
                date_text = ""
                date_tag = item.select_one("h2 + p, p.date, span.date, td:nth-child(4)")
                if date_tag:
                    date_text = date_tag.get_text(strip=True)
                    # "2026/03/04 13:16:26" -> "2026-03-04"
                    date_match = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", date_text)
                    if date_match:
                        date_text = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

                jobs.append({
                    "출처": "교민잡지",
                    "직무명": title.replace("[구인]", "").strip()[:100],
                    "회사명": "",
                    "급여": "",
                    "위치": "태국",
                    "업무요약": "",
                    "자격요건": "",
                    "원본링크": href,
                    "게시일": date_text,
                })

            _sleep()
        except Exception as e:
            print(f"  [KyominThai] 페이지 {page} 오류: {e}")
            continue

    print(f"  [KyominThai] 총 {len(jobs)}건 수집")
    return jobs


# ============================================================
# 3. 사람인 (Saramin) 크롤러
# ============================================================

def crawl_saramin():
    """
    사람인 해외취업 > 태국 지역 (loc_cd=211500) 최신 채용 공고 수집.
    사람인은 모든 글이 채용이므로 별도 필터 불필요.
    """
    jobs = []
    url = "https://m.saramin.co.kr/location-job/recently-list"
    params = {
        "loc_cd": "211500",
        "is_detail_search": "y",
    }

    try:
        print("  [Saramin] 태국 채용 목록 크롤링")
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 사람인 모바일 채용 카드 셀렉터
        cards = (
            soup.select("a[href*='job-search/view']") or
            soup.select("div.list_item a, li.list_item a")
        )

        seen_links = set()
        for card in cards:
            href = card.get("href", "")
            if not href or "rec_idx" not in href:
                continue

            # 중복 링크 제거
            rec_match = re.search(r"rec_idx=(\d+)", href)
            rec_id = rec_match.group(1) if rec_match else href
            if rec_id in seen_links:
                continue
            seen_links.add(rec_id)

            # 절대 URL
            if not href.startswith("http"):
                href = "https://m.saramin.co.kr" + href

            # 제목 추출
            title = card.get_text(strip=True)
            # 이미지나 너무 짧은 텍스트는 건너뛰기
            if len(title) < 5 or title.startswith("기업이미지"):
                continue

            # 회사명 / 조건 추출 시도 (카드 내부 구조)
            company = ""
            company_tag = card.select_one("span.company, div.company_nm")
            if company_tag:
                company = company_tag.get_text(strip=True)

            # 제목 정리: 날짜(~03.26(목)) 등 제거
            title_clean = re.sub(r"~?\d{2}\.\d{2}\([가-힣]\)|D-\d+|채용시|기업이미지", "", title).strip()
            # 회사명이 제목에 포함되어 있으면 분리
            for sep in ["아시아·중동 태국"]:
                if sep in title_clean:
                    parts = title_clean.split(sep)
                    title_clean = parts[0].strip()
                    if len(parts) > 1:
                        remaining = parts[1].strip()
                        # 경력/학력 등 조건 정보와 회사명 분리
                        for comp_candidate in remaining.split("\n"):
                            comp_candidate = comp_candidate.strip()
                            if comp_candidate and not any(kw in comp_candidate for kw in ["경력", "학력", "대졸", "초대졸", "무관", "운영", "수당"]):
                                if not company:
                                    company = comp_candidate[:50]

            # 마감일 추출 (사람인 카드에서 ~03.26(목) 등)
            deadline = ""
            deadline_match = re.search(r'~?(\d{2}\.\d{2})\([가-힣]\)', title)
            if deadline_match:
                deadline = f"~{deadline_match.group(1)}"
            d_match = re.search(r'D-(\d+)', title)
            if d_match:
                deadline = f"D-{d_match.group(1)}"

            jobs.append({
                "출처": "사람인",
                "직무명": title_clean[:100],
                "회사명": company,
                "급여": "",
                "위치": "태국",
                "업무요약": "",
                "자격요건": "",
                "원본링크": href,
                "게시일": "",
            })

    except Exception as e:
        print(f"  [Saramin] 크롤링 오류: {e}")

    print(f"  [Saramin] 총 {len(jobs)}건 수집")
    return jobs


# ============================================================
def crawl_jobthai():
    """
    JobThai(jobthai.com)에서 'Korean' 키워드로 검색된 채용 공고 수집.
    JS 렌더링이 필요하므로 Playwright 사용.
    """
    jobs = []
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [JobThai] playwright 미설치, 건너뜀")
        return jobs

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            
            url = "https://www.jobthai.com/th/jobs?keyword=Korean"
            print(f"  [JobThai] 크롤링: {url}")
            
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) # 렌더링 대기
            
            # 게시물 추출 (id 패턴 매칭)
            raw_jobs = page.evaluate("""() => {
                const items = document.querySelectorAll('a[id^="job-list-job-"]:not([id="job-list-job-on-map"])');
                return Array.from(items).map(item => {
                    const h2s = item.querySelectorAll('h2');
                    return {
                        title: h2s.length > 0 ? h2s[0].textContent.trim() : '',
                        company: h2s.length > 1 ? h2s[1].textContent.trim() : '',
                        href: item.href
                    };
                }).filter(j => j.title && j.href);
            }""")
            
            for item in raw_jobs:
                title = item["title"]
                
                # 한국 관련 필터
                if not is_korean_related_job(title):
                    continue
                
                jobs.append({
                    "출처": "JobThai",
                    "직무명": title[:100],
                    "회사명": item["company"],
                    "급여": "",
                    "위치": "태국",
                    "업무요약": "",
                    "자격요건": "",
                    "원본링크": item["href"],
                    "게시일": "",
                })
            
            browser.close()
    except Exception as e:
        print(f"  [JobThai] 크롤링 오류: {e}")

    print(f"  [JobThai] 총 {len(jobs)}건 수집")
    return jobs


def is_korean_related_job(title):
    """
    제목에 한국 관련 키워드가 있는지 확인하여 무관한 공고(예: Service Engineer, Japanese Interpreter)를 필터링합니다.
    """
    if not title:
        return False
        
    title_lower = title.lower()
    
    # 1. 1차 긍정 키워드 (오직 한국/한국어 관련 단어만 포함)
    keywords = [
        "korean", "korea", "เกาหลี", "한국", "한국어", "한국인"
    ]
    is_match = any(k in title_lower for k in keywords)
    
    # 2. 2차 부정 키워드 (만약 타이틀에 한국어가 있더라도 다른 언어가 메인인 어뷰징 방지)
    # ex: "Japanese Interpreter (Welcome Korean too)" -> 이런 예외도 제거 원할 시
    exclusions = ["japanese", "chinese", "ญี่ปุ่น", "จีน", "일본어", "중국어"]
    has_exclusion = any(e in title_lower for e in exclusions)
    
    return is_match and not has_exclusion


# ============================================================
# 5. JobsDB Thailand 크롤러 (Playwright 헤드리스 브라우저)
# ============================================================

def _parse_relative_date(date_text):
    """
    JobsDB의 상대 날짜("27d ago", "1mo ago")를 YYYY-MM-DD로 변환.
    """
    from datetime import timedelta

    if not date_text:
        return ""

    days_match = re.search(r"(\d+)d\s*ago", date_text)
    if days_match:
        days_ago = int(days_match.group(1))
        return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    months_match = re.search(r"(\d+)mo\s*ago", date_text)
    if months_match:
        months_ago = int(months_match.group(1))
        return (datetime.now() - timedelta(days=months_ago * 30)).strftime("%Y-%m-%d")

    hours_match = re.search(r"(\d+)h\s*ago", date_text)
    if hours_match:
        return datetime.now().strftime("%Y-%m-%d")

    return ""


def crawl_jobsdb():
    """
    JobsDB Thailand(th.jobsdb.com)에서 'korean-jobs' 페이지 채용 공고 수집.
    React SPA이므로 Playwright 헤드리스 브라우저로 JS 렌더링 후 데이터 추출.
    """
    jobs = []
    seen_ids = set()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [JobsDB] playwright 미설치, 건너뜀 (pip install playwright)")
        return jobs

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
            )
            page = ctx.new_page()

            try:
                url = "https://th.jobsdb.com/korean-jobs"
                print(f"  [JobsDB] 크롤링: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(8)  # React SPA 렌더링 대기

                # page.evaluate()로 렌더링된 DOM에서 직접 추출
                raw_jobs = page.evaluate("""() => {
                    const articles = document.querySelectorAll('article');
                    return Array.from(articles).map(a => {
                        const titleEl = a.querySelector('a[data-automation="jobTitle"]');
                        const compEl = a.querySelector('a[data-automation="jobCompany"]');
                        const locEl = a.querySelector('a[data-automation="jobLocation"]');
                        const dateEl = a.querySelector('span[data-automation="jobListingDate"]');
                        const salEl = a.querySelector('span[data-automation="jobSalary"]');
                        return {
                            title: titleEl ? titleEl.textContent.trim() : '',
                            href: titleEl ? titleEl.href : '',
                            company: compEl ? compEl.textContent.trim() : '',
                            location: locEl ? locEl.textContent.trim() : '',
                            date: dateEl ? dateEl.textContent.trim() : '',
                            salary: salEl ? salEl.textContent.trim() : ''
                        };
                    }).filter(j => j.title && j.href);
                }""")

                print(f"    {len(raw_jobs)}건 발견")

                def parse_jobsdb_salary(salary_str):
                    if not salary_str:
                        return 0
                    # "THB 50,000 - THB 80,000" -> extract max or average. Let's extract max.
                    nums = [int(n.replace(',', '')) for n in re.findall(r'\b\d{2,3}(?:,\d{3})+\b', salary_str)]
                    if not nums:
                        return 0
                    return max(nums)

                for item in raw_jobs:
                    title = item.get("title", "")
                    
                    # 한국인/한국어 관련 채용인지 강력하게 필터링
                    if not is_korean_related_job(title):
                        continue
                        
                    # 급여 50,000 바트 이상 필터
                    raw_salary = item.get("salary", "")
                    max_sal = parse_jobsdb_salary(raw_salary)
                    if raw_salary and max_sal > 0 and max_sal < 50000:
                        print(f"    [급여 미달 필터링] {title} (최대급여: {max_sal} THB)")
                        continue
                        
                    href = item.get("href", "")
                    # URL에서 job ID 추출하여 중복 체크
                    job_id_match = re.search(r"/job/(\d+)", href)
                    job_id = job_id_match.group(1) if job_id_match else href
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # --- 상세 내용 추가 추출 (Playwright 세션 내) ---
                    print(f"    [JobsDB] 상세 내용 추출 중: {title[:30]}...")
                    detail_text = ""
                    try:
                        # 별도 탭/페이지보다는 현재 페이지 이동 후 뒤로 가기 방식이 안정적
                        detail_url = href.split("#")[0].split("?")[0]
                        if not detail_url.startswith("http"):
                            detail_url = "https://th.jobsdb.com" + detail_url
                        
                        # 지연 시간을 조금 더 주어 봇 감지 회피 시도
                        page.goto(detail_url, wait_until="networkidle", timeout=30000)
                        time.sleep(5) # SSR/React 렌더링 추가 대기
                        
                        desc_text = page.evaluate("""() => {
                            const desc = document.querySelector('[data-automation="jobDescription"]');
                            return desc ? desc.innerText : '';
                        }""")
                        
                        if not desc_text:
                            # 다른 선택자 시도 (가장 텍스트가 많은 div 검색 - 본문일 가능성 높음)
                            desc_text = page.evaluate("""() => {
                                let maxLen = 0;
                                let bestText = '';
                                document.querySelectorAll('div, section, article').forEach(el => {
                                    const text = el.innerText || '';
                                    if (text.length > maxLen && text.length < 10000) {
                                        maxLen = text.length;
                                        bestText = text;
                                    }
                                });
                                return bestText;
                            }""")

                        if desc_text:
                            detail_text = desc_text
                            print(f"      추출 성공 ({len(detail_text)}자)")
                        else:
                            print("      추출 내용 없음 (선택자 확인 필요)")
                        
                        # 목록으로 복귀
                        page.go_back(wait_until="domcontentloaded")
                        time.sleep(2)
                    except Exception as de:
                        print(f"      상세 추출 실패: {de}")

                    # 게시일 변환 ("27d ago" → YYYY-MM-DD)
                    post_date = _parse_relative_date(item.get("date", ""))

                    jobs.append({
                        "출처": "JobsDB",
                        "직무명": title[:100],
                        "회사명": item.get("company", ""),
                        "급여": item.get("salary", ""),
                        "위치": item.get("location", "") or "태국",
                        "업무요약": "",
                        "자격요건": "",
                        "원본링크": href,
                        "게시일": post_date,
                        "detail_text": detail_text # 임시 저장 (요약 시 사용)
                    })
                    _sleep() # 과도한 요청 방지
                _sleep()
            except Exception as e:
                print(f"  [JobsDB] 크롤링 오류: {e}")

            browser.close()
    except Exception as e:
        print(f"  [JobsDB] Playwright 오류: {e}")

    print(f"  [JobsDB] 총 {len(jobs)}건 수집")
    return jobs


# ============================================================
# 상세 페이지 크롤링 및 이미지 추출 (멀티모달 AI 연동)
# ============================================================

def fetch_detail_content(url, max_chars=2000):
    """
    개별 채용 공고의 상세 페이지에서 본문 텍스트와 핵심 이미지 URL들을 가져옴.
    반환: (text_content, list_of_image_urls)
    """
    text = ""
    img_urls = []
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        
        # 4xx, 5xx 에러인 경우 빈 값 반환
        if resp.status_code >= 400:
            print(f"    상세 페이지 접근 실패 (Status {resp.status_code}): {url}")
            return "", []

        resp.encoding = "utf-8"
        
        # 페이지 내용에 404나 '찾을 수 없습니다'와 같은 문구가 지배적인지 확인
        error_keywords = ["요청하신 URL을 찾을 수 없습니다", "페이지를 찾을 수 없습니다", "404 Not Found", "Object not found"]
        if any(kw in resp.text for kw in error_keywords) and len(resp.text) < 5000:
            print(f"    상세 페이지 오류 문구 감지: {url}")
            return "", []

        soup = BeautifulSoup(resp.text, "html.parser")

        # 사람인의 경우 본문이 iframe 안에 숨겨져 있음
        if "saramin.co.kr" in url:
            # URL에서 rec_idx 추출
            rec_match = re.search(r"rec_idx=(\d+)", url)
            if rec_match:
                rec_idx = rec_match.group(1)
                
                # 시도 1: 모바일 iframe Endpoint
                iframe_urls = [
                    f"https://m.saramin.co.kr/job-search/iframe-recruit-detail?rec_idx={rec_idx}",
                    f"https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx={rec_idx}"
                ]
                
                for iframe_url in iframe_urls:
                    try:
                        i_resp = requests.get(iframe_url, headers=HEADERS, timeout=10)
                        i_soup = BeautifulSoup(i_resp.text, "html.parser")
                        
                        # 텍스트 추출 (누적)
                        extracted = i_soup.get_text(separator="\n", strip=True)
                        if extracted and len(extracted) > len(text):
                            text = extracted
                        
                        # 이미지 추출
                        for img in i_soup.find_all("img"):
                            src = img.get("src", "")
                            # 서빙용/트래킹용 의미없는 이미지 필터링
                            if src and "file_sri" not in src and "tpl" not in src and "logo" not in src:
                                if src.startswith("//"):
                                    src = "https:" + src
                                elif src.startswith("/"):
                                    src = "https://www.saramin.co.kr" + src
                                if src not in img_urls: # 중복 방지
                                    img_urls.append(src)
                        
                        # 이미지를 하나라도 찾았으면 루프 종료
                        if img_urls:
                            print(f"    [Saramin] Found {len(img_urls)} images in {iframe_url.split('/')[2]}.")
                            break
                    except Exception as ie:
                        print(f"    [Saramin] Iframe 접근 실패 ({iframe_url}): {ie}")
                    
        # 기본 텍스트 추출 (사람인이 아니거나 iframe 실패 시 대비)
        if not text:
            content = (
                soup.select_one("div.view_content, div.board_view, div.cont_wrap, "
                                "div.job_summary, div#content, article, main")
            )
            if content:
                text = content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

        # 텍스트 정리
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)
        
        return text[:max_chars], img_urls
    except Exception as e:
        print(f"    상세 페이지 접근 실패: {e}")
        return "", []


import base64
def _download_and_encode_image(url):
    """URL에서 이미지를 다운로드하여 base64 문자열로 반환"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            encoded = base64.b64encode(resp.content).decode("utf-8")
            return {"mime_type": content_type, "data": encoded}
    except Exception as e:
        print(f"      이미지 다운로드 실패: {url[:50]}... ({e})")
    return None


# ============================================================
# Gemini AI 요약 / 번역 (Vision 포함)
# ============================================================

def summarize_with_gemini(jobs, api_key):
    """
    수집된 채용 공고 목록을 Gemini API로 한국어 JSON 요약.
    필요 시 이미지(Vision) 데이터를 함께 넘겨 OCR 수행.
    """
    genai.configure(api_key=api_key)
    # Gemini 모델 초기화 시 JSON 모드 강제 설정
    model = genai.GenerativeModel(
        "gemini-2.5-flash", 
        generation_config={"response_mime_type": "application/json"}
    )

    summarized = []

    for i, job in enumerate(jobs):
        print(f"  [{i+1}/{len(jobs)}] AI 요약 중: {job['직무명'][:40]}...")

        # 장소나 이미지 등 상세 정보 가져오기
        detail_text = job.get("detail_text", "")
        img_urls = []
        
        # 상세 내용이 없으면(또는 사민인처럼 이미지가 필요한 경우) fetch 시도
        if not detail_text or "saramin.co.kr" in job.get("원본링크", ""):
            if job["원본링크"]:
                fetched_text, img_urls = fetch_detail_content(job["원본링크"])
                # fetched_text가 더 길거나 detail_text가 없으면 엎어침
                if not detail_text or (fetched_text and len(fetched_text) > len(detail_text)):
                    detail_text = fetched_text
                _sleep()

        prompt_str = f"""다음은 태국에서의 채용 공고입니다.
내용이 영어나 태국어인 경우 반드시 한국어로 번역해주세요.
아래 정보를 분석해서 지정된 JSON 형식으로 완벽하게 정리해주세요.

[공고 제목] {job['직무명']}
[출처] {job['출처']}
[회사명] {job.get('회사명', '')}
[기존 게시일 정보] {job.get('게시일', '')}
[해독된 상세 텍스트]
{detail_text if detail_text else '(상세 텍스트 없음)'}

중요 규칙:
- 만약 이미지(스크린샷)가 첨부되었다면, **이미지 안의 텍스트(급여, 자격요건, 주요업무, 근무시간 등)를 완벽히 해독하여 반영**해주세요.
- 영어/태국어 직무명은 한국어로 번역하되, 원래 영어 명칭도 괄호로 병기 (예: "한국어 통역사 (Korean Interpreter)")
- 회사명은 번역하지 말고 원문 그대로 유지
- 태국어 지역명은 한국어 발음 표기 (예: กรุงเทพ → 방콕)
- 급여가 바트(฿/THB)인 경우 바트 단위 그대로 표시
- 게시일: 공고가 게시된 날짜를 찾아서 YYYY-MM-DD 형식으로 변환 (서기 변환 필수, 찾을 수 없으면 빈 문자열)
- 카테고리: 직무 내용을 분석하여 다음 중 하나로 지정 ('영업', '마케팅', 'IT/개발', 'CS/고객지원', '통번역', '경영지원', '기타')
- 이모지: 카테고리에 맞는 이모지를 선택하세요 (영업: 🤝, 마케팅: 📈, IT/개발: 💻, CS/고객지원: 🎧, 통번역: 🗣️, 경영지원: 📂, 기타: 💼)

다음 형식으로 정확히 응답해주세요 (JSON):
{{
  "카테고리": "분류된 카테고리 (예: IT/개발)",
  "직무명": "이모지가 포함된 한국어 직무명 (예: 💻 소프트웨어 엔지니어 (Software Engineer))",
  "회사명": "회사명 원문 그대로 (알 수 있으면, 모르면 빈 문자열)",
  "급여": "급여 정보 (알 수 있으면, 모르면 '협의')",
  "위치": "근무 위치 (한국어 표기, 예: 방콕)",
  "업무요약": "주요 업무 내용 2-3줄 한국어 요약",
  "자격요건": "자격 요건 2-3줄 한국어 요약",
  "게시일": "YYYY-MM-DD 형식 (찾을 수 없으면 빈 문자열)"
}}"""

        # 이미지 리스트 생성
        contents = [prompt_str]
        
        if img_urls:
            print(f"    - 첨부된 이미지 {len(img_urls)}장 처리 중...")
            for img_url in img_urls[:3]: # 비용 및 속도 문제로 최대 3장까지만 처리
                img_data = _download_and_encode_image(img_url)
                if img_data:
                    contents.append({
                        "mime_type": img_data["mime_type"],
                        "data": img_data["data"]
                    })
                    
        try:
            # 멀티모달 배열 전송
            response = model.generate_content(contents)
            # Response is forced to JSON, parsing directly
            parsed = json.loads(response.text)
            
            # Gemini가 가끔 리스트 형태로 [{...}] 응답할 때가 있으므로 처리
            if isinstance(parsed, list) and len(parsed) > 0:
                parsed = parsed[0]
                
            # 요약 결과가 '알 수 없음'이나 '시스템 오류' 등 무의미한 정보면 제외
            summary = parsed.get("업무요약", "")
            qual = parsed.get("자격요건", "")
            
            invalid_keywords = ["알 수 없음", "정보 없음", "찾을 수 없습니다", "확인할 수 없습니다", "시스템 오류"]
            if any(kw in summary for kw in invalid_keywords) and any(kw in qual for kw in invalid_keywords):
                print(f"    - [요약 품질 미달로 제외] {job['직무명']}")
                continue

            job["카테고리"] = parsed.get("카테고리", "기타")
            job["직무명"] = parsed.get("직무명", job["직무명"])
            job["회사명"] = parsed.get("회사명", job["회사명"]) or job["회사명"]
            job["급여"] = parsed.get("급여", "협의")
            job["위치"] = parsed.get("위치", "태국")
            job["업무요약"] = summary
            job["자격요건"] = qual
            
            # 게시일: Gemini가 찾은 값 우선, 없으면 크롤러에서 추출한 값
            gemini_date = parsed.get("게시일", "")
            if gemini_date:
                job["게시일"] = convert_buddhist_era(gemini_date)

        except Exception as e:
            print(f"    Gemini 오류 (JSON 파싱 포함): {e}")
            job["카테고리"] = "기타"
            # 실패 시 기존 크롤링 기본값 유지

        summarized.append(job)
        time.sleep(12)  # Gemini rate limit 고려 (1s는 너무 짧아 429 발생 가능)

    return summarized


# ============================================================
# Google Sheets 저장
# ============================================================

def get_gsheet_client():
    """로드 우선순위: Streamlit secrets.toml -> 환경변수(GOOGLE_CREDENTIALS_JSON) -> 로컬 JSON"""
    creds_json = None
    
    # 1) Streamlit secrets.toml 로드 시도 (GSheets Connection 설정 공유)
    try:
        import streamlit as st
        # update_news 워크플로우와 동일한 APP_SECRETS 내 키 구조 사용
        creds_dict = st.secrets.get("connections", {}).get("gsheets_news", {})
        if creds_dict and "type" in creds_dict:
            creds_json = json.dumps(dict(creds_dict))
            print("  [GSheets] Using credentials from Streamlit secrets.")
    except Exception as e:
        pass

    # 2) 환경변수 방식 (하위 호환성)
    if not creds_json:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            print("  [GSheets] Using credentials from GOOGLE_CREDENTIALS_JSON env.")

    if creds_json:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(creds_json)
            creds_path = f.name
    else:
        # 3) 로컬 JSON 파일 방식
        creds_path = os.path.join(os.path.dirname(__file__),
                                  "board-484107-65691b0765f5.json")
        print(f"  [GSheets] Using local credential file: {os.path.basename(creds_path)}")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    return client


def save_to_gsheets(jobs):
    """
    Google Sheets "Jobs" 워크시트에 새 공고만 추가.
    중복 판단: 원본링크 기준.
    """
    if not jobs:
        print("저장할 공고가 없습니다.")
        return

    client = get_gsheet_client()

    # 스프레드시트 열기 (기존 board 시트와 같은 스프레드시트)
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xa6Vwpx7jhaT_YqX6n1pvh0VdLY4N277hdq3QWMNEV8"
    spreadsheet = client.open_by_url(SPREADSHEET_URL)

    # "Jobs" 워크시트 가져오기 (없으면 새로 생성)
    try:
        worksheet = spreadsheet.worksheet("Jobs")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="Jobs", rows=1000, cols=10)
        # 헤더 행 추가
        worksheet.append_row(SHEET_COLUMNS, value_input_option="USER_ENTERED")
        print("  'Jobs' 워크시트 새로 생성됨")

    # 기존 데이터에서 원본링크 목록 가져오기 (중복 방지)
    existing_data = worksheet.get_all_values()
    if existing_data:
        # 헤더가 있으면 원본링크 컬럼 인덱스 찾기
        header = existing_data[0]
        try:
            link_col_idx = header.index("원본링크")
        except ValueError:
            link_col_idx = 8  # 기본값
        existing_links = {row[link_col_idx] for row in existing_data[1:] if len(row) > link_col_idx}
    else:
        # 빈 시트 — 헤더 추가
        worksheet.append_row(SHEET_COLUMNS, value_input_option="USER_ENTERED")
        existing_links = set()

    # 새 공고만 필터링
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_jobs = []
    for job in jobs:
        if job["원본링크"] and job["원본링크"] not in existing_links:
            posting_date = job.get("게시일", "")
            if not posting_date:
                posting_date = datetime.now().strftime("%Y-%m-%d")
            row = [
                job.get("카테고리", "기타"),
                posting_date,
                job.get("출처", ""),
                job.get("직무명", ""),
                job.get("회사명", ""),
                job.get("급여", ""),
                job.get("위치", ""),
                job.get("업무요약", ""),
                job.get("자격요건", ""),
                job.get("원본링크", ""),
                now, # 수집일시
            ]
            new_jobs.append(row)

    if new_jobs:
        # 일괄 추가 (효율적)
        worksheet.append_rows(new_jobs, value_input_option="USER_ENTERED")
        print(f"✅ 새 공고 {len(new_jobs)}건 추가 완료!")
    else:
        print("ℹ️ 새로운 공고가 없습니다 (모두 중복).")

    print(f"  기존 링크: {len(existing_links)}개 / 이번 수집: {len(jobs)}개 / 신규: {len(new_jobs)}개")


# ============================================================
# 메인 실행
# ============================================================

import sys

def main():
    try:
        print("=" * 60)
        print("🕷️ 태국 한국인 채용 공고 크롤러 시작")
        print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # ── 1단계: 크롤링 ──
        print("\n📡 [1/3] 사이트 크롤링...")
        all_jobs = []

        all_jobs.extend(crawl_hanasia())
        all_jobs.extend(crawl_kyominthai())
        all_jobs.extend(crawl_jobsdb())
        all_jobs.extend(crawl_saramin())
        all_jobs.extend(crawl_jobthai())

        print(f"\n📊 총 {len(all_jobs)}건 수집 완료")

        if not all_jobs:
            print("❌ 수집된 공고가 없습니다. 종료합니다.")
            return

        # ── 2단계: AI 번역/요약 ──
        print("\n🤖 [2/3] Gemini AI 요약 중...")
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            # secrets.toml에서 읽기 시도
            try:
                import toml
                secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
                if os.path.exists(secrets_path):
                    secrets = toml.load(secrets_path)
                    api_key = secrets.get("GEMINI_API_KEY", "")
            except Exception:
                pass

        if api_key:
            all_jobs = summarize_with_gemini(all_jobs, api_key)
        else:
            print("⚠️ GEMINI_API_KEY가 설정되지 않아 AI 요약을 건너뜁니다.")

        # ── 3단계: Google Sheets 저장 ──
        print("\n💾 [3/3] Google Sheets에 저장 중...")
        try:
            save_to_gsheets(all_jobs)
        except Exception as e:
            print(f"❌ Google Sheets 저장 실패: {e}")
            # 실패 시 로컬 JSON으로 백업
            backup_path = os.path.join(os.path.dirname(__file__), "data", "jobs_backup.json")
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(all_jobs, f, ensure_ascii=False, indent=2)
            print(f"  로컬 백업 저장: {backup_path}")
            raise  # 예외를 상위로 던져서 CI에서 실패하도록 처리

        print("\n" + "=" * 60)
        print("✅ 크롤링 완료!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n🚨 치명적 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
