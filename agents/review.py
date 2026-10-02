"""review.md: iki onay noktasının tek özet dosyası (konu onayı ve yayın öncesi final onayı)."""

import re
from pathlib import Path

from src.schemas import ShortScript

from . import limits, scriptwriter
from .base import RunContext

STAGE_TEXT = {
    "topic_review": "⏸ **Konu onayı bekleniyor.**",
    "producing": "⏳ Üretim sürüyor (arka planda). Bittiğinde bu dosya güncellenir ve bildirim gelir.",
    "final_review": "⏸ **Yayın öncesi final onayı bekleniyor.**",
    "budget_stopped": "⛔ **Harcama sınırı nedeniyle durdu.** Onayla aşılamaz; yalnızca config'deki limit "
                      "değiştirilerek (ya da ElevenLabs kredisi yenilenince) devam edilebilir.",
    "budget_paused": "⛔ **Harcama sınırı nedeniyle durdu** (eski sürüm).",
    "published": "✅ Onaylandı ve yayına hazır klasörüne kopyalandı.",
    "error": "❌ Pipeline bir hatayla durdu (ayrıntı log.md'de).",
}


def _commands(ctx: RunContext) -> list[str]:
    run = ctx.dir.name
    stage = ctx.stage
    if stage == "topic_review":
        return [
            "## Karar",
            "",
            f"- Onayla (üretim arka planda başlar): `python pipeline.py --approve --run {run}`",
            f"- Reddet (yeni konu önerilir): `python pipeline.py --reject \"gerekçe\" --run {run}`",
            f"- Konuyu koru, planı düzelttir (gerekçeyle yeniden üretilir ve doğrulanır): "
            f"`python pipeline.py --reject \"gerekçe\" --keep-topic --run {run}`",
        ]
    if stage == "final_review":
        return [
            "## Karar",
            "",
            f"- Tümünü onayla (yayına hazır klasörüne kopyalanır): `python pipeline.py --approve --run {run}`",
            f"- Reddet ve düzelttir (tümü): `python pipeline.py --reject \"gerekçe\" --run {run}`",
            f"- Yalnızca bir short'u düzelttir: `python pipeline.py --reject \"gerekçe\" --short 2 --run {run}`",
        ]
    if stage in ("budget_stopped", "budget_paused"):
        reason = ctx.state.get("limit_stop", {}).get("reason", "")
        return ["## Neden durdu", "", f"> {reason}" if reason else "", "",
                "## Devam etmek için", "",
                "1. `config/pipeline.json` içinde `gemini_budget_usd_per_week` ya da `elevenlabs` sınırını "
                "bilerek artırın (ya da ElevenLabs kredisinin yenilenmesini bekleyin).",
                f"2. `python pipeline.py --approve --run {run}` — limitler yeniden kontrol edilir; hâlâ "
                "aşılıyorsa devam etmez."]
    if stage == "error":
        return ["## Karar", "", f"- Kaldığı yerden yeniden dene: `python pipeline.py --approve --run {run}`"]
    return []


_LEADING_NUMBER = re.compile(r"^\s*\d+[.)]\s*")


def _topic_section(ctx: RunContext) -> list[str]:
    t, plan = ctx.state["topic"], ctx.state["plan"]
    lines = [
        "## Konu",
        "",
        f"**{t['title']}** — {t.get('company', '')}  ",
        f"Kaynak: {t.get('source', '')}{(' · ' + t['reference']) if t.get('reference') else ''}",
        "",
        plan["topic_summary"],
        "",
    ]
    if ctx.state.get("brief"):
        lines += ["<details><summary>Editör notu (bu çalıştırmaya özel)</summary>", "",
                  ctx.state["brief"].strip(), "", "</details>", ""]
    lines += [
        "## Bölüm planı",
        "",
        "| Gün | Başlık | Odak | Olaylar | Kapanış kancası |",
        "|---|---|---|---|---|",
    ]
    for day, p in zip(plan["days"], plan["parts"]):
        lines.append(f"| {day} | {p['focus_title']} | {p['focus']} | {'<br>'.join(p['key_events'])} | {p['cliffhanger']} |")
    lines += ["", "<details><summary>Hafta sonu uzun videosu taslağı (ikinci aşama)</summary>", ""]
    # Model maddeleri bazen kendisi numaralandırıyor ("1. ..."); çift numarayı önle.
    lines += [f"{i}. {_LEADING_NUMBER.sub('', x)}" for i, x in enumerate(plan.get("long_video_outline", []), 1)]
    lines += ["", "</details>", ""]
    return lines + _plan_verify_section(ctx)


