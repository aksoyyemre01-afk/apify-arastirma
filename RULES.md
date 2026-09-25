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

**Uygulama:** `src/schemas.py` (`Scene`), `src/script_writer.py` (`SCENE_RULES`),
`src/scene_planner.py` (`_align_scene_starts` sahneyi kelime zamanlamalarına
hizalar; `_validate_comparisons`), `src/logos.py` (Wikidata resmi logo özelliği P154; elle konan
`assets/logos/<marka>.svg|png` önceliklidir; etiket eşleşmesi zorunlu, yanlış
şirketin logosu gelmez), `remotion/src/components.tsx` (`LogoCard`).

## 2. Hook tipine göre marka görünürlüğü

- **Gizemli hook** (hook bir soru/gizem kuruyorsa, ör. "…yapan şirketi biliyor
  musunuz?"): ilk sahnede bağlamı veren somut unsur gösterilir (ilgili rakam,
  karşı taraf şirketin logosu ya da olay yılı); cevap olan marka soru işaretli
  boş kutuyla gizlenir ve **en geç 5. saniyede** impact efektiyle açılır.
- **Doğrudan hook:** ana marka **ilk 3 saniyede** doğrudan görünür.

Gemini her script'te `hook_type` (mystery/direct), `mystery_brand` ve
`reveal_by_seconds` alanlarını üretir.

**Uygulama:** `src/script_writer.py` (`HOOK_RULES`), `src/scene_planner.py`
(`_apply_mystery`: reveal anı markanın sesli söylendiği kelimedir, 5 sn'yi
aşarsa 5 sn'ye çekilir; ilk sahnede gizli kutu yoksa eklenir; reveal anındaki
sahne markayı büyük göstermiyorsa o andan itibaren logo reveal kartı konur;
reveal edilen logo en az 1,3 sn ekranda kalır. `_apply_direct`: ana marka ilk
3 sn'de yoksa ilk sahneye eklenir).

## 3. Doğal, kolay telaffuz edilen Türkçe

Kısa, konuşma diline yakın cümleler; klişe yapay zekâ kalıpları, sesteş
belirsizlikleri (kar/kâr), zor ünsüz kümeleri ve gereksiz yabancı terimler yok.
Rakamlar konuşulduğu gibi ama rakamla yazılır ("44,6 milyar dolar").

**Uygulama:** `src/script_writer.py` (`NARRATION_STYLE_RULES`).

## 4. Güçlü hook, hızlı tempo, merak uyandıran kapanış

İlk cümle en fazla 10 kelime ve 2-3 saniyede bir şok/çelişki/soru kurar. Her
cümle yeni bilgi taşır. Son cümle ve ekrandaki kapanış metni (cta) merak açığı
bırakır; outro kartında gösterilir.

**Uygulama:** `src/script_writer.py` (`HOOK_RULES`), `remotion/src/Short.tsx` (`Outro`).

## 5. Her sahne 2-3 saniye, sürekli hareket

Script her sahneyi 5-10 kelime (~2-3 sn) tutar. **Hiçbir sahne 3 sn'yi geçmez:**
daha uzun bir sahne parçalara bölünür ve ikinci parça FARKLI bir sahne tipidir
(rakam kartı → markanın logo kartı, grafik → son değerin rakam kartı, karşılaştırma →
vurgulanan tarafın logosu, diğerleri → o anda söylenen kelimelerin alıntı kartı).
1 sn'den kısa sahneler komşusundan süre alır. Her sahnede animasyonlu giriş, sürekli
yavaş zoom, sayaç efekti (rakam ve yıllar), çizilen grafikler ve hareketli zemin
vardır; ekran hiç durağan kalmaz.

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
müzik tüm videoda düşük seviyede, whoosh sahne geçişlerinde, impact reveal
anında ve düşüş grafiklerinde. Dosya yoksa o katman sessizce atlanır.
Render'dan sonra ses -14 LUFS'a (true peak -1,5 dBTP) normalize edilir; ElevenLabs
çıktısı ~-24 LUFS geldiği için normalizasyonsuz video neredeyse sessiz duyulur.

**Uygulama:** `src/scene_planner.py` (sfx listesi), `remotion/src/Short.tsx`,
`src/renderer.py` (`normalize_loudness`), `assets/audio/README.md`.

## 9. Haftalık plan

Bir konu 3 short'a bölünür (Pazartesi: giriş/kuruluş, Çarşamba: zirve/kritik
hata, Cuma: çöküş/sonuç); hafta sonu bu üçünü sentezleyen uzun video üretilir.
Outro'da bölüm bilgisi (`config/brand.json` → `outro.next_part_template`) gösterilir.

**Uygulama:** `run.py --mode weekly`, `src/script_writer.py` (`WEEKLY_PARTS`).
Uzun videonun şema ve script'i sahneli üretilir; 16:9 render'ı ikinci aşamadadır.

## 10. İç notlar asla videoda görünmez

Şemada iç not/prompt için bir alan yoktur; ekranda görünen her metin kısadır ve
render öncesi süzülür: köşeli parantez ya da "görsel/sahne/prompt/animasyon/
kamera" gibi kelimeler içeren metin ekrana çıkmaz, uzun metinler kısaltılır.

**Uygulama:** `src/scene_planner.py` (`_clean`, `_BANNED`).

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
