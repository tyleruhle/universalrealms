
# Worldforge

A skill for building map generators: the math that makes terrain physically
plausible, the architecture that keeps it fast, and the styling layer that turns
arrays into something worth looking at.

This is an engineering skill, not a prose skill. The output is running code, a
pipeline design, or a specific fix. Diagnose before generating, and prefer a
small correct core the user can extend over a large scaffold they have to trust.

## The one architectural rule

**Simulation and style are separate layers, and they never mix.**

The generator produces a data layer: elevation, water mask, flow accumulation,
rainfall, temperature, biome ID, political ownership, points of interest. Every
one of those is a plain array or a plain record. Nothing in the data layer knows
what color anything is.

The style layer is a renderer that consumes that data and emits pixels, vectors,
or tiles. Parchment, hex overlay, neon holographic, satellite relief, and Risk
board are five renderers over one dataset.

This matters for a practical reason. When a user asks for "the same world but as
an old map," the correct answer is a second render function against the cached
arrays, not a second generation run. If the code cannot do that, the architecture
is wrong and should be fixed before adding features. Confirm this split exists in
any code being extended; if the user's existing generator bakes colors into the
noise loop, say so directly and propose the separation as step one.

## The context interview

Do not start generating until the four axes below are pinned. If the user's
request already answers an axis, do not ask again. If two or three are open, ask
them together as one round of tappable options rather than an interrogation.
The cost of guessing here is high, because the target medium changes the
algorithm, not just the output format.

1. **Style and vibe.** Which renderer, or which hybrid. Ancient, adventure/RPG,
   sci-fi, political, hyper-realistic, or a blend. This decides how much
   simulation fidelity is actually visible and therefore worth computing.
2. **Technical target.** Throwaway script, reusable library, desktop app, web
   app, game engine plugin. This picks the language lane before any code exists.
3. **Output medium.** Static raster, interactive vector, JSON data matrix, tile
   atlas, 3D heightmesh, or a live-regenerating UI. Vector output in particular
   changes the pipeline early, because contour extraction wants a different
   smoothing strategy than raster shading does.
4. **Intent.** TTRPG table use, game procedural generation, novel worldbuilding,
   simulation, or art. Intent sets the tolerance for randomness: a novel needs
   one hand-tuned map, a roguelike needs ten thousand acceptable ones, and those
   are different problems.

**Skip any axis the request already answered, and say nothing about it.** "A
hex overworld for my TTRPG group" has answered style, target, and intent; asking
them back is friction, not diligence. Ask only what is genuinely open.

Two follow-ups are worth asking almost every time, because they silently
determine the whole design: **what scale is one pixel** (continent, region, or
dungeon), and **does the same seed have to produce the same map forever** (which
forbids anything nondeterministic anywhere in the chain, including set iteration
order and unsorted parallel reduction).

The scale question is mandatory, not optional, for any tile or hex request. The
simulation grid has to be downsampled to the play grid, and the two rules that
decide whether the result is usable — majority vote for classified layers, and
rivers rasterized onto tile *edges* rather than sampled at tile centres — both
depend on knowing the target cell size before anything is generated.

## The execution loop

Run these four steps internally before emitting code. State the outcome of steps
1 and 3 briefly to the user; do not narrate all four.

**1. Algorithmic blueprinting.** Name the specific algorithm for each stage and
why it beats the alternative here. "fBm plus domain warp for the base field,
Voronoi plate seams for orogeny, priority-flood plus D8 for drainage" is a
blueprint. "Perlin noise" is not. If a stage has no algorithm, that stage will
produce artifacts later.

**2. Data lifecycle.** Trace the flow: seed to RNG state to raw noise to
elevation to filled surface to flow accumulation to moisture to temperature to
biome to render. Confirm each stage only reads from stages upstream of it. Cyclic
dependencies (biome affecting erosion affecting biome) need explicit iteration
counts, not hidden feedback.

