"""
spherical.py — whole-planet generation.

A flat square is not a sphere. Two things break when you pretend otherwise:
the map does not wrap at the antimeridian, and every latitude-dependent
statistic over-weights the poles (Earth reads 0.332 land on an unweighted
equirectangular grid against a true 0.289).

This module fixes both by generating the field in 3D and sampling it on the
sphere, so longitude wrap is exact by construction rather than patched at the
seam, and by area-weighting everything that gets measured.

    world = generate_sphere(SphereParams(seed=7, nlat=512))
    img   = render_equirectangular(world)
    img   = render_globe(world, lon_0=0)

Known limits, stated rather than hidden: hydrology runs on the equirectangular
grid with longitude wrapped by padding, which is correct away from the poles and
degrades in the last few rows where cell width collapses. Polar drainage is not
trustworthy. For most purposes the poles are ice and nobody looks.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling modules, wherever installed
import worldforge_core as wf
import biomes as bm


@dataclass
class SphereParams:
    seed: int = 0
    nlat: int = 512                  # nlon is always 2 * nlat
    octaves: int = 7
    base_frequency: float = 2.4
    lacunarity: float = 2.0
    gain: float = 0.52
    warp_strength: float = 0.16
    land_fraction: float = 0.31
    plate_count: int = 20
    ridge_width: float = 0.11        # radians of arc
    tectonic_strength: float = 0.55
    erosion_passes: int = 2
    thermal_rate: float = 0.35
    incision_rate: float = 0.20
    lapse_rate: float = 0.80
    rain_shadow: float = 3.2
    moisture_recharge: float = 0.55
    river_threshold: float = 0.0016
    axial_tilt_deg: float = 23.0
    # Climate shaping. Neither draws from the RNG, so changing them does not
    # move the continents: the same seed gives the same coastline hotter, colder,
    # wetter or drier.
    temp_offset: float = 0.0        # -0.35 frozen .. +0.30 hothouse
    plate_warp: float = 0.0         # 0 = legacy straight seams; ~0.3-0.5 organic
    humidity: float = 1.0           # 0.35 arid .. 1.8 lush


# ---------------------------------------------------------------- geometry

def lonlat_grid(nlat):
    nlon = nlat * 2
    lat = np.linspace(90.0, -90.0, nlat)
    lon = np.linspace(-180.0, 180.0, nlon, endpoint=False)
    LON, LAT = np.meshgrid(lon, lat)
    return LAT, LON


def to_xyz(lat_deg, lon_deg):
    la, lo = np.deg2rad(lat_deg), np.deg2rad(lon_deg)
    cl = np.cos(la)
    return np.stack([cl * np.cos(lo), cl * np.sin(lo), np.sin(la)], axis=-1)


def area_weights(nlat):
    lat = np.linspace(90.0, -90.0, nlat)
    return np.cos(np.deg2rad(lat))[:, None]


def area_quantile(field, mask, q, nlat):
    """Quantile weighted by true cell area. Using an unweighted quantile on an
    equirectangular grid sets sea level by counting polar cells that represent
    almost no surface."""
    w = np.broadcast_to(area_weights(nlat), field.shape)[mask].ravel()
    v = field[mask].ravel()
    o = np.argsort(v)
    v, w = v[o], w[o]
    c = np.cumsum(w) / w.sum()
    return float(np.interp(q, c, v))


# ------------------------------------------------------------------- noise

def _lattice3(rng, n):
    return rng.random((n, n, n)).astype(np.float32)


def _sample3(lattice, xyz, freq):
    """Sample a periodic 3D lattice at unit-sphere coordinates. Because the
    lattice is indexed with wrap mode, the field is continuous across the
    antimeridian and over the poles with no seam to hide."""
    n = lattice.shape[0]
    p = (xyz * freq) % n
    coords = [p[..., 0], p[..., 1], p[..., 2]]
    return ndimage.map_coordinates(lattice, coords, order=1, mode="grid-wrap")


def fbm_sphere(xyz, rng, octaves=7, frequency=2.4, lacunarity=2.0, gain=0.52):
    total = np.zeros(xyz.shape[:-1], np.float32)
    amp, freq, norm = 1.0, float(frequency), 0.0
    for _ in range(octaves):
        # The lattice only has to cover the sphere without repeating: xyz spans
        # [-1,1], so n >= 2*freq suffices. Oversizing it is what makes 3D noise
        # blow up memory, since cost is n cubed.
        n = min(320, max(4, int(2 * freq) + 2))
        total += amp * _sample3(_lattice3(rng, n), xyz, freq)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def warp_sphere(xyz, rng, strength):
    """Domain warp in 3D. Displacing the sample point on the sphere keeps the
    warp continuous everywhere, which a 2D warp cannot do at the seam."""
    if strength <= 0:
        return xyz
    d = np.stack([fbm_sphere(xyz, rng, 4, 1.8) - 0.5 for _ in range(3)], axis=-1)
    out = xyz + d * strength * 2.0
    return out / (np.linalg.norm(out, axis=-1, keepdims=True) + 1e-9)


# --------------------------------------------------------------- tectonics

def plates_sphere(xyz, p, rng, xyz_warp=None):
    """Plates as points on the sphere. Nearest-neighbour in 3D means seams wrap
    correctly instead of terminating at a map edge."""
    v = rng.normal(size=(p.plate_count, 3))
    seeds = v / np.linalg.norm(v, axis=1, keepdims=True)
    drift = rng.normal(size=(p.plate_count, 3))
    drift -= (drift * seeds).sum(1, keepdims=True) * seeds      # tangential only
    drift /= np.linalg.norm(drift, axis=1, keepdims=True) + 1e-9
    bias = np.where(rng.random(p.plate_count) < 0.45, 0.22, -0.18).astype(np.float32)

    # Plate lookup through a warped domain bends seams off great-circle arcs.
    # Unwarped, sea level slices the bias step along Voronoi edges and every
    # continent gets ruler-straight coasts. Reuses the generator's warp field,
    # so it draws no RNG and plate_warp=0 reproduces legacy worlds exactly.
    q = xyz
    if xyz_warp is not None and p.plate_warp > 0:
        q = xyz + (p.plate_warp / max(p.warp_strength, 1e-6)) * (xyz_warp - xyz)
        q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    flat = q.reshape(-1, 3)
    dist, idx = cKDTree(seeds).query(flat, k=2)
    i0, i1 = idx[:, 0], idx[:, 1]

    # chord distance to the seam, converted to arc
    seam = np.arcsin(np.clip((dist[:, 1] - dist[:, 0]) / 4.0, -1, 1)) * 2.0
    prox = np.exp(-np.abs(seam) / p.ridge_width)

    axis = seeds[i1] - seeds[i0]
    axis /= np.linalg.norm(axis, axis=1, keepdims=True) + 1e-9
    conv = ((drift[i0] - drift[i1]) * axis).sum(1)

    shape = xyz.shape[:-1]
    uplift = (prox * conv * p.tectonic_strength).reshape(shape).astype(np.float32)
    uplift = ndimage.gaussian_filter(uplift, sigma=1.2, mode=("nearest", "wrap"))
    pbias = ndimage.gaussian_filter(bias[i0].reshape(shape).astype(np.float32),
                                    sigma=0.02 * shape[1], mode=("nearest", "wrap"))
    return uplift, pbias, i0.reshape(shape)


# --------------------------------------------------------------- hydrology

def _wrap_pad(a, pad):
    return np.concatenate([a[:, -pad:], a, a[:, :pad]], axis=1)


def hydrology_wrapped(elev, pad=64, jitter=3e-3, seed=0, weights=None):
    """Depression fill and flow accumulation with longitude wrapped by padding.

    The pad has to be wider than the longest flow path that crosses the seam,
    which in practice means wider than any single drainage basin. 64 cells is
    generous at these resolutions.

    `jitter` breaks ties on flat ground. Priority-flood fills a depression to a
    single level, and D8 routing across a perfectly level surface then runs in
    dead-straight lines to the pour point, so the map grows rivers with
    kilometre-long right angles. Noise sized against the terrain (3e-3 on a 0..1 field, the same magnitude the
    watershed fix needed) restores a natural channel; 3e-4 was far too small.
    Same failure and same fix as the watershed fragments in cartography.py.
    """
    rng = np.random.default_rng(seed)
    e = elev + rng.normal(0.0, jitter, elev.shape).astype(elev.dtype)
    padded = _wrap_pad(e, pad)
    filled = wf.fill_depressions(padded)
    wts = None if weights is None else _wrap_pad(weights, pad)
    acc, _ = wf.flow_accumulation(filled, wts)
    return filled[:, pad:-pad], acc[:, pad:-pad]


# ----------------------------------------------------------------- climate

def three_cell_moisture(elev_above, sea, p):
    """Advected moisture under three-cell circulation.

    Trade easterlies 0-30, westerlies 30-60, polar easterlies 60-90, each
    hemisphere. This is the difference between a climate map that reads as
    researched and one that turns every continental interior into desert: a
    single prevailing wind has no ITCZ to wet the equator and no reversal to
    wet a subcontinent.
    """
    nlat, nlon = elev_above.shape
    lat = np.linspace(90.0, -90.0, nlat)
    abs_lat = np.abs(lat)
    # True = wind blows toward +lon (westerly), False = toward -lon (easterly)
    westerly = (abs_lat >= 30.0) & (abs_lat < 60.0)

    rain = np.zeros_like(elev_above)
    for row in range(nlat):
        e = elev_above[row]
        s = sea[row]
        order = range(nlon) if westerly[row] else range(nlon - 1, -1, -1)
        order = list(order) * 2                      # two laps: wrap spin-up
        m = 0.6
        prev = None
        out = np.zeros(nlon, np.float32)
        # equatorial convergence band is wetter, poles are drier
        conv = 1.0 + 0.9 * np.exp(-(abs_lat[row] / 12.0) ** 2)
        for x in order:
            if s[x]:
                m = min(1.0, m + p.moisture_recharge)
            rise = 0.0 if prev is None else max(0.0, float(e[x]) - prev)
            drop = m * (1.0 - np.exp(-p.rain_shadow * rise)) + m * 0.02 * conv
            drop = min(drop, m)
            out[x] = drop
            m -= drop
            prev = float(e[x])
        rain[row] = out

    rain = ndimage.gaussian_filter(rain, sigma=1.5, mode=("nearest", "wrap"))
    ref = np.quantile(rain[~sea], 0.90) if (~sea).any() else rain.max()
    return np.clip(rain / (ref + 1e-9), 0, 1)


def temperature_sphere(elev_above, p):
    nlat, nlon = elev_above.shape
    lat = np.abs(np.linspace(90.0, -90.0, nlat)) / 90.0
    base = np.clip(1.0 - lat ** 1.25, 0, 1)[:, None] * np.ones((1, nlon), np.float32)
    return np.clip(base - p.lapse_rate * elev_above + p.temp_offset, 0, 1)


# -------------------------------------------------------------- generation

def generate_sphere(p: SphereParams):
    rng = np.random.default_rng(p.seed)
    LAT, LON = lonlat_grid(p.nlat)
    xyz = to_xyz(LAT, LON)

    base = fbm_sphere(xyz, rng, p.octaves, p.base_frequency, p.lacunarity, p.gain)
    xyzw = warp_sphere(xyz, rng, p.warp_strength)
    base = 0.5 * base + 0.5 * fbm_sphere(xyzw, rng, p.octaves, p.base_frequency,
                                         p.lacunarity, p.gain)

    uplift, pbias, plate = plates_sphere(xyz, p, rng, xyzw)
    elev = np.clip(0.68 * base + 0.32 * (0.5 + 2.2 * pbias + uplift), 0, 1)
    elev = wf.thermal_erosion(elev, p.thermal_rate)

    sea_level = area_quantile(elev, np.ones_like(elev, bool),
                              1.0 - p.land_fraction, p.nlat)
    for _ in range(p.erosion_passes):
        filled, acc = hydrology_wrapped(elev, seed=p.seed + 11)
        land = elev > sea_level
        elev = np.where(land, wf.stream_power_incision(elev, acc * land,
                                                       p.incision_rate), elev)
        elev = np.clip(elev, 0, 1)

    sea_level = area_quantile(elev, np.ones_like(elev, bool),
                              1.0 - p.land_fraction, p.nlat)
    surface = derive_surface(elev, p, sea_level)
    return dict(params=p, elevation=elev, uplift=uplift, plate=plate,
                lat=LAT, lon=LON, **surface)


def derive_surface(elev, p: SphereParams, sea_level):
    """Everything that follows from a finished elevation field on a planet:
    drainage, temperature, three-cell moisture, biomes and rain-weighted rivers.

    Split out of generate_sphere so that anything which edits terrain afterwards
    (coastal sculpting, the feature editor) recomputes the planet's climate with
    the planet's own physics, instead of flat-map winds that ignore the
    longitude wrap. Draws only from fixed per-seed RNGs (hydrology jitter and
    biome jitter), never from the generator's main stream, so calling it again
    on unchanged terrain reproduces generation bit for bit.

    `sea_level` is passed, not recomputed: after an edit the sea stays where it
    was. Re-deriving it from land_fraction would quietly undo the edit.
    """
    filled, acc = hydrology_wrapped(elev, seed=p.seed + 12)
    sea = elev <= sea_level
    above = np.clip(elev - sea_level, 0, None)

    temp = temperature_sphere(above, p)
    rain = three_cell_moisture(above, sea, p)
    # Raw advection output is not fit to classify on: it runs away arid because
    # nothing recycles water back into the interior. See biomes.refine_moisture.
    moisture = bm.refine_moisture(rain, sea, temp, above, wrap=True,
                                  coastal_gain=0.26 * p.humidity,
                                  recycling=0.28 * p.humidity)
    # refine_moisture normalises to its own land median, which erases any global
    # wetness change. Apply humidity as a level AFTER normalising, or "arid" is a
    # silent no-op. No-op at humidity=1.0, and draws no RNG.
    moisture = np.clip(moisture * p.humidity, 0, 1.4)
    gy, gx = np.gradient(elev)
    slope = np.hypot(gy, gx)
    biome = bm.classify(elev, sea_level, temp, moisture, acc, slope, seed=p.seed)
    # Rivers carry rain, not area. Same jitter seed as above, so routing is
    # identical; only the volume changes. Runoff is 1.0 at the median of a
    # humidity-1.0 world, so temperate worlds keep roughly their river count.
    runoff = np.clip(moisture / 0.5, 0.0, 2.5) * ~sea
    _, discharge = hydrology_wrapped(elev, seed=p.seed + 12, weights=runoff)
    rivers = (discharge > p.river_threshold * elev.size) & ~sea
    return dict(sea_level=sea_level, sea=sea, accumulation=acc, discharge=discharge,
                rivers=rivers, rainfall=rain, moisture=moisture, temperature=temp,
                biome=biome)


def is_planet(world):
    """True for worlds from generate_sphere (wrapping, lat/lon, 17 biome classes)."""
    return isinstance(world.get("params"), SphereParams)


def land_fraction_true(world):
    """Area-weighted, i.e. correct. Compare against the naive cell count to see
    how much the projection was lying."""
    land = ~world["sea"]
    w = np.broadcast_to(area_weights(world["params"].nlat), land.shape)
    return float((land * w).sum() / w.sum()), float(land.mean())


# ----------------------------------------------------------------- render

def shade_rgb(world, palette=None):
    biome, elev, sea = world["biome"], world["elevation"], world["sea"]
    rgb = bm.colorize(biome).copy()
    depth = np.clip((world["sea_level"] - elev) / (world["sea_level"] + 1e-9), 0, 1)
    rgb[sea] *= (1 - 0.55 * depth[sea])[:, None]
    shade = wf.hillshade(elev, z=10.0)[..., None]
    rgb = np.where(sea[..., None], rgb, rgb * (0.58 + 0.72 * shade))
    rgb[world["rivers"]] = np.array([0.28, 0.45, 0.62], np.float32)
    return np.clip(rgb, 0, 1)


def render_equirectangular(world, graticule=30):
    from PIL import Image
    rgb = shade_rgb(world).copy()
    nlat, nlon = world["elevation"].shape
    if graticule:
        for d in range(-90 + graticule, 90, graticule):
            r = int((90 - d) / 180 * (nlat - 1))
            rgb[r] = rgb[r] * 0.72 + 0.28
        for d in range(-180, 180, graticule):
            c = int((d + 180) / 360 * (nlon - 1))
            rgb[:, c] = rgb[:, c] * 0.72 + 0.28
    return Image.fromarray((rgb * 255).astype(np.uint8))


def render_globe(world, lon_0=0.0, lat_0=20.0, size=900, graticule=30):
    """Orthographic hemisphere. This is what people mean by a planet map."""
    from PIL import Image
    rgb = shade_rgb(world)
    nlat, nlon = world["elevation"].shape

    y, x = np.mgrid[0:size, 0:size]
    xx = (x - size / 2) / (size / 2 - 2)
    yy = (size / 2 - y) / (size / 2 - 2)
    rho = np.hypot(xx, yy)
    inside = rho <= 1.0
    c = np.arcsin(np.clip(rho, 0, 1))
    l0, p0 = np.deg2rad(lon_0), np.deg2rad(lat_0)

    with np.errstate(invalid="ignore", divide="ignore"):
        lat = np.arcsin(np.cos(c) * np.sin(p0) +
                        np.where(rho == 0, 0, yy * np.sin(c) * np.cos(p0) / np.maximum(rho, 1e-9)))
        lon = l0 + np.arctan2(xx * np.sin(c),
                              rho * np.cos(p0) * np.cos(c) - yy * np.sin(p0) * np.sin(c))

    row = np.clip(((np.pi / 2 - lat) / np.pi * (nlat - 1)), 0, nlat - 1)
    col = ((np.rad2deg(lon) + 180) % 360) / 360 * nlon

    out = np.zeros((size, size, 3), np.float32)
    for ch in range(3):
        out[..., ch] = ndimage.map_coordinates(rgb[..., ch], [row, col], order=1,
                                               mode="grid-wrap")
    if graticule:
        latd, lond = np.rad2deg(lat), np.rad2deg(lon)
        g = ((np.abs((latd + 90) % graticule - graticule / 2) < 0.35) |
             (np.abs((lond + 180) % graticule - graticule / 2) < 0.35))
        out[g & inside] = out[g & inside] * 0.7 + 0.3

    # limb shading and a clean edge
    out *= np.clip(1.15 - 0.45 * rho ** 3, 0, 1.15)[..., None]
    out[~inside] = 0.043
    ring = (rho > 0.985) & (rho <= 1.0)
    out[ring] = 0.85
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
