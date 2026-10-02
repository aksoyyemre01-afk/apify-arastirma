"""Uzun video akışı: komutlar (pipeline.py --long), onay kapıları ve dry-run (sahte istemci).

Kapılar: long_estimate [A] -> long_voice_review [B] -> (arka planda üretim) -> long_final [C] -> long_published.
Bütçe/kredi yetmezse: long_postponed (onayla aşılamaz; --approve yalnızca koşullar sağlanınca devam eder).
"""

import json
import re
import types as pytypes
from datetime import date, datetime

from src import script_writer, tts
from src.schemas import LongScene, LongSection, LongVideoScript, ShortScript

from . import long_video as lv
from . import review
from .base import RUNS_DIR, BudgetExceeded, RunContext, attach_usage_hooks, notify


def long_dir_name(source: str, dry_run: bool) -> str:
    return f"{source}-uzun" + ("-dryrun" if dry_run else "")


def _last_long_date() -> date | None:
    dates = []
    for p in RUNS_DIR.glob("*-uzun"):
        st = p / "state.json"
        if st.exists():
            dates.append(datetime.fromtimestamp(st.stat().st_mtime).date())
    return max(dates, default=None)


def start(run: str | None, dry_run: bool) -> RunContext:
    """ONAY A: kaynak araştırmayı topla, API'siz tahmin + kilit kontrolü, review.md."""
    if run:
        source = RUNS_DIR / run
    else:
        last = _last_long_date()
        if last and (date.today() - last).days < 7 * lv.cfg()["every_n_weeks"] and not dry_run:
            raise SystemExit(f"Son uzun video {last} tarihinde; sıklık {lv.cfg()['every_n_weeks']} hafta "
                             f"(config/pipeline.json -> long.every_n_weeks). Belirli bir run için: --long --run <hafta>")
        cands = lv.candidate_runs()
        if not cands:
            raise SystemExit("Son iki haftada short run'ı yok; uzun video konusu seçilemedi.")
        source = cands[0]
    if not (source / "state.json").exists():
        raise SystemExit(f"Kaynak run bulunamadı: {source.name}")
    path = RUNS_DIR / long_dir_name(source.name, dry_run)
    if (path / "state.json").exists() and not dry_run:
        raise SystemExit(f"{path.name} zaten var. Durum: python pipeline.py --status --run {path.name}")
    if dry_run and path.exists():
        import shutil
        shutil.rmtree(path)
    src = RunContext(source)
    ctx = RunContext(path)
    attach_usage_hooks(ctx)
    research = lv.source_research(src)
    est = lv.estimate(research)
    lim = lv.check_limits(est)
    ctx.state.update(kind="long", source_run=source.name, research=research, estimate=est, limit_check=lim,
                     dry_run=dry_run)
    ctx.log("pipeline", f"Uzun video çalıştırması: {path.name} (kaynak {source.name}: {research['topic']['title']})")
    ctx.log(lv.AGENT, f"Tahmin: Gemini ~${est['gemini_with_margin']:.2f} (pay dahil), ElevenLabs ~{est['chars_with_margin']:,} "
                      f"karakter (pay dahil); kilit: {'UYGUN' if lim['ok'] else 'ERTELE'}",
            "\n".join(lim["reasons"]) or None)
    ctx.set_stage("long_estimate")
    review.write(ctx)
    if not dry_run:
        notify("Uzun video: tahmin hazır", f"{research['topic']['title']} — ONAY A için review.md")
    return ctx


def _postpone(ctx: RunContext, reasons: list[str], at: str) -> None:
    ctx.state["postponed"] = {"at": at, "reasons": reasons, "when": datetime.now().isoformat(timespec="seconds")}
    ctx.log("pipeline", "Uzun video ERTELENDİ (bütçe/kredi): " + " | ".join(reasons))
    ctx.set_stage("long_postponed")
    review.write(ctx)
    notify("Uzun video ertelendi", (reasons or ["bütçe/kredi"])[0][:200])


