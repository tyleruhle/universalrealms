/**
 * Seed script — Anno Domini 1066 scenario
 * Run once on the server:  node scripts/seed-1066.js
 * Requires .env to be present with AWS_REGION set (IAM role handles auth).
 */
require('dotenv').config({ path: require('path').join(__dirname, '../.env') });
const { DynamoDBClient }       = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, PutCommand, QueryCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 }           = require('uuid');

const client = new DynamoDBClient({ region: process.env.AWS_REGION || 'us-east-2' });
const dynamo = DynamoDBDocumentClient.from(client);

const SLUG = 'anno-domini-1066';
const TABLE = 'ur_scenarios';

const CONTENT = {
  statKeys: ['Martial', 'Stewardship', 'Diplomacy', 'Intrigue', 'Learning'],
  statCap:  18,
  hardCap:  25,

  factions: [
    { id:'noble_house',    icon:'🏰', label:'Noble House',    rank:'Baron / Count',   gold:'200–400',   army:'500–2,000 levies',  desc:'Land, levies, and loyalty define your power.' },
    { id:'military_order', icon:'⚔',  label:'Military Order', rank:'Commander',       gold:'150–300',   army:'200–800 elite',     desc:'Small but elite. Your soldiers are worth three ordinary levies.' },
    { id:'merchant_house', icon:'💰', label:'Merchant House', rank:'Master Merchant', gold:'500–1,000', army:'0–100 guards',      desc:'Trade routes, ports, and markets are your battlefield.' },
    { id:'religious_order',icon:'✝',  label:'Religious Order',rank:'Bishop / Abbot',  gold:'300–500',   army:'0 (influence only)',desc:'No army, but the Pope\'s ear. Influence and spiritual authority.' },
    { id:'city_state',     icon:'🏛', label:'City-State',     rank:'Podesta / Consul',gold:'400–700',   army:'300–1,500 militia', desc:'Trade and walls defend what diplomacy and gold cannot.' },
  ],

  archetypes: [
    { id:'warlord',      name:'The Warlord',        icon:'⚔',  bonuses:{Martial:3},                           pc:12, primary:'Martial',      bg:'Raised in campaign. Knows war from childhood.',          flavor:'They have never known a home that wasn\'t a fortress or a field. War is not something that happens to them — it is something they make happen.' },
    { id:'knight',       name:'The Knight',          icon:'🏇', bonuses:{Martial:2,Intrigue:1},                pc:14, primary:'Martial',      bg:'Tournament trained. Skilled fighter, reads enemies.',     flavor:'The lists taught them how to read a man before the charge lands. What they study in the arena, they apply in the council chamber.' },
    { id:'border_lord',  name:'The Border Lord',     icon:'🗺', bonuses:{Martial:2,Stewardship:2},             pc:10, primary:'Martial',      bg:'Ran a frontier. Fights and administers equally.',         flavor:'The border is a place where the sword and the ledger must both be sharp. They learned to hold ground and count grain in the same breath.' },
    { id:'crusader',     name:'The Crusader',        icon:'🛡', bonuses:{Martial:2,Learning:2},                pc:12, primary:'Martial',      bg:'Holy war veteran. Faith and sword in equal measure.',     flavor:'They have fought in the name of God and studied what they fought for. The Psalms and the siege manual sit side by side on their shelf.' },
    { id:'raider',       name:'The Raider',          icon:'🪓', bonuses:{Martial:2,Intrigue:2},                pc:13, primary:'Martial',      bg:'Born to raid. Fast, brutal, unpredictable.',              flavor:'They did not learn war in a keep or a tournament yard. They learned it on fast boats and burning villages, where hesitation is death.' },
    { id:'siege_eng',    name:'The Siege Engineer',  icon:'🪨', bonuses:{Martial:2,Stewardship:1,Learning:1}, pc:8,  primary:'Martial',      bg:'Built walls and broke them. The mathematics of violence.', flavor:'They see every fortress as a problem waiting to be solved. Given time, timber, and men, they have never met a wall they could not bring down.' },
    { id:'cav_lord',     name:'The Cavalry Lord',    icon:'🐴', bonuses:{Martial:3,Diplomacy:1},               pc:11, primary:'Martial',      bg:'Born to the saddle. Commands mounted forces.',            flavor:'In the saddle they are a different creature entirely — faster, more dangerous, impossible to pin. On foot they are merely dangerous.' },
    { id:'courtier',     name:'The Courtier',        icon:'👑', bonuses:{Diplomacy:3},                         pc:6,  primary:'Diplomacy',   bg:'Raised at a great court. Silver-tongued.',                 flavor:'Courts are their native terrain — whispered alliances, strategic marriages, the smile that conceals the knife. They have never needed a sword.' },
    { id:'merch_prince', name:'The Merchant Prince', icon:'💰', bonuses:{Diplomacy:2,Stewardship:2},           pc:6,  primary:'Diplomacy',   bg:'Trade networks and foreign contacts.',                     flavor:'Every foreign tongue they speak is a trade route. Every ally they cultivate is an investment. The world is a ledger of favors and debts.' },
    { id:'diplomat',     name:'The Diplomat',        icon:'🕊', bonuses:{Diplomacy:3,Learning:1},              pc:6,  primary:'Diplomacy',   bg:'Treaty negotiator. Knows canon law and custom.',           flavor:'They have brokered peace between men who wanted blood. They know the exact article of canon law that turns a war into a negotiation.' },
    { id:'herald',       name:'The Herald',          icon:'📯', bonuses:{Diplomacy:2,Learning:2},              pc:5,  primary:'Diplomacy',   bg:'Envoy between great houses. Knows every court.',           flavor:'They have ridden into enemy camps under a flag of truce and left with more than they arrived with. Words are their currency and they are never poor.' },
    { id:'matchmaker',   name:'The Match-Maker',     icon:'💍', bonuses:{Diplomacy:2,Intrigue:2},              pc:5,  primary:'Diplomacy',   bg:'Arranged noble marriages. Knows bloodlines.',              flavor:'They see every unmarried noble as an opportunity and every alliance as a chain of future obligations. They have never wasted a daughter.' },
    { id:'admin',        name:'The Administrator',   icon:'📋', bonuses:{Stewardship:3,Learning:1},            pc:6,  primary:'Stewardship', bg:'Ran estates before knowing war. Economy is the battlefield.', flavor:'The harvest yield and the garrison strength are the same equation to them. They have run provinces while others ran armies — and they have won.' },
    { id:'trader',       name:'The Trader',          icon:'⚖',  bonuses:{Stewardship:2,Diplomacy:2},           pc:6,  primary:'Stewardship', bg:'Merchant background. Reads people and ledgers.',           flavor:'Every market taught them something about human nature. Every negotiation sharpened their sense of when a man is lying about his price.' },
    { id:'quartermaster',name:'The Quartermaster',   icon:'🧱', bonuses:{Stewardship:3,Martial:1},             pc:7,  primary:'Stewardship', bg:'Supplied armies in the field. Logistics wins wars.',       flavor:'They have watched brilliant generals lose wars because they ran out of grain in October. They have never run out of grain in October.' },
    { id:'harbor',       name:'The Harbor Master',   icon:'⚓', bonuses:{Stewardship:2,Diplomacy:1,Learning:1},pc:5,  primary:'Stewardship', bg:'Ran a major port. Trade, ships, foreign relations.',       flavor:'Every ship that entered their harbor was an intelligence report. They know what moves, what it costs, and who profits from keeping it moving.' },
    { id:'schemer',      name:'The Schemer',         icon:'🕸', bonuses:{Intrigue:3},                          pc:8,  primary:'Intrigue',    bg:'Forger, poisoner, assassin\'s sponsor.',                   flavor:'They have never needed to be in the room when things happen. They arrange events from a distance, through intermediaries, through information.' },
    { id:'spymaster',    name:'The Spymaster',       icon:'🌑', bonuses:{Intrigue:2,Diplomacy:2},              pc:8,  primary:'Intrigue',    bg:'Intelligence networks. Knows everyone\'s secrets.',        flavor:'They built a network before they built a reputation. Everyone who matters owes them something — or fears them.' },
    { id:'assassin',     name:'The Assassin',        icon:'🗡', bonuses:{Intrigue:2},                          pc:16, primary:'Intrigue',    bg:'Trained killer. Exceptional personal combat.',             flavor:'What they know about politics they learned from studying who to remove and when. Every other skill is subordinate to the one they were made for.' },
    { id:'blackmailer',  name:'The Blackmailer',     icon:'🖋', bonuses:{Intrigue:2,Stewardship:2},            pc:6,  primary:'Intrigue',    bg:'Collected debts and secrets in equal measure.',            flavor:'They never need to threaten anyone directly. The documents exist. The witnesses are available. Everyone who has dealt with them knows this.' },
    { id:'cleric',       name:'The Cleric',          icon:'✝',  bonuses:{Learning:3,Diplomacy:1},              pc:4,  primary:'Learning',    bg:'Church education. Canon law, Latin, church politics.',     flavor:'The Church gave them the keys to every door — Latin opens archives, canon law opens courts, and faith opens hearts. They never needed a sword.' },
    { id:'scholar',      name:'The Scholar',         icon:'📚', bonuses:{Learning:3,Stewardship:1},            pc:4,  primary:'Learning',    bg:'University trained. Greek texts, engineering.',            flavor:'They have read things most lords cannot imagine exist. Engineering, geometry, Arabic astronomy. Knowledge is a force multiplier.' },
    { id:'physician',    name:'The Physician',       icon:'⚕',  bonuses:{Learning:2,Intrigue:2},               pc:6,  primary:'Learning',    bg:'Medical knowledge. Useful in plagues.',                    flavor:'They know the body — its humors, its weaknesses, what heals it and what ends it. That knowledge has uses in peacetime and more interesting uses in war.' },
    { id:'inquisitor',   name:'The Inquisitor',      icon:'🔎', bonuses:{Learning:2,Intrigue:2},               pc:7,  primary:'Learning',    bg:'Church investigator. Hunts heretics and forged claims.',   flavor:'They have been trained to find the truth in whatever form it takes — in testimony, in texts, in the small inconsistencies that liars always leave behind.' },
    { id:'astronomer',   name:'The Astronomer',      icon:'🔭', bonuses:{Learning:3,Stewardship:1},            pc:4,  primary:'Learning',    bg:'Star-reader, calendar-keeper, advisor to kings.',          flavor:'They know when to plant, when to march, when the tides favor a crossing and when they do not. Kings pay well for this kind of certainty.' },
  ],

  cultures: [
    { id:'anglo',   label:'Anglo-Saxon',       region:'England',          bonuses:'+1 Levy, +1 Logistics',                    combat:'+1 shieldwall defense on prepared positions',            context:'War of succession — three claimants contest the throne' },
    { id:'norman',  label:'Norman',            region:'Normandy',         bonuses:'+2 Cavalry, +1 Siege',                     combat:'+2 cavalry charge (first charge) on open ground',        context:'Duke William assembles his invasion fleet' },
    { id:'scandi',  label:'Scandinavian',      region:'Norway/Denmark',   bonuses:'+3 Naval, +2 Raid',                        combat:'+3 naval combat, +1 raid. Fearless in shore assaults',   context:'Hardrada campaigns in the north. Longships on the Humber' },
    { id:'german',  label:'German',            region:'Holy Roman Empire', bonuses:'+2 Heavy Infantry',                       combat:'Disciplined heavy infantry hold ground in open battle',   context:'Henry IV feuds with Pope Gregory VII' },
    { id:'french',  label:'French',            region:'France',           bonuses:'+1 Diplomacy, +1 Naval',                   combat:'No specific cultural combat note',                        context:'King Philip I watches Normandy — and waits' },
    { id:'iberian', label:'Iberian',           region:'Iberia',           bonuses:'+1 Cavalry, Reconquista bonus',            combat:'Reconquista veterans fight with conviction on home soil', context:'The Reconquista grinds on. Moors and Christians share a frontier' },
    { id:'byz',     label:'Byzantine',         region:'Byzantine Empire', bonuses:'+2 Intrigue, +1 Diplomacy',               combat:'+2 counter-attack after feigned retreat. Greek Fire: +2 naval', context:'Manzikert\'s aftermath. Seljuk pressure mounts' },
    { id:'celtic',  label:'Celtic',            region:'Scotland/Ireland', bonuses:'+2 Raid, +1 Guerrilla',                   combat:'+2 guerrilla in hills/forests. +1 raid',                  context:'English succession chaos creates opportunity' },
    { id:'italian', label:'Italian',           region:'Italy (North)',    bonuses:'+2 Trade, +1 Diplomacy',                   combat:'No specific cultural combat note',                        context:'Pope Alexander II watches the HRE. City-states grow rich' },
    { id:'rus',     label:'Rus / Norse-Slavic',region:'Kievan Rus',       bonuses:'+1 Infantry, +2 Trade (Varangian route)', combat:'+1 heavy infantry. +2 in forest terrain (taiga)',         context:'Yaroslavichi coalition fractures. Cumans raid from the south' },
    { id:'steppe',  label:'Steppe / Nomadic',  region:'Cuman Steppe',     bonuses:'+3 Cavalry, +2 Raid',                      combat:'+2 cavalry pursuit. +3 raid. Cannot be besieged in open steppe', context:'Dominant steppe power. Raids Rus and Byzantium annually' },
    { id:'caucas',  label:'Georgian/Armenian', region:'Caucasus',         bonuses:'+2 Mountain combat, +1 Cavalry',           combat:'+2 mountain combat. Negates enemy cavalry in highlands', context:'King Bagrat IV holds off Seljuk pressure' },
    { id:'arab',    label:'Arab / Bedouin',    region:'Arabia',           bonuses:'+2 Cavalry (desert), Pilgrimage income',  combat:'+2 in desert/hot terrain. Excellent light cavalry',       context:'Fatimid, Abbasid, and Seljuk all claim authority' },
    { id:'persian', label:'Seljuk / Persian',  region:'Persia',           bonuses:'+2 Cavalry, +1 Admin, Silk Road income',  combat:'+2 cavalry (composite bow). +1 in desert/steppe',         context:'Richest eastern region. Persian administrators keep the empire running' },
    { id:'fatimid', label:'Egyptian / Fatimid',region:'Egypt',            bonuses:'+1 Naval (Mediterranean), +2 Trade',       combat:'+1 naval (Mediterranean). Sudanese/Turkish mercs give flexibility', context:'Cairo fabulously wealthy. The Vizier holds real power' },
    { id:'berber',  label:'Berber / Almoravid',region:'North Africa',     bonuses:'+2 Coastal Raid, +1 Desert combat',        combat:'+2 coastal raid. +1 desert combat. Ships at half travel time', context:'Almoravid empire rising. Will invade Iberia within 5 years' },
  ],

  traits: {
    Martial: [
      { id:'iron_const',   name:'Iron Constitution',  icon:'🛡', flavor:'Hardship forged this body before they ever held a sword.',                        bonus:'+1 to all personal combat rolls.' },
      { id:'warlords_eye', name:'Warlord\'s Eye',      icon:'👁', flavor:'Even as a child they could read a field — where the weakness was, where the line would break.', bonus:'+1 to battle rolls when commanding an army.' },
      { id:'drilled',      name:'Drilled from Birth',  icon:'⚔',  flavor:'Sword drill at dawn, lance practice at dusk. War before letters.',               bonus:'+2 to personal combat rolls in duels.' },
      { id:'fear_god',     name:'Fear of God',         icon:'✝',  flavor:'They fight because God placed a sword in their hand.',                             bonus:'+1 to all battle rolls when defending own territory.' },
      { id:'hunter_born',  name:'Hunter Born',         icon:'🏹', flavor:'Forests and marshes hold no fear — terrain is a language they read fluently.',    bonus:'+2 to battle rolls in forest, marsh, or rough terrain.' },
      { id:'siege_sense',  name:'Siege Sense',         icon:'🏰', flavor:'They spent years watching walls fall and walls hold. They know the difference.',   bonus:'+1 to siege attack rolls.' },
      { id:'shield_train', name:'Shield Trained',      icon:'🛡', flavor:'Hours behind a shield taught them something most fighters never learn: how to wait.', bonus:'+1 to personal combat rolls when defending in a duel.' },
      { id:'cav_bred',     name:'Cavalry Bred',        icon:'🐴', flavor:'Raised with horses before they could walk properly. The saddle is home.',          bonus:'+1 to battle rolls when leading a cavalry-dominant force.' },
      { id:'tireless',     name:'Tireless Soldier',    icon:'🥾', flavor:'They can march further and fight longer than anyone expects.',                     bonus:'+1 to battle rolls in engagements past the first round.' },
    ],
    Stewardship: [
      { id:'ledger_mind', name:'Ledger Mind',     icon:'📊', flavor:'Numbers came naturally — taxes, yields, debts. A holding\'s health read in an afternoon.', bonus:'+1 to all economy and tax-collection rolls.' },
      { id:'harvest',     name:'Harvest Sense',   icon:'🌾', flavor:'Raised among fields and mills — they understand the rhythms that keep armies fed.',        bonus:'+1 to all Stewardship rolls involving food and supply.' },
      { id:'iron_purse',  name:'Iron Purse',      icon:'💰', flavor:'A lord who cannot account for every coin is already a lord in debt.',                     bonus:'+1 to Stewardship rolls involving treasury management.' },
      { id:'builder',     name:'Master Builder',  icon:'🏗',  flavor:'They apprenticed under engineers. They know how walls rise and why they fall.',           bonus:'+1 to all construction and building rolls.' },
      { id:'trade_inst',  name:'Trade Instinct',  icon:'⚖',  flavor:'A childhood in markets gave them a nose for value and who was cheating whom.',            bonus:'+1 to all trade and market Stewardship rolls.' },
      { id:'supply',      name:'Supply Runner',   icon:'🛒', flavor:'They know how to move goods through difficult country under difficult conditions.',        bonus:'+1 to Stewardship rolls for supplying armies in the field.' },
      { id:'estate',      name:'Estate Born',     icon:'🌻', flavor:'They grew up managing a small estate and learned every detail of how one runs.',           bonus:'+1 to Stewardship rolls for managing settlements.' },
      { id:'coin',        name:'Coin Counter',    icon:'🪙', flavor:'They can spot a debased coin at ten paces and a dishonest ledger in five minutes.',        bonus:'+1 to Stewardship rolls when detecting financial fraud.' },
      { id:'road',        name:'Road Builder',    icon:'🛤',  flavor:'They think about movement — how armies march, how goods flow, how provinces connect.',     bonus:'+1 to Stewardship rolls for infrastructure projects.' },
    ],
    Diplomacy: [
      { id:'silver',     name:'Silver Tongue',  icon:'🗣', flavor:'Words come to them like water — smooth, persistent, wearing down the hardest stone.',     bonus:'+1 to all diplomacy rolls.' },
      { id:'noble_bear', name:'Noble Bearing',  icon:'👑', flavor:'Their bearing commands rooms. Greater men take notice.',                                  bonus:'+1 to diplomacy rolls when negotiating with equal or higher rank.' },
      { id:'peacemaker', name:'Peacemaker',     icon:'🕊', flavor:'Even as a child they found the middle ground — the truce that held.',                     bonus:'+1 to diplomacy rolls when proposing or mediating a truce.' },
      { id:'feast_lord', name:'Feast Lord',     icon:'🍷', flavor:'Full bellies and good wine open doors that siege engines cannot.',                        bonus:'+1 to diplomacy rolls made at or following a hosted feast.' },
      { id:'courtly',    name:'Courtly Grace',  icon:'🎭', flavor:'Courts, councils, ceremonies — they move through them as if born to the marble floor.',   bonus:'+1 to diplomacy rolls in formal court or council settings.' },
      { id:'trusted',    name:'Trusted Face',   icon:'🤝', flavor:'Something about them invites confidence. They are not necessarily honest — just convincing.', bonus:'+1 to diplomacy rolls when making a first approach to a new faction.' },
      { id:'marriage',   name:'Marriage Minded',icon:'💍', flavor:'They understand dynastic politics at an instinctive level.',                              bonus:'+2 to diplomacy rolls involving marriage proposals.' },
      { id:'crowd',      name:'Crowd Speaker',  icon:'📣', flavor:'They can address a crowd and make every person in it feel spoken to personally.',          bonus:'+1 to diplomacy rolls when addressing large groups.' },
      { id:'oath',       name:'Oath Keeper',    icon:'📜', flavor:'They have never broken a sworn oath. The reputation precedes them.',                      bonus:'+1 to diplomacy rolls when calling in a sworn alliance or favor.' },
    ],
    Intrigue: [
      { id:'shadow',    name:'Shadow Walker',  icon:'🌑', flavor:'They learned young to move unseen — through halls, crowds, the spaces between loyalties.', bonus:'+1 to all espionage rolls.' },
      { id:'forger',    name:'Forger\'s Hand', icon:'🖋', flavor:'Scripts, seals, signatures — their eye for imitation was not for noble purposes.',          bonus:'+2 to Intrigue rolls when forging documents or fabricating claims.' },
      { id:'poison',    name:'Poison Lore',    icon:'🧪', flavor:'Someone taught this character which plants kill quietly.',                                  bonus:'+2 to assassination attempt rolls.' },
      { id:'web',       name:'Web Weaver',     icon:'🕸', flavor:'Even in childhood they collected secrets — favors, overheard words, accumulated debts.',    bonus:'+1 to Intrigue rolls when running or expanding a spy network.' },
      { id:'iron_mask', name:'Iron Mask',      icon:'🎭', flavor:'No one has ever read this face. All have tried. All have failed.',                         bonus:'+1 to Intrigue rolls involving deception or misdirection.' },
      { id:'pick',      name:'Light Fingers',  icon:'🤏', flavor:'They learned early that information is everywhere — in pockets, desks, unlocked rooms.',    bonus:'+1 to Intrigue rolls when stealing documents or intercepting messages.' },
      { id:'backstab',  name:'Backstabber',    icon:'🗡', flavor:'They do not fight fair and they have never pretended otherwise.',                           bonus:'+1 to personal combat rolls when attacking an unsuspecting target.' },
      { id:'rumor',     name:'Rumor Monger',   icon:'👂', flavor:'They know exactly how fast a well-placed lie travels and where it ends up.',               bonus:'+1 to Intrigue rolls when spreading false information.' },
      { id:'patient',   name:'Patient Planner',icon:'⏳', flavor:'They think in seasons, not days. The trap was laid months ago.',                           bonus:'+1 to Intrigue rolls for schemes that span more than one season.' },
    ],
    Learning: [
      { id:'scholar_gift', name:'Scholar\'s Gift',      icon:'📚', flavor:'Letters came early, languages faster. They had read more than most lords by fifteen.', bonus:'+1 to all scholarly and research rolls.' },
      { id:'physician',    name:'Physician\'s Touch',    icon:'⚕',  flavor:'They studied the body — bones, humors, wounds. Useful when war is permanent.',        bonus:'+1 to Learning rolls involving medicine, wounds, or disease.' },
      { id:'canonist',     name:'The Canonist',          icon:'📖', flavor:'Canon law, papal decrees — they know which verse to cite to which priest.',           bonus:'+2 to Learning rolls involving church law or papal matters.' },
      { id:'nat_phil',     name:'Natural Philosopher',   icon:'🔭', flavor:'Stars, tides, siege angles — they see patterns and bend them to advantage.',          bonus:'+1 to Learning rolls involving engineering or natural science.' },
      { id:'linguist',     name:'Linguist',              icon:'🌍', flavor:'Latin, Arabic, Norse, Greek — language is the first bridge and the first weapon.',     bonus:'+1 to all Diplomacy rolls with foreign cultures.' },
      { id:'cartog',       name:'Cartographer',          icon:'🗺', flavor:'They have studied more maps than most men have seen. They know where things are.',     bonus:'+1 to Learning rolls involving navigation or campaign planning.' },
      { id:'theol',        name:'Theologian',            icon:'✝',  flavor:'They have read the arguments on both sides of every schism. Faith is a tool.',        bonus:'+1 to Diplomacy rolls with religious factions.' },
      { id:'code',         name:'Code Breaker',          icon:'🔑', flavor:'Ciphers, patterns, hidden meanings — their mind finds structure in apparent chaos.',   bonus:'+1 to Intrigue rolls when decoding intercepted messages.' },
      { id:'mil_hist',     name:'Military Historian',    icon:'📜', flavor:'They have read every battle account they could find. Theory and practice meet.',       bonus:'+1 to battle rolls when facing a tactically familiar situation (mod discretion).' },
    ],
  },

  combatTraits: [
    { id:'shield_anchor', name:'Shield Wall Anchor', icon:'🛡', flavor:'Where others step back, this one plants their feet. Lines hold because they hold first.', bonus:'All friendly battle dice in a defensive formation gain +1. Holding the defender role for 2+ consecutive turns adds a further +1 (stacks once). Immune to forced-retreat on a Narrow Victory.', use:'Defensive battles and prolonged sieges' },
    { id:'cav_master',    name:'Cavalry Master',     icon:'🐴', flavor:'Horse and rider became one thing. The charge does not break — it transforms.',             bonus:'Cavalry-led charges grant +1 to all battle dice in the opening round. Cavalry pursuit after a rout adds 5% additional casualties.', use:'Open-field offensives and pursuit' },
    { id:'siege_break',   name:'Siege Breaker',      icon:'🪨', flavor:'Walls are a problem of patience and geometry. They learned both before they learned mercy.', bonus:'Siege attack rolls gain +1. Siege engines deal +3 total (instead of +2). Attacker attrition reduced 25% during their command.', use:'Assault operations and fortification reduction' },
    { id:'duelist',       name:'Duelist',            icon:'⚔',  flavor:'They have won more single combats than most men fight in a lifetime. The body remembers.', bonus:'+3 to personal combat rolls in duels, assassination defense, and heroic assault. Once per duel, may force a re-roll on the opponent\'s highest die.', use:'Duels, assassination defense and front-line heroics' },
    { id:'ghost',         name:'Ghost of the Field', icon:'🌑', flavor:'They move armies the way a shadow moves — without announcement, without warning, then present.', bonus:'Ambush DC reduced from 12 to 9. Hidden forces 1-in-6 less likely to be detected. Army movement in forest/marsh costs 1 fewer in-game day.', use:'Ambushes, flanking and covert advance' },
  ],

  combatEvents: [
    { roll:1, bonus:0, icon:'🌾', label:'Uneventful Upbringing',   desc:'No noteworthy combat experience. The archetype\'s training is the whole story.' },
    { roll:2, bonus:0, icon:'🌾', label:'Uneventful Upbringing',   desc:'No noteworthy combat experience. The archetype\'s training is the whole story.' },
    { roll:3, bonus:1, icon:'🐗', label:'Hunting Accident',         desc:'A boar, a cornered wolf, a riding fall that could have killed them. They learned something about pain — and about getting back up.' },
    { roll:4, bonus:1, icon:'🥊', label:'Formative Brawl',          desc:'A street fight, a tavern confrontation, a boundary dispute that turned bloody. Not training — but real.' },
    { roll:5, bonus:2, icon:'⚔',  label:'Border Skirmish',          desc:'A raid, a bandit attack, a night alarm on the frontier. They fought before they were ready and came out the other side.' },
    { roll:6, bonus:3, icon:'🔥', label:'Survived Serious Violence', desc:'Ambush, siege, a battle they had no business being in. Whatever happened, they are harder for it — and they carry the scars to prove it.' },
  ],
};

