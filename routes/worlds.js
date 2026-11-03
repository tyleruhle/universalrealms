/**
 * /api/worlds — the World Engine: a user's worlds, their lore, maps, edits and history.
 *
 * Small metadata lives in the worlds table (lib/worldsDb.js); files live in the
 * world store (lib/worldStore.js) under worlds/<worldId>/:
 *   bible.json  lore.json
 *   map/world.npz  map/atlas.json  map/preview.png            the generated planet
 *   map/edits.json map/edited.npz  map/atlas-current.json
 *   map/preview-current.png  map/geography.md                 after Atlas Studio edits
 *   history/history.md  history/timeline.md  history/eras.png  history/summary.json
 * Map generation, edits and history run as background jobs (lib/jobs.js).
 */
const express = require('express');
const fsp     = require('fs/promises');
const path    = require('path');
const { randomUUID } = require('crypto');
const requireAuth = require('../middleware/auth');
const { createStore } = require('../lib/worldStore');
const { createDb }    = require('../lib/worldsDb');
const { createJobRunner } = require('../lib/jobs');
const { createLore, SECTIONS, SECTION_KEYS } = require('../lib/lore');

const router = express.Router();
const store = createStore();
const db    = createDb();
const jobs  = createJobRunner({ store });
const lore  = createLore();

const UUID_RE  = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SIZES    = ['small', 'medium', 'large'];
const MAX_WORLDS_PER_USER = Number(process.env.MAX_WORLDS_PER_USER || 25);
const k = (id, name) => `worlds/${id}/${name}`;

class HttpError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
const bad = msg => new HttpError(400, msg);

// Every handler runs through here: async errors become JSON answers.
const h = fn => (req, res) => fn(req, res).catch(err => {
  const status = err.status || 500;
  if (status >= 500 && !err.status) console.error('worlds route error:', err);
  res.status(status).json({ error: status === 500 && !err.status ? 'Something went wrong. Please try again.' : err.message });
});

async function readJson(key, fallback) {
  const raw = await store.get(key);
  return raw ? JSON.parse(raw) : fallback;
}

/** Loads the world and enforces ownership. Unknown and foreign worlds both answer 404. */
async function owned(req) {
  const id = req.params.id;
  if (!UUID_RE.test(id)) throw new HttpError(404, 'World not found.');
  const w = await db.get(id);
  if (!w || w.ownerUserId !== req.user.userId) throw new HttpError(404, 'World not found.');
  return w;
}

function str(v, name, max, { required = true } = {}) {
  if (v === undefined || v === null || v === '') { if (required) throw bad(`${name} is required.`); return ''; }
  if (typeof v !== 'string') throw bad(`${name} must be text.`);
  const s = v.trim();
  if (required && !s) throw bad(`${name} is required.`);
  if (s.length > max) throw bad(`${name} must be at most ${max} characters.`);
  return s;
}

function int(v, name, lo, hi, dflt) {
  if (v === undefined || v === null || v === '') return dflt;
  const n = Number(v);
  if (!Number.isInteger(n) || n < lo || n > hi) throw bad(`${name} must be a whole number from ${lo} to ${hi}.`);
  return n;
}

async function bibleSummary(bible) {
  const out = {};
  for (const [key, s] of Object.entries(bible.sections || {})) out[key] = s.status;
  return { sections: out };
}

/** One job per world at a time, two per user. */
async function guardJobs(world, userId) {
  if (world.activeJob) {
    const j = await jobs.get(world.activeJob.jobId);
    if (j && !['done', 'failed'].includes(j.status))
      throw new HttpError(409, `This world is busy (${world.activeJob.kind}). Wait for it to finish.`);
  }
  if (jobs.activeFor(userId) >= 2) throw new HttpError(429, 'You already have two world jobs running. Wait for one to finish.');
}

const clearActive = worldId => () => db.update(worldId, { activeJob: null });

// ───────────────────────────────────────────────────────── worlds

router.get('/meta', requireAuth, h(async (req, res) => {
  res.json({ sections: SECTIONS.map(({ key, title }) => ({ key, title })), sizes: SIZES,
    loreConfigured: lore.configured, maxWorlds: MAX_WORLDS_PER_USER });
}));

