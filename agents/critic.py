"""Eleştirmen (QA): render edilen videoyu RULES.md'ye göre puanlar ve geçmezse gerekçesiyle
ilgili agent'a geri gönderir.

İki katman:
1) Kodla ölçülenler (kesin, istek harcamaz): seslendirme süresi 30-45 sn, gizemli markanın
   söylenme anı <= 4,5 sn, hiçbir sahne > 3 sn, ses -14 LUFS, teslim biçimi (H.264 yuv420p,
   AAC 48 kHz stereo, faststart), altyazı var.
2) Gemini görsel modeli: contact sheet'ler + RULES.md + sahne planı; her kural için 1-5
   puan, gerekçe, sorunlu sahneler ve düzeltmeyi yapacak agent.
Geçme şartı (config/pipeline.json -> qa): tüm ölçümler geçer, hiçbir kural
min_rule_score'un altında değil ve ortalama >= min_average_score.
Kod kaynaklı sorunlar ("kod") hiçbir agent'a gönderilmez: tekrar render aynı sonucu verir;
doğrudan rapora yazılır.
"""

import json
import re
import struct
import subprocess
from pathlib import Path
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from src import proc
from src import script_writer
from src.scene_planner import _find_spoken, measure_lufs

from . import scriptwriter
from .base import CONFIG, ROOT, RunContext, model_for

AGENT = "Eleştirmen"
# Görsel/metin olarak değerlendirilebilen kurallar. 8 (müzik/efekt) sesle ilgilidir ve
# kodla ölçülür; 9 (haftalık plan) Araştırmacı düzeyinde kontrol edilir.
SCORED_RULES = (1, 2, 3, 4, 5, 6, 7, 10)
# Bir kurala 5 verilebilmesi için evidence alanında en az bu kadar somut açıklama gerekir.
MIN_EVIDENCE_CHARS = 25
Target = Literal["senarist", "dogrulayici", "yonetmen", "kod", "yok"]


class RuleScore(BaseModel):
    rule: int = Field(description="RULES.md kural numarası")
    evidence: str = Field(description="SOMUT kanıt: hangi sayfa/kare/sahnede tam olarak ne görülüyor (ekrandaki "
                                      "metin/rakam/logo ve o sahnenin cümlesi). Kanıtsız 5 verilemez.")
    score: int = Field(description="1 (çok kötü) - 5 (kusursuz)")
    reason: str = Field(description="Puanın gerekçesi")
    scenes: list[int] = Field(default_factory=list, description="Sorunlu sahne numaraları (1'den başlar)")
    target: Target = Field(description="Düzeltmeyi kim yapmalı: senarist (metin/sahne seçimi/alanlar), "
                                       "dogrulayici (olgu şüphesi), yonetmen (ses/zamanlama), kod (render/yerleşim "
                                       "hatası, script değişikliğiyle düzelmez), yok (sorun yok)")
    fix: str = Field(default="", description="Somut düzeltme önerisi")


class Violation(BaseModel):
    scene: int = Field(description="Sahne numarası (tüm videoyu etkiliyorsa 0)")
    rule: int = Field(description="İhlal edilen RULES.md kural numarası")
    what: str = Field(description="Ne yanlış: ekranda ne görülüyor, olması gereken ne (ör. 'ekranda 31, cümlede 7')")


class Critique(BaseModel):
    violations: list[Violation] = Field(description="Kontrol listesinde bulunan HER açık ihlal ayrı bir madde; aynı "
                                                    "kuraldan birden fazla ihlal olabilir. İhlal yoksa boş liste.")
    scores: list[RuleScore]
    improvements: list[str] = Field(description="EN AZ 2 somut iyileştirme önerisi (sahne numarasıyla); video "
                                                "iyi olsa bile daha iyi yapılabilecek şeyler")
    summary: str = Field(description="2-3 cümlelik genel değerlendirme")


