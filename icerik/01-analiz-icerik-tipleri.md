# LinkedIn İçerik Tipi Analizi — Pazarlama / Büyüme / Satış

> **Durum notu:** Bu oturumun ağ politikası `api.apify.com` dahil tüm dış hostları
> engelliyor (proxy CONNECT'e 403 dönüyor). Bu yüzden aşağıdaki tablo **canlı
> scrape verisi değil**, bilinen LinkedIn içerik kalıplarına dayanan bir hipotez
> setidir. `scripts/apify-linkedin.mjs` scriptini kendi makinende çalıştırdığında
> bu tablo gerçek sayılarla doğrulanır/güncellenir.

## Ölçüm mantığı

LinkedIn algoritması yorumu ve paylaşımı beğeniden ağır sayar. Script bu yüzden
ham beğeni yerine ağırlıklı bir skor kullanıyor:

```
etkileşim = beğeni + (yorum × 3) + (paylaşım × 5)
```

Top %20'lik dilim alınır, içerik tipine göre sınıflanır, biçim sinyalleri
(kelime sayısı, satır sayısı, soru/liste/emoji/CTA oranı) çıkarılır.

## Yüksek performans gösteren içerik tipleri

| # | İçerik tipi | Neden tutuyor | Riski |
|---|---|---|---|
| 1 | **Kişisel hikâye + ders** | Yorum davetiyesi doğal. "Ben de yaşadım" refleksi tetikliyor. | Klişeye kayarsa ("bir kahve dükkânında...") ters teper. |
| 2 | **Vaka çalışması / somut sayı** | Doğrulanabilir iddia = kaydetme (save) ve paylaşım. | Sayı bağlamsızsa güven kaybı. |
| 3 | **Liste / çerçeve (framework)** | Taranabilir, kaydedilebilir, alıntılanabilir. | 10+ madde olunca okunmuyor; 5–7 ideal. |
| 4 | **Karşıt görüş** | Katılan da katılmayan da yorum yazıyor. | İçi boş provokasyon marka zedeliyor. |
| 5 | **"Neyi yanlış yaptım"** | Uzman çalışan sesi için en güçlüsü: kırılganlık + otorite. | Sahte alçakgönüllülük ("en büyük kusurum çok çalışmam"). |
| 6 | **Süreç şeffaflığı** (ekran görüntüsü, gerçek pano) | Kanıt gösterir, teoriden ayrışır. | Şirket verisi paylaşırken izin/gizlilik. |

## Biçim kuralları (top %20'de tekrar eden desen)

- **İlk satır tek başına dursun.** Mobilde "…daha fazla göster" öncesi görünen
  tek şey o. Kanca oradadır.
- **900–1.300 karakter.** Çok kısa = sığ, çok uzun = tıklanmıyor.
- **Tek cümlelik paragraflar.** İki satırdan uzun blok yok.
- **Dış link birinci yorumda.** Gövdedeki link erişimi düşürüyor.
- **3–5 hashtag.** 10+ hashtag spam sinyali.
- **Kapanış = soru.** Genel değil, cevaplaması kolay ve spesifik bir soru.
- **Emoji: madde işareti yerine az ve fonksiyonel.** Uzman çalışan tonunda
  emoji yağmuru güveni düşürüyor.

## Ton: "uzman çalışan" sesi

| Yap | Yapma |
|---|---|
| "Ekipte şunu denedik, şu çıktı" | "5 sırrı açıklıyorum 🚀🔥" |
| Sayıyı bağlamıyla ver | Bağlamsız "%300 büyüdük" |
| Ne işe yaramadığını da yaz | Sadece zafer anlatısı |
| Krediyi ekiple paylaş | Tek kahraman anlatısı |
| Sade dil, jargonsuz | "sinerjik omni-channel paradigma" |
