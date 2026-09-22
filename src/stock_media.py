"""Pexels / Pixabay'den görsel/video klip arama ve indirme.

En az bir API anahtarı (PEXELS_API_KEY veya PIXABAY_API_KEY) tanımlıysa kullanılır.
Her kaynaktan (çözünürlüğe göre sıralı) birden fazla aday toplanır; her aday
indirilip src/relevance.py ile konuyla gerçekten alakalı mı diye kontrol edilir -
ilk alakalı bulunan kullanılır, değilse reddedilip bir sonraki adaya/kaynağa geçilir.
`exclude_kind` verilirse (önceki sahneyle aynı tür olmasın diye), o türün önceliği
düşürülür - yine de başka kaynak bulunamazsa aynı tür kullanılabilir.
"""

import os
from pathlib import Path

import requests

from . import relevance

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")

_TIMEOUT = 15
_PER_PAGE = 6
_MIN_VIDEO_WIDTH = 480
_MAX_CANDIDATES_PER_SOURCE = 3


def _download(url: str, dest: Path) -> Path:
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                f.write(chunk)
    return dest


def _pexels_video_candidates(query: str) -> list[str]:
    """Her sonucun en yüksek çözünürlüklü dosya varyantını alır, sonuçları
    çözünürlüğe göre azalan sırada döner."""
    if not PEXELS_API_KEY:
        return []
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return []
    videos = resp.json().get("videos") or []

    candidates = []
    for video in videos:
        best_url, best_area = None, -1
        for f in video.get("video_files", []):
            width, height = f.get("width") or 0, f.get("height") or 0
            if width < _MIN_VIDEO_WIDTH:
                continue
            area = width * height
            if area > best_area:
                best_area, best_url = area, f.get("link")
        if best_url:
            candidates.append((best_area, best_url))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return [url for _, url in candidates]


def _pexels_photo_candidates(query: str) -> list[str]:
    if not PEXELS_API_KEY:
        return []
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return []
    photos = resp.json().get("photos") or []
    photos.sort(key=lambda p: (p.get("width") or 0) * (p.get("height") or 0), reverse=True)

    urls = []
    for photo in photos:
        src = photo.get("src", {})
        url = src.get("original") or src.get("large2x") or src.get("portrait")
        if url:
            urls.append(url)
    return urls


def _pixabay_video_candidates(query: str) -> list[str]:
    if not PIXABAY_API_KEY:
        return []
    resp = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": PIXABAY_API_KEY, "q": query, "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return []
    hits = resp.json().get("hits") or []

    candidates = []
    for hit in hits:
        best_url, best_area = None, -1
        for size in ("large", "medium", "small", "tiny"):
            variant = hit.get("videos", {}).get(size)
            if not variant:
                continue
            area = (variant.get("width") or 0) * (variant.get("height") or 0)
            if area > best_area:
                best_area, best_url = area, variant.get("url")
        if best_url:
            candidates.append((best_area, best_url))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return [url for _, url in candidates]


def _pixabay_photo_candidates(query: str) -> list[str]:
    if not PIXABAY_API_KEY:
        return []
    resp = requests.get(
        "https://pixabay.com/api/",
        params={"key": PIXABAY_API_KEY, "q": query, "image_type": "photo", "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return []
    hits = resp.json().get("hits") or []
    hits.sort(key=lambda h: (h.get("imageWidth") or 0) * (h.get("imageHeight") or 0), reverse=True)
    return [
        h.get("largeImageURL") or h.get("webformatURL")
        for h in hits
        if h.get("largeImageURL") or h.get("webformatURL")
    ]


_VIDEO_FIRST = [
    (_pexels_video_candidates, "video", "mp4"),
    (_pexels_photo_candidates, "photo", "jpg"),
    (_pixabay_video_candidates, "video", "mp4"),
    (_pixabay_photo_candidates, "photo", "jpg"),
]
_PHOTO_FIRST = [
    (_pexels_photo_candidates, "photo", "jpg"),
    (_pixabay_photo_candidates, "photo", "jpg"),
    (_pexels_video_candidates, "video", "mp4"),
    (_pixabay_video_candidates, "video", "mp4"),
]


def fetch_clip(
    query: str, note: str, dest_dir: Path, index: int, exclude_kind: str | None = None
) -> dict | None:
    """query için klip arar. Her kaynaktan en fazla `_MAX_CANDIDATES_PER_SOURCE` aday
    indirilip relevance.is_relevant() ile kontrol edilir; ilk alakalı bulunan kullanılır,
    reddedilenler diskten silinir. exclude_kind ("video"/"photo") verilirse önceki
    sahneyle aynı türden olmasın diye o türün denenme sırası sona atılır.

    Bulunursa {"path": Path, "kind": "video"|"photo"} döner, hiçbiri bulunamaz/alakalı
    çıkmazsa None (çağıran taraf bu durumda bir placeholder sahne üretmeli)."""
    attempts = _PHOTO_FIRST if exclude_kind == "video" else _VIDEO_FIRST

    for finder, kind, ext in attempts:
        try:
            candidates = finder(query)
        except requests.RequestException:
            continue

        for candidate_url in candidates[:_MAX_CANDIDATES_PER_SOURCE]:
            dest = dest_dir / f"src_{index:02d}_{kind}.{ext}"
            try:
                _download(candidate_url, dest)
            except requests.RequestException:
                continue
            if relevance.is_relevant(dest, kind, query, note):
                return {"path": dest, "kind": kind}
            dest.unlink(missing_ok=True)
    return None
