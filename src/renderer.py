"""Bir video klasöründen (script.json + audio.mp3 + word_timings.json) Remotion ile
dikey short videosu üretir. Görsel arama yoktur; tüm görseller remotion/
altındaki bileşenlerle kodla çizilir."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import proc
from . import brand_config, scene_planner, subtitles

ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = ROOT / "remotion"


class RenderError(RuntimeError):
    pass


def _find_node() -> str:
    node = shutil.which("node")
    if node:
        return node
    # winget kullanıcı kurulumu PATH'i ancak yeni oturumlarda günceller.
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for cand in sorted(base.glob("OpenJS.NodeJS*/node-*/node.exe"), reverse=True):
        return str(cand)
    raise RenderError("Node.js bulunamadı. Kurulum: winget install OpenJS.NodeJS.LTS")


def probe_duration(path: Path) -> float:
    result = proc.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RenderError(f"ffprobe süresini okuyamadı: {path}\n{result.stderr}")
    return float(result.stdout.strip())


def _load_timings(video_dir: Path, narration: str, duration: float) -> list[dict]:
    path = video_dir / "word_timings.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    print("      UYARI: word_timings.json yok; kelime zamanlamaları tahmin ediliyor.")
    return subtitles.estimate_word_timings(narration, duration)


def render(video_dir: Path, part_info: dict | None = None, offline_logos: bool = False, mutate=None) -> Path:
    video_dir = Path(video_dir)
    script = json.loads((video_dir / "script.json").read_text(encoding="utf-8"))
    audio = video_dir / "audio.mp3"
    if not audio.exists():
        raise RenderError(f"{audio} bulunamadı")
    if not (REMOTION_DIR / "node_modules").exists():
        raise RenderError("remotion/node_modules yok. Önce: cd remotion && npm install")

    duration = probe_duration(audio)
    narration = script.get("narration_full") or " ".join(s["narration"] for s in script.get("scenes", []))
    timings = _load_timings(video_dir, narration, duration)
    part_info = part_info or script.get("series_part")

    cfg = brand_config.load()
    props, files = scene_planner.build_props(script, timings, audio, duration, cfg, part_info, offline_logos)
    if mutate:
        # Yalnızca test amaçlı: planlanmış sahnelere kasıtlı müdahale (Eleştirmen kalibrasyonu).
        mutate(props, files)

    work = video_dir / "assets"
    public_dir = work / "public"
    scene_planner.write_public_dir(files, public_dir)
    props_path = work / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    (video_dir / "captions.srt").write_text(subtitles.build_cumulative_srt(timings), encoding="utf-8")

    out = video_dir / "video.mp4"
    cli = REMOTION_DIR / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    cmd = [
        _find_node(), str(cli), "render", "src/index.ts", "Short", str(out.resolve()),
        f"--props={props_path.resolve()}",
        f"--public-dir={public_dir.resolve()}",
        "--log=warn",
    ]
    print(f"      Remotion render başlıyor ({props['durationInFrames']} kare)...")
    result = proc.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not out.exists():
        raise RenderError(f"Remotion render başarısız:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    add_music(out, audio, cfg.get("audio", {}), timings)
    normalize_loudness(out)
    return out


def _remotion(composition: str, out: Path, props_path: Path, public_dir: Path, still: bool = False) -> None:
    cli = REMOTION_DIR / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    cmd = [_find_node(), str(cli), "still" if still else "render", "src/index.ts", composition, str(out.resolve()),
           f"--props={props_path.resolve()}", f"--public-dir={public_dir.resolve()}", "--log=warn"]
    if still:
        cmd.append("--frame=30")  # giriş animasyonları bitmiş kare
    result = proc.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not out.exists():
        raise RenderError(f"Remotion {composition} başarısız:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")


def render_long(video_dir: Path, props: dict, files: dict[str, Path], audio: Path, timings: list[dict]) -> Path:
    """Uzun video (1920x1080, 'Long' kompozisyonu): render + müzik (8 dB kelime zamanlı) + -14 LUFS."""
    work = video_dir / "assets"
    public_dir = work / "public"
    scene_planner.write_public_dir(files, public_dir)
    props_path = work / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    (video_dir / "captions.srt").write_text(subtitles.build_cumulative_srt(timings), encoding="utf-8")
    out = video_dir / "video.mp4"
    print(f"      Remotion (Long) render başlıyor ({props['durationInFrames']} kare)...")
    _remotion("Long", out, props_path, public_dir)
    add_music(out, audio, brand_config.load().get("audio", {}), timings)
    normalize_loudness(out)
    return out


def render_thumbnail(video_dir: Path, props: dict, files: dict[str, Path]) -> Path:
    """1280x720 küçük resim (tek kare, 'Thumbnail' kompozisyonu)."""
    work = video_dir / "assets"
    public_dir = work / "thumb_public"
    scene_planner.write_public_dir(files, public_dir)
    props_path = work / "thumbnail.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    out = video_dir / "thumbnail.png"
    _remotion("Thumbnail", out, props_path, public_dir, still=True)
    return out


# ---------------------------------------------------------------------------- müzik
# Kural 8: müzik seslendirmeyi asla bastırmaz, ama konuşma sırasında da duyulur. İki katman:
# 1) Taban seviye: müziğin videoda KULLANILAN bölümü ölçülür ve seslendirmenin
#    `music_below_voice_db` (15) altına oturtulur (parçanın tamamını ölçmek, girişi sessiz
#    parçalarda ~1 dB sapıyordu).
# 2) Konuşma anlarında sabit `music_duck_db` (8) ek kısma: aralıklar kelime zamanlarından
#    (0,35 sn'den kısa boşluklar birleşir), 80 ms iniş / 350 ms çıkış rampası. Kompresörlü
#    ducking konuşma yüksekliğine göre ~24 dB kısıyor ve müziği konuşma altında duyulmaz
#    yapıyordu. Duraklamalarda ve outro'da müzik taban seviyeye döner; sonda
#    `music_fade_out_sec` (2,5) sn'de söner.
MUSIC_FILE = ROOT / "assets" / "audio" / "music.mp3"
DUCK_ATTACK, DUCK_RELEASE, DUCK_MERGE_GAP = 0.08, 0.35, 0.35


def speech_spans(timings: list[dict]) -> list[list[float]]:
    spans: list[list[float]] = []
    for w in timings:
        if spans and w["start"] - spans[-1][1] < DUCK_MERGE_GAP:
            spans[-1][1] = max(spans[-1][1], w["end"])
        else:
            spans.append([w["start"], w["end"]])
    return spans


def music_duck_filter(gain_db: float, duration: float, spans: list[list[float]], duck_db: float,
                      fade_out: float, mix: str, music: str, out: str, music_only: str | None = None) -> str:
    """ffmpeg filter_complex parçası: `music`e taban kazanç + fade + konuşma aralıklarında sabit
    `duck_db` kısma uygulayıp `mix` (seslendirme + efekt) ile karıştırır, sonucu `out`a yazar.
    music_only verilirse kısılmış müzik ayrıca o etikete de çıkar (ölçüm için)."""
    env = "0"
    for a, b in spans:
        env = (f"max({env},clip((t-{a - DUCK_ATTACK:.3f})/{DUCK_ATTACK},0,1)"
               f"*clip(({b + DUCK_RELEASE:.3f}-t)/{DUCK_RELEASE},0,1))")
    g = 10 ** (-duck_db / 20)
    tail = f"asplit=2[m1][{music_only}]" if music_only else "anull[m1]"
    return (
        f"[{music}]aresample=48000,aformat=channel_layouts=stereo,volume={gain_db:.2f}dB,"
        f"afade=t=in:d=0.4,afade=t=out:st={max(duration - fade_out, 0):.3f}:d={fade_out},"
        f"atrim=0:{duration:.3f},asetnsamples=n=256,volume='1-{1 - g:.5f}*{env}':eval=frame,{tail};"
        f"[{mix}]aresample=48000,aformat=channel_layouts=stereo[dry];"
        f"[dry][m1]amix=inputs=2:normalize=0:duration=first[{out}]"
    )


def add_music(video: Path, narration: Path, audio_cfg: dict, timings: list[dict]) -> None:
    if not MUSIC_FILE.exists():
        return
    below = float(audio_cfg.get("music_below_voice_db", 15))
    duck_db = float(audio_cfg.get("music_duck_db", 8))
    fade_out = float(audio_cfg.get("music_fade_out_sec", 2.5))
    duration = probe_duration(video)
    segment = video.with_name("music_segment.wav")
    proc.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(MUSIC_FILE), "-t", f"{duration:.3f}",
              "-c:a", "pcm_s16le", str(segment)], check=True)
    voice_lufs, music_lufs = scene_planner.measure_lufs(narration), scene_planner.measure_lufs(segment)
    segment.unlink(missing_ok=True)
    if voice_lufs is None or music_lufs is None:
        print("      UYARI: müzik/ses yüksekliği ölçülemedi; müzik eklenmedi.")
        return
    gain_db = min((voice_lufs - below) - music_lufs, 0.0)
    # Ara dosya: görüntü kopyalanır, ses kayıpsız (PCM) kalır; tek AAC kodlaması normalize_loudness'ta.
    tmp = video.with_name(video.stem + ".music.mov")
    fc = music_duck_filter(gain_db, duration, speech_spans(timings), duck_db, fade_out, "0:a", "1:a", "aout")
    result = proc.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(MUSIC_FILE),
         "-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "pcm_s16le",
         "-t", f"{duration:.3f}", str(tmp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RenderError(f"müzik eklenemedi:\n{result.stderr[-1500:]}")
    tmp.replace(video)  # içerik MOV/PCM; normalize_loudness standart MP4'e yeniden yazar
    print(f"      Müzik: {music_lufs:.1f} LUFS (kullanılan bölüm), ses {voice_lufs:.1f} LUFS -> taban {gain_db:+.1f} dB "
          f"(sesin {below:g} dB altı), konuşmada ek -{duck_db:g} dB, sonda {fade_out:g} sn sönme")


# ElevenLabs çıktısı ~-24 LUFS geliyor; YouTube/telefonlar ~-14 LUFS bekler. Normalize
# edilmezse video diğer içeriklere göre ~10 LU kısık (neredeyse sessiz) duyulur.
TARGET_LUFS = -14.0
TARGET_TRUE_PEAK = -1.5
TARGET_LRA = 11.0


# Her oynatıcıda (Windows Filmler ve TV, QuickTime, tarayıcılar, telefonlar, sosyal medya
# yükleyicileri) açılan standart teslim biçimi. Remotion JPEG kareleri tam aralıklı
# `yuvj420p` (pc range, BT.470BG) üretiyor; bazı oynatıcı/donanım kod çözücüler bunu açmıyor
# ya da renkleri yanlış gösteriyor. Bu yüzden görüntü her zaman sınırlı aralıklı BT.709
# yuv420p'ye yeniden kodlanır.
VIDEO_ENCODE_ARGS = [
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-profile:v", "high", "-level:v", "4.0", "-pix_fmt", "yuv420p",
    "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
    # Renk etiketleri bitstream'e de yazılır (ffmpeg bayrakları tek başına "unknown" bırakıyordu).
    "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off",
    "-tag:v", "avc1",
]
# Kaynak kareler tam aralıklı BT.601 (470bg) geliyor; renk kaymasın diye aralık ve matris
# zscale ile dönüştürülür. (swscale `scale` bu parametreleri yok sayıp görüntüyü ~2/255
# koyulaştırıyordu; zscale parlaklığı koruyor - ölçüm: ortalama 51,5 -> 51,1, PSNR 41,6 dB.)
_ZSCALE_FILTER = "zscale=rangein=full:range=limited:matrixin=470bg:matrix=709,format=yuv420p"
_SCALE_FILTER = "scale=in_range=full:out_range=limited:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p"
AUDIO_ENCODE_ARGS = ["-c:a", "aac", "-profile:a", "aac_low", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def _video_filter() -> str:
    """zscale (libzimg) varsa onu, yoksa swscale'i kullanır."""
    filters = proc.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return _ZSCALE_FILTER if " zscale " in filters else _SCALE_FILTER


