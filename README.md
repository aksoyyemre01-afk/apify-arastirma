# apify-arastirma — Business Stories Otomasyonu

Şirketlerin battığı ya da büyük hata yaptığı gerçek olayları (Nokia, Blockbuster,
Enron, FTX vb.) araştırıp bunlardan otomatik olarak YouTube video senaryoları
üreten bir içerik hattı.

**Haftalık çıktı:** 3 adet YouTube Shorts (30-45 sn) + 1 adet uzun video (~5 dk),
senaryo metni + ElevenLabs ile seslendirme (mp3).

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
  (`response_schema`) ile çağrı yapılır; model doğrudan JSON döner (başlık,
  hook, seslendirme metni, görsel notlar, CTA, hashtag) — ekstra metin
  ayrıştırma gerekmez.
- **Seslendirme** (`src/tts.py`): Sadece `narration` alanı (görsel notlar hariç,
  temiz konuşma metni) ElevenLabs'e gönderilir.
- **Tekrar önleme** (`src/state.py`): Hangi konunun ne zaman/ne formatta
  kullanıldığı `state/used_topics.json`'da tutulur, bu dosya her haftalık
  çalışmadan sonra repoya commit edilir.
- **Video oluşturma** (`build_video.py`, `src/video_builder.py`): script.json +
  audio.mp3'ten dikey (1080x1920) .mp4 üretir. Her "Görsel Not" için
  `src/keywords.py` Gemini ile İngilizce bir arama sorgusu üretir,
  `src/stock_media.py` bu sorguyla Pexels'ten (önce video, sonra foto),
  bulamazsa Pixabay'den bir klip indirir; hiçbiri bulunamazsa düz renkli bir
  placeholder sahne kullanılır (pipeline hiçbir zaman tamamen durmaz).
  Sahneler ses süresine eşit paylaştırılır, ffmpeg ile art arda eklenir,
  `src/subtitles.py`'nin ürettiği .srt altyazı üzerine gömülür.

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

Bu, `PEXELS_API_KEY` ve/veya `PIXABAY_API_KEY` ile her görsel not için bir
klip indirir, ffmpeg ile ses + altyazıyla birleştirir ve aynı klasöre
`video.mp4` olarak kaydeder. İkisi de `.env`'de tanımlı değilse video yine
üretilir ama stok klip yerine düz renkli placeholder sahneler kullanılır.

Ara dosyaları (indirilen klipler, segment videoları) silmeden debug etmek
istersen: `--keep-assets`.

Pexels/Pixabay anahtarlarını buradan alabilirsin (ikisi de ücretsiz):
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
  videoların şeması `visual_notes` içermiyor). Ayrıca henüz `run.py`/GitHub
  Actions akışına otomatik bağlanmadı — her klasör için elle çalıştırılıyor.
- Altyazı zamanlaması gerçek kelime-hizalamalı değil; cümleler ses süresine
  karakter sayısına orantılı dağıtılır. Çoğu short için yeterince yakın
  ama mükemmel senkron için ElevenLabs'in timestamp özelliği entegre
  edilebilir (şu an kapsam dışı).
