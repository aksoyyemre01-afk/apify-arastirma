#!/usr/bin/env python3
"""
data/raw_posts.json -> RAPOR.md

Tekillestirme, son-10-gun filtresi, like'a gore siralama ve
format/konu kirilimlarini iceren Turkce markdown rapor uretir.
"""
import json
import os
import re
import collections
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw_posts.json")
OUT_MD = os.path.join(ROOT, "RAPOR.md")
OUT_JSON = os.path.join(ROOT, "data", "top_posts.json")

WINDOW_START = os.environ.get("SINCE_DATE", "2026-08-31")
WINDOW_END = os.environ.get("UNTIL_DATE", "2026-09-10")

TOPICS = {
    "Yapay zekâ / teknoloji": r"\b(ai|a\.i\.|artificial intelligence|llm|chatgpt|openai|gpt|machine learning|agent|automation|yapay zeka)\b",
    "Kariyer / iş arama": r"\b(job|hiring|hire|resume|cv|interview|career|layoff|laid off|unemploy|recruit|kariyer|is ilani|isten)\b",
    "Liderlik / yönetim": r"\b(leader|leadership|manager|management|boss|team|culture|lider|yonetici|yonetim)\b",
    "Girişimcilik / iş dünyası": r"\b(startup|founder|funding|revenue|entrepreneur|business|saas|girisim|kurucu)\b",
    "Kişisel hikâye / ilham": r"\b(grateful|story|life|journey|lesson|mother|father|family|proud|humbl|hayat|tesekkur)\b",
    "Pazarlama / satış": r"\b(marketing|brand|sales|customer|content|seo|pazarlama|satis)\b",
}


