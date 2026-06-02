"""
youtube_extractor – multi‑strategy YouTube subtitle fetcher
"""

import json
import re
import logging
import requests
from xml.etree import ElementTree
from typing import Optional

logger = logging.getLogger(__name__)

def _load_video_page(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "Chrome/124.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=12)
    resp.raise_for_status()
    return resp.text

def _fetch_via_youtube_data_api(video_id: str, api_key: str) -> Optional[str]:
    from googleapiclient.discovery import build
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        resp = youtube.captions().list(part="snippet", videoId=video_id).execute()
        items = resp.get("items", [])
        if not items: return None
        en_item = next((i for i in items if i["snippet"]["language"] == "en"), items[0])
        caption_id = en_item["id"]
        caps = youtube.captions().download(id=caption_id, tfmt="ttml").execute()
        root = ElementTree.fromstring(caps)
        texts = [e.text for e in root.iter() if e.text]
        return " ".join(texts).strip()
    except Exception as exc:
        logger.debug("YouTube Data API failed: %s", exc)
        return None

def _fetch_via_unsigned_html(video_id: str) -> Optional[str]:
    try:
        html = _load_video_page(video_id)
        match = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?});", html)
        if not match: return None
        data = json.loads(match.group(1))
        tracks = data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
        if not tracks: return None
        track = next((t for t in tracks if t.get("languageCode") == "en"), tracks[0])
        base_url = track.get("baseUrl")
        if not base_url or "signature=" in base_url or "expire=" in base_url: return None
        xml_resp = requests.get(base_url, timeout=10)
        xml_resp.raise_for_status()
        root = ElementTree.fromstring(xml_resp.text)
        texts = [node.text for node in root.iter("text") if node.text]
        return " ".join(texts).strip()
    except Exception as exc:
        logger.debug("Unsigned HTML fetch failed: %s", exc)
        return None

def _fetch_via_pytube(video_id: str) -> Optional[str]:
    try:
        from pytube import YouTube
        yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
        caption = yt.captions.get_by_language_code("en") or list(yt.captions)[0]
        if not caption: return None
        xml = caption.xml_captions
        root = ElementTree.fromstring(xml)
        texts = [node.text for node in root.iter("text") if node.text]
        return " ".join(texts).strip()
    except Exception as exc:
        logger.debug("pytube fetch failed: %s", exc)
        return None

def _fallback_metadata(video_id: str) -> Optional[str]:
    try:
        html = _load_video_page(video_id)
        title_match = re.search(r"<title>(.+?)</title>", html)
        title = title_match.group(1).replace(" - YouTube", "").strip() if title_match else ""
        desc_match = re.search(r'"shortDescription":"([^"]+)"', html)
        description = desc_match.group(1).replace("\\n", "\n").replace("\\\"", "\"") if desc_match else ""
        if not (title or description): return None
        return f"**{title}**\n\n{description}"
    except Exception as exc:
        logger.debug("Metadata fallback failed: %s", exc)
        return None

def fetch_youtube_transcript(video_url: str, youtube_api_key: str | None = None) -> str:
    video_id = video_url.split("watch?v=")[-1].split("&")[0] if "watch?v=" in video_url else video_url.split("/")[-1]
    if youtube_api_key:
        txt = _fetch_via_youtube_data_api(video_id, youtube_api_key)
        if txt: return txt
    txt = _fetch_via_unsigned_html(video_id)
    if txt: return txt
    txt = _fetch_via_pytube(video_id)
    if txt: return txt
    txt = _fallback_metadata(video_id)
    if txt: return txt
    return "❌ Unable to retrieve subtitles or metadata for this video."
