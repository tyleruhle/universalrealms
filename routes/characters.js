const express = require('express');
const { PutCommand, QueryCommand, DeleteCommand, UpdateCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 } = require('uuid');
const dynamo      = require('../lib/dynamo');
const requireAuth = require('../middleware/auth');

const router     = express.Router();
const CHARS_TABLE = 'ur_characters';
const USERS_TABLE = 'ur_users';

// GET /api/characters — current user's characters
router.get('/', requireAuth, async (req, res) => {
  try {
    const result = await dynamo.send(new QueryCommand({
      TableName: CHARS_TABLE,
      KeyConditionExpression: 'userId = :uid',
      ExpressionAttributeValues: { ':uid': req.user.userId },
      ScanIndexForward: false,
    }));
    res.json(result.Items || []);
  } catch (err) {
    console.error('Get characters error:', err);
    res.status(500).json({ error: 'Failed to fetch characters.' });
  }
});

// POST /api/characters — save a character
router.post('/', requireAuth, async (req, res) => {
  const {
    name, faction, archetype, culture, stats, notes,
    factionLabel, factionRank,
    archetypeName, archetypeIcon,
    cultureLabel, cultureRegion, cultureBonuses, cultureCombat,
    pc, traits, combatTrait,
  } = req.body;

  if (!name || !faction || !archetype)
    return res.status(400).json({ error: 'Name, faction, and archetype are required.' });

  try {
    const characterId = `${Date.now()}-${uuidv4()}`;
    const now = new Date().toISOString();

    const item = {
      userId:        req.user.userId,
      characterId,
      name:          name.trim(),
      faction,
      factionLabel:  factionLabel  || '',
      factionRank:   factionRank   || '',
      archetype,
      archetypeName: archetypeName || '',
      archetypeIcon: archetypeIcon || '',
      culture:       culture       || '',
      cultureLabel:  cultureLabel  || '',
      cultureRegion: cultureRegion || '',
      cultureBonuses:cultureBonuses|| '',
      cultureCombat: cultureCombat || '',
      stats:         stats         || {},
      pc:            pc            || 0,
      traits:        traits        || [],
      combatTrait:   combatTrait   || null,
      notes:         notes         || '',
      createdAt:     now,
      isPublic:      false,
    };

    await dynamo.send(new PutCommand({ TableName: CHARS_TABLE, Item: item }));

    await dynamo.send(new UpdateCommand({
      TableName: USERS_TABLE,
      Key: { userId: req.user.userId },
      UpdateExpression: 'SET stats.charactersCreated = stats.charactersCreated + :one',
      ExpressionAttributeValues: { ':one': 1 },
    }));

    res.json(item);
  } catch (err) {
    console.error('Save character error:', err);
    res.status(500).json({ error: 'Failed to save character.' });
  }
});

// PATCH /api/characters/:characterId/visibility — toggle public/private
router.patch('/:characterId/visibility', requireAuth, async (req, res) => {
  const { isPublic } = req.body;
  if (typeof isPublic !== 'boolean')
    return res.status(400).json({ error: 'isPublic must be a boolean.' });

  try {
    await dynamo.send(new UpdateCommand({
      TableName: CHARS_TABLE,
      Key: { userId: req.user.userId, characterId: req.params.characterId },
      UpdateExpression: 'SET isPublic = :v',
      ExpressionAttributeValues: { ':v': isPublic },
    }));
    res.json({ ok: true });
  } catch (err) {
    console.error('Visibility error:', err);
    res.status(500).json({ error: 'Failed to update visibility.' });
  }
});

// DELETE /api/characters/:characterId
router.delete('/:characterId', requireAuth, async (req, res) => {
  try {
    await dynamo.send(new DeleteCommand({
      TableName: CHARS_TABLE,
      Key: { userId: req.user.userId, characterId: req.params.characterId },
    }));
    res.json({ ok: true });
  } catch (err) {
    console.error('Delete character error:', err);
    res.status(500).json({ error: 'Failed to delete character.' });
  }
});

module.exports = router;
