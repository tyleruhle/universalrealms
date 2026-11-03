/**
 * World Engine end to end: a real server (local store + file DB), the real
 * Python engine, and a mock Claude API that records what it is sent.
 *
 *   npm test          (needs the engine's Python packages: npm run engine:setup)
 */
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const jwt = require('jsonwebtoken');

const ROOT = path.join(__dirname, '..');
const SECRET = 'test-secret';
let server, mock, base, dataDir;
const claudeCalls = [];

const cookie = userId => `ur_token=${jwt.sign({ userId, username: userId }, SECRET)}`;
const ALICE = cookie('alice'), BOB = cookie('bob');

async function api(method, url, { body, as = ALICE, raw = false } = {}) {
  const res = await fetch(base + url, {
    method, headers: { 'content-type': 'application/json', ...(as ? { cookie: as } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (raw) return res;
  const type = res.headers.get('content-type') || '';
  return { status: res.status, body: type.includes('json') ? await res.json() : await res.text() };
}

async function waitJob(worldId, jobId, ms = 240000) {
  const end = Date.now() + ms;
  for (;;) {
    const r = await api('GET', `/api/worlds/${worldId}/jobs/${jobId}`);
    assert.equal(r.status, 200);
    if (['done', 'failed'].includes(r.body.status)) return r.body;
    if (Date.now() > end) throw new Error(`job ${jobId} still ${r.body.status}`);
    await new Promise(r => setTimeout(r, 400));
  }
}

before(async () => {
  // Mock Claude: answers by request type, records every call.
  mock = http.createServer((req, res) => {
    let body = '';
    req.on('data', d => (body += d));
    req.on('end', () => {
      const parsed = JSON.parse(body);
      claudeCalls.push({ headers: req.headers, body: parsed, url: req.url });
      const last = parsed.messages.at(-1).content;
      let text = 'The salt flats were once a sea. Which people remember the shoreline?';
      if (last.includes('Reply with JSON only')) text = '{"brief": "arid mountainous world, fractured kingdoms", "why": "The bible describes salt deserts and many small realms."}';
      else if (last.startsWith('Write the "')) text = 'A dry world of salt flats.\n\n### The Salt Flats\nOnce an inland sea (proposed).\n\n### Open questions\n- Who drained it?';
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ content: [{ type: 'text', text }], stop_reason: 'end_turn',
        usage: { input_tokens: 120, output_tokens: 40, cache_read_input_tokens: 6400, cache_creation_input_tokens: 0 } }));
    });
  });
  await new Promise(r => mock.listen(0, '127.0.0.1', r));
  dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ur-world-test-'));
  const port = 30000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['server.js'], {
    cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PORT: String(port), JWT_SECRET: SECRET, NODE_ENV: 'test',
      WORLD_DB: 'file', WORLD_STORE: 'local', DATA_DIR: dataDir,
      ANTHROPIC_API_KEY: 'test-key', ANTHROPIC_BASE_URL: `http://127.0.0.1:${mock.address().port}`,
      AWS_REGION: 'us-east-2' },
  });
  let log = '';
  server.stdout.on('data', d => (log += d));
  server.stderr.on('data', d => (log += d));
  for (let i = 0; i < 100; i++) {
    if (log.includes('running on port')) return;
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('server did not start:\n' + log);
});

after(() => { server?.kill(); mock?.close(); fs.rmSync(dataDir, { recursive: true, force: true }); });

let world;

test('signed-out requests are refused', async () => {
  assert.equal((await api('GET', '/api/worlds', { as: null })).status, 401);
});

test('create, list and rename a world', async () => {
  assert.equal((await api('POST', '/api/worlds', { body: { name: '' } })).status, 400);
  const r = await api('POST', '/api/worlds', { body: { name: 'The Salt Throne' } });
  assert.equal(r.status, 201);
  world = r.body;
  assert.equal(world.stage, 'lore');
  const list = await api('GET', '/api/worlds');
  assert.deepEqual(list.body.map(w => w.name), ['The Salt Throne']);
  assert.equal((await api('PATCH', `/api/worlds/${world.worldId}`, { body: { name: 'Salt Throne' } })).body.name, 'Salt Throne');
});

test('other users cannot see or touch a world', async () => {
  assert.equal((await api('GET', `/api/worlds/${world.worldId}`, { as: BOB })).status, 404);
  assert.equal((await api('PUT', `/api/worlds/${world.worldId}/bible/overview`, { as: BOB, body: { text: 'x' } })).status, 404);
  assert.equal((await api('GET', '/api/worlds/not-a-uuid')).status, 404);
  assert.deepEqual((await api('GET', '/api/worlds', { as: BOB })).body, []);
});

