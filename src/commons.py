"""Uzun video için Wikimedia Commons'tan lisanslı arşiv fotoğrafı.

- Yanlış kişinin/kurumun fotoğrafı gelmesin diye görsel, Wikidata'da etiketi ya da takma adı
  konu adıyla BİREBİR eşleşen öğenin resmi görselinden (P18) alınır; serbest arama yapılmaz.
- Yalnızca serbest lisanslar kabul edilir: CC0, kamu malı (PD), CC BY, CC BY-SA. NC/ND,
  "fair use" ve lisansı belirsiz dosyalar reddedilir.
- Eser adı, yazar, lisans ve kaynak linki saklanır; video açıklamasına eklenir (atıf).
- Sonuç assets/photos/ altında önbelleğe alınır; ücretsizdir, API anahtarı gerektirmez.
"""

import json
import re
from pathlib import Path

import requests

from .logos import _HEADERS, _key
from .utils import slugify

ROOT = Path(__file__).resolve().parent.parent
PHOTO_DIR = ROOT / "assets" / "photos"
_TIMEOUT = 20
_ALLOWED = re.compile(r"^(cc0|public domain|pd\b|pd-|cc[- ]by(-sa)?[- ]\d|cc[- ]by(-sa)?$)", re.IGNORECASE)
_FORBIDDEN = re.compile(r"\b(nc|nd|non-?commercial|no ?deriv|fair use)\b", re.IGNORECASE)


def _get(url: str, params: dict) -> dict | None:
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"      [Foto] istek başarısız: {e}")
        return None


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def license_ok(short_name: str) -> bool:
    name = (short_name or "").strip()
    return bool(name) and bool(_ALLOWED.search(name)) and not _FORBIDDEN.search(name)


def _wikidata_image(subject: str) -> str | None:
    data = _get("https://www.wikidata.org/w/api.php",
                {"action": "wbsearchentities", "search": subject, "language": "en", "type": "item",
                 "limit": 7, "format": "json"})
    key = _key(subject)
    ids = [it["id"] for it in (data or {}).get("search", [])
           if _key((it.get("match") or {}).get("text", "")) == key or _key(it.get("label", "")) == key]
    if not ids:
        return None
    ents = _get("https://www.wikidata.org/w/api.php",
                {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims", "format": "json"})
    for qid in ids:
        for claim in (ents or {}).get("entities", {}).get(qid, {}).get("claims", {}).get("P18", []):
            if claim.get("rank") == "deprecated":
                continue
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if value:
                return value
    return None


def _imageinfo(filename: str) -> dict | None:
    data = _get("https://commons.wikimedia.org/w/api.php",
                {"action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
                 "iiprop": "url|extmetadata", "iiurlwidth": 1920, "format": "json"})
    pages = (data or {}).get("query", {}).get("pages", {})
    for page in pages.values():
        for info in page.get("imageinfo", []):
            return info
    return None


def resolve(subject: str, offline: bool = False) -> dict | None:
    """{'name','path','file','artist','license','license_url','source_url'} ya da None."""
    slug = slugify(subject)
    meta_path = PHOTO_DIR / f"{slug}.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("path") and (ROOT / meta["path"]).exists():
            return {**meta, "path": ROOT / meta["path"]}
        if meta.get("missing"):
            return None
    if offline:
        return None
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    filename = _wikidata_image(subject)
    info = _imageinfo(filename) if filename else None
    ext = (info or {}).get("extmetadata", {})
    lic = _strip_html(ext.get("LicenseShortName", {}).get("value", ""))
    if not info or not license_ok(lic):
        reason = "Wikidata'da görsel yok" if not filename else f"lisans uygun değil ({lic or 'belirsiz'})"
        print(f"      [Foto] {subject}: {reason}; fotoğraf kullanılmayacak.")
        meta_path.write_text(json.dumps({"missing": True, "reason": reason}, ensure_ascii=False), encoding="utf-8")
        return None
    url = info.get("thumburl") or info.get("url")
    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"      [Foto] {subject}: indirilemedi ({e})")
        return None
    suffix = Path(url.split("?")[0]).suffix.lower() or ".jpg"
    path = PHOTO_DIR / f"{slug}{suffix if suffix in ('.jpg', '.jpeg', '.png', '.webp') else '.jpg'}"
    path.write_bytes(r.content)
    meta = {
        "name": subject, "path": str(path.relative_to(ROOT)), "file": filename,
        "artist": _strip_html(ext.get("Artist", {}).get("value", "")) or "bilinmiyor",
        "license": lic, "license_url": ext.get("LicenseUrl", {}).get("value", ""),
        "source_url": info.get("descriptionurl", ""),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"      [Foto] {subject}: {filename} ({lic}, {meta['artist']})")
    return {**meta, "path": path}


def credit_line(meta: dict) -> str:
    """Açıklama için atıf satırı."""
    lic = meta["license"] + (f" ({meta['license_url']})" if meta.get("license_url") else "")
    return f"{meta['name']}: \"{meta['file']}\" - {meta['artist']}, {lic}, {meta['source_url']}"
