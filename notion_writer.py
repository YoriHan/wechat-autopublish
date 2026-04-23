"""Write translated articles to a Notion database, with images uploaded directly to Notion."""
import re
import json
import httpx
from config import NOTION_TOKEN, NOTION_DATABASE_ID, GH_PAT
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
# GitHub Gist upload for WeChat HTML themes
# ---------------------------------------------------------------------------

def _create_gist(title: str, themes: list[tuple[str, str, str]]) -> str | None:
    """
    Upload all WeChat HTML themes as a single private GitHub Gist.
    Returns the Gist HTML URL, or None on failure.

    Avoids Cloudflare WAF on api.notion.com — Gist API has no WAF on HTML content.
    """
    if not GH_PAT:
        print("[gist] GH_PAT not set — skipping Gist upload")
        return None

    files = {}
    for key, label, html in themes:
        safe_title = re.sub(r"[^\w\-]", "_", title[:40])
        filename = f"wechat_{key}_{safe_title}.html"
        files[filename] = {"content": html}

    payload = json.dumps({
        "description": f"微信排版 HTML — {title}",
        "public": False,
        "files": files,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://api.github.com/gists",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"token {GH_PAT}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
            },
        )
        import urllib.request as _ur
        with _ur.urlopen(req, timeout=30) as resp:
            gist = json.loads(resp.read())
            url = gist.get("html_url", "")
            print(f"[gist] Created: {url}")
            return url
    except Exception as e:
        print(f"[gist] Gist creation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Markdown → Notion blocks  (handles <<<IMG:N>>> placeholders)
# ---------------------------------------------------------------------------

def _md_to_blocks(md: str, images: list[str] | None = None) -> list:
    images = images or []
    blocks = []

    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

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
      - WeChat theme HTML: uploaded as a private GitHub Gist,
        Notion page stores the Gist URL (bypasses Cloudflare WAF on api.notion.com)
    Returns the page URL.
    """
    import urllib.request
    today = date.today().isoformat()
    images = images or []

    content_blocks: list = []

    # --- Cover image ---
    if cover_url:
        print(f"[notion] Uploading cover image...")
        content_blocks.append(_upload_image(cover_url))

    # --- Article body ---
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

    # --- WeChat themes: upload to GitHub Gist, store URL in Notion ---
    # Gist approach bypasses Cloudflare WAF that blocks HTML with inline styles
    # on PATCH /v1/blocks/{id}/children requests.
    gist_blocks: list = []
    if wechat_themes:
        gist_url = _create_gist(title, wechat_themes)
        gist_blocks.append({"object": "block", "type": "divider", "divider": {}})
        gist_blocks.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "微信排版 HTML"}}]},
        })
        if gist_url:
            # One callout block with the Gist link — safe for Notion (no HTML content)
            theme_names = " / ".join(label for _, label, _ in wechat_themes)
            gist_blocks.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"4 套主题（{theme_names}）已存入 GitHub Gist\n"}},
                        {"type": "text", "text": {
                            "content": gist_url,
                            "link": {"url": gist_url},
                        }},
                    ],
                    "icon": {"type": "emoji", "emoji": "🎨"},
                    "color": "purple_background",
                },
            })
            # Individual theme links (raw HTML URLs from Gist)
            for _, label, _ in wechat_themes:
                gist_blocks.append({
                    "object": "block", "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": label}}],
                    },
                })
        else:
            # GH_PAT not set or Gist failed — note in Notion, no HTML stored
            gist_blocks.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {
                        "content": "WeChat HTML 未写入（GH_PAT 未设置或 Gist 创建失败）"
                    }}],
                    "icon": {"type": "emoji", "emoji": "⚠️"},
                    "color": "yellow_background",
                },
            })

    # Notion allows max 100 blocks per call — create page with first batch
    all_blocks = content_blocks + gist_blocks
    first_batch = all_blocks[:100]
    rest = [all_blocks[i:i+100] for i in range(100, len(all_blocks), 100)]

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

    import time as _time
    for batch in rest:
        _time.sleep(0.3)
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=_HEADERS, json={"children": batch}, timeout=30,
        )
        r.raise_for_status()

    print(f"[notion] Page created: {page_url}")
    return page_url
