# LinkedIn — Son 10 Günün En Çok Beğeni Alan Paylaşımları

**Analiz penceresi:** 2026-08-31 → 2026-09-10 (10 gün)  
**Rapor tarihi:** 2026-09-10  
**Veri kaynağı:** Apify · `harvestapi/linkedin-post-search` aktörü  
**Örneklem:** 1.078 benzersiz gönderi (20 anahtar kelime taraması + 20 yüksek erişimli hesap)

---

## ⚠️ Önce metodoloji: bu rapor neyi ölçer, neyi ölçmez

LinkedIn'de **"tüm platformdaki en çok beğenilen postlar"** diye sorgulanabilir bir
liste yok. Ne resmî API'de ne de arama ekranında "beğeniye göre sırala" seçeneği
bulunuyor; arama yalnızca *ilgi düzeyi* veya *tarih* sıralaması veriyor. Dolayısıyla
bu rapor **örneklem tabanlıdır**:

1. **Keşif taraması** — 20 geniş konu sorgusu (EN + TR), son 10 gün filtresiyle,
   ilgi düzeyine göre sıralı (LinkedIn'in ilgi sıralaması yüksek etkileşimi öne
   çıkarma eğiliminde olduğu için viral içerik bu yolla yakalanıyor).
2. **Hesap taraması** — düzenli paylaşan, yüksek takipçili 20 hesabın aynı
   penceredeki tüm gönderileri.

Sonuçlar yerelde tekilleştirilip beğeni sayısına göre sıralandı. Yani aşağıdaki
tablo **"1.078 gönderilik bu örneklemin en çok beğeni alanları"**; 
"LinkedIn'in tamamının kesin top listesi" değil. Böyle bir liste kimse tarafından
üretilemez — LinkedIn bu veriyi dışarı açmıyor.

**Bilinen sapmalar:** Örneklem İngilizce ağırlıklı; arama motoru son 3-4 güne
doğru daha yoğun sonuç veriyor (pencerenin ilk günleri daha seyrek temsil
ediliyor); beğeni sayıları çekim anındaki değerlerdir ve yeni postlar hâlâ
etkileşim topluyor olabilir.

---

## 📊 Örneklemin genel görünümü

| Metrik | Değer |
|---|---|
| Benzersiz gönderi | 1.078 |
| Medyan beğeni | 4 |
| Ortalama beğeni | 258 |
| En yüksek beğeni | 44.198 |
| Medyan yorum | 0 |
| 1.000+ beğeni alan gönderi | 52 (4.8%) |
| 100+ beğeni alan gönderi | 125 (11.6%) |

Dağılım aşırı uzun kuyruklu: medyan gönderi **4 beğeni** alırken
tepedeki gönderi 44.198 beğeniye ulaşıyor — yaklaşık **11.049 kat** fark.
Örneklemin %88'i 100 beğeninin altında. Yani "viral LinkedIn postu"
istisnadır, kural değil; ortalamaya (bu örneklemde 258) bakmak yanıltıcıdır çünkü
tepedeki birkaç gönderi ortalamayı tek başına yukarı çekiyor.

> **Not:** Buradaki medyan *bu örneklemin* medyanıdır, LinkedIn'in geneli değil.
> Anahtar kelime taraması küçük hesapların düşük etkileşimli gönderilerini de
> bolca getirdiği için gerçek platform medyanının altında kalıyor.

---

## 🏆 Top 25 — En çok beğeni alan gönderiler

