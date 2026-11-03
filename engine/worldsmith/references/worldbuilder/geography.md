# Geography & Maps

Geography is the floor everything else stands on. Climate determines crops, which determine population, which determine cities, which determine politics. Get the physical world wrong and everything built on top of it feels arbitrary.

## Before drawing the map

Resist the urge to start with a coastline. First answer:

- **What's the scale?** A river valley? A kingdom? A continent? A planet? A galaxy?
- **Where on the planet?** Equator or pole? Coast or interior? Mountain or plain?
- **What's the climate baseline?** Wet or dry? Hot or cold? Stable or extreme?
- **What's the geological story?** Old eroded mountains or young jagged ones? Volcanic? Tectonically active?
- **What's the most important geographic feature?** A great river, a mountain range, an inland sea, a desert, an archipelago — one defining feature is often enough to anchor a region.

Then draw.

## Plausibility basics

These get violated often in fantasy maps; violating them is fine if intentional, but know what you're doing:

- **Rivers flow downhill** and don't usually fork going downstream. They merge as they descend.
- **Mountain ranges have rain shadows.** Wet on the windward side, dry on the leeward. The world's great deserts are mostly behind mountains, in subtropical latitudes, or far from oceans.
- **Climate follows latitude and continentality.** Tropics near the equator, deserts around 30°, temperate at mid-latitudes, polar at the poles. Interiors are more extreme (continental); coasts more moderate (maritime).
- **Population follows water and farmland.** Cities sit on rivers, harbors, road junctions, or productive farmland. A city in a desert with no oasis needs an explanation.
- **Trade routes follow easiest paths.** Up rivers, across passes, along coasts, around rather than over mountains.

A weird geography (floating islands, perpetually-night hemispheres, infinite mountains) is fine — but think through how the world's life adapts.

## The regional layer

A world is usually best built as a collection of regions, each with a distinct character. For each region:

- **Climate:** What's the weather like across the year? When does it rain? Snow? Storm?
- **Biome:** Forest, plain, marsh, desert, tundra, jungle, mountain, coast?
- **Resources:** What does this region produce? What does it lack? (Iron, salt, timber, grain, gold, fish, horses...)
- **Habitability:** How many people can live here? How densely?
- **Borders:** What separates this region from neighbors? Mountains, rivers, deserts, deep forests?
- **Strategic value:** What makes it worth controlling — fertility, position, resources, sacred status?

Geography drives economics drives politics. Once you've placed a fertile basin and a salt mine, you've already implied trade routes, taxation, and probable wars.

## Settlements

Cities and towns aren't dropped on the map randomly. They exist because:

- **A geographic feature demanded it** — river crossing, harbor, pass, oasis, defensive height
- **A historical accident put it there** — a saint's birthplace, a battle site, an old fort
- **A resource pinned it down** — mine, sacred grove, healing spring, fishery

Settlement size is constrained by what surrounds it. A premodern city of 100,000 needs a hinterland of perhaps a million farmers feeding it. A city in a desert needs continuous food import. Place cities deliberately; their size implies the productivity of the land around them.

Useful settlement scale (premodern, rough):
- **Hamlet** (10-50): kin group, one or two trades
- **Village** (50-500): self-sufficient farming, perhaps a smith and a priest
- **Town** (500-5,000): market, multiple crafts, some specialization
- **Small city** (5,000-30,000): regional center, walls, garrison, multiple religious sites
- **Major city** (30,000-100,000): cosmopolitan, dependent on long-distance trade
- **Great city** (100,000+): rare in premodern settings; requires extensive infrastructure

In industrial or magical settings, these scale up dramatically — but specify the mechanism.

## Travel & distance

Decide *and stick to* travel realities. A common worldbuilding flaw: distances that change to suit plot.

Rough premodern travel rates:
- Foot, decent road, one person: 20-30 miles/day
- Mounted courier, relay system: 60-100 miles/day
- Marching army: 10-15 miles/day
- River barge downstream: 30-50 miles/day
- Sailing ship, open water with wind: 100-150 miles/day
- Caravan: 10-15 miles/day, with rest days

These compress with magic, infrastructure, or unusual conditions — but if a journey that should take a month takes a week, the world should explain why.

## Maps as artifacts vs. maps as reality

Two senses of "map":

1. **The cartographer's truth** — what's actually there in the world. The author/GM may know this perfectly.
2. **An in-world map** — what someone in the world has drawn. These have edges, blanks, mistakes, biases ("here be dragons"), political distortions.

Both have uses. In-world maps are often better for player handouts and narrative props — the gaps and errors carry meaning. The cartographer's truth is the consistency reference behind the scenes.

## When you don't need a map

Many great worlds work without one, or with only sketches. If the story is regional, a map of one country and vague gestures beyond may be plenty. Don't generate global maps just because; only build the geography the story will actually use.

## Common pitfalls

- **The single continent.** Most fantasy maps are one weirdly-shaped continent in an empty ocean. Earth has seven continents and the moon affects tides. Implications follow.
- **The blender of biomes.** Frozen tundra adjacent to tropical jungle adjacent to desert. Possible with mountain effects or magic, but usually unmotivated.
- **The everywhere river.** A river that flows wherever convenient. Decide watersheds — rivers in one basin drain to one sea.
- **The cities-without-food.** A "great desert city" with no apparent food supply. Where do the grain shipments come from? Who feeds the metropolis on the lifeless plain?
- **Ignoring scale.** A "kingdom" the size of France is very different from one the size of Texas or the EU. State the scale; the size of armies, the time to ride to the capital, and the diversity of subjects all change accordingly.
- **Coastlines too smooth or too jagged.** Real coastlines have inlets, peninsulas, islands. Generic fantasy coastlines often have neither.

## Originality moves

- **Let one feature dominate.** A world where one feature — a great wall of mountains, a colossal river, an endless forest, a perpetual storm — defines everything. Forces interesting culture.
- **Weird but consistent physics.** A world where the sun rises once per generation; a tide-locked planet; a continent on the back of something. Then *honor it* in every subsequent choice.
- **Make geography sacred.** Mountains are gods. Certain rivers cannot be crossed. The desert sings on the third night of summer. Geography that means something narrows the map's flavor sharply.
- **Make geography contested.** A border that no one agrees on. A region claimed by three powers, lived in by none. A holy site shared, uneasily.
- **Use lost geography.** A region that was lush a thousand years ago and is now desert. A sunken kingdom remembered in songs. A new island risen from the sea last year.

## Output format

For a regional file:

```
# [Region name]

## Overview
One paragraph: where it is, what it's like, what it's known for.

## Climate & terrain
Seasons, biome, water, weather extremes.

## Resources & limits
What it produces, what it lacks.

## Settlements
Major and notable, with one-line characterizations.

## Travel & infrastructure
Roads, rivers, passes, ports, sailing routes.

## Borders & neighbors
What's adjacent, what separates.

## Strategic & sacred geography
Why it matters, who wants it, what's holy.

## Open questions
```

For a whole-world geography file, keep it high-level (a paragraph per region) and let regional files carry the detail.
