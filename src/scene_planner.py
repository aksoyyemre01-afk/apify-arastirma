"""script.json (sahneli) + word_timings.json -> Remotion props (RULES.md'nin kod tarafı).

Bu modül hiçbir şirkete/konuya/kanala özgü değildir; tüm kurallar script'teki
alanlardan ve kelime zamanlamalarından türetilir:

- Kural 1: her sahne, kendi cümlesinin seslendirildiği anda ekrandadır
  (sahne cümleleri kelime zamanlamalarına difflib ile hizalanır).
- Kural 2: hook_type=mystery ise cevap markası, sesli söylendiği ana kadar
  soru işaretli kutuyla gizlenir ve en geç REVEAL_DEADLINE saniyede impact ile
  açılır; ilk sahnede gizli kutu mutlaka görünür. hook_type=direct ise ana
  marka ilk DIRECT_BRAND_DEADLINE saniyede görünür (gerekirse ilk sahneye
  logo çipi eklenir).
- Kural 5: MAX_SCENE_SECONDS'tan uzun sahneler görsel varyantlara bölünür.
- Kural 6: altyazı sayfaları kelime zamanlamalarından üretilir.
- Kural 7: palet/font/rozet/outro config/brand.json'dan gelir.
- Kural 8: assets/audio içindeki müzik/efektler varsa eklenir.
- Kural 10: ekranda görünen her metin temizlenir; iç not/prompt izi taşıyan
  metinler ekrana hiç çıkmaz.
"""

import difflib
import math
import re
import shutil
from pathlib import Path

from . import logos
from .schemas import Scene
from .utils import slugify

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "remotion" / "public" / "fonts"
AUDIO_ASSETS_DIR = ROOT / "assets" / "audio"

FPS = 30
WIDTH = 1080
HEIGHT = 1920

MAX_SCENE_SECONDS = 3.0
SPLIT_THRESHOLD = 3.0  # hiçbir sahne 3 sn'yi geçmez
SCENE_LEAD = 0.08  # sahne, ilk kelimesinden hemen önce başlar (animasyon kelimeyle çakışsın)
REVEAL_DEADLINE = 5.0
DIRECT_BRAND_DEADLINE = 3.0
MIN_SPLIT_PART = 0.7
MIN_SCENE_SECONDS = 1.0
REVEAL_HOLD = 1.3  # reveal edilen logo en az bu kadar ekranda kalır
WHOOSH_MIN_GAP = 1.5

CAPTION_MAX_WORDS = 3
CAPTION_MAX_CHARS = 18
CAPTION_GAP_BREAK = 0.3

# Kural 10: iç not/prompt/sahne tarifi izi taşıyan ekran metinleri.
_BANNED = re.compile(
    r"[\[\]{}<>]|g[öo]rsel|sahne|prompt|animasyon|kamera|visual|scene|dry.?run|placeholder|\bnot\s*:",
    re.IGNORECASE,
)
_SENTENCE_END = (".", "!", "?", ":", ";", "…")


class PlanError(RuntimeError):
    pass


def _norm(word: str) -> str:
    word = word.replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"[^\w]", "", word)


def _tokens(text: str) -> list[str]:
    return [t for t in (_norm(w) for w in text.split()) if t]


