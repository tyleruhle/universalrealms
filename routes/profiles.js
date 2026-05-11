const express = require('express');
const { QueryCommand, GetCommand, UpdateCommand, ScanCommand } = require('@aws-sdk/lib-dynamodb');
const dynamo      = require('../lib/dynamo');
const requireAuth = require('../middleware/auth');

const router      = express.Router();
const USERS_TABLE = 'ur_users';
const CHARS_TABLE = 'ur_characters';

// GET /api/profiles — list all players
router.get('/', async (req, res) => {
  try {
    const result = await dynamo.send(new ScanCommand({
      TableName: USERS_TABLE,
      ProjectionExpression: 'userId, username, displayName, title, createdAt, bio, stats',
    }));

    const players = (result.Items || [])
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

    res.json(players);
  } catch (err) {
    console.error('List players error:', err);
    res.status(500).json({ error: 'Failed to fetch players.' });
  }
});

// GET /api/profiles/:username — public profile
router.get('/:username', async (req, res) => {
  try {
    const result = await dynamo.send(new QueryCommand({
      TableName: USERS_TABLE,
      IndexName: 'username-index',
      KeyConditionExpression: 'username = :u',
      ExpressionAttributeValues: { ':u': req.params.username.toLowerCase() },
      Limit: 1,
    }));

    const user = result.Items?.[0];
    if (!user) return res.status(404).json({ error: 'Player not found.' });

    const chars = await dynamo.send(new QueryCommand({
      TableName: CHARS_TABLE,
      KeyConditionExpression: 'userId = :uid',
      FilterExpression: 'isPublic = :t',
      ExpressionAttributeValues: { ':uid': user.userId, ':t': true },
      ScanIndexForward: false,
    }));

    const { passwordHash, email, ...publicUser } = user;
    res.json({ ...publicUser, characters: chars.Items || [] });
  } catch (err) {
    console.error('Profile error:', err);
    res.status(500).json({ error: 'Failed to fetch profile.' });
  }
});

// PATCH /api/profiles/me — update own profile (bio, title)
router.patch('/me', requireAuth, async (req, res) => {
  const { bio, title } = req.body;
  const updates = [];
  const vals    = {};

  if (bio !== undefined)   { updates.push('bio = :bio');     vals[':bio']   = bio.slice(0, 300);  }
  if (title !== undefined) { updates.push('title = :title'); vals[':title'] = title.slice(0, 40); }

  if (!updates.length)
    return res.status(400).json({ error: 'Nothing to update.' });

  try {
    await dynamo.send(new UpdateCommand({
      TableName: USERS_TABLE,
      Key: { userId: req.user.userId },
      UpdateExpression: `SET ${updates.join(', ')}`,
      ExpressionAttributeValues: vals,
    }));
    res.json({ ok: true });
  } catch (err) {
    console.error('Update profile error:', err);
    res.status(500).json({ error: 'Failed to update profile.' });
  }
});

module.exports = router;
