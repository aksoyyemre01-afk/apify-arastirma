"""Ekran-seslendirme kuralları (RULES.md kural 1 ve 5), word_timings'e göre.

1) Ekrandaki her metin, etiket, rakam ve büyük gösterilen marka (logo kartı, karşılaştırma
   tarafı), o sahne ekrandayken seslendirmede GERÇEKTEN söylenen kelimelerden gelir
   (sahne aralığı ± SPOKEN_TOLERANCE sn). Logo çipleri kalıcı bağlam rozetidir: yalnızca
   videoda söylenen markalar çip olabilir.
2) Aynı rakam kartı ya da aynı metin (alıntı, zaman çizelgesi metni, etiket, yıl, değer)
   bir videoda en fazla bir kez gösterilir. Metinsiz logo kartı bu kurala girmez.

violations(): Eleştirmen'in otomatik kontrolü (props.json + word_timings.json).
enforce(): sahne planlayıcısının render öncesi düzeltmesi - kuralı ihlal eden alan
söylenmiyorsa kaldırılır, sahnenin ana içeriği söylenmiyorsa ya da tekrarsa sahne, o anda
söylenenden üretilen farklı bir tipe dönüştürülür (yıl -> zaman çizelgesi, rakam -> rakam
kartı, marka -> logo kartı, aksi halde söylenen kelimelerin alıntı kartı).
Konuya/kanala özgü hiçbir şey içermez; API isteği yoktur.
"""

import re

from . import tr_numbers

SPOKEN_TOLERANCE = 0.25  # sn: kelime sahne sınırına bu kadar yakınsa o sahnede söylenmiş sayılır
_SYMBOLS = {"$": "dolar", "%": "yüzde", "€": "euro", "£": "sterlin", "₺": "lira"}
_CURRENCY = {"dolar": "$", "euro": "€", "avro": "€", "sterlin": "£", "lira": "TL"}
_SCALE_WORDS = ("trilyon", "milyar", "milyon", "bin")
_TEXT_FIELDS = {  # tip -> (alan, props anahtarı) listesi: ekranda yazı olarak görünenler
    "quote": ["text"], "timeline": ["year", "text"], "big_number": ["value_unit"],
    "comparison": ["leftValue", "rightValue"], "chart": ["pointLabels", "endValue"], "logo_intro": [],
}


def _norm(w: str) -> str:
    w = w.replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"[^\w]", "", w)


def _fields(sc: dict) -> dict[str, str]:
    """Sahnede yazı olarak görünen alanlar (boş olmayanlar)."""
    out = {}
    if sc.get("label"):
        out["label"] = sc["label"]
    for f in _TEXT_FIELDS.get(sc["type"], []):
        if f == "value_unit":
            v = " ".join(x for x in (sc.get("value", ""), sc.get("unit", "")) if x)
        elif f == "pointLabels":
            v = " ".join(sc.get("pointLabels") or [])
        else:
            v = sc.get(f, "")
        if v:
            out[f] = v
    return out


def _big_brands(sc: dict) -> dict[str, str]:
    """Büyük gösterilen (gizli olmayan) markalar: logo kartı ve karşılaştırma tarafları."""
    refs = {"logo": sc.get("logo")} if sc["type"] == "logo_intro" else (
        {"left": sc.get("left"), "right": sc.get("right")} if sc["type"] == "comparison" else {})
    return {k: r["name"] for k, r in refs.items() if r and r.get("name") and not r.get("hidden")}


_SENT_END = (".", "!", "?", ":", "…")
# Alıntı kartının sonunda anlamsız kalan bağlaç/edat/zarflar.
_DANGLING = {"ve", "ile", "ama", "ancak", "fakat", "gibi", "için", "bu", "bir", "şu", "o", "tam", "henüz", "çok",
             "daha", "en", "de", "da", "ki", "ya", "hem", "peki", "hızla", "kadar"}


def _fold(s: str) -> str:
    """Eşleştirme için ı/i farkı yok sayılır ('EDISON' Türkçe küçültmede 'edıson' olur)."""
    return s.replace("ı", "i")


