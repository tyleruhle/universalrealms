"""Worldsmith geographic label layout: stable, collision-aware, terrain-aware.

MapLabel coordinates and optional path points are final *map panel* pixels. Path
labels use independent character poses shared by raster and SVG renderers.
Locked labels retain their anchor but remain subject to safety constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import atan2, degrees, hypot
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class MapLabel:
    text: str
    x: float
    y: float
    kind: str = 'region'
    priority: int = 0
    locked: bool = False
    terrain: str | None = None  # 'land', 'sea' or None
    path: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class GlyphPose:
    char: str
    x: float
    y: float
    angle: float


@dataclass(frozen=True)
class PlacedLabel:
    text: str
    x: float
    y: float
    bounds: tuple[int, int, int, int]
    kind: str
    glyphs: tuple[GlyphPose, ...] = ()


FONT_CANDIDATES = {
    'regular': ['/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
                '/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf'],
    'bold': ['/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
             '/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf'],
    'italic': ['/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf',
               '/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf'],
}


def load_font(size, face='regular'):
    for path in FONT_CANDIDATES.get(face, FONT_CANDIDATES['regular']):
        try:
            return ImageFont.truetype(path, max(9, int(size)))
        except OSError:
            pass
    return ImageFont.load_default()


def _font_for(kind, sizes):
    return load_font(sizes.get(kind, 20), 'italic' if kind in {'ocean','river'} else
                     'bold' if kind=='region' else 'regular')


def _intersects(a, b, gap=5):
    return a[0] < b[2]+gap and a[2]+gap > b[0] and a[1] < b[3]+gap and a[3]+gap > b[1]


def _sample_terrain(bounds, terrain, image_size, requirement):
    if terrain is None or requirement is None:
        return True
    width,height = image_size
    h,w = terrain.shape
    x0,y0,x1,y1=bounds
    xs=np.linspace(x0+3,x1-3,5).astype(int)
    ys=np.linspace(y0+3,y1-3,3).astype(int)
    xx,yy=np.meshgrid(xs,ys)
    ix=np.clip((xx*w/width).astype(int),0,w-1)
    iy=np.clip((yy*h/height).astype(int),0,h-1)
    frac=float(terrain[iy,ix].mean())
    return frac >= (.80 if requirement=='land' else .90) if requirement=='land' else frac <= .10


def _path_poses(text, path, font, max_bend=58):
    """Return centered, upright individual letters along a polyline."""
    if len(path)<2: return ()
    pts=np.array(path,float)
    dist=np.hypot(np.diff(pts[:,0]),np.diff(pts[:,1]))
    good=np.r_[True,dist>1e-6]
    pts=pts[good]
    if len(pts)<2: return ()
    distances=np.hypot(np.diff(pts[:,0]),np.diff(pts[:,1]))
    cum=np.r_[0,np.cumsum(distances)]
    widths=[font.getlength(c) for c in text]
    length=sum(widths)+max(0,len(text)-1)*.9
    if length>cum[-1]*.90: return ()
    # Reverse writing direction to keep characters right-side-up.
    if pts[-1,0]<pts[0,0]:
        pts=pts[::-1]; distances=distances[::-1]
        cum=np.r_[0,np.cumsum(distances)]
    start=(cum[-1]-length)/2
    cursor=start
    glyphs=[]
    for i,(c,cw) in enumerate(zip(text,widths)):
        d=cursor+cw/2
        seg=min(len(distances)-1,max(0,int(np.searchsorted(cum,d,side='right')-1)))
        t=(d-cum[seg])/(distances[seg]+1e-9)
        x,y=pts[seg]*(1-t)+pts[seg+1]*t
        a=degrees(atan2(pts[seg+1,1]-pts[seg,1],pts[seg+1,0]-pts[seg,0]))
        if abs(a)>max_bend: return ()
        glyphs.append(GlyphPose(c,float(x),float(y),float(a)))
        cursor+=cw+.9
    if glyphs and max(g.angle for g in glyphs)-min(g.angle for g in glyphs)>65:
        return ()
    return tuple(glyphs)


def place_labels(labels: Iterable[MapLabel], image_size, sizes=None,
                 reserved=(), margin=24, max_shift=65, land_mask=None, terrain_mask=None):
    """Deterministic placement with geographic screening and optional paths.

    `land_mask` is a bool grid (not upscaled); it is never modified. `terrain`
    defaults to land for regions and cities, sea for oceans, and unrestricted for
    range/river labels, which routinely cross narrow streams and mountain rock.
    """
    sizes=sizes or {'region':25,'ocean':29,'range':19,'city':18,'river':15}
    width,height=image_size
    occupied=list(reserved)
    placed,rejected=[],[]
    offsets=((0,0),(0,-.5),(0,.5),(-.65,0),(.65,0),(-.65,-.5),(.65,-.5),(-.65,.5),(.65,.5))
    for label in sorted(labels,key=lambda p:-p.priority):
        if not label.text.strip():
            rejected.append(label); continue
        font=_font_for(label.kind,sizes)
        requirement=label.terrain if label.terrain is not None else ('sea' if label.kind=='ocean' else 'land' if label.kind in ('region','city') else None)
        if label.path:
            poses=_path_poses(label.text,label.path,font)
            if not poses:
                rejected.append(label); continue
            pad=max(4,sizes.get(label.kind,20)*.7)
            x0=min(g.x for g in poses)-pad; x1=max(g.x for g in poses)+pad
            y0=min(g.y for g in poses)-pad; y1=max(g.y for g in poses)+pad
            bounds=tuple(int(round(q)) for q in (x0,y0,x1,y1))
            if x0<margin or y0<margin or x1>width-margin or y1>height-margin:
                rejected.append(label); continue
            if any(_intersects(bounds,b) for b in occupied):
                rejected.append(label); continue
            # Path should lie on the appropriate surface if constrained.
            if land_mask is not None and requirement:
                samples=[]
                for glyph in poses:
                    ix=int(np.clip(glyph.x*land_mask.shape[1]/width,0,land_mask.shape[1]-1))
                    iy=int(np.clip(glyph.y*land_mask.shape[0]/height,0,land_mask.shape[0]-1))
                    samples.append(bool(land_mask[iy,ix]))
                frac=np.mean(samples)
                if (requirement=='land' and frac<.90) or (requirement=='sea' and frac>.10):
                    rejected.append(label); continue
            occupied.append(bounds)
            placed.append(PlacedLabel(label.text,float(np.mean([p.x for p in poses])),
                                      float(np.mean([p.y for p in poses])),bounds,label.kind,poses))
            continue
        bb=font.getbbox(label.text)
        tw,th=bb[2]-bb[0],bb[3]-bb[1]
        for dx,dy in offsets[:1 if label.locked else None]:
            cx,cy=label.x+dx*max_shift,label.y+dy*max_shift
            x0,y0=int(cx-tw/2),int(cy-th/2)
            bounds=(x0,y0,x0+tw,y0+th)
            if x0<margin or y0<margin or x0+tw>width-margin or y0+th>height-margin:continue
            if any(_intersects(bounds,b) for b in occupied):continue
            if land_mask is not None and not _sample_terrain(bounds,land_mask,image_size,requirement):continue
            if terrain_mask is not None and not terrain_mask(cx,cy,label.kind,bounds):continue
            occupied.append(bounds)
            placed.append(PlacedLabel(label.text,cx,cy,bounds,label.kind))
            break
        else: rejected.append(label)
    return placed,rejected


def paint_labels(image, placed, colors=None, sizes=None, halo_width=3):
    colors=colors or {'region':(55,41,30),'ocean':(48,75,96),
                      'range':(85,66,50),'city':(55,41,30),'river':(43,88,111)}
    sizes=sizes or {'region':25,'ocean':29,'range':19,'city':18,'river':15}
    dr=ImageDraw.Draw(image)
    for label in placed:
        font=_font_for(label.kind,sizes)
        col=colors.get(label.kind,colors['region'])
        if not label.glyphs:
            dr.text((label.x,label.y),label.text,anchor='mm',font=font,fill=col,
                    stroke_width=halo_width,stroke_fill=(243,235,215))
            continue
        # Character-level rotation preserves a genuinely curved label in PNG.
        fsize=sizes.get(label.kind,20)
        for g in label.glyphs:
            if g.char==' ':continue
            tile=Image.new('RGBA',(fsize*4,fsize*4),(0,0,0,0))
            ImageDraw.Draw(tile).text((fsize*2,fsize*2),g.char,anchor='mm',font=font,
                                      fill=col,stroke_width=halo_width,
                                      stroke_fill=(243,235,215))
            rotated=tile.rotate(-g.angle,resample=Image.Resampling.BICUBIC,expand=True)
            image.paste(rotated,(round(g.x-rotated.width/2),round(g.y-rotated.height/2)),rotated)
    return image


def labels_to_svg(placed, sizes=None, dy=0, stroke='#f3ebd7'):
    """Vector lettering uses same glyph poses as PNG (font fallback may differ)."""
    sizes=sizes or {'region':25,'ocean':29,'range':19,'city':18,'river':15}
    colors={'region':'#37291e','ocean':'#304b60','range':'#554232',
            'city':'#37291e','river':'#2b586f'}
    parts=['<g id="cartographic-labels" paint-order="stroke fill" stroke-linejoin="round">']
    for label in placed:
        size=sizes.get(label.kind,20)
        fontstyle='italic' if label.kind in ('river','ocean') else 'normal'
        weight='bold' if label.kind=='region' else 'normal'
        col=colors.get(label.kind,'#37291e')
        attrs=f'fill="{col}" font-size="{size}" font-family="DejaVu Serif, Liberation Serif, Georgia, serif" font-style="{fontstyle}" font-weight="{weight}" stroke="{stroke}" stroke-width="2" text-anchor="middle" dominant-baseline="central"'
        if not label.glyphs:
            parts.append(f'<text x="{label.x:.2f}" y="{label.y+dy:.2f}" {attrs}>{escape(label.text)}</text>')
        else:
            for g in label.glyphs:
                if g.char==' ':continue
                parts.append(f'<text x="{g.x:.2f}" y="{g.y+dy:.2f}" transform="rotate({g.angle:.2f} {g.x:.2f} {g.y+dy:.2f})" {attrs}>{escape(g.char)}</text>')
    parts.append('</g>')
    return '\n'.join(parts)
