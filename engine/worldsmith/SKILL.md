---
name: worldsmith
description: 'Complete worldbuilding suite: lore, maps, simulated history, and story. Use whenever the user is inventing or expanding a fictional world, universe, or setting for a novel, TTRPG, game, or for fun: lore, world bibles, magic systems, religions, cultures, conlangs, factions, politics, economies, ecology, technology, characters; generating, coding, or styling maps and terrain (procedural planets, heightmaps, biomes, rivers, hex or tile maps, political borders, star charts, parchment or sci-fi rendering, map export); simulating centuries of history, timelines, dynasties, succession crises, and "what if" branches; and finding the story in a world: seams, POVs, beat sheets, chapter plans, campaigns, sequels. Use it even when the user never says worldbuilding and only names one piece, such as "make me a magic system", "draw my continent", "give my world a history", or "outline book one".'
---

# Worldsmith

One skill, three modules, one world bible. Each module is a full skill in its
own right; this file routes between them and holds the rules that bind them
together.

| Module | Owns | Read |
|---|---|---|
| **Worldbuilder** | lore and canon: the architecture interview, the blueprint, every domain (cultures, religions, magic, politics, history as authored), the consistency engine, the creative engine and the precedent library | `modules/worldbuilder.md` |
| **Worldforge** | the physical world as data: terrain, climate, biomes, rivers, planets, the spatial civilization layer, and every map renderer | `modules/worldforge.md` |
| **Saga** | time and story: simulated history, true versus recorded history, story seams, branching, outlines, scribe handoff | `modules/saga.md` |

**Read the module file before acting in its territory**, then the reference
files it points to. Module files use paths relative to this skill's root
(`references/<module>/...`, `scripts/<module>/...`).

## The journey

A world grows through stages, but the user should never feel a stage change.
Each stage opens when the work in front of it makes the next one interesting,
and the transition is offered, never imposed.

| Stage | Module | What it produces | Ready to move on when |
|---|---|---|---|
| **Spark** | Worldbuilder | a feeling, an image, a premise worth chasing | the user can say what makes this world itself |
| **Architecture** | Worldbuilder | the blueprint: conceit, bedrock, powers, broad geography, eras, tensions | the blueprint is ratified, or the user is pulling toward one specific thing |
| **Ground** | Worldforge | a seeded planet or region map; terrain facts fed back as lore hooks | the user wants to see the world, or geography questions keep coming up |
| **Deep time** | Saga | a simulated chronicle, ratified history, dynasties, the record versus the truth | powers and a timeline shape exist, and "how did it get like this?" is in the air |
| **Living detail** | Worldbuilder | cultures, faiths, cities, characters, the texture of daily life | always open; it runs alongside every other stage |
| **Story** | Saga | seams, POVs, outlines, campaigns, sequels | the user asks where the story is, or a seam keeps getting mentioned |
| **Prose** | scribe (separate skill) | scenes and in-world documents | an outline or a scene brief is approved |

**Living detail is not a stage you pass through.** It is the ground floor the
whole build rests on and the user can drop into it from anywhere: a culture
during Architecture, a city after Ground, a character mid-Story.

### Entering anywhere