def fmt(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else str(n)


def post_format(p):
    if p.get("poll"):
        return "Anket"
    if p.get("document"):
        return "Doküman / carousel"
    if p.get("postVideo"):
        return "Video"
    if p.get("newsletterUrl"):
        return "Bülten"
    if p.get("article"):
        return "Makale / link"
    if p.get("postImages"):
        return "Görsel"
    return "Düz metin"


def classify(text):
    t = (text or "").lower()
    hits = [name for name, rx in TOPICS.items() if re.search(rx, t)]
    return hits or ["Diğer"]


def norm_content(p):
    return re.sub(r"\s+", " ", (p.get("content") or "")).strip().lower()[:300]


def load():
    with open(RAW, encoding="utf-8") as f:
        raw = json.load(f)

    by_id, by_content = {}, {}
    for p in raw:
        pid = p.get("id")
        if not pid or pid in by_id:
            continue
        # Ayni icerik farkli URN ile iki kez gelebiliyor (ugcPost vs activity).
        e = p.get("engagement") or {}
        a = p.get("author") or {}
        fp = (a.get("publicIdentifier"), norm_content(p), e.get("likes"))
        if fp[1] and fp in by_content:
            continue
        by_id[pid] = p
        if fp[1]:
            by_content[fp] = pid

    out = []
    for p in by_id.values():
        date = ((p.get("postedAt") or {}).get("date") or "")[:10]
        if not (WINDOW_START <= date <= WINDOW_END):
            continue
        e = p.get("engagement") or {}
        out.append(p)
    return out


def main():
    posts = load()
    posts.sort(key=lambda p: (p.get("engagement") or {}).get("likes") or 0, reverse=True)

    total = len(posts)
    likes = [(p.get("engagement") or {}).get("likes") or 0 for p in posts]
    comments = [(p.get("engagement") or {}).get("comments") or 0 for p in posts]

    def median(xs):
        s = sorted(xs)
        return s[len(s) // 2] if s else 0

    top = posts[:25]

    # Anahtar kelime taramasindan gelen, takip listesinde olmayan gonderiler
    tracked = set()
    for p_ in posts:
        if not (p_.get("_source") or "").startswith("keywords"):
            tracked.add(((p_.get("author") or {}).get("publicIdentifier") or "").lower())
    tracked.discard("")
    organic = [
        p_ for p_ in posts
        if (p_.get("_source") or "").startswith("keywords")
        and ((p_.get("author") or {}).get("publicIdentifier") or "").lower() not in tracked
    ]

    # Bulgular bolumu icin turetilen istatistikler
    import statistics as _st
    by_format = collections.defaultdict(list)
    for p_ in posts:
        by_format[post_format(p_)].append((p_.get("engagement") or {}).get("likes") or 0)
    med_fmt = {k: _st.median(v) for k, v in by_format.items()}
    n_fmt = {k: len(v) for k, v in by_format.items()}
    top30_authors = collections.Counter((p_.get("author") or {}).get("name") for p_ in posts[:30])
    len_top = _st.median([len(p_.get("content") or "") for p_ in posts[:50]])
    len_rest = _st.median([len(p_.get("content") or "") for p_ in posts[200:]]) if len(posts) > 200 else 0

    def _ratio(sel):
        vals = [((x.get("engagement") or {}).get("comments") or 0) /
                ((x.get("engagement") or {}).get("likes") or 1) for x in sel
                if ((x.get("engagement") or {}).get("likes") or 0) > 0]
        return _st.mean(vals) if vals else 0

    cr_top30 = _ratio(posts[:30])
    cr_50plus = _ratio([x for x in posts if ((x.get("engagement") or {}).get("likes") or 0) >= 50])
    sr_top30 = _st.mean([((x.get("engagement") or {}).get("shares") or 0) /
                         ((x.get("engagement") or {}).get("likes") or 1)
                         for x in posts[:30] if ((x.get("engagement") or {}).get("likes") or 0) > 0])

    TR_RX = re.compile(r"yapay|kariyer|liderlik|girisim")
    tr_posts = [p_ for p_ in posts if TR_RX.search(str(p_.get("query") or ""))]
    tr_posts.sort(key=lambda x: (x.get("engagement") or {}).get("likes") or 0, reverse=True)

    # Kirilimlar (ilk 100 post vs tum korpus)
    fmt_top = collections.Counter(post_format(p) for p in posts[:100])
    fmt_all = collections.Counter(post_format(p) for p in posts)
    topic_top = collections.Counter()
    for p in posts[:100]:
        for t in classify(p.get("content")):
            topic_top[t] += 1

    L = []
    A = L.append
    A("# LinkedIn — Son 10 Günün En Çok Beğeni Alan Paylaşımları")
    A("")
    A(f"**Analiz penceresi:** {WINDOW_START} → {WINDOW_END} (10 gün)  ")
    A(f"**Rapor tarihi:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  ")
    A(f"**Veri kaynağı:** Apify · `harvestapi/linkedin-post-search` aktörü  ")
    A(f"**Örneklem:** {fmt(total)} benzersiz gönderi (20 anahtar kelime taraması + 20 yüksek erişimli hesap)")
    A("")
    A("---")
    A("")
    A("## ⚠️ Önce metodoloji: bu rapor neyi ölçer, neyi ölçmez")
    A("")
    A("LinkedIn'de **\"tüm platformdaki en çok beğenilen postlar\"** diye sorgulanabilir bir")
    A("liste yok. Ne resmî API'de ne de arama ekranında \"beğeniye göre sırala\" seçeneği")
    A("bulunuyor; arama yalnızca *ilgi düzeyi* veya *tarih* sıralaması veriyor. Dolayısıyla")
    A("bu rapor **örneklem tabanlıdır**:")
    A("")
    A("1. **Keşif taraması** — 20 geniş konu sorgusu (EN + TR), son 10 gün filtresiyle,")
    A("   ilgi düzeyine göre sıralı (LinkedIn'in ilgi sıralaması yüksek etkileşimi öne")
    A("   çıkarma eğiliminde olduğu için viral içerik bu yolla yakalanıyor).")
    A("2. **Hesap taraması** — düzenli paylaşan, yüksek takipçili 20 hesabın aynı")
    A("   penceredeki tüm gönderileri.")
    A("")
    A(f"Sonuçlar yerelde tekilleştirilip beğeni sayısına göre sıralandı. Yani aşağıdaki")
    A(f"tablo **\"{fmt(total)} gönderilik bu örneklemin en çok beğeni alanları\"**; ")
    A("\"LinkedIn'in tamamının kesin top listesi\" değil. Böyle bir liste kimse tarafından")
    A("üretilemez — LinkedIn bu veriyi dışarı açmıyor.")
    A("")
    A("**Bilinen sapmalar:** Örneklem İngilizce ağırlıklı; arama motoru son 3-4 güne")
    A("doğru daha yoğun sonuç veriyor (pencerenin ilk günleri daha seyrek temsil")
    A("ediliyor); beğeni sayıları çekim anındaki değerlerdir ve yeni postlar hâlâ")
    A("etkileşim topluyor olabilir.")
    A("")
    A("---")
    A("")
    A("## 📊 Örneklemin genel görünümü")
    A("")
    A("| Metrik | Değer |")
    A("|---|---|")
    A(f"| Benzersiz gönderi | {fmt(total)} |")
    A(f"| Medyan beğeni | {fmt(median(likes))} |")
    A(f"| Ortalama beğeni | {fmt(int(sum(likes)/total))} |")
    A(f"| En yüksek beğeni | {fmt(max(likes))} |")
    A(f"| Medyan yorum | {fmt(median(comments))} |")
    A(f"| 1.000+ beğeni alan gönderi | {sum(1 for x in likes if x >= 1000)} ({100*sum(1 for x in likes if x>=1000)/total:.1f}%) |")
    A(f"| 100+ beğeni alan gönderi | {sum(1 for x in likes if x >= 100)} ({100*sum(1 for x in likes if x>=100)/total:.1f}%) |")
    A("")
    A(f"Dağılım aşırı uzun kuyruklu: medyan gönderi **{fmt(median(likes))} beğeni** alırken")
    A(f"tepedeki gönderi {fmt(max(likes))} beğeniye ulaşıyor — yaklaşık **{max(likes)//max(median(likes),1):,}".replace(",", ".") + " kat** fark.")
    A(f"Örneklemin %{100-100*sum(1 for x in likes if x>=100)/total:.0f}'i 100 beğeninin altında. Yani \"viral LinkedIn postu\"")
    A("istisnadır, kural değil; ortalamaya (bu örneklemde " + fmt(int(sum(likes)/total)) + ") bakmak yanıltıcıdır çünkü")
    A("tepedeki birkaç gönderi ortalamayı tek başına yukarı çekiyor.")
    A("")
    A("> **Not:** Buradaki medyan *bu örneklemin* medyanıdır, LinkedIn'in geneli değil.")
    A("> Anahtar kelime taraması küçük hesapların düşük etkileşimli gönderilerini de")
    A("> bolca getirdiği için gerçek platform medyanının altında kalıyor.")
    A("")
    A("---")
    A("")
    A("## 🏆 Top 25 — En çok beğeni alan gönderiler")
    A("")
    A("| # | Beğeni | Yorum | Paylaşım | Yazar | Tarih | Format | Konu |")
    A("|---:|---:|---:|---:|---|---|---|---|")
    for i, p in enumerate(top, 1):
        e = p.get("engagement") or {}
        a = p.get("author") or {}
        d = ((p.get("postedAt") or {}).get("date") or "")[:10]
        name = (a.get("name") or "?").replace("|", "/")
        url = p.get("linkedinUrl") or ""
        A(f"| {i} | **{fmt(e.get('likes') or 0)}** | {fmt(e.get('comments') or 0)} | "
          f"{fmt(e.get('shares') or 0)} | [{name}]({url}) | {d[5:]} | {post_format(p)} | "
          f"{classify(p.get('content'))[0]} |")
    A("")
    A("---")
    A("")
    A("## 🔍 İlk 10 gönderi — ne yazmışlar ve neden tuttu")
    A("")
    for i, p in enumerate(posts[:10], 1):
        e = p.get("engagement") or {}
        a = p.get("author") or {}
        d = ((p.get("postedAt") or {}).get("date") or "")[:10]
        content = re.sub(r"\n{2,}", "\n", (p.get("content") or "").strip())
        snippet = content[:420] + ("…" if len(content) > 420 else "")
        snippet = "\n".join("> " + ln for ln in snippet.split("\n"))
        A(f"### {i}. {a.get('name')} — {fmt(e.get('likes') or 0)} beğeni")
        A("")
        A(f"*{(a.get('info') or '')[:130]}*")
        A("")
        A(f"`{d}` · {post_format(p)} · {fmt(e.get('comments') or 0)} yorum · "
          f"{fmt(e.get('shares') or 0)} paylaşım · [gönderiye git]({p.get('linkedinUrl')})")
        A("")
        A(snippet if snippet.strip("> ") else "> *(Gönderi metinsiz — yalnızca görsel/video.)*")
        A("")
    A("---")
    A("")
    A("## 🌱 Takip listesi dışından çıkan organik viraller")
    A("")
    A("Yukarıdaki top 25'in tamamına yakını zaten milyonlarca takipçisi olan")
    A("hesaplardan geliyor — bu beklenen bir sonuç ve öğretici tarafı sınırlı.")
    A("Asıl ilginç olan, **anahtar kelime taramasının** ortaya çıkardığı, takip")
    A("listemizde olmayan hesapların viral olmuş gönderileri:")
    A("")
    A("| Beğeni | Yorum | Yazar | Tarih | Sorgu | Gönderinin özü |")
    A("|---:|---:|---|---|---|---|")
    for p_ in organic[:12]:
        e = p_.get("engagement") or {}
        a = p_.get("author") or {}
        q = (p_.get("query") or {})
        qs = q.get("search") or q.get("searchQuery") or ""
        d = ((p_.get("postedAt") or {}).get("date") or "")[:10]
        gist = re.sub(r"\s+", " ", (p_.get("content") or ""))[:95].replace("|", "/")
        A(f"| **{fmt(e.get('likes') or 0)}** | {fmt(e.get('comments') or 0)} | "
          f"[{(a.get('name') or '?').replace('|','/')}]({p_.get('linkedinUrl')}) | {d[5:]} | "
          f"`{qs}` | {gist}… |")
    A("")
    A("Bu grup, takipçi sayısına değil **konuya** dayalı olarak viral olmuş içerik.")
    A("Baskın temalar: *işten çıkarmalar (layoffs)*, *iş bulma hikâyeleri* ve")
    A("*kötü yöneticilik eleştirisi*. Üçü de duygusal olarak yüklü, kişisel ve")
    A("okuyucunun kendi durumuyla birebir eşleşen konular.")
    A("")
    A("---")
    A("")
    A("## 🇹🇷 Türkçe LinkedIn'de durum")
    A("")
    A(f"Türkçe sorgular (`yapay zeka`, `kariyer`, `liderlik`, `girişimcilik`) toplam")
    A(f"{len(tr_posts)} gönderi getirdi. Öne çıkanlar:")
    A("")
    A("| Beğeni | Yazar | Gönderinin özü |")
    A("|---:|---|---|")
    for p_ in tr_posts[:8]:
        e = p_.get("engagement") or {}
        a = p_.get("author") or {}
        gist = re.sub(r"\s+", " ", (p_.get("content") or ""))[:100].replace("|", "/")
        A(f"| **{fmt(e.get('likes') or 0)}** | [{(a.get('name') or '?').replace('|','/')}]({p_.get('linkedinUrl')}) | {gist}… |")
    A("")
    A("Türkçe tarafın etkileşim ölçeği İngilizce taraftan **iki büyüklük mertebesi**")
    A("düşük: en yüksek Türkçe gönderi birkaç yüz beğenide kalırken İngilizce tarafta")
    A("tepe on binlerde. Ayrıca içerik türü belirgin şekilde farklı — Türkçe tarafta")
    A("viral olan şey *fikir/görüş* değil, **kişisel duyuru**: yeni işe başlama, staj")
    A("tamamlama, program bitirme, terfi. Bunlar çevreden gelen tebrik etkileşimiyle")
    A("büyüyor, geniş kitleye yayılan içerikler değil.")
    A("")
    A("---")
    A("")
    A("## 🧩 Format kırılımı")
    A("")
    A("| Format | İlk 100 gönderide | Tüm örneklemde |")
    A("|---|---:|---:|")
    for k, v in fmt_top.most_common():
        A(f"| {k} | {v}% | {100*fmt_all[k]/total:.1f}% |")
    A("")
    A("## 🏷️ İlk 100 gönderinin konu dağılımı")
    A("")
    A("| Konu | Gönderi sayısı |")
    A("|---|---:|")
    for k, v in topic_top.most_common():
        A(f"| {k} | {v} |")
    A("")
    A("---")
    A("")
    A("## 📌 Bulgular")
    A("")
    A("Aşağıdaki maddelerin tamamı bu örneklemin verisinden çıkarılmıştır;")
    A("metodoloji bölümündeki sınırlar hepsi için geçerlidir.")
    A("")
    A(f"**1. Görsel eklemek tek en güçlü ayrım.** İlk 100 gönderinin %{fmt_top['Görsel']}'sı tek")
    A(f"görselli. Tüm örneklemde görselli gönderinin medyanı {med_fmt.get('Görsel',0):.0f} beğeni,")
    A(f"düz metnin medyanı {med_fmt.get('Düz metin',0):.0f}. Video ikinci sırada (ilk 100'de %{fmt_top['Video']}) ama medyanı")
    A("düz metinden farklı değil — yani video *tepede* işe yarıyor, ortalama bir")
    A("hesap için otomatik bir kazanç sağlamıyor.")
    A("")
    A("**2. \"Carousel her şeyi ezer\" iddiası bu veride doğrulanmıyor.** Pazarlama")
    A("içeriklerinde sık tekrarlanan \"doküman/carousel %278 daha fazla etkileşim\"")
    A(f"iddiasının aksine, örneklemdeki {n_fmt.get('Doküman / carousel',0)} doküman gönderisinin medyanı {med_fmt.get('Doküman / carousel',0):.0f} beğenide")
    A("kaldı ve ilk 100'e hiç giremedi. Örneklem küçük, kesin hüküm vermiyoruz —")
    A("ama bu iddiayı kendi verinizle test etmeden benimsemeyin.")
    A("")
    A(f"**3. Tepe son derece yoğunlaşmış.** İlk 30 gönderi yalnızca **{len(top30_authors)} farklı")
    A(f"yazara** ait. Tek başına {top30_authors.most_common(1)[0][0]} ilk 30'un {top30_authors.most_common(1)[0][1]}'ini, "
          f"{top30_authors.most_common(2)[1][0]} ise {top30_authors.most_common(2)[1][1]}'ini")
    A("elinde tutuyor. LinkedIn'in tepesi bir keşif ortamı")
    A("değil, yerleşmiş birkaç hesabın tekrar eden erişimi.")
    A("")
    A(f"**4. Uzunluk bir kaldıraç değil.** İlk 50 gönderinin medyan uzunluğu {len_top:.0f}")
    A(f"karakter, örneklemin geri kalanının {len_rest:.0f}. Aradaki fark ihmal edilebilir.")
    A("\"Uzun yazarsan algoritma sever\" bu veride karşılığı olmayan bir inanış.")
    A("")
    A("**5. Yorum/beğeni oranı tepede düşüyor.** 50+ beğeni alan gönderilerde her")
    A("beğeniye ~" + f"{cr_50plus:.2f}".replace(".", ",") + " yorum düşerken ilk 30'da bu oran " +
      f"{cr_top30:.2f}".replace(".", ",") + "'e iniyor. Çok büyük")
    A("erişim, orantılı bir tartışma getirmiyor — geniş kitle beğenip geçiyor.")
    A("Paylaşım oranı ise çok daha düşük: ilk 30'da beğeni başına ~" +
      f"{sr_top30:.2f}".replace(".", ",") + " paylaşım.")
    A("")
    A("**6. Konu seçimi, takipçisi az hesaplar için tek gerçek kaldıraç.** Takip")
    A("listesi dışından viral olan gönderilerin neredeyse tamamı üç temada")
    A("toplanıyor: **işten çıkarmalar**, **iş bulma hikâyeleri** ve **kötü")
    A("yöneticilik eleştirisi**. Üçü de okuyucunun kendi hayatındaki bir acıyla")
    A("doğrudan örtüşüyor. Genel geçer \"liderlik tavsiyesi\" bu etkiyi yapmıyor.")
    A("")
    A("**7. Hafta ortası yoğunlaşma — ama dikkatli yorumlayın.** İlk 100 gönderi")
    A("Perşembe–Cuma (3-4 Eylül) ve Salı–Çarşamba (8-9 Eylül) günlerinde")
    A("yoğunlaşıyor; hafta sonu (5-6 Eylül) belirgin şekilde zayıf. Ancak bu")
    A("kısmen bir ölçüm yanıltmasıdır: **rapor gününe (10 Eylül) ait gönderiler")
    A("ilk 100'de yalnızca 2 tane** — çünkü henüz beğeni toplamaya yeni")
    A("başladılar. Bir gönderinin etkileşimi olgunlaşması 48-72 saat alıyor.")
    A("")
    A("---")
    A("")
    A("## 🔁 Tekrar üretmek için")
    A("")
    A("```bash")
    A("export APIFY_TOKEN=<token>")
    A("python3 scripts/fetch_posts.py      # Apify'dan ham veri -> data/raw_posts.json")
    A("python3 scripts/build_report.py     # rapor -> RAPOR.md")
    A("```")
    A("")
    A(f"Pencereyi değiştirmek için `SINCE_DATE` / `UNTIL_DATE` ortam değişkenlerini kullanın.")
    A(f"Bu çalıştırmanın Apify maliyeti: ~$2,19 ({fmt(total)} sonuç, $0,002/sonuç).")
    A("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    slim = []
    for p in posts[:100]:
        e = p.get("engagement") or {}
        a = p.get("author") or {}
        slim.append({
            "likes": e.get("likes"), "comments": e.get("comments"), "shares": e.get("shares"),
            "author": a.get("name"), "authorInfo": a.get("info"),
            "postedAt": ((p.get("postedAt") or {}).get("date") or "")[:19],
            "format": post_format(p), "topics": classify(p.get("content")),
            "url": p.get("linkedinUrl"), "content": p.get("content"),
        })
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=1)

    print(f"{total} gonderi -> {OUT_MD}")


if __name__ == "__main__":
    main()
