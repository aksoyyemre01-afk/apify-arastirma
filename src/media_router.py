"""Sahne başına görsel kaynağını RULES.md kural 15'teki önceliğe göre seçer:

Rakam/karşılaştırma İÇEREN sahneler için önce üretilen grafikler denenir (bir stok
sitesinde "120 milyar dolar" araması yapmak anlamsızdır - bu tür içeriğin en doğru
temsili kodla üretilen bir kart/grafiktir). Diğer tüm sahneler için sıra:

    1) Wikimedia Commons (gerçek logo/kurucu/genel merkez/ürün görseli, lisanslı)
    2) Wayback Machine (marka-çapa sahnesi ya da "web sitesi" geçen notlar için -
       şirketin geçmiş bir yıldaki web sitesi ekran görüntüsü)
    3) Pexels/Pixabay (sadece genel/jenerik sahneler için son çare)

Hiçbiri bulunamazsa None döner - video_builder.py bu durumda placeholder sahne
kullanır. Her sonuç, hangi kaynaktan geldiğini belirten bir "source" alanı taşır
(RULES.md kural 21 - doğrulama çıktısı bunu konsola yazdırır).
"""

import re
from pathlib import Path

from . import graphics, stock_media, wayback, wikimedia

_WEBSITE_HINTS = re.compile(
    r"web ?sitesi|website|ana ?sayfa|homepage|tarayıcı|browser", re.IGNORECASE
)


def _looks_like_website_note(note: str) -> bool:
    return bool(_WEBSITE_HINTS.search(note))


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
) -> dict | None:
    """Bulunursa {"path": Path, "kind": "photo"|"video", "source": str} döner,
    hiçbir kaynaktan uygun bir şey bulunamazsa None döner."""

    stat = graphics.extract_stat(note)
    if stat:
        number_text, label_text = stat
        path = graphics.render_stat_card(number_text, label_text, dest_dir, index, dramatic=dramatic)
        return {"path": path, "kind": "photo", "source": f"üretilen grafik (rakam kartı: {number_text})"}

    comparison = graphics.extract_comparison(note)
    if comparison:
        left, right = comparison
        left_logo = wikimedia.fetch(f"{left} logo", dest_dir, index * 1000)
        right_logo = wikimedia.fetch(f"{right} logo", dest_dir, index * 1000 + 1)
        path = graphics.render_comparison_card(
            left, right, dest_dir, index,
            left_logo=left_logo["path"] if left_logo else None,
            right_logo=right_logo["path"] if right_logo else None,
        )
        return {"path": path, "kind": "photo", "source": f"üretilen grafik (karşılaştırma: {left} vs {right})"}

    wiki = wikimedia.fetch(query, dest_dir, index)
    if wiki:
        return {"path": wiki["path"], "kind": "photo", "source": f"Wikimedia Commons ({wiki['license']})"}

    if is_brand_anchor or _looks_like_website_note(note):
        wb = wayback.fetch(company, dest_dir, index)
        if wb:
            return {"path": wb["path"], "kind": "photo", "source": f"Wayback Machine ({wb['snapshot_url']})"}

    clip = stock_media.fetch_clip(
        query, note, dest_dir, index, exclude_kind=exclude_kind, company=company, used_urls=used_urls
    )
    if clip:
        return {"path": clip["path"], "kind": clip["kind"], "source": "Pexels/Pixabay (son çare)"}

    return None
