# apify-arastirma — Short Video Otomasyonu

Şirketlerin battığı ya da büyük hata yaptığı gerçek olayları araştırıp bunlardan
otomatik olarak dikey YouTube Shorts videoları (script + seslendirme + hareketli
grafik video) üreten bir içerik hattı.

**Haftalık çıktı:** Her hafta seçilen TEK bir konu 3 bölümlük bir seriye bölünür
(Pazartesi / Çarşamba / Cuma) ve hafta sonu için bu 3 bölümü sentezleyen uzun
video script'i üretilir. Üretim kuralları için bkz. **[RULES.md](RULES.md)**.

## Nasıl çalışır

```
Konu araştırma (src/research.py: kürasyonlu vaka bankası + Google News RSS)
        │
        ▼
Gemini (src/script_writer.py) — TEK istekte: metin + her cümlenin sahnesi
   (sahne tipi, rakam, etiket, logo, yıl) + hook tipi (gizemli/doğrudan)
        │
        ▼
ElevenLabs (src/tts.py) — audio.mp3 + word_timings.json
        │
        ▼
Sahne planı (src/scene_planner.py) — sahneleri kelime zamanlarına hizalar,
   gizem/reveal ve 2-3 sn kurallarını uygular, logoları çözer (src/logos.py),
   altyazı sayfalarını ve ses efektlerini hazırlar
        │
        ▼
Remotion (remotion/) — kodla çizilen hareketli grafikler -> video.mp4
```

- **Görsel arama yoktur.** Tüm görseller 6 sahne tipinden oluşur:
  `logo_intro`, `big_number`, `comparison`, `timeline`, `chart`, `quote`
  (`remotion/src/scenes.tsx`).
- **Logolar:** `src/logos.py` Wikidata'daki resmi logo kaydını (P154) indirir ve
  `assets/logos/` altına önbelleğe alır. Yanlış/eski bir logo gelirse doğrusunu
  `assets/logos/<marka-slug>.svg|png` olarak koymak yeterli; elle konan dosya
  her zaman önceliklidir. Logo bulunamazsa marka adı yazı logosu olarak çizilir.
- **Kanal/seri kimliği:** `config/brand.json` (seri adı, rozet, palet, font,
  outro metinleri). Boş bırakılan metinler çizilmez.
- **Müzik/efekt:** `assets/audio/` (bkz. `assets/audio/README.md`).
- **Tekrar önleme:** `state/used_topics.json`.

## Kurulum

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env           # GEMINI_API_KEY ve ELEVENLABS_API_KEY değerlerini gir
```

Video için ayrıca **ffmpeg** ve **Node.js** gerekir:

```bash
winget install ffmpeg
winget install OpenJS.NodeJS.LTS          # macOS: brew install node / Linux: nodesource
cd remotion && npm install                 # Remotion + bağımlılıklar
npx remotion browser ensure                # headless Chrome (ilk seferde ~110 MB)
```

Remotion lisansı: bireyler ve 3 kişiye kadar şirketler için ücretsizdir; daha
büyük şirketlerde ticari lisans gerekir (remotion.dev/license).

### API çağrısı yapmadan test (dry-run)

```bash
python run.py --mode shorts --shorts-count 1 --dry-run --topic kodak
```

Gemini/ElevenLabs çağrısı yapmadan, konudan bağımsız sahte bir script (tüm sahne
tipleri + gizemli hook + reveal) ve sessiz bir ses ile gerçek bir video render eder.

### Üretim

```bash
python run.py --mode weekly                       # 3 short (video dahil) + uzun video script'i
python run.py --mode shorts --shorts-count 1      # tek short
python run.py --mode shorts --skip-tts --no-video # sadece script
```

### Var olan bir klasörden video üretme

```bash
python build_video.py --dir output/<tarih>/<short-klasörü>
python build_video.py --dir ... --migrate     # eski formatlı script'i sahneli yapar (1 Gemini isteği, ses değişmez)
python build_video.py --dir ... --frames 2    # kalite kontrolü: 2 sn'de bir kare -> kareler/
```

Remotion Studio ile canlı önizleme: `cd remotion && npx remotion studio`
(`--props=<klasör>/assets/props.json --public-dir=<klasör>/assets/public`).

## Haftalık multi-agent pipeline (`pipeline.py`)

Sürekli geri bildirim gerektirmeden haftanın 3 short'unu üretir. Yalnızca iki onay
noktası vardır; ikisi de tek bir dosyadan (`runs/<yıl>-W<hafta>/review.md`) ve tek
komutla verilir.

```
python pipeline.py --week          # Araştırmacı: konu + 3 bölüm planı -> review.md  (ONAY 1)
python pipeline.py --approve       # üretim arka planda başlar, bitince bildirim
                                   # -> review.md: script'ler, doğrulama kaynakları, QA puanları, videolar (ONAY 2)
