import feedparser, httpx, time, re
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
from config import SOURCES, TWITTER_ACCOUNTS
from db import is_duplicate
from email.utils import parsedate_to_datetime


# --- helpers ---

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


def _is_valid_img(src: str) -> bool:
    if not src or src.startswith("data:"):
        return False
    # Skip tiny tracking pixels / icons
    if any(x in src for x in ("1x1", "pixel", "tracking", "beacon", "icon")):
        return False
    return True


_URL_RE = re.compile(r'https?://[^\s"<>\']+')
# Domains that are the tweet itself or URL shorteners — skip as article URLs
_SKIP_DOMAINS = {"twitter.com", "x.com", "t.co", "bit.ly", "tinyurl.com", "ow.ly"}


def _extract_article_url(entry: dict) -> str | None:
    """For Twitter RSS entries, find the first external article link in the tweet."""
    content = entry.get("summary", "")
    if entry.get("content"):
        content += entry.get("content", [{}])[0].get("value", "")
    for url in _URL_RE.findall(content):
        domain = url.split("/")[2].lower().lstrip("www.")
        if domain not in _SKIP_DOMAINS:
            return url
    return None


# --- RSS ---

def fetch_rss(source: dict) -> list[dict]:
    feed = feedparser.parse(source["url"])
    is_twitter = source.get("twitter", False)
    articles = []
    for entry in feed.entries[:15]:
        tweet_url = entry.get("link", "")

        if is_twitter:
            # For Twitter sources: prefer the article linked in the tweet
            article_url = _extract_article_url(entry) or tweet_url
        else:
            article_url = tweet_url

        if not article_url or is_duplicate(article_url):
            continue

        title = entry.get("title", "").strip()
        # Twitter RSS titles are often just the tweet text — keep them as summary
        summary = title if is_twitter else entry.get("summary", "")[:1000]

        articles.append({
            "title": title,
            "url": article_url,
            "summary": summary[:1000],
            "published_ts": _parse_published(entry),
            "source": source["name"],
            "tier": source["tier"],
            "tweet_url": tweet_url if is_twitter else "",
        })
    return articles


# --- custom scrapers ---

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


def scrape_anthropic_research() -> list[dict]:
    """Scrape Anthropic research papers page."""
    try:
        resp = httpx.get(
            "https://www.anthropic.com/research", timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []
        seen_urls = set()
        for a in soup.find_all("a", href=re.compile(r"^/research/[a-z0-9-]+")):
            href = a["href"]
            url = "https://www.anthropic.com" + href
            if url in seen_urls or is_duplicate(url):
                continue
            seen_urls.add(url)
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            articles.append({
                "title": title, "url": url, "summary": "",
                "published_ts": time.time() - 86400,
                "source": "Anthropic Research", "tier": 1,
            })
        return articles[:6]
    except Exception as e:
        print(f"[fetcher] Anthropic Research scrape failed: {e}")
        return []


def scrape_claude_blog() -> list[dict]:
    """Scrape Claude.com blog — product updates, Skills, Claude Code."""
    try:
        resp = httpx.get(
            "https://claude.ai/blog", timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        soup = BeautifulSoup(resp.text, "lxml")
        articles = []
        seen_urls = set()
        for a in soup.find_all("a", href=re.compile(r"/blog/[a-z0-9-]+")):
            href = a["href"]
            url = href if href.startswith("http") else "https://claude.ai" + href
            if url in seen_urls or is_duplicate(url):
                continue
            seen_urls.add(url)
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            articles.append({
                "title": title, "url": url, "summary": "",
                "published_ts": time.time() - 86400,
                "source": "Claude Blog", "tier": 1,
            })
        return articles[:6]
    except Exception as e:
        print(f"[fetcher] Claude Blog scrape failed: {e}")
        return []


# --- full content fetch with images ---

def fetch_article_content(url: str) -> dict:
    """
    Fetch full article text and images.

    Returns:
        {
            "text":      str  — article text with <<<IMG:N>>> placeholders for inline images,
            "cover_url": str  — og:image or first img found,
            "images":    list[str]  — image URLs in order (index matches placeholder N),
        }
    """
    empty = {"text": "", "cover_url": "", "images": []}
    try:
        resp = httpx.get(
            url, timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            follow_redirects=True,
        )
        soup = BeautifulSoup(resp.text, "lxml")

        # --- cover image: og:image preferred ---
        cover_url = ""
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") or meta.get("name", "")
            if prop in ("og:image", "twitter:image"):
                cover_url = meta.get("content", "")
                if cover_url:
                    if not cover_url.startswith("http"):
                        cover_url = urljoin(url, cover_url)
                    break

        # --- clean up noise ---
        for tag in soup(["nav", "footer", "script", "style", "aside", "header"]):
            tag.decompose()
        body = soup.find("article") or soup.find("main") or soup.body
        if not body:
            return empty

        # --- replace <img> tags with placeholders, collect URLs ---
        images: list[str] = []

        for img in body.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src", "")
            src = src.strip() if src else ""
            if not _is_valid_img(src):
                img.decompose()
                continue
            if not src.startswith("http"):
                src = urljoin(url, src)
            idx = len(images)
            images.append(src)
            img.replace_with(f"\n<<<IMG:{idx}>>>\n")

        # Set cover from first inline image if not found in meta
        if not cover_url and images:
            cover_url = images[0]

        text = body.get_text(separator="\n", strip=True)[:10000]
        return {"text": text, "cover_url": cover_url, "images": images}

    except Exception as e:
        print(f"[fetcher] fetch_article_content failed: {e}")
        return empty


def fetch_full_text(url: str) -> str:
    """Thin wrapper kept for backward compatibility."""
    return fetch_article_content(url)["text"]


# --- orchestrator ---

def fetch_all() -> list[dict]:
    articles = []

    for source in SOURCES:
        try:
            scrape_type = source.get("scrape")
            if scrape_type == "anthropic_news":
                articles.extend(scrape_anthropic())
            elif scrape_type == "anthropic_research":
                articles.extend(scrape_anthropic_research())
            elif scrape_type == "claude_blog":
                articles.extend(scrape_claude_blog())
            elif scrape_type:
                # legacy boolean scrape -> anthropic_news
                articles.extend(scrape_anthropic())
            else:
                articles.extend(fetch_rss(source))
        except Exception as e:
            print(f"[fetcher] {source['name']} failed: {e}")

    # Twitter/X via Playwright
    try:
        from twitter_scraper import scrape_all, _session_exists
        if _session_exists():
            print("[fetcher] Scraping Twitter/X via Playwright...")
            tweets = scrape_all(TWITTER_ACCOUNTS)
            for t in tweets:
                t.setdefault("published_ts", time.time() - 3600)
                if not is_duplicate(t["url"]):
                    articles.append(t)
            print(f"[fetcher] Twitter/X: {len(tweets)} tweet(s) total")
        else:
            print("[fetcher] Twitter/X: no session — run `python twitter_scraper.py --login` to set up")
    except Exception as e:
        print(f"[fetcher] Twitter/X failed: {e}")

    # Hard cutoff: drop anything older than 48 hours
    cutoff = time.time() - 48 * 3600
    before = len(articles)
    articles = [a for a in articles if a.get("published_ts", 0) >= cutoff]
    dropped = before - len(articles)
    if dropped:
        print(f"[fetcher] Dropped {dropped} articles older than 48 h ({len(articles)} remain)")

    return articles
