# Cartographic detail: scaling up and filling in

How to take a working generator and produce a map somebody wants to print. Two
separate problems: **resolution** (how much detail exists in the data) and
**geometry** (how much of it you draw). Solve them in that order.

Code for all of this is in `scripts/worldforge/cartography.py`.

---

## 1. Scaling resolution without destroying the world

This is the single most dangerous operation in the whole pipeline, because it
looks harmless and silently invalidates everything downstream.

**The rule: raising resolution is safe. Changing the RNG draw sequence is not.**

Value-noise fBm built from an interpolated lattice is resolution-independent by
construction. The lattice dimensions depend on frequency and aspect ratio, not
on output size, so the same seed produces the *same continents* at 512, 1536, or
4096. Only the sampling gets finer.

But every stage that consumes random numbers must consume exactly the same
number of them in the same order. Anything that changes the draw count relocates
every subsequent stage onto a different random stream:

- changing the octave count (each octave draws a lattice)
- adding, removing, or reordering a noise call anywhere upstream
- toggling an optional feature that draws
- switching a stage between drawing once and drawing per-iteration

**Measured case.** A world regenerated from 640² to 1536² with the octave count
raised from 8 to 10 for "more detail" came back with a land IoU of **0.229**
against the original. Different continents, different coastlines, every derived
statistic invalid. The same regeneration at the original 8 octaves gave IoU
**0.991**. The two extra octaves pulled two extra lattices before domain warp
and plate placement, and everything after them landed somewhere else.

**So: detail comes from the grid, not from more octaves.** If extra octaves are
genuinely wanted, give them their own independent generator (`rng.spawn()` or a
fresh `default_rng(seed + k)`) seeded outside the main sequence, and add them
after the stages that must stay stable.

**Verify, do not assume.** After any resolution change, compute IoU between the
old land mask (nearest-neighbour zoomed) and the new one. Above ~0.95 is the
same world. Below ~0.8, something moved and every number in every downstream
document is now wrong.

```python
z = ndimage.zoom(old_land.astype(float), new/old, order=0) > 0.5
iou = (z & new_land).sum() / (z | new_land).sum()
```

**What legitimately shifts even at IoU 0.99.** Erosion, depression filling, and
flow accumulation are pixel-scale operations, so a finer grid resolves real
structure that was previously below the sampling limit. Expect more rivers, more
lakes, and more settlement sites. Those are not errors. In one measured case,
2.4x linear resolution took mapped rivers from 5,695km to 9,745km — the
tributaries were always implied by the drainage, the coarse grid just could not
draw them.

**Cost scales with area.** 1536² is 5.8x the work of 640². Priority-flood
filling stayed near 5s at 1536² in NumPy, which is usually the surprise: the
Dijkstra-style territory growth over the same grid is often slower.

---

## 2. The detail stack

Layers in draw order. Each one is cheap; the effect is cumulative.

1. **Base surface.** Hypsometric land, depth-ramped sea, relief shading.
2. **Elevation contours.** The cheapest large gain in perceived detail and the
   thing that makes a map read as surveyed rather than painted. 10 to 16 bands.
   Gaussian-smooth the field before banding.
3. **Bathymetric contours.** Same, offshore, fewer bands, heavier smoothing.
   Smooth *before* banding or the isolines fray into visible artifacts.
4. **Categorical hatch.** Diagonal ruling for a class that has no natural
   colour: seasonal ground, disputed territory, unexplored region.
5. **Category tint.** One distinguished surface tone for the single most
   important distinction on the map. Only one, or none of them read.
6. **Region lines, twice.** Provinces light, national borders heavy. Same
   weight for both means the map has no hierarchy.
7. **Graded rivers.** Three or more widths keyed to accumulation.
8. **Lakes.** Flat shaded with an ink shoreline.
9. **Coastline.** Ink, drawn last of the raster layers so nothing overprints it.
10. **Vector overlays at upscale.** Relief glyphs, routes, markers, labels,
    frame, legend, scale bar, compass.

Render the raster stack at data resolution, then upscale 2x with Lanczos before
drawing vectors. Vector elements stay crisp, the terrain gains no false detail,
and labels get room to breathe.

