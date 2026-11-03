#!/usr/bin/env python3
"""World Engine service: the one entry point the Universal Realms server calls.

Each command reads its inputs from files, writes its outputs into --out, and
prints ONE line of JSON on stdout as its last line:

    {"ok": true, ...summary...}           success
    {"ok": false, "error": "<reason>"}     a problem with the request (exit 2)

Anything else (a crash) exits 1 with a traceback on stderr. The server treats
exit 2 messages as safe to show the user and keeps exit 1 details in its log.

    python engine/service.py vocab
    python engine/service.py generate    --out DIR --brief TEXT [--seed N] [--size small|medium|large] [--title T]
    python engine/service.py apply-edits --world DIR/world.npz --edits EDITS.json --out DIR [--title T]
    python engine/service.py history     --world DIR/world.npz [--edits EDITS.json] --brief TEXT --out DIR
                                         [--turns N] [--years N] [--seed N]

The engine itself is Worldsmith (engine/worldsmith); this file only wires it
to the web app. Sizes are capped so one job fits a 4 GB instance.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
WF = HERE / "worldsmith" / "scripts" / "worldforge"
SAGA = HERE / "worldsmith" / "scripts" / "saga"
sys.path.insert(0, str(WF))

# Rows of latitude per size; the grid is twice as wide. Generation time on one
# vCPU, measured: small ~4 s, medium ~10 s, large ~18 s (plus rendering).
SIZES = {"small": 256, "medium": 384, "large": 512}
MAX_TURNS, MAX_YEARS = 60, 50


class UserError(Exception):
    """A problem with the request; its message is shown to the user."""


def done(**summary):
    print(json.dumps({"ok": True, **summary}))
    return 0


# ------------------------------------------------------------------ helpers

def _render_preview(world, path, title):
    import map_render as mr
    w = world["sea"].shape[1]
    img = mr.render_map(world, "atlas", title=title.upper()[:60], scale=2, labels=[],
                        km_per_cell=40075 / w)
    img = img[0] if isinstance(img, tuple) else img
    img.save(path, optimize=True)


def _world_summary(world):
    import numpy as np
    import spherical as sp
    import biomes as bm
    from world_fingerprint import baseline_fingerprint
    land = ~world["sea"]
    if sp.is_planet(world):
        land_fraction = sp.land_fraction_true(world)[0]
        wt = np.cos(np.radians(world["lat"]))
        shares = bm.shares(world["biome"], land, wt)
    else:
        land_fraction = float(land.mean())
        shares = bm.shares(world["biome"], land)
    top = sorted(shares.items(), key=lambda kv: -kv[1])[:6]
    h, w = world["sea"].shape
    return {
        "grid": [int(w), int(h)],
        "land_fraction": round(float(land_fraction), 3),
        "biomes": [{"name": k.replace("_", " "), "share": round(v, 3)} for k, v in top],
        "river_cells": int(world["rivers"].sum()),
        "fingerprint": baseline_fingerprint(world),
    }


def _run(args, what):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or ["no output"])[-1]
        if "fingerprint" in tail:
            raise UserError("These edits were made for a different version of the map.")
        raise RuntimeError(f"{what} failed: {tail}")
    return r.stdout


# ----------------------------------------------------------------- commands

def cmd_vocab(a):
    import brief
    import civilization as civ
    return done(terrain=sorted(brief.TERRAIN), implies=sorted(brief.IMPLIES_CIV),
                civ=sorted(civ.KEYWORDS), presets=sorted(civ.PRESETS))


def cmd_generate(a):
    import brief
    import world_io
    if a.size not in SIZES:
        raise UserError("Size must be small, medium or large.")
    text = (a.brief or "").strip()
    if not text or len(text) > 300:
        raise UserError("Describe the world in 1 to 300 characters.")
    seed = a.seed if a.seed is not None else 1
    if not 0 <= seed < 2 ** 31:
        raise UserError("Seed must be between 0 and 2147483647.")
    spp, civp, rep = brief.parse(text, seed=seed, nlat=SIZES[a.size])
    spp.plate_warp = 0.5          # organic coastlines for every new web world
    import spherical as sp
    world = sp.generate_sphere(spp)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    world_io.save_world(world, out / "world.npz", note=f"brief: {text}")
    from feature_editor import WorldEditor
    world_io.atlas_bundle(world, out / "atlas.json", editor=WorldEditor(world), title=a.title or f"Seed {seed}",
                          scale=2)
    _render_preview(world, out / "preview.png", a.title or f"Seed {seed}")
    return done(seed=seed, size=a.size, brief=text, matched=rep["matched"],
                unmatched=rep["unmatched_hint"][:12], matching=rep["matching"],
                physical=rep["physical"], **_world_summary(world))


def cmd_apply_edits(a):
    import world_io
    from feature_editor import WorldEditor
    base = world_io.load_world(a.world)
    try:
        editor = WorldEditor.from_json(base, a.edits)
    except ValueError as e:
        if "fingerprint" in str(e):
            raise UserError("These edits were made for a different version of the map.")
        raise UserError(f"The edits could not be applied: {e}")
    except (KeyError, TypeError) as e:
        raise UserError(f"The edits file is malformed: {e}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    world_io.save_world(editor.world, out / "edited.npz", edits=a.edits)
    title = a.title or f"Seed {base['params'].seed}"
    world_io.atlas_bundle(base, out / "atlas.json", editor=editor, title=title, scale=2)
    (out / "geography.md").write_text(editor.geography_entries("edits.json"), encoding="utf-8")
    _render_preview(editor.world, out / "preview.png", title)
    changed = int((editor.world["sea"] != base["sea"]).sum())
    return done(features=len(editor.features), edits_applied=editor.cursor, coast_cells_changed=changed,
                **_world_summary(editor.world))


def cmd_history(a):
    if not 5 <= a.turns <= MAX_TURNS:
        raise UserError(f"Turns must be between 5 and {MAX_TURNS}.")
    if not 1 <= a.years <= MAX_YEARS:
        raise UserError(f"Years per turn must be between 1 and {MAX_YEARS}.")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    wdir = out / "world"
    args = [SAGA / "wf_adapter.py", "--world", a.world, "--out", wdir]
    if a.edits:
        args += ["--edits", a.edits]
    if a.brief:
        args += ["--brief", a.brief]
    adapter = json.loads(_run(args, "Building peoples and polities"))
    sw_path = wdir / "saga_world.json"
    sw = json.loads(sw_path.read_text(encoding="utf-8"))
    sw.setdefault("meta", {})["years_per_turn"] = a.years
    sw_path.write_text(json.dumps(sw), encoding="utf-8")
    run = out / "run"
    _run([SAGA / "saga_sim.py", "simulate", sw_path, "--seed", a.seed, "--turns", a.turns, "--out", run], "History")
    _run([SAGA / "saga_sim.py", "seams", run / "chronicle.json", "--top", 8], "Story seams")
    _run([SAGA / "to_bible.py", run / "chronicle.json", "--out", out / "history.md"], "History write-up")
    mid = a.turns // 2
    _run([SAGA / "render_eras.py", "--chronicle", run / "chronicle.json", "--world-dir", wdir,
          "--turns", 0, mid, a.turns, "--out", out / "eras.png"], "Era maps")
    chron = json.loads((run / "chronicle.json").read_text(encoding="utf-8"))
    from collections import Counter
    counts = Counter(e["type"] for e in chron["events"])
    final_states = len(set(chron["snapshots"][-1]["ownership"].values()))
    seams = json.loads((run / "seams.json").read_text(encoding="utf-8")) if (run / "seams.json").exists() else []
    top = []
    for s in seams[:5]:
        e = s if "truth" in s else s.get("event", {})
        top.append({"id": e.get("id"), "year": e.get("year"), "type": e.get("type"), "text": e.get("truth", "")[:240]})
    (out / "timeline.md").write_text((run / "timeline.md").read_text(encoding="utf-8"), encoding="utf-8")
    return done(regions=adapter.get("regions"), starting_factions=adapter.get("factions"),
                terrain=adapter.get("terrain"), turns=a.turns, years_per_turn=a.years,
                span_years=a.turns * a.years, events=len(chron["events"]), event_types=dict(counts),
                final_states=final_states, seams=top)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Universal Realms World Engine service")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("vocab")
    g = sub.add_parser("generate")
    g.add_argument("--out", required=True)
    g.add_argument("--brief", required=True)
    g.add_argument("--seed", type=int)
    g.add_argument("--size", default="small")
    g.add_argument("--title")
    e = sub.add_parser("apply-edits")
    e.add_argument("--world", required=True)
    e.add_argument("--edits", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--title")
    h = sub.add_parser("history")
    h.add_argument("--world", required=True)
    h.add_argument("--edits")
    h.add_argument("--brief", default="")
    h.add_argument("--out", required=True)
    h.add_argument("--turns", type=int, default=30)
    h.add_argument("--years", type=int, default=25)
    h.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    fn = {"vocab": cmd_vocab, "generate": cmd_generate,
          "apply-edits": cmd_apply_edits, "history": cmd_history}[a.cmd]
    try:
        return fn(a)
    except UserError as err:
        print(json.dumps({"ok": False, "error": str(err)}))
        return 2
    except Exception:
        traceback.print_exc()
        print(json.dumps({"ok": False, "error": "The world engine hit an internal error."}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
