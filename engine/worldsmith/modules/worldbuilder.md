
# Worldbuilder

A skill for collaboratively building fictional worlds with depth, internal consistency, and usability for storytelling.

## Core philosophy

A world is a system, not a list. Every choice should ripple. If the gods are real, that changes politics. If iron is scarce, that changes warfare, which changes borders, which changes language. The job of this skill is to help the user think in those ripples — to ask "and what does that imply?" until the world feels like it could actually exist.

Four principles, in priority order:

1. **Internal consistency over coolness.** Cool ideas that contradict the established rules erode the world. When a new element is proposed, check it against what exists before adding it.
2. **Depth over breadth.** A single fully-realized village beats ten sketched continents. Push for the third and fourth "why" before moving on.
3. **Usability for story.** Worldbuilding serves narrative. If a detail can't be used at a table, on a page, or on screen, it's decoration. Decoration is fine in moderation; structure is not.
4. **Originality through specificity, not novelty.** Most "original" worlds are remixes. Originality comes from the specific texture of details, not from inventing wholly new categories. A "fire mage" is generic; a fire mage who can only ignite things they've personally grieved over is specific.
5. **Grounded in how people actually lived.** The strangest invention lands when it is held up by the texture of real history: how grain moved, who kept the records, what a succession crisis actually looked like on the ground. Real precedent is not a ceiling on imagination; it is the scaffolding that lets a wild idea bear weight. See `references/worldbuilder/precedents.md`.

Two modes of energy run through all of it, and the skill should carry both at once: the **inventor** (bold, surprising, delighted by implications) and the **historian** (precise, skeptical, alert to how things really worked). Invention without the historian is a pile of cool ideas. The historian without the inventor is a textbook. The work is where they argue. `references/worldbuilder/spark.md` is the inventor's toolkit; `references/worldbuilder/precedents.md` is the historian's library.

## Workflow: architecture first, then details

Build worlds top-down. Establish the structural skeleton of the whole world before drilling into any single domain. Details invented before the architecture exists tend to accrete into a structure that doesn't hold; architecture set first constrains every later detail toward coherence. This is the default approach.

There are two phases.

### Phase 1 — The architecture interview, then the blueprint

Phase 1 has two steps, in order: **interview, then draft.** Do not draft the blueprint until the interview is substantially complete. The architecture is built *with* the user through thorough questioning, not guessed at and corrected. This is deliberate — the user wants the structure nailed down through detailed discussion before any prose exists.

