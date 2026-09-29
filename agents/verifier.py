"""Doğrulayıcı: script'teki rakam, tarih ve olgusal iddiaları Gemini + Google Search
grounding ile kontrol eder.

İki adım (ölçülen davranışa göre):
1) Araştırma: Google Search açık, SERBEST METİN istek. Model yanıtı bir formata (JSON)
   dökmesi istendiğinde aramayı atlayıp hafızasından cevap veriyordu (grounding bilgisi
   boş, URL'ler modelin kendi yazdıkları). Serbest metin araştırmada aramayı gerçekten
   yapıyor; yapılan aramalar ve bulunan kaynaklar yanıtın grounding bilgisinden okunur.
2) Karar: aramasız, yapılandırılmış ikinci çağrı - araştırma metni ve NUMARALI gerçek
   kaynak listesiyle her iddia için karar verir; kaynaklar yalnızca bu listeden seçilir.

- Hem seslendirme metni hem ekranda görünen alanlar (value, year, label...) kontrol edilir.
- Karar: verified / incorrect (doğrusu verilir) / unverifiable.
- Yanlış olan doğru değerle düzeltilir, doğrulanamayan çıkarılır ya da genel bir ifadeye
  çevrilir (Senarist'e tek düzeltme isteği); düzeltmeden sonra yeniden kontrol edilir
  (config/pipeline.json -> verify.max_rounds).
- Arama yapılmadıysa sonuç "aramasız" olarak işaretlenir; kaynaklar sources.json'a ve
  log.md'ye yazılır.
- verify_plan(): Araştırmacı'nın haftalık planı da (özet, odaklar, olaylar, kapanış
  kancaları) konu onayına sunulmadan önce aynı yöntemle kontrol edilir; sorunlu iddialar
  Araştırmacı'ya düzelttirilir, sonuç plan_sources.json'a ve review.md'ye yazılır.
"""

import json

from google.genai import types
from pydantic import BaseModel, Field

from src import script_writer
from src.schemas import ShortScript

from . import researcher, scriptwriter
from .base import CONFIG, RunContext, model_for

AGENT = "Doğrulayıcı"


class Claim(BaseModel):
    scene: int = Field(description="İddianın geçtiği sahne numarası (1'den başlar)")
    claim: str = Field(description="Kontrol edilen iddia, kısa")
    verdict: str = Field(description="verified | incorrect | unverifiable")
    correct: str = Field(default="", description="incorrect ise doğru değer/ifade, değilse boş")
    explanation: str = Field(default="", description="Kısa gerekçe (araştırmada ne bulunduğu)")
    source_ids: list[int] = Field(default_factory=list, description="Dayanılan kaynakların listedeki numaraları")


class Verification(BaseModel):
    claims: list[Claim]


class PlanClaim(BaseModel):
    item: int = Field(description="İddianın geçtiği plan maddesinin numarası (listedeki numara)")
    claim: str = Field(description="Kontrol edilen iddia, kısa")
    verdict: str = Field(description="verified | incorrect | unverifiable")
    correct: str = Field(default="", description="incorrect ise doğru değer/ifade, değilse boş")
    explanation: str = Field(default="", description="Kısa gerekçe (araştırmada ne bulunduğu)")
    source_ids: list[int] = Field(default_factory=list, description="Dayanılan kaynakların listedeki numaraları")


class PlanVerification(BaseModel):
    claims: list[PlanClaim]


RESEARCH_PROMPT = """Google'da araştır: Aşağıdaki YouTube Shorts cümlelerindeki rakamlar, para
tutarları, yüzdeler, yıllar/tarihler, kişi/şirket adları ve olaylar doğru mu? Ekrandaki
alanlardaki (value, unit, year, label, text, left_value, right_value, end_value) değerleri de
kontrol et. Her biri için web'de ara, güvenilir kaynaklarda ne yazdığını kısaca açıkla ve
farklılık varsa doğrusunu belirt. Yorum/görüş cümlelerini, soruları ve seriye atıf yapan geçiş
cümlelerini ("önceki bölümde…", "sıradaki bölümde…", "takipte kalın") atla.

Konu: {topic}

{scenes}"""

