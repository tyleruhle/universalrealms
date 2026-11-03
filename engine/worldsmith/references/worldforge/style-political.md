# Style: Civilization and Political

Borders are the output of a process, not a drawing. Generating them from a growth
simulation over terrain gives shapes that look historical, because they are
produced by the same pressures that produce real ones.

## Territory growth

Three approaches, ascending in quality and cost.

**1. Voronoi from capitals.** Instant, and looks it. Straight-edged cells that
ignore terrain. Acceptable only for abstract board-game aesthetics.

**2. Weighted flood fill (recommended default).** Seed each faction at its
capital, expand outward with a priority queue ordered by accumulated cost. Cost
per cell is the interesting part:

```
cost = base
     + slope_penalty * slope
     + water_penalty  * is_water        # rivers are cheap, seas expensive
     + biome_penalty[biome]             # desert and tundra cost more
     - road_bonus     * on_road
     + distance_decay * dist_from_capital   # power projection falls off
```

Because expansion is cheap along valleys and coasts and expensive over ranges,
borders land on watersheds and mountain crests without being told to. That is the
single behavior that makes generated political maps convincing.

**3. Agent simulation.** Factions as agents with population, military, and
aggression, running turns of expansion, conflict, and collapse. Produces
enclaves, exclaves, and irregular frontiers. Use when history matters more than
the current snapshot. This is implemented by saga: `scripts/saga/wf_adapter.py`
turns a worldforge world into a region graph, `modules/saga.md` runs the turns,
and `scripts/saga/render_eras.py` repaints borders per era. Background in
references/worldforge/living-world.md.

## Capital placement

Capitals come from the settlement scoring in references/worldforge/geophysics.md, with two extra
constraints: a minimum separation between capitals of different factions
(otherwise the growth phase produces slivers), and a preference for defensible
sites with good regional access. Place capitals first, then let territory grow,
then place secondary cities inside the resulting territories. Reversing that
order produces cities that ignore their own borders.

## Border rendering

- **Extract, do not trace pixels.** Find cells whose ownership differs from a
  neighbor, then build polylines from those edges and simplify
  (Douglas-Peucker). Rendering border pixels directly gives aliased, jittery
  lines that look like a bug.
- **Line convention.** Solid for settled borders, dashed for disputed, dotted for
  claimed but uncontrolled. A wider soft halo in the faction color just inside
  the border is the standard atlas treatment and reads clearly at any zoom.
- **Fill.** Low-alpha faction color over the terrain so relief stays visible, or
  flat color if the map is purely political. Choose one; half-transparency over
  full terrain detail is muddy.

## Faction color

Generate in HSL, not RGB. Space hues evenly around the wheel with a random
offset, hold saturation and lightness in a mid band, then check adjacent
territories for hue separation and swap where two neighbors collide. Reserve a
distinct treatment for unclaimed land (desaturated gray-green) and for water.
Verify the palette in grayscale and against the common color vision deficiencies;
red-green faction pairs on a shared border are a real accessibility failure.

## Enclaves, exclaves, and irregularity

Perfectly contiguous territories look generated. Add: a small chance a growth
front jumps a water body (colonial holdings), islands of one faction inside
another (historical accidents), and buffer regions owned by nobody. A simple rule
that pays off: after growth completes, transfer a handful of small border regions
to the neighbor, which produces the ragged frontier real maps have.

## Named regions

Provinces, duchies, and states subdivide factions. Generate with the same growth
process seeded from secondary cities and clipped to the faction boundary. Region
names should reflect terrain (a river name, a range name, a directional term
relative to the capital), which ties the political layer back to the physical one
and makes the whole map feel like one artifact.

## Layer budget

Every overlay must leave the relief underneath it readable.

- Hatch, grid, or ruling: under ~35% ink at the lightest weight that still reads.
- Glow or bloom: taken from an emissive mask, never the whole composite.
  Blurring the finished frame erases the shading the terrain depends on.
- One accent hue carrying meaning. A second competes and both stop signalling.
- Symbol, marker, and decoration layers: under ~5% of frame.
- Exactly one categorical surface tint.

The test is direct: look at the finished image and find the hillshade. If it is
gone, lighten a layer. Never darken the base to compensate.
See `references/worldforge/cartographic-detail.md` for the full detail stack.
