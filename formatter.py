import mistune, re, subprocess, json, tempfile, os
from openai import OpenAI
from config import DEEPSEEK_API_KEY

# mistune PINNED to 2.0.5 — do NOT upgrade. 3.x removed mistune.html()

_deepseek = None


def _get_deepseek():
    global _deepseek
    if _deepseek is None:
        _deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
    return _deepseek


# ---------- Theme definitions ----------

THEMES: dict[str, dict] = {
    "green": {
        "label":    "🟢 绿色清新",
        "primary":  "#07C160",
        "bg_light": "#f6fff9",
        "strong":   "#07C160",
        "link":     "#07C160",
        "h_border": "#07C160",
    },
    "blue": {
        "label":    "🔵 蓝色商务",
        "primary":  "#1677FF",
        "bg_light": "#f0f5ff",
        "strong":   "#1677FF",
        "link":     "#1677FF",
        "h_border": "#1677FF",
    },
    "minimal": {
        "label":    "⚫ 极简黑白",
        "primary":  "#222222",
        "bg_light": "#f5f5f5",
        "strong":   "#111111",
        "link":     "#333333",
        "h_border": "#555555",
    },
    "purple": {
        "label":    "🟣 紫色优雅",
        "primary":  "#7C3AED",
        "bg_light": "#f5f0ff",
        "strong":   "#7C3AED",
        "link":     "#7C3AED",
        "h_border": "#7C3AED",
    },
}

DEFAULT_THEME = "green"


# ---------- md2wechat AI mode (enhanced styling) ----------

def _md2wechat_available() -> bool:
    return subprocess.run(["which", "md2wechat"], capture_output=True).returncode == 0


