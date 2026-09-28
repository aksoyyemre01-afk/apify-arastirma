"""Araştırmacı: haftanın konusunu seçer ve 3 short'a (Pzt/Çar/Cum) + uzun video taslağına böler.

Konu, mevcut src/research.py'den (kürasyonlu vaka bankası + haber kaynağı) kullanılmamış
olanlar arasından seçilir; reddedilen konular aynı hafta tekrar önerilmez. Bölümleme tek
bir Gemini isteğiyle yapılır: her short aynı hikâyenin farklı bir evresini anlatır ve
olaylar bölümler arasında tekrar etmez.

Plan onaya sunulmadan önce Doğrulayıcı'dan geçer (verifier.verify_plan); sorunlu iddialar
revise_plan() ile düzeltilir. Konu reddi --keep-topic ile yapılırsa konu korunur ve plan,
gerekçe dikkate alınarak yeniden üretilir.
"""

import difflib
import json
import re

from google.genai import types
from pydantic import BaseModel, Field

from src import research, script_writer, state

from .base import RunContext

AGENT = "Araştırmacı"
DAYS = [script_writer.WEEKLY_PARTS[i]["day_label"] for i in (1, 2, 3)]


class PartPlan(BaseModel):
    focus_title: str = Field(description="Bölümün kısa başlığı (ör. 'Yükseliş', 'Kritik karar', 'Çöküş')")
    focus: str = Field(description="Bu short'un anlatacağı evre, 1-2 cümle")
    key_events: list[str] = Field(description="Bu bölümde anlatılacak 3-5 somut olay/rakam/tarih; diğer bölümlerde TEKRAR ETMEZ")
    cliffhanger: str = Field(description="Bölümün kapanışında izleyiciyi sonraki bölüme bağlayacak merak kancası")


class WeekPlan(BaseModel):
    topic_summary: str = Field(description="Konunun 2-3 cümlelik özeti")
    parts: list[PartPlan] = Field(description="TAM OLARAK 3 bölüm, kronolojik: 1) giriş/yükseliş 2) zirve/kritik karar 3) çöküş/sonuç")
    long_video_outline: list[str] = Field(description="Hafta sonu uzun videosu için 4-6 maddelik bölüm taslağı (ikinci aşamada kullanılacak)")


PLAN_PROMPT = """Sen bir YouTube Shorts serisi için araştırma editörüsün.

Konu: {title}
Şirket: {company}
Olayın özeti: {angle}
{rejection}
Bu konuyu, haftanın üç gününde ({days}) yayınlanacak 3 short'a böl. Kurallar:
- Her short aynı hikâyenin FARKLI bir evresini anlatır: 1) giriş/yükseliş, 2) zirve ve
  kritik karar, 3) çöküş/sonuç ve ders. Kronolojik sıra korunur.
- Her bölümün key_events listesi o bölüme özgü 3-5 SOMUT olay, rakam ya da tarihtir;
  aynı olay/rakam iki bölümde geçmez.
- Yalnızca gerçek, kamuya açık ve doğrulanabilir olgulara dayan; emin olmadığın rakamı yazma.
- 1. ve 2. bölümün cliffhanger'ı izleyiciyi bir sonraki bölüme bağlar; 3. bölümünki seriyi
  bir dersle kapatır.
- Ayrıca hafta sonu uzun videosu için kısa bir bölüm taslağı yaz.
- Metinler Türkçe."""

REVISE_PLAN_PROMPT = """Aşağıdaki haftalık video planında (JSON) şu sorunlar tespit edildi:

{feedback}

Planı bu maddelere göre düzelt: yanlış olguları doğrusuyla değiştir, doğrulanamayan iddiaları
çıkar ya da doğrulanabilir genel bir ifadeye çevir. Sorunsuz kısımları olduğu gibi bırak;
bölüm yapısı (3 bölüm, kronolojik, olaylar bölümler arasında tekrar etmez) korunur. Her
bölümün key_events listesi yine 3-5 somut ve doğru olay içermeli. Metinler Türkçe.

Konu: {title} ({company})

Plan:
{plan}"""


def _generate(ctx: RunContext, prompt: str, purpose: str) -> None:
    """Planı üretir, 3 bölüm ve örtüşme kontrolünü yapar, ctx.state['plan']'a yazar."""
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=WeekPlan)
    plan = WeekPlan.model_validate_json(script_writer.generate_raw(prompt, config, purpose=purpose).text)
    if len(plan.parts) != 3:
        raise RuntimeError(f"Plan 3 bölüm yerine {len(plan.parts)} bölüm içeriyor.")
    for a, b, ratio in _overlaps(plan):
        ctx.log(AGENT, f"UYARI: {DAYS[a]} ve {DAYS[b]} bölümlerinin olayları %{ratio * 100:.0f} örtüşüyor.")
    ctx.state["plan"] = {**plan.model_dump(), "days": DAYS}


def _plan_listing(plan: dict) -> str:
    return "\n".join(f"{DAYS[i]} - {p['focus_title']}: {p['focus']} | olaylar: {'; '.join(p['key_events'])}"
                     for i, p in enumerate(plan["parts"]))


