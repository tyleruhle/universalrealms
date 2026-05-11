const express = require('express');
const { PutCommand, GetCommand, QueryCommand, UpdateCommand, DeleteCommand, ScanCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 } = require('uuid');
const dynamo      = require('../lib/dynamo');
const requireAuth = require('../middleware/auth');

const router         = express.Router();
const GAMES_TABLE    = 'ur_games';
const MEMBERS_TABLE  = 'ur_game_members';
const CHRONICLE_TABLE= 'ur_game_chronicle';
const SCENARIOS_TABLE= 'ur_scenarios';
const SLUG_RE        = /^[a-z][a-z0-9-]{1,49}$/;

async function getGame(gameId) {
  const r = await dynamo.send(new GetCommand({ TableName: GAMES_TABLE, Key: { gameId } }));
  return r.Item || null;
}

async function getMember(gameId, userId) {
  const r = await dynamo.send(new GetCommand({ TableName: MEMBERS_TABLE, Key: { gameId, userId } }));
  return r.Item || null;
}

function isOwnerOrMod(member) {
  return member && (member.role === 'owner' || member.role === 'mod');
}

// GET /api/games — list public games
router.get('/', async (req, res) => {
  try {
    const result = await dynamo.send(new ScanCommand({
      TableName: GAMES_TABLE,
      FilterExpression: '#vis = :pub',
      ExpressionAttributeNames: { '#n': 'name', '#vis': 'visibility', '#st': 'state' },
      ExpressionAttributeValues: { ':pub': 'public' },
      ProjectionExpression: 'gameId, slug, #n, tagline, #st, #vis, scenarioId, scenarioName, ownerUserId, ownerName, memberCount, currentInGameDate, createdAt',
    }));
    res.json((result.Items || []).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)));
  } catch (err) {
    console.error('List games error:', err);
    res.status(500).json({ error: 'Failed to fetch games.' });
  }
});

// GET /api/games/mine — games the logged-in user is a member of
router.get('/mine', requireAuth, async (req, res) => {
  try {
    const result = await dynamo.send(new QueryCommand({
      TableName: MEMBERS_TABLE,
      IndexName: 'user-index',
      KeyConditionExpression: 'userId = :uid',
      ExpressionAttributeValues: { ':uid': req.user.userId },
    }));

    const memberRows = result.Items || [];
    if (!memberRows.length) return res.json([]);

    const games = await Promise.all(memberRows.map(m => getGame(m.gameId)));
    res.json(games.filter(Boolean));
  } catch (err) {
    console.error('My games error:', err);
    res.status(500).json({ error: 'Failed to fetch your games.' });
  }
});

// GET /api/games/:id — get a game
router.get('/:id', async (req, res) => {
  try {
    const game = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });

    if (game.visibility === 'private') {
      if (!req.user) return res.status(403).json({ error: 'This game is private.' });
      const member = await getMember(game.gameId, req.user.userId);
      if (!member) return res.status(403).json({ error: 'This game is private.' });
    }

    res.json(game);
  } catch (err) {
    console.error('Get game error:', err);
    res.status(500).json({ error: 'Failed to fetch game.' });
  }
});

