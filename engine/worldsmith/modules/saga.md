
# Saga

History in, story out. Saga runs a deterministic simulation of an invented
world's history, keeps every event's causes, keeps the true history apart from
what each side recorded, scores the past for story potential, and then
architects plot from the strongest seam.

## The one rule

**History is simulated before story exists, and the simulation never sees the plot.**

The point of the tool is that conflicts arrive from the world's own logic. If
the outline is decided first and history is bent to fit it, the result is the
contrivance this skill exists to prevent. So: simulate, read, pick a seam,
then plot. When the user already has canon the history must reach, do not
hand-edit the chronicle to force it; use `fit` to search for a seed whose
history arrives there honestly (see Mode 1b).

The user owns canon. The sim proposes; anything the user keeps becomes canon,
anything they reject is discarded or demoted to in-world rumor. Say which
events you are treating as canon when you hand off to scribe.

## Pipeline and modes

Scripts live in `scripts/saga/`; run them from there or by full path. All are deterministic: same world, seed and turns
always produce the same history.

| Mode | Command | Output |
|---|---|---|
| Ingest | hand-author `saga_world.json`, or `scripts/saga/wf_adapter.py` from a worldforge seed | `saga_world.json` (+ grids for maps) |
| Simulate | `scripts/saga/saga_sim.py simulate saga_world.json --seed N --turns T --out DIR` | `chronicle.json`, `timeline.md`, `seams.md` |
| Fit to canon | `scripts/saga/saga_sim.py fit saga_world.json --target target.json` | ranked seeds whose history reaches the canon present |
| Trace | `scripts/saga/saga_sim.py trace chronicle.json EVENT_ID` | cause chain behind an event, consequences after it |
| Seams | `scripts/saga/saga_sim.py seams chronicle.json --top 10` | ranked story seeds |
| Branch | `scripts/saga/saga_sim.py branch saga_world.json --base chronicle.json --override ID=OUTCOME --out DIR` | alternate history + diff |
| Era maps | `scripts/saga/render_eras.py --chronicle ... --world-dir ... --turns 0 20 40` | political map per era (worldforge worlds only) |
| Outline | Claude, using `references/saga/plot-architecture.md` | arcs, POVs, beat sheet, chapter plan |
| To the bible | `scripts/saga/to_bible.py chronicle.json --out world-bible/history.md` | worldbuilder-format history draft, all marked proposed |
| Hand off | Claude, using `references/saga/handoffs.md` | scribe scene briefs, canon ledger |

Run `python scripts/saga/saga_sim.py template` for a starter world file (also in `assets/saga_world_template.json`).

### Mode 1: Ingest

Pick the source the user already has. Check memory and the conversation for an
existing worldbuilder bible or worldforge seed before asking.

- **From a worldbuilder bible:** translate factions, regions, cultures,
  religions, succession laws and secrets into `saga_world.json`. Read
  `references/saga/simulation.md` for the schema and for how lore maps onto the
  gauges. Ten to forty regions is the sweet spot for a hand-authored world.
  Secrets are the highest-value field: every secret the bible has (a false
  founding myth, a hidden heir, a bargain) goes in, because their exposure is
  a story engine.
- **From worldforge:** `scripts/saga/wf_adapter.py --seed N --brief "<plain-language
  brief>"` generates a planet (or `--flat` for a region map), runs worldforge's
  civilization layer, and writes a region graph with land borders plus sea
  lanes scaled by `sea_affinity`. Regions are worldforge polities, factions
  start as one per culture (`--factions polity` for a warring-states start).
  Always show the user the `brief_matched` list it prints, per worldforge's
  rule against silent keyword misses. Use the same seed and brief the world's
  maps were made with, recorded in `world-bible/maps/`, or the history will
  run on a different planet. If the map has been edited (sculpted coasts,
  named features), pass `--world world-bible/maps/world.npz` instead, or
  `--edits world-bible/maps/edits.json` with the seed; regenerating from the
  seed alone drops the edits. The adapter reports `terrain` (seed, saved world,
  + edits) and any brief words it could not apply to saved terrain: show both.
  Names are placeholders; rename from the bible before simulating so the
  timeline reads as the user's world.
- **Both:** run the adapter for geography, then overwrite factions, cultures
  and secrets from the bible.

Confirm the timescale (years per turn, number of turns) and where the story's
"present" sits. Those are the only two questions usually worth asking.

