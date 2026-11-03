"""
worldforge_core.py: reference implementation of the Worldforge data pipeline.

This is the skeleton every Worldforge project starts from. It is deliberately
dependency-light (numpy + scipy + Pillow, no `noise` C extension) so it runs
anywhere, and deliberately explicit so each stage can be swapped out.

Pipeline stages (see references/geophysics.md for the physics behind each):

    seed -> plates -> base elevation -> erosion -> sea level
         -> depression fill -> flow accumulation (rivers)
         -> orographic rainfall -> temperature -> biomes -> render

Everything is a float32 array in [0,1] unless noted. Same seed + same params
== byte-identical output, which is the contract the rest of the engine relies on.

CLI:
    python worldforge_core.py --seed 42 --size 512 --out world
"""

from __future__ import annotations

import argparse
import heapq
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------


@dataclass
class WorldParams:
    seed: int = 0
    width: int = 512
    height: int = 512

    # continents
    octaves: int = 7
    base_frequency: float = 3.0
    lacunarity: float = 2.0
    gain: float = 0.5
    warp_strength: float = 0.10          # domain warp, kills the "grid" look
    land_fraction: float = 0.32          # target fraction of map above sea level

    # tectonics
    plate_count: int = 18
    ridge_width: float = 0.045           # as fraction of map width
    tectonic_strength: float = 0.55

    # erosion
    erosion_passes: int = 3
    thermal_rate: float = 0.35
    incision_rate: float = 0.22

    # climate
    wind_from_west: bool = True
    rain_shadow: float = 4.0             # how hard mountains wring out moisture
    moisture_recharge: float = 0.55      # per-cell recharge over water
    lapse_rate: float = 0.85             # temperature lost per unit elevation
    equator_row: float = 0.5             # 0..1, where the hot band sits

    # hydrology
    river_threshold: float = 0.0035      # fraction of total cells draining in

    labels: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Noise
# --------------------------------------------------------------------------


def _upsample(grid: np.ndarray, h: int, w: int, order: int = 3) -> np.ndarray:
    """Resample a coarse lattice to exactly (h, w). Exact shape, no off-by-one."""
    gh, gw = grid.shape
    ys = np.linspace(0, gh - 1, h)
    xs = np.linspace(0, gw - 1, w)
    coords = np.meshgrid(ys, xs, indexing="ij")
    return ndimage.map_coordinates(grid, coords, order=order, mode="reflect")


def fbm(h: int, w: int, rng: np.random.Generator, octaves: int = 6,
        frequency: float = 3.0, lacunarity: float = 2.0, gain: float = 0.5) -> np.ndarray:
    """Fractal Brownian motion built from bicubic-interpolated value noise.

    Cheaper than Perlin and visually equivalent once you stack 5+ octaves.
    Swap in `noise.snoise2` later if you need tileability or true gradient noise.
    """
    total = np.zeros((h, w), dtype=np.float32)
    amp, freq, norm = 1.0, float(frequency), 0.0
    aspect = w / h
    for _ in range(octaves):
        gh = max(2, int(round(freq)) + 1)
        gw = max(2, int(round(freq * aspect)) + 1)
        lattice = rng.random((gh, gw)).astype(np.float32)
        total += amp * _upsample(lattice, h, w)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def domain_warp(field_: np.ndarray, rng: np.random.Generator, strength: float) -> np.ndarray:
    """Push sample coordinates around with two low-frequency noise fields.

    This is the single highest-value-per-line trick in procedural terrain: it
    turns the soft blobs of raw fBm into coastlines with fjords and peninsulas.
    """
    if strength <= 0:
        return field_
    h, w = field_.shape
    dx = (fbm(h, w, rng, octaves=4, frequency=2.0) - 0.5) * 2.0
    dy = (fbm(h, w, rng, octaves=4, frequency=2.0) - 0.5) * 2.0
    ys, xs = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    coords = [ys + dy * strength * h, xs + dx * strength * w]
    return ndimage.map_coordinates(field_, coords, order=1, mode="reflect")


# --------------------------------------------------------------------------
# Tectonics
# --------------------------------------------------------------------------


