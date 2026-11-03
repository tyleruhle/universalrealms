"""
vector.py — turn raster layers into attributed vector geometry.

This is the prerequisite for three separate capabilities that all look like
different features: SVG export, clickable regions, and smooth zoom. All three
need the same thing, which is polygons with identity and attributes rather than
a grid of coloured cells. Build it once.

    feats = vector.extract(world, layers)
    svg   = vector.to_svg(feats, width=2000)
    open("map.svg", "w").write(svg)

Design rules that matter:

**Simplify, do not decimate.** Douglas-Peucker keeps the points that carry the
shape and drops the ones that do not, so a coastline stays recognisable at a
tenth the vertex count. Dropping every Nth point instead destroys exactly the
headlands and inlets that make a coast look real.

**Carry attributes on the geometry.** A province polygon that does not know its
own area, elevation and population is a drawing. One that does is data, and the
viewer, the exporter and the label placer all read the same fields.

**One tolerance per feature class.** Coastlines need detail, province borders do
not, and rivers need their own treatment entirely because they are lines rather
than rings.
"""

from __future__ import annotations

import json

from html import escape as xml_escape
from pathlib import Path
import sys

import numpy as np
from scipy import ndimage
from skimage import measure

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worldforge_core as wf


def _rings(mask, tolerance):
    """Marching squares, then Douglas-Peucker. Returns list of (N,2) arrays in
    (row, col) order. Holes come back as separate rings with reversed winding,
    which SVG handles correctly under fill-rule evenodd."""
    padded = np.pad(mask.astype(np.float32), 1)
    out = []
    for c in measure.find_contours(padded, 0.5):
        c = c - 1.0
        if len(c) < 4:
            continue
        s = measure.approximate_polygon(c, tolerance=tolerance)
        if len(s) >= 4:
            out.append(s)
    return out


def river_polylines(world, river_min=None, simplify=0.8):
    """Trace rivers along the flow graph, not with marching squares.

    Contouring a river mask returns the OUTLINE of the channel, so a river comes
    back as a closed loop around a one-pixel line and the network shatters into
    fragments. Rivers are directed polylines and the flow receiver already
    encodes the topology: walk each headwater downstream until it meets a
    channel already traced, and the whole network falls out as a tree drawn
    exactly once.
    """
    elev, land = world["elevation"], ~world["sea"]
    acc = world["accumulation"]
    h, w = elev.shape
    thr = river_min if river_min is not None else 0.0022 * acc.size

    recv = world.get("receiver")
    if recv is None:
        filled = wf.fill_depressions(elev)
        acc2, recv = wf.flow_accumulation(filled)
        acc = acc if acc is not None else acc2
    recv = recv.reshape(h, w)

    is_river = (acc > thr) & land
    idx = np.arange(h * w).reshape(h, w)

    # a headwater is a river cell with no river cell draining into it
    donors = np.zeros((h, w), np.int32)
    rflat = recv.ravel()
    riv_flat = is_river.ravel()
    src = idx.ravel()[riv_flat]
    np.add.at(donors.ravel(), rflat[riv_flat], 1)
    heads = is_river & (donors == 0)

    visited = np.zeros((h, w), bool)
    out = []
    for y, x in zip(*np.nonzero(heads)):
        pts, a_start = [], float(acc[y, x])
        cy, cx = int(y), int(x)
        guard = 0
        while guard < 100000:
            pts.append((cy, cx))
            if visited[cy, cx] and len(pts) > 1:
                break
            visited[cy, cx] = True
            nxt = int(recv[cy, cx])
            ny, nx = divmod(nxt, w)
            if (ny, nx) == (cy, cx) or not is_river[ny, nx]:
                if not land[ny, nx]:
                    pts.append((ny, nx))          # run the mouth into the sea
                break
            cy, cx = ny, nx
            guard += 1
        if len(pts) < 3:
            continue
        arr = np.array(pts, float)
        if simplify:
            arr = measure.approximate_polygon(arr, tolerance=simplify)
        a_end = float(acc[pts[-1][0], pts[-1][1]])
        cls = "major" if a_end > thr * 18 else ("trunk" if a_end > thr * 5 else "minor")
        out.append({"class": cls, "points": arr.tolist(),
                    "discharge_start": round(a_start, 1),
                    "discharge_end": round(a_end, 1)})
    return out


