"""Worldsmith Phase 1B cartographic renderer: one world, three visual profiles.

Example:
    from worldforge_core import BIOMES, WorldParams, generate
    from map_render import render_map
    world = generate(WorldParams(seed=42, width=512, height=320))
    render_map(world, style='illustrated', title='My World').save('map.png')

All effects operate on finished world arrays. No RNG state is taken from the
simulation; decorative randomness has its own stable seed derived from params.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
from html import escape as xml_escape
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import cartography as ct
from coastal_waterways import coastal_channels, apply_coastal_waterways
from coastal_morphology import classify_coasts, render_morphology
from label_engine import MapLabel, load_font, paint_labels, place_labels, labels_to_svg
from map_scene import make_symbol_scene, paint_scene, scene_svg, omit_symbols_behind_labels
from worldforge_core import BIOMES, WorldParams, generate
from biomes import BIOMES as BIOME_TABLE
from spherical import is_planet

STYLE = {
    "illustrated": {
        "palette": {
            "land_hi": (234, 216, 173), "land_lo": (190, 167, 122),
            "sea_hi": (176, 200, 194), "sea_lo": (108, 152, 160),
            "ink": (60, 54, 39), "river": (64, 105, 119),
            "accent": (151, 91, 56), "cool": (101, 138, 133),
        }, "paper": (237, 219, 182), "ink": (58, 50, 37),
        "lines": .075, "mountains": True, "forests": True,
    },
    "atlas": {
        "palette": ct.ATLAS, "paper": (238, 239, 227),
        "ink": (34, 45, 49), "lines": .14,
        "mountains": False, "forests": False,
    },
    "medieval": {
        "palette": {
            "land_hi": (237, 219, 185), "land_lo": (223, 198, 154),
            "sea_hi": (218, 207, 181), "sea_lo": (176, 180, 161),
            "ink": (69, 50, 34), "river": (84, 99, 103),
            "accent": (139, 70, 45), "cool": (126, 133, 120),
        }, "paper": (236, 215, 178), "ink": (76, 53, 36),
        "lines": .05, "mountains": True, "forests": True,
    },
}


def _paper_grain(rgb, rng, strength=4.5):
    grain = ndimage.gaussian_filter(rng.standard_normal(rgb.shape[:2]), 0.65)
    return np.clip(rgb.astype(float) + grain[..., None] * strength, 0, 255)


def _ocean_ripples(dr, sea, scale, ink, seed=0, spacing=12):
    """Sparse, deterministic shore-hugging ink strokes, not full-width stripes."""
    h, w = sea.shape
    dist = ndimage.distance_transform_edt(sea)
    rng = np.random.default_rng(seed)
    for y in range(9, h - 8, spacing):
        for x in range(10, w - 9, spacing * 2):
            xx = int(x + rng.integers(-4, 5))
            yy = int(y + rng.integers(-3, 4))
            if (20 <= xx < w-20 and 20 <= yy < h-20 and sea[yy, xx]
                    and 3 < dist[yy, xx] < 28 and rng.random() < .65):
                sx, sy = xx * scale, yy * scale
                dr.arc((sx - 6 * scale, sy - 3 * scale,
                        sx + 6 * scale, sy + 3 * scale), 200, 330,
                       fill=ink + (100,), width=max(1, int(.65 * scale)))


def _default_labels(world, scale):
    """Illustrative names; not canonical geography or user-established lore."""
    land = ~world['sea']
    land_ids, n = ndimage.label(land)
    sizes = np.bincount(land_ids.ravel())
    components = sorted(range(1, n+1), key=lambda i: -sizes[i])
    names = ["WESTERLAND", "THE EAST REACH", "SOUTHERN ISLES", "THE OUTER ISLES"]
    labels = []
    for rank, i in enumerate(components[:4]):
        if sizes[i] < 125:
            continue
        dist = ndimage.distance_transform_edt(land_ids == i)
        y, x = np.unravel_index(np.argmax(dist), dist.shape)
        if dist[y, x] < 8:
            continue
        labels.append(MapLabel(names[rank], x*scale, y*scale,
                               kind="region", priority=90-rank*10))
    # Ocean label can be repositioned, but remains in actual sea with broad clearance.
    sea = world['sea']
    dist = ndimage.distance_transform_edt(sea)
    yy, xx = np.indices(sea.shape)
    # Prefer central sea close to midheight, away from a map edge.
    edge = np.minimum.reduce((xx, yy, sea.shape[1]-1-xx, sea.shape[0]-1-yy))
    score = np.minimum(dist, 34) + np.minimum(edge, 40)*.3 - np.abs(yy-sea.shape[0]*.54)*.07
    score[~sea] = -1e5
    y, x = np.unravel_index(np.argmax(score), score.shape)
    if score[y, x] > 15:
        labels.append(MapLabel("THE GREY SEA", x*scale, y*scale,
                               kind="ocean", priority=40))
    return labels


def render_map(world: dict, style="illustrated", title="AN UNNAMED WORLD",
               scale=3, labels=None, km_per_cell=None, subtitle=None,
               return_metadata=False, path_labels=None, return_composition=False):
    """Render one finished world in a named style without altering its data.

    `labels` can be a list of MapLabel in *final image* pixel coordinates or
    an empty list to suppress labels. `None` adds placeholder demo names
    (WESTERLAND, THE GREY SEA); never use None for a world that has a bible.
    Metadata reports `placeholder_labels` so callers can check.
    `km_per_cell` must be explicit before a real distance scale is drawn.
    """
    if style not in STYLE:
        raise ValueError(f"style must be one of: {', '.join(STYLE)}")
    if scale < 1 or int(scale) != scale:
        raise ValueError("scale must be a positive integer")
    scale = int(scale)
    st = STYLE[style]
    pal = st['palette']
    seed = int(getattr(world.get('params'), 'seed', 0))
    elev, sea = world['elevation'], world['sea']
    h,w = elev.shape
    rng = np.random.default_rng(seed + 34011)

    rgb = ct.base_surface(world, palette=pal, z=16 if style=='atlas' else 10)
    if style == 'atlas':
        # Biome-aware watercolor tint, smoothed to avoid noisy patchwork.
        # biomes.BIOMES is the 17-class superset: ids 0-12 match the flat
        # generator exactly (same names, same colours), planets add 13-16
        # (cold desert, wetland, beach, boreal wetland). Indexing the 13-class
        # flat table crashed on every planet.
        lut = np.array([BIOME_TABLE[i][1] for i in range(len(BIOME_TABLE))],dtype=float)
        ids = np.asarray(world["biome"])
        if ids.max() >= len(lut):
            raise ValueError(f"biome id {int(ids.max())} has no colour; known ids are 0-{len(lut)-1}")
        mode = ("nearest", "wrap", "nearest") if is_planet(world) else "reflect"
        biome_colors = ndimage.gaussian_filter(lut[ids], sigma=(5,5,0), mode=mode)
        land = ~sea
        rgb[land] = rgb[land]*.82 + biome_colors[land]*.18
    if style == 'medieval':
        # Deliberate lighter land relief, faded ocean, varied paper grain.
        rgb = rgb * .35 + np.array(st['paper'],dtype=float)[None,None,:] * .65
    elif style == 'illustrated':
        rgb = rgb * .67 + np.array(st['paper'],dtype=float)[None,None,:] * .33
    rgb = ct.contours(rgb, world, bands=12 if style=='atlas' else 9,
                      smooth=2.5 if style=='atlas' else 3.0,
                      weight=st['lines'], palette=pal)
    if style == 'atlas':
        rgb = ct.bathymetric_contours(rgb, world, bands=8, smooth=4.0,
                                      weight=.12, palette=pal)
    rgb = ct.graded_rivers(rgb, world, palette=pal,
                           steps=((1,0),(8,1),(35,2)) if style=='atlas'
                                 else ((1,0),(15,1)))
    channels = coastal_channels(world)
    rgb = apply_coastal_waterways(rgb, world, channels,
           river_color=tuple(int(c) for c in pal["river"]),
           sea_tint=tuple(int(c) for c in pal["sea_hi"]))
    rgb = render_morphology(rgb, world, classify_coasts(world, channels),
            wetland_color=(126,151,112) if style=="atlas" else (158,170,127),
            plume_color=tuple(int(c) for c in pal["sea_hi"]))
    rgb = ct.coastline(rgb, world, palette=pal)
    rgb = _paper_grain(rgb, rng, strength=2.1 if style=='atlas' else 4.5)

    map_img = ct.upscale(rgb, scale)
    dr = ImageDraw.Draw(map_img, 'RGBA')
    if style in ('illustrated','medieval'):
        _ocean_ripples(dr, sea, scale, st['ink'], seed+910)
    # Preserve a pristine map base; SVG reuses its exact pixels and overlays
    # the same path/label geometry as real, independently editable vectors.
    map_bg = map_img.copy()
    symbols = make_symbol_scene(world, style=style, margin=18)

    placeholder = labels is None
    if placeholder:
        # Demo names only (WESTERLAND, THE GREY SEA...). A world with a bible
        # must pass its own names, or labels=[] for none; these are never canon.
        labels = _default_labels(world,scale)
    # Leave significant clearance for decorative frame.
    sizes = {"region": max(15, 6*scale), "ocean": max(17, 8*scale),
             "range": max(12, 6*scale), "city": max(12, 6*scale),
             "river": max(10, 5*scale)}
    path_labels = path_labels or []
    # MapLabel.path keeps a single placement pipeline and prevents curved and
    # straight text from colliding. All accepted text uses the same geometry in
    # vector/raster exports.
    combined=[*labels,*path_labels]
    placed,rejected=place_labels(combined,map_img.size,sizes=sizes,
         margin=16*scale,max_shift=35*scale,land_mask=~sea)
    symbols=omit_symbols_behind_labels(symbols,placed,scale=scale,padding=3*scale)
    paint_scene(map_img,symbols,scale,st['ink'])
    paint_labels(map_img,placed,sizes=sizes,halo_width=max(1,scale//2))
    curved=[p for p in placed if p.glyphs]
    curved_rejected=[p for p in rejected if p.path]

    # Put map furniture outside the geography, so labels and frame never hide
    # the terrain or cities.  This is intentionally a composition stage.
    heading = 28*scale
    foot = 21*scale
    paper = st['paper']
    canvas = Image.new('RGB',(w*scale,h*scale+heading+foot),paper)
    canvas.paste(map_img,(0,heading))
    d = ImageDraw.Draw(canvas)
    ink = st['ink']
    pad = 12*scale
    # Border and double hairline.
    d.rectangle((pad//2,heading+pad//2,w*scale-pad//2,heading+h*scale-pad//2),
                outline=ink,width=max(1,scale))
    d.rectangle((pad,heading+pad,w*scale-pad,heading+h*scale-pad),
                outline=ink,width=1)
    title_font = load_font(12*scale,'bold')
    sm_font = load_font(max(10,5*scale),'italic')
    d.text((w*scale//2,heading//2),title,anchor='mm',font=title_font,fill=ink)
    line_y=heading-5*scale
    d.line((pad,line_y,w*scale-pad,line_y),fill=ink,width=max(1,scale//2))
    d.line((pad,heading+h*scale+5*scale,w*scale-pad,heading+h*scale+5*scale),
           fill=ink,width=max(1,scale//2))
    left = subtitle or f'{style.upper()} CARTOGRAPHIC STUDY  /  SEED {seed}'
    d.text((pad+4*scale,heading+h*scale+12*scale),left,font=sm_font,anchor='lm',fill=ink)
    if km_per_cell is not None:
        if km_per_cell <= 0:
            raise ValueError('km_per_cell must be positive')
        bar_km = 100
        # Use nice increments at variable world scales.
        for value in (50,100,200,500,1000,2000,5000):
            if 45*scale <= value/km_per_cell*scale <= 110*scale:
                bar_km=value
                break
        bw=bar_km/km_per_cell*scale
        if bw < .35*w*scale:
            x=w*scale-pad-bw
            y=heading+h*scale+12*scale
            d.line((x,y,x+bw,y),fill=ink,width=max(1,scale))
            for xp in (x,x+bw/2,x+bw):
                d.line((xp,y-3*scale,xp,y+3*scale),fill=ink,width=max(1,scale//2))
            # Equirectangular planets: east-west scale shrinks by cos(latitude),
            # so one bar is only true at the equator and must say so.
            label=f'{bar_km} km'
            below=d.textbbox((x+bw/2,y+5*scale),label,font=sm_font,anchor='mt')
            # Move the label beside the bar only when it is really cut off (more
            # than a third of its height below the canvas, as at scale=1);
            # bbox descender space alone is not clipping.
            cut=(below[3]-canvas.height) > .33*(below[3]-below[1])
            side=[label] if cut else []
            if not cut:
                d.text((x+bw/2,y+5*scale),label,font=sm_font,anchor='mt',fill=ink)
            if is_planet(world):
                # Equirectangular planets: east-west scale shrinks by
                # cos(latitude), so one bar is only true at the equator.
                side.append('scale true at equator')
            if side:
                sub_right=d.textbbox((pad+4*scale,y),left,font=sm_font,anchor='lm')[2]
                for text in (' · '.join(side), ' · '.join(side).replace('scale true at equator','at equator')):
                    tl=d.textbbox((x-6*scale,y),text,font=sm_font,anchor='rm')[0]
                    if tl > sub_right+8*scale:
                        d.text((x-6*scale,y),text,font=sm_font,anchor='rm',fill=ink)
                        break
    else:
        d.text((w*scale-pad,heading+h*scale+12*scale),'NOT TO SCALE',
               font=sm_font,anchor='rm',fill=ink)
    metadata = {"style":style,"labels_placed":len(placed),
                "placeholder_labels":placeholder,
                "labels_rejected":[lbl.text for lbl in rejected],
                "path_labels_placed":len(curved),
                "path_labels_rejected":[lbl.text for lbl in curved_rejected],
                "coastal_mouths":len(channels),
                "candidate_distributaries":sum(len(c.branches) for c in channels),
                "map_grid":[h,w],"seed":seed}
    if return_composition:
        background=canvas.copy()
        background.paste(map_bg,(0,heading))
        # The frame crosses the map pane; redraw after restoring raster terrain.
        db=ImageDraw.Draw(background)
        db.rectangle((pad//2,heading+pad//2,w*scale-pad//2,
                      heading+h*scale-pad//2),outline=ink,width=max(1,scale))
        db.rectangle((pad,heading+pad,w*scale-pad,heading+h*scale-pad),
                     outline=ink,width=1)
        composition={'background':background,'strokes':symbols,
                     'straight':placed,'curved':curved,'sizes':sizes,
                     'heading':heading,'grid':(h,w),'scale':scale,'ink':ink}
        return (canvas,metadata,composition)
    if return_metadata:
        return canvas,metadata
    return canvas


def render_svg(world: dict, style='illustrated', title='AN UNNAMED WORLD',
               scale=3, labels=None, path_labels=None, km_per_cell=None,
               subtitle=None):
    """Hybrid atlas SVG: exact raster terrain + independently editable vector
    symbols and labels, all from the identical scene as PNG. This is not a
    fully-vector terrain export; raster relief is embedded as a PNG data URI.
    """
    _, meta, comp=render_map(world,style=style,title=title,scale=scale,
       labels=labels,path_labels=path_labels,km_per_cell=km_per_cell,
       subtitle=subtitle,return_composition=True)
    base=comp['background']
    W,H=base.size
    h,w=comp['grid']; head=comp['heading']
    buff=io.BytesIO();base.save(buff,format='PNG')
    png='data:image/png;base64,'+base64.b64encode(buff.getvalue()).decode('ascii')
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'width="{W}" height="{H}">',
           f'<title>{xml_escape(str(title))}</title>',
           f'<desc>Worldsmith hybrid SVG: rasterized terrain with editable vector terrain symbols and text.</desc>',
           f'<image id="raster-terrain" width="{W}" height="{H}" href="{png}"/>',
           f'<g transform="translate(0 {head})">',
           scene_svg(comp['strokes'],w*scale,h*scale,w,h,comp['ink']),
           labels_to_svg(comp['straight'],sizes=comp['sizes'])]
    lines += ['</g>','</svg>']
    return '\n'.join(lines)


def main():
    ap=argparse.ArgumentParser(description='Worldsmith illustrated map showcase')
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--width',type=int,default=480)
    ap.add_argument('--height',type=int,default=320)
    ap.add_argument('--land',type=float,default=.34)
    ap.add_argument('--scale',type=int,default=3)
    ap.add_argument('--out',default='worldsmith_gallery')
    ap.add_argument('--title',default='THE KNOWN WORLD')
    ap.add_argument('--km-per-cell',type=float)
    ap.add_argument('--svg',action='store_true',help='also write hybrid SVG maps')
    args=ap.parse_args()
    if args.width<64 or args.height<64 or args.scale<1:
        ap.error('width and height must be >=64; scale must be positive')
    p=WorldParams(seed=args.seed,width=args.width,height=args.height,
                  land_fraction=args.land)
    world=generate(p)
    prefix=Path(args.out)
    prefix.parent.mkdir(parents=True,exist_ok=True)
    import hashlib
    before=hashlib.sha256(world['elevation'].tobytes()).hexdigest()
    results=[]
    for name in STYLE:
        img,metadata=render_map(world,style=name,title=args.title,
                                scale=args.scale,km_per_cell=args.km_per_cell,
                                return_metadata=True)
        target=f'{prefix}_{name}.png'
        img.save(target)
        if args.svg:
            svg_target=f'{prefix}_{name}.svg'
            Path(svg_target).write_text(render_svg(world,style=name,title=args.title,
                scale=args.scale,km_per_cell=args.km_per_cell),encoding='utf-8')
            metadata['svg_path']=svg_target
        metadata['path']=target
        results.append(metadata)
    assert hashlib.sha256(world['elevation'].tobytes()).hexdigest()==before
    manifest={'generator':'Worldsmith Worldforge','seed':p.seed,
              'width':p.width,'height':p.height,'land_fraction':p.land_fraction,
              'world_elevation_sha256':before,'renders':results}
    Path(f'{prefix}_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    main()
