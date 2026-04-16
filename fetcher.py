import feedparser, httpx, time, re, json, subprocess
from bs4 import BeautifulSoup
from pathlib import Path
from config import SOURCES, TWITTER_ACCOUNTS
from db import is_duplicate
from email.utils import parsedate_to_datetime

# --- CDP Proxy (web-access skill) ---
CDP_PROXY_PORT = 3456
CDP_PROXY_URL = f"http://127.0.0.1:{CDP_PROXY_PORT}"
CDP_PROXY_SCRIPT = Path.home() / ".claude/skills/web-access/scripts/cdp-proxy.mjs"
_cdp_proc = None


def _cdp_available() -> bool:
    """Returns True if the CDP proxy is running AND Chrome is connected."""
    try:
        resp = httpx.get(f"{CDP_PROXY_URL}/health", timeout=2)
        data = resp.json()
        return data.get("status") == "ok" and data.get("connected", False)
    except Exception:
        return False


def _ensure_cdp() -> bool:
    """Start CDP proxy subprocess if not already running. Returns True if available."""
    global _cdp_proc
    if _cdp_available():
        return True
    if not CDP_PROXY_SCRIPT.exists():
        return False
    try:
        _cdp_proc = subprocess.Popen(
            ["node", str(CDP_PROXY_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(6):
            time.sleep(1)
            if _cdp_available():
                return True
        return False
    except Exception:
        return False


def _cdp_eval(target_id: str, js: str, timeout: int = 15) -> object:
    """Run JS in a tab. Returns the value, or None on error."""
    try:
        resp = httpx.post(
            f"{CDP_PROXY_URL}/eval",
            params={"target": target_id},
            content=js,
            timeout=timeout,
        )
        data = resp.json()
        return data.get("value")
    except Exception:
        return None


def _cdp_open(url: str, timeout: int = 25) -> str | None:
    """Open a background tab and wait for load. Returns targetId or None."""
    try:
        resp = httpx.get(f"{CDP_PROXY_URL}/new", params={"url": url}, timeout=timeout)
        return resp.json().get("targetId")
    except Exception:
        return None


def _cdp_close(target_id: str) -> None:
    try:
        httpx.get(f"{CDP_PROXY_URL}/close", params={"target": target_id}, timeout=5)
    except Exception:
        pass


def fetch_full_text_via_cdp(url: str) -> str:
    """Fetch full page text via user's Chrome (login state, JS rendered)."""
    target_id = _cdp_open(url)
    if not target_id:
        return ""
    try:
        text = _cdp_eval(target_id, "document.body.innerText")
        return (text or "")[:8000]
    finally:
        _cdp_close(target_id)


def scrape_twitter_cdp(account: str) -> list[dict]:
    """Scrape recent tweet threads from a Twitter/X account via CDP."""
    url = f"https://x.com/{account}"
    target_id = _cdp_open(url, timeout=35)
    if not target_id:
        return []
    try:
        # Extra wait for Twitter's JS to hydrate
        time.sleep(4)
        js = (
            "JSON.stringify("
            "  Array.from(document.querySelectorAll('[data-testid=\"tweetText\"]'))"
            "  .slice(0, 6).map(el => el.innerText)"
            ")"
        )
        raw = _cdp_eval(target_id, js)
        if not raw:
            return []
        tweets = json.loads(raw)
        articles = []
        for i, text in enumerate(tweets):
            text = text.strip()
            if len(text) < 60:
                continue
            if is_duplicate(url + f"#t{i}"):
                continue
            articles.append({
                "title": text[:120].replace("\n", " "),
                "url": url + f"#t{i}",
                "summary": text[:600],
                "published_ts": time.time() - i * 1800,
                "source": f"@{account}",
                "tier": 1,
            })
        return articles
    except Exception as e:
        print(f"[fetcher] @{account} CDP parse error: {e}")
        return []
    finally:
        _cdp_close(target_id)


# --- Existing RSS / httpx fetchers ---

def _parse_published(entry: dict) -> float:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return time.mktime(parsed)
    pub_str = entry.get("published", "") or entry.get("updated", "")
    if pub_str:
        try:
            return parsedate_to_datetime(pub_str).timestamp()
        except Exception:
            pass
    return time.time() - 86400


def fetch_rss(source: dict) -> list[dict]:
    feed = feedparser.parse(source["url"])
    articles = []
    for entry in feed.entries[:10]:
        url = entry.get("link", "")
        if not url or is_duplicate(url):
            continue
        articles.append({
            "title": entry.get("title", "").strip(),
            "url": url,
            "summary": entry.get("summary", "")[:1000],
            "published_ts": _parse_published(entry),
            "source": source["name"],
            "tier": source["tier"],
        })
    return articles


def scrape_anthropic() -> list[dict]:
    resp = httpx.get(
        "https://www.anthropic.com/news", timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    )
    soup = BeautifulSoup(resp.text, "lxml")
    articles = []
    seen_urls = set()
    for a in soup.find_all("a", href=re.compile(r"^/news/[a-z0-9-]+")):
        href = a["href"]
        url = "https://www.anthropic.com" + href
        if url in seen_urls or is_duplicate(url):
            continue
        seen_urls.add(url)
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or title.lower() in ("news", "research", "company"):
            continue
        articles.append({
            "title": title, "url": url, "summary": "",
            "published_ts": time.time() - 86400,
            "source": "Anthropic", "tier": 1,
        })
    return articles[:8]


def fetch_full_text(url: str) -> str:
    """Fetch full article text. Uses CDP when available (Twitter/X), else httpx."""
    if _cdp_available() and ("x.com" in url or "twitter.com" in url):
        text = fetch_full_text_via_cdp(url)
        if text:
            return text
    try:
        resp = httpx.get(
            url, timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            follow_redirects=True
        )
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["nav", "footer", "script", "style", "aside", "header"]):
            tag.decompose()
        body = soup.find("article") or soup.find("main") or soup.body
        return body.get_text(separator="\n", strip=True)[:8000] if body else ""
    except Exception:
        return ""


def fetch_all() -> list[dict]:
    articles = []

    # RSS + httpx sources
    for source in SOURCES:
        try:
            if source.get("scrape"):
                articles.extend(scrape_anthropic())
            else:
                articles.extend(fetch_rss(source))
        except Exception as e:
            print(f"[fetcher] {source['name']} failed: {e}")

    # Twitter/X via CDP (only when user's Chrome is open and connected)
    if _ensure_cdp():
        print("[fetcher] CDP available — scraping Twitter/X accounts")
        for account in TWITTER_ACCOUNTS:
            try:
                tweets = scrape_twitter_cdp(account)
                articles.extend(tweets)
                if tweets:
                    print(f"[fetcher] @{account}: {len(tweets)} tweet(s)")
            except Exception as e:
                print(f"[fetcher] @{account} failed: {e}")
    else:
        print("[fetcher] CDP not available — skipping Twitter/X (Chrome not open)")

    return articles