def plan_week(ctx: RunContext, topic_id: str | None = None, keep_topic: bool = False) -> None:
    """keep_topic: mevcut konuyu koruyup planı ctx.state['plan_feedback'] dikkate alınarak yeniden üretir."""
    ctx.current_agent = AGENT
    rejected = set(ctx.state.get("rejected_topic_ids", []))
    used = state.get_used_ids() | rejected
    if keep_topic:
        topic = ctx.state["topic"]
    elif topic_id:
        bank = {t["id"]: t for t in research.load_bank()}
        if topic_id not in bank:
            raise SystemExit(f"Konu bankasında '{topic_id}' yok.")
        topic = {**bank[topic_id], "reference": "", "source": "evergreen"}
    else:
        topics = research.get_topics(1, used)
        if not topics:
            raise SystemExit("Kullanılmamış konu bulunamadı.")
        topic = topics[0]
    if keep_topic:
        ctx.log(AGENT, f"Konu korunuyor, plan yeniden üretiliyor: **{topic['title']}**")
    else:
        ctx.log(AGENT, f"Konu seçildi: **{topic['title']}** ({topic.get('company', '')}, kaynak: {topic.get('source', '')})")
        ctx.state["plan_feedback"] = []  # önceki konunun plan düzeltmeleri yeni konuya taşınmaz

    rejection = ""
    reasons = ctx.state.get("rejection_reasons", [])
    if reasons and not keep_topic:
        rejection = "\nÖnceki konu önerileri şu gerekçelerle reddedildi; bunları dikkate al:\n" + "\n".join(f"- {r}" for r in reasons) + "\n"
    feedback = ctx.state.get("plan_feedback", [])
    if feedback:
        rejection += ("\nBu konunun önceki planı şu gerekçelerle reddedildi; aynı hataları yapma, bu "
                      "düzeltmeleri esas al:\n" + "\n".join(f"- {r}" for r in feedback) + "\n")
    prompt = PLAN_PROMPT.format(
        title=topic["title"], company=topic.get("company", ""), angle=topic.get("angle", ""),
        rejection=rejection, days=", ".join(DAYS),
    )
    _generate(ctx, prompt, purpose="hafta planı")
    ctx.state["topic"] = topic
    ctx.state["plan_revisions"] = []
    ctx.state.pop("plan_verify", None)
    ctx.log(AGENT, "Hafta planı hazır:", _plan_listing(ctx.state["plan"]))
    ctx.save()


def revise_plan(ctx: RunContext, feedback: list[str], source: str) -> None:
    """Planı geri bildirim maddelerine göre tek bir düzeltme isteğiyle düzeltir; farkı log'a yazar."""
    ctx.current_agent = AGENT
    topic = ctx.state["topic"]
    before = ctx.state["plan"]
    ctx.log(AGENT, f"Plan revizyonu ({source} geri bildirimi, {len(feedback)} madde)",
            "\n".join(f"- {f}" for f in feedback))
    plan_json = json.dumps({k: v for k, v in before.items() if k != "days"}, ensure_ascii=False, indent=1)
    _generate(ctx, REVISE_PLAN_PROMPT.format(feedback="\n".join(f"- {f}" for f in feedback), title=topic["title"],
                                             company=topic.get("company", ""), plan=plan_json),
              purpose="hafta planı revizyonu")
    diff = "\n".join(difflib.unified_diff(_plan_listing(before).splitlines(),
                                          _plan_listing(ctx.state["plan"]).splitlines(),
                                          "önce", "sonra", lineterm="", n=0))
    ctx.log(AGENT, "Plan revizyon farkı:", diff or "(bölüm odak/olaylarında değişiklik yok)")
    ctx.state.setdefault("plan_revisions", []).append({"source": source, "feedback": feedback, "diff": diff})
    ctx.save()


def _words(items: list[str]) -> set[str]:
    return {w for w in re.findall(r"\w+", " ".join(items).lower()) if len(w) > 3}


def _overlaps(plan: WeekPlan, limit: float = 0.35) -> list[tuple[int, int, float]]:
    """Bölümlerin olay listeleri arasında kelime örtüşmesi (Jaccard) - tekrar uyarısı için."""
    out = []
    sets = [_words(p.key_events) for p in plan.parts]
    for i in range(3):
        for j in range(i + 1, 3):
            union = sets[i] | sets[j]
            ratio = len(sets[i] & sets[j]) / len(union) if union else 0
            if ratio > limit:
                out.append((i, j, ratio))
    return out


def part_focus_block(ctx: RunContext, index: int, previous_narrations: list[str]) -> str:
    """Senarist'e verilecek bölüm talimatı (plan + önceki bölümler)."""
    plan = ctx.state["plan"]
    part = plan["parts"][index]
    lines = [
        "",
        f"Bu, 3 bölümlük haftalık serinin {index + 1}/3. bölümü ({plan['days'][index]}): {part['focus_title']}.",
        f"Bu bölümün odağı: {part['focus']}",
        "Bu bölümde anlatılacak olaylar (başka bölümdeki olayları anlatma):",
        *[f"- {e}" for e in part["key_events"]],
        f"Kapanış (son cümle + cta): {part['cliffhanger']}",
    ]
    if previous_narrations:
        lines.append("Önceki bölüm(ler)de anlatılanlar (TEKRAR ETME):")
        lines += [f"- Bölüm {i + 1}: {t}" for i, t in enumerate(previous_narrations)]
    lines.append("")
    return "\n".join(lines)