CRITIC_PROMPT = """Sen bir YouTube Shorts kalite kontrol editörüsün. Aşağıdaki kurallara (RULES.md)
göre bu videoyu değerlendir. Görseller videonun contact sheet'leridir: her sayfada en fazla 8
kare, soldan sağa ve yukarıdan aşağı sırayla. Her sahneden TAM OLARAK bir kare vardır ve sıra
birebir aynıdır: videodaki k. kare = k. sahne (son kare kapanış kartı). Kareleri sahnelerle
eşleştirirken sayıyı kaydırma. Kareler sırasıyla şunlardır:
{frames}
Sahne kareleri, o sahnenin giriş animasyonları (sayaç, vurgu şeridi, grafik çizimi) BİTTİKTEN
sonraki halidir; ekrandaki değerleri son hal olarak değerlendir.

Puan vermeden önce HER sahne karesi için şu kontrol listesini uygula (yukarıda her karenin
yanında o sahnede söylenen cümle yazıyor):
1. Ekrandaki her rakam/yıl/tutar, o sahnenin cümlesindeki rakamla AYNI mı? Farklıysa (ör.
   cümlede "7 milyar", ekranda "31") bu kural 1'in açık ihlalidir.
2. Ekrandaki logo/marka, o sahnenin cümlesinde geçen marka ya da videonun konusu olan marka mı?
   Cümleyle ilgisiz bir markanın logosu kural 1'in açık ihlalidir.
3. Altyazıda kelimeler arasında boşluk var mı, okunaklı mı? Bitişik/birleşik kelimeler kural
   6'nın açık ihlalidir.
4. Sahne planındaki süreler: 3 saniyeyi geçen her sahne kural 5'in açık ihlalidir.
5. Kırpık/taşan yazı, çakışan öğeler, bozuk ya da yarım görünen logo var mı?
Bulduğun HER açık ihlali `violations` listesine AYRI bir madde olarak yaz (sahne numarası,
kural, ne görüldüğü). Aynı kuraldan birden fazla ihlal varsa (ör. bir sahnede yanlış logo,
başka bir sahnede yanlış rakam) hepsini ayrı ayrı yaz; birini yazıp diğerini atlama.

Puanlama cetveli (katı uygula):
- 5: kural her karede kusursuz uygulanmış VE bunu evidence alanında somut olarak gösterdin.
  Somut kanıt yazamıyorsan en fazla 4 ver.
- 4: küçük, izleyicinin fark etmeyeceği bir kusur.
- 3: fark edilen ama anlamı bozmayan kusur.
- 1-2: kuralın en az bir AÇIK ihlali (yukarıdaki listedeki durumlar). Tek bir açık ihlal
  bile o kurala en fazla 2 puan demektir.
Ayrıca `improvements` alanına video ne kadar iyi olursa olsun EN AZ 2 somut iyileştirme
önerisi (sahne numarasıyla) yaz.

Sahne planı (başlangıç-bitiş saniyesi, tip, seslendirilen cümle):
{plan}

Seslendirme metni: {narration}
Ekranda kapanış metni: {cta}

Yalnızca şu kuralları puanla: {rules}. Her kural için 1-5 puan ver (5 = kusursuz, 3 =
kabul edilebilir ama belirgin kusur var, 1-2 = kural açıkça ihlal ediliyor). Gerekçen,
karelerde gördüğün SOMUT şeye dayansın; göremediğin şeyi varsayma. Sorunlu sahne
numaralarını ve düzeltmeyi kimin yapması gerektiğini (target) yaz. Kırpık/taşan yazı,
çakışan öğeler, bozuk logo gibi yerleşim hataları "kod"dur.

RULES.md:
{rules_md}"""


# ---------------------------------------------------------------------------- ölçümler

def _probe(video: Path) -> dict:
    out = proc.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,pix_fmt,sample_rate,channels", "-of", "json", str(video)],
                         capture_output=True, text=True).stdout
    return json.loads(out or "{}")


def _moov_first(video: Path) -> bool:
    with video.open("rb") as f:
        pos, order = 0, []
        while len(order) < 8:
            f.seek(pos)
            h = f.read(8)
            if len(h) < 8:
                break
            size, typ = struct.unpack(">I4s", h)
            order.append(typ)
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0]
            if size == 0:
                break
            pos += size
    return b"moov" in order and b"mdat" in order and order.index(b"moov") < order.index(b"mdat")


def measure(ctx: RunContext, index: int) -> list[dict]:
    return measure_dir(scriptwriter.short_dir(ctx, index), scriptwriter.load(ctx, index))


