"""Marka logosu çözümleme (RULES.md kural 1/2: gerçek logolar, her zaman düzgün zeminde).

Sıra:
1) assets/logos/<slug>.(svg|png|webp|jpg) - elle konan dosya her zaman önceliklidir
   (yanlış/eski logo gelirse doğrusunu buraya koymak yeterli).
2) Wikidata'nın resmi "logo image" özelliği (P154) - markanın güncel, resmi logosu,
   çoğunlukla vektörel SVG. İndirilen dosya assets/logos/ altına önbelleğe alınır.
3) Commons'ta "<marka> logo" SVG araması.
Bulunamazsa None döner; video logonun yerine markanın adını düzgün bir yazı
logosu (wordmark) olarak çizer - bozuk/kırpılmış logo asla gösterilmez.
"""

import json
from pathlib import Path
from urllib.parse import quote

import requests

from .utils import slugify

LOGO_DIR = Path(__file__).resolve().parent.parent / "assets" / "logos"
_EXTS = ("svg", "png", "webp", "jpg", "jpeg")
_TIMEOUT = 20
# Wikimedia User-Agent politikası proje adı + iletişim kanalı (repo URL'si) ister.
_HEADERS = {
    "User-Agent": "short-video-automation/2.0 (https://github.com/aksoyyemre01-afk/apify-arastirma)"
}
# Aynı marka için ağa tekrar gitmemek adına "bulunamadı" sonuçları da saklanır.
_MISS_FILE = LOGO_DIR / "_not_found.json"


def _key(name: str) -> str:
    """Karşılaştırma anahtarı: 'Yahoo!' == 'yahoo', 'Eastman Kodak' != 'Kodak'."""
    return slugify(name).replace("-", "")


def _cached(slug: str) -> Path | None:
    for ext in _EXTS:
        p = LOGO_DIR / f"{slug}.{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def _get_json(url: str, params: dict) -> dict | None:
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"      [Logo] istek başarısız ({url}): {e}")
        return None


def _wikidata_logo_filename(brand: str) -> str | None:
    data = _get_json(
        "https://www.wikidata.org/w/api.php",
        {"action": "wbsearchentities", "search": brand, "language": "en", "type": "item",
         "limit": 7, "format": "json"},
    )
    # Yalnızca etiketi/takma adı marka adıyla birebir eşleşen sonuçlar: rastgele bir
    # kelimenin ("Rakip" gibi) alakasız bir şirketin logosunu getirmesini önler.
    key = _key(brand)
    ids = [
        item["id"] for item in (data or {}).get("search", [])
        if _key((item.get("match") or {}).get("text", "")) == key or _key(item.get("label", "")) == key
    ]
    if not ids:
        return None
    ents = _get_json(
        "https://www.wikidata.org/w/api.php",
        {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims", "format": "json"},
    )
    entities = (ents or {}).get("entities", {})
    # wbsearchentities alaka sırasını korur; P154'ü olan ilk sonuç seçilir. Birden
    # fazla logo varsa güncel olan: "preferred" rank > bitiş tarihi (P582) olmayan >
    # en yeni başlangıç tarihi (P580) > listede en sonda olan.
    for qid in ids:
        claims = entities.get(qid, {}).get("claims", {}).get("P154", [])
        candidates = []
        for i, claim in enumerate(claims):
            if claim.get("rank") == "deprecated":
                continue
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if not value:
                continue
            quals = claim.get("qualifiers", {})
            start = ""
            for q in quals.get("P580", []):
                start = (q.get("datavalue", {}).get("value", {}) or {}).get("time", "") or start
            candidates.append((claim.get("rank") == "preferred", "P582" not in quals, start, i, value))
        if candidates:
            return max(candidates)[-1]
    return None


def _commons_logo_filename(brand: str) -> str | None:
    data = _get_json(
        "https://commons.wikimedia.org/w/api.php",
        {"action": "query", "list": "search", "srsearch": f"{brand} logo filetype:drawing",
         "srnamespace": 6, "srlimit": 5, "format": "json"},
    )
    key = _key(brand)
    for hit in (data or {}).get("query", {}).get("search", []):
        title = hit.get("title", "").removeprefix("File:")
        # Dosya adı markayı ve "logo"yu içermeli (ör. "Nokia 2023 logo.svg").
        if key and key in _key(title) and "logo" in title.lower():
            return title
    return None


def _download(filename: str, slug: str) -> Path | None:
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + quote(filename.replace(" ", "_"))
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in _EXTS:
        # Raster olmayan/tanınmayan biçimler için Commons'tan PNG küçük resmi iste.
        url += "?width=1000"
        ext = "png"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"      [Logo] indirme başarısız ({url}): {e}")
        return None
    if not resp.content:
        return None
    dest = LOGO_DIR / f"{slug}.{ext}"
    dest.write_bytes(resp.content)
    return dest


def _load_misses() -> set[str]:
    try:
        return set(json.loads(_MISS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def resolve(brand: str, offline: bool = False) -> Path | None:
    """brand için yerel logo dosyası yolunu döner (gerekirse indirir), yoksa None."""
    brand = (brand or "").strip()
    if not brand:
        return None
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(brand)
    cached = _cached(slug)
    if cached or offline:
        return cached
    misses = _load_misses()
    if slug in misses:
        return None

    filename = _wikidata_logo_filename(brand) or _commons_logo_filename(brand)
    path = _download(filename, slug) if filename else None
    if path:
        print(f"      [Logo] {brand}: {filename}")
    else:
        print(f"      [Logo] {brand}: logo bulunamadı, yazı logosu kullanılacak "
              f"(elle eklemek için assets/logos/{slug}.svg|png)")
        misses.add(slug)
        _MISS_FILE.write_text(json.dumps(sorted(misses), indent=2), encoding="utf-8")
    return path
