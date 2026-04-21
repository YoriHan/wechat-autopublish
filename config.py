from dotenv import load_dotenv
from pathlib import Path
import os
import sys

load_dotenv(Path(__file__).parent / ".env")

try:
    DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
except KeyError as e:
    print(f"[config] Missing required env var: {e}. Check your .env file.", file=sys.stderr)
    sys.exit(1)

# WeChat — optional; pipeline skips WeChat output if not set
WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
WECHAT_COVER_MEDIA_ID = os.environ.get("WECHAT_COVER_MEDIA_ID", "")

# Notion — optional; pipeline writes to Notion if token is set
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
BARK_KEY = os.environ.get("BARK_KEY", "")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
USE_MD2WECHAT = os.environ.get("USE_MD2WECHAT", "false").lower() == "true"
WECHAT_THEME = os.environ.get("WECHAT_THEME", "autumn-warm")

BASE_DIR = Path(__file__).parent

SOURCES = [
    # Tier 1: Primary AI/tech sources
    {"name": "OpenAI Blog", "url": "https://openai.com/news/rss.xml", "tier": 1},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "tier": 1},
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/everything/", "tier": 1},
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news", "tier": 1, "scrape": "anthropic_news"},
    {"name": "Anthropic Research", "url": "https://www.anthropic.com/research", "tier": 1, "scrape": "anthropic_research"},
    {"name": "Claude Blog", "url": "https://claude.ai/blog", "tier": 1, "scrape": "claude_blog"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "tier": 1},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "tier": 1},
    {"name": "Bloomberg Tech", "url": "https://feeds.bloomberg.com/technology/news.rss", "tier": 1},
    # Tier 2: Broader tech/business sources
    {"name": "The Batch", "url": "https://www.deeplearning.ai/the-batch/feed/", "tier": 2},
    {"name": "HN AI", "url": "https://hnrss.org/newest?q=Claude+LLM+AI+agent&points=50", "tier": 2},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/", "tier": 2},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml", "tier": 2},
    {"name": "WSJ Tech", "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml", "tier": 2},
]

TWITTER_ACCOUNTS = [
    "AnthropicAI", "sama", "karpathy", "ylecun", "demishassabis",
    "business",       # Bloomberg
    "WSJ",            # Wall Street Journal
    "theinformation", # The Information
]

RELEVANCE_KEYWORDS = [
    "claude", "llm", "gpt", "gemini", "ai agent", "model", "reasoning",
    "anthropic", "openai", "deepmind", "reinforcement", "training",
]
