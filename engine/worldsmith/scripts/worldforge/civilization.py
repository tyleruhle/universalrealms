"""
civilization.py — the human layer, driven by user filters rather than by lore.

Use this when worldforge is generating a world on its own, without the
worldbuilder skill supplying cultures and history. It produces SPATIAL,
terrain-derived facts: where peoples are, who rules what, where force is
concentrated, how developed each region is. It does not write lore. If a
worldbuilder session is running, that session owns culture and this module
should be used only for the spatial scaffolding underneath it.

Everything here derives from the same movement-cost surface, which is the point:
culture spreads where travel is cheap, borders settle where it is expensive, and
development follows connectivity. Change the terrain and every layer moves.

    import civilization as civ
    p = civ.CivParams(political_fragmentation=0.7, militarization=0.3)
    layers = civ.build(world, p)
"""

from __future__ import annotations

import heapq
import re
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

NEI = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# Biome habitability, 0 unusable to 1 ideal. Indices match biomes.BIOMES.
HABITABILITY = {
    0: 0.0, 1: 0.0, 2: 0.02, 3: 0.15, 4: 0.45, 5: 0.95, 6: 0.90, 7: 0.45,
    8: 0.10, 9: 0.70, 10: 0.60, 11: 0.08, 12: 0.0, 13: 0.12, 14: 0.55,
    15: 0.60, 16: 0.30,
}


@dataclass
class CivParams:
    """The user-facing filters. Every one runs 0..1 and every one has a stated
    physical meaning, so a request like "fractured, militarised, poor" maps onto
    numbers rather than onto vibes."""

    seed: int = 0

    # --- the six filters -------------------------------------------------
    political_fragmentation: float = 0.5   # 0 = few vast empires, 1 = many small states
    cultural_diversity: float = 0.5        # 0 = one culture everywhere, 1 = highly local
    religiosity: float = 0.5               # 0 = religion tracks culture, 1 = crosses borders
    militarization: float = 0.5            # 0 = open borders, 1 = fortified everything
    economic_development: float = 0.5      # 0 = subsistence, 1 = dense industrial
    biome_pressure: float = 0.5            # 0 = people ignore biome, 1 = they cling to good land

    # --- secondary knobs -------------------------------------------------
    trade_openness: float = 0.5            # how far goods and influence travel
    urbanization: float = 0.5              # concentration vs spread of population
    sea_affinity: float = 0.6              # willingness to cross water
    notes: dict = field(default_factory=dict)


PRESETS = {
    "fractured warring states": dict(political_fragmentation=0.85, militarization=0.8,
                                     cultural_diversity=0.7, trade_openness=0.3),
    "single hegemonic empire": dict(political_fragmentation=0.1, militarization=0.45,
                                    cultural_diversity=0.25, trade_openness=0.7),
    "mercantile city-states": dict(political_fragmentation=0.8, militarization=0.35,
                                   economic_development=0.75, trade_openness=0.9,
                                   sea_affinity=0.9, urbanization=0.85),
    "post-collapse frontier": dict(political_fragmentation=0.75, economic_development=0.2,
                                   urbanization=0.25, militarization=0.55,
                                   trade_openness=0.25),
    "theocratic union": dict(religiosity=0.95, political_fragmentation=0.3,
                             cultural_diversity=0.35),
    "isolated valley cultures": dict(cultural_diversity=0.95, trade_openness=0.15,
                                     political_fragmentation=0.8, sea_affinity=0.2),
}

