"""Worldsmith Phase 1B: shared cartographic symbol scene for PNG + hybrid SVG.

Geometry is in world grid cells; renderer-specific code handles scale.  The
simulation is immutable.  Glyphs are small authored vector strokes placed
using geographic masks and seeded deterministic jitter.
"""
from __future__ import annotations
from dataclasses import dataclass
from html import escape
from typing import Tuple
import numpy as np
from scipy import ndimage
from PIL import ImageDraw

Point = Tuple[float, float]

@dataclass(frozen=True)
class InkStroke:
    points: tuple[Point, ...]
    width: float = 0.48
    alpha: int = 220
    family: str = 'terrain'
    fill: bool = False
    feature_id: str = ""


def _strokes_at(glyph: str, x: float, y: float, size: float, variant: int = 0, feature_id: str = ""):
    """Drawn-by-hand inspired glyph geometry, generated in consistent units.

    Coordinates intentionally encode actual lines/hatch detail rather than
    simple triangle placeholders; all primitives are true SVG-ready vectors.
    """
    out = []
    def stroke(coords, width=.44, alpha=210, fill=False):
        pts=tuple((x+px*size, y+py*size) for px,py in coords)
        out.append(InkStroke(pts,width,alpha,glyph,fill,feature_id))

    if glyph == 'mountain':
        # Non-symmetric ridgeline with three distinct peaks and broken foothills.
        skew = (variant % 4 - 1.5) * .07
        stroke([(-1.06,.52),(-.68,.12),(-.49,-.06),(-.33,.06),(-.08,-.59),(.03,-.8),(.23,-.46),(.36,-.22),(.52,-.4),(.68,-.08),(1.02,.50)],.58,244)
        stroke([(-.93,.54),(-.64,.54),(-.29,.48),(-.03,.57),(.34,.50),(.61,.56),(.95,.53)],.24,100)
        # Detailed rock-face hatching, weighted to shaded right flank.
        stroke([(.03,-.8),(.10,-.26),(.30,.10),(.37,.50)],.34,174)
        stroke([(.19,-.22),(.32,-.08),(.44,.32)],.24,155)
        stroke([(.40,-.18),(.57,.03),(.68,.37)],.27,165)
        stroke([(-.45,-.03),(-.42,.18),(-.25,.37)],.26,163)
        stroke([(-.33,.28),(-.22,.40)],.25,125)
        # Snow-line scribble at highest peak (not an artificial filled white cap).
        if variant % 3 == 0:
            stroke([(-.08,-.59),(.02,-.42),(.12,-.52),(.22,-.45)],.28,185)
        # Distinct slope accents, preventing identical repeats.
        if variant % 2:
            stroke([(.54,.15),(.70,.36)],.24,140)
        else:
            stroke([(-.72,.23),(-.81,.43)],.24,130)
    elif glyph == 'pine':
        skew = (variant % 3-1)*.05
        stroke([(0,.65),(0,-.8)],.37,217)
        stroke([(-.55,.28),(-.25,-.12),(0,-.80),(.25,-.12),(.55,.28)],.39,221)
        stroke([(-.43,-.02),(0,-.58),(.43,-.02)],.31,215)
        stroke([(-.66,.45),(-.28,.20),(0,-.32),(.28,.20),(.66,.45)],.33,191)
        stroke([(-.25,.57),(.25,.57)],.19,128)
    elif glyph == 'oak':
        # Crown with scalloped open outline, not a circle stamp.
        stroke([(-.70,.07),(-.80,-.15),(-.58,-.35),(-.56,-.56),(-.25,-.62),(-.05,-.80),(.22,-.64),(.48,-.68),(.65,-.42),(.81,-.28),(.68,-.02),(.76,.15),(.43,.30),(.10,.24),(-.22,.32),(-.48,.27),(-.70,.07)],.39,216)
        stroke([(0,.65),(0,-.06),(-.26,-.30)],.36,208)
        stroke([(0,.14),(.30,-.19)],.28,165)
        stroke([(-.35,.64),(.36,.64)],.25,100)
    return out