router.get('/', requireAuth, h(async (req, res) => {
  res.json(await db.listByOwner(req.user.userId));
}));

router.post('/', requireAuth, h(async (req, res) => {
  const name = str(req.body?.name, 'Name', 80);
  if ((await db.listByOwner(req.user.userId)).length >= MAX_WORLDS_PER_USER)
    throw bad(`You can have up to ${MAX_WORLDS_PER_USER} worlds. Delete one to make room.`);
  const now = new Date().toISOString();
  const world = await db.create({ worldId: randomUUID(), ownerUserId: req.user.userId, name,
    createdAt: now, updatedAt: now, stage: 'lore', bible: { sections: {} } });
  res.status(201).json(world);
}));

router.get('/:id', requireAuth, h(async (req, res) => { res.json(await owned(req)); }));

router.patch('/:id', requireAuth, h(async (req, res) => {
  await owned(req);
  res.json(await db.update(req.params.id, { name: str(req.body?.name, 'Name', 80) }));
}));

router.delete('/:id', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  if (w.activeJob) {
    const j = await jobs.get(w.activeJob.jobId);
    if (j && !['done', 'failed'].includes(j.status)) throw new HttpError(409, 'Wait for the running job to finish before deleting.');
  }
  await store.del(`worlds/${w.worldId}`);
  await db.remove(w.worldId);
  res.json({ deleted: true });
}));

router.get('/:id/jobs/:jobId', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  if (!UUID_RE.test(req.params.jobId)) throw new HttpError(404, 'Job not found.');
  const j = await jobs.get(req.params.jobId);
  if (!j || j.worldId !== w.worldId) throw new HttpError(404, 'Job not found.');
  res.json(j);
}));

// ───────────────────────────────────────────────────────── bible

router.get('/:id/bible', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  res.json(await readJson(k(w.worldId, 'bible.json'), { sections: {} }));
}));

router.put('/:id/bible/:section', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  const key = req.params.section;
  if (!SECTION_KEYS.has(key)) throw new HttpError(404, 'Unknown bible section.');
  const text = str(req.body?.text, 'Text', 60000, { required: false });
  const status = req.body?.status === 'confirmed' ? 'confirmed' : 'proposed';
  const bible = await readJson(k(w.worldId, 'bible.json'), { sections: {} });
  if (!text) delete bible.sections[key];
  else bible.sections[key] = { text, status, updatedAt: new Date().toISOString(),
    source: ['claude', 'user', 'history', 'map'].includes(req.body?.source) ? req.body.source : 'user' };
  await store.put(k(w.worldId, 'bible.json'), JSON.stringify(bible));
  await db.update(w.worldId, { bible: await bibleSummary(bible) });
  res.json(bible);
}));

// ───────────────────────────────────────────────────────── lore (Claude)

async function loreInputs(w) {
  const [bible, conv, geography] = await Promise.all([
    readJson(k(w.worldId, 'bible.json'), { sections: {} }),
    readJson(k(w.worldId, 'lore.json'), { messages: [] }),
    store.get(k(w.worldId, 'map/geography.md')),
  ]);
  return { bible, conv, extras: { geography: geography ? String(geography) : '' } };
}

function loreGate(req) {
  if (!lore.configured) throw new HttpError(503, 'The lore assistant is not set up on this server yet.');
  if (!lore.allow(req.user.userId)) throw new HttpError(429, 'You have reached the hourly limit for the lore assistant. Try again later.');
}

router.get('/:id/lore', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  res.json(await readJson(k(w.worldId, 'lore.json'), { messages: [] }));
}));

router.delete('/:id/lore', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  await store.put(k(w.worldId, 'lore.json'), JSON.stringify({ messages: [] }));
  res.json({ messages: [] });
}));

router.post('/:id/lore/message', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  const text = str(req.body?.text, 'Message', 4000);
  loreGate(req);
  const { bible, conv, extras } = await loreInputs(w);
  const history = conv.messages.map(({ role, content }) => ({ role, content }));
  const r = await lore.chat({ world: w, bible, extras, history, text });
  const now = new Date().toISOString();
  conv.messages.push({ role: 'user', content: text, at: now }, { role: 'assistant', content: r.text, at: now });
  if (conv.messages.length > 400) conv.messages = conv.messages.slice(-400);
  await store.put(k(w.worldId, 'lore.json'), JSON.stringify(conv));
  await db.update(w.worldId, {});
  res.json({ reply: r.text, usage: r.usage });
}));

