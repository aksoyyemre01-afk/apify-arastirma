"""Seslendirmede söylenen rakamların script ve ekranla karşılaştırılması.

ElevenLabs'in kelime zamanları (word_timings.json) GÖNDERİLEN metnin karakterlerine zaman
atar; sesin gerçekte ne söylediğini göstermez (TTS "11" yerine "17" dese bile orada "11"
yazar). Bu yüzden ses, yerel bir konuşma tanıma modeliyle (faster-whisper; API/ücret yok)
yazıya dökülür ve:
- script seslendirmesindeki her rakam (çoklu küme olarak) duyulan metinde bulunmalı;
- ekrandaki kartların rakamları (value/unit/year/karşılaştırma/grafik son değeri)
  seslendirme metninde geçmeli.
Uyuşmazlık varsa kontrol başarısızdır (Eleştirmen ölçümü -> QA kalır, ses yeniden üretilir).
Döküm, ses dosyası değişmedikçe stt.json'dan tekrar kullanılır.
"""

import json
import os
from collections import Counter
from pathlib import Path

from . import tr_numbers

SCREEN_FIELDS = ("value", "unit", "year", "left_value", "right_value", "end_value")
_model = None


def _whisper(model_name: str):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        _model = WhisperModel(model_name, device="cpu", compute_type="int8")
    return _model


def transcribe(audio: Path, model_name: str = "medium") -> str:
    """Sesin Türkçe dökümü; ses değişmediyse önbellekten."""
    audio = Path(audio)
    cache = audio.with_name("stt.json")
    key = {"size": audio.stat().st_size, "mtime": audio.stat().st_mtime, "model": model_name}
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("key") == key:
            return data["text"]
    segments, _ = _whisper(model_name).transcribe(str(audio), language="tr", beam_size=5,
                                                  condition_on_previous_text=False)
    text = " ".join(s.text.strip() for s in segments)
    cache.write_text(json.dumps({"key": key, "text": text}, ensure_ascii=False, indent=1), encoding="utf-8")
    return text


def _heard_in_segment(d: Path, value: float, model_name: str) -> bool:
    """value'nun script'te geçtiği kelimenin çevresi (±2 kelime) kesilip dökülür; duyuldu mu."""
    from . import proc

    timings = json.loads((d / "word_timings.json").read_text(encoding="utf-8"))
    for k, w in enumerate(timings):
        if value not in tr_numbers.numbers_in(w["word"], words=False):
            continue
        a = max(0.0, timings[max(0, k - 2)]["start"] - 0.15)
        b = timings[min(len(timings) - 1, k + 2)]["end"] + 0.15
        clip = d / "stt_bolum.wav"
        proc.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-i", str(d / "audio.mp3"),
                  "-ac", "1", "-ar", "16000", str(clip)], check=True)
        try:
            segs, _ = _whisper(model_name).transcribe(str(clip), language="tr", beam_size=5,
                                                      condition_on_previous_text=False)
            text = " ".join(s.text.strip() for s in segs)
        finally:
            clip.unlink(missing_ok=True)
        if value in tr_numbers.numbers_in(text):
            return True
    return False


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") if x == int(x) else f"{x:g}".replace(".", ",")


def compare(script: dict, heard_text: str) -> dict:
    """script: script.json içeriği. Dönen: ok, eksik (söylenmeyen), fazladan duyulan, ekranda olup
    seslendirmede olmayan rakamlar."""
    narration = script.get("narration_full") or " ".join(s["narration"] for s in script.get("scenes", []))
    expected = Counter(tr_numbers.numbers_in(narration, words=False))
    heard = Counter(tr_numbers.numbers_in(heard_text))
    missing = expected - heard
    extra = Counter({k: v for k, v in (heard - expected).items() if k in expected or k >= 10})
    # Ekran kartı, seslendirmede yazıyla geçen sayıyla da eşleşebilir ("yüzlerce" = "100'LERCE").
    narrated = set(expected) | set(tr_numbers.numbers_in(narration))
    screen = []
    for i, sc in enumerate(script.get("scenes", []), 1):
        # Değer ve birimi birlikte okunur: "9" + "MİLYAR $" = 9 milyar (seslendirmedeki gibi).
        fields = {"value": f"{sc.get('value') or ''} {sc.get('unit') or ''}".strip()}
        fields |= {f: str(sc.get(f) or "") for f in SCREEN_FIELDS if f not in ("value", "unit")}
        for f, val in fields.items():
            for n in tr_numbers.numbers_in(val, words=False) if val else []:
                if n not in narrated:
                    screen.append(f"sahne {i} {f}={val}")
    return {"ok": not missing and not screen, "missing": sorted(missing.elements()),
            "extra": sorted(extra.elements()), "screen_not_spoken": screen}


def check_dir(d: Path, model_name: str = "medium") -> dict:
    """{'spoken': (geçti, açıklama), 'screen': (geçti, açıklama)}.
    spoken: sesin söylediği rakamlar = script (döküm yapılamazsa başarısız, güvenli taraf).
    screen: ekran kartlarındaki rakamlar seslendirme metninde var mı."""
    script = json.loads((Path(d) / "script.json").read_text(encoding="utf-8"))
    screen = compare(script, "")["screen_not_spoken"]
    screen_res = (not screen, "ekranda olup seslendirmede olmayan: " + "; ".join(screen) if screen else "eşleşiyor")
    try:
        heard = transcribe(Path(d) / "audio.mp3", model_name)
    except Exception as e:  # noqa: BLE001 - model/kurulum hatası: kontrol edilemedi = geçmedi
        return {"spoken": (False, f"döküm yapılamadı ({type(e).__name__}: {e}); faster-whisper kurulu mu?"),
                "screen": screen_res}
    r = compare(script, heard)
    # İkinci görüş: tam dökümde eksik çıkan rakam, söylendiği bölüm kesilip ayrıca dökülür
    # (uzun kayıtta model yılları bazen yanlış yazar; kısa bölümde daha isabetli). Bölümde de
    # yoksa gerçekten yanlış okunmuş sayılır.
    confirmed = [n for n in r["missing"] if not _heard_in_segment(Path(d), n, model_name)]
    if len(confirmed) < len(r["missing"]):
        cleared = sorted(set(r["missing"]) - set(confirmed))
        r["missing"] = confirmed
        r["extra"] = []  # eşleşmeyen fazlalıklar büyük olasılıkla aynı yazım hatasıydı
    else:
        cleared = []
    parts = [f"bölüm kontrolüyle doğrulanan: {', '.join(map(_fmt, cleared))}"] if cleared else []
    if r["missing"]:
        parts.append("söylenmeyen/yanlış okunan: " + ", ".join(map(_fmt, r["missing"])))
    if r["extra"]:
        parts.append("fazladan duyulan: " + ", ".join(map(_fmt, r["extra"])))
    spoken = (not r["missing"], ("; ".join(parts) or "tüm rakamlar eşleşti") + f" | duyulan: \"{heard[:160]}\"")
    return {"spoken": spoken, "screen": screen_res}
