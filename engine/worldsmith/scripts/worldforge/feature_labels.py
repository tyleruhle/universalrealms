"""Geographically anchored cartographic labels for selected real features.

Suggest paths for *user-provided names* without inventing canonical hydronyms.
The river geometry always originates in the Worldforge receiver graph.
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter1d
from label_engine import MapLabel, place_labels
from vector import river_polylines


def suggest_river_label(world: dict, name: str, scale=3, existing=(),
                        min_length_px=110):
    """Return a MapLabel on a real watercourse, or None when no legible fit.

    Uses a smoothed *label baseline* only; river geometry/hydrology is not
    modified. Works best for short names and long mostly east/west rivers.
    The result is a proposal, not an attribution of the supplied name to any
    known river. Pass explicit coordinates for a particular canonical river.
    """
    if not name.strip():return None
    h,w=world['sea'].shape
    min_cells=min_length_px/max(1,scale)
    channels=river_polylines(world,river_min=max(10,int(w*h*.00020)),simplify=.15)
    def length(rv):
        p=np.array(rv['points'],float)
        return float(np.hypot(*np.diff(p,axis=0).T).sum()) if len(p)>=2 else 0
    candidates=sorted(channels,key=length,reverse=True)
    sizes={'river':max(12,5*scale),'region':max(15,6*scale),
           'ocean':max(17,8*scale),'range':max(12,6*scale),'city':max(12,6*scale)}
    for rv in candidates:
        if length(rv) < min_cells: break
        points=np.asarray(rv['points'],dtype=float)
        if len(points)<6: continue
        # Only the display baseline is smoothed; actual river stays untouched.
        baseline=gaussian_filter1d(points,2.2,axis=0,mode='nearest')
        coords=tuple((float(p[1]*scale),float(p[0]*scale)) for p in baseline)
        label=MapLabel(name,coords[len(coords)//2][0],coords[len(coords)//2][1],
                       kind='river',priority=75,locked=True,terrain='land',path=coords)
        placed,rejected=place_labels([*existing,label],(w*scale,h*scale),
              sizes=sizes,margin=17*scale,land_mask=~world['sea'])
        if any(p.text==name and p.glyphs for p in placed):return label
    return None
