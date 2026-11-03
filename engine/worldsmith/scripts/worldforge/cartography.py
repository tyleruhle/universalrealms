"""
cartography.py — the detail stack that turns a data layer into a readable map.

Every function here consumes finished arrays and returns pixels or draws onto an
image. None of them generate terrain. Import alongside worldforge_core:

    import worldforge_core as wf
    import cartography as ct

    world = wf.generate(params)
    rgb   = ct.base_surface(world, palette=ct.PARCHMENT)
    rgb   = ct.contours(rgb, world, bands=14)
    rgb   = ct.region_lines(rgb, provinces, weight=0.34)
    rgb   = ct.region_lines(rgb, owner, weight=0.78, dilate=2)
    rgb   = ct.graded_rivers(rgb, world)
    rgb   = ct.lakes(rgb, world)
    img   = ct.upscale(rgb, 2)
    ct.relief_glyphs(img, world, scale=2)
    ct.frame(img); ct.legend(img, rows); ct.scale_bar(img, km_per_px, 2)

Layer budget (learned by getting it wrong): each overlay must leave the relief
underneath it readable. Grid or hatch under ~35% ink at the lightest useful
weight, glow or emphasis from a mask never the whole composite, one accent hue
carrying meaning, and any symbol layer covering under ~5% of frame. If you
cannot see the hillshade through the stack, the stack is too heavy.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

try:
    from skimage import segmentation
except ImportError:  # boundaries fall back to a dilation difference
    segmentation = None

# ------------------------------------------------------------------ palettes

PARCHMENT = {
    "land_hi": (0xEE, 0xE2, 0xC8), "land_lo": (0xC0, 0xA9, 0x7F),
    "sea_hi": (0x86, 0x9B, 0xAD), "sea_lo": (0x3D, 0x53, 0x6B),
    "ink": (0x2A, 0x22, 0x1B), "river": (0x3A, 0x5F, 0x84),
    "accent": (0x8C, 0x3A, 0x2E), "cool": (0x63, 0x7C, 0x96),
}
ATLAS = {
    "land_hi": (0xF2, 0xF0, 0xE8), "land_lo": (0x9E, 0xA8, 0x8C),
    "sea_hi": (0xA8, 0xC0, 0xD4), "sea_lo": (0x35, 0x5A, 0x80),
    "ink": (0x1E, 0x1E, 0x22), "river": (0x2E, 0x6E, 0xA8),
    "accent": (0xB4, 0x4A, 0x2E), "cool": (0x7A, 0x92, 0xA8),
}


def _c(pal, k):
    return np.array(pal[k], dtype=np.float32)


def _boundaries(labels):
    if segmentation is not None:
        return segmentation.find_boundaries(labels, mode="outer")
    grown = ndimage.grey_dilation(labels, size=3)
    return grown != labels


def hillshade(elev, **kw):
    from worldforge_core import hillshade as _h
    return _h(elev, **kw)


# --------------------------------------------------------------- base layers

def base_surface(world, palette=PARCHMENT, z=13.0):
    """Hypsometric land, depth-ramped sea, relief shading. The floor everything
    else sits on. If a later layer hides this, that layer is too strong."""
    elev, sea = world["elevation"], world["sea"]
    land = ~sea
    h, w = elev.shape
    sl = float(world.get("sea_level", np.quantile(elev, 1 - land.mean())))
    rel = np.clip((elev - sl) / (1 - sl + 1e-9), 0, 1)

    rgb = np.zeros((h, w, 3), np.float32)
    lo, hi = _c(palette, "land_lo"), _c(palette, "land_hi")
    rgb[land] = lo + (hi - lo) * (1 - rel[land])[:, None]

    if sea.any():
        dep = np.clip((elev[sea].max() - elev[sea]) / (np.ptp(elev[sea]) + 1e-9), 0, 1)
        shi, slo = _c(palette, "sea_hi"), _c(palette, "sea_lo")
        rgb[sea] = shi + (slo - shi) * dep[:, None]

    shade = hillshade(elev, z=z)[..., None]
    return np.where(land[..., None], rgb * (0.76 + 0.38 * shade), rgb)


def contours(rgb, world, bands=14, smooth=1.4, weight=0.20, palette=PARCHMENT):
    """Elevation isolines. The cheapest large gain in perceived detail, and the
    thing that makes a map read as surveyed rather than painted."""
    elev, land = world["elevation"], ~world["sea"]
    sl = float(world.get("sea_level", np.quantile(elev, 1 - land.mean())))
    rel = np.clip((elev - sl) / (1 - sl + 1e-9), 0, 1)
    b = np.floor(ndimage.gaussian_filter(rel, smooth) * bands).astype(np.int32)
    line = _boundaries(b) & land
    out = rgb.copy()
    out[line] = out[line] * (1 - weight) + _c(palette, "ink") * weight
    return out


def bathymetric_contours(rgb, world, bands=7, smooth=5.0, weight=0.12,
                         palette=PARCHMENT):
    """Depth isolines. Smooth BEFORE banding: banding a noisy field frays the
    lines into something that reads as an artifact."""
    elev, sea = world["elevation"], world["sea"]
    depth = np.where(sea, 1.0 - elev, 0.0)
    b = np.floor(ndimage.gaussian_filter(depth, smooth) * bands).astype(np.int32)
    line = _boundaries(b) & sea
    out = rgb.copy()
    out[line] = out[line] * (1 - weight) + _c(palette, "ink") * weight
    return out


def hatch(rgb, mask, period=9, width=2, weight=0.34, palette=PARCHMENT,
          key="cool"):
    """Diagonal hatch for a categorical overlay (seasonal ground, disputed
    territory, unexplored). Keep it under the layer budget or it eats relief."""
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx + yy) % period < width) & mask
    out = rgb.copy()
    out[m] = out[m] * (1 - weight) + _c(palette, key) * weight
    return out


def tint(rgb, mask, color, weight=0.22):
    """Give a category its own surface tone. Use for the ONE distinction the map
    exists to communicate; more than one competing tint and both stop reading."""
    out = rgb.copy()
    c = np.array(color, dtype=np.float32)
    out[mask] = out[mask] * (1 - weight) + c * weight
    return out


def region_lines(rgb, labels, mask=None, weight=0.34, dilate=0, palette=PARCHMENT):
    """Draw boundaries of a label field: provinces, territories, zones.

    Call twice with different weights to get a hierarchy. Provinces light,
    national borders heavy. If they render at the same weight the map has no
    hierarchy and the reader cannot tell what is important.
    """
    line = _boundaries(labels)
    if mask is not None:
        line &= mask
    if dilate:
        line = ndimage.binary_dilation(line, iterations=dilate)
    out = rgb.copy()
    out[line] = out[line] * (1 - weight) + _c(palette, "ink") * weight
    return out


def watershed_regions(world, spacing=48, seed=0, jitter=0.42, tie_break=3e-3,
                      min_px=0):
    """Drainage-basin regions: provinces, precincts, natural districts.

    Two corrections over a naive watershed call, both learned from artifacts:

    `tie_break` adds imperceptible noise to the elevation before segmenting.
    Where terrain is locally flat, ties are otherwise broken by array scan order
    and the result is floating vertical and horizontal line fragments in the
    middle of plains, which read as a rendering bug because they are one.

    Size the tie_break against the terrain, not against float precision. It has
    to exceed the actual elevation difference between neighbouring cells on the
    flattest inhabited ground, which after erosion is far larger than epsilon.
    Measured on a 0..1 field: 1e-4 changed nothing and the straight fragments
    survived; 3e-3 cleared them. Too large makes boundaries visibly jagged, so
    raise it until the fragments go and stop.

    `min_px` optionally drops specks, but leaving it at 0 is usually right:
    deleting regions punches unowned holes in the map and leaves loose boundary
    ends where they were.
    """
    elev, land = world["elevation"], ~world["sea"]
    h, w = elev.shape
    rng = np.random.default_rng(seed)

    ys = np.arange(spacing // 2, h, spacing)
    xs = np.arange(spacing // 2, w, spacing)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")
    j = spacing * jitter
    py = np.clip(gy + rng.uniform(-j, j, gy.shape), 0, h - 1).astype(int)
    px = np.clip(gx + rng.uniform(-j, j, gx.shape), 0, w - 1).astype(int)
    keep = land[py, px]

    markers = np.zeros(elev.shape, dtype=np.int32)
    markers[py[keep], px[keep]] = np.arange(1, int(keep.sum()) + 1)

    field = elev + rng.normal(0.0, tie_break, elev.shape).astype(elev.dtype)
    if segmentation is None:
        raise RuntimeError("watershed_regions needs scikit-image")
    lab = segmentation.watershed(field, markers, mask=land)

    if min_px:
        ids, counts = np.unique(lab[lab > 0], return_counts=True)
        for i in ids[counts < min_px]:
            lab[lab == i] = 0
    return lab


def clip_labels(inner, outer, background=0):
    """Combine two label fields so no inner region straddles an outer boundary.
    Provinces that cross a national border look like a bug to every reader."""
    combined = inner.astype(np.int64) * 100 + (outer.astype(np.int64) + 1)
    combined[inner == background] = 0
    return combined


def graded_rivers(rgb, world, threshold=None, steps=((1, 0), (5, 1), (18, 2)),
                  palette=PARCHMENT):
    """Rivers widened by discharge. Width should scale with the cube root of
    accumulation, never linearly, or trunk rivers render as highways.

    A single-width river layer is the most common reason a detailed map still
    looks flat: real drainage is a hierarchy and drawing it uniformly hides it.
    """
    acc, land = world.get("discharge", world["accumulation"]), ~world["sea"]
    h, w = acc.shape
    thr = threshold if threshold is not None else 0.0022 * h * w
    out = rgb.copy()
    col = _c(palette, "river")
    for mult, grow in steps:
        m = (acc > thr * mult) & land
        if grow:
            m = ndimage.binary_dilation(m, iterations=grow)
        out[m] = col
    return out


def lakes(rgb, world, min_depth=0.004, palette=PARCHMENT):
    """Lakes from the depression-fill delta, flat shaded with an ink shore.

    Flat shading is not a style choice. A lake surface is level by definition,
    so a hillshaded lake is an instant tell that the water was painted on.
    """
    elev, land = world["elevation"], ~world["sea"]
    from worldforge_core import fill_depressions
    lake = ((fill_depressions(elev) - elev) > min_depth) & land
    lake = ndimage.binary_opening(lake, np.ones((3, 3), bool))
    out = rgb.copy()
    water = _c(palette, "sea_hi") * 0.85
    out[lake] = water
    shore = ndimage.binary_dilation(lake) & ~lake & land
    out[shore] = _c(palette, "ink")
    return out, lake


def coastline(rgb, world, palette=PARCHMENT):
    land = ~world["sea"]
    line = ndimage.binary_dilation(land, iterations=1) & world["sea"]
    out = rgb.copy()
    out[line] = _c(palette, "ink")
    return out


# ------------------------------------------------------------ vector overlays

def upscale(rgb, scale=2):
    from PIL import Image
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    return img


def relief_glyphs(img, world, scale=2, rel_min=0.45, prominence_q=0.965,
                  size=17, min_sep=14, color=(0x3A, 0x2E, 0x24)):
    """Hand-drawn range glyphs at prominent peaks.

    Two filters, both required, for two different failure modes.

    The prominence test kills flat-plateau false maxima: many adjacent cells
    share a value, every one registers as a peak, and the glyphs smear.

    The min_sep thinning kills ridge-crest clustering, which survives the
    prominence test because the crest genuinely IS prominent along its whole
    length. Without it a range renders as one long horizontal bar instead of a
    row of peaks. Greedy: take the highest, suppress its neighbourhood, repeat.
    """
    from PIL import ImageDraw
    elev, land = world["elevation"], ~world["sea"]
    sl = float(world.get("sea_level", np.quantile(elev, 1 - land.mean())))
    rel = np.clip((elev - sl) / (1 - sl + 1e-9), 0, 1)

    prom = elev - ndimage.minimum_filter(elev, size=size)
    peaks = ((elev == ndimage.maximum_filter(elev, size=size)) & land
             & (rel > rel_min) & (prom > np.quantile(prom[land], prominence_q)))

    ys, xs = np.nonzero(peaks)
    order = np.argsort(rel[ys, xs])[::-1]
    taken_y, taken_x, sep2 = [], [], min_sep * min_sep
    for i in order:
        y, x = int(ys[i]), int(xs[i])
        if taken_y:
            dy = np.asarray(taken_y) - y
            dx = np.asarray(taken_x) - x
            if (dy * dy + dx * dx).min() < sep2:
                continue
        taken_y.append(y)
        taken_x.append(x)

    dr = ImageDraw.Draw(img, "RGBA")
    for y, x in zip(taken_y, taken_x):
        r = float(rel[y, x])
        s = (3.2 + 6.5 * r) * scale
        px, py = x * scale, y * scale
        dr.line([(px - s, py + s * 0.8), (px, py - s), (px + s, py + s * 0.8)],
                fill=color + (235,), width=max(1, scale))
        dr.line([(px - s * 0.35, py + s * 0.12), (px, py - s)],
                fill=color + (150,), width=max(1, scale))
    return img


def dashed(img, path, scale=2, color=(0x8C, 0x3A, 0x2E), width=3, step=4, on=2):
    """Draw a route as a dashed polyline. `path` is [(y, x), ...] in data
    coordinates, e.g. the output of a least-cost path search."""
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img, "RGBA")
    pts = [(int(x) * scale, int(y) * scale) for y, x in path[::step]]
    for i in range(0, len(pts) - 1, on):
        dr.line([pts[i], pts[i + 1]], fill=color + (240,), width=width)
    return img


def halo_text(dr, x, y, text, font, fill=(0x2A, 0x22, 0x1B),
              halo=(0xF4, 0xEA, 0xD4), spread=2):
    """Labels need a halo or they vanish over hatch and contours. Cheap version:
    draw the string offset in six directions in the paper colour, then on top."""
    for ox, oy in ((-spread, 0), (spread, 0), (0, -spread), (0, spread),
                   (-spread, -spread), (spread, spread)):
        dr.text((x + ox, y + oy), text, font=font, fill=halo + (225,))
    dr.text((x, y), text, font=font, fill=fill)


def seat_marker(dr, x, y, kind="permanent", r=9,
                ink=(0x2A, 0x22, 0x1B), paper=(0xF4, 0xEA, 0xD4)):
    """Filled square for one class of settlement, open circle for the other.
    Two shapes beats two colours: it survives greyscale and colour blindness."""
    if kind == "permanent":
        dr.rectangle([x - r, y - r, x + r, y + r], fill=ink, outline=paper, width=3)
    else:
        dr.ellipse([x - r, y - r, x + r, y + r], fill=paper, outline=ink, width=4)


def frame(img, ink=(0x2A, 0x22, 0x1B), outer=14, inner=30):
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img)
    W, H = img.size
    dr.rectangle([outer, outer, W - outer - 1, H - outer - 1], outline=ink, width=4)
    dr.rectangle([inner, inner, W - inner - 1, H - inner - 1], outline=ink, width=2)
    return img


def scale_bar(img, km_per_px, scale=2, bar_km=500, font=None,
              ink=(0x2A, 0x22, 0x1B), margin=70):
    """A scale bar is the one element a reader can check by eye. If it is wrong,
    every other claim to accuracy on the map is dead."""
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img)
    W, H = img.size
    bar_px = int(bar_km / km_per_px * scale)
    x0, y0 = W - margin - bar_px, H - margin - 14
    dr.line([(x0, y0), (x0 + bar_px, y0)], fill=ink, width=5)
    for t in range(3):
        xt = x0 + int(bar_px * t / 2)
        dr.line([(xt, y0 - 12), (xt, y0 + 12)], fill=ink, width=5)
    if font is not None:
        label = f"{bar_km} kilometres"
        tw = dr.textlength(label, font=font)          # centre by real width, not a guess
        tx = min(x0 + bar_px / 2 - tw / 2, W - margin - tw)
        halo_text(dr, int(tx), y0 + 16, label, font)
    return img


def compass(img, x, y, r=52, font=None, ink=(0x2A, 0x22, 0x1B)):
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img)
    dr.ellipse([x - r, y - r, x + r, y + r], outline=ink, width=3)
    dr.polygon([(x, y - r + 8), (x - 13, y + 10), (x + 13, y + 10)], fill=ink)
    if font is not None:
        halo_text(dr, x - 10, y + r + 4, "N", font)
    return img


def legend(img, box, title, rows, title_font, row_font,
           paper=(0xF4, 0xEA, 0xD4), ink=(0x2A, 0x22, 0x1B)):
    """rows is [(draw_swatch_callable, text), ...]. Draw real swatches: most
    display fonts have no geometric glyphs and unicode squares render as tofu."""
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img, "RGBA")
    dr.rectangle(box, fill=paper + (235,), outline=ink, width=3)
    x, y = box[0] + 26, box[1] + 20
    dr.text((x, y), title, font=title_font, fill=ink)
    y += title_font.size + 14
    for swatch, text in rows:
        swatch(dr, x + 14, y + 11)
        dr.text((x + 62, y), text, font=row_font, fill=ink)
        y += row_font.size + 12
    return img
