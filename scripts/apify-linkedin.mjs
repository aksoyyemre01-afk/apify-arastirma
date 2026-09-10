#!/usr/bin/env node
/**
 * LinkedIn Post Scraper (Apify) — arama, calistirma ve etkilesim analizi.
 *
 * Kullanim:
 *   export APIFY_TOKEN=apify_api_xxx
 *   node scripts/apify-linkedin.mjs actors                 # Store'da LinkedIn post scraper'lari listele
 *   node scripts/apify-linkedin.mjs run "yapay zeka" "ai automation"
 *   node scripts/apify-linkedin.mjs analyze data/posts.json
 *
 * Not: APIFY_TOKEN'i asla koda gomme, ortam degiskeni olarak ver.
 */

const API = 'https://api.apify.com/v2';
const TOKEN = process.env.APIFY_TOKEN;

// Store'daki LinkedIn post scraper aktoru. Farkli bir aktor kullanmak icin:
//   export APIFY_ACTOR=kullanici~aktor-adi
const ACTOR = process.env.APIFY_ACTOR || 'apimaestro~linkedin-post-search-scraper';

// Kac gun geriye bakilacak (varsayilan: son 30 gun = "bu ay")
const DAYS = Number(process.env.DAYS || 30);

function need(v, msg) {
  if (!v) {
    console.error(msg);
    process.exit(1);
  }
}

