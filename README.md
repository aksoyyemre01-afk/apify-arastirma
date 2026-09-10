# apify-arastirma

Apify üzerinden LinkedIn gönderi verisi toplayıp, belirli bir zaman
penceresindeki en çok beğeni alan gönderileri raporlayan küçük bir boru hattı.

## Çıktı

- **[`RAPOR.md`](RAPOR.md)** — 31 Ağustos – 10 Eylül 2026 penceresi için üretilmiş rapor
- `data/raw_posts.json` — Apify'dan gelen ham gönderiler
- `data/top_posts.json` — tekilleştirilmiş, sıralanmış ilk 100 gönderi

## Çalıştırma

```bash
export APIFY_TOKEN=<apify_token>

python3 scripts/fetch_posts.py     # Apify aktörünü çalıştırır -> data/raw_posts.json
python3 scripts/build_report.py    # analiz + rapor -> RAPOR.md
```

### Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APIFY_TOKEN` | — | Zorunlu |
| `SINCE_DATE` | `2026-08-31` | Pencerenin başlangıcı |
| `UNTIL_DATE` | `2026-09-10` | Pencerenin sonu (yalnızca rapor tarafında) |
| `MAX_PER_QUERY` | `50` | Anahtar kelime başına gönderi |
| `MAX_PER_AUTHOR_BATCH` | `120` | 10'luk yazar grubu başına gönderi |

## Nasıl çalışıyor

LinkedIn araması **beğeniye göre sıralama sunmuyor** — yalnızca *ilgi düzeyi*
veya *tarih*. Bu yüzden yaklaşım iki fazlı:

1. **Keşif taraması** — 20 geniş konu sorgusu (EN + TR), ilgi düzeyine göre
   sıralı. LinkedIn'in ilgi sıralaması yüksek etkileşimli içeriği öne çıkarma
   eğiliminde olduğu için organik viraller bu yolla yakalanıyor.
2. **Hesap taraması** — yüksek takipçili 20 hesabın penceredeki tüm gönderileri.

Sonuçlar (`id` + içerik parmak izi ile) tekilleştirilip beğeniye göre yerelde
sıralanıyor. Yani çıktı **örneklem tabanlıdır**, platformun tamamının kesin
sıralaması değildir; ayrıntı için `RAPOR.md` içindeki metodoloji bölümüne bakın.

## Maliyet

Aktör: `harvestapi/linkedin-post-search`, sonuç başına **$0,002**.
Rapordaki çalıştırma 1.092 sonuç için ~**$2,19** tuttu.
