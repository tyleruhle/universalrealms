# Blind spot and epistemic audit

Run this before delivering a generator or declaring a map finished. Grouped by
the three failure classes: physics, computation, and feel.

---

## A. Physics violated under a style constraint

Style is a depiction choice. It never licenses breaking the model underneath.
An ancient map may draw a river as a stylized ribbon; the ribbon still has to
run downhill from a watershed to a sea.

| Check | Failure signature | Cause |
|---|---|---|
| Do rivers only merge downstream? | Forks inland | Routing without depression fill, or drawing rivers from noise |
| Do rivers reach a sea or a lake? | River stops in a plain | Same |
| Are deserts leeward? | Desert on the windward coast | Moisture generated as noise instead of advected |
| Are ranges linear? | Mountains as scattered blobs | Uplift has no linear source (no plate seams or ridged mask) |
| Do lakes have outlets or a closed basin justification? | Lakes on slopes | Lake mask taken from noise rather than from the fill delta |
| Is snowline consistent? | Snow at low elevation in the tropics | Lapse rate not applied, or applied before latitude |
| Do coastlines respond to relief? | Uniform smooth coast everywhere | No domain warp; coastline is a raw noise contour |
| Are islands where tectonics allows? | Random dots in deep ocean | Islands scattered post hoc instead of from arc volcanism or seamounts |

Also worth checking against the user's stated scale: at continental scale a
single pixel can be 5km, which means a "river" one pixel wide is 5km wide. Scale
mismatch is the most common realism error in fantasy maps and it is invisible
until someone does the arithmetic.

---

## B. Computational boundaries

**Seed determinism.** The same seed must give the same world forever. Threats:
an unseeded global RNG anywhere in the chain; iteration over a `set` or a `dict`
built from unordered input; parallel reduction with nondeterministic ordering;
floating-point differences across platforms in an iterative loop; consuming a
different number of RNG draws when an optional feature toggles.

The draw-count one is the killer, because it looks like a quality setting rather
than a structural change. **Measured:** the same seed regenerated at higher
resolution with the octave count raised 8 to 10 produced a land IoU of 0.229
against the original world. At the original 8 octaves, IoU 0.991. Two extra
lattice draws before domain warp and plate placement relocated every downstream
stage onto a different random stream. Anything that draws — an extra octave, an
optional feature, a reordered call — must be given its own generator via
`rng.spawn()` rather than being allowed to shift the main sequence. After any
resolution or parameter change, measure IoU against the previous land mask
before trusting a single downstream number. See `references/worldforge/cartographic-detail.md`. Test by running
generation twice in one process and comparing array hashes, then in two separate
processes.

**Noise layering.** Octave count past 8 is invisible and costly. Lacunarity at
exactly 2.0 with a power-of-two grid can produce visible axis-aligned structure;
2.03 breaks it. Reusing the same lattice across octaves creates self-similar
artifacts that look like a grid at a distance.

**Voronoi artifacts.** Straight polygon edges leaking into coastlines (blur the
bias field). Uniform cell sizes reading as artificial (use Poisson-disk or
jittered-grid seeding, or Lloyd relaxation, and pick deliberately: relaxation
makes cells *more* uniform, which is right for game territories and wrong for
natural regions). Cells clipped at the map border creating false coastal shapes.

**Performance.** In Python, anything per-pixel in a `for` loop is a bug unless
inherently sequential. The three legitimate sequential stages are priority-flood
filling, flow accumulation, and column-swept moisture advection. Everything else
vectorizes. Cost scales with area, so 1024 x 1024 is 4x the work of 512 x 512,
not 2x. State the crossover where the target size stops being interactive.

**Chunked and infinite generation.** The hard constraint: any stage that needs
global information cannot be chunked naively. Noise is chunkable because it is a
pure function of coordinates. Flow accumulation is not, because a river's
drainage area may originate outside the chunk. Options are a coarse global pass
that constrains fine local chunks, overlapping chunk margins with stitched
seams, or accepting locally-plausible hydrology that is globally wrong. Say
which one is being chosen and why, because this decision is expensive to reverse.

**Projection and area bias.** A square array is not a sphere and an
equirectangular grid is not equal-area. Any latitude-dependent statistic
computed by counting cells over-weights the poles: Earth's land fraction reads
0.332 on an unweighted equirectangular grid against a true 0.289. Either weight
by `cos(latitude)` or state plainly that the map is a region rather than a
globe. Generating a "planet" as a flat square and reporting global statistics
from it is wrong in both directions at once.

**Memory.** A float32 array at 4096 x 4096 is 64MB per layer. A pipeline holding
ten layers plus intermediates will exceed 1GB. Use float32 not float64, drop
intermediates explicitly, and consider uint8 for classified layers like biome ID.

---

## C. The narrative and user-experience element

**Sterile randomness.** Pure noise has no hierarchy: everything is equally
interesting, which reads as nothing being interesting. Real geography has a few
dominant features and a long tail. Fix by amplifying the largest structures
(higher weight on low-frequency octaves, stronger plate influence) rather than
adding more detail.

**Poetic vs realistic scale.** A TTRPG map where a party crosses the continent in
two weeks is not a realistic continent, and that is a legitimate choice. Ask
which one the user wants. If the answer is poetic, keep the *relationships*
plausible (rivers downhill, deserts leeward) and let absolute distances lie.

**Hand-crafted feel.** What makes a map feel authored is asymmetry with intent:
one enormous inland sea, one range that dominates the continent, one anomaly.
Generate a handful of candidate worlds and select, rather than trying to make
every seed good. Selection is cheaper than constraint.

**Legibility.** A physically perfect map that a person cannot read at a glance
has failed. Check contrast between adjacent biome colors, whether rivers survive
at the display resolution, whether labels collide, and whether the eye can find
the intended focus. For game maps, check the map at the size it will actually be
seen, not zoomed in.

**Determinism as a user promise.** If the user shares a seed with their table or
their players, the seed is now a contract. Any later parameter change silently
breaks every previously shared world. Version the parameters alongside the seed.
