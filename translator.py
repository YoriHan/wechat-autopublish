import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "你是一名专业的AI科技媒体编辑，为中国微信公众号受众翻译外文文章。\n\n"
    "翻译原则：\n"
    "- 保留英文专业术语（Claude、LLM、RAG、GPT、API等）\n"
    "- 语言流畅自然，避免翻译腔\n"
    "- 适当调整文化语境，无需逐字翻译\n"
    "- 保留原文的论点结构和关键数据\n"
)

def _build_prompt(source: str, author: str, url: str, content: str) -> str:
    return (
        f"请将以下文章翻译为适合微信公众号的中文，按如下格式输出：\n\n"
        f"第一行必须是：# [中文标题]\n\n"
        f"> 📌 原文来源：{source} | 作者：{author} | 原文链接：{url}\n\n"
        f"**编者按：** [用1-2句话说明此文的价值，为什么值得读]\n\n"
        f"（正文翻译，使用 ## 作为二级标题，**加粗**重点，保持段落清晰）\n\n"
        f"---\n"
        f"*本文由 AI 辅助翻译自英文原文，如有偏差以原文为准。*\n\n"
        f"原文内容：\n{content}"
    )

def translate(article: dict, full_text: str) -> str:
    prompt = _build_prompt(
        source=article["source"],
        author=article.get("author", "未知"),
        url=article["url"],
        content=full_text or article["summary"] or article["title"],
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

def extract_chinese_title(translated_md: str) -> str:
    lines = [l.strip() for l in translated_md.splitlines()]
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    for line in lines:
        if line and not line.startswith(">") and not line.startswith("*"):
            return line[:60]
    return "今日AI译介"
