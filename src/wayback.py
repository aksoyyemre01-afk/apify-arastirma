"""Wayback Machine'den şirketin web sitesinin geçmiş bir yıldaki (ör. yahoo.com,
2000) ekran görüntüsünü alır (RULES.md kural 15 - görsel kaynak önceliği b maddesi).

İki adım: (1) archive.org'un ücretsiz "availability" API'siyle en yakın arşivlenmiş
snapshot URL'sini bul, (2) Playwright (headless Chromium, bu ortamda önceden kurulu)
ile o snapshot'ın ekran görüntüsünü al. Şirketin domaini bilinmediği için basit bir
"{şirket}.com" tahminiyle çalışılır - yanlışsa (site yoksa/snapshot bulunamazsa)
None döner ama HER ZAMAN nedenini konsola yazar (kural 5 - hata sessizce
yutulmasın); çağıran taraf None'da bir sonraki kaynağa geçer.
"""

import glob
import os
import re
from pathlib import Path

import requests

_TIMEOUT = 15
_AVAILABILITY_URL = "https://archive.org/wayback/available"

WIDTH = 1080
HEIGHT = 1920


def _guess_domain(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    return f"{slug}.com"


def _find_chromium_executable() -> str | None:
    """PLAYWRIGHT_BROWSERS_PATH altında önceden kurulu bir Chromium ikili dosyası
    varsa yolunu döner (bu tür sabit kurulumlu ortamlarda Playwright'ın kendi sürüm
    beklentisiyle kurulu tarayıcı sürümü uyuşmayabiliyor - executable_path'i elle
    vermek bunu atlatır). Bulunamazsa None döner, Playwright kendi varsayılan
    (indirilmiş/yönetilen) tarayıcısını kullanır."""
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not base or not os.path.isdir(base):
        return None
    for pattern in ("chromium-*/chrome-linux/chrome", "chromium-*/chrome-win/chrome.exe",
                     "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"):
        matches = sorted(glob.glob(os.path.join(base, pattern)))
        if matches:
            return matches[-1]
    return None


def find_snapshot_url(domain: str, year: int) -> str | None:
    try:
        resp = requests.get(
            _AVAILABILITY_URL,
            params={"url": domain, "timestamp": f"{year}0101"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"      [Wayback] availability API isteği başarısız ({domain}): {e}")
        return None
    if resp.status_code != 200:
        print(f"      [Wayback] availability API HTTP {resp.status_code} döndü ({domain})")
        return None
    closest = (resp.json().get("archived_snapshots") or {}).get("closest") or {}
    if closest.get("available"):
        return closest.get("url")
    print(f"      [Wayback] {domain} için {year} civarında arşivlenmiş snapshot bulunamadı")
    return None


def screenshot(url: str, dest_path: Path) -> bool:
    """url'yi headless Chromium ile açıp ekran görüntüsü alır. Başarısız olursa
    NEDENİNİ konsola yazıp False döner (istisna fırlatmaz) - çağıran taraf bunu
    bir sonraki kaynağa geçiş sinyali olarak kullanır."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "      [Wayback] 'playwright' paketi kurulu değil - "
            "'pip install -r requirements.txt' çalıştırdığından emin ol"
        )
        return False

    executable_path = _find_chromium_executable()
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(executable_path=executable_path)
            except Exception as e:
                print(
                    f"      [Wayback] Chromium başlatılamadı ({e}). "
                    "Muhtemelen tarayıcı ikili dosyası eksik - "
                    "'playwright install chromium' çalıştırman gerekiyor."
                )
                return False
            try:
                page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
                page.goto(url, timeout=20000, wait_until="load")
                page.screenshot(path=str(dest_path))
            finally:
                browser.close()
        return dest_path.exists()
    except Exception as e:
        print(f"      [Wayback] ekran görüntüsü alınamadı ({url}): {e}")
        return False


def fetch(
    company: str, dest_dir: Path, index: int, year: int = 2005, exclude_urls: set[str] | None = None
) -> dict | None:
    """company için tahmini domainin `year`e en yakın Wayback snapshot'ını bulup
    ekran görüntüsünü alır. exclude_urls verilirse (kural 7) ve bulunan snapshot
    zaten kullanılmışsa None döner. Bulunursa {'path': Path, 'kind': 'photo',
    'snapshot_url': str} döner, herhangi bir adımda başarısız olursa None -
    her başarısızlık nedeniyle birlikte konsola yazılır."""
    exclude_urls = exclude_urls or set()
    domain = _guess_domain(company)
    print(f"      [Wayback] deneniyor: {domain} (~{year})")
    snapshot_url = find_snapshot_url(domain, year)
    if not snapshot_url:
        return None
    if snapshot_url in exclude_urls:
        print(f"      [Wayback] snapshot zaten kullanılmış: {snapshot_url}")
        return None

    dest = dest_dir / f"wayback_{index:02d}.png"
    if not screenshot(snapshot_url, dest):
        return None
    return {"path": dest, "kind": "photo", "snapshot_url": snapshot_url}
