"""Türkçe görsel not metnini stok medya aramasına uygun İngilizce anahtar kelimelere çevirir."""

import os
import random

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

_client = None
_client_tried = False

# twist (dramatik an) sahneleri için, Gemini'nin ürettiği sorguya eklenen garanti modifiyerler
# - Gemini kullanılamasa/başarısız olsa bile dramatik görsel arama etkisi korunur.
DRAMATIC_MODIFIERS = [
    "dramatic red alarm crisis",
    "dark storm collapse chaos",
    "red warning light emergency",
    "crisis red siren dramatic",
]


def _get_client():
    global _client, _client_tried
    if _client_tried:
        return _client
    _client_tried = True
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai

    _client = genai.Client(api_key=api_key)
    return _client


def to_search_query(note: str, company: str = "", context: str = "", dramatic: bool = False) -> str:
    """Görsel notu (ör. '2000'lerden gerçek Blockbuster mağaza görüntüleri') stok medya
    aramasına uygun, spesifik/somut ve sinematik bir İngilizce sorguya çevirir.

    company (ör. 'Nokia') ve context (konunun tek cümlelik özeti) modele güçlü bir
    konu çapası verir - bu sayede jenerik/ilgisiz görseller yerine (ör. rastgele
    tokalaşma, alakasız fabrika) konuyla gerçekten ilgili terimler üretilir. company
    sonuç sorgusunda mutlaka geçer (Gemini es geçse bile koddan garanti edilir).

    dramatic=True ise (twist/kriz sahnesi) sonuca kırmızı/kriz temalı modifiyerler
    eklenir. Gemini kullanılamazsa basit ama yine de company'ye çapalı bir yedek
    sorgu döner."""
    company = (company or "").strip()
    query = _generate(note, company, context, dramatic) or _fallback(company, dramatic)

    if company and company.lower() not in query.lower():
        query = f"{company} {query}"
    if dramatic:
        query = f"{query} {random.choice(DRAMATIC_MODIFIERS)}"
    return query


def _generate(note: str, company: str, context: str, dramatic: bool) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        instruction = (
            "Aşağıdaki video sahne açıklamasını, stok görsel/video sitesinde (Pexels/Pixabay) "
            "arama yapmak için 4-6 kelimelik SPESİFİK ve SOMUT bir İngilizce arama sorgusuna "
            "çevir.\n\n"
        )
        if company:
            instruction += f"İlgili şirket/konu: {company}\n"
        if context:
            instruction += f"Konu özeti: {context}\n"
        instruction += (
            "\nKurallar:\n"
            "- Sorgu MUTLAKA bu şirketin sektörünü/ürününü somut olarak belirtmeli "
            "(ör. şirket bir telefon üreticisiyse 'mobile phone'/'cellphone', bir hava "
            "yolu ise 'airplane', bir banka ise 'bank building', bir perakende zinciriyse "
            "'retail store'). Şirket eski bir döneme aitse 'vintage'/'retro'/'old' gibi "
            "dönem belirteçleri ekle.\n"
            "- Genel/jenerik iş dünyası klişeleri KULLANMA (ör. 'business handshake', "
            "'corporate office', 'people shaking hands', 'generic factory') - bunlar "
            "konuyla alakasız görsellere yol açıyor.\n"
            "- Genel kelimeler yerine somut, görsel olarak çarpıcı tanımlayıcılar kullan.\n"
        )
        if dramatic:
            instruction += (
                "- Bu sahne senaryonun EN DRAMATİK/kriz anı: kırmızı tonlar, alarm, çöküş, "
                "kaos hissi veren spesifik görsel öğeler ekle (yine şirketin ürünü/sektörüyle "
                "ilişkili olarak, ör. 'broken smartphone screen red light' gibi).\n"
            )
        instruction += (
            "- Sadece anahtar kelimeleri yaz, başka açıklama, tırnak veya noktalama ekleme.\n\n"
            f"Sahne: {note}"
        )
        response = client.models.generate_content(model=MODEL, contents=instruction)
        text = (response.text or "").strip().strip('"').strip()
        return text or None
    except Exception:
        return None


def _fallback(company: str, dramatic: bool) -> str:
    base = company if company else "business"
    if dramatic:
        return f"{base} crisis"
    return f"{base} product closeup"
