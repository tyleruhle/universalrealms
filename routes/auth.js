const express  = require('express');
const bcrypt   = require('bcryptjs');
const jwt      = require('jsonwebtoken');
const crypto   = require('crypto');
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

// GET /api/auth/discord — redirect to Discord OAuth
router.get('/discord', (req, res) => {
  const state = crypto.randomBytes(16).toString('hex');
  res.cookie('discord_state', state, { httpOnly: true, maxAge: 5 * 60 * 1000, sameSite: 'lax' });

  const params = new URLSearchParams({
    client_id:     process.env.DISCORD_CLIENT_ID,
    redirect_uri:  process.env.DISCORD_REDIRECT_URI,
    response_type: 'code',
    scope:         'identify email',
    state,
  });
  res.redirect(`https://discord.com/api/oauth2/authorize?${params}`);
});

// GET /api/auth/discord/callback — handle Discord OAuth callback
router.get('/discord/callback', async (req, res) => {
  const { code, state } = req.query;
  const storedState = req.cookies.discord_state;

  if (!state || state !== storedState)
    return res.redirect('/login.html?error=state_mismatch');

  res.clearCookie('discord_state');

  if (!code) return res.redirect('/login.html?error=cancelled');

  try {
    // Exchange code for access token
    const tokenRes = await fetch('https://discord.com/api/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id:     process.env.DISCORD_CLIENT_ID,
        client_secret: process.env.DISCORD_CLIENT_SECRET,
        code,
        grant_type:    'authorization_code',
        redirect_uri:  process.env.DISCORD_REDIRECT_URI,
      }),
    });

    const tokenData = await tokenRes.json();
    if (!tokenData.access_token) throw new Error('No access token from Discord');

    // Fetch Discord user info
    const userRes = await fetch('https://discord.com/api/users/@me', {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    const du = await userRes.json();

    // Look up existing user by discordId
    const existing = await dynamo.send(new QueryCommand({
      TableName: USERS_TABLE,
      IndexName: 'discordId-index',
      KeyConditionExpression: 'discordId = :did',
      ExpressionAttributeValues: { ':did': du.id },
      Limit: 1,
    }));

    let user;

    if (existing.Items?.length > 0) {
      user = existing.Items[0];
      await dynamo.send(new UpdateCommand({
        TableName: USERS_TABLE,
        Key: { userId: user.userId },
        UpdateExpression: 'SET lastSeen = :now, discordUsername = :du',
        ExpressionAttributeValues: { ':now': new Date().toISOString(), ':du': du.username },
      }));
    } else {
      // Build a safe username from Discord handle
      let base = (du.username || 'player')
        .toLowerCase().replace(/[^a-z0-9_-]/g, '_').slice(0, 18);

      const taken = await dynamo.send(new QueryCommand({
        TableName: USERS_TABLE,
        IndexName: 'username-index',
        KeyConditionExpression: 'username = :u',
        ExpressionAttributeValues: { ':u': base },
        Limit: 1,
      }));
      const username = taken.Items?.length > 0
        ? base.slice(0, 14) + Math.floor(1000 + Math.random() * 9000)
        : base;

      const userId = uuidv4();
      const now    = new Date().toISOString();
      user = {
        userId,
        username,
        displayName:     du.global_name || du.username,
        email:           du.email || '',
        discordId:       du.id,
        discordUsername: du.username,
        authProvider:    'discord',
        createdAt:       now,
        lastSeen:        now,
        bio:             '',
        title:           'Wanderer',
        stats: { charactersCreated: 0, battlesRolled: 0, duelsRolled: 0, raidsRolled: 0 },
      };
      await dynamo.send(new PutCommand({ TableName: USERS_TABLE, Item: user }));
    }

    const token = signToken(user);
    res.cookie('ur_token', token, COOKIE_OPTS);
    res.redirect('/');
  } catch (err) {
    console.error('Discord OAuth error:', err);
    res.redirect('/login.html?error=discord_failed');
  }
});

module.exports = router;
