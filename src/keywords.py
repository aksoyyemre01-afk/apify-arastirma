"""Türkçe görsel not metnini stok medya aramasına uygun İngilizce anahtar kelimelere çevirir."""

import os

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

_client = None
_client_tried = False


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


def to_search_query(note: str, company: str = "") -> str:
    """Görsel notu (ör. '2000'lerden gerçek Blockbuster mağaza görüntüleri') stok medya
    aramasına uygun kısa bir İngilizce sorguya (ör. 'video store retro 2000s') çevirir.
    Gemini kullanılamazsa basit bir yedek sorgu döner."""
    client = _get_client()
    if client is not None:
        try:
            prompt = (
                "Aşağıdaki video sahne açıklamasını, stok görsel/video sitesinde (Pexels/Pixabay) "
                "arama yapmak için 2-4 kelimelik SADE bir İngilizce arama sorgusuna çevir. "
                "Sadece anahtar kelimeleri yaz, başka hiçbir açıklama, tırnak veya noktalama ekleme.\n\n"
                f"Sahne: {note}"
            )
            response = client.models.generate_content(model=MODEL, contents=prompt)
            text = (response.text or "").strip().strip('"').strip()
            if text:
                return text
        except Exception:
            pass

    fallback = (company or "").strip()
    return f"{fallback} corporate office".strip() if fallback else "business office city"
