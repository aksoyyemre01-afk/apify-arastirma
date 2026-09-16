"""script.json + audio.mp3'ten ffmpeg ile dikey (9:16) YouTube Shorts videosu üretir.

Adımlar:
1. script.json'daki her sahne (hook/setup/twist bölümlerindeki visual_notes) için
   Gemini ile spesifik/sinematik bir İngilizce arama sorgusu üretilir - twist
   sahneleri dramatik/kriz temalı modifiyerlerle güçlendirilir. Pexels'ten (önce
   video, sonra foto), bulunamazsa Pixabay'den en yüksek çözünürlüklü klip
   indirilir; art arda iki sahne aynı türde (ikisi de foto/video) olmasın diye
   önceki sahnenin türü bir sonrakinde dışlanır. Hiçbir kaynak bulunamazsa düz
   renkli bir placeholder sahne kullanılır.
2. Her klip, ses süresine eşit paylaştırılmış bir segment uzunluğuna
   sığdırılıp 1080x1920'ye ölçeklenir/kırpılır.
3. Segmentler art arda eklenir (concat), seslendirme ile birleştirilir, üzerine
   kelime-kelime senkronize, büyük/kalın dinamik altyazı gömülür (ElevenLabs'in
   ürettiği gerçek kelime zaman kodları varsa onlar, yoksa tahmini zamanlama).

Eski (hook/setup/twist'ten önceki) düz `visual_notes` formatındaki script.json'lar
da desteklenir - bkz. _extract_scenes.
"""

import json
import shutil
import subprocess
from pathlib import Path

from . import keywords, stock_media, subtitles

WIDTH = 1080
HEIGHT = 1920
FPS = 25

PLACEHOLDER_COLORS = ["0x1a1a2e", "0x16213e", "0x0f3460", "0x533483", "0x2d132c", "0x122620"]


class VideoBuildError(RuntimeError):
    pass


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoBuildError(
            f"ffmpeg komutu başarısız oldu:\n{' '.join(str(c) for c in cmd)}\n\n{result.stderr[-4000:]}"
        )


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise VideoBuildError(f"ffprobe ses süresini okuyamadı: {path}\n{result.stderr}")
    return float(result.stdout.strip())


def _build_segment_from_video(src: Path, dest: Path, duration: float) -> None:
    _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf",
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(dest),
    ])


def _build_segment_from_photo(src: Path, dest: Path, duration: float) -> None:
    frames = max(int(duration * FPS), 1)
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(src),
        "-vf",
        f"scale={WIDTH * 2}:{HEIGHT * 2}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH * 2}:{HEIGHT * 2},"
        f"zoompan=z='min(zoom+0.0015,1.3)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(dest),
    ])


def _build_segment_placeholder(dest: Path, duration: float, index: int) -> None:
    color = PLACEHOLDER_COLORS[index % len(PLACEHOLDER_COLORS)]
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s={WIDTH}x{HEIGHT}:d={duration:.3f}:r={FPS}",
        "-pix_fmt", "yuv420p",
        str(dest),
    ])


def _ffmpeg_filter_path(path: Path) -> str:
    """subtitles= filter argümanı için path'i (Windows sürücü harfi dahil) güvenli hale getirir."""
    p = str(path.resolve()).replace("\\", "/")
    p = p.replace(":", "\\:")
    return p


def _extract_scenes(data: dict) -> tuple[list[dict], str]:
    """script.json'dan sahneleri ve tam seslendirme metnini çıkarır.

    Yeni format (hook/setup/twist beat yapısı) ve eski format (düz visual_notes
    listesi) her ikisi de desteklenir. Döndürülen her sahne
    {"note": str, "dramatic": bool} şeklindedir - dramatic=True sadece twist
    bölümündeki sahnelerde olur."""
    hook = data.get("hook")
    if isinstance(hook, dict):
        scenes = []
        narration_parts = []
        for beat_name, dramatic in (("hook", False), ("setup", False), ("twist", True)):
            beat = data.get(beat_name) or {}
            narration_parts.append(beat.get("narration", ""))
            for note in beat.get("visual_notes", []):
                scenes.append({"note": note, "dramatic": dramatic})
        narration = data.get("narration_full") or " ".join(narration_parts)
        return scenes, narration

    # eski format: düz visual_notes listesi + narration
    visual_notes = data.get("visual_notes") or []
    scenes = [{"note": n, "dramatic": False} for n in visual_notes]
    narration = data.get("narration", "")
    return scenes, narration


