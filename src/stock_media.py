"""Pexels / Pixabay'den görsel/video klip arama ve indirme.

En az bir API anahtarı (PEXELS_API_KEY veya PIXABAY_API_KEY) tanımlıysa kullanılır.
Her arama, birden fazla sonuç arasından en yüksek çözünürlüklü dosyayı seçer.
`exclude_kind` verilirse (önceki sahneyle aynı tür olmasın diye), o türün önceliği
düşürülür - yine de başka kaynak bulunamazsa aynı tür kullanılabilir.
"""

import os
from pathlib import Path

import requests

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")

_TIMEOUT = 15
_PER_PAGE = 6
_MIN_VIDEO_WIDTH = 480


def _download(url: str, dest: Path) -> Path:
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                f.write(chunk)
    return dest


def _pexels_video(query: str) -> str | None:
    """Sonuç kümesindeki TÜM videoların TÜM dosya varyantları arasından en yüksek
    çözünürlüklü (width*height) olanı seçer."""
    if not PEXELS_API_KEY:
        return None
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    videos = resp.json().get("videos") or []

    best_url = None
    best_area = -1
    for video in videos:
        for f in video.get("video_files", []):
            width, height = f.get("width") or 0, f.get("height") or 0
            if width < _MIN_VIDEO_WIDTH:
                continue
            area = width * height
            if area > best_area:
                best_area = area
                best_url = f.get("link")
    return best_url


def _pexels_photo(query: str) -> str | None:
    """Dönen fotoğraflar arasından (orijinal boyutlarına göre) en yüksek çözünürlüklü
    olanı seçer, ardından o fotoğrafın en büyük kaynak URL'sini döner."""
    if not PEXELS_API_KEY:
        return None
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    photos = resp.json().get("photos") or []
    if not photos:
        return None

    best = max(photos, key=lambda p: (p.get("width") or 0) * (p.get("height") or 0))
    src = best.get("src", {})
    return src.get("original") or src.get("large2x") or src.get("portrait")


def _pixabay_video(query: str) -> str | None:
    if not PIXABAY_API_KEY:
        return None
    resp = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": PIXABAY_API_KEY, "q": query, "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    hits = resp.json().get("hits") or []

    best_url = None
    best_area = -1
    for hit in hits:
        for size in ("large", "medium", "small", "tiny"):
            variant = hit.get("videos", {}).get(size)
            if not variant:
                continue
            area = (variant.get("width") or 0) * (variant.get("height") or 0)
            if area > best_area:
                best_area = area
                best_url = variant.get("url")
    return best_url


def _pixabay_photo(query: str) -> str | None:
    if not PIXABAY_API_KEY:
        return None
    resp = requests.get(
        "https://pixabay.com/api/",
        params={"key": PIXABAY_API_KEY, "q": query, "image_type": "photo", "per_page": _PER_PAGE},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    hits = resp.json().get("hits") or []
    if not hits:
        return None

    best = max(hits, key=lambda h: (h.get("imageWidth") or 0) * (h.get("imageHeight") or 0))
    return best.get("largeImageURL") or best.get("webformatURL")


_VIDEO_FIRST = [
    (_pexels_video, "video", "mp4"),
    (_pexels_photo, "photo", "jpg"),
    (_pixabay_video, "video", "mp4"),
    (_pixabay_photo, "photo", "jpg"),
]
_PHOTO_FIRST = [
    (_pexels_photo, "photo", "jpg"),
    (_pixabay_photo, "photo", "jpg"),
    (_pexels_video, "video", "mp4"),
    (_pixabay_video, "video", "mp4"),
]


def fetch_clip(query: str, dest_dir: Path, index: int, exclude_kind: str | None = None) -> dict | None:
    """query için klip arar. exclude_kind ("video"/"photo") verilirse -bir önceki sahneyle
    aynı türden olmasın diye- o türün denenme sırası sona atılır (görsel çeşitliliği için);
    yine de başka hiçbir kaynak yoksa aynı tür kullanılır (video bulunamamasındansa yeğdir).

    Bulunursa {"path": Path, "kind": "video"|"photo"} döner, hiçbiri bulunamazsa None
    (çağıran taraf bu durumda bir placeholder sahne üretmeli)."""
    attempts = _PHOTO_FIRST if exclude_kind == "video" else _VIDEO_FIRST

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
