# Stack: Python (default lane)

Default to Python for prototyping. It gets the pipeline correct fastest, and the
data layer ports cleanly once the algorithms are settled.

## Libraries

| Need | Use | Notes |
|---|---|---|
| Arrays, all math | NumPy | float32 for terrain layers, uint8 for classified |
| Filters, distance transforms, resampling | SciPy `ndimage` | `gaussian_filter`, `distance_transform_edt`, `map_coordinates`, `maximum_filter` |
| Voronoi, nearest-neighbor, Delaunay | SciPy `spatial` | `cKDTree` for per-pixel nearest-plate queries |
| Perlin / Simplex | `noise` (`snoise2`, `pnoise2`) | Optional. C extension, sometimes painful to install. Value-noise fBm in pure NumPy is a fine substitute at 5+ octaves |
| Raster output, glyphs, text | Pillow | `ImageDraw` for lines and glyphs, `ImageFont.truetype` for labels |
| Vector output | `svgwrite`, or write SVG strings directly | Direct string writing is often simpler than the library |
| Contours and polygons | `skimage.measure.find_contours` | The clean way to get coastlines and borders as polylines |
| Interactive UI, fast | Streamlit | Best effort-to-result ratio for a parameter explorer |
| Interactive UI, smooth | Pygame | Real pan and zoom, game-loop feel, more code |
| Hot loops | Numba `@njit` | For droplet erosion and other genuinely sequential work |

## Performance rules

1. **Vectorize or justify.** A per-pixel `for` loop is a defect unless the stage
   is inherently sequential. The three legitimate exceptions are priority-flood
   depression filling, flow accumulation ordering, and column-swept moisture
   advection.
2. **Prefer `ndimage` to hand-rolled loops.** `uniform_filter`, `maximum_filter`,
   and `distance_transform_edt` are all compiled and are usually 50 to 200x
   faster than the obvious NumPy equivalent.
3. **float32 everywhere.** Halves memory and is faster on most hardware. Terrain
   does not need 15 decimal digits.
4. **Profile before optimizing.** `cProfile` at target resolution. In practice
   the cost is almost always in depression filling or in an accidental
   `float64` upcast, and rarely where it is assumed to be.
5. **Cache the data layer.** `np.savez_compressed` the arrays. Restyling should
   never regenerate.

## Determinism

Use `np.random.default_rng(seed)` and thread the generator through every stage
explicitly. Never call `np.random.*` module-level functions, which use hidden
global state. Never iterate a `set` in a path that consumes randomness. If an
optional feature draws from the RNG, the same seed with the feature off produces
a different world downstream, so either draw unconditionally or give each stage
its own child generator via `rng.spawn()`.

## Streamlit pattern

```python
import streamlit as st

st.sidebar.number_input("seed", value=42, key="seed")
# ... other params ...

@st.cache_data
def build(params_tuple):          # hashable key, not the dataclass
    return generate(WorldParams(*params_tuple))

world = build(params_tuple)
style = st.sidebar.selectbox("style", ["realistic", "parchment", "political"])
st.image(RENDERERS[style](world), use_container_width=True)
```

The important part is that `@st.cache_data` wraps generation only. Changing the
style must not invalidate the cache, which is the layer split paying off
immediately.

## Pygame pattern

Render the full map once to a `Surface`, then pan and zoom by blitting a
subsurface scaled to the window. Never re-render per frame. Regenerate only when
a parameter changes, on a worker thread with a progress indicator, since a
multi-second generation will otherwise freeze the event loop and look like a
crash.

## Packaging

For a script the user runs, a single file plus a `requirements.txt` is enough.
For anything reused, split into `generate.py` (data layer), `render/` (one module
per style), and `cli.py`. That structure survives the port to another language,
because the split is the architecture rather than a Python convention.
