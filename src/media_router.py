"""Sahne başına görsel kaynağını RULES.md kural 15'teki önceliğe göre seçer:

Marka-çapa sahnesi (is_brand_anchor) HER ZAMAN kendi şirketinin logosunu gösterir
(başka hiçbir kaynak denenmez). Diğer sahnelerde, rakam/karşılaştırma/başka bir
marka İÇEREN sahneler için önce üretilen grafikler/logolar denenir (bir stok
sitesinde "120 milyar dolar" araması yapmak anlamsızdır). Kalan sahneler için sıra:

    1) Wikimedia Commons (gerçek logo/kurucu/genel merkez/ürün görseli, lisanslı)
    2) Wayback Machine (marka-çapa sahnesi ya da "web sitesi" geçen notlar için -
       şirketin geçmiş bir yıldaki web sitesi ekran görüntüsü)
    3) Pexels/Pixabay (sadece genel/jenerik sahneler için son çare)

Hiçbiri bulunamazsa None döner - video_builder.py bu durumda önce son çare marka
logosu, o da olmazsa bir metin kartı dener (asla tamamen kopuk bir stok görsel
kullanılmaz - kural 24). Her sonuç, hangi kaynaktan geldiğini belirten bir
"source" alanı taşır (kural 21 - doğrulama çıktısı bunu konsola yazdırır).
"""

import re
from pathlib import Path

from . import graphics, keywords, stock_media, wayback, wikimedia

_WEBSITE_HINTS = re.compile(
    r"web ?sitesi|website|ana ?sayfa|homepage|tarayıcı|browser", re.IGNORECASE
)


def _looks_like_website_note(note: str) -> bool:
    return bool(_WEBSITE_HINTS.search(note))


def _fetch_logo_scene(brand: str, dest_dir: Path, index: int, used_urls: set[str] | None) -> dict | None:
    """brand için Wikimedia'dan logo bulup düz zemine kompoze eder (kural 22 -
    şeffaf logoların ffmpeg'de siyah zemine dönüşmesini önlemek için)."""
    wiki = wikimedia.fetch(f"{brand} logo", dest_dir, index, exclude_urls=used_urls)
    if not wiki:
        return None
    if used_urls is not None:
        used_urls.add(wiki["url"])
    composed = graphics.compose_logo_on_background(wiki["path"], dest_dir, index)
    return {"path": composed, "kind": "logo", "source": f"Wikimedia Commons logo ({wiki['license']})"}


def resolve_scene(
    note: str,
    query: str,
    company: str,
    dest_dir: Path,
    index: int,
    exclude_kind: str | None = None,
    used_urls: set[str] | None = None,
    dramatic: bool = False,
    is_brand_anchor: bool = False,
    beat_narration: str = "",
    allow_generated_card: bool = True,
    used_stats: set[str] | None = None,
) -> dict | None:
    """Bulunursa {"path": Path, "kind": "photo"|"video"|"logo", "source": str} döner,
    hiçbir kaynaktan uygun bir şey bulunamazsa None döner.

    allow_generated_card=False verilirse (kural 23 - aynı notun tempo sınırı için
    bölünmüş bir sonraki alt-kesimi), stat/comparison/diğer-marka tespiti atlanır -
    aksi halde AYNI kart art arda birden fazla alt-kesimde tekrar üretilip ekranda
    olması gerekenden çok daha uzun süre kalmış gibi görünür."""

    if is_brand_anchor:
        logo = _fetch_logo_scene(company, dest_dir, index, used_urls)
        if logo:
            return logo
        # Wikimedia'da bile logo bulunamadıysa normal akışa (Wayback/Pexels) düş.

    if allow_generated_card and not is_brand_anchor:
        stat = graphics.extract_stat(note) or graphics.extract_stat(beat_narration)
        # Aynı rakam, aynı bölümün birden fazla sahnesinde (not kendi başına
        # bulamayıp beat_narration'a düştüğünde) tekrar kart olarak üretilmesin
        # diye (kural 23'ün bir başka boyutu) used_stats ile dedup edilir.
        if stat and (used_stats is None or stat not in used_stats):
            if used_stats is not None:
                used_stats.add(stat)
            label = keywords.clean_stat_label(note or beat_narration, stat)
            path = graphics.render_stat_card(stat, label, dest_dir, index, dramatic=dramatic)
            return {"path": path, "kind": "photo", "source": f"üretilen grafik (rakam kartı: {stat} / {label})"}

        comparison = graphics.extract_comparison(note) or graphics.extract_comparison(beat_narration)
        if not comparison:
            other_brands = keywords.detect_other_brands(note, beat_narration, company)
            if len(other_brands) == 2:
                comparison = (other_brands[0], other_brands[1])
            elif len(other_brands) == 1:
                logo = _fetch_logo_scene(other_brands[0], dest_dir, index, used_urls)
                if logo:
                    return logo

        if comparison:
            left, right = comparison
            left_logo = wikimedia.fetch(f"{left} logo", dest_dir, index * 1000, exclude_urls=used_urls)
            if left_logo and used_urls is not None:
                used_urls.add(left_logo["url"])
            right_logo = wikimedia.fetch(f"{right} logo", dest_dir, index * 1000 + 1, exclude_urls=used_urls)
            if right_logo and used_urls is not None:
                used_urls.add(right_logo["url"])
            path = graphics.render_comparison_card(
                left, right, dest_dir, index,
                left_logo=left_logo["path"] if left_logo else None,
                right_logo=right_logo["path"] if right_logo else None,
            )
            return {"path": path, "kind": "photo", "source": f"üretilen grafik (karşılaştırma: {left} vs {right})"}

    wiki = wikimedia.fetch(query, dest_dir, index, exclude_urls=used_urls)
    if wiki:
        if used_urls is not None:
            used_urls.add(wiki["url"])
        return {"path": wiki["path"], "kind": "photo", "source": f"Wikimedia Commons ({wiki['license']})"}

    if is_brand_anchor or _looks_like_website_note(note):
        wb = wayback.fetch(company, dest_dir, index, exclude_urls=used_urls)
        if wb:
            if used_urls is not None:
                used_urls.add(wb["snapshot_url"])
            return {"path": wb["path"], "kind": "photo", "source": f"Wayback Machine ({wb['snapshot_url']})"}

    clip = stock_media.fetch_clip(
        query, note, dest_dir, index, exclude_kind=exclude_kind, company=company, used_urls=used_urls
    )
    if clip:
        return {"path": clip["path"], "kind": clip["kind"], "source": "Pexels/Pixabay (son çare)"}

    return None
