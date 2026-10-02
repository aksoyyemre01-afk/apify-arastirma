"""Uzun video (1920x1080, 5-6 dk): son iki haftanın short konularından birinin tam hikâyesi.

Onay kapıları (ses senin onayından önce asla üretilmez):
  long_estimate      [ONAY A] API'siz yerel tahmin: Gemini $, ElevenLabs karakter, kredi/bütçe payları
  long_voice_review  [ONAY B] script yazıldı + yeni iddialar doğrulandı; kesin karakter sayısı
  long_final         [ONAY C] ses + render + küçük resim + QA
  long_published     yayina-hazir/<hafta>/ klasöründe
  long_postponed     bütçe/kredi yetmedi: üretilmedi, ertelendi (onayla aşılamaz; config ya da yeni dönem)

Bütçe (agents/limits.py kilitlerine EK, hiçbirini gevşetmez):
- ElevenLabs aylık sınırı short'larla ortaktır; önce yenilenme tarihine kadarki short'ların payı
  ayrılır: kullanılabilir = kalan - short payı. Uzun video ancak kullanılabilir >= tahmini
  karakter x 1,10 ise başlar.
- Gemini haftalık sınırı aynıdır; bu haftanın short run'ı bitmediyse (ya da hiç yoksa) short payı
  ayrılır. Uzun video ancak harcanan + short payı + tahmini maliyet x 1,10 <= sınır ise başlar.
- Her Gemini/ElevenLabs isteği ayrıca mevcut sert kilitlerden geçer.

Maliyet tasarrufu: short run'ının doğrulanmış iddiaları/kaynakları yeniden kullanılır,
Doğrulayıcı yalnızca bunlarla örtüşmeyen YENİ cümleleri arar; ses bölüm bölüm üretilir ve
metni değişmeyen bölümün sesi yeniden üretilmez (önbellek).
"""

import hashlib
import json
import math
import os
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from google.genai import types
from pydantic import BaseModel, Field

from src import commons, long_planner, proc, renderer, screen_rules, speech_check, tr_numbers
from src import brand_config, script_writer
from src.schemas import LongVideoScript, section_text

from . import limits, verifier
from .base import CONFIG, PRICING, RUNS_DIR, BudgetExceeded, RunContext, notify

AGENT = "Uzun video"
ROOT = Path(__file__).resolve().parent.parent


def cfg() -> dict:
    d = {"every_n_weeks": 2, "lookback_weeks": 2, "max_spoken_chars": 4800, "min_spoken_chars": 3800, "min_seconds": 300,
         "max_seconds": 360, "margin": 0.10, "gemini_short_reserve_usd": 1.50, "qa_rounds": 1,
         "tts_context": False, "section_gap_sec": long_planner.SECTION_GAP}
    return {**d, **CONFIG.get("long", {})}


# ---------------------------------------------------------------------------- kaynak araştırma

def source_research(src: RunContext) -> dict:
    """Short run'ının doğrulanmış olguları (plan + script doğrulamaları), kaynaklar ve metinler."""
    st = src.state
    facts, sources = [], {}
    for c in (st.get("plan_verify") or {}).get("claims", []):
        if c["verdict"] == "verified":
            facts.append(c["claim"])
            sources.update(zip(c.get("source_urls", []), c.get("source_titles", [])))
    for rec in st.get("shorts", {}).values():
        for c in (rec.get("verify") or {}).get("claims", []):
            if c["verdict"] == "verified":
                facts.append(c["claim"])
                sources.update(zip(c.get("source_urls", []), c.get("source_titles", [])))
    narrations = []
    for d in sorted(src.dir.glob("short-*/script.json")):
        narrations.append(json.loads(d.read_text(encoding="utf-8")).get("narration_full", ""))
    return {"topic": st["topic"], "plan": st.get("plan", {}), "facts": list(dict.fromkeys(facts)),
            "sources": sources, "narrations": narrations, "brief": st.get("brief", "")}


def candidate_runs(today: date | None = None) -> list[Path]:
    """Son `lookback_weeks` haftanın short run'ları (uzun video run'ları hariç), yeniden eskiye."""
    today = today or date.today()
    out = []
    for p in RUNS_DIR.glob("*-W*"):
        if p.name.endswith(("-uzun", "-uzun-dryrun")) or not (p / "state.json").exists():
            continue
        m = re.match(r"(\d{4})-W(\d{2})", p.name)
        if not m:
            continue
        monday = date.fromisocalendar(int(m[1]), int(m[2]), 1)
        if (today - monday).days < 7 * cfg()["lookback_weeks"] + 7:
            out.append(p)
    return sorted(out, key=lambda p: p.name, reverse=True)


# ---------------------------------------------------------------------------- tahmin (API'siz)

def _history() -> dict[str, tuple[float, float, int]]:
    """purpose -> (ort. girdi, ort. çıktı token, adet), tüm çalıştırmaların usage.json'undan."""
    agg: dict[str, list[float]] = {}
    for f in RUNS_DIR.glob("*/usage.json"):
        for u in json.loads(f.read_text(encoding="utf-8")):
            if u["service"] == "gemini":
                a = agg.setdefault(u["purpose"], [0, 0, 0])
                a[0] += u["input_tokens"]
                a[1] += u["output_tokens"]
                a[2] += 1
    return {k: (a[0] / a[2], a[1] / a[2], int(a[2])) for k, a in agg.items()}


def _usd(inp: float, out: float) -> float:
    g = PRICING["gemini"]
    return inp / 1e6 * g["input_per_million"] + out / 1e6 * g["output_per_million"]


# Geçmiş yoksa kullanılan ihtiyatlı varsayılanlar (ort. girdi, ort. çıktı token).
_DEFAULTS = {"ShortScript": (3500, 5000), "doğrulama: araştırma (Google Search)": (1700, 5500),
             "doğrulama: karar": (4300, 3000), "QA görsel puanlama": (10000, 4000)}


