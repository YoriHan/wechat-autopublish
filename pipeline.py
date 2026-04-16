#!/usr/bin/env python3
"""WeChat Auto-publish Pipeline — runs daily at 8am CST"""
import os
from db import init_db, mark_published
from fetcher import fetch_all, fetch_full_text
from scorer import select_best
from translator import translate, extract_chinese_title
from formatter import format_article
from wechat import create_draft
from notifier import notify_review_ready, send_pushplus, send_bark

DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

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

    print("[pipeline] Formatting...")
    html, summary = format_article(translated, chinese_title)

    print("[pipeline] Creating WeChat draft...")
    draft_id = create_draft(chinese_title, html, source_url=best["url"])
    print(f"[pipeline] Draft created: {draft_id}")

    mark_published(best["url"], chinese_title)

    print("[pipeline] Sending notification...")
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