router.post('/:id/lore/draft', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  const section = req.body?.section;
  if (!SECTION_KEYS.has(section)) throw bad('Choose a bible section to draft.');
  const instructions = str(req.body?.instructions, 'Instructions', 1000, { required: false });
  loreGate(req);
  const { bible, conv, extras } = await loreInputs(w);
  const r = await lore.draft({ world: w, bible, extras, history: conv.messages, section, instructions });
  res.json({ section, text: r.text, usage: r.usage });
}));

let VOCAB = null;
async function vocab() {
  if (VOCAB) return VOCAB;
  const dir = await fsp.mkdtemp(path.join(require('os').tmpdir(), 'ur-vocab-'));
  const r = await jobs.runPython(['vocab'], dir);
  fsp.rm(dir, { recursive: true, force: true }).catch(() => {});
  const v = JSON.parse(r.out.trim().split('\n').pop());
  if (!v.ok) throw new Error('vocab failed');
  return (VOCAB = v);
}

router.post('/:id/lore/brief', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  loreGate(req);
  const bible = await readJson(k(w.worldId, 'bible.json'), { sections: {} });
  res.json(await lore.brief({ world: w, bible, vocab: await vocab() }));
}));

// ───────────────────────────────────────────────────────── map

router.post('/:id/map', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  const brief = str(req.body?.brief, 'Brief', 300);
  const size = SIZES.includes(req.body?.size) ? req.body.size : 'small';
  const seed = int(req.body?.seed, 'Seed', 0, 2147483646, Math.floor(Math.random() * 2147483646));
  await guardJobs(w, req.user.userId);
  const job = await jobs.submit({
    worldId: w.worldId, userId: req.user.userId, kind: 'map',
    prepare: async dir => ['generate', '--out', path.join(dir, 'out'), '--brief', brief, '--seed', String(seed),
                           '--size', size, '--title', w.name],
    finish: async (dir, result) => {
      // A new planet replaces the old one: its edits and history no longer apply.
      await store.del(`worlds/${w.worldId}/map`);
      await store.del(`worlds/${w.worldId}/history`);
      for (const f of ['world.npz', 'atlas.json', 'preview.png'])
        await store.putFile(k(w.worldId, `map/${f}`), path.join(dir, 'out', f));
      const map = { ...result, generatedAt: new Date().toISOString(), version: (w.map?.version || 0) + 1 };
      await db.update(w.worldId, { map, edits: null, history: null, activeJob: null, stage: 'map' });
      return map;
    },
    onFail: clearActive(w.worldId),
  });
  await db.update(w.worldId, { activeJob: { jobId: job.jobId, kind: 'map' } });
  res.status(202).json(job);
}));

const sendFile = (type, name) => h(async (req, res) => {
  const w = await owned(req);
  const body = await store.get(k(w.worldId, name(w)));
  if (!body) throw new HttpError(404, 'Not generated yet.');
  res.set('Content-Type', type).set('Cache-Control', 'private, no-cache').send(body);
});

router.get('/:id/map/atlas', requireAuth, sendFile('application/json', w => w.edits ? 'map/atlas-current.json' : 'map/atlas.json'));
router.get('/:id/map/preview.png', requireAuth, sendFile('image/png', w => w.edits ? 'map/preview-current.png' : 'map/preview.png'));
router.get('/:id/map/geography', requireAuth, sendFile('text/markdown; charset=utf-8', () => 'map/geography.md'));

