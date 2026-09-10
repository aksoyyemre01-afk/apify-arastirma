# LinkedIn içerik paketi / LinkedIn content pack

> **Veri notu / Data note:** Bu oturumda `api.apify.com` ağ politikası tarafından bloklandığı için
> canlı scrape çalıştırılamadı. Aşağıdaki analiz, LinkedIn'de yerleşik olarak yüksek etkileşim alan
> format kalıplarına dayanıyor. Gerçek verilerle doğrulamak için:
> `scripts/linkedin-trend-scraper.mjs` (README'ye bakın).
>
> Live scraping was blocked in this session (`api.apify.com` is not on the egress allowlist), so the
> analysis below reflects established high-engagement LinkedIn format patterns rather than a fresh
> pull. Re-run `scripts/linkedin-trend-scraper.mjs` to validate against live data.

---

## 1. Bu ay tutan içerik tipleri / Content types that are working

| # | Tip / Type | Neden tutuyor / Why it lands |
|---|---|---|
| 1 | **Karşıt görüş** — "Unpopular opinion: ..." | İlk satırda gerilim yaratır, yorum kutusunu tartışmaya açar. Yorum = en ağır sinyal. |
| 2 | **Kişisel hikâye + somut sayı** | Kırılganlık + ölçülebilir sonuç. En yüksek "reshare" oranı buradan gelir. |
| 3 | **Veriye dayalı bulgu** — "We analyzed X, here's what we found" | Otorite kurar, kaydedilir (save), zaman içinde yayılır. |
| 4 | **Çerçeve / adım listesi** (3–5 madde) | Uygulanabilir. Kaydetme ve repost oranı yüksek. |
| 5 | **Şeffaf sayılar / build-in-public** | MRR, kullanıcı, hata maliyeti — gerçek rakam gösteren post nadir, o yüzden dikkat çeker. |
| 6 | **AI'ı işte pratik kullanma** | 2026'nın en kalabalık ama hâlâ en yüksek erişimli teması; jenerik olmayan somut örnek şart. |

### Ortak stil ve ton kuralları / Shared style rules

- **İlk 2 satır her şey.** Mobilde ~200 karakterden sonra "…more" kesiyor. Kancayı oraya sıkıştır.
- **Satır başına bir fikir.** Bol boşluk. Paragraf yok, nefes var.
- **Ton:** birinci tekil şahıs, konuşur gibi, kendinden emin ama kibirsiz. Kurumsal jargon yok.
- **Somut sayı > sıfat.** "Çok hızlandı" değil, "9 saat 40 dakikaya indi".
- **Gövdede dış link yok.** Link ilk yoruma. (Erişimi düşürüyor.)
- **Kapanış:** tek, cevaplaması kolay bir soru. "Ne düşünüyorsunuz?" değil, spesifik bir soru.
- **3–5 hashtag**, sonda, karışık: 1 geniş + 2-3 niş.
- **Uzunluk:** 900–1.500 karakter tatlı nokta. Kısa form (<300) sadece güçlü tek cümlelik iddia için.

---

## 2. Post A — Karşıt görüş + veri / Contrarian + data

### 🇬🇧 English

> Unpopular opinion: most "AI strategies" I see are just a slide deck with a robot icon.
>
> I pulled the last 30 days of posts in my feed and read them properly.
>
> The pattern was hard to miss:
>
> → Everyone is talking about agents.
> → Almost nobody is talking about what broke.
> → Zero posts showed the actual cost per task.
>
> That gap is the whole story.
>
> The teams actually getting value from AI right now are not the ones with the boldest deck. They're the ones who picked one ugly, repetitive process — the one everybody complains about on Monday — and automated it end to end.
>
> One process. Measured. Boring. Working.
>
> Here's the test I use before starting anything:
>
> 1. Can I describe the task in one sentence?
> 2. Do we do it more than 20 times a week?
> 3. Would I notice within a day if it silently failed?
>
> If any answer is no, it's not an AI project yet. It's a slide.
>
> What's the one process on your team that everyone complains about but nobody has automated?
>
> #AI #Automation #DataDriven #ProductStrategy

**Hashtag'ler:** `#AI` `#Automation` `#DataDriven` `#ProductStrategy`

### 🇹🇷 Türkçe

> Pek popüler olmayan bir görüş: gördüğüm "yapay zekâ stratejileri"nin çoğu, üstüne robot ikonu konmuş bir sunumdan ibaret.
>
> Son 30 günde akışıma düşen paylaşımları tek tek okudum.
>
> Tablo net:
>
> → Herkes agent'lardan bahsediyor.
> → Neyin patladığından bahseden neredeyse yok.
> → İşlem başına maliyeti paylaşan tek bir kişi bile yok.
>
> Asıl hikâye tam olarak bu boşlukta.
>
> Şu an yapay zekâdan gerçekten değer üreten ekipler, en iddialı sunumu yapanlar değil. Herkesin pazartesi sabahı şikâyet ettiği o sevimsiz, tekrar eden süreci seçip uçtan uca otomatikleştirenler.
>
> Tek süreç. Ölçülmüş. Sıkıcı. Ve çalışıyor.
>
> Başlamadan önce uyguladığım test:
>
> 1. İşi tek cümleyle anlatabiliyor muyum?
> 2. Haftada 20'den fazla tekrarlanıyor mu?
> 3. Sessizce bozulsa 1 gün içinde fark eder miyim?
>
> Cevaplardan biri "hayır" ise bu henüz bir yapay zekâ projesi değil. Sadece bir slayt.
>
> Sizin ekipte herkesin şikâyet ettiği ama kimsenin otomatikleştirmediği o süreç hangisi?
>
> #YapayZeka #Otomasyon #VeriAnalizi #Teknoloji

**Hashtag'ler:** `#YapayZeka` `#Otomasyon` `#VeriAnalizi` `#Teknoloji`

---

## 3. Post B — Kişisel hikâye + sayı / Personal story + number

### 🇬🇧 English

> Two years ago I spent every Friday copying data between two tabs.
>
> Four hours. Every week. By hand.
>
> I told myself it was "just admin work." It wasn't. It was 200 hours a year I was quietly setting on fire.
>
> The thing that finally changed it wasn't a big platform decision. It was a 60-line script I wrote on a Sunday, half-annoyed, half-curious.
>
> Friday now takes 6 minutes.
>
> But the number I didn't expect is this one: since it stopped being painful, we run that report 4x more often. And because we look at it 4x more often, we caught a pricing mistake in week two that had been running for months.
>
> That's the part nobody tells you about automation.
>
> The time you save is the small win. The behaviour that changes because the friction is gone — that's the real one.
>
> You stop avoiding the thing you should be looking at.
>
> What's the four-hour Friday you're still doing by hand?
>
> #Automation #Productivity #DataAnalytics #LessonsLearned

**Hashtag'ler:** `#Automation` `#Productivity` `#DataAnalytics` `#LessonsLearned`

### 🇹🇷 Türkçe

> İki yıl boyunca her cuma iki sekme arasında veri kopyalayıp yapıştırdım.
>
> Dört saat. Her hafta. Elle.
>
> Kendime "sadece operasyonel iş" dedim. Değildi. Yılda 200 saati sessizce yakıyordum.
>
> Bunu bitiren şey büyük bir platform kararı olmadı. Bir pazar günü, yarı sinirli yarı meraklı yazdığım 60 satırlık bir script oldu.
>
> Cuma artık 6 dakika sürüyor.
>
> Ama beklemediğim sayı şu: iş acı vermeyi bıraktığından beri o raporu 4 kat daha sık çalıştırıyoruz. 4 kat daha sık baktığımız için de aylardır devam eden bir fiyatlama hatasını ikinci hafta yakaladık.
>
> Otomasyonun kimsenin anlatmadığı kısmı burası.
>
> Kazandığın zaman küçük kazanç. Asıl kazanç, sürtünme kalkınca değişen davranış.
>
> Bakman gereken şeyden kaçmayı bırakıyorsun.
>
> Sizin hâlâ elle yaptığınız "dört saatlik cuma" hangisi?
>
> #Otomasyon #Verimlilik #VeriAnalizi #Girişimcilik

**Hashtag'ler:** `#Otomasyon` `#Verimlilik` `#VeriAnalizi` `#Girişimcilik`

---

## 4. Post C — Çerçeve / uygulanabilir liste / Framework post

### 🇬🇧 English

> I've watched a lot of automation projects die in month two.
>
> Never because the tech didn't work. Always because nobody agreed on what "working" meant.
>
> Here's the 4-question filter I now run before a single line of code:
>
> **1. What's the trigger?**
> If you can't say exactly what starts the process, you don't have a process. You have a habit.
>
> **2. What does failure look like?**
> Silent failure is worse than no automation. Decide how it screams before you build it.
>
> **3. Who owns it in six months?**
> Automation without an owner is just technical debt with better PR.
>
> **4. What's the manual fallback?**
> If there isn't one, you haven't automated a process. You've replaced it with a single point of failure.
>
> Four questions. Ten minutes. They've killed more of my bad ideas than any review meeting ever has.
>
> The ones that survive all four tend to still be running a year later.
>
> Which of the four does your team skip most often? Mine used to be #3.
>
> #Automation #Engineering #Leadership #ProcessDesign

**Hashtag'ler:** `#Automation` `#Engineering` `#Leadership` `#ProcessDesign`

### 🇹🇷 Türkçe

> Çok sayıda otomasyon projesinin ikinci ayda öldüğünü gördüm.
>
> Hiçbiri teknoloji çalışmadığı için değil. Hepsi "çalışıyor"un ne demek olduğunda anlaşılmadığı için.
>
> Artık tek satır kod yazılmadan önce uyguladığım 4 soruluk filtre:
>
> **1. Tetikleyici ne?**
> Süreci neyin başlattığını net söyleyemiyorsan elinde süreç yok. Alışkanlık var.
>
> **2. Hata neye benziyor?**
> Sessiz hata, otomasyon olmamasından beterdir. Nasıl bağıracağına kurmadan önce karar ver.
>
> **3. Altı ay sonra sahibi kim?**
> Sahibi olmayan otomasyon, sadece pazarlaması iyi yapılmış teknik borçtur.
>
> **4. Manuel yedek planı ne?**
> Yoksa bir süreci otomatikleştirmemişsindir. Onu tek bir kırılma noktasıyla değiştirmişsindir.
>
> Dört soru. On dakika. Benim kötü fikirlerimi hiçbir değerlendirme toplantısının öldüremediği kadar öldürdüler.
>
> Dördünü de geçenler bir yıl sonra hâlâ çalışıyor oluyor.
>
> Sizin ekip en çok hangisini atlıyor? Bende uzun süre 3 numaraydı.
>
> #Otomasyon #Teknoloji #Liderlik #SüreçYönetimi

**Hashtag'ler:** `#Otomasyon` `#Teknoloji` `#Liderlik` `#SüreçYönetimi`

---

## 5. Hashtag stratejisi / Hashtag strategy

**Kural:** post başına 3–5 tane. Hepsi sonda. 1 geniş + 2–3 niş + 1 topluluk.

| Katman | 🇬🇧 English | 🇹🇷 Türkçe |
|---|---|---|
| Geniş (erişim) | `#AI` `#Technology` `#Leadership` | `#YapayZeka` `#Teknoloji` `#Kariyer` |
| Niş (doğru kitle) | `#Automation` `#DataAnalytics` `#WebScraping` `#ProductStrategy` `#ProcessDesign` | `#Otomasyon` `#VeriAnalizi` `#Verimlilik` `#SüreçYönetimi` |
| Topluluk / anlatı | `#BuildInPublic` `#LessonsLearned` `#FutureOfWork` | `#Girişimcilik` `#DijitalDönüşüm` `#İşDünyası` |

**Kaçınılacaklar:** `#followme`, `#likeforlike`, `#motivation` gibi jenerik ve spam sinyali veren etiketler; 8+ hashtag; gövde içine serpiştirilmiş hashtag'ler.

---

## 6. Yayınlama notları / Publishing notes

- **Zamanlama (TR saati):** Salı–Perşembe 08:30–10:00 veya 13:00–14:00. İngilizce içerik için hedef kitle ABD ise 15:00–17:00 TSİ.
- **İlk 60 dakika kritik.** Postu at, sekmeyi kapatma; gelen yorumlara cümlelerle cevap ver (emoji değil).
- **Link ilk yoruma**, gövdeye değil.
- **Aynı postu iki dilde aynı gün atma.** İngilizceyi salı, Türkçeyi perşembe yayınla — ya da iki ayrı hesaba/sayfaya dağıt.
- **Bir hafta = bir arketip.** A → B → C sırasıyla dön; aynı formatı üst üste iki hafta kullanma.
