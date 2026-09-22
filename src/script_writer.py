"""Gemini API ile YouTube Shorts / uzun video senaryosu üretimi."""

import os

from google import genai
from google.genai import types

from .schemas import LongScript, ShortScript

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
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


NARRATION_STYLE_RULES = """Seslendirme metni yazım kuralları (TTS doğallığı için - ÖNEMLİ):
- Türkçe'de yazılışı/okunuşu birbirine çok yakın ama anlamı ve doğru okunuşu farklı olan
  kelimelerden (ör. "kar" (kış yağışı) / "kâr" (kazanç), "adet" (sayı/tane) / "âdet"
  (gelenek)) kaçın. Bu tür kelimeleri kullanman gerekiyorsa MUTLAKA doğru aksan işaretiyle
  yaz (â, î, û) - TTS motoru düz "kar" yazılan bir kelimeyi her zaman "kış yağışı" olarak
  okur. Mümkünse aksan gerektirmeyen bir eş anlamlısını tercih et (ör. "kârlı" yerine
  "kazançlı"/"gelir getiren").
- Cümleler KISA ve konuşma diline yakın olsun; TTS'in yanlış vurgulayacağı, nefes alacak
  yer bırakmayan uzun/iç içe geçmiş, çok sayıda bağlaçla uzayan cümlelerden kaçın.
- Art arda gelen benzer/zor ünsüz kümeleri, nadir kullanılan kelimeler ve gereksiz
  yabancı/teknik terimlerden kaçın - bunlar TTS'te doğal akmıyor, robotik/yapay duyuluyor.
- Metni, bir insan sunucunun rahatça tek nefeste söyleyebileceği şekilde yaz; yazı dili
  resmiyetinden çok, doğal ve akıcı konuşma dili kullan."""


SHORT_PROMPT = """Sen viral iş dünyası içerikleri yazan deneyimli bir YouTube Shorts senaristisin.

Aşağıdaki gerçek şirket olayı hakkında 30-45 saniyelik bir Shorts senaryosu yaz.
Senaryo TAM OLARAK 3 net bölümden oluşmalı: hook, setup, twist.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
Ek kaynak (varsa): {reference}

Bölüm kuralları:
- **hook** (0-3 saniye, ~10-18 kelime): İzleyiciyi ilk saniyede durduracak şok edici bir
  gerçek, soru veya çelişki. visual_notes'a TEK güçlü bir açılış sahnesi yaz.
- **setup** (~14-20 saniye, ~35-50 kelime): Şirketin kuruluşu/zirvesi/gücü - neden bu kadar
  büyük/güvenilir/başarılıydı. visual_notes'a 2 sahne yaz.
- **twist** (~12-18 saniye, ~30-45 kelime): Senaryonun EN DRAMATİK anı - kritik hata, çöküş
  veya kriz. visual_notes'a 2 sahne yaz ve bu sahneleri MUTLAKA dramatik, yüksek kontrastlı,
  kriz hissi veren somut görsellerle tarif et (ör. "kırmızı alarm ışıkları yanan bir ofis",
  "kapanan mağaza kepenkleri", "aşağı düşen kırmızı bir grafik çizgisi", "enkaz/terk edilmiş bina").

Genel kurallar:
- Tüm seslendirme metinleri {language} dilinde, akıcı ve konuşma diline uygun olsun.
- Somut sayı ve gerçek olaylara dayan, abartılı reklam dilinden kaçın.
- Her visual_notes maddesi somut ve görsel olarak spesifik olsun (ör. "ofis" yerine
  "boş, karanlık bir kurumsal ofis, kapalı jaluziler").
- cta alanına izleyiciyi takip etmeye/yorum yapmaya teşvik eden tek cümlelik bir kapanış yaz
  (bu metin seslendirilmeyecek, sadece ekranda görünecek).
- hashtags alanına 5-8 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme.

{narration_style_rules}"""


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
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme.

{narration_style_rules}"""


def _format(prompt: str, topic: dict) -> str:
    return prompt.format(
        title=topic.get("title", ""),
        company=topic.get("company", ""),
        angle=topic.get("angle", ""),
        reference=topic.get("reference", ""),
        language=LANGUAGE,
        narration_style_rules=NARRATION_STYLE_RULES,
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
