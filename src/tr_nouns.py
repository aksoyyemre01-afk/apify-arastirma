"""Uzun video anahtar kelime kartları ve vurgu öğeleri için isim seçimi (RULES.md kural 11).

Yalnızca isim ya da isim tamlaması, YALIN hâlde (ek almamış) gösterilir: "vaatler" -> "vaat",
"laboratuvarı" -> "laboratuvar", "sahte vaatler" -> "sahte vaat". Çekimli fiil, ortaç ve fiilden
türemiş kelimeler ("çalışan", "geliştirilen", "büyüleyici", "kaçınılmazdı") ile tek başına anlamsız
kalan genel isimler ("yapı", "dönem", "şey") seçilmez; uygun kelime yoksa hiçbir şey seçilmez.
Biçimbilim çözümlemesi yerel `zeyrek` kütüphanesiyle yapılır (API yok).
"""

import logging
import re
from functools import lru_cache

# Tek başına anlamsız kalan / içeriksiz genel isimler.
_GENERIC = {
    "şey", "yapı", "dönem", "süre", "yıl", "kez", "taraf", "kısım", "durum", "şekil", "zaman", "sonuç", "ara",
    "yer", "gün", "ay", "hafta", "tarih", "bölüm", "kişi", "insan", "dünya", "alan", "biçim", "konu", "olay",
    "sıra", "nokta", "parça", "türlü", "çeşit", "yan", "baş", "son", "ilk", "iç", "dış", "üst", "alt", "hayat",
    "gerçek", "büyük", "büyüklük", "fazla", "tüm", "her", "bütün", "hikaye", "hikâye", "ad", "isim",
    "üzer", "üzeri", "orta", "ön", "yok", "peş", "var", "kurul",
    # birimler / ölçüler: tek başına anlam taşımaz
    "dolar", "dolarlık", "milyar", "milyarlık", "milyon", "milyonluk", "lira", "yıllık", "aylık", "kat", "adet", "yüzde",
    "çıkma", "şirket", "eski", "yeni", "beri", "sıfır", "ortay", "peşin", "arka", "karşı", "taraf", "yüz", "kere", "defa", "tür", "biri", "hepsi",
}
# Niteleyici sayılmayan belirteçler ("bir cihaz", "bu yapı").
_DETERMINERS = {"bir", "bu", "şu", "o", "her", "tüm", "bütün", "aynı", "hiçbir", "birçok", "çok", "az", "diğer", "başka",
                "bazı", "kimi", "birkaç", "hangi", "ne", "bunca", "öyle", "böyle"}
# 4 harften kısa ama tek başına anlamlı isimler.
_SHORT_OK = {"sır", "kan", "hız", "suç", "dev", "jüri", "ceza", "kar", "kâr"}
_analyzer = None


def _az():
    global _analyzer
    if _analyzer is None:
        import zeyrek
        import zeyrek.morphology as zm

        logging.getLogger("zeyrek").setLevel(logging.ERROR)
        logging.getLogger("zeyrek.rulebasedanalyzer").setLevel(logging.ERROR)
        # Tek kelime çözümlüyoruz: NLTK cümle bölücüsüne (ek veri dosyası) gerek yok.
        zm._tokenize_text = lambda text: [text.replace("'", "").replace("’", "")]
        _analyzer = zeyrek.MorphAnalyzer()
    return _analyzer


@lru_cache(maxsize=4096)
def _parses(word: str) -> tuple:
    root = logging.getLogger()
    level = root.level
    root.setLevel(logging.ERROR)  # zeyrek her sonucu INFO/DEBUG olarak yazar
    try:
        res = _az().analyze(word)
    finally:
        root.setLevel(level)
    parses = [(p.lemma, p.pos, p.formatted) for p in (res[0] if res else [])]
    # Anlatım üçüncü kişidir: 1./2. kişi ekli okumalar ("denet+im" = benim denetim) geriye; kalanlarda
    # en uzun (sözlükteki) kök önce ("denetim", "kurum").
    return tuple(sorted(parses, key=lambda x: (bool(re.search(r":(P1|P2|A1|A2)(sg|pl)", x[2])), -len(x[0]))))


