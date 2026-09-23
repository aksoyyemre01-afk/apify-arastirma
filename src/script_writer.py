"""Gemini API ile YouTube Shorts / uzun video senaryosu üretimi.

RULES.md kural 3, 4, 8, 9, 13'ü uygular: visual_notes narration ile AYNI
Gemini çağrısında (aynı ShortBeat objesi içinde) üretilir; hook/trend uyumlu
hızlı açılış istenir; her short cliffhanger ile kapanır; haftalık 3+1 seri
akışı için write_weekly_part_script()/write_weekly_recap_script() vardır.
"""

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


VISUAL_SYNC_RULES = """Görsel not kuralları (RULES.md kural 1, 3, 4 - ÖNEMLİ):
- Her visual_notes maddesi, AYNI bölümün narration'ında o cümlede anlatılan SOMUT
  olayı/nesneyi birebir betimlemeli (ör. narration "1975'te bir mühendis ilk dijital
  kamerayı icat etti" diyorsa, visual_notes "1970'ler tarzı ilk dijital kamera
  prototipi" gibi somut olmalı - narration'da geçmeyen, alakasız bir sahne değil).
- Her not somut ve gösterilebilir bir SAHNE/NESNE tarif etmeli (ör. "eski bir Nokia
  cep telefonu", "kapanan bir mağaza vitrini"); sadece bir DUYGU/RUH HALİ (ör. "kriz
  hissi", "dramatik an") tarif ETMEMELİ - duygu/ruh hali sadece somut bir nesneye
  eklenen bir sıfat olabilir (ör. "kırmızı ışıklı, hasarlı bir ürün kutusu").
- hook ya da setup bölümlerinden en az birinin visual_notes'unda şirketin/markanın
  kendisini (logosu, tabelası, ürünü, ismi görünür şekilde) tarif eden somut bir
  sahne olsun - konuyu bilmeyen bir izleyici bile görsellerden neyden bahsedildiğini
  anlayabilmeli."""


HOOK_TREND_RULES = """Hook ve tempo kuralları (RULES.md kural 9, 13):
- hook'un İLK CÜMLESİ en geç 2-3 saniyede söylenebilecek kadar KISA olsun (maks
  ~8-10 kelime) ve bir soru, şok edici bir rakam ya da bir çelişki içersin - izleyici
  ilk saniyede durup izlemeye devam etmeli.
- Genel tempo hızlı ve güncel YouTube Shorts formatına uygun olsun: kısa cümleler,
  gereksiz giriş cümlesi yok, doğrudan konuya gir.
- cta/kapanış, izleyicide MERAK AÇIĞI bırakan bir cliffhanger tonunda olsun (ör. bir
  sonraki gelişmeyi/dersi merak ettiren bir soru veya yarım bırakılmış bir ima)."""


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
  veya kriz. visual_notes'a 2 sahne yaz; bu sahneler MUTLAKA somut bir nesne/olayı (ör.
  "kapanan bir mağazanın vitrini", "aşağı düşen kırmızı bir borsa ekranı") tarif etsin,
  sadece bir "kriz hissi" tarif etmesin.

Genel kurallar:
- Tüm seslendirme metinleri {language} dilinde, akıcı ve konuşma diline uygun olsun.
- Somut sayı ve gerçek olaylara dayan, abartılı reklam dilinden kaçın.
- cta alanına izleyiciyi takip etmeye/yorum yapmaya teşvik eden tek cümlelik bir kapanış yaz
  (bu metin seslendirilmeyecek, sadece ekranda görünecek).
- hashtags alanına 5-8 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme.

{narration_style_rules}

{visual_sync_rules}