def _loudnorm_filter(video: Path) -> str | None:
    """İki geçişli loudnorm'un ikinci geçiş filtresi; ses sessizse (ör. dry-run) None."""
    base = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TRUE_PEAK}:LRA={TARGET_LRA}"
    probe = proc.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-map", "0:a", "-af", f"{base}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        stats = json.loads(probe.stderr[probe.stderr.rindex("{"):probe.stderr.rindex("}") + 1])
        measured = float(stats["input_i"])
    except (ValueError, KeyError):
        measured = float("-inf")
    if not measured > -70:
        print("      Ses: sessiz, normalizasyon atlandı")
        return None
    print(f"      Ses: {measured:.1f} LUFS -> {TARGET_LUFS:.0f} LUFS")
    return (
        f"{base}:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}:linear=true"
    )


def normalize_loudness(video: Path) -> None:
    """Son teslim adımı (her render'da): sesi -14 LUFS'a normalize eder ve dosyayı standart,
    her oynatıcıda açılan biçime yeniden kodlar - H.264 High@4.0 yuv420p (BT.709, sınırlı
    aralık) + AAC-LC 48 kHz stereo + faststart (moov dosya başında)."""
    loudnorm = _loudnorm_filter(video)
    # Doğrusal loudnorm tepe sınırlamaz; true peak'i TARGET_TRUE_PEAK altında tutmak için 4x
    # örneklemede hafif bir sınırlayıcı (-2 dB) - ses yüksekliğini değiştirmez.
    limiter = "aresample=192000,alimiter=limit=0.7943:level=false:attack=1:release=50,"
    audio_filter = f"{loudnorm + ',' + limiter if loudnorm else ''}aresample=48000,aformat=channel_layouts=stereo"
    tmp = video.with_name(video.stem + ".final.mp4")
    result = proc.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-map", "0:v:0", "-map", "0:a:0",
         "-vf", _video_filter(), *VIDEO_ENCODE_ARGS,
         "-af", audio_filter, *AUDIO_ENCODE_ARGS,
         "-movflags", "+faststart", str(tmp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RenderError(f"son kodlama başarısız:\n{result.stderr[-1500:]}")
    tmp.replace(video)
    print("      Kodlama: H.264 High@4.0 yuv420p BT.709 + AAC-LC 48 kHz stereo + faststart")


def extract_audio(video: Path, dest: Path) -> Path:
    """Videonun ses kanalını ayrıca dinlemek için MP3 olarak çıkarır (48 kHz stereo, 192 kb/s)."""
    proc.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-map", "0:a:0",
         "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(dest)],
        check=True,
    )
    return dest


def extract_frames(video: Path, dest_dir: Path, every_seconds: float = 2.0) -> list[Path]:
    """Kalite kontrolü için her `every_seconds` saniyede bir kare çıkarır."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    proc.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{every_seconds}",
         str(dest_dir / "kare_%02d.png")],
        check=True,
    )
    return sorted(dest_dir.glob("kare_*.png"))
