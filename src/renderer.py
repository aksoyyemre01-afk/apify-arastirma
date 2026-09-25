"""Bir video klasöründen (script.json + audio.mp3 + word_timings.json) Remotion ile
dikey short videosu üretir. Görsel arama yoktur; tüm görseller remotion/
altındaki bileşenlerle kodla çizilir."""

import json
import os
import shutil
import subprocess
from pathlib import Path

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
    result = subprocess.run(
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


def render(video_dir: Path, part_info: dict | None = None, offline_logos: bool = False) -> Path:
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
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not out.exists():
        raise RenderError(f"Remotion render başarısız:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    normalize_loudness(out)
    return out


# ElevenLabs çıktısı ~-24 LUFS geliyor; YouTube/telefonlar ~-14 LUFS bekler. Normalize
# edilmezse video diğer içeriklere göre ~10 LU kısık (neredeyse sessiz) duyulur.
TARGET_LUFS = -14.0
TARGET_TRUE_PEAK = -1.5
TARGET_LRA = 11.0


def normalize_loudness(video: Path) -> None:
    """Videonun sesini iki geçişli loudnorm ile TARGET_LUFS'a getirir (görüntü kopyalanır)."""
    base = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TRUE_PEAK}:LRA={TARGET_LRA}"
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-map", "0:a", "-af", f"{base}:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        stats = json.loads(probe.stderr[probe.stderr.rindex("{"):probe.stderr.rindex("}") + 1])
    except ValueError:
        raise RenderError(f"loudnorm ölçümü okunamadı:\n{probe.stderr[-1500:]}")
    # Sessiz ses (ör. dry-run) -inf ölçülür; yükseltilecek bir şey yok, olduğu gibi bırakılır.
    try:
        measured = float(stats["input_i"])
    except (KeyError, ValueError):
        measured = float("-inf")
    if not measured > -70:
        print(f"      Ses: {stats.get('input_i')} LUFS (sessiz), normalizasyon atlandı")
        return
    second = (
        f"{base}:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}:linear=true"
    )
    tmp = video.with_name(video.stem + ".norm.mp4")
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-map", "0:v", "-map", "0:a", "-c:v", "copy",
         "-af", f"{second},aresample=48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RenderError(f"ses normalizasyonu başarısız:\n{result.stderr[-1500:]}")
    tmp.replace(video)
    print(f"      Ses: {float(stats['input_i']):.1f} LUFS -> {TARGET_LUFS:.0f} LUFS")


def extract_frames(video: Path, dest_dir: Path, every_seconds: float = 2.0) -> list[Path]:
    """Kalite kontrolü için her `every_seconds` saniyede bir kare çıkarır."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{every_seconds}",
         str(dest_dir / "kare_%02d.png")],
        check=True,
    )
    return sorted(dest_dir.glob("kare_*.png"))