def _clean(word: str) -> str:
    return re.split(r"['’]", word.strip(".,!?;:\"'()“”"))[0]


def _parse_info(formatted: str) -> dict:
    """'[denet:Noun] denet:Noun+A3sg|çi:Agt→Noun+leri:P3pl' -> kök türü, son tür, yalın gövde, özel ad mı."""
    head, _, body = formatted.partition("] ")
    root_pos = head.strip("[").split(":", 1)[1] if ":" in head else ""
    parts = body.split("|")
    stem = ""
    for part in parts:
        first = part.split("+")[0]                  # 'denet:Noun' ya da 'çi:Agt→Noun' ('Zero→Noun': yüzeysiz)
        if ":" in first:
            stem += first.split(":", 1)[0]          # yalnızca kök + türetme ekleri (çekim ekleri atılır)
    last = parts[-1].split("+")[0]
    final_pos = last.split("→")[1] if "→" in last else (last.split(":", 1)[1] if ":" in last else root_pos)
    return {"root_pos": root_pos.split(",")[0], "proper": ",Prop" in head, "final_pos": final_pos.split(",")[0],
            "stem": stem, "derived": len(parts) > 1, "to_verb": "→Verb" in body}


def noun_lemma(word: str) -> str | None:
    """Kelime fiilden türememiş bir isimse YALIN hâli (ek almamış gövde); değilse None.
    'denetçileri' -> 'denetçi', 'vaatler' -> 'vaat'; 'çalışan', 'büyüleyici', 'edildiği' -> None."""
    w = _clean(word)
    if len(w) < 3 or not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû]", w):
        return None
    lower = w[:1].islower()
    for lem, pos, formatted in _parses(w):
        info = _parse_info(formatted)
        if info["root_pos"] == "Verb" or info["to_verb"] or info["final_pos"] != "Noun":
            continue
        if info["proper"] and lower:
            continue  # küçük harfli kelimenin özel ad çözümü değil ("dönemde" -> "Döne" hatası)
        if info["root_pos"] == "Adj" and w.lower() == lem.lower():
            continue  # çekimsiz sıfat ("eski") isim değildir; çekimliyse ("hastaların") isim kullanımıdır
        stem = w if info["proper"] else (_spoken_spelling(w, lem) if not info["derived"] else info["stem"])
        if stem.lower() in _GENERIC or (len(stem) < 4 and stem.lower() not in _SHORT_OK):
            return None
        return stem
    return None


_PLAIN = str.maketrans("âîûÂÎÛ", "aiuAIU")


def _spoken_spelling(word: str, lemma: str) -> str:
    """Sözlük kökü söylenen kelimenin başıyla (şapkasız) aynıysa söylenen yazım: 'felâket' -> 'felaket'."""
    plain = lemma.translate(_PLAIN)
    return word[:len(plain)].lower() if word.lower().translate(_PLAIN).startswith(plain.lower()) else lemma


def _surface_until(formatted: str, tag: str) -> str | None:
    """Biçimbirim yüzeylerini `tag`e kadar (dahil) birleştirir: 'dayanağ'+'ı' -> 'dayanağı'."""
    body = formatted.partition("] ")[2]
    out = ""
    for piece in re.split(r"[|+]", body):
        if ":" in piece:
            surf, label = piece.split(":", 1)
            out += surf
            if label.split("→")[0] == tag:
                return out
    return None


