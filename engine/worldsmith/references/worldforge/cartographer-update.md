# Worldsmith 2.0 Cartographer Update — Phase 1B

Incremental graphics improvements only: geography, flow, erosion, biomes, world
seed and historical simulation are unchanged. This is a renderer release, not a
world model migration.

## CLI and files

From the skill root:

```bash
python scripts/worldforge/map_render.py --seed 28 --width 480 --height 320 \
  --scale 3 --out preview/worldsmith --title 'THE KNOWN WORLD' --svg
```

Generates three PNG maps, three hybrid SVG maps, and one JSON manifest. All
three styles consume the same arrays and share one terrain SHA-256 fingerprint.
`--svg` is opt-in because the hybrid SVGs contain embedded PNG base maps and
may be larger than standalone PNGs.

## Use geographic text paths

```python
from worldforge_core import WorldParams, generate
from label_engine import MapLabel
from map_render import render_map, render_svg
from feature_labels import suggest_river_label

world = generate(WorldParams(seed=28, width=480, height=320))
# MapLabel paths use MAP PANEL pixel coordinates, without the title header.
river_label = suggest_river_label(world, 'RIVER ALDEN', scale=3)
labels = [MapLabel('MY KINGDOM', 660, 490,
                   kind='region', priority=90, locked=True)]
path_labels = [river_label] if river_label else []
image, info = render_map(world, 'illustrated', scale=3,
                         labels=labels, path_labels=path_labels,
                         return_metadata=True)
image.save('atlas.png')
with open('atlas.svg','w',encoding='utf-8') as out:
    out.write(render_svg(world, 'illustrated', scale=3,
                         labels=labels, path_labels=path_labels))
```

`MapLabel(..., path=((x1,y1), (x2,y2), ...))` can be authored for any real
feature. The label engine measures glyph advances and computes a tangent angle
for each letter. It rejects paths that are too short, too steep, or collide
with higher-priority labels; positions are deterministic. `terrain='land'` or
`'sea'` restricts placement to that surface. Automatic `suggest_river_label`
chooses a readable candidate stream; it does NOT identify a canonical stream
by name. For real map canon, select the known feature manually.

## Rendering details

- `map_scene.py` is the shared vector stroke scene. Mountain ridges use
  multi-peak silhouettes and rock-face hatching; forests use clustered oak
  and pine glyphs. Placement respects major coastlines, hydrology and the map
  furniture margin; all stroke groups are deterministic from seed.
- Symbol groups have stable per-render identities. Label knockout removes the
  whole tree or mountain glyph so details never appear orphaned.
- PNG and hybrid SVG reuse identical scene geometry and glyph layout. SVG has a
  raster base (relief, coast, water coloring, ornament, frame, furniture) and
  vector symbol/label overlays. Slight rasterization/font variation is normal.
- `vector.py` still exports actual coastlines, regions, and watercourses as
  geometric vector paths. Hybrid atlas SVG and true data-vector SVG are different
  output modes and should not be described as equivalent.
- The sample names, such as WESTERLAND and THE ALDEN, are **demo placeholders**;
  they are never written back to lore/canon.

## Verification

```bash
python -m unittest discover -s tests -v
```

Eleven deterministic tests cover seeds, style modes, terrain immutability,
collision ordering, water/land label masks, curved labels, complete-glyph
clearing, XML correctness and the PNG/SVG raster difference.

## Honest remaining gaps

- No fully vectorized terrain surface; hybrid SVG embeds raster geography.
- No multi-scale symbol density/zoom LOD or true geographic feature locking.
- Symbols are reusable authored geometry, but no large external illustration
  library or hand-placed designer assets are included.
- Need better automatic feature identification, label fitting inside irregular
  territorial polygons, and river text baselines on sharply twisting streams.
- Procedural world generation still has known morphological limits, especially
  realistic deltas, estuaries and distinctive mountain types (Phase 2).
