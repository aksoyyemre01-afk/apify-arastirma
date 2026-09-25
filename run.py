"""Short video otomasyonu - ana çalıştırma script'i.

Akış: konu araştırma -> Gemini (script + her cümlenin sahne yapısı, TEK istek)
-> ElevenLabs (audio.mp3 + word_timings.json) -> Remotion (video.mp4).

RULES.md kural 9: --mode weekly TEK bir konuyu 3 short'a böler (Pazartesi /
Çarşamba / Cuma) ve hafta sonu için 1 uzun video script'i üretir (uzun videonun
render'ı ikinci aşamada).

Kullanım:
    python run.py --mode weekly                 # haftalık 3 short + 1 uzun script (gerçek API)
    python run.py --mode weekly --dry-run       # API çağrısı yok, sahte içerikle boru hattı + render testi
    python run.py --mode shorts --shorts-count 1
    python run.py --mode shorts --dry-run --topic kodak   # belirli bir konuyla dry-run render
    python run.py --mode long
    --skip-tts : seslendirme yapma   --no-video : video render etme
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import research, state  # noqa: E402
from src.schemas import LongChapter, LongScript, Scene, ShortScript  # noqa: E402
from src.utils import slugify  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = Path("output")


# --------------------------------------------------------------------------- dry-run içerikleri
# Konudan bağımsız şablon: şirket adı topic'ten gelir; tüm sahne tiplerini,
# gizemli hook + reveal'ı, logosu bulunamayan bir tarafı (yazı logosu) ve 3 sn'den
# uzun bir sahnenin bölünmesini test eder. Ekrana çıkan metinlerde "[DRY RUN]" yoktur
# (kural 10); sahte olduğu başlıkta ve klasör adında belirtilir.
def _dry_run_short(topic: dict, suffix: str = "") -> ShortScript:
    c = topic.get("company") or "Şirket"
    scenes = [
        Scene(narration="Tek bir kararla milyarlarca dolar kaybeden şirketi biliyor musunuz?",
              scene_type="big_number", value="10", unit="MİLYAR $", label="Tek kararın bedeli"),
        Scene(narration=f"Cevap: {c}.", scene_type="logo_intro", brand=c, reveal=True),
        Scene(narration=f"{c}, 1998 yılında pazarın açık ara lideriydi.",
              scene_type="timeline", year="1998", text="Pazarın açık ara lideri", brand=c),
        Scene(narration="Şirketin değeri 250 milyar dolara ulaştı.",
              scene_type="big_number", value="250", unit="MİLYAR $", label="Piyasa değeri", brand=c),
        Scene(narration="Sonra yepyeni bir rakip sahneye çıktı.",
              scene_type="comparison", left_brand=c, right_brand="Yeni rakip",
              left_value="LİDER", right_value="YENİ", highlight_side="right"),
        Scene(narration="Satışlar sadece birkaç yıl içinde çakıldı.",
              scene_type="chart", direction="down", points=[100, 92, 60, 31, 12],
              point_labels=["2007", "2008", "2009", "2010", "2011"], end_value="-%88", brand=c),
        Scene(narration="Yönetim değişime bir türlü ayak uyduramadı.",
              scene_type="quote", text="Değişime ayak uyduramadı", highlight=["Değişime"]),
        Scene(narration="Sonunda şirket, zirvedeki değerinin çok küçük bir kısmına, yalnızca 7 milyar dolara satıldı.",
              scene_type="big_number", value="7", unit="MİLYAR $", label="Satış fiyatı", brand=c),
        Scene(narration="Asıl ders ise hâlâ çoğu şirketin gözünden kaçıyor.",
              scene_type="quote", text="Asıl ders hâlâ gözden kaçıyor", highlight=["ders"]),
    ]
    return ShortScript(
        title=f"[DRY RUN] {topic['title']}{suffix}",
        main_brand=c,
        hook_type="mystery",
        mystery_brand=c,
        reveal_by_seconds=5,
        scenes=scenes,
        cta="Asıl hatayı bir sonraki bölümde anlatıyoruz",
        hashtags=["#dryrun", "#test"],
    )


def _dry_run_long(topic: dict) -> LongScript:
    return LongScript(
        title=f"[DRY RUN] {topic['title']}",
        main_brand=topic.get("company", ""),
        hook="Uzun video için örnek açılış.",
        chapters=[
            LongChapter(heading="Giriş", narration="Örnek giriş metni."),
            LongChapter(heading="Kritik Hata", narration="Örnek gelişme metni."),
            LongChapter(heading="Dersler", narration="Örnek kapanış ve ders metni."),
        ],
        cta="Abone olmayı unutma!",
        hashtags=["#dryrun", "#test"],
    )


def _silent_audio_with_timings(text: str, video_dir: Path) -> None:
    """dry-run: ses yerine tahmini süreli sessiz bir mp3 ve tahmini kelime zamanlamaları."""
    from src import subtitles

    duration = max(len(text.split()) * 0.42, 3.0)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{duration:.2f}", "-q:a", "9", str(video_dir / "audio.mp3")],
        check=True,
    )
    timings = subtitles.estimate_word_timings(text, duration)
    (video_dir / "word_timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- yazma / render

def _script_md(topic: dict, script: ShortScript) -> str:
    lines = [
        f"# {script.title}",
        "",
        f"**Kaynak konu:** {topic['title']} ({topic.get('source', '')})",
        f"**Ana marka:** {script.main_brand} · **Hook:** {script.hook_type}"
        + (f" (gizli marka: {script.mystery_brand}, reveal ≤ {script.reveal_by_seconds:g} sn)" if script.hook_type == "mystery" else ""),
        "",
        "| # | Cümle | Sahne | İçerik |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(script.scenes, 1):
        fields = {k: v for k, v in s.model_dump().items() if k not in ("narration", "scene_type") and v not in ("", [], False)}
        content = ", ".join(f"{k}={v}" for k, v in fields.items())
        lines.append(f"| {i} | {s.narration} | {s.scene_type} | {content} |")
    lines += ["", f"**Kapanış metni (ekranda):** {script.cta}", "", f"**Hashtags:** {' '.join(script.hashtags)}", ""]
    return "\n".join(lines)


def _write_short(
    topic: dict,
    script: ShortScript,
    out_dir: Path,
    do_tts: bool,
    do_video: bool,
    dry_run: bool,
    prefix: str = "",
    part_info: dict | None = None,
) -> Path:
    from src.script_writer import dump_script

    video_dir = out_dir / f"short-{prefix}{slugify(script.title)}"
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "script.md").write_text(_script_md(topic, script), encoding="utf-8")
    extra = {"company": topic.get("company", ""), "topic_context": topic.get("angle", "")}
    if part_info:
        extra["series_part"] = part_info
    (video_dir / "script.json").write_text(dump_script(script, extra), encoding="utf-8")

    narration = script.narration_full
    if do_tts:
        from src import tts

        timings = tts.synthesize_with_timestamps(narration, str(video_dir / "audio.mp3"))
        if timings:
            (video_dir / "word_timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")
    elif dry_run and do_video:
        _silent_audio_with_timings(narration, video_dir)

    if do_video and (video_dir / "audio.mp3").exists():
        from src import renderer

        try:
            out = renderer.render(video_dir, part_info=part_info)
            print(f"   Video: {out}")
        except renderer.RenderError as e:
            print(f"   HATA (video üretilemedi, script/ses hazır): {e}")
    return video_dir


def _write_long(topic: dict, script: LongScript, out_dir: Path, do_tts: bool, prefix: str = "") -> Path:
    video_dir = out_dir / f"long-{prefix}{slugify(script.title)}"
    video_dir.mkdir(parents=True, exist_ok=True)

    md_lines = [f"# {script.title}", "", f"**Kaynak konu:** {topic['title']} ({topic.get('source', '')})", "",
                f"**Hook:** {script.hook}", ""]
    for chapter in script.chapters:
        md_lines += [f"## {chapter.heading}", "", chapter.narration, ""]
        if chapter.scenes:
            md_lines += [f"- *{s.scene_type}*: {s.narration}" for s in chapter.scenes] + [""]
    md_lines += [f"**CTA:** {script.cta}", "", f"**Hashtags:** {' '.join(script.hashtags)}", ""]
    (video_dir / "script.md").write_text("\n".join(md_lines), encoding="utf-8")
    (video_dir / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")

    if do_tts:
        from src import tts

        tts.synthesize(script.full_narration, str(video_dir / "audio.mp3"))
    return video_dir


def _pick_topics(n: int, topic_id: str | None) -> list[dict]:
    if topic_id:
        bank = {t["id"]: t for t in research.load_bank()}
        if topic_id not in bank:
            raise SystemExit(f"Konu bankasında '{topic_id}' yok. Seçenekler: {', '.join(bank)}")
        return [{**bank[topic_id], "reference": "", "source": "evergreen"}] * n
    return research.get_topics(n, state.get_used_ids())


# --------------------------------------------------------------------------- akışlar

def run_weekly_arc(do_tts: bool, do_video: bool, dry_run: bool, topic_id: str | None) -> None:
    topics = _pick_topics(1, topic_id)
    if not topics:
        print("UYARI: haftalık seri için konu bulunamadı.")
        return
    topic = topics[0]
    out_dir = OUTPUT_DIR / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    from src.script_writer import WEEKLY_PARTS

    print(f"Haftalık seri konusu: {topic['title']} ({topic.get('company', '')})")
    results = []
    part_narrations: list[str] = []
    for part_index in (1, 2, 3):
        part = WEEKLY_PARTS[part_index]
        if dry_run:
            script = _dry_run_short(topic, suffix=f" - {part['focus_title']}")
        else:
            from src import script_writer

            script = script_writer.write_weekly_part_script(topic, part_index, part_narrations)
        part_narrations.append(script.narration_full)
        part_info = {
            "index": part_index,
            "total": 3,
            "day": part["day_label"],
            "next_day": WEEKLY_PARTS[part_index + 1]["day_label"] if part_index < 3 else "",
        }
        path = _write_short(
            topic, script, out_dir, do_tts and not dry_run, do_video, dry_run,
            prefix=f"{part_index}-{slugify(part['day_label'])}-", part_info=part_info,
        )
        results.append(str(path))

    if dry_run:
        long_script = _dry_run_long(topic)
    else:
        from src import script_writer

        long_script = script_writer.write_weekly_recap_script(topic, part_narrations)
    results.append(str(_write_long(topic, long_script, out_dir, do_tts and not dry_run, prefix="hafta-sonu-ozet-")))

    if not dry_run:
        state.mark_used(topic["id"], "weekly-arc")
        state.save()

    print(f"\nÜretildi: {len(results)} içerik (3 short + 1 uzun video script'i) -> {out_dir}")
    for r in results:
        print(" -", r)
    if dry_run:
        print("\n(dry-run: gerçek API çağrısı yapılmadı, state güncellenmedi)")


def run_adhoc(mode: str, count: int, do_tts: bool, do_video: bool, dry_run: bool, topic_id: str | None) -> None:
    topics = _pick_topics(count, topic_id)
    if len(topics) < count:
        print(f"UYARI: {count} konu istendi ama sadece {len(topics)} tane bulunabildi.")
    out_dir = OUTPUT_DIR / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for topic in topics:
        if mode == "shorts":
            if dry_run:
                script = _dry_run_short(topic)
            else:
                from src import script_writer

                script = script_writer.write_short_script(topic)
            results.append(str(_write_short(topic, script, out_dir, do_tts and not dry_run, do_video, dry_run)))
        else:
            if dry_run:
                long_script = _dry_run_long(topic)
            else:
                from src import script_writer

                long_script = script_writer.write_long_script(topic)
            results.append(str(_write_long(topic, long_script, out_dir, do_tts and not dry_run)))
        if not dry_run:
            state.mark_used(topic["id"], "short" if mode == "shorts" else "long")

    if not dry_run:
        state.save()
    print(f"\nÜretildi: {len(results)} içerik -> {out_dir}")
    for r in results:
        print(" -", r)
    if dry_run:
        print("\n(dry-run: gerçek API çağrısı yapılmadı, state güncellenmedi)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Short video içerik otomasyonu")
    parser.add_argument("--mode", choices=["shorts", "long", "weekly"], default="weekly")
    parser.add_argument("--shorts-count", type=int, default=int(os.environ.get("SHORTS_PER_WEEK", 3)))
    parser.add_argument("--long-count", type=int, default=int(os.environ.get("LONG_PER_WEEK", 1)))
    parser.add_argument("--topic", help="Konu bankasından belirli bir konu id'si (ör. nokia, kodak)")
    parser.add_argument("--skip-tts", action="store_true", help="ElevenLabs çağrısını atla")
    parser.add_argument("--no-video", action="store_true", help="Video render etme")
    parser.add_argument("--dry-run", action="store_true", help="API çağrısı yapmadan sahte veriyle test et")
    args = parser.parse_args()

    if args.mode == "weekly":
        run_weekly_arc(not args.skip_tts, not args.no_video, args.dry_run, args.topic)
    else:
        count = args.shorts_count if args.mode == "shorts" else args.long_count
        run_adhoc(args.mode, count, not args.skip_tts, not args.no_video, args.dry_run, args.topic)
