"""Gemini API ile YouTube Shorts / uzun video senaryosu üretimi.

RULES.md: script ve her cümlenin sahne yapısı (sahne tipi + rakam/etiket/logo/yıl)
AYNI Gemini çağrısında yapılandırılmış JSON olarak üretilir (kural 1). Hook
tipi (gizemli/doğrudan) ve reveal zamanlaması da aynı çağrıda belirlenir
(kural 2). Görsel arama yoktur; sahneler src/scene_planner.py + remotion/
tarafından kodla çizilir.

Gemini kotası kısıtlı olduğu için her fonksiyon TEK istek atar, otomatik
tekrar denemez.
"""

import json
import os
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .schemas import LongScript, SceneLayout, ShortScript

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
LANGUAGE = os.environ.get("CONTENT_LANGUAGE", "tr")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY tanımlı değil (.env dosyasını kontrol et)")
        # SDK'nın kendi tekrar denemesi kapalı (attempts=1); tekrar politikası _generate'te.
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )
    return _client


NARRATION_STYLE_RULES = """Seslendirme metni kuralları (RULES.md kural 3 - doğal Türkçe):
- Bir insan sunucu gibi konuş: kısa, akıcı, günlük konuşma dili. Yazı dili resmiyeti,
  "Peki ya...?", "İşte tam bu noktada" gibi klişe yapay zekâ kalıpları ve abartılı
  reklam dili YOK.
- Sesteş kelimelerden kaçın ya da doğru aksanla yaz ("kar"/"kâr", "adet"/"âdet");
  mümkünse aksan gerektirmeyen eş anlamlısını seç ("kâr" yerine "kazanç").
- Zor ünsüz kümeleri, nadir kelimeler ve gereksiz yabancı terimler kullanma.
- Rakamları konuşulduğu gibi ama rakamla yaz: "125 milyar dolar", "44,6 milyar dolar"
  (ondalık ayırıcı virgül). Kısaltma (vb., örn., $) kullanma."""


SCENE_RULES = """Sahne kuralları (RULES.md kural 1, 5, 10 - ÇOK ÖNEMLİ):
- Metni sahnelere böl: her sahne TEK kısa cümle ya da yan cümle, 5-10 kelime (~2-3 saniye).
  Toplam 12-18 sahne. Tüm narration'lar art arda okununca tam metin oluşur; metni sahneler
  arasında tekrar ETME.
- Her sahnenin scene_type'ı ve alanları, O CÜMLEDE söyleneni doğrudan göstermeli:
  * cümlede önemli bir rakam varsa -> big_number (value + unit + kısa label)
  * cümlede iki marka/taraf karşı karşıyaysa -> comparison (left_brand/right_brand + değerler)
  * cümlede yıl/tarih + olay varsa -> timeline (year + kısa text)
  * cümlede yükseliş/düşüş/erime anlatılıyorsa -> chart (direction + points + end_value)
  * bir marka tanıtılıyor/açığa çıkıyorsa -> logo_intro (brand + kısa label)
  * hiçbiri yoksa -> quote (cümlenin özü, en fazla 8 kelime, 1-2 highlight kelimesi)
- comparison'ın iki tarafı da ZORUNLU olarak GERÇEK şirket ya da ürün adıdır (logosu otomatik
  çekilir; ör. "Apple", "iPhone", "Microsoft"). "yeni rakip", "diğerleri", "rakipler",
  "herkes", "pazar" gibi genel ifadeler YASAK. Karşı taraf cümlede adıyla geçmiyorsa ama
  gerçekte biliniyorsa gerçek adını yaz; bilinmiyorsa comparison kullanma. Oran/pay
  anlatılıyorsa big_number kullan (ör. value "%50", label "İnternet kullanıcılarının payı").
- Her sahnenin mood'unu belirle: rise (zirve/büyüme/başarı), fall (düşüş/kayıp/kriz/kötü
  karar) ya da neutral. Zemin tonu buna göre değişir.
- Ekranda görünen her rakam (value, year, end_value, left_value, right_value, label) O
  SAHNENİN cümlesinde rakamla söylenmiş olmalı; cümlede geçmeyen tahmini/uydurma rakam
  yazma (uymayan rakamlar ekrandan otomatik silinir).
- quote.text cümlenin KENDİ kelimelerinden kısaltılmış olmalı; cümlede olmayan yeni bir
  yorum/hüküm ekleme.
- Aynı sahne tipini art arda 2'den fazla kullanma; çeşitlilik tempoyu yükseltir.
- Ekranda görünen alanlar (value, unit, label, text, left_value, right_value, end_value,
  cta) izleyiciye yönelik KISA metinlerdir. Bunlara ASLA iç not, sahne tarifi, kamera
  yönlendirmesi, prompt metni, köşeli parantez ya da "görsel/sahne/animasyon" gibi
  kelimeler yazma.
- Marka adlarını resmi, bilinen yazımıyla yaz (ör. "Google", "Microsoft"); logosu
  otomatik bulunur."""