KEYWORDS = {
    "fractured": ("political_fragmentation", 0.85), "fragmented": ("political_fragmentation", 0.85),
    "unified": ("political_fragmentation", 0.15), "empire": ("political_fragmentation", 0.15),
    "imperial": ("political_fragmentation", 0.2), "city-states": ("political_fragmentation", 0.8),
    "militarised": ("militarization", 0.85), "militarized": ("militarization", 0.85),
    "warring": ("militarization", 0.85), "peaceful": ("militarization", 0.15),
    "demilitarised": ("militarization", 0.1),
    "diverse": ("cultural_diversity", 0.85), "homogeneous": ("cultural_diversity", 0.15),
    "monoculture": ("cultural_diversity", 0.1),
    "devout": ("religiosity", 0.9), "theocratic": ("religiosity", 0.95),
    "secular": ("religiosity", 0.15),
    "wealthy": ("economic_development", 0.85), "industrial": ("economic_development", 0.9),
    "prosperous": ("economic_development", 0.8), "poor": ("economic_development", 0.2),
    "subsistence": ("economic_development", 0.12), "pre-industrial": ("economic_development", 0.3),
    "mercantile": ("trade_openness", 0.9), "isolated": ("trade_openness", 0.15),
    "insular": ("trade_openness", 0.2), "seafaring": ("sea_affinity", 0.9),
    "landlocked": ("sea_affinity", 0.15), "urban": ("urbanization", 0.85),
    "rural": ("urbanization", 0.2),
}


def match_keywords(text, words, legacy=False):
    """Which keywords a brief contains, longest first, as whole words.

    Raw substring matching let "demilitarised" also match "militarised",
    "pre-industrial" match "industrial", "swarm" match "warm" and "islanders"
    match "island"; the right value won only by dictionary order. Now each
    keyword must start and end on a word boundary (a plural -s/-es is allowed),
    and text claimed by a longer keyword cannot be matched again by a shorter
    one, so "kingdoms" is reported once, not as "kingdom" too.

    `legacy=True` reproduces the old substring behaviour exactly, for worlds
    that were generated from a brief before this change.
    """
    t = text.lower()
    if legacy:
        return [w for w in words if w in t]
    taken = []
    found = []
    for w in sorted(words, key=len, reverse=True):
        for m in re.finditer(r"(?<![a-z0-9-])" + re.escape(w) + r"(?:e?s)?(?![a-z0-9-])", t):
            a, b = m.span()
            if any(a < y and x < b for x, y in taken):
                continue
            taken.append((a, b))
            found.append(w)
            break
    return found


def params_from_prompt(text, seed=0, legacy_matching=False):
    """Map a plain-language brief onto CivParams. Deliberately dumb: exact
    preset match first, then keyword hits. Report what it matched so the user
    can correct it rather than discovering the guess in the output."""
    kw = {}
    matched = []
    presets = match_keywords(text, list(PRESETS), legacy_matching)
    for name in PRESETS:                      # keep table order for overlaps
        if name in presets:
            kw.update(PRESETS[name])
            matched.append(name)
    words = match_keywords(text, list(KEYWORDS), legacy_matching)
    for word, (field_, value) in KEYWORDS.items():
        if word in words:
            kw[field_] = value
            matched.append(word)
    p = CivParams(seed=seed, **kw)
    p.notes["matched"] = matched
    p.notes["prompt"] = text
    p.notes["matching"] = "legacy substring" if legacy_matching else "whole word"
    return p


# ------------------------------------------------------------ cost surface

def movement_cost(world, p: CivParams, biome_costs=None):
    """One cost surface, used by every layer below.

    Travel is cheap along rivers and coasts and expensive over slope and hostile
    biome. `sea_affinity` sets the price of open water: low makes seas into
    walls and produces isolated island cultures, high makes them highways and
    produces thalassocracies. That single number changes the political map more
    than any other.
    """
    elev, sea = world["elevation"], world["sea"]
    land = ~sea
    biome = world["biome"]

    gy, gx = np.gradient(elev)
    slope = np.hypot(gy, gx)
    slope = slope / (np.quantile(slope[land], 0.98) + 1e-9)

    hab = np.zeros(biome.shape, np.float32)
    for k, v in (biome_costs or HABITABILITY).items():
        hab[biome == k] = v

    cost = 1.0 + 5.5 * np.clip(slope, 0, 3)
    cost += 4.0 * p.biome_pressure * (1.0 - hab)
    if "rivers" in world:
        cost[world["rivers"]] *= 0.45
    coast = ndimage.binary_dilation(land) & sea
    near = ndimage.distance_transform_edt(~coast) < 6
    cost[near & land] *= 0.6

    # water: passable but priced by sea_affinity
    water_cost = 2.5 + 26.0 * (1.0 - p.sea_affinity) ** 2
    cost[sea] = water_cost
    deep = sea & (ndimage.distance_transform_edt(sea) > 18)
    cost[deep] = water_cost * 2.4
    return cost.astype(np.float32)


