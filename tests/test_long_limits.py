"""Uzun video bütçe kilitlerinin testleri (gerçek API çağrısı YOK).

Kontrol edilenler:
- ElevenLabs: short payı ayrıldıktan sonra kalan kredi tahmin x 1,10'a yetmiyorsa uzun video ertelenir.
- Gemini: bu hafta harcanan + short payı + tahmin x 1,10 > sınır ise ertelenir; short'lar bitince pay kalkar.
- --approve kilidi aşamaz: ertelenmiş run onaylansa da Gemini/ElevenLabs isteği gitmez.
- Yalnızca config (sınır) değişince devam eder.
- ONAY B'de (ses) kredi yetmezse ses üretilmez, işçi başlatılmaz.

Çalıştırma: python tests/test_long_limits.py   (ya da pytest)
"""

import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import base, limits, long_flow  # noqa: E402
from agents import long_video as lv  # noqa: E402
from src import script_writer  # noqa: E402

TODAY = date(2026, 10, 7)  # W41 çarşamba
EST = {"chars": 4800, "chars_with_margin": 5280, "gemini_usd": 0.39, "gemini_with_margin": 0.43,
       "gemini_items": {}, "history_n": 0, "based_on_script": False}


class Env:
    """Geçici runs/ klasörü + sahte ElevenLabs/Gemini durumları."""

    def __init__(self, el_remaining=21000, reset="2026-10-23", spent=0.0, short_stage=None):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = []
        self._set(lv, "RUNS_DIR", self.tmp)
        self._set(long_flow, "RUNS_DIR", self.tmp)
        self._set(limits, "elevenlabs_status", lambda: {"tier": "starter", "used": 27000 - el_remaining, "plan_limit": 30000,
                                                        "cap": 27000, "remaining": el_remaining, "reset": reset})
        self._set(limits, "weekly_gemini_usd", lambda now=None: spent)
        # Testler config'den bağımsız: haftalık sınır 2,00 (geçici sınır kaydı olsa da).
        self._set(limits, "gemini_limit", lambda today=None: 2.0)
        self.api_calls = []
        self._set(script_writer, "generate_raw", self._no_api)
        if short_stage:
            d = self.tmp / "2026-W41"
            d.mkdir()
            (d / "state.json").write_text(json.dumps({"stage": short_stage, "shorts": {}}), encoding="utf-8")

    def _no_api(self, *a, **k):
        self.api_calls.append(k.get("purpose"))
        raise AssertionError("gerçek Gemini isteği yapılmamalıydı")

    def _set(self, obj, name, value):
        self.patches.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def close(self):
        for obj, name, value in reversed(self.patches):
            setattr(obj, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)


def test_el_reserve_postpones():
    env = Env(el_remaining=12000, short_stage="final_review")
    try:
        r = lv.check_limits(EST, TODAY)
        # bu haftanın short'ları bitti (0) + 2 gelecek hafta (12, 19 Ekim) x 3 x 1300 = 7800 -> kullanılabilir 4200 < 5280
        assert r["el_reserve"] == 7800, r["el_reserve"]
        assert r["el_available"] == 4200 and not r["ok"]
        assert any("ElevenLabs" in x for x in r["reasons"])
    finally:
        env.close()


def test_el_enough_ok():
    env = Env(el_remaining=21000, short_stage="final_review")
    try:
        r = lv.check_limits(EST, TODAY)
        assert r["ok"], r["reasons"]
        assert r["el_available"] == 21000 - 7800
    finally:
        env.close()


def test_current_week_shorts_reserved():
    env = Env(el_remaining=21000, short_stage=None)  # bu haftanın short run'ı henüz başlamadı
    try:
        r = lv.check_limits(EST, TODAY)
        assert r["el_current_week"] == 3 * 1300 and r["el_reserve"] == 3900 + 7800
        assert r["short_pending"] and r["gemini_reserve"] == 1.50
    finally:
        env.close()


def test_gemini_short_priority():
    env = Env(spent=0.2, short_stage=None)  # short'lar başlamadı: 0,2 + 1,50 pay + 0,43 > 2
    try:
        r = lv.check_limits(EST, TODAY)
        assert not r["ok"] and any("Gemini" in x for x in r["reasons"])
    finally:
        env.close()
    env = Env(spent=1.3, short_stage="published")  # short'lar bitti: pay 0 -> 1,3 + 0,43 <= 2
    try:
        assert lv.check_limits(EST, TODAY)["ok"]
    finally:
        env.close()


def _long_ctx(env) -> base.RunContext:
    src = env.tmp / "2026-W40"
    src.mkdir()
    (src / "state.json").write_text(json.dumps({"stage": "published", "topic": {"title": "T", "company": "C"},
                                                "plan": {}, "shorts": {}}), encoding="utf-8")
    ctx = base.RunContext(env.tmp / "2026-W40-uzun")
    ctx.state.update(kind="long", source_run="2026-W40", research=lv.source_research(base.RunContext(src)),
                     estimate=EST, dry_run=False)
    ctx.state["stage"] = "long_estimate"
    ctx.save()
    return ctx


def test_approve_cannot_bypass_and_config_unlocks():
    env = Env(spent=1.9, short_stage="published")  # 1,9 + 0,43 > 2
    notified = []
    env._set(long_flow, "notify", lambda *a: notified.append(a))
    env._set(lv, "estimate", lambda research, script=None: EST)
    try:
        ctx = _long_ctx(env)
        long_flow.approve(ctx, spawn_worker=lambda c: (_ for _ in ()).throw(AssertionError("işçi başlamamalı")))
        assert ctx.stage == "long_postponed" and env.api_calls == [] and notified
        # Tekrar onay: koşul değişmedi -> yine ertelenir, yine istek yok.
        long_flow.approve(ctx, spawn_worker=lambda c: None)
        assert ctx.stage == "long_postponed" and env.api_calls == []
        # Yalnızca config değişince devam eder (burada sınırı yükseltiyoruz).
        env._set(limits, "gemini_limit", lambda: 10.0)
        written = []
        env._set(lv, "write_script", lambda c, r: written.append(1) or __import__("src.schemas", fromlist=["x"]).LongVideoScript.model_validate(
            json.loads((ROOT / "tests" / "_long_fixture.json").read_text(encoding="utf-8"))))
        env._set(lv, "verify_new", lambda c, s, r: s)
        long_flow.approve(ctx, spawn_worker=lambda c: None)
        assert written and ctx.stage == "long_voice_review"
    finally:
        env.close()


def test_voice_stage_blocks_without_credit():
    env = Env(el_remaining=6000, short_stage="published")  # 6000 - 7800 < 5280
    env._set(long_flow, "notify", lambda *a: None)
    env._set(lv, "estimate", lambda research, script=None: EST)
    try:
        ctx = _long_ctx(env)
        ctx.state["script"] = json.loads((ROOT / "tests" / "_long_fixture.json").read_text(encoding="utf-8"))
        ctx.state["stage"] = "long_voice_review"
        started = []
        long_flow.approve(ctx, spawn_worker=lambda c: started.append(1))
        assert ctx.stage == "long_postponed" and not started
        assert ctx.state["postponed"]["at"] == "voice"
    finally:
        env.close()


def test_hard_gemini_guard_unchanged():
    env = Env(spent=2.17)
    try:
        try:
            limits.gemini_guard("test")
            raise AssertionError("kilit isteği durdurmalıydı")
        except base.BudgetExceeded:
            pass
    finally:
        env.close()


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"{len(tests)}/{len(tests)} test geçti")