def estimate(research: dict, script: LongVideoScript | None = None) -> dict:
    """Yerel tahmin. script yoksa hedef uzunluk (max_spoken_chars) üzerinden."""
    c = cfg()
    h = _history()

    def avg(p):
        return h.get(p, (*_DEFAULTS[p], 0))[:2]

    short_chars = sum(len(tr_numbers.to_spoken(n)) for n in research["narrations"]) / max(len(research["narrations"]), 1) or 600
    chars = len(tr_numbers.to_spoken(script.narration_full)) if script else int(c["max_spoken_chars"])
    k = max(chars / short_chars * 0.6, 1.0)  # düşünme token'ları metinle doğrusal büyümez
    s_in, s_out = avg("ShortScript")
    facts_tokens = sum(len(f) for f in research["facts"]) / 3.5 + sum(len(n) for n in research["narrations"]) / 3.5
    script_usd = _usd(s_in + facts_tokens + 1500, s_out * k)
    items = {
        "script yazımı (1 istek)": 0.0 if script else script_usd,
        "kısaltma ya da uzatma (en fazla 1 istek, olasılığa bakmadan dahil)": 0.0 if script else _usd(s_out * k + 1500, s_out * k * 0.8),
        f"yeni iddiaların doğrulanması ({int(CONFIG.get('verify', {}).get('max_rounds', 2))} tur, aramalı)":
            int(CONFIG.get("verify", {}).get("max_rounds", 2)) * 1.5 * (_usd(*avg("doğrulama: araştırma (Google Search)")) + _usd(*avg("doğrulama: karar"))),
        "düzeltme (sorunlu bölüm, 1 istek)": script_usd * 0.5,
        f"görsel QA ({c['qa_rounds']} tur)": c["qa_rounds"] * 2 * _usd(*avg("QA görsel puanlama")),
    }
    if script is not None:
        # Script yazılmış ve doğrulanmışsa (ONAY B) geriye kalan tek Gemini işi görsel QA'dır.
        items = {k: v for k, v in items.items() if k.startswith("görsel QA")}
    gemini = sum(items.values())
    return {"chars": chars, "chars_with_margin": math.ceil(chars * (1 + c["margin"])),
            "gemini_items": items, "gemini_usd": gemini, "gemini_with_margin": gemini * (1 + c["margin"]),
            "history_n": sum(v[2] for v in h.values()), "based_on_script": script is not None}


# ---------------------------------------------------------------------------- short öncelikli kilitler

def _current_week_short_runs(today: date) -> list[RunContext]:
    y, w, _ = today.isocalendar()
    return [RunContext(p) for p in RUNS_DIR.glob(f"{y}-W{w:02d}*")
            if (p / "state.json").exists() and "uzun" not in p.name]


def _short_run_done(ctx: RunContext) -> bool:
    return ctx.stage in ("final_review", "published")


def reservations(today: date | None = None, el_status: dict | None = None) -> dict:
    """Short'lar için ayrılan ElevenLabs karakteri ve Gemini $ (uzun video bunlara dokunamaz)."""
    today = today or date.today()
    per_short = limits.estimated_chars_per_short()
    runs = _current_week_short_runs(today)
    if runs:
        cur_chars = sum(3 * per_short if not r.state.get("shorts") else
                        sum(per_short for s in r.state["shorts"].values() if s.get("status") not in ("passed", "failed"))
                        + per_short * (3 - len(r.state["shorts"]))
                        for r in runs if not _short_run_done(r))
    else:
        cur_chars = 3 * per_short  # bu haftanın short run'ı henüz başlamadı
    future_weeks = 0
    if el_status and el_status.get("reset"):
        reset = date.fromisoformat(el_status["reset"])
        monday = today + timedelta(days=7 - today.weekday())
        while monday < reset:
            future_weeks += 1
            monday += timedelta(days=7)
    el_reserve = cur_chars + future_weeks * 3 * per_short
    short_pending = not runs or not all(_short_run_done(r) for r in runs)
    spent_by_shorts = sum(r.cost_summary()["gemini_usd"] + r.cost_summary()["search_usd"] for r in runs)
    gem_reserve = max(0.0, cfg()["gemini_short_reserve_usd"] - spent_by_shorts) if short_pending else 0.0
    return {"el_reserve": el_reserve, "el_current_week": cur_chars, "el_future_weeks": future_weeks,
            "gemini_reserve": gem_reserve, "short_pending": short_pending}


def check_limits(est: dict, today: date | None = None) -> dict:
    """{'ok': bool, 'reasons': [...], ...ayrıntılar}. Hiçbir koşul onayla aşılamaz."""
    reasons, el = [], None
    try:
        el = limits.elevenlabs_status()
    except limits.QuotaExceeded as e:
        reasons.append(f"ElevenLabs kredisi okunamadı: {e}")
    res = reservations(today, el)
    spent, limit = limits.weekly_gemini_usd(), limits.gemini_limit()
    need_usd = est["gemini_with_margin"]
    if spent + res["gemini_reserve"] + need_usd > limit:
        reasons.append(f"Gemini: bu hafta ${spent:.2f} harcandı + short payı ${res['gemini_reserve']:.2f} + uzun video "
                       f"~${need_usd:.2f} (%{cfg()['margin'] * 100:.0f} pay dahil) > haftalık sınır ${limit:.2f}")
    available = None
    if el:
        available = el["remaining"] - res["el_reserve"]
        if available < est["chars_with_margin"]:
            reasons.append(f"ElevenLabs: kalan {el['remaining']:,} - short payı {res['el_reserve']:,} = {available:,} karakter "
                           f"< gereken {est['chars_with_margin']:,} (%{cfg()['margin'] * 100:.0f} pay dahil)")
    return {"ok": not reasons, "reasons": reasons, "gemini_spent": spent, "gemini_limit": limit,
            "el": el, "el_available": available, **res}


# ---------------------------------------------------------------------------- Gemini adımları