def _same_root(a: str, b: str) -> bool:
    """Türkçe ek farkı: 'ifşayı'~'ifşa', 'kapıya'~'kapısına', 'mıydı'~'mı'; 'yayınladı'!~'yağdırdı'."""
    if a == b:
        return True
    cp = len(next((a[:i] for i in range(min(len(a), len(b)), 0, -1) if a[:i] == b[:i]), ""))
    short, long_ = sorted((len(a), len(b)))
    if cp == short:  # biri diğerinin kökü
        return short >= 3 or long_ - short <= 3
    return cp >= 4 and cp >= short - 2


def _sentences(timings: list[dict]) -> list[tuple[float, float, list[str]]]:
    out, cur = [], []
    for w in timings:
        cur.append(w)
        if w["word"].rstrip("\"'”’)").endswith(_SENT_END):
            out.append((cur[0]["start"], cur[-1]["end"], [x["word"] for x in cur]))
            cur = []
    if cur:
        out.append((cur[0]["start"], cur[-1]["end"], [x["word"] for x in cur]))
    return out


class _Window:
    """Bir sahne ekrandayken söylenenler. İki katman:
    - kelimeler/isimler: sahne sırasında söylenmekte olan CÜMLE(ler) (cümlenin tamamını gösteren
      bir alıntı kartı, cümle ikiye bölündüğünde de geçerli kalır);
    - rakamlar: sıkı zaman - sahne aralığı ± tol içinde söylenmiş olmalı (rakam kartı,
      rakam söylenmeden önce ya da sonra görünmez)."""

    def __init__(self, timings: list[dict], a: float, b: float, tol: float = SPOKEN_TOLERANCE):
        self.words = [w["word"] for w in timings if w["start"] < b + tol and w["end"] > a - tol]
        self.core = [w["word"] for w in timings if w["start"] < b and w["end"] > a] or self.words
        sent_words = [x for s0, s1, ws in _sentences(timings) if s0 < b - 0.05 and s1 > a + 0.05 for x in ws]
        self.tokens = {_norm(x) for x in (sent_words or self.words) if _norm(x)}
        text = " ".join(self.words)
        self.numbers = set(tr_numbers.numbers_in(text)) | set(tr_numbers.numbers_in(text, words=False))

    def has_word(self, tok: str) -> bool:
        tok = _fold(_norm(_SYMBOLS.get(tok, tok)))
        if not tok:
            return True
        return any(_same_root(tok, _fold(s)) for s in self.tokens)

    def unspoken(self, text: str) -> list[str]:
        """text'in söylenmeyen parçaları (sayılar değerle, kelimeler kökle karşılaştırılır)."""
        nums = tr_numbers.numbers_in(text, words=False)
        missing = [f"{n:g}" for n in nums if n not in self.numbers]
        for raw in re.findall(r"[^\s]+", text):
            parts = [p for p in re.split(r"[-/]", raw) if p]
            for p in parts:
                if re.search(r"\d", p):
                    continue  # sayılar yukarıda değerle kontrol edildi ("100'LERCE", "2015")
                sym = p.strip(".,!?;:\"'()")
                if sym in _SYMBOLS:
                    if not self.has_word(sym):
                        missing.append(sym)
                    continue
                if _norm(sym) in _SCALE_WORDS and nums:
                    continue  # ölçek kelimesi sayı değerine dahil ("9 MİLYAR" = 9e9), orada kontrol edildi
                if _norm(sym) and not self.has_word(sym):
                    missing.append(sym)
        return missing

    def phrase(self, max_words: int = 9) -> str:
        words = self.core[-max_words:] if len(self.core) > max_words else list(self.core)
        # Yarım kalan uçlar kırpılır: "...Holmes, henüz" -> "...Holmes".
        while len(words) > 2 and _norm(words[-1]) in _DANGLING:
            words.pop()
        text = " ".join(words).strip(" ,;:.")
        return (text[:1].replace("i", "İ").replace("ı", "I").upper() + text[1:]) if text else ""


def _span(sc: dict, fps: int) -> tuple[float, float]:
    return sc["from"] / fps, (sc["from"] + sc["durationInFrames"]) / fps


def _signatures(sc: dict) -> list[str]:
    """Tekrar kontrolü için sahnenin gösterdiği yazılar (normalize)."""
    return [" ".join(_norm(w) for w in v.split() if _norm(w)) or v for v in _fields(sc).values()]


