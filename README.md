# apify-arastirma — Business Stories Otomasyonu

Şirketlerin battığı ya da büyük hata yaptığı gerçek olayları (Nokia, Blockbuster,
Enron, FTX vb.) araştırıp bunlardan otomatik olarak YouTube video senaryoları
üreten bir içerik hattı.

**Haftalık çıktı:** Her hafta seçilen TEK bir konu 3 bölümlük bir seriye bölünür
(Pazartesi: giriş/kuruluş, Çarşamba: zirve/kritik hata, Cuma: çöküş/sonuç) ve
hafta sonu bu 3 bölümü sentezleyen 1 uzun özet video (~5 dk) üretilir — senaryo
metni + ElevenLabs ile seslendirme (mp3). Üretim kuralları (görsel alaka, marka
tutarlılığı, tempo vb.) için bkz. **[RULES.md](RULES.md)**.

## Nasıl çalışır

```
Konu araştırma (Google News RSS + kürasyonlu vaka bankası)
        │
        ▼
Senaryo yazımı (Gemini API, structured JSON çıktı)
        │
        ▼
Seslendirme (ElevenLabs TTS)
        │
        ▼
output/<tarih>/<video-klasörü>/ altında script.md + script.json + audio.mp3
        │
        ▼  (build_video.py, ayrı adım)
Pexels/Pixabay'den klip + ffmpeg birleştirme + altyazı
        │
        ▼
video.mp4 (aynı klasörde)
```

- **Konu araştırma** (`src/research.py`): Apify kullanılmıyor. Önce
  `data/topics_bank.json` içindeki 35+ tanınmış, dramatik klasik vakadan
  (Nokia, Blockbuster, Kodak, Enron, Theranos, WeWork, FTX...) kullanılmamış
  olanlar seçilir — tanınmışlık = daha yüksek viral potansiyel. Bu vakalar
  yetmezse Google News RSS'ten ("company files for bankruptcy" gibi
  aramalarla) taze haberlerle tamamlanır. Böylece içerik hep güncel ama
  düşük profilli haberlerle sınırlı kalmaz.
- **Senaryo yazımı** (`src/script_writer.py`): Gemini API'ye structured output
  (`response_schema`) ile çağrı yapılır; short'lar için model TAM OLARAK 3
  bölümden oluşan bir JSON döner - **hook** (0-3 sn, tek çarpıcı sahne),
  **setup** (kuruluş/bağlam, 2 sahne), **twist** (senaryonun en dramatik anı,
  2 sahne - görselleri kasıtlı olarak kriz/kontrast temalı istenir). Her
  bölümün kendi `narration` + `visual_notes`'u var; `cta` ayrı, seslendirilmeyen
  bir kapanış metnidir. Her iki prompt'a (short + long) `NARRATION_STYLE_RULES`
  eklenir: Türkçe sesteş/yazılışı belirsiz kelimelerden (kar/kâr, adet/âdet)
  doğru aksanla yazmasını ya da kaçınmasını, kısa/konuşma diline yakın cümleler
  kurmasını ve TTS'in doğal okuyamayacağı yapılardan (uzun iç içe cümleler,
  nadir/yabancı terimler) kaçınmasını ister - amaç seslendirmenin robotik değil
  bir insan sunucu gibi doğal akması.
- **Seslendirme** (`src/tts.py`): `synthesize_with_timestamps()` ElevenLabs'in
  karakter bazlı zaman kodlarını kelime bazlı zamanlamaya indirger
  (`word_timings.json` olarak kaydedilir) - bu, altyazıların gerçek kelime
  senkronizasyonu için kullanılır. Endpoint kullanılamazsa (plan/SDK
  desteklemiyorsa) sessizce düz seslendirmeye düşer.
- **Tekrar önleme** (`src/state.py`): Hangi konunun ne zaman/ne formatta
  kullanıldığı `state/used_topics.json`'da tutulur, bu dosya her haftalık
  çalışmadan sonra repoya commit edilir.