LONG_PROMPT = """Sen belgesel tadında iş dünyası hikâyeleri anlatan bir YouTube senaristisin. Aşağıdaki konunun
TAM HİKÂYESİNİ 5-6 dakikalık yatay bir video için yaz.

Konu: {title}
Şirket: {company}
{brief}
Bu konu daha önce 3 short'luk bir seri olarak işlendi. Short'ların seslendirme metinleri:
{narrations}

DOĞRULANMIŞ OLGULAR (Google araştırmasıyla doğrulandı; rakam ve tarihlerde YALNIZCA bunları kullan.
Buraya yazılmamış yeni bir rakam/tarih kullanırsan ayrıca doğrulanacak; emin değilsen yazma):
{facts}

Yapı:
- hook: 20-30 saniyelik (50-70 kelime) güçlü açılış; heading boş.
- chapters: 3-4 bölüm, kronolojik; her birinin kısa bir başlığı (heading, en fazla 5 kelime) var. Başlık
  seslendirmede okunur ve ekranda bölüm kartı olarak görünür.
- closing: çıkarılacak ders + izleyiciye bir soru; heading boş.
- Toplam seslendirme (başlıklar dahil) en fazla {max_chars} karakter (rakamlar okunuşuyla sayılır);
  {min_words}-{max_words} kelime hedefle.
- Gerçek kişileri yalnızca belgelenmiş, kesinleşmiş bilgilerle an (ör. mahkeme kararları).
- Her sahne bir cümledir; sahne tipleri short'larla aynıdır, ek olarak 'photo': cümlede adı geçen gerçek
  bir kişinin/kurumun/yerin arşiv fotoğrafı (konu adı `brand` alanında). Aynı tip art arda 3'ten fazla
  kullanılmaz; her bölümde en az 3 farklı tip olsun.
- Ekrandaki her metin/etiket/rakam o cümlede söylenen kelimelerden gelsin; aynı rakam kartı ya da metin
  iki kez kullanılmasın.
- description: 2-3 cümlelik açıklama girişi; tags: 10-15 etiket; thumbnail_value/unit: doğrulanmış
  olgulardan en çarpıcı rakam (yoksa boş) ve thumbnail_headline: en fazla 5 kelimelik başlık.
- Metinler Türkçe.

{narration_style_rules}

{scene_rules}"""

SHORTEN_PROMPT = """Aşağıdaki uzun video script'inin (JSON) toplam seslendirmesi {chars} karakter; en fazla {max_chars}
karakter olmalı (rakamlar okunuşuyla sayılır). Yapıyı (hook, bölümler, kapanış, başlıklar) ve doğrulanmış
olguları koruyarak, en az önemli cümleleri çıkararak ya da sadeleştirerek kısalt. Yeni olgu ekleme.
Her sahne kendi cümlesiyle kalsın.

{script}"""

EXTEND_PROMPT = """Aşağıdaki uzun video script'inin (JSON) toplam seslendirmesi {chars} karakter; 5-6 dakikalık bir video için
{min_chars}-{max_chars} karakter olmalı (rakamlar okunuşuyla sayılır). Yapıyı (hook, bölümler, başlıklar, kapanış)
koruyarak her bölümü derinleştir: aşağıdaki DOĞRULANMIŞ OLGULARDAN henüz kullanılmayanları, bağlamı ve sonuçlarını
ekle. Doğrulanmış olgularda olmayan yeni rakam/tarih ekleme; ekleyeceksen ayrıca doğrulanacağını bil. Her yeni cümle
kendi sahnesiyle gelsin (ekrandaki metin o cümlede söylenen kelimelerden; aynı kart/metin tekrar etmesin).

DOĞRULANMIŞ OLGULAR:
{facts}

Script:
{script}"""

REVISE_SECTION_PROMPT = """Aşağıdaki video bölümünde (JSON) şu sorunlar bulundu:
{feedback}
Bölümü düzelt: yanlış olguyu doğrusuyla değiştir, doğrulanamayanı çıkar ya da doğrulanabilir genel bir ifadeye
çevir. Başlığı ve geri kalanını koru; her sahne kendi cümlesiyle kalsın. Yeni olgu ekleme.

{section}"""

NEW_CLAIMS_RESEARCH = """Google'da araştır: Aşağıdaki cümlelerdeki rakamlar, tarihler, kişi/şirket/kurum adları ve olaylar
doğru mu? Her biri için web'de ara, güvenilir kaynaklarda ne yazdığını kısaca açıkla, farklılık varsa
doğrusunu belirt. Yorum/görüş ve sorular hariç.

Konu: {topic}

{items}"""

NEW_CLAIMS_JUDGE = verifier.PLAN_JUDGE_PROMPT.replace("haftalık video planının numaralı maddeleri",
                                                      "uzun video script'inin numaralı cümleleri")


def _schema_cfg(schema) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)


def write_script(ctx: RunContext, research: dict) -> LongVideoScript:
    c = cfg()
    words_per_char = 0.135  # Türkçe okunuş: ~7,4 karakter/kelime
    prompt = LONG_PROMPT.format(
        title=research["topic"]["title"], company=research["topic"].get("company", ""),
        brief=(f"Editör notu:\n{research['brief']}\n" if research["brief"] else ""),
        narrations="\n".join(f"- Bölüm {i}: {n}" for i, n in enumerate(research["narrations"], 1)),
        facts="\n".join(f"- {f}" for f in research["facts"]) or "(yok)",
        max_chars=c["max_spoken_chars"], min_words=int(c["max_spoken_chars"] * words_per_char * 0.85),
        max_words=int(c["max_spoken_chars"] * words_per_char),
        narration_style_rules=script_writer.NARRATION_STYLE_RULES, scene_rules=script_writer.SCENE_RULES,
    )
    ctx.current_agent = "Senarist"
    resp = script_writer.generate_raw(prompt, _schema_cfg(LongVideoScript), purpose="uzun video script")
    script = LongVideoScript.model_validate_json(resp.text)
    chars = len(tr_numbers.to_spoken(script.narration_full))
    ctx.log("Senarist", f"Uzun video script'i yazıldı: \"{script.title}\" ({len(script.chapters)} bölüm, {chars} okunuş karakteri)")
    if chars > c["max_spoken_chars"]:
        ctx.check_budget()
        resp = script_writer.generate_raw(
            SHORTEN_PROMPT.format(chars=chars, max_chars=c["max_spoken_chars"], script=script.model_dump_json(indent=1)),
            _schema_cfg(LongVideoScript), purpose="uzun video kısaltma")
        script = LongVideoScript.model_validate_json(resp.text)
        after = len(tr_numbers.to_spoken(script.narration_full))
        ctx.log("Senarist", f"Kısaltma (tek istek): {chars} -> {after} karakter"
                + ("" if after <= c["max_spoken_chars"] else " — UYARI: hâlâ sınırın üstünde, bu haliyle kullanılacak"))
    elif chars < c["min_spoken_chars"]:
        script = extend_script(ctx, script, research)
    return script


