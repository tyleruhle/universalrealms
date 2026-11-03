# Simulation reference

## Contents
1. saga_world.json schema
2. Mapping lore onto the model
3. Gauges and what moves them
4. Event catalog
5. Fit targets
6. Tuning a history that feels wrong
7. Limits

## 1. saga_world.json schema

```json
{
  "meta": {"name": "...", "start_year": 0, "years_per_turn": 10},
  "cultures": {"vael": {"syllables": ["vae","lin","or"], "endings": ["","n","th"]}},
  "religions": {"the_flame": {}},
  "regions": [
    {"id": "r1", "name": "Ashvale", "terrain": "river plain",
     "wealth": 0.8, "population": 0.8, "defensibility": 0.2,
     "culture": "vael", "religion": "the_flame",
     "neighbors": ["r2", "r3"], "chokepoint": false}
  ],
  "factions": [
    {"id": "f1", "name": "Throne of Ashvale", "culture": "vael", "religion": "the_flame",
     "succession": "primogeniture", "regions": ["r1", "r2"],
     "legitimacy": 0.7, "cohesion": 0.6, "militarism": 0.4, "treasury": 0.5,
     "grievances": {"f2": 0.5}, "allies": [], "claims": [],
     "ruler": {"name": "Elsath", "age": 52, "heirs": 1}}
  ],
  "secrets": [{"id": "s1", "about": "f1", "text": "The founding king was a Kor exile.", "potency": 0.7}]
}
```

Required: `regions` (id, name, neighbors) and `factions` (id, name, regions).
Everything else has defaults. Neighbors are made symmetric automatically.
Ids must be `r<number>` for regions if you want era maps (the renderer reads
the number); otherwise any string works. All numbers run 0 to 1.

`succession` is one of: `primogeniture` (low crisis risk), `council`,
`appointment`, `divine`, `elective`, `tanistry` (high), `none` (very high).
Worldbuilder's politics vocabulary is accepted too: `ultimogeniture`,
`agnatic`, `predecessor` (chosen by the ruler), `trial`. Anything else runs at
a middling risk and prints a warning, so a typo cannot silently change history.

Rulers who reuse a dynasty name get regnal numbers (Dradra II), which carry
straight into the genealogies `to_bible.py` writes.

`claims` lists factions whose throne this faction has a claim on. Claims raise
war appetite against that faction and make its successions more dangerous.
Marriages in the sim create new claims, so claims accumulate over time.

## 2. Mapping lore onto the model

| Lore says | Set |
|---|---|
| ancient, sanctified dynasty | legitimacy 0.8+, succession `divine` or `primogeniture` |
| new regime, usurper, junta | legitimacy 0.3 to 0.4 |
| fractious nobles, federated clans | cohesion 0.3 to 0.4, succession `tanistry` or `elective` |
| bureaucratic empire | cohesion 0.7, succession `appointment` or `council` |
| warrior culture, expansionist | militarism 0.75+ |
| merchant republic | militarism 0.2 to 0.3, treasury 0.7, succession `council` |
| old feud, lost province | `grievances` toward the other side, 0.5 to 0.9 |
| a dynastic marriage, a pretender abroad | `claims` |
| a mountain pass, a strait, a bridge city | `chokepoint: true`, defensibility 0.8+ |
| conquered people | region culture or religion differing from owner (unrest rises on its own) |

Science fiction translates directly: regions are systems or habitats,
neighbors are jump lanes or wormholes, chokepoints are gate systems,
succession is whatever transfers authority (election, AI appointment, House
inheritance). For a setting whose core conceit is legitimacy or succession
law, model the competing legal doctrines as different `succession` values on
rival factions and add each doctrine's weak point as a secret.

Secrets: write anything the bible keeps hidden that would damage a faction if
exposed. `potency` scales the legitimacy and cohesion hit. Each secret can
surface at most once, more likely when the faction is divided and has enemies.

## 3. Gauges and what moves them