def _stats(world, layers, mask):
    """Attributes every consumer of this geometry will want."""
    elev = world["elevation"]
    a = {}
    n = int(mask.sum())
    a["cells"] = n
    if n:
        a["mean_elevation"] = round(float(elev[mask].mean()), 4)
        a["max_elevation"] = round(float(elev[mask].max()), 4)
        if "biome" in world:
            vals, counts = np.unique(world["biome"][mask], return_counts=True)
            a["dominant_biome"] = int(vals[np.argmax(counts)])
        for key, name in (("density", "population_index"),
                          ("development", "development_index"),
                          ("garrison", "garrison_index")):
            if layers and key in layers:
                a[name] = round(float(layers[key][mask].mean()), 3)
        for key, name in (("culture", "culture"), ("religion", "religion"),
                          ("polity", "polity")):
            if layers and key in layers:
                v = layers[key][mask]
                v = v[v >= 0]
                if v.size:
                    vals, counts = np.unique(v, return_counts=True)
                    a[name] = int(vals[np.argmax(counts)])
    return a


ATTR_META = {
    "cells": ("cells", "continuous", None),
    "mean_elevation": ("mean elevation", "continuous", "normalised 0-1"),
    "max_elevation": ("peak elevation", "continuous", "normalised 0-1"),
    "dominant_biome": ("dominant biome", "categorical", None),
    "population_index": ("population", "continuous", "index 0-1"),
    "development_index": ("development", "continuous", "index 0-1"),
    "garrison_index": ("garrison", "continuous", "index 0-1"),
    "culture": ("culture", "categorical", None),
    "religion": ("religion", "categorical", None),
    "polity": ("polity", "categorical", None),
}


def build_manifest(feats, km_per_px=None, categories=None, title=None,
                   seed=None, extra=None):
    """Describe the file to whatever reads it, so the viewer stays world-agnostic.

    A viewer that hardcodes biome names, attribute lists, scale, or region counts
    is a viewer for exactly one world. Everything world-specific belongs in this
    manifest and everything generic belongs in the reader: it discovers which
    attributes exist, whether each is continuous or categorical, what the real
    ranges are, and what the category ids mean. An unknown attribute renders
    generically rather than breaking or being dropped.
    """
    h, w = feats["meta"]["grid"]
    attrs = {}
    for rg in feats["regions"]:
        for k, v in rg["attributes"].items():
            label, kind, unit = ATTR_META.get(k, (k.replace("_", " "), None, None))
            if kind is None:
                kind = "categorical" if isinstance(v, int) and not isinstance(v, bool) \
                       and k.endswith(("_id", "id")) else "continuous"
            a = attrs.setdefault(k, {"label": label, "type": kind, "unit": unit,
                                     "min": v, "max": v, "values": set()})
            a["min"] = min(a["min"], v)
            a["max"] = max(a["max"], v)
            if a["type"] == "categorical":
                a["values"].add(v)
    for k, a in attrs.items():
        vals = sorted(a.pop("values"))
        if a["type"] == "categorical":
            a["categories"] = {str(v): (categories or {}).get(k, {}).get(v, f"{a['label']} {v}")
                               for v in vals}

    return {
        "schema_version": 1,
        "generator": "worldforge",
        "title": title,
        "seed": seed,
        "grid": [int(h), int(w)],
        "km_per_px": km_per_px,
        # Projection is not cosmetic. On an equirectangular whole-planet map,
        # east-west scale shrinks by cos(latitude), so a single linear scale bar
        # is only true at the equator and a viewer must say so.
        "projection": feats["meta"].get("projection", "flat"),
        "scale_note": ("km_per_px is exact at the equator; east-west distance "
                       "scales by cos(latitude)")
        if feats["meta"].get("projection") == "equirectangular" else
        "km_per_px is uniform across the map",
        "region_field": feats["meta"].get("region_field"),
        "counts": feats["meta"].get("counts", {}),
        "river_classes": sorted({r["class"] for r in feats["rivers"]}),
        "attributes": attrs,
        **(extra or {}),
    }