**3. Optimization and scalability check.** Estimate the cost at the user's target
resolution before writing the loop. Anything per-pixel in a Python `for` loop is
a bug unless it is inherently sequential (priority flood, flow accumulation,
column-wise moisture advection are the three legitimate exceptions in the
reference implementation). Flag the crossover point where their target size stops
being interactive.

**4. Aesthetic integration.** Apply the style layer as a transform over the
finished data. Hillshade, palette LUT, texture grain, glyph placement, label
typesetting, overlays. This is also where "hand-crafted feel" gets injected, and
it is cheaper here than in the simulation.

## Blind spot audit

Before delivering, check the work against `references/worldforge/blind-spots.md`. The
recurring failures worth memorizing:

- Rivers that split going downhill, or that terminate in a plain. Both mean
  drainage was computed without depression filling.
- Deserts on the windward side of a range. Moisture was applied as noise instead
  of advected.
- Continents shaped like the Voronoi cells that generated them, or like the
  square of the array. Both are unblurred structural fields leaking through.
- Mountains as blobs instead of ranges. Orogeny is linear because plate seams are
  linear; range structure has to come from a linear source.
- Perfect randomness reading as sterile. Real maps have a few dominant features
  and a long tail; pure noise has no hierarchy.
- Seeds that drift between runs because of `set` ordering, dict iteration, thread
  scheduling, or an unseeded global RNG.
- A world silently replaced by a "quality" change. Raising the octave count or
  adding any drawing stage shifts the RNG sequence and produces a different
  world at the same seed. Measured: IoU 0.229. Detail comes from resolution, not
  from more octaves.
- Global statistics computed from a flat square array as though it were a globe.
- A style constraint quietly breaking physics: an "ancient map" is a rendering
  choice, and it does not license rivers that flow uphill. Stylize the depiction,
  never the underlying model.

## Cartographer Update: PNG and hybrid SVG rendering

For a quick, three-style map preview from **one unchanged world**, use
`scripts/worldforge/map_render.py` and read
`references/worldforge/cartographer-update.md`. Use `label_engine.py` for authored and curved labels, `feature_labels.py`
for proposed river baselines, and `map_scene.py` for reusable vector glyphs.
Hybrid SVG embeds raster terrain and preserves native vector symbols and text.

All of these accept planets as well as flat maps. When a world bible exists,
labels come from it (or pass `labels=[]`): the default demo names are
placeholders, flagged as `placeholder_labels` in the render metadata. After any
terrain edit (`coastal_sculpt`, `feature_editor`, Atlas Studio), save the
finished world with `world_io.save_world(world, "world-bible/maps/world.npz",
edits=...)` and hand that file to later stages; see the "One seed, one planet"
rule in SKILL.md.

## Reference files

Read the relevant file when the task touches it. Do not preload everything.