- **Video oluşturma** (`build_video.py`, `src/video_builder.py`): script.json +
  audio.mp3'ten dikey (1080x1920) .mp4 üretir.
  - Her sahne için `src/keywords.py` Gemini ile spesifik/somut bir İngilizce
    arama sorgusu üretir (ör. "Nokia vintage cellphone factory 1990s" - jenerik
    "corporate office"/"business handshake" gibi klişeler yasak). Konunun
    şirket adı ve özeti (`company`/`topic_context`, script.json'a `run.py`
    tarafından yazılır) modele çapa verir ve sorguya koddan da garanti edilir
    (Gemini es geçse bile şirket adı sorguya eklenir); twist sahneleri ayrıca
    kırmızı/kriz temalı modifiyerlerle güçlendirilir.
  - `src/stock_media.py` sırayla Pexels video → Pexels foto → Pixabay video →
    Pixabay foto dener, her kaynaktan (en yüksek çözünürlüklüden başlayarak)
    birden fazla aday indirir; `src/relevance.py` her adayı Gemini vision ile
    "bu görsel gerçekten bu sahneyle/şirketle ilgili mi" diye kontrol eder,
    ilk alakalı bulunan kullanılır (Gemini yoksa bu filtre devre dışı kalır,
    ilk aday kullanılır). Art arda iki sahne aynı türde (ikisi de foto/video)
    olmasın diye önceki sahnenin türü bir sonrakinde dışlanır. Hiçbir uygun
    kaynak bulunamazsa düz renkli bir placeholder sahne kullanılır (pipeline
    hiçbir zaman tamamen durmaz).
  - Sahneler ses süresine eşit paylaştırılır, ffmpeg ile art arda eklenir.
  - Altyazı `word_timings.json` varsa gerçek kelime zamanlamasıyla, yoksa
    `src/subtitles.py`'nin tahmini kelime dağıtımıyla üretilir - kelimeler
    tek tek EKLENEREK birikir (ör. "Nokia," → "Nokia, cebinde" → "Nokia,
    cebinde taşıdığımız...", cümle sonunda ya da 6 kelimede bir sıfırlanır),
    kalın/büyük, dinamik bir stille gömülür (statik tam cümle bloğu ya da
    tek kelime değil).

## Kurulum (local test)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env dosyasını aç, GEMINI_API_KEY ve ELEVENLABS_API_KEY değerlerini gir
```

Video oluşturma adımı (`build_video.py`) için ayrıca **ffmpeg** gerekir:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y ffmpeg

# Windows (PowerShell, winget ile)
winget install ffmpeg
# veya: choco install ffmpeg
# Kurulumdan sonra yeni bir terminal aç ki PATH güncellensin, sonra doğrula:
ffmpeg -version
```

Wikimedia/Wayback görsel kaynağı için ayrıca (bir kere) Playwright'ın Chromium
tarayıcısını indirmen gerekir:

```bash
playwright install chromium
```

### Önce API çağrısı yapmadan boru hattını test et

```bash
python run.py --mode weekly --dry-run
```

Bu, gerçek Gemini/ElevenLabs çağrısı yapmadan sahte içerikle `output/<tarih>/`
altına, her video kendi klasöründe olacak şekilde dosyalar üretir — dosya
yapısını ve akışı görmek için.

### Gerçek anahtarlarla test (önce sadece senaryo, TTS'siz)

```bash
python run.py --mode shorts --shorts-count 1 --skip-tts
```

`output/<tarih>/short-*/script.md` dosyasını aç, senaryo kalitesini kontrol et.

### Tam haftalık üretim (senaryo + seslendirme)

```bash
python run.py --mode weekly
```

Diğer kullanışlı komutlar:

```bash
python run.py --mode long                    # sadece uzun video
python run.py --mode shorts --shorts-count 5  # örn. 5 short üret
```

### Video (.mp4) oluşturma

Bir short klasöründe `script.json` (visual_notes içermeli — yani uzun
videolar değil, sadece short'lar destekleniyor) ve `audio.mp3` hazırsa:

```bash
python build_video.py --dir output/2026-09-16/airbaltic-iflasi
```

Her sahne için görsel kaynağı RULES.md kural 15'teki önceliği izler: rakam/
karşılaştırma içeren sahneler için otomatik üretilen bir grafik (anahtar
gerekmez), diğerleri için sırayla Wikimedia Commons (anahtar gerekmez) →
Wayback Machine (anahtar gerekmez, Chromium ile ekran görüntüsü) →
`PEXELS_API_KEY`/`PIXABAY_API_KEY` varsa Pexels/Pixabay (son çare). Hiçbiri
bulunamazsa düz renkli placeholder sahne kullanılır — video hiçbir zaman
üretimi durmaz.

Ekstra özellikler:
- **İnsan hook:** video klasörüne kendi çektiğin 2-4 sn'lik dikey bir
  `hook.mp4` koyarsan, video onunla (kendi sesiyle) başlar, seslendirme
  ondan sonra devam eder.
- **Ses tasarımı:** `assets/audio/` klasörüne `music.mp3`/`whoosh.mp3`/
  `impact.mp3` koyarsan otomatik miksajlanır (bkz. `assets/audio/README.md`).
- **Ses klonu:** `.env`'deki `ELEVENLABS_VOICE_ID`'yi kendi klonladığın
  sesin ID'siyle değiştirmen yeterli.

Ara dosyaları (indirilen klipler, segment videoları) silmeden debug etmek
istersen: `--keep-assets`.

Pexels/Pixabay anahtarlarını buradan alabilirsin (ikisi de ücretsiz, ama
artık son çare):
- Pexels: https://www.pexels.com/api/
- Pixabay: https://pixabay.com/api/docs/

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
- Ses dosyaları (`.mp3`) repoyu şişirmemek için commit edilmez, workflow
  **artifact** olarak yüklenir (90 gün saklanır, Actions run sayfasından
  indirilebilir).

## Ortam değişkenleri (.env)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `GEMINI_API_KEY` | — | zorunlu |
| `GEMINI_MODEL` | `gemini-3.6-flash` | |
| `ELEVENLABS_API_KEY` | — | zorunlu (TTS için) |
| `ELEVENLABS_VOICE_ID` | ElevenLabs "Brian" (`nPczCjzI2devNBz1zQrb`) | free planda API'den kullanılabilen premade bir ses; değiştirmek istersen ElevenLabs hesabındaki "My Voices" altında **kendi hesabına ait** (library/shared değil) bir ses ID'si kullan, aksi halde free planda aynı hata tekrar alınır |
| `CONTENT_LANGUAGE` | `tr` | senaryoların yazılacağı dil |
| `SHORTS_PER_WEEK` | `3` | |
| `LONG_PER_WEEK` | `1` | |
| `NEWS_LANG` / `NEWS_GL` | `en-US` / `US` | Google News RSS arama dili/bölgesi |
| `PEXELS_API_KEY` | — | `build_video.py` için, opsiyonel ama önerilir |
| `PIXABAY_API_KEY` | — | `build_video.py` için, opsiyonel ama önerilir (Pexels'te bulunamazsa yedek) |

## Konu bankasını genişletme

`data/topics_bank.json` içine yeni vakalar eklemek için:

```json
{"id": "benzersiz-id", "company": "Şirket Adı", "title": "Video başlığı", "angle": "Ne oldu, tek cümlelik özet", "category": "collapse|big-mistake|fraud|near-miss"}
```

## Notlar / bilinen sınırlar

- Google News RSS bazı ağlarda/proxy'lerde engellenebilir; kod bu durumda
  sessizce evergreen bankaya düşer (`try/except` ile korunuyor).
- Gemini'den gelen JSON, `pydantic` şemasıyla doğrulanır; şema uyuşmazsa
  hata fırlatır — bu genelde model/istem değişikliğinde kontrol edilmesi
  gereken bir noktadır.
- `--dry-run` state'i güncellemez, yani dry-run çalıştırmaları konu
  havuzunu tüketmez.
- `build_video.py` şu an sadece **short** senaryoları destekliyor (uzun
  videoların şeması hook/setup/twist yapısında değil). Ayrıca henüz
  `run.py`/GitHub Actions akışına otomatik bağlanmadı — her klasör için elle
  çalıştırılıyor.
- Eski (bu güncellemeden önce üretilmiş) script.json dosyaları hâlâ çalışır -
  `video_builder.py` düz `visual_notes` formatını da destekler - ama twist
  dramatikleştirmesi ve beat bazlı yapı olmadan.
- ElevenLabs'in `convert_with_timestamps` endpoint'i her hesap/plan/SDK
  sürümünde garanti değildir; kullanılamazsa kod sessizce düz seslendirmeye
  ve tahmini kelime zamanlamasına düşer (yine kelime-kelime görünür, sadece
  daha az hassas senkronla).
- Placeholder sahnelerde (stok klip bulunamadığında) `to_search_query`
  Gemini çağrısı yine de yapılır; sadece stok medya sonucu boş döner.
- `to_search_query` şirket adını sorguya her zaman garanti eder, ama tek başına
  bu yeterli olmayabilir: Türkçe'den birebir çevrilen çok anlamlı kelimeler
  (ör. "kepenk" -> "shutter") stok arama motorunda ve hatta Gemini vision
  alaka kontrolünde jenerik/alakasız sonuçlarla eşleşebilir (ör. bambaşka bir
  markanın benzin istasyonu) - çünkü görsel, markaya özgü hiçbir işaret
  taşımadığından "kelimeyle eşleşiyor" görünebilir. Bu yüzden prompt artık
  böyle belirsiz tek kelimelik çevirilerden kaçınmayı ve en az 2 somut
  tanımlayıcı kullanmayı istiyor, `relevance.py`'nin kontrolü de şirket adını
  ayrı bir alan olarak alıp emin olmadığında reddetmeye (HAYIR) daha yatkın.
  Yine de mükemmel değildir - tamamen alakasız bir sonuç görürsen, o script.json
  içindeki ilgili `visual_notes` maddesini elle netleştirmek en garanti çözümdür.
