"""Senarist: mevcut script üretimini (src/script_writer.py) kullanır.

- write(): bölüm planından script üretir; süre (30-45 sn) ve gizemli hook kontrolleri
  script_writer.write_short_script içinde zaten uygulanır.
- revise(): Doğrulayıcı/Eleştirmen/insan geri bildirimini tek bir düzeltme isteğiyle uygular.
Her revizyon, önce/sonra farkıyla log.md'ye yazılır.
"""

import difflib
import json
from pathlib import Path

import run as run_module
from src import script_writer
from src.schemas import ShortScript
from src.utils import slugify

from . import researcher
from .base import RunContext

AGENT = "Senarist"


def short_dir(ctx: RunContext, index: int) -> Path:
    day = ctx.state["plan"]["days"][index]
    return ctx.dir / f"short-{index + 1}-{slugify(day)}"


def part_info(ctx: RunContext, index: int) -> dict:
    days = ctx.state["plan"]["days"]
    return {"index": index + 1, "total": 3, "day": days[index], "next_day": days[index + 1] if index < 2 else ""}


def load(ctx: RunContext, index: int) -> ShortScript:
    data = json.loads((short_dir(ctx, index) / "script.json").read_text(encoding="utf-8"))
    return ShortScript.model_validate(data)


def save(ctx: RunContext, index: int, script: ShortScript) -> None:
    d = short_dir(ctx, index)
    d.mkdir(parents=True, exist_ok=True)
    run_module._save_script(d, ctx.state["topic"], script, part_info(ctx, index))


def write(ctx: RunContext, index: int, previous_narrations: list[str]) -> ShortScript:
    ctx.current_agent = AGENT
    focus = researcher.part_focus_block(ctx, index, previous_narrations)
    script = script_writer.write_short_script(ctx.state["topic"], focus_block=focus)
    save(ctx, index, script)
    ctx.log(AGENT, f"{ctx.state['plan']['days'][index]} script'i yazıldı: \"{script.title}\" "
                   f"({len(script.scenes)} sahne, {script_writer._summary(script)})")
    return script


def revise(ctx: RunContext, index: int, feedback: list[str], source: str) -> ShortScript:
    """feedback: Gemini'ye iletilecek düzeltme maddeleri. source: kimden geldiği (log için)."""
    ctx.current_agent = AGENT
    before = load(ctx, index)
    ctx.log(AGENT, f"{ctx.state['plan']['days'][index]} revizyonu ({source} geri bildirimi, {len(feedback)} madde)",
            "\n".join(f"- {f}" for f in feedback))
    # Çalıştırmaya özel editör notu revizyonlarda da geçerlidir (ör. bölümler arası geçiş cümleleri).
    brief = (ctx.state.get("brief") or "").strip()
    note = ([f"Bu düzeltmeyi yaparken editörün bu seri için talimatlarını koru (bu script {index + 1}/3. "
             f"bölümdür; yalnızca bu bölüme ve tüm bölümlere ortak olanlar geçerli):\n{brief}"] if brief else [])
    after = script_writer._revise(before, feedback + note)
    save(ctx, index, after)
    diff = "\n".join(difflib.unified_diff(
        [f"{i + 1}. [{s.scene_type}] {s.narration}" for i, s in enumerate(before.scenes)],
        [f"{i + 1}. [{s.scene_type}] {s.narration}" for i, s in enumerate(after.scenes)],
        "önce", "sonra", lineterm="", n=0))
    ctx.log(AGENT, "Revizyon farkı (sahneler):", diff or "(sahne metinlerinde değişiklik yok; yalnızca alanlar değişti)")
    hist = ctx.state.setdefault("shorts", {}).setdefault(str(index), {}).setdefault("revisions", [])
    hist.append({"source": source, "feedback": feedback, "diff": diff})
    ctx.save()
    return after
