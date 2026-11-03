"""Phase 2C: opt-in coastal land sculpting with protected geography.

This is a constrained morphological terrain edit, NOT a sediment transport model.
Edits affect the elevation and land/sea mask; drainage, climate and biomes are
recomputed to remain consistent. No changes occur to the source world.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import ndimage
from worldforge_core import (fill_depressions, flow_accumulation,
    orographic_moisture, temperature_field, classify_biomes)
from coastal_morphology import classify_coasts
from spherical import is_planet, derive_surface

@dataclass(frozen=True)
class SculptResult:
    world: dict
    changed: np.ndarray
    added_land: np.ndarray
    removed_land: np.ndarray
    rejected: tuple[str,...]


def sculpt_coast(world, *, mouths=None, protected=None, radius=12,
                 strength=0.018, mode='delta', max_features=3):
    """Build real coastal changes from selected shoreline mouths.

    `mouths` is a list of (x,y); if omitted, delta-prone mouths are selected.
    `protected` is a bool array locking cells against modification. Changes
    are restricted to a circle centered on each mouth, always on the sea side.
    mode='delta' deposits shallow sea cells; mode='inlet' cuts low land cells.
    Recomputes runoff-weighted discharge and routing for resulting elevation.
    """
    if mode not in ('delta','inlet'): raise ValueError('mode must be delta or inlet')
    if radius < 3 or strength <= 0 or max_features < 0: raise ValueError('invalid sculpt parameters')
    old_sea=np.asarray(world['sea'],bool)
    elev=np.asarray(world['elevation'],float)
    h,w=elev.shape
    if protected is None: locked=np.zeros((h,w),bool)
    else:
        locked=np.asarray(protected,bool)
        if locked.shape != elev.shape: raise ValueError('protected mask shape mismatch')
    level=float(world['sea_level'])
    planet=is_planet(world)
    selected=([f.mouth for f in classify_coasts(world) if f.kind=='delta_prone']
              if mouths is None else list(mouths))[:max_features]
    edited=elev.copy(); changed=np.zeros((h,w),bool); rejected=[]
    # Original shoreline is the reference so later edits do not cascade.
    # Planets wrap east-west: each edit window is rotated to the map centre,
    # edited there, and rotated back, so a mouth near the date line is shaped
    # on both sides of it instead of being clipped. Flat maps are not rotated.
    for coord in selected:
        x,y=map(int,coord)
        if not (0<=x<w and 0<=y<h) or old_sea[y,x]:
            rejected.append(f'{coord}: not a land mouth'); continue
        sh=(w//2-x) if planet else 0
        E=np.roll(edited,sh,1) if sh else edited
        S=np.roll(old_sea,sh,1) if sh else old_sea
        Lk=np.roll(locked,sh,1) if sh else locked
        C=np.roll(changed,sh,1) if sh else changed
        x=x+sh
        y0,y1=max(0,y-radius),min(h,y+radius+1)
        x0,x1=max(0,x-radius),min(w,x+radius+1)
        sy,sx=np.mgrid[y0:y1,x0:x1]
        sea_near=S[y0:y1,x0:x1]
        shore_cells=np.argwhere(sea_near)
        if not len(shore_cells):rejected.append(f'{coord}: no nearby sea');continue
        # Direction toward nearest sea, NOT toward an arbitrary fixed edge.
        nearest=shore_cells[np.argmin(np.sum((shore_cells-[y-y0,x-x0])**2,axis=1))]
        vx=float(nearest[1]+x0-x);vy=float(nearest[0]+y0-y)
        norm=np.hypot(vx,vy)
        if norm==0:rejected.append(f'{coord}: no sea direction');continue
        vx/=norm;vy/=norm
        along=(sx-x)*vx+(sy-y)*vy
        across=-(sx-x)*vy+(sy-y)*vx
        # Three tapered tongues on sea side; inlet is a narrower single fjord.
        block=E[y0:y1,x0:x1]
        if mode=='delta':
            tongue=np.maximum.reduce([np.exp(-((across-k*radius*.28)/(radius*.16))**2)
                for k in (-1,0,1)])
            footprint=(along>=1)&(along<radius*.9)&(np.abs(across)<radius*.65)
            influence=tongue*np.maximum(0,1-along/(radius*.95))
            target=level+strength*(.12+.88*influence)
            # Height raise must actually cross sea level, but cap excessive
            # vertical adjustment to avoid filling deep ocean.
            eligible=block >= level-strength*2
            active=footprint & sea_near & eligible & ~Lk[y0:y1,x0:x1] & (influence>.22)
            block[active]=np.maximum(block[active],target[active])
        else:
            footprint=(along<=1)&(along>-radius*.8)&(np.abs(across)<radius*.14)
            eligible=block <= level+strength*2
            active=footprint & ~sea_near & eligible & ~Lk[y0:y1,x0:x1]
            block[active]=np.minimum(block[active],level-strength*.12)
        C[y0:y1,x0:x1] |= active
        if sh:
            edited=np.roll(E,-sh,1); changed=np.roll(C,-sh,1)
    new_sea=edited<=level
    # Lock pixels are guaranteed bit-identical.
    if not np.array_equal(edited[locked],elev[locked]):raise AssertionError('protected terrain changed')
    if planet:
        # Same physics the planet was generated with: wrapped drainage,
        # three-cell moisture, humidity, 17-class biomes, rain-weighted rivers.
        surface=derive_surface(edited.astype(np.asarray(world['elevation']).dtype),
                               world['params'],level)
        updated=dict(world,elevation=edited.astype(np.asarray(world['elevation']).dtype),**surface)
        return SculptResult(updated,changed,(~surface['sea'])&old_sea,
                            surface['sea']&(~old_sea),tuple(rejected))
    filled=fill_depressions(edited)
    area,receiver=flow_accumulation(filled)
    params=world['params']
    rain=orographic_moisture(np.clip(edited-level,0,None),new_sea,params)
    temp=temperature_field(np.clip(edited-level,0,None),params)
    biomes=classify_biomes(edited,temp,rain,level)
    # Keep former river threshold semantics and add weighted runoff data.
    runoff=np.maximum(rain.astype(float),1.e-5)
    discharge,_=flow_accumulation(filled,weights=runoff)
    rivers=(area>params.river_threshold*h*w)&~new_sea
    updated=dict(world,elevation=edited.astype(np.asarray(world['elevation']).dtype),
        sea=new_sea,accumulation=area,receiver=receiver,rainfall=rain,
        temperature=temp,biome=biomes,rivers=rivers,discharge=discharge)
    return SculptResult(updated,changed,(~new_sea)&old_sea,new_sea&(~old_sea),tuple(rejected))
