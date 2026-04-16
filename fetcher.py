import feedparser, httpx, time, re
from bs4 import BeautifulSoup
from config import SOURCES
from db import is_duplicate
from email.utils import parsedate_to_datetime

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
    for source in SOURCES:
        try:
            if source.get("scrape"):
                articles.extend(scrape_anthropic())
            else:
                articles.extend(fetch_rss(source))
        except Exception as e:
            print(f"[fetcher] {source['name']} failed: {e}")
    return articles
