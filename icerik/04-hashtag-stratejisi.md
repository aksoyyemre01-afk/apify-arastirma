# Hashtag Stratejisi

## Kural: gönderi başına 3–5 tane

LinkedIn'de 10+ hashtag erişimi artırmıyor, spam sinyali veriyor.
Doğru karışım şu:

| Katman | Adet | İşlev | Örnek |
|---|---|---|---|
| **Geniş** | 1 | Kategoriye girmek | `#Marketing` / `#Pazarlama` |
| **Niş** | 2–3 | Doğru kitleye ulaşmak | `#DemandGeneration`, `#B2BMarketing` |
| **Bağlam** | 1 | Gönderinin konusu | `#ContentMarketing`, `#RevenueOps` |

Geniş etiket seni havuza sokar, niş etiket doğru insanı bulur.
Sadece geniş kullanırsan gürültüde kaybolursun; sadece niş kullanırsan
kimse görmez.

## Türkçe set (TR kitlesi)

**Ana rotasyon**
`#Pazarlama` · `#B2BPazarlama` · `#TalepYaratma` · `#SatışvePazarlama` · `#BüyümePazarlaması`

**Konuya göre ek**
`#İçerikPazarlaması` · `#PazarlamaStratejisi` · `#LeadYönetimi` · `#DijitalPazarlama` · `#SatışStratejisi` · `#MüşteriDeneyimi`

> Not: Türkçe hashtag hacmi İngilizce'ye göre düşük. TR gönderilerde
> 1 İngilizce niş etiket (`#B2BMarketing`) karıştırmak erişimi genelde artırıyor.

## İngilizce set (global kitle)

**Ana rotasyon**
`#B2BMarketing` · `#DemandGeneration` · `#GrowthMarketing` · `#SalesAndMarketing` · `#Marketing`

**Konuya göre ek**
`#ContentMarketing` · `#MarketingStrategy` · `#RevenueOps` · `#GoToMarket` · `#MarketingAnalytics` · `#SaaSMarketing` · `#PipelineGeneration`

## Kaçınılacaklar

- `#love` `#motivation` `#success` gibi genel etiketler — yanlış kitle, sıfır dönüşüm.
- Her gönderide **aynı** 5 etiketi kullanmak — LinkedIn tekrarı zayıf sinyal sayıyor. 3–4 setlik rotasyon tut.
- Cümle içine gömülü hashtag (`bu #pazarlama işi zor`) — okunabilirliği bozuyor. Gönderi sonunda ayrı satırda dursun.
- Marka/şirket hashtag'i (`#ŞirketAdı`) — takip eden yoksa yer israfı.

## Doğrulama

`scripts/apify-linkedin.mjs` çalıştıktan sonra **"EN ÇOK GEÇEN HASHTAGLER"**
tablosu, senin nişinde bu ay gerçekten kullanılan etiketleri sıklığa göre verir.
Yukarıdaki listeyi o çıktıyla değiştir — tahmin yerine veri.