def approve(ctx: RunContext, spawn_worker) -> None:
    stage = ctx.stage
    if stage in ("long_estimate", "long_postponed") and ctx.state.get("postponed", {}).get("at", "script") == "script" \
            and "script" not in ctx.state:
        _write_and_verify(ctx)
    elif stage in ("long_voice_review", "long_postponed"):
        _start_voice(ctx, spawn_worker)
    elif stage == "long_final":
        dest = lv.publish(ctx)
        ctx.state["published_to"] = str(dest)
        ctx.set_stage("long_published")
        review.write(ctx)
        print(f"Yayına hazır: {dest}")
    elif stage == "long_error":
        ctx.state.pop("error", None)
        _start_voice(ctx, spawn_worker)
    else:
        raise SystemExit(f"Onay bekleyen bir uzun video aşaması yok (aşama: {stage}).")


def _write_and_verify(ctx: RunContext) -> None:
    """ONAY A sonrası: kilitleri yeniden kontrol et, script yaz (Gemini) + yalnızca yeni iddiaları doğrula."""
    research = ctx.state["research"]
    lim = lv.check_limits(lv.estimate(research))
    ctx.state["limit_check"] = lim
    if not lim["ok"] and not ctx.state.get("dry_run"):
        return _postpone(ctx, lim["reasons"], "script")
    ctx.state.pop("postponed", None)
    ctx.log("insan", "Uzun video tahmini onaylandı (ONAY A).")
    try:
        script = lv.write_script(ctx, research)
        script = lv.verify_new(ctx, script, research)
    except BudgetExceeded as e:
        return _postpone(ctx, [str(e)], "script")
    est = lv.estimate(research, script)
    ctx.state.update(script=script.model_dump(), script_text=script.narration_full, estimate=est,
                     limit_check=lv.check_limits(est))
    ctx.set_stage("long_voice_review")
    review.write(ctx)
    notify("Uzun video: script hazır", f"{script.title} — ses için ONAY B (review.md)")


def _start_voice(ctx: RunContext, spawn_worker) -> None:
    """ONAY B sonrası: kesin karakterle kilit kontrolü; uygunsa üretimi arka planda başlat."""
    est = lv.estimate(ctx.state["research"], LongVideoScript.model_validate(ctx.state["script"]))
    lim = lv.check_limits(est)
    ctx.state.update(estimate=est, limit_check=lim)
    if not lim["ok"] and not ctx.state.get("dry_run"):
        return _postpone(ctx, lim["reasons"], "voice")
    ctx.state.pop("postponed", None)
    ctx.log("insan", "Uzun video sesi onaylandı (ONAY B).")
    ctx.save()
    spawn_worker(ctx)


def produce(ctx: RunContext) -> None:
    """Arka plan işçisi (uzun video)."""
    import traceback
    try:
        ctx.set_stage("long_producing")
        lv.produce(ctx, dry_run=bool(ctx.state.get("dry_run")))
        ctx.set_stage("long_final")
        review.write(ctx)
        notify("Uzun video hazır", "Final onayı (ONAY C) için review.md")
    except BudgetExceeded as e:
        _postpone(ctx, [str(e)], "voice")
    except Exception as e:  # noqa: BLE001
        ctx.state["error"] = "".join(traceback.format_exception(e))[-3000:]
        ctx.log("pipeline", f"HATA: {e}", ctx.state["error"])
        ctx.set_stage("long_error")
        review.write(ctx)
        notify("Uzun video hatası", str(e)[:200])


# ---------------------------------------------------------------------------- dry-run (API yok)