JUDGE_PROMPT = """Aşağıda bir YouTube Shorts script'i, bu script için yapılmış bir web araştırmasının
metni ve araştırmada bulunan NUMARALI kaynak listesi var. Script'teki her olgusal iddia için
(rakam, tarih, olay; yorum, sorular ve seriye atıf yapan geçiş cümleleri - "önceki bölümde…",
"sıradaki bölümde…" - hariç; bunlar iddia değildir, listeye alma) araştırmaya dayanarak karar ver:
- verified: araştırma iddiayı destekliyor (makul yuvarlama kabul).
- incorrect: araştırma farklı bir değer veriyor; `correct` alanına doğrusunu yaz.
- unverifiable: araştırmada bu iddiaya dair bilgi yok ya da kaynaklar çelişiyor.
Kararını YALNIZCA araştırma metnine dayandır, kendi bilgini ekleme. Araştırma metnindeki [n]
işaretleri, o cümlenin dayandığı kaynak numaralarıdır; source_ids'e iddiayı destekleyen ya da
çürüten cümlelerin [n] numaralarını yaz (yalnızca aşağıdaki listedeki numaralar).

Script:
{scenes}

Araştırma metni:
\"\"\"{research}\"\"\"

Kaynak listesi:
{sources}"""

PLAN_RESEARCH_PROMPT = """Google'da araştır: Aşağıdaki haftalık video planı maddelerindeki rakamlar,
para tutarları, yüzdeler, yıllar/tarihler, kişi/şirket/kurum adları ve olaylar doğru mu? Her biri
için web'de ara, güvenilir kaynaklarda ne yazdığını kısaca açıkla ve farklılık varsa doğrusunu
belirt (ör. olay hiç yaşanmadıysa ya da başka bir kurum/kişi yaptıysa). Yorum/görüş cümlelerini
ve merak kancalarındaki dramatik ifadeleri atla.

Konu: {topic}

{items}"""

PLAN_JUDGE_PROMPT = """Aşağıda bir haftalık video planının numaralı maddeleri, bu plan için yapılmış bir
web araştırmasının metni ve araştırmada bulunan NUMARALI kaynak listesi var. Plandaki her olgusal
iddia için (rakam, tarih, olay, kurum/kişi; yorum ve dramatik ifadeler hariç) araştırmaya
dayanarak karar ver; `item` alanına iddianın geçtiği madde numarasını yaz:
- verified: araştırma iddiayı destekliyor (makul yuvarlama kabul).
- incorrect: araştırma farklı bir değer/olgu veriyor; `correct` alanına doğrusunu yaz.
- unverifiable: araştırmada bu iddiaya dair bilgi yok ya da kaynaklar çelişiyor.
Kararını YALNIZCA araştırma metnine dayandır, kendi bilgini ekleme. Araştırma metnindeki [n]
işaretleri, o cümlenin dayandığı kaynak numaralarıdır; source_ids'e iddiayı destekleyen ya da
çürüten cümlelerin [n] numaralarını yaz (yalnızca aşağıdaki listedeki numaralar).

Plan maddeleri:
{items}

Araştırma metni:
\"\"\"{research}\"\"\"

Kaynak listesi:
{sources}"""

_SCREEN_FIELDS = ("value", "unit", "year", "label", "text", "left_brand", "right_brand",
                  "left_value", "right_value", "end_value")
# Arama yapılmadıysa bir kez daha, aramayı açıkça isteyen bu ekle denenir.
_FORCE_SEARCH = ("\n\nHafızana güvenme: her iddia için Google'da en az bir arama yap ve "
                 "bulduğun sayfaları kaynak göster.")


def _scene_listing(script: ShortScript) -> str:
    lines = []
    for i, s in enumerate(script.scenes, 1):
        fields = {k: getattr(s, k) for k in _SCREEN_FIELDS if getattr(s, k)}
        lines.append(f"{i}. \"{s.narration}\"" + (f"  | ekran: {json.dumps(fields, ensure_ascii=False)}" if fields else ""))
    return "\n".join(lines)


def _grounding(response) -> tuple[list[dict], list[str], str]:
    """(kaynaklar, aramalar, [n] atıflı araştırma metni) döner. Atıflar grounding_supports'tan
    eklenir: karar adımı, hangi bilginin hangi numaralı kaynaktan geldiğini ancak böyle görür."""
    sources, queries, number = [], [], {}
    text = response.text or ""
    for cand in response.candidates or []:
        gm = getattr(cand, "grounding_metadata", None)
        if not gm:
            continue
        queries += list(gm.web_search_queries or [])
        chunk_no = {}
        for i, ch in enumerate(gm.grounding_chunks or []):
            if ch.web and ch.web.uri:
                if ch.web.uri not in number:
                    sources.append({"title": ch.web.title or "", "uri": ch.web.uri})
                    number[ch.web.uri] = len(sources)
                chunk_no[i] = number[ch.web.uri]
        for sup in getattr(gm, "grounding_supports", None) or []:
            seg = (sup.segment.text or "") if sup.segment else ""
            nums = sorted({chunk_no[k] for k in (sup.grounding_chunk_indices or []) if k in chunk_no})
            pos = text.find(seg) if seg and nums else -1
            if pos >= 0:
                end = pos + len(seg)
                text = f"{text[:end]} [{', '.join(map(str, nums))}]{text[end:]}"
    return sources, queries, text