def _md2wechat_prompt(markdown: str, theme: str) -> str | None:
    """Call md2wechat CLI to get the theme prompt for a Markdown string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(markdown)
        tmp = f.name
    try:
        result = subprocess.run(
            ["md2wechat", "convert", tmp, "--mode", "ai", "--theme", theme, "--json"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        return data.get("data", {}).get("prompt")
    except Exception:
        return None
    finally:
        os.unlink(tmp)


def format_article_md2wechat(translated_md: str, chinese_title: str, theme: str = "autumn-warm") -> tuple[str, str]:
    """Format using md2wechat AI theme + DeepSeek. Falls back to mistune on any error."""
    prompt = _md2wechat_prompt(translated_md, theme)
    if not prompt:
        return format_article(translated_md, chinese_title)

    try:
        resp = _get_deepseek().chat.completions.create(
            model="deepseek-chat",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        html = resp.choices[0].message.content
        if "```html" in html:
            html = html.split("```html")[1].split("```")[0].strip()
        elif "```" in html:
            html = html.split("```")[1].split("```")[0].strip()
    except Exception:
        return format_article(translated_md, chinese_title)

    clean = re.sub(r'<[^>]+>', '', translated_md)
    clean = re.sub(r'[#*`>_\[\]]+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    summary = clean[:200] + "..."
    return html, summary


# ---------- Theme-aware mistune formatter ----------

def md_to_wechat_html(md_text: str, chinese_title: str, theme_key: str = DEFAULT_THEME) -> str:
    t = THEMES.get(theme_key, THEMES[DEFAULT_THEME])
    p = t["primary"]
    bg = t["bg_light"]
    strong_c = t["strong"]
    link_c = t["link"]

    processed = re.sub(r'^# .+\r?\n?', '', md_text, count=1, flags=re.MULTILINE)
    html = mistune.html(processed)

    # Headings
    html = html.replace(
        '<h1>',
        f'<h1 style="font-size:24px;font-weight:bold;color:#1a1a1a;'
        f'margin:32px 0 16px;line-height:1.4;'
        f'border-bottom:2px solid {p};padding-bottom:8px;">'
    )
    html = html.replace(
        '<h2>',
        f'<h2 style="font-size:20px;font-weight:bold;color:#1a1a1a;'
        f'margin:28px 0 12px;line-height:1.4;'
        f'border-left:4px solid {p};padding-left:10px;">'
    )
    html = html.replace(
        '<h3>',
        '<h3 style="font-size:17px;font-weight:bold;color:#333;'
        'margin:20px 0 8px;line-height:1.5;">'
    )
    html = html.replace(
        '<h4>',
        '<h4 style="font-size:15px;font-weight:bold;color:#444;margin:16px 0 6px;">'
    )

    # Paragraph
    html = html.replace(
        '<p>',
        '<p style="font-size:16px;line-height:1.9;color:#333;'
        'margin:16px 0;letter-spacing:0.03em;">'
    )

    # Strong / Em
    html = html.replace(
        '<strong>',
        f'<strong style="color:{strong_c};font-weight:bold;">'
    )
    html = html.replace(
        '<em>',
        '<em style="color:#555;font-style:italic;">'
    )

    # Lists
    html = html.replace(
        '<ul>',
        '<ul style="padding-left:24px;margin:12px 0;list-style-type:disc;">'
    )
    html = html.replace(
        '<ol>',
        '<ol style="padding-left:24px;margin:12px 0;list-style-type:decimal;">'
    )
    html = html.replace(
        '<li>',
        '<li style="font-size:15px;line-height:1.9;color:#444;margin:6px 0;">'
    )

    # Blockquotes
    html = html.replace(
        '<blockquote>',
        f'<blockquote style="border-left:4px solid {p};'
        f'background:{bg};margin:16px 0;padding:12px 16px;'
        f'border-radius:0 4px 4px 0;">'
    )

    # Inline code
    html = re.sub(
        r'<code>(?!</code>)',
        '<code style="background:#f0f0f0;color:#c0392b;'
        'padding:2px 6px;border-radius:3px;font-size:14px;'
        'font-family:\'Courier New\',Courier,monospace;">',
        html
    )

    # Code blocks
    html = html.replace(
        '<pre>',
        '<pre style="background:#1e1e1e;color:#d4d4d4;'
        'padding:16px 20px;border-radius:6px;overflow-x:auto;'
        'font-size:14px;line-height:1.6;margin:16px 0;'
        'font-family:\'Courier New\',Courier,monospace;">'
    )

    # HR
    html = html.replace(
        '<hr>',
        '<hr style="border:none;border-top:1px solid #e5e5e5;margin:28px 0;">'
    )

    # Tables
    html = html.replace(
        '<table>',
        '<table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:15px;">'
    )
    html = html.replace(
        '<th>',
        f'<th style="background:{p};color:#fff;padding:10px 14px;'
        f'text-align:left;font-weight:bold;border:1px solid {p};">'
    )
    html = html.replace(
        '<td>',
        '<td style="padding:9px 14px;border:1px solid #e5e5e5;color:#444;line-height:1.6;">'
    )
    html = html.replace('<tr>', '<tr style="background:#fff;">')

    # Links
    html = re.sub(
        r'<a href=(["\'][^"\']*["\'])>',
        rf'<a href=\1 style="color:{link_c};text-decoration:none;border-bottom:1px solid {link_c};">',
        html
    )

    # CTA block (top & bottom)
    cta_html = (
        '<p style="font-size:12px;font-weight:bold;color:#555;'
        'text-align:center;line-height:1.8;margin:0;">'
        '关注<span style="color:#FF6600;">养虾社</span>，'
        '一个专注于AI优质内容分享的中文社区。'
        '</p>'
    )
    cta_divider = '<hr style="border:none;border-top:1px solid #e5e5e5;margin:16px 0;">'

    # Title
    title_html = (
        f'<h1 style="font-size:22px;font-weight:bold;color:#1a1a1a;'
        f'margin:20px 0 8px;line-height:1.4;'
        f'border-bottom:2px solid {p};padding-bottom:8px;">{chinese_title}</h1>'
    )

    container_style = (
        'font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",'
        '"Helvetica Neue","Microsoft YaHei",sans-serif;'
        'max-width:677px;margin:0 auto;padding:0 20px;background:#fff;'
    )
    header_block = f'{cta_divider}{cta_html}{cta_divider}'
    footer_block = f'{cta_divider}{cta_html}{cta_divider}'
    return f'<section style="{container_style}">{header_block}{title_html}{html}{footer_block}</section>'


def format_article(translated_md: str, chinese_title: str, theme_key: str = DEFAULT_THEME) -> tuple[str, str]:
    html = md_to_wechat_html(translated_md, chinese_title, theme_key)
    clean = re.sub(r'<[^>]+>', '', translated_md)
    clean = re.sub(r'[#*`>_\[\]]+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    summary = clean[:200] + "..."
    return html, summary


def format_all_themes(translated_md: str, chinese_title: str) -> list[tuple[str, str, str]]:
    """Return [(theme_key, label, html), ...] for all themes."""
    results = []
    for key, cfg in THEMES.items():
        html, _ = format_article(translated_md, chinese_title, key)
        results.append((key, cfg["label"], html))
    return results
