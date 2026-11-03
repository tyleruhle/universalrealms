#!/usr/bin/env python3
"""
wf_adapter.py: turn a worldforge world into a saga_world.json.

Regions are worldforge polities (terrain-derived political cells). Factions
start as one per culture, owning that culture's polities, so the sim begins
from "peoples on the land" and history decides who ends up ruling what.
Use --factions polity to start every polity independent (warring-states start).

    python wf_adapter.py --seed 1174 --brief "fractured island kingdoms, devout" --out world_dir/
    python wf_adapter.py --seed 1174 --flat --size 384 --preset "fractured warring states" --out world_dir/

Default is a whole planet (worldforge spherical.py). A --brief is parsed by
worldforge brief.py, so BOTH the physical and the human halves apply, and the
matched keywords are printed: show them to the user. --flat uses
worldforge_core on a 2:1 region map instead.

Writes world_dir/saga_world.json, region_grid.npy, elevation.npy, sea.npy.
Edit saga_world.json before simulating: rename regions and factions, add secrets,
set succession laws from the worldbuilder bible. The sim reads only the json;
the .npy files are for render_eras.py.
"""
from __future__ import annotations

import argparse
import sys as _sys
_sys.dont_write_bytecode = True
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

SUCCESSIONS = ["primogeniture", "elective", "tanistry", "appointment", "council", "divine"]
SYLLABLE_BANK = [
    ["ka", "ri", "to", "ve", "ma", "sel", "dor", "an", "is", "ul", "mer", "th"],
    ["vae", "lin", "or", "sa", "rhen", "el", "ith", "ae", "lor"],
    ["kor", "dra", "gun", "ba", "tor", "ek", "gra", "uk", "zar"],
    ["sha", "mir", "zan", "ha", "qa", "rim", "das", "il", "sur"],
    ["bo", "nu", "ta", "ke", "mo", "ri", "pa", "lu", "ho"],
    ["ost", "vil", "brek", "an", "tho", "ska", "frey", "ulf", "gar"],
    ["xi", "lan", "chen", "wu", "mei", "tao", "rin", "su", "jai"],
    ["cae", "lus", "ver", "num", "ti", "aur", "mar", "sex", "pol"],
]


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WF = os.path.normpath(os.path.join(HERE, "..", "worldforge"))