def measure_dir(d: Path, script) -> list[dict]:
    from src import script_writer as sw

    timings = json.loads((d / "word_timings.json").read_text(encoding="utf-8"))
    props = json.loads((d / "assets" / "props.json").read_text(encoding="utf-8"))
    video = d / "video.mp4"
    checks = []

    def check(name, ok, value, target):
        checks.append({"name": name, "ok": bool(ok), "value": value, "target": "yok" if ok else target})

    dur = timings[-1]["end"]
    check("Seslendirme süresi 30-45 sn", sw.MIN_SECONDS <= dur <= sw.MAX_SECONDS, f"{dur:.1f} sn", "senarist")
    if script.hook_type == "mystery":
        at = _find_spoken(script.mystery_brand or script.main_brand, timings)
        check("Gizemli marka <= 4,5 sn'de söyleniyor", at is not None and at <= sw.MYSTERY_BRAND_DEADLINE,
              f"{at:.2f} sn" if at is not None else "söylenmiyor", "senarist")
    longest = max(s["durationInFrames"] for s in props["scenes"]) / props["fps"]
    check("Hiçbir sahne 3 sn'yi geçmiyor", longest <= 3.05, f"en uzun {longest:.2f} sn", "kod")
    lufs = measure_lufs(video)
    check("Ses -14 LUFS (±1)", lufs is not None and abs(lufs + 14) <= 1, f"{lufs} LUFS", "kod")
    streams = {s["codec_type"]: s for s in _probe(video).get("streams", [])}
    v, a = streams.get("video", {}), streams.get("audio", {})
    fmt_ok = (v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p" and a.get("codec_name") == "aac"
              and a.get("sample_rate") == "48000" and a.get("channels") == 2 and _moov_first(video))
    check("Teslim biçimi (H.264 yuv420p, AAC 48 kHz stereo, faststart)", fmt_ok,
          f"{v.get('codec_name')}/{v.get('pix_fmt')}, {a.get('codec_name')} {a.get('sample_rate')} Hz {a.get('channels')} kanal",
          "kod")
    check("Altyazı var", len(props.get("captions", [])) > 0, f"{len(props.get('captions', []))} sayfa", "kod")
    return checks


# ---------------------------------------------------------------------------- görsel puanlama

def _plan_text(props: dict, script) -> str:
    fps = props["fps"]
    lines = []
    for i, s in enumerate(props["scenes"], 1):
        start, end = s["from"] / fps, (s["from"] + s["durationInFrames"]) / fps
        lines.append(f"{i}. {start:5.1f}-{end:5.1f} sn [{s['type']}]")
    lines.append("Script cümleleri: " + " | ".join(f"{i}. {sc.narration}" for i, sc in enumerate(script.scenes, 1)))
    return "\n".join(lines)


def score(ctx: RunContext, index: int) -> Critique:
    return score_dir(scriptwriter.short_dir(ctx, index), scriptwriter.load(ctx, index))


def score_dir(d: Path, script) -> Critique:
    """Bir video klasörünü (props.json + kareler/) puanlar; çalıştırma bağlamı gerektirmez
    (kalibrasyon testi de bunu kullanır)."""
    props = json.loads((d / "assets" / "props.json").read_text(encoding="utf-8"))
    sheets = sorted((d / "kareler").glob("sheet_*.png"), key=lambda p: int(p.stem.split("_")[1]))
    per = int(CONFIG.get("qa", {}).get("frames_per_sheet", 8))
    frame_list = json.loads((d / "kareler" / "kareler.json").read_text(encoding="utf-8"))
    timings = json.loads((d / "word_timings.json").read_text(encoding="utf-8"))
    fps = props["fps"]

    def spoken(label: str) -> str:
        """Kare bir sahneye aitse, o sahne ekrandayken söylenen kelimeler (rakam/logo kontrolü için)."""
        m = re.match(r"sahne (\d+)", label)
        if not m:
            return ""
        s = props["scenes"][int(m.group(1)) - 1]
        a, b = s["from"] / fps, (s["from"] + s["durationInFrames"]) / fps
        words = " ".join(w["word"] for w in timings if a - 0.1 <= w["start"] < b)
        return f" — bu sahnede söylenen: \"{words}\"" if words else ""

    frames = "\n".join(f"- sayfa {n // per + 1}, kare {n % per + 1}: {f['t']:.1f} sn — {f['label']}{spoken(f['label'])}"
                       for n, f in enumerate(frame_list))
    prompt = CRITIC_PROMPT.format(
        frames=frames,
        plan=_plan_text(props, script), narration=script.narration_full, cta=script.cta,
        rules=", ".join(map(str, SCORED_RULES)), rules_md=(ROOT / "RULES.md").read_text(encoding="utf-8"),
    )
    parts = [types.Part.from_bytes(data=p.read_bytes(), mime_type="image/png") for p in sheets] + [prompt]
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=Critique)
    response = script_writer.generate_raw(parts, cfg, purpose="QA görsel puanlama", model=model_for("vision"))
    critique = Critique.model_validate_json(response.text)
    critique.scores = [s for s in critique.scores if s.rule in SCORED_RULES]
    # Kod düzeyinde uygulanan kalibrasyon kuralı: somut kanıtı olmayan 5 verilemez.
    for s in critique.scores:
        if s.score >= 5 and len(s.evidence.strip()) < MIN_EVIDENCE_CHARS:
            s.score = 4
            s.reason += " (kanıt yetersiz olduğu için 5 -> 4)"
    if len(critique.improvements) < 2:
        critique.summary += f" [UYARI: yalnızca {len(critique.improvements)} iyileştirme önerisi yazıldı]"
    return critique


