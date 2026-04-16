import httpx
from urllib.parse import quote
from config import BARK_KEY, PUSHPLUS_TOKEN

def send_bark(title: str, body: str, url: str = "https://mp.weixin.qq.com") -> bool:
    if not BARK_KEY:
        return False
    try:
        resp = httpx.get(
            f"https://api.day.app/{BARK_KEY}/{quote(title)}/{quote(body)}",
            params={"url": url, "group": "公众号", "sound": "minuet"},
            timeout=10
        )
        ok = resp.json().get("code") == 200
        print(f"[notifier] Bark: {'OK' if ok else resp.text}")
        return ok
    except Exception as e:
        print(f"[notifier] Bark failed: {e}")
        return False

def send_pushplus(title: str, content: str) -> bool:
    if not PUSHPLUS_TOKEN:
        return False
    try:
        resp = httpx.post(
            "http://www.pushplus.plus/send",
            json={"token": PUSHPLUS_TOKEN, "title": title,
                  "content": content, "template": "html"},
            timeout=10
        )
        ok = resp.json().get("code") == 200
        print(f"[notifier] PushPlus: {'OK' if ok else resp.text}")
        return ok
    except Exception as e:
        print(f"[notifier] PushPlus failed: {e}")
        return False

def notify_review_ready(chinese_title: str, summary: str) -> bool:
    body = summary[:100] + " — 点击前往草稿箱发布"
    sent = send_bark("公众号草稿 | " + chinese_title[:20], body)
    if not sent:
        content = (
            "<h3>📰 今日公众号文章已就绪</h3>"
            "<p><strong>" + chinese_title + "</strong></p>"
            "<p>" + summary + "</p>"
            '<p>✅ 请前往 <a href="https://mp.weixin.qq.com">公众号后台</a> 草稿箱发布</p>'
        )
        sent = send_pushplus("公众号草稿 | " + chinese_title[:20], content)
    return sent
