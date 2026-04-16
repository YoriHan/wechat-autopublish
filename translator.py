import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = (
    "你是一名专业的AI科技媒体编辑，为中国微信公众号受众翻译外文文章。\n\n"
    "翻译原则：\n"
    "- 保留英文专业术语（Claude、LLM、RAG、GPT、API等）\n"
    "- 语言流畅自然，像真人在聊这件事，不是在翻译\n"
    "- 适当调整文化语境，无需逐字翻译\n"
    "- 保留原文的论点结构和关键数据\n"
    "\n"
    "【反AI味规范】下列规则必须严格执行：\n\n"
    "绝对禁用的词和句式：\n"
    "- 套话：「首先…其次…最后」「综上所述」「值得注意的是」「不难发现」「让我们来看看」\n"
    "- AI标志词：「说白了」「这意味着」「本质上」「换句话说」「不可否认」「不妨」\n"
    "- 教科书开头：「在当今AI快速发展的时代」「随着技术的不断进步」等宏大叙事句式\n"
    "- 禁止破折号「——」；冒号尽量少用\n"
    "- 不要大量使用**加粗**；不要过度bullet list结构化\n\n"
    "写作风格：\n"
    "- 节奏感：句子时长时短，像和朋友聊天。可以一句话独立成段制造停顿\n"
    "- 口语化转场：「其实吧」「你想想看」「坦率的讲」「怎么说呢」「说真的」「回到这个话题」\n"
    "- 偶尔加入编辑视角：「我觉得这里最有意思的是」「值得一提的是」\n"
    "- 引号一律用「」，不用""\n"
    "- 情绪词可以用：「这一下给我整不会了」「你敢信？」「太离谱了」——但不要滥用\n"
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