def extend_script(ctx: RunContext, script: LongVideoScript, research: dict) -> LongVideoScript:
    """Metin 5-6 dk için kısa kaldıysa TEK bir uzatma isteği (kısaltmanın simetriği)."""
    c = cfg()
    chars = len(tr_numbers.to_spoken(script.narration_full))
    ctx.check_budget()
    ctx.current_agent = "Senarist"
    resp = script_writer.generate_raw(
        EXTEND_PROMPT.format(chars=chars, min_chars=c["min_spoken_chars"], max_chars=c["max_spoken_chars"],
                             facts="\n".join(f"- {f}" for f in research["facts"]), script=script.model_dump_json(indent=1)),
        _schema_cfg(LongVideoScript), purpose="uzun video uzatma")
    longer = LongVideoScript.model_validate_json(resp.text)
    ctx.state.setdefault("script_drafts", []).append({"purpose": "uzatma", "script": longer.model_dump()})
    ctx.save()  # hiçbir istek sonucu kaybolmasın
    after = len(tr_numbers.to_spoken(longer.narration_full))
    ctx.log("Senarist", f"Uzatma (tek istek): {chars} -> {after} karakter")
    if after > c["max_spoken_chars"]:
        trimmed = trim_local(longer, c["max_spoken_chars"])
        if trimmed is not None:
            ctx.log("Senarist", f"Üst sınır az farkla aşıldı: yerelde kırpıldı (API yok) -> "
                                f"{len(tr_numbers.to_spoken(trimmed.narration_full))} karakter")
            return trimmed
        ctx.check_budget()
        resp = script_writer.generate_raw(
            SHORTEN_PROMPT.format(chars=after, max_chars=c["max_spoken_chars"], script=longer.model_dump_json(indent=1)),
            _schema_cfg(LongVideoScript), purpose="uzun video kısaltma")
        longer = LongVideoScript.model_validate_json(resp.text)
        ctx.log("Senarist", f"Kısaltma (tek istek): {after} -> {len(tr_numbers.to_spoken(longer.narration_full))} karakter")
    return longer


TARGETED_EXTEND_PROMPT = """Aşağıdaki uzun video script'ini (JSON) BÖLÜM BÖLÜM belirtilen uzunluklara getir. Uzunluklar okunuş
karakteridir (rakamlar okunuşuyla, boşluklar dahil). Her bölümün hedefine ±%5 içinde uy; bu kesin bir şarttır.

{targets}

Kurallar: yapıyı ve başlıkları koru; mevcut cümleleri koru, aralarına ve sonlarına derinleştiren yeni cümleler ekle.
Yeni olgu yalnızca aşağıdaki DOĞRULANMIŞ OLGULARDAN gelsin; yeni rakam/tarih uydurma. Her yeni cümle kendi sahnesiyle
gelsin (ekrandaki metin o cümlede söylenen kelimelerden; aynı kart/metin/fotoğraf tekrar etmesin).

DOĞRULANMIŞ OLGULAR:
{facts}

Script:
{script}"""


def section_targets(script: LongVideoScript, total: int) -> dict[str, int]:
    """Toplam hedefi bölümlere dağıtır: hook %10, kapanış %8, kalan bölümlere eşit."""
    hook, closing = round(total * 0.10), round(total * 0.08)
    per = (total - hook - closing) // max(len(script.chapters), 1)
    return {"hook": hook, **{f"bolum-{i}": per for i in range(1, len(script.chapters) + 1)}, "kapanis": closing}


def request_usd_estimate(ctx: RunContext, purposes: tuple[str, ...], fallback: float) -> float:
    """Bu çalıştırmada aynı türden önceki isteklerin gerçek ortalama maliyeti (yoksa fallback), %10 paylı."""
    same = [u for u in ctx.usage if u["service"] == "gemini" and u["purpose"] in purposes]
    avg = sum(_usd(u["input_tokens"], u["output_tokens"]) for u in same) / len(same) if same else fallback
    return avg * (1 + cfg()["margin"])


def extend_targeted(ctx: RunContext, script: LongVideoScript, research: dict, low: int, high: int) -> tuple[LongVideoScript | None, int]:
    """TEK hedefli uzatma isteği; sonuç [low, high] dışındaysa (None, karakter) döner — yeni istek ATILMAZ."""
    total_target = (low + high) // 2
    targets = section_targets(script, total_target)
    cur = {k: len(tr_numbers.to_spoken(section_text(s))) for k, s in script.sections()}
    lines = [f"- {k}{' (' + s.heading + ')' if s.heading else ''}: şu an {cur[k]} -> hedef {targets[k]} karakter"
             for k, s in script.sections()]
    ctx.check_budget()
    ctx.current_agent = "Senarist"
    resp = script_writer.generate_raw(
        TARGETED_EXTEND_PROMPT.format(targets="\n".join(lines) + f"\nTOPLAM hedef: {total_target} (kabul aralığı {low}-{high})",
                                      facts="\n".join(f"- {f}" for f in research["facts"]), script=script.model_dump_json(indent=1)),
        _schema_cfg(LongVideoScript), purpose="uzun video hedefli uzatma")
    out = LongVideoScript.model_validate_json(resp.text)
    ctx.state.setdefault("script_drafts", []).append({"purpose": "hedefli uzatma", "script": out.model_dump()})
    ctx.save()
    chars = len(tr_numbers.to_spoken(out.narration_full))
    per = {k: len(tr_numbers.to_spoken(section_text(s))) for k, s in out.sections()}
    ctx.log("Senarist", f"Hedefli uzatma (tek istek): {sum(cur.values())} -> {chars} karakter (kabul {low}-{high})",
            "\n".join(f"{k}: {cur[k]} -> {per.get(k, 0)} (hedef {targets[k]})" for k in targets))
    return (out if low <= chars <= high else None), chars


