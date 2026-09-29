"""Türkçe sayı okunuşu: seslendirmeye giden metinde rakamlar yazıya çevrilir.

TTS rakamları bazen yanlış okuyabildiği için ElevenLabs'e giden metinde tüm rakamlar
Türkçe yazıyla gönderilir ("11 yıl" -> "on bir yıl", "2001'de" -> "iki bin birde",
"%88" -> "yüzde seksen sekiz", "90,75" -> "doksan virgül yetmiş beş", "2." -> "ikinci").
Ekrandaki kartlar ve altyazılar rakamla kalır: spoken_form() her orijinal kelimenin kaç
okunuş kelimesine dönüştüğünü de döner; tts.py kelime zamanlarını buna göre orijinal
kelimelere geri eşler. Tamamen yereldir (API isteği yok).

numbers_in(): bir metindeki sayı değerlerini (rakam ya da Türkçe sayı kelimeleri) çıkarır;
seslendirme kontrolü (src/speech_check.py) script ile duyulan metni bununla karşılaştırır.
"""

import re

_ONES = ("", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
_TENS = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")
_SCALES = ((10**12, "trilyon"), (10**9, "milyar"), (10**6, "milyon"), (1000, "bin"))
_ORDINAL = {
    "bir": "birinci", "iki": "ikinci", "üç": "üçüncü", "dört": "dördüncü", "beş": "beşinci",
    "altı": "altıncı", "yedi": "yedinci", "sekiz": "sekizinci", "dokuz": "dokuzuncu", "on": "onuncu",
    "yirmi": "yirminci", "otuz": "otuzuncu", "kırk": "kırkıncı", "elli": "ellinci", "altmış": "altmışıncı",
    "yetmiş": "yetmişinci", "seksen": "sekseninci", "doksan": "doksanıncı", "yüz": "yüzüncü",
    "bin": "bininci", "milyon": "milyonuncu", "milyar": "milyarıncı", "trilyon": "trilyonuncu", "sıfır": "sıfırıncı",
}
# Rakam grubu: binlik noktalı (1.500.000) ya da ondalık virgüllü/noktalı (90,75) sayı.
_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
_NUM_RE = re.compile(_NUM)


def number_words(n: int) -> str:
    """Tam sayının Türkçe okunuşu, kelimeler boşlukla: 63 -> 'altmış üç', 1000 -> 'bin'."""
    def below_1000(k: int) -> list[str]:
        h, r = divmod(k, 100)
        out = ([] if h == 0 else ["yüz"] if h == 1 else [_ONES[h], "yüz"])
        return out + [w for w in (_TENS[r // 10], _ONES[r % 10]) if w]

    if n == 0:
        return "sıfır"
    words: list[str] = []
    for scale, name in _SCALES:
        q, n = divmod(n, scale)
        if q:
            words += ([] if (q == 1 and name == "bin") else below_1000(q)) + [name]
    return " ".join(words + below_1000(n))


def _value_words(s: str) -> str:
    """'1.500' -> 'bin beş yüz', '90,75' -> 'doksan virgül yetmiş beş', '2.5' -> 'iki virgül beş'."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        s = s.replace(".", "")
    if re.search(r"[.,]", s):
        whole, frac = re.split(r"[.,]", s, maxsplit=1)
        frac_words = " ".join(["sıfır"] * (len(frac) - len(frac.lstrip("0"))) + [number_words(int(frac))]) \
            if frac.strip("0") else "sıfır"
        return f"{number_words(int(whole))} virgül {frac_words}"
    return number_words(int(s))


def _token_words(tok: str, next_tok: str = "") -> str:
    """Tek bir kelimedeki rakamları okunuşa çevirir; ek (’de, 'ında) okunuşa bitişir."""
    if not re.search(r"\d", tok):
        return tok
    m = re.fullmatch(rf"(?P<pre>[^\d%]*)(?P<pct>%?)(?P<num>{_NUM})(?P<rest>.*)", tok)
    if not m:
        return _NUM_RE.sub(lambda x: _value_words(x.group(0)), tok.replace("%", "yüzde "))
    pre, num, rest = m["pre"], m["num"], m["rest"]
    words = _value_words(num)
    # Sıra sayısı: "2. bölüm" (rakam + nokta + küçük harfle devam eden kelime).
    if rest == "." and next_tok[:1].islower() and "," not in num and "." not in num:
        last = words.split()[-1]
        words = " ".join(words.split()[:-1] + [_ORDINAL.get(last, last)])
        rest = ""
    # Ek: "2001'de" -> "iki bin birde"; ayraçsız ekler ("90'lar", "20bin") de bitişir.
    suffix = re.match(r"['’]?([a-zçğıöşüâîû]+)(.*)", rest, flags=re.IGNORECASE)
    if suffix:
        words += suffix.group(1)
        rest = suffix.group(2)
    if re.search(r"\d", rest):  # aralık: "1996-2001" -> "... altı-iki bin bir"
        rest = _token_words(rest, next_tok)
    return f"{pre}{'yüzde ' if m['pct'] else ''}{words}{rest}"


def spoken_form(text: str) -> tuple[str, list[int]]:
    """(okunuş metni, her orijinal kelimenin okunuşta kaç kelime olduğu)."""
    toks = text.split()
    spoken, groups = [], []
    for i, tok in enumerate(toks):
        s = _token_words(tok, toks[i + 1] if i + 1 < len(toks) else "")
        spoken.append(s)
        groups.append(len(s.split()))
    return " ".join(spoken), groups


def to_spoken(text: str) -> str:
    return spoken_form(text)[0]


# ---------------------------------------------------------------------------- sayı çıkarma

_WORD_VALUE = {w: i for i, w in enumerate(_ONES) if w} | {w: i * 10 for i, w in enumerate(_TENS) if w} | {"sıfır": 0}
_SCALE_VALUE = {name: scale for scale, name in _SCALES}
# Ek alabilen sayı kelimeleri, en uzundan kısaya (ör. "altmış" "altı"dan önce denenir).
_SUFFIXABLE = sorted([*_WORD_VALUE, "yüz", *_SCALE_VALUE], key=len, reverse=True)
_PLURAL = {"onlarca": 10, "yüzlerce": 100, "binlerce": 1000, "milyonlarca": 10**6, "milyarlarca": 10**9}
# Tek başına ekli okunabilen, başka kelimelerle karışmayan sayı kelimeleri ("on", "bir", "altı",
# "yüz", "bin", "yedi" gibi yaygın kelime kökleri hariç).
_SAFE_SUFFIXED = ("sıfır", "sekiz", "dokuz", "yirmi", "otuz", "elli", "altmış", "yetmiş", "seksen",
                  "doksan", "milyon", "milyar", "trilyon")


def _tr_lower(s: str) -> str:
    """Türkçe küçük harf: 'MİLYAR' -> 'milyar', 'KIRK' -> 'kırk' (str.lower() İ'yi bozar)."""
    return s.replace("İ", "i").replace("I", "ı").lower()


def _suffixed_start(t: str) -> int | None:
    for k in _SAFE_SUFFIXED:
        if t.startswith(k) and t != k:
            return _WORD_VALUE.get(k, _SCALE_VALUE.get(k))
    return None


# Sayı kelimesiyle başlayan ama sayı olmayan kelimeler.
_NOT_NUMBER = {"yüzde", "yüzü", "yüzünden", "bina", "binası", "onun", "ona", "ondan", "onlar", "onları",
               "bire", "birlikte", "biraz", "birçok", "birkaç", "birisi", "biri", "birine", "altında", "altına"}


def _norm_num(s: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        s = s.replace(".", "")
    return float(s.replace(",", "."))


def numbers_in(text: str, words: bool = True) -> list[float]:
    """Metindeki sayı değerleri, sırayla. Rakamlar (ve words=True ise Türkçe sayı kelimeleri)
    tanınır; ardından gelen bin/milyon/milyar çarpan olarak uygulanır ("9 milyar" = "dokuz
    milyar"). words=False: yalnızca rakamla yazılmış sayılar ("bir zamanlar" sayı sayılmaz)."""
    # Aralıklar ("1996-2001", "altı-iki bin bir") ayrı sayılardır: tire yerine sınır işareti.
    raw = [p for t in text.split() for p in re.sub(r"[-–/]", " | ", t).split()]
    toks = [re.sub(r"^[^\w%]+|[^\w,.]+$", "", _tr_lower(t)).rstrip(".,") for t in raw]
    out: list[float] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        # Ekli rakam ("2001'de" -> 2001) ve aralık ("1996-2001" -> 1996, 2001).
        found = _NUM_RE.findall(t) if re.match(r"%?\d", t) else []
        if found:
            out += [_norm_num(x) for x in found[:-1]]
            val = _norm_num(found[-1])
            j = i + 1
        elif words and t in _PLURAL:  # "yüzlerce" -> 100 (ekrandaki "100'LERCE" ile eşleşir)
            out.append(float(_PLURAL[t]))
            i += 1
            continue
        elif words and _suffixed_start(t) is not None:  # tek ekli sayı: "sıfıra", "dokuzda"
            out.append(float(_suffixed_start(t)))
            i += 1
            continue
        elif words and (t in _WORD_VALUE or t in ("yüz", "bin")):
            total, current, j = 0, 0, i
            while j < len(toks) and (toks[j] in _WORD_VALUE or toks[j] in ("yüz",) or toks[j] in _SCALE_VALUE):
                w = toks[j]
                if w == "yüz":
                    current = (current or 1) * 100
                elif w in _SCALE_VALUE:
                    total += (current or 1) * _SCALE_VALUE[w]
                    current = 0
                else:
                    current += _WORD_VALUE[w]
                j += 1
            # Sayının son kelimesi ekli olabilir: "iki bin birde", "bin dokuz yüz doksanlarda".
            if j < len(toks) and j > i:
                key = None if toks[j] in _NOT_NUMBER else next(
                    (k for k in _SUFFIXABLE if toks[j].startswith(k) and toks[j] != k), None)
                if key:
                    if key in _SCALE_VALUE:
                        total += (current or 1) * _SCALE_VALUE[key]
                        current = 0
                    elif key == "yüz":
                        current = (current or 1) * 100
                    else:
                        current += _WORD_VALUE[key]
                    j += 1
            val = total + current
            if j < len(toks) and toks[j] == "virgül":  # "doksan virgül yetmiş beş"
                frac = numbers_in(" ".join(toks[j + 1:j + 4]))
                if frac:
                    digits = str(int(frac[0]))
                    val = float(f"{int(val)}.{digits}")
                    j += 1 + len(number_words(int(frac[0])).split())
            out.append(float(val))
            i = j
            continue
        else:
            i += 1
            continue
        # Rakamdan sonra gelen çarpan kelimesi: "20 bin", "9 milyar".
        if j < len(toks) and toks[j] in _SCALE_VALUE:
            val *= _SCALE_VALUE[toks[j]]
            j += 1
        out.append(val)
        i = j
    return out