| Gauge | Rises with | Falls with | Drives |
|---|---|---|---|
| legitimacy | won wars, reforms, unions | lost wars, usurpation, revealed secrets, betrayal | succession stability, rebellion, unions |
| cohesion | legitimacy, reform, slow recovery toward 0.55 | unrest, contested successions, schism, size | collapse below 0.12, schism, rebellion odds |
| militarism | set by lore, inherited by successors | (static) | war appetite, ruler mortality |
| treasury | regional wealth | war (-0.15 each side), reform | war appetite, strength |
| grievance | lost wars, refused unions, betrayal, secession | decays 10% per turn | war target choice, alliances |
| region unrest | foreign culture or religion, recent conquest, disaster, low legitimacy | cohesion, concessions, crushed revolts | rebellion |

Strength = population and wealth of owned regions, scaled by cohesion,
militarism, treasury and legitimacy. Defense adds the front region's
defensibility and defenders' allies.

The gauges echo real theories of history: cohesion is Ibn Khaldun's
*asabiyyah*, legitimacy falling through disaster is the dynastic cycle and the
Mandate of Heaven, accumulating claims are Turchin's elite overproduction. See
`references/worldbuilder/precedents.md` section 13 when explaining a chronicle
to the user; it turns "the dice said so" into a reason.

## 4. Event catalog

| Type | Outcomes (branchable) | Notes |
|---|---|---|
| succession | smooth, contested_heir_wins, contested_claimant_wins, split | split creates a rival faction holding half the realm |
| war | attacker_wins, defender_wins, stalemate | big wins take two regions |
| rebellion | rebels_win, rebels_crushed, concession | rebels join neighboring kin or found a free state |
| union | union_accepted, union_refused | small state folds into strong kin; the counterweight to fragmentation |
| alliance | alliance_holds, alliance_betrayed | half of alliances are sealed by marriage, creating claims |
| schism | schism_spreads, schism_suppressed | new religion id in the most restless regions |
| disaster | famine, plague, flood, earthquake | not branchable |
| reform | reform | a golden age; rarely a seam |
| revelation | exposed | a world-file secret becomes public |
| collapse | fragmented, extinct | splits by culture |

Event ids are `T<turn>-<n>`. Causes are the involved factions' and regions'
most recent prior events plus explicit links; `trace` walks them.

## 5. Fit targets

```json
{
  "ownership": {"r12": "f3", "r40": "f1"},
  "alive": ["f1", "f3"],
  "dead": ["f2"],
  "require_events": [{"type": "succession", "outcome": "contested_claimant_wins", "faction": "f1"}],
  "forbid_events": [{"type": "collapse", "faction": "f3"}]
}
```

Faction ids created during the sim (`f31` and up) are not stable across
seeds, so constrain on starting factions. Fit is a fraction of satisfied
constraints. Two hundred seeds of a 30-region, 30-turn world takes seconds;
widen `--seeds` before loosening canon.

## 6. Tuning a history that feels wrong

| Symptom | Adjust |
|---|---|
| Everything shatters into dozens of states | raise starting cohesion, lower militarism, fewer cultures per faction |
| Nothing happens | raise militarism, add grievances and claims, lower legitimacy |
| One empire eats the world | lower its cohesion, add rival claims, give neighbors high defensibility |
| Successions dominate the timeline | use more `primogeniture` or `council`; raise legitimacy |
| Too few seams with real ambiguity | add secrets; mix cultures inside realms |

Change starting conditions and rerun. Do not edit events in a chronicle by
hand; a hand-edited chronicle has causes that no longer explain its effects.

## 7. Limits

The sim models politics on a graph: no individual characters beyond rulers,
no technology change, no economy beyond wealth and treasury, no sea lanes
unless written as neighbors. Islands with no neighbors cannot be invaded;
the worldforge adapter adds sea lanes automatically (listed per region under
`sea_lanes`), but a hand-authored world needs them written as neighbors. These gaps are where the
outline and the bible do the work.
