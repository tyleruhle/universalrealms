# Stack: JavaScript / Web

Choose the web when sharing matters, when the map is interactive, or when the
user wants others to explore it without installing anything.

## Picking the rendering path

| Path | Use when | Limit |
|---|---|---|
| Canvas 2D | Static or lightly interactive raster, under ~2048px | Redraw cost grows fast; no shaders |
| SVG | Vector maps, crisp labels, styleable with CSS, printable | Thousands of paths will crush the DOM. Simplify aggressively |
| WebGL via Three.js | 3D terrain, orbit camera, heightmesh, large scenes | Real learning curve; overkill for a flat map |
| WebGL raw or a shader lib | Per-pixel effects, huge maps, live parameter tweaks | Most powerful, least readable |

Default to Canvas 2D for a flat map and Three.js only when the user actually
wants a third dimension.

## The split matters more here

Generation is CPU-bound and will block the UI thread. Two viable architectures:

1. **Generate in Python, ship data.** Export the data layer as JSON (small maps)
   or a packed binary or PNG-encoded array (large ones), and let the browser only
   render. Best when the generator already exists and the web is a viewer.
2. **Generate in the browser, in a Worker.** Port the pipeline to JS, run it in a
   Web Worker, and post `Transferable` typed arrays back so nothing is copied.
   Best when users need to change seeds and parameters live.

Encoding elevation into the RGB channels of a PNG (a 24-bit fixed-point value) is
a compact, cache-friendly transport for heightmaps and is worth knowing.

## Canvas notes

- Draw the terrain once into an offscreen canvas or `ImageBitmap`, then blit for
  pan and zoom. Do not redraw per frame.
- Use `ImageData` and write the pixel buffer directly for the terrain layer.
  Per-pixel `fillRect` is orders of magnitude slower.
- Keep overlays (borders, labels, grid, fog) on separate stacked canvases so
  toggling one does not force a full redraw.
- Set `imageSmoothingEnabled = false` for tile and pixel-art maps, true for
  realistic ones.

## Three.js heightmesh

- `PlaneGeometry` with segments matching the heightmap, then displace vertices
  from the elevation array. Above roughly 512x512 segments, displace in a vertex
  shader with the heightmap as a texture instead of touching geometry on the CPU.
- Vertex colors from the biome array, or a texture built from the same renderer
  used for the 2D map, which keeps both views consistent for free.
- Water as a separate flat plane at sea level with a transparent material. Much
  cheaper and better-looking than trying to shade the terrain as water.
- `OrbitControls` is a separate import from the examples directory, not part of
  the core bundle. Version mismatches here are a common source of silent failure.

## Determinism in JS

`Math.random()` cannot be seeded. Use an explicit PRNG (mulberry32, sfc32, or
xoshiro128) so seeds reproduce. If a world must be identical in Python and JS,
that is a real constraint: floating-point and library differences will diverge.
Either generate in one place and ship the data, or accept that the two
implementations agree only approximately.

## Deployment

A single self-contained HTML file with inlined JS is the most shareable artifact
and needs no build step. Reach for a bundler only when the dependency graph
justifies it.