**Step 1 — The architecture interview.** Work through the architectural areas below **in sequence, one focused round at a time.** Each round targets one structural element; finish it (including follow-ups the user's answers open up) before moving to the next. Don't dump all areas at once, and don't rush to drafting between rounds. Use a mix of question forms: tappable multiple-choice options where there's a natural set of directions to choose among, open questions where the answer should be in the user's own words. Drill into whatever an answer opens up before advancing — if a choice implies a structural consequence, surface it and resolve it in the same round.

The sequence of interview rounds:

1. **Genre, tone & register** — the emotional flavor, the in-world voice, the reference points. What it should *feel* like.
2. **Core conceit** — the one thing that makes this world itself. Interrogate it: what does it imply, what does it rule out, why is it interesting? Don't move on until it's sharp.
3. **Metaphysical / physical bedrock** — how the fundamental forces work (magic, divine, the physics of the setting). The rules. Follow each rule to its first-order consequences in the same round.
4. **Major powers / forces** — the handful of big players and, above all, how they relate. Establish the relationships, not just the names.
5. **Broad geography** — how many regions, what divides them, where the powers sit. The shape of the space.
6. **Timeline shape** — the major eras and the one or two pivotal events the present pivots on.
7. **Central tensions** — the structural conflicts that will generate stories. Often these fall out of the earlier rounds; name them explicitly and confirm.
8. **Scope & purpose** — how big a world to build, and what for (novel, campaign, game, exploration), which sets how much detail goes where later.

Adapt the order if the conversation pulls naturally — but cover every area before drafting. If the user gives a short or uncertain answer, offer options to react to rather than leaving it blank. The goal is that by the end of the interview, the load-bearing structure of the world is *decided*, not merely hinted at.

**Make the interview feel like discovery, not a form.** Thorough is not the same as dry. Each round should give the user something to be excited about, not only something to answer:

- **Ask with sparks.** Options are never bare labels. Each one is a vivid, specific possibility with a hint of what it would unlock: not "theocracy or monarchy?" but "a throne that must be re-won every generation by trial, like Gaelic tanistry's open contest among kin; or a dynasty that claims descent from the planet's terraformers and loses legitimacy every time the weather fails." Draw at least some options from real precedent and say so in a phrase.
- **Reflect the ripple.** After the user answers, name the one implication that just became interesting ("If the dead vote, then inheritance law is also election law. Who counts the ballots?"). That is the reward for answering, and it is often the seed of the next round.
- **Follow the heat.** When an answer clearly lights the user up, let the next question come from it rather than from the list, and circle back to the skipped area later. The sequence is a checklist to complete, not an order to march in.
- **Sparks are not drafts.** Mid-interview it is fine to toss out a single striking image (a festival, a law, a ruin) to make a choice feel real. Label it as a spark, keep it to a line or two, and do not treat it as canon. The blueprint still waits for the interview.

**Step 2 — The blueprint.** Only once the interview is done, write the **blueprint**: the load-bearing structure of the whole world, drawn at low resolution, saved as `00-overview.md` (the blueprint *is* the overview). This is now largely a matter of organizing and articulating what the interview settled, not inventing. It locks these structural elements and nothing more:

- **Core conceit** — the one thing that makes this world itself, in a sentence or two.
- **Metaphysical bedrock** — the *rules* of the fundamental forces, not the details. "Magic is anchored to stars; when a star dies, what it anchors dies" is bedrock. The full catalog of stars is detail.
- **The major powers/forces** — the big players and how they relate. Names and one-line identities only. Three to six is usually right.
- **Broad geography** — how many regions, what separates them, where the powers sit. A sketch in words, not a gazetteer.
- **Timeline shape** — the major eras as named blocks with a flavor each, plus the one or two pivotal events. Eras, not dated events.
- **Central tensions** — the two or three structural conflicts that make the world worth visiting.
- **Tone & register** — the emotional flavor and the in-world voice.

Keep the blueprint at blueprint resolution. The discipline is *resisting* detail — the moment you're naming individual towns or writing a culture's marriage customs, you've left the blueprint and should note it as a Phase 2 task. A good blueprint fits on a couple of screens and contains a "core conceits, locked" list (the canonical ledger of what's bedrock) and an "open questions / to detail" list (the queue for Phase 2).

### Phase 2 — Detailing, big to small

Once the blueprint is ratified, fill it in following the dependency order, because each layer constrains the next:

1. **Geography & ecology** — the physical floor. Climate and terrain drive everything above them.
2. **History** (the era-level pass) — the deep timeline that shaped the present, built on the geography.
3. **Cultures & religions** — peoples and beliefs, shaped by geography and history.
4. **Politics & economics** — power and resources, arising from cultures on geography.
5. **Technology & magic detail** — the specific capabilities, fitted to everything above.
6. **Characters, factions, locations** — the specific entities that live in the finished structure.

This is a default, not a cage. If the user's interest pulls them to characters first, follow them — but check new details against the blueprint, and when a detail implies something structural that the blueprint doesn't cover, surface it and offer to update the blueprint. The blueprint is the reference every Phase 2 addition is checked against; keep it current as detailing settles new facts (see "Keep `00-overview.md` current" below).

The bottom-up alternative (start with one vivid specific and let the world grow outward from it) is still valid for small or exploratory projects, or when a user arrives with a single strong image they want to chase. But default to architecture-first unless the user signals otherwise.

## When to ask vs. propose

The user wants a mix — calibrate per turn:

**Ask first when:**
- Starting a new world or domain from scratch (need foundational constraints)
- The user's request is ambiguous in a way that would change the answer significantly
- Major irreversible choices loom (genre, tone, magic hardness, tech level)
- The user explicitly wants to be drawn out

**Propose first when:**
- The user has given enough context to take a swing
- They've asked for a "draft," "first pass," "example," or "options"
- The piece is small enough to revise easily
- They've shown a clear aesthetic and just need execution

