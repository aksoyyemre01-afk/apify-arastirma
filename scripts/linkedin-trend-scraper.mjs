#!/usr/bin/env node
/**
 * LinkedIn trend research via Apify.
 *
 * Usage:
 *   export APIFY_TOKEN=apify_api_xxx
 *
 *   node scripts/linkedin-trend-scraper.mjs search "linkedin post"
 *   node scripts/linkedin-trend-scraper.mjs run <actorId> [inputFile.json]
 *   node scripts/linkedin-trend-scraper.mjs analyze data/posts.json
 *
 * `search`  -> lists LinkedIn post scrapers in the Apify Store with their exact actor IDs.
 * `run`     -> starts the actor, waits for it, downloads the dataset to data/posts.json.
 * `analyze` -> turns a raw dataset into content-type / tone / hashtag statistics.
 *
 * The token is never written to disk or to the repo: it is read from APIFY_TOKEN only.
 */

const TOKEN = process.env.APIFY_TOKEN;
const API = 'https://api.apify.com/v2';

function requireToken() {
  if (!TOKEN) {
    console.error('APIFY_TOKEN is not set. Run: export APIFY_TOKEN=apify_api_...');
    process.exit(1);
  }
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`${options.method || 'GET'} ${path} -> ${res.status} ${await res.text()}`);
  }
  return res.json();
}

/* ------------------------------------------------------------------ search */

async function search(term = 'linkedin post') {
  requireToken();
  const { data } = await api(`/store?search=${encodeURIComponent(term)}&limit=30`);
  const rows = data.items
    .filter((a) => /linkedin/i.test(`${a.name} ${a.title}`))
    .map((a) => ({
      actorId: `${a.username}/${a.name}`,
      title: a.title,
      users: a.stats?.totalUsers ?? 0,
      runsLast30d: a.stats?.totalRuns ?? 0,
      pricing: a.currentPricingInfo?.pricingModel ?? 'unknown',
    }))
    .sort((a, b) => b.users - a.users);
  console.table(rows);
  console.log('\nPick an actorId above, then:\n  node scripts/linkedin-trend-scraper.mjs run <actorId> input.json');
}

/* --------------------------------------------------------------------- run */

/** Default input; most LinkedIn post scrapers accept some subset of these keys. */
function defaultInput() {
  const now = new Date();
  const monthStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  return {
    // keyword-search style actors
    keywords: ['AI automation', 'web scraping', 'data', 'startup'],
    searchQuery: 'AI automation',
    // date filtering (actor-dependent; harmless extras are ignored by Apify)
    datePosted: 'past-month',
    postedAfter: monthStart.toISOString().slice(0, 10),
    sortBy: 'relevance',
    maxItems: 200,
    maxPosts: 200,
  };
}

async function run(actorId, inputFile) {
  requireToken();
  if (!actorId) {
    console.error('Missing actorId. Run the `search` command first.');
    process.exit(1);
  }
  const fs = await import('node:fs/promises');
  const input = inputFile
    ? JSON.parse(await fs.readFile(inputFile, 'utf8'))
    : defaultInput();

  const actorPath = actorId.replace('/', '~');
  console.log(`Starting ${actorId} ...`);
  const { data: started } = await api(`/acts/${actorPath}/runs`, {
    method: 'POST',
    body: JSON.stringify(input),
  });

  let run = started;
  while (['READY', 'RUNNING'].includes(run.status)) {
    await new Promise((r) => setTimeout(r, 5000));
    ({ data: run } = await api(`/actor-runs/${run.id}`));
    process.stdout.write(`\r  status: ${run.status}   `);
  }
  console.log(`\nRun finished: ${run.status}`);
  if (run.status !== 'SUCCEEDED') {
    console.error(`See https://console.apify.com/actors/runs/${run.id} for logs.`);
    process.exit(1);
  }

  const items = await api(`/datasets/${run.defaultDatasetId}/items?clean=true&format=json`);
  await fs.writeFile('data/posts.json', JSON.stringify(items, null, 2));
  console.log(`Saved ${items.length} posts to data/posts.json`);
  console.log('Next: node scripts/linkedin-trend-scraper.mjs analyze data/posts.json');
}

/* ----------------------------------------------------------------- analyze */

const pick = (obj, keys) => keys.map((k) => obj?.[k]).find((v) => v !== undefined && v !== null);

function normalize(raw) {
  const text = pick(raw, ['text', 'postContent', 'content', 'description', 'commentary']) ?? '';
  const num = (v) => (typeof v === 'number' ? v : Number(String(v ?? '').replace(/[^\d]/g, '')) || 0);
  return {
    text: String(text),
    url: pick(raw, ['url', 'postUrl', 'link', 'postLink']) ?? '',
    author: pick(raw, ['authorName', 'author', 'authorFullName', 'profileName']) ?? '',
    postedAt: pick(raw, ['postedAt', 'publishedAt', 'date', 'postedAtISO', 'timestamp']) ?? '',
    reactions: num(pick(raw, ['numLikes', 'likesCount', 'reactions', 'numReactions', 'totalReactions'])),
    comments: num(pick(raw, ['numComments', 'commentsCount', 'comments'])),
    reposts: num(pick(raw, ['numShares', 'sharesCount', 'reposts', 'repostsCount'])),
    type: pick(raw, ['postType', 'type', 'contentType']) ?? '',
  };
}

