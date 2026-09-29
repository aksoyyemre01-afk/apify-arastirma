"""Sert harcama kilitleri: haftalık Gemini bütçesi ve aylık ElevenLabs karakter limiti.

- Gemini: config/pipeline.json -> gemini_budget_usd_per_week. Harcama, o ISO haftasındaki
  TÜM çalıştırmaların (runs/*/usage.json) Gemini + Google Search maliyetidir. Her Gemini
  isteğinden ÖNCE kontrol edilir: harcanan + istek payı (gemini_reserve_usd_per_request)
  limiti aşacaksa istek gönderilmez. Onayla aşılamaz; yalnızca config'deki limit
  değiştirilerek devam edilebilir.
- ElevenLabs: config/pipeline.json -> elevenlabs. Aylık sınır = plan kredisi x oran (ör.
  Starter 30.000 x %90). Kalan kredi her üretimden ve her seslendirmeden ÖNCE ElevenLabs
  API'sinden okunur; yetmiyorsa ya da okunamıyorsa ses üretilmez.
"""

import json
import math
from datetime import datetime

from .base import CONFIG, PRICING, RUNS_DIR, BudgetExceeded, _monthly_searches


class QuotaExceeded(BudgetExceeded):
    """ElevenLabs kredisi yetersiz ya da kontrol edilemedi."""


# ---------------------------------------------------------------------------- Gemini

def gemini_limit() -> float:
    return float(CONFIG.get("gemini_budget_usd_per_week", 2.0))


def _week_key(ts: str) -> tuple[int, int]:
    return tuple(datetime.fromisoformat(ts).isocalendar()[:2])


def weekly_gemini_usd(now: datetime | None = None) -> float:
    """Bu ISO haftasında tüm çalıştırmaların Gemini (token + ücretli arama) tahmini maliyeti."""
    week = tuple((now or datetime.now()).isocalendar()[:2])
    g = PRICING["gemini"]
    inp = out = searches = 0
    for path in RUNS_DIR.glob("*/usage.json"):
        for u in json.loads(path.read_text(encoding="utf-8")):
            if u.get("service") == "gemini" and _week_key(u["at"]) == week:
                inp += u["input_tokens"]
                out += u["output_tokens"]
                searches += u.get("searches", 0)
    billable = max(0, min(searches, _monthly_searches() - g["search_free_per_month"]))
    return inp / 1e6 * g["input_per_million"] + out / 1e6 * g["output_per_million"] + billable / 1000 * g["search_per_thousand"]


def gemini_guard(purpose: str = "") -> None:
    """Gemini isteğinden önce çağrılır; bütçe aşılacaksa BudgetExceeded fırlatır (istek gitmez)."""
    spent, limit = weekly_gemini_usd(), gemini_limit()
    reserve = float(CONFIG.get("gemini_reserve_usd_per_request", 0.05))
    if spent + reserve > limit:
        raise BudgetExceeded(
            f"Haftalık Gemini bütçesi: ${spent:.2f} harcandı, sınır ${limit:.2f} (istek payı ${reserve:.2f}); "
            f"'{purpose}' isteği gönderilmedi. Devam için config/pipeline.json -> gemini_budget_usd_per_week "
            f"değerini artırın.")


# ---------------------------------------------------------------------------- ElevenLabs

def _el_cfg() -> dict:
    return CONFIG.get("elevenlabs", {})


def elevenlabs_cap() -> int:
    c = _el_cfg()
    return math.floor(int(c.get("plan_monthly_credits", 30000)) * float(c.get("monthly_limit_ratio", 0.9)))


def elevenlabs_status() -> dict:
    """ElevenLabs aboneliğinden kullanım; bizim sınırımızla birlikte. Okunamazsa QuotaExceeded."""
    from src import tts

    try:
        client = tts._get_client()
        sub = client.user.subscription.get()
    except Exception as e:  # noqa: BLE001 - ağ/izin/anahtar hatası: güvenli tarafta kal
        detail = str(getattr(e, "body", "") or e)
        hint = (" API anahtarına ElevenLabs panelinde 'User -> Read' (user_read) izni verin."
                if "user_read" in detail or "missing_permissions" in detail else "")
        raise QuotaExceeded(f"ElevenLabs kalan kredisi okunamadı, ses üretilmedi.{hint} ({detail[:200]})") from e
    used, plan_limit, cap = int(sub.character_count), int(sub.character_limit), elevenlabs_cap()
    reset = getattr(sub, "next_character_count_reset_unix", None)
    return {
        "tier": getattr(sub, "tier", ""), "used": used, "plan_limit": plan_limit, "cap": cap,
        "remaining": max(0, min(cap, plan_limit) - used),
        "reset": datetime.fromtimestamp(reset).strftime("%Y-%m-%d") if reset else "",
    }


def tts_guard(chars: int, what: str = "seslendirme") -> dict:
    """Seslendirmeden önce: kalan kredi `chars`'a yetmiyorsa ya da okunamıyorsa QuotaExceeded."""
    st = elevenlabs_status()
    if chars > st["remaining"]:
        raise QuotaExceeded(
            f"ElevenLabs: {what} için ~{chars:,} karakter gerekiyor, aylık sınır içinde kalan {st['remaining']:,} "
            f"(kullanılan {st['used']:,} / sınır {st['cap']:,}, plan {st['plan_limit']:,}; yenilenme {st['reset']}). "
            f"Ses üretilmedi.")
    return st


def estimated_chars_per_short() -> int:
    return int(_el_cfg().get("estimated_chars_per_short", 1300))


# ---------------------------------------------------------------------------- rapor

def balance_report() -> str:
    spent, limit = weekly_gemini_usd(), gemini_limit()
    lines = [
        "| Servis | Bu dönem kullanılan | Sınır | Kalan |",
        "|---|---|---|---|",
        f"| Gemini (bu hafta, tüm çalıştırmalar; tahmini) | ${spent:.2f} | ${limit:.2f} | **${max(0.0, limit - spent):.2f}** |",
    ]
    try:
        st = elevenlabs_status()
        lines.append(f"| ElevenLabs ({st['tier']}, yenilenme {st['reset']}) | {st['used']:,} karakter | "
                     f"{st['cap']:,} (plan {st['plan_limit']:,}) | **{st['remaining']:,} karakter** |")
        expected = str(_el_cfg().get("plan", "")).lower()
        if expected and expected not in str(st["tier"]).lower():
            lines += ["", f"> ⚠️ Hesabın planı '{st['tier']}', config'de '{expected}' yazıyor; "
                          f"`elevenlabs.plan_monthly_credits` değerini kontrol edin."]
    except QuotaExceeded as e:
        lines.append(f"| ElevenLabs | ? | {elevenlabs_cap():,} | **okunamadı** — {e} |")
    lines += ["", "_Gemini'nin bakiye API'si yoktur; kalan, bu projenin kayıtlı kullanımından hesaplanır. "
                  "ElevenLabs değerleri API'den anlık okunur._"]
    return "\n".join(lines)


def attach_guards() -> None:
    """src katmanındaki API çağrılarının önüne kilitleri takar."""
    from src import script_writer, tts

    script_writer.PRE_REQUEST_HOOK = gemini_guard
    tts.PRE_REQUEST_HOOK = lambda text: tts_guard(len(text))