def fix_sentence(script: LongVideoScript, old: str, new: str) -> int:
    """Bir ifadeyi seslendirme ve ekran alanlarında değiştirir (API yok). Değişen yer sayısını döner."""
    n = 0
    for _, sec in script.sections():
        if old in sec.narration:
            sec.narration = sec.narration.replace(old, new)
            n += 1
        for sc in sec.scenes:
            for f in ("narration", "text", "label"):
                if old in (getattr(sc, f) or ""):
                    setattr(sc, f, getattr(sc, f).replace(old, new))
                    n += 1
    return n


def trim_local(script: LongVideoScript, max_chars: int, max_over: float = 0.10) -> LongVideoScript | None:
    """Üst sınır en fazla %10 aşıldıysa API'siz kırpma: en uzun bölümün ortasından, rakam ve özel ad
    içermeyen cümleler sahneleriyle birlikte çıkarılır (ilk ve son cümleye dokunulmaz). Olmazsa None."""
    s = script.model_copy(deep=True)
    total = lambda: len(tr_numbers.to_spoken(s.narration_full))  # noqa: E731
    if total() > max_chars * (1 + max_over):
        return None
    while total() > max_chars:
        chapters = sorted(s.chapters, key=lambda ch: -len(tr_numbers.to_spoken(section_text(ch))))
        removed = False
        for ch in chapters:
            cands = [i for i, sc in enumerate(ch.scenes[1:-1], 1)
                     if not re.search(r"\d", sc.narration) and not [w for w in sc.narration.split()[1:] if w[:1].isupper()]]
            if cands:
                del ch.scenes[cands[len(cands) // 2]]
                ch.narration = " ".join(sc.narration for sc in ch.scenes)
                removed = True
                break
        if not removed:
            return None
    return s


def _sentences(script: LongVideoScript) -> list[tuple[str, str]]:
    out = []
    for key, sec in script.sections():
        for s in re.split(r"(?<=[.!?])\s+", section_text(sec)):
            if s.strip():
                out.append((key, s.strip()))
    return out


def new_sentences(script: LongVideoScript, research: dict) -> list[tuple[str, str]]:
    """Doğrulanmış olgularla örtüşmeyen, olgu içeren cümleler (yalnızca bunlar aranır)."""
    corpus = " ".join(research["facts"] + research["narrations"])
    known_nums = set(tr_numbers.numbers_in(corpus, words=False))
    known_tokens = {screen_rules._fold(screen_rules._norm(w)) for w in corpus.split() if len(w) >= 4}
    out = []
    for key, s in _sentences(script):
        nums = tr_numbers.numbers_in(s, words=False)
        toks = [screen_rules._fold(screen_rules._norm(w)) for w in s.split() if len(screen_rules._norm(w)) >= 4]
        proper = [w for w in s.split()[1:] if w[:1].isupper()]
        if not nums and not proper:
            continue  # rakam ya da özel ad yok: olgu iddiası taşımıyor
        overlap = sum(any(screen_rules._same_root(t, k) for k in known_tokens) for t in toks) / max(len(toks), 1)
        if any(n not in known_nums for n in nums) or overlap < 0.5:
            out.append((key, s))
    return out


def verify_new(ctx: RunContext, script: LongVideoScript, research: dict) -> LongVideoScript:
    rounds = int(CONFIG.get("verify", {}).get("max_rounds", 2))
    history = ctx.state.setdefault("verify_rounds", [])
    for rnd in range(1, rounds + 1):
        items = new_sentences(script, research)
        total = len(_sentences(script))
        ctx.log(verifier.AGENT, f"Tur {rnd}: {total} cümlenin {total - len(items)}'i doğrulanmış olgularla örtüşüyor; "
                                f"{len(items)} yeni cümle aranacak")
        if not items:
            ctx.state["verify"] = {"round": rnd, "claims": [], "new": 0, "reused": total, "grounded": True, "queries": []}
            break
        ctx.check_budget()
        ctx.current_agent = verifier.AGENT
        listing = "\n".join(f"{n}. {s}" for n, (_, s) in enumerate(items, 1))
        ver, sources, queries, grounded = verifier._research_and_judge(
            NEW_CLAIMS_RESEARCH.format(topic=research["topic"]["title"], items=listing),
            NEW_CLAIMS_JUDGE.replace("{items}", listing), verifier.PlanVerification, "uzun video doğrulama")
        claims = [verifier._with_sources(c, sources) for c in ver.claims]
        for c in claims:
            c["section"] = items[c["item"] - 1][0] if 1 <= c["item"] <= len(items) else ""
            c["sentence"] = items[c["item"] - 1][1] if 1 <= c["item"] <= len(items) else ""
        # Doğrulanan yeni cümleler doğrulanmış olgulara eklenir: sonraki turlarda yeniden aranmaz.
        research["facts"] += [c["sentence"] for c in claims if c["verdict"] == "verified" and c["sentence"]
                              and c["sentence"] not in research["facts"]]
        result = {"round": rnd, "claims": claims, "new": len(items), "reused": total - len(items),
                  "grounded": grounded, "queries": queries, "sources": sources}
        history.append(result)
        ctx.state["verify"] = result
        bad = [c for c in claims if c["verdict"] != "verified"]
        ctx.log(verifier.AGENT, f"Tur {rnd}: {len(claims) - len(bad)} doğrulandı, {len(bad)} sorunlu")
        if not bad or rnd == rounds:
            break
        for key in dict.fromkeys(c["section"] for c in bad if c["section"]):
            fb = [f"\"{c['claim']}\": " + (f"YANLIŞ, doğrusu {c['correct']}" if c["verdict"] == "incorrect" else "doğrulanamadı")
                  for c in bad if c["section"] == key]
            sec = dict(script.sections())[key]
            ctx.check_budget()
            ctx.current_agent = "Senarist"
            resp = script_writer.generate_raw(REVISE_SECTION_PROMPT.format(feedback="\n".join(fb), section=sec.model_dump_json(indent=1)),
                                              _schema_cfg(type(sec)), purpose="uzun video bölüm düzeltme")
            new = type(sec).model_validate_json(resp.text)
            if key == "hook":
                script.hook = new
            elif key == "kapanis":
                script.closing = new
            else:
                script.chapters[int(key.split("-")[1]) - 1] = new
            ctx.log("Senarist", f"{key} düzeltildi ({len(fb)} madde)")
    ctx.save()
    return script


# ---------------------------------------------------------------------------- ses (bölüm bölüm)

def _section_key(text: str) -> str:
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "") + os.environ.get("ELEVENLABS_MODEL", "")
    return hashlib.sha1((tr_numbers.to_spoken(text) + "|" + voice).encode("utf-8")).hexdigest()[:16]


def _fake_section_audio(text: str, path: Path) -> list[dict]:
    """Dry-run: okunuş hızına göre tahmini kelime zamanları + sessiz ses (API yok)."""
    t, out = 0.0, []
    for w in text.split():
        dur = max(script_writer._spoken_chars(w) / script_writer.SPEECH_CHARS_PER_SEC, 0.12)
        out.append({"word": w, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur + (script_writer.SENTENCE_PAUSE_SEC if w.endswith((".", "?", "!", ":")) else 0.04)
    proc.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{t + 0.2:.2f}",
              "-q:a", "9", str(path)], check=True)
    return out


def voice(ctx: RunContext, script: LongVideoScript, dry_run: bool) -> tuple[Path, list[dict], dict[str, float]]:
    """Bölüm bölüm ses; metni değişmeyen bölüm önbellekten. (birleşik ses, kelime zamanları, bölüm başları)."""
    from src import tts

    vdir = ctx.dir / "ses"
    vdir.mkdir(exist_ok=True)
    cache = ctx.state.setdefault("voice_cache", {})
    secs = script.sections()
    parts, offset, timings, starts = [], 0.0, [], {}
    gap = float(cfg()["section_gap_sec"])
    for i, (key, sec) in enumerate(secs):
        text = section_text(sec)
        k = _section_key(text)
        audio, tfile = vdir / f"{key}.mp3", vdir / f"{key}.json"
        if cache.get(key) == k and audio.exists() and tfile.exists():
            words = json.loads(tfile.read_text(encoding="utf-8"))
            ctx.log("Yönetmen", f"{key}: metin değişmedi, ses önbellekten (0 karakter)")
        elif dry_run:
            words = _fake_section_audio(text, audio)
        else:
            kw = {}
            if cfg()["tts_context"]:
                kw = {"previous_text": section_text(secs[i - 1][1]) if i else None,
                      "next_text": section_text(secs[i + 1][1]) if i + 1 < len(secs) else None}
            ctx.current_agent = "Yönetmen"
            words = tts.synthesize_with_timestamps(text, str(audio), **kw)
            if not words:
                raise RuntimeError(f"{key}: kelime zamanları alınamadı")
            ctx.log("Yönetmen", f"{key}: seslendirildi ({len(tr_numbers.to_spoken(text))} karakter)")
        tfile.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
        cache[key] = k
        dur = renderer.probe_duration(audio)
        starts[key] = offset
        timings += [{"word": w["word"], "start": round(w["start"] + offset, 3), "end": round(w["end"] + offset, 3)} for w in words]
        parts.append(audio)
        offset += dur + gap
    ctx.save()
    # Birleştirme: bölümler arasına `gap` sn sessizlik; 44,1 kHz mono -> ortak biçim.
    joined = ctx.dir / "audio.mp3"
    inputs, fc = [], []
    for n, p in enumerate(parts):
        inputs += ["-i", str(p)]
        fc.append(f"[{n}:a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur={gap if n < len(parts) - 1 else 0}[a{n}]")
    fc.append("".join(f"[a{n}]" for n in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]")
    proc.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[out]",
              "-c:a", "libmp3lame", "-b:a", "192k", str(joined)], check=True)
    (ctx.dir / "word_timings.json").write_text(json.dumps(timings, ensure_ascii=False, indent=1), encoding="utf-8")
    return joined, timings, starts


