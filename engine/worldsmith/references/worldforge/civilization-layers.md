# Civilization layers: generating the human world from filters

Use this when worldforge is running without the worldbuilder skill and the user
wants a populated world rather than bare terrain. Code: `scripts/worldforge/civilization.py`.

**Scope boundary, and hold it.** This produces spatial facts: where peoples are,
who rules what ground, where force concentrates, how developed each region is.
It does not write lore. If a worldbuilder session is running, that session owns
culture, religion and history, and this module supplies only the map underneath
them. Generating both independently produces two settings that disagree.

---

## The six filters

Every filter runs 0..1 and has a stated physical meaning, so a brief like
"fractured, militarised, poor" maps onto numbers instead of onto vibes.

| Filter | 0 | 1 | What it actually changes |
|---|---|---|---|
| `political_fragmentation` | few vast states | many small ones | polity seed count and separation |
| `cultural_diversity` | one culture | highly local | culture seed count and spread radius |
| `religiosity` | religion tracks culture | religion crosses borders | how much the faith layer ignores movement cost |
| `militarization` | open borders | fortified everything | garrison weight on borders and chokepoints |
| `economic_development` | subsistence | dense industrial | development index scaling |
| `biome_pressure` | people ignore terrain | they cling to good land | how hard habitability enters movement cost |

Three secondary knobs matter more than they look: `trade_openness`,
`urbanization`, and `sea_affinity`. **`sea_affinity` changes the political map
more than any other single number** — low turns seas into walls and produces
isolated island cultures, high turns them into highways and produces
thalassocracies whose territory ignores coastlines entirely.

## The physical half of the brief

`scripts/worldforge/brief.py` is the single entry point. It parses one plain-language brief
into BOTH a `SphereParams` (the physical world) and a `CivParams` (the human
one), and returns a report of what it matched.

```python
sp_params, civ_params, report = brief.parse("scorched desert world, one brutal empire")
```

Three findings from testing it, all of which the code now handles:

**Parse the physical half or discard half the brief.** The first version read
only civilization words. Across four test briefs, every terrain and climate term
matched nothing: "drowned", "scorched desert", "lush temperate", "frozen" all
silently did nothing while the user believed they had specified a world.

**Match longest keyword first and never overwrite.** "kingdom" is a substring of
"kingdoms" and whichever the dict reached last won, so "island kingdoms" came out
at fragmentation 0.35 instead of 0.75.

**Land fraction alone does not make an archipelago.** Lowering it only raises sea
level, which turns a continent into a slightly smaller continent. Water words
must also raise `plate_count` and `base_frequency` to break the structure up.
Measured: "drowned world of scattered islands" went from one dominant continent
to 37 landmasses, 9 of them over 1% of land, largest holding 46%.

Always show the user `report["matched"]`. A silent miss is discovered three
layers downstream.

## Getting the filters from the user

Ask, do not assume, but ask in one round and skip anything the brief already
answered. Two shortcuts exist:

- **Presets** in `PRESETS`: fractured warring states, single hegemonic empire,
  mercantile city-states, post-collapse frontier, theocratic union, isolated
  valley cultures.
- **`params_from_prompt(text)`** maps a plain-language brief onto the filters by
  preset match then keyword. It reports what it matched in `notes["matched"]`.
  **Always show the user that list.** A silent keyword guess that misses is
  worse than asking, because they discover it three layers downstream.

## How the layers derive

One movement-cost surface feeds everything, which is the point: change the
terrain and every human layer moves with it.

```
cost = slope + biome hostility + water price   (rivers and coasts discounted)
  -> population density   (habitability, fresh water, harbours)
  -> cultures             (Dijkstra regions from density peaks)
  -> polities             (finer regions, nested inside cultures)
  -> religion             (separate regions on a flattened cost surface)
  -> military             (borders + chokepoints, scaled by militarization)
  -> development          (connectivity x density x habitability, minus war)
```

Two design decisions worth keeping:

**Polities nest inside cultures, they never straddle.** A political border that
cuts a culture in half is a real thing in history but it should be a deliberate
event, not an artifact of two independent segmentations disagreeing.

**Religion runs on a flattened cost surface.** Raising `religiosity` lowers the
terrain's ability to stop the faith layer, so a devout world grows a small number
of large religions that cross mountains and borders, while a secular one grows
religions that look exactly like its cultures. That is the actual difference
between the two cases and it falls out of one multiplier.

**War suppresses development.** The development index is reduced by local
garrison weight, so a militarised world is measurably poorer along its own
borders without anyone deciding that separately.

## Measured example

Same terrain, same seed, two briefs:

| | fractured warring states, poor | single hegemonic empire, mercantile, wealthy |
|---|---|---|
| cultures | 30 | 9 |
| polities | 264 | 29 |
| religions | 19 | 6 |
| mean development | 0.16 | 0.45 |
| militarised land | 26.6% | 15.4% |

## Cost

Each layer is a Dijkstra pass over the full grid, so the civilization build
scales with cell count and is comparable to one hydrology pass. Roughly 14s on a
640x1280 grid. At 1536x3072 budget a few minutes, and build the civilization
layer once and cache it rather than regenerating per render.