def violations(props: dict, timings: list[dict]) -> dict[str, list[str]]:
    """{'unspoken': [...], 'duplicate': [...]} - Eleştirmen ölçümü."""
    fps = props["fps"]
    spoken_all = _Window(timings, 0, 1e9)
    unspoken, dup, seen = [], [], {}
    for i, sc in enumerate(props["scenes"], 1):
        a, b = _span(sc, fps)
        win = _Window(timings, a, b)
        where = f"sahne {i} ({a:.1f}-{b:.1f} sn, {sc['type']})"
        for f, v in _fields(sc).items():
            miss = win.unspoken(v)
            if miss:
                unspoken.append(f"{where}: {f}=\"{v}\" söylenmiyor ({', '.join(miss)}); o sırada: \"{' '.join(win.words)}\"")
        for f, name in _big_brands(sc).items():
            if not any(win.has_word(t) for t in name.split()[:1]):
                unspoken.append(f"{where}: {f} logosu \"{name}\" o sırada söylenmiyor; o sırada: \"{' '.join(win.words)}\"")
        for c in sc.get("chips") or []:
            if c and not c.get("hidden") and not spoken_all.has_word(c["name"].split()[0]):
                unspoken.append(f"{where}: çip \"{c['name']}\" videoda hiç söylenmiyor")
        for s in _signatures(sc):
            if s in seen:
                dup.append(f"{where}: \"{s}\" daha önce sahne {seen[s]}'de gösterildi")
            else:
                seen[s] = i
    return {"unspoken": unspoken, "duplicate": dup}


# ---------------------------------------------------------------------------- düzeltme

def _spoken_year(win: _Window) -> str:
    for w in win.core:
        m = re.match(r"^(1[89]\d\d|20\d\d)(?!\d)", w)
        if m:
            return m.group(1)
    return ""


def _spoken_amount(win: _Window) -> tuple[str, str]:
    """O anda söylenen (yıl olmayan) rakam ve birimi: '9 milyar dolara' -> ('9', 'MİLYAR $')."""
    words = win.core
    for k, w in enumerate(words):
        m = re.match(r"^%?(\d[\d.,]*)", w)
        if not m or re.match(r"^(1[89]\d\d|20\d\d)$", m.group(1)):
            continue
        unit = []
        if w.startswith("%"):
            unit.append("%")
        for nxt in words[k + 1:k + 3]:
            n = _norm(nxt)
            scale = next((s for s in _SCALE_WORDS if n.startswith(s)), None)
            cur = next((c for c in _CURRENCY if n.startswith(c)), None)
            if scale:
                unit.append(scale.replace("i", "İ").upper())
            elif cur:
                unit.append(_CURRENCY[cur])
                break
            else:
                break
        return m.group(1).rstrip(".,"), " ".join(unit)
    return "", ""


def enforce(scenes: list[dict], timings: list[dict], fps: int, brands: list[str], logo_ref) -> list[dict]:
    """Kuralları props sahnelerine uygular (yerinde). logo_ref(marka) -> props logo sözlüğü ya da None."""
    seen: set[str] = set()
    prev_type = ""
    for i, sc in enumerate(scenes):
        neighbours = [x for x in (scenes[i - 1] if i else None, scenes[i + 1] if i + 1 < len(scenes) else None) if x]
        a, b = _span(sc, fps)
        win = _Window(timings, a, b)
        # Mystery: gizli marka kartları (soru işareti) kurala girmez.
        hidden = any(r and r.get("hidden") for r in (sc.get("logo"), sc.get("left"), sc.get("right")))
        # 1) Söylenmeyen yan alanlar kaldırılır.
        if sc.get("label") and (win.unspoken(sc["label"]) or _sig(sc["label"]) in seen):
            sc["label"] = ""
        if sc["type"] == "chart":
            if sc.get("pointLabels") and win.unspoken(" ".join(sc["pointLabels"])):
                sc["pointLabels"] = []
            if sc.get("endValue") and (win.unspoken(sc["endValue"]) or _sig(sc["endValue"]) in seen):
                sc["endValue"] = ""
        if sc["type"] == "comparison":
            for f in ("leftValue", "rightValue"):
                if sc.get(f) and (win.unspoken(sc[f]) or _sig(sc[f]) in seen):
                    sc[f] = ""
        if sc["type"] == "timeline" and sc.get("text") and win.unspoken(sc["text"]):
            sc["text"] = _phrase_without(win, sc.get("year", ""))
        if sc["type"] == "quote" and sc.get("text") and win.unspoken(sc["text"]):
            sc["text"] = win.phrase()
            sc["highlight"] = _highlight(sc["text"])
        # 2) Ana içerik söylenmiyor ya da tekrar ediyorsa sahne dönüştürülür.
        main_bad = False
        if not hidden:
            main_bad = any(not any(win.has_word(t) for t in n.split()[:1]) for n in _big_brands(sc).values())
        if sc["type"] == "big_number":
            main_bad |= bool(win.unspoken(_fields(sc).get("value_unit", "")))
        if sc["type"] == "timeline":
            main_bad |= bool(sc.get("year") and win.unspoken(sc["year"]))
        main_bad |= any(s in seen for s in _signatures(sc))
        if main_bad and not hidden:
            _convert(sc, win, seen, prev_type, brands, logo_ref, neighbours)
        seen.update(_signatures(sc))
        prev_type = sc["type"]
    return scenes


