"""Pexels / Pixabay'den görsel/video klip arama ve indirme.

En az bir API anahtarı (PEXELS_API_KEY veya PIXABAY_API_KEY) tanımlıysa kullanılır.
Sırayla denenir: Pexels video -> Pexels foto -> Pixabay video -> Pixabay foto.
"""

import os
from pathlib import Path

import requests

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")

_TIMEOUT = 15


def _download(url: str, dest: Path) -> Path:
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                f.write(chunk)
    return dest


def _pexels_video(query: str) -> str | None:
    if not PEXELS_API_KEY:
        return None
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 3},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    videos = resp.json().get("videos") or []
    for video in videos:
        files = sorted(
            (f for f in video.get("video_files", []) if f.get("width")),
            key=lambda f: abs((f.get("width") or 0) - 1080),
        )
        if files:
            return files[0]["link"]
    return None


def _pexels_photo(query: str) -> str | None:
    if not PEXELS_API_KEY:
        return None
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 3},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    photos = resp.json().get("photos") or []
    if not photos:
        return None
    src = photos[0]["src"]
    return src.get("portrait") or src.get("large2x") or src.get("original")


def _pixabay_video(query: str) -> str | None:
    if not PIXABAY_API_KEY:
        return None
    resp = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": PIXABAY_API_KEY, "q": query, "per_page": 3},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    hits = resp.json().get("hits") or []
    if not hits:
        return None
    videos = hits[0].get("videos", {})
    for size in ("large", "medium", "small", "tiny"):
        if size in videos:
            return videos[size]["url"]
    return None


def _pixabay_photo(query: str) -> str | None:
    if not PIXABAY_API_KEY:
        return None
    resp = requests.get(
        "https://pixabay.com/api/",
        params={"key": PIXABAY_API_KEY, "q": query, "image_type": "photo", "per_page": 3},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    hits = resp.json().get("hits") or []
    if not hits:
        return None
    return hits[0].get("largeImageURL") or hits[0].get("webformatURL")


def fetch_clip(query: str, dest_dir: Path, index: int) -> dict | None:
    """query için Pexels video -> Pexels foto -> Pixabay video -> Pixabay foto sırayla denenir.

    Bulunursa {"path": Path, "kind": "video"|"photo"} döner, hiçbiri bulunamazsa None
    (çağıran taraf bu durumda bir placeholder sahne üretmeli)."""
    attempts = [
        (_pexels_video, "video", "mp4"),
        (_pexels_photo, "photo", "jpg"),
        (_pixabay_video, "video", "mp4"),
        (_pixabay_photo, "photo", "jpg"),
    ]
    for finder, kind, ext in attempts:
        try:
            url = finder(query)
        except requests.RequestException:
            continue
        if not url:
            continue
        dest = dest_dir / f"src_{index:02d}.{ext}"
        try:
            _download(url, dest)
        except requests.RequestException:
            continue
        return {"path": dest, "kind": kind}
    return None