def _research_and_judge(research_prompt: str, judge_prompt: str, schema: type[BaseModel], label: str):
    """Aramalı araştırma + aramasız karar. judge_prompt {research} ve {sources} içerir.
    (kararlar, gerçek arama kaynakları, yapılan aramalar, arama yapıldı mı) döner."""
    search_cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    model = model_for("search")
    research = script_writer.generate_raw(research_prompt, search_cfg,
                                          purpose=f"{label}: araştırma (Google Search)", model=model)
    sources, queries, cited = _grounding(research)
    if not queries:
        research = script_writer.generate_raw(research_prompt + _FORCE_SEARCH, search_cfg,
                                              purpose=f"{label}: araştırma (tekrar)", model=model)
        sources, queries, cited = _grounding(research)

    listing = "\n".join(f"{n}. {s['title']} — {s['uri']}" for n, s in enumerate(sources, 1)) or "(kaynak yok)"
    judge_cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)
    judged = script_writer.generate_raw(
        judge_prompt.replace("{research}", cited).replace("{sources}", listing),
        judge_cfg, purpose=f"{label}: karar", model=model_for("text"),
    )
    return schema.model_validate_json(judged.text), sources, queries, bool(queries)


def _call(topic: str, script: ShortScript) -> tuple[Verification, list[dict], list[str], bool]:
    scenes = _scene_listing(script)
    return _research_and_judge(
        RESEARCH_PROMPT.format(topic=topic, scenes=scenes),
        JUDGE_PROMPT.replace("{scenes}", scenes), Verification, "doğrulama",
    )


def _with_sources(claim: BaseModel, sources: list[dict]) -> dict:
    # Kaynak numaraları yalnızca gerçek arama sonuçlarına çevrilir (modelin yazdığı URL yok).
    d = claim.model_dump()
    d["source_urls"] = [sources[k - 1]["uri"] for k in claim.source_ids if 1 <= k <= len(sources)]
    d["source_titles"] = [sources[k - 1]["title"] for k in claim.source_ids if 1 <= k <= len(sources)]
    return d


def verify(ctx: RunContext, index: int) -> dict:
    """Script'i doğrular, gerekirse Senarist'e düzelttirip yeniden doğrular. Son durumu döner."""
    rounds = int(CONFIG.get("verify", {}).get("max_rounds", 2))
    day = ctx.state["plan"]["days"][index]
    record = ctx.state.setdefault("shorts", {}).setdefault(str(index), {})
    history = record.setdefault("verify_rounds", [])
    result = {}
    for rnd in range(1, rounds + 1):
        ctx.current_agent = AGENT
        script = scriptwriter.load(ctx, index)
        ver, sources, queries, grounded = _call(ctx.state["topic"]["title"], script)
        claims = [_with_sources(c, sources) for c in ver.claims]
        counts = {v: sum(c["verdict"] == v for c in claims) for v in ("verified", "incorrect", "unverifiable")}
        result = {"round": rnd, "claims": claims, "sources": sources, "queries": queries, "counts": counts,
                  "grounded": grounded}
        if not grounded:
            ctx.log(AGENT, f"UYARI: {day} tur {rnd}: model iki denemede de Google araması yapmadı; "
                           f"sonuçlar modelin kendi bilgisine dayanıyor (review.md'de işaretlenecek).")
        history.append(result)
        (scriptwriter.short_dir(ctx, index) / "sources.json").write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.log(AGENT, f"{day} tur {rnd}: {counts['verified']} doğrulandı, {counts['incorrect']} yanlış, "
                       f"{counts['unverifiable']} doğrulanamadı ({len(queries)} arama, {len(sources)} kaynak)",
                "\n".join(f"[{c['verdict']}] sahne {c['scene']}: {c['claim']}"
                          + (f" -> doğrusu: {c['correct']}" if c["correct"] else "")
                          + (f" | kaynak: {', '.join(c['source_titles'][:3])}" if c["source_titles"] else "")
                          for c in claims) + ("\nKaynaklar:\n" + "\n".join(f"- {s['title']}: {s['uri']}" for s in sources)
                                              if sources else ""))
        problems = [c for c in claims if c["verdict"] in ("incorrect", "unverifiable")]
        if not problems:
            break
        if rnd == rounds:
            ctx.log(AGENT, f"{day}: {len(problems)} iddia son turda da sorunlu; review.md'de işaretlenecek.")
            break
        feedback = []
        for c in problems:
            if c["verdict"] == "incorrect":
                feedback.append(f"Sahne {c['scene']}: \"{c['claim']}\" YANLIŞ; doğrusu: {c['correct']}. "
                                f"Seslendirmeyi ve ekrandaki alanları bu doğru değere göre düzelt.")
            else:
                feedback.append(f"Sahne {c['scene']}: \"{c['claim']}\" doğrulanamadı. Bu iddiayı/rakamı çıkar ya "
                                f"da doğrulanabilir, genel bir ifadeyle değiştir (uydurma rakam yazma).")
        scriptwriter.revise(ctx, index, feedback, source=AGENT)
    record["verify"] = result
    ctx.save()
    return result


