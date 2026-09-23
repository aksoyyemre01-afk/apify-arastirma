# RULES.md — Business Stories Otomasyonu Kalıcı Kuralları

Bu dosya, içerik üretim pipeline'ının (senaryo yazımı, görsel arama/doğrulama,
video birleştirme) HER çalıştırmada uyması gereken kalıcı kuralları tanımlar.
Kod bu kuralları uygulamaya çalışır; her kuralın yanında hangi dosya/fonksiyonun
onu uyguladığı ve bilinen sınırları belirtilmiştir.

## 1. Görsel alaka (KRİTİK)

Her sahnenin görsel arama sorgusu **MUTLAKA** konu/şirket adını içermeli ve
**somut, gösterilebilir bir nesne/sahne** tarif etmeli. "dramatic", "crisis",
"shutter" gibi soyut/çok anlamlı kelimeler TEK BAŞINA asla sorgu olamaz;
sadece somut bir nesneye eklenen bir sıfat olabilir (ör. "broken smartphone
screen red light" - somut nesne "smartphone screen", sıfat "broken"/"red").

**Uygulama:** `src/keywords.py` — `to_search_query()`, `_ABSTRACT_ONLY_BANLIST`
ile üretilen sorgunun soyut kelimelerden ibaret olup olmadığını kontrol eder;
öyleyse somut bir yedek sorguya (`_fallback()`) düşer. Gemini prompt'u da
somut/gösterilebilir sahne tarifi ister, soyut ruh hali kelimelerini yasaklar.

## 2. Telaffuz/fonetik doğallık

Seslendirme metninde Türkçe TTS'in yanlış okuyabileceği kelimelerden
(kar/kâr, adet/âdet gibi sesteşler) kaçınılır ya da doğru aksanla yazılır.
Şirket/marka isimleri hariç script tamamen doğal Türkçe telaffuza uygun
olmalı; okuma bir insan sunucu gibi doğal duyulmalı.

**Uygulama:** `src/script_writer.py` — `NARRATION_STYLE_RULES` bloğu, hem
short hem long prompt'una enjekte edilir.

## 3. Script-görsel senkronu

Görsel notu, script yazılırken **AYNI ADIMDA** (aynı Gemini çağrısında), o
bölümde anlatılan somut olayı/nesneyi betimleyecek şekilde üretilir. Script
yazıldıktan sonra ayrı bir adımda görsel "aranmaz" — `visual_notes` zaten
`ShortBeat` şemasının bir parçası olarak `narration` ile birlikte tek bir
yapılandırılmış (structured JSON) Gemini çağrısında üretilir.

**Uygulama:** `src/schemas.py` (`ShortBeat.narration` + `ShortBeat.visual_notes`
aynı obje), `src/script_writer.py` — prompt, her `visual_notes` maddesinin o
bölümün `narration`'ında geçen SOMUT bir olayı/nesneyi birebir görselleştirmesini
ister.

## 4. Marka/konu görseli

Ana konu bir marka/şirketse, videoda **en az bir sahnede** o markanın
logosu, ürünü veya tanınabilir bir görseli mutlaka yer alır. Konuyu bilmeyen
bir izleyici de görsellerden neyden bahsedildiğini anlayabilmeli.

**Uygulama:** `src/video_builder.py` — ilk sahnenin arama sorgusu, script'in
kendi notundan bağımsız olarak koddan `"{company} logo"` içerecek şekilde
zorlanır (brand-anchor sahnesi garantisi).

## 5. Marka adı her sorguda zorunlu (KRİTİK)

Video boyunca üretilen **HER** arama sorgusu şirket/konu adıyla **başlar**.
Bu opsiyonel değildir, sistemin temel davranışıdır — Gemini bunu atlasa bile
koddan garanti edilir.

**Uygulama:** `src/keywords.py` — `to_search_query()`, sorguyu her zaman
`f"{company} {somut_ifade}"` şeklinde, şirket adı en başta olacak şekilde
deterministik olarak kurar (Gemini'nin çıktısına bağımlı değildir).

## 6. Alaka doğrulama (KRİTİK)

Görsel indirildikten sonra:
1. Önce **ucuz bir ön filtre**: stok sitesinin kendi etiket/açıklama metni
   (Pexels `alt`, Pixabay `tags`) ile sorgu/sahne arasında en az bir ortak
   somut anahtar kelime (şirket adı ya da somut nesne adı) var mı diye
   bakılır — yoksa görsel indirilmeden elenir.
2. Sonra (Gemini varsa) **Gemini vision** ile görsel gerçekten konuyla
   ilgili mi diye kontrol edilir; emin değilse HAYIR kabul edilir.

Alakasız bulunursa görsel reddedilip bir sonraki adaya geçilir. Tüm adaylar
tükenirse, konuya en azından şirket adı üzerinden bağlı bir son çare
görseli (`"{company} logo"` araması) denenir. O da bulunamazsa **tamamen
kopuk bir görsel asla kullanılmaz** — düz renkli placeholder sahne kullanılır.

**Uygulama:** `src/stock_media.py` — `_keyword_overlap()` ön filtresi;
`src/relevance.py` — `is_relevant()` Gemini vision kontrolü (company ayrı
alan olarak geçilir, emin olunmadığında red); `src/video_builder.py` — son
çare `{company} logo` denemesi ve placeholder'a düşüş.

## 7. Görsel çeşitliliği

Aynı sorgudan art arda aynı/çok benzer görsel gelmez. Her sahne için en az
3 aday çekilip aralarından ilk **hem alaka hem tekrar** filtresini geçen
seçilir; bir videoda daha önce kullanılmış görsel URL'si tekrar kullanılmaz.
Art arda iki sahne aynı medya türünde (ikisi de foto/ikisi de video) olmaz.

**Uygulama:** `src/stock_media.py` — her kaynaktan `_MAX_CANDIDATES_PER_SOURCE`
(3) aday toplanır; `fetch_clip()`'e geçilen `used_urls` seti, video boyunca
kullanılmış URL'leri tutar ve tekrarları eler; `exclude_kind` art arda aynı
türü engeller.

## 8. Haftalık içerik planı

Her hafta seçilen TEK bir ana konu 3 short'a bölünür (Pazartesi/Çarşamba/
Cuma). Her biri konunun farklı bir bölümünü anlatır:
1. **Pazartesi:** Giriş/kuruluş — şirket nasıl kuruldu, neden güçlendi.
2. **Çarşamba:** Zirve/kritik hata anı — şirketin zirvesi ve aldığı yanlış karar.
3. **Cuma:** Çöküş/sonuç — bu hatanın sonucu, bugünkü durum, alınan ders.

Hafta sonu bu 3 bölümü sentezleyen (yeni bir konu değil, aynı hikayenin
özeti/derinleştirmesi) bir uzun video üretilir. Her bölüm, bir sonraki
bölümü merak ettiren bir cliffhanger ile biter (bkz. kural 13).

**Uygulama:** `run.py` — `--mode weekly`, `run_weekly_arc()`; `state.py`'de
TEK konu "kullanıldı" olarak işaretlenir (4 ayrı konu değil).
`src/script_writer.py` — `write_weekly_part_script()` (önceki bölümlerin
özetini bağlam olarak alır) ve `write_weekly_recap_script()`.

## 9. Hook ve trend uyumu

Her short'un ilk 2-3 saniyesi güçlü bir hook cümlesiyle (soru, şok edici
rakam veya çelişki) başlar. Üretim, güncel YouTube Shorts formatına uygun
olmalı: hızlı tempo, merak uyandıran açılış, cliffhanger.

