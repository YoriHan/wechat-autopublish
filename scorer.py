from config import RELEVANCE_KEYWORDS
import time

def score(article: dict) -> float:
    s = 0.0
    age_h = (time.time() - article["published_ts"]) / 3600
    if age_h < 48:
        s += 40
    elif age_h < 168:
        s += 40 * (1 - (age_h - 48) / 120)
    s += 35 if article["tier"] == 1 else 20
    text = (article["title"] + " " + article["summary"]).lower()
    hits = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)
    s += min(hits * 5, 25)
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
