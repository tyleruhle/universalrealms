"""
brief.py — one entry point from a plain-language brief to a whole world.

The civilization filters alone are half a world. A user who asks for "a drowned
world of scattered island kingdoms, devout and insular" is specifying the
PHYSICAL world as much as the human one, and a parser that only reads the human
half silently discards the first eight words. That was a real measured failure:
of four test briefs, every terrain and climate term matched nothing.

    sp_params, civ_params, report = brief.parse("scorched desert world, one
                                                 brutal empire, militarized")

`report` lists exactly which words were matched and which physical knobs moved.
Show it to the user. A silent miss is discovered three layers downstream.
"""

from __future__ import annotations

import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling modules, wherever installed
import civilization as civ
import spherical as sp

# Physical vocabulary. Each entry sets SphereParams fields directly.
TERRAIN = {
    # --- how much land -------------------------------------------------
    # Land fraction alone only moves sea level, which drowns a continent into a
    # continent with a coastline further in. To actually get scattered land you
    # have to break the structure up: more plates and a higher base frequency.
    "drowned": dict(land_fraction=0.12, plate_count=30, base_frequency=3.6),
    "ocean world": dict(land_fraction=0.08, plate_count=34, base_frequency=4.0),
    "archipelago": dict(land_fraction=0.15, plate_count=34, base_frequency=4.4),
    "island": dict(land_fraction=0.16, plate_count=30, base_frequency=4.0),
    "islands": dict(land_fraction=0.16, plate_count=30, base_frequency=4.0), 
    "continental": dict(land_fraction=0.45), "supercontinent": dict(land_fraction=0.55),
    "pangaea": dict(land_fraction=0.55),
    # --- temperature ---------------------------------------------------
    "frozen": dict(temp_offset=-0.30), "ice age": dict(temp_offset=-0.26),
    "glacial": dict(temp_offset=-0.28), "cold": dict(temp_offset=-0.15),
    "temperate": dict(temp_offset=0.0), "warm": dict(temp_offset=0.12),
    "tropical": dict(temp_offset=0.20), "hothouse": dict(temp_offset=0.28),
    "scorched": dict(temp_offset=0.25), "burning": dict(temp_offset=0.25),
    # --- humidity ------------------------------------------------------
    "desert": dict(humidity=0.40), "arid": dict(humidity=0.45),
    "parched": dict(humidity=0.35), "dry": dict(humidity=0.6),
    "lush": dict(humidity=1.6), "verdant": dict(humidity=1.6),
    "jungle": dict(humidity=1.7), "rainforest": dict(humidity=1.7),
    "swamp": dict(humidity=1.7), "monsoon": dict(humidity=1.5),
    # --- relief --------------------------------------------------------
    "mountainous": dict(tectonic_strength=0.85, ridge_width=0.09),
    "alpine": dict(tectonic_strength=0.85), "rugged": dict(tectonic_strength=0.75),
    "flat": dict(tectonic_strength=0.25), "plains": dict(tectonic_strength=0.28),
    "eroded": dict(erosion_passes=4, tectonic_strength=0.3),
    "young": dict(erosion_passes=1, tectonic_strength=0.75),
}

# Physical words that should also nudge a civilization filter, because the
# terrain implies something about how people live on it.
IMPLIES_CIV = {
    "archipelago": dict(sea_affinity=0.9, political_fragmentation=0.75),
    "island": dict(sea_affinity=0.9, political_fragmentation=0.7),
    "islands": dict(sea_affinity=0.9, political_fragmentation=0.7),
    "drowned": dict(sea_affinity=0.9, political_fragmentation=0.7),
    "scattered": dict(political_fragmentation=0.75),
    "mountainous": dict(cultural_diversity=0.8, political_fragmentation=0.7),
    "desert": dict(economic_development=0.35, urbanization=0.7),
    "supercontinent": dict(sea_affinity=0.3),
    "kingdoms": dict(political_fragmentation=0.7),
    "kingdom": dict(political_fragmentation=0.35),
    "clans": dict(political_fragmentation=0.85, cultural_diversity=0.8),
    "tribes": dict(political_fragmentation=0.85, cultural_diversity=0.85),
}


def parse(text, seed=0, nlat=1024, legacy_matching=False):
    """Brief to (SphereParams, CivParams, report).

    Keywords match as whole words, longest first (see
    civilization.match_keywords). Pass legacy_matching=True to reproduce a
    world generated from a brief before 2.0.2; the report says which was used.
    """
    t = text.lower()
    terrain_kw, civ_kw, matched = {}, {}, []

    # Longest keyword first, and never overwrite a field already set. Without
    # this, "kingdom" matches inside "kingdoms" and whichever the dict happens
    # to reach last decides the answer.
    terrain_hits = civ.match_keywords(text, list(TERRAIN), legacy_matching)
    for word in sorted(TERRAIN, key=len, reverse=True):
        if word in terrain_hits:
            for k, v in TERRAIN[word].items():
                terrain_kw.setdefault(k, v)
            matched.append(word)
    civ_hits = civ.match_keywords(text, list(IMPLIES_CIV), legacy_matching)
    for word in sorted(IMPLIES_CIV, key=len, reverse=True):
        if word in civ_hits:
            for k, v in IMPLIES_CIV[word].items():
                civ_kw.setdefault(k, v)
            if word not in matched:
                matched.append(word)

    cp = civ.params_from_prompt(text, seed=seed, legacy_matching=legacy_matching)
    # explicit civilization words beat terrain implications
    for k, v in civ_kw.items():
        if k not in cp.notes.get("matched_fields", []):
            setattr(cp, k, v)
    cp2 = civ.params_from_prompt(text, seed=seed, legacy_matching=legacy_matching)
    for f in vars(cp2):
        if f in ("seed", "notes"):
            continue
        if f in civ_kw and getattr(cp2, f) == getattr(civ.CivParams(), f):
            setattr(cp2, f, civ_kw[f])
    cp2.notes["matched"] = sorted(set(cp2.notes["matched"]) | set(matched))

    spp = sp.SphereParams(seed=seed, nlat=nlat, **terrain_kw)
    report = {
        "prompt": text,
        "matching": "legacy substring" if legacy_matching else "whole word",
        "matched": cp2.notes["matched"],
        "unmatched_hint": [w for w in t.replace(",", " ").split()
                           if len(w) > 4 and w not in " ".join(cp2.notes["matched"])],
        "physical": {k: v for k, v in terrain_kw.items()},
        "civil": {f: round(getattr(cp2, f), 2) for f in
                  ("political_fragmentation", "cultural_diversity", "religiosity",
                   "militarization", "economic_development", "sea_affinity")},
    }
    return spp, cp2, report
