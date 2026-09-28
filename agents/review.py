"""review.md: iki onay noktasının tek özet dosyası (konu onayı ve yayın öncesi final onayı)."""

from pathlib import Path

from src.schemas import ShortScript

from . import scriptwriter
from .base import CONFIG, RunContext

STAGE_TEXT = {
    "topic_review": "⏸ **Konu onayı bekleniyor.**",
    "producing": "⏳ Üretim sürüyor (arka planda). Bittiğinde bu dosya güncellenir ve bildirim gelir.",
    "final_review": "⏸ **Yayın öncesi final onayı bekleniyor.**",
    "budget_paused": "⏸ **Bütçe sınırına ulaşıldı; devam etmek için onay gerekiyor.**",
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
        ]
    if stage == "final_review":
        return [
            "## Karar",
            "",
            f"- Tümünü onayla (yayına hazır klasörüne kopyalanır): `python pipeline.py --approve --run {run}`",
            f"- Reddet ve düzelttir (tümü): `python pipeline.py --reject \"gerekçe\" --run {run}`",
            f"- Yalnızca bir short'u düzelttir: `python pipeline.py --reject \"gerekçe\" --short 2 --run {run}`",
        ]
    if stage == "budget_paused":
        return ["## Karar", "", f"- Bütçeyi bir hafta sınırı kadar artırıp devam et: `python pipeline.py --approve --run {run}`"]
    if stage == "error":
        return ["## Karar", "", f"- Kaldığı yerden yeniden dene: `python pipeline.py --approve --run {run}`"]
    return []


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
        "## Bölüm planı",
        "",
        "| Gün | Başlık | Odak | Olaylar | Kapanış kancası |",
        "|---|---|---|---|---|",
    ]
    for day, p in zip(plan["days"], plan["parts"]):
        lines.append(f"| {day} | {p['focus_title']} | {p['focus']} | {'<br>'.join(p['key_events'])} | {p['cliffhanger']} |")
    lines += ["", "<details><summary>Hafta sonu uzun videosu taslağı (ikinci aşama)</summary>", ""]
    lines += [f"{i}. {x}" for i, x in enumerate(plan.get("long_video_outline", []), 1)]
    lines += ["", "</details>", ""]
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
        icon = {"verified": "✅", "incorrect": "❌", "unverifiable": "⚠️"}
        for cl in ver["claims"]:
            titles = cl.get("source_titles") or [str(n) for n in range(1, len(cl["source_urls"]) + 1)]
            src = " ".join(f"[{t}]({u})" for t, u in list(zip(titles, cl["source_urls"]))[:3])
            note = (f"doğrusu: {cl['correct']}. " if cl["correct"] else "") + cl["explanation"]
            lines.append(f"| {icon.get(cl['verdict'], cl['verdict'])} | {cl['scene']} | {cl['claim']} | {note} | {src} |")
        if ver.get("sources"):
            lines += ["", "<details><summary>Arama kaynakları</summary>", ""]
            lines += [f"- [{s['title'] or s['uri']}]({s['uri']})" for s in ver["sources"]]
            lines += ["", "</details>"]
        if c["incorrect"] or c["unverifiable"]:
            lines += ["", "> ⚠️ Son doğrulama turunda hâlâ sorunlu iddialar var; yayından önce kontrol edin."]
        if not ver.get("grounded", False):
            lines += ["", "> ⚠️ Bu turda Google araması YAPILMADI: sonuçlar ve linkler modelin kendi bilgisine "
                          "dayanıyor, arama sonucu değil. Rakamları elle kontrol edin."]
        else:
            lines += ["", f"_{len(ver.get('queries', []))} Google araması yapıldı: "
                          + "; ".join(f"“{q}”" for q in ver.get("queries", [])[:6]) + "_"]

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
    lines += ["## Kullanım ve tahmini maliyet", "", ctx.cost_report(), "",
              f"_Haftalık bütçe sınırı: ${float(CONFIG.get('budget_usd_per_week', 2.0)) + ctx.budget_extra:.2f}. "
              f"Ayrıntılı kararlar ve revizyon geçmişi: [log.md](log.md)._", ""]
    path = ctx.dir / "review.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