def plan_items(plan: dict) -> list[str]:
    """Planın olgu içerebilen maddeleri, numaralandırma sırasıyla ('[etiket] metin')."""
    items = [f"[Konu özeti] {plan['topic_summary']}"]
    for day, p in zip(plan["days"], plan["parts"]):
        items.append(f"[{day} · odak] {p['focus']}")
        items += [f"[{day} · olay] {e}" for e in p["key_events"]]
        items.append(f"[{day} · kapanış] {p['cliffhanger']}")
    return items


def verify_plan(ctx: RunContext) -> dict:
    """Haftalık planı doğrular, gerekirse Araştırmacı'ya düzelttirip yeniden doğrular. Son durumu döner."""
    rounds = int(CONFIG.get("verify", {}).get("max_rounds", 2))
    history = ctx.state["plan_verify_rounds"] = []
    result = {}
    for rnd in range(1, rounds + 1):
        ctx.current_agent = AGENT
        items = plan_items(ctx.state["plan"])
        listing = "\n".join(f"{n}. {t}" for n, t in enumerate(items, 1))
        ver, sources, queries, grounded = _research_and_judge(
            PLAN_RESEARCH_PROMPT.format(topic=ctx.state["topic"]["title"], items=listing),
            PLAN_JUDGE_PROMPT.replace("{items}", listing), PlanVerification, "plan doğrulama",
        )
        claims = [_with_sources(c, sources) for c in ver.claims]
        for c in claims:
            c["item_text"] = items[c["item"] - 1] if 1 <= c["item"] <= len(items) else ""
        counts = {v: sum(c["verdict"] == v for c in claims) for v in ("verified", "incorrect", "unverifiable")}
        result = {"round": rnd, "claims": claims, "sources": sources, "queries": queries, "counts": counts,
                  "grounded": grounded}
        if not grounded:
            ctx.log(AGENT, f"UYARI: plan tur {rnd}: model iki denemede de Google araması yapmadı; "
                           f"sonuçlar modelin kendi bilgisine dayanıyor (review.md'de işaretlenecek).")
        history.append(result)
        (ctx.dir / "plan_sources.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        ctx.log(AGENT, f"Plan tur {rnd}: {counts['verified']} doğrulandı, {counts['incorrect']} yanlış, "
                       f"{counts['unverifiable']} doğrulanamadı ({len(queries)} arama, {len(sources)} kaynak)",
                "\n".join(f"[{c['verdict']}] madde {c['item']}: {c['claim']}"
                          + (f" -> doğrusu: {c['correct']}" if c["correct"] else "")
                          + (f" | kaynak: {', '.join(c['source_titles'][:3])}" if c["source_titles"] else "")
                          for c in claims))
        problems = [c for c in claims if c["verdict"] in ("incorrect", "unverifiable")]
        if not problems:
            break
        if rnd == rounds:
            ctx.log(AGENT, f"Plan: {len(problems)} iddia son turda da sorunlu; review.md'de işaretlenecek.")
            break
        feedback = []
        for c in problems:
            where = c["item_text"].split("]")[0].lstrip("[") if c["item_text"] else f"madde {c['item']}"
            if c["verdict"] == "incorrect":
                feedback.append(f"{where}: \"{c['claim']}\" YANLIŞ; doğrusu: {c['correct'].rstrip('.')}. "
                                f"({c['explanation']}) Planı bu doğru bilgiye göre düzelt.")
            else:
                feedback.append(f"{where}: \"{c['claim']}\" doğrulanamadı. Bu iddiayı/rakamı çıkar ya da "
                                f"doğrulanabilir, genel bir ifadeyle değiştir (uydurma rakam yazma).")
        researcher.revise_plan(ctx, feedback, source=AGENT)
    ctx.state["plan_verify"] = result
    ctx.save()
    return result