{hook_trend_rules}"""


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


# RULES.md kural 8: haftalık 3+1 seri - her bölüm konunun farklı bir evresini anlatır.
WEEKLY_PARTS = {
    1: {
        "day_label": "Pazartesi",
        "focus_title": "Bölüm 1/3: Giriş / Kuruluş",
        "focus": "Şirketin kuruluşu, erken dönemi ve nasıl bu kadar güçlü/tanınmış hale "
        "geldiği. Henüz hatadan/çöküşten BAHSETME - bu bölüm sadece yükselişi anlatır.",
        "cliffhanger": "Kapanışta 'ama her şey değişti' hissi ver, izleyiciyi Çarşamba "
        "günkü 2. bölümü (şirketin aldığı kritik yanlış karar) merak ettir.",
    },
    2: {
        "day_label": "Çarşamba",
        "focus_title": "Bölüm 2/3: Zirve / Kritik Hata",
        "focus": "Şirket zirvedeyken aldığı kritik/yanlış karar ya da gözden kaçırdığı "
        "fırsat. Henüz SONUCU anlatma (iflas/çöküş bu bölümde değil) - sadece kararın "
        "kendisini ve o anki gerekçesini anlat.",
        "cliffhanger": "Kapanışta bu kararın ne kadar yıkıcı sonuçlar doğuracağını ima "
        "et, izleyiciyi Cuma günkü 3. bölümü (çöküş/sonuç) merak ettir.",
    },
    3: {
        "day_label": "Cuma",
        "focus_title": "Bölüm 3/3: Çöküş / Sonuç",
        "focus": "Önceki bölümdeki hatanın sonucunda yaşanan çöküş/iflas/kayıp ve "
        "bugünden bakınca çıkarılan somut ders.",
        "cliffhanger": "Seriyi net bir dersle kapat; izleyiciyi yorumlarda fikrini "
        "paylaşmaya ve hafta sonu gelecek özet videosunu izlemeye davet et.",
    },
}


WEEKLY_PART_PROMPT = """Sen viral iş dünyası içerikleri yazan deneyimli bir YouTube Shorts senaristisin.
Bu, {company} hakkında 3 bölümlük haftalık bir serinin **{focus_title}** bölümü
({day_label} günü yayınlanacak). Senaryo TAM OLARAK 3 net bölümden oluşmalı: hook, setup, twist.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
Ek kaynak (varsa): {reference}

Bu bölümün odağı: {focus}
{previous_parts_block}
Bölüm kuralları:
- **hook** (0-3 saniye, ~10-18 kelime): İzleyiciyi ilk saniyede durduracak şok edici bir
  gerçek, soru veya çelişki - SADECE bu bölümün odağıyla ilgili. visual_notes'a TEK güçlü
  bir açılış sahnesi yaz.
- **setup** (~14-20 saniye, ~35-50 kelime): Bu bölümün odağını somut olaylarla anlat.
  visual_notes'a 2 sahne yaz.
- **twist** (~12-18 saniye, ~30-45 kelime): Bu bölümün kendi dönüm noktası/vurgusu.
  visual_notes'a 2 sahne yaz; bu sahneler MUTLAKA somut bir nesne/olayı tarif etsin,
  sadece bir "kriz hissi" tarif etmesin.

Genel kurallar:
- Tüm seslendirme metinleri {language} dilinde, akıcı ve konuşma diline uygun olsun.
- Somut sayı ve gerçek olaylara dayan, abartılı reklam dilinden kaçın.
- Önceki bölüm(ler)de anlatılmış olayları TEKRAR ETME, bu bölümün kendi odağına odaklan.
- cta alanına, bu bölümün "cliffhanger" talimatına uygun tek cümlelik bir kapanış yaz
  (bu metin seslendirilmeyecek, sadece ekranda görünecek): {cliffhanger}
- hashtags alanına 5-8 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme.

{narration_style_rules}

{visual_sync_rules}

{hook_trend_rules}"""


WEEKLY_RECAP_PROMPT = """Sen derinlemesine iş dünyası analiz videoları yazan deneyimli bir YouTube senaristisin.

