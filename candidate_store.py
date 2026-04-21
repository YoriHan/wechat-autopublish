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
                    {"name": "候选", "color": "blue"},
                    {"name": "选中", "color": "green"},
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
        payload = {
            "parent": {"database_id": NOTION_CANDIDATES_DATABASE_ID},
            "properties": {
                "Name":        {"title":      [{"text": {"content": art["title"][:200]}}]},
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