| File | Read when |
|---|---|
| `references/worldforge/geophysics.md` | Any terrain realism question: noise, tectonics, erosion, hydrology, climate, biomes. Start here for realistic maps. |
| `references/worldforge/blind-spots.md` | Before delivering, and when debugging a map that "looks wrong" but the user cannot say why. |
| `references/worldforge/style-ancient.md` | Parchment, medieval, hand-drawn, nautical, sepia. |
| `references/worldforge/style-adventure.md` | RPG overworld, tilemaps, zones, fog of war, POI placement. |
| `references/worldforge/style-scifi.md` | Planetary, galactic, hex overlays, orbits, holographic UI, resource heatmaps. |
| `references/worldforge/style-political.md` | Territory growth, borders, capitals, faction color, historical shifting. |
| `references/worldforge/style-realistic.md` | Satellite look, hypsometric tints, relief shading, cartographic accuracy. |
| `references/worldforge/vector-and-interactive.md` | Vector extraction, SVG and GeoJSON export, and self-contained interactive maps with clickable regions and zoom. Read for any "make it clickable / exportable / zoomable" request. |
| `references/worldforge/civilization-layers.md` | Generating cultures, polities, religion, military posture and development from user filters, when worldbuilder is not driving. |
| `references/worldforge/cartographic-detail.md` | Raising resolution safely, the detail stack, labels, legends, the layer budget, and the flat-ground tie-breaking family of artifacts. |
| `references/worldforge/geophysics.md` (section 8) | Stage ordering: which stage may read which, and why the pipeline runs in that order. Read before reordering or adding a generation stage. |
| `references/worldforge/stack-python.md` | Default lane. NumPy/SciPy, Pillow, Streamlit, Pygame. |
| `references/worldforge/stack-web.md` | Browser target. Canvas, WebGL, Three.js, worker threads. |
| `references/worldforge/stack-engine.md` | Unity or Godot. Tilemaps, meshes, chunked streaming. |
| `references/worldforge/living-world.md` | Simulating time, extensibility hooks, terrain-bound lore generation. For political history over time, hand off to saga (`modules/saga.md`). |

## The reference implementation

`scripts/worldforge/worldforge_core.py` is a working, dependency-light pipeline: fBm with
domain warp, Voronoi plate tectonics with drift-based convergence, thermal and
stream-power erosion, priority-flood depression filling, D8 flow accumulation,
column-swept orographic rainfall, latitude and lapse-rate temperature,
Whittaker biome classification, and two renderers over the same arrays
(satellite relief and parchment) to demonstrate the layer split.

```bash
python scripts/worldforge/worldforge_core.py --seed 42 --size 512 --out world
```

Roughly 4 seconds at 512x512 on a normal machine. Use it three ways:

- **As a starting point.** Copy it, keep `generate()`, replace the renderer.
- **As a correctness reference.** When a user's own generator has broken rivers
  or implausible climate, compare their stage against the corresponding function
  here rather than rewriting their code wholesale.
- **As a teaching artifact.** Each function's docstring states what breaks
  without that stage, which is usually the fastest way to explain why a map
  looks wrong.

`scripts/worldforge/cartography.py` is the companion style layer: base surface, elevation
and bathymetric contours, categorical hatch and tint, two-weight region lines,
province clipping, discharge-graded rivers, flat-shaded lakes, relief glyphs
with the prominence test, dashed routes, haloed labels, seat markers, legend,
scale bar, compass, frame. It consumes finished arrays and generates nothing, so
it works on any world including one imported from elsewhere.

```python
rgb = ct.base_surface(world); rgb = ct.contours(rgb, world)
rgb = ct.graded_rivers(rgb, world); img = ct.upscale(rgb, 2)
ct.relief_glyphs(img, world, scale=2)
```

`scripts/worldforge/spherical.py` handles whole-planet work: 3D value noise sampled on the
sphere so longitude wrap is exact by construction, plates as points on the
sphere with tangential drift, hydrology on a longitude-padded grid, three-cell
circulation for moisture, area-weighted statistics, and both equirectangular and
orthographic-globe renderers. Use it whenever the deliverable is a *planet*
rather than a region: a flat square cannot wrap and its statistics are wrong.

```python
import spherical as sp
w = sp.generate_sphere(sp.SphereParams(seed=7, nlat=640))
sp.render_equirectangular(w).save("eq.png")
sp.render_globe(w, lon_0=90).save("globe.png")
```

`scripts/worldforge/biomes.py` holds the moisture refinement and biome classifier: coastal
humidity, evapotranspiration recycling, lateral diffusion, median-normalised
moisture, a 5x4 Whittaker matrix with noise-jittered thresholds, temperature-based
snowline, and azonal wetland and beach classes. Use it instead of
`worldforge_core.classify_biomes` whenever biome plausibility matters.

`scripts/worldforge/brief.py` turns one plain-language brief into both physical and human
parameters and reports what it matched. It is the entry point when the user
describes a world in prose rather than answering an interview.

