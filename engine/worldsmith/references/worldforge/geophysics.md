# Geophysics: the math under a believable map

Contents: [Noise](#1-noise) | [Tectonics](#2-tectonics) | [Erosion](#3-erosion) |
[Hydrology](#4-hydrology) | [Climate](#5-climate) | [Biomes](#6-biomes) |
[Settlement](#7-settlement) | [Ordering](#8-stage-ordering)

The goal is not simulation accuracy. It is *plausibility per unit of compute*.
Each section states the cheapest model that produces the visual signature people
recognize, and what it costs to go one level deeper.

---

## 1. Noise

**Value noise vs Perlin vs Simplex.** At 5 or more octaves they are visually
interchangeable for terrain. Value noise built from an interpolated random
lattice needs no dependency and is fast in NumPy. Reach for `noise.snoise2`
(Simplex) only when tileability, 3D sampling, or true gradient behavior matters.

**fBm.** Sum octaves with `amplitude *= gain` (0.5) and `frequency *= lacunarity`
(2.0). Gain below 0.5 gives smooth rolling land, above 0.5 gives jagged noise.
Octave count past 8 adds nothing visible at typical resolutions and costs a full
resample each.

**Domain warp.** The single highest-value trick available. Offset sample
coordinates by two more low-frequency noise fields before evaluating:

```
warped(x, y) = base(x + A*nx(x,y), y + A*ny(x,y))
```

A of 0.05 to 0.15 of map width. This converts the soft round blobs of raw fBm
into coastlines with peninsulas, fjords, and inlets. If a generated coastline
looks "computery," this is almost always the missing piece.

**Ridged multifractal.** For sharp ranges: `1 - |noise*2 - 1|`, then square it,
then accumulate octaves weighted by the previous octave's value. Use as a
*mask multiplied against uplift*, not as the base field, or the whole map turns
into corduroy.

**Continent shaping.** Three common approaches, in ascending quality:
radial falloff (fast, obviously circular), a low-frequency mask thresholded
(better, still blobby), and plate-derived continental crust (see below).
Combine: `elev = 0.68*fbm + 0.32*(0.5 + plate_bias + uplift)` is a good default
ratio. More plate weight gives coherent continents but risks polygon edges.

---

## 2. Tectonics

This is what separates terrain that reads as *a world* from terrain that reads as
*a texture*. Mountain ranges are linear because plate boundaries are linear.

**Minimum viable model:**

1. Scatter N seed points (12 to 30 for a continental map). Voronoi partition.
2. Give each plate a random unit drift vector and a crust type. Continental crust
   gets a positive elevation bias, oceanic gets negative.
3. For each pixel, find the two nearest plate seeds. Boundary proximity is
   `exp(-(d1 - d0) / width)`.
4. Convergence is `dot(drift[a] - drift[b], normalize(seed_b - seed_a))`.
   Positive means the plates are closing.
5. `uplift = proximity * convergence * strength`. Positive uplift builds ranges,
   negative carves rifts and trenches.

**Critical step:** blur the plate bias field hard (sigma near 3.5% of width)
before adding it to the base. Unblurred, the Voronoi cell edges become straight
coastlines and the map reads as generated. Blur the uplift only slightly, since
ridge sharpness is the point.

**One level deeper:** continent-continent convergence gives high plateaus
(Himalaya), oceanic-continental gives a coastal range plus offshore trench
(Andes), oceanic-oceanic gives island arcs. Branch on the crust types of the two
plates and scale uplift accordingly. Transform boundaries produce offset ridges
and are worth adding only if the user cares about fault detail.

---

## 3. Erosion

**Thermal / diffusive.** Material slides downhill when slope exceeds a talus
angle. Cheap approximation: iteratively blend toward a local mean, weighted by
local slope. Rounds peaks, fills valley floors. 10 to 15 iterations is plenty.

**Hydraulic, stream power law.** `E = K * A^m * S^n` where A is upstream drainage
area, S is local slope, m is around 0.5, n around 1.0. This produces V-shaped
valleys, dendritic branching, and the correct relationship where large rivers cut
deeper. It requires flow accumulation, so it runs *after* drainage, and the loop
is: fill, accumulate, incise, repeat 2 to 4 times.

Explicit stepping is unstable above K of roughly 0.4. If terrain develops holes or
NaNs, halve K and double the passes rather than adding clamps.

**Droplet / particle erosion.** Spawn thousands of droplets, each carrying
sediment, moving downhill, eroding on steep terrain and depositing on flat.
Produces the most attractive results and the most convincing alluvial fans. It is
inherently sequential per droplet and slow in Python; move it to a compiled path
(numba, C#, GLSL compute) if the user wants it.

**Glacial and coastal erosion** are specialty additions. U-shaped valleys and
fjords come from glacial carving above a snowline elevation. Only add if the map
is polar or alpine and the user asks.

---

## 4. Hydrology

Get this right and the map instantly reads as real. Get it wrong and every viewer
notices even if they cannot articulate why.

**Depression filling is mandatory.** Raw noise terrain is full of local minima.
D8 routing without filling produces rivers that vanish mid-plain. Use
priority-flood (Barnes et al. 2014) with an epsilon tilt: push border cells into
a heap, pop the lowest, and raise each unvisited neighbor to
`max(its_elevation, popped + epsilon)`. The epsilon guarantees flats still have a
downhill direction so routing does not stall. O(n log n), and it is one of the
few legitimate sequential loops in the pipeline.

**Flow routing.** D8 sends all water to the single steepest of 8 neighbors.
Simple, and produces slightly angular rivers. D-infinity or multiple-flow-
direction spreads water proportionally across downslope neighbors and gives
smoother, more natural networks at higher cost. Start with D8.

**Accumulation.** Sort all cells by elevation descending, then push each cell's
accumulated flow into its receiver in one pass. Every donor resolves before its
receiver, so a single linear sweep is correct.

**Rivers.** Threshold the accumulation array. A threshold near 0.3% of total cell
count gives a visible primary network; lower it for tributary detail. River
*width* should scale with the square root or cube root of accumulation, never
linearly, or trunk rivers become highways.

**Lakes.** The difference between the filled surface and the original elevation
is exactly the water body depth. Cells where `filled - elev > small_epsilon` are
lake cells, for free, as a byproduct of the fill.

**The rule that catches most bugs:** rivers merge going downstream and never
split. A distributary delta is the sole exception and only at a river mouth. If
a generated river forks inland, routing is broken.

---

## 5. Climate

**Temperature.** Latitude gradient plus lapse rate:
`T = f(|latitude|) - lapse * elevation_above_sea`. A power near 1.25 on the
latitude term gives a wide tropical band and sharp poles, which matches Earth
better than a linear gradient. Continentality (distance from ocean) widens the
seasonal range, which matters only if simulating seasons.

**Moisture, the important one.** Do not generate rainfall as noise. Advect it:

1. Pick a prevailing wind direction. Sweep the grid column by column along it.
2. Over water, moisture recharges toward saturation.
3. Over land, precipitation is `moisture * (1 - exp(-k * elevation_rise))` plus a
   small background convective term.
4. Subtract precipitation from the carried moisture and continue.

Rain shadow then emerges rather than being painted on: windward slopes are wet,
leeward interiors are dry, and the effect strengthens behind tall ranges. That
single behavior is what makes a climate map look researched.

**Normalize against a high quantile, not the max.** One freak windward peak will
otherwise scale the entire map down and turn every continent into desert.

**Three-cell circulation is required, not optional, for any map claiming
realism.** Hadley, Ferrel and Polar cells give latitude-banded prevailing winds
and reproduce the horse-latitude desert belts near 30 degrees. Implement as a
wind direction that varies by latitude band, then run the same advection sweep
per band.

**Measured:** a single prevailing westerly applied to Earth's real coastline put
the Amazon and the Congo in *desert*, the Sahara in shrubland, and Kansas in
tundra — 2 of 10 well-known sites classified plausibly. One wind direction dries
out every continental interior, because there is no ITCZ to wet the equator and
no monsoon to wet a subcontinent. If the brief is fantasy, one wind is fine and
nobody will check. If the brief is realism, this is the first thing to fix.

---

## 6. Biomes

Whittaker classification on the temperature and moisture plane covers nearly
every need. Bucket temperature into 4 bands and moisture into 3, assign the 12
cells of that matrix, then apply elevation overrides last (alpine, then snowcap)
since a cold wet peak is snow regardless of what the moisture band says.

**Moisture recycling is not a refinement, it is required.** A pure
advect-and-deplete model puts nothing back, so humidity falls monotonically with
distance from the coast and every continent becomes a desert with a green rim.
On Earth roughly a third to a half of continental rainfall is re-evaporated from
the land it already fell on. Measured on a generated planet without the term:
70% of land below the dry threshold, and 52% of land classed desert or shrubland
against Earth's ~19% desert. Adding a coastal humidity bonus, a recycling term,
and lateral diffusion moved that to 31% arid and 43% forest.

**Normalise moisture against the land median, not a high quantile.** A handful of
soaked windward peaks otherwise set the scale and push the whole continent below
every threshold. This is the same class of error as normalising by the maximum,
just less obvious.

`scripts/worldforge/biomes.py` implements all of this plus the classifier below.

Common refinements, in order of payoff:
- Shallow water as its own class near the coast. Cheap, large visual gain.
- A coastal band that shifts biomes one step wetter.
- Beach and dune classes on low-slope shoreline.
- Wetland where flow accumulation is high but slope is near zero.
- Sharp biome edges look artificial. Add a small noise offset to the *thresholds*
  rather than blurring the classified output, which would blend IDs into
  meaningless intermediate values. Fixed thresholds on a smooth field draw that
  field's isolines, which is why unjittered biome maps come out as concentric
  bands parallel to the coast.
- **Snow belongs to temperature, not to elevation.** Keying alpine and snowcap to
  relative height puts the same snowline on a tropical and a polar range. The
  lapse rate already carries elevation into temperature; classify on the result.
- **Order the pipeline: zonal matrix, then speckle removal, then azonal classes,
  then cold overrides.** Azonal features (wetland, beach, floodplain) are
  legitimately one or two cells wide, so a mode filter applied after them
  deletes them entirely. Use a mode filter and never a blur, so every output
  value stays a legal biome ID.
- The intermediate classes matter more than the exotic ones. Most of what reads
  as wrong in a generated biome map is a missing transition: cold desert between
  tundra and desert, shrubland between grass and sand, wetland along the
  floodplain.

---

## 7. Settlement

Settlements are a data-layer product, not decoration, and their placement is what
makes a map feel historical.

Score every land cell and take local maxima with a minimum separation:

- **Fresh water access.** Distance to a river or lake cell. Dominant term.
- **Coastal or confluence bonus.** Natural harbor (sheltered coast with low
  slope) and river confluences are where real cities are.
- **Arable land.** Fraction of moderate-slope, temperate, non-desert cells within
  a radius.
- **Defensibility.** Local elevation relative to surroundings, or a river bend.
- **Chokepoint value.** Cells on the only low-cost path between two regions. Run
  a least-cost path between region centroids and score cells on that path.
- **Resource proximity.** If ore or special resources exist, weight them.

Then place larger settlements first, suppress a radius around each, and place
smaller ones in the remainder. Roads follow least-cost paths between settlements
weighted by slope and river crossings, which naturally routes them through the
same passes the chokepoint term identified. That mutual reinforcement is the
whole reason to compute settlement from terrain rather than sprinkling dots.

---

## 8. Stage ordering

The order is load-bearing. Every stage reads only from stages above it.

```
seed
  -> base field (fBm + domain warp)
  -> tectonics (plates, uplift, crust bias)
  -> combined elevation
  -> thermal erosion
  -> sea level (quantile for target land fraction)
  -> [ fill depressions -> flow accumulation -> stream-power incision ] x N
  -> final fill + accumulation (rivers, lakes)
  -> temperature (latitude + lapse)
  -> moisture (advection sweep, needs final elevation and sea mask)
  -> biomes
  -> settlements, roads, borders
  -> render
```

Two ordering mistakes are extremely common. Setting sea level before erosion
means erosion changes the land fraction underneath it, so recompute the quantile
after. Computing moisture before final elevation means rain shadow is cast by
mountains that erosion has since removed.
