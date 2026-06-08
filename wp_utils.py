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


def get_wp_tag_id(tag_name, config):
    """태그 이름을 ID로 변환 (없으면 새로 생성)"""
    auth_header = _build_auth_header(config)
    api_url = f"{config['site_url']}/wp-json/wp/v2/tags"
    
    # 1. 기존 태그 검색
    try:
        resp = requests.get(api_url, headers=auth_header, params={"search": tag_name}, timeout=10)
        if resp.status_code == 200:
            tags = resp.json()
            for t in tags:
                if t['name'] == tag_name:
                    return t['id']
    except Exception: pass

    # 2. 없으면 새로 생성
    try:
        resp = requests.post(api_url, headers=auth_header, json={"name": tag_name}, timeout=10)
        if resp.status_code in (200, 201):
            return resp.json().get("id")
        elif resp.status_code == 400: # 이미 존재할 수도 있음
            data = resp.json()
            if "term_exists" in data.get("code", ""):
                return data.get("data", {}).get("term_id")
    except Exception: pass
    
    return None


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
    뉴스 topic dict를 WordPress 본문 HTML로 변환합니다. (SEO & UI 최적화 버전)
    """
    parts = []
    refs = topic.get("references", [])
    
    # 1. 상단 핵심 요약 (다크 모드 & 골드 시그니처 스타일)
    summary = topic.get("summary", "")
    if summary:
        summary_lines = [line.strip().lstrip("- ").strip() for line in summary.strip().split("\n") if line.strip()]
        summary_items = "".join(f'<li style="margin-bottom: 8px;">{line}</li>' for line in summary_lines)
        parts.append('<blockquote class="wp-block-quote" style="border-left: 4px solid #F2C94C; background-color: rgba(255,255,255,0.05); padding: 20px; margin: 0 0 30px 0; border-radius: 0 12px 12px 0;">')
        parts.append(f'<p style="color: #F2C94C; font-size: 18px; font-weight: 800; margin: 0 0 15px 0;">✨ 핵심 요약</p>')
        parts.append(f'<ul style="margin: 0; padding-left: 20px; list-style-type: disc; color: #eeeeee; line-height: 1.6; font-size: 15px;">{summary_items}</ul>')
        parts.append('</blockquote>')

    # 2. 에디터 인사이트 (애드센스 승인 및 품질 향상용 핵심 콘텐츠)
    insight = topic.get("editorial_insight", "")
    if insight:
        parts.append('<div style="margin: 30px 0; padding: 25px; border-radius: 12px; background: linear-gradient(145deg, rgba(30,30,35,1) 0%, rgba(20,20,25,1) 100%); border: 1px solid rgba(242,201,76,0.2); box-shadow: 0 4px 15px rgba(0,0,0,0.3);">')
        parts.append('<div style="display: flex; align-items: center; margin-bottom: 15px;">')
        parts.append('<span style="font-size: 24px; margin-right: 10px;">💡</span>')
        parts.append('<h3 style="color: #F2C94C; margin: 0; font-size: 18px; font-weight: 800; letter-spacing: -0.5px;">태국 투데이 수석 에디터의 관점</h3>')
        parts.append('</div>')
        parts.append(f'<p style="color: #E0E0E0; font-size: 16px; line-height: 1.8; margin: 0; font-weight: 400; word-break: keep-all;">{insight}</p>')
        parts.append('</div>')

    # 3. 본문 섹션
    full_text = topic.get("full_translated", "")
    if full_text:
        paragraphs = full_text.strip().split("\n\n")
        for para in paragraphs:
            clean = para.strip()
            if not clean: continue
            
            # 마크다운 헤딩 변환 (골드 포인트)
            if clean.startswith("### "):
                parts.append(f'<h4 style="color: #F2C94C; margin-top: 25px; font-weight: 700;">{clean[4:]}</h4>')
            elif clean.startswith("## ") or clean.startswith("# "):
                parts.append(f'<h3 style="margin-top: 35px; border-bottom: 2px solid rgba(242,201,76,0.3); color: #F2C94C; display: inline-block; padding-bottom: 5px; font-weight: 800;">{clean.lstrip("# ").strip()}</h3>')
            else:
                inner = clean.replace("\n", "<br>")
                # 마크다운 볼드(**text**) → <strong>
                import re
                inner = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #F2C94C;">\1</strong>', inner)
                parts.append(f'<p style="line-height: 1.8; margin-bottom: 1.6em; color: #dddddd; font-size: 16px;">{inner}</p>')

    # 3. 여행자 영향도 (배지 스타일 강조)
    score = topic.get("tourist_impact_score", 0)
    if score:
        emoji = "🔴" if score >= 7 else ("🟡" if score >= 4 else "🟢")
        reason = topic.get("impact_reason", "")
        parts.append('<hr class="wp-block-separator" style="margin: 40px 0; border: none; border-top: 1px solid rgba(255,255,255,0.1);">')
        parts.append(f'<div style="padding: 20px; border: 1.5px dashed rgba(242,201,76,0.4); border-radius: 12px; background: rgba(242,201,76,0.03);">')
        parts.append(f'<span style="color: #F2C94C; font-weight: 800; font-size: 16px;">{emoji} 여행자 영향도: {score} / 10</span>')
        if reason:
            parts.append(f'<p style="margin-top: 12px; font-style: italic; font-size: 14px; color: #A0A5B5; line-height: 1.5;">{reason}</p>')
        parts.append('</div>')


    # 5. 관련 기사 리스트 (작은 링크)
    if refs:
        parts.append('<div style="margin-top: 40px; padding: 20px; background: rgba(255,255,255,0.03); border-radius: 12px;">')
        parts.append('<p style="margin: 0 0 10px 0; font-size: 14px; color: #888;">🔗 관련 기사 및 출처:</p>')
        parts.append('<ul style="font-size: 13px; padding-left: 20px; margin: 0; color: #666;">')
        for ref in refs:
            r_title = ref.get("title", "기사 보기")
            r_url = ref.get("url", "#")
            parts.append(f'<li style="margin-bottom: 5px;"><a href="{r_url}" target="_blank" rel="nofollow" style="color: #A0A5B5; text-decoration: none;">[{ref.get("source", "Source")}] {r_title}</a></li>')
        parts.append('</ul>')
        parts.append('</div>')
        
    # 6. 저작권/안내
    parts.append('<p style="font-size: 12px; color: #666; margin-top: 60px; text-align: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 25px;">')
    parts.append('본 뉴스는 태국 투데이 AI 여행 코디네이터가 실시간 분석하여 제공합니다.')
    parts.append('</p>')

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

    # 2. 본문 및 요약문(SEO) 생성
    content_html = format_news_html(topic)
    
    # SEO 요약문 생성 (최대 160자)
    summary = topic.get("summary", "")
    excerpt = summary.replace("- ", "").replace("\n", " ")[:160] + "..." if len(summary) > 160 else summary
    
    # 태그 생성 (카테고리 + 키워드) → ID로 변환
    tag_names = ["태국뉴스", category]
    if "방콕" in title: tag_names.append("방콕")
    if "푸켓" in title: tag_names.append("푸켓")
    if "치앙마이" in title: tag_names.append("치앙마이")
    
    tag_ids = []
    for name in tag_names:
        tid = get_wp_tag_id(name, config)
        if tid: tag_ids.append(tid)

    # 3. 포스팅 데이터 구성
    post_data = {
        "title": title,
        "content": content_html,
        "excerpt": excerpt,
        "status": "publish",
        "categories": [get_wp_category_id(category, config["default_category_id"])],
        "tags": tag_ids
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
        resp = requests.get(f"{config['site_url']}/wp-json/", timeout=30)
        if resp.status_code != 200:
            return False, f"REST API 접근 불가 (HTTP {resp.status_code})"

        site_info = resp.json()
        site_name = site_info.get("name", "Unknown")

        # 2) 인증 확인 (사용자 정보 조회)
        auth_header = _build_auth_header(config)
        me_resp = requests.get(f"{config['site_url']}/wp-json/wp/v2/users/me",
                               headers=auth_header, timeout=30)

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