// POST /api/games — create a game from a scenario
router.post('/', requireAuth, async (req, res) => {
  const { scenarioId, name, slug, tagline, visibility, joinPolicy } = req.body;

  if (!scenarioId || !name || !slug) return res.status(400).json({ error: 'Scenario, name and slug are required.' });
  if (!SLUG_RE.test(slug)) return res.status(400).json({ error: 'Slug must be lowercase letters, numbers, and hyphens.' });

  try {
    // Validate scenario exists and is accessible
    const scenarioRes = await dynamo.send(new GetCommand({ TableName: SCENARIOS_TABLE, Key: { scenarioId } }));
    const scenario = scenarioRes.Item;
    if (!scenario) return res.status(404).json({ error: 'Scenario not found.' });
    if (scenario.state !== 'published' && scenario.authorUserId !== req.user.userId)
      return res.status(403).json({ error: 'Scenario is not published.' });

    // Check slug uniqueness
    const slugCheck = await dynamo.send(new QueryCommand({
      TableName: GAMES_TABLE,
      IndexName: 'slug-index',
      KeyConditionExpression: 'slug = :s',
      ExpressionAttributeValues: { ':s': slug },
      Limit: 1,
    }));
    if (slugCheck.Items?.length > 0) return res.status(409).json({ error: 'That slug is already taken.' });

    const gameId = uuidv4();
    const now    = new Date().toISOString();

    const game = {
      gameId,
      slug,
      name,
      tagline:         tagline    || '',
      state:           'setup',
      visibility:      visibility || 'private',
      joinPolicy:      joinPolicy || 'invite-only',
      scenarioId:      scenario.scenarioId,
      scenarioName:    scenario.name,
      scenarioVersion: scenario.version,
      ownerUserId:     req.user.userId,
      ownerName:       req.user.username,
      memberCount:     1,
      currentInGameDate: scenario.era || '',
      currentTurn:     0,
      createdAt:       now,
      updatedAt:       now,
    };

    await dynamo.send(new PutCommand({ TableName: GAMES_TABLE, Item: game }));

    // Add GM as owner member
    await dynamo.send(new PutCommand({
      TableName: MEMBERS_TABLE,
      Item: {
        gameId,
        userId:   req.user.userId,
        username: req.user.username,
        role:     'owner',
        joinedAt: now,
      },
    }));

    // Increment scenario game count
    await dynamo.send(new UpdateCommand({
      TableName: SCENARIOS_TABLE,
      Key: { scenarioId },
      UpdateExpression: 'SET gameCount = gameCount + :one',
      ExpressionAttributeValues: { ':one': 1 },
    }));

    res.json(game);
  } catch (err) {
    console.error('Create game error:', err);
    res.status(500).json({ error: 'Failed to create game.' });
  }
});

// PATCH /api/games/:id — update game settings (owner/mod)
router.patch('/:id', requireAuth, async (req, res) => {
  try {
    const game   = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });
    const member = await getMember(game.gameId, req.user.userId);
    if (!isOwnerOrMod(member)) return res.status(403).json({ error: 'Not authorized.' });

    const allowed = ['name', 'tagline', 'visibility', 'joinPolicy', 'state', 'currentInGameDate', 'currentTurn'];
    const updates = ['updatedAt = :upd'];
    const vals    = { ':upd': new Date().toISOString() };
    const names   = {};

    for (const key of allowed) {
      if (req.body[key] !== undefined) {
        const safe = key === 'name' || key === 'state' ? `#${key}` : key;
        updates.push(`${safe} = :${key}`);
        vals[`:${key}`] = req.body[key];
        if (key === 'name' || key === 'state') names[`#${key}`] = key;
      }
    }

    await dynamo.send(new UpdateCommand({
      TableName: GAMES_TABLE,
      Key: { gameId: req.params.id },
      UpdateExpression: `SET ${updates.join(', ')}`,
      ExpressionAttributeValues: vals,
      ...(Object.keys(names).length ? { ExpressionAttributeNames: names } : {}),
    }));

    res.json({ ok: true });
  } catch (err) {
    console.error('Update game error:', err);
    res.status(500).json({ error: 'Failed to update game.' });
  }
});

// GET /api/games/:id/members — list members
router.get('/:id/members', async (req, res) => {
  try {
    const game = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });

    if (game.visibility === 'private') {
      if (!req.user) return res.status(403).json({ error: 'Private game.' });
      const member = await getMember(game.gameId, req.user.userId);
      if (!member) return res.status(403).json({ error: 'Private game.' });
    }

    const result = await dynamo.send(new QueryCommand({
      TableName: MEMBERS_TABLE,
      KeyConditionExpression: 'gameId = :gid',
      ExpressionAttributeValues: { ':gid': req.params.id },
    }));
    res.json(result.Items || []);
  } catch (err) {
    console.error('List members error:', err);
    res.status(500).json({ error: 'Failed to fetch members.' });
  }
});

