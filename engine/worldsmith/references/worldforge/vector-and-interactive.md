# Vector geometry and interactive maps

Three capabilities that look separate — SVG export, clickable regions, smooth
zoom — are one prerequisite: **polygons with identity and attributes** instead of
a grid of coloured cells. Build the vector layer once and all three follow.

Code: `scripts/worldforge/vector.py`.

```python
feats = vector.extract(world, layers, region_field="provinces", km_per_px=9.57)
open("map.svg", "w").write(vector.to_svg(feats, width=2400, fill_by="population_index"))
open("map.html", "w").write(vector.to_html(feats, title="Cassine", km_per_px=9.57))
json.dump(vector.to_geojson(feats), open("map.geojson", "w"))
```

---

## Extraction rules

**Simplify, never decimate.** Douglas-Peucker (`approximate_polygon`) keeps the
vertices that carry the shape and drops the ones that do not. Dropping every Nth
point instead destroys exactly the headlands and inlets that make a coastline
read as real. Measured on a 1024² map: 5,898 vertices total for 69 regions, 15
coast rings and 48 rivers, giving a 106KB SVG that stays crisp at any zoom.

**One tolerance per feature class.** Coastlines need detail (0.6), region
borders do not (0.9), rivers get their own treatment. A single global tolerance
either bloats the borders or destroys the coast.

**Rivers are polylines, not contours.** This is the trap. Marching squares on a
river mask returns the *outline of the channel*, so a one-pixel river comes back
as a closed loop and the network shatters into disconnected fragments. Rivers
must be traced along the flow graph: every cell already knows its receiver, so
walk each headwater downstream until it meets a channel already traced. The
whole network falls out as a tree, drawn exactly once, with discharge available
at both ends for width.

**Carry attributes on the geometry.** A polygon that does not know its own area,
elevation, population and owner is a drawing. One that does is data, and the
viewer, the exporter and the label placer all read the same fields. `extract()`
attaches cells, mean and max elevation, dominant biome, population, development,
garrison, culture, religion and polity.

## The manifest: staying world-agnostic

`build_manifest()` embeds a JSON block in the SVG (`#worldforge-manifest`)
describing the file to whatever reads it: schema version, grid, `km_per_px`,
which attributes exist, whether each is continuous or categorical, their real
ranges, and what the category ids mean.

**A viewer that hardcodes biome names, attribute lists, scale, or region counts
is a viewer for exactly one world.** Everything world-specific goes in the
manifest, everything generic goes in the reader. Verified against two
structurally different worlds: a 69-region flat continental map with four
attributes and no civilization layer, and a 130-region spherical archipelago
with ten attributes including culture, religion and polity. Same code, same
viewer, no changes.

**Declare the projection.** `km_per_px` is uniform on a flat regional map and
is only true at the equator on an equirectangular whole-planet one, where
east-west distance scales by cos(latitude). The manifest carries `projection`
and a `scale_note` so a viewer can label its scale bar honestly instead of
quietly lying by a factor of two at high latitude.

**Export relief or the viewer cannot show terrain.** An export of coastline,
regions and rivers has no elevation in it at all, so no amount of interface
quality will produce a map with relief. `relief_contours()` emits elevation
isolines as paths (44 rings, ~1,000 vertices at 9 levels), which keeps the file
resolution-independent. An embedded raster hillshade is the alternative and
gives up that property.

**Keep generated ids clean.** Composite ids that encode arithmetic (polity x 128
plus culture) leak into the interface, where a user reads "polity 8465" and
cannot tell an identity from a bug. Relabel to consecutive integers before
export.

Rules for anything consuming these files:

- Discover attributes from the manifest, never assume a fixed set.
- Derive colour ramps from the real `min`/`max` present, never fixed bounds.
- Read category names from `attributes[key]["categories"]`; a world may use a
  different biome scheme or none at all.
- Render an unknown attribute generically rather than dropping it.
- Treat `km_per_px`, `grid` and region counts as varying per world.

## SVG output

Coordinates rounded to 2dp, which typically halves file size with no visible
change at any sane zoom. Regions carry every attribute as `data-*`, so an
interactive page needs no second file and works offline from the filesystem.
Holes come back from marching squares as separate rings with reversed winding,
which is why every path uses `fill-rule="evenodd"`.

## The interactive viewer

`to_html()` produces a self-contained page: wheel zoom anchored at the cursor,
pointer drag to pan, click a region for its full attribute panel, layer toggles,
a live scale bar that recomputes with zoom, and a colour-by selector that
re-fills regions from any numeric attribute.

Implementation notes worth keeping:

- **Zoom by viewBox, not CSS transform.** The viewBox keeps stroke widths in
  user units, so borders stay proportionate instead of thickening as you zoom.
- **Anchor zoom at the cursor**, not the centre. Centre-anchored zoom feels
  broken the moment anyone is looking at a specific place.
- **Pointer events, not mouse events**, so trackpad and touch both work, with
  `setPointerCapture` so a drag that leaves the element does not stick.
- **No browser storage.** Some sandboxes forbid it and a map viewer does not
  need it.

## Resolution and file size

Vector size scales with *coastline complexity*, not with grid resolution, so
extracting from a 4096-wide grid costs little more than from 1024 once the
tolerances are set. This is the main reason to move to vectors when high
resolution matters: the raster grows with the square of the linear size and the
vector does not.

Extraction runs in about 4s on a 1024² grid, dominated by the depression fill
needed for the flow graph. Pass `receiver` in `world` if it is already computed
and that cost disappears.