| # | Beğeni | Yorum | Paylaşım | Yazar | Tarih | Format | Konu |
|---:|---:|---:|---:|---|---|---|---|
| 1 | **44.198** | 518 | 1.619 | [Brené Brown](https://www.linkedin.com/posts/brenebrown_grateful-for-a-mother-who-warned-her-daughters-activity-7501404699175071744-X9ZG) | 09-03 | Görsel | Liderlik / yönetim |
| 2 | **25.235** | 828 | 2.196 | [Simon Sinek](https://www.linkedin.com/posts/simonsinek_activity-7500994800813420544-wIal) | 09-02 | Görsel | Diğer |
| 3 | **13.751** | 1.409 | 190 | [Steven Bartlett](https://www.linkedin.com/posts/stevenbartlett-123_i-just-turned-34-i-learnt-a-lot-this-ugcPost-7500314314478780416-izSd) | 09-03 | Görsel | Girişimcilik / iş dünyası |
| 4 | **8.969** | 212 | 145 | [Melinda French Gates](https://www.linkedin.com/posts/melindagates_some-of-the-most-iconic-artists-use-their-activity-7500331246602956800--Krh) | 08-31 | Görsel | Liderlik / yönetim |
| 5 | **8.738** | 1.497 | 337 | [Justin Welsh](https://www.linkedin.com/posts/justinwelsh_if-success-costs-you-your-health-marriage-activity-7500882312734199808-12-y) | 09-02 | Görsel | Girişimcilik / iş dünyası |
| 6 | **8.342** | 269 | 384 | [Adam Grant](https://www.linkedin.com/posts/adammgrant_activity-7502028301742403584-4dHK) | 09-05 | Görsel | Diğer |
| 7 | **7.843** | 383 | 458 | [Simon Sinek](https://www.linkedin.com/posts/simonsinek_activity-7502727707487653888-73OR) | 09-07 | Görsel | Diğer |
| 8 | **7.834** | 751 | 672 | [Bill Gates](https://www.linkedin.com/posts/williamhgates_ive-had-a-number-of-thoughtful-and-engaging-activity-7501738402128715777-2w69) | 09-04 | Video | Yapay zekâ / teknoloji |
| 9 | **6.761** | 622 | 224 | [Steven Bartlett](https://www.linkedin.com/posts/stevenbartlett-123_underpricing-yourself-is-one-of-the-most-activity-7503061892907552768-bx4S) | 09-08 | Video | Girişimcilik / iş dünyası |
| 10 | **6.321** | 261 | 466 | [Andrew Ng](https://www.linkedin.com/posts/andrewyng_the-most-important-skills-for-using-ai-coding-activity-7501655987133681666-MHap) | 09-04 | Makale / link | Yapay zekâ / teknoloji |
| 11 | **5.489** | 1.202 | 235 | [Justin Welsh](https://www.linkedin.com/posts/justinwelsh_your-job-thinks-youre-worth-more-than-they-activity-7501607086317916160-mZKO) | 09-04 | Görsel | Kariyer / iş arama |
| 12 | **4.922** | 294 | 356 | [Satya Nadella](https://www.linkedin.com/posts/satyanadella_it-was-a-great-week-for-innovation-across-activity-7502385664945111040-uGka) | 09-06 | Video | Diğer |
| 13 | **4.549** | 1.204 | 198 | [Justin Welsh](https://www.linkedin.com/posts/justinwelsh_if-youre-great-at-what-you-do-but-nobody-activity-7503419032046497792-xskg) | 09-09 | Görsel | Girişimcilik / iş dünyası |
| 14 | **4.319** | 317 | 213 | [Richard Branson](https://www.linkedin.com/posts/rbranson_a-message-for-anyone-who-might-be-going-through-activity-7502639947804250114-QtHV) | 09-07 | Video | Diğer |
| 15 | **4.070** | 205 | 48 | [Richard Branson](https://www.linkedin.com/posts/rbranson_happy-birthday-virgin-australia-26-years-activity-7500239515551268864-TeVE) | 08-31 | Görsel | Diğer |
| 16 | **3.967** | 191 | 482 | [Satya Nadella](https://www.linkedin.com/posts/satyanadella_super-excited-about-hydrafusion-in-github-activity-7501674820452069376-H5T7) | 09-04 | Video | Diğer |
| 17 | **3.881** | 560 | 192 | [Richard Branson](https://www.linkedin.com/posts/rbranson_failure-lessons-mindset-activity-7501313292619919360-HXqx) | 09-03 | Görsel | Liderlik / yönetim |
| 18 | **3.713** | 1.067 | 95 | [Justin Welsh](https://www.linkedin.com/posts/justinwelsh_most-entrepreneurs-try-to-build-a-business-activity-7503056641819402240-19iT) | 09-08 | Görsel | Yapay zekâ / teknoloji |
| 19 | **3.704** | 116 | 262 | [Satya Nadella](https://www.linkedin.com/posts/satyanadella_gpt-6-astra-frontier-intelligence-for-work-activity-7501479712469450753-KUuq) | 09-04 | Makale / link | Diğer |
| 20 | **3.513** | 1.115 | 131 | [Justin Welsh](https://www.linkedin.com/posts/justinwelsh_comfort-is-overrated-a-lot-of-people-want-activity-7500519924076027905-2oG0) | 09-01 | Görsel | Girişimcilik / iş dünyası |
| 21 | **3.463** | 364 | 295 | [Bill Gates](https://www.linkedin.com/posts/williamhgates_fda-approves-a-new-blood-test-to-detect-signs-activity-7501466755261820928-k89N) | 09-04 | Makale / link | Diğer |
| 22 | **3.393** | 261 | 278 | [Simon Sinek](https://www.linkedin.com/posts/simonsinek_arrogance-is-thinking-something-is-perfect-activity-7501641686561857537-K8jN) | 09-04 | Video | Girişimcilik / iş dünyası |
| 23 | **3.216** | 1.140 | 208 | [Bill Gates](https://www.linkedin.com/posts/williamhgates_ive-been-thinking-a-lot-about-the-idea-of-activity-7503320303024926720-1t50) | 09-09 | Düz metin | Yapay zekâ / teknoloji |
| 24 | **3.170** | 1.000 | 89 | [Justin Welsh](https://www.linkedin.com/posts/justinwelsh_there-are-three-important-decisions-that-activity-7502694251907104768-Q8f4) | 09-07 | Görsel | Liderlik / yönetim |
| 25 | **2.916** | 323 | 168 | [Steven Bartlett](https://www.linkedin.com/posts/stevenbartlett-123_the-first-30-minutes-after-waking-up-could-activity-7501172522868989952-PNup) | 09-03 | Video | Diğer |

---

## 🔍 İlk 10 gönderi — ne yazmışlar ve neden tuttu

### 1. Brené Brown — 44.198 beğeni

*University of Houston + University of Texas at Austin | Researcher. Storyteller. Courage-builder.*

`2026-09-03` · Görsel · 518 yorum · 1.619 paylaşım · [gönderiye git](https://www.linkedin.com/posts/brenebrown_grateful-for-a-mother-who-warned-her-daughters-activity-7501404699175071744-X9ZG)

> Grateful for a mother who warned her daughters about the price she paid for trying to conform to nice girl culture in the 1950’s. We didn’t know all of the details of her wounds, but we fully understood the depth of her pain. 
> When she died she had framed pictures of Gloria Steinem and Angela Davis over her desk.
> Grateful for the women who lead the way. 👊🏼
> Quote: Gloria Steinem’s remarks at the National Organization …

### 2. Simon Sinek — 25.235 beğeni

*Optimist, New York Times bestselling author of "Start with Why" and "The Infinite Game", and founder of The Optimism Company*

`2026-09-02` · Görsel · 828 yorum · 2.196 paylaşım · [gönderiye git](https://www.linkedin.com/posts/simonsinek_activity-7500994800813420544-wIal)

> *(Gönderi metinsiz — yalnızca görsel/video.)*

### 3. Steven Bartlett — 13.751 beğeni

*Founder: Steven.com The Creator Economy Company, home to FlightStory & FlightCast.*

`2026-09-03` · Görsel · 1.409 yorum · 190 paylaşım · [gönderiye git](https://www.linkedin.com/posts/stevenbartlett-123_i-just-turned-34-i-learnt-a-lot-this-ugcPost-7500314314478780416-izSd)

> I just turned 34! 🎂 I LEARNT A LOT this year... Here are 3 things that might help ya 👇🏾
> 🔋 1. Energy is the foundational currency of life. 
> I recently interviewed the leading mitochondria expert and the neuroscientist who popularised the idea of our finite daily "body budget." 
> In this very noisy season of my life, every distraction, opportunity (they look the same), or social media scroll presents a temptation to spe…

### 4. Melinda French Gates — 8.969 beğeni

*Founder of Pivotal. Co-founder of the Gates Foundation. Author of The Moment of Lift & The Next Day.*

`2026-08-31` · Görsel · 212 yorum · 145 paylaşım · [gönderiye git](https://www.linkedin.com/posts/melindagates_some-of-the-most-iconic-artists-use-their-activity-7500331246602956800--Krh)

> Some of the most iconic artists use their platforms to inspire action, and that’s exactly what Olivia Rodrigo did with Daisy Chain Fields.
>  
> She turned the energy of a music festival into meaningful support for women and girls, bringing together an electric all-women lineup and 45,000 fans to raise millions for organizations doing vital work.
>  
> It’s the kind of leadership that gives me so much hope for the future, an…

### 5. Justin Welsh — 8.738 beğeni

*Writer & Entrepreneur. I write The Saturday Essay for 200,000+ ambitious people living and working on their own terms.*

`2026-09-02` · Görsel · 1.497 yorum · 337 paylaşım · [gönderiye git](https://www.linkedin.com/posts/justinwelsh_if-success-costs-you-your-health-marriage-activity-7500882312734199808-12-y)

> If success costs you your health, marriage, and time, you've made a terrible trade.
> Of course, work is incredibly easy to measure.
> The big titles, multiple awards, maybe a lot of followers, and certainly all that revenue.
> It'll never be as interesting to post about getting 8 hours of sleep, or hanging out with your spouse, or having a completely free day.
> So, naturally, you end up with a very warped definition of suc…

### 6. Adam Grant — 8.342 beğeni

*Organizational psychologist at Wharton, #1 NYT bestselling author of THINK AGAIN, host of the TED podcast Re:Thinking*

`2026-09-05` · Görsel · 269 yorum · 384 paylaşım · [gönderiye git](https://www.linkedin.com/posts/adammgrant_activity-7502028301742403584-4dHK)

> *(Gönderi metinsiz — yalnızca görsel/video.)*

### 7. Simon Sinek — 7.843 beğeni

*Optimist, New York Times bestselling author of "Start with Why" and "The Infinite Game", and founder of The Optimism Company*

`2026-09-07` · Görsel · 383 yorum · 458 paylaşım · [gönderiye git](https://www.linkedin.com/posts/simonsinek_activity-7502727707487653888-73OR)

> *(Gönderi metinsiz — yalnızca görsel/video.)*

### 8. Bill Gates — 7.834 beğeni

*Chair, Gates Foundation and Founder, Breakthrough Energy*

`2026-09-04` · Video · 751 yorum · 672 paylaşım · [gönderiye git](https://www.linkedin.com/posts/williamhgates_ive-had-a-number-of-thoughtful-and-engaging-activity-7501738402128715777-2w69)

> I’ve had a number of thoughtful and engaging conversations since sharing my memo on AI. Here are some of the most interesting questions I’ve received:

### 9. Steven Bartlett — 6.761 beğeni

*Founder: Steven.com The Creator Economy Company, home to FlightStory & FlightCast.*

`2026-09-08` · Video · 622 yorum · 224 paylaşım · [gönderiye git](https://www.linkedin.com/posts/stevenbartlett-123_underpricing-yourself-is-one-of-the-most-activity-7503061892907552768-bx4S)

> Underpricing yourself is one of the most expensive habits in business...👇🏾
> Excited to get to work with Nathan shortly! 
> Agree or disagree?
> Dragon's Den

### 10. Andrew Ng — 6.321 beğeni

*DeepLearning.AI, AI Fund and AI Aspire*

`2026-09-04` · Makale / link · 261 yorum · 466 paylaşım · [gönderiye git](https://www.linkedin.com/posts/andrewyng_the-most-important-skills-for-using-ai-coding-activity-7501655987133681666-MHap)

> The most important skills for using AI coding agents effectively. Presenting the AI Engineering Skills Map for using coding agents.

---

## 🌱 Takip listesi dışından çıkan organik viraller

Yukarıdaki top 25'in tamamına yakını zaten milyonlarca takipçisi olan
hesaplardan geliyor — bu beklenen bir sonuç ve öğretici tarafı sınırlı.
Asıl ilginç olan, **anahtar kelime taramasının** ortaya çıkardığı, takip
listemizde olmayan hesapların viral olmuş gönderileri:

| Beğeni | Yorum | Yazar | Tarih | Sorgu | Gönderinin özü |
|---:|---:|---|---|---|---|
| **1.644** | 90 | [Claudia Robbins](https://www.linkedin.com/posts/claudia-robbins-714a9b205_some-managers-can-show-you-the-rest-can-activity-7501251336022384640-xJ8R) | 09-03 | `management` | Some managers can show you. The rest can only tell you. A manager who can't do the job can't le… |
| **1.038** | 41 | [Summer Chang](https://www.linkedin.com/posts/summerchang_if-youre-looking-for-a-job-linkedin-isn-activity-7502380901662916608--tjO) | 09-06 | `job search` | If you’re looking for a job, LinkedIn isn’t the only place to look. I’ve been testing different… |
| **751** | 73 | [Nichole H.](https://www.linkedin.com/posts/activity-7503491246678724608-PzAq) | 09-09 | `job search` | After what feels like a million applications, countless resumes sent, and way too many moments … |
| **552** | 75 | [Jenna O'Connor CLMP](https://www.linkedin.com/posts/jennaoconnor_layoffs-careertransition-workplaceculture-activity-7502149320037773312-jERH) | 09-05 | `layoffs` | There is a side of corporate layoffs that people rarely talk about on here, and it isn't the fi… |
| **516** | 17 | [Carlos A Perez](https://www.linkedin.com/posts/carlos-a-perez-20085674_leadership-servantleadership-teamwork-activity-7501526933168357376-sACi) | 09-04 | `leadership` | Leadership isn’t about getting more out of people. It’s about creating an environment where gre… |
| **388** | 11 | [Jimmy Brown](https://www.linkedin.com/posts/jimmy-d-brown_my-heart-breaks-seeing-all-the-posts-from-activity-7503277642595581953-Ox40) | 09-09 | `layoffs` | My heart breaks seeing all the posts from my fellow coworkers and friends at Centene Corporatio… |
| **379** | 95 | [Lloyd Birch](https://www.linkedin.com/posts/lloydbirch_youre-not-a-ceo-stop-it-unless-you-activity-7501211167923535872-JK7W) | 09-03 | `CEO` | 🌶️ You’re not a CEO. Stop it. Unless you’ve been appointed to lead an executive team, CEO isn’t… |
| **332** | 3 | [Daniela Rus](https://www.linkedin.com/posts/daniela-rus-220b3_mitcsail-phd-computerscience-activity-7503571250938544128-Sh9h) | 09-09 | `artificial intelligence` | Today we welcomed our first-year PhD students to MIT Computer Science and Artificial Intelligen… |
| **329** | 39 | [Maid Dizdarevic](https://www.linkedin.com/posts/maid-dizdarevic_if-being-laid-off-has-made-your-job-search-activity-7503067998921068544-YGir) | 09-08 | `layoffs` | If being laid off has made your job search harder than you expected, start here: https://lnkd.i… |
| **322** | 106 | [Harry Stebbings](https://www.linkedin.com/posts/harrystebbings_founder-funding-business-activity-7500893560158834688-zHkM) | 09-02 | `startup` | European founders are fundamentally disadvantaged in a venture world today. Why? Today, every s… |
| **299** | 49 | [Scott Keyser](https://www.linkedin.com/posts/scott-f-keyser_the-worst-thing-you-can-do-it-take-career-activity-7503467589646430209--vRP) | 09-09 | `career advice` | The worst thing you can do it take career advice from the people who love you. I learned that t… |
| **298** | 27 | [Sam Khoury](https://www.linkedin.com/posts/sam-khoury-432a78166_i-wasnt-really-sure-how-to-comment-on-yesterday-activity-7502022514001453056-EgzM) | 09-05 | `layoffs` | I wasn’t really sure how to comment on yesterday’s layoffs at The Trade Desk. TTD has always be… |

Bu grup, takipçi sayısına değil **konuya** dayalı olarak viral olmuş içerik.
Baskın temalar: *işten çıkarmalar (layoffs)*, *iş bulma hikâyeleri* ve
*kötü yöneticilik eleştirisi*. Üçü de duygusal olarak yüklü, kişisel ve
okuyucunun kendi durumuyla birebir eşleşen konular.

---

## 🇹🇷 Türkçe LinkedIn'de durum

Türkçe sorgular (`yapay zeka`, `kariyer`, `liderlik`, `girişimcilik`) toplam
197 gönderi getirdi. Öne çıkanlar:

| Beğeni | Yazar | Gönderinin özü |
|---:|---|---|
| **227** | [Gebze Technical University](https://www.linkedin.com/posts/gebze-teknik-%C3%BCniversitesi_gebzeteknik-gtaes-yapayzeka-activity-7501172277590343680-cxAH) | Yapay zeka devriminde Türkiye'nin endüstriyel gücünü merkeze alan bir vizyonla, üniversitemiz bünyes… |
| **210** | [Evrim Tuncay](https://www.linkedin.com/posts/evrim-tuncay-28908456_ki%C5%9Fisel-%C3%BClkem-ve-t%C3%BCm-meslekta%C5%9Flar%C4%B1m-ad%C4%B1na-activity-7501584163108700160-SBAp) | Kişisel, ülkem ve tüm meslektaşlarım adına gurur duyduğum bir gelişmeyi sizlerle paylaşmak isterim. … |
| **97** | [Elif Doğan](https://www.linkedin.com/posts/elif-do%C4%9Fan-50156229a_merchandising-textileindustry-ai-activity-7502735674450751489-1pgk) | Li & Fung LF Young Talent'26 kapsamında, Merchandising departmanında gerçekleştirdiğim stajımı tamam… |
| **89** | [Ayşe Betül Yılmaz](https://www.linkedin.com/posts/aysebetulyilmaz_newjob-salesengineer-peri-activity-7500931930780180482-jnu-) | I’m happy to share that I’ve started my new position as a Sales Engineer at PERI / PERI Türkiye! Exc… |
| **79** | [Taha Ersel T.](https://www.linkedin.com/posts/taha-ersel-tas_bir-yolculu%C4%9Fun-daha-sonu-geldi-bug%C3%BCn-ye%C5%9Filova-activity-7503729307807281155-ECrE) | Bir yolculuğun daha sonu geldi, bugün Yeşilova’daki son günüm. Yaklaşık 6 yıl boyunca İş Geliştirme,… |
| **72** | [Alper Tunaboylu](https://www.linkedin.com/posts/alper-tunaboylu-07101215_leadership-leadershipdevelopment-ericsson-activity-7503053724487933952-wCbu) | Ericsson’un Experienced Leaders’ Program (ELP) programını tamamlamış olmaktan mutluluk duyuyorum. Be… |
| **67** | [Elif Nur Arslan](https://www.linkedin.com/posts/elif-nur-arslan-_tr-bazen-insan-tam-olarak-nereye-ait-oldu%C4%9Funu-activity-7503172715806228480-xBlO) | TR Bazen insan tam olarak nereye ait olduğunu ve ne üretmek istediğini zamanla, deneyimledikçe anlıy… |
| **64** | [Cansu Deniz](https://www.linkedin.com/posts/cansu-deniz-a01963282_taesbiaovtak-biaovlgem-yte-activity-7502694049850552321-_40C) | TÜBİTAK BİLGEM YTE’de gerçekleştirdiğim staj sürecini tamamlamış olmanın mutluluğunu yaşıyorum. YTE … |

Türkçe tarafın etkileşim ölçeği İngilizce taraftan **iki büyüklük mertebesi**
düşük: en yüksek Türkçe gönderi birkaç yüz beğenide kalırken İngilizce tarafta
tepe on binlerde. Ayrıca içerik türü belirgin şekilde farklı — Türkçe tarafta
viral olan şey *fikir/görüş* değil, **kişisel duyuru**: yeni işe başlama, staj
tamamlama, program bitirme, terfi. Bunlar çevreden gelen tebrik etkileşimiyle
büyüyor, geniş kitleye yayılan içerikler değil.

---

## 🧩 Format kırılımı

| Format | İlk 100 gönderide | Tüm örneklemde |
|---|---:|---:|
| Görsel | 46% | 23.1% |
| Video | 24% | 19.8% |
| Düz metin | 19% | 37.9% |
| Makale / link | 5% | 11.1% |
| Bülten | 5% | 4.6% |
| Anket | 1% | 1.9% |

## 🏷️ İlk 100 gönderinin konu dağılımı

| Konu | Gönderi sayısı |
|---|---:|
| Kişisel hikâye / ilham | 32 |
| Diğer | 30 |
| Girişimcilik / iş dünyası | 30 |
| Kariyer / iş arama | 22 |
| Liderlik / yönetim | 18 |
| Yapay zekâ / teknoloji | 18 |
| Pazarlama / satış | 7 |

---

## 📌 Bulgular

Aşağıdaki maddelerin tamamı bu örneklemin verisinden çıkarılmıştır;
metodoloji bölümündeki sınırlar hepsi için geçerlidir.

**1. Görsel eklemek tek en güçlü ayrım.** İlk 100 gönderinin %46'sı tek
görselli. Tüm örneklemde görselli gönderinin medyanı 13 beğeni,
düz metnin medyanı 3. Video ikinci sırada (ilk 100'de %24) ama medyanı
düz metinden farklı değil — yani video *tepede* işe yarıyor, ortalama bir
hesap için otomatik bir kazanç sağlamıyor.

**2. "Carousel her şeyi ezer" iddiası bu veride doğrulanmıyor.** Pazarlama
içeriklerinde sık tekrarlanan "doküman/carousel %278 daha fazla etkileşim"
iddiasının aksine, örneklemdeki 16 doküman gönderisinin medyanı 4 beğenide
kaldı ve ilk 100'e hiç giremedi. Örneklem küçük, kesin hüküm vermiyoruz —
ama bu iddiayı kendi verinizle test etmeden benimsemeyin.

**3. Tepe son derece yoğunlaşmış.** İlk 30 gönderi yalnızca **10 farklı
yazara** ait. Tek başına Justin Welsh ilk 30'un 9'ini, Simon Sinek ise 4'ini
elinde tutuyor. LinkedIn'in tepesi bir keşif ortamı
değil, yerleşmiş birkaç hesabın tekrar eden erişimi.

**4. Uzunluk bir kaldıraç değil.** İlk 50 gönderinin medyan uzunluğu 596
karakter, örneklemin geri kalanının 574. Aradaki fark ihmal edilebilir.
"Uzun yazarsan algoritma sever" bu veride karşılığı olmayan bir inanış.

**5. Yorum/beğeni oranı tepede düşüyor.** 50+ beğeni alan gönderilerde her
beğeniye ~0,18 yorum düşerken ilk 30'da bu oran 0,14'e iniyor. Çok büyük
erişim, orantılı bir tartışma getirmiyor — geniş kitle beğenip geçiyor.
Paylaşım oranı ise çok daha düşük: ilk 30'da beğeni başına ~0,05 paylaşım.

**6. Konu seçimi, takipçisi az hesaplar için tek gerçek kaldıraç.** Takip
listesi dışından viral olan gönderilerin neredeyse tamamı üç temada
toplanıyor: **işten çıkarmalar**, **iş bulma hikâyeleri** ve **kötü
yöneticilik eleştirisi**. Üçü de okuyucunun kendi hayatındaki bir acıyla
doğrudan örtüşüyor. Genel geçer "liderlik tavsiyesi" bu etkiyi yapmıyor.

**7. Hafta ortası yoğunlaşma — ama dikkatli yorumlayın.** İlk 100 gönderi
Perşembe–Cuma (3-4 Eylül) ve Salı–Çarşamba (8-9 Eylül) günlerinde
yoğunlaşıyor; hafta sonu (5-6 Eylül) belirgin şekilde zayıf. Ancak bu
kısmen bir ölçüm yanıltmasıdır: **rapor gününe (10 Eylül) ait gönderiler
ilk 100'de yalnızca 2 tane** — çünkü henüz beğeni toplamaya yeni
başladılar. Bir gönderinin etkileşimi olgunlaşması 48-72 saat alıyor.

---

## 🔁 Tekrar üretmek için

```bash
export APIFY_TOKEN=<token>
python3 scripts/fetch_posts.py      # Apify'dan ham veri -> data/raw_posts.json
python3 scripts/build_report.py     # rapor -> RAPOR.md
```

Pencereyi değiştirmek için `SINCE_DATE` / `UNTIL_DATE` ortam değişkenlerini kullanın.
Bu çalıştırmanın Apify maliyeti: ~$2,19 (1.078 sonuç, $0,002/sonuç).
