/**
 * jobs.js — background world-engine jobs (generate a map, apply edits, run history).
 *
 * Jobs run as Python child processes on this server, JOB_CONCURRENCY at a time
 * (default 1: one large planet peaks near 1.5 GB), each in its own temp folder,
 * killed after JOB_TIMEOUT_MS. Arguments are passed as an array, never through a
 * shell, so user text (a world brief) cannot become a command.
 *
 * Job state is kept in memory and mirrored to the store (jobs/<id>.json), so a
 * page can poll it. A job that was running when the server restarted is
 * reported as failed with a clear message instead of hanging forever.
 *
 * Scaling path: replace run() with a queue (SQS) and a worker fleet; the rest of
 * the app only uses submit() and get().
 */
const { spawn } = require('child_process');
const fs   = require('fs');
const fsp  = require('fs/promises');
const os   = require('os');
const path = require('path');
const { randomUUID } = require('crypto');

const TERMINAL = new Set(['done', 'failed']);

function defaultPython(root) {
  const venv = path.join(root, 'engine', '.venv', 'bin', 'python');
  return fs.existsSync(venv) ? venv : 'python3';
}

function createJobRunner({ store, root = path.join(__dirname, '..'), env = process.env, log = console } = {}) {
  const pythonBin   = env.PYTHON_BIN || defaultPython(root);
  const servicePath = path.join(root, 'engine', 'service.py');
  const concurrency = Math.max(1, Number(env.JOB_CONCURRENCY || 1));
  const timeoutMs   = Number(env.JOB_TIMEOUT_MS || 10 * 60 * 1000);
  const jobs = new Map();
  const queue = [];
  let running = 0;

  const publicView = j => j && ({
    jobId: j.jobId, worldId: j.worldId, kind: j.kind, status: j.status,
    createdAt: j.createdAt, startedAt: j.startedAt || null, finishedAt: j.finishedAt || null,
    queuePosition: j.status === 'queued' ? queue.indexOf(j) + 1 : 0,
    result: j.result || null, error: j.error || null,
  });

  async function persist(j) {
    try { await store.put(`jobs/${j.jobId}.json`, JSON.stringify(publicView(j))); }
    catch (e) { log.error('job persist failed', j.jobId, e.message); }
  }

  function runPython(args, cwd) {
    return new Promise(resolve => {
      const child = spawn(pythonBin, [servicePath, ...args], {
        cwd, env: { PATH: env.PATH, HOME: cwd, PYTHONDONTWRITEBYTECODE: '1', MPLBACKEND: 'Agg' },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      let out = '', err = '';
      child.stdout.on('data', d => { out = (out + d).slice(-200000); });
      child.stderr.on('data', d => { err = (err + d).slice(-20000); });
      const timer = setTimeout(() => child.kill('SIGKILL'), timeoutMs);
      child.on('error', e => { clearTimeout(timer); resolve({ code: -1, out, err: String(e) }); });
      child.on('close', (code, signal) => { clearTimeout(timer); resolve({ code, signal, out, err }); });
    });
  }

  async function run(j) {
    running++;
    j.status = 'running'; j.startedAt = new Date().toISOString(); await persist(j);
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), `ur-${j.kind}-`));
    try {
      const args = await j.prepare(dir);
      const r = await runPython(args, dir);
      let msg = null;
      try { msg = JSON.parse(r.out.trim().split('\n').pop()); } catch { /* no JSON line */ }
      if (r.signal === 'SIGKILL') throw Object.assign(new Error('The job took too long and was stopped.'), { user: true });
      if (!msg) { log.error(`job ${j.jobId} produced no result`, r.err.slice(-2000)); throw new Error('The world engine did not return a result.'); }
      if (!msg.ok) {
        if (r.code !== 2) log.error(`job ${j.jobId} engine error`, r.err.slice(-2000));
        throw Object.assign(new Error(msg.error || 'The world engine failed.'), { user: r.code === 2 });
      }
      delete msg.ok;
      j.result = (await j.finish(dir, msg)) || msg;
      j.status = 'done';
    } catch (e) {
      j.status = 'failed';
      j.error = e.user || e.message?.startsWith('The ') ? e.message : 'The job failed. Please try again.';
      if (!e.user) log.error(`job ${j.jobId} failed`, e);
      try { await j.onFail?.(j.error); } catch (e2) { log.error('job onFail', e2); }
    } finally {
      j.finishedAt = new Date().toISOString();
      await persist(j);
      fsp.rm(dir, { recursive: true, force: true }).catch(() => {});
      running--;
      pump();
    }
  }

  function pump() {
    while (running < concurrency && queue.length) run(queue.shift());
  }

  return {
    pythonBin, servicePath, runPython,
    /** spec: {worldId, userId, kind, prepare(dir) -> args[], finish(dir, result) -> result, onFail(msg)} */
    async submit(spec) {
      const j = { ...spec, jobId: randomUUID(), status: 'queued', createdAt: new Date().toISOString() };
      jobs.set(j.jobId, j);
      queue.push(j);
      await persist(j);
      pump();
      return publicView(j);
    },
    async get(jobId) {
      const live = jobs.get(jobId);
      if (live) return publicView(live);
      const raw = await store.get(`jobs/${jobId}.json`);
      if (!raw) return null;
      const j = JSON.parse(raw);
      if (!TERMINAL.has(j.status)) {          // lost in a restart
        j.status = 'failed'; j.error = 'The server restarted while this job was running. Please start it again.';
        j.finishedAt = new Date().toISOString();
        await store.put(`jobs/${jobId}.json`, JSON.stringify(j));
      }
      return j;
    },
    activeFor(userId) {
      return [...jobs.values()].filter(j => j.userId === userId && !TERMINAL.has(j.status)).length;
    },
    stats: () => ({ running, queued: queue.length, concurrency }),
  };
}

module.exports = { createJobRunner };
