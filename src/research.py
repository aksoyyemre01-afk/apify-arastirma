"""Konu araştırması: Google News RSS (taze haberler) + evergreen konu bankası.

Apify kullanılmıyor; bu modül sadece ücretsiz Google News RSS ve
data/topics_bank.json içindeki kürasyonlu klasik vakalarla çalışır.
"""

import json
import os
from pathlib import Path
from urllib.parse import quote

import feedparser

from .utils import slugify

BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "topics_bank.json"

NEWS_LANG = os.environ.get("NEWS_LANG", "en-US")
NEWS_GL = os.environ.get("NEWS_GL", "US")

# Şirket iflası / büyük hata temalı taze haberleri yakalamak için arama terimleri.
SEED_QUERIES = [
    "company files for bankruptcy",
    "startup shuts down",
    "corporate collapse",
    "company scandal collapse",
    "failed startup layoffs shutdown",
]


def _news_lang_params():
    lang_code = NEWS_LANG.split("-")[0]
    return NEWS_LANG, NEWS_GL, f"{NEWS_GL}:{lang_code}"


def fetch_google_news(query: str, max_items: int = 8) -> list[dict]:
    hl, gl, ceid = _news_lang_params()
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append(
            {
                "title": getattr(entry, "title", "").strip(),
                "link": getattr(entry, "link", ""),
                "published": getattr(entry, "published", ""),
                "summary": getattr(entry, "summary", ""),
                "source": getattr(getattr(entry, "source", None), "title", ""),
            }
        )
    return items


def _fresh_candidates(exclude_titles_lower: set[str], max_total: int) -> list[dict]:
    candidates = []
    seen = set(exclude_titles_lower)
    for query in SEED_QUERIES:
        if len(candidates) >= max_total:
            break
        try:
            items = fetch_google_news(query)
        except Exception:
            continue
        for item in items:
            key = item["title"].strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            candidates.append(item)
            if len(candidates) >= max_total:
                break
    return candidates


def load_bank() -> list[dict]:
    return json.loads(BANK_PATH.read_text(encoding="utf-8"))


def get_topics(n: int, used_ids: set[str]) -> list[dict]:
    """n adet konu döner: önce taze haberler, sonra kullanılmamış evergreen vakalar,
    hâlâ eksikse en eski kullanılmış evergreen vakalar tekrar kullanılır."""
    if n <= 0:
        return []

    bank = load_bank()
    topics: list[dict] = []

    fresh = _fresh_candidates({t["title"].lower() for t in bank}, max_total=n)
    for item in fresh:
        topics.append(
            {
                "id": "news-" + slugify(item["title"])[:48],
                "company": item.get("source", ""),
                "title": item["title"],
                "angle": (item.get("summary") or "")[:400],
                "reference": item.get("link", ""),
                "source": "news",
            }
        )
        if len(topics) >= n:
            return topics

    unused_bank = [t for t in bank if t["id"] not in used_ids]
    for t in unused_bank:
        topics.append({**t, "reference": "", "source": "evergreen"})
        if len(topics) >= n:
            return topics

    used_ids_list = {t["id"] for t in topics}
    for t in bank:
        if t["id"] in used_ids_list:
            continue
        topics.append({**t, "reference": "", "source": "evergreen-reuse"})
        if len(topics) >= n:
            break

    return topics
