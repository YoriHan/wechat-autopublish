"""
twitter_scraper.py — X.com scraper using a saved Playwright session.

First-time setup (saves session to .twitter_session/):
  python twitter_scraper.py --login
  python twitter_scraper.py --login --username EMAIL --password PASS

Or set TWITTER_USERNAME / TWITTER_PASSWORD in .env and just run:
  python twitter_scraper.py --login

Subsequent runs reuse the saved session automatically.
"""

import time, os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

SESSION_DIR  = Path(__file__).parent / ".twitter_session"
SESSION_FILE = SESSION_DIR / "state.json"

TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD", "")


# ---------------------------------------------------------------------------
# Login & session management
# ---------------------------------------------------------------------------

def login_and_save_session(username: str = "", password: str = "") -> bool:
    """
    Log in to X.com with Playwright, save storage state to SESSION_FILE.
    Returns True on success.
    """
    username = username or TWITTER_USERNAME
    password = password or TWITTER_PASSWORD
    if not username or not password:
        print("[twitter] No credentials — pass --username / --password or set TWITTER_USERNAME/TWITTER_PASSWORD in .env")
        return False

    SESSION_DIR.mkdir(exist_ok=True)
    print(f"[twitter] Logging in as {username}...")

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
        page = ctx.new_page()
        try:
            page.goto("https://x.com/i/flow/login", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Step 1: username / email
            page.fill('input[autocomplete="username"]', username)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            # Step 2: "Enter phone or username" extra verification prompt
            try:
                unusual = page.locator('input[data-testid="ocfEnterTextTextInput"]')
                if unusual.is_visible(timeout=3000):
                    unusual.fill(username)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            # Step 3: password
            page.fill('input[name="password"]', password)
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            # Verify success
            logged_in = False
            try:
                page.wait_for_selector('[data-testid="SideNav_NewTweet_Button"]', timeout=10000)
                logged_in = True
            except PWTimeout:
                logged_in = "home" in page.url

            if logged_in:
                ctx.storage_state(path=str(SESSION_FILE))
                print(f"[twitter] Login successful. Session saved → {SESSION_FILE}")
                browser.close()
                return True
            else:
                print(f"[twitter] Login may have failed — URL: {page.url}")
                browser.close()
                return False

        except Exception as e:
            print(f"[twitter] Login error: {e}")
            browser.close()
            return False


def _session_exists() -> bool:
    return SESSION_FILE.exists() and SESSION_FILE.stat().st_size > 100


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_account(account: str, limit: int = 5) -> list[dict]:
    """Scrape recent tweets from an X.com account using the saved session."""
    if not _session_exists():
        return []

    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                storage_state=str(SESSION_FILE),
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()
            page.goto(f"https://x.com/{account}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)

            try:
                page.wait_for_selector('[data-testid="tweetText"]', timeout=12000)
            except PWTimeout:
                print(f"[twitter] No tweets visible for @{account} — session may be expired")
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
                    "tier": 1,
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


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from config import TWITTER_RSS_ACCOUNTS

    parser = argparse.ArgumentParser(description="Twitter/X scraper")
    parser.add_argument("--login",    action="store_true", help="Log in and save session")
    parser.add_argument("--username", default="", help="X.com username or email")
    parser.add_argument("--password", default="", help="X.com password")
    args = parser.parse_args()

    if args.login:
        ok = login_and_save_session(args.username, args.password)
        if ok:
            print("\n[twitter] Testing session with @AnthropicAI...")
            items = scrape_account("AnthropicAI", limit=2)
            for item in items:
                print(f"  {item['source']}: {item['title'][:70]}")
    else:
        accounts = [h for h, *_ in TWITTER_RSS_ACCOUNTS[:3]]
        items = scrape_all(accounts)
        for item in items:
            print(f"  {item['source']}: {item['title'][:70]}")
