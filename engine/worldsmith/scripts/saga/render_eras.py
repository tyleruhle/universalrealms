#!/usr/bin/env python3
"""
render_eras.py: political maps of a saga chronicle, one panel per era.

Needs the region_grid.npy written by wf_adapter.py (and optionally
elevation.npy / sea.npy for relief). Faction colors are stable across eras
and across branches, so two renders of the same world can be compared by eye.

    python render_eras.py --chronicle out/chronicle.json --world-dir world_dir \
        --turns 0 10 20 30 --out out/eras.png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


def color_for(fid):
    """Golden-angle hue from the faction's creation index, mid-band saturation and
    value (worldforge style-political convention). Ids are created in a fixed
    order, so a faction keeps its color across eras and across branches."""
    try:
        k = int(fid.lstrip("f"))
    except ValueError:
        k = int(hashlib.md5(fid.encode()).hexdigest()[:6], 16)
    hue = (0.11 + k * 0.618034) % 1.0
    sat = 0.48 + 0.14 * ((k * 7) % 3) / 2
    val = 0.70 + 0.12 * ((k * 5) % 2)
    return matplotlib.colors.hsv_to_rgb([hue, sat, val])


def shade(elev):
    gy, gx = np.gradient(elev)
    s = np.clip(0.75 + 6.0 * (gx - gy), 0.45, 1.15)
    return s[..., None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chronicle", required=True)
    ap.add_argument("--world-dir", required=True)
    ap.add_argument("--turns", type=int, nargs="*")
    ap.add_argument("--out", default="eras.png")
    a = ap.parse_args()

    chron = json.load(open(a.chronicle))
    grid = np.load(os.path.join(a.world_dir, "region_grid.npy"))
    ep = os.path.join(a.world_dir, "elevation.npy")
    sp = os.path.join(a.world_dir, "sea.npy")
    relief = shade(np.load(ep)) if os.path.exists(ep) else 1.0
    sea = np.load(sp) if os.path.exists(sp) else grid < 0

    snaps = chron["snapshots"]
    turns = a.turns or sorted({0, len(snaps) // 3, 2 * len(snaps) // 3, len(snaps) - 1})
    turns = [t for t in turns if 0 <= t < len(snaps)]
    rows = len(turns)
    h, w = grid.shape
    fig, axes = plt.subplots(rows, 1, figsize=(10, 10 * h / w * rows + 1.0 * rows), squeeze=False)
    names = chron["faction_names"]
    y0, ypt = chron.get("start_year", 0), chron["years_per_turn"]

    for ax, t in zip(axes[:, 0], turns):
        own = snaps[t]["ownership"]
        img = np.zeros((h, w, 3), np.float32)
        img[sea] = (0.16, 0.24, 0.36)
        present = {}
        for rid, fid in own.items():
            rnum = int(rid[1:])
            m = grid == rnum
            if fid:
                img[m] = color_for(fid)
                present[fid] = present.get(fid, 0) + int(m.sum())
        if not np.isscalar(relief):
            img[~sea] = np.clip(img[~sea] * relief[~sea], 0, 1)
        # borders
        b = np.zeros((h, w), bool)
        ogrid = np.full(grid.shape, -1)
        fids = sorted(set(f for f in own.values() if f))
        for k, fid in enumerate(fids):
            for rid, f in own.items():
                if f == fid:
                    ogrid[grid == int(rid[1:])] = k
        for dy, dx in ((0, 1), (1, 0)):
            o2 = np.roll(np.roll(ogrid, -dy, 0), -dx, 1)
            b |= (ogrid != o2) & (ogrid >= 0) & (o2 >= 0)
        img[b] = (0.08, 0.08, 0.08)
        ax.imshow(img, interpolation="nearest")
        ax.set_axis_off()
        ax.set_title(f"Year {y0 + t * ypt}", loc="left", fontsize=11)
        top = sorted(present.items(), key=lambda kv: -kv[1])[:10]
        ax.legend(handles=[Patch(color=color_for(f), label=names.get(f, f)) for f, _ in top],
                  loc="upper center", bbox_to_anchor=(0.5, -0.01), fontsize=7, frameon=False, ncol=5)
    plt.tight_layout()
    plt.savefig(a.out, dpi=110)
    print(a.out)


if __name__ == "__main__":
    main()