def p3sg_form(word: str) -> str | None:
    """Belirtisiz isim tamlamasının ikinci ismi: tamlama eki korunur, durum eki atılır
    ('zincirini' -> 'zinciri', 'cezasına' -> 'cezası', "Vadisi'ni" -> 'Vadisi')."""
    w = _clean(word)
    plural = None
    for lem, pos, formatted in _parses(w):
        info = _parse_info(formatted)
        if info["root_pos"] == "Verb" or info["to_verb"] or info["final_pos"] != "Noun" or (info["proper"] and w[:1].islower()):
            continue
        if re.search(r":A3pl|:P3pl", formatted):
            if plural is None and re.search(r":(P3pl|P3sg)", formatted):
                plural = _singular_p3sg(info["stem"])  # çoğul eki de atılır: 'denetçileri' -> 'denetçisi'
            continue
        form = _surface_until(formatted, "P3sg")
        if form:
            return form
    return plural


_MUTATE = {"p": "b", "ç": "c", "t": "d", "k": "ğ"}


def _singular_p3sg(stem: str) -> str | None:
    """Tekil iyelik: 'denetçi' -> 'denetçisi', 'skandal' -> 'skandalı', 'kitap' -> 'kitabı'."""
    vowels = [c for c in stem.lower() if c in "aeıioöuü"]
    if not vowels:
        return None
    v = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[vowels[-1]]
    if stem[-1].lower() in "aeıioöuü":
        return stem + "s" + v
    if len(vowels) > 1 and stem[-1] in _MUTATE:  # çok heceli kelimede ünsüz yumuşaması
        stem = stem[:-1] + ("g" if stem.endswith("nk") else _MUTATE[stem[-1]])
    return stem + v


def adjective_lemma(word: str) -> str | None:
    """Fiilden türememiş, türetmesiz niteleyici sıfat (ör. 'sahte', 'yanlış') ise yalın hâli."""
    w = _clean(word)
    for lem, pos, formatted in _parses(w):
        info = _parse_info(formatted)
        if (info["root_pos"] == "Adj" and info["final_pos"] == "Adj" and not info["derived"]
                and lem.lower() not in _GENERIC and lem.lower() not in _DETERMINERS):
            return info["stem"]
    return None


def can_be_noun(word: str) -> bool:
    """Kelimenin (fiilden türememiş) isim okuması var mı ('hasta' sıfat ama isim de olabilir)."""
    for _, _, formatted in _parses(_clean(word)):
        info = _parse_info(formatted)
        if info["root_pos"] != "Verb" and not info["to_verb"] and info["final_pos"] == "Noun" and not info["proper"]:
            return True
    return False


def candidates(words: list[str], mid_first: bool = False) -> list[tuple[str, int]]:
    """Söylenen kelimelerden isim / isim tamlaması adayları (yalın hâl), puanlarıyla. Özel adın tek
    parçası, birimler ve içeriksiz kelimeler aday olmaz."""
    out = []
    clean = [_clean(w) for w in words]
    for i, w in enumerate(clean):
        nxt = clean[i + 1] if i + 1 < len(clean) else ""
        name_part = (i > 0 or mid_first) and w[:1].isupper()  # cümle ortasında büyük harf: özel adın parçası
        n = noun_lemma(w)
        if n and not (name_part and n[:1].islower()):
            out.append((n, len(n)))
        if not nxt:
            continue
        if (i > 0 or mid_first) and w[:1].isupper() and nxt[:1].isupper() and len(w) >= 3 and len(nxt) >= 3:
            out.append((f"{w} {nxt}", len(w) + len(nxt) + 4))          # özel ad: "Silikon Vadisi"
            continue
        second = p3sg_form(nxt) if nxt[:1].islower() and noun_lemma(nxt) else None
        bare = w.lower() == (noun_lemma(w) or adjective_lemma(w) or "#").lower() or (can_be_noun(w) and not noun_lemma(w))
        if second and bare and can_be_noun(w) and w.lower() not in _GENERIC:
            out.append((f"{w.lower()} {second}", len(w) + len(second) + 4))  # tamlama: "eczane zinciri", "hasta sağlığı"
            continue
        adj, noun = adjective_lemma(w), noun_lemma(nxt)
        if adj and noun and nxt[:1].islower():
            out.append((f"{adj} {noun}", len(adj) + len(noun) + 4))    # sıfat + isim: "sahte vaat", "bilimsel dayanak"
    return out