**Uygulama:** `src/script_writer.py` — `SHORT_PROMPT` ve haftalık bölüm
prompt'ları `hook` bölümü için maksimum kelime sayısı ve "ilk cümle en geç
2-3 saniyede bitecek şekilde kısa" talimatı içerir.

## 10. Format / güvenli alan

Görseller 9:16 dikeye kırpılırken önemli unsurlar (logo, yüz, metin) kenara
düşmemeli, altyazıyla çakışmamalı.

**Uygulama:** `src/video_builder.py` — ffmpeg `crop` filtresi varsayılan
olarak ortalanmış kırpma yapar (kenar taşmasını asgariye indirir); altyazı
`MarginV`/`MarginL`/`MarginR` ile ekranın alt/yan kenarından güvenli mesafede
tutulur. **Bilinen sınır:** gerçek yüz/logo tespiti (object detection)
yapılmıyor — akıllı ortalanmış kırpma, mükemmel değil ama pratik bir
yaklaşımdır.

## 11. Tempo

Her görsel ekranda 2-4 saniyeden uzun kalmaz; görsel değişimleri anlatım
hızına senkronize olur.

**Uygulama:** `src/video_builder.py` — bir sahnenin süresi 4 saniyeyi
aşarsa, aynı sorguyla birden fazla alt-kesime bölünür (`_MAX_SCENE_SECONDS`).