/** Heuristic content-type classification, based on how the post opens and reads. */
function classify(p) {
  const t = p.text;
  const first = t.split('\n').find((l) => l.trim()) ?? '';
  const tags = [];
  if (/^(unpopular opinion|hot take|controversial|nobody wants to|stop )/i.test(first)) tags.push('contrarian-take');
  if (/\b(I|my|me)\b/i.test(first) && /\b(years? ago|in \d{4}|when I|I was)\b/i.test(t)) tags.push('personal-story');
  if (/^\s*\d+[\).:\-]/m.test(t) || /\b\d+\s+(lessons|things|ways|steps|mistakes|rules|tips)\b/i.test(t)) tags.push('listicle-framework');
  if (/\b(we (analyzed|studied|scraped|surveyed)|data (shows|says)|\d+%|\$\d)/i.test(t)) tags.push('data-driven');
  if (/\b(hiring|candidate|interview|resume|laid off|manager|team|culture)\b/i.test(t)) tags.push('workplace-career');
  if (/\b(AI|LLM|GPT|agent|automation|prompt)\b/i.test(t)) tags.push('ai-automation');
  if (/\b(MRR|ARR|revenue|churn|users|launched|shipped)\b/i.test(t)) tags.push('build-in-public');
  if (t.length < 300) tags.push('short-form');
  return tags.length ? tags : ['general'];
}

async function analyze(file) {
  const fs = await import('node:fs/promises');
  const raw = JSON.parse(await fs.readFile(file, 'utf8'));
  const posts = raw.map(normalize).filter((p) => p.text.length > 40);

  const now = new Date();
  const monthStart = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1);
  const thisMonth = posts.filter((p) => {
    const d = Date.parse(p.postedAt);
    return Number.isNaN(d) ? true : d >= monthStart;
  });

  const scored = thisMonth
    .map((p) => ({ ...p, engagement: p.reactions + p.comments * 3 + p.reposts * 5, tags: classify(p) }))
    .sort((a, b) => b.engagement - a.engagement);

  const byType = {};
  for (const p of scored) {
    for (const tag of p.tags) {
      byType[tag] ??= { posts: 0, reactions: 0, comments: 0, engagement: 0 };
      byType[tag].posts++;
      byType[tag].reactions += p.reactions;
      byType[tag].comments += p.comments;
      byType[tag].engagement += p.engagement;
    }
  }
  const typeTable = Object.entries(byType)
    .map(([type, s]) => ({
      type,
      posts: s.posts,
      avgReactions: Math.round(s.reactions / s.posts),
      avgComments: Math.round(s.comments / s.posts),
      avgEngagement: Math.round(s.engagement / s.posts),
    }))
    .sort((a, b) => b.avgEngagement - a.avgEngagement);

  const hashtags = {};
  for (const p of scored) {
    for (const h of p.text.match(/#[\p{L}\p{N}_]+/gu) ?? []) {
      const k = h.toLowerCase();
      hashtags[k] = (hashtags[k] ?? 0) + 1;
    }
  }
  const topTags = Object.entries(hashtags).sort((a, b) => b[1] - a[1]).slice(0, 30);

  const top = scored.slice(0, 25);
  const lengths = top.map((p) => p.text.length).sort((a, b) => a - b);
  const median = lengths[Math.floor(lengths.length / 2)] ?? 0;

  console.log(`\nPosts analyzed (this month): ${scored.length}\n`);
  console.log('Content types by average engagement:');
  console.table(typeTable);
  console.log(`\nMedian length of top 25 posts: ${median} characters`);
  console.log('\nTop hashtags:');
  console.table(topTags.map(([tag, count]) => ({ tag, count })));
  console.log('\nTop 15 hooks (first line of the highest-engagement posts):');
  top.slice(0, 15).forEach((p, i) => {
    const hook = (p.text.split('\n').find((l) => l.trim()) ?? '').slice(0, 120);
    console.log(`${String(i + 1).padStart(2)}. [${p.engagement}] ${hook}`);
  });

  await fs.writeFile('data/analysis.json', JSON.stringify({ typeTable, topTags, top }, null, 2));
  console.log('\nFull analysis written to data/analysis.json');
}

/* -------------------------------------------------------------------- main */

const [cmd, ...args] = process.argv.slice(2);
const commands = { search, run, analyze };
if (!commands[cmd]) {
  console.log('Commands: search [term] | run <actorId> [input.json] | analyze <file.json>');
  process.exit(1);
}
commands[cmd](...args).catch((err) => {
  console.error(err.message);
  process.exit(1);
});
