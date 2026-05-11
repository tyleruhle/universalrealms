const express = require('express');
const { PutCommand, GetCommand, QueryCommand, UpdateCommand, ScanCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 } = require('uuid');
const dynamo      = require('../lib/dynamo');
const requireAuth = require('../middleware/auth');

const router   = express.Router();
const TABLE    = 'ur_scenarios';
const SLUG_RE  = /^[a-z][a-z0-9-]{1,49}$/;

function requireOwner(req, res, scenario) {
  if (scenario.authorUserId !== req.user.userId && !req.user.isAdmin)
    return res.status(403).json({ error: 'Not the scenario author.' });
  return null;
}

// GET /api/scenarios — list published public scenarios
router.get('/', async (req, res) => {
  try {
    const result = await dynamo.send(new ScanCommand({
      TableName: TABLE,
      FilterExpression: '#s = :pub AND visibility = :pub2',
      ExpressionAttributeNames: { '#s': 'state' },
      ExpressionAttributeValues: { ':pub': 'published', ':pub2': 'public' },
      ProjectionExpression: 'scenarioId, slug, #s, visibility, name, tagline, era, authorUserId, authorName, gameCount, createdAt, publishedAt, version',
      ExpressionAttributeNames: { '#s': 'state' },
    }));
    res.json((result.Items || []).sort((a, b) => new Date(b.publishedAt || b.createdAt) - new Date(a.publishedAt || a.createdAt)));
  } catch (err) {
    console.error('List scenarios error:', err);
    res.status(500).json({ error: 'Failed to fetch scenarios.' });
  }
});

// GET /api/scenarios/mine — scenarios authored by the logged-in user
router.get('/mine', requireAuth, async (req, res) => {
  try {
    const result = await dynamo.send(new QueryCommand({
      TableName: TABLE,
      IndexName: 'author-index',
      KeyConditionExpression: 'authorUserId = :uid',
      ExpressionAttributeValues: { ':uid': req.user.userId },
    }));
    res.json((result.Items || []).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)));
  } catch (err) {
    console.error('Mine scenarios error:', err);
    res.status(500).json({ error: 'Failed to fetch your scenarios.' });
  }
});

// GET /api/scenarios/:id — get a scenario (with content)
router.get('/:id', async (req, res) => {
  try {
    const result = await dynamo.send(new GetCommand({
      TableName: TABLE,
      Key: { scenarioId: req.params.id },
    }));
    if (!result.Item) return res.status(404).json({ error: 'Scenario not found.' });

    const s = result.Item;
    // Only return content to: author, or public/unlisted published scenarios
    const isAuthor = req.user?.userId === s.authorUserId;
    if (s.state !== 'published' && !isAuthor)
      return res.status(404).json({ error: 'Scenario not found.' });
    if (s.visibility === 'private' && !isAuthor)
      return res.status(403).json({ error: 'This scenario is private.' });

    res.json(s);
  } catch (err) {
    console.error('Get scenario error:', err);
    res.status(500).json({ error: 'Failed to fetch scenario.' });
  }
});

