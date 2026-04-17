"""
twitter_scraper.py — 从 Chrome 读 cookies，用 Playwright 抓 Twitter/X 推文
无需手动登录，直接复用浏览器里的登录态。
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

SESSION_DIR = Path(__file__).parent / ".twitter_session"


def _get_chrome_cookies() -> list[dict]:
    """从用户 Chrome 读取 x.com cookies。"""
    try:
        import browser_cookie3
        jar = browser_cookie3.chrome(domain_name='.x.com')
        cookies = []
        for c in jar:
            cookies.append({
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path or "/",
                "secure": bool(c.secure),
                "httpOnly": False,
                "sameSite": "Lax",
            })
        return cookies
    except Exception as e:
        print(f"[twitter] Failed to read Chrome cookies: {e}")
        return []


def scrape_account(account: str, limit: int = 5) -> list[dict]:
    """抓取指定账号的最新推文。"""
    cookies = _get_chrome_cookies()
    if not cookies:
        print(f"[twitter] No cookies found — skipping @{account}")
        return []

    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            page.goto(f"https://x.com/{account}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            try:
                page.wait_for_selector('[data-testid="tweetText"]', timeout=12000)
            except PWTimeout:
                print(f"[twitter] No tweets visible for @{account}")
                browser.close()
                return []

            tweets = page.eval_on_selector_all(
                '[data-testid="tweetText"]',
                "els => els.slice(0, 8).map(el => el.innerText)"
            )
            links = page.eval_on_selector_all(
                'article a[href*="/status/"]',
                "els => [...new Set(els.map(el => el.href))].slice(0, 8)"
            )

            for i, text in enumerate(tweets[:limit]):
                text = text.strip()
                if not text or len(text) < 30:
                    continue
                url = links[i] if i < len(links) else f"https://x.com/{account}"
                results.append({
                    "title": text[:100].replace("\n", " "),
                    "summary": text,
                    "url": url,
                    "source": f"@{account}",
                    "author": account,
                    "tier": 2,
                    "published_ts": time.time() - i * 1800,
                })

            browser.close()
    except Exception as e:
        print(f"[twitter] Error scraping @{account}: {e}")

    return results


def scrape_all(accounts: list[str]) -> list[dict]:
    all_items = []
    for account in accounts:
        print(f"[twitter] Scraping @{account}...")
        items = scrape_account(account, limit=5)
        print(f"[twitter]   → {len(items)} tweets")
        all_items.extend(items)
    return all_items


def _session_exists() -> bool:
    """Always true — we use Chrome cookies, no separate session needed."""
    try:
        import browser_cookie3
        jar = browser_cookie3.chrome(domain_name='.x.com')
        return any(c.name == 'auth_token' for c in jar)
    except Exception:
        return False


if __name__ == "__main__":
    from config import TWITTER_ACCOUNTS
    items = scrape_all(TWITTER_ACCOUNTS[:3])
    for item in items:
        print(f"  {item['source']}: {item['title'][:70]}")
