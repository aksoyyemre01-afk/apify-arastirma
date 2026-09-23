"""Türkçe görsel not metnini stok medya aramasına uygun İngilizce anahtar kelimelere çevirir.

RULES.md kural 1 ve 5'i uygular: her sorgu şirket adıyla BAŞLAR (koddan garanti
edilir, Gemini'nin çıktısına bağımlı değildir) ve soyut/çok anlamlı kelimelerden
(dramatic, crisis, shutter...) İBARET olamaz - bunlar sadece somut bir nesneye
eklenen sıfat olabilir.
"""

import os
import random
import re

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

_client = None
_client_tried = False

# Tek başına sorgu OLAMAYACAK, sadece somut bir nesneye sıfat olarak eklenebilecek
# soyut/çok anlamlı kelimeler (kural 1). Üretilen sorgu, şirket adı çıkarıldıktan
# sonra SADECE bu kelimelerden oluşuyorsa (somut bir isim içermiyorsa) reddedilir.
_ABSTRACT_ONLY_WORDS = {
    "dramatic", "crisis", "shutter", "business", "corporate", "generic",
    "storm", "chaos", "emergency", "collapse", "office", "closing", "closed",
    "red", "dark", "warning", "alarm", "siren", "sad", "failure", "decline",
}

# twist (dramatik an) sahneleri için somut nesneye eklenen kriz görünümü modifiyerleri
# - "dramatic"/"crisis" gibi soyut kelimeler TEK BAŞINA değil, üretilen somut ifadenin
# SONUNA sıfat olarak eklenir (ör. "Kodak camera factory sign" + "red warning tone").
_CRISIS_LOOK_MODIFIERS = [
    "red tone warning",
    "dark dramatic lighting",
    "cracked broken damaged",
    "red alarm glow",
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


def _is_abstract_only(phrase: str) -> bool:
    """phrase (company çıkarılmış hali) sadece _ABSTRACT_ONLY_WORDS kümesindeki
    kelimelerden mi oluşuyor - yani hiç somut bir isim içermiyor mu?"""
    words = re.findall(r"[a-zA-Z]+", phrase.lower())
    if not words:
        return True
    return all(w in _ABSTRACT_ONLY_WORDS for w in words)


def to_search_query(note: str, company: str = "", context: str = "", dramatic: bool = False) -> str:
    """Görsel notu (ör. '2000'lerden gerçek Blockbuster mağaza görüntüleri') stok medya
    aramasına uygun, şirket adıyla BAŞLAYAN, somut/gösterilebilir bir sahne tarif eden
    İngilizce sorguya çevirir.

    - company (ör. 'Nokia') sorgunun HER ZAMAN en başında yer alır (kural 5) - Gemini
      metninde tekrar geçse de geçmese de koddan garanti edilir.
    - Üretilen ifade soyut kelimelerden ibaretse (somut bir isim içermiyorsa, ör. sadece
      "crisis" ya da "dramatic red") kural 1 gereği reddedilir ve somut bir yedeğe düşülür.
    - dramatic=True ise (twist/kriz sahnesi) soyut kriz kelimeleri değil, somut nesneye
      eklenen bir "görünüm" modifiyeri (ör. "cracked broken damaged") eklenir."""
    company = (company or "").strip()

    phrase = _generate(note, company, context, dramatic)
    if not phrase or _is_abstract_only(_strip_company(phrase, company)):
        phrase = _fallback(company, context, dramatic)

    if dramatic:
        phrase = f"{phrase} {random.choice(_CRISIS_LOOK_MODIFIERS)}"

    # Kural 5: sorgu HER ZAMAN şirket adıyla başlar (deterministik, Gemini'ye bağımlı değil).
    if company:
        phrase = _strip_company(phrase, company)
        return f"{company} {phrase}".strip()
    return phrase.strip()


def _strip_company(phrase: str, company: str) -> str:
    """phrase içinde company zaten geçiyorsa (Gemini kendisi eklemiş olabilir) onu
    çıkarır, böylece to_search_query şirket adını başa eklediğinde tekrar etmez."""
    if not company:
        return phrase
    pattern = re.compile(re.escape(company), re.IGNORECASE)
    return pattern.sub("", phrase).strip()


def _generate(note: str, company: str, context: str, dramatic: bool) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        instruction = (
            "Aşağıdaki video sahne açıklamasını, stok görsel/video sitesinde (Pexels/Pixabay) "
            "arama yapmak için 4-6 kelimelik, SOMUT VE GÖSTERİLEBİLİR bir İngilizce arama "
            "sorgusuna çevir. Sorgu bir fotoğrafçının gerçekten çekebileceği somut bir nesne/"
            "sahne tarif etmeli (ör. 'eski bir Nokia telefonu', 'kapanan bir mağaza vitrini') - "
            "sadece bir DUYGU/RUH HALİ (ör. 'kriz', 'dramatik') tarif etmemeli.\n\n"
        )
        if company:
            instruction += f"İlgili şirket/konu: {company}\n"
        if context:
            instruction += f"Konu özeti: {context}\n"
        instruction += (
            "\nKurallar:\n"
            "- Sorgu MUTLAKA somut bir ana isim (nesne/yer/ürün) içermeli - bu şirketin "
            "sektörünü/ürününü somut olarak belirten bir isim olmalı (ör. şirket bir telefon "
            "üreticisiyse 'mobile phone'/'cellphone', bir hava yolu ise 'airplane', bir banka "
            "ise 'bank building', bir perakende zinciriyse 'retail store'). Şirket eski bir "
            "döneme aitse 'vintage'/'retro'/'old' gibi dönem belirteçleri ekle.\n"
            "- 'dramatic', 'crisis', 'business', 'corporate' gibi SOYUT/duygu kelimelerini "
            "ASLA tek başına ya da sorgunun ana unsuru olarak kullanma - sadece somut bir "
            "isme eklenen bir sıfat olabilirler (ör. 'dramatic office' DEĞİL, 'broken "
            "smartphone screen' gibi somut bir nesnenin hasarlı/kırık hali).\n"
            "- Genel/jenerik iş dünyası klişeleri KULLANMA (ör. 'business handshake', "
            "'corporate office', 'people shaking hands', 'generic factory', 'product "
            "closeup') - bunlar konuyla alakasız görsellere yol açıyor.\n"
            "- Türkçe'den birebir çevrildiğinde İngilizce'de ÇOK ANLAMLI/BELİRSİZ olan "
            "kelimelerden kaçın (ör. 'kepenk' -> 'shutter' YAZMA; 'shutter' hem kamera "
            "obtüratörü hem rastgele bir dükkan/istasyon kepenği anlamına gelir ve şirketle "
            "hiç alakasız bir görsel getirebilir). Bunun yerine sahneyi somut ve tek anlamlı "
            "şekilde tarif et (ör. 'kapanan kepenk' yerine 'abandoned closed factory "
            "building dusk' gibi, kelimenin kendisini değil SAHNEYİ çevir).\n"
            "- En az 2 spesifik/somut tanımlayıcıyı bir arada kullan ki arama sonucu yanlış "
            "bağlama kaymasın.\n"
        )
        if dramatic:
            instruction += (
                "- Bu sahne senaryonun EN DRAMATİK/kriz anı: yine somut bir nesne/sahne "
                "tarif et ama onu hasarlı/kırık/kırmızı ışıklı bir görünümde tarif et "
                "(ör. 'broken smartphone screen red light', 'closed store dark red sign') - "
                "'crisis'/'dramatic' kelimelerini kullanma, görünümü somut nesne üzerinden "
                "anlat.\n"
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


def _fallback(company: str, context: str, dramatic: bool) -> str:
    """Gemini kullanılamadığında (ya da ürettiği ifade soyut çıktığında) somut,
    şirkete çapalı bir yedek üretir. 'crisis'/'product closeup' gibi soyut/belirsiz
    yedekler KULLANILMAZ (kural 1) - her zaman somut, evrensel olarak var olan bir
    kavram (logo/tabela/bina) kullanılır."""
    base = company if company else "company"
    if dramatic:
        return f"{base} logo sign red warning"
    return f"{base} logo sign building"
