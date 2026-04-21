import mistune, re, subprocess, json, tempfile, os
from openai import OpenAI
from pathlib import Path
from config import DEEPSEEK_API_KEY

# mistune PINNED to 2.0.5 — do NOT upgrade. 3.x removed mistune.html()

_deepseek = None


def _get_deepseek():
    global _deepseek
    if _deepseek is None:
        _deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")
    return _deepseek


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
        # Strip markdown code fences if the model wraps the HTML
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


# ---------- Default mistune-based formatter (doocs/md-inspired) ----------

def md_to_wechat_html(md_text: str, chinese_title: str) -> str:
    # Pre-process blockquotes before mistune (mistune renders them as <blockquote>)
    processed = re.sub(r'^# .+\r?\n?', '', md_text, count=1, flags=re.MULTILINE)

    html = mistune.html(processed)

    # ---------- doocs/md-inspired inline styles ----------

    # Headings
    html = html.replace(
        '<h1>',
        '<h1 style="font-size:24px;font-weight:bold;color:#1a1a1a;'
        'margin:32px 0 16px;line-height:1.4;'
        'border-bottom:2px solid #07C160;padding-bottom:8px;">'
    )
    html = html.replace(
        '<h2>',
        '<h2 style="font-size:20px;font-weight:bold;color:#1a1a1a;'
        'margin:28px 0 12px;line-height:1.4;'
        'border-left:4px solid #07C160;padding-left:10px;">'
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
        '<strong style="color:#07C160;font-weight:bold;">'
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

    # Blockquotes — doocs/md style: left accent bar + soft background
    html = html.replace(
        '<blockquote>',
        '<blockquote style="border-left:4px solid #07C160;'
        'background:#f6fff9;margin:16px 0;padding:12px 16px;'
        'border-radius:0 4px 4px 0;">'
    )
    # Also style paragraphs inside blockquotes (already styled above, but the
    # blockquote wrapper handles the visual framing)

    # Inline code
    html = re.sub(
        r'<code>(?!</code>)',
        '<code style="background:#f0f0f0;color:#c0392b;'
        'padding:2px 6px;border-radius:3px;font-size:14px;'
        'font-family:\'Courier New\',Courier,monospace;">',
        html
    )

    # Code blocks (pre > code)
    html = html.replace(
        '<pre>',
        '<pre style="background:#1e1e1e;color:#d4d4d4;'
        'padding:16px 20px;border-radius:6px;overflow-x:auto;'
        'font-size:14px;line-height:1.6;margin:16px 0;'
        'font-family:\'Courier New\',Courier,monospace;">'
    )

    # Horizontal rule
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
        '<th style="background:#07C160;color:#fff;padding:10px 14px;'
        'text-align:left;font-weight:bold;border:1px solid #07C160;">'
    )
    html = html.replace(
        '<td>',
        '<td style="padding:9px 14px;border:1px solid #e5e5e5;color:#444;line-height:1.6;">'
    )
    html = html.replace(
        '<tr>',
        '<tr style="background:#fff;">'
    )

    # Links
    html = re.sub(
        r'<a href=(["\'][^"\']*["\'])>',
        r'<a href=\1 style="color:#07C160;text-decoration:none;border-bottom:1px solid #07C160;">',
        html
    )

    # ---------- Title block ----------
    title_html = (
        f'<h1 style="font-size:22px;font-weight:bold;color:#1a1a1a;'
        f'margin:20px 0 8px;line-height:1.4;'
        f'border-bottom:2px solid #07C160;padding-bottom:8px;">{chinese_title}</h1>'
    )

    # ---------- Footer ----------
    footer_html = (
        '<hr style="border:none;border-top:1px solid #e5e5e5;margin:36px 0 20px;">'
        '<p style="font-size:13px;color:#999;text-align:center;'
        'line-height:1.8;margin:0;">'
        'AI 译介 · 每日一篇<br>'
        '<span style="color:#ccc;">转载请注明来源</span>'
        '</p>'
    )

    # ---------- Outer container ----------
    container_style = (
        'font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",'
        '"Helvetica Neue","Microsoft YaHei",sans-serif;'
        'max-width:677px;margin:0 auto;padding:0 20px;'
        'background:#fff;'
    )
    return f'<section style="{container_style}">{title_html}{html}{footer_html}</section>'


def format_article(translated_md: str, chinese_title: str) -> tuple[str, str]:
    html = md_to_wechat_html(translated_md, chinese_title)
    clean = re.sub(r'<[^>]+>', '', translated_md)
    clean = re.sub(r'[#*`>_\[\]]+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    summary = clean[:200] + "..."
    return html, summary
