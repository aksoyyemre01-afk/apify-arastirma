"""Haftalık multi-agent short üretimi.

Araştırmacı -> Doğrulayıcı (plan) -> [ONAY 1: konu] -> Senarist -> Doğrulayıcı -> Yönetmen -> Eleştirmen
(geçmezse ilgili agent'a geri, en fazla qa.max_rounds revizyon turu) -> [ONAY 2: final].
Onaylar runs/<hafta>/review.md üzerinden tek komutla verilir.

Kullanım:
    python pipeline.py --week                     # haftanın konusunu seç, planla -> review.md (onay 1)
    python pipeline.py --week --topic kodak       # belirli bir konuyla başlat
    python pipeline.py --approve                  # bekleyen aşamayı onayla
    python pipeline.py --reject "gerekçe"         # reddet (onay 1: yeni konu; onay 2: düzelttir)
    python pipeline.py --reject "gerekçe" --keep-topic   # onay 1: konuyu koru, planı gerekçeyle yeniden üret
    python pipeline.py --reject "gerekçe" --short 2   # yalnızca 2. short'u düzelttir
    python pipeline.py --status                   # durum + maliyet
    --run 2026-W40  ile belirli bir haftayı seçin (varsayılan: en son çalıştırma)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
# pythonw.exe ile (konsolsuz, ör. Görev Zamanlayıcı'dan) çalışırken stdout/stderr yoktur;
# çıktı runs/pipeline-konsol.log dosyasına yazılır, böylece hiçbir pencere açılmaz.
if sys.stdout is None or sys.stderr is None:
    (ROOT / "runs").mkdir(exist_ok=True)
    _log = open(ROOT / "runs" / "pipeline-konsol.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agents import critic, director, researcher, review, scriptwriter, verifier  # noqa: E402
from agents.base import CONFIG, RUNS_DIR, BudgetExceeded, RunContext, attach_usage_hooks, notify  # noqa: E402
from src import proc
from src import state as topic_state  # noqa: E402
from src.utils import slugify  # noqa: E402


# ---------------------------------------------------------------------------- yardımcılar

def _week_id() -> str:
    y, w, _ = date.today().isocalendar()
    return f"{y}-W{w:02d}"


def _latest_run() -> Path | None:
    runs = [p for p in RUNS_DIR.glob("*-W*") if (p / "state.json").exists()]
    return max(runs, key=lambda p: (p / "state.json").stat().st_mtime) if runs else None


def _open(run: str | None) -> RunContext:
    path = RUNS_DIR / run if run else _latest_run()
    if not path or not (path / "state.json").exists():
        raise SystemExit("Çalıştırma bulunamadı. Önce: python pipeline.py --week")
    ctx = RunContext(path)
    attach_usage_hooks(ctx)
    return ctx


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    out = proc.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def _spawn_worker(ctx: RunContext) -> None:
    """Üretimi arka planda başlatır (Windows'ta bağımsız süreç); komut hemen döner."""
    if _pid_alive(ctx.state.get("worker_pid")):
        raise SystemExit(f"Bu hafta için üretim zaten çalışıyor (PID {ctx.state['worker_pid']}).")
    out = (ctx.dir / "pipeline.out").open("a", encoding="utf-8")
    args = dict(cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, close_fds=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    cmd = [sys.executable, str(ROOT / "pipeline.py"), "--continue", "--run", ctx.dir.name]
    if os.name == "nt":
        # Gizli bir konsolla başlatılır (CREATE_NO_WINDOW). DETACHED_PROCESS kullanılmaz:
        # konsolsuz bir süreçten çağrılan her ffmpeg/ffprobe/node yeni ve GÖRÜNÜR bir pencere
        # açar (ve Windows CREATE_NO_WINDOW'u DETACHED_PROCESS ile birlikte yok sayar).
        # Gizli konsolu tüm alt süreçler (Remotion'un başlattıkları dahil) miras alır.
        base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        # Başlatan terminal/araç bir "job object" içindeyse, kapanırken tüm alt süreçleri
        # öldürür; işçi job'dan ayrılarak başlatılır. Ortam izin vermezse ayrılmadan başlar.
        try:
            proc = subprocess.Popen(cmd, creationflags=base | subprocess.CREATE_BREAKAWAY_FROM_JOB, **args)
        except OSError:
            proc = subprocess.Popen(cmd, creationflags=base, **args)
    else:
        proc = subprocess.Popen(cmd, start_new_session=True, **args)
    ctx.state["worker_pid"] = proc.pid
    ctx.set_stage("producing")
    review.write(ctx)
    print(f"Üretim arka planda başladı (PID {proc.pid}). İlerleme: {ctx.log_path}\n"
          f"Bittiğinde bildirim gelir ve {ctx.dir / 'review.md'} güncellenir.")


def _finish_report(ctx: RunContext) -> None:
    print("\nKullanım ve tahmini maliyet:\n" + ctx.cost_report())
    ctx.log("pipeline", f"Toplam tahmini maliyet: ${ctx.cost_summary()['total_usd']:.4f}")


# ---------------------------------------------------------------------------- aşamalar

def cmd_week(topic_id: str | None) -> None:
    run_id = _week_id()
    path = RUNS_DIR / run_id
    n = 2
    while (path / "state.json").exists():
        existing = RunContext(path)
        if existing.stage != "published":
            raise SystemExit(f"{run_id} için bir çalıştırma zaten var (aşama: {existing.stage}). "
                             f"Durum: python pipeline.py --status --run {path.name}")
        path = RUNS_DIR / f"{run_id}-{n}"
        n += 1
    ctx = RunContext(path)
    attach_usage_hooks(ctx)
    ctx.log("pipeline", f"Yeni haftalık çalıştırma: {path.name}")
    _plan_for_review(ctx, topic_id=topic_id)
    rp = review.write(ctx)
    notify("Haftanın konusu hazır", f"{ctx.state['topic']['title']} — onay için review.md")
    print(f"\nOnay dosyası: {rp}")
    _finish_report(ctx)


def _plan_for_review(ctx: RunContext, topic_id: str | None = None, keep_topic: bool = False) -> None:
    """Araştırmacı planlar, Doğrulayıcı planı kontrol edip düzelttirir; ardından konu onayı."""
    researcher.plan_week(ctx, topic_id, keep_topic=keep_topic)
    ctx.check_budget()
    verifier.verify_plan(ctx)
    ctx.set_stage("topic_review")


def cmd_approve(ctx: RunContext) -> None:
    stage = ctx.stage
    if stage == "topic_review":
        ctx.log("insan", "Konu onaylandı.")
        _spawn_worker(ctx)
    elif stage == "final_review":
        ctx.log("insan", "Final videolar onaylandı.")
        publish(ctx)
    elif stage == "budget_paused":
        ctx.budget_extra += float(CONFIG.get("budget_usd_per_week", 2.0))
        ctx.state["budget_extra_usd"] = ctx.budget_extra
        ctx.log("insan", f"Bütçe artırıldı (+${CONFIG.get('budget_usd_per_week', 2.0)}); üretime devam.")
        _spawn_worker(ctx)
    elif stage == "error":
        ctx.state.pop("error", None)
        ctx.log("insan", "Hatadan sonra yeniden deneme onaylandı.")
        _spawn_worker(ctx)
    elif stage == "producing" and not _pid_alive(ctx.state.get("worker_pid")):
        # İşçi süreci beklenmedik şekilde kapanmış (ör. bilgisayar yeniden başladı): kaldığı yerden devam.
        ctx.log("insan", "Durmuş üretim kaldığı yerden devam ettiriliyor.")
        _spawn_worker(ctx)
    else:
        raise SystemExit(f"Onay bekleyen bir aşama yok (aşama: {stage}).")


def cmd_reject(ctx: RunContext, reason: str, short: int | None, keep_topic: bool = False) -> None:
    stage = ctx.stage
    if keep_topic and stage != "topic_review":
        raise SystemExit("--keep-topic yalnızca konu onayı aşamasında kullanılır.")
    if stage == "topic_review" and keep_topic:
        ctx.log("insan", f"Plan reddedildi (konu korunuyor): {reason}")
        ctx.state.setdefault("plan_feedback", []).append(reason)
        ctx.save()
        _plan_for_review(ctx, keep_topic=True)
        rp = review.write(ctx)
        notify("Plan yeniden üretildi", f"{ctx.state['topic']['title']} — onay için review.md")
        print(f"Plan yeniden üretildi ve doğrulandı. Onay dosyası: {rp}")
        _finish_report(ctx)
    elif stage == "topic_review":
        ctx.log("insan", f"Konu reddedildi: {reason}")
        ctx.state.setdefault("rejected_topic_ids", []).append(ctx.state["topic"]["id"])
        ctx.state.setdefault("rejection_reasons", []).append(reason)
        ctx.save()
        _plan_for_review(ctx)
        rp = review.write(ctx)
        notify("Yeni konu önerildi", f"{ctx.state['topic']['title']} — onay için review.md")
        print(f"Yeni konu önerildi. Onay dosyası: {rp}")
        _finish_report(ctx)
    elif stage == "final_review":
        targets = [short - 1] if short else [0, 1, 2]
        if any(t not in (0, 1, 2) for t in targets):
            raise SystemExit("--short 1, 2 ya da 3 olmalı.")
        for t in targets:
            rec = ctx.state["shorts"][str(t)]
            rec["human_feedback"] = reason
            rec["status"] = "human_revision"
            rec["qa_revisions"] = 0
        ctx.log("insan", f"Final reddedildi ({', '.join(ctx.state['plan']['days'][t] for t in targets)}): {reason}")
        ctx.save()
        _spawn_worker(ctx)
    else:
        raise SystemExit(f"Reddedilecek bir onay aşaması yok (aşama: {stage}).")


def produce(ctx: RunContext) -> None:
    """Arka plan işçisi: 3 short'u sırayla üretir; kaldığı yerden devam edebilir."""
    ctx.state["worker_pid"] = os.getpid()
    ctx.save()
    try:
        narrations: list[str] = []
        for i in range(3):
            _produce_one(ctx, i, narrations)
            if (scriptwriter.short_dir(ctx, i) / "script.json").exists():
                narrations.append(scriptwriter.load(ctx, i).narration_full)
        ctx.state["worker_pid"] = None
        ctx.set_stage("final_review")
        review.write(ctx)
        failed = [ctx.state["plan"]["days"][int(i)] for i, r in ctx.state["shorts"].items() if r.get("status") == "failed"]
        notify("Haftanın videoları hazır" if not failed else "Videolar hazır — bazıları QA'dan geçmedi",
               "Final onayı için review.md" + (f" (sorunlu: {', '.join(failed)})" if failed else ""))
    except BudgetExceeded as e:
        ctx.log("pipeline", f"Durduruldu: {e}")
        ctx.state["worker_pid"] = None
        ctx.set_stage("budget_paused")
        review.write(ctx)
        notify("Bütçe sınırı", f"{e}. Devam için review.md")
    except Exception as e:  # noqa: BLE001 - her hata raporlanır, işçi sessizce ölmez
        ctx.state["error"] = "".join(traceback.format_exception(e))[-3000:]
        ctx.log("pipeline", f"HATA: {e}", ctx.state["error"])
        ctx.state["worker_pid"] = None
        ctx.set_stage("error")
        review.write(ctx)
        notify("Pipeline hatası", str(e)[:200])
    finally:
        _finish_report(ctx)


def _produce_one(ctx: RunContext, i: int, previous: list[str]) -> None:
    shorts = ctx.state.setdefault("shorts", {})
    rec = shorts.setdefault(str(i), {"status": "new"})
    day = ctx.state["plan"]["days"][i]
    max_rev = int(CONFIG.get("qa", {}).get("max_rounds", 3))

    if rec.get("status") in ("passed", "failed"):
        return
    if rec.get("status", "new") == "new":
        ctx.check_budget()
        scriptwriter.write(ctx, i, previous)
        rec["status"] = "written"
        ctx.save()
    if rec["status"] == "human_revision":
        ctx.check_budget()
        actions = critic.human_feedback_actions(rec.pop("human_feedback", ""))
        _apply_actions(ctx, i, actions, source="insan editör")
        rec["status"] = "rendered"
        ctx.save()
    if rec["status"] == "written":
        ctx.check_budget()
        verifier.verify(ctx, i)
        rec["status"] = "verified"
        ctx.save()
    if rec["status"] == "verified":
        ctx.check_budget()
        director.produce(ctx, i)
        rec["status"] = "rendered"
        ctx.save()

    # QA döngüsü
    while rec["status"] == "rendered":
        ctx.check_budget()
        result = critic.review(ctx, i, round_no=len(rec.get("qa_rounds", [])) + 1)
        if result["passed"]:
            rec["status"] = "passed"
            break
        actions = {k: v for k, v in result["actions"].items() if k != "yok"}
        fixable = {k: v for k, v in actions.items() if k != "kod"}
        if not fixable:
            rec["status"] = "failed"
            rec["stop_reason"] = ("kalan sorunlar kod/render kaynaklı; script değişikliğiyle düzelmez, "
                                  "geliştirici incelemesi gerekiyor" if actions else "geçme şartı karşılanmadı, "
                                  "düzeltilebilir somut bir öneri yok")
            break
        if rec.get("qa_revisions", 0) >= max_rev:
            rec["status"] = "failed"
            rec["stop_reason"] = f"{max_rev} revizyon turundan sonra hâlâ geçmedi"
            break
        rec["qa_revisions"] = rec.get("qa_revisions", 0) + 1
        ctx.log("pipeline", f"{day}: QA revizyon turu {rec['qa_revisions']}/{max_rev} "
                            f"({critic.summarize_actions(actions)})")
        _apply_actions(ctx, i, fixable, source=f"Eleştirmen tur {len(rec['qa_rounds'])}")
        ctx.save()
    if rec["status"] == "failed":
        ctx.log("pipeline", f"{day}: DURDURULDU — {rec['stop_reason']}")
    ctx.save()


def _apply_actions(ctx: RunContext, i: int, actions: dict[str, list[str]], source: str) -> None:
    rec = ctx.state["shorts"][str(i)]
    script_changed = False
    if actions.get("senarist"):
        scriptwriter.revise(ctx, i, actions["senarist"], source=source)
        script_changed = True
    if script_changed or actions.get("dogrulayici"):
        verifier.verify(ctx, i)
    if actions.get("yonetmen"):
        rec["tts_narration"] = None  # ses/zamanlama sorunu: sesi yeniden üret
    director.produce(ctx, i)


def publish(ctx: RunContext) -> None:
    dest_root = ROOT / CONFIG.get("publish_dir", "yayina-hazir") / ctx.dir.name
    dest_root.mkdir(parents=True, exist_ok=True)
    for i, day in enumerate(ctx.state["plan"]["days"]):
        d = scriptwriter.short_dir(ctx, i)
        if not (d / "video.mp4").exists():
            ctx.log("pipeline", f"{day}: video yok, yayına hazır klasörüne kopyalanmadı.")
            continue
        script = scriptwriter.load(ctx, i)
        name = f"{i + 1}-{slugify(day)}-{slugify(script.title)[:50]}"
        shutil.copy(d / "video.mp4", dest_root / f"{name}.mp4")
        (dest_root / f"{name}.txt").write_text(
            f"{script.title}\n\n{script.cta}\n\n{' '.join(script.hashtags)}\n", encoding="utf-8")
    topic_state.mark_used(ctx.state["topic"]["id"], "weekly-arc")
    topic_state.save()
    ctx.state["published_to"] = str(dest_root)
    ctx.set_stage("published")
    review.write(ctx)
    print(f"Yayına hazır: {dest_root}")
    _finish_report(ctx)


def cmd_status(ctx: RunContext) -> None:
    alive = _pid_alive(ctx.state.get("worker_pid"))
    print(f"Çalıştırma: {ctx.dir.name}\nAşama: {ctx.stage}"
          + (f" (işçi PID {ctx.state.get('worker_pid')}, {'çalışıyor' if alive else 'DURMUŞ - devam için: --approve'})"
             if ctx.stage == "producing" else ""))
    if "topic" in ctx.state:
        print(f"Konu: {ctx.state['topic']['title']}")
    for i, rec in sorted(ctx.state.get("shorts", {}).items()):
        qa = (rec.get("qa_rounds") or [None])[-1]
        print(f"  {ctx.state['plan']['days'][int(i)]}: {rec.get('status')}"
              + (f", QA ort. {qa['average']}" if qa else ""))
    print(f"Onay dosyası: {ctx.dir / 'review.md'}\n\n" + ctx.cost_report())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Haftalık multi-agent short üretimi")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--week", action="store_true", help="Yeni hafta: konu seç ve planla (onay 1)")
    g.add_argument("--approve", action="store_true", help="Bekleyen aşamayı onayla")
    g.add_argument("--reject", metavar="GEREKCE", help="Bekleyen aşamayı gerekçeyle reddet")
    g.add_argument("--status", action="store_true", help="Durum ve maliyet")
    g.add_argument("--continue", dest="cont", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--run", help="Çalıştırma kimliği (ör. 2026-W40); varsayılan en son")
    p.add_argument("--topic", help="--week ile: konu bankasından belirli bir konu id'si")
    p.add_argument("--short", type=int, help="--reject ile: yalnızca bu short (1-3)")
    p.add_argument("--keep-topic", action="store_true",
                   help="--reject ile, konu onayında: konuyu koru, planı gerekçeyle yeniden üret")
    a = p.parse_args()

    if a.week:
        cmd_week(a.topic)
    elif a.cont:
        produce(_open(a.run))
    elif a.approve:
        cmd_approve(_open(a.run))
    elif a.reject:
        cmd_reject(_open(a.run), a.reject, a.short, a.keep_topic)
    elif a.status:
        cmd_status(_open(a.run))
