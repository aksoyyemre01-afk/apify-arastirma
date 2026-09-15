"""Gemini API ile YouTube Shorts / uzun video senaryosu üretimi."""

import os

from google import genai
from google.genai import types

from .schemas import LongScript, ShortScript

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
LANGUAGE = os.environ.get("CONTENT_LANGUAGE", "tr")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY tanımlı değil (.env dosyasını kontrol et)")
        _client = genai.Client(api_key=api_key)
    return _client


SHORT_PROMPT = """Sen viral iş dünyası içerikleri yazan deneyimli bir YouTube Shorts senaristisin.

Aşağıdaki gerçek şirket olayı hakkında 30-45 saniyelik (yaklaşık 85-105 kelimelik seslendirme metni) bir Shorts senaryosu yaz.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
Ek kaynak (varsa): {reference}

Kurallar:
- Seslendirme metni {language} dilinde, akıcı ve konuşma diline uygun olsun.
- İlk cümle (hook) izleyiciyi ilk 3 saniyede durdurmalı; bir şok edici gerçek, soru veya çelişki içersin.
- Anlatım; kuruluş/yükseliş -> kritik hata/an -> sonuç -> kısa ders akışını izlesin.
- Abartılı reklam dili kullanma, somut sayı ve gerçek olaylara dayan.
- visual_notes alanına 4-6 kısa sahne/görsel yönlendirmesi yaz (ör. "Nokia logosu eski reklamlarla açılıyor").
- cta alanına izleyiciyi takip etmeye/yorum yapmaya teşvik eden tek cümlelik bir kapanış yaz.
- hashtags alanına 5-8 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme."""


LONG_PROMPT = """Sen derinlemesine iş dünyası analiz videoları yazan deneyimli bir YouTube senaristisin.

Aşağıdaki gerçek şirket olayı hakkında yaklaşık 5 dakikalık (toplam 680-780 kelimelik seslendirme metni) bir video senaryosu yaz.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
Ek kaynak (varsa): {reference}

Kurallar:
- Seslendirme metni {language} dilinde, akıcı, belgesel/analiz tonunda olsun.
- Video 4-5 bölümden (chapters) oluşsun: örn. "Giriş / Zirve", "İlk Uyarı Sinyalleri", "Kritik Hata", "Çöküş", "Alınacak Dersler".
- hook alanı ilk 15 saniyede izleyiciyi bağlayacak, merak uyandıran bir açılış olsun.
- Anlatım somut tarih, rakam ve gerçek olaylara dayansın, abartılı reklam dilinden kaçın.
- Son bölüm mutlaka izleyicinin çıkaracağı 2-3 somut dersi içersin.
- cta alanına izleyiciyi abone olmaya/yorum yapmaya teşvik eden bir kapanış cümlesi yaz.
- hashtags alanına 6-10 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme."""


def _format(prompt: str, topic: dict) -> str:
    return prompt.format(
        title=topic.get("title", ""),
        company=topic.get("company", ""),
        angle=topic.get("angle", ""),
        reference=topic.get("reference", ""),
        language=LANGUAGE,
    )


def write_short_script(topic: dict) -> ShortScript:
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=_format(SHORT_PROMPT, topic),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ShortScript,
        ),
    )
    return ShortScript.model_validate_json(response.text)


def write_long_script(topic: dict) -> LongScript:
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=_format(LONG_PROMPT, topic),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LongScript,
        ),
    )
    return LongScript.model_validate_json(response.text)
