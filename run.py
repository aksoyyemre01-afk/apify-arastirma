"""Business Stories otomasyonu - ana çalıştırma script'i.

Kullanım:
    python run.py --mode weekly              # 3 short + 1 uzun video üretir (gerçek API çağrılarıyla)
    python run.py --mode shorts               # sadece short'lar
    python run.py --mode long                 # sadece uzun video
    python run.py --mode weekly --dry-run      # API çağrısı yapmadan, sahte içerikle boru hattını test eder
    python run.py --mode weekly --skip-tts     # senaryoları üretir ama ElevenLabs ile seslendirme yapmaz
"""

import argparse
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import research, state  # noqa: E402
from src.schemas import LongChapter, LongScript, ShortScript  # noqa: E402
from src.utils import slugify  # noqa: E402

OUTPUT_DIR = Path("output")


def _dry_run_short(topic: dict) -> ShortScript:
    return ShortScript(
        title=f"[DRY RUN] {topic['title']}",
        hook="[DRY RUN] Bu bir örnek açılış cümlesidir.",
        narration=f"[DRY RUN] {topic['title']} hakkında örnek bir seslendirme metni. Gerçek çalıştırmada bu metin Gemini tarafından üretilecek.",
        visual_notes=["[DRY RUN] örnek sahne notu 1", "[DRY RUN] örnek sahne notu 2"],
        cta="[DRY RUN] Takip etmeyi unutma!",
        hashtags=["#dryrun", "#test"],
    )


def _dry_run_long(topic: dict) -> LongScript:
    return LongScript(
        title=f"[DRY RUN] {topic['title']}",
        hook="[DRY RUN] Uzun video için örnek açılış.",
        chapters=[
            LongChapter(heading="Giriş", narration="[DRY RUN] örnek giriş metni."),
            LongChapter(heading="Kritik Hata", narration="[DRY RUN] örnek gelişme metni."),
            LongChapter(heading="Dersler", narration="[DRY RUN] örnek kapanış ve ders metni."),
        ],
        cta="[DRY RUN] Abone olmayı unutma!",
        hashtags=["#dryrun", "#test"],
    )


def _write_short(topic: dict, script: ShortScript, out_dir: Path, do_tts: bool) -> Path:
    video_dir = out_dir / f"short-{slugify(script.title)}"
    video_dir.mkdir(parents=True, exist_ok=True)

    md_lines = [
        f"# {script.title}",
        "",
        f"**Kaynak konu:** {topic['title']} ({topic.get('source', '')})",
        "",
        f"**Hook:** {script.hook}",
        "",
        "## Seslendirme Metni",
        "",
        script.narration,
        "",
        "## Görsel Notlar",
        "",
        *[f"- {v}" for v in script.visual_notes],
        "",
        f"**CTA:** {script.cta}",
        "",
        f"**Hashtags:** {' '.join(script.hashtags)}",
        "",
    ]
    (video_dir / "script.md").write_text("\n".join(md_lines), encoding="utf-8")
    (video_dir / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")

    if do_tts:
        from src import tts

        tts.synthesize(script.narration, str(video_dir / "audio.mp3"))

    return video_dir


def _write_long(topic: dict, script: LongScript, out_dir: Path, do_tts: bool) -> Path:
    video_dir = out_dir / f"long-{slugify(script.title)}"
    video_dir.mkdir(parents=True, exist_ok=True)

    md_lines = [
        f"# {script.title}",
        "",
        f"**Kaynak konu:** {topic['title']} ({topic.get('source', '')})",
        "",
        f"**Hook:** {script.hook}",
        "",
    ]
    for chapter in script.chapters:
        md_lines += [f"## {chapter.heading}", "", chapter.narration, ""]
    md_lines += [
        f"**CTA:** {script.cta}",
        "",
        f"**Hashtags:** {' '.join(script.hashtags)}",
        "",
    ]
    (video_dir / "script.md").write_text("\n".join(md_lines), encoding="utf-8")
    (video_dir / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")

    if do_tts:
        from src import tts

        tts.synthesize(script.full_narration, str(video_dir / "audio.mp3"))

    return video_dir


def run(mode: str, shorts_count: int, long_count: int, do_tts: bool, dry_run: bool) -> None:
    used = state.get_used_ids()

    needed = 0
    if mode in ("shorts", "weekly"):
        needed += shorts_count
    if mode in ("long", "weekly"):
        needed += long_count

    topics = research.get_topics(needed, used)
    if len(topics) < needed:
        print(f"UYARI: {needed} konu istendi ama sadece {len(topics)} tane bulunabildi.")

    out_dir = OUTPUT_DIR / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    idx = 0
    results = []

    if mode in ("shorts", "weekly"):
        for _ in range(min(shorts_count, max(0, len(topics) - idx))):
            topic = topics[idx]
            idx += 1
            if dry_run:
                script = _dry_run_short(topic)
            else:
                from src import script_writer

                script = script_writer.write_short_script(topic)
            path = _write_short(topic, script, out_dir, do_tts and not dry_run)
            if not dry_run:
                state.mark_used(topic["id"], "short")
            results.append(str(path))

    if mode in ("long", "weekly"):
        for _ in range(min(long_count, max(0, len(topics) - idx))):
            topic = topics[idx]
            idx += 1
            if dry_run:
                script = _dry_run_long(topic)
            else:
                from src import script_writer

                script = script_writer.write_long_script(topic)
            path = _write_long(topic, script, out_dir, do_tts and not dry_run)
            if not dry_run:
                state.mark_used(topic["id"], "long")
            results.append(str(path))

    if not dry_run:
        state.save()

    print(f"\nÜretildi: {len(results)} içerik -> {out_dir}")
    for r in results:
        print(" -", r)
    if dry_run:
        print("\n(dry-run modunda: gerçek API çağrısı yapılmadı, state güncellenmedi)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Business Stories içerik otomasyonu")
    parser.add_argument("--mode", choices=["shorts", "long", "weekly"], default="weekly")
    parser.add_argument(
        "--shorts-count", type=int, default=int(os.environ.get("SHORTS_PER_WEEK", 3))
    )
    parser.add_argument(
        "--long-count", type=int, default=int(os.environ.get("LONG_PER_WEEK", 1))
    )
    parser.add_argument("--skip-tts", action="store_true", help="ElevenLabs çağrısını atla")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hiçbir API çağrısı yapmadan boru hattını sahte veriyle test et",
    )
    args = parser.parse_args()

    run(
        mode=args.mode,
        shorts_count=args.shorts_count,
        long_count=args.long_count,
        do_tts=not args.skip_tts,
        dry_run=args.dry_run,
    )
