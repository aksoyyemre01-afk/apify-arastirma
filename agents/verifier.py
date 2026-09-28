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
"""

import json

from google.genai import types
from pydantic import BaseModel, Field

from src import script_writer
from src.schemas import ShortScript

from . import scriptwriter
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


RESEARCH_PROMPT = """Google'da araştır: Aşağıdaki YouTube Shorts cümlelerindeki rakamlar, para
tutarları, yüzdeler, yıllar/tarihler, kişi/şirket adları ve olaylar doğru mu? Ekrandaki
alanlardaki (value, unit, year, label, text, left_value, right_value, end_value) değerleri de
kontrol et. Her biri için web'de ara, güvenilir kaynaklarda ne yazdığını kısaca açıkla ve
farklılık varsa doğrusunu belirt. Yorum/görüş cümlelerini ve soruları atla.

Konu: {topic}

{scenes}"""

JUDGE_PROMPT = """Aşağıda bir YouTube Shorts script'i, bu script için yapılmış bir web araştırmasının
metni ve araştırmada bulunan NUMARALI kaynak listesi var. Script'teki her olgusal iddia için
(rakam, tarih, olay; yorum ve sorular hariç) araştırmaya dayanarak karar ver:
- verified: araştırma iddiayı destekliyor (makul yuvarlama kabul).
- incorrect: araştırma farklı bir değer veriyor; `correct` alanına doğrusunu yaz.
- unverifiable: araştırmada bu iddiaya dair bilgi yok ya da kaynaklar çelişiyor.
Kararını YALNIZCA araştırma metnine dayandır, kendi bilgini ekleme. source_ids'e yalnızca
aşağıdaki listedeki numaraları yaz.

Script:
{scenes}

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


def _grounding(response) -> tuple[list[dict], list[str]]:
    sources, queries, seen = [], [], set()
    for cand in response.candidates or []:
        gm = cand.grounding_metadata
        if not gm:
            continue
        queries += list(gm.web_search_queries or [])
        for ch in gm.grounding_chunks or []:
            if ch.web and ch.web.uri and ch.web.uri not in seen:
                seen.add(ch.web.uri)
                sources.append({"title": ch.web.title or "", "uri": ch.web.uri})
    return sources, queries


def _call(topic: str, script: ShortScript) -> tuple[Verification, list[dict], list[str], bool]:
    """(kararlar, gerçek arama kaynakları, yapılan aramalar, arama yapıldı mı) döner."""
    scenes = _scene_listing(script)
    search_cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    model = model_for("search")
    prompt = RESEARCH_PROMPT.format(topic=topic, scenes=scenes)
    research = script_writer.generate_raw(prompt, search_cfg, purpose="doğrulama: araştırma (Google Search)", model=model)
    sources, queries = _grounding(research)
    if not queries:
        research = script_writer.generate_raw(prompt + _FORCE_SEARCH, search_cfg,
                                              purpose="doğrulama: araştırma (tekrar)", model=model)
        sources, queries = _grounding(research)

    listing = "\n".join(f"{n}. {s['title']} — {s['uri']}" for n, s in enumerate(sources, 1)) or "(kaynak yok)"
    judge_cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=Verification)
    judged = script_writer.generate_raw(
        JUDGE_PROMPT.format(scenes=scenes, research=research.text or "", sources=listing),
        judge_cfg, purpose="doğrulama: karar", model=model_for("text"),
    )
    return Verification.model_validate_json(judged.text), sources, queries, bool(queries)


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
        claims = []
        for c in ver.claims:
            d = c.model_dump()
            # Kaynak numaraları yalnızca gerçek arama sonuçlarına çevrilir (modelin yazdığı URL yok).
            d["source_urls"] = [sources[k - 1]["uri"] for k in c.source_ids if 1 <= k <= len(sources)]
            d["source_titles"] = [sources[k - 1]["title"] for k in c.source_ids if 1 <= k <= len(sources)]
            claims.append(d)
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