def relief_contours(world, levels=9, smooth=1.6, tolerance=1.2):
    """Elevation isolines as vector paths.

    Without these the export has no terrain at all: coastline, regions and
    rivers only. A viewer then cannot show relief no matter how good it is,
    because relief was never in the file. Contours are the cheap vector answer
    (a raster hillshade would work too but stops being resolution-independent).
    """
    elev, land = world["elevation"], ~world["sea"]
    sl = float(world.get("sea_level", np.quantile(elev, 1 - land.mean())))
    rel = np.clip((elev - sl) / (1 - sl + 1e-9), 0, 1)
    rel = ndimage.gaussian_filter(rel, smooth)
    out = []
    for i in range(1, levels):
        t = i / levels
        for r in _rings((rel > t) & land, tolerance):
            out.append({"level": round(t, 3), "points": r.tolist()})
    return out


def extract(world, layers=None, region_field="provinces", coast_tol=1.0,
            region_tol=1.6, river_min=None, km_per_px=None,
            projection="flat", relief_levels=9):
    """Extract coastline, region polygons and river polylines.

    `region_field` names the raster label array to polygonise: provinces,
    polity, culture, religion, anything integer-labelled. Pass it from
    `layers` or from `world`.
    """
    elev, sea = world["elevation"], world["sea"]
    land = ~sea
    h, w = elev.shape

    feats = {"meta": {"grid": [int(h), int(w)],
                      "km_per_px": km_per_px,
                      "projection": projection,
                      "region_field": region_field},
             "coast": [], "regions": [], "rivers": [], "lakes": [], "relief": []}
    if relief_levels:
        feats["relief"] = relief_contours(world, levels=relief_levels)

    for r in _rings(land, coast_tol):
        feats["coast"].append(r.tolist())

    labels = None
    if layers and region_field in layers:
        labels = layers[region_field]
    elif region_field in world:
        labels = world[region_field]

    if labels is not None:
        for lab in np.unique(labels[land]):
            if lab < 0:
                continue
            m = (labels == lab) & land
            if m.sum() < 12:
                continue
            rings = _rings(m, region_tol)
            if not rings:
                continue
            feats["regions"].append({
                "id": int(lab),
                "rings": [r.tolist() for r in rings],
                "attributes": _stats(world, layers, m),
            })

    if "accumulation" in world:
        feats["rivers"] = river_polylines(world, river_min)

    if "lakes" in world:
        for r in _rings(world["lakes"], 1.0):
            feats["lakes"].append(r.tolist())

    feats["meta"]["counts"] = {k: len(v) for k, v in feats.items()
                               if isinstance(v, list)}
    return feats


# ------------------------------------------------------------------- SVG

PALETTE = {
    "sea": "#22354f", "land": "#e9dfc6", "coast": "#2a221b",
    "region": "#2a221b", "river": "#3a5f84", "lake": "#6e8eac",
}


def _path(ring, sx, sy, closed=True):
    """(row, col) to SVG path data. Rounding to 2dp typically halves file size
    with no visible change at any sane zoom."""
    pts = [f"{p[1] * sx:.2f},{p[0] * sy:.2f}" for p in ring]
    return "M" + "L".join(pts) + ("Z" if closed else "")