# ---------------------------------------------------------------------------- karar

def review(ctx: RunContext, index: int, round_no: int) -> dict:
    """Ölçüm + puanlama; geçti/kaldı kararı ve agent'lara gidecek aksiyonlar."""
    ctx.current_agent = AGENT
    day = ctx.state["plan"]["days"][index]
    qa = CONFIG.get("qa", {})
    min_rule, min_avg = float(qa.get("min_rule_score", 3)), float(qa.get("min_average_score", 4.0))
    checks = measure(ctx, index)
    critique = score(ctx, index)
    scores = [s.score for s in critique.scores]
    avg = sum(scores) / len(scores) if scores else 0
    passed = all(c["ok"] for c in checks) and scores and min(scores) >= min_rule and avg >= min_avg

    # Aksiyonlar: başarısız ölçümler + eşiğin altındaki ya da ortalamayı düşüren (<=3) kurallar.
    weak = [s for s in critique.scores if s.score < min_rule or (avg < min_avg and s.score <= 3)]
    actions: dict[str, list[str]] = {}
    for c in checks:
        if not c["ok"]:
            actions.setdefault(c["target"], []).append(f"Ölçüm başarısız: {c['name']} ({c['value']}).")
    for s in weak:
        if s.target == "yok":
            continue
        where = f" Sahneler: {', '.join(map(str, s.scenes))}." if s.scenes else ""
        actions.setdefault(s.target, []).append(f"Kural {s.rule} (puan {s.score}): {s.reason}{where} Öneri: {s.fix}".strip())
    # Her somut ihlal, kuralının hedef agent'ına sahne numarasıyla ayrıca iletilir.
    target_of = {s.rule: s.target for s in critique.scores}
    for v in critique.violations:
        t = target_of.get(v.rule, "senarist")
        if t != "yok":
            actions.setdefault(t, []).append(f"İhlal - sahne {v.scene or 'genel'}, kural {v.rule}: {v.what}")

    result = {
        "round": round_no, "passed": bool(passed), "average": round(avg, 2), "min": min(scores) if scores else 0,
        "checks": checks, "scores": [s.model_dump() for s in critique.scores], "summary": critique.summary,
        "improvements": critique.improvements,
        "violations": [v.model_dump() for v in critique.violations],
        "actions": actions,
    }
    record = ctx.state["shorts"][str(index)]
    record.setdefault("qa_rounds", []).append(result)
    ctx.save()
    status = "GEÇTİ" if passed else "KALDI"
    ctx.log(AGENT, f"{day} tur {round_no}: **{status}** (ortalama {avg:.2f}, en düşük {result['min']}; "
                   f"ölçümler {sum(c['ok'] for c in checks)}/{len(checks)})",
            "\n".join([f"[{'OK' if c['ok'] else 'X'}] {c['name']}: {c['value']}" for c in checks]
                      + [f"Kural {s.rule}: {s.score}/5 - {s.reason}" for s in critique.scores]
                      + [f"İhlal: sahne {v.scene}, kural {v.rule}: {v.what}" for v in critique.violations]
                      + [f"Öneri: {x}" for x in critique.improvements]
                      + [f"-> {t}: {len(v)} madde" for t, v in actions.items()]))
    return result


def human_feedback_actions(text: str) -> dict[str, list[str]]:
    """İnsan editörün red gerekçesini Senarist'e iletilecek bir madde olarak hazırlar.
    (Metin, sahne seçimi, rakam ve kapanış gibi çoğu geri bildirim script düzeyindedir.)"""
    return {"senarist": [f"İnsan editör geri bildirimi (öncelikli): {text.strip()}"]}


def is_code_only(actions: dict[str, list[str]]) -> bool:
    return bool(actions) and set(actions) <= {"kod"}


def summarize_actions(actions: dict) -> str:
    return "; ".join(f"{k}: {len(v)}" for k, v in actions.items()) or "yok"