# ---------------------------------------------------------------------------- render + ölçüm

def thumbnail_props(script: LongVideoScript, research: dict, cfg_brand: dict, logo_ref) -> dict:
    """Küçük resim: rakam doğrulanmış olgularda geçmiyorsa gösterilmez (başlık kalır)."""
    known = set(tr_numbers.numbers_in(" ".join(research["facts"]), words=False))
    value = script.thumbnail_value.strip()
    if value and not set(tr_numbers.numbers_in(f"{value} {script.thumbnail_unit}", words=False)) & known:
        value = ""
    headline = " ".join(script.thumbnail_headline.split()[:5])
    return {"width": 1280, "height": 720,
            "theme": {"palette": cfg_brand["palette"], "headingFont": f"fonts/{cfg_brand['fonts']['heading']}",
                      "bodyFont": f"fonts/{cfg_brand['fonts']['body']}", "badgeText": "", "intro": False},
            "value": value, "unit": script.thumbnail_unit.strip() if value else "", "headline": headline,
            "logo": logo_ref(script.main_brand) if script.main_brand else None, "tone": "fall"}


def measure(d: Path, script: LongVideoScript, props: dict, marks: list, dry_run: bool = False,
            target: dict | None = None) -> list[dict]:
    """Uzun video ölçümleri (kod düzeyi, ücretsiz). İhlal varsa video QA'dan geçmez."""
    from .critic import _moov_first, _probe
    from src.scene_planner import measure_lufs

    c, checks = {**cfg(), **(target or {})}, []  # target: bu çalıştırmaya özel süre hedefi (state.duration_target)

    def check(name, ok, value):
        checks.append({"name": name, "ok": bool(ok), "value": value})

    timings = json.loads((d / "word_timings.json").read_text(encoding="utf-8"))
    video = d / "video.mp4"
    dur = renderer.probe_duration(video)
    check(f"Süre {c['min_seconds'] / 60:g}-{c['max_seconds'] / 60:g} dk", c["min_seconds"] <= dur <= c["max_seconds"], f"{dur / 60:.2f} dk")
    chars = len(tr_numbers.to_spoken(script.narration_full))
    check(f"Seslendirme <= {c['max_spoken_chars']} karakter", chars <= c["max_spoken_chars"], f"{chars}")
    streams = {s["codec_type"]: s for s in _probe(video).get("streams", [])}
    v, a = streams.get("video", {}), streams.get("audio", {})
    wh = proc.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json",
                   str(video)], capture_output=True, text=True).stdout
    v = {**v, **(json.loads(wh or "{}").get("streams") or [{}])[0]}
    check("Teslim biçimi (1920x1080 H.264 yuv420p, AAC 48 kHz stereo, faststart)",
          v.get("width") == 1920 and v.get("height") == 1080 and v.get("codec_name") == "h264"
          and a.get("codec_name") == "aac" and _moov_first(video), f"{v.get('width')}x{v.get('height')} {v.get('codec_name')}, {a.get('codec_name')}")
    lufs = measure_lufs(video)
    if dry_run:
        check("Ses -14 LUFS (±1)", True, f"dry-run: sessiz sahte ses ({lufs} LUFS), uygulanamaz")
    else:
        check("Ses -14 LUFS (±1)", lufs is not None and abs(lufs + 14) <= 1, f"{lufs} LUFS")
    sv = screen_rules.violations(props, timings)
    check("Ekrandaki her metin/rakam/logo o sahnede söyleniyor", not sv["unspoken"], "; ".join(sv["unspoken"][:3]) or "hepsi söyleniyor")
    check("Aynı kart/metin en fazla bir kez", not sv["duplicate"], "; ".join(sv["duplicate"][:3]) or "tekrar yok")
    for name, viol in (("En uzun sahne 8 sn (fotoğraf 10 sn)", long_planner.max_scene_violations(props)),
                       ("Ekran 4 sn'den fazla sabit kalmıyor", long_planner.static_violations(props)),
                       ("Sahne tipi çeşitliliği (60 sn / 90 sn)", long_planner.variety_violations(props)),
                       ("YouTube bölümleri geçerli", long_planner.chapter_problems(marks, dur))):
        check(name, not viol, "; ".join(viol[:3]) or "uygun")
    if dry_run:  # sessiz sahte ses yazıya dökülemez
        check("Söylenen rakamlar (konuşma tanıma)", True, "dry-run: sessiz ses, atlandı")
        sc = None
    else:
        sc = speech_check.check_dir(d, CONFIG.get("speech_check", {}).get("model", "medium"))
    if sc:
        check("Söylenen rakamlar script ile aynı (konuşma tanıma)", *sc["spoken"])
        check("Ekrandaki rakamlar seslendirmede geçiyor", *sc["screen"])
    return checks