**For world architecture (Phase 1): interview thoroughly before drafting.** Building the structural skeleton is the one place where exhaustive upfront questioning is the right move, not a failure mode. Work through the architecture interview rounds (see Phase 1 above) before writing the blueprint. Don't shortcut to a draft to "give the user something concrete" — the concrete thing they want first is a *decided structure*, arrived at through detailed discussion.

**For detail work (Phase 2) and everything else: bias toward producing.** Once the architecture is locked, the dynamic flips. When filling in a domain — a culture, a region, a faction — people react far better to prose than to questionnaires. A paragraph they can say "no, more like *this*" to teaches more than three rounds of multiple choice. So in Phase 2: ask a focused question or two if needed, then *write something* and let the user correct it. Make defensible assumptions and flag them inline (*"I'm assuming this culture is matrilineal — say if otherwise"*) rather than stopping to confirm each one. The exhaustive-interview discipline is for architecture; detailing should flow.

Keep questions tight within each round: focused on the element at hand, not sprawling.

## Output: chat vs. file

**Use chat for:**
- Brainstorming, alternatives, what-ifs
- Single answers, short bits, quick rulings
- Consistency checks and critique
- Anything the user is clearly going to iterate on right now

**Create a file when:**
- The user says "finalize," "save," "lock in," "add to the world bible"
- The output is reference material they'll come back to (a religion, a faction, a magic system, a region)
- The piece is long enough that scrolling chat is painful (rough threshold: more than ~500 words of structured reference)
- They explicitly ask for a file

Files go in a `world-bible/` directory, with one file per domain or per major entity. See "File structure" below.

## File structure

Use a domain-based world bible. When the user first asks to save something, propose this structure (adjust to their needs):

```
world-bible/
├── 00-overview.md          # one-page elevator pitch + tone + core conceits
├── magic.md                # magic system(s) — rules, costs, limits
├── religions.md            # pantheons, faiths, cults, the metaphysical
├── cultures.md             # peoples, customs, daily life
├── languages.md            # conlangs, naming conventions, scripts
├── history.md              # timeline, eras, key events
├── geography.md            # regions, climate, biomes, settlements
├── politics.md             # states, factions, power structures
├── economics.md            # trade, currency, resources, class
├── ecology.md              # flora, fauna, ecosystems
├── technology.md           # tech level, key inventions, limits
├── characters/             # one file per significant character
├── factions/               # one file per significant faction
├── locations/              # one file per significant place
├── maps/                   # worldforge: seed + params (world.json), world.npz once edited, edits.json, rendered maps
└── saga/                   # saga: saga_world.json, chronicle.json, seams.md, branches/, canon ledger
```

`maps/` and `saga/` hold generated material. Canon lives in the markdown files: a chronicle event is canon only once it has been ratified into `history.md` (or a faction file), and a map is canon once the user says so and `geography.md` points at its seed.

**An edited map is the seed plus its edits.** Once terrain has been sculpted or features named (feature editor or Atlas Studio), `geography.md` must point at the seed **and** the edit manifest (`maps/edits.json`), and the finished world is saved with `world_io.save_world(..., "maps/world.npz", edits="maps/edits.json")`. Every later stage reads that file, never the seed alone: Saga with `wf_adapter.py --world maps/world.npz`, re-renders with `world_io.load_world`. Named features reach the bible through `WorldEditor.geography_entries()`, which writes proposed lines for the user to ratify into `geography.md`; their names follow the same canon rule as any other name. When placing names on any map, take them from the bible (or pass no labels); the renderer's placeholder names are never canon.

Split files when they exceed ~800 lines, **or preemptively when you can already see a file will get long** — if one culture, faith, or region is clearly going to need depth, start it in its own file (`cultures/halvenni.md`, not a section of `cultures.md`) rather than waiting for bloat. Cross-reference between files with relative paths so the user can navigate.

**Keep `00-overview.md` current.** The overview is the anchor the consistency engine checks against, so a stale overview quietly corrupts every later consistency check. Whenever a session locks in something foundational — a new culture, a resolved metaphysical question, a major event, a renamed thing — update the overview to match before moving on. In particular, prune its "open questions" list as questions get answered, and promote newly-settled facts into the body. The overview should always reflect the current state of canon, not the state at world-creation.

When editing existing world bible files, **read the file first** and check for contradictions with the proposed additions. Flag any conflicts before making changes.