def to_svg(feats, width=2000, fill_by=None, title="map", manifest=None):
    """Self-contained SVG. Every region carries its id and attributes as data-*,
    and an embedded manifest describes what those attributes mean, so a reader
    needs no knowledge of the particular world."""
    h, w = feats["meta"]["grid"]
    height = int(round(width * h / w))
    sx, sy = width / w, height / h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" id="map">',
        f'<title>{xml_escape(str(title))}</title>',
        ('<script type="application/json" id="worldforge-manifest">'
         + json.dumps(manifest).replace("&", "\\u0026").replace("<", "\\u003c") + '</script>') if manifest else '',
        f'<rect width="{width}" height="{height}" fill="{PALETTE["sea"]}"/>',
        '<g id="land">',
    ]
    for r in feats["coast"]:
        parts.append(f'<path d="{_path(r, sx, sy)}" fill="{PALETTE["land"]}" '
                     f'fill-rule="evenodd" stroke="{PALETTE["coast"]}" stroke-width="1.2"/>')
    parts.append("</g>")

    vals = None
    if fill_by:
        vals = [rg["attributes"].get(fill_by) for rg in feats["regions"]]
        vals = [v for v in vals if v is not None]
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)

    parts.append('<g id="regions">')
    for rg in feats["regions"]:
        d = " ".join(_path(r, sx, sy) for r in rg["rings"])
        a = rg["attributes"]
        if fill_by and a.get(fill_by) is not None and hi > lo:
            t = (a[fill_by] - lo) / (hi - lo)
            fill = f"hsl({int(48 - 40 * t)},{int(30 + 45 * t)}%,{int(78 - 26 * t)}%)"
        else:
            fill = "none"
        attrs = " ".join(f'data-{k.replace("_", "-")}="{xml_escape(str(v), quote=True)}"' for k, v in a.items())
        parts.append(f'<path class="region" data-id="{xml_escape(str(rg["id"]), quote=True)}" {attrs} d="{d}" '
                     f'fill="{fill}" fill-rule="evenodd" '
                     f'stroke="{PALETTE["region"]}" stroke-width="0.7" '
                     f'stroke-opacity="0.55"/>')
    parts.append("</g>")

    if feats.get("relief"):
        parts.append('<g id="relief" fill="none" stroke="#6b5c4c" '
                     'stroke-opacity="0.30">')
        for c in feats["relief"]:
            parts.append(f'<path data-level="{c["level"]}" '
                         f'd="{_path(c["points"], sx, sy, closed=False)}" stroke-width="0.6"/>')
        parts.append("</g>")

    widths = {"major": 2.6, "trunk": 1.5, "minor": 0.8}
    parts.append('<g id="rivers" fill="none" stroke="%s" stroke-linecap="round">'
                 % PALETTE["river"])
    for rv in feats["rivers"]:
        parts.append(f'<path d="{_path(rv["points"], sx, sy, closed=False)}" '
                     f'stroke-width="{widths.get(rv["class"], 1.0)}"/>')
    parts.append("</g>")

    if feats["lakes"]:
        parts.append('<g id="lakes">')
        for r in feats["lakes"]:
            parts.append(f'<path d="{_path(r, sx, sy)}" fill="{PALETTE["lake"]}" '
                         f'stroke="{PALETTE["coast"]}" stroke-width="0.8"/>')
        parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


def to_geojson(feats, km_per_px=None):
    """GeoJSON in grid coordinates, for engine import or GIS. Coordinates are
    (x, y) in cells; multiply by km_per_px for a real-world scale."""
    out = {"type": "FeatureCollection", "features": []}
    for rg in feats["regions"]:
        out["features"].append({
            "type": "Feature",
            "id": rg["id"],
            "properties": dict(rg["attributes"], km_per_px=km_per_px),
            "geometry": {"type": "Polygon",
                         "coordinates": [[[p[1], p[0]] for p in r]
                                         for r in rg["rings"]]},
        })
    for rv in feats["rivers"]:
        out["features"].append({
            "type": "Feature",
            "properties": {"kind": "river", "class": rv["class"]},
            "geometry": {"type": "LineString",
                         "coordinates": [[p[1], p[0]] for p in rv["points"]]},
        })
    return out


def stats(feats):
    v_regions = sum(len(r) for rg in feats["regions"] for r in rg["rings"])
    v_coast = sum(len(r) for r in feats["coast"])
    v_rivers = sum(len(r["points"]) for r in feats["rivers"])
    return {"regions": len(feats["regions"]), "coast_rings": len(feats["coast"]),
            "rivers": len(feats["rivers"]),
            "vertices": {"regions": v_regions, "coast": v_coast,
                         "rivers": v_rivers,
                         "total": v_regions + v_coast + v_rivers}}


# ------------------------------------------------------- interactive viewer