def description(script: LongVideoScript, marks: list, credits: list[dict], research: dict) -> str:
    lines = [script.description.strip(), "", "Bölümler:"]
    lines += [f"{long_planner.fmt_ts(t)} {name}" for t, name in marks]
    if credits:
        lines += ["", "Fotoğraflar (Wikimedia Commons):"] + [f"- {commons.credit_line(m)}" for m in credits]
    titles = sorted({t for t in research["sources"].values() if t})
    if titles:
        lines += ["", "Kaynaklar: " + ", ".join(titles[:12])]
    lines += ["", " ".join(f"#{re.sub(r'[^0-9A-Za-zÇĞİÖŞÜçğıöşü]', '', t)}" for t in script.tags[:3])]
    return "\n".join(lines).strip()


SHORT_LINK_TEXT = "Bu hikâyenin tamamı (uzun video): {UZUN_VIDEO_LINKI}"

LONG_CRITIC_PROMPT = """Sen bir YouTube kalite kontrol editörüsün. Aşağıda 5-6 dakikalık YATAY (16:9) bir belgesel videodan
örneklenmiş kareler (kontak sayfaları) ve o anlarda söylenen metin var. Yalnızca şu kuralları 1-5 arası puanla
(5'i ancak somut kanıtla ver): 1 (ekrandaki her metin/rakam/logo/fotoğraf o anda söylenenle uyuşuyor),
3 (anlatım doğal, anlaşılır), 5 (sahneler en fazla 8 sn - fotoğraf 10 sn -, görsel çeşitlilik, ekran 4 sn'den fazla
sabit değil), 6 (altyazı okunur, alt bölgede, konuşmayla senkron), 7 (seri kimliği tutarlı), 10 (iç not/prompt izi yok).
Her ihlali sahne/kare ile yaz; en az 2 somut iyileştirme önerisi ver. Kısa sahne (3 sn) ve hook zamanlaması kuralları
bu format için GEÇERLİ DEĞİLDİR.

Kareler:
{frames}

Seslendirme:
{narration}

RULES.md:
{rules_md}"""


