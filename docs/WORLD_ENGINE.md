# World Engine — runbook

The World Engine lets a signed-in user build a world in one place: talk the lore
through with Claude and keep it in a world bible, raise a planet from a brief,
name its rivers, coasts and cities in Atlas Studio, and simulate centuries of
history on that map. Everything is stored per user, per world.

The full build-and-setup guide (with diagrams and the reasoning behind each
choice) is the "Universal Realms World Engine — Build and Setup Guide" doc.
This file is the short version that lives with the code.

## Pages

| Page | What it does |
|---|---|
| `/worlds.html` | Your worlds: create one, open one. |
| `/world.html?id=…#lore` | Chat with the worldbuilder; draft, edit, save and confirm bible sections. |
| `/world.html?id=…#map` | Brief (or "Suggest from the bible") → Generate. Preview, biome mix, named features. |
| `/world.html?id=…#history` | Turns, years per turn, seed → Run history. Era maps, story seams, history write-up. |
| `/atlas_studio.html?world=…` | Draw and name features on the world's map; **Save to world** replays them on the planet. |

The nav (`/js/ur-nav.js`) has a top-level **Worlds** link; Atlas Studio is also under **Maps**.

## How the pieces fit

```
browser ──/api/worlds──▶ Express (routes/worlds.js)
                           ├─ lib/worldsDb.js   world records    DynamoDB ur_worlds  (or data/worlds-db.json)
                           ├─ lib/worldStore.js world files      S3 bucket           (or data/)
                           ├─ lib/lore.js       lore assistant   Claude Messages API (worldbuilder.md as a cached system prompt)
                           └─ lib/jobs.js       background jobs  python engine/service.py (Worldsmith engine, vendored)
```

* Map generation, edit replay and history run as **background jobs**: the API answers
  `202 {jobId}` and the page polls `GET /api/worlds/:id/jobs/:jobId`. Jobs run one at a time
  by default (`JOB_CONCURRENCY`), each in a temp dir, killed after `JOB_TIMEOUT_MS`.
  One active job per world (409) and two per user (429).
* `engine/worldsmith/` is a vendored copy of the Worldsmith skill (2.0.3). The site only
  calls it through `engine/service.py`, which prints one JSON line (`{"ok": true, …}` or
  `{"ok": false, "error": "…"}`).
* Lore never writes the bible by itself. Drafts land in the editor; the user saves them as
  *proposed* and confirms them as *canon*. Confirmed sections are sent to Claude as canon.
* A new planet replaces the old map, its edits and its history; the bible is kept.

Store layout, per world: `worlds/<id>/bible.json`, `lore.json`, `map/{world.npz, atlas.json,
preview.png, edits.json, edited.npz, atlas-current.json, preview-current.png, geography.md}`,
`history/{history.md, timeline.md, eras.png}`, plus `jobs/<jobId>.json`.

## Run it on a laptop

```bash
npm install
npm run engine:setup               # Python 3.10+; use PYTHON=python3.11 npm run engine:setup to pick one
cp .env.example .env               # then set, for local work:
#   WORLD_DB=file  WORLD_STORE=local  DATA_DIR=./data
#   ANTHROPIC_API_KEY=sk-ant-…      (optional: without it the chat says it is not set up)
npm start                          # http://localhost:3000/worlds.html
npm test                           # 14 end-to-end tests: real engine, mock Claude, file storage
```

Signing in still needs the site's normal auth (DynamoDB `ur_users`). To try the pages
without it, mint a cookie in the browser console of a local server:
`node -e "console.log(require('jsonwebtoken').sign({userId:'me',username:'me'}, process.env.JWT_SECRET))"`
and set it as the `ur_token` cookie for `localhost`.

## Production (EC2) checklist

See **AWS_SETUP.md §6** for the exact commands. In short:

1. Python 3.10+ on the instance, then `npm run engine:setup`.
2. DynamoDB table `ur_worlds` (key `worldId`), GSI `owner-index` (`ownerUserId` + `updatedAt`).
3. S3 bucket for world files (private, Block Public Access on).
4. IAM: add the table, its index and the bucket to the instance role's policy.
5. `.env`: `ANTHROPIC_API_KEY`, `WORLD_DB=dynamo`, `WORLD_STORE=s3`, `WORLD_BUCKET=…`.
6. nginx: `client_max_body_size 8m;` and `proxy_read_timeout 120s;` (in `nginx.conf.example`).
7. `pm2 restart universal-realms`, then open `/worlds.html` and run one world end to end.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Claude API key for the lore assistant. Unset → lore endpoints answer 503, everything else works. |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Model for chat, drafts and brief suggestions. |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Override for tests. |
| `LORE_MAX_PER_HOUR` | `60` | Lore requests per user per hour (in memory, per process). |
| `WORLD_DB` | `dynamo` | `dynamo` or `file`. |
| `WORLDS_TABLE` | `ur_worlds` | DynamoDB table name. |
| `WORLD_STORE` | `local` | `s3` or `local`. |
| `WORLD_BUCKET` | — | S3 bucket (required with `WORLD_STORE=s3`). |
| `DATA_DIR` | `./data` | Root for `file` / `local` storage. |
| `PYTHON_BIN` | `engine/.venv/bin/python`, else `python3` | Interpreter for engine jobs. |
| `JOB_CONCURRENCY` | `1` | Engine jobs at once. Each needs about 0.5 GB of memory at peak. |
| `JOB_TIMEOUT_MS` | `600000` | A job is killed after this long. |
| `MAX_WORLDS_PER_USER` | `25` | Worlds each user may keep. |

## Measured costs

On one vCPU: small map ≈ 5 s, large ≈ 19 s; Atlas Studio replay ≈ 5–10 s; history of
12 turns ≈ 10 s, 40 turns on a large map ≈ 46 s. Peak memory per job ≈ 0.5 GB.
Lore: the ~26 KB worldbuilder prompt is cached, so after the first message in a five-minute
window most input tokens are billed at the cache-read rate.

## Limits worth knowing

* Jobs run inside the web process's machine. If PM2 restarts mid-job, that job is marked
  failed on the next poll and the user can run it again; nothing half-written is kept.
* `LORE_MAX_PER_HOUR` is per process; with several Node processes, multiply it.
* Atlas Studio keeps unsaved edits in the browser (per map) until **Save to world**.