def tectonic_field(p: WorldParams, rng: np.random.Generator):
    """Voronoi plates with drift vectors. Convergent boundaries uplift, divergent rift.

    Returns (uplift, plate_bias, plate_id). Uplift is signed: ridges positive,
    rifts negative. This is what stops mountain ranges from looking like noise
    blobs, because ranges become *linear* features along plate seams.
    """
    h, w = p.height, p.width
    pts = np.stack([rng.random(p.plate_count) * h, rng.random(p.plate_count) * w], axis=1)
    drift = rng.normal(size=(p.plate_count, 2))
    drift /= np.linalg.norm(drift, axis=1, keepdims=True) + 1e-9
    # continental vs oceanic plates
    bias = np.where(rng.random(p.plate_count) < 0.45, 0.22, -0.18).astype(np.float32)

    ys, xs = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    cells = np.stack([ys.ravel(), xs.ravel()], axis=1).astype(np.float32)
    dist, idx = cKDTree(pts).query(cells, k=2)

    i0, i1 = idx[:, 0], idx[:, 1]
    # distance to the seam between the two nearest plates
    seam = (dist[:, 1] - dist[:, 0]) / 2.0
    proximity = np.exp(-seam / (p.ridge_width * w))

    axis = pts[i1] - pts[i0]
    axis /= np.linalg.norm(axis, axis=1, keepdims=True) + 1e-9
    relative = drift[i0] - drift[i1]
    convergence = np.sum(relative * axis, axis=1)  # >0 closing, <0 opening

    uplift = (proximity * convergence * p.tectonic_strength).reshape(h, w).astype(np.float32)
    uplift = ndimage.gaussian_filter(uplift, sigma=max(1.0, 0.004 * w))

    # Blur the plate bias hard. Without this the Voronoi cells leak straight
    # polygon edges into the coastline and the map reads as computer-generated.
    plate_bias = ndimage.gaussian_filter(bias[i0].reshape(h, w).astype(np.float32),
                                         sigma=0.035 * w)
    return uplift, plate_bias, i0.reshape(h, w)


# --------------------------------------------------------------------------
# Erosion
# --------------------------------------------------------------------------


def thermal_erosion(elev: np.ndarray, rate: float, iterations: int = 12) -> np.ndarray:
    """Diffusive mass wasting. Rounds off peaks, builds talus at cliff bases."""
    out = elev.copy()
    for _ in range(iterations):
        smooth = ndimage.uniform_filter(out, size=3, mode="nearest")
        slope = np.abs(out - smooth)
        out += rate * (smooth - out) * (slope / (slope.max() + 1e-9))
    return out


def stream_power_incision(elev: np.ndarray, accum: np.ndarray, rate: float,
                          m: float = 0.5, n: float = 1.0) -> np.ndarray:
    """E = K * A^m * S^n. The reason real terrain has V-notched valleys.

    Applied as a single explicit step per pass; if you raise `rate` past ~0.4
    it goes unstable and punches holes. Lower rate, more passes.
    """
    gy, gx = np.gradient(elev)
    slope = np.sqrt(gy ** 2 + gx ** 2)
    a = accum / (accum.max() + 1e-9)
    incision = rate * (a ** m) * (slope ** n)
    return elev - incision


# --------------------------------------------------------------------------
# Hydrology
# --------------------------------------------------------------------------

