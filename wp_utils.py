"""
wp_utils.py - WordPress REST API 연동 모듈
태국 투데이(thai-today.com) 자동 포스팅 엔진

기능:
1. 이미지 업로드 (외부 URL → WP 미디어 라이브러리)
2. 기사 포스팅 (HTML 본문 + 특성 이미지)
3. 카테고리 매핑 (batch_job 카테고리 → WP 카테고리 ID)
"""

import os
import base64
import time
import requests
import json


# ──────────────────────────────────────────────
# 1. 설정 로드 (st.secrets 또는 toml 직접 로드)
# ──────────────────────────────────────────────

def _load_wp_config():
    """
    WordPress 인증 정보를 로드합니다.
    Streamlit 런타임이 있으면 st.secrets, 없으면 toml 파일에서 직접 로드.
    Returns: dict with keys: site_url, username, app_password, default_category_id
    """
    # 1) Streamlit 런타임 시도
    try:
        import streamlit as st
        wp = st.secrets["wordpress"]
        return {
            "site_url": wp["site_url"],
            "username": wp["username"],
            "app_password": wp["app_password"],
            "default_category_id": int(wp.get("default_category_id", 1)),
        }
    except Exception:
        pass

    # 2) toml 직접 로드 (batch_job / CLI 환경)
    try:
        import toml
        secrets = toml.load(".streamlit/secrets.toml")
        wp = secrets["wordpress"]
        return {
            "site_url": wp["site_url"],
            "username": wp["username"],
            "app_password": wp["app_password"],
            "default_category_id": int(wp.get("default_category_id", 1)),
        }
    except Exception as e:
        print(f"[WP] secrets 로드 실패: {e}")
        return None


def _build_auth_header(config):
    """Basic Auth 헤더를 생성합니다."""
    token = base64.b64encode(
        f"{config['username']}:{config['app_password']}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}"}


# ──────────────────────────────────────────────
# 2. 카테고리 매핑
# ──────────────────────────────────────────────

# batch_job의 카테고리 → WordPress 카테고리 ID 매핑
# 사용자 정의 ID 반영 (태국뉴스:1, 경제:8, 여행:9, 문화:11, 정치:10)
CATEGORY_MAP = {
    # 1. 표준 영문 키 (batch_job API 연동용)
    "POLITICS": 10,
    "BUSINESS": 8,
    "TRAVEL": 9,
    "LIFESTYLE": 11,
    
    # 2. 한글 키 (직접 호출 또는 확장용)
    "태국뉴스": 2,
    "정치": 10,
    "경제": 8,
    "여행": 9,
    "문화": 11,
    "사건/사고": 10,
    "범죄": 10,
    "안전": 10,
    "사회": 10,
    "교통": 9,
    "관광": 9,
}


def get_wp_category_id(category_name, default_id=1):
    """batch_job 카테고리명을 WordPress 카테고리 ID로 변환합니다."""
    # 1. 대문자 변환 후 검색 (POLITICS 등)
    found_id = CATEGORY_MAP.get(category_name.upper())
    if found_id:
        return found_id
    
    # 2. 한글 키 그대로 검색 (경제, 여행 등)
    return CATEGORY_MAP.get(category_name, default_id)


# ──────────────────────────────────────────────
# 3. 이미지 업로드
# ──────────────────────────────────────────────

def upload_image_to_wp(image_source, config=None, alt_text="태국 투데이 뉴스 이미지"):
    """
    이미지를 WordPress 미디어 라이브러리에 업로드합니다.

    Args:
        image_source: 외부 이미지 URL (str) 또는 로컬 파일 경로 (str)
        config: WP 설정 dict (None이면 자동 로드)
        alt_text: 이미지 대체 텍스트

    Returns:
        media_id (int) 성공 시, None 실패 시
    """
    if not config:
        config = _load_wp_config()
    if not config:
        print("[WP] 설정 로드 실패 - 이미지 업로드 불가")
        return None

    api_url = f"{config['site_url']}/wp-json/wp/v2/media"
    auth_header = _build_auth_header(config)

    # 타임스탬프 기반 고유 파일명 생성
    timestamp = int(time.time() * 1000)

    try:
        # Case 1: 외부 URL에서 이미지 다운로드
        if image_source.startswith("http"):
            print(f"[WP] 이미지 다운로드 중: {image_source[:80]}...")
            resp = requests.get(image_source, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ThaiTodayBot/1.0)"
            })
            if resp.status_code != 200:
                print(f"[WP] 이미지 다운로드 실패 (HTTP {resp.status_code})")
                return None

            # Content-Type에서 확장자 추론
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
            ext = ext_map.get(content_type.split(";")[0].strip(), "jpg")
            filename = f"thai-today-{timestamp}.{ext}"

            headers = {**auth_header, "Content-Type": content_type,
                       "Content-Disposition": f'attachment; filename="{filename}"'}
            upload_resp = requests.post(api_url, headers=headers, data=resp.content, timeout=30)

        # Case 2: 로컬 파일 업로드
        elif os.path.exists(image_source):
            print(f"[WP] 로컬 이미지 업로드 중: {image_source}")
            ext = os.path.splitext(image_source)[1].lstrip(".") or "jpg"
            filename = f"thai-today-{timestamp}.{ext}"
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                        "webp": "image/webp", "gif": "image/gif"}
            content_type = mime_map.get(ext, "image/jpeg")

            with open(image_source, "rb") as f:
                img_data = f.read()

            headers = {**auth_header, "Content-Type": content_type,
                       "Content-Disposition": f'attachment; filename="{filename}"'}
            upload_resp = requests.post(api_url, headers=headers, data=img_data, timeout=30)

        else:
            print(f"[WP] 유효하지 않은 이미지 소스: {image_source}")
            return None

        # 응답 처리
        if upload_resp.status_code in (200, 201):
            media_id = upload_resp.json().get("id")
            print(f"[WP] ✅ 이미지 업로드 성공 (media_id: {media_id})")

            # alt_text 업데이트
            try:
                requests.post(f"{api_url}/{media_id}", headers={**auth_header, "Content-Type": "application/json"},
                              json={"alt_text": alt_text}, timeout=10)
            except Exception:
                pass
            return media_id
        else:
            print(f"[WP] ❌ 이미지 업로드 실패 (HTTP {upload_resp.status_code}): {upload_resp.text[:200]}")
            return None

    except Exception as e:
        print(f"[WP] 이미지 업로드 에러: {e}")
        return None


