"""Wikimedia Commons API ile şirket logosu, kurucu fotoğrafı, genel merkez binası
gibi gerçek/markalı görselleri arar ve indirir (RULES.md kural 15 - görsel kaynak
önceliği a maddesi). API anahtarı gerekmez, herkese açık bir API'dir.

Bulunan her görselin lisans bilgisi (extmetadata) çağıran tarafa döndürülür ve
script'in "media_log"una kaydedilmesi beklenir (bkz. video_builder.py).
"""

from pathlib import Path

import requests

_TIMEOUT = 15
_API_URL = "https://commons.wikimedia.org/w/api.php"
_MIN_WIDTH = 300

# Wikimedia'nın User-Agent politikası (meta.wikimedia.org/wiki/User-Agent_policy)
# hem proje adını HEM DE bir iletişim kanalı (URL/e-posta) ister; ikisi de
# eksikse istekler oran sınırlamasına takılabilir/engellenebilir. İletişim
# kanalı olarak repo URL'si kullanılıyor - kullanıcının kişisel bilgisi
# (e-posta vb.) rızası olmadan üçüncü bir servise gönderilmiyor.
_USER_AGENT = (
    "business-stories-automation/1.0 "
    "(https://github.com/aksoyyemre01-afk/apify-arastirma)"
)
_HEADERS = {"User-Agent": _USER_AGENT}


def search(query: str) -> list[dict]:
    """query için Wikimedia Commons'ta dosya arar. Her sonuç için
    {'url':, 'width':, 'height':, 'license':, 'artist':, 'title':} döner
    (çözünürlüğe göre azalan sırada)."""
    try:
        resp = requests.get(
            _API_URL,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"filetype:bitmap {query}",
                "gsrnamespace": 6,  # File: ad alanı
                "gsrlimit": 8,
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata|mime",
                "format": "json",
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if resp.status_code != 200:
        return []

    pages = (resp.json().get("query") or {}).get("pages") or {}
    results = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime", "")
        if not mime.startswith("image/") or mime == "image/svg+xml":
            continue  # SVG'yi atla, ffmpeg doğrudan işleyemez
        width = info.get("width") or 0
        if width < _MIN_WIDTH:
            continue
        extmeta = info.get("extmetadata") or {}
        results.append(
            {
                "url": info.get("url"),
                "width": width,
                "height": info.get("height") or 0,
                "license": (extmeta.get("LicenseShortName") or {}).get("value", "bilinmiyor"),
                "artist": (extmeta.get("Artist") or {}).get("value", ""),
                "title": page.get("title", ""),
            }
        )
    results.sort(key=lambda r: r["width"], reverse=True)
    return results


def fetch(query: str, dest_dir: Path, index: int) -> dict | None:
    """query için en iyi Commons sonucunu indirir.
    Bulunursa {'path': Path, 'kind': 'photo', 'license': str, 'title': str} döner,
    bulunamazsa None (çağıran taraf bir sonraki kaynağa geçmeli)."""
    results = search(query)
    for result in results:
        url = result["url"]
        if not url:
            continue
        ext = url.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        dest = dest_dir / f"wikimedia_{index:02d}.{ext}"
        try:
            resp = requests.get(url, headers=_HEADERS, stream=True, timeout=30)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        except requests.RequestException:
            continue
        return {
            "path": dest,
            "kind": "photo",
            "license": result["license"],
            "title": result["title"],
        }
    return None
