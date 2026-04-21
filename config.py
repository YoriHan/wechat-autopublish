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

# RSSHub base URL — set RSSHUB_BASE_URL to your self-hosted instance for reliability
# Self-host: docker run -d -p 1200:1200 diygod/rsshub
# Then set: RSSHUB_BASE_URL=http://your-server:1200
RSSHUB_BASE_URL = os.environ.get("RSSHUB_BASE_URL", "https://rsshub.app").rstrip("/")

BASE_DIR = Path(__file__).parent

# Twitter/X accounts to follow via RSSHub.
# Each entry produces an RSS feed: {RSSHUB_BASE_URL}/twitter/user/{handle}
# The fetcher extracts article links shared in tweets (not just the tweet itself).
TWITTER_RSS_ACCOUNTS = [
    # ── AI Lab leaders ──
    ("sama",           "Sam Altman",           1),
    ("karpathy",       "Andrej Karpathy",       1),
    ("ylecun",         "Yann LeCun",            1),
    ("demishassabis",  "Demis Hassabis",        1),
    ("AnthropicAI",    "Anthropic",             1),
    ("OpenAI",         "OpenAI",                1),
    ("GoogleAI",       "Google AI",             1),
    ("MetaAI",         "Meta AI",               1),
    ("MistralAI",      "Mistral AI",            1),
    # ── Researchers & practitioners ──
    ("emollick",       "Ethan Mollick",         1),  # best applied AI commentary
    ("DrJimFan",       "Jim Fan / NVIDIA",      1),  # robotics + embodied AI
    ("gdb",            "Greg Brockman",         1),
    ("fchollet",       "François Chollet",      1),  # Keras, ARC Prize
    ("JeffDean",       "Jeff Dean",             1),  # Google
    ("ilyasut",        "Ilya Sutskever",        2),
    ("npew",           "Nathan Lambert",        2),  # RLHF / alignment
    ("hardmaru",       "David Ha",              2),  # Sakana AI
    # ── AI tools & platforms ──
    ("huggingface",    "HuggingFace",           2),
    ("LangChainAI",    "LangChain",             2),
    ("weights_biases", "Weights & Biases",      2),
    ("ReplicateHQ",    "Replicate",             2),
    ("Scale_AI",       "Scale AI",              2),
    # ── Tech analysis & VC ──
    ("paulg",          "Paul Graham",           2),  # YC essays on tech
    ("pmarca",         "Marc Andreessen",       2),  # a16z
    ("benedictevans",  "Benedict Evans",        2),  # best tech industry analysis
    # ── Engineering blogs ──
    ("netflixtech",    "Netflix Tech",          2),  # high-quality engineering articles
    # ── High-freq article sharers (A类) ──
    ("_akhaliq",       "AK / Papers Daily",     1),  # posts arXiv papers every day, must-follow
    ("omarsar0",       "Elvis Saravia",         1),  # DAIR.AI, AI newsletter curator
    ("chiphuyen",      "Chip Huyen",            1),  # ML systems, Designing ML Systems author
    ("rasbt",          "Sebastian Raschka",     1),  # ML books, frequent article shares
    ("svpino",         "Santiago Valdarrama",   1),  # ML practitioner, tutorials & articles
    ("reach_vb",       "Vaibhav Srivastava",    1),  # HuggingFace daily papers curator, very prolific
    ("arankomatsuzaki","Aran Komatsuzaki",       1),  # arXiv papers daily, JAX/TPU research
    ("cwolferesearch", "Cameron Wolfe",          1),  # Deep Learning Focus newsletter, paper breakdowns
    # ── Framework authors & practitioners (B类) ──
    ("jeremyphoward",  "Jeremy Howard",         2),  # fast.ai
    ("goodside",       "Riley Goodside",        2),  # prompt engineering expert
    ("ClementDelangue","Clément Delangue",      2),  # HuggingFace CEO personal account
    ("jackclarkSF",    "Jack Clark",            2),  # Import AI newsletter, Anthropic co-founder
    ("eugeneyan",      "Eugene Yan",            2),  # applied ML at Amazon, writes deep essays
    ("srush_nlp",      "Sasha Rush",            2),  # Harvard NLP, LLM research & tools
    ("HamelHusain",    "Hamel Husain",          2),  # ML engineer, RAG/LLM practitioner tutorials
    ("AravSrinivas",   "Arav Srinivas",         2),  # Perplexity AI CEO
    ("GaryMarcus",     "Gary Marcus",           2),  # AI researcher/critic, frequent op-eds
    # ── AI platforms & orgs (B类) ──
    ("xai",            "xAI",                   2),  # Elon's xAI, Grok announcements
    ("Gradio",         "Gradio",                2),  # ML demo platform, tutorials
    ("llama_index",    "LlamaIndex",            2),  # LlamaIndex / Jerry Liu
    ("MSFTResearch",   "Microsoft Research",    2),  # MSFT Research blog & papers
    # ── Engineering & dev education (C类) ──
    ("GergelyOrosz",   "Gergely Orosz",         2),  # Pragmatic Engineer, must-read eng articles
    ("addyosmani",     "Addy Osmani",           2),  # Google Chrome, web perf articles
    ("swyx",           "swyx",                  2),  # developer educator, lots of AI analysis
    ("b0rk",           "Julia Evans",           2),  # zines & deep dives on systems/debugging
    ("danluu",         "Dan Luu",               2),  # systems engineering essays, very thorough
    ("copyconstruct",  "Cindy Sridharan",       2),  # distributed systems, observability articles
]