// POST /api/games/:id/members — invite a player by username
router.post('/:id/members', requireAuth, async (req, res) => {
  const { username, role } = req.body;
  if (!username) return res.status(400).json({ error: 'Username required.' });

  try {
    const game   = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });
    const member = await getMember(game.gameId, req.user.userId);
    if (!isOwnerOrMod(member)) return res.status(403).json({ error: 'Not authorized.' });

    // Look up the user to invite
    const userRes = await dynamo.send(new QueryCommand({
      TableName: 'ur_users',
      IndexName: 'username-index',
      KeyConditionExpression: 'username = :u',
      ExpressionAttributeValues: { ':u': username.toLowerCase() },
      Limit: 1,
    }));
    const invitee = userRes.Items?.[0];
    if (!invitee) return res.status(404).json({ error: 'Player not found.' });

    const existing = await getMember(game.gameId, invitee.userId);
    if (existing) return res.status(409).json({ error: 'Player is already a member.' });

    await dynamo.send(new PutCommand({
      TableName: MEMBERS_TABLE,
      Item: {
        gameId:   game.gameId,
        userId:   invitee.userId,
        username: invitee.username,
        role:     role || 'player',
        joinedAt: new Date().toISOString(),
      },
    }));

    await dynamo.send(new UpdateCommand({
      TableName: GAMES_TABLE,
      Key: { gameId: game.gameId },
      UpdateExpression: 'SET memberCount = memberCount + :one',
      ExpressionAttributeValues: { ':one': 1 },
    }));

    res.json({ ok: true });
  } catch (err) {
    console.error('Invite member error:', err);
    res.status(500).json({ error: 'Failed to invite player.' });
  }
});

// DELETE /api/games/:id/members/:userId — remove a member
router.delete('/:id/members/:userId', requireAuth, async (req, res) => {
  try {
    const game   = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });
    const member = await getMember(game.gameId, req.user.userId);

    const isSelf = req.params.userId === req.user.userId;
    if (!isSelf && !isOwnerOrMod(member)) return res.status(403).json({ error: 'Not authorized.' });

    await dynamo.send(new DeleteCommand({ TableName: MEMBERS_TABLE, Key: { gameId: req.params.id, userId: req.params.userId } }));
    await dynamo.send(new UpdateCommand({
      TableName: GAMES_TABLE,
      Key: { gameId: req.params.id },
      UpdateExpression: 'SET memberCount = memberCount - :one',
      ExpressionAttributeValues: { ':one': 1 },
    }));

    res.json({ ok: true });
  } catch (err) {
    console.error('Remove member error:', err);
    res.status(500).json({ error: 'Failed to remove member.' });
  }
});

// GET /api/games/:id/chronicle — get chronicle entries
router.get('/:id/chronicle', async (req, res) => {
  try {
    const game = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });
    if (game.visibility === 'private') {
      if (!req.user) return res.status(403).json({ error: 'Private game.' });
      const member = await getMember(game.gameId, req.user.userId);
      if (!member) return res.status(403).json({ error: 'Private game.' });
    }

    const result = await dynamo.send(new QueryCommand({
      TableName: CHRONICLE_TABLE,
      KeyConditionExpression: 'gameId = :gid',
      ExpressionAttributeValues: { ':gid': req.params.id },
      ScanIndexForward: false,
      Limit: 50,
    }));
    res.json(result.Items || []);
  } catch (err) {
    console.error('Chronicle error:', err);
    res.status(500).json({ error: 'Failed to fetch chronicle.' });
  }
});

// POST /api/games/:id/chronicle — add a chronicle entry
router.post('/:id/chronicle', requireAuth, async (req, res) => {
  const { body, inGameDate, isPublic } = req.body;
  if (!body?.trim()) return res.status(400).json({ error: 'Entry body is required.' });

  try {
    const game   = await getGame(req.params.id);
    if (!game) return res.status(404).json({ error: 'Game not found.' });
    const member = await getMember(game.gameId, req.user.userId);
    if (!member) return res.status(403).json({ error: 'You are not a member of this game.' });

    const now     = new Date().toISOString();
    const entryId = `${now}#${uuidv4()}`;

    const entry = {
      gameId: req.params.id,
      entryId,
      body:        body.trim(),
      authorUserId: req.user.userId,
      authorName:   req.user.username,
      authorRole:   member.role,
      inGameDate:   inGameDate || game.currentInGameDate || '',
      isPublic:     isPublic !== false,
      createdAt:    now,
    };

    await dynamo.send(new PutCommand({ TableName: CHRONICLE_TABLE, Item: entry }));
    res.json(entry);
  } catch (err) {
    console.error('Add chronicle error:', err);
    res.status(500).json({ error: 'Failed to add chronicle entry.' });
  }
});

module.exports = router;
