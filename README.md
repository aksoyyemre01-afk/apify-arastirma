# apify-arastirma

Apify **LinkedIn Post Scraper** ile bu ayın yüksek etkileşimli gönderilerini
çekip içerik tipi / ton analizi yapan script ve bu analize göre yazılmış
LinkedIn içerikleri (TR + EN).

## Kurulum

Node 18+ yeterli, bağımlılık yok.

```bash
export APIFY_TOKEN=apify_api_xxxxxxxx     # kendi token'ın
```

## Kullanım

```bash
# 1) Store'daki LinkedIn post scraper aktörlerini listele, birini seç
node scripts/apify-linkedin.mjs actors
export APIFY_ACTOR=apimaestro~linkedin-post-search-scraper

# 2) Anahtar kelimelerinle son 30 günü tara + analiz et
node scripts/apify-linkedin.mjs run "demand generation" "b2b pazarlama"

# 3) Kaydedilmiş veriyi tekrar analiz et
node scripts/apify-linkedin.mjs analyze data/posts.json
```

Ayarlanabilir ortam değişkenleri: `APIFY_ACTOR`, `DAYS` (varsayılan 30),
`MAX_ITEMS` (varsayılan 200).

### Script ne çıkarıyor

- İçerik tipi kırılımı (hikâye / liste / vaka / karşıt görüş / rehber …) ve tip başına ortalama etkileşim
- Biçim sinyalleri: ortalama kelime & satır, soru/liste/emoji/CTA oranı
- En çok geçen hashtag'ler (sıklık sıralı)
- En iyi 15 açılış cümlesi (hook) + gönderi linkleri

Etkileşim skoru ham beğeni değil: `beğeni + yorum×3 + paylaşım×5`.

## İçerikler

| Dosya | İçerik |
|---|---|
| `icerik/01-analiz-icerik-tipleri.md` | Hangi içerik tipi neden tutuyor + biçim/ton kuralları |
| `icerik/02-post-tr.md` | 3 Türkçe LinkedIn gönderisi |
| `icerik/03-post-en.md` | 3 İngilizce LinkedIn gönderisi |
| `icerik/04-hashtag-stratejisi.md` | Hashtag katman modeli ve TR/EN setler |

Niş: pazarlama / büyüme / satış. Ses: uzman çalışan.
Gönderilerdeki `[ ]` alanları kendi gerçek rakamlarınla doldur.

## Güvenlik

Token'ı repoya yazma; ortam değişkeni olarak ver. `data/` klasörü ve `.env`
gitignore'da.