// POST /api/scenarios — create a new scenario draft
router.post('/', requireAuth, async (req, res) => {
  const { name, slug, tagline, era, description, visibility } = req.body;

  if (!name || !slug) return res.status(400).json({ error: 'Name and slug are required.' });
  if (!SLUG_RE.test(slug)) return res.status(400).json({ error: 'Slug must be lowercase letters, numbers, and hyphens (2–50 chars, start with a letter).' });

  try {
    // Check slug uniqueness
    const slugCheck = await dynamo.send(new QueryCommand({
      TableName: TABLE,
      IndexName: 'slug-index',
      KeyConditionExpression: 'slug = :s',
      ExpressionAttributeValues: { ':s': slug },
      Limit: 1,
    }));
    if (slugCheck.Items?.length > 0) return res.status(409).json({ error: 'That slug is already taken.' });

    const scenarioId = uuidv4();
    const now = new Date().toISOString();

    const item = {
      scenarioId,
      slug,
      name,
      tagline:      tagline     || '',
      era:          era         || '',
      description:  description || '',
      authorUserId: req.user.userId,
      authorName:   req.user.username,
      state:        'draft',
      visibility:   visibility || 'private',
      version:      '1.0.0',
      gameCount:    0,
      createdAt:    now,
      content: {
        statKeys:     ['Martial', 'Diplomacy', 'Stewardship', 'Intrigue', 'Learning'],
        statCap:      18,
        hardCap:      25,
        factions:     [],
        archetypes:   [],
        cultures:     [],
        traits:       {},
        combatTraits: [],
        combatEvents: [
          { roll:1, bonus:0, icon:'🌾', label:'Uneventful Upbringing',   desc:'No noteworthy combat experience.' },
          { roll:2, bonus:0, icon:'🌾', label:'Uneventful Upbringing',   desc:'No noteworthy combat experience.' },
          { roll:3, bonus:1, icon:'🐗', label:'Hunting Accident',         desc:'A boar, a cornered wolf, a riding fall. They learned about pain — and getting back up.' },
          { roll:4, bonus:1, icon:'🥊', label:'Formative Brawl',          desc:'A street fight, a tavern confrontation. Not training — but real.' },
          { roll:5, bonus:2, icon:'⚔',  label:'Border Skirmish',          desc:'A raid, a bandit attack. They fought before they were ready.' },
          { roll:6, bonus:3, icon:'🔥', label:'Survived Serious Violence', desc:'Ambush, siege, a battle they had no business being in. They are harder for it.' },
        ],
      },
    };

    await dynamo.send(new PutCommand({ TableName: TABLE, Item: item }));
    res.json(item);
  } catch (err) {
    console.error('Create scenario error:', err);
    res.status(500).json({ error: 'Failed to create scenario.' });
  }
});

// PATCH /api/scenarios/:id — update scenario metadata or content
router.patch('/:id', requireAuth, async (req, res) => {
  try {
    const existing = await dynamo.send(new GetCommand({ TableName: TABLE, Key: { scenarioId: req.params.id } }));
    if (!existing.Item) return res.status(404).json({ error: 'Scenario not found.' });
    const err = requireOwner(req, res, existing.Item);
    if (err) return;

    const allowed = ['name', 'tagline', 'era', 'description', 'visibility', 'content'];
    const updates = [];
    const vals    = {};
    const names   = {};

    for (const key of allowed) {
      if (req.body[key] !== undefined) {
        const safe = key === 'name' ? '#n' : `#${key}`;
        updates.push(`${safe} = :${key}`);
        vals[`:${key}`] = req.body[key];
        if (key === 'name') names['#n'] = 'name';
        else names[`#${key}`] = key;
      }
    }

    if (!updates.length) return res.status(400).json({ error: 'Nothing to update.' });

    updates.push('#upd = :upd');
    vals[':upd'] = new Date().toISOString();
    names['#upd'] = 'updatedAt';

    await dynamo.send(new UpdateCommand({
      TableName: TABLE,
      Key: { scenarioId: req.params.id },
      UpdateExpression: `SET ${updates.join(', ')}`,
      ExpressionAttributeValues: vals,
      ExpressionAttributeNames: names,
    }));

    res.json({ ok: true });
  } catch (err) {
    console.error('Update scenario error:', err);
    res.status(500).json({ error: 'Failed to update scenario.' });
  }
});

// POST /api/scenarios/:id/publish — publish a draft scenario
router.post('/:id/publish', requireAuth, async (req, res) => {
  try {
    const existing = await dynamo.send(new GetCommand({ TableName: TABLE, Key: { scenarioId: req.params.id } }));
    if (!existing.Item) return res.status(404).json({ error: 'Scenario not found.' });
    const err = requireOwner(req, res, existing.Item);
    if (err) return;

    const s = existing.Item;
    if (!s.content?.factions?.length)    return res.status(400).json({ error: 'Add at least one faction before publishing.' });
    if (!s.content?.archetypes?.length)  return res.status(400).json({ error: 'Add at least one archetype before publishing.' });

    await dynamo.send(new UpdateCommand({
      TableName: TABLE,
      Key: { scenarioId: req.params.id },
      UpdateExpression: 'SET #s = :pub, publishedAt = :now, visibility = :vis',
      ExpressionAttributeNames: { '#s': 'state' },
      ExpressionAttributeValues: { ':pub': 'published', ':now': new Date().toISOString(), ':vis': req.body.visibility || 'public' },
    }));

    res.json({ ok: true });
  } catch (err) {
    console.error('Publish scenario error:', err);
    res.status(500).json({ error: 'Failed to publish scenario.' });
  }
});

module.exports = router;