async function api(path, opts = {}) {
  const url = `${API}${path}${path.includes('?') ? '&' : '?'}token=${TOKEN}`;
  const res = await fetch(url, {
    ...opts,
    headers: { 'content-type': 'application/json', ...(opts.headers || {}) },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status} ${path}\n${text.slice(0, 800)}`);
  return text ? JSON.parse(text) : null;
}

/* ------------------------------------------------------------------ */
/* 1) Store'da uygun aktoru bul                                        */
/* ------------------------------------------------------------------ */
async function listActors() {
  need(TOKEN, 'APIFY_TOKEN tanimli degil.');
  const { data } = await api('/store?search=linkedin%20post&limit=50');
  const rows = (data.items || [])
    .filter((a) => /linkedin/i.test(`${a.name} ${a.title}`))
    .map((a) => ({
      id: `${a.username}~${a.name}`,
      title: a.title,
      runs: a.stats?.totalRuns ?? 0,
      users: a.stats?.totalUsers ?? 0,
      pricing: a.currentPricingInfo?.pricingModel || 'n/a',
    }))
    .sort((a, b) => b.users - a.users);

  console.table(rows.slice(0, 25));
  console.log('\nSectigin aktoru soyle kullan:  export APIFY_ACTOR=<id>');
}

/* ------------------------------------------------------------------ */
/* 2) Aktoru calistir ve sonuclari indir                               */
/* ------------------------------------------------------------------ */
async function run(keywords) {
  need(TOKEN, 'APIFY_TOKEN tanimli degil.');
  need(keywords.length, 'En az bir anahtar kelime ver. Ornek: node scripts/apify-linkedin.mjs run "yapay zeka"');

  // Cogu LinkedIn post scraper'i bu alanlari kabul eder. Aktorun Input
  // sekmasindaki alan adlari farkliysa burayi ona gore duzelt.
  const input = {
    keywords,
    searchQueries: keywords,
    queries: keywords,
    datePosted: 'past-month',
    postedLimit: 'month',
    sortBy: 'relevance',
    maxItems: Number(process.env.MAX_ITEMS || 200),
    maxPosts: Number(process.env.MAX_ITEMS || 200),
  };

  console.log(`Aktor calistiriliyor: ${ACTOR}`);
  const run = await api(`/acts/${ACTOR}/runs?waitForFinish=300`, {
    method: 'POST',
    body: JSON.stringify(input),
  });

  const runId = run.data.id;
  let status = run.data.status;
  while (status === 'RUNNING' || status === 'READY') {
    await new Promise((r) => setTimeout(r, 10_000));
    const cur = await api(`/actor-runs/${runId}`);
    status = cur.data.status;
    console.log(`  ... ${status}`);
  }
  if (status !== 'SUCCEEDED') throw new Error(`Run bitti ama durum: ${status}`);

  const dsId = run.data.defaultDatasetId;
  const items = await api(`/datasets/${dsId}/items?clean=true&limit=1000`);
  const { writeFileSync, mkdirSync } = await import('node:fs');
  mkdirSync('data', { recursive: true });
  writeFileSync('data/posts.json', JSON.stringify(items, null, 2));
  console.log(`${items.length} gonderi kaydedildi -> data/posts.json`);
  analyzeItems(items);
}

/* ------------------------------------------------------------------ */
/* 3) Etkilesim analizi                                                */
/* ------------------------------------------------------------------ */
const num = (...cands) => {
  for (const c of cands) {
    const n = Number(c);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return 0;
};

function normalize(p) {
  const text = p.text || p.content || p.postText || p.description || '';
  const likes = num(p.numLikes, p.likesCount, p.reactionsCount, p.likes, p.socialCount?.numLikes);
  const comments = num(p.numComments, p.commentsCount, p.comments, p.socialCount?.numComments);
  const shares = num(p.numShares, p.sharesCount, p.reposts, p.socialCount?.numShares);
  const date = p.postedAt || p.publishedAt || p.date || p.time || p.postedAtISO || null;
  return {
    url: p.url || p.postUrl || p.link || '',
    author: p.author?.name || p.authorName || p.author || '',
    date,
    text,
    likes,
    comments,
    shares,
    // Yorum ve paylasim, LinkedIn algoritmasinda begeniden agir basar.
    engagement: likes + comments * 3 + shares * 5,
    words: text.trim().split(/\s+/).filter(Boolean).length,
    lines: text.split('\n').filter((l) => l.trim()).length,
    hashtags: (text.match(/#[\p{L}\p{N}_]+/gu) || []).map((h) => h.toLowerCase()),
    hasQuestion: /\?/.test(text),
    hasList: /^\s*([-•*\d]|[→✅✔])/m.test(text),
    hasEmoji: /\p{Extended_Pictographic}/u.test(text),
    hasCTA: /(ne dusunuyorsun|yorumlarda|comment below|what do you think|dm|follow|takip)/i.test(text),
    hook: text.split('\n')[0]?.slice(0, 120) || '',
  };
}

function classify(p) {
  const t = p.text.toLowerCase();
  if (/(ogrendim|dersim|hata yaptim|i failed|lesson|mistake|yil once|years ago)/.test(t)) return 'Kisisel hikaye / ders';
  if (p.hasList && p.lines >= 6) return 'Liste / cerceve (framework)';
  if (/(%|\bx\b|\d+\s*(kat|adet|gun|saat)|\$\d|\d+k\b)/.test(t) && /(sonuc|result|buyu|grew|artis)/.test(t)) return 'Vaka calismasi / sayilar';
  if (/(katilmiyorum|unpopular|yanlis|myth|herkes .* diyor|kimse soylemiyor)/.test(t)) return 'Karsit gorus / provokasyon';
  if (/(nasil|how to|adim adim|step by step|rehber|guide)/.test(t)) return 'Nasil yapilir / rehber';
  if (p.hasQuestion && p.words < 80) return 'Soru / tartisma acici';
  if (/(duyur|announc|lansman|launch|katildim|joining|yeni rol)/.test(t)) return 'Duyuru / kilometre tasi';
  return 'Diger / gozlem';
}

function analyzeItems(items) {
  const cutoff = Date.now() - DAYS * 864e5;
  const posts = items
    .map(normalize)
    .filter((p) => p.text.length > 40)
    .filter((p) => !p.date || new Date(p.date).getTime() >= cutoff)
    .sort((a, b) => b.engagement - a.engagement);

  if (!posts.length) return console.log('Filtreden gecen gonderi yok.');

  const top = posts.slice(0, Math.max(10, Math.ceil(posts.length * 0.2)));

  const byType = {};
  for (const p of top) {
    const t = classify(p);
    byType[t] = byType[t] || { adet: 0, toplam: 0 };
    byType[t].adet++;
    byType[t].toplam += p.engagement;
  }

  console.log(`\n=== SON ${DAYS} GUN — EN COK TUTAN ICERIK TIPLERI (n=${top.length}) ===`);
  console.table(
    Object.entries(byType)
      .map(([tip, v]) => ({ tip, adet: v.adet, ortEtkilesim: Math.round(v.toplam / v.adet) }))
      .sort((a, b) => b.ortEtkilesim - a.ortEtkilesim)
  );

  const avg = (k) => Math.round(top.reduce((s, p) => s + p[k], 0) / top.length);
  const pct = (k) => Math.round((top.filter((p) => p[k]).length / top.length) * 100);
  console.log('\n=== BICIM / TON SINYALLERI (top %20) ===');
  console.table([
    { sinyal: 'ort. kelime', deger: avg('words') },
    { sinyal: 'ort. satir', deger: avg('lines') },
    { sinyal: 'soru iceren %', deger: pct('hasQuestion') },
    { sinyal: 'liste iceren %', deger: pct('hasList') },
    { sinyal: 'emoji iceren %', deger: pct('hasEmoji') },
    { sinyal: 'CTA iceren %', deger: pct('hasCTA') },
    { sinyal: 'ort. hashtag', deger: (top.reduce((s, p) => s + p.hashtags.length, 0) / top.length).toFixed(1) },
  ]);

  const tags = {};
  for (const p of top) for (const h of new Set(p.hashtags)) tags[h] = (tags[h] || 0) + 1;
  console.log('\n=== EN COK GECEN HASHTAGLER ===');
  console.table(
    Object.entries(tags)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 25)
      .map(([hashtag, adet]) => ({ hashtag, adet }))
  );

  console.log('\n=== EN IYI 15 ACILIS CUMLESI (hook) ===');
  top.slice(0, 15).forEach((p, i) => {
    console.log(`${String(i + 1).padStart(2)}. [${p.engagement}] ${p.hook.replace(/\s+/g, ' ')}`);
    if (p.url) console.log(`    ${p.url}`);
  });
}

/* ------------------------------------------------------------------ */
const [cmd, ...rest] = process.argv.slice(2);
const main = async () => {
  if (cmd === 'actors') return listActors();
  if (cmd === 'run') return run(rest);
  if (cmd === 'analyze') {
    const { readFileSync } = await import('node:fs');
    return analyzeItems(JSON.parse(readFileSync(rest[0] || 'data/posts.json', 'utf8')));
  }
  console.log('Komutlar: actors | run <anahtar kelime...> | analyze [dosya.json]');
};
main().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
