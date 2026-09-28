"""Eleştirmen (QA) kalibrasyon testi.

Aynı dry-run script'inden iki video üretir (Gemini/ElevenLabs gerektirmez; ses sessiz,
kelime zamanları tahmini):
- temiz: normal render - Eleştirmen GEÇİRMELİ (yanlış alarm kontrolü);
- bozuk: planlanmış sahnelere kasıtlı hatalar eklenmiş render - Eleştirmen her hatayı
  doğru kuralda (ve mümkünse doğru sahnede) YAKALAMALI:
    * alakasız logo      -> kural 1 veya 2
    * seslendirmeyle çelişen rakam -> kural 1
    * 5 sn'yi aşan sahne -> kural 5 (ayrıca kodla ölçülen "sahne <= 3 sn" kontrolü)
    * yapışık altyazı    -> kural 6
Her iki videoda en az 2 iyileştirme önerisi beklenir. Hatalar sahne tipine göre seçilir;
hiçbir konuya özgü değildir.

Çalıştırma (her biri ~1 görsel Gemini isteği, toplam ~0,07 $):
    python tests/test_critic_calibration.py            # render + puanlama + rapor
    python tests/test_critic_calibration.py --reuse    # videolar varsa yeniden render etme
    pytest tests/test_critic_calibration.py            # GEMINI_API_KEY yoksa atlanır
Rapor: tests/_calibration/report.json
"""

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORK = ROOT / "tests" / "_calibration"
TOPIC_ID = "nokia"
LOGO_DIR = ROOT / "assets" / "logos"
LONG_SCENE_SECONDS = 5.5


# ---------------------------------------------------------------------------- fixture

def _make_source(dest: Path):
    import run as run_module
    from src import research
    from src.schemas import ShortScript

    topic = {**{t["id"]: t for t in research.load_bank()}[TOPIC_ID], "reference": "", "source": "evergreen"}
    script: ShortScript = run_module._dry_run_short(topic)
    dest.mkdir(parents=True, exist_ok=True)
    run_module._save_script(dest, topic, script, None)
    run_module._silent_audio_with_timings(script.narration_full, dest)
    return script


def sabotage(props: dict, files: dict, defects: list[dict], brands: set[str]) -> None:
    """Planlanmış sahnelere kasıtlı hatalar ekler; beklenen tespitleri `defects`e yazar.
    brands: script'te geçen tüm markaların slug'ları (alakasız logo bunların dışından seçilir)."""
    scenes, fps = props["scenes"], props["fps"]

    # 1) 5 sn'yi aşan sahne: ortalardaki ilk timeline/quote sahnesi, sonraki sahneleri yutar.
    li = next(i for i, s in enumerate(scenes) if i >= 2 and s["type"] in ("timeline", "quote"))
    while scenes[li]["durationInFrames"] < LONG_SCENE_SECONDS * fps and li + 1 < len(scenes):
        scenes[li]["durationInFrames"] += scenes.pop(li + 1)["durationInFrames"]

    # 2) Çelişen rakam: sayısal değerli ilk big_number (açılış sahnesi hariç).
    ni = next(i for i, s in enumerate(scenes) if i > 0 and s["type"] == "big_number" and s["value"].strip().isdigit())
    real = scenes[ni]["value"]
    wrong = str(int(real) * 4 + 3)
    scenes[ni]["value"] = wrong

    # 3) Alakasız logo: reveal sonrası ilk logo_intro'ya, videoda geçmeyen bir markanın logosu.
    gi = next(i for i, s in enumerate(scenes) if s["type"] == "logo_intro" and s.get("logo"))
    decoy = next(p for p in sorted(LOGO_DIR.glob("*.svg")) if p.stem not in brands)
    files[f"logos/{decoy.name}"] = decoy
    scenes[gi]["logo"] = {"name": decoy.stem, "src": f"logos/{decoy.name}", "hidden": False, "revealAt": None}
    scenes[gi]["chips"] = []

    # 4) Yapışık altyazı: her sayfadaki kelimeler boşluksuz tek kelimeye birleşir.
    for page in props["captions"]:
        if len(page["words"]) > 1:
            w = page["words"]
            page["words"] = [{"text": "".join(x["text"] for x in w), "start": w[0]["start"], "end": w[-1]["end"]}]

    defects += [
        {"id": "uzun_sahne", "rules": [5], "scene": li + 1, "keywords": ["uzun", "saniye", " sn", "süre"],
         "note": f"sahne {li + 1}: {scenes[li]['durationInFrames'] / fps:.1f} sn"},
        {"id": "celisen_rakam", "rules": [1], "scene": ni + 1, "keywords": [wrong],
         "note": f"sahne {ni + 1}: ekranda {wrong}, seslendirmede {real}"},
        {"id": "alakasiz_logo", "rules": [1, 2], "scene": gi + 1, "keywords": ["logo", decoy.stem.lower()],
         "note": f"sahne {gi + 1}: {decoy.stem} logosu"},
        {"id": "yapisik_altyazi", "rules": [6], "scene": None,
         "keywords": ["altyazı", "bitişik", "boşluk", "yapışık", "birleşik"], "note": "tüm altyazı sayfaları"},
    ]


def _render(d: Path, mutate=None):
    from agents import director
    from src import renderer

    video = renderer.render(d, mutate=mutate)
    director.contact_sheets(d, video)
    return video


# ---------------------------------------------------------------------------- değerlendirme

