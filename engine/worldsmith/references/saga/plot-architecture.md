# Plot architecture

From a seam to an outline. The history supplies the pressure; this file turns
pressure into story.

## Contents
1. Zoom: from seam to story window
2. Casting POVs
3. Choosing the structure
4. Beat sheets with dependency tags
5. Chapter plans
6. Campaigns (TTRPG)
7. Sequels and trilogies: branch forward
8. Failure modes

## 1. Zoom

A seam is one event. A story needs a window around it.

1. `trace` the seam. The causes are the backstory and the setup; the first
   ring of consequences is the fallout the story can show or imply.
2. Set the window. Default: start one turn before the seam (when the pressure
   is visible but the outcome is open), end at the seam's resolution or one
   consequence later. A short story usually covers days inside the event; a
   novel covers the turn; a trilogy covers the seam and two consequence rings.
3. Name the question. Every seam reduces to a question the reader will hold:
   "Who takes the throne?", "Will Saltreach rise?", "Is the founding myth
   true?" If you cannot state it in one line, pick another seam.
4. Name what is irreversible. The ending changes something that cannot be
   undone; the history tells you what.

The sim fixes WHAT happens at the level of states. The story invents WHO and
HOW at the level of people. Never contradict the outcome the user has
accepted as canon; do invent everything beneath it.

## 2. Casting POVs

Draw POVs from the factions with opposing stakes in the seam, plus one from
outside the contest.

| Slot | Comes from | Job |
|---|---|---|
| The contender | the faction with the most to gain | drives action |
| The defender | the faction with the most to lose | drives resistance; often the most sympathetic |
| The record-keeper | a chronicler, priest, envoy, archivist | sees the gap between truth and record; carries mystery |
| The ground | someone from a disputed region with no faction | carries cost; keeps the story honest about who pays |

Two POVs are the minimum for a contest; four is a lot for a novel. For each
POV, write: faction, gauge they personify (a legitimacy POV fears
illegitimacy; a cohesion POV fears the realm splitting), what they believe
happened in the causes (often the faction's account, not the truth), and the
want that collides with another POV.

Motivations come from the same gauges that drove the sim, so character and
history run on one engine. A faction at low legitimacy produces characters
desperate for proof of right; high grievance produces revenge; a pending
claim produces a pretender.

## 3. Choosing the structure

| Format | Length | Structure | Seams used |
|---|---|---|---|
| Short story | 3k to 10k words | single POV, single scene sequence inside the seam, ends on the irreversible moment | 1 |
| Novella | 20k to 40k | two POVs, three movements: pressure, break, cost | 1 |
| Novel | 80k to 120k | 2 to 4 POVs, four acts or 3-act with midpoint reversal; midpoint usually a revelation or betrayal from the chronicle | 1 main, 1 or 2 causal seams as subplots |
| Trilogy | 3 novels | book 1 resolves the seam; book 2 lives in its consequence ring (often a branch); book 3 resolves what the first outcome made inevitable | 3, linked by cause chains |
| Campaign | open | see section 6 | 3 to 6 concurrent |

Midpoints and reversals: the best ones are already in the chronicle. Look for
a suppressed event, a betrayed alliance, or a revelation inside the story
window and place it at the midpoint.

## 4. Beat sheets with dependency tags

Every beat names the chronicle event or gauge it depends on, so the user can
see which beats move if canon changes.

```
## Act 1: Pressure
1. Elsath dies; the court learns the heir is fourteen.  [dep: T21-1 ruler_died] [POV: defender]
2. An envoy from Kor arrives with a marriage contract nobody remembers signing. [dep: claim from T14-3 alliance] [POV: record-keeper]
...
## Midpoint
9. The record-keeper finds the founding charter: the first king was a Kor exile. [dep: secret s1, revelation T22-1] [POV: record-keeper]
```

Rules:
- A beat with no dependency tag is invention; that's fine, but mark it
  `[dep: invented]` so the user can see the ratio. A good outline is mostly
  tagged at the act level and mostly invented at the scene level.
- If a beat contradicts a tagged event, the beat is wrong or the user wants a
  branch. Ask which.
- Keep the outcome of the seam where the chronicle put it unless the user has
  asked for the branch.

## 5. Chapter plans

Expand beats into chapters only after the user approves the beat sheet. One
line per chapter: number, POV, location (region name), what changes, dep tag.
Group by act. Rotate POVs on a pattern the user can feel, and break pattern on
purpose at the midpoint and climax.

## 6. Campaigns (TTRPG)

A campaign uses several live seams at once and lets the players decide them.

1. Pick 3 to 6 seams from the same turn window as **fronts**. Each front has
   a clock: the turn-by-turn progression the chronicle shows if the players
   do nothing.
2. Each front gets: the question, the factions (as patrons and antagonists),
   two or three locations (regions), and the default outcome from the sim.
3. When players resolve a front differently, branch the sim with that
   outcome. The branch tells you how the world reacts next session.
4. Secrets become clues; suppressed events become dungeons, ruins, and
   witnesses.
5. Session prep = the next turn of every active branch.

## 7. Sequels and trilogies: branch forward

If book one's ending changes the seam's outcome, run `branch` with that
outcome. Book two is set in the branch's next consequence ring. Read
`diff.json` for what changed: regions that changed hands are new settings,
powers only in the branch are new antagonists, and events that occur only in
the branch are book two's seams. Run `seams` on the branch chronicle.

If book one's ending matches the chronicle, no branch is needed; book two is
the existing consequence ring.

## 8. Failure modes

- **Plot first, history bent to fit.** Defeats the tool. Go back to seams.
- **The chronicle as summary.** An outline that just narrates the timeline has
  no POV and no question. Zoom further in.
- **Every POV a ruler.** Rulers are what the sim tracks; stories live below
  them. At least one POV should be someone the chronicle never names.
- **Ignoring the record gap.** A story where every character knows the truth
  wastes the historiography layer.
- **Too many seams in one novel.** One main seam; others are background.