### Mode 1b: Fit to canon

When the bible already fixes facts about the present (who holds which region,
which dynasty fell, which realm no longer exists), write them as a target file
and search seeds. Schema in `references/saga/simulation.md`. Report the best fit
score; below 1.0, list the constraints the history missed and let the user
decide whether to accept a near miss, loosen canon, or edit the starting
state. Never quietly hand-edit events to close the gap.

### Mode 2: Simulate and read

Run the sim, then read `timeline.md` and `seams.md` yourself before reporting.
Give the user the shape of the history in a few sentences (who rose, who fell,
the two or three turning points), not a dump of events. Offer the era map if
the world came from worldforge.

### Mode 3: Find seams

A seam is a moment where history could have gone another way and something
real was at stake. The scorer ranks events by contest, stakes, the gap between
truth and record, downstream cascade, and irreversibility. Treat its ranking
as a shortlist, not a verdict: a low-scoring event that touches one of the
user's secrets, or sits where two cascades cross, can be the better story.
Use `trace` on any finalist to see what caused it and what it caused.

Present the top three to five seams as pitches: one line on what happened,
one line on what the records disagree about, one line on why it's a story.
Let the user choose.

### Mode 4: Outline

Read `references/saga/plot-architecture.md`. In short: zoom to the seam, set the
story window, cast POVs from factions with opposing stakes in it, choose the
structure for the format (short story, novel, trilogy, campaign), and build
beats. **Every beat is tagged with the chronicle event or gauge it depends
on.** That tag is what keeps the plot honest to the history and what lets the
user see which beats break if they change canon.

### Mode 5: Branch

When the user asks "what if", or when a protagonist's success would change an
outcome, branch: override the event's outcome and re-run. The branch is
identical to the base up to that event, then diverges for causal reasons.
Use `diff.json` to tell the user what changed. For trilogies, the branch from
book one's climax *is* book two's world; see the sequel section of
`references/saga/plot-architecture.md`.

The branch command refuses an override that matches what already happened, and
an override on an event id that the branch never reaches. Both are signals to
pick a different outcome or event, not errors to work around.

### Mode 5b: Write history into the bible

When the user wants the history as lore rather than as story material, run
`to_bible.py`. It cuts eras at the chronicle's own turning points, keeps only
events that matter (worldbuilder's excess-precision rule), charts dynasties in
worldbuilder's genealogy format with regnal numbers, and marks everything
proposed. Walk the user through it era by era: they name each era, strike
events, and only then does the file become canon. Promote the one or two
pivotal events to `00-overview.md`, per worldbuilder's overview rule.

### Mode 6: Hand off

Read `references/saga/handoffs.md`. Scene briefs go to scribe; a canon ledger
(facts, dates, who knows what) goes alongside so later sessions and continuity
checks have one source of truth; era border maps go back to worldforge's
political style if the user wants them polished.

## True versus recorded history

Every event carries `truth` and per-faction `accounts`. Some events are
`suppressed`: they happened, and no public record exists. This gap is
deliberate material: mysteries, propaganda, unreliable narrators, a POV who
believes the winner's account. Read `references/saga/historiography.md` before
writing any in-world document (chronicle excerpt, proclamation, epic) or
designing a reveal.

## Working style

- Direct and compact. Lead with results; the user does not want a narration
  of steps.
- Report history as consequences, not dice: "the Kor collapse followed two
  contested successions and a lost war at Highmarch", never "the sim rolled".
- Names from the sim are placeholders. Rename freely to fit the bible, and
  keep a mapping so ids still resolve.
- The sim is a coarse instrument. If its output contradicts the bible's tone
  or rules (a theocracy schisming every decade, a pacifist culture warring),
  adjust the starting gauges and rerun rather than rationalizing the output.
- If the user asks for prose, write the outline and briefs here and let
  scribe write the scenes.

## Reference files

| File | Read when |
|---|---|
| `references/saga/simulation.md` | Authoring or editing `saga_world.json`, mapping lore to gauges, writing a fit target, tuning a sim that feels wrong. |
| `references/saga/plot-architecture.md` | Any outline, POV, beat sheet, chapter plan, campaign, or sequel work. |
| `references/saga/historiography.md` | Writing in-world documents, designing reveals, using suppressed events or secrets. |
| `references/saga/handoffs.md` | Sending work to scribe, worldforge or worldbuilder; exporting a canon ledger. |