_ICON = {"verified": "✅", "incorrect": "❌", "unverifiable": "⚠️"}


def _source_links(cl: dict) -> str:
    titles = cl.get("source_titles") or [str(n) for n in range(1, len(cl["source_urls"]) + 1)]
    return " ".join(f"[{t}]({u})" for t, u in list(zip(titles, cl["source_urls"]))[:3])


def _grounding_note(ver: dict) -> list[str]:
    if not ver.get("grounded", False):
        return ["", "> ⚠️ Bu turda Google araması YAPILMADI: sonuçlar ve linkler modelin kendi bilgisine "
                    "dayanıyor, arama sonucu değil. Rakamları elle kontrol edin."]
    return ["", f"_{len(ver.get('queries', []))} Google araması yapıldı: "
                + "; ".join(f"“{q}”" for q in ver.get("queries", [])[:6]) + "_"]


def _plan_verify_section(ctx: RunContext) -> list[str]:
    ver = ctx.state.get("plan_verify")
    fixes = ctx.state.get("plan_revisions", [])
    feedback = ctx.state.get("plan_feedback", [])
    if not ver and not feedback:
        return []
    lines = ["## Plan doğrulaması (Doğrulayıcı)", ""]
    if feedback:
        lines += ["Planın önceki sürümü şu gerekçelerle reddedildi; bu plan onlara göre yeniden üretildi:", ""]
        lines += [f"- {r}" for r in feedback] + [""]
    if not ver:
        return lines
    c = ver["counts"]
    lines.append(f"Son tur ({ver['round']}): {c['verified']} doğrulandı, {c['incorrect']} yanlış, "
                 f"{c['unverifiable']} doğrulanamadı.")
    if fixes:
        lines += ["", f"**Doğrulayıcı'nın düzelttirdikleri** ({len(fixes)} revizyon):", ""]
        lines += [f"- {f}" for r in fixes for f in r["feedback"]]
    problems = [cl for cl in ver["claims"] if cl["verdict"] != "verified"]
    if problems:
        lines += ["", "> ⚠️ Son turda hâlâ sorunlu iddialar var; onaylamadan önce kontrol edin.", "",
                  "| Sonuç | Madde | İddia | Not | Kaynak |", "|---|---|---|---|---|"]
        for cl in problems:
            note = (f"doğrusu: {cl['correct']}. " if cl["correct"] else "") + cl["explanation"]
            lines.append(f"| {_ICON.get(cl['verdict'], cl['verdict'])} | {cl['item']} | {cl['claim']} | {note} | {_source_links(cl)} |")
    lines += ["", f"<details><summary>Tüm iddialar ({len(ver['claims'])})</summary>", "",
              "| Sonuç | İddia | Kaynak |", "|---|---|---|"]
    lines += [f"| {_ICON.get(cl['verdict'], cl['verdict'])} | {cl['claim']} | {_source_links(cl)} |" for cl in ver["claims"]]
    lines += ["", "</details>"]
    lines += _grounding_note(ver) + [""]
    return lines