async function seed() {
  // Check if already seeded
  const check = await dynamo.send(new QueryCommand({
    TableName: TABLE,
    IndexName: 'slug-index',
    KeyConditionExpression: 'slug = :s',
    ExpressionAttributeValues: { ':s': SLUG },
    Limit: 1,
  }));

  if (check.Items?.length > 0) {
    console.log('✓ Anno Domini 1066 already exists:', check.Items[0].scenarioId);
    return;
  }

  const scenarioId = uuidv4();
  const now        = new Date().toISOString();

  const item = {
    scenarioId,
    slug:        SLUG,
    name:        'Anno Domini 1066',
    tagline:     'A continent on the eve of conquest.',
    era:         '1066 AD',
    description: 'Europe in 1066 — a single year that changed everything. Three kings claim England, the Pope feuds with the Emperor, the Normans are about to remake the world. This is the flagship Universal Realms scenario: a political, military, and dynastic sandbox set at the hinge point of medieval history.',
    authorUserId: 'system',
    authorName:   'Universal Realms',
    state:        'published',
    visibility:   'public',
    version:      '1.0.0',
    gameCount:    0,
    createdAt:    now,
    publishedAt:  now,
    content:      CONTENT,
  };

  await dynamo.send(new PutCommand({ TableName: TABLE, Item: item }));
  console.log('✓ Seeded Anno Domini 1066 — scenarioId:', scenarioId);
}

seed().catch(err => { console.error('Seed failed:', err); process.exit(1); });
