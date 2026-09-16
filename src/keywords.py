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


def to_search_query(note: str, company: str = "", dramatic: bool = False) -> str:
    """Görsel notu (ör. '2000'lerden gerçek Blockbuster mağaza görüntüleri') stok medya
    aramasına uygun, spesifik ve sinematik bir İngilizce sorguya çevirir.
    dramatic=True ise (twist/kriz sahnesi) sonuca kırmızı/kriz temalı modifiyerler eklenir.
    Gemini kullanılamazsa basit bir yedek sorgu döner (yine de dramatic ise modifiye edilir)."""
    client = _get_client()
    if client is not None:
        try:
            instruction = (
                "Aşağıdaki video sahne açıklamasını, stok görsel/video sitesinde (Pexels/Pixabay) "
                "arama yapmak için 4-6 kelimelik SPESİFİK ve SİNEMATİK bir İngilizce arama sorgusuna "
                "çevir. Genel kelimeler yerine somut, görsel olarak çarpıcı tanımlayıcılar kullan "
                "(ör. 'office' yerine 'empty corporate office dramatic lighting'). "
            )
            if dramatic:
                instruction += (
                    "Bu sahne senaryonun EN DRAMATİK/kriz anı: kırmızı tonlar, alarm, çöküş, kaos "
                    "hissi veren spesifik görsel öğeler ekle. "
                )
            instruction += (
                "Sadece anahtar kelimeleri yaz, başka açıklama, tırnak veya noktalama ekleme.\n\n"
                f"Sahne: {note}"
            )
            response = client.models.generate_content(model=MODEL, contents=instruction)
            text = (response.text or "").strip().strip('"').strip()
            if text:
                if dramatic:
                    text = f"{text} {random.choice(DRAMATIC_MODIFIERS)}"
                return text
        except Exception:
            pass

    fallback = (company or "").strip() or "business"
    query = f"{fallback} corporate office cinematic"
    if dramatic:
        query = f"{query} {random.choice(DRAMATIC_MODIFIERS)}"
    return query
