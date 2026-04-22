from config import (
    RELEVANCE_KEYWORDS,
    DEEP_CONTENT_SOURCES,
    NEWS_SOURCES,
    DEEP_TITLE_SIGNALS,
    NEWS_TITLE_SIGNALS,
)
import time


def score(article: dict) -> float:
    s = 0.0
    title_lower = article["title"].lower()
    text = (article["title"] + " " + article["summary"]).lower()

    # --- Recency (0–40 pts) ---
    age_h = (time.time() - article["published_ts"]) / 3600
    if age_h < 48:
        s += 40
    elif age_h < 168:
        s += 40 * (1 - (age_h - 48) / 120)

    # --- Source quality (0–35 pts) ---
    source = article.get("source", "")
    if source in DEEP_CONTENT_SOURCES:
        s += 35          # Research / long-form sources
    elif source in NEWS_SOURCES:
        s += 5           # News snippets — minimal credit
    elif article["tier"] == 1:
        s += 20          # Tier-1 sources not in either list
    else:
        s += 10          # Tier-2 sources

    # --- Keyword relevance (0–25 pts) ---
    hits = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    s += min(hits * 5, 25)

    # --- Deep-content title signals (+3 each, up to +20) ---
    deep_hits = sum(1 for sig in DEEP_TITLE_SIGNALS if sig in title_lower)
    s += min(deep_hits * 3, 20)

    # --- News-snippet title penalties (−5 each, down to −20) ---
    news_hits = sum(1 for sig in NEWS_TITLE_SIGNALS if sig in title_lower)
    s -= min(news_hits * 5, 20)

    return round(s, 1)


def select_best(articles: list[dict]) -> dict | None:
    scored = [(a, score(a)) for a in articles]
    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored:
        return None
    best, best_score = scored[0]
    print(f"[scorer] Best: '{best['title']}' score={best_score}")
    if best_score < 30:
        print(f"[scorer] Best score {best_score} < 30 — publishing anyway (never skip)")
    best["score"] = best_score
    return best