## 3. Four failures worth memorizing

**Uniform river width.** The most common reason a detailed map still looks flat.
Real drainage is a hierarchy; drawing it at one width hides the hierarchy that
the simulation worked hard to produce. Width scales with the cube root of
accumulation, never linearly.

**Hillshaded lakes.** A lake surface is level by definition. Shading it is an
instant tell that the water was painted on rather than derived. Flat-shade, and
take the lake mask from the depression-fill delta so it is real.

**Glyph smear on plateaus.** `elev == maximum_filter(elev)` matches every cell
of a flat region, so a plateau spawns thousands of overlapping peak glyphs that
render as horizontal streaks. Always add a prominence test:
`elev - minimum_filter(elev) > quantile(prominence, ~0.96)`.

**Provinces crossing borders.** Subdivide *within* ownership, or multiply the
label fields together and clip. A province straddling a national border reads as
a bug to every viewer, instantly.

**Flat ground breaks every tie-based algorithm, and it is always the same fix.**
Three separate artifacts in one family, all caused by an algorithm resolving a
tie geometrically because the terrain gave it nothing to work with, and all
fixed by adding noise sized *against the terrain* rather than against float
precision. On a 0..1 elevation field the working magnitude was 3e-3 in every
case; 1e-4 and 3e-4 both changed nothing.

1. Watershed region boundaries become straight floating fragments.
2. D8 rivers run dead straight across epsilon-filled depressions, producing
   channels with kilometre-long right angles.
3. Any maximum-filter peak test fires on every cell of a plateau at once.

If a map has suspiciously straight short lines anywhere, this family is the
first thing to check, and rendering each layer alone is the fastest way to find
which one is guilty.

**Watershed fragments on flat ground.** Straight vertical and horizontal line
segments floating in the middle of plains, connected to nothing. Watershed
segmentation breaks ties by array scan order, so wherever terrain is locally
flat the boundary is decided geometrically rather than topographically. Add
tie-breaking noise to the elevation before segmenting, sized against the
terrain rather than against float precision: measured on a 0..1 field, 1e-4
changed nothing and 3e-3 cleared it. `cartography.watershed_regions` handles
this. Note that these fragments look exactly like badly-drawn relief glyphs, so
confirm the source by rendering the label boundaries alone before chasing the
wrong layer.

## 4. Deriving provinces

Do not draw sub-regions by hand and do not use plain Voronoi. Watershed
segmentation over elevation, seeded from a jittered lattice and masked to land,
produces cells bounded by drainage divides — which is what real administrative
geography converges on, because divides are where movement is expensive.

Then clip against ownership so no province crosses a border. At roughly 46px
spacing on a 1536² grid this yields several hundred provinces, which is enough
texture to make a continent feel administered without labelling any of them.

## 5. Labels and furniture

- **Halo every label.** Text over hatch and contours vanishes without one. Six
  offset draws in the paper colour, then the glyph on top. Cheap and effective.
- **Two shapes beat two colours** for settlement classes. A filled square and an
  open circle survive greyscale printing and colour vision deficiency; two hues
  do not.
- **Draw legend swatches, never unicode.** Most display faces have no geometric
  glyphs, and `\u25a0` renders as tofu. Draw the square, the circle, the hatch
  patch, and the dashed line with the same code that drew them on the map.
- **The scale bar is the one element a reader can verify by eye.** If it is
  wrong, every other accuracy claim on the map dies with it.
- **Place furniture in empty space.** Compute a distance-from-content field and
  put the compass, cartouche, and legend at its maxima. This is what makes a
  generated layout look composed rather than scattered.

## 6. The layer budget

Every overlay must leave the relief underneath it readable.

- Hatch and grid: under ~35% ink at the lightest weight that still reads.
- Glow or bloom: taken from an emissive mask, never from the whole composite.
  Blurring the finished frame erases the shading the terrain depends on.
- One accent hue carrying meaning. A second accent competes and both stop
  signalling.
- Symbol and marker layers: under ~5% of frame.
- Categorical tint: exactly one.

The test is direct. Look at the finished map and find the hillshade. If it is
gone, the stack is too heavy, and the fix is always to lighten a layer rather
than to darken the base.
