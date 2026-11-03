# Historiography: true history and recorded history

Worldbuilder's history reference names five layers of memory: what happened,
what's recorded, what's remembered, what's mythologized, what's suppressed.
The chronicle carries the first, second and fifth. Remembered and
mythologized versions are authored on top, usually from the `locals`,
`loyalists` and `reformers` accounts, which are the closest thing to folk
memory the sim produces.

Every event in the chronicle has three layers:

- `truth`: what happened. Only the author and the reader (eventually) see it.
- `accounts`: what each involved faction recorded. Keys are faction ids, or
  `loyalists`, `locals`, `reformers` for groups without a state.
- `suppressed`: true means the event happened and left no public record.

## Using the gap

| Gap | Story use |
|---|---|
| Winner calls it liberation, loser calls it betrayal | POVs on both sides can be sincere and opposed |
| Loser's account is `(not recorded)` | a lost people; a scholar POV who notices the silence |
| `suppressed: true` | a mystery, a buried crime, a dungeon, a witness worth killing |
| contested succession, "the true heir lives" | a pretender plot, years later, with a claim nobody can verify |
| alliance_betrayed, betrayer recorded nothing | the betrayed side's grievance looks irrational to outsiders |
| secret exposed by `revelation` | the founding myth breaks; legitimacy collapses in-story |
| disaster recorded as divine judgment | religious politics, scapegoating |

## Writing in-world documents

When the user wants a chronicle excerpt, proclamation, epic fragment, treaty,
or inscription:

1. Choose whose record it is and when it was written. Records written a
   generation later lie differently from records written that week.
2. Write from that faction's `accounts` entry, never from `truth`.
3. Let the truth leak through details the writer could not control: a date
   that does not fit, a missing name, a region described as loyal that the
   chronicle shows in revolt.
4. Keep the register of the culture. Hand prose-quality documents to scribe
   with the brief from `references/saga/handoffs.md`.

## Designing reveals

A reveal moves a character or the reader from an `account` to the `truth`.
Plan it backwards:

1. Pick the event whose truth matters most to the seam.
2. List who knows the truth (often only the dead or the suppressed).
3. Place two or three clues earlier in the outline, each tagged to a chronicle
   detail, so the reveal is fair.
4. Decide what the reveal costs: which gauge drops, for whom. That cost is
   the scene's weight.

## Unreliable narrators

A POV raised inside a faction believes its account. Write their chapters
from the account and let the reader catch the gap through other POVs or
documents. Make the shift in belief a character arc, not an info dump.
