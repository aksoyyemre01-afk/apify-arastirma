"""Seslendirme metninden/zaman kodlarından dikey video için altyazı (.srt) üretir.

- estimate_word_timings: gerçek zaman kodu yoksa (ör. dry-run, ya da ElevenLabs
  timestamp endpoint'i kullanılamadıysa), metni ses süresine kelime uzunluğuna
  orantılı olarak dağıtan bir tahmin üretir.
- build_cumulative_srt: kelime bazlı zaman kodlarından (gerçek ya da tahmini),
  o ana kadar birikmiş öbeği gösteren dinamik altyazı üretir
  (ör. "Nokia," -> "Nokia, cebinde" -> "Nokia, cebinde taşıdığımız..."),
  statik tam cümle bloğu ya da tek kelime yerine.
"""

_MIN_WORD_SECONDS = 0.12
_MAX_WORDS_PER_CHUNK = 6
_SENTENCE_END_CHARS = (".", "!", "?", "…")


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


def build_cumulative_srt(word_timings: list[dict]) -> str:
    """Kelime bazlı zaman kodlarından, her yeni kelimede bir öncekinin üzerine eklenen
    ("birikimli") dinamik bir .srt üretir: "Nokia," -> "Nokia, cebinde" -> "Nokia,
    cebinde taşıdığımız...". Birikim, cümle sonunda (./!/?) ya da öbek
    `_MAX_WORDS_PER_CHUNK` kelimeyi aşınca sıfırlanıp yeniden başlar (okunabilirlik
    ve ekran genişliği için)."""
    if not word_timings:
        return ""

    entries = []
    index = 1
    chunk: list[dict] = []

    for i, w in enumerate(word_timings):
        chunk.append(w)
        is_last_overall = i == len(word_timings) - 1
        next_start = word_timings[i + 1]["start"] if not is_last_overall else None

        text = " ".join(item["word"] for item in chunk)
        # Cue, bu kelimenin başlangıcından bir sonraki kelime eklenene (ya da
        # cümle/öbek bitene) kadar birikmiş metni gösterir.
        start = w["start"]
        end = next_start if next_start is not None else w["end"]
        entries.append(f"{index}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{text}\n")
        index += 1

        ends_sentence = w["word"].rstrip().endswith(_SENTENCE_END_CHARS)
        chunk_full = len(chunk) >= _MAX_WORDS_PER_CHUNK
        if ends_sentence or chunk_full or is_last_overall:
            chunk = []

    return "\n".join(entries)
