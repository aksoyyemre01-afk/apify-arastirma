"""Arka plan müziği ve ses efektlerini (whoosh, impact) seslendirmenin üzerine
miksajlar (RULES.md kural 18). assets/audio/ altındaki music.mp3/whoosh.mp3/
impact.mp3 dosyaları (varsa) kullanılır; hiçbiri yoksa seslendirme olduğu gibi
kopyalanır - eksik asset video üretimini asla durdurmaz.
"""

import shutil
import subprocess
from pathlib import Path

AUDIO_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
MUSIC_PATH = AUDIO_ASSETS_DIR / "music.mp3"
WHOOSH_PATH = AUDIO_ASSETS_DIR / "whoosh.mp3"
IMPACT_PATH = AUDIO_ASSETS_DIR / "impact.mp3"

# RULES.md kural 18: müzik, seslendirmenin -18/-22 dB altında olmalı.
MUSIC_DB = -20


class AudioMixError(RuntimeError):
    pass


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AudioMixError(result.stderr[-2000:])


def mix(
    narration_path: Path,
    duration: float,
    dest_path: Path,
    whoosh_at: list[float] | None = None,
    impact_at: list[float] | None = None,
) -> Path:
    """narration_path'in üzerine (varsa) music.mp3'ü -18/-22dB aralığında
    döngüleyerek, whoosh_at/impact_at (saniye) zaman damgalarında (varsa)
    whoosh.mp3/impact.mp3'ü ekleyerek dest_path'e yeni bir ses dosyası yazar.
    Hiçbir asset dosyası bulunamazsa (ya da ffmpeg miksajı başarısız olursa)
    narration'ı değiştirmeden dest_path'e kopyalar."""
    whoosh_at = whoosh_at or []
    impact_at = impact_at or []

    inputs = ["-i", str(narration_path)]
    filter_parts = []
    mix_labels = ["[0:a]"]
    idx = 1

    if MUSIC_PATH.exists():
        inputs += ["-stream_loop", "-1", "-i", str(MUSIC_PATH)]
        filter_parts.append(f"[{idx}:a]atrim=0:{duration:.3f},volume={MUSIC_DB}dB[music]")
        mix_labels.append("[music]")
        idx += 1

    for t in whoosh_at:
        if not WHOOSH_PATH.exists():
            continue
        inputs += ["-i", str(WHOOSH_PATH)]
        filter_parts.append(f"[{idx}:a]adelay={int(t * 1000)}|{int(t * 1000)}[sfx{idx}]")
        mix_labels.append(f"[sfx{idx}]")
        idx += 1

    for t in impact_at:
        if not IMPACT_PATH.exists():
            continue
        inputs += ["-i", str(IMPACT_PATH)]
        filter_parts.append(f"[{idx}:a]adelay={int(t * 1000)}|{int(t * 1000)}[sfx{idx}]")
        mix_labels.append(f"[sfx{idx}]")
        idx += 1

    if len(mix_labels) == 1:
        shutil.copy(narration_path, dest_path)
        return dest_path

    filter_complex = (
        ";".join(filter_parts)
        + ";"
        + "".join(mix_labels)
        + f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0[out]"
    )
    try:
        _run([
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", f"{duration:.3f}",
            str(dest_path),
        ])
    except AudioMixError:
        shutil.copy(narration_path, dest_path)
    return dest_path
