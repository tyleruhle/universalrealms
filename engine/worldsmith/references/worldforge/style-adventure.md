# Style: Adventure / RPG Overworld

Optimized for play, not for realism. Every visual element answers a player
question: where can I go, what is there, what have I not seen.

## Grid and topology

If the cells only need to be *read* rather than counted, a terrain-conforming
tessellation beats any lattice (see `references/worldforge/cartographic-detail.md`). Grids earn their
place when movement, range, and area-of-effect have to be computed. When both
are needed, the usual answer is watershed cells for the visual and political
layer with an invisible hex grid underneath for mechanics.

Decide the grid first, because it changes pathfinding, distance, and art.

- **Square, 4-connected.** Simple, but diagonal movement is either forbidden or
  distorted.
- **Square, 8-connected.** Diagonals cost sqrt(2) or the map lies about distance.
- **Hex.** Uniform neighbor distance, no diagonal problem, the traditional
  wargame and overworld choice. Use axial coordinates (q, r) internally and
  convert to pixels only at render. Offset coordinates are easier to store and
  much harder to do math with.

Downsample the simulation grid to the play grid by majority vote for
classification layers (biome) and by mean for continuous ones (elevation). Never
sample a single pixel per tile; one-pixel sampling makes rivers disappear.

## Readability over accuracy

At tile resolution, physical accuracy loses to legibility.

- Ensure adjacent-tile colors differ enough to distinguish at the actual display
  size. Check contrast in grayscale.
- Rivers must survive downsampling. Rasterize them onto the tile grid explicitly
  as an edge feature (a river runs *between* tiles, along the shared edge) rather
  than hoping a river pixel lands in a tile center.
- Impassable terrain should look impassable. If mountains block movement, they
  need a visual weight that a player reads instantly.

## Zones and pathways

Segment the map into named regions with clear boundaries: flood-fill on biome
plus elevation, merge small regions into neighbors, then smooth boundaries. Each
zone gets a difficulty tier, which drives both encounter tables and palette
saturation (safe zones warmer, dangerous zones cooler and darker).

Guarantee connectivity. Run a traversability check across the whole map before
delivery: if any zone the design intends to be reachable is not reachable, carve
a pass. Do this as an explicit repair step with a log line, not silently.

Roads and paths are least-cost paths between settlements with slope-weighted
cost and river-crossing penalties. Crossings become bridges and fords, which are
free points of interest.

## Points of interest

Place from terrain features rather than at random:

- Dungeon entrances at high-elevation isolated cells or cave-plausible geology.
- Ruins at sites that scored well for settlement but have no current settlement.
  That single rule makes a world feel like it has a past.
- Shrines at extremes: highest peak, deepest lake, only oasis.
- Camps and outposts along roads at roughly one day of travel apart, which
  requires knowing the travel-speed scale.

Store POIs as records with coordinates, type, tier, and a discovery flag, kept
in the data layer. The renderer decides whether a marker is shown.

## Fog of war

Three distinct mechanisms, often conflated:

1. **Unexplored shroud.** Never seen. Render opaque, usually a parchment or dark
   texture that hides even terrain shape.
2. **Explored but not currently visible.** Terrain remembered, entities not.
   Render desaturated and dimmed.
3. **Currently visible.** Full color.

Store visibility as a separate uint8 array parallel to the terrain, updated by
line-of-sight from the party position. For soft edges, blur the visibility mask
before using it as an alpha, and dilate slightly so revealed regions have a
feathered frontier rather than a hard circle. Reveal by region rather than by
radius when the design wants discovery to feel authored.

## Interactivity

If the target is interactive, the minimum useful set is: pan and zoom, hover
readout of tile data, click to select, layer toggles (terrain, political,
resources, grid), and a seed input box. Streamlit gets this working in an hour;
Pygame gives smoother pan and zoom; a canvas web app gives the best sharing
story. See the stack references.

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