def build_video(video_dir: Path, keep_assets: bool = False) -> Path:
    video_dir = Path(video_dir)
    script_path = video_dir / "script.json"
    audio_path = video_dir / "audio.mp3"

    if not script_path.exists():
        raise VideoBuildError(f"script.json bulunamadı: {script_path}")
    if not audio_path.exists():
        raise VideoBuildError(
            f"audio.mp3 bulunamadı: {audio_path} (önce ElevenLabs ile seslendirme üretilmeli, "
            f"örn. python run.py --mode shorts ... veya src.tts.synthesize)"
        )

    data = json.loads(script_path.read_text(encoding="utf-8"))
    scenes, narration = _extract_scenes(data)
    if not scenes:
        raise VideoBuildError(
            "script.json içinde görsel sahne bulunamadı (ne hook/setup/twist ne de "
            "visual_notes). Video oluşturma şu an sadece short senaryoları için destekleniyor."
        )
    company_hint = data.get("title", "")

    total_duration = _probe_duration(audio_path)
    segment_count = len(scenes)
    seg_duration = total_duration / segment_count

    assets_dir = video_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    seg_paths = []
    print(f"Toplam ses süresi: {total_duration:.1f} sn, {segment_count} sahne (~{seg_duration:.1f} sn/sahne)")
    last_kind: str | None = None
    for i, scene in enumerate(scenes):
        note, dramatic = scene["note"], scene["dramatic"]
        query = keywords.to_search_query(note, company=company_hint, dramatic=dramatic)
        tag = " [DRAMATİK]" if dramatic else ""
        print(f"  [{i + 1}/{segment_count}]{tag} \"{note[:60]}\" -> arama: \"{query}\"")
        clip = stock_media.fetch_clip(query, assets_dir, i, exclude_kind=last_kind)
        seg_path = assets_dir / f"seg_{i:02d}.mp4"

        if clip is None:
            print("      stok görsel/video bulunamadı, placeholder sahne kullanılıyor")
            _build_segment_placeholder(seg_path, seg_duration, i)
        elif clip["kind"] == "video":
            _build_segment_from_video(clip["path"], seg_path, seg_duration)
            last_kind = "video"
        else:
            _build_segment_from_photo(clip["path"], seg_path, seg_duration)
            last_kind = "photo"
        seg_paths.append(seg_path)

    concat_list = assets_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve().as_posix()}'" for p in seg_paths), encoding="utf-8"
    )
    visual_track = assets_dir / "visual_track.mp4"
    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy",
        str(visual_track),
    ])

    timings_path = video_dir / "word_timings.json"
    if timings_path.exists():
        word_timings = json.loads(timings_path.read_text(encoding="utf-8"))
    else:
        word_timings = subtitles.estimate_word_timings(narration, total_duration)

    captions_path = video_dir / "captions.srt"
    captions_path.write_text(subtitles.build_word_srt(word_timings), encoding="utf-8")

    output_path = video_dir / "video.mp4"
    subtitle_arg = _ffmpeg_filter_path(captions_path)
    encode_args = [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
    ]
    try:
        _run(
            ["ffmpeg", "-y", "-i", str(visual_track), "-i", str(audio_path)]
            + [
                "-vf",
                f"subtitles='{subtitle_arg}':force_style="
                f"'PlayResX={WIDTH},PlayResY={HEIGHT},"
                "Fontsize=34,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=140,MarginL=48,MarginR=48'",
            ]
            + encode_args
            + [str(output_path)]
        )
    except VideoBuildError as e:
        print("UYARI: Altyazı gömme başarısız oldu, altyazısız devam ediliyor.")
        print(str(e)[:800])
        _run(
            ["ffmpeg", "-y", "-i", str(visual_track), "-i", str(audio_path)]
            + encode_args
            + [str(output_path)]
        )

    if not keep_assets:
        shutil.rmtree(assets_dir, ignore_errors=True)

    return output_path
