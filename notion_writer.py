"""Write translated articles to a Notion database."""
import httpx
from config import NOTION_TOKEN, NOTION_DATABASE_ID
from datetime import date

_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def _md_to_blocks(md: str) -> list:
    """Convert markdown text to Notion block objects (best-effort)."""
    blocks = []
    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}})
        elif stripped.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]}})
        elif stripped.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]}})
        elif stripped.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}})
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}})
        elif stripped.startswith("---"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        else:
            # Paragraph — strip simple **bold** markers for plain text
            text = stripped.replace("**", "")
            # Truncate single block to Notion's 2000-char limit
            text = text[:2000]
            blocks.append({"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}})
    return blocks


def _html_code_blocks(html: str) -> list:
    """Wrap WeChat HTML in a Notion code block (splits into 2000-char chunks)."""
    CHUNK = 2000
    chunks = [html[i:i+CHUNK] for i in range(0, len(html), CHUNK)]
    rich_text = [{"type": "text", "text": {"content": c}} for c in chunks]
    return [
        {"object": "block", "type": "divider", "divider": {}},
        {"object": "block", "type": "heading_2",
         "heading_2": {"rich_text": [{"type": "text", "text": {"content": "微信排版 HTML（直接复制粘贴）"}}]}},
        {"object": "block", "type": "code",
         "code": {"language": "html", "rich_text": rich_text}},
    ]


def write_to_notion(title: str, translated_md: str, source_url: str, wechat_html: str = "") -> str:
    """Create a Notion page and return its URL."""
    today = date.today().isoformat()

    content_blocks = _md_to_blocks(translated_md)
    if wechat_html:
        content_blocks += _html_code_blocks(wechat_html)

    # Notion allows max 100 blocks per append call
    first_batch = content_blocks[:100]
    rest_batches = [content_blocks[i:i+100] for i in range(100, len(content_blocks), 100)]

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {
                "title": [{"text": {"content": f"[{today}] {title}"}}]
            }
        },
        "children": first_batch,
    }

    resp = httpx.post("https://api.notion.com/v1/pages", headers=_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    page = resp.json()
    page_id = page["id"]
    page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

    # Append remaining blocks if any
    for batch in rest_batches:
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_HEADERS,
            json={"children": batch},
            timeout=30,
        )
        r.raise_for_status()

    print(f"[notion] Page created: {page_url}")
    return page_url