_XS = None   # per-row east-west scale, set by build() for spherical worlds


def _dijkstra_regions(cost, seeds, wrap=True, xscale=None):
    """`xscale` (per row) is the true length of an east-west step relative to a
    north-south one. On an equirectangular planet it is cos(latitude); without it
    high-latitude regions grow as thin north-south strips."""
    h, w = cost.shape
    if xscale is None:
        xscale = np.ones(h)
    step = {(dy, dx): [float(np.hypot(dy, dx * xscale[r])) for r in range(h)]
            for dy, dx in NEI}
    dist = np.full(h * w, np.inf)
    owner = np.full(h * w, -1, np.int32)
    pq = []
    for i, (y, x) in enumerate(seeds):
        idx = y * w + x
        dist[idx] = 0.0
        owner[idx] = i
        heapq.heappush(pq, (0.0, idx, i))
    flat = cost.ravel()
    while pq:
        dv, idx, who = heapq.heappop(pq)
        if dv > dist[idx]:
            continue
        y, x = divmod(idx, w)
        for dy, dx in NEI:
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= h:
                continue
            if wrap:
                nx %= w
            elif nx < 0 or nx >= w:
                continue
            n = ny * w + nx
            nd = dv + flat[n] * step[(dy, dx)][y]
            if nd < dist[n]:
                dist[n] = nd
                owner[n] = who
                heapq.heappush(pq, (nd, n, who))
    return owner.reshape(h, w), dist.reshape(h, w)


def _seed_points(weight, n, min_sep, rng):
    h, w = weight.shape
    global _XS
    if _XS is None or len(_XS) != h:
        _XS = np.ones(h)
    s = weight.copy()
    out = []
    for _ in range(n):
        i = int(np.argmax(s))
        y, x = divmod(i, w)
        if s[y, x] <= 0:
            break
        out.append((int(y), int(x)))
        yy, xx = np.ogrid[:h, :w]
        dx_ = np.minimum(np.abs(xx - x), w - np.abs(xx - x)) * _XS[y]
        d2 = (yy - y) ** 2 + dx_ ** 2
        s[d2 < min_sep ** 2] = 0
    return out


# ----------------------------------------------------------------- layers

