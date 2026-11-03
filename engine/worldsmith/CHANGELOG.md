## Phase 2B — Coastal morphology
Added `coastal_morphology.py`: estuary/delta-prone classification, sedimentary wetland/marine plume visual masks, renderer integration, and four regression tests. Non-destructive visual interpretation only.

# Worldsmith changelog

## 2.0.3 — 2026-10-27 — Atlas Studio for Universal Realms

Engine output is unchanged from 2.0.2.

### Atlas Studio rebuilt (`editor/index.html`)
- **Design.** Rebuilt in the Universal Realms design language, using Chronicle Map's tokens (parchment, seal red, gilt, lapis accent) and type (Cinzel, EB Garamond, IM Fell English SC, JetBrains Mono). It adds Chronicle Map's ＋ / － / ⌂ controls and ZOOM readout, its parchment ledger panel, and the site nav shell. On the site, `/js/ur-nav.js` replaces the fallback nav and adds sign-in.
- **Correct proportions.** The map is drawn in grid units, so the image and features always share the world's aspect ratio; the old page stretched maps into a fixed 960×580 frame. Adds pan, scroll-zoom and pinch-zoom.
- **Phones.** The map comes first at the world's own proportions, with a horizontal tool row. Tap places points, and starting a drawing scrolls the map back into view. The page never scrolls sideways.
- **Safe import.** Every field of every feature and every history edit is validated before anything changes. Bad files are refused with a specific reason and leave the current world intact. Only allow-listed fields can be changed, closing a `__proto__` path; map images must be embedded data. `?bundle=` opens same-site files only.
- **Terrain edits from the browser.** You can queue a delta or inlet on a delta or coastline feature. Worldforge carries it out with real drainage and climate when the edits are replayed. Protected features cannot be moved, deleted or sculpted, and their protected ground is drawn on the map with the same shape as Python's lock mask.
- **Hand-off.** "Export edits" writes a v1 manifest that `WorldEditor.from_json` and `wf_adapter.py --edits` replay. "Copy for geography.md" produces byte-for-byte the same proposed lines as `WorldEditor.geography_entries()`.
- **Autosave.** Unsaved edits are kept per world in the browser and restored only when they continue the opened file's history.

### Added
- `world_io.atlas_bundle()`: writes one file Atlas Studio opens directly. It is a v1 manifest plus the map image drawn at exact grid proportions, the projection, and the generator parameters.
- `world_io.regenerate()`: rebuilds the world a bundle names.
- `editor/atlas_studio.template.html`, `editor/build_atlas_studio.py` and `editor/README.md`. The sample world is seed 606 at 512×256.
- `tests/test_atlas_studio.py` (21 tests) runs the page's own script in Node:
  - the site wiring and design tokens;
  - 13 kinds of bad file;
  - id rules matching Python;
  - geography.md parity on a planet and a flat map, including rounding ties;
  - a browser-made manifest with a new river, a rename and a queued delta, replayed in Python (the delta builds real land) and through the Saga adapter.

Suite: 105 passed, 1 skipped.

### Site integration (separate patch for the Universal Realms repo)
- Adds `public/atlas_studio.html`.
- In `public/js/ur-nav.js`, "Maps" becomes a dropdown with Chronicle Map and Atlas Studio, and every nav dropdown is now wired the same way (opening one closes the others; `aria-expanded` is set).


## 2.0.2 — 2026-10-27 — worldbuilding connected to the 2.0 map tools

Generation and rendering output is unchanged from 2.0.1: planets bit-identical, flat renders pixel-identical. Ordinary briefs parse to the same parameters (checked on the seed-606 brief and others).

### Fixed
1. **Terrain edits never reached history.** `wf_adapter.py` always regenerated the planet from the seed, so sculpted coasts, named-feature edits and any setting not in the brief vanished from peoples and history. New `--world FILE` reads a saved world. New `--edits MANIFEST` replays an edit manifest onto the seed's planet; its terrain fingerprint refuses any other world. The adapter reports `terrain` (seed / saved world / + edits) and any brief words it could not apply to saved terrain. `saga_world.json` records the terrain source and fingerprint.
2. **Placeholder names on lore worlds.** `map_render` with no labels stamps demo names (WESTERLAND, THE GREY SEA). Its metadata now reports `placeholder_labels`, and the instructions require the bible's names, or `labels=[]`, whenever a bible exists.
3. **Keyword parsing matched substrings.** "demilitarised" also matched "militarised", "pre-industrial" matched "industrial", "swarm" matched "warm" and "islanders" matched "island". The right value won only by dictionary order. `brief.parse` and `civilization.params_from_prompt` now match whole words, longest first, and report each keyword once. `legacy_matching=True` reproduces the old parse exactly for worlds made from a brief before this release. Reports say which matching was used.
4. **Adapter factions lacked `grievances`, `allies` and `claims`**, so a bible overwrite had to create them. They are now written empty.

