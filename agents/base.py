"""Agent'ların ortak altyapısı: çalıştırma klasörü, durum, okunabilir log, kullanım/maliyet.

Her haftalık çalıştırma runs/<yıl>-W<hafta>/ altında tutulur:
  state.json   aşama ve agent çıktıları (makine için)
  log.md       her agent'ın kararları ve revizyon geçmişi (insan için)
  usage.json   Gemini/ElevenLabs kullanım kayıtları
  review.md    onay dosyası (agents/review.py yazar)
Konuya/kanala özgü hiçbir şey içermez.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from src import proc

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
CONFIG = json.loads((ROOT / "config" / "pipeline.json").read_text(encoding="utf-8"))
PRICING = json.loads((ROOT / "config" / "pricing.json").read_text(encoding="utf-8"))
MONTHLY_SEARCH_FILE = RUNS_DIR / "search_usage_by_month.json"


class BudgetExceeded(RuntimeError):
    pass


class RunContext:
    """Bir haftalık çalıştırmanın durumu, logu ve kullanım sayacı."""

    def __init__(self, run_dir: Path):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.usage_path = self.dir / "usage.json"
        self.log_path = self.dir / "log.md"
        self.state: dict = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
        self.usage: list[dict] = json.loads(self.usage_path.read_text(encoding="utf-8")) if self.usage_path.exists() else []
        self.current_agent = "pipeline"
        self.budget_extra = float(self.state.get("budget_extra_usd", 0.0))

    # ------------------------------------------------------------------ durum
    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        self.usage_path.write_text(json.dumps(self.usage, ensure_ascii=False, indent=1), encoding="utf-8")

    @property
    def stage(self) -> str:
        return self.state.get("stage", "new")

    def set_stage(self, stage: str) -> None:
        self.state["stage"] = stage
        self.log("pipeline", f"Aşama: **{stage}**")
        self.save()

    # ------------------------------------------------------------------ log
    def log(self, agent: str, message: str, detail: str | None = None) -> None:
        """log.md'ye zaman damgalı, okunabilir bir satır (ve isteğe bağlı detay bloğu) ekler."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"- `{stamp}` **{agent}** — {message}\n"
        if detail:
            line += "\n  ```\n" + "\n".join("  " + l for l in detail.strip().splitlines()) + "\n  ```\n"
        if not self.log_path.exists():
            self.log_path.write_text(f"# Pipeline log — {self.dir.name}\n\n", encoding="utf-8")
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        print(f"[{agent}] {message}")

    # ------------------------------------------------------------------ kullanım
    def record_gemini(self, response, purpose: str) -> None:
        um = getattr(response, "usage_metadata", None)
        prompt = (getattr(um, "prompt_token_count", 0) or 0) + (getattr(um, "tool_use_prompt_token_count", 0) or 0)
        output = (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        searches = 0
        for cand in getattr(response, "candidates", None) or []:
            gm = getattr(cand, "grounding_metadata", None)
            if gm and gm.web_search_queries:
                searches += len(gm.web_search_queries)
        self.usage.append({
            "service": "gemini", "agent": self.current_agent, "purpose": purpose,
            "input_tokens": prompt, "output_tokens": output, "searches": searches,
            "at": datetime.now().isoformat(timespec="seconds"),
        })
        if searches:
            _add_monthly_searches(searches)
        self.save()

    def record_tts(self, chars: int, model_id: str) -> None:
        self.usage.append({
            "service": "elevenlabs", "agent": self.current_agent, "purpose": model_id,
            "chars": chars, "at": datetime.now().isoformat(timespec="seconds"),
        })
        self.save()

    def cost_summary(self) -> dict:
        g = PRICING["gemini"]
        e = PRICING["elevenlabs"]
        gem = [u for u in self.usage if u["service"] == "gemini"]
        tts = [u for u in self.usage if u["service"] == "elevenlabs"]
        inp = sum(u["input_tokens"] for u in gem)
        out = sum(u["output_tokens"] for u in gem)
        searches = sum(u["searches"] for u in gem)
        chars = sum(u["chars"] for u in tts)
        # Arama: ayın ücretsiz kotası aşıldıysa ücretlendirilir.
        month_total = _monthly_searches()
        billable = max(0, min(searches, month_total - g["search_free_per_month"]))
        gemini_usd = inp / 1e6 * g["input_per_million"] + out / 1e6 * g["output_per_million"]
        search_usd = billable / 1000 * g["search_per_thousand"]
        tts_usd = chars / 1000 * e["per_thousand_chars"]
        by_agent: dict[str, float] = {}
        for u in gem:
            by_agent[u["agent"]] = by_agent.get(u["agent"], 0) + (
                u["input_tokens"] / 1e6 * g["input_per_million"] + u["output_tokens"] / 1e6 * g["output_per_million"])
        for u in tts:
            by_agent[u["agent"]] = by_agent.get(u["agent"], 0) + u["chars"] / 1000 * e["per_thousand_chars"]
        return {
            "gemini_requests": len(gem), "input_tokens": inp, "output_tokens": out,
            "searches": searches, "searches_this_month": month_total, "billable_searches": billable,
            "tts_requests": len(tts), "tts_chars": chars,
            "gemini_usd": gemini_usd, "search_usd": search_usd, "tts_usd": tts_usd,
            "total_usd": gemini_usd + search_usd + tts_usd, "by_agent": by_agent,
        }

    def cost_report(self) -> str:
        c = self.cost_summary()
        lines = [
            "| Kalem | Kullanım | Tahmini maliyet |",
            "|---|---|---|",
            f"| Gemini | {c['gemini_requests']} istek, {c['input_tokens']:,} girdi + {c['output_tokens']:,} çıktı token | ${c['gemini_usd']:.4f} |",
            f"| Google Search grounding | {c['searches']} arama (bu ay toplam {c['searches_this_month']}, "
            f"ücretli {c['billable_searches']}) | ${c['search_usd']:.4f} |",
            f"| ElevenLabs | {c['tts_requests']} seslendirme, {c['tts_chars']:,} karakter | ${c['tts_usd']:.4f} |",
            f"| **Toplam** | | **${c['total_usd']:.4f}** |",
        ]
        if c["by_agent"]:
            lines += ["", "Agent bazında: " + ", ".join(f"{k} ${v:.4f}" for k, v in sorted(c["by_agent"].items()))]
        return "\n".join(lines)

    def check_budget(self) -> None:
        limit = float(CONFIG.get("budget_usd_per_week", 2.0)) + self.budget_extra
        total = self.cost_summary()["total_usd"]
        if total > limit:
            raise BudgetExceeded(f"Tahmini maliyet ${total:.2f}, haftalık sınır ${limit:.2f}")


def _add_monthly_searches(n: int) -> None:
    data = json.loads(MONTHLY_SEARCH_FILE.read_text(encoding="utf-8")) if MONTHLY_SEARCH_FILE.exists() else {}
    key = datetime.now().strftime("%Y-%m")
    data[key] = data.get(key, 0) + n
    MONTHLY_SEARCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    MONTHLY_SEARCH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _monthly_searches() -> int:
    if not MONTHLY_SEARCH_FILE.exists():
        return 0
    return json.loads(MONTHLY_SEARCH_FILE.read_text(encoding="utf-8")).get(datetime.now().strftime("%Y-%m"), 0)


def attach_usage_hooks(ctx: RunContext) -> None:
    """Mevcut modüllerin (script_writer, tts) çağrılarını bu çalıştırmanın sayacına bağlar."""
    from src import script_writer, tts

    script_writer.USAGE_HOOK = ctx.record_gemini
    tts.USAGE_HOOK = ctx.record_tts


def model_for(kind: str) -> str:
    """config/pipeline.json -> models.<kind>; boşsa GEMINI_MODEL."""
    from src import script_writer

    return (CONFIG.get("models", {}).get(kind) or "").strip() or script_writer.MODEL


def notify(title: str, message: str) -> None:
    """Windows bildirimi (en iyi çaba; başarısız olursa sessizce geçer)."""
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$x = $t.GetElementsByTagName('text');"
        f"$x.Item(0).AppendChild($t.CreateTextNode({_ps_str(title)})) > $null;"
        f"$x.Item(1).AppendChild($t.CreateTextNode({_ps_str(message)})) > $null;"
        "$n = [Windows.UI.Notifications.ToastNotification]::new($t);"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($n)"
    )
    try:
        proc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass


def _ps_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"
