# RULES.md — Short video üretiminin kalıcı kuralları

Bu kurallar **tüm** short'lar için geçerlidir; hiçbiri belirli bir konuya, şirkete
ya da kanala özel değildir. Kod bu kuralları uygular; her kuralın altında hangi
dosyanın onu uyguladığı yazar.

**Temel yaklaşım:** Video görselliği tamamen kodla üretilen hareketli grafiklerden
oluşur (Remotion, `remotion/`). Stok görsel/klip araması yoktur. Script yazılırken
her cümlenin sahne tipi ve içeriği (rakam, etiket, logo, yıl) aynı Gemini
çağrısında yapılandırılmış JSON olarak üretilir.

Sahne tipleri: `logo_intro` (logo açılış/reveal kartı), `big_number` (büyük rakam
kartı + etiket), `comparison` (iki logo yan yana), `timeline` (yıl + olay),
`chart` (yükseliş/düşüş grafiği), `quote` (vurgulu cümle kartı).

---

## 1. Her görsel, o cümlede anlatılanı doğrudan gösterir

Her sahne tek bir kısa cümleye bağlıdır ve o cümle seslendirilirken ekrandadır.
Cümlede rakam varsa rakam kartı, iki taraf varsa karşılaştırma, yıl varsa zaman
çizelgesi, yükseliş/düşüş varsa grafik gösterilir. Gerçek şirket logoları her
zaman düz, açık renkli bir kart üzerinde ve tamamı görünecek şekilde çizilir;
logo bulunamazsa marka adı düzgün bir yazı logosu olur (bozuk/kırpık logo asla).
Karşılaştırma kartının iki tarafı da logosu çekilebilen gerçek bir şirket/ürün
olmak zorundadır; "yeni rakip", "diğerleri" gibi genel ifadeler yasaktır. Bir taraf
geçersizse sahne geçerli tarafın rakam/logo kartına, ikisi de geçersizse alıntı
kartına dönüşür.

