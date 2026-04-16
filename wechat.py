import httpx, time, sqlite3
from pathlib import Path
from config import WECHAT_APP_ID, WECHAT_APP_SECRET, WECHAT_COVER_MEDIA_ID, BASE_DIR

TOKEN_DB = str(BASE_DIR / "wechat_token.db")

def _init_token_db():
    with sqlite3.connect(TOKEN_DB) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS token (access_token TEXT, expires_at REAL)"
        )

def get_access_token() -> str:
    _init_token_db()
    with sqlite3.connect(TOKEN_DB) as conn:
        row = conn.execute("SELECT access_token, expires_at FROM token").fetchone()
    if row and row[1] > time.time() + 600:
        return row[0]
    resp = httpx.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": WECHAT_APP_ID,
            "secret": WECHAT_APP_SECRET,
        },
        timeout=10
    )
    data = resp.json()
    if "errcode" in data or "access_token" not in data:
        raise RuntimeError(
            f"WeChat token error: errcode={data.get('errcode')} "
            f"errmsg={data.get('errmsg', 'unknown')}"
        )
    token = data["access_token"]
    expires_at = time.time() + data["expires_in"]
    with sqlite3.connect(TOKEN_DB) as conn:
        conn.execute("DELETE FROM token")
        conn.execute("INSERT INTO token VALUES (?,?)", (token, expires_at))
    return token

def create_draft(chinese_title: str, html_content: str, source_url: str = "") -> str:
    token = get_access_token()
    payload = {
        "articles": [{
            "title": chinese_title,
            "author": "AI译介",
            "content": html_content,
            "content_source_url": source_url,
            "thumb_media_id": WECHAT_COVER_MEDIA_ID,
            "need_open_comment": 0,
        }]
    }
    resp = httpx.post(
        "https://api.weixin.qq.com/cgi-bin/draft/add",
        params={"access_token": token},
        json=payload,
        timeout=15
    )
    data = resp.json()
    if "media_id" not in data:
        raise RuntimeError(f"WeChat draft API error: {data}")
    return data["media_id"]