test('bible sections save as proposed, then confirm', async () => {
  assert.equal((await api('PUT', `/api/worlds/${world.worldId}/bible/nonsense`, { body: { text: 'x' } })).status, 404);
  let r = await api('PUT', `/api/worlds/${world.worldId}/bible/overview`, { body: { text: 'A desert planet ruled by water empires.' } });
  assert.equal(r.body.sections.overview.status, 'proposed');
  r = await api('PUT', `/api/worlds/${world.worldId}/bible/overview`, { body: { text: 'A desert planet ruled by water empires.', status: 'confirmed' } });
  assert.equal(r.body.sections.overview.status, 'confirmed');
  assert.equal((await api('GET', `/api/worlds/${world.worldId}`)).body.bible.sections.overview, 'confirmed');
});

test('lore chat sends the cached Worldsmith prompt and the world context', async () => {
  const r = await api('POST', `/api/worlds/${world.worldId}/lore/message`, { body: { text: 'Start the architecture interview.' } });
  assert.equal(r.status, 200, JSON.stringify(r.body));
  assert.match(r.body.reply, /salt flats/);
  const call = claudeCalls.at(-1);
  assert.equal(call.url, '/v1/messages');
  assert.equal(call.headers['x-api-key'], 'test-key');
  assert.equal(call.headers['anthropic-version'], '2023-06-01');
  assert.equal(call.body.model, 'claude-sonnet-5-5');
  assert.deepEqual(call.body.system[0].cache_control, { type: 'ephemeral' });
  assert.match(call.body.system[0].text, /Worldsmith worldbuilder inside Universal Realms/);
  assert.match(call.body.system[0].text, /architecture interview/i);           // the real module
  assert.match(call.body.system[1].text, /A desert planet ruled by water empires\./);
  assert.match(call.body.system[1].text, /CONFIRMED/);
  const conv = await api('GET', `/api/worlds/${world.worldId}/lore`);
  assert.equal(conv.body.messages.length, 2);
  // the next turn carries the conversation
  await api('POST', `/api/worlds/${world.worldId}/lore/message`, { body: { text: 'The Jimid remember it.' } });
  assert.equal(claudeCalls.at(-1).body.messages.length, 3);
});

test('drafting a section uses that section\'s Worldsmith reference and is not auto-saved', async () => {
  const r = await api('POST', `/api/worlds/${world.worldId}/lore/draft`, { body: { section: 'geography' } });
  assert.equal(r.status, 200);
  assert.match(r.body.text, /Open questions/);
  const sys = claudeCalls.at(-1).body.system.map(b => b.text).join('\n');
  assert.match(sys, /Reference for this section/);
  assert.equal((await api('GET', `/api/worlds/${world.worldId}/bible`)).body.sections.geography, undefined);
  assert.equal((await api('POST', `/api/worlds/${world.worldId}/lore/draft`, { body: { section: 'nope' } })).status, 400);
});

test('a map brief is suggested in the generator\'s vocabulary', async () => {
  const r = await api('POST', `/api/worlds/${world.worldId}/lore/brief`);
  assert.equal(r.status, 200);
  assert.equal(r.body.brief, 'arid mountainous world, fractured kingdoms');
  assert.match(claudeCalls.at(-1).body.messages[0].content, /mountainous/);   // vocab from the engine
});

test('generate a planet in the background, one job at a time', async () => {
  assert.equal((await api('POST', `/api/worlds/${world.worldId}/map`, { body: { brief: '' } })).status, 400);
  const r = await api('POST', `/api/worlds/${world.worldId}/map`, { body: { brief: 'arid mountainous world, fractured kingdoms, devout', seed: 4242, size: 'small' } });
  assert.equal(r.status, 202);
  const busy = await api('POST', `/api/worlds/${world.worldId}/history`, { body: {} });
  assert.equal(busy.status, 409);
  assert.equal((await api('GET', `/api/worlds/${world.worldId}/jobs/${r.body.jobId}`, { as: BOB })).status, 404);
  const job = await waitJob(world.worldId, r.body.jobId);
  assert.equal(job.status, 'done', job.error);
  const w = (await api('GET', `/api/worlds/${world.worldId}`)).body;
  assert.equal(w.map.seed, 4242);
  assert.deepEqual(w.map.matched, ['arid', 'devout', 'fractured', 'kingdoms', 'mountainous']);
  assert.equal(w.activeJob, null);
  const png = await api('GET', `/api/worlds/${world.worldId}/map/preview.png`, { raw: true });
  assert.equal(png.headers.get('content-type'), 'image/png');
  const atlas = (await api('GET', `/api/worlds/${world.worldId}/map/atlas`)).body;
  assert.equal(atlas.schema, 'worldsmith-feature-editor/v1');
  assert.equal(atlas.baseline_fingerprint, w.map.fingerprint);
  assert.match(atlas.background, /^data:image\/png;base64,/);
  world = w;
});

