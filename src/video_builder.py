"""script.json + audio.mp3'ten ffmpeg ile dikey (9:16) YouTube Shorts videosu üretir.

RULES.md'deki kuralları uygular (bkz. dosyanın kendisi için tam liste):
1. Her sahne için önce src/media_router.py, RULES.md kural 15'teki kaynak
   önceliğini dener: üretilen grafik (rakam/karşılaştırma içeren notlar) ->
   Wikimedia Commons -> Wayback Machine (marka-çapa/website notları) ->
   Pexels/Pixabay (son çare). İlk sahne her zaman "{company} logo" aramasına
   zorlanır (marka en az bir sahnede garanti görünür). Hiçbir kaynak uygun bir
   şey bulamazsa son çare olarak yine "{company} logo" denenir, o da
   bulunamazsa placeholder sahne kullanılır. Her sahne için kullanılan kaynak
   ve sorgu konsola yazdırılır (kural 21).
2. Hiçbir sahne 3 saniyeden uzun ekranda kalmaz - sahne süresi bunu aşarsa
   aynı notu paylaşan alt-kesimlere bölünür. Fotoğraf/üretilen grafik kaynaklı
   sahnelere Ken Burns (yavaş zoom) efekti uygulanır, hiçbir görsel sabit
   durmaz. Her klip 1080x1920'ye ölçeklenir/kırpılır (ortalanmış kırpma).
3. Segmentler art arda eklenir (concat), seslendirme ile birleştirilir, üzerine
   kelime kelime BİRİKEREK büyüyen dinamik altyazı gömülür. Seslendirmenin
   üzerine (varsa) src/audio_mix.py ile arka plan müziği + whoosh/impact efektleri
   miksajlanır. video_dir içinde bir hook.mp4 varsa (kullanıcının kendi çektiği
   2-4 sn'lik dikey açılış klibi), video ONUNLA başlar, seslendirme ondan sonra
   devam eder.

Eski (hook/setup/twist'ten önceki) düz `visual_notes` formatındaki script.json'lar
da desteklenir - bkz. _extract_scenes.
"""

import json
import shutil
import subprocess
from math import ceil
from pathlib import Path

from . import audio_mix, graphics, keywords, media_router, subtitles

WIDTH = 1080
HEIGHT = 1920
FPS = 25

# RULES.md kural 17: hiçbir görsel 2-3 saniyeden uzun ekranda kalmaz (önceki
# 4sn'lik kuralın yerine geçer - yeni kurallar çelişkide önceliklidir).
MAX_SCENE_SECONDS = 3.0

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
        raise VideoBuildError(f"ffprobe süresini okuyamadı: {path}\n{result.stderr}")
    return float(result.stdout.strip())


def _build_segment_from_video(src: Path, dest: Path, duration: float, keep_audio: bool = False) -> None:
    audio_args = ["-c:a", "aac", "-b:a", "192k"] if keep_audio else ["-an"]
    _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf",
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}",
        *audio_args, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(dest),
    ])


def _build_segment_from_photo(src: Path, dest: Path, duration: float) -> None:
    """Fotoğraf/üretilen grafik sahnelerine Ken Burns (yavaş zoom) efekti uygular -
    hiçbir görsel sabit durmaz."""
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


