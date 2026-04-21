"""Render HTML to screenshot and upload to GitHub for Notion preview."""
import base64, os, tempfile, httpx
from datetime import date

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "YoriHan/wechat-autopublish"
BRANCH       = "main"


def _html_to_png(html: str, out_path: str) -> bool:
    """Render HTML to PNG using headless Chromium via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 430, "height": 900})
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=out_path, full_page=True)
            browser.close()
        return True
    except Exception as e:
        print(f"[screenshot] Playwright error: {e}")
        return False


def _upload_to_github(png_path: str, theme_key: str) -> str | None:
    """Upload PNG to GitHub repo, return raw URL."""
    if not GITHUB_TOKEN:
        print("[screenshot] GITHUB_TOKEN not set — skipping upload")
        return None

    today = date.today().isoformat()
    remote = f"screenshots/{today}/{theme_key}.png"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{remote}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    with open(png_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    # Check if file already exists (need SHA to overwrite)
    sha = None
    check = httpx.get(api_url, headers=headers, timeout=15)
    if check.status_code == 200:
        sha = check.json().get("sha")

    payload: dict = {
        "message": f"chore: screenshot {today}/{theme_key}",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    resp = httpx.put(api_url, headers=headers, json=payload, timeout=60)
    if resp.status_code in (200, 201):
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{BRANCH}/{remote}"
        print(f"[screenshot] Uploaded → {raw_url}")
        return raw_url
    else:
        print(f"[screenshot] Upload failed: {resp.status_code} {resp.text[:200]}")
        return None


def render_and_upload(html: str, theme_key: str) -> str | None:
    """Render HTML to screenshot, upload to GitHub. Returns public URL or None."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
    try:
        if _html_to_png(html, tmp_path):
            return _upload_to_github(tmp_path, theme_key)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
