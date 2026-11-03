require('dotenv').config();
const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');

const authRoutes      = require('./routes/auth');
const characterRoutes = require('./routes/characters');
const profileRoutes   = require('./routes/profiles');
const scenarioRoutes  = require('./routes/scenarios');
const gameRoutes      = require('./routes/games');
const worldRoutes     = require('./routes/worlds');

const app  = express();
const PORT = process.env.PORT || 3000;

// Atlas Studio edit manifests can exceed the default 100 KB body limit; only
// that one route gets a larger parser.
const jsonDefault = express.json();
const jsonLarge   = express.json({ limit: '6mb' });
app.use((req, res, next) =>
  (/^\/api\/worlds\/[^/]+\/edits$/.test(req.path) ? jsonLarge : jsonDefault)(req, res, next));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

app.use('/api/auth',       authRoutes);
app.use('/api/characters', characterRoutes);
app.use('/api/profiles',   profileRoutes);
app.use('/api/scenarios',  scenarioRoutes);
app.use('/api/games',      gameRoutes);
app.use('/api/worlds',     worldRoutes);

app.listen(PORT, () => {
  console.log(`Universal Realms running on port ${PORT}`);
});