### Added
- `scripts/worldforge/world_io.py`: `save_world` / `load_world` for planets and flat maps. Plain `.npz`, no pickles, with parameters, terrain fingerprint and edit provenance. Load verifies the fingerprint and rejects damaged or altered files.
- `WorldEditor.geography_entries()`: named features as proposed lines for `geography.md`, using lat/lon on planets and cells on flat maps, with the edit manifest and fingerprint. This is the hand-off to the bible; the user ratifies.
- Instructions:
  - **SKILL.md:** routing rows for styled maps, feature editing, and history on edited maps. The "One seed, one planet" rule now covers edited worlds, plus a new "Map names come from the bible" rule. Removed the stale Phase 2D line that called the editor non-graphical.
  - **worldbuilder.md:** an edited map is canon as seed **plus** edit manifest, saved to `maps/world.npz`.
  - **worldforge.md and saga.md:** the same hand-offs.
- `tests/test_worldbuilding_bridge.py` (21 tests): save/load and tamper rejection; the adapter on seed, `--edits` and `--world`; wrong-world refusal; the full chain from bible names through simulation, `to_bible` and era maps on an edited planet; ratification output; the placeholder flag; whole-word parsing and legacy reproduction. Suite: 84 passed, 1 skipped.


## 2.0.1 — 2026-10-27 — planet support for the 2.0 tools, portability, engine tests

Generation output is unchanged: planets and flat maps are bit-identical to 2.0, and default worlds still match the original skill (seed 1174 included).

### Fixed
1. **Coastal sculpting crashed on planets** (`coastal_sculpt.py`). It recomputed climate with flat-map functions (`'SphereParams' object has no attribute 'wind_from_west'`). Planet worlds now recompute with the planet's own physics through the new `spherical.derive_surface`: wrapped drainage, three-cell moisture, humidity, 17-class biomes and rain-weighted rivers. The sea level is held fixed so edits are not undone. Edit windows wrap across the date line.
2. **Named feature editing crashed on planets** (`feature_editor.py`), through the same path. Lock zones now also wrap across the date line, so a protected feature near it is protected on both sides.
3. **`map_render` crashed on planets** (`map_render.py`). Its colour table had 13 biome classes; planets have 17. It now uses the 17-class table, whose first 13 entries match the flat table exactly, so flat renders are unchanged. Unknown biome ids raise a clear error. Planet colour blending wraps east-west.
4. **Planet scale bars now say "scale true at equator"** (`map_render.py`). At scale 1 the distance label, which fell off the canvas on every map, now moves beside the bar. Scales 2 and 3 are pixel-identical to 2.0.
5. **Hard-coded sandbox paths removed.** `spherical.py` and `brief.py` imported siblings from `/home/claude/worldforge/scripts`; they now resolve relative to their own file. Demos 2A–2D wrote to `/mnt/data`; all five demos now take `--out` and default to the current directory.

### Added
- `spherical.derive_surface(elev, params, sea_level)`: the planet climate step, reusable by anything that edits terrain. Calling it on unchanged terrain reproduces generation bit for bit. Also `spherical.is_planet(world)`.
- `tests/test_planet_engine.py` (24 tests): planet generation and determinism, legacy golden hashes from the original skill, each of the seven seed-606 fixes, the civilization layer, and every 2.0 tool on a planet (coastal detection, sculpting, date-line wrap, feature locks, manifest replay, all three render styles, SVG).
- `tests/test_saga.py` (6 tests): determinism, no input mutation, event causality and snapshots, and the secret-exposure fix.
- Suite: 63 passed, 1 skipped (optional CairoSVG). Against the unfixed 2.0 upload the new tests fail 10; against the original skill every fix test fails, which is the point.

### Notes
- If a numpy or scipy upgrade makes `test_default_worlds_match_original_skill` fail, the dependency changed the world. Pin versions; do not update the hash.


## 2026-10-27 — fixes found building seed 606

Worlds made with `humidity=1.0` and `plate_warp=0` (the defaults) generate the same land and biomes as before. Seed 1174 was checked and is unchanged.

### Worldforge
1. **`humidity` was a no-op** (`spherical.py`). `refine_moisture` rescales to its own land median, which erased any global wetness change, so "arid" worlds still came out 21–34% rainforest. Humidity is now applied as a level after normalising.
2. **Rivers ignored rainfall** (`worldforge_core.flow_accumulation`, `spherical.py`, `cartography.graded_rivers`). Accumulation counted drainage area only, so deserts had as many rivers as jungles. `flow_accumulation` takes optional per-cell weights; worlds now carry `discharge` (rain-weighted), rivers are cut from it, and the renderer prefers it. `accumulation` stays unweighted for erosion. River routing is unchanged, but temperate worlds lose about 30% of their river cells as rivers concentrate where rain falls.
3. **Coastlines traced Voronoi plate edges** (`spherical.plates_sphere`). New `SphereParams.plate_warp` (default 0) warps the plate lookup through the generator's existing warp field. It draws no RNG; 0.3–0.5 gives organic coasts.
4. **Scale-bar label** (`cartography.scale_bar`) is centred by measured text width instead of a fixed offset.

