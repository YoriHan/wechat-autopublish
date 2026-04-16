"""
Auto-generate WeChat article cover images.
Tries providers in order: Gemini → OpenAI DALL-E → skip (use static cover).
Requires at least one of: GEMINI_API_KEY or OPENAI_API_KEY in .env
"""
import os
import httpx
import tempfile
from pathlib import Path
from config import BASE_DIR

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def _build_prompt(title: str, summary: str) -> str:
    return (
        f"Professional tech article cover image for Chinese WeChat blog. "
        f"Topic: {title[:80]}. "
        "Style: clean, modern, minimalist. Abstract geometric or circuit patterns. "
        "Color: dark blue or dark purple background with bright accent colors. "
        "No text, no people, no logos. Wide format 900x500."
    )

def _generate_with_gemini(prompt: str) -> bytes | None:
    """Use Gemini Imagen API to generate cover image."""
    try:
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict",
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={
                "instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
            },
            timeout=60,
        )
        data = resp.json()
        if "predictions" in data and data["predictions"]:
            import base64
            b64 = data["predictions"][0].get("bytesBase64Encoded", "")
            if b64:
                return base64.b64decode(b64)
    except Exception as e:
        print(f"[image_gen] Gemini failed: {e}")
    return None

def _generate_with_openai(prompt: str) -> bytes | None:
    """Use OpenAI DALL-E 3 to generate cover image."""
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1792x1024",
                "quality": "standard",
                "response_format": "url",
            },
            timeout=60,
        )
        data = resp.json()
        image_url = data["data"][0]["url"]
        img_resp = httpx.get(image_url, timeout=30)
        return img_resp.content
    except Exception as e:
        print(f"[image_gen] OpenAI failed: {e}")
    return None

def generate_cover(title: str, summary: str) -> str | None:
    """
    Generate a cover image for the article.
    Returns local file path, or None if no image provider is configured.
    """
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        print("[image_gen] No image API key set — using static cover")
        return None

    prompt = _build_prompt(title, summary)
    image_bytes = None

    if GEMINI_API_KEY:
        print("[image_gen] Generating cover with Gemini...")
        image_bytes = _generate_with_gemini(prompt)

    if image_bytes is None and OPENAI_API_KEY:
        print("[image_gen] Generating cover with DALL-E...")
        image_bytes = _generate_with_openai(prompt)

    if image_bytes is None:
        print("[image_gen] Image generation failed — using static cover")
        return None

    # Save to temp file
    cover_path = str(BASE_DIR / "cover_latest.jpg")
    with open(cover_path, "wb") as f:
        f.write(image_bytes)
    print(f"[image_gen] Cover saved: {cover_path} ({len(image_bytes)//1024}KB)")
    return cover_path
