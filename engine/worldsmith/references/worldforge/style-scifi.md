# Style: Sci-Fi Planetary and Galactic

Two different problems share one aesthetic. Planetary maps are terrain with an
instrument-readout skin. Galactic maps are sparse point data in 3D projected to
2D, where the design problem is legibility, not terrain.

## The instrument-readout aesthetic

The look reads as *data being displayed by a machine*, which means:

- Dark substrate (#080C14 to #0F1620), never pure black.
- One or two saturated accent hues carrying meaning (cyan #38E1FF, amber
  #FFB13C, magenta #FF4FD8), everything else near-monochrome. Neon everywhere
  reads as noise; neon on one channel reads as a signal.
- Thin, consistent stroke weights. Scanlines, subtle chromatic offset, and a
  faint bloom on emissive elements.
- Monospace or geometric sans type, uppercase, letterspaced, with numeric
  readouts that look measured: coordinates, delta-v, population to three
  significant figures, spectral class.

The credibility comes from the numbers being internally consistent, not from the
glow. A star labeled M-class should be dim and red in the render.

## Hex overlays

Consider first whether a grid is wanted at all. An imposed lattice reads as
stamped-on over organic terrain, and for anything that is not a wargame the
better default is a terrain-conforming tessellation: watershed cells seeded from
a jittered point set, so every boundary is a drainage divide. See
`references/worldforge/cartographic-detail.md`. Use hexes when cells must be addressable and distances
must be computable; use watershed cells when the map is for reading.

Standard for 4X and strategy. Use axial coordinates internally. Draw the hex grid
as a separate overlay layer with per-cell alpha so it can be toggled and so cells
can be individually highlighted for range, control, or resource display.

Cost of a hex: for pointy-top hexes with size s, width is `sqrt(3)*s` and height
is `2*s`, with vertical spacing `1.5*s`. Getting this wrong by a factor produces
grids that almost tile, which looks worse than no grid.

## Planetary maps

The terrain pipeline is unchanged. What changes is the projection and the skin.

- **Projection matters here more than on fantasy maps** because the audience
  expects a globe. Equirectangular is the easy default and distorts poles badly.
  If the map wraps, the noise must be sampled on a sphere (3D noise evaluated at
  points on the sphere surface) or the seam will not match.
- **Alien climate.** Change the constants, not the algorithm. A tidally locked
  world uses a temperature field keyed to substellar distance instead of
  latitude. A high-axial-tilt world has extreme seasonal bands. A thin atmosphere
  raises the lapse rate and shrinks the habitable band. These are parameter
  swaps, which is exactly why the physics layer is worth having.
- **Resource heatmaps.** Generate as a separate low-frequency noise field
  correlated with terrain features (ore near orogeny, hydrocarbons in former
  basins, ice at poles and permanently shadowed craters). Render as an additive
  glow layer with a legend. Correlation with terrain is what makes resource
  distribution feel geological rather than sprinkled.
- Landing sites, habitable zones, and hazard regions are POI records scored from
  terrain, the same as settlements in a fantasy map.

## Galactic and stellar maps

- **Distribution.** Real stellar neighborhoods are roughly uniform in density
  locally, spiral-arm structured at galactic scale. Generate arms as a
  logarithmic spiral `r = a * exp(b * theta)` with scatter perpendicular to the
  arm, plus a central bulge and a sparse halo.
- **Coordinates.** Store real 3D positions and project. Displaying a 3D volume in
  2D is the core UX problem: options are a projected plane with depth encoded as
  size or brightness, an explicit z-axis "drop line" to a reference plane (the
  classic Traveller and Elite solution, and still the clearest), or interactive
  3D. Pick one and commit.
- **Star properties.** Spectral class drives color and luminosity together. A
  simple table of O/B/A/F/G/K/M with color, mass, and frequency (M-class is
  roughly 76% of stars, which is why a realistic map is mostly dim red dots) is
  enough to make a chart feel researched.
- **Routes.** Jump links between systems form a graph. Generate as a
  distance-limited Delaunay triangulation or a relative neighborhood graph, not
  as all-pairs within a radius, which produces a hairball. Then prune to a
  spanning structure plus a few redundant links, which yields chokepoints and
  therefore strategy.
- **Orbits.** Draw as ellipses with the primary at a focus, not at the center.
  This is the most common error in generated system maps and it is immediately
  visible to anyone who knows.

## Data overlays

Sci-fi maps carry more data layers than any other style: political control,
trade volume, threat level, sensor coverage, resource yield. Build the overlay
system as an explicit stack of toggleable, individually-alpha'd layers from the
start. Retrofitting a layer system onto a flat renderer is a rewrite.

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
