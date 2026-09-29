"""Bir short'un sesini mevcut script'ten yeniden üretir ve videoyu yeniden render eder.

Gemini isteği yapılmaz (script değişmez; Gemini çağrısı kilitlenir). ElevenLabs isteği
harcama kilidinden geçer (agents/limits.py: kalan kredi API'den okunur, yetmiyorsa ya da
okunamıyorsa ses üretilmez). Rakamlar seslendirmeye Türkçe yazıyla gider (src/tr_numbers.py);
sonunda söylenen rakamlar script ve ekranla karşılaştırılır (src/speech_check.py).
assets/audio/music.mp3 varsa render onu otomatik ekler.

Kullanım:
    python tools/revoice.py --dir runs/2026-W40/short-3-cuma
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import run as run_module  # noqa: E402
from agents import director, limits  # noqa: E402
from agents.base import BudgetExceeded, RunContext, attach_usage_hooks  # noqa: E402
from src import renderer, script_writer, speech_check  # noqa: E402
from src.schemas import ShortScript  # noqa: E402


def _no_gemini(*_a, **_k):
    raise RuntimeError("revoice: Gemini isteği yapılmaz")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Short'un sesini yeniden üret + render (Gemini yok)")
    p.add_argument("--dir", required=True, help="Short klasörü (script.json içerir)")
    d = Path(p.parse_args().dir).resolve()

    run_dir = d.parent
    if (run_dir / "state.json").exists():
        ctx = RunContext(run_dir)          # kullanım o çalıştırmanın usage.json'una yazılır
        ctx.current_agent = "Yönetmen"
        attach_usage_hooks(ctx)            # + harcama kilitleri
    else:
        limits.attach_guards()
    script_writer.generate_raw = _no_gemini

    script = ShortScript.model_validate_json((d / "script.json").read_text(encoding="utf-8"))
    try:
        timings = run_module._synthesize(d, script)
    except BudgetExceeded as e:
        raise SystemExit(f"Ses üretilmedi: {e}")
    if not timings:
        raise SystemExit("Kelime zamanları alınamadı; render yapılmadı.")
    video = renderer.render(d)
    director.contact_sheets(d, video)
    res = speech_check.check_dir(d)
    print(f"Video: {video}")
    print(f"Söylenen rakamlar: {'OK' if res['spoken'][0] else 'UYUŞMAZLIK'} — {res['spoken'][1]}")
    print(f"Ekran rakamları: {'OK' if res['screen'][0] else 'UYUŞMAZLIK'} — {res['screen'][1]}")
    print("\nKalan bakiye / kredi:\n" + limits.balance_report())