HOOK_RULES = """Hook, tempo ve kapanış kuralları (RULES.md kural 2, 4):
- İlk cümle en geç 2-3 saniyede söylenebilecek kadar kısa (en fazla 10 kelime) ve güçlü
  olsun: şok edici bir rakam, çelişki ya da soru.
- hook_type'ı belirle:
  * mystery: hook bir soru/gizem kuruyor ve cevap olan marka ilk cümlede SÖYLENMİYOR
    (ör. "...reddeden şirketi biliyor musunuz?"). Bu durumda: ilk sahne bağlamı veren
    somut unsuru göstermeli (ilgili rakam, karşı taraf şirketin logosu ya da olay yılı);
    cevap olan marka (mystery_brand) ilk sahnede de yer alabilir, video onu soru işaretli
    kutuyla gizler. Marka en geç 5. saniyede sesli söylenmeli; söylendiği sahne
    logo_intro + reveal=true olmalı. reveal_by_seconds'a bu saniyeyi yaz (<= 5).
  * direct: ana marka ilk cümlede söyleniyor; ilk sahne o markayı (logo_intro ya da
    brand alanı dolu bir sahne) göstermeli ki ilk 3 saniyede görünsün.
- Tempo hızlı: gereksiz giriş yok, her cümle yeni bir bilgi.
- Son cümle ve cta izleyicide merak açığı bırakmalı (bir sonraki gelişmeyi merak ettiren
  soru ya da yarım bırakılmış bir ima)."""


SHORT_PROMPT = """Sen viral iş dünyası içerikleri yazan deneyimli bir YouTube Shorts senaristisin.

Aşağıdaki gerçek şirket olayı hakkında 30-45 saniyelik (80-110 kelime) bir Shorts senaryosu
yaz ve AYNI ANDA her cümlenin ekranda nasıl görüneceğini yapılandır.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
Ek kaynak (varsa): {reference}
{focus_block}
Genel kurallar:
- Tüm metinler {language} dilinde.
- Somut sayı, yıl ve gerçek olaylara dayan; uydurma rakam kullanma.
- hashtags alanına 5-8 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret.

{narration_style_rules}

{scene_rules}

{hook_rules}"""


MIGRATE_PROMPT = """Aşağıdaki Türkçe YouTube Shorts seslendirme metni zaten seslendirildi; metni
DEĞİŞTİREMEZSİN. Görevin sadece bu metni sırasıyla sahnelere bölmek ve her sahnenin ekranda
nasıl görüneceğini yapılandırmak.

- Sahnelerin narration alanları, metni HİÇBİR kelimeyi değiştirmeden, eklemeden, silmeden ve
  sırayı bozmadan böler (noktalama dahil birebir aynı). Her sahne 5-10 kelime.
- Ana şirket: {company}
- Ekranda kapanışta görünecek cta (varsa bunu kısalt/iyileştir): {cta}

Seslendirme metni:
\"\"\"{narration}\"\"\"

{scene_rules}

{hook_rules}"""


LONG_PROMPT = """Sen derinlemesine iş dünyası analiz videoları yazan deneyimli bir YouTube senaristisin.

Aşağıdaki gerçek şirket olayı hakkında yaklaşık 5 dakikalık (toplam 680-780 kelimelik seslendirme metni) bir video senaryosu yaz.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
Ek kaynak (varsa): {reference}

Kurallar:
- Seslendirme metni {language} dilinde, akıcı, belgesel/analiz tonunda olsun.
- Video 4-5 bölümden (chapters) oluşsun: örn. "Giriş / Zirve", "İlk Uyarı Sinyalleri", "Kritik Hata", "Çöküş", "Alınacak Dersler".
- Her bölümün scenes alanında, bölüm metnini cümle cümle sahnelere böl (narration'ların
  birleşimi bölümün narration'ı ile birebir aynı olmalı) ve her cümlenin sahnesini yapılandır.
- hook alanı ilk 15 saniyede izleyiciyi bağlayacak, merak uyandıran bir açılış olsun.
- Anlatım somut tarih, rakam ve gerçek olaylara dayansın, abartılı reklam dilinden kaçın.
- Son bölüm mutlaka izleyicinin çıkaracağı 2-3 somut dersi içersin.
- cta alanına izleyiciyi abone olmaya/yorum yapmaya teşvik eden bir kapanış cümlesi yaz.
- hashtags alanına 6-10 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret.

{narration_style_rules}

{scene_rules}"""


# RULES.md kural 9: haftalık seri - her bölüm konunun farklı bir evresini anlatır.
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
- Video 4-5 bölümden (chapters) oluşsun ve haftanın 3 bölümünün akışını takip etsin,
  ama sadece özetlemekle kalmayıp yeni bağlam/detay/rakam ekleyerek derinleştirsin.