_NEIGHBORS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def fill_depressions(elev: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
    """Priority-flood depression filling (Barnes et al. 2014), epsilon variant.

    Without this, D8 flow accumulation dead-ends in every pit the noise created
    and you get rivers that stop in the middle of a plain. The epsilon tilt
    guarantees every filled cell still has a downhill neighbour, so flats route.
    """
    h, w = elev.shape
    filled = np.full((h, w), np.inf, dtype=np.float64)
    closed = np.zeros((h, w), dtype=bool)
    pq: list[tuple[float, int, int]] = []

    for y in range(h):
        for x in (0, w - 1):
            heapq.heappush(pq, (float(elev[y, x]), y, x))
            closed[y, x] = True
            filled[y, x] = elev[y, x]
    for x in range(w):
        for y in (0, h - 1):
            if not closed[y, x]:
                heapq.heappush(pq, (float(elev[y, x]), y, x))
                closed[y, x] = True
                filled[y, x] = elev[y, x]

    while pq:
        val, y, x = heapq.heappop(pq)
        for dy, dx in _NEIGHBORS:
            ny, nx = y + dy, x + dx
            if ny < 0 or nx < 0 or ny >= h or nx >= w or closed[ny, nx]:
                continue
            nv = max(float(elev[ny, nx]), val + epsilon)
            filled[ny, nx] = nv
            closed[ny, nx] = True
            heapq.heappush(pq, (nv, ny, nx))
    return filled.astype(np.float32)


def flow_accumulation(filled: np.ndarray, weights=None) -> tuple[np.ndarray, np.ndarray]:
    """D8 steepest-descent routing. Returns (accumulation, receiver_index).

    Processing cells in descending elevation guarantees every donor is resolved
    before its receiver, so one linear pass is enough. O(n log n) from the sort.
    """
    h, w = filled.shape
    flat = filled.ravel()
    receiver = np.arange(h * w)
    best = np.zeros(h * w, dtype=np.float32)

    for dy, dx in _NEIGHBORS:
        shifted = np.roll(np.roll(filled, -dy, axis=0), -dx, axis=1)
        # cells rolled in from the far edge are invalid; mask them
        valid = np.ones((h, w), dtype=bool)
        if dy == 1:
            valid[-1, :] = False
        elif dy == -1:
            valid[0, :] = False
        if dx == 1:
            valid[:, -1] = False
        elif dx == -1:
            valid[:, 0] = False
        drop = (filled - shifted) / np.hypot(dy, dx)
        take = (drop > best.reshape(h, w)) & valid
        best = np.where(take, drop, best.reshape(h, w)).ravel()
        idx = (np.arange(h * w).reshape(h, w)
               + dy * w + dx)
        receiver = np.where(take.ravel(), idx.ravel(), receiver)

    # weights = per-cell runoff. None counts drainage AREA (right for erosion);
    # rainfall weights give DISCHARGE (right for rivers: a desert drains less).
    accum = (np.ones(h * w, dtype=np.float32) if weights is None
             else np.asarray(weights, np.float32).ravel().copy())
    order = np.argsort(flat)[::-1]
    for cell in order:
        r = receiver[cell]
        if r != cell:
            accum[r] += accum[cell]
    return accum.reshape(h, w), receiver.reshape(h, w)


# --------------------------------------------------------------------------
# Climate
# --------------------------------------------------------------------------


def orographic_moisture(elev: np.ndarray, sea: np.ndarray, p: WorldParams) -> np.ndarray:
    """Advect moisture across the map, dumping it on windward slopes.

    Sweeping column by column is the whole trick: it makes rain shadow an
    emergent property rather than a texture you paint on afterwards.
    """
    h, w = elev.shape
    cols = range(w) if p.wind_from_west else range(w - 1, -1, -1)

    moisture = np.zeros(h, dtype=np.float32)
    rain = np.zeros((h, w), dtype=np.float32)
    prev = None
    for x in cols:
        col_elev = elev[:, x]
        is_sea = sea[:, x]
        moisture = np.where(is_sea,
                            np.minimum(1.0, moisture + p.moisture_recharge),
                            moisture)
        if prev is not None:
            rise = np.maximum(0.0, col_elev - prev)
            drop = moisture * (1.0 - np.exp(-p.rain_shadow * rise))
        else:
            drop = moisture * 0.02
        drop += moisture * 0.030  # background convective rain
        drop = np.minimum(drop, moisture)
        rain[:, x] = drop
        moisture -= drop
        prev = col_elev
    rain = ndimage.gaussian_filter(rain, sigma=1.5)
    # Normalise against a high quantile, not the max. One freak windward peak
    # will otherwise scale the whole map down and turn every continent to desert.
    ref = np.quantile(rain[~sea], 0.90) if (~sea).any() else rain.max()
    return np.clip(rain / (ref + 1e-9), 0.0, 1.0)


def temperature_field(elev: np.ndarray, p: WorldParams) -> np.ndarray:
    h, w = elev.shape
    lat = np.abs(np.linspace(0, 1, h) - p.equator_row) * 2.0
    base = np.clip(1.0 - lat ** 1.25, 0.0, 1.0)[:, None] * np.ones((1, w), dtype=np.float32)
    return np.clip(base - p.lapse_rate * np.clip(elev, 0, None), 0.0, 1.0)


# --------------------------------------------------------------------------
# Biomes
# --------------------------------------------------------------------------

BIOMES = {
    0: ("ocean",            (26, 52, 92)),
    1: ("shallows",         (48, 92, 136)),
    2: ("ice",              (232, 238, 242)),
    3: ("tundra",           (142, 152, 138)),
    4: ("taiga",            (74, 104, 82)),
    5: ("temperate_forest", (72, 122, 68)),
    6: ("grassland",        (150, 166, 96)),
    7: ("shrubland",        (146, 140, 92)),
    8: ("desert",           (206, 184, 130)),
    9: ("savanna",          (176, 168, 92)),
    10: ("rainforest",      (44, 102, 56)),
    11: ("alpine",          (168, 164, 160)),
    12: ("snowcap",         (245, 245, 248)),
}


def classify_biomes(elev: np.ndarray, temp: np.ndarray, rain: np.ndarray,
                    sea_level: float) -> np.ndarray:
    """Whittaker-style classification on the (temperature, moisture) plane.

    Elevation overrides run last because a cold wet peak is snowcap regardless
    of what the moisture band says.
    """
    b = np.zeros(elev.shape, dtype=np.uint8)
    land = elev > sea_level
    b[~land] = np.where(elev[~land] > sea_level - 0.04, 1, 0)

    t, r = temp, rain
    hot = t > 0.66
    warm = (t > 0.42) & ~hot
    cool = (t > 0.20) & ~hot & ~warm
    cold = t <= 0.20

    wet = r > 0.55
    mid = (r > 0.28) & ~wet
    dry = r <= 0.28

    b[land & hot & wet] = 10
    b[land & hot & mid] = 9
    b[land & hot & dry] = 8
    b[land & warm & wet] = 5
    b[land & warm & mid] = 6
    b[land & warm & dry] = 7
    b[land & cool & wet] = 4
    b[land & cool & mid] = 4
    b[land & cool & dry] = 3
    b[land & cold] = 2

    rel = (elev - sea_level) / (1.0 - sea_level + 1e-9)
    b[land & (rel > 0.62)] = 11
    b[land & (rel > 0.80)] = 12
    return b


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def generate(p: WorldParams) -> dict:
    rng = np.random.default_rng(p.seed)
    h, w = p.height, p.width

    base = fbm(h, w, rng, p.octaves, p.base_frequency, p.lacunarity, p.gain)
    base = domain_warp(base, rng, p.warp_strength)
    uplift, plate_bias, plate_id = tectonic_field(p, rng)

    elev = 0.68 * base + 0.32 * (0.5 + 2.2 * plate_bias + uplift)
    elev = np.clip(elev, 0, 1)
    elev = thermal_erosion(elev, p.thermal_rate)

    sea_level = float(np.quantile(elev, 1.0 - p.land_fraction))

    for _ in range(p.erosion_passes):
        filled = fill_depressions(elev)
        accum, receiver = flow_accumulation(filled)
        land_mask = elev > sea_level
        eroded = stream_power_incision(elev, accum * land_mask, p.incision_rate)
        elev = np.where(land_mask, eroded, elev)
        elev = np.clip(elev, 0, 1)

    filled = fill_depressions(elev)
    accum, receiver = flow_accumulation(filled)

    sea_level = float(np.quantile(elev, 1.0 - p.land_fraction))
    sea = elev <= sea_level

    rain = orographic_moisture(np.clip(elev - sea_level, 0, None), sea, p)
    temp = temperature_field(np.clip(elev - sea_level, 0, None), p)
    biome = classify_biomes(elev, temp, rain, sea_level)

    rivers = (accum > p.river_threshold * h * w) & (~sea)

    return dict(params=p, elevation=elev, sea_level=sea_level, sea=sea,
                accumulation=accum, receiver=receiver, rivers=rivers,
                rainfall=rain, temperature=temp, biome=biome,
                plate_id=plate_id, uplift=uplift)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def hillshade(elev: np.ndarray, azimuth: float = 315.0, altitude: float = 45.0,
              z: float = 12.0) -> np.ndarray:
    gy, gx = np.gradient(elev * z)
    slope = np.pi / 2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az = np.deg2rad(360.0 - azimuth + 90.0)
    alt = np.deg2rad(altitude)
    shade = (np.sin(alt) * np.sin(slope) +
             np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip((shade + 1) / 2, 0, 1)


def render_realistic(world: dict):
    """Hypsometric biome tint x relief shading. The 'satellite' look."""
    from PIL import Image
    biome, elev, sea = world["biome"], world["elevation"], world["sea"]
    lut = np.zeros((len(BIOMES), 3), dtype=np.float32)
    for k, (_, rgb) in BIOMES.items():
        lut[k] = rgb
    rgb = lut[biome] / 255.0

    depth = np.clip((world["sea_level"] - elev) / (world["sea_level"] + 1e-9), 0, 1)
    rgb[sea] *= (1.0 - 0.55 * depth[sea])[:, None]

    shade = hillshade(elev)[..., None]
    rgb = np.where(sea[..., None], rgb, rgb * (0.55 + 0.75 * shade))

    rv = world["rivers"]
    rgb[rv] = np.array([0.28, 0.45, 0.62], dtype=np.float32)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def render_parchment(world: dict, rng: np.random.Generator | None = None):
    """Same arrays, antique skin. Proof that style is a shader, not a rerun."""
    from PIL import Image, ImageDraw, ImageFilter
    rng = rng or np.random.default_rng(world["params"].seed + 991)
    elev, sea = world["elevation"], world["sea"]
    h, w = elev.shape

    grain = fbm(h, w, rng, octaves=6, frequency=8.0)
    paper = np.stack([
        0.90 - 0.10 * grain, 0.83 - 0.12 * grain, 0.68 - 0.14 * grain
    ], axis=-1)
    ink = np.array([0.22, 0.16, 0.11], dtype=np.float32)

    # sea hatching: horizontal ruled lines that fade offshore
    dist = ndimage.distance_transform_edt(sea).astype(np.float32)
    rule = (np.arange(h)[:, None] % 6 == 0) & sea & (dist < 34)
    paper[rule] = paper[rule] * 0.72 + ink * 0.28

    coast = ndimage.binary_dilation(~sea, iterations=1) & sea
    paper[coast] = ink

    img = Image.fromarray((np.clip(paper, 0, 1) * 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # rivers as tapering ink
    rv = np.argwhere(world["rivers"])
    for y, x in rv:
        draw.point((int(x), int(y)), fill=(60, 72, 96))

    # hand-drawn mountain glyphs on local elevation maxima
    peaks = (elev == ndimage.maximum_filter(elev, size=11)) & (~sea)
    rel = (elev - world["sea_level"]) / (1 - world["sea_level"] + 1e-9)
    peaks &= rel > 0.55
    for y, x in np.argwhere(peaks):
        s = 4 + int(6 * float(rel[y, x]))
        draw.line([(x - s, y + s), (x, y - s), (x + s, y + s)], fill=(70, 55, 40), width=1)
        draw.line([(x - s * 0.4, y + s * 0.2), (x, y - s)], fill=(70, 55, 40), width=1)

    return img.filter(ImageFilter.SMOOTH)


# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Worldforge reference generator")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--land", type=float, default=0.32)
    ap.add_argument("--out", default="world")
    ap.add_argument("--style", default="both", choices=["realistic", "parchment", "both"])
    args = ap.parse_args()

    p = WorldParams(seed=args.seed, width=args.size, height=args.size,
                    land_fraction=args.land)
    world = generate(p)

    if args.style in ("realistic", "both"):
        render_realistic(world).save(f"{args.out}_realistic.png")
    if args.style in ("parchment", "both"):
        render_parchment(world).save(f"{args.out}_parchment.png")

    land = float((~world["sea"]).mean())
    print(f"seed={p.seed} size={p.width}x{p.height} land={land:.1%} "
          f"sea_level={world['sea_level']:.3f} "
          f"river_cells={int(world['rivers'].sum())}")


if __name__ == "__main__":
    main()
