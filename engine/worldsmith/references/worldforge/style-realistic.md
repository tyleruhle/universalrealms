# Style: Hyper-Realistic Geomorphic

The satellite or physical-atlas look. Correctness is the aesthetic, so the
physics layer does most of the work and the renderer mostly stays out of the way.

## Elevation color

Two conventions, and mixing them badly is the most common error.

**Hypsometric tinting** maps elevation to color directly: greens low, tans and
browns mid, gray and white high. This is the atlas convention. It is *not*
realistic (low-elevation deserts are not green) but it is highly legible for
reading terrain.

**Biome tinting** maps the classified biome to color, which is what a satellite
actually shows. Green appears where there is vegetation, regardless of altitude.

Pick one deliberately. For "hyper-realistic," use biome tinting with a slight
elevation-driven desaturation and a snowline override. Blending the two produces
maps that read as neither.

## Relief shading

Hillshade is what turns a flat color field into terrain.

```
slope  = pi/2 - arctan(hypot(dz/dx, dz/dy) * z_factor)
aspect = arctan2(-dz/dx, dz/dy)
shade  = sin(alt)*sin(slope) + cos(alt)*cos(slope)*cos(azimuth - aspect)
```

Conventions that matter: light from the northwest (315 degrees) at 45 degrees
altitude. Light from the south inverts the perception and mountains read as
valleys, which is a genuine perceptual illusion and not a matter of taste.

- `z_factor` exaggerates vertical scale. 1.0 is true, and true is usually too
  flat to read. 5 to 20 is typical. State the exaggeration if the map claims
  accuracy.
- **Multidirectional hillshade** (combine 4 azimuths with weights) reveals detail
  that single-source shading flattens, at four times the cost.
- Apply shade multiplicatively over the color, clamped so shadows do not crush to
  black. `color * (0.55 + 0.75 * shade)` is a reasonable band.

## Water

- **Bathymetry.** Depth deserves its own ramp, not a flat blue. Shallow shelf,
  continental slope, abyssal plain. Depth banding at the shelf edge is a strong
  realism cue and costs one extra color stop.
- **Rivers.** Width scaled by cube root of accumulation. Render as a polyline
  with a subtle darker outline, not as thresholded pixels, or they will alias
  into dashes.
- **Lakes** come from the depression-fill delta and should be flat-shaded, since
  a lake surface is level by definition. A hillshaded lake is an instant tell.
- **Coastal foam or surf line**, a 1 to 2 px lighter band at the waterline, adds
  a surprising amount of perceived quality.

## Detail at scale

Realism fails at zoom when the underlying array runs out of resolution. Options:

- **Detail noise on render.** Add high-frequency noise to the shading normal (not
  the elevation) when zoomed in. Cheap, and preserves the data layer.
- **Adaptive subdivision.** Generate additional octaves only for the visible
  region, seeded deterministically from the coordinate so the same detail
  reappears. This is the correct answer for anything zoomable.
- **Texture splatting.** Per-biome tiling textures blended by biome weight,
  standard in engines. See references/worldforge/stack-engine.md.

## Cartographic honesty

If the map claims realism, these details are checked by viewers who know:

- Graticule (latitude and longitude lines) and a stated projection.
- A scale bar that is actually correct, plus a north arrow.
- Contour lines at a stated interval, if the map is topographic. Contours must
  never cross and must close or leave the frame.
- A legend covering every color and symbol used.
- Elevation and depth values in stated units.

Getting the physics right and then labeling the scale bar wrong undoes the whole
effect, because a scale bar is the one element a reader can verify by eye.

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
