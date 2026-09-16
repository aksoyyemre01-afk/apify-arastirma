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
output/<tarih>/ altında .md + .json (+ .mp3)
```

- **Konu araştırma** (`src/research.py`): Apify kullanılmıyor. Önce Google News
  RSS'ten ("company files for bankruptcy" gibi aramalarla) taze haberler
  denenir; bulunamazsa `data/topics_bank.json` içindeki 25+ klasik vakadan
  (Nokia, Kodak, Enron, Theranos, WeWork, FTX...) kullanılmamış olanlar seçilir.
  Böylece RSS boş dönse bile içerik akışı hiç kesilmez.
- **Senaryo yazımı** (`src/script_writer.py`): Gemini API'ye structured output
  (`response_schema`) ile çağrı yapılır; model doğrudan JSON döner (başlık,
  hook, seslendirme metni, görsel notlar, CTA, hashtag) — ekstra metin
  ayrıştırma gerekmez.
- **Seslendirme** (`src/tts.py`): Sadece `narration` alanı (görsel notlar hariç,
  temiz konuşma metni) ElevenLabs'e gönderilir.
- **Tekrar önleme** (`src/state.py`): Hangi konunun ne zaman/ne formatta
  kullanıldığı `state/used_topics.json`'da tutulur, bu dosya her haftalık
  çalışmadan sonra repoya commit edilir.

## Kurulum (local test)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env dosyasını aç, GEMINI_API_KEY ve ELEVENLABS_API_KEY değerlerini gir
```

### Önce API çağrısı yapmadan boru hattını test et

```bash
python run.py --mode weekly --dry-run
```

Bu, gerçek Gemini/ElevenLabs çağrısı yapmadan sahte içerikle `output/<tarih>/`
altına dosyalar üretir — dosya yapısını ve akışı görmek için.

### Gerçek anahtarlarla test (önce sadece senaryo, TTS'siz)

```bash
python run.py --mode shorts --shorts-count 1 --skip-tts
```

`output/<tarih>/short-*.md` dosyasını aç, senaryo kalitesini kontrol et.

### Tam haftalık üretim (senaryo + seslendirme)

```bash
python run.py --mode weekly
```

Diğer kullanışlı komutlar:

```bash
python run.py --mode long                    # sadece uzun video
python run.py --mode shorts --shorts-count 5  # örn. 5 short üret
```

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
| `ELEVENLABS_VOICE_ID` | ElevenLabs "Rachel" | kendi klonladığın/seçtiğin ses ID'si ile değiştir |
| `CONTENT_LANGUAGE` | `tr` | senaryoların yazılacağı dil |
| `SHORTS_PER_WEEK` | `3` | |
| `LONG_PER_WEEK` | `1` | |
| `NEWS_LANG` / `NEWS_GL` | `en-US` / `US` | Google News RSS arama dili/bölgesi |

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
