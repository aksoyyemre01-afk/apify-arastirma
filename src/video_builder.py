"""script.json + audio.mp3'ten ffmpeg ile dikey (9:16) YouTube Shorts videosu üretir.

RULES.md'deki kuralları uygular (özellikle 1, 4, 5, 6, 7, 11, 14):
1. Her sahne için src/keywords.py, şirket adıyla BAŞLAYAN, somut/gösterilebilir bir
   İngilizce arama sorgusu üretir (kural 1, 5). İlk sahne, script'in kendi notundan
   bağımsız olarak `"{company} logo"` aramasına zorlanır - marka en az bir sahnede
   garanti görünür (kural 4). Pexels'ten (önce video, sonra foto), bulunamazsa
   Pixabay'den birden fazla aday toplanır; her aday önce ucuz bir etiket/keyword
   ön filtresinden, sonra src/relevance.py ile Gemini vision kontrolünden geçer
   (kural 6). Aynı videoda aynı URL bir daha kullanılmaz, art arda iki sahne aynı
   türde (foto/video) olmaz (kural 7). Hiçbir aday geçemezse son çare olarak
   `"{company} logo"` denenir, o da bulunamazsa placeholder sahne kullanılır -
   tamamen kopuk bir görsel asla kullanılmaz.
2. Hiçbir sahne 4 saniyeden uzun ekranda kalmaz (kural 11) - sahne süresi bunu
   aşarsa aynı notu paylaşan alt-kesimlere bölünür. Her klip, segment uzunluğuna
   sığdırılıp 1080x1920'ye ölçeklenir/kırpılır (ortalanmış kırpma, kural 10).
3. Segmentler art arda eklenir (concat), seslendirme ile birleştirilir, üzerine
   kelime kelime BİRİKEREK büyüyen (statik cümle bloğu ya da tek kelime yerine),
   büyük/kalın dinamik altyazı gömülür (kural 14) (ElevenLabs'in ürettiği gerçek
   kelime zaman kodları varsa onlar, yoksa tahmini zamanlama).

Eski (hook/setup/twist'ten önceki) düz `visual_notes` formatındaki script.json'lar
da desteklenir - bkz. _extract_scenes.
"""

import json
import shutil
import subprocess
from math import ceil
from pathlib import Path

from . import keywords, stock_media, subtitles

WIDTH = 1080
HEIGHT = 1920
FPS = 25

# RULES.md kural 11: hiçbir görsel 4 saniyeden uzun ekranda kalmaz.
MAX_SCENE_SECONDS = 4.0

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
    # Eski script.json'larda "company" alanı yoktur; bu durumda görsel başlığa düşülür
    # (idealden az anlamlı olsa da company hiç olmamasından daha iyi).
    company_hint = data.get("company") or data.get("title", "")
    topic_context = data.get("topic_context", "")

    total_duration = _probe_duration(audio_path)

    # Kural 11: hiçbir sahne 4 saniyeden uzun kalmasın - eşit paylaşımda sahne
    # süresi bunu aşıyorsa, her sahneyi aynı notu/sorguyu paylaşan alt-kesimlere böl
    # (used_urls dedup sayesinde her alt-kesim farklı bir aday görsel/klip alır).
    raw_seg_duration = total_duration / len(scenes)
    if raw_seg_duration > MAX_SCENE_SECONDS:
        sub_count = max(1, ceil(raw_seg_duration / MAX_SCENE_SECONDS))
        scenes = [scene for scene in scenes for _ in range(sub_count)]
    segment_count = len(scenes)
    seg_duration = total_duration / segment_count

    assets_dir = video_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    seg_paths = []
    used_urls: set[str] = set()
    print(f"Toplam ses süresi: {total_duration:.1f} sn, {segment_count} sahne (~{seg_duration:.1f} sn/sahne)")
    last_kind: str | None = None
    for i, scene in enumerate(scenes):
        note, dramatic = scene["note"], scene["dramatic"]

        # Kural 4: en az bir sahne (ilk sahne) markanın logosunu/adını garanti gösterir -
        # konuyu bilmeyen izleyici bile görsellerden neyden bahsedildiğini anlayabilsin.
        if i == 0 and company_hint:
            query = f"{company_hint} logo"
        else:
            query = keywords.to_search_query(
                note, company=company_hint, context=topic_context, dramatic=dramatic
            )
        tag = " [DRAMATİK]" if dramatic else (" [MARKA]" if i == 0 else "")
        print(f"  [{i + 1}/{segment_count}]{tag} \"{note[:60]}\" -> arama: \"{query}\"")

        clip = stock_media.fetch_clip(
            query, note, assets_dir, i, exclude_kind=last_kind, company=company_hint, used_urls=used_urls
        )
        if clip is None and company_hint and query != f"{company_hint} logo":
            # Kural 6: son çare - konuya en azından şirket adı üzerinden bağlı bir
            # görsel dene (tamamen kopuk bir görsel yerine).
            print("      alakalı sonuç yok, son çare olarak marka logosu deneniyor")
            clip = stock_media.fetch_clip(
                f"{company_hint} logo", note, assets_dir, i,
                exclude_kind=last_kind, company=company_hint, used_urls=used_urls,
            )
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
    captions_path.write_text(subtitles.build_cumulative_srt(word_timings), encoding="utf-8")

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
                "Fontsize=38,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
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
