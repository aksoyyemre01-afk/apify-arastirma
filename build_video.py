"""Bir video klasöründeki script.json + audio.mp3'ten dikey (.mp4) video üretir.

Kullanım:
    python build_video.py --dir output/2026-09-16/airbaltic-iflasi
    python build_video.py --dir output/2026-09-16/airbaltic-iflasi --keep-assets

Gereksinimler:
    - ffmpeg ve ffprobe PATH'te olmalı
    - .env içinde PEXELS_API_KEY ve/veya PIXABAY_API_KEY tanımlı olmalı
      (hiçbiri yoksa görsel yerine düz renkli placeholder sahneler kullanılır)
    - klasörde script.json (visual_notes içermeli) ve audio.mp3 bulunmalı
"""

import argparse
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.video_builder import VideoBuildError, build_video  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="script.json + audio.mp3'ten dikey video (.mp4) üretir")
    parser.add_argument("--dir", required=True, help="Video klasörü (script.json ve audio.mp3 içermeli)")
    parser.add_argument(
        "--keep-assets", action="store_true", help="Ara dosyaları (assets/ klasörü) silme, debug için sakla"
    )
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("HATA: ffmpeg/ffprobe PATH'te bulunamadı. Önce ffmpeg kurmalısın.")
        raise SystemExit(1)

    try:
        output = build_video(Path(args.dir), keep_assets=args.keep_assets)
    except VideoBuildError as e:
        print(f"HATA: {e}")
        raise SystemExit(1)

    print(f"\nVideo üretildi: {output}")