Bu hafta {company} hakkında 3 bölümlük bir Shorts serisi yayınlandı (aşağıda özetleri
var). Şimdi bu üç bölümü SENTEZLEYEN, derinleştiren, yaklaşık 5 dakikalık (680-780
kelimelik) bir hafta sonu özet videosu yaz - YENİ bir konu değil, aynı hikayenin daha
derin/detaylı anlatımı.

Şirket: {company}
Olayın özeti: {angle}

Bu haftaki 3 bölümün seslendirme metinleri (bunları sentezle, tekrar etme - üzerine
detay/bağlam ekleyerek derinleştir):
{parts_summary}

Kurallar:
- Seslendirme metni {language} dilinde, akıcı, belgesel/analiz tonunda olsun.
- Video 4-5 bölümden (chapters) oluşsun ve haftanın 3 bölümünün (giriş/kuruluş, zirve/
  kritik hata, çöküş/sonuç) akışını takip etsin, ama sadece özetlemekle kalmayıp yeni
  bağlam/detay/rakam ekleyerek derinleştirsin.
- hook alanı ilk 15 saniyede izleyiciyi bağlayacak, "bu hafta {company}'nin hikayesini
  anlattık, şimdi tüm resmi birleştirelim" hissi veren bir açılış olsun.
- Anlatım somut tarih, rakam ve gerçek olaylara dayansın, abartılı reklam dilinden kaçın.
- Son bölüm mutlaka izleyicinin çıkaracağı 2-3 somut dersi içersin.
- cta alanına izleyiciyi abone olmaya/yorum yapmaya teşvik eden bir kapanış cümlesi yaz.
- hashtags alanına 6-10 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret, ekstra açıklama ekleme.

{narration_style_rules}"""


def _format(prompt: str, topic: dict, **extra: str) -> str:
    return prompt.format(
        title=topic.get("title", ""),
        company=topic.get("company", ""),
        angle=topic.get("angle", ""),
        reference=topic.get("reference", ""),
        language=LANGUAGE,
        narration_style_rules=NARRATION_STYLE_RULES,
        visual_sync_rules=VISUAL_SYNC_RULES,
        hook_trend_rules=HOOK_TREND_RULES,
        **extra,
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


def write_weekly_part_script(topic: dict, part_index: int, previous_narrations: list[str]) -> ShortScript:
    """Haftalık 3'lü serinin `part_index` (1, 2 ya da 3) numaralı bölümünü yazar.
    previous_narrations, önceki bölüm(ler)in tam seslendirme metinlerini içerir -
    bu, tekrarı önlemek ve anlatı sürekliliğini korumak için modele bağlam olarak
    verilir (RULES.md kural 8)."""
    part = WEEKLY_PARTS[part_index]

    if previous_narrations:
        prev_lines = "\n".join(
            f"- Bölüm {i + 1} özeti: {text}" for i, text in enumerate(previous_narrations)
        )
        previous_parts_block = f"\nÖnceki bölüm(ler)de anlatılanlar:\n{prev_lines}\n"
    else:
        previous_parts_block = ""

    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=_format(
            WEEKLY_PART_PROMPT,
            topic,
            day_label=part["day_label"],
            focus_title=part["focus_title"],
            focus=part["focus"],
            cliffhanger=part["cliffhanger"],
            previous_parts_block=previous_parts_block,
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ShortScript,
        ),
    )
    return ShortScript.model_validate_json(response.text)


def write_weekly_recap_script(topic: dict, part_narrations: list[str]) -> LongScript:
    """Haftanın 3 bölümünü sentezleyen hafta sonu uzun videosunu yazar."""
    parts_summary = "\n\n".join(
        f"Bölüm {i + 1}: {text}" for i, text in enumerate(part_narrations)
    )

    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=_format(WEEKLY_RECAP_PROMPT, topic, parts_summary=parts_summary),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LongScript,
        ),
    )
    return LongScript.model_validate_json(response.text)
