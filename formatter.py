import mistune, re

# mistune PINNED to 2.0.5 — do NOT upgrade. 3.x removed mistune.html()

def md_to_wechat_html(md_text: str, chinese_title: str) -> str:
    processed = re.sub(
        r'^> (.+)$',
        r'<div style="border-left:4px solid #07C160;padding:8px 12px;'
        r'background:#f0faf4;margin:12px 0;color:#555;font-size:14px;">\1</div>',
        md_text,
        flags=re.MULTILINE
    )
    processed = re.sub(r'^# .+\r?\n?', '', processed, count=1, flags=re.MULTILINE)

    html = mistune.html(processed)

    replacements = [
        ('<h2>', '<h2 style="font-size:20px;font-weight:bold;color:#1a1a1a;margin:24px 0 12px;border-bottom:2px solid #07C160;padding-bottom:6px;">'),
        ('<h3>', '<h3 style="font-size:17px;font-weight:bold;color:#333;margin:20px 0 8px;">'),
        ('<p>', '<p style="font-size:16px;line-height:1.8;color:#333;margin:12px 0;">'),
        ('<strong>', '<strong style="color:#07C160;font-weight:bold;">'),
        ('<ul>', '<ul style="padding-left:20px;margin:12px 0;">'),
        ('<ol>', '<ol style="padding-left:20px;margin:12px 0;">'),
        ('<li>', '<li style="font-size:15px;line-height:1.8;color:#444;margin:4px 0;">'),
        ('<hr>', '<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">'),
    ]
    for old, new in replacements:
        html = html.replace(old, new)

    title_html = (
        f'<h1 style="font-size:22px;font-weight:bold;color:#1a1a1a;'
        f'margin:20px 0 8px;line-height:1.4;">{chinese_title}</h1>'
    )
    footer_html = (
        '<hr style="border:none;border-top:1px solid #eee;margin:32px 0;">'
        '<p style="font-size:13px;color:#999;text-align:center;line-height:1.6;">'
        'AI 译介 · 每日一篇<br>转载请注明来源</p>'
    )
    container_style = (
        'font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;'
        'max-width:677px;margin:0 auto;padding:0 16px;'
    )
    return f'<section style="{container_style}">{title_html}{html}{footer_html}</section>'

def format_article(translated_md: str, chinese_title: str) -> tuple[str, str]:
    html = md_to_wechat_html(translated_md, chinese_title)
    clean = re.sub(r'<[^>]+>', '', translated_md)
    clean = re.sub(r'[#*`>_\[\]]+', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    summary = clean[:200] + "..."
    return html, summary