## 12. Seri tutarlılığı

Haftalık 3 short + 1 uzun video aynı serinin parçasıdır; sabit font, renk
paleti kullanılır. İntro/outro ve müzik motifi için sabit varlık dosyaları
(`assets/brand/intro.mp4`, `assets/brand/outro.mp4`, `assets/brand/music.mp3`)
varsa otomatik kullanılır.

**Uygulama:** `src/video_builder.py` — font/renk sabitleri (`Fontsize`,
`PrimaryColour` vb.) tüm videolarda aynıdır (koddan sabit). **Bilinen
sınır:** gerçek intro/outro/müzik dosyaları bu repoda YOK — bunlar tasarım
varlıklarıdır, otomasyon onları üretemez. Kod, `assets/brand/` altına
konursa bunları kullanacak şekilde hazır (hook), ama şu an aktif değil;
kullanmak isteyen bu dosyaları elle eklemeli.

## 13. Kapanış / cliffhanger

Her short, merak uyandıran ve bir sonraki bölüme bağlayan bir kapanış
cümlesiyle biter.

**Uygulama:** `src/script_writer.py` — `cta` alanı için talimat, haftalık
bölümlerde bir sonraki bölümü işaret eden bir cliffhanger cümlesi ister;
tek başına (haftalık seri dışı) short'larda takip/yorum çağrısıyla
birlikte merak açığı bırakan bir ton ister.

## 14. Altyazı

Ses-altyazı senkronizasyonu (kelime bazlı, birikimli gösterim) korunur;
font boyutu bir tık büyütülür.

**Uygulama:** `src/video_builder.py` — `force_style` içindeki `Fontsize`
34'ten 38'e çıkarıldı, diğer altyazı mantığı (`src/subtitles.py`,
`build_cumulative_srt`) değişmedi.

---

## Bilinen sınırlar (özet)

- Kural 6 (alaka doğrulama) best-effort'tur: `GEMINI_API_KEY` yoksa Gemini
  vision katmanı devre dışı kalır (sadece etiket/keyword ön filtresi çalışır).
- Kural 8 (haftalık plan), `--mode shorts`/`--mode long` ile yapılan
  tekil/ad-hoc test çalıştırmalarını etkilemez — o modlar hâlâ bağımsız
  konularla çalışır, sadece `--mode weekly` yeni 3+1 seri akışını kullanır.
- Kural 10 ve 12'nin bazı kısımları (gerçek nesne tespiti, hazır marka
  varlıkları) bu ortamda üretilemeyen tasarım/ML kaynakları gerektirir;
  kod bunlar için en iyi pratik yaklaşımı (ortalanmış kırpma, sabit stil,
  opsiyonel varlık klasörü) uygular ama mükemmel değildir.
