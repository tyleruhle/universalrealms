"""Deterministic coast-sensitive estuary and delta cartography.

IMPORTANT: this is a *cartographic* overlay, not a new flow solver.
Distributaries are candidate channels inferred from real river mouths; they do
not alter drainage, sea level, or water budgets. Detailed sediment transport,
tidal hydrodynamics and true bifurcating flow remain future research tasks.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw

@dataclass(frozen=True)
class CoastalChannel:
    mouth: tuple[int,int]       # (x,y) of source shoreline river cell
    kind: str                  # 'estuary' or 'delta'
    branches: tuple[tuple[tuple[int,int],...], ...]
    discharge: float


def coastal_channels(world, *, min_discharge=None, max_mouths=9,
                     separation=28, max_inland=14):
    """Identify sea-adjacent river mouths and optional nearby distributaries.

    A branch is kept only where all its land pixels are close to the shore, and
    it terminates on the sea. Returns stable coordinates independent of style.
    """
    sea = np.asarray(world['sea'],bool)
    h,w=sea.shape
    discharge=np.asarray(world.get('discharge',world['accumulation']),float)
    land=~sea
    shore=land & ndimage.binary_dilation(sea,structure=np.ones((3,3),bool))
    finite=discharge[np.isfinite(discharge)&land]
    if not len(finite):return []
    cutoff = float(min_discharge) if min_discharge is not None else max(h*w*.0015,float(np.quantile(finite,.89)))
    yy,xx=np.where(shore & (discharge>=cutoff))
    order=sorted(zip(xx.tolist(),yy.tolist()),key=lambda xy:(-discharge[xy[1],xy[0]],xy[1],xy[0]))
    selected=[]
    for x,y in order:
        if len(selected)>=max_mouths:break
        if any((x-px)**2+(y-py)**2 < separation**2 for px,py in selected):continue
        selected.append((x,y))
    # EDT gives distance to nearest ocean pixel and its position.
    dist, nearest=ndimage.distance_transform_edt(land,return_indices=True)
    result=[]
    for x,y in selected:
        # Map two distinct coastal directions, never inland beyond max_inland.
        branches=[]
        salinity='estuary'
        for direction in (-1,1):
            candidates=[]
            for r in range(3,max_inland+1):
                for dy in (-r,0,r):
                    for dx in (-r,0,r):
                        xx=x+dx; yy=y+dy
                        if not (1<=xx<w-1 and 1<=yy<h-1 and land[yy,xx] and dist[yy,xx]<=max_inland):continue
                        if discharge[yy,xx] < cutoff*.14:continue
                        if direction*(xx-x)<2:continue
                        candidates.append((float(discharge[yy,xx])/(1+r*.12),xx,yy))
                if candidates:break
            if not candidates:continue
            _,sx,sy=max(candidates,key=lambda item:(item[0],-item[2],-item[1]))
            # Only draw if a coastal arc actually routes into the sea without
            # crossing distant inland regions. Interpolate small source-mouth segment.
            ey,ex=nearest[:,y,x]
            path=[]
            for t in np.linspace(0,1,max(4,int(np.hypot(x-sx,y-sy))*3)):
                px=int(round(sx+(x-sx)*t));py=int(round(sy+(y-sy)*t))
                if not land[py,px] or dist[py,px]>max_inland:break
                if not path or path[-1]!=(px,py):path.append((px,py))
            if len(path)<3 or path[-1]!=(x,y):continue
            path.append((int(ex),int(ey)))
            if not sea[int(ey),int(ex)]:continue
            if path not in branches:branches.append(path)
        if len(branches)>1:salinity='delta'
        # Even without a branch, retain high-flow shoreline mouths for estuary shading.
        result.append(CoastalChannel((x,y),salinity,tuple(tuple(b) for b in branches),float(discharge[y,x])))
    return result


def apply_coastal_waterways(rgb,world,channels=None,*,river_color=(66,109,130),
                            sea_tint=(116,164,176)):
    """Add subtle estuary tint and candidate distributary strokes to RGB grid."""
    if channels is None:channels=coastal_channels(world)
    if not channels:return rgb.copy()
    sea=np.asarray(world['sea'],bool)
    h,w=sea.shape
    out=rgb.astype(float).copy()
    tint=np.zeros((h,w),bool)
    ink=Image.new('L',(w,h),0);dr=ImageDraw.Draw(ink)
    for c in channels:
        x,y=c.mouth
        for yy in range(max(0,y-5),min(h,y+6)):
            for xx in range(max(0,x-5),min(w,x+6)):
                if sea[yy,xx] and (xx-x)**2+(yy-y)**2<=25:
                    tint[yy,xx]=True
        for branch in c.branches:
            dr.line(branch,fill=255,width=1,joint='curve')
    out[tint]=out[tint]*.67+np.asarray(sea_tint)*.33
    painted=np.asarray(ink)>0
    out[painted]=np.asarray(river_color,dtype=float)
    return np.uint8(np.clip(out,0,255))
