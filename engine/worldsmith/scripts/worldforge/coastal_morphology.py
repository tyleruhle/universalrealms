"""Phase 2B: deterministic, non-destructive coastal morphology and sedimentary rendering.

All outputs are *interpretative masks*, not terrain/hydrodynamic simulation.
Morphology classification distinguishes recessed estuaries, delta-prone mouths,
and exposed shores using coast geometry and supplied discharge. No mutations.
"""
from dataclasses import dataclass
import numpy as np
from scipy import ndimage
from coastal_waterways import coastal_channels

@dataclass(frozen=True)
class CoastalFeature:
    mouth: tuple[int,int]
    kind: str
    discharge: float
    openness: float
    coastal_relief: float


def classify_coasts(world, channels=None, *, radius=12):
    """Return reproducible local coastal types using neighborhood sea openness.

    A low sea fraction near the coast suggests an enclosed estuary; exposed
    mouths with high relative flow are classed delta-prone, not true deltas.
    """
    sea=np.asarray(world['sea'],dtype=bool)
    elevation=np.asarray(world['elevation'],dtype=float)
    channels=coastal_channels(world) if channels is None else channels
    if not channels:return []
    discharge=np.array([c.discharge for c in channels])
    baseline=max(float(np.quantile(discharge,.60)),1e-8)
    h,w=sea.shape
    results=[]
    for c in channels:
        x,y=c.mouth
        x0,x1=max(0,x-radius),min(w,x+radius+1)
        y0,y1=max(0,y-radius),min(h,y+radius+1)
        local_sea=sea[y0:y1,x0:x1]
        openness=float(local_sea.mean())
        land_elev=elevation[y0:y1,x0:x1][~local_sea]
        relief=float(np.std(land_elev)) if len(land_elev) else 0.
        kind=('recessed_estuary' if openness<.27 else
              'delta_prone' if c.discharge>=baseline and openness<.75 else
              'open_estuary')
        results.append(CoastalFeature((x,y),kind,float(c.discharge),openness,relief))
    return results


def sediment_masks(world, features=None, *, radius=9):
    """Return masks for plausible floodplain, wetland, and shallow marine plume.

    The land mask never crosses into sea; marine plume never crosses onto
    land. These represent suggested depositional zones only.
    """
    sea=np.asarray(world['sea'],bool)
    features=classify_coasts(world) if features is None else features
    h,w=sea.shape
    wetland=np.zeros((h,w),bool)
    plume=np.zeros((h,w),bool)
    yy,xx=np.ogrid[:h,:w]
    land_distance=ndimage.distance_transform_edt(~sea)
    for f in features:
        x,y=f.mouth
        r=radius*(1.5 if f.kind=='delta_prone' else 1.)
        circular=(xx-x)**2+(yy-y)**2<=r*r
        wetland |= circular & ~sea & (land_distance<=3 if f.kind=='delta_prone' else land_distance<=2)
        plume |= circular & sea
    return wetland,plume


def render_morphology(rgb, world, features=None, *,
                      wetland_color=(125,155,121),plume_color=(166,189,179)):
    """Blend morphology into RGB map; preserves input arrays and world data."""
    wetland,plume=sediment_masks(world,features)
    out=rgb.astype(float).copy()
    out[wetland]=out[wetland]*.60+np.asarray(wetland_color)*.40
    out[plume]=out[plume]*.83+np.asarray(plume_color)*.17
    return np.uint8(np.clip(out,0,255))
