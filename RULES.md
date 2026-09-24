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

## Ek görsel/ses kuralları (2. tur)

Bu bölümdeki kurallar önceki 14 kuralı **tamamlar**; çelişki olduğunda bu
kurallar geçerlidir (ör. kural 11'deki 4sn sınırı, kural 17'deki 2-3sn'ye
düşürüldü).

### 15. Görsel kaynak önceliği (KRİTİK)

Pexels/Pixabay marka içeriği barındırmadığı için artık **birincil kaynak
değil**. Her sahne için sıra:

- Sahne notu somut bir **rakam** (şirket değeri, teklif tutarı, kullanıcı
  sayısı vb.) ya da **karşılaştırma** (X vs Y) içeriyorsa, doğrudan **kural
  16**'daki üretilen grafiğe gidilir (stok sitede "120 milyar dolar" aramak
  anlamsızdır).
- Diğer tüm sahneler için: **a) Wikimedia Commons** (logo, kurucu fotoğrafı,
  genel merkez, ürün görseli - lisans bilgisiyle) → **b) Wayback Machine**
  (marka-çapa sahnesi ya da "web sitesi" geçen notlar için, şirketin geçmiş
  bir yıldaki web sitesi ekran görüntüsü) → **c) Pexels/Pixabay** (sadece
  genel sahneler için son çare, kural 6'daki alaka filtreleriyle).

**Uygulama:** `src/media_router.py` — `resolve_scene()` bu sırayı uygular;
`src/wikimedia.py` (Commons API, anahtar gerekmez), `src/wayback.py`
(archive.org availability API + Playwright ile ekran görüntüsü).
**Bilinen sınır:** Wayback için şirketin domaini bilinmiyor, `{şirket}.com`
tahmin ediliyor - yanlışsa (site farklı bir domaindeyse) sessizce
atlanıp bir sonraki kaynağa geçilir.

### 16. Üretilen grafikler

Script'te geçen her önemli rakam için otomatik görsel üretilir: büyük
puntolu bir rakam kartı (ör. "120 Milyar $ → 4.8 Milyar $" düşüş anlatımı
için ayrı ayrı iki kart, sırayla). Karşılaştırmalar için iki logoyu (varsa
Wikimedia'dan, yoksa metin olarak) yan yana koyan bir kart üretilir. Tüm
grafikler seri renk paletiyle (`graphics.PALETTE`) tutarlıdır.

**Uygulama:** `src/graphics.py` — `extract_stat()`/`extract_comparison()`
(regex tabanlı tespit), `render_stat_card()`/`render_comparison_card()`
(Pillow ile çizim). `src/media_router.py` bu tespiti her sahnede önce dener.

### 17. Hareket

Hiçbir görsel sabit durmaz: fotoğraf/üretilen grafik sahnelerine Ken Burns
(yavaş zoom) uygulanır (video klipler zaten hareketlidir). Sahne geçişleri
hızlı kesimdir; hiçbir görsel 2-3 saniyeden uzun ekranda kalmaz - sahne
uzunsa aynı sahneye 2-3 farklı görsel atanır.

**Uygulama:** `src/video_builder.py` — `MAX_SCENE_SECONDS = 3.0`; bunu aşan
sahneler aynı notu/sorguyu paylaşan alt-kesimlere bölünür (her alt-kesim,
`used_urls` dedup sayesinde farklı bir aday görsel alma eğilimindedir).
`_build_segment_from_photo()` zoompan filtresiyle Ken Burns uygular.

### 18. Ses tasarımı

Arka plana telifsiz, seslendirmenin belirgin şekilde altında (-18/-22 dB)
gerilimli bir müzik eklenir. Rakam kartları ekrana geldiğinde "whoosh",
twist (dramatik/çöküş) anında "impact" efekti eklenir. Dosyalar
`assets/audio/` klasöründen okunur.

**Uygulama:** `src/audio_mix.py` — `mix()`, `assets/audio/music.mp3`
(-20dB'de döngülenir), `whoosh.mp3` (üretilen grafik sahnelerinin
başlangıcında), `impact.mp3`'ü (ilk dramatik sahnenin başlangıcında) ffmpeg
`amix`/`adelay` filtreleriyle seslendirmenin üzerine bindirir.
**Bilinen sınır:** bu dosyalar repoda YOK - `assets/audio/README.md`
hangi dosyaların nereden bulunup eklenmesi gerektiğini anlatır. Hiçbiri
yoksa bu katman sessizce atlanır, video normal üretilir.

### 19. Ses klonu desteği

`ELEVENLABS_VOICE_ID` `.env`'den okunur; kullanıcı kendi klonlanmış sesine
bu değeri değiştirerek kolayca geçebilir.

**Uygulama:** `src/tts.py` — zaten `os.environ.get("ELEVENLABS_VOICE_ID")
or DEFAULT_VOICE_ID` şeklinde okunuyordu (önceki turda kurulmuştu); bu
kural sadece bunu teyit eder/belgeler.

### 20. İnsan hook desteği

Bir short klasöründe `hook.mp4` (kullanıcının çektiği 2-4 sn'lik dikey
video) varsa, video BUNUNLA (kendi sesiyle) başlar, script'in
seslendirmesi ondan sonra devam eder. Dosya yoksa normal akış çalışır.

**Uygulama:** `src/video_builder.py` — `build_video()`, `hook.mp4`'ü
1080x1920'ye normalize edip (kendi sesini koruyarak) asıl içeriğin önüne
ffmpeg concat ile ekler.

### 21. Doğrulama çıktısı

Her video üretiminden sonra her sahne için kullanılan görselin kaynağı
(Wikimedia/Wayback/üretilen grafik/Pexels-Pixabay/placeholder) ve arama
sorgusu konsola yazdırılır.

**Uygulama:** `src/video_builder.py` — `_build_visual_track()`, her sahne
için `sorgu: "..."  |  kaynak: ...` satırını yazdırır.

---

## Ek düzeltmeler (3. tur — gerçek çalıştırma geri bildirimi)

Bu bölüm, gerçek bir üretimde (Google/Yahoo hikayesi) gözlemlenen somut
hatalardan çıkan kuralları tanımlar; önceki kuralları tamamlar.

### 22. Logo render (kırpma yok, düz zemin)

Wikimedia'dan gelen logolar genelde şeffaf PNG'dir; ffmpeg'in yuv420p
kodlaması şeffaflığı desteklemediği için şeffaf alanlar SİYAHA döner (sadece
logonun dış çizgileri görünür kalır). Bu yüzden her logo, video segmentine
dönüştürülmeden önce düz bir zemine (varsayılan beyaz) tamamı görünecek
şekilde (contain, kırpma yok) kompoze edilir; sadece hafif (en fazla %8) bir
zoom animasyonu uygulanır - agresif Ken Burns kırpması yok.

**Uygulama:** `src/graphics.py` — `compose_logo_on_background()` (PIL ile
alfa kanalını doğru karıştırır); `src/video_builder.py` —
`_build_segment_from_logo()` (kırpmasız hafif zoom). `src/media_router.py`
— `_fetch_logo_scene()` bu iki fonksiyonu birlikte kullanan, "logo" türünde
sonuç döndüren ortak yol.

### 23. Kart tekrarını ve süresini sınırlama

Aynı üretilen kart (rakam/karşılaştırma/logo), tempo sınırı (kural 17) bir
notu birden fazla alt-kesime böldüğünde ya da aynı rakam bir bölümün birden
fazla sahnesinde (notun kendisinde geçmeyip o bölümün seslendirmesinde
geçtiğinde) tekrar tespit edildiğinde, art arda/birden fazla kez
üretilip ekranda olması gerekenden çok daha uzun süre kalmış gibi
görünmesin.

**Uygulama:** `src/video_builder.py` — bir notun alt-kesimlerinden sadece
İLKİ (`allow_generated_card=True`) kart üretebilir. `src/media_router.py`
— `used_stats` seti, aynı rakamın bir video boyunca yalnızca bir kez kart
olarak kullanılmasını garanti eder.

### 24. Rakam kartı içeriği ve eksiksizliği

Rakam kartında SADECE rakam ve 1-3 kelimelik kısa bir etiket görünür (notun
tamamı değil). Script'te seslendirilen (ama görsel notunda birebir
geçmeyebilen) TÜM önemli rakamlar için kart üretilebilmelidir.

**Uygulama:** `src/graphics.py` — `extract_stat()` artık sadece rakamı
döner (eski hâli notun geri kalanını "etiket" diye kullanıyordu - bu bug'dı).
`src/keywords.py` — `clean_stat_label()` Gemini ile (yoksa anahtar kelime
sözlüğüyle) 1-3 kelimelik gerçek bir etiket üretir. `src/video_builder.py`
— her sahnenin notu VE o notun ait olduğu bölümün TAM seslendirmesi
(`beat_narration`) birlikte taranır, böylece bir rakam sadece o cümlede
SÖYLENMİŞ ama görsel notunda YAZILMAMIŞ olsa bile yakalanır.

### 25. Diğer markaların görselleri

Script'te ana konu dışında ismiyle geçen başka bir şirket/marka (ör. bir
teklif/rakip bağlamında) için de mümkünse gerçek logosu gösterilir; iki
marka aynı cümlede/sahnede geçiyorsa yan yana bir karşılaştırma kartı
üretilir.

**Uygulama:** `src/keywords.py` — `detect_other_brands()` (Gemini ile,
best-effort); `src/media_router.py` bunu regex tabanlı "X vs Y" tespitinden
sonraki bir katman olarak dener - 2 marka bulunursa karşılaştırma kartı,
1 marka bulunursa o markanın logo sahnesi üretilir.

### 26. Wayback ve Wikimedia hataları asla sessiz kalmaz

Bu kaynaklardan biri başarısız olursa (ağ hatası, API hatası, Chromium
tarayıcısı eksik/kurulu değil, snapshot bulunamadı vb.) NEDENİ konsola
yazdırılır - sessizce None dönüp bir sonraki kaynağa geçmek, sorunun asla
fark edilmemesine yol açıyordu.

**Uygulama:** `src/wikimedia.py`/`src/wayback.py` — her başarısızlık
noktasında (`[Wikimedia]`/`[Wayback]` önekiyle) açıklayıcı bir `print()`
satırı var; Playwright/Chromium eksikse bunun için özel, eyleme geçirilebilir
bir mesaj (`playwright install chromium` çalıştırma talimatı) verilir.

### 27. Pexels/Pixabay alakasız çıkarsa kart tercih edilir

Hiçbir kaynaktan (Wikimedia, Wayback, Pexels/Pixabay - alaka filtresinden
geçen) uygun bir görsel bulunamazsa, marka logosu son çare olarak denenir;
o da bulunamazsa alakasız bir stok görsel kullanmak yerine notun kendi
metnini gösteren sade bir kart kullanılır. Düz renkli placeholder artık
gerçekten son çaredir (kart üretimi bile başarısız olursa).

**Uygulama:** `src/graphics.py` — `render_text_card()`;
`src/video_builder.py` — `_build_visual_track()`'teki son adım. Ayrıca
`src/relevance.py`'nin Gemini vision prompt'una, gerçek çalıştırmada
gözlemlenen somut hatalı-kabul örnekleri (alakasız vintage bilgisayar,
yangın alarmı, jenerik cam bina) negatif örnek olarak eklendi - bu tür
yüzeysel eşleşmeleri daha güvenilir reddetmesi için.

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
- Kural 25 (`detect_other_brands`) `GEMINI_API_KEY` gerektirir; anahtar
  yoksa diğer markalar sadece notta zaten "X vs Y" gibi açıkça yazılmışsa
  (regex ile) yakalanır, örtük geçen marka isimleri kaçırılabilir.
- Kural 15/22'deki Wayback domain tahmini (`{şirket}.com`) hâlâ bir
  heuristiktir - farklı bir domaindeki şirketler için (ör. `.io`/`.net`
  uzantılı ya da adı domaninden çok farklı olan şirketler) Wayback hiç
  sonuç bulamayabilir; bu artık konsola açıkça yazılır (kural 26), sessiz
  kalmaz.
- Kural 6/27'deki Gemini vision alaka filtresi hâlâ mükemmel değildir -
  somut negatif örneklerle güçlendirildi ama yine de yanlışlıkla "EVET"
  diyebilir; bu durumda tek garanti, sonucun asla markaya tamamen yabancı
  bir görsel olmaması için son çarenin marka logosu/metin kartı olmasıdır,
  vision'ın kendi doğruluğu garanti edilmez.
