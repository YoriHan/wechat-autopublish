#!/usr/bin/env python3
"""WeChat Auto-publish Pipeline — runs daily at 8am CST"""
import os
from db import init_db, mark_published
from fetcher import fetch_all, fetch_article_content
from scorer import select_best
from translator import translate, extract_chinese_title
from notifier import notify_review_ready, send_pushplus, send_bark

DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
from config import WECHAT_APP_ID, WECHAT_APP_SECRET, NOTION_TOKEN, NOTION_DATABASE_ID

WECHAT_ENABLED = bool(WECHAT_APP_ID and WECHAT_APP_SECRET)
NOTION_ENABLED = bool(NOTION_TOKEN and NOTION_DATABASE_ID)


def run():
    if DRY_RUN:
        print("[pipeline] DRY RUN — will not submit or send notifications")

    init_db()
    print("[pipeline] Fetching articles...")
    articles = fetch_all()
    print(f"[pipeline] Found {len(articles)} new articles")

    if not articles:
        if not DRY_RUN:
            send_bark("公众号日报", "今日无新文章，跳过。") or \
                send_pushplus("公众号日报", "今日无新文章，跳过。")
        return

    best = select_best(articles)
    if not best:
        return

    print(f"[pipeline] Selected: {best['title']} (score={best.get('score')})")
    print(f"[pipeline] Fetching full content + images from: {best['url']}")
    content = fetch_article_content(best["url"])
    full_text = content["text"]
    cover_url = content["cover_url"]
    images = content["images"]
    print(f"[pipeline] Cover: {cover_url or '(none)'}, inline images: {len(images)}")

    if DRY_RUN:
        print("[pipeline] DRY RUN — skipping translation and submission")
        print(f"[pipeline] Would translate: {best['title']}")
        print(f"[pipeline] Score: {best['score']}")
        return

    print("[pipeline] Translating...")
    translated = translate(best, full_text)
    chinese_title = extract_chinese_title(translated)
    print(f"[pipeline] Chinese title: {chinese_title}")

    notion_url = ""

    # — Notion output —
    if NOTION_ENABLED:
        print("[pipeline] Writing to Notion (uploading images)...")
        from notion_writer import write_to_notion
        notion_url = write_to_notion(
            title=chinese_title,
            translated_md=translated,
            source_url=best["url"],
            cover_url=cover_url,
            images=images,
        )

    # — WeChat output (text-only; no image generation) —
    if WECHAT_ENABLED:
        from formatter import format_article
        from wechat import create_draft
        print("[pipeline] Formatting for WeChat...")
        html, summary = format_article(translated, chinese_title)
        print("[pipeline] Creating WeChat draft...")
        draft_id = create_draft(
            chinese_title, html,
            source_url=best["url"],
            cover_media_id=os.getenv("WECHAT_COVER_MEDIA_ID", ""),
        )
        print(f"[pipeline] Draft created: {draft_id}")

    if not WECHAT_ENABLED and not NOTION_ENABLED:
        print("[pipeline] WARNING: Neither WeChat nor Notion configured.")
        print(f"[pipeline] Translated content:\n{translated[:500]}...")

    mark_published(best["url"], chinese_title)

    print("[pipeline] Sending notification...")
    if notion_url:
        msg = f"「{chinese_title}」已存入 Notion：{notion_url}"
        send_bark("公众号素材已就绪 📝", msg) or send_pushplus("公众号素材已就绪 📝", msg)
    else:
        summary = translated[:200].replace("\n", " ")
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
