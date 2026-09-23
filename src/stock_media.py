"""Pexels / Pixabay'den görsel/video klip arama ve indirme.

En az bir API anahtarı (PEXELS_API_KEY veya PIXABAY_API_KEY) tanımlıysa kullanılır.
Her kaynaktan (çözünürlüğe göre sıralı) birden fazla aday toplanır. RULES.md kural 6
ve 7'yi uygular:
- Kural 6 (alaka doğrulama, 2 aşamalı): önce ucuz bir etiket/keyword ön filtresi
  (stok sitesinin kendi alt-text/tags metniyle sorgu arasında ortak somut kelime var
  mı) - yoksa indirilmeden elenir; sonra (varsa) src/relevance.py ile Gemini vision
  kontrolü.
- Kural 7 (çeşitlilik): `used_urls` setine geçilen URL'ler bir daha kullanılmaz;
  `exclude_kind` art arda aynı medya türünü (foto/video) engeller.
"""

import os
import re
from pathlib import Path

import requests

from . import relevance

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")

_TIMEOUT = 15
_PER_PAGE = 6
_MIN_VIDEO_WIDTH = 480
_MAX_CANDIDATES_PER_SOURCE = 3

# relevance kelime-eşleşme kontrolünde göz ardı edilecek jenerik kelimeler
_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "and", "or", "with", "for",
    "red", "dark", "old", "vintage", "retro", "closeup", "sign", "building",
    "warning", "tone", "lighting", "dramatic", "glow", "cracked", "broken",
    "damaged", "logo",
}


def _download(url: str, dest: Path) -> Path:
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                f.write(chunk)
    return dest


def _pexels_video_candidates(query: str) -> list[tuple[str, str]]:
    """(url, metadata_text) çiftleri döner - Pexels video API'sinde alt-text/tags
    standart olarak gelmediği için metadata_text genelde boş kalır (ön filtre bu
    durumda devre dışı kalır, Gemini vision kontrolüne bırakılır)."""
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
            metadata = str(video.get("user", {}).get("name", ""))
            candidates.append((best_area, best_url, metadata))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return [(url, meta) for _, url, meta in candidates]


def _pexels_photo_candidates(query: str) -> list[tuple[str, str]]:
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

    results = []
    for photo in photos:
        src = photo.get("src", {})
        url = src.get("original") or src.get("large2x") or src.get("portrait")
        if url:
            results.append((url, str(photo.get("alt", ""))))
    return results


def _pixabay_video_candidates(query: str) -> list[tuple[str, str]]:
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
            candidates.append((best_area, best_url, str(hit.get("tags", ""))))
    candidates.sort(key=lambda c: c[0], reverse=True)
    return [(url, meta) for _, url, meta in candidates]


def _pixabay_photo_candidates(query: str) -> list[tuple[str, str]]:
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
    results = []
    for h in hits:
        url = h.get("largeImageURL") or h.get("webformatURL")
        if url:
            results.append((url, str(h.get("tags", ""))))
    return results


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


def _keywords_of(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _keyword_overlap_ok(query: str, company: str, metadata: str) -> bool:
    """Ucuz ön filtre (kural 6, aşama 1): stok sitesinin kendi etiket/açıklama
    metniyle (metadata) sorgu arasında en az bir somut ortak kelime (ya da şirket
    adı) var mı? metadata boşsa (site bu bilgiyi vermiyorsa) karar verilemez,
    filtre devre dışı kalır (True döner - Gemini vision'a bırakılır)."""
    if not metadata.strip():
        return True

    meta_words = _keywords_of(metadata)
    if not meta_words:
        return True

    if company and company.lower() in metadata.lower():
        return True

    query_words = _keywords_of(query) - _keywords_of(company)
    return bool(query_words & meta_words)


def fetch_clip(
    query: str,
    note: str,
    dest_dir: Path,
    index: int,
    exclude_kind: str | None = None,
    company: str = "",
    used_urls: set[str] | None = None,
) -> dict | None:
    """query için klip arar. Her kaynaktan en fazla `_MAX_CANDIDATES_PER_SOURCE` aday
    toplanır; her aday önce ucuz etiket/keyword ön filtresinden (kural 6/1), sonra
    (indirildikten sonra) relevance.is_relevant() Gemini vision kontrolünden geçer.
    used_urls verilirse (kural 7), o sete zaten eklenmiş URL'ler atlanır ve kabul
    edilen URL sete eklenir - aynı videoda aynı görsel tekrar kullanılmaz.
    exclude_kind ("video"/"photo") verilirse önceki sahneyle aynı türden olmasın diye
    o türün denenme sırası sona atılır.

    Bulunursa {"path": Path, "kind": "video"|"photo"} döner, hiçbiri bulunamaz/alakalı
    çıkmazsa None (çağıran taraf bu durumda bir placeholder sahne üretmeli)."""
    attempts = _PHOTO_FIRST if exclude_kind == "video" else _VIDEO_FIRST
    used_urls = used_urls if used_urls is not None else set()

    for finder, kind, ext in attempts:
        try:
            candidates = finder(query)
        except requests.RequestException:
            continue

        tried = 0
        for candidate_url, metadata in candidates:
            if candidate_url in used_urls:
                continue
            if not _keyword_overlap_ok(query, company, metadata):
                continue
            if tried >= _MAX_CANDIDATES_PER_SOURCE:
                break
            tried += 1

            dest = dest_dir / f"src_{index:02d}_{kind}_{tried}.{ext}"
            try:
                _download(candidate_url, dest)
            except requests.RequestException:
                continue
            if relevance.is_relevant(dest, kind, query, note, company=company):
                used_urls.add(candidate_url)
                return {"path": dest, "kind": kind}
            dest.unlink(missing_ok=True)
    return None