def _short_section(ctx: RunContext, i: int) -> list[str]:
    day = ctx.state["plan"]["days"][i]
    rec = ctx.state.get("shorts", {}).get(str(i), {})
    d = scriptwriter.short_dir(ctx, i)
    lines = [f"## {i + 1}. {day}"]
    if not (d / "script.json").exists():
        return lines + ["", "_Henüz üretilmedi._", ""]
    script: ShortScript = scriptwriter.load(ctx, i)
    qa = (rec.get("qa_rounds") or [None])[-1]
    status = {"passed": "✅ QA geçti", "failed": "❌ QA geçmedi — durduruldu"}.get(rec.get("status"), rec.get("status", ""))
    lines += ["", f"**{script.title}** · {status}", ""]
    if (d / "video.mp4").exists():
        rel = d.relative_to(ctx.dir).as_posix()
        sheets = " · ".join(f"[kareler {n}]({rel}/kareler/{Path(s).name})" for n, s in enumerate(rec.get("sheets", []), 1))
        lines += [f"- Video: [{rel}/video.mp4]({rel}/video.mp4)", f"- Contact sheet: {sheets}"]
    lines += [f"- Hook: {script.hook_type}, kapanış metni: \"{script.cta}\"", ""]

    lines += ["### Script", "", "| # | Cümle | Sahne |", "|---|---|---|"]
    lines += [f"| {n} | {s.narration} | {s.scene_type} |" for n, s in enumerate(script.scenes, 1)]

    ver = rec.get("verify")
    if ver:
        c = ver["counts"]
        lines += ["", f"### Doğrulama (tur {ver['round']}): {c['verified']} doğrulandı, {c['incorrect']} yanlış, "
                      f"{c['unverifiable']} doğrulanamadı", "",
                  "| Sonuç | Sahne | İddia | Not | Kaynak |", "|---|---|---|---|---|"]
        for cl in ver["claims"]:
            note = (f"doğrusu: {cl['correct']}. " if cl["correct"] else "") + cl["explanation"]
            lines.append(f"| {_ICON.get(cl['verdict'], cl['verdict'])} | {cl['scene']} | {cl['claim']} | {note} | {_source_links(cl)} |")
        if ver.get("sources"):
            lines += ["", "<details><summary>Arama kaynakları</summary>", ""]
            lines += [f"- [{s['title'] or s['uri']}]({s['uri']})" for s in ver["sources"]]
            lines += ["", "</details>"]
        if c["incorrect"] or c["unverifiable"]:
            lines += ["", "> ⚠️ Son doğrulama turunda hâlâ sorunlu iddialar var; yayından önce kontrol edin."]
        lines += _grounding_note(ver)

    if qa:
        lines += ["", f"### QA (tur {qa['round']}): ortalama {qa['average']}/5, en düşük {qa['min']}/5", "",
                  "| Ölçüm | Değer | |", "|---|---|---|"]
        lines += [f"| {c['name']} | {c['value']} | {'✅' if c['ok'] else '❌'} |" for c in qa["checks"]]
        lines += ["", "| Kural | Puan | Gerekçe |", "|---|---|---|"]
        lines += [f"| {s['rule']} | {s['score']}/5 | {s['reason']} |" for s in qa["scores"]]
        lines += ["", f"_{qa['summary']}_"]
        if qa.get("violations"):
            lines += ["", "**Tespit edilen ihlaller:**", ""] + [f"- Sahne {v['scene'] or 'genel'}, kural {v['rule']}: {v['what']}" for v in qa["violations"]]
        if qa.get("improvements"):
            lines += ["", "**İyileştirme önerileri:**", ""] + [f"- {x}" for x in qa["improvements"]]
    revs = rec.get("revisions", [])
    if revs:
        lines += ["", f"<details><summary>Revizyon geçmişi ({len(revs)})</summary>", ""]
        for n, r in enumerate(revs, 1):
            lines.append(f"{n}. **{r['source']}**: " + " / ".join(r["feedback"]))
        lines += ["", "</details>"]
    lines.append("")
    return lines


def _failure_report(ctx: RunContext) -> list[str]:
    failed = [(i, rec) for i, rec in sorted(ctx.state.get("shorts", {}).items()) if rec.get("status") == "failed"]
    if not failed:
        return []
    lines = ["## ⚠️ Durdurulan short'lar — rapor", ""]
    for i, rec in failed:
        day = ctx.state["plan"]["days"][int(i)]
        rounds = rec.get("qa_rounds", [])
        lines.append(f"**{day}**: {len(rounds)} QA değerlendirmesi, {rec.get('qa_revisions', 0)} revizyon turu. "
                     f"Neden durdu: {rec.get('stop_reason', '')}")
        last = rounds[-1] if rounds else None
        if last:
            for target, items in last["actions"].items():
                for it in items:
                    lines.append(f"- ({target}) {it}")
        lines.append("")
    return lines


def write(ctx: RunContext) -> Path:
    if ctx.state.get("kind") == "long":
        return write_long(ctx)
    lines = [f"# Haftalık onay — {ctx.dir.name}", "", STAGE_TEXT.get(ctx.stage, ctx.stage), ""]
    lines += _commands(ctx) + [""]
    if ctx.state.get("error"):
        lines += ["## Hata", "", "```", ctx.state["error"], "```", ""]
    if "topic" in ctx.state:
        lines += _failure_report(ctx)
        if ctx.stage in ("topic_review",):
            lines += _topic_section(ctx)
        else:
            if ctx.state.get("shorts"):
                lines += ["## Özet", "", "| Gün | Başlık | QA | Doğrulama |", "|---|---|---|---|"]
                for i, day in enumerate(ctx.state["plan"]["days"]):
                    rec = ctx.state.get("shorts", {}).get(str(i), {})
                    qa = (rec.get("qa_rounds") or [None])[-1]
                    ver = rec.get("verify")
                    d = scriptwriter.short_dir(ctx, i)
                    title = scriptwriter.load(ctx, i).title if (d / "script.json").exists() else "-"
                    lines.append(f"| {day} | {title} | "
                                 f"{('✅' if qa['passed'] else '❌') + ' ' + str(qa['average']) if qa else '-'} | "
                                 f"{('✅ ' + str(ver['counts']['verified']) + ' / ⚠️ ' + str(ver['counts']['incorrect'] + ver['counts']['unverifiable'])) if ver else '-'} |")
                lines.append("")
            for i in range(3):
                lines += _short_section(ctx, i)
            lines += _topic_section(ctx)
    lines += ["## Kullanım ve tahmini maliyet (bu çalıştırma)", "", ctx.cost_report(), "",
              "## Kalan bakiye / kredi", "", limits.balance_report(), "",
              "_Ayrıntılı kararlar ve revizyon geçmişi: [log.md](log.md)._", ""]
    path = ctx.dir / "review.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------- uzun video