_PERSON = re.compile(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+ [A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\b")


def _photo_ok(name: str) -> bool:
    from src import commons
    return commons.resolve(name) is not None


def _dry_script(ctx: RunContext) -> LongVideoScript:
    """Kaynak run'ın DOĞRULANMIŞ metinlerinden kurulan sahte uzun video script'i."""
    src = RunContext(RUNS_DIR / ctx.state["source_run"])
    plan = src.state["plan"]
    shorts = [ShortScript.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(src.dir.glob("short-*/script.json"))]
    chapters, used_people = [], set()
    for part, s in zip(plan["parts"], shorts):
        scenes = []
        for sc in s.scenes:
            d = sc.model_dump()
            names = [n for n in _PERSON.findall(sc.narration) if n not in used_people and _photo_ok(n)]
            if names and d["scene_type"] in ("quote", "logo_intro"):
                d.update(scene_type="photo", brand=names[0], label=names[0])
                used_people.add(names[0])
            scenes.append(LongScene.model_validate(d))
        chapters.append(LongSection(heading=part["focus_title"], narration=s.narration_full, scenes=scenes))
    hook_text = plan["topic_summary"]
    hook = LongSection(narration=hook_text, scenes=[LongScene(narration=hook_text, scene_type="quote", brand="", text="")])
    close_text = plan["parts"][-1]["cliffhanger"]
    closing = LongSection(narration=close_text, scenes=[LongScene(narration=close_text, scene_type="quote", text="")])
    return LongVideoScript(title=f"{src.state['topic']['title']} (dry-run)", main_brand=src.state["topic"].get("company", ""),
                           hook=hook, chapters=chapters, closing=closing, cta="Kurumsal Dedektif'i takip edin",
                           description=hook_text, tags=["theranos", "elizabeth holmes", "iş dünyası", "skandal"],
                           thumbnail_value="9", thumbnail_unit="MİLYAR $", thumbnail_headline="Tek damla kan yalanı")


def run_dry(run: str) -> RunContext:
    """Tüm akış, gerçek API OLMADAN: sahte Gemini (doğrulanmış metinlerden script, sahte doğrulama ve
    görsel QA), sahte TTS (sessiz ses + tahmini zamanlar). Kilit kararı gösterilir ama test için devam edilir."""
    from . import critic

    ctx = start(run, dry_run=True)
    calls = []

    def fake_generate(contents, config, purpose, model=None):
        calls.append(purpose)
        if purpose == "uzun video script":
            return pytypes.SimpleNamespace(text=_dry_script(ctx).model_dump_json(), candidates=[], usage_metadata=None)
        if purpose.endswith("araştırma (Google Search)") or purpose.endswith("araştırma (tekrar)"):
            gm = pytypes.SimpleNamespace(web_search_queries=["dry-run"], grounding_chunks=[], grounding_supports=[])
            return pytypes.SimpleNamespace(text="dry-run araştırma", candidates=[pytypes.SimpleNamespace(grounding_metadata=gm)],
                                           usage_metadata=None)
        if purpose.endswith("karar"):
            n = len(lv.new_sentences(LongVideoScript.model_validate(json.loads(_dry_script(ctx).model_dump_json())), ctx.state["research"]))
            return pytypes.SimpleNamespace(text=json.dumps({"claims": [{"item": i, "claim": "dry-run", "verdict": "verified"} for i in range(1, n + 1)]}),
                                           candidates=[], usage_metadata=None)
        if purpose.startswith("QA görsel puanlama"):
            crit = critic.Critique(violations=[], scores=[critic.RuleScore(rule=r, evidence="dry-run", score=4, reason="dry-run", target="yok", fix="")
                                                          for r in (1, 3, 5, 6, 7, 10)],
                                   improvements=["dry-run 1", "dry-run 2"], summary="dry-run: sahte QA")
            return pytypes.SimpleNamespace(text=crit.model_dump_json(), candidates=[], usage_metadata=None)
        raise RuntimeError(f"dry-run: beklenmeyen Gemini isteği: {purpose}")

    def no_tts(*a, **k):
        raise RuntimeError("dry-run: ElevenLabs isteği yapılmaz")

    script_writer.generate_raw = fake_generate
    tts.synthesize_with_timestamps = tts.synthesize = no_tts
    # Dry-run'da gerçek istek gitmez; sert Gemini kilidi yalnızca "gerçekte burada durdururdu" diye
    # kaydedilir ve akış test için sürer. Gerçek akışta kilit aynen geçerlidir.
    from . import limits as _limits
    real_guard = _limits.gemini_guard
    hits = ctx.state.setdefault("dry_run_lock_hits", [])

    def recording_guard(purpose: str = "") -> None:
        try:
            real_guard(purpose)
        except BudgetExceeded as e:
            if str(e) not in hits:
                hits.append(str(e))

    _limits.gemini_guard = recording_guard
    ctx.state["dry_run_vision"] = True
    ctx.save()
    approve(ctx, spawn_worker=lambda c: None)       # ONAY A -> script + doğrulama (sahte)
    approve(ctx, spawn_worker=produce)               # ONAY B -> ses (sahte) + render + QA (sahte), ön planda
    ctx.state["dry_run_calls"] = calls
    ctx.save()
    review.write(ctx)
    return ctx
