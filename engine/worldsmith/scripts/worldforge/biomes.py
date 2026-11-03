"""
biomes.py — moisture refinement and biome classification that holds together.

Three failures this module fixes, diagnosed by measurement rather than by eye.

1. RUNAWAY ARIDITY. A pure advect-and-deplete moisture model strips air to zero
   a few hundred kilometres inland, because nothing puts water back. Measured on
   a generated planet: 70% of land below the dry threshold, 52% of land classed
   desert or shrubland against Earth's ~19% desert. Real continents are wetter
   than that because land recycles its own water. Roughly a third to a half of
   continental rainfall on Earth is re-evaporated from the land it already fell
   on. Without a recycling term, every generator produces a Dune.

2. CONTOUR BANDING. Classifying a smooth field with fixed thresholds draws the
   isolines of that field, so biomes appear as concentric bands parallel to the
   coast. The fix is to jitter the THRESHOLDS with low-frequency noise, never to
   blur the classified output, which would average biome IDs into meaningless
   intermediate values.

3. SNOW BY ALTITUDE INSTEAD OF TEMPERATURE. Keying alpine and snowcap to
   relative elevation puts identical snowlines on a tropical and a polar range.
   Snow is a temperature phenomenon; the lapse rate already carries elevation
   into temperature, so classify on the result.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

# Extended palette. Transitional classes matter more than exotic ones: most of
# what reads as "wrong" in a generated biome map is a missing intermediate.
BIOMES = {
    0:  ("ocean",            (26, 52, 92)),
    1:  ("shallows",         (48, 92, 136)),
    2:  ("ice",              (232, 238, 242)),
    3:  ("tundra",           (142, 152, 138)),
    4:  ("taiga",            (74, 104, 82)),
    5:  ("temperate_forest", (72, 122, 68)),
    6:  ("grassland",        (150, 166, 96)),
    7:  ("shrubland",        (146, 140, 92)),
    8:  ("desert",           (206, 184, 130)),
    9:  ("savanna",          (176, 168, 92)),
    10: ("rainforest",       (44, 102, 56)),
    11: ("alpine",           (168, 164, 160)),
    12: ("snowcap",          (245, 245, 248)),
    13: ("cold_desert",      (178, 172, 148)),
    14: ("wetland",          (86, 118, 96)),
    15: ("beach",            (222, 208, 168)),
    16: ("boreal_wetland",   (96, 116, 104)),
}

LUT = np.zeros((len(BIOMES), 3), np.float32)
for _k, (_n, _c) in BIOMES.items():
    LUT[_k] = _c


def _fbm_like(shape, rng, scale):
    """Cheap low-frequency field for threshold jitter."""
    h, w = shape
    small = rng.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    ys = np.linspace(0, small.shape[0] - 1, h)
    xs = np.linspace(0, small.shape[1] - 1, w)
    return ndimage.map_coordinates(small, np.meshgrid(ys, xs, indexing="ij"),
                                   order=3, mode="reflect")


def refine_moisture(rain, sea, temp, elev_above, wrap=False,
                    coastal_gain=0.26, coastal_scale=18.0,
                    recycling=0.28, diffusion=6.0, floor=0.04):
    """Turn a raw advection result into a moisture field worth classifying on.

    Four corrections, in order:

    `coastal_gain` adds humidity near the shore. Maritime margins are wetter
    than any advection sweep alone will make them, and this is the single
    largest visual improvement.

    `recycling` re-injects a fraction of local rainfall as new local humidity,
    standing in for evapotranspiration. This is the term whose absence causes
    runaway aridity: without it, interiors dry monotonically with distance from
    the coast and every continent becomes a desert with a green rim.

    `diffusion` mixes laterally, so a rain shadow is a gradient rather than a
    cliff and single dry cells do not survive.

    `floor` keeps a small baseline so nothing classifies on exactly zero.

    Finally the field is rescaled against its own land median rather than a high
    quantile. Normalising by a high quantile lets a handful of soaked windward
    peaks set the scale and pushes the entire continent below every threshold,
    which is exactly the measured failure.
    """
    mode = "wrap" if wrap else "nearest"
    land = ~sea
    out = rain.astype(np.float32).copy()

    coast = ndimage.binary_dilation(land) & sea
    d_coast = ndimage.distance_transform_edt(~coast).astype(np.float32)
    out += coastal_gain * np.exp(-d_coast / coastal_scale)

    if recycling > 0:
        recycled = ndimage.gaussian_filter(out * land, sigma=diffusion * 1.5,
                                           mode=("nearest", mode))
        out += recycling * recycled

    out = ndimage.gaussian_filter(out, sigma=diffusion, mode=("nearest", mode))

    # warmer air carries more water; cold land is dry even beside an ocean
    out *= (0.55 + 0.55 * np.clip(temp, 0, 1))
    out += floor

    if land.any():
        med = float(np.median(out[land]))
        out = out / (2.0 * med + 1e-9)
    return np.clip(out, 0, 1.4)


def classify(elev, sea_level, temp, moisture, accumulation=None, slope=None,
             seed=0, jitter_temp=0.05, jitter_moist=0.07, jitter_scale=28,
             wetland_q=0.955, majority=True):
    """Whittaker classification with jittered thresholds and real overrides.

    Order matters and is deliberate: water, then the moisture/temperature
    matrix, then speckle removal, then azonal classes that override climate
    (wetland, beach), then the cold overrides last, because a frozen peak is
    snow regardless of what the moisture band said.

    A mode filter is used for speckle rather than a blur, because a blur would
    average biome IDs and invent classes that are not in the table.
    """
    rng = np.random.default_rng(seed)
    shape = elev.shape
    land = elev > sea_level

    t = np.clip(temp + jitter_temp * (_fbm_like(shape, rng, jitter_scale) - 0.5) * 2, 0, 1)
    m = np.clip(moisture + jitter_moist * (_fbm_like(shape, rng, jitter_scale) - 0.5) * 2,
                0, 1.4)

    b = np.zeros(shape, np.uint8)
    b[~land] = np.where(elev[~land] > sea_level - 0.035, 1, 0)

    # ---- temperature bands (5) x moisture bands (4) -----------------------
    polar = t <= 0.16
    cold = (t > 0.16) & (t <= 0.34)
    cool = (t > 0.34) & (t <= 0.52)
    warm = (t > 0.52) & (t <= 0.72)
    hot = t > 0.72

    arid = m <= 0.24
    semi = (m > 0.24) & (m <= 0.46)
    sub = (m > 0.46) & (m <= 0.72)
    wet = m > 0.72

    def put(tb, mb, code):
        b[land & tb & mb] = code

    put(polar, arid, 13); put(polar, semi, 3); put(polar, sub, 3); put(polar, wet, 2)
    put(cold, arid, 13); put(cold, semi, 3); put(cold, sub, 4); put(cold, wet, 4)
    put(cool, arid, 13); put(cool, semi, 6); put(cool, sub, 5); put(cool, wet, 5)
    put(warm, arid, 8); put(warm, semi, 7); put(warm, sub, 6); put(warm, wet, 5)
    put(hot, arid, 8); put(hot, semi, 9); put(hot, sub, 9); put(hot, wet, 10)

    # Speckle removal belongs HERE, between the zonal matrix and the azonal
    # classes. Run it at the end instead and it eats wetlands and beaches, which
    # are legitimately one or two cells wide and are not noise.
    if majority:
        b = _majority(b, land)

    # ---- azonal classes: local water beats regional climate ---------------
    if accumulation is not None and slope is not None:
        flat = slope < np.quantile(slope[land], 0.25)
        big = accumulation > np.quantile(accumulation[land], wetland_q)
        marsh = land & flat & big & (m > 0.34)
        b[marsh] = np.where(t[marsh] > 0.34, 14, 16)

    coast_band = ndimage.binary_erosion(land, iterations=1) ^ land
    beachy = coast_band & land & (t > 0.30)
    if slope is not None:
        beachy &= slope < np.quantile(slope[land], 0.35)
    b[beachy] = 15

    # ---- cold overrides run last -----------------------------------------
    b[land & (t < 0.115)] = 12                     # snowcap, by temperature
    b[land & (t >= 0.115) & (t < 0.175) & (elev > sea_level + 0.16)] = 11

    return b


def _majority(b, land, size=3):
    out = b.copy()
    counts = {}
    for v in np.unique(b[land]):
        counts[v] = ndimage.uniform_filter((b == v).astype(np.float32), size=size,
                                           mode="nearest")
    keys = list(counts)
    stack = np.stack([counts[k] for k in keys], axis=0)
    win = np.array(keys, dtype=np.uint8)[np.argmax(stack, axis=0)]
    out[land] = win[land]
    return out


def shares(b, land, weights=None):
    w = np.ones_like(b, np.float32) if weights is None else weights
    lw = w * land
    return {BIOMES[int(k)][0]: float(((b == k) * lw).sum() / lw.sum())
            for k in np.unique(b[land])}


def colorize(b):
    return LUT[b] / 255.0
