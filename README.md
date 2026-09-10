# apify-arastirma

LinkedIn içerik araştırması ve içerik üretimi.
LinkedIn content research + content production.

## İçerik / Content

- **[`content/linkedin-posts.md`](content/linkedin-posts.md)** — bu ay tutan içerik tiplerinin analizi ve
  3 arketip × 2 dil (İngilizce + Türkçe) hazır LinkedIn postu, hashtag setleriyle birlikte.

## Araştırma scripti / Research script

`scripts/linkedin-trend-scraper.mjs`, Apify üzerinden LinkedIn Post Scraper çalıştırır ve sonucu
içerik tipi / ton / hashtag istatistiklerine çevirir. Node 18+ gerekir, bağımlılık yok.

```bash
export APIFY_TOKEN=apify_api_...          # token asla repoya yazılmaz

# 1. Store'daki LinkedIn post scraper'ları ve kesin actor ID'lerini listele
node scripts/linkedin-trend-scraper.mjs search "linkedin post"

# 2. Seçtiğin actor'ü çalıştır ve dataset'i data/posts.json'a indir
node scripts/linkedin-trend-scraper.mjs run <actorId>

# 3. Analiz et: içerik tipi bazında ortalama etkileşim, en iyi hook'lar, hashtag frekansı
node scripts/linkedin-trend-scraper.mjs analyze data/posts.json
```

`run` komutu argümansız çağrıldığında bu ayı kapsayan varsayılan bir input kullanır.
Kendi input'unu vermek için: `node scripts/linkedin-trend-scraper.mjs run <actorId> my-input.json`.

### Not

`analyze` komutu farklı actor'lerin alan isimlerini normalize eder (`text`/`postContent`/`content`,
`numLikes`/`likesCount`/`reactions` vb.), bu yüzden hangi LinkedIn scraper'ını seçtiğinden bağımsız
çalışır.
