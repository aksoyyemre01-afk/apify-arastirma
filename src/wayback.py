"""Wayback Machine'den şirketin web sitesinin geçmiş bir yıldaki (ör. yahoo.com,
2000) ekran görüntüsünü alır (RULES.md kural 15 - görsel kaynak önceliği b maddesi).

İki adım: (1) archive.org'un ücretsiz "availability" API'siyle en yakın arşivlenmiş
snapshot URL'sini bul, (2) Playwright (headless Chromium, bu ortamda önceden kurulu)
ile o snapshot'ın ekran görüntüsünü al. Şirketin domaini bilinmediği için basit bir
"{şirket}.com" tahminiyle çalışılır - yanlışsa (site yoksa/snapshot bulunamazsa)
sessizce None döner, çağıran taraf bir sonraki kaynağa geçer.
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
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    closest = (resp.json().get("archived_snapshots") or {}).get("closest") or {}
    if closest.get("available"):
        return closest.get("url")
    return None


def screenshot(url: str, dest_path: Path) -> bool:
    """url'yi headless Chromium ile açıp ekran görüntüsü alır. Playwright/Chromium
    kullanılamazsa (paket eksik, tarayıcı bulunamadı, sayfa zaman aşımı vb.) False
    döner - istisna fırlatmaz, çağıran taraf bunu bir sonraki kaynağa geçiş sinyali
    olarak kullanır."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=_find_chromium_executable())
            try:
                page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
                page.goto(url, timeout=20000, wait_until="load")
                page.screenshot(path=str(dest_path))
            finally:
                browser.close()
        return dest_path.exists()
    except Exception:
        return False


def fetch(company: str, dest_dir: Path, index: int, year: int = 2005) -> dict | None:
    """company için tahmini domainin `year`e en yakın Wayback snapshot'ını bulup
    ekran görüntüsünü alır. Bulunursa {'path': Path, 'kind': 'photo',
    'snapshot_url': str} döner, herhangi bir adımda başarısız olursa None."""
    domain = _guess_domain(company)
    snapshot_url = find_snapshot_url(domain, year)
    if not snapshot_url:
        return None

    dest = dest_dir / f"wayback_{index:02d}.png"
    if not screenshot(snapshot_url, dest):
        return None
    return {"path": dest, "kind": "photo", "snapshot_url": snapshot_url}