def _sig(text: str) -> str:
    return " ".join(_norm(w) for w in text.split() if _norm(w)) or text


def _phrase_without(win: _Window, year: str) -> str:
    """Zaman çizelgesi metni: yıl ve hemen ardındaki "yılında/yılı" kelimesi olmadan."""
    words, skip = [], False
    for w in win.core:
        if year and w.startswith(year):
            skip = True
            continue
        if skip and _norm(w).startswith("yıl"):
            skip = False
            continue
        skip = False
        words.append(w)
    text = " ".join(words[-7:]).strip(" ,;:.")
    return (text[:1].replace("i", "İ").replace("ı", "I").upper() + text[1:]) if text else ""


def _highlight(text: str) -> list[str]:
    words = [w.strip(".,!?;:\"'") for w in text.split()]
    digits = [w for w in words if any(ch.isdigit() for ch in w)]
    if digits:
        return digits[:1]
    longest = max(words, key=len, default="")
    return [longest] if len(longest) >= 4 else []


def _convert(sc: dict, win: _Window, seen: set[str], prev_type: str, brands: list[str], logo_ref,
             neighbours: list[dict] = ()) -> None:
    """Sahneyi o anda söylenene uygun, tekrar etmeyen, mümkünse öncekinden farklı bir tipe çevirir."""
    base = {k: sc[k] for k in ("from", "durationInFrames", "variant", "chips", "tone") if k in sc}
    cands: list[dict] = []
    year = _spoken_year(win)
    if year:
        cands.append({"type": "timeline", "year": year, "text": _phrase_without(win, year), "label": ""})
    value, unit = _spoken_amount(win)
    if value:
        cands.append({"type": "big_number", "value": value, "unit": unit, "label": ""})
    # Komşu sahne zaten aynı markanın logo kartıysa art arda aynı logo gösterilmez.
    near_logos = {_norm(n["logo"]["name"]) for n in neighbours if n.get("type") == "logo_intro" and n.get("logo")}
    for brand in brands:
        if brand and _norm(brand) not in near_logos and win.has_word(brand.split()[0]):
            ref = logo_ref(brand)
            if ref:
                cands.append({"type": "logo_intro", "logo": ref, "label": ""})
                break
    text = win.phrase()
    if text:
        cands.append({"type": "quote", "text": text, "highlight": _highlight(text), "label": ""})

    def ok(c: dict) -> bool:
        tmp = dict(base, **c)
        return not any(s in seen for s in _signatures(tmp)) and not _unspoken_any(tmp, win)

    valid = [c for c in cands if ok(c)]
    pick = next((c for c in valid if c["type"] != prev_type), valid[0] if valid else None)
    if pick is None:
        pick = {"type": "quote", "text": text, "highlight": _highlight(text), "label": ""}
    for k in [k for k in sc if k not in base]:
        del sc[k]
    sc.update(pick)
    sc["variant"] = 0
    # Büyük gösterilen marka, çiplerde tekrar edilmez.
    if pick["type"] == "logo_intro":
        name = _norm(pick["logo"]["name"])
        sc["chips"] = [c for c in sc.get("chips", []) if c and _norm(c["name"]) != name]


def _unspoken_any(sc: dict, win: _Window) -> bool:
    return any(win.unspoken(v) for v in _fields(sc).values())
