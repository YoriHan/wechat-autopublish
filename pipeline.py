#!/usr/bin/env python3
"""WeChat Auto-publish Pipeline — runs daily at 8am CST"""
import os
from db import init_db, mark_published
from fetcher import fetch_all, fetch_full_text
from scorer import select_best
from translator import translate, extract_chinese_title
from formatter import format_article, format_article_md2wechat, format_all_themes
from notifier import notify_review_ready, send_pushplus, send_bark
from image_gen import generate_cover

DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
from config import USE_MD2WECHAT, WECHAT_THEME, WECHAT_APP_ID, WECHAT_APP_SECRET, NOTION_TOKEN, NOTION_DATABASE_ID

WECHAT_ENABLED = bool(WECHAT_APP_ID and WECHAT_APP_SECRET)
NOTION_ENABLED = bool(NOTION_TOKEN and NOTION_DATABASE_ID)

def run():
    if DRY_RUN:
        print("[pipeline] DRY RUN — will not submit to WeChat or send notifications")

    init_db()
    print("[pipeline] Fetching articles...")
    articles = fetch_all()
    print(f"[pipeline] Found {len(articles)} new articles")

    if not articles:
        if not DRY_RUN:
            send_bark("公众号日报", "今日无新文章，跳过。") or send_pushplus("公众号日报", "今日无新文章，跳过。")
        return

    best = select_best(articles)
    if not best:
        if not DRY_RUN:
            send_bark("公众号日报", "今日文章质量不足，跳过发布。") or send_pushplus("公众号日报", "今日文章质量不足（score < 30），跳过发布。")
        return

    print(f"[pipeline] Selected: {best['url']}")
    full_text = fetch_full_text(best["url"])

    if DRY_RUN:
        print("[pipeline] DRY RUN — skipping translation, formatting, and submission")
        print(f"[pipeline] Would have translated: {best['title']}")
        print(f"[pipeline] Score: {best['score']}")
        return

    print("[pipeline] Translating...")
    translated = translate(best, full_text)

    chinese_title = extract_chinese_title(translated)
    print(f"[pipeline] Chinese title: {chinese_title}")

    summary = translated[:200].replace("\n", " ")
    notion_url = ""

    # — Notion output —
    if NOTION_ENABLED:
        print("[pipeline] Formatting all WeChat themes...")
        themed = format_all_themes(translated, chinese_title)  # [(key, label, html), ...]

        print("[pipeline] Taking theme screenshots...")
        screenshots: dict[str, str] = {}
        try:
            from screenshot import render_and_upload
            for key, label, html in themed:
                print(f"[pipeline] Screenshotting {label}...")
                url = render_and_upload(html, key)
                if url:
                    screenshots[key] = url
        except Exception as e:
            print(f"[pipeline] Screenshot step failed (non-fatal): {e}")

        print("[pipeline] Writing to Notion...")
        from notion_writer import write_to_notion
        notion_url = write_to_notion(
            chinese_title, translated, best["url"],
            themes=themed, screenshots=screenshots,
        )

    # — WeChat output —
    if WECHAT_ENABLED:
        print("[pipeline] Formatting for WeChat...")
        if USE_MD2WECHAT:
            print(f"[pipeline] Using md2wechat theme: {WECHAT_THEME}")
            html, summary = format_article_md2wechat(translated, chinese_title, WECHAT_THEME)
        else:
            html, summary = format_article(translated, chinese_title)

        cover_media_id = ""
        cover_path = generate_cover(chinese_title, summary)
        if cover_path:
            print("[pipeline] Uploading cover image to WeChat...")
            try:
                from wechat import upload_image, create_draft
                cover_media_id = upload_image(cover_path)
                print(f"[pipeline] Cover media_id: {cover_media_id}")
            except Exception as e:
                print(f"[pipeline] Cover upload failed (using static): {e}")

        print("[pipeline] Creating WeChat draft...")
        from wechat import upload_image, create_draft
        draft_id = create_draft(chinese_title, html, source_url=best["url"], cover_media_id=cover_media_id)
        print(f"[pipeline] Draft created: {draft_id}")
    elif not NOTION_ENABLED:
        print("[pipeline] WARNING: Neither WeChat nor Notion is configured. Translation complete but not published.")
        print(f"[pipeline] Translated content:\n{translated[:500]}...")

    mark_published(best["url"], chinese_title)

    print("[pipeline] Sending notification...")
    if notion_url:
        msg = f"「{chinese_title}」已存入 Notion，点击查看：{notion_url}"
        send_bark("公众号素材已就绪 📝", msg) or send_pushplus("公众号素材已就绪 📝", msg)
    else:
        notify_review_ready(chinese_title, summary)

    print("[pipeline] Done.")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        if not DRY_RUN:
            msg = f"Pipeline 报错：{str(e)[:200]}"
            send_bark("公众号日报 ❌", msg) or send_pushplus("公众号日报 ❌", msg)
        raise
