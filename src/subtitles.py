"""Seslendirme metninden zaman kodlu .srt altyazı dosyası üretir.

Gerçek kelime-zaman hizalaması yapılmıyor (bunun için ElevenLabs'in
"timestamps" özelliği ya da ayrı bir forced-alignment aracı gerekir); bunun
yerine cümleler, toplam ses süresine karakter sayısına orantılı olarak
dağıtılır. Kısa video senaryoları için yeterince yakın bir yaklaşım."""

import re
import textwrap

_WRAP_WIDTH = 42
_MIN_SEGMENT_SECONDS = 0.8


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


def build_srt(text: str, duration: float) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return ""

    total_chars = sum(len(s) for s in sentences) or 1
    entries = []
    t = 0.0
    for i, sentence in enumerate(sentences, start=1):
        frac = len(sentence) / total_chars
        seg_duration = max(duration * frac, _MIN_SEGMENT_SECONDS)
        start = t
        end = min(t + seg_duration, duration) if i < len(sentences) else duration
        wrapped = "\n".join(textwrap.wrap(sentence, width=_WRAP_WIDTH)) or sentence
        entries.append(f"{i}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{wrapped}\n")
        t = end

    return "\n".join(entries)