LONG_STAGE_TEXT = {
    "long_estimate": "⏸ **ONAY A — tahmin.** Henüz hiçbir API isteği yapılmadı. Onaylarsan script yazılır ve yalnızca yeni iddialar doğrulanır (Gemini).",
    "long_voice_review": "⏸ **ONAY B — ses.** Script hazır ve doğrulandı. Onaylarsan bölüm bölüm ses üretilir (ElevenLabs), video render edilir.",
    "long_producing": "⏳ Ses + render + QA sürüyor (arka planda).",
    "long_final": "⏸ **ONAY C — final.** Video, küçük resim ve açıklama hazır.",
    "long_published": "✅ Yayına hazır klasörüne kopyalandı.",
    "long_postponed": "⛔ **ERTELENDİ — bütçe/kredi yetmiyor.** Onayla aşılamaz; koşullar sağlanınca (yeni hafta/kredi dönemi ya da config) `--approve` yeniden kontrol eder.",
    "long_error": "❌ Hata (ayrıntı log.md'de). `--approve` kaldığı yerden yeniden dener.",
}


def _long_commands(ctx: RunContext) -> list[str]:
    run = ctx.dir.name
    if ctx.state.get("dry_run"):
        return ["## Karar", "", "_Bu bir dry-run: gerçek Gemini/ElevenLabs isteği yapılmadı (sahte istemci). Onay verilmez._"]
    st = ctx.stage
    lines = ["## Karar", ""]
    if st in ("long_estimate", "long_voice_review", "long_final", "long_postponed", "long_error"):
        lines.append(f"- Onayla: `python pipeline.py --approve --run {run}`")
    if st == "long_voice_review":
        lines.append(f"- Script'i gerekçeyle yeniden yazdır: `python pipeline.py --reject \"gerekçe\" --run {run}`")
    return lines


def _long_budget(ctx: RunContext) -> list[str]:
    est, lim = ctx.state.get("estimate", {}), ctx.state.get("limit_check", {})
    if not est:
        return []
    margin = f"%{int(round((est['chars_with_margin'] / max(est['chars'], 1) - 1) * 100))}"
    lines = ["## Tahmini maliyet (API'siz, yerel)", "",
             f"_Kaynak: {'yazılmış script' if est.get('based_on_script') else 'hedef uzunluk'}; Gemini istek maliyetleri "
             f"{est.get('history_n', 0)} geçmiş isteğin ortalamasından._", "",
             "| Kalem | Tahmin |", "|---|---|"]
    lines += [f"| Gemini — {k} | ${v:.3f} |" for k, v in est["gemini_items"].items()]
    lines += [f"| **Gemini toplam** | **${est['gemini_usd']:.2f}** ({margin} payla ${est['gemini_with_margin']:.2f}) |",
              f"| **ElevenLabs** | **{est['chars']:,} karakter** ({margin} payla {est['chars_with_margin']:,}) |", ""]
    if lim:
        el = lim.get("el") or {}
        rows = [f"| Gemini bu hafta harcanan / sınır | ${lim['gemini_spent']:.2f} / ${lim['gemini_limit']:.2f} |",
                f"| Gemini short payı (bu haftanın short'ları {'bitmedi' if lim['short_pending'] else 'bitti'}) | ${lim['gemini_reserve']:.2f} |"]
        if el:
            rows.append(f"| ElevenLabs kalan (sınır {el.get('cap', 0):,}, yenilenme {el.get('reset', '?')}) | {el.get('remaining', 0):,} |")
        else:
            rows.append("| ElevenLabs kalan | okunamadı |")
        rows.append(f"| ElevenLabs short payı (bu hafta {lim['el_current_week']:,} + {lim['el_future_weeks']} hafta x 3 short) | {lim['el_reserve']:,} |")
        if lim.get("el_available") is not None:
            rows.append(f"| ElevenLabs uzun videoya kullanılabilir | {lim['el_available']:,} |")
        rows.append(f"| **Karar** | **{'UYGUN' if lim['ok'] else 'ERTELE'}** |")
        lines += ["## Bütçe kilitleri (short'lar öncelikli)", "", "| | Değer |", "|---|---|"] + rows + [""]
        if lim["reasons"]:
            lines += ["> " + x for x in lim["reasons"]] + [""]
    return lines


