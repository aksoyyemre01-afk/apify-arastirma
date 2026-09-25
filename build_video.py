"""Bir video klasöründeki script.json + audio.mp3 (+ word_timings.json) dosyalarından
Remotion ile dikey short videosu (video.mp4) üretir.

Kullanım:
    python build_video.py --dir output/2026-09-24/short-...
    python build_video.py --dir ... --migrate      # eski formatlı (hook/setup/twist) script'i
                                                  # sahneli formata çevirir (1 Gemini isteği)
    python build_video.py --dir ... --frames 2    # kalite kontrolü: 2 sn'de bir kare -> kareler/

Gereksinimler: ffmpeg/ffprobe PATH'te, Node.js kurulu, remotion/ içinde `npm install` yapılmış.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import renderer  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def migrate(video_dir: Path) -> None:
    """Eski formatlı script.json'ı, metni ve sesi değiştirmeden sahneli formata çevirir."""
    from src import scene_planner, script_writer

    path = video_dir / "script.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("scenes"):
        print("script.json zaten sahneli formatta, migrate atlandı.")
        return
    narration = data.get("narration_full") or " ".join(
        data[k]["narration"] for k in ("hook", "setup", "twist") if k in data
    )
    print("Gemini: mevcut metin sahnelere bölünüyor (1 istek)...")
    layout = script_writer.structure_existing_narration(narration, data.get("company", ""), data.get("cta", ""))

    joined = " ".join(s.narration for s in layout.scenes)
    a, b = scene_planner._tokens(narration), scene_planner._tokens(joined)
    import difflib

    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    print(f"Sahne metni / orijinal metin eşleşmesi: %{ratio * 100:.0f}")

    backup = video_dir / "script.legacy.json"
    if not backup.exists():
        shutil.copy(path, backup)
    new = {
        "title": data.get("title", ""),
        **layout.model_dump(),
        "hashtags": data.get("hashtags", []),
        "narration_full": narration,
        "company": data.get("company", ""),
        "topic_context": data.get("topic_context", ""),
    }
    path.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"script.json sahneli formata çevrildi (eski hali: {backup.name}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="script.json + audio.mp3'ten dikey video (.mp4) üretir")
    parser.add_argument("--dir", required=True, help="Video klasörü")
    parser.add_argument("--migrate", action="store_true", help="Eski formatlı script'i sahneli formata çevir")
    parser.add_argument("--frames", type=float, default=0, help="Her N saniyede bir kare çıkar (kareler/)")
    parser.add_argument("--offline-logos", action="store_true", help="Logo için ağa çıkma, sadece assets/logos")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("HATA: ffmpeg/ffprobe PATH'te bulunamadı.")
        raise SystemExit(1)

    video_dir = Path(args.dir)
    if args.migrate:
        try:
            migrate(video_dir)
        except Exception as e:  # noqa: BLE001 - Gemini hatası (kota/503) kısa mesajla bildirilir
            print(f"HATA (migrate, Gemini): {str(e)[:400]}")
            raise SystemExit(1)

    try:
        output = renderer.render(video_dir, offline_logos=args.offline_logos)
    except (renderer.RenderError, Exception) as e:  # noqa: BLE001
        print(f"HATA: {e}")
        raise SystemExit(1)
    print(f"\nVideo üretildi: {output}")

    if args.frames:
        frames = renderer.extract_frames(output, video_dir / "kareler", args.frames)
        print(f"{len(frames)} kare çıkarıldı -> {video_dir / 'kareler'}")