# ──────────────────────────────────────────────
# 4. 기사 포스팅
# ──────────────────────────────────────────────

def format_news_html(topic):
    """
    뉴스 topic dict를 WordPress 본문 HTML로 변환합니다.
    한국어 가독성을 위해 <p>, <br> 태그 사용.

    Args:
        topic: batch_job에서 생성된 뉴스 topic dict
              (title, summary, full_translated, category, references 등)
    Returns:
        HTML 문자열
    """
    parts = []

    # 요약 섹션
    summary = topic.get("summary", "")
    if summary:
        # 줄바꿈(-로 시작하는 리스트)을 HTML로 변환
        summary_lines = summary.strip().split("\n")
        summary_html = "<br>".join(line.strip() for line in summary_lines if line.strip())
        parts.append('<div class="news-summary">')
        parts.append(f"<strong>📌 핵심 요약</strong><br>{summary_html}")
        parts.append("</div>")

    # 본문 (Markdown → HTML 간이 변환)
    full_text = topic.get("full_translated", "")
    if full_text:
        # 줄바꿈을 <p> 태그로 변환
        paragraphs = full_text.strip().split("\n\n")
        for para in paragraphs:
            clean = para.strip()
            if not clean:
                continue
            # 마크다운 헤딩 변환
            if clean.startswith("### "):
                parts.append(f"<h3>{clean[4:]}</h3>")
            elif clean.startswith("## "):
                parts.append(f"<h2>{clean[3:]}</h2>")
            elif clean.startswith("# "):
                parts.append(f"<h2>{clean[2:]}</h2>")
            else:
                # 줄바꿈을 <br>로 변환
                inner = clean.replace("\n", "<br>")
                # 마크다운 볼드(**text**) → <strong>
                import re
                inner = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', inner)
                parts.append(f"<p>{inner}</p>")

    # 여행 영향도 점수
    score = topic.get("tourist_impact_score", 0)
    if score:
        emoji = "🔴" if score >= 7 else ("🟡" if score >= 4 else "🟢")
        reason = topic.get("impact_reason", "")
        parts.append(f'<p><strong>{emoji} 여행자 영향도: {score}/10</strong>')
        if reason:
            parts.append(f"<br><em>{reason}</em>")
        parts.append("</p>")

    # 이벤트 정보 (있는 경우)
    evt = topic.get("event_info")
    if evt and isinstance(evt, dict) and evt.get("date"):
        parts.append('<div class="news-event-info">')
        parts.append("<strong>📅 이벤트 정보</strong><br>")
        if evt.get("date"):
            parts.append(f"일시: {evt['date']}<br>")
        if evt.get("location"):
            parts.append(f"장소: {evt['location']}<br>")
        if evt.get("price"):
            parts.append(f"가격: {evt['price']}")
        parts.append("</div>")

    # 출처 (References)
    refs = topic.get("references", [])
    if refs:
        parts.append("<hr>")
        parts.append("<p><strong>📰 출처</strong></p><ul>")
        for ref in refs:
            title = ref.get("title", "원문 보기")
            url = ref.get("url", "#")
            source = ref.get("source", "")
            source_label = f" ({source})" if source else ""
            parts.append(f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a>{source_label}</li>')
        parts.append("</ul>")

    return "\n".join(parts)


def publish_to_wordpress(topic, config=None):
    """
    뉴스 topic을 WordPress에 포스팅합니다.

    Args:
        topic: batch_job에서 생성된 뉴스 topic dict
        config: WP 설정 dict (None이면 자동 로드)

    Returns:
        (success: bool, result: dict or str)
        성공 시: (True, {"post_id": int, "post_url": str})
        실패 시: (False, "에러 메시지")
    """
    if not config:
        config = _load_wp_config()
    if not config:
        return False, "WordPress 설정 로드 실패"

    api_url = f"{config['site_url']}/wp-json/wp/v2/posts"
    auth_header = _build_auth_header(config)

    title = topic.get("title", "제목 없음")
    category = topic.get("category", "TRAVEL")

    # 1. 이미지 업로드 시도 (실패해도 포스팅은 계속)
    media_id = None
    image_url = topic.get("image_url")
    if image_url:
        media_id = upload_image_to_wp(image_url, config=config, alt_text=title)
        if not media_id:
            print(f"[WP] ⚠️ 이미지 업로드 실패 - 이미지 없이 포스팅 진행: {title}")

    # 2. 본문 HTML 생성
    content_html = format_news_html(topic)

    # 3. 포스팅 데이터 구성
    post_data = {
        "title": title,
        "content": content_html,
        "status": "publish",
        "categories": [get_wp_category_id(category, config["default_category_id"])],
    }

    if media_id:
        post_data["featured_media"] = media_id

    # 4. POST 요청
    try:
        headers = {**auth_header, "Content-Type": "application/json"}
        resp = requests.post(api_url, headers=headers, json=post_data, timeout=30)

        if resp.status_code in (200, 201):
            result = resp.json()
            post_id = result.get("id")
            post_url = result.get("link", "")
            print(f"[WP] ✅ 포스팅 성공: [{post_id}] {title}")
            print(f"[WP]    URL: {post_url}")
            return True, {"post_id": post_id, "post_url": post_url}
        else:
            err = resp.text[:300]
            print(f"[WP] ❌ 포스팅 실패 (HTTP {resp.status_code}): {err}")
            return False, f"HTTP {resp.status_code}: {err}"

    except Exception as e:
        print(f"[WP] 포스팅 에러: {e}")
        return False, str(e)


# ──────────────────────────────────────────────
# 5. 일괄 포스팅 (batch_job 연동용)
# ──────────────────────────────────────────────

def publish_batch_to_wordpress(topics, delay_seconds=5):
    """
    여러 뉴스 topic을 순차적으로 WordPress에 포스팅합니다.
    batch_job.py의 new_topics_to_save 리스트를 직접 전달 가능.

    Args:
        topics: 뉴스 topic dict 리스트
        delay_seconds: 포스팅 간 대기 시간 (서버 부하 방지)

    Returns:
        dict: {"success": int, "failed": int, "results": list}
    """
    config = _load_wp_config()
    if not config:
        print("[WP] WordPress 설정 로드 실패 - 일괄 포스팅 중단")
        return {"success": 0, "failed": len(topics), "results": []}

    results = []
    success_count = 0
    fail_count = 0

    for i, topic in enumerate(topics):
        print(f"\n[WP] [{i+1}/{len(topics)}] 포스팅 중: {topic.get('title', '?')}")

        ok, result = publish_to_wordpress(topic, config=config)
        results.append({"title": topic.get("title"), "success": ok, "result": result})

        if ok:
            success_count += 1
        else:
            fail_count += 1

        # 마지막 항목이 아니면 대기
        if i < len(topics) - 1:
            print(f"[WP]    {delay_seconds}초 대기...")
            time.sleep(delay_seconds)

    print(f"\n[WP] === 일괄 포스팅 완료: 성공 {success_count} / 실패 {fail_count} ===")
    return {"success": success_count, "failed": fail_count, "results": results}


# ──────────────────────────────────────────────
# 6. 연결 테스트
# ──────────────────────────────────────────────

def test_wp_connection():
    """WordPress REST API 연결 상태를 테스트합니다."""
    config = _load_wp_config()
    if not config:
        return False, "설정 로드 실패"

    try:
        # 1) 사이트 기본 정보 확인
        resp = requests.get(f"{config['site_url']}/wp-json/", timeout=10)
        if resp.status_code != 200:
            return False, f"REST API 접근 불가 (HTTP {resp.status_code})"

        site_info = resp.json()
        site_name = site_info.get("name", "Unknown")

        # 2) 인증 확인 (사용자 정보 조회)
        auth_header = _build_auth_header(config)
        me_resp = requests.get(f"{config['site_url']}/wp-json/wp/v2/users/me",
                               headers=auth_header, timeout=10)

        if me_resp.status_code == 200:
            user = me_resp.json()
            print(f"[WP] ✅ 연결 성공!")
            print(f"[WP]    사이트: {site_name}")
            print(f"[WP]    사용자: {user.get('name')} (ID: {user.get('id')})")
            print(f"[WP]    권한: {', '.join(user.get('roles', []))}")
            return True, {"site": site_name, "user": user.get("name")}
        else:
            return False, f"인증 실패 (HTTP {me_resp.status_code}): Application Password를 확인하세요."

    except Exception as e:
        return False, f"연결 에러: {e}"


# ──────────────────────────────────────────────
# CLI 테스트
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=== WordPress 연결 테스트 ===\n")
    ok, info = test_wp_connection()
    if ok:
        print(f"\n연결 성공: {info}")
    else:
        print(f"\n연결 실패: {info}")