def _clean(text: str, max_words: int, field: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    if _BANNED.search(text):
        print(f"      [Kural 10] ekran metni reddedildi ({field}): {text!r}")
        return ""
    words = text.split(" ")
    if len(words) > max_words:
        # Önce sınır içindeki son tam cümlede kes; cümle sonu yoksa kelimeden kes.
        cut = [i for i, w in enumerate(words[:max_words]) if w.endswith((".", "!", "?"))]
        text = " ".join(words[: cut[-1] + 1] if cut else words[:max_words]).rstrip(",;:-")
    return text


# Karşılaştırmada taraf olamayacak genel ifadelerin kelimeleri (marka değil).
_GENERIC_WORDS = {
    _norm(x) for x in (
        "diğer", "diğerleri", "rakip", "rakipler", "rakibi", "yeni", "herkes", "kullanıcılar",
        "pazar", "sektör", "şirket", "şirketler", "firma", "geri", "kalan", "others", "other",
        "competitor", "competitors", "rest", "new",
    )
}


def _is_generic(name: str) -> bool:
    words = [_norm(w) for w in (name or "").split() if _norm(w)]
    return not words or all(w in _GENERIC_WORDS for w in words)


def _validate_comparisons(scenes: list[dict], has_logo) -> None:
    """Kural 1: karşılaştırmanın iki tarafı da gerçek, logosu çekilebilen bir şirket/ürün
    olmalı. "X vs Yeni rakip" gibi bir taraf genel ifadeyse ya da logosu bulunamıyorsa
    sahne, geçerli tarafın rakam/logo kartına; iki taraf da geçersizse alıntı kartına döner."""
    for s in scenes:
        if s["scene_type"] != "comparison":
            continue
        sides = [(s.get("left_brand", ""), s.get("left_value", "")), (s.get("right_brand", ""), s.get("right_value", ""))]
        valid = [(b, v) for b, v in sides if not _is_generic(b) and has_logo(b)]
        if len(valid) == 2:
            continue
        print(f"      [Kural 1] '{sides[0][0]} vs {sides[1][0]}': gerçek/logolu iki taraf yok, sahne dönüştürüldü.")
        s.update(left_brand="", right_brand="", left_value="", right_value="", highlight_side="none")
        if valid:
            brand, value = valid[0]
            s["brand"] = brand
            if value:
                s.update(scene_type="big_number", value=value, unit="")
            else:
                s.update(scene_type="logo_intro")
        else:
            s.update(scene_type="quote", text="", highlight=[])


def _frame(t: float) -> int:
    return int(round(t * FPS))


# --------------------------------------------------------------------------- hizalama

def _align_scene_starts(scenes: list[dict], timings: list[dict]) -> list[float]:
    """Her sahnenin ilk kelimesinin seslendirmedeki başlangıç zamanı."""
    script_tokens: list[tuple[int, str]] = []
    for i, s in enumerate(scenes):
        script_tokens += [(i, tok) for tok in _tokens(s["narration"])]
    timing_tokens = [_norm(w["word"]) for w in timings]

    matcher = difflib.SequenceMatcher(None, [t for _, t in script_tokens], timing_tokens, autojunk=False)
    a_to_b: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            a_to_b[block.a + k] = block.b + k

    ratio = len(a_to_b) / max(len(script_tokens), 1)
    if ratio < 0.8:
        print(f"      UYARI: sahne metni ile seslendirme %{ratio * 100:.0f} eşleşiyor; zamanlama tahmini olabilir.")

    starts: list[float | None] = []
    for i in range(len(scenes)):
        idxs = [a for a, (si, _) in enumerate(script_tokens) if si == i]
        start = None
        # Sahnenin eşleşen ilk kelimesi; ondan önce eşleşmeyen kelime varsa
        # onların süresi kadar geri kaydırılmaz (küçük hata, kabul edilebilir).
        for a in idxs:
            if a in a_to_b:
                start = timings[a_to_b[a]]["start"]
                break
        starts.append(start)

    # Eşleşmeyen sahneler için komşulardan doğrusal interpolasyon.
    total = timings[-1]["end"] if timings else 0.0
    known = [(i, s) for i, s in enumerate(starts) if s is not None]
    if not known:
        step = total / max(len(scenes), 1)
        return [i * step for i in range(len(scenes))]
    result = []
    for i, s in enumerate(starts):
        if s is not None:
            result.append(s)
            continue
        prev = max(((j, v) for j, v in known if j < i), default=(-1, 0.0))
        nxt = min(((j, v) for j, v in known if j > i), default=(len(scenes), total))
        frac = (i - prev[0]) / (nxt[0] - prev[0])
        result.append(prev[1] + (nxt[1] - prev[1]) * frac)
    result[0] = 0.0
    for i in range(1, len(result)):
        result[i] = max(result[i], result[i - 1] + 0.4)
    return result


# --------------------------------------------------------------------------- marka kuralları

def _brands_of(seg: dict) -> set[str]:
    s = seg["scene"]
    names = {s.get("brand", ""), s.get("left_brand", ""), s.get("right_brand", "")}
    names |= set(seg.get("chips", []))
    return {_norm(n) for n in names if n}


def _find_spoken(brand: str, timings: list[dict]) -> float | None:
    key = _norm((brand or "").split()[0]) if brand else ""
    if not key:
        return None
    for w in timings:
        if _norm(w["word"]).startswith(key):
            return w["start"]
    return None


def _apply_mystery(segs: list[dict], script: dict, timings: list[dict]) -> float | None:
    """Gizemli hook: reveal zamanını belirler, gerekirse reveal sahnesini kurar.
    Reveal zamanını döner."""
    brand = (script.get("mystery_brand") or script.get("main_brand") or "").strip()
    if not brand:
        print("      UYARI: hook_type=mystery ama mystery_brand boş; doğrudan hook olarak işlendi.")
        return None
    key = _norm(brand)

    reveal_t = _find_spoken(brand, timings)
    if reveal_t is None:
        flagged = next((s for s in segs if s["scene"].get("reveal")), None)
        reveal_t = flagged["start"] if flagged else REVEAL_DEADLINE
    if reveal_t > REVEAL_DEADLINE:
        print(f"      [Kural 2] marka {reveal_t:.2f} sn'de söyleniyor; reveal {REVEAL_DEADLINE:.0f}. saniyeye çekildi.")
        reveal_t = REVEAL_DEADLINE

    # İlk sahnede gizli kutu mutlaka görünsün.
    if key not in _brands_of(segs[0]):
        s0 = segs[0]["scene"]
        if s0["scene_type"] == "comparison" and not s0.get("right_brand"):
            s0["right_brand"] = brand
        elif s0["scene_type"] == "comparison" and not s0.get("left_brand"):
            s0["left_brand"] = brand
        else:
            segs[0].setdefault("chips", []).append(brand)

    # Reveal anındaki sahne markayı büyük göstermiyorsa, o andan itibaren
    # logo_intro reveal sahnesine geçilir.
    idx = next((i for i, s in enumerate(segs) if s["start"] <= reveal_t < s["end"]), len(segs) - 1)
    seg = segs[idx]
    sc = seg["scene"]
    shows_big = (sc["scene_type"] == "logo_intro" and _norm(sc.get("brand", "")) == key) or (
        sc["scene_type"] == "comparison" and key in {_norm(sc.get("left_brand", "")), _norm(sc.get("right_brand", ""))}
    )
    if not shows_big:
        reveal_scene = Scene(narration="", scene_type="logo_intro", brand=brand, reveal=True).model_dump()
        if reveal_t - seg["start"] >= MIN_SPLIT_PART:
            tail = {"scene": reveal_scene, "start": reveal_t, "end": seg["end"], "variant": 0}
            seg["end"] = reveal_t
            segs.insert(idx + 1, tail)
        else:
            reveal_scene["label"] = sc.get("label", "")
            seg["scene"] = reveal_scene
    return reveal_t


def _apply_direct(segs: list[dict], script: dict) -> None:
    brand = (script.get("main_brand") or script.get("company") or "").strip()
    if not brand:
        return
    key = _norm(brand)
    if any(key in _brands_of(s) for s in segs if s["start"] < DIRECT_BRAND_DEADLINE):
        return
    s0 = segs[0]["scene"]
    if not s0.get("brand") and s0["scene_type"] != "comparison":
        s0["brand"] = brand
    else:
        segs[0].setdefault("chips", []).append(brand)
    print(f"      [Kural 2] ana marka ({brand}) ilk {DIRECT_BRAND_DEADLINE:.0f} sn'de yoktu; ilk sahneye eklendi.")


def _enforce_min_durations(segs: list[dict], reveal_t: float | None) -> None:
    """Çok kısa sahneler göz kırpması gibi görünür; reveal edilen logo da okunacak
    kadar ekranda kalmalı. Gerekirse sonraki sahnenin başlangıcı (o sahne
    MIN_SCENE_SECONDS'ın altına düşmeyecek kadar) ileri kaydırılır."""
    for i in range(len(segs) - 1):
        seg, nxt = segs[i], segs[i + 1]
        need = MIN_SCENE_SECONDS
        if reveal_t is not None and seg["start"] <= reveal_t < seg["end"] + 1e-3:
            need = max(need, reveal_t - seg["start"] + REVEAL_HOLD)
        short = need - (seg["end"] - seg["start"])
        room = (nxt["end"] - nxt["start"]) - MIN_SCENE_SECONDS
        shift = min(short, room)
        if shift > 0:
            seg["end"] += shift
            nxt["start"] += shift


# --------------------------------------------------------------------------- bölme / props

def _split_long(segs: list[dict], timings: list[dict], main_brand: str) -> list[dict]:
    out = []
    for seg in segs:
        dur = seg["end"] - seg["start"]
        if dur <= SPLIT_THRESHOLD:
            out.append(seg)
            continue
        n = math.ceil(dur / MAX_SCENE_SECONDS)
        step = dur / n
        alts = _alternates(seg["scene"], main_brand)
        for k in range(n):
            start, end = seg["start"] + k * step, seg["start"] + (k + 1) * step
            part = dict(seg, start=start, end=end)
            if k % 2 == 0:
                # Orijinal sahne; tekrar ediyorsa yakın plan varyantıyla.
                part["variant"] = seg.get("variant", 0) + k // 2
            else:
                alt = dict(seg["scene"], **alts[(k // 2) % len(alts)], reveal=False)
                if alt["scene_type"] == "quote" and not alt.get("text"):
                    alt["text"] = _spoken_text(timings, start, end) or seg["scene"]["narration"]
                    alt["highlight"] = _pick_highlight(alt["text"])
                elif alt["scene_type"] == "logo_intro" and not alt.get("label"):
                    alt["label"] = _spoken_text(timings, start, end, max_words=5)
                part.update(scene=alt, variant=0)
            out.append(part)
    return out


def _spoken_text(timings: list[dict], start: float, end: float, max_words: int = 8) -> str:
    """[start, end) aralığında seslendirilen kelimeler (sahnenin o anki cümle parçası)."""
    words = [w["word"] for w in timings if start - 0.05 <= w["start"] < end]
    return " ".join(words[:max_words]).strip(" ,;:.")


def _pick_highlight(text: str) -> list[str]:
    words = [w.strip(".,!?;:\"'") for w in text.split()]
    with_digit = [w for w in words if any(ch.isdigit() for ch in w)]
    if with_digit:
        return with_digit[:1]
    longest = max(words, key=len, default="")
    return [longest] if len(longest) >= 4 else []


def _split_value(value: str) -> tuple[str, str] | None:
    """'4,8 MİLYAR $' -> ('4,8', 'MİLYAR $')."""
    m = re.match(r"^\s*([-+]?%?[\d.,]+%?)\s*(.*)$", value or "")
    return (m.group(1), m.group(2).strip()) if m else None


def _alternates(sc: dict, main_brand: str) -> list[dict]:
    """Kural 5: 3 sn'yi aşan bir sahnenin ikinci yarısı için FARKLI tipte, aynı cümleyi
    gösteren sahne adayları (öncelik sırasıyla). Alanlar sahnenin kendi verisinden ya da
    o anda seslendirilen kelimelerden gelir; hiçbir konuya özgü değildir."""
    t = sc["scene_type"]
    brand = sc.get("brand") or ""
    out: list[dict] = []
    if t == "big_number":
        if brand:
            out.append({"scene_type": "logo_intro", "brand": brand,
                        "label": " ".join(x for x in (sc.get("value", ""), sc.get("unit", "")) if x)})
    elif t == "chart":
        parsed = _split_value(sc.get("end_value", ""))
        if parsed:
            out.append({"scene_type": "big_number", "value": parsed[0], "unit": parsed[1]})
    elif t == "comparison":
        side = sc.get("highlight_side")
        pick = (sc.get("right_brand"), sc.get("right_value")) if side == "right" else (sc.get("left_brand"), sc.get("left_value"))
        if pick[0]:
            out.append({"scene_type": "logo_intro", "brand": pick[0], "label": pick[1] or ""})
    elif t == "timeline":
        if brand:
            out.append({"scene_type": "logo_intro", "brand": brand, "label": sc.get("year", "")})
    elif t == "quote":
        if brand or main_brand:
            out.append({"scene_type": "logo_intro", "brand": brand or main_brand, "label": ""})
    if t != "quote":
        out.append({"scene_type": "quote", "text": "", "highlight": [], "label": ""})
    if not out:
        out.append({"scene_type": "logo_intro", "brand": main_brand, "label": ""})
    return out


class _LogoRegistry:
    def __init__(self, offline: bool):
        self.offline = offline
        self.files: dict[str, Path] = {}  # public yolu -> kaynak dosya
        self._cache: dict[str, str | None] = {}

    def src(self, brand: str) -> str | None:
        key = _norm(brand)
        if key not in self._cache:
            path = logos.resolve(brand, offline=self.offline)
            if path:
                rel = f"logos/{slugify(brand)}{path.suffix.lower()}"
                self.files[rel] = path
                self._cache[key] = rel
            else:
                self._cache[key] = None
        return self._cache[key]


def _logo_ref(brand: str, seg: dict, reg: _LogoRegistry, mystery_key: str, reveal_t: float | None) -> dict | None:
    brand = (brand or "").strip()
    if not brand:
        return None
    ref = {"name": brand, "src": reg.src(brand), "hidden": False, "revealAt": None}
    if mystery_key and reveal_t is not None and _norm(brand) == mystery_key:
        if seg["end"] <= reveal_t + 1e-3:
            ref["hidden"] = True
        elif seg["start"] < reveal_t:
            ref["hidden"] = True
            ref["revealAt"] = max(_frame(reveal_t) - _frame(seg["start"]), 0)
    return ref


def _mask(text: str, brand: str, seg: dict, reveal_t: float | None) -> str:
    """Reveal'dan önce biten sahnelerde gizli markanın adı metinde de görünmez."""
    if not text or not brand or reveal_t is None or seg["start"] >= reveal_t:
        return text
    return re.sub(re.escape(brand.split()[0]), "???", text, flags=re.IGNORECASE)


# mood alanı olmayan (eski) script'ler için cümleden yön tahmini: Türkçe kök eşleşmesi.
_RISE_STEMS = ("zirve", "rekor", "yüksel", "büyü", "lider", "kral", "patlama", "arttı", "artış",
               "başarı", "ulaştı", "ulaşmıştı", "devleş", "hükmed")
_FALL_STEMS = ("düştü", "düşüş", "düşer", "çök", "eridi", "eriy", "kaybet", "kayıp", "iflas", "batt",
               "redde", "geri çevir", "kapandı", "kapat", "küçül", "zarar", "kriz", "çakıl", "satıl")


def _tone(s: dict) -> str:
    """Kural 5 (çeşitlilik): sahnenin zemin tonu - 'rise', 'fall' ya da 'neutral'."""
    if s.get("mood") in ("rise", "fall"):
        return s["mood"]
    if s["scene_type"] == "chart" and s.get("direction") in ("up", "down"):
        return "rise" if s["direction"] == "up" else "fall"
    words = [w.replace("I", "ı").replace("İ", "i").lower() for w in (s.get("narration") or "").split()]
    text = " ".join(words)
    fall = any(w.startswith(st) for w in words for st in _FALL_STEMS if " " not in st) or any(
        st in text for st in _FALL_STEMS if " " in st
    )
    rise = any(w.startswith(st) for w in words for st in _RISE_STEMS)
    if fall != rise:
        return "fall" if fall else "rise"
    return "neutral"


def _scene_props(seg: dict, reg: _LogoRegistry, mystery: str, reveal_t: float | None) -> dict:
    s = seg["scene"]
    mkey = _norm(mystery) if mystery else ""
    t = s["scene_type"]

    def txt(field: str, max_words: int) -> str:
        return _mask(_clean(s.get(field, ""), max_words, field), mystery, seg, reveal_t)

    props = {
        "type": t,
        "from": _frame(seg["start"]),
        "durationInFrames": max(_frame(seg["end"]) - _frame(seg["start"]), 1),
        "variant": seg.get("variant", 0),
        "label": txt("label", 6),
        "chips": [],
        "tone": _tone(s),
    }

    chip_names = []
    if t != "logo_intro" and s.get("brand") and _norm(s["brand"]) not in {
        _norm(s.get("left_brand", "")), _norm(s.get("right_brand", ""))
    }:
        chip_names.append(s["brand"])
    chip_names += [c for c in seg.get("chips", []) if _norm(c) not in {_norm(n) for n in chip_names}]
    props["chips"] = [_logo_ref(c, seg, reg, mkey, reveal_t) for c in chip_names[:2]]

    if t == "logo_intro":
        props["logo"] = _logo_ref(s.get("brand", "") or mystery, seg, reg, mkey, reveal_t)
    elif t == "big_number":
        props["value"] = _clean(s.get("value", ""), 2, "value")
        props["unit"] = _clean(s.get("unit", ""), 3, "unit")
    elif t == "comparison":
        props["left"] = _logo_ref(s.get("left_brand", ""), seg, reg, mkey, reveal_t)
        props["right"] = _logo_ref(s.get("right_brand", ""), seg, reg, mkey, reveal_t)
        props["leftValue"] = txt("left_value", 4)
        props["rightValue"] = txt("right_value", 4)
        side = s.get("highlight_side", "")
        props["highlight"] = side if side in ("left", "right") else ""
    elif t == "timeline":
        props["year"] = _clean(s.get("year", ""), 2, "year")
        props["text"] = txt("text", 7)
    elif t == "chart":
        pts = [float(p) for p in s.get("points", []) if isinstance(p, (int, float))][:8]
        direction = s.get("direction") if s.get("direction") in ("up", "down") else ""
        if len(pts) < 2:
            pts = [2, 5, 9, 12] if direction == "up" else [12, 10, 5, 2]
        if not direction:
            direction = "up" if pts[-1] >= pts[0] else "down"
        labels = [_clean(str(x), 2, "point_labels") for x in s.get("point_labels", [])]
        props["points"] = pts
        props["pointLabels"] = labels if len(labels) == len(pts) else []
        props["direction"] = direction
        props["endValue"] = txt("end_value", 4)
    elif t == "quote":
        text = txt("text", 9) or _mask(_clean(s.get("narration", ""), 9, "narration"), mystery, seg, reveal_t)
        props["text"] = text
        props["highlight"] = [h for h in (_clean(x, 2, "highlight") for x in s.get("highlight", [])) if h]
    return props


def _captions(timings: list[dict], total_end: float) -> list[dict]:
    pages, cur = [], []

    def flush():
        if cur:
            pages.append(list(cur))
            cur.clear()

    for i, w in enumerate(timings):
        word = w["word"].strip()
        if not word:
            continue
        candidate = " ".join([x["word"] for x in cur] + [word])
        if cur and (len(cur) >= CAPTION_MAX_WORDS or len(candidate) > CAPTION_MAX_CHARS):
            flush()
        cur.append({"word": word, "start": w["start"], "end": w["end"]})
        nxt = timings[i + 1]["start"] if i + 1 < len(timings) else None
        if word.endswith(_SENTENCE_END) or word.endswith(",") or (nxt is not None and nxt - w["end"] > CAPTION_GAP_BREAK):
            flush()
    flush()

    out = []
    for i, page in enumerate(pages):
        start = page[0]["start"]
        next_start = pages[i + 1][0]["start"] if i + 1 < len(pages) else total_end
        end = min(next_start, page[-1]["end"] + 0.6)
        out.append({
            "from": _frame(start),
            "durationInFrames": max(_frame(end) - _frame(start), 1),
            "words": [
                {"text": w["word"], "start": _frame(w["start"]) - _frame(start), "end": _frame(w["end"]) - _frame(start)}
                for w in page
            ],
        })
    return out


def _outro(cfg: dict, script: dict, part_info: dict | None, start_frame: int) -> dict | None:
    oc = cfg.get("outro", {})
    if not oc.get("enabled"):
        return None
    part_text = ""
    if part_info:
        tmpl = oc.get("next_part_template") if part_info.get("next_day") else oc.get("last_part_template")
        if tmpl:
            part_text = tmpl.format(**part_info)
    return {
        "from": start_frame,
        "durationInFrames": _frame(float(oc.get("seconds", 2.5))),
        "cta": _clean(script.get("cta", ""), 12, "cta"),
        "seriesName": cfg.get("series_name", ""),
        "followText": oc.get("follow_text", ""),
        "partText": part_text,
    }


def build_props(
    script: dict,
    timings: list[dict],
    audio_path: Path,
    audio_duration: float,
    cfg: dict,
    part_info: dict | None = None,
    offline_logos: bool = False,
) -> tuple[dict, dict[str, Path]]:
    """Remotion props sözlüğü ve render public klasörüne kopyalanacak dosyaları
    ({public_yolu: kaynak}) döner."""
    raw = script.get("scenes") or []
    if not raw:
        raise PlanError("script.json'da 'scenes' yok (eski format). build_video.py --migrate ile dönüştür.")
    scenes = [Scene.model_validate(s).model_dump() for s in raw]
    reg = _LogoRegistry(offline_logos)
    _validate_comparisons(scenes, lambda b: reg.src(b) is not None)
    if not timings:
        raise PlanError("kelime zamanlamaları boş")

    starts = _align_scene_starts(scenes, timings)
    segs = []
    for i, sc in enumerate(scenes):
        start = 0.0 if i == 0 else max(starts[i] - SCENE_LEAD, 0.0)
        end = audio_duration if i == len(scenes) - 1 else max(starts[i + 1] - SCENE_LEAD, start + 0.3)
        segs.append({"scene": sc, "start": start, "end": end, "variant": 0})

    mystery = ""
    reveal_t = None
    if script.get("hook_type") == "mystery":
        reveal_t = _apply_mystery(segs, script, timings)
        if reveal_t is not None:
            mystery = (script.get("mystery_brand") or script.get("main_brand") or "").strip()
    if reveal_t is None:
        _apply_direct(segs, script)

    _enforce_min_durations(segs, reveal_t)
    segs = _split_long(segs, timings, (script.get("main_brand") or script.get("company") or "").strip())

    scene_props = [_scene_props(seg, reg, mystery, reveal_t) for seg in segs]

    # Kural 8: ses efektleri (dosya varsa).
    sfx = []
    whoosh = AUDIO_ASSETS_DIR / "whoosh.mp3"
    impact = AUDIO_ASSETS_DIR / "impact.mp3"
    files: dict[str, Path] = {"audio/narration" + audio_path.suffix: audio_path}
    if whoosh.exists():
        files["audio/whoosh.mp3"] = whoosh
        last = -99.0
        for seg, sp in zip(segs, scene_props):
            if seg["start"] > 0.2 and sp["variant"] == 0 and seg["start"] - last >= WHOOSH_MIN_GAP:
                if reveal_t is not None and abs(seg["start"] - reveal_t) < 0.5:
                    continue
                sfx.append({"src": "audio/whoosh.mp3", "from": _frame(seg["start"])})
                last = seg["start"]
    if impact.exists():
        files["audio/impact.mp3"] = impact
        hits = [reveal_t] if reveal_t is not None else []
        hits += [seg["start"] for seg, sp in zip(segs, scene_props)
                 if sp["type"] == "chart" and sp.get("direction") == "down" and sp["variant"] == 0]
        sfx += [{"src": "audio/impact.mp3", "from": _frame(t)} for t in hits]
    music = AUDIO_ASSETS_DIR / "music.mp3"
    if music.exists():
        files["audio/music.mp3"] = music

    audio_frames = _frame(audio_duration) + 1
    outro = _outro(cfg, script, part_info, audio_frames)
    total = audio_frames + (outro["durationInFrames"] if outro else _frame(0.4))

    files.update(reg.files)
    for key in ("heading", "body"):
        name = cfg["fonts"][key]
        files[f"fonts/{name}"] = FONT_DIR / name

    audio_cfg = cfg.get("audio", {})
    props = {
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "durationInFrames": total,
        "theme": {
            "palette": cfg["palette"],
            "headingFont": f"fonts/{cfg['fonts']['heading']}",
            "bodyFont": f"fonts/{cfg['fonts']['body']}",
            "badgeText": cfg.get("badge_text", ""),
            "intro": bool(cfg.get("intro", {}).get("enabled")),
        },
        "scenes": scene_props,
        "captions": _captions(timings, audio_duration),
        "audio": {
            "narration": "audio/narration" + audio_path.suffix,
            "music": "audio/music.mp3" if music.exists() else None,
            "musicVolume": 10 ** (float(audio_cfg.get("music_volume_db", -20)) / 20),
            "sfxVolume": 10 ** (float(audio_cfg.get("sfx_volume_db", -6)) / 20),
            "sfx": sfx,
        },
        "outro": outro,
    }

    print(f"      Sahne planı ({len(scene_props)} sahne, reveal={f'{reveal_t:.2f}s' if reveal_t is not None else '-'}):")
    for seg, sp in zip(segs, scene_props):
        detail = {k: v for k, v in sp.items() if k not in ("type", "from", "durationInFrames", "variant") and v}
        brief = ", ".join(
            f"{k}={v['name'] + ('?' if v['hidden'] else '') if isinstance(v, dict) else v}"
            for k, v in detail.items() if not isinstance(v, list) or k != "chips"
        )
        chips = ",".join(c["name"] + ("?" if c["hidden"] else "") for c in sp["chips"])
        print(f"        {seg['start']:5.2f}-{seg['end']:5.2f}s {sp['type']:<10} v{sp['variant']} "
              f"{brief}{' chips=' + chips if chips else ''}")
    return props, files


def write_public_dir(files: dict[str, Path], public_dir: Path) -> None:
    if public_dir.exists():
        shutil.rmtree(public_dir)
    for rel, src in files.items():
        dest = public_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
