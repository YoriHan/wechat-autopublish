from dotenv import load_dotenv
from pathlib import Path
import os
import sys

load_dotenv(Path(__file__).parent / ".env")

try:
    ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
    WECHAT_APP_ID = os.environ["WECHAT_APP_ID"]
    WECHAT_APP_SECRET = os.environ["WECHAT_APP_SECRET"]
    WECHAT_COVER_MEDIA_ID = os.environ["WECHAT_COVER_MEDIA_ID"]
except KeyError as e:
    print(f"[config] Missing required env var: {e}. Check your .env file.", file=sys.stderr)
    sys.exit(1)
BARK_KEY = os.environ.get("BARK_KEY", "")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")

BASE_DIR = Path(__file__).parent

SOURCES = [
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml", "tier": 1},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "tier": 1},
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "tier": 1},
    {"name": "The Batch", "url": "https://www.deeplearning.ai/the-batch/feed/", "tier": 2},
    {"name": "HN AI", "url": "https://hnrss.org/newest?q=Claude+LLM+AI+agent&points=50", "tier": 2},
    {"name": "Anthropic Scrape", "url": "https://www.anthropic.com/news", "tier": 1, "scrape": True},
]

RELEVANCE_KEYWORDS = [
    "claude", "llm", "gpt", "gemini", "ai agent", "model", "reasoning",
    "anthropic", "openai", "deepmind", "reinforcement", "training",
]