def make_symbol_scene(world: dict, style='illustrated', margin=18) -> list[InkStroke]:
    """Place symbols only where their geographic footprint fits within land.

    Each symbol has coastal clearance, river avoidance and page-frame clearance.
    The map contains no fictional labels/cities introduced by this module.
    """
    if style == 'atlas':
        return []
    elev = world['elevation']; sea = world['sea']; biome = world['biome']
    h,w = elev.shape
    seed = int(getattr(world.get('params'), 'seed', 0))
    rng = np.random.default_rng(seed + 97031)
    clearance = ndimage.distance_transform_edt(~sea)
    slopes = np.hypot(*np.gradient(ndimage.gaussian_filter(elev, 1.2)))
    rel = np.clip((elev-world['sea_level'])/(1-world['sea_level']+1e-8),0,1)
    river = world.get('rivers')
    if river is not None:
        river_clear = ndimage.distance_transform_edt(~river.astype(bool))
    else:
        river_clear = np.full((h,w),100.0)
    scene=[]
    # Place mountains on highland candidates rather than an arbitrary fixed grid.
    smoothing=ndimage.gaussian_filter(rel,2.0)
    crests=(smoothing==ndimage.maximum_filter(smoothing,size=11))
    candidates=np.column_stack(np.nonzero(crests & (rel>.31) & (clearance>13)))
    candidates=sorted(candidates,key=lambda p:(-round(float(rel[p[0],p[1]]),5),p[0],p[1]))
    chosen=[]
    for y,x in candidates:
        if not (margin+11 < x < w-margin-11 and margin+11 < y < h-margin-11):
            continue
        if river_clear[y,x] < 5:
            continue
        if any((x-xx)**2+(y-yy)**2 < 13**2 for yy,xx in chosen):
            continue
        chosen.append((y,x))
        size=7.0+4.5*min(1,float(rel[y,x]))
        scene.extend(_strokes_at('mountain',float(x),float(y),size,(x*17+y*23+seed)%16,f'mountain-{x}-{y}'))
        if len(chosen)>=max(70,(h*w)//500):
            break
    # Trees are clustered using actual biome and a distinct woodland texture.
    forest_mask=np.isin(biome,[4,5,10])
    gx=10
    for gy in range(margin+9,h-margin-8,9):
        for gx in range(margin+9,w-margin-8,9):
            cx=int(np.clip(gx+rng.integers(-3,4),0,w-1))
            cy=int(np.clip(gy+rng.integers(-3,4),0,h-1))
            if not forest_mask[cy,cx] or clearance[cy,cx]<8 or river_clear[cy,cx]<3:
                continue
            if slopes[cy,cx]>.043 or rel[cy,cx]>.46:
                continue
            if rng.random() > (.88 if biome[cy,cx]==10 else .69):
                continue
            family='oak' if biome[cy,cx] in (4,5) and rng.random()<.5 else 'pine'
            size=2.65+rng.random()*1.0
            # Tight groupings read as forests, not scattered isolated symbols.
            for ox,oy,scale in ((-.65,.4,.9),(.8,.25,.86),(0,-.45,1.05)):
                tx=cx+ox*size; ty=cy+oy*size
                if 0<=int(tx)<w and 0<=int(ty)<h and clearance[int(ty),int(tx)]>=4:
                    scene.extend(_strokes_at(family,tx,ty,size*scale,int(rng.integers(0,16)),f'tree-{gy}-{gx}-{ox}'))
    return scene


def paint_scene(img, strokes, scale, ink):
    dr=ImageDraw.Draw(img,'RGBA')
    for stroke in strokes:
        coords=[(round(x*scale,2),round(y*scale,2)) for x,y in stroke.points]
        if stroke.fill:
            dr.polygon(coords, fill=(*ink,stroke.alpha))
        else:
            dr.line(coords,fill=(*ink,stroke.alpha),width=max(1,round(stroke.width*scale)),joint='curve')
    return img


def scene_svg(strokes, width, height, grid_width, grid_height, ink):
    sx=width/grid_width;sy=height/grid_height
    chunks=['<g id="cartographic-symbols" fill="none" stroke-linecap="round" stroke-linejoin="round">']
    color='#%02x%02x%02x' % tuple(ink[:3])
    for idx,s in enumerate(strokes):
        pts=' '.join(('%0.2f,%0.2f'%(x*sx,y*sy)) for x,y in s.points)
        chunks.append('<polyline class="%s" points="%s" stroke="%s" stroke-opacity="%.3f" stroke-width="%.2f"%s/>'%
                      (escape(s.family,quote=True),pts,color,s.alpha/255.0,s.width*(sx+sy)/2,
                       ' fill="%s"'%color if s.fill else ''))
    chunks.append('</g>')
    return '\n'.join(chunks)


def omit_symbols_behind_labels(strokes, placed, scale=1, padding=3):
    """Remove complete glyphs from labels' knock-out zones, never half a tree.

    Every individual glyph is addressed by feature_id; all its vector strokes
    either survive or are removed.  No simulation data is ever modified.
    """
    if not placed:
        return list(strokes)
    occupied=[]
    for label in placed:
        x0,y0,x1,y1=label.bounds
        occupied.append((x0-padding,y0-padding,x1+padding,y1+padding))
    hidden=set()
    for i,stroke in enumerate(strokes):
        xs=[p[0]*scale for p in stroke.points]
        ys=[p[1]*scale for p in stroke.points]
        box=(min(xs),min(ys),max(xs),max(ys))
        if any(box[0]<=r[2] and box[2]>=r[0] and box[1]<=r[3] and box[3]>=r[1]
               for r in occupied):
            hidden.add(stroke.feature_id or ('unidentified',i))
    return [st for i,st in enumerate(strokes)
            if (st.feature_id or ('unidentified',i)) not in hidden]
