const express  = require('express');
const bcrypt   = require('bcryptjs');
const jwt      = require('jsonwebtoken');
const { PutCommand, GetCommand, QueryCommand, UpdateCommand } = require('@aws-sdk/lib-dynamodb');
const { v4: uuidv4 } = require('uuid');
const dynamo      = require('../lib/dynamo');
const requireAuth = require('../middleware/auth');

const router      = express.Router();
const USERS_TABLE = 'ur_users';
const COOKIE_OPTS = {
  httpOnly: true,
  secure:   process.env.NODE_ENV === 'production',
  sameSite: 'lax',
  maxAge:   30 * 24 * 60 * 60 * 1000,
};

function signToken(user) {
  return jwt.sign(
    { userId: user.userId, username: user.username },
    process.env.JWT_SECRET,
    { expiresIn: '30d' }
  );
}

// POST /api/auth/register
router.post('/register', async (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password)
    return res.status(400).json({ error: 'All fields are required.' });
  if (username.length < 3 || username.length > 20)
    return res.status(400).json({ error: 'Username must be 3–20 characters.' });
  if (!/^[a-zA-Z0-9_-]+$/.test(username))
    return res.status(400).json({ error: 'Username may only contain letters, numbers, _ and -.' });
  if (password.length < 8)
    return res.status(400).json({ error: 'Password must be at least 8 characters.' });

  try {
    const emailCheck = await dynamo.send(new QueryCommand({
      TableName: USERS_TABLE,
      IndexName: 'email-index',
      KeyConditionExpression: 'email = :e',
      ExpressionAttributeValues: { ':e': email.toLowerCase() },
      Limit: 1,
    }));
    if (emailCheck.Items?.length > 0)
      return res.status(409).json({ error: 'That email is already registered.' });

    const usernameCheck = await dynamo.send(new QueryCommand({
      TableName: USERS_TABLE,
      IndexName: 'username-index',
      KeyConditionExpression: 'username = :u',
      ExpressionAttributeValues: { ':u': username.toLowerCase() },
      Limit: 1,
    }));
    if (usernameCheck.Items?.length > 0)
      return res.status(409).json({ error: 'That username is already taken.' });

    const userId      = uuidv4();
    const passwordHash = await bcrypt.hash(password, 12);
    const now          = new Date().toISOString();

    const item = {
      userId,
      username:     username.toLowerCase(),
      displayName:  username,
      email:        email.toLowerCase(),
      passwordHash,
      createdAt:    now,
      lastSeen:     now,
      bio:          '',
      title:        'Wanderer',
      stats: { charactersCreated: 0, battlesRolled: 0, duelsRolled: 0, raidsRolled: 0 },
    };

    await dynamo.send(new PutCommand({ TableName: USERS_TABLE, Item: item }));

    const token = signToken(item);
    res.cookie('ur_token', token, COOKIE_OPTS);
    res.json({ userId, username: item.username, displayName: item.displayName });
  } catch (err) {
    console.error('Register error:', err);
    res.status(500).json({ error: 'Registration failed. Please try again.' });
  }
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;

  if (!email || !password)
    return res.status(400).json({ error: 'Email and password are required.' });

  try {
    const result = await dynamo.send(new QueryCommand({
      TableName: USERS_TABLE,
      IndexName: 'email-index',
      KeyConditionExpression: 'email = :e',
      ExpressionAttributeValues: { ':e': email.toLowerCase() },
      Limit: 1,
    }));

    const user = result.Items?.[0];
    if (!user) return res.status(401).json({ error: 'Invalid email or password.' });

    const valid = await bcrypt.compare(password, user.passwordHash);
    if (!valid) return res.status(401).json({ error: 'Invalid email or password.' });

    await dynamo.send(new UpdateCommand({
      TableName: USERS_TABLE,
      Key: { userId: user.userId },
      UpdateExpression: 'SET lastSeen = :now',
      ExpressionAttributeValues: { ':now': new Date().toISOString() },
    }));

    const token = signToken(user);
    res.cookie('ur_token', token, COOKIE_OPTS);
    res.json({ userId: user.userId, username: user.username, displayName: user.displayName });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Login failed. Please try again.' });
  }
});

// POST /api/auth/logout
router.post('/logout', (req, res) => {
  res.clearCookie('ur_token');
  res.json({ ok: true });
});

// GET /api/auth/me
router.get('/me', requireAuth, async (req, res) => {
  try {
    const result = await dynamo.send(new GetCommand({
      TableName: USERS_TABLE,
      Key: { userId: req.user.userId },
    }));
    if (!result.Item) return res.status(404).json({ error: 'User not found.' });

    const { passwordHash, ...user } = result.Item;
    res.json(user);
  } catch (err) {
    console.error('Me error:', err);
    res.status(500).json({ error: 'Failed to retrieve session.' });
  }
});

module.exports = router;