### Civilization layer
5. **Population read drainage area, not water** (`civilization.build`). It now uses `discharge` when the world has it.
6. **High-latitude regions grew as north-south strips** (`civilization._dijkstra_regions`, `_seed_points`). Steps and seed spacing now use true distance (east-west scaled by cos latitude) when the world has `lat`.

### Saga
7. **Secrets surfaced almost immediately** (`saga_sim.maybe_secrets`). Exposure odds added 5% per grievance regardless of size, so a faction with many trivial grudges exposed its secret within a turn or two. Odds now scale with total grievance, capped at +8%.

### Not changed, worth knowing
- At 25-year turns most rulers die every turn. That is realistic, but successions dominate the timeline; filter by importance when reading.
- `wf_adapter.py` regenerates the planet at its own resolution with stock settings. For a world built with non-default settings (for example `plate_warp`), write `saga_world.json` from your own civilization data instead, or the history runs on a different planet.

## 2026-10-27 — Worldforge Cartographer Update (Phase 1 / alpha)

- Added `scripts/worldforge/map_render.py` as a shared renderer for three
  demonstrably different styles (`illustrated`, `atlas`, `medieval`) over one
  immutable world result. Separate style RNGs avoid disturbing generation.
- Added deterministic forest and mountain glyph placement, shoreline ink
  ripples, watercolor-like atlas biome tint, map furniture and optional
  accurate scale bar (only when km per map cell is supplied).
- Added `scripts/worldforge/label_engine.py`: priority-order text placement,
  collision rejection, manual locked anchors, text halos, placement metadata.
  Curved labels and geographic-mask-aware placement remain future work.
- Fixed vector SVG river and isoline polylines being incorrectly closed with
  `Z`; removed an environment-specific Python import path; XML-escaped SVG
  titles/attributes and sanitized embedded manifest data.
- Added regression tests for renderer immutability/repeatability, label
  collisions and XML-safe vector exports.
- Added a reproducible three-style sample gallery and manifest CLI.

## Worldsmith 2.0 Phase 1B — Cartographer quality pass (2026-10-27)

- **Shared vector artwork** (`map_scene.py`): hand-specified mountain ridge and rock-hatching strokes, conifer and deciduous crowns, forest cluster placement, stable per-glyph identities, coastline/river/page-margin clearance. The identical strokes feed Pillow and SVG.
- **Label placement** (`label_engine.py`): curved per-glyph text following supplied geographic paths, priority-aware collision handling, land/sea surface checks, SVG and PNG glyph poses in a shared coordinate system; locked authored anchors stay locked.
- **Geographic naming helpers** (`feature_labels.py`): suggest readable paths from actual river polylines for an explicitly supplied *demo or authored name*. No names are silently applied to canon and no hydrology is altered.
- **Hybrid SVG** (`map_render.py`): exact raster terrain embedded once with genuine editable vector symbol strokes and vector map labels above it. This is not a fully vector DEM/contour export; the longstanding `vector.py` remains the standalone geometry exporter.
- **Aesthetic pass:** lighter illustrated contours; no chopped trees/mountains under labels; ocean ornaments kept clear of the frame.
- **Regression:** 11 tests cover stable symbols, full-glyph clearing, curved labels, land-water placement, XML safety, style consistency, and PNG/SVG raster comparison.
- **Compatibility:** `render_map` and its Phase 1 options remain available; optional `path_labels`, `render_svg`, and CLI `--svg` are additive.

## 2.0 Phase 2A — Coastal waterways initial implementation
- Added `scripts/worldforge/coastal_waterways.py` with reproducible river-mouth detection, local estuary tinting, and optional candidate distributary paths.
- Integrated overlay into all three `map_render.py` styles while preserving baseline elevation and drainage fields.
- Added `tests/test_coastal_waterways.py`, `scripts/worldforge/demo_phase2a.py`, and `PHASE2A_RELEASE.md`.
- Important: proposed branches are decorative approximations, **not** a physical delta model.

## Worldsmith 2.0 Phase 2C — Coastal Sculpting
- Introduced opt-in `coastal_sculpt.sculpt_coast`: edits real elevation/coastline data, supports locked cells, and recomputes derived geographic data.
- Added protected-area and deterministic-edit tests and visual preview.
- Explicitly distinguishes conservative morphology approximation from sediment transport.