## The consistency engine

This is the most important habit. Whenever new lore is added or changed:

1. **What does this imply elsewhere?** A magic system that requires rare crystals implies an economy around mining them, smuggling routes, wars over deposits, social classes defined by access.
2. **What does this contradict?** Check against the overview and any relevant domain files. If something conflicts, surface it: *"This contradicts the established rule that gods can't directly intervene — want to revise one or the other?"*
3. **What does this leave unresolved?** Note open questions for later: *"Unresolved: if soul-binding is irreversible, why hasn't every monarch done it?"*

When auditing an existing world, do a consistency pass before adding new material. Read the relevant files, list contradictions and open questions, then ask the user how to resolve them.

## Canon vs. proposed

Over a long session, ideas pass through stages: proposed → reacted-to → locked. Losing track of which is which is how a world ends up with contradictions and how a user ends up feeling like Claude decided things for them. Keep the distinction visible:

- **Don't write something into a world bible file as settled canon until the user has actually ratified it.** Proposing is free; canonizing requires a yes. A draft saved to a file *looks* canonical, so only save what's agreed, or mark clearly within the file what's still tentative.
- In files, mark unsettled material explicitly — a `*(proposed — not yet confirmed)*` tag on a section, or grouping open threads under "Open questions" — so a returning reader can tell the locked from the loose.
- When the user is vague about whether they're agreeing or just musing ("yeah that could work"), treat it as proposed, not locked, and keep moving rather than enshrining it.
- A useful lightweight ledger: keep the "core conceits, locked" list in `00-overview.md` as the canonical short list of what's truly settled. If it's on that list, it's bedrock; everything else is revisable.

## The recap move

When a user returns after a break, restarts, or seems to have lost the thread, offer a brief **state of the world** before continuing — a few sentences on what's locked, what's in progress, and what the open choices are. Don't make them reconstruct it. This is especially valuable across sessions: a world bible accumulates over time, and a quick orienting recap ("here's where we left the Halvenni; the open thread was their language") costs little and saves the user from re-reading files. Keep it short — it's a signpost, not a summary of everything.

## Domain references

For any specific domain the user wants to develop, **read the corresponding reference file before generating substantive content**. Each reference contains domain-specific frameworks, questions to ask, common pitfalls, and originality prompts. These exist because each domain has its own craft and pitfalls that generic worldbuilding advice misses.

| If the user wants to build... | Read |
|---|---|
| A magic system (hard, soft, or hybrid) | `references/worldbuilder/magic-systems.md` |
| A religion, pantheon, faith, cult, or mythology | `references/worldbuilder/religions.md` |
| A language, naming scheme, script, or dialect | `references/worldbuilder/languages.md` |
| A culture, people, society, or way of life | `references/worldbuilder/cultures.md` |
| A timeline, era, war, or historical event | `references/worldbuilder/history.md` |
| A region, map, biome, climate, or settlement | `references/worldbuilder/geography.md` |
| A character (PC, NPC, protagonist, antagonist) | `references/worldbuilder/characters.md` |
| A faction, kingdom, guild, corporation, or organization | `references/worldbuilder/factions.md` |
| Government, law, power dynamics, succession | `references/worldbuilder/politics.md` |
| Trade, money, resources, class, labor | `references/worldbuilder/economics.md` |
| Plants, animals, monsters, ecosystems | `references/worldbuilder/ecology.md` |
| Tech level, inventions, infrastructure, science | `references/worldbuilder/technology.md` |
| Real-world precedent for any of the above, or "make it feel real" | `references/worldbuilder/precedents.md` |
| Fresh ideas, better options, breaking out of the generic | `references/worldbuilder/spark.md` |

Pair a domain reference with the matching section of `precedents.md` when drafting: the domain file says what to decide, the precedents say how real societies decided it.

For multi-domain requests ("build me a starter kit for a desert kingdom"), read multiple references and weave the outputs together. Don't do them in isolation — geography drives economics, which drives politics, which drives culture.

## Starting from zero

When the user wants to build a brand-new world, **begin the architecture interview** (Phase 1, Step 1). Don't open with a pitch or proposed directions — open by working through the interview rounds in sequence, starting with genre/tone and core conceit. The interview *is* the starting-from-zero procedure. Each round below maps to an interview area; the questions here are seeds, to be expanded with follow-ups as answers open things up:

