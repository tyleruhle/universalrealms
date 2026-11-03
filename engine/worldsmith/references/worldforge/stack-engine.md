# Stack: C# and Engine Native (Unity, Godot)

Use when the map is part of a game, needs streaming at scale, or must be edited
in-editor. The pipeline is the same; the constraints are memory, frame budget,
and the engine's threading rules.

## Universal engine constraints

- **Generation must not block the main thread.** A multi-second hitch is a frozen
  game. Use `Task.Run` plus a main-thread callback in Unity, or a `Thread` with
  `call_deferred` in Godot. Engine API objects (meshes, textures, tilemaps) can
  usually only be *created* on the main thread, so structure the work as
  "compute arrays off-thread, upload on-thread."
- **Chunk everything.** Generate and mesh in chunks (64, 128, or 256 cells) and
  stream by distance from the camera. See the chunking caveat in
  references/worldforge/blind-spots.md: noise chunks cleanly, hydrology does not.
- **Determinism.** Seed an explicit PRNG per chunk from
  `hash(worldSeed, chunkX, chunkY)`. Never let chunk output depend on generation
  order, or a player who approaches from the other direction gets a different
  world.

## Unity

**Tilemaps.** `Tilemap` plus `SetTiles` in bulk. Never call `SetTile` per cell in
a loop for a large map; the batched call is dramatically faster. `TileBase`
assets per biome, and a `RuleTile` handles auto-transitions between biomes and
coastlines without per-cell logic.

**Meshes.** Build `Vector3[]` and `int[]` arrays off-thread, then assign to a
`Mesh` on the main thread. Above 65k vertices per mesh, set
`indexFormat = UInt32` or split into submeshes. Recalculate normals on the CPU
from the heightmap analytically rather than calling `RecalculateNormals()`, which
is slow and gives worse results at chunk seams.

**Chunk seams.** Adjacent chunks must sample identical values on shared edges.
The reliable pattern is generating each chunk with a one-cell overlap margin and
computing normals from the margin, then discarding it. Without this, every chunk
boundary shows a lighting crack.

**Performance path.** For anything heavy, the Job System plus Burst with
`NativeArray` is roughly an order of magnitude faster than plain C# and is worth
the ceremony for terrain. Compute shaders are faster still for noise generation
specifically, but reading results back to the CPU has latency, so keep
GPU-generated data on the GPU where possible.

**Terrain vs mesh.** Unity's built-in `Terrain` component gives LOD, splatmap
texturing, and detail scattering free, and accepts a heightmap directly via
`SetHeights`. It is the right default unless overhangs, caves, or non-heightfield
geometry are needed, in which case build custom meshes.

## Godot

**TileMap.** `set_cell` per cell is acceptable at moderate scale, but
`TileMapLayer` with a prepared pattern is faster for bulk fills. Terrain sets
(autotiling) handle biome transitions.

**Meshes.** `SurfaceTool` for convenience, `ArrayMesh` with pre-built
`PackedVector3Array` for speed. `MeshInstance3D` per chunk. Godot's
`HeightMapShape3D` handles collision from the same array.

**Threading.** Godot 4 uses `WorkerThreadPool`. Resource creation on a thread is
allowed for some types but not all; when in doubt, compute arrays off-thread and
construct resources in a deferred main-thread call.

**GDScript vs C#.** GDScript is fast enough for orchestration and far too slow
for per-cell terrain math at scale. Put the generation loop in C# or a GDExtension
and keep GDScript for glue.

## Porting the pipeline

Straightforward: noise, tectonics, erosion, climate, biomes are all pure array
math and port directly.

Harder: priority-flood depression filling needs a real priority queue
(`SortedSet` or a binary heap; C# has no `PriorityQueue` before .NET 6), and flow
accumulation needs a full-map sort, which conflicts with chunked generation. The
usual resolution is a coarse global hydrology pass computed once at low
resolution, with chunks sampling and refining from it. Decide this before writing
the chunk system, because retrofitting global hydrology into a chunked generator
is a rewrite.
