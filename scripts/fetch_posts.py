#!/usr/bin/env python3
"""
LinkedIn post toplayici - Apify `harvestapi/linkedin-post-search` aktorunu kullanir.

Iki stratejiyi birlikte calistirir:
  1. Genis anahtar kelime taramasi (kesif)  -> organik viral postlari yakalar
  2. Yuksek takipcili yazar taramasi        -> buyuk hesaplarin postlarini garantiler

LinkedIn arama API'si "like sayisina gore sirala" secenegi sunmadigi icin
mumkun oldugunca genis bir ornek toplanip siralama yerelde yapilir.

Kullanim:  APIFY_TOKEN=... python3 scripts/fetch_posts.py
"""
import json
import os
import sys
import time
import urllib.request

ACTOR = "harvestapi~linkedin-post-search"
BASE = "https://api.apify.com/v2"
TOKEN = os.environ.get("APIFY_TOKEN")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Son 10 gun. Aktor "postedLimitDate" ile bu tarihten bugune kadarki postlari getirir.
SINCE_DATE = os.environ.get("SINCE_DATE", "2026-08-31")

# Faz 1: genis konu taramasi (EN + TR)
KEYWORD_QUERIES = [
    "artificial intelligence", "leadership", "hiring", "layoffs",
    "startup", "career advice", "remote work", "marketing",
    "productivity", "founder", "job search", "CEO",
    "AI agents", "success", "management", "entrepreneurship",
    "yapay zeka", "kariyer", "liderlik", "girisimcilik",
]

# Faz 2: yuksek erisimli, duzenli paylasan hesaplar (authorUrls maxItems = 10)
AUTHOR_BATCHES = [
    [
        "https://www.linkedin.com/in/williamhgates",
        "https://www.linkedin.com/in/justinwelsh",
        "https://www.linkedin.com/in/simonsinek",
        "https://www.linkedin.com/in/adammgrant",
        "https://www.linkedin.com/in/satyanadella",
        "https://www.linkedin.com/in/rbranson",
        "https://www.linkedin.com/in/gary-vaynerchuk",
        "https://www.linkedin.com/in/reidhoffman",
        "https://www.linkedin.com/in/stevenbartlett-123",
        "https://www.linkedin.com/in/melindagates",
    ],
    [
        "https://www.linkedin.com/in/jeffweiner08",
        "https://www.linkedin.com/in/ariannahuffington",
        "https://www.linkedin.com/in/andrewyng",
        "https://www.linkedin.com/in/allie-k-miller",
        "https://www.linkedin.com/in/lara-acosta",
        "https://www.linkedin.com/in/hnshah",
        "https://www.linkedin.com/in/danshipper",
        "https://www.linkedin.com/in/sahilbloom",
        "https://www.linkedin.com/in/codie-sanchez",
        "https://www.linkedin.com/in/brenebrown",
    ],
]


def api(method, path, payload=None, timeout=120):
    url = f"{BASE}{path}{'&' if '?' in path else '?'}token={TOKEN}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def start_run(run_input):
    return api("POST", f"/acts/{ACTOR}/runs", run_input)["data"]["id"]


def wait_for(run_ids, poll=15, max_wait=2400):
    """Birden fazla run'i paralel bekler, biten run'larin dataset id'lerini dondurur."""
    pending = dict(run_ids)  # run_id -> label
    done = {}
    waited = 0
    while pending and waited < max_wait:
        for rid in list(pending):
            d = api("GET", f"/actor-runs/{rid}")["data"]
            if d["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                label = pending.pop(rid)
                done[rid] = (label, d["status"], d["defaultDatasetId"])
                usage = (d.get("usageTotalUsd") or 0)
                print(f"  [{d['status']}] {label}  (${usage:.3f})", flush=True)
        if pending:
            time.sleep(poll)
            waited += poll
    for rid, label in pending.items():
        print(f"  [TIMEOUT-WAIT] {label} (run {rid} hala calisiyor)", flush=True)
    return done


def fetch_items(dataset_id):
    out, offset = [], 0
    while True:
        batch = api("GET", f"/datasets/{dataset_id}/items?limit=1000&offset={offset}")
        if not batch:
            break
        out.extend(batch)
        offset += len(batch)
        if len(batch) < 1000:
            break
    return out


def main():
    if not TOKEN:
        sys.exit("APIFY_TOKEN tanimli degil.")
    os.makedirs(OUT_DIR, exist_ok=True)

    runs = {}

    # Faz 1 - anahtar kelimeler. Tek run'da coklu query; maxPosts query BASINA uygulanir.
    rid = start_run({
        "searchQueries": KEYWORD_QUERIES,
        "maxPosts": int(os.environ.get("MAX_PER_QUERY", "50")),
        "postedLimitDate": SINCE_DATE,
        "sortBy": "relevance",
        "profileScraperMode": "short",
        "scrapeReactions": False,
    })
    runs[rid] = f"keywords ({len(KEYWORD_QUERIES)} sorgu)"

    # Faz 2 - yazar bazli
    for i, batch in enumerate(AUTHOR_BATCHES, 1):
        rid = start_run({
            "authorUrls": batch,
            "maxPosts": int(os.environ.get("MAX_PER_AUTHOR_BATCH", "120")),
            "postedLimitDate": SINCE_DATE,
            "sortBy": "date",
            "profileScraperMode": "short",
            "scrapeReactions": False,
        })
        runs[rid] = f"authors batch {i} ({len(batch)} hesap)"

    print(f"{len(runs)} run baslatildi, bekleniyor...", flush=True)
    for rid, label in runs.items():
        print(f"  -> {label}: {rid}", flush=True)

    done = wait_for(runs)

    all_items = []
    for rid, (label, status, ds) in done.items():
        if status != "SUCCEEDED" or not ds:
            continue
        items = fetch_items(ds)
        print(f"  {label}: {len(items)} post", flush=True)
        for it in items:
            it["_source"] = label
        all_items.extend(items)

    path = os.path.join(OUT_DIR, "raw_posts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=1)
    print(f"\nToplam {len(all_items)} ham post -> {path}")


if __name__ == "__main__":
    main()