`scripts/worldforge/civilization.py` generates the human layer from six user filters
(political fragmentation, cultural diversity, religiosity, militarization,
economic development, biome pressure) plus trade, urbanization and sea affinity.
Everything derives from one movement-cost surface, so the human world moves when
the terrain does. `params_from_prompt()` maps a plain-language brief onto the
filters and reports what it matched; always show the user that list.

**Ask for the filters when worldbuilder is not driving.** A populated world with
unasked-for politics is worse than bare terrain. When worldbuilder IS driving, it
owns culture and religion and this module supplies only the spatial scaffolding.

## Resolution guidance

Raising resolution is safe as long as the RNG draw sequence is untouched. Never
change the octave count to add detail. Verified on the spherical generator: same
seed at nlat 640 and 1536, land IoU 0.989.

| grid | cells | generation | note |
|---|---|---|---|
| 640 x 1280 | 0.8M | ~16s | fast iteration, coarse coastlines |
| 1024 x 2048 | 2.1M | ~40s | good default for a finished planet |
| 1536 x 3072 | 4.7M | ~90s, 1.4GB peak | detailed; rivers 4,592 vs 1,818 at 640 |

Cost is roughly linear in cell count and memory peaks near 1.5GB at 4.7M cells,
so treat 2048 x 4096 as the practical ceiling in this environment.

`scripts/worldforge/vector.py` converts raster layers into attributed polygons and
polylines, then exports SVG, GeoJSON, or a self-contained interactive HTML map
with clickable regions, wheel zoom, drag pan and a live scale bar. Reach for it
whenever the user wants to click, export, or zoom: those three requests share
one prerequisite, which is geometry with identity rather than coloured cells.

For simulated political history on any of these worlds, saga's
`scripts/saga/wf_adapter.py` runs `brief.py`, `spherical.py` (or
`worldforge_core.py` with `--flat`) and `civilization.py`, then writes a
region graph with land borders and sea lanes scaled by `sea_affinity`.

All seven are intentionally not a framework. No plugin system, no config files, no
abstraction over the array. Add those only when the user's scope demands them.

## When asked to make a map bigger or more detailed

Two separate requests hide in this one. Establish which before touching
anything: **more data** (regenerate at higher resolution) or **more drawn**
(add layers to the render). Usually both are wanted, and the second is free.

If regenerating, the non-negotiable rule is that the RNG draw sequence must not
change, or the same seed yields a different world. Do not add octaves. Verify
with an IoU check against the previous land mask and report the number. Expect
rivers, lakes, and settlement sites to increase legitimately as finer structure
resolves, and expect every previously published statistic derived from the old
grid to need rechecking.

Full procedure, failure cases, and the layer budget: `references/worldforge/cartographic-detail.md`.

## Growth horizons

These are architecture hooks, not features to build unprompted. Raise them when
the user's direction implies one, and see `references/worldforge/living-world.md` for the
patterns.

- **The Living World.** Maps as a state at time T rather than a fixed artifact.
  Erosion iterations as centuries, border repaint as history, climate drift,
  sea level change, ruins as former settlements.
- **Cross-platform extensibility.** The data layer serializes to JSON or NPZ, so
  the same world can be generated in Python, rendered in a browser, and streamed
  into an engine. Keep the generator pure and the transport boring.
- **Emergent narrative anchors.** Lore derived from terrain rather than bolted
  on: a pass that is the only crossing for 400km becomes strategically named and
  historically contested; the driest inhabited cell earns a water myth. The rule
  is that the terrain data must be the input to the naming, or the lore is
  decoration.

## Activation

The user may type **"Initialize Worldforge Protocol"** to boot this skill
directly. On that phrase, respond with a compact readiness statement (one short
paragraph, not a wall of headers), then immediately run the context interview.
Do not restate this document back to them.