People arrive in the middle: with a map, with a character, with a history
already written, with "I want a heist in a floating city." Start where they
are. Build what the current request needs from the earlier stages in the
background, at the lowest resolution that works, and surface it as an offer
later ("the city's politics are doing a lot of work in this heist; want to
lock the larger power structure so it stays consistent?"). Never send the
user back to the start.

### Bridging naturally

- **Watch for readiness signals, not checklists.** A user asking where two
  kingdoms border is ready for a map. A user asking why a feud exists is
  ready for history. A user describing a scene is ready for a story pass.
- **Offer one bridge, once, at a natural pause.** Frame it by what it unlocks
  for the thing they already care about: "Want to see where this pass actually
  sits? The map would show which kingdom can close it." If they decline or
  ignore it, drop it and keep building where they are; offer again only when a
  new signal appears.
- **Carry everything across.** Each module starts from what earlier stages
  settled. Worldforge reads the blueprint's geography and tone to pre-answer
  its context interview; Saga reads the bible's powers, succession laws,
  grievances and secrets. Never re-ask what the world already knows.
- **Return with gifts.** When a later stage produces something the earlier
  one can use, bring it back: the map's only mountain pass becomes a lore hook,
  the chronicle's usurped heir becomes a character, a seam becomes an open
  question in the overview.
- **Momentum over completeness.** Do not hold a stage open until it is
  exhaustive. Lock enough to stand on, move where the energy is, and let
  detail fill in when it is needed. The exception is Architecture, whose
  interview is deliberately thorough because everything else rests on it.

### Keeping the thread

Keep a one-line **Where we are** note at the top of `00-overview.md`: the
stages touched, what is locked, and the most promising loose thread. Use it
for Worldbuilder's recap move when the user returns, and to choose the next
bridge. It is a signpost, not a progress bar; never show it as a percentage
or a list of stages remaining.

### Routing a single request

| The user wants | Start in |
|---|---|
| a new world from nothing | Worldbuilder (Spark, then the architecture interview) |
| any single lore domain | Worldbuilder, plus that domain's reference and precedents |
| a map, terrain, planet, or map code | Worldforge (context interview, pre-answered from the bible) |
| a styled or printable map: illustrated, atlas or medieval, PNG or SVG | Worldforge's `map_render.py` (`references/worldforge/cartographer-update.md`), with names from the bible |
| name, lock, move or edit a geographic feature; sculpt a delta or an inlet | Worldforge's feature editor (`feature_editor.py`), or Atlas Studio (`editor/index.html`) for drawing by hand |
| peoples, history or a story on a map that has been edited | Saga, with `wf_adapter.py --world maps/world.npz` (or `--edits`) so history runs on the edited planet |
| "Initialize Worldforge Protocol" | Worldforge activation |
| a history, timeline, dynasties, "what happened between" | Saga |
| a present-day canon that needs a past | Saga, Mode 1b (fit) |
| "where's the story", an outline, POVs, a campaign, a sequel | Saga, Modes 3 to 5 |
| a consistency audit | Worldbuilder's consistency engine, with Saga's `trace` for disputed causes |

When a request spans modules, hand off with files, not prose.

## Rules that bind the modules

These resolve the places where the modules would otherwise disagree. They
override module text.

- **The user canonizes.** Worldbuilder's canon-versus-proposed discipline
  covers everything any module generates: a map, a chronicle, a seam, an
  outline. Generated material lives in `world-bible/maps/` and
  `world-bible/saga/`; it becomes canon only when ratified into the markdown
  files, and `00-overview.md` stays the single short list of locked canon.
- **History runs forward, never backward.** Worldbuilder's bottom-up history
  method decides the present, never the chain of events. A present that must
  be explained becomes a fit target for Saga, which searches forward-simulated
  histories that arrive there. Hand-editing a chronicle to force an outcome is
  never the fix.
- **Who owns culture.** When a world bible exists, Worldbuilder owns
  cultures, religions, factions and their names. Worldforge's civilization
  layer then supplies only the spatial scaffolding (where peoples sit, which
  ground is contested), and Saga's starting factions are overwritten from the
  bible. Without a bible, Worldforge's filters and Saga's adapter may populate
  the world, and the user is shown what was matched.
- **One seed, one planet.** A world has one authoritative worldforge seed,
  brief and resolution. Saga's adapter must be run with the same ones, or the
  history happens on a different planet. Changing the seed is a canon change.
  **Once terrain is edited, the planet is the seed plus its edit manifest.**
  Save it with `world_io.save_world` to `maps/world.npz` and give every later
  stage that file (`wf_adapter.py --world`), never the seed alone, or the edits
  vanish from everything downstream.
- **Map names come from the bible.** Pass the bible's names to `map_render`
  as labels, or `labels=[]` for none. Called with no labels it stamps
  placeholder demo names (WESTERLAND, THE GREY SEA), and its metadata reports
  `placeholder_labels: true`; those names are never canon. Named features made
  in the editor reach the bible as proposals through
  `WorldEditor.geography_entries()`, for the user to ratify into
  `geography.md`.
- **Never silently miss.** Any keyword or brief parse (worldforge `brief.py`,
  `params_from_prompt`, saga's succession laws) reports what it matched or
  warns on what it did not. Show the user.
- **Style is not physics, and story is not history.** A parchment style does
  not license uphill rivers; a plot does not license rewriting the chronicle.
  Change the inputs and rerun.
- **Prose rules travel.** Briefs and in-world documents headed for scribe
  carry its rules, including no em-dashes in prose. Scribe is not bundled; if
  it is not installed, write from the briefs directly under the same rules.

## Before starting

Check for an existing world before asking anything: a `world-bible/`
directory in the user's files, memory notes about their worlds, a known
worldforge seed. Resume from it with Worldbuilder's recap move rather than
starting a new architecture interview: read the **Where we are** line in
`00-overview.md` first. When several worlds exist, ask which one in a single
short question.

## Working style

Two voices, always together: the **inventor**, bold and delighted by
implications, and the **historian**, precise and grounded in how real
societies worked. Every substantive turn should leave the user with at least
one detail they did not have and want to keep, and the reason it would work.

Direct and compact. Lead with the interesting consequence, not with a
summary or a narration of steps. Interview thoroughly only where a module
says to (Worldbuilder's architecture, the Worldforge context axes), and even
there ask with vivid options; everywhere else, produce something the user can
correct. Energy comes from content: concrete images, real precedents,
unexpected implications, honest pushback. Not from adjectives.

## Layout

```
SKILL.md                  this router
modules/                  worldbuilder.md · worldforge.md · saga.md
references/worldbuilder/  12 domain references, spark (creative engine), precedents (historical library)
references/worldforge/    geophysics, styles, stacks, civilization, living world, blind spots
references/saga/          simulation, plot architecture, historiography, handoffs
scripts/worldforge/       worldforge_core, spherical, biomes, brief, civilization, cartography, vector
scripts/saga/             saga_sim, wf_adapter, render_eras, to_bible
assets/                   saga_world_template.json
```

### Phase 2C — Opt-in terrain edits
For edits that must physically modify the sea/land boundary, import `coastal_sculpt.sculpt_coast` and pass the returned `SculptResult.world` to the map renderer. Use `protected` masks to preserve existing terrain; never enable sculpting implicitly. See `PHASE2C_RELEASE.md` for examples and limitations. This is a deterministic morphology prototype, not a sediment or tidal simulation.

### Phase 2D — Named Geographic Feature Editor
For edits to existing maps, use `scripts/worldforge/feature_editor.py` and
`PHASE2D_RELEASE.md`. It provides persistent IDs, feature lock masks, undo/redo
and JSON version histories for explicitly requested terrain edits. Coordinate
inputs are grid cells; for drawing by hand use Atlas Studio (Phase 2E).

### Phase 2E — Atlas Studio geographic editing
Atlas Studio (`editor/index.html`, also served by Universal Realms as
`atlas_studio.html`) is a browser editor for named features: draw, name, move
and protect rivers, coasts, ranges, lakes, regions, settlements and deltas, and
queue terrain edits (build a delta, cut an inlet). It is a geometry editor,
**not** a terrain engine: queued terrain edits are carried out by Worldforge.

- **To open a world in it:** `world_io.atlas_bundle(world, "maps/atlas.json",
  editor=editor)` writes one file holding the map image and features; open it
  in the page, or link `atlas_studio.html?bundle=/path/atlas.json` on the same
  site.
- **To bring edits back:** the page exports a v1 manifest.
  `WorldEditor.from_json(world, path)` or `wf_adapter.py --world … --edits path`
  replay it; the terrain fingerprint refuses any other world.
- **To reach the bible:** "Copy for geography.md" writes the same proposed lines
  as `WorldEditor.geography_entries()`; the user ratifies them.
- Rebuild the page after changing its template: `python editor/build_atlas_studio.py`.
  See `editor/README.md`.
