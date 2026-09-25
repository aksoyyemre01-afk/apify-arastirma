"""Kanal/seri kimliği ayarları (RULES.md kural 7).

Kanal adı, seri adı, rozet metni, renk paleti, fontlar ve intro/outro metinleri
koda gömülmez; hepsi config/brand.json'dan (ya da BRAND_CONFIG ortam
değişkenindeki dosyadan) okunur. Metin alanları boş bırakılabilir: seri adı
boşsa video rozetsiz üretilir.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config" / "brand.json"

# Dosyada eksik olan alanlar için nötr (kanala özgü olmayan) varsayılanlar.
_DEFAULTS = {
    "series_name": "",
    "badge_text": "",
    "palette": {
        "background": "#0B1020",
        "background_alt": "#18204A",
        "text": "#FFFFFF",
        "muted": "#A9B1D6",
        "accent": "#FFC61A",
        "up": "#22C55E",
        "down": "#FF3B3B",
        "card": "#FFFFFF",
        "card_text": "#0B1020",
    },
    "fonts": {"heading": "Montserrat.ttf", "body": "Inter.ttf"},
    "intro": {"enabled": True},
    "outro": {
        "enabled": True,
        "seconds": 2.6,
        "follow_text": "",
        "next_part_template": "",
        "last_part_template": "",
    },
    "audio": {"music_volume_db": -20, "sfx_volume_db": -6},
}


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            out[key] = _merge(base[key], value)
        else:
            out[key] = value
    return out


def load(path: str | Path | None = None) -> dict:
    path = Path(path or os.environ.get("BRAND_CONFIG") or DEFAULT_PATH)
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        print(f"UYARI: marka ayar dosyası bulunamadı ({path}); rozetsiz, varsayılan paletle üretilecek.")
    cfg = _merge(_DEFAULTS, data)
    cfg["series_name"] = (cfg.get("series_name") or "").strip()
    cfg["badge_text"] = (cfg.get("badge_text") or "").strip() or cfg["series_name"]
    return cfg