**Ekrandaki her yazı söylenenden gelir.** Her metin, etiket, rakam ve büyük gösterilen marka
(logo kartı, karşılaştırma tarafı), o sahne ekrandayken seslendirmede gerçekten söylenen
kelimelerden gelir; söylenmeyen bir isim ya da ifade (script'in özet/yorum alanları dahil)
ekrana çıkmaz. Kelime ve isimler, sahne sırasında söylenmekte olan cümlede geçmelidir;
rakam ve yıllar sıkı zamanlıdır (sahne aralığı ±0,25 sn içinde söylenmelidir - rakam kartı
rakam söylenmeden önce görünmez). Logo çipleri kalıcı bağlam rozetidir: yalnızca videoda
söylenen markalar çip olabilir. Render öncesi söylenmeyen yan alanlar (etiket, grafik
etiketleri, karşılaştırma değeri) kaldırılır; ana içerik söylenmiyorsa sahne, o anda
söylenenden üretilen bir tipe çevrilir (yıl → zaman çizelgesi, rakam → rakam kartı,
marka → logo kartı, aksi halde söylenen kelimelerin alıntısı). Eleştirmen aynı kuralı
word_timings'e göre ölçer; ihlal varsa video geçmez.

**Uygulama:** `src/screen_rules.py` (`enforce`, `violations`), `src/scene_planner.py`
(`build_props`), `agents/critic.py` (`measure_dir`), `src/schemas.py` (`Scene`), `src/script_writer.py` (`SCENE_RULES`),
`src/scene_planner.py` (`_align_scene_starts` sahneyi kelime zamanlamalarına
hizalar; `_validate_comparisons`), `src/logos.py` (Wikidata resmi logo özelliği P154; elle konan
`assets/logos/<marka>.svg|png` önceliklidir; etiket eşleşmesi zorunlu, yanlış
şirketin logosu gelmez), `remotion/src/components.tsx` (`LogoCard`).

## 2. Hook tipine göre marka görünürlüğü

- **Gizemli hook** (hook bir soru/gizem kuruyorsa, ör. "…yapan şirketi biliyor
  musunuz?"): ilk sahnede bağlamı veren somut unsur gösterilir (ilgili rakam,
  karşı taraf şirketin logosu ya da olay yılı); cevap olan marka soru işaretli
  boş kutuyla gizlenir ve **en geç 5. saniyede** impact efektiyle açılır. Marka adı
  seslendirmede **en geç 4,5. saniyede** (metnin ilk ~8 kelimesi içinde) söylenir.
- **Doğrudan hook:** ana marka **ilk 3 saniyede** doğrudan görünür.

Gemini her script'te `hook_type` (mystery/direct), `mystery_brand` ve
`reveal_by_seconds` alanlarını üretir.

**Uygulama:** `src/script_writer.py` (`HOOK_RULES`; `short_problems` markanın söylenme
anını TTS'ten önce yerelde tahmin eder - rakamlar okunuşuyla, cümle duraklamaları dahil -
ve 0,7 sn güvenlik payıyla erken filtreler; bu tahmin açılışta ±0,8 sn sapabildiği için
kesin kontrol TTS'ten sonradır), `run.py` (`_synthesize_checked`: gerçek kelime zamanında
marka 4,5 sn'yi aşarsa `fix_late_brand` ile TEK bir açılış düzeltmesi istenir ve ses BİR
kez yeniden üretilir; hâlâ geçse uyarı verilir), `src/scene_planner.py`
(`_apply_mystery`: reveal anı markanın sesli söylendiği kelimedir, 5 sn'yi
aşarsa 5 sn'ye çekilir; ilk sahnede gizli kutu yoksa eklenir; reveal anındaki
sahne markayı büyük göstermiyorsa o andan itibaren logo reveal kartı konur;
reveal edilen logo en az 1,3 sn ekranda kalır. `_apply_direct`: ana marka ilk
3 sn'de yoksa ilk sahneye eklenir).

## 3. Doğal, kolay telaffuz edilen Türkçe

Kısa, konuşma diline yakın cümleler; klişe yapay zekâ kalıpları, sesteş
belirsizlikleri (kar/kâr), zor ünsüz kümeleri ve gereksiz yabancı terimler yok.
Rakamlar konuşulduğu gibi ama rakamla yazılır ("44,6 milyar dolar").

Seslendirmeye giden metinde ise tüm rakamlar Türkçe yazıyla gönderilir ("11" → "on bir",
"2001'de" → "iki bin birde"); TTS rakamları yanlış okuyamaz. Ekran kartları ve altyazı
rakamla kalır (kelime zamanları orijinal kelimelere geri eşlenir). Her seslendirmeden sonra
ses yerel konuşma tanımayla yazıya dökülür; söylenen rakamlar script'le, ekran kartlarındaki
rakamlar seslendirmeyle eşleşmezse QA başarısız olur. (word_timings.json gönderilen metni
yansıtır, sesi değil; bu kontrol için kullanılamaz.)

**Uygulama:** `src/script_writer.py` (`NARRATION_STYLE_RULES`), `src/tr_numbers.py`,
`src/tts.py` (`spoken_form` + `_regroup`), `src/speech_check.py`, `agents/critic.py` (`measure_dir`).

## 4. Güçlü hook, hızlı tempo, merak uyandıran kapanış

İlk cümle en fazla 10 kelime ve 2-3 saniyede bir şok/çelişki/soru kurar. Her
cümle yeni bilgi taşır. Son cümle ve ekrandaki kapanış metni (cta) merak açığı
bırakır; outro kartında gösterilir.

**Süre: seslendirme 30-45 sn.** Bu ses ~1,95 kelime/sn (boşluksuz ~12 karakter/sn)
konuştuğu için prompt 60-85 kelime ister. Script üretildikten sonra süre, karakter
sayısından yerelde tahmin edilir (gerçek seslendirmelerde ±1,4 sn isabet); aralık
dışındaysa Gemini'ye **yalnızca bir kez** kısaltma/uzatma isteği gider, sonuç hâlâ
uymuyorsa uyarı verilip kullanılır. Ses/model değişirse `SPEECH_CHARS_PER_SEC` ve
`OPENING_CHARS_PER_SEC` yeniden ölçülmelidir.

**Uygulama:** `src/script_writer.py` (`HOOK_RULES`, `enforce_short_constraints`,
`estimate_seconds`), `run.py` (`_report_actual_timing`), `remotion/src/Short.tsx` (`Outro`).

## 5. Her sahne 2-3 saniye, sürekli hareket

Script her sahneyi 5-10 kelime (~2-3 sn) tutar. **Hiçbir sahne 3 sn'yi geçmez:**
daha uzun bir sahne parçalara bölünür ve ikinci parça FARKLI bir sahne tipidir
(rakam kartı → markanın logo kartı, grafik → son değerin rakam kartı, karşılaştırma →
vurgulanan tarafın logosu, diğerleri → o anda söylenen kelimelerin alıntı kartı).
1 sn'den kısa sahneler komşusundan süre alır. **Aynı rakam kartı ya da aynı metin (alıntı,
etiket, yıl, değer) bir videoda en fazla bir kez gösterilir**; bölünen bir sahnenin ikinci
parçası aynı kartı tekrarlamaz, o anda söylenene uygun farklı bir sahneye dönüşür (metinsiz
logo kartı bu kurala girmez). Eleştirmen word_timings'e göre ölçer; tekrar varsa video geçmez. Her sahnede animasyonlu giriş, sayaç
efekti (rakam ve yıllar), çizilen grafikler ve sürekli hareket eden zemin (yavaş zoom
yapan gradyan, kayan ızgara ve parçacıklar) vardır; ekran hiç durağan kalmaz.

**Titreme yok:** yazı, logo ve grafik katmanlarında `scale`/`rotate` kullanılmaz; her
karede yeniden ölçeklenen yazı ve ince çizgiler kenarlarda titrer. Hareket yalnızca
opacity ve tam piksele yuvarlanmış translate ile yapılır, zoom sadece arka plan
gradyanına uygulanır. Nabız efektleri boyutla değil parlaklıkla verilir. Tüm rastgele
değerler Remotion `random(seed)` ile sabittir. Konumlar tam piksel, hareketli katmanlarda
`will-change: transform` var; giriş, sayaç ve çizimlerde yumuşak (bezier) easing kullanılır.
Ölçüm (Enron, 10 kare/sn, durağan anlarda ardışık kare farkı): yazı piksellerinde
0,26-0,83'ten ~0,005'e indi; kalan fark yalnızca arka planın bilinçli hareketi.

Görsel çeşitlilik: zemin tonu sahneye göre hafifçe değişir (yükseliş/zirve
yeşilimsi, düşüş/kayıp kırmızımsı, rakam/logo kartları vurgu rengi, zaman çizelgesi
ve karşılaştırma nötr ton); renkler seri paletinden gelir, zemin yapısı aynı kalır.
Ton, Gemini'nin her sahne için ürettiği `mood` alanından; yoksa grafik yönünden ya da
cümledeki yükseliş/düşüş köklerinden belirlenir.

Sabit ekran bölgeleri: rozet (56-132 px), logo çipleri (168-298 px), sahne içeriği,
altyazı (1250-1510 px). Sahne katmanı zoom'da bile rozet/çip bölgesine taşamaz.

**Uygulama:** `src/scene_planner.py` (`_split_long`, `_alternates`,
`_enforce_min_durations`, `_tone`), `remotion/src/theme.tsx` (`LAYOUT`),
`remotion/src/components.tsx` (`SceneFrame`, `Chips`, `Counter`, `Background`),
`remotion/src/Short.tsx`, `remotion/src/scenes.tsx`.

## 6. Senkron, büyük, kelime vurgulu altyazı

Altyazı ElevenLabs'in kelime zamanlamalarından (`word_timings.json`) üretilir,
en fazla 3 kelimelik sayfalar halinde büyük fontla gösterilir; o an söylenen
kelime vurgu renginde ve hafifçe yukarıdadır. Vurgu kelimenin genişliğini
değiştirmez; kelime aralıkları her durumda korunur. Altyazı YouTube arayüzünün
kapattığı alt bölgenin üstündedir. Ayrıca `captions.srt` yazılır.

**Uygulama:** `src/scene_planner.py` (`_captions`), `remotion/src/Short.tsx` (`Caption`).

## 7. Seri kimliği ayar dosyasındadır

Kanal/seri adı, rozet metni, renk paleti, fontlar, intro ve outro metinleri koda
gömülmez; `config/brand.json`'da (ya da `BRAND_CONFIG` ile verilen dosyada) durur.
Metin alanları boş bırakılabilir: seri adı boşsa video rozetsiz üretilir.

**Uygulama:** `src/brand_config.py`, `config/brand.json`, `remotion/src/theme.tsx`.

## 8. Müzik ve efektler

`assets/audio/` içinde `music.mp3`, `whoosh.mp3`, `impact.mp3` varsa kullanılır:
müzik tüm videoda, whoosh sahne geçişlerinde, impact reveal anında ve düşüş
grafiklerinde. Dosya yoksa o katman sessizce atlanır. whoosh/impact telifsiz olarak
`tools/make_sfx.py` ile sentezlenir; müzik kullanıcının lisanslı dosyasıdır.

**Müzik ve efektler seslendirmeyi asla bastırmaz.** Seviyeler sabit kazançla değil,
seslendirmenin ölçülen seviyesine göre ayarlanır (sabit kazançta whoosh'lar konuşmadan
1-4 dB, impact 6 dB yüksek çıkıyordu; yüksek masterlanmış bir müzik konuşmanın ancak
birkaç dB altında kalıyordu):
- efekt: sesin `whoosh_below_voice_db` (12) / `impact_below_voice_db` (6) altında;
  impact ile aynı ana denk gelen whoosh atlanır;
- müzik: taban seviyesi sesin `music_below_voice_db` (15) altında (müziğin videoda
  kullanılan bölümü ölçülür); konuşma anlarında kelime zamanlarından hesaplanan sabit
  `music_duck_db` (8) ek kısma (80 ms iniş, 350 ms çıkış) - müzik konuşma altında da
  duyulur (kompresörlü ducking ~24 dB kısıp müziği duyulmaz yapıyordu); duraklamalarda
  taban seviyeye döner, sonda `music_fade_out_sec` (2,5) sn'de söner.
Son olarak mix -14 LUFS'a normalize edilir (true peak, 4x örneklemede hafif bir
sınırlayıcıyla -1,5 dBTP'nin altında tutulur); ElevenLabs çıktısı
~-24 LUFS geldiği için normalizasyonsuz video neredeyse sessiz duyulur.
Ölçüm (Enron, çok yüksek masterlanmış -11,5 LUFS test müziğiyle): konuşmalı her 400 ms
pencerede ses müziğin en az 14,3 dB üstünde (medyan 32 dB); whoosh'lar sesin 9-12 dB,
impact'ler 3-4 dB altında.

**Uygulama:** `src/scene_planner.py` (`_sfx_gain`, sfx listesi), `remotion/src/Short.tsx`,
`src/renderer.py` (`add_music`, `speech_spans`, `music_duck_filter`, `normalize_loudness`),
`tools/make_sfx.py`, `assets/audio/README.md`, `config/brand.json` → `audio`.

## 9. Haftalık plan

Bir konu 3 short'a bölünür (Pazartesi: giriş/kuruluş, Çarşamba: zirve/kritik
hata, Cuma: çöküş/sonuç). İki haftada bir (`config/pipeline.json` → `long.every_n_weeks`)
son iki haftanın konularından birinin tam hikâyesi uzun video olarak üretilir (kural 11).
Outro'da bölüm bilgisi (`config/brand.json` → `outro.next_part_template`) gösterilir.

