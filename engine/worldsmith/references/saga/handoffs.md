# Handoffs

Saga sits between worldbuilder and worldforge (inputs) and scribe (output).
World-bible locations follow `modules/worldbuilder.md`: generated files in
`world-bible/saga/`, canon in the markdown files.

Scribe is a separate skill and is not bundled here. If it is not installed,
the briefs still work as a writing plan, and prose can be written directly
from them while honoring the same rules (no em-dashes in prose).

## To scribe: scene briefs

One brief per scene. Scribe writes the prose; the brief carries everything
scribe should not have to invent or look up.

```
SCENE BRIEF · Book 1, ch 7, scene 2
POV: <name>, <faction>, believes: <their faction's account of the key event>
Where / when: <region name>, year <Y>, <season or hour if it matters>
Canon in play: <event ids and one-line truths the scene must not contradict>
What the POV does not know: <truth they lack>
Scene goal: <what the POV wants here>
Turn: <what changes by the end; tie to a gauge if possible>
Must include: <clue, object, line of dialogue, image>
Must avoid: <spoilers, facts this POV cannot know yet>
Register: <tone, culture's voice, reference points from the bible>
Length: <words>
```

Scribe holds a hard rule against em-dashes in prose. Write briefs without
them so the register carries cleanly, and do not ask scribe to imitate a
document style that depends on them.

## Canon ledger

After the user accepts an outline, export a ledger beside the chronicle,
`canon.md` or `canon.json`: one line per accepted fact, with event id, year,
regions, factions, the truth, the public account, and which POVs know which.
Mark facts the outline invented with `invented`. This is the single source
for later continuity checks and for the next saga run.

## To worldforge: polished era maps

`render_eras.py` makes functional political maps. For finished maps, give
worldforge the era's `ownership` snapshot from `chronicle.json` and the
`region_grid.npy`, and use `references/worldforge/style-political.md` and
`scripts/worldforge/cartography.py`. `render_eras.py` assigns golden-angle hues
by faction creation order, so a faction keeps its color across eras and
across branches; the polished map should keep that mapping.

## Back to worldbuilder

For the history itself, `scripts/saga/to_bible.py` drafts `history.md` in
worldbuilder's format with every line marked proposed. For everything else the
history changed (a dynasty fell, a new faith exists, a region is now
independent), list the changes as bible updates for the user to approve,
grouped by domain: politics, religion, geography. Do not rewrite the bible
silently. Run worldbuilder's consistency engine over the approved changes.