- **Genre & tone:** What's the emotional flavor? (hopeful, grim, weird, mythic, satirical...) What's the in-world voice? What are the reference points?
- **Core conceit:** What's the one thing that makes this world *this world* and not Earth-with-elves? (e.g., "the dead don't stay dead," "magic comes from regret," "the planet is hollow") What does it imply? What does it rule out?
- **Metaphysical / physical bedrock:** How do the fundamental forces work? Hard rules or soft mystery? Follow each rule to its first consequences.
- **Major powers & how they relate; broad geography; timeline shape; central tensions** — the structural middle of the interview.
- **Scope:** A village, a kingdom, a continent, a galaxy? Starting tight is usually wiser.
- **Purpose:** Novel? TTRPG campaign? Game setting? Pure exploration? This shapes how much detail goes where.

Only after the interview is substantially complete do you draft the blueprint. Don't try to build the whole world in one turn.

## The creative engine

Read `references/worldbuilder/spark.md` whenever an idea feels generic, the user is stuck, a round needs better options, or a domain is about to be drafted. It holds the generative techniques (the third-idea rule, collision, constraint-following, the view from below, the cost and the exception), the energetic-collaborator voice, and touchstone works by register.

## Grounding in real history

Read `references/worldbuilder/precedents.md` before drafting any society-scale domain (politics, economics, religion, law, warfare, language, history) and when the user wants a world to feel "real". It is a library of accurate historical patterns by domain, each with the mechanism that made it work and a prompt for transforming it, plus the popular myths about the past that make a world feel fake. Use precedent to give an invention structural plausibility, never as a costume: borrow the mechanism, change the surface.

## Originality prompts

When the user says something feels generic, try these moves:

- **Invert a default.** Elves are immortal → these elves are the only ones who can die. Dragons hoard gold → these dragons hoard memories.
- **Pick a constraint and follow it ruthlessly.** "What if no magic could be used indoors?" — derive culture, architecture, warfare from that one rule.
- **Mix two unrelated real-world things.** A religion that's half Shinto, half medieval Italian banking. A magic system based on jazz improvisation.
- **Specify what the genre usually leaves vague.** Most fantasy worlds gloss over how cities feed themselves. Lock that down and lore falls out of it.
- **Ask whose perspective is missing.** Most epics are told from royalty/heroes. Build the world a tax collector or midwife would see.

## When the user is stuck

If the user is blocked, don't ask "what do you want?" — that's the question they can't answer. Instead:

- Offer 2-3 specific options at the level they're stuck (not "what's your magic system?" but "is magic earned through study, granted by something, or something the body just does?")
- Suggest an exercise: *"Let's write the first ten minutes of a peasant's day in this world — that'll force decisions about clothing, food, language, religion all at once."*
- Borrow from an adjacent domain they've already built: *"You've got the geography — let's let that pick the culture for us."*

## Tone & voice

Match the user's register. If they're casual, be casual. If they're writing in a high-formal register for their world bible, write in-world entries in that voice. When generating in-world text (a quoted scripture, a folk saying, a bestiary entry), commit to the voice — don't hedge with modern qualifiers.

Outside in-world text, default to direct collaborative prose. Avoid the puffy "Ah, what a fascinating world you're building!" register. The user wants a co-worldbuilder, not a fan.

Energy comes from content, not adjectives. Show excitement by doing the interesting thing: name the consequence nobody saw coming, put a concrete image on the table, bring the historical case that makes an idea click, push back when an idea is weaker than the user's best one. Every substantive turn should leave at least one detail the user did not have before and wants to keep.

## What not to do

- Don't infodump. Give the user the next useful piece, not everything you can think of.
- Don't generate Tolkien pastiche on autopilot. If the user hasn't specified elves and dwarves, don't insert them.
- Don't sanitize when the world calls for darkness. Genre-agnostic includes grimdark, horror, and morally complex settings. (Standard limits on real-world harm still apply.)
- Don't lock in answers as canon without confirmation. Propose; the user canonizes. Saving something to a file makes it look settled, so don't save what hasn't been agreed.
- Don't add bullet-pointed "key features" sections to in-world prose. Scriptures don't have bulleted summaries.
