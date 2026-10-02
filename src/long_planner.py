"""Uzun video (1920x1080) sahne planı: script + kelime zamanları -> Remotion 'Long' props.

RULES.md aynen geçerlidir; uzun videoya özgü değerler (RULES.md "Uzun video" bölümü):
- en uzun sahne MAX_SCENE (8 sn), fotoğrafta MAX_PHOTO_SCENE (10 sn); uzunlar bölünür;
- 4 sn'den uzun sahnelerde her ACCENT_EVERY (3,5) sn'de bir yeni öğe (o anda söylenen kelime/
  rakam vurgusu) ekrana girer: ekran hiçbir zaman STATIC_MAX (4) sn'den fazla tamamen sabit kalmaz;
- aynı sahne tipi en fazla VARIETY_RUN (60) sn kesintisiz sürer ve her VARIETY_WINDOW (90) sn'lik
  aralıkta en az 2 farklı tip vardır;
- her bölüm, seslendirmede okunan başlığıyla bir bölüm kartıyla açılır;
- ekran metinleri/tekrarlar src/screen_rules.py ile (short'larla aynı kural) düzeltilir.
Konuya/kanala özgü hiçbir şey içermez; API isteği yapmaz (fotoğraf/logo indirmeleri hariç, ücretsiz).
"""

import re
from pathlib import Path

from . import commons, scene_planner, screen_rules
from .schemas import LongVideoScript, section_text

WIDTH, HEIGHT, FPS = 1920, 1080, scene_planner.FPS
MAX_SCENE = 8.0
MAX_PHOTO_SCENE = 10.0
ACCENT_EVERY = 3.5
STATIC_MAX = 4.0
VARIETY_RUN = 60.0
VARIETY_WINDOW = 90.0
SECTION_GAP = 0.6  # bölümler arası sessizlik (sn); ses birleştirmede de kullanılır


def flat_scenes(script: LongVideoScript) -> list[dict]:
    """Bölüm kartları dahil tüm sahneler, seslendirme sırasıyla (section anahtarıyla)."""
    out = []
    for key, sec in script.sections():
        if sec.heading.strip():
            head = section_text(type(sec)(heading=sec.heading, narration="", scenes=[]))
            out.append({"narration": head, "scene_type": "chapter", "text": sec.heading.strip(), "section": key})
        for sc in sec.scenes:
            out.append({**sc.model_dump(), "section": key})
    return out


def _subjects(script: LongVideoScript) -> list[str]:
    names = [script.main_brand]
    for _, sec in script.sections():
        for sc in sec.scenes:
            names += [sc.brand, sc.left_brand, sc.right_brand]
    return [n for n in dict.fromkeys(names) if n]


def build_props(script: LongVideoScript, timings: list[dict], audio_path: Path, audio_duration: float, cfg: dict,
                offline: bool = False) -> tuple[dict, dict[str, Path], list[dict]]:
    """(props, public dosyaları, kullanılan fotoğrafların lisans bilgisi)."""
    scenes = flat_scenes(script)
    scene_planner._enforce_spoken_numbers([s for s in scenes if s["scene_type"] != "chapter"])
    reg = scene_planner._LogoRegistry(offline)
    scene_planner._validate_comparisons(scenes, lambda b: reg.src(b) is not None)
    starts = scene_planner._align_scene_starts(scenes, timings)
    segs = []
    for i, sc in enumerate(scenes):
        start = 0.0 if i == 0 else max(starts[i] - scene_planner.SCENE_LEAD, 0.0)
        end = audio_duration if i == len(scenes) - 1 else max(starts[i + 1] - scene_planner.SCENE_LEAD, start + 0.3)
        segs.append({"scene": sc, "start": start, "end": end, "variant": 0})
    scene_planner._enforce_min_durations(segs, None)

    # Fotoğraflar: lisanslı görsel yoksa sahne logo kartına (logo da yoksa alıntıya) döner.
    files: dict[str, Path] = {}
    credits: list[dict] = []
    for seg in segs:
        sc = seg["scene"]
        if sc["scene_type"] != "photo":
            continue
        meta = commons.resolve(sc.get("brand", ""), offline=offline) if sc.get("brand") else None
        if meta:
            rel = f"photos/{Path(meta['path']).name}"
            files[rel] = Path(meta["path"])
            seg["photo"] = {"name": sc["brand"], "src": rel}
            if meta not in credits:
                credits.append({k: v for k, v in meta.items() if k != "path"})
        else:
            sc["scene_type"] = "logo_intro" if reg.src(sc.get("brand", "")) else "quote"

    segs = _split_long(segs, timings)
    props_scenes = [_scene_props(seg, reg) for seg in segs]
    screen_rules.enforce(props_scenes, timings, FPS, _subjects(script),
                         lambda b: scene_planner._logo_ref(b, {"start": 0, "end": 0}, reg, "", None))
    _add_accents(props_scenes, timings)

    audio_frames = scene_planner._frame(audio_duration) + 1
    outro = scene_planner._outro(cfg, {"cta": script.cta}, None, audio_frames)
    total = audio_frames + (outro["durationInFrames"] if outro else scene_planner._frame(0.4))
    files.update(reg.files)
    files["audio/narration" + audio_path.suffix] = audio_path
    for key in ("heading", "body"):
        files[f"fonts/{cfg['fonts'][key]}"] = scene_planner.FONT_DIR / cfg["fonts"][key]
    sfx = _sfx(props_scenes, audio_path, cfg.get("audio", {}), files)
    props = {
        "fps": FPS, "width": WIDTH, "height": HEIGHT, "durationInFrames": total,
        "theme": {"palette": cfg["palette"], "headingFont": f"fonts/{cfg['fonts']['heading']}",
                  "bodyFont": f"fonts/{cfg['fonts']['body']}", "badgeText": cfg.get("badge_text", ""),
                  "intro": bool(cfg.get("intro", {}).get("enabled"))},
        "scenes": props_scenes,
        "captions": scene_planner._captions(timings, audio_duration),
        "audio": {"narration": "audio/narration" + audio_path.suffix, "music": None, "musicVolume": 0.0,
                  "sfxVolume": 1.0, "sfx": sfx},
        "outro": outro,
    }
    return props, files, credits