def _build_segment_from_logo(src: Path, dest: Path, duration: float) -> None:
    """Logo sahneleri için: src zaten graphics.compose_logo_on_background() ile
    tam WIDTHxHEIGHT boyutunda, düz zemine ortalanmış olarak üretildi - burada
    KIRPMA yapılmaz, sadece hafif (en fazla %8) bir zoom uygulanır ki logonun
    tamamı her zaman görünür kalsın (kural 22)."""
    frames = max(int(duration * FPS), 1)
    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(src),
        "-vf",
        f"scale={WIDTH}:{HEIGHT},"
        f"zoompan=z='min(zoom+0.0006,1.08)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1",
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
    {"note": str, "dramatic": bool, "beat_narration": str} şeklindedir -
    dramatic=True sadece twist bölümündeki sahnelerde olur; beat_narration, o
    notun ait olduğu bölümün TAM seslendirme metnidir (kural 23 - notta geçmeyen
    ama aynı bölümde SESLENDİRİLEN bir rakamı/markayı da yakalayabilmek için)."""
    hook = data.get("hook")
    if isinstance(hook, dict):
        scenes = []
        narration_parts = []
        for beat_name, dramatic in (("hook", False), ("setup", False), ("twist", True)):
            beat = data.get(beat_name) or {}
            beat_narration = beat.get("narration", "")
            narration_parts.append(beat_narration)
            for note in beat.get("visual_notes", []):
                scenes.append({"note": note, "dramatic": dramatic, "beat_narration": beat_narration})
        narration = data.get("narration_full") or " ".join(narration_parts)
        return scenes, narration

    # eski format: düz visual_notes listesi + narration
    visual_notes = data.get("visual_notes") or []
    full_narration = data.get("narration", "")
    scenes = [{"note": n, "dramatic": False, "beat_narration": full_narration} for n in visual_notes]
    return scenes, full_narration


def _build_visual_track(
    scenes: list[dict], seg_duration: float, company_hint: str, topic_context: str, assets_dir: Path
) -> tuple[Path, list[float], list[float]]:
    """Sahneleri sırayla çözüp segment videolarını üretir, art arda ekler.
    (visual_track_path, whoosh_at, impact_at) döner - whoosh_at üretilen grafik
    kullanılan sahnelerin, impact_at ise ilk dramatik sahnenin başlangıç zamanı."""
    segment_count = len(scenes)
    seg_paths = []
    used_urls: set[str] = set()
    used_stats: set[str] = set()
    whoosh_at: list[float] = []
    impact_at: list[float] = []
    last_kind: str | None = None

    print(f"Toplam ses süresi hesaplandı, {segment_count} sahne (~{seg_duration:.1f} sn/sahne)")
    for i, scene in enumerate(scenes):
        note, dramatic = scene["note"], scene["dramatic"]
        beat_narration = scene.get("beat_narration", "")
        allow_card = scene.get("allow_generated_card", True)
        is_brand_anchor = i == 0 and bool(company_hint)
        scene_start = i * seg_duration

        query = f"{company_hint} logo" if is_brand_anchor else keywords.to_search_query(
            note, company=company_hint, context=topic_context, dramatic=dramatic
        )
        result = media_router.resolve_scene(
            note, query, company_hint, assets_dir, i,
            exclude_kind=last_kind, used_urls=used_urls,
            dramatic=dramatic, is_brand_anchor=is_brand_anchor,
            beat_narration=beat_narration, allow_generated_card=allow_card,
            used_stats=used_stats,
        )
        if result is None and company_hint and not is_brand_anchor:
            # Kural 15 son çare: konuya en azından marka adı üzerinden bağlı bir
            # görsel dene (tamamen kopuk bir görsel yerine).
            result = media_router.resolve_scene(
                f"{company_hint} logo", f"{company_hint} logo", company_hint, assets_dir, i,
                exclude_kind=last_kind, used_urls=used_urls, dramatic=False, is_brand_anchor=True,
            )
        if result is None:
            # Kural 24: hiçbir kaynak (Wikimedia/Wayback/Pexels/marka logosu) uygun
            # bir şey bulamadıysa, alakasız bir stok görselle uğraşmak yerine
            # notun kendi metnini gösteren sade bir kart kullan - düz placeholder
            # renkten de, yanlış bir stok fotoğraftan da her zaman daha iyidir.
            try:
                text_card_path = graphics.render_text_card(note, assets_dir, i, dramatic=dramatic)
                result = {
                    "path": text_card_path, "kind": "photo",
                    "source": "üretilen grafik (metin kartı, son çare)",
                }
            except Exception as e:
                print(f"      metin kartı da üretilemedi ({e}), placeholder kullanılıyor")
                result = {"path": None, "kind": "placeholder", "source": "placeholder (hiçbir şey üretilemedi)"}

        tag = " [MARKA]" if is_brand_anchor else (" [DRAMATİK]" if dramatic else "")
        # Kural 21: her sahne için kaynak + sorgu konsola yazdırılır.
        print(f"  [{i + 1}/{segment_count}]{tag} \"{note[:55]}\"")
        print(f"      sorgu: \"{query}\"  |  kaynak: {result['source']}")

        if "üretilen grafik" in result["source"]:
            whoosh_at.append(scene_start)
        if dramatic and not impact_at:
            impact_at.append(scene_start)

        seg_path = assets_dir / f"seg_{i:02d}.mp4"
        if result["kind"] == "placeholder":
            _build_segment_placeholder(seg_path, seg_duration, i)
        elif result["kind"] == "video":
            _build_segment_from_video(result["path"], seg_path, seg_duration)
            last_kind = "video"
        elif result["kind"] == "logo":
            _build_segment_from_logo(result["path"], seg_path, seg_duration)
            last_kind = "photo"
        else:
            _build_segment_from_photo(result["path"], seg_path, seg_duration)
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
    return visual_track, whoosh_at, impact_at


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

    # Kural 17: hiçbir sahne 3 saniyeden uzun kalmasın - eşit paylaşımda sahne
    # süresi bunu aşıyorsa, her sahneyi aynı notu/sorguyu paylaşan alt-kesimlere böl.
    # Kural 23: bir notun alt-kesimlerinden sadece İLKİ üretilen kart üretebilir -
    # aksi halde AYNI kart art arda birden fazla alt-kesimde yeniden üretilip
    # ekranda olması gerekenden çok daha uzun süre kalmış gibi görünür.
    raw_seg_duration = total_duration / len(scenes)
    if raw_seg_duration > MAX_SCENE_SECONDS:
        sub_count = max(1, ceil(raw_seg_duration / MAX_SCENE_SECONDS))
        scenes = [
            {**scene, "allow_generated_card": sub_index == 0}
            for scene in scenes
            for sub_index in range(sub_count)
        ]
    else:
        scenes = [{**scene, "allow_generated_card": True} for scene in scenes]
    seg_duration = total_duration / len(scenes)

    assets_dir = video_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    visual_track, whoosh_at, impact_at = _build_visual_track(
        scenes, seg_duration, company_hint, topic_context, assets_dir
    )

    timings_path = video_dir / "word_timings.json"
    if timings_path.exists():
        word_timings = json.loads(timings_path.read_text(encoding="utf-8"))
    else:
        word_timings = subtitles.estimate_word_timings(narration, total_duration)

    captions_path = video_dir / "captions.srt"
    captions_path.write_text(subtitles.build_cumulative_srt(word_timings), encoding="utf-8")

    # Kural 18: arka plan müziği + whoosh/impact efektleri (assets/audio/ varsa).
    mixed_audio_path = assets_dir / "mixed_audio.mp3"
    audio_mix.mix(audio_path, total_duration, mixed_audio_path, whoosh_at=whoosh_at, impact_at=impact_at)

    content_path = assets_dir / "content.mp4"
    subtitle_arg = _ffmpeg_filter_path(captions_path)
    encode_args = [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
    ]
    try:
        _run(
            ["ffmpeg", "-y", "-i", str(visual_track), "-i", str(mixed_audio_path)]
            + [
                "-vf",
                f"subtitles='{subtitle_arg}':force_style="
                f"'PlayResX={WIDTH},PlayResY={HEIGHT},"
                "Fontsize=38,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                "BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=140,MarginL=48,MarginR=48'",
            ]
            + encode_args
            + [str(content_path)]
        )
    except VideoBuildError as e:
        print("UYARI: Altyazı gömme başarısız oldu, altyazısız devam ediliyor.")
        print(str(e)[:800])
        _run(
            ["ffmpeg", "-y", "-i", str(visual_track), "-i", str(mixed_audio_path)]
            + encode_args
            + [str(content_path)]
        )

    output_path = video_dir / "video.mp4"
    hook_path = video_dir / "hook.mp4"
    if hook_path.exists():
        # Kural 20: hook.mp4 varsa video ONUNLA (kendi sesiyle) başlar, script'in
        # seslendirmesi ondan sonra devam eder.
        print(f"İnsan çekimi hook bulundu ({hook_path.name}), video onunla başlatılıyor.")
        hook_normalized = assets_dir / "hook_normalized.mp4"
        _build_segment_from_video(
            hook_path, hook_normalized, _probe_duration(hook_path), keep_audio=True
        )
        concat_final = assets_dir / "concat_final.txt"
        concat_final.write_text(
            f"file '{hook_normalized.resolve().as_posix()}'\nfile '{content_path.resolve().as_posix()}'",
            encoding="utf-8",
        )
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_final),
            "-c", "copy",
            str(output_path),
        ])
    else:
        shutil.copy(content_path, output_path)

    if not keep_assets:
        shutil.rmtree(assets_dir, ignore_errors=True)

    return output_path
