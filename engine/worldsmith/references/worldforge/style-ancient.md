# Style: Ancient / Medieval

The look is not "old paper filter." It is a set of period conventions applied to
the same data arrays, plus deliberate imprecision. Period maps were drawn by
someone who had not seen most of what they drew.

## Palette and substrate

Base parchment in the range #E8D9B5 to #C9B187, ink in #2B2118 to #4A3B2A, water
ink slightly cooler at #3C4A63. Never pure black and never pure white.

Build the paper procedurally rather than compositing a texture file: two octaves
of low-frequency noise for tonal variation, one high-frequency octave for grain,
plus a vignette and a few darker blotches. Fold creases are two or three faint
straight gradients. Edge burn is a distance-to-border falloff multiplied into the
tone. This keeps the asset dependency-free and scales to any output size.

## Line work

- **Coastline.** Extract the sea mask boundary, then perturb it. Two techniques:
  offset each contour vertex by low-frequency noise along its normal, or render
  the coast at a lower resolution than the map so it inherits chunky honesty.
  Add a second and third parallel line offset 2 to 4 px seaward, fading. That
  stacked-contour halo is the strongest single signal of "old map."
- **Rivers.** Single tapering ink line, wider downstream by cube root of
  accumulation. Do not render every tributary; period maps showed the ones that
  mattered. Threshold higher than a realistic render would.
- **Sea hatching.** Horizontal ruled lines parallel to the coast, densest within
  20 to 40 px of shore, fading out. Compute with a distance transform on the sea
  mask.

## Glyphs, not shading

Terrain is drawn as symbols placed at points, not as a continuous surface.

- **Mountains.** Small caret or triangle glyphs at local elevation maxima. Find
  them with a maximum filter and a minimum separation. Scale by elevation, jitter
  rotation and size, and overlap them in clusters for ranges. Two or three
  hand-drawn glyph variants beat one perfect glyph.
- **Forests.** Small tree glyphs scattered by Poisson-disk sampling within forest
  biome cells, density proportional to biome moisture.
- **Hills, dunes, marshes.** Each gets its own repeating glyph. This is the whole
  visual language.

## Furniture

Compass rose, decorative scale bar, cartouche title block, border frame,
sea monsters and ships in empty ocean, and a wind-head or two. Place furniture in
low-information regions: compute an "emptiness" field (distance from coast and
from any labeled feature) and place decorations at its maxima. That single trick
makes generated layouts look composed instead of scattered.

Sea monsters are placeholders in the literal medieval sense: they mark areas the
mapmaker did not know. Placing them in the largest unexplored ocean expanse is
both authentic and functional.

## Labels

Use a period-appropriate serif or blackletter, letterspaced generously. Curve
region labels along their region's principal axis (PCA on the region's cell
coordinates gives the axis). River labels follow the river path. All-caps
letterspaced for major regions, italic for water bodies, which is the
conventional hierarchy.

Font rendering with Pillow requires an actual TTF; ship one with permissive
licensing or fall back to the default bitmap font and say so, rather than
silently rendering something that looks wrong.

## Deliberate imprecision

The characteristic move: distort the *depiction* while keeping the *data* true.
Slightly wrong proportions, an over-large capital region, a coastline that gets
vaguer with distance from the "known" center. Pick a notional origin city and
apply distortion proportional to distance from it. That is how real period maps
were wrong, and reproducing the specific character of the error is what sells it.

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
