"""Seslendirme metninden/zaman kodlarından dikey video için altyazı (.srt) üretir.

İki mod var:
- build_word_srt: ElevenLabs'in "with-timestamps" endpoint'inden gelen gerçek kelime
  zaman kodlarını kullanır (hassas, kelime kelime senkronize).
- estimate_word_timings + build_word_srt: gerçek zaman kodu yoksa (ör. dry-run, ya da
  ElevenLabs timestamp endpoint'i kullanılamadıysa), metni ses süresine kelime uzunluğuna
  orantılı olarak dağıtan bir tahmin üretir. Yine kelime-kelime görünür, sadece zamanlama
  daha az hassastır.
"""

_MIN_WORD_SECONDS = 0.12


def _format_timestamp(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        millis = 0
        secs += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def estimate_word_timings(text: str, duration: float) -> list[dict]:
    """Gerçek zaman kodu yokken, kelimeleri ses süresine karakter sayısına orantılı
    dağıtan bir tahmin üretir. [{'word':.., 'start':.., 'end':..}, ...] döner."""
    words = text.split()
    if not words:
        return []

    total_chars = sum(len(w) for w in words) or 1
    entries = []
    t = 0.0
    for word in words:
        frac = len(word) / total_chars
        seg_duration = max(duration * frac, _MIN_WORD_SECONDS)
        start = t
        end = min(t + seg_duration, duration)
        entries.append({"word": word, "start": start, "end": end})
        t = end

    if entries:
        entries[-1]["end"] = duration
    return entries


def build_word_srt(word_timings: list[dict]) -> str:
    """Kelime bazlı zaman kodlarından, her kelimenin kendi kısa cue'su olduğu, dinamik
    "kelime kelime" tarzı bir .srt üretir (statik cümle bloğu yerine)."""
    entries = []
    for i, w in enumerate(word_timings, start=1):
        entries.append(
            f"{i}\n{_format_timestamp(w['start'])} --> {_format_timestamp(w['end'])}\n{w['word']}\n"
        )
    return "\n".join(entries)