test('Atlas Studio edits are replayed by the engine before they are kept', async () => {
  const atlas = (await api('GET', `/api/worlds/${world.worldId}/map/atlas`)).body;
  delete atlas.background;
  const wrong = { ...atlas, baseline_fingerprint: '0'.repeat(64) };
  assert.equal((await api('PUT', `/api/worlds/${world.worldId}/edits`, { body: { manifest: wrong } })).status, 409);
  // > 100 KB body: proves the larger parser is on this route only
  const manifest = { ...atlas, features: [], cursor: 2, history: [
    { operation: 'add', arguments: { feature: { id: 'the-long-wadi', name: 'The Long Wadi', kind: 'river',
      geometry: [[40, 40], [60, 52], [80, 58]], locked: false, lock_radius: 3, properties: { notes: 'x'.repeat(150000) } } } },
    { operation: 'add', arguments: { feature: { id: 'oasis-of-tears', name: 'Oasis of Tears', kind: 'settlement',
      geometry: [[120, 90]], locked: true, lock_radius: 4, properties: {} } } },
  ] };
  const r = await api('PUT', `/api/worlds/${world.worldId}/edits`, { body: { manifest } });
  assert.equal(r.status, 202, JSON.stringify(r.body));
  const job = await waitJob(world.worldId, r.body.jobId);
  assert.equal(job.status, 'done', job.error);
  const geo = await api('GET', `/api/worlds/${world.worldId}/map/geography`);
  assert.match(geo.body, /The Long Wadi/);
  assert.match(geo.body, /Oasis of Tears.*protected/);
  const current = (await api('GET', `/api/worlds/${world.worldId}/map/atlas`)).body;
  assert.equal(current.history.length, 2);
  assert.equal((await api('GET', `/api/worlds/${world.worldId}`)).body.edits.features, 2);
  // a non-default-size body elsewhere is still limited
  const big = await api('PUT', `/api/worlds/${world.worldId}/bible/overview`, { body: { text: 'y'.repeat(200000) } });
  assert.equal(big.status, 413);
});

test('a broken edit is refused and the saved edits stay', async () => {
  const atlas = (await api('GET', `/api/worlds/${world.worldId}/map/atlas`)).body;
  delete atlas.background;
  const broken = { ...atlas, history: [...atlas.history, { operation: 'remove', arguments: { id: 'oasis-of-tears' } }], cursor: atlas.history.length + 1 };
  const r = await api('PUT', `/api/worlds/${world.worldId}/edits`, { body: { manifest: broken } });
  const job = await waitJob(world.worldId, r.body.jobId);
  assert.equal(job.status, 'failed');
  assert.match(job.error, /could not be applied/);
  assert.equal((await api('GET', `/api/worlds/${world.worldId}/map/atlas`)).body.history.length, 2);
});

test('history runs on the edited planet', async () => {
  assert.equal((await api('POST', `/api/worlds/${world.worldId}/history`, { body: { turns: 100 } })).status, 400);
  const r = await api('POST', `/api/worlds/${world.worldId}/history`, { body: { turns: 8, years: 25, seed: 7 } });
  assert.equal(r.status, 202);
  const job = await waitJob(world.worldId, r.body.jobId);
  assert.equal(job.status, 'done', job.error);
  assert.equal(job.result.terrain, 'saved world + edits');
  assert.equal(job.result.span_years, 200);
  assert.ok(job.result.seams.length > 0);
  const md = await api('GET', `/api/worlds/${world.worldId}/history/history.md`);
  assert.match(md.body, /proposed/i);
  const png = await api('GET', `/api/worlds/${world.worldId}/history/eras.png`, { raw: true });
  assert.equal(png.status, 200);
});

test('the lore assistant sees the map and history', async () => {
  await api('POST', `/api/worlds/${world.worldId}/lore/message`, { body: { text: 'What happened?' } });
  const ctx = claudeCalls.at(-1).body.system[1].text;
  assert.match(ctx, /## Map \(generated\)/);
  assert.match(ctx, /The Long Wadi/);
  assert.match(ctx, /## Simulated history/);
});

test('deleting a world removes it and its files', async () => {
  assert.equal((await api('DELETE', `/api/worlds/${world.worldId}`, { as: BOB })).status, 404);
  assert.equal((await api('DELETE', `/api/worlds/${world.worldId}`)).status, 200);
  assert.equal((await api('GET', `/api/worlds/${world.worldId}`)).status, 404);
  assert.equal(fs.existsSync(path.join(dataDir, 'worlds', world.worldId)), false);
});

test('without an API key the lore assistant says so', async () => {
  const { createLore } = require('../lib/lore');
  const lore = createLore({ env: {} });
  assert.equal(lore.configured, false);
  await assert.rejects(lore.chat({ world: { name: 'x' }, bible: {}, history: [], text: 'hi' }), e => e.status === 503);
});