python pipeline.py --approve       # videolar yayina-hazir/<hafta>/ klasörüne, konu "kullanıldı"
python pipeline.py --reject "gerekçe" [--short 2]   # onay 1: yeni konu / onay 2: düzelttir
python pipeline.py --status        # durum + kullanım ve tahmini maliyet
```

| Agent | Ne yapar |
|---|---|
| Araştırmacı (`agents/researcher.py`) | Konuyu seçer; tek istekle Pzt/Çar/Cum bölümlerine ayırır (olaylar bölümler arasında tekrar etmez); uzun video taslağı (2. aşama). |
| Senarist (`agents/scriptwriter.py`) | Mevcut script üretimi + süre/hook kontrolleri; geri bildirimle revizyon (önce/sonra farkı log'a). |
| Doğrulayıcı (`agents/verifier.py`) | Rakam, tarih ve iddiaları Gemini + Google Search grounding ile kontrol eder; yanlışı düzelttirir, doğrulanamayanı çıkarttırır, kaynakları kaydeder. |
| Yönetmen (`agents/director.py`) | Mevcut ses + render; ses yalnızca metin değiştiyse yeniden üretilir; contact sheet'ler. |
| Eleştirmen (`agents/critic.py`) | Kodla ölçülenler (süre, marka zamanı, sahne süresi, LUFS, format) + Gemini görsel modeliyle RULES.md puanlaması; geçmezse ilgili agent'a geri (en fazla 3 tur), hâlâ geçmezse durur ve rapor yazar. |

- Her agent'ın kararları ve revizyon geçmişi: `runs/<hafta>/log.md`.
- Kullanım ve tahmini maliyet her komutun sonunda ve review.md'de; fiyatlar `config/pricing.json`.
- Ayarlar (bütçe sınırı, QA eşiği, tur sayısı, modeller): `config/pipeline.json`.
- Haftalık otomatik tetikleme: [docs/zamanlayici.md](docs/zamanlayici.md). Pipeline tamamen
  sessiz çalışır: arka plan işçisi gizli konsolda başlar, tüm ffmpeg/Node/PowerShell çağrıları
  `src/proc.py` üzerinden `CREATE_NO_WINDOW` ile yapılır, zamanlayıcı `pythonw.exe` kullanır.

### Eleştirmen kalibrasyon testi

```
python tests/test_critic_calibration.py          # ~5 dk (2 render) + 2 görsel Gemini isteği (~0,07 $)
python tests/test_critic_calibration.py --reuse  # videolar varsa yalnızca puanlama
```

Aynı dry-run script'inden temiz ve kasıtlı bozulmuş (alakasız logo, seslendirmeyle çelişen
rakam, 5 sn'yi aşan sahne, yapışık altyazı) iki video üretir. Eleştirmen temizi geçirmeli, her
hatayı doğru kural ve sahneyle yakalamalı, her videoda en az 2 iyileştirme önerisi yazmalıdır.
Eleştirmen'in istemi veya modeli değiştiğinde çalıştırın. Rapor: `tests/_calibration/report.json`.

## GitHub Actions ile haftalık otomasyon

`.github/workflows/weekly-content.yml`, her **Pazartesi 06:00 UTC**'de
(TR 09:00) otomatik çalışır ve `python run.py --mode weekly` komutunu koşar.
Elle tetiklemek için repo → Actions → "Weekly Content Generation" →
**Run workflow**.

### Kurulması gereken GitHub Secrets

Repo → Settings → Secrets and variables → Actions → **Secrets**:

| Secret | Açıklama |
|---|---|
| `GEMINI_API_KEY` | Gemini API anahtarın |
| `ELEVENLABS_API_KEY` | ElevenLabs API anahtarın |
| `ELEVENLABS_VOICE_ID` | (opsiyonel) kullanılacak ses ID'si |

**Variables** sekmesinde (opsiyonel, override etmek istersen):
`GEMINI_MODEL`, `ELEVENLABS_MODEL`, `CONTENT_LANGUAGE`, `NEWS_LANG`, `NEWS_GL`

### Çıktılar nereye gider

- Senaryo dosyaları (`.md` + `.json`) ve `state/used_topics.json` doğrudan
  repoya **commit edilir** (bot commit).
- Ses ve video dosyaları (`.mp3`, `.mp4`) repoyu şişirmemek için commit edilmez, workflow
  **artifact** olarak yüklenir (90 gün saklanır, Actions run sayfasından
  indirilebilir).

## Ortam değişkenleri (.env)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `GEMINI_API_KEY` | — | zorunlu |
| `GEMINI_MODEL` | `gemini-3.6-flash` | |
| `ELEVENLABS_API_KEY` | — | zorunlu (TTS için) |
| `ELEVENLABS_VOICE_ID` | ElevenLabs "Brian" (`nPczCjzI2devNBz1zQrb`) | kendi hesabına ait bir ses ID'si (klon dahil) |
| `CONTENT_LANGUAGE` | `tr` | |
| `SHORTS_PER_WEEK` / `LONG_PER_WEEK` | `3` / `1` | ad-hoc modlar için |
| `NEWS_LANG` / `NEWS_GL` | `en-US` / `US` | Google News RSS dili/bölgesi |
| `BRAND_CONFIG` | `config/brand.json` | farklı bir kanal kimliği dosyası |

## Konu bankasını genişletme

`data/topics_bank.json` içine yeni vakalar eklemek için:

```json
{"id": "benzersiz-id", "company": "Şirket Adı", "title": "Video başlığı", "angle": "Ne oldu, tek cümlelik özet", "category": "collapse|big-mistake|fraud|near-miss"}
```

## Notlar / bilinen sınırlar

- Gemini kotası kısıtlı: her script TEK istek. 429 (kota) tekrar denenmez; yalnızca 503
  (sunucu yoğun) 5/15/45 sn beklemeyle en fazla 3 kez tekrar denenir (`src/script_writer.py`).
- Uzun (hafta sonu) videonun şeması ve script'i sahneli üretilir; 16:9 render
  ikinci aşamadadır.
- ElevenLabs `convert_with_timestamps` kullanılamazsa kelime zamanlamaları
  tahmin edilir (altyazı ve sahne senkronu daha az hassas olur).
- Google News RSS bazı ağlarda engellenebilir; kod bu durumda evergreen bankaya düşer.
- `--dry-run` state'i güncellemez.
