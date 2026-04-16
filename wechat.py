"""WeChat API client — powered by wechatpy SDK (auto token management)."""
import httpx
from pathlib import Path
from wechatpy import WeChatClient
from config import WECHAT_APP_ID, WECHAT_APP_SECRET, WECHAT_COVER_MEDIA_ID, BASE_DIR

# wechatpy handles token fetch + refresh automatically (60s buffer before expiry)
_client: WeChatClient | None = None

def get_client() -> WeChatClient:
    global _client
    if _client is None:
        _client = WeChatClient(WECHAT_APP_ID, WECHAT_APP_SECRET)
    return _client

def upload_image(image_path: str) -> str:
    """Upload a local image file to WeChat permanent materials. Returns media_id."""
    client = get_client()
    with open(image_path, "rb") as f:
        result = client.media.upload("image", f)
    return result["media_id"]

def create_draft(chinese_title: str, html_content: str,
                 source_url: str = "", cover_media_id: str = "") -> str:
    """Create a WeChat draft (草稿箱). Returns draft media_id."""
    client = get_client()
    thumb_id = cover_media_id or WECHAT_COVER_MEDIA_ID
    result = client.draft.add([{
        "title": chinese_title,
        "author": "AI译介",
        "digest": "",          # pipeline.py fills this in
        "content": html_content,
        "content_source_url": source_url,
        "thumb_media_id": thumb_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }])
    if "media_id" not in result:
        raise RuntimeError(f"WeChat draft API error: {result}")
    return result["media_id"]
