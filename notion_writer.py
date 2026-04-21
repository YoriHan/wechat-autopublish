"""Write translated articles to a Notion database, with images uploaded directly to Notion."""
import re
import httpx
from config import NOTION_TOKEN, NOTION_DATABASE_ID
from datetime import date

_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------

def _upload_image(image_url: str) -> dict:
    """
    Download image_url and upload it to Notion file storage.
    Returns a ready-to-use Notion image block dict.
    Falls back to an external-URL block if upload fails.
    """
    try:
        # 1. Download the image
        r = httpx.get(
            image_url, timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            raise ValueError(f"Not an image content-type: {content_type}")
        image_bytes = r.content
        filename = image_url.split("/")[-1].split("?")[0] or "image.jpg"

        # 2. Create a Notion file upload slot
        headers_no_ct = {k: v for k, v in _HEADERS.items() if k != "Content-Type"}
        r1 = httpx.post(
            "https://api.notion.com/v1/file_uploads",
            headers=headers_no_ct,
            json={"mode": "single_part"},
            timeout=30,
        )
        r1.raise_for_status()
        upload_data = r1.json()
        upload_url = upload_data["upload_url"]
        file_id = upload_data["id"]

        # 3. Upload the image bytes (multipart)
        r2 = httpx.put(
            upload_url,
            files={"file": (filename, image_bytes, content_type)},
            timeout=60,
        )
        r2.raise_for_status()

        return {
            "object": "block",
            "type": "image",
            "image": {"type": "file_upload", "file_upload": {"id": file_id}},
        }

    except Exception as e:
        print(f"[notion] Image upload failed ({image_url[:80]}): {e} — using external link")
        return {
            "object": "block",
            "type": "image",
            "image": {"type": "external", "external": {"url": image_url}},
        }


# ---------------------------------------------------------------------------
# Markdown → Notion blocks  (handles <<<IMG:N>>> placeholders)
# ---------------------------------------------------------------------------

def _md_to_blocks(md: str, images: list[str] | None = None) -> list:
    """
    Convert markdown text to Notion block objects.
    <<<IMG:N>>> placeholders are replaced with uploaded image blocks.
    """
    images = images or []
    blocks = []

    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Image placeholder
        m = re.match(r"^<<<IMG:(\d+)>>>$", stripped)
        if m:
            idx = int(m.group(1))
            if idx < len(images):
                blocks.append(_upload_image(images[idx]))
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
        elif stripped.startswith(("- ", "* ")):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}})
        elif stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        else:
            text = stripped.replace("**", "")[:2000]
            blocks.append({"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}})

    return blocks


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def write_to_notion(
    title: str,
    translated_md: str,
    source_url: str,
    cover_url: str = "",
    images: list[str] | None = None,
) -> str:
    """
    Create a Notion page with:
      - Cover image (uploaded to Notion) as first block
      - Translated article body (with inline images in place)
      - Source link callout at the bottom
    Returns the page URL.
    """
    today = date.today().isoformat()
    images = images or []

    content_blocks: list = []

    # --- Cover image ---
    if cover_url:
        print(f"[notion] Uploading cover image...")
        content_blocks.append(_upload_image(cover_url))

    # --- Article body (text + inline images) ---
    content_blocks += _md_to_blocks(translated_md, images)

    # --- Source callout ---
    content_blocks.append({"object": "block", "type": "divider", "divider": {}})
    content_blocks.append({
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [
                {"type": "text", "text": {"content": "原文链接："}},
                {"type": "text", "text": {"content": source_url, "link": {"url": source_url}}},
            ],
            "icon": {"type": "emoji", "emoji": "🔗"},
            "color": "gray_background",
        },
    })

    # Notion allows max 100 blocks per call
    first_batch = content_blocks[:100]
    rest_batches = [content_blocks[i:i+100] for i in range(100, len(content_blocks), 100)]

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": f"[{today}] {title}"}}]}
        },
        "children": first_batch,
    }

    resp = httpx.post(
        "https://api.notion.com/v1/pages",
        headers=_HEADERS, json=payload, timeout=30,
    )
    resp.raise_for_status()
    page = resp.json()
    page_id = page["id"]
    page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

    for batch in rest_batches:
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_HEADERS, json={"children": batch}, timeout=30,
        )
        r.raise_for_status()

    print(f"[notion] Page created: {page_url}")
    return page_url