def write_long(ctx: RunContext) -> Path:
    from src import commons, tr_numbers
    from src.schemas import LongVideoScript, section_text

    from .long_video import SHORT_LINK_TEXT

    st = ctx.state
    r = st.get("research", {})
    lines = [f"# Uzun video — {ctx.dir.name}", "", LONG_STAGE_TEXT.get(ctx.stage, ctx.stage), ""]
    lines += _long_commands(ctx) + [""]
    if st.get("postponed"):
        lines += ["## Erteleme nedeni", ""] + [f"- {x}" for x in st["postponed"]["reasons"]] + [""]
    if st.get("error"):
        lines += ["## Hata", "", "```", st["error"], "```", ""]
    lines += [f"**Konu:** {r.get('topic', {}).get('title', '')} — kaynak short run'ı `{st.get('source_run', '')}` "
              f"({len(r.get('facts', []))} doğrulanmış olgu, {len(r.get('sources', {}))} kaynak yeniden kullanılıyor)", ""]
    lines += _long_budget(ctx)
    s = st.get("script")
    if s:
        sc = LongVideoScript.model_validate(s)
        desc = st.get("description") or (sc.description + "\n\n(Bölüm zaman damgaları ve fotoğraf atıfları ses üretiminden sonra eklenir.)")
        lines += ["## YouTube", "", f"**Başlık:** {sc.title}", "", "**Açıklama:**", "", "```", desc, "```", "",
                  f"**Etiketler:** {', '.join(sc.tags)}", "",
                  f"**Küçük resim:** {' '.join(x for x in (sc.thumbnail_value, sc.thumbnail_unit) if x) or '-'} · "
                  f"\"{sc.thumbnail_headline}\" + {sc.main_brand} logosu", "",
                  f"**Short açıklamalarına eklenecek:** `{SHORT_LINK_TEXT}`", "",
                  "## Bölümler", "", "| Bölüm | Başlık | Karakter (okunuş) | Sahne |", "|---|---|---|---|"]
        for key, sec in sc.sections():
            lines.append(f"| {key} | {sec.heading or '-'} | {len(tr_numbers.to_spoken(section_text(sec)))} | {len(sec.scenes)} |")
        lines += [""]
        v = st.get("verify")
        if v:
            lines += ["## Doğrulama (araştırma yeniden kullanıldı)", "",
                      f"{v.get('reused', 0)} cümle short'larda doğrulanmış olgularla örtüştü (aranmadı); "
                      f"{v.get('new', 0)} yeni cümle arandı.", ""]
            if v.get("claims"):
                icon = {"verified": "✅", "incorrect": "❌", "unverifiable": "⚠️"}
                lines += ["| Sonuç | İddia | Not |", "|---|---|---|"]
                lines += [f"| {icon.get(c['verdict'], c['verdict'])} | {c['claim']} | {c.get('correct') or c.get('explanation', '')} |"
                          for c in v["claims"]] + [""]
    if st.get("checks"):
        lines += ["## Video", "", f"- Video: `{st.get('video', '')}`", f"- Küçük resim: `{st.get('thumbnail', '')}`", "",
                  "| Ölçüm | Değer | |", "|---|---|---|"]
        lines += [f"| {c['name']} | {c['value']} | {'✅' if c['ok'] else '❌'} |" for c in st["checks"]]
        qa = st.get("qa")
        if qa:
            lines += ["", f"**Görsel QA (1 tur):** {'✅ geçti' if qa['passed'] else '❌ geçmedi'} — ortalama {qa['average']}/5. {qa['summary']}"]
            lines += [f"- Öneri: {x}" for x in qa.get("improvements", [])]
        if st.get("credits"):
            lines += ["", "**Fotoğraf lisansları:**", ""] + [f"- {commons.credit_line(m)}" for m in st["credits"]]
        lines += [""]
    if st.get("dry_run_calls") is not None:
        lines += ["## Dry-run", "", f"Sahte istemciye giden çağrılar ({len(st['dry_run_calls'])}): "
                  + ", ".join(st["dry_run_calls"]) + ". Gerçek Gemini/ElevenLabs isteği: **0**.", ""]
    lines += ["## Kullanım (bu çalıştırma)", "", ctx.cost_report(), "", "## Kalan bakiye / kredi", "",
              limits.balance_report(), "", "_Ayrıntı: [log.md](log.md)._", ""]
    path = ctx.dir / "review.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