def build(world, p: CivParams):
    """Produce every civilization layer. Returns a dict of arrays plus a
    per-polity table. Order is deliberate: population, then culture, then
    polities inside culture, then religion across it, then military on the
    borders that resulted, then development from the connectivity of all of it.
    """
    rng = np.random.default_rng(p.seed)
    elev, sea = world["elevation"], world["sea"]
    land = ~sea
    h, w = elev.shape
    cost = movement_cost(world, p)
    global _XS
    _XS = (np.clip(np.cos(np.radians(world["lat"][:, 0])), 0.08, 1.0)
           if "lat" in world else np.ones(h))
    xs = _XS

    # --- population density ------------------------------------------------
    hab = np.zeros(world["biome"].shape, np.float32)
    for k, v in HABITABILITY.items():
        hab[world["biome"] == k] = v
    coast = ndimage.binary_dilation(land) & sea
    harbor = np.exp(-ndimage.distance_transform_edt(~coast) / 14.0)
    # Discharge (rain-weighted) when the world has it: a dry basin drains a huge
    # AREA but carries little WATER, and people settle on water, not on area.
    flow = world.get("discharge", world.get("accumulation", np.ones_like(elev)))
    water = np.clip(np.log1p(flow) / np.log1p(flow.max()), 0, 1)
    dens = (0.45 * hab + 0.30 * water + 0.25 * harbor) * land
    dens = ndimage.gaussian_filter(dens, 3.0) * land
    if land.any():
        dens = dens / (np.quantile(dens[land], 0.995) + 1e-9)
    dens = np.clip(dens, 0, 1) ** (0.6 + 1.4 * p.urbanization)

    # --- cultures ----------------------------------------------------------
    n_cult = int(round(4 + 46 * p.cultural_diversity ** 1.6))
    sep_c = max(6, int(0.055 * w * (1.0 - 0.7 * p.cultural_diversity)))
    cult_seeds = _seed_points(dens * land, n_cult, sep_c, rng)
    culture, cult_dist = _dijkstra_regions(cost, cult_seeds, xscale=xs)
    culture[~land] = -1

    # --- polities: cultures subdivide, they do not straddle ----------------
    n_pol = int(round(n_cult * (1.0 + 5.0 * p.political_fragmentation)))
    sep_p = max(4, int(sep_c * (1.0 - 0.6 * p.political_fragmentation)))
    pol_seeds = _seed_points(dens * land, n_pol, sep_p, rng)
    polity, pol_dist = _dijkstra_regions(cost, pol_seeds, xscale=xs)
    polity[~land] = -1
    # A polity is its own cell within its culture, so borders stay nested. Encode
    # the pair, then RELABEL to consecutive ids: the raw composite leaks
    # arithmetic into the interface, where a user sees "polity 8465" and cannot
    # tell whether that is an identity or a bug.
    pair = np.where(land, polity * 128 + np.maximum(culture, 0), -1)
    vals = np.unique(pair[land])
    remap = {int(v): i for i, v in enumerate(vals)}
    polity = np.full_like(pair, -1)
    for v, i in remap.items():
        polity[pair == v] = i

    # --- religion: crosses political borders in proportion to religiosity --
    n_rel = max(1, int(round(n_cult * (1.0 - 0.75 * p.religiosity))))
    rel_cost = cost * (1.0 - 0.55 * p.religiosity) + 0.55 * p.religiosity
    rel_seeds = _seed_points(dens * land, n_rel, sep_c, rng)
    religion, _ = _dijkstra_regions(rel_cost, rel_seeds, xscale=xs)
    religion[~land] = -1

    # --- military posture --------------------------------------------------
    border = np.zeros((h, w), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = polity
        b = np.roll(np.roll(polity, -dy, 0), -dx, 1)
        border |= (a != b) & (a >= 0) & (b >= 0)
    # chokepoints: cheap ground with expensive ground on both sides
    smooth = ndimage.uniform_filter(cost, 9)
    choke = (cost < np.quantile(cost[land], 0.35)) & (smooth > np.quantile(smooth[land], 0.6))
    garrison = ndimage.gaussian_filter(
        (border * 1.0 + 0.8 * choke) * land, 2.5) * p.militarization
    garrison = np.clip(garrison / (np.quantile(garrison[land], 0.995) + 1e-9), 0, 1)

    # --- economic development ---------------------------------------------
    # connectivity: how cheaply a cell reaches the population around it
    reach = ndimage.gaussian_filter(dens / (cost + 1e-3), 9.0) * land
    reach = reach / (np.quantile(reach[land], 0.99) + 1e-9) if land.any() else reach
    devel = (0.45 * np.clip(reach, 0, 1) + 0.30 * dens + 0.25 * hab) * land
    devel = np.clip(devel, 0, 1) * (0.25 + 1.5 * p.economic_development)
    devel = np.clip(ndimage.gaussian_filter(devel, 4.0) * land, 0, 1)
    devel *= (1.0 - 0.35 * garrison)          # war is expensive

    return dict(params=p, cost=cost, density=dens, culture=culture,
                polity=polity, religion=religion, border=border,
                garrison=garrison, development=devel,
                culture_seeds=cult_seeds, polity_seeds=pol_seeds,
                religion_seeds=rel_seeds)


def summarize(layers, world, weights=None):
    land = ~world["sea"]
    w = np.ones_like(world["elevation"], np.float32) if weights is None else weights
    lw = w * land
    def share(mask):
        return float((mask * lw).sum() / lw.sum())
    return {
        "cultures": int(len(np.unique(layers["culture"][land]))),
        "polities": int(len(np.unique(layers["polity"][land]))),
        "religions": int(len(np.unique(layers["religion"][land]))),
        "mean_development": round(float((layers["development"] * lw).sum() / lw.sum()), 3),
        "militarized_land": round(share(layers["garrison"] > 0.35), 3),
        "high_density_land": round(share(layers["density"] > 0.55), 3),
    }