def _twitter_rss_sources() -> list[dict]:
    return [
        {
            "name": f"𝕏 {label}",
            "url":  f"{RSSHUB_BASE_URL}/twitter/user/{handle}",
            "tier": tier,
            "twitter": True,   # flag: extract article links from tweet content
        }
        for handle, label, tier in TWITTER_RSS_ACCOUNTS
    ]


SOURCES = [
    # ── Tier 1: Primary AI/tech sources ──
    {"name": "OpenAI Blog",      "url": "https://openai.com/news/rss.xml",                                    "tier": 1},
    {"name": "Google DeepMind",  "url": "https://deepmind.google/blog/rss.xml",                               "tier": 1},
    {"name": "Simon Willison",   "url": "https://simonwillison.net/atom/everything/",                         "tier": 1},
    {"name": "Anthropic News",   "url": "https://www.anthropic.com/news",     "tier": 1, "scrape": "anthropic_news"},
    {"name": "Anthropic Research","url": "https://www.anthropic.com/research","tier": 1, "scrape": "anthropic_research"},
    {"name": "Claude Blog",      "url": "https://claude.ai/blog",             "tier": 1, "scrape": "claude_blog"},
    {"name": "HuggingFace Blog", "url": "https://huggingface.co/blog/feed.xml",                               "tier": 1},
    {"name": "TechCrunch AI",    "url": "https://techcrunch.com/category/artificial-intelligence/feed/",      "tier": 1},
    {"name": "VentureBeat AI",   "url": "https://venturebeat.com/category/ai/feed/",                         "tier": 1},
    # ── Tier 2: Broader tech / research ──
    {"name": "The Batch",        "url": "https://www.deeplearning.ai/the-batch/feed/",                       "tier": 2},
    {"name": "MIT Tech Review",  "url": "https://www.technologyreview.com/feed/",                            "tier": 2},
    {"name": "The Verge AI",     "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml", "tier": 2},
    {"name": "Papers With Code", "url": "https://paperswithcode.com/latest.rss",                             "tier": 2},
    {"name": "HN AI",            "url": "https://hnrss.org/newest?q=Claude+LLM+AI+agent&points=50",         "tier": 2},
    {"name": "Bloomberg Tech",   "url": "https://feeds.bloomberg.com/technology/news.rss",                   "tier": 2},
    {"name": "WSJ Tech",         "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml",                           "tier": 2},
    # ── Twitter/X via RSSHub (article links extracted from tweets) ──
    *_twitter_rss_sources(),
]

# Legacy — kept for backward compat; no longer used by fetcher
TWITTER_ACCOUNTS: list[str] = []

RELEVANCE_KEYWORDS = [
    "claude", "llm", "gpt", "gemini", "ai agent", "model", "reasoning",
    "anthropic", "openai", "deepmind", "reinforcement", "training",
]