// Atlas Studio saves here. Python replays the manifest against the generated
// planet; only if that succeeds do the new edits replace the old.
router.put('/:id/edits', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  await guardJobs(w, req.user.userId);
  if (!w.map) throw bad('Generate a map before saving edits.');
  const m = req.body?.manifest;
  if (!m || typeof m !== 'object' || m.schema !== 'worldsmith-feature-editor/v1') throw bad('That is not an Atlas Studio edits file.');
  if (m.baseline_fingerprint !== w.map.fingerprint)
    throw new HttpError(409, 'These edits were made for an older version of this map. Reload Atlas Studio.');
  if (!Array.isArray(m.history) || m.history.length > 10000 || !Array.isArray(m.features) || m.features.length > 2000)
    throw bad('The edits file is too large or malformed.');
  delete m.background;
  const manifest = JSON.stringify(m);
  const job = await jobs.submit({
    worldId: w.worldId, userId: req.user.userId, kind: 'edits',
    prepare: async dir => {
      await store.getToFile(k(w.worldId, 'map/world.npz'), path.join(dir, 'world.npz'));
      await fsp.writeFile(path.join(dir, 'edits.json'), manifest);
      return ['apply-edits', '--world', path.join(dir, 'world.npz'), '--edits', path.join(dir, 'edits.json'),
              '--out', path.join(dir, 'out'), '--title', w.name];
    },
    finish: async (dir, result) => {
      await store.put(k(w.worldId, 'map/edits.json'), manifest);
      await store.putFile(k(w.worldId, 'map/edited.npz'), path.join(dir, 'out', 'edited.npz'));
      await store.putFile(k(w.worldId, 'map/atlas-current.json'), path.join(dir, 'out', 'atlas.json'));
      await store.putFile(k(w.worldId, 'map/preview-current.png'), path.join(dir, 'out', 'preview.png'));
      await store.putFile(k(w.worldId, 'map/geography.md'), path.join(dir, 'out', 'geography.md'));
      const edits = { features: result.features, applied: result.edits_applied,
        coast_cells_changed: result.coast_cells_changed, savedAt: new Date().toISOString() };
      await db.update(w.worldId, { edits, activeJob: null });
      return edits;
    },
    onFail: clearActive(w.worldId),
  });
  await db.update(w.worldId, { activeJob: { jobId: job.jobId, kind: 'edits' } });
  res.status(202).json(job);
}));

// ───────────────────────────────────────────────────────── history

router.post('/:id/history', requireAuth, h(async (req, res) => {
  const w = await owned(req);
  await guardJobs(w, req.user.userId);      // "busy" beats "no map yet" while a map is being made
  if (!w.map) throw bad('Generate a map before running history.');
  const turns = int(req.body?.turns, 'Turns', 5, 60, 30);
  const years = int(req.body?.years, 'Years per turn', 1, 50, 25);
  const seed  = int(req.body?.seed, 'Seed', 0, 2147483646, 1);
  const job = await jobs.submit({
    worldId: w.worldId, userId: req.user.userId, kind: 'history',
    prepare: async dir => {
      await store.getToFile(k(w.worldId, 'map/world.npz'), path.join(dir, 'world.npz'));
      const args = ['history', '--world', path.join(dir, 'world.npz'), '--out', path.join(dir, 'out'),
                    '--brief', w.map.brief, '--turns', String(turns), '--years', String(years), '--seed', String(seed)];
      if (await store.getToFile(k(w.worldId, 'map/edits.json'), path.join(dir, 'edits.json')))
        args.push('--edits', path.join(dir, 'edits.json'));
      return args;
    },
    finish: async (dir, result) => {
      await store.del(`worlds/${w.worldId}/history`);
      for (const f of ['history.md', 'timeline.md', 'eras.png'])
        await store.putFile(k(w.worldId, `history/${f}`), path.join(dir, 'out', f));
      const history = { ...result, seed, ranAt: new Date().toISOString() };
      await store.put(k(w.worldId, 'history/summary.json'), JSON.stringify(history));
      await db.update(w.worldId, { history, activeJob: null, stage: 'history' });
      return history;
    },
    onFail: clearActive(w.worldId),
  });
  await db.update(w.worldId, { activeJob: { jobId: job.jobId, kind: 'history' } });
  res.status(202).json(job);
}));

router.get('/:id/history/eras.png',   requireAuth, sendFile('image/png', () => 'history/eras.png'));
router.get('/:id/history/history.md', requireAuth, sendFile('text/markdown; charset=utf-8', () => 'history/history.md'));
router.get('/:id/history/timeline.md', requireAuth, sendFile('text/markdown; charset=utf-8', () => 'history/timeline.md'));

router.jobs = jobs;                        // for health checks and tests
module.exports = router;
