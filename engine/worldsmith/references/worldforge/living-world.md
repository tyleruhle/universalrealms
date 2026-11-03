# Growth horizons: living worlds, extensibility, emergent lore

Architecture hooks, not a build list. Each section describes the pattern and the
one design decision that determines whether it will work later.

---

## 1. The Living World

A map as a state at time T rather than a fixed artifact.

**The decision that determines everything:** are you storing snapshots or
replaying a simulation? Snapshots (an array per era) are simple, bounded in
memory, and cannot answer "what happened between." Replay (seed plus event log,
re-simulated on demand) is compact and queryable but requires the simulation to
be deterministic and fast. Choose before building, because converting between
them is a rewrite.

**Geological time.** Erosion iterations already are time. Expose the iteration
count as an age parameter and the same seed gives a young jagged world or an old
worn one. Sea level as a time-varying parameter reveals and floods continental
shelves, which is a cheap and dramatic effect. Plate drift over time is possible
by advecting the plate seed points and regenerating uplift, though everything
downstream must then be recomputed.

**Historical time.** Political borders repainted per era by rerunning the growth
simulation with changed capitals, populations, and costs. Keep the physical layer
frozen and vary only the political layer; this is fast enough to animate.
Saga does exactly this (`modules/saga.md`): it stores both an event log and a
per-turn snapshot, so it answers "what happened between" and replays
deterministically from a seed.

The rule that keeps this coherent: **history must be generated forward, never
backward.** Generating a present state and then inventing a past to explain it
produces contradictions the moment anyone checks. Run centuries forward from an
initial condition and record what happens.

**Ruins as residue.** Every settlement that existed and no longer does leaves a
ruin at its coordinates. In a saga chronicle, the candidates are regions whose
population collapsed in crushed revolts and disasters, and the seats of extinct
or fragmented factions. This is nearly free once history runs forward, and it is
the single most effective way to make a world feel old.

**Weather and seasons.** Distinct from climate. Climate is the multi-year mean
the biome layer uses; weather is a shorter-period field on top. Model as an
advected pressure and moisture field over the existing terrain, with the climate
layer as the boundary condition. Do not let weather feed back into biomes.

---

## 2. Cross-platform extensibility

**The hook: the data layer must serialize.** If `generate()` returns a
dictionary of arrays plus a parameter record, and that serializes to NPZ or
JSON, then the same world can be generated in Python, rendered in a browser,
imported into an engine, and printed, with no shared code.

Practical form:

```
world.npz        elevation, biome, rivers, temperature, rainfall, ownership
world.json       params, seed, version, sea_level, settlements, POIs, factions
```

Version the schema from the first commit. A `schema_version` field costs nothing
now and saves the entire archive later.

**Keep the generator pure.** No file IO, no printing, no UI calls inside
generation. A pure `params -> data` function can be called from a CLI, a
notebook, a web service, a game loop, or a test, and that is the entire
extensibility story. Everything else is transport.

**Scaling to multi-user.** Generation is expensive and deterministic, which makes
it ideal for caching by seed plus parameter hash. A shared world becomes a shared
seed. Live collaborative editing is a different problem entirely, since edits are
no longer derivable from a seed and must be stored as an explicit diff layer over
the generated base. Design the diff layer before promising collaboration.

---

## 3. Emergent narrative anchors

Lore generated *from* terrain rather than bolted onto it. The rule: terrain data
must be an input to the generation, or it is decoration wearing a costume.

**Feature significance.** Score every feature by how much it constrains movement
or life. The only pass through a range for 400km. The single river in an arid
region. The largest island. The deepest lake. High scores earn names, and the
highest earn history.

**Names from geography.** Build a small morpheme set per culture and compose from
observed traits: a river that runs red through iron-rich terrain, a pass that is
the only crossing, a coast that faces a prevailing storm. The place name then
encodes something true about the place, which is exactly how real toponyms work
and why they feel authentic.

**Conflict from scarcity.** Compute what each faction lacks: a landlocked polity
with no port, two factions sharing one river, a region whose only arable land
sits across a border. Each of these is a ready-made casus belli derived from the
map; write them into saga's starting `grievances` and `claims` so the
simulated history inherits them. Quest hooks and campaign premises fall out of the same computation.

**Myth from anomaly.** Find the statistical outliers in the data (the driest
inhabited cell, an unexplained elevation spike, a lake with no outlet) and
generate a local legend explaining it. Anomalies are where real folklore comes
from, and the generator already knows exactly where its anomalies are.

**The handoff.** This is where worldforge stops and worldbuilder begins.
Worldforge produces the terrain-derived facts: this pass is strategically
critical, this region is isolated, this city controls the only harbor.
Worldbuilder turns those facts into cultures, histories, and religions that
explain and exploit them. Keep the boundary clean. Worldforge should output
structured findings, not prose.