**Uygulama:** `pipeline.py --week` / `--long`, `agents/researcher.py`, `src/script_writer.py` (`WEEKLY_PARTS`).

## 10. İç notlar asla videoda görünmez

Şemada iç not/prompt için bir alan yoktur; ekranda görünen her metin kısadır ve
render öncesi süzülür: köşeli parantez ya da "görsel/sahne/prompt/animasyon/
kamera" gibi kelimeler içeren metin ekrana çıkmaz, uzun metinler kısaltılır.

**Uygulama:** `src/scene_planner.py` (`_clean`, `_BANNED`).

## 11. Uzun video (1920x1080, 5-6 dk)

Yukarıdaki kurallar uzun videoda **aynen** geçerlidir (ekran metni söylenenle uyuşur, tekrar yok,
rakamlar seslendirmede Türkçe yazıyla, müzik 8 dB kelime zamanlı, -14 LUFS, altyazı). Yalnızca
formata özgü şu değerler farklıdır:

- **Sahne süresi:** en uzun sahne 8 sn, fotoğrafta 10 sn (short'taki 3 sn yerine). Uzun sahne
  bölünür; ikinci parça o anda söylenenden üretilen farklı bir karttır.
- **Ekran 4 sn'den fazla sabit kalmaz:** 4 sn'den uzun sahnelerde her ~3,5 sn'de bir yeni öğe
  (o anda söylenen bir kelime/rakamın vurgusu) ekrana girer.
- **Çeşitlilik:** aynı sahne tipi en fazla 60 sn kesintisiz sürer; her 90 sn'lik aralıkta en az 2
  farklı tip vardır.
- **Fotoğraf:** Wikimedia Commons'tan, yalnızca serbest lisanslı (CC0, kamu malı, CC BY, CC BY-SA);
  kişi/kurumun Wikidata resmi görseli (yanlış kişi gelmez). Fotoğraf o ad söylenirken görünür.
  **Yavaş zoom yalnızca üzerinde yazı olmayan fotoğraf katmanında serbesttir**; yazılar sabittir.
  Eser adı, yazar, lisans ve link açıklamaya eklenir.
- **Yapı:** hook (20-30 sn), 3-4 bölüm (her biri seslendirmede okunan başlığıyla bölüm kartı),
  kapanış. YouTube bölüm zaman damgaları gerçek ses zamanlarından (ilki 0:00, her biri >= 10 sn).
- **Uzunluk:** seslendirme en fazla 4.800 karakter (okunuş metni); aşarsa tek bir kısaltma isteği.
- **Küçük resim:** 1280x720; doğrulanmış olgulardan büyük rakam ya da en fazla 5 kelimelik başlık
  + marka logosu.
- **QA:** kod ölçümleri her zaman; görsel QA varsayılan 1 tur (otomatik revizyon döngüsü yok,
  öneriler final onayında sunulur).
- **Bütçe:** ElevenLabs aylık ve Gemini haftalık sınırları short'larla ortaktır; önce short payı
  ayrılır, uzun video kalan bütçeye tahmin + %10 sığmıyorsa ertelenir. Onayla aşılamaz.

**Uygulama:** `agents/long_video.py`, `agents/long_flow.py`, `src/long_planner.py`, `src/commons.py`,
`remotion/src/Short.tsx` (`Long`), `remotion/src/scenes.tsx` (`Photo`, `Chapter`, `Accents`),
`remotion/src/Thumbnail.tsx`, `tests/test_long_limits.py`.

---

## Kalite kontrolü

`python build_video.py --dir <klasör> --frames 2` her 2 saniyede bir kareyi
`kareler/` altına çıkarır; kareler bu kurallara göre gözden geçirilir.

## Bilinen sınırlar

- Logo, Wikidata'daki resmi logo kaydına bağlıdır. Beyaz/şeffaf bir logo açık
  kartta zor görünebilir ya da eski bir logo gelebilir; doğrusunu
  `assets/logos/<marka-slug>.svg|png` olarak koymak yeterlidir.
- Grafik veri noktaları Gemini'den gelir; kesin değer bilinmiyorsa yönü yansıtan
  temsili değerlerdir (ekranda yalnızca gerçek son değer `end_value` yazılır).
- Gemini kotası kısıtlı: 429 (kota) ve diğer hatalar hiç tekrar denenmez; yalnızca 503
  (sunucu yoğun) artan beklemeyle (5/15/45 sn) en fazla 3 kez tekrar denenir.