def _split_long(segs: list[dict], timings: list[dict]) -> list[dict]:
    """8 sn'den (fotoğrafta 10 sn'den) uzun sahneler eşit parçalara bölünür; ilk parça
    orijinal sahne, sonrakiler o anda söylenen kelimelerin alıntısıdır (screen_rules gerekirse
    rakam/yıl/logo kartına çevirir ve tekrarı önler)."""
    out = []
    for seg in segs:
        limit = MAX_PHOTO_SCENE if seg["scene"]["scene_type"] == "photo" else MAX_SCENE
        dur = seg["end"] - seg["start"]
        n = max(1, -(-int(dur * 1000) // int(limit * 1000)))
        step = dur / n
        for k in range(n):
            part = dict(seg, start=seg["start"] + k * step, end=seg["start"] + (k + 1) * step)
            if k:
                win = screen_rules._Window(timings, part["start"], part["end"])
                part["scene"] = {**seg["scene"], "scene_type": "quote", "text": win.phrase(), "highlight": [],
                                 "label": "", "value": "", "unit": "", "year": ""}
                part.pop("photo", None)
            out.append(part)
    return out


def _scene_props(seg: dict, reg) -> dict:
    sc = seg["scene"]
    if sc["scene_type"] == "chapter":
        return {"type": "chapter", "from": scene_planner._frame(seg["start"]),
                "durationInFrames": max(scene_planner._frame(seg["end"]) - scene_planner._frame(seg["start"]), 1),
                "variant": 0, "label": "", "chips": [], "tone": "neutral", "title": sc["text"]}
    if sc["scene_type"] == "photo":
        p = scene_planner._scene_props(dict(seg, scene={**sc, "scene_type": "quote", "brand": ""}), reg, "", None)
        p.update(type="photo", photo=seg.get("photo"), label=sc.get("label", ""))
        p.pop("text", None)
        p.pop("highlight", None)
        return p
    return scene_planner._scene_props(seg, reg, "", None)


def _add_accents(scenes: list[dict], timings: list[dict]) -> None:
    """4 sn'den uzun sahnelere her ~3,5 sn'de bir, o anda söylenen bir kelime/rakam vurgusu."""
    used: set[str] = set()
    for sc in scenes:
        a, b = sc["from"] / FPS, (sc["from"] + sc["durationInFrames"]) / FPS
        if b - a <= STATIC_MAX:
            continue
        shown = " ".join(screen_rules._fields(sc).values()).lower()
        accents, t = [], a + min(ACCENT_EVERY, (b - a) / 2)
        while t < b - 0.3:
            cands = [w for w in timings if t - 1.2 <= w["start"] <= t + 0.8 and w["start"] < b - 0.3]
            pick = _best_word(cands, used, shown) or _best_word(
                [w for w in timings if a + 1.0 <= w["start"] < min(b - 0.3, t + STATIC_MAX - ACCENT_EVERY + 0.4)], used, "")
            if pick:
                at = scene_planner._frame(max(pick["start"], a + 0.2)) - sc["from"]
                accents.append({"at": at, "text": pick["word"].strip(".,!?;:\"'’").upper()})
                used.add(screen_rules._norm(pick["word"]))
                t = pick["start"] + ACCENT_EVERY
            else:
                t += 0.5
        if accents:
            sc["accents"] = accents


def _best_word(words: list[dict], used: set[str], shown: str) -> dict | None:
    def score(w):
        tok = screen_rules._norm(w["word"])
        if not tok or tok in used or tok in screen_rules._DANGLING or len(tok) < 4:
            return -1
        return (2 if re.search(r"\d", tok) else 1) * len(tok) - (5 if tok in shown else 0)
    best = max(words, key=score, default=None)
    return best if best and score(best) > 0 else None


def _sfx(scenes: list[dict], audio: Path, audio_cfg: dict, files: dict) -> list[dict]:
    whoosh = scene_planner.AUDIO_ASSETS_DIR / "whoosh.mp3"
    if not whoosh.exists():
        return []
    files["audio/whoosh.mp3"] = whoosh
    vol = scene_planner._sfx_gain(audio, whoosh, float(audio_cfg.get("whoosh_below_voice_db", 12)))
    out, last = [], -99.0
    for sc in scenes:
        t = sc["from"] / FPS
        if t > 0.2 and t - last >= 1.5 and sc["type"] in ("chapter", "photo", "big_number", "timeline"):
            out.append({"src": "audio/whoosh.mp3", "from": sc["from"], "volume": vol})
            last = t
    return out


# ---------------------------------------------------------------------------- ölçümler (Eleştirmen)

def static_violations(props: dict) -> list[str]:
    """Ekranın 4 sn'den fazla tamamen sabit kaldığı sahneler (yeni öğe girişleri arası boşluk)."""
    out = []
    for i, sc in enumerate(props["scenes"], 1):
        dur = sc["durationInFrames"] / FPS
        if dur <= STATIC_MAX:
            continue
        marks = [0.0] + [a["at"] / FPS for a in sc.get("accents") or []] + [dur]
        gap = max(b - a for a, b in zip(marks, marks[1:]))
        if gap > STATIC_MAX + 0.05:
            out.append(f"sahne {i} ({sc['from'] / FPS:.1f} sn, {sc['type']}, {dur:.1f} sn): {gap:.1f} sn yeni öğe yok")
    return out


def variety_violations(props: dict) -> list[str]:
    """Aynı tip 60 sn'den uzun kesintisiz ya da 90 sn'lik bir aralıkta tek tip."""
    out, scenes = [], props["scenes"]
    run_start, run_type = 0.0, None
    for sc in scenes + [{"type": None, "from": props["durationInFrames"], "durationInFrames": 0}]:
        t = sc["from"] / FPS
        if sc["type"] != run_type:
            if run_type and t - run_start > VARIETY_RUN:
                out.append(f"{run_start:.0f}-{t:.0f} sn: {t - run_start:.0f} sn kesintisiz '{run_type}'")
            run_start, run_type = t, sc["type"]
    end = scenes[-1]["from"] / FPS + scenes[-1]["durationInFrames"] / FPS if scenes else 0
    w = 0.0
    while w + VARIETY_WINDOW <= end:
        types = {sc["type"] for sc in scenes if sc["from"] / FPS < w + VARIETY_WINDOW and (sc["from"] + sc["durationInFrames"]) / FPS > w}
        if len(types) < 2:
            out.append(f"{w:.0f}-{w + VARIETY_WINDOW:.0f} sn aralığında tek sahne tipi ({', '.join(types)})")
        w += 15.0
    return out


def max_scene_violations(props: dict) -> list[str]:
    out = []
    for i, sc in enumerate(props["scenes"], 1):
        limit = MAX_PHOTO_SCENE if sc["type"] == "photo" else MAX_SCENE
        if sc["durationInFrames"] / FPS > limit + 0.05:
            out.append(f"sahne {i} ({sc['type']}) {sc['durationInFrames'] / FPS:.1f} sn > {limit:g} sn")
    return out


def chapter_marks(section_starts: dict[str, float], script: LongVideoScript) -> list[tuple[float, str]]:
    """YouTube bölüm zaman damgaları: 0:00 Giriş, her bölüm, Kapanış."""
    marks = [(0.0, "Giriş")]
    for i, ch in enumerate(script.chapters, 1):
        marks.append((section_starts[f"bolum-{i}"], ch.heading.strip()))
    marks.append((section_starts["kapanis"], "Kapanış"))
    return marks


def chapter_problems(marks: list[tuple[float, str]], total: float) -> list[str]:
    """YouTube kuralları: ilki 0:00, en az 3 bölüm, her biri en az 10 sn."""
    out = []
    if not marks or marks[0][0] != 0:
        out.append("ilk bölüm 0:00'da değil")
    if len(marks) < 3:
        out.append(f"{len(marks)} bölüm (en az 3)")
    ends = [m[0] for m in marks[1:]] + [total]
    out += [f"'{t}' {e - s:.0f} sn (< 10 sn)" for (s, t), e in zip(marks, ends) if e - s < 10]
    return out


def fmt_ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"
