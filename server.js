require('dotenv').config();
const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');

const authRoutes      = require('./routes/auth');
const characterRoutes = require('./routes/characters');
const profileRoutes   = require('./routes/profiles');

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

app.use('/api/auth',       authRoutes);
app.use('/api/characters', characterRoutes);
app.use('/api/profiles',   profileRoutes);

app.listen(PORT, () => {
  console.log(`Universal Realms running on port ${PORT}`);
});
