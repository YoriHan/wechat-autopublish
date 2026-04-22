"""
Candidate article store — Notion database for daily Top-5 selection.

Required Notion database (set NOTION_CANDIDATES_DATABASE_ID in .env):
  Create an empty full-page database in Notion.
  This module auto-patches the schema on first use:
    Name        title   — article title
    Status      select  — 候选 | 选中
    Score       number  — scorer output
    Source      text    — source name
    OriginalURL url     — original article URL
    Date        date    — fetch date (YYYY-MM-DD)

Workflow:
  Stage 1 calls save_candidates() → 5 rows appear in Notion with Status=候选
  User opens Notion, changes one row's Status to 选中
  Stage 2 calls get_selected_candidate() → gets that row
  Fallback: get_top_candidate_today() → highest-score 候选 for today
"""
import httpx
from datetime import date
from config import NOTION_TOKEN, NOTION_CANDIDATES_DATABASE_ID

_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

_SCHEMA_PATCH = {
    "properties": {
        "Status": {
            "select": {
                "options": [
                    {"name": "候选",     "color": "blue"},
                    {"name": "选中",     "color": "green"},
                    {"name": "查找记录", "color": "gray"},
                ]
            }
        },
        "Score":       {"number": {"format": "number"}},
        "Source":      {"rich_text": {}},
        "OriginalURL": {"url": {}},
        "Date":        {"date": {}},
    }
}


def ensure_schema() -> None:
    """Patch the candidates database to add required properties (idempotent)."""
    r = httpx.patch(
        f"https://api.notion.com/v1/databases/{NOTION_CANDIDATES_DATABASE_ID}",
        headers=_HEADERS,
        json=_SCHEMA_PATCH,
        timeout=20,
    )
    r.raise_for_status()


def save_candidates(articles: list[dict]) -> str:
    """
    Save articles as 候选 entries in the candidates database.
    Returns the Notion database URL.
    """
    ensure_schema()
    today = date.today().isoformat()

    for art in articles:
        entry_title = f"[{today}] {art['title']}"[:200]
        payload = {
            "parent": {"database_id": NOTION_CANDIDATES_DATABASE_ID},
            "properties": {
                "Name":        {"title":      [{"text": {"content": entry_title}}]},
                "Status":      {"select":     {"name": "候选"}},
                "Score":       {"number":     art.get("score", 0)},
                "Source":      {"rich_text":  [{"text": {"content": art.get("source", "")}}]},
                "OriginalURL": {"url":        art["url"]},
                "Date":        {"date":       {"start": today}},
            },
        }
        r = httpx.post(
            "https://api.notion.com/v1/pages",
            headers=_HEADERS, json=payload, timeout=20,
        )
        r.raise_for_status()

    db_url = f"https://notion.so/{NOTION_CANDIDATES_DATABASE_ID.replace('-', '')}"
    print(f"[candidates] Saved {len(articles)} candidates → {db_url}")
    return db_url


def _page_to_article(page: dict) -> dict:
    props = page["properties"]

    def _text(prop):
        items = prop.get("rich_text") or prop.get("title") or []
        return "".join(t["plain_text"] for t in items)

    return {
        "title":  _text(props.get("Name", {})),
        "url":    props.get("OriginalURL", {}).get("url", ""),
        "source": _text(props.get("Source", {})),
        "score":  props.get("Score", {}).get("number", 0),
    }


def get_selected_candidate() -> dict | None:
    """Return the 选中 candidate for today, or None."""
    today = date.today().isoformat()
    payload = {
        "filter": {
            "and": [
                {"property": "Status", "select": {"equals": "选中"}},
                {"property": "Date",   "date":   {"equals": today}},
            ]
        },
        "page_size": 1,
    }
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{NOTION_CANDIDATES_DATABASE_ID}/query",
        headers=_HEADERS, json=payload, timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return _page_to_article(results[0]) if results else None


def get_top_candidate_today() -> dict | None:
    """Return the highest-scoring 候选 for today (fallback when nothing selected)."""
    today = date.today().isoformat()
    payload = {
        "filter": {
            "and": [
                {"property": "Status", "select": {"equals": "候选"}},
                {"property": "Date",   "date":   {"equals": today}},
            ]
        },
        "sorts":     [{"property": "Score", "direction": "descending"}],
        "page_size": 1,
    }
    r = httpx.post(
        f"https://api.notion.com/v1/databases/{NOTION_CANDIDATES_DATABASE_ID}/query",
        headers=_HEADERS, json=payload, timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return _page_to_article(results[0]) if results else None


def create_source_log(articles: list[dict]) -> None:
    """
    Create a daily source-log page in the candidates database.
    Lists every fetched article grouped by source, with URL.
    Page title: "{today} 已查找文章清单"
    """
    ensure_schema()
    today = date.today().isoformat()

    # Group articles by source
    by_source: dict[str, list[dict]] = {}
    for art in articles:
        src = art.get("source", "未知来源")
        by_source.setdefault(src, []).append(art)

    # Build Notion blocks
    blocks: list[dict] = []
    blocks.append({
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {
                "content": f"{today} 共抓取 {len(articles)} 篇文章，来自 {len(by_source)} 个来源。"
            }}],
            "icon": {"type": "emoji", "emoji": "📋"},
            "color": "gray_background",
        },
    })

    for src, arts in sorted(by_source.items()):
        blocks.append({
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {
                "content": f"{src} ({len(arts)}篇)"
            }}]},
        })
        for art in arts:
            title = art.get("title", "(无标题)")[:100]
            url   = art.get("url", "")
            if url:
                blocks.append({
                    "object": "block", "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {"type": "text", "text": {"content": title + " "}},
                            {"type": "text", "text": {"content": url, "link": {"url": url}},
                             "annotations": {"color": "blue"}},
                        ]
                    },
                })
            else:
                blocks.append({
                    "object": "block", "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": title}}]
                    },
                })

    # Create the log page (Status=查找记录)
    page_payload = {
        "parent": {"database_id": NOTION_CANDIDATES_DATABASE_ID},
        "properties": {
            "Name":   {"title": [{"text": {"content": f"{today} 已查找文章清单"}}]},
            "Status": {"select": {"name": "查找记录"}},
            "Date":   {"date": {"start": today}},
        },
        "children": blocks[:100],
    }
    r = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=_HEADERS, json=page_payload, timeout=30,
    )
    r.raise_for_status()
    page_id = r.json()["id"]

    # Append remaining blocks in batches of 100
    for i in range(100, len(blocks), 100):
        httpx.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_HEADERS,
            json={"children": blocks[i:i+100]},
            timeout=30,
        ).raise_for_status()

    print(f"[candidates] Source log created: {today} 已查找文章清单 ({len(articles)} articles, {len(by_source)} sources)")