def load_worldforge(path):
    sys.dont_write_bytecode = True
    sys.path.insert(0, path)
    import worldforge_core as wf  # noqa
    import civilization as civ  # noqa
    import biomes  # noqa
    import brief  # noqa
    import spherical as sp  # noqa
    return wf, civ, biomes, brief, sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worldforge", default=DEFAULT_WF, help="path to worldforge scripts (default: sibling folder)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--flat", action="store_true", help="flat region map instead of a planet")
    ap.add_argument("--size", type=int, default=384, help="flat: map width")
    ap.add_argument("--nlat", type=int, default=320, help="planet: latitude rows (width is 2x)")
    ap.add_argument("--preset", default=None, help="a civilization.PRESETS key")
    ap.add_argument("--brief", default=None, help="plain-language civ brief, e.g. 'fractured devout poor'")
    ap.add_argument("--factions", choices=["culture", "polity"], default="culture")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default="saga_world")
    ap.add_argument("--world", default=None,
                    help="a saved world (.npz from world_io.save_world); use instead of regenerating")
    ap.add_argument("--edits", default=None,
                    help="an edit manifest (feature editor / Atlas Studio) to replay before history")
    a = ap.parse_args()

    wf, civ, biomes, brief, sp = load_worldforge(a.worldforge)
    report = None
    if a.brief:
        spp, p, report = brief.parse(a.brief, seed=a.seed, nlat=a.nlat)
    else:
        spp = sp.SphereParams(seed=a.seed, nlat=a.nlat)
        if a.preset and a.preset not in civ.PRESETS:
            sys.exit(f"unknown preset {a.preset!r}; options: {sorted(civ.PRESETS)}")
        p = civ.CivParams(seed=a.seed, **(civ.PRESETS.get(a.preset, {}) if a.preset else {}))
    import world_io  # noqa: E402  (worldforge path is on sys.path now)
    terrain_source = "seed"
    ignored_physical = []
    if a.world:
        # The terrain already exists: the brief can still set the human
        # filters, but its physical words cannot change a saved planet. Say so.
        world = world_io.load_world(a.world)
        terrain_source = "saved world"
        if report:
            ignored_physical = sorted(report["physical"])
        a.seed = int(world["params"].seed)
        a.flat = not isinstance(world["params"], sp.SphereParams)
        a.nlat = int(world["sea"].shape[0])
        a.size = int(world["sea"].shape[1])
    elif a.flat:
        world = wf.generate(wf.WorldParams(seed=a.seed, width=a.size, height=a.size // 2))
    else:
        world = sp.generate_sphere(spp)
    if a.edits:
        # Replays the user's named edits onto this exact planet. The manifest's
        # terrain fingerprint refuses any other world, so a history can never
        # run on edits made for a different seed or resolution.
        import feature_editor as fe
        world = fe.WorldEditor.from_json(world, a.edits).world
        terrain_source += " + edits"
    L = civ.build(world, p)

    pol, cul, rel = L["polity"], L["culture"], L["religion"]
    land = pol >= 0
    rng = np.random.default_rng([a.seed, 99])
    ids = sorted(int(x) for x in np.unique(pol[land]))

    # adjacency, same wrap convention as civilization.build
    adj = defaultdict(set)
    for dy, dx in ((0, 1), (1, 0)):
        b = np.roll(np.roll(pol, -dy, 0), -dx, 1)
        m = (pol != b) & (pol >= 0) & (b >= 0)
        for u, v in set(zip(pol[m].tolist(), b[m].tolist())):
            adj[u].add(v); adj[v].add(u)

    sea = world["sea"]
    from scipy import ndimage
    from scipy.spatial import cKDTree
    coast = ndimage.binary_dilation(sea) & land

    # sea lanes: coastal regions within reach across water become neighbors.
    # Reach scales with sea_affinity, the same knob worldforge uses to decide
    # whether seas are walls or highways. Without this, island worlds have
    # regions history can never touch.
    reach = (0.01 + 0.07 * p.sea_affinity) * pol.shape[1]
    cy, cx = np.nonzero(coast)
    lanes = defaultdict(set)
    if len(cy):
        step = max(1, len(cy) // 20000)
        cy, cx = cy[::step], cx[::step]
        owner = pol[cy, cx]
        pts = np.c_[cy, cx].astype(float)
        tree = cKDTree(pts)
        for i, j in tree.query_pairs(r=reach):
            u, v = int(owner[i]), int(owner[j])
            if u != v and v not in adj[u]:
                lanes[u].add(v); lanes[v].add(u)
    cost = L["cost"]
    cq = np.quantile(cost[land], [0.05, 0.95])
    elev_above = np.clip(world["elevation"] - world["sea_level"], 0, None)
    ehi = np.quantile(elev_above[land], 0.9)
    dens_q = np.quantile(L["density"][land], 0.99) + 1e-9

    cultures = sorted(int(x) for x in np.unique(cul[land]))
    religions = sorted(int(x) for x in np.unique(rel[land]))
    cname = {c: f"c{c}" for c in cultures}
    world_cultures = {cname[c]: {"syllables": SYLLABLE_BANK[i % len(SYLLABLE_BANK)],
                                 "endings": ["", "n", "r", "th", "s"]} for i, c in enumerate(cultures)}

    def nm(culture_key, parts=2):
        syl = world_cultures[culture_key]["syllables"]
        s = "".join(syl[int(rng.integers(len(syl)))] for _ in range(parts))
        return s.capitalize()

    regions = []
    for i in ids:
        m = pol == i
        n = int(m.sum())
        c = Counter(cul[m].tolist()).most_common(1)[0][0]
        r = Counter(rel[m].tolist()).most_common(1)[0][0]
        bio = Counter(world["biome"][m].tolist()).most_common(1)[0][0]
        bname = biomes.BIOMES[bio][0].replace("_", " ") if bio in biomes.BIOMES else f"biome {bio}"
        mean_e = float(elev_above[m].mean())
        terrain = "highlands" if mean_e > ehi * 0.8 else bname
        if coast[m].mean() > 0.05:
            terrain += ", coastal"
        defend = float(np.clip((cost[m].mean() - cq[0]) / (cq[1] - cq[0] + 1e-9), 0, 1))
        ys, xs = np.nonzero(m)
        regions.append({
            "id": f"r{i}", "name": nm(cname[c]), "terrain": terrain,
            "wealth": round(float(L["development"][m].mean()), 3),
            "population": round(float(np.clip(L["density"][m].mean() / dens_q * 1.2, 0, 1)), 3),
            "defensibility": round(defend, 3), "culture": cname[c], "religion": f"faith{r}",
            "neighbors": sorted(f"r{x}" for x in adj[i] | lanes[i]),
            "sea_lanes": sorted(f"r{x}" for x in lanes[i]),
            "chokepoint": bool(n < np.median([int((pol == j).sum()) for j in ids[:50]]) * 0.6 and defend > 0.5),
            "cells": n, "centroid": [int(ys.mean()), int(xs.mean())],
        })

    factions = []
    if a.factions == "culture":
        groups = defaultdict(list)
        for r in regions:
            groups[r["culture"]].append(r["id"])
        items = sorted(groups.items())
    else:
        items = [(r["culture"], [r["id"]]) for r in regions]
    for k, (ck, regs) in enumerate(items, 1):
        rr = [x for x in regions if x["id"] in regs]
        relig = Counter(x["religion"] for x in rr).most_common(1)[0][0]
        factions.append({
            "id": f"f{k}", "name": f"Realm of {rr[0]['name']}" if len(rr) > 1 else rr[0]["name"],
            "culture": ck, "religion": relig,
            "succession": SUCCESSIONS[int(rng.integers(len(SUCCESSIONS)))],
            "regions": regs,
            "legitimacy": round(float(rng.uniform(0.4, 0.8)), 2),
            "cohesion": round(float(np.clip(0.75 - 0.015 * len(regs) + rng.normal(0, 0.05), 0.2, 0.9)), 2),
            "militarism": round(float(np.clip(p.militarization + rng.normal(0, 0.15), 0.05, 0.95)), 2),
            "treasury": round(float(np.mean([x["wealth"] for x in rr])), 2),
            "grievances": {}, "allies": [], "claims": [],
        })

    out = {
        "schema_version": 1,
        "meta": {"name": a.name or f"Worldforge seed {a.seed}", "start_year": 0, "years_per_turn": 10,
                 "source": {"worldforge_seed": a.seed, "geometry": "flat" if a.flat else "planet",
                            "size": a.size if a.flat else None, "nlat": None if a.flat else a.nlat,
                            "preset": a.preset, "brief": a.brief, "brief_matched": report and report["matched"],
                            "factions_from": a.factions,
                            "terrain": terrain_source, "world_file": a.world, "edits": a.edits,
                            "terrain_fingerprint": world_io.baseline_fingerprint(world)}},
        "cultures": world_cultures,
        "religions": {f"faith{r}": {} for r in religions},
        "regions": regions, "factions": factions, "secrets": [],
    }
    os.makedirs(a.out, exist_ok=True)
    json.dump(out, open(os.path.join(a.out, "saga_world.json"), "w"), indent=1)
    grid = np.full(pol.shape, -1, np.int32)
    grid[land] = pol[land]
    np.save(os.path.join(a.out, "region_grid.npy"), grid)
    np.save(os.path.join(a.out, "elevation.npy"), world["elevation"].astype(np.float32))
    np.save(os.path.join(a.out, "sea.npy"), sea)
    print(json.dumps({"brief_matched": report and report["matched"],
                      "terrain": terrain_source,
                      "brief_physical_ignored": ignored_physical or None,
                      "civ_filters": report and report["civil"],
                      "regions": len(regions), "factions": len(factions), "cultures": len(cultures),
                      "isolated_regions": [r["id"] for r in regions if not r["neighbors"]],
                      "out": a.out}, indent=1))


if __name__ == "__main__":
    main()