def vision_qa(ctx: RunContext, props: dict) -> dict:
    """1 tur (config long.qa_rounds) görsel QA: 16 kare, 2 kontak sayfası. Geçmezse otomatik revizyon
    döngüsü YOK (maliyet); öneriler ONAY C'de sunulur, düzeltme kararı insanındır."""
    from . import critic

    d, fps = ctx.dir, props["fps"]
    timings = json.loads((d / "word_timings.json").read_text(encoding="utf-8"))
    total = props["durationInFrames"] / fps
    kdir = d / "kareler"
    kdir.mkdir(exist_ok=True)
    plan = []
    for n in range(16):
        t = (n + 0.5) * total / 16
        said = " ".join(w["word"] for w in timings if t - 1.5 <= w["start"] <= t + 1.5)
        plan.append((t, said))
        proc.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(d / "video.mp4"), "-frames:v", "1",
                  "-vf", "scale=640:-1", str(kdir / f"kare_{n + 1:02d}.png")], check=True)
    sheets = []
    for s in range(2):
        out = kdir / f"sheet_{s + 1}.png"
        proc.run(["ffmpeg", "-v", "error", "-y", "-start_number", str(s * 8 + 1), "-i", str(kdir / "kare_%02d.png"),
                  "-frames:v", "1", "-vf", "tile=4x2:padding=6:color=white", str(out)], check=True)
        sheets.append(out)
    frames = "\n".join(f"- sayfa {n // 8 + 1}, kare {n % 8 + 1}: {t:.0f} sn — söylenen: \"{said}\"" for n, (t, said) in enumerate(plan))
    prompt = LONG_CRITIC_PROMPT.format(frames=frames, narration=ctx.state["script_text"][:6000],
                                       rules_md=(ROOT / "RULES.md").read_text(encoding="utf-8"))
    parts = [types.Part.from_bytes(data=p.read_bytes(), mime_type="image/png") for p in sheets] + [prompt]
    ctx.check_budget()
    ctx.current_agent = critic.AGENT
    resp = script_writer.generate_raw(parts, _schema_cfg(critic.Critique), purpose="QA görsel puanlama (uzun)")
    cq = critic.Critique.model_validate_json(resp.text)
    scores = [s.score for s in cq.scores]
    qa_cfg = CONFIG.get("qa", {})
    avg = sum(scores) / len(scores) if scores else 0
    passed = bool(scores) and min(scores) >= float(qa_cfg.get("min_rule_score", 3)) and avg >= float(qa_cfg.get("min_average_score", 4.0))
    result = {"passed": passed, "average": round(avg, 2), "scores": [s.model_dump() for s in cq.scores],
              "violations": [v.model_dump() for v in cq.violations], "improvements": cq.improvements, "summary": cq.summary}
    ctx.log(critic.AGENT, f"Uzun video görsel QA: {'GEÇTİ' if passed else 'KALDI'} (ort. {avg:.2f})")
    return result


# ---------------------------------------------------------------------------- akış

def produce(ctx: RunContext, dry_run: bool = False) -> None:
    """ONAY B'den sonra: bölüm bölüm ses -> render -> küçük resim -> ölçüm (+ görsel QA)."""
    script = LongVideoScript.model_validate(ctx.state["script"])
    research = ctx.state["research"]
    audio, timings, starts = voice(ctx, script, dry_run)
    duration = renderer.probe_duration(audio)
    brand = brand_config.load()
    (ctx.dir / "script.json").write_text(json.dumps({"narration_full": script.narration_full,
                                                     "scenes": [s for s in long_planner.flat_scenes(script) if s["scene_type"] != "chapter"]},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    props, files, credits = long_planner.build_props(script, timings, audio, duration, brand)
    video = renderer.render_long(ctx.dir, props, files, audio, timings)
    reg = renderer.scene_planner._LogoRegistry(False)
    tprops = thumbnail_props(script, research, brand, lambda b: renderer.scene_planner._logo_ref(b, {"start": 0, "end": 0}, reg, "", None))
    tfiles = {**reg.files, **{f"fonts/{brand['fonts'][k]}": renderer.scene_planner.FONT_DIR / brand["fonts"][k] for k in ("heading", "body")}}
    renderer.render_thumbnail(ctx.dir, tprops, tfiles)
    marks = long_planner.chapter_marks(starts, script)
    checks = measure(ctx.dir, script, props, marks, dry_run, ctx.state.get("duration_target"))
    qa = None if dry_run and not ctx.state.get("dry_run_vision") else vision_qa(ctx, props)
    ctx.state.update(section_starts=starts, marks=marks, credits=credits, checks=checks, qa=qa,
                     description=description(script, marks, credits, research),
                     video=str(video), thumbnail=str(ctx.dir / "thumbnail.png"))
    ctx.log(AGENT, f"Video hazır ({renderer.probe_duration(video) / 60:.2f} dk); ölçümler {sum(c['ok'] for c in checks)}/{len(checks)}",
            "\n".join(f"[{'OK' if c['ok'] else 'X'}] {c['name']}: {c['value']}" for c in checks))
    ctx.save()


def publish(ctx: RunContext) -> Path:
    week = ctx.state["source_run"].split("-uzun")[0]
    dest = ROOT / CONFIG.get("publish_dir", "yayina-hazir") / week
    dest.mkdir(parents=True, exist_ok=True)
    from src.utils import slugify
    name = f"uzun-{slugify(ctx.state['script']['title'])[:50]}"
    shutil.copy(ctx.dir / "video.mp4", dest / f"{name}.mp4")
    shutil.copy(ctx.dir / "thumbnail.png", dest / f"{name}-kucuk-resim.png")
    s = ctx.state["script"]
    (dest / f"{name}.txt").write_text(f"{s['title']}\n\n{ctx.state['description']}\n\nEtiketler: {', '.join(s['tags'])}\n\n"
                                      f"Short açıklamalarına: {SHORT_LINK_TEXT}\n", encoding="utf-8")
    return dest / f"{name}.mp4"