VIEWER_CSS = """
:root{--ink:#2a221b;--panel:#f4ead6;--sea:#22354f}
*{box-sizing:border-box}
body{margin:0;background:#11131a;color:#e9e3d5;
 font:14px/1.5 ui-serif,Georgia,serif;overflow:hidden}
#wrap{position:fixed;inset:0}
svg{width:100%;height:100%;display:block;cursor:grab;touch-action:none}
svg.drag{cursor:grabbing}
.region{transition:fill-opacity .12s}
.region:hover{stroke:#8c3a2e;stroke-width:2.2;stroke-opacity:1}
.region.sel{stroke:#8c3a2e;stroke-width:3;stroke-opacity:1}
#hud{position:fixed;top:14px;left:14px;background:rgba(244,234,214,.94);
 color:var(--ink);border-radius:8px;padding:14px 16px;max-width:300px;
 box-shadow:0 6px 24px rgba(0,0,0,.45)}
#hud h1{margin:0 0 8px;font-size:19px;letter-spacing:.02em}
#hud .row{display:flex;justify-content:space-between;gap:14px;font-size:13px;
 padding:2px 0;border-bottom:1px solid rgba(42,34,27,.12)}
#hud .row span:last-child{font-variant-numeric:tabular-nums;font-weight:600}
#ctl{position:fixed;bottom:14px;left:14px;background:rgba(244,234,214,.94);
 color:var(--ink);border-radius:8px;padding:12px 14px;
 box-shadow:0 6px 24px rgba(0,0,0,.45)}
#ctl label{display:block;font-size:12px;margin:3px 0}
#ctl select{font:inherit;font-size:12px;margin-top:4px;width:100%}
button{font:inherit;font-size:12px;padding:4px 10px;margin-top:8px;cursor:pointer;
 background:var(--ink);color:var(--panel);border:0;border-radius:5px}
#scale{position:fixed;bottom:16px;right:16px;color:#e9e3d5;font-size:12px;
 text-align:right;text-shadow:0 1px 3px #000}
#scale i{display:block;height:4px;background:#e9e3d5;margin-top:4px}
.muted{opacity:.6}
"""

VIEWER_JS = """
const svg=document.getElementById('map');
const vb={x:0,y:0,w:%(W)d,h:%(H)d};
const home={...vb};
const KM=%(KM)s;
function apply(){svg.setAttribute('viewBox',`${vb.x} ${vb.y} ${vb.w} ${vb.h}`);scale();}
function scale(){
  const el=document.getElementById('scale');
  if(!KM){el.style.display='none';return;}
  const pxPerUnit=svg.clientWidth/vb.w;
  let km=KM*(200/pxPerUnit);
  const p=Math.pow(10,Math.floor(Math.log10(km)));
  km=Math.round(km/p)*p;
  el.querySelector('b').textContent=km.toLocaleString()+' km';
  el.querySelector('i').style.width=(km/KM*pxPerUnit)+'px';
}
svg.addEventListener('wheel',e=>{
  e.preventDefault();
  const r=svg.getBoundingClientRect();
  const mx=vb.x+(e.clientX-r.left)/r.width*vb.w;
  const my=vb.y+(e.clientY-r.top)/r.height*vb.h;
  const k=e.deltaY>0?1.15:1/1.15;
  const nw=Math.min(home.w*3,Math.max(home.w/300,vb.w*k));
  const s=nw/vb.w;
  vb.x=mx-(mx-vb.x)*s; vb.y=my-(my-vb.y)*s; vb.w=nw; vb.h*=s;
  apply();
},{passive:false});
let drag=null;
svg.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,vx:vb.x,vy:vb.y};
  svg.classList.add('drag');svg.setPointerCapture(e.pointerId);});
svg.addEventListener('pointermove',e=>{
  if(!drag)return;
  const r=svg.getBoundingClientRect();
  vb.x=drag.vx-(e.clientX-drag.x)/r.width*vb.w;
  vb.y=drag.vy-(e.clientY-drag.y)/r.height*vb.h;
  apply();
});
addEventListener('pointerup',()=>{drag=null;svg.classList.remove('drag');});
const hud=document.getElementById('hud');
const LABEL={'cells':'cells','mean-elevation':'mean elevation','max-elevation':'peak',
 'dominant-biome':'dominant biome','population-index':'population','development-index':'development',
 'garrison-index':'garrison','culture':'culture','religion':'religion','polity':'polity'};
let sel=null;
document.querySelectorAll('.region').forEach(p=>{
  p.addEventListener('click',ev=>{
    ev.stopPropagation();
    if(sel)sel.classList.remove('sel');
    sel=p;p.classList.add('sel');
    let h='<h1>Region '+p.dataset.id+'</h1>';
    for(const k in p.dataset){
      if(k==='id')continue;
      const kk=k.replace(/([A-Z])/g,'-$1').toLowerCase();
      h+='<div class="row"><span>'+(LABEL[kk]||kk)+'</span><span>'+p.dataset[k]+'</span></div>';
    }
    hud.innerHTML=h;
  });
});
svg.addEventListener('click',()=>{if(sel){sel.classList.remove('sel');sel=null;}
  hud.innerHTML='<h1>%(TITLE)s</h1><div class="muted">Click a region. Scroll to zoom, drag to pan.</div>';});
document.getElementById('reset').onclick=()=>{Object.assign(vb,home);apply();};
document.querySelectorAll('#ctl input[type=checkbox]').forEach(c=>{
  c.onchange=()=>{const g=document.getElementById(c.dataset.layer);
    if(g)g.style.display=c.checked?'':'none';};
});
const FILLS=%(FILLS)s;
document.getElementById('fill').onchange=e=>{
  const key=e.target.value;
  document.querySelectorAll('.region').forEach(p=>{
    if(key==='none'){p.setAttribute('fill','none');return;}
    const v=parseFloat(p.dataset[key]);
    const [lo,hi]=FILLS[key];
    const t=(hi>lo)?(v-lo)/(hi-lo):0;
    p.setAttribute('fill',`hsl(${Math.round(48-40*t)},${Math.round(30+45*t)}%%,${Math.round(78-26*t)}%%)`);
  });
};
apply();
"""


