"""Worldsmith 2D: versioned named geographic features and explicit coastline edits.

The feature registry is serialized as JSON. Terrain arrays stay in the caller's
world object; version history stores reversible edit commands, not large rasters.
Undo/redo replays commands from a retained immutable baseline to guarantee an
accurate drainage/climate recomputation and prevent hidden mutations.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
import json
import re
from typing import Optional
import numpy as np
from coastal_sculpt import sculpt_coast
from spherical import is_planet
from world_fingerprint import baseline_fingerprint

_ALLOWED = {'river', 'mountain_range', 'coastline', 'lake', 'region', 'settlement', 'delta'}
_ID = re.compile(r'^[a-z][a-z0-9_-]{1,63}$')

@dataclass
class GeoFeature:
    id: str
    name: str
    kind: str
    geometry: list[tuple[float, float]]
    locked: bool = False
    lock_radius: int = 3
    properties: dict = field(default_factory=dict)

    def __post_init__(self):
        if not _ID.fullmatch(self.id): raise ValueError('invalid stable feature ID')
        if self.kind not in _ALLOWED: raise ValueError(f'unknown feature type: {self.kind}')
        if not self.name.strip(): raise ValueError('feature must have a name')
        if not self.geometry: raise ValueError('feature must have coordinates')
        if self.lock_radius < 0: raise ValueError('negative lock radius')
        self.geometry = [(float(x), float(y)) for x,y in self.geometry]

    def as_dict(self):
        return dict(id=self.id,name=self.name,kind=self.kind,
                    geometry=[list(p) for p in self.geometry],locked=self.locked,
                    lock_radius=self.lock_radius,properties=deepcopy(self.properties))

@dataclass
class Revision:
    operation: str
    arguments: dict

    def as_dict(self): return {'operation':self.operation,'arguments':deepcopy(self.arguments)}

class WorldEditor:
    def __init__(self, world: dict, features=()):
        self.baseline = deepcopy(world)
        self.fingerprint = baseline_fingerprint(world)
        self.features = {f.id:deepcopy(f) for f in features}
        if len(self.features)!=len(list(features)):
            raise ValueError('duplicate feature IDs')
        self._initial_features=deepcopy(self.features)
        self.history:list[Revision]=[]
        self.cursor=0
        self.world=deepcopy(world)
        self.changes=np.zeros_like(world['sea'],dtype=bool)
        self.last_rejected=[]

    def _check_xy(self, geometry):
        h,w=self.world['sea'].shape
        if not all(0<=x<w and 0<=y<h for x,y in geometry):
            raise ValueError('feature geometry falls outside world grid')

    def protected_mask(self):
        h,w=self.world['sea'].shape
        mask=np.zeros((h,w),bool)
        yy,xx=np.ogrid[:h,:w]
        wrap=is_planet(self.world)
        def dx(x):
            # On a planet the map wraps east-west, so a lock near the date line
            # must also cover the cells just across it.
            d=np.abs(xx-x)
            return np.minimum(d,w-d) if wrap else xx-x
        for f in self.features.values():
            if not f.locked: continue
            pts=f.geometry
            for (x,y) in pts:
                mask|=dx(x)**2+(yy-y)**2 <= f.lock_radius**2
            # Protect every segment, not just control points.
            for (ax,ay),(bx,by) in zip(pts,pts[1:]):
                n=max(1,int(np.ceil(np.hypot(bx-ax,by-ay))))
                for t in np.linspace(0,1,n+1):
                    x=ax+t*(bx-ax);y=ay+t*(by-ay)
                    mask|=dx(x)**2+(yy-y)**2 <= f.lock_radius**2
        return mask

    def _apply(self, revision):
        op,a=revision.operation,revision.arguments
        if op=='add':
            f=GeoFeature(**a['feature']);self._check_xy(f.geometry)
            if f.id in self.features:raise ValueError(f'duplicate feature: {f.id}')
            self.features[f.id]=f
        elif op=='update':
            if a['id'] not in self.features:raise KeyError(a['id'])
            f=self.features[a['id']]
            if f.locked and 'geometry' in a['changes']:
                raise ValueError('unlock feature before moving its geometry')
            data=f.as_dict();data.update(a['changes'])
            new=GeoFeature(**data);self._check_xy(new.geometry)
            self.features[f.id]=new
        elif op=='remove':
            if self.features[a['id']].locked:raise ValueError('unlock feature before removal')
            del self.features[a['id']]
        elif op=='sculpt':
            f=self.features[a['id']]
            if f.kind not in ('delta','coastline'):
                raise ValueError('sculpt feature must be a delta or coastline')
            if f.locked:raise ValueError('cannot sculpt locked feature')
            x,y=f.geometry[0]
            result=sculpt_coast(self.world,mouths=[(round(x),round(y))],
                 protected=self.protected_mask(),radius=a['radius'],
                 strength=a['strength'],mode=a['mode'],max_features=1)
            if result.rejected:raise ValueError('; '.join(result.rejected))
            self.world=result.world
            self.changes |= result.changed
        else:raise ValueError(f'unknown edit: {op}')

    def _replay(self, upto):
        self.world=deepcopy(self.baseline)
        self.features=deepcopy(self._initial_features)
        self.changes=np.zeros_like(self.world['sea'],dtype=bool)
        for revision in self.history[:upto]:self._apply(revision)

    def commit(self, operation, **arguments):
        revision=Revision(operation,deepcopy(arguments))
        # Validate on an isolated working copy so a failing edit is atomic.
        old=(self.world,self.features,self.changes)
        self.world=deepcopy(self.world)
        self.features=deepcopy(self.features)
        self.changes=self.changes.copy()
        try:self._apply(revision)
        except Exception:
            self.world,self.features,self.changes=old
            raise
        self.history=self.history[:self.cursor]+[revision]
        self.cursor+=1
        return self

    def add(self, feature):return self.commit('add',feature=feature.as_dict())
    def update(self, feature_id, **changes):return self.commit('update',id=feature_id,changes=changes)
    def remove(self, feature_id):return self.commit('remove',id=feature_id)
    def sculpt(self, feature_id, mode='delta', radius=12, strength=.018):
        return self.commit('sculpt',id=feature_id,mode=mode,radius=radius,strength=strength)

    def undo(self):
        if self.cursor==0:return False
        self.cursor-=1;self._replay(self.cursor);return True
    def redo(self):
        if self.cursor==len(self.history):return False
        self.cursor+=1;self._replay(self.cursor);return True

    def geography_entries(self, manifest_path=None):
        """Markdown for `world-bible/geography.md`, one line per named feature,
        all marked proposed. Features are canon only after the user ratifies
        them; this is the hand-off, not the ratification.

        Planet coordinates are given as latitude/longitude so the entry still
        means something if the map is re-rendered at another resolution.
        """
        h, w = self.world['sea'].shape
        planet = is_planet(self.world)
        lines = ["## Named features *(proposed — not yet confirmed)*", "",
                 f"Terrain fingerprint `{self.fingerprint[:16]}…`"
                 + (f", edits in `{manifest_path}`" if manifest_path else "")
                 + f", {self.cursor} edit(s) applied.", ""]
        for f in sorted(self.features.values(), key=lambda f: (f.kind, f.name)):
            x, y = f.geometry[0]
            if planet:
                lat = 90 - (y + .5) * 180 / h
                lon = (x + .5) * 360 / w - 180
                where = (f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'} "
                         f"{abs(lon):.1f}°{'E' if lon >= 0 else 'W'}")
            else:
                where = f"cell ({x:.0f}, {y:.0f})"
            extra = f", {len(f.geometry)} points" if len(f.geometry) > 1 else ""
            lock = ", protected" if f.locked else ""
            lines.append(f"- **{f.name}** — {f.kind.replace('_', ' ')} at {where}{extra}{lock} `[{f.id}]`")
        return "\n".join(lines) + "\n"

    def manifest(self):
        return {'schema':'worldsmith-feature-editor/v1',
                'grid':[int(x) for x in self.world['sea'].shape[::-1]],
                'baseline_fingerprint':self.fingerprint,
                'features':[f.as_dict() for f in self._initial_features.values()],
                'history':[r.as_dict() for r in self.history], 'cursor':self.cursor}
    def export_json(self,path):
        with open(path,'w',encoding='utf-8') as f:json.dump(self.manifest(),f,indent=2)
    @classmethod
    def from_json(cls,world,path):
        with open(path,encoding='utf-8') as f:d=json.load(f)
        if d['schema']!='worldsmith-feature-editor/v1':raise ValueError('unsupported manifest schema')
        if d['grid']!=list(world['sea'].shape[::-1]):raise ValueError('world grid mismatch')
        if d.get('baseline_fingerprint') != baseline_fingerprint(world):
            raise ValueError('baseline fingerprint mismatch; refusing to replay edits on another world')
        editor=cls(world,[GeoFeature(**f) for f in d['features']])
        for r in d['history']:editor.commit(r['operation'],**r['arguments'])
        while editor.cursor>d['cursor']:editor.undo()
        return editor