def _detected(defect: dict, critique) -> tuple[bool, str]:
    """Bir hata; ihlal listesinde (doğru kural + doğru sahne ya da anahtar kelime) veya ilgili
    kuralın <= 3 puanlı gerekçesinde geçiyorsa yakalanmış sayılır."""
    for v in critique.violations:
        if v.rule in defect["rules"] and ((defect["scene"] and v.scene == defect["scene"])
                                           or any(k.lower() in v.what.lower() for k in defect["keywords"])):
            return True, f"ihlal (kural {v.rule}, sahne {v.scene}): {v.what[:140]}"
    for s in critique.scores:
        if s.rule not in defect["rules"] or s.score > 3:
            continue
        text = (s.reason + " " + s.fix).lower()
        if (defect["scene"] and defect["scene"] in s.scenes) or any(k.lower() in text for k in defect["keywords"]):
            return True, f"kural {s.rule} = {s.score}/5: {s.reason[:140]}"
    related = [f"kural {s.rule}={s.score}" for s in critique.scores if s.rule in defect["rules"]]
    return False, "yakalanmadı (" + ", ".join(related) + ")"


def _passes(critique) -> tuple[bool, float, int]:
    from agents.base import CONFIG

    qa = CONFIG.get("qa", {})
    scores = [s.score for s in critique.scores]
    avg = sum(scores) / len(scores) if scores else 0
    ok = bool(scores) and min(scores) >= float(qa.get("min_rule_score", 3)) and avg >= float(qa.get("min_average_score", 4))
    return ok, round(avg, 2), min(scores) if scores else 0


def run_calibration(reuse: bool = False) -> dict:
    from agents import critic
    from src.schemas import ShortScript

    clean, broken = WORK / "temiz", WORK / "bozuk"
    defects: list[dict] = []
    if not (reuse and (clean / "video.mp4").exists() and (broken / "video.mp4").exists()
            and (WORK / "defects.json").exists()):
        if WORK.exists():
            shutil.rmtree(WORK)
        script = _make_source(clean)
        shutil.copytree(clean, broken)
        print("Temiz video render ediliyor...")
        _render(clean)
        print("Bozuk video render ediliyor...")
        from src.utils import slugify

        brands = {slugify(b) for s in script.scenes for b in (s.brand, s.left_brand, s.right_brand) if b}
        brands.add(slugify(script.main_brand))
        _render(broken, mutate=lambda p, f: sabotage(p, f, defects, brands))
        (WORK / "defects.json").write_text(json.dumps(defects, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        # Videolar yeniden kullanılsa da kareler güncel kare planıyla yeniden çıkarılır.
        from agents import director

        for d in (clean, broken):
            director.contact_sheets(d, d / "video.mp4")
    defects = json.loads((WORK / "defects.json").read_text(encoding="utf-8"))

    report = {"defects": [], "clean": {}, "broken": {}}
    for name, d in (("clean", clean), ("broken", broken)):
        script = ShortScript.model_validate(json.loads((d / "script.json").read_text(encoding="utf-8")))
        crit = critic.score_dir(d, script)
        checks = critic.measure_dir(d, script)
        ok, avg, mn = _passes(crit)
        report[name] = {
            "passes_vision": ok, "average": avg, "min": mn, "improvements": crit.improvements,
            "scores": [s.model_dump() for s in crit.scores],
            "violations": [v.model_dump() for v in crit.violations],
            "scene_check": next(c for c in checks if "sahne" in c["name"].lower()),
        }
        if name == "broken":
            for df in defects:
                hit, why = _detected(df, crit)
                report["defects"].append({**df, "detected": hit, "evidence": why})

    ok_all = (report["clean"]["passes_vision"] and not report["broken"]["passes_vision"]
              and all(x["detected"] for x in report["defects"])
              and len(report["clean"]["improvements"]) >= 2 and len(report["broken"]["improvements"]) >= 2)
    report["ok"] = ok_all
    (WORK / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nTemiz video : {'GEÇTİ' if report['clean']['passes_vision'] else 'KALDI (yanlış alarm!)'} "
          f"(ort {report['clean']['average']}, min {report['clean']['min']}, "
          f"öneri {len(report['clean']['improvements'])})")
    print(f"Bozuk video : {'KALDI' if not report['broken']['passes_vision'] else 'GEÇTİ (hatalar kaçtı!)'} "
          f"(ort {report['broken']['average']}, min {report['broken']['min']}, "
          f"öneri {len(report['broken']['improvements'])}); kodla sahne kontrolü: "
          f"{'yakaladı' if not report['broken']['scene_check']['ok'] else 'yakalamadı'}")
    for x in report["defects"]:
        print(f"  [{'✓' if x['detected'] else '✗'}] {x['id']:<16} {x['note']:<40} -> {x['evidence']}")
    print(f"\nKALİBRASYON: {'BAŞARILI' if ok_all else 'BAŞARISIZ'}  (rapor: {WORK / 'report.json'})")
    return report


def test_critic_calibration():
    """pytest: GEMINI_API_KEY yoksa atlanır (render + 2 görsel Gemini isteği gerektirir)."""
    if not os.environ.get("GEMINI_API_KEY"):
        import pytest

        pytest.skip("GEMINI_API_KEY yok")
    assert run_calibration(reuse=True)["ok"]


if __name__ == "__main__":
    result = run_calibration(reuse="--reuse" in sys.argv)
    sys.exit(0 if result["ok"] else 1)