def to_html(feats, title="map", width=2000, km_per_px=None, fill_by=None,
            manifest=None, categories=None, seed=None):
    """A self-contained interactive map: pan, zoom, clickable regions, layer
    toggles and a live scale bar.

    Everything the viewer needs is already on the geometry as data-* attributes,
    so there is no second file to keep in sync and the page works offline from
    the filesystem.
    """
    h, w = feats["meta"]["grid"]
    if manifest is None:
        manifest = build_manifest(feats, km_per_px=km_per_px,
                                  categories=categories, title=title, seed=seed)
    svg = to_svg(feats, width=width, fill_by=fill_by, title=title,
                 manifest=manifest)
    sw = width
    sh = int(round(width * h / w))
    km = (km_per_px * w / width) if km_per_px else None

    # ranges come from the manifest, which came from the data. Nothing here
    # knows what world this is.
    ranges = {k: [a["min"], a["max"]] for k, a in manifest["attributes"].items()}
    camel = {k: k.split("_")[0] + "".join(p.title() for p in k.split("_")[1:])
             for k in ranges}
    fills = {camel[k]: v for k, v in ranges.items()}
    opts = "".join(f'<option value="{camel[k]}">{k.replace("_", " ")}</option>'
                   for k in ranges)

    js = VIEWER_JS % {"W": sw, "H": sh, "KM": km if km else "null",
                      "TITLE": str(title).replace("\\", "\\\\").replace("'", "\\u0027").replace("<", "\\u003c").replace("\n", "\\n"), "FILLS": json.dumps(fills)}
    layers = [("regions", "regions"), ("relief", "relief contours"),
              ("rivers", "rivers"), ("lakes", "lakes"), ("land", "coastline")]
    checks = "".join(
        f'<label><input type="checkbox" data-layer="{gid}" checked> {name}</label>'
        for gid, name in layers)

    return f"""<!doctype html><meta charset="utf-8">
<title>{xml_escape(str(title))}</title><style>{VIEWER_CSS}</style>
<div id="wrap">{svg}</div>
<div id="hud"><h1>{xml_escape(str(title))}</h1>
<div class="muted">Click a region. Scroll to zoom, drag to pan.</div></div>
<div id="ctl">{checks}
<label>colour by<select id="fill"><option value="none">none</option>{opts}</select></label>
<button id="reset">reset view</button></div>
<div id="scale"><b></b><i></i></div>
<script>{js}</script>"""
