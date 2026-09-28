"""Yönetmen: mevcut ses (ElevenLabs + marka zamanı kontrolü) ve render (Remotion) sistemini
kullanır; Eleştirmen için kareleri ve contact sheet'leri hazırlar.

Ses yalnızca seslendirme metni değiştiyse yeniden üretilir (yalnızca görsel alanlar
değiştiyse eski ses kullanılır) - ElevenLabs maliyeti gereksiz yere artmaz.
"""

import json
import shutil
import subprocess
from pathlib import Path

import run as run_module
from src import proc
from src import renderer

from . import scriptwriter
from .base import CONFIG, RunContext

AGENT = "Yönetmen"


def produce(ctx: RunContext, index: int) -> Path:
    ctx.current_agent = AGENT
    day = ctx.state["plan"]["days"][index]
    d = scriptwriter.short_dir(ctx, index)
    script = scriptwriter.load(ctx, index)
    record = ctx.state.setdefault("shorts", {}).setdefault(str(index), {})

    if (d / "audio.mp3").exists() and record.get("tts_narration") == script.narration_full:
        ctx.log(AGENT, f"{day}: seslendirme metni değişmedi, mevcut ses kullanılıyor.")
    else:
        ctx.log(AGENT, f"{day}: seslendirme üretiliyor ({len(script.narration_full)} karakter).")
        script = run_module._synthesize_checked(d, ctx.state["topic"], script, scriptwriter.part_info(ctx, index))
        record["tts_narration"] = script.narration_full
        ctx.save()

    ctx.log(AGENT, f"{day}: render başlıyor.")
    video = renderer.render(d, part_info=scriptwriter.part_info(ctx, index))
    sheets = contact_sheets(d, video)
    record["video"] = str(video)
    record["sheets"] = [str(s) for s in sheets]
    ctx.save()
    ctx.log(AGENT, f"{day}: video hazır -> {video.relative_to(ctx.dir.parent.parent)} ({len(sheets)} contact sheet)")
    return video


def frame_plan(video_dir: Path) -> list[dict]:
    """Eleştirmen için kare zamanları: her sahneden BİR kare, sahnenin %80'inde (sayaç, vurgu
    şeridi, grafik çizimi gibi giriş animasyonları oturduktan sonra) + outro. Kare k = sahne k.
    Sabit aralıkla alınan kareler animasyonların ortasına denk geliyordu (sayacın ara değeri
    "yanlış rakam", yarım vurgu şeridi "köşeli parantez" sanılıyordu); ayrı bir "video başı"
    karesi de sayaç ortasını yakalıyor ve modelin kareleri sahnelerle bir kaydırarak
    eşleştirmesine yol açıyordu. İlk 3 saniye (hook) 1. sahnenin karesiyle kontrol edilir."""
    props = json.loads((video_dir / "assets" / "props.json").read_text(encoding="utf-8"))
    fps = props["fps"]
    plan = []
    for n, s in enumerate(props["scenes"], 1):
        t = (s["from"] + 0.8 * s["durationInFrames"]) / fps
        plan.append({"t": round(t, 2), "label": f"sahne {n} [{s['type']}]"})
    if props.get("outro"):
        o = props["outro"]
        plan.append({"t": round((o["from"] + 0.8 * o["durationInFrames"]) / fps, 2), "label": "kapanış kartı"})
    return plan


def contact_sheets(video_dir: Path, video: Path) -> list[Path]:
    """frame_plan karelerini çıkarır ve `frames_per_sheet`'lik (4x2) sayfalar yapar."""
    per = int(CONFIG.get("qa", {}).get("frames_per_sheet", 8))
    kdir = video_dir / "kareler"
    if kdir.exists():
        shutil.rmtree(kdir)
    kdir.mkdir(parents=True)
    plan = frame_plan(video_dir)
    for n, f in enumerate(plan, 1):
        proc.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{f['t']:.3f}", "-i", str(video), "-frames:v", "1",
                        str(kdir / f"kare_{n:02d}.png")], check=True)
    (kdir / "kareler.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    sheets = []
    for n, start in enumerate(range(0, len(plan), per), 1):
        dest = kdir / f"sheet_{n}.png"
        proc.run(
            ["ffmpeg", "-v", "error", "-y", "-start_number", str(start + 1), "-i", str(kdir / "kare_%02d.png"),
             "-frames:v", "1", "-vf", f"scale=360:-1,tile=4x2:nb_frames={min(per, len(plan) - start)}:padding=6:color=white",
             str(dest)],
            check=True,
        )
        sheets.append(dest)
    return sheets