- Her bölümün scenes alanında, bölüm metnini cümle cümle sahnelere böl (narration'ların
  birleşimi bölümün narration'ı ile birebir aynı olmalı) ve her cümlenin sahnesini yapılandır.
- hook alanı ilk 15 saniyede izleyiciyi bağlayacak bir açılış olsun.
- Anlatım somut tarih, rakam ve gerçek olaylara dayansın.
- Son bölüm mutlaka izleyicinin çıkaracağı 2-3 somut dersi içersin.
- cta alanına izleyiciyi abone olmaya/yorum yapmaya teşvik eden bir kapanış cümlesi yaz.
- hashtags alanına 6-10 adet ilgili, İngilizce ve {language} dilinde karışık hashtag ekle.
- Sadece istenen JSON şemasına uygun çıktı üret.

{narration_style_rules}

{scene_rules}"""


def _format(prompt: str, topic: dict, **extra: str) -> str:
    values = {
        "title": topic.get("title", ""),
        "company": topic.get("company", ""),
        "angle": topic.get("angle", ""),
        "reference": topic.get("reference", ""),
        "language": LANGUAGE,
        "narration_style_rules": NARRATION_STYLE_RULES,
        "scene_rules": SCENE_RULES,
        "hook_rules": HOOK_RULES,
        "focus_block": "",
    }
    values.update(extra)
    return prompt.format(**values)


# 503 (sunucu yoğun) istekleri üretim yapmadan döner: artan beklemeyle 3 kez daha
# denenir. 429 (kota) ve diğer tüm hatalar ASLA tekrar denenmez - günlük kota kısıtlı.
RETRY_ON_STATUS = 503
RETRY_DELAYS_SECONDS = (5, 15, 45)


def _generate(contents: str, schema: type):
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            response = _get_client().models.generate_content(model=MODEL, contents=contents, config=config)
            return schema.model_validate_json(response.text)
        except genai_errors.APIError as e:
            if e.code != RETRY_ON_STATUS or attempt == len(RETRY_DELAYS_SECONDS):
                raise
            delay = RETRY_DELAYS_SECONDS[attempt]
            print(f"   Gemini {e.code} (sunucu yoğun); {delay} sn sonra tekrar denenecek "
                  f"({attempt + 1}/{len(RETRY_DELAYS_SECONDS)})...")
            time.sleep(delay)


def write_short_script(topic: dict, focus_block: str = "") -> ShortScript:
    return _generate(_format(SHORT_PROMPT, topic, focus_block=focus_block), ShortScript)


def write_long_script(topic: dict) -> LongScript:
    return _generate(_format(LONG_PROMPT, topic), LongScript)


def write_weekly_part_script(topic: dict, part_index: int, previous_narrations: list[str]) -> ShortScript:
    """Haftalık 3'lü serinin `part_index` (1, 2 ya da 3) numaralı bölümünü yazar.
    previous_narrations önceki bölümlerin metinleridir - tekrarı önlemek için."""
    part = WEEKLY_PARTS[part_index]
    lines = [
        "",
        f"Bu, {topic.get('company', '')} hakkında 3 bölümlük haftalık serinin "
        f"**{part['focus_title']}** bölümü ({part['day_label']} günü yayınlanacak).",
        f"Bu bölümün odağı: {part['focus']}",
        f"Kapanış (son cümle + cta): {part['cliffhanger']}",
        "Önceki bölüm(ler)de anlatılmış olayları TEKRAR ETME.",
    ]
    if previous_narrations:
        lines.append("Önceki bölüm(ler)de anlatılanlar:")
        lines += [f"- Bölüm {i + 1}: {text}" for i, text in enumerate(previous_narrations)]
    lines.append("")
    return write_short_script(topic, focus_block="\n".join(lines))


def write_weekly_recap_script(topic: dict, part_narrations: list[str]) -> LongScript:
    """Haftanın 3 bölümünü sentezleyen hafta sonu uzun videosunu yazar."""
    parts_summary = "\n\n".join(f"Bölüm {i + 1}: {text}" for i, text in enumerate(part_narrations))
    return _generate(_format(WEEKLY_RECAP_PROMPT, topic, parts_summary=parts_summary), LongScript)


def structure_existing_narration(narration: str, company: str, cta: str = "") -> SceneLayout:
    """Seslendirmesi hazır eski formatlı bir script için (hook/setup/twist +
    visual_notes) sabit metni sahnelere bölüp sahne yapısını üretir. TEK istek."""
    contents = _format(
        MIGRATE_PROMPT,
        {"company": company},
        narration=narration,
        cta=cta or "(yok)",
    )
    return _generate(contents, SceneLayout)


def dump_script(script: ShortScript, extra: dict | None = None) -> str:
    data = script.model_dump()
    data["narration_full"] = script.narration_full
    data.update(extra or {})
    return json.dumps(data, ensure_ascii=False, indent=2)
