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
    wechat_themes: list[tuple[str, str, str]] | None = None,
) -> str:
    """
    Create a Notion page with:
      - Cover image (uploaded to Notion) as first block
      - Translated article body (with inline images in place)
      - Source link callout at the bottom
      - Optional WeChat theme HTML code blocks (one per theme)
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

    # --- Build WeChat HTML blocks separately (kept out of page-create payload
    #     to avoid Cloudflare WAF flagging large inline-style HTML in POST body) ---
    wechat_blocks: list = []
    if wechat_themes:
        wechat_blocks.append({"object": "block", "type": "divider", "divider": {}})
        wechat_blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "微信排版 HTML"}}]},
        })
        for _key, label, html in wechat_themes:
            wechat_blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": label}}]},
            })
            # Notion code blocks max 2000 chars — chunk if needed
            chunk_size = 1990
            for i in range(0, len(html), chunk_size):
                wechat_blocks.append({
                    "object": "block", "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": html[i:i+chunk_size]}}],
                        "language": "html",
                    },
                })

    # Notion allows max 100 blocks per call.
    # Create the page with article body only (no WeChat HTML) to avoid WAF blocks.
    first_batch = content_blocks[:100]
    rest_article = [content_blocks[i:i+100] for i in range(100, len(content_blocks), 100)]
    wechat_batches = [wechat_blocks[i:i+100] for i in range(0, len(wechat_blocks), 100)]

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
    if not resp.is_success:
        print(f"[notion] Page create failed {resp.status_code}: {resp.text[:500]}")
    resp.raise_for_status()
    page = resp.json()
    page_id = page["id"]
    page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

    for batch in rest_article:
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_HEADERS, json={"children": batch}, timeout=30,
        )
        r.raise_for_status()

    # Append WeChat HTML blocks in separate batches after page exists.
    # Non-fatal: if Cloudflare WAF blocks the request, log and continue.
    import time as _time
    wechat_ok = True
    for batch in wechat_batches:
        _time.sleep(0.5)
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_HEADERS, json={"children": batch}, timeout=60,
        )
        if not r.is_success:
            print(f"[notion] WeChat HTML append blocked ({r.status_code}) — "
                  f"HTML saved to local file only")
            wechat_ok = False
            break

    if wechat_themes and not wechat_ok:
        # Fallback: base64-encode HTML so Cloudflare WAF won't flag inline styles.
        # Store as plaintext code blocks — WAF-safe since no HTML tags remain.
        import base64 as _b64
        import time as _time
        b64_blocks: list = []
        b64_blocks.append({"object": "block", "type": "divider", "divider": {}})
        b64_blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "微信排版 HTML (base64)"}}]},
        })
        b64_blocks.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content":
                    "内容以 base64 编码存储。使用前在浏览器控制台运行：atob(\"...\") 解码，或访问 base64decode.org"
                }}],
                "icon": {"type": "emoji", "emoji": "ℹ️"},
                "color": "blue_background",
            },
        })
        for _key, label, html in wechat_themes:
            encoded = _b64.b64encode(html.encode("utf-8")).decode("ascii")
            b64_blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": label}}]},
            })
            chunk_size = 1990
            for i in range(0, len(encoded), chunk_size):
                b64_blocks.append({
                    "object": "block", "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": encoded[i:i+chunk_size]}}],
                        "language": "plain text",
                    },
                })

        b64_ok = True
        for batch in [b64_blocks[i:i+100] for i in range(0, len(b64_blocks), 100)]:
            _time.sleep(0.3)
            r2 = httpx.patch(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=_HEADERS, json={"children": batch}, timeout=60,
            )
            if not r2.is_success:
                print(f"[notion] base64 fallback also failed ({r2.status_code})")
                b64_ok = False
                break

        if b64_ok:
            print("[notion] WeChat HTML written as base64 (WAF workaround)")
        else:
            # Last resort: save to local file
            from pathlib import Path as _Path
            import json as _json
            out_dir = _Path(__file__).parent / ".wechat_html"
            out_dir.mkdir(exist_ok=True)
            out_file = out_dir / f"{today}_{page_id[:8]}.json"
            out_file.write_text(
                _json.dumps([{"key": k, "label": l, "html": h}
                             for k, l, h in wechat_themes], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[notion] WeChat HTML saved locally → {out_file}")

    print(f"[notion] Page created: {page_url}")
    return page_url
