/**
 * worldsDb.js — world records (small metadata; large files live in worldStore).
 *
 * WORLD_DB=dynamo (default)  table ur_worlds (WORLDS_TABLE), partition key worldId,
 *                            GSI owner-index: ownerUserId + updatedAt
 * WORLD_DB=file              one JSON file under DATA_DIR, for local development
 */
const fsp  = require('fs/promises');
const path = require('path');

const PUBLIC_FIELDS = ['worldId', 'ownerUserId', 'name', 'createdAt', 'updatedAt', 'stage',
  'map', 'edits', 'history', 'bible', 'activeJob'];

function clean(item) {
  if (!item) return null;
  const out = {};
  for (const k of PUBLIC_FIELDS) if (item[k] !== undefined) out[k] = item[k];
  return out;
}

function dynamoDb(env) {
  const { GetCommand, PutCommand, QueryCommand, UpdateCommand, DeleteCommand } = require('@aws-sdk/lib-dynamodb');
  const dynamo = require('./dynamo');
  const TableName = env.WORLDS_TABLE || 'ur_worlds';
  return {
    kind: 'dynamo',
    async create(item) {
      await dynamo.send(new PutCommand({ TableName, Item: item, ConditionExpression: 'attribute_not_exists(worldId)' }));
      return clean(item);
    },
    async get(worldId) {
      const r = await dynamo.send(new GetCommand({ TableName, Key: { worldId } }));
      return clean(r.Item);
    },
    async listByOwner(ownerUserId) {
      const r = await dynamo.send(new QueryCommand({
        TableName, IndexName: 'owner-index',
        KeyConditionExpression: 'ownerUserId = :u', ExpressionAttributeValues: { ':u': ownerUserId },
        ScanIndexForward: false, Limit: 200,
      }));
      return (r.Items || []).map(clean);
    },
    async update(worldId, fields) {
      const names = {}, values = {}, sets = [];
      Object.entries({ ...fields, updatedAt: new Date().toISOString() }).forEach(([k, v], i) => {
        names[`#k${i}`] = k; values[`:v${i}`] = v; sets.push(`#k${i} = :v${i}`);
      });
      const r = await dynamo.send(new UpdateCommand({
        TableName, Key: { worldId }, UpdateExpression: 'SET ' + sets.join(', '),
        ConditionExpression: 'attribute_exists(worldId)',
        ExpressionAttributeNames: names, ExpressionAttributeValues: values, ReturnValues: 'ALL_NEW',
      }));
      return clean(r.Attributes);
    },
    async remove(worldId) {
      await dynamo.send(new DeleteCommand({ TableName, Key: { worldId } }));
    },
  };
}

function fileDb(env) {
  const file = path.resolve(env.DATA_DIR || path.join(__dirname, '..', 'data'), 'worlds-db.json');
  let cache = null, chain = Promise.resolve();
  async function load() {
    if (cache) return cache;
    try { cache = JSON.parse(await fsp.readFile(file, 'utf8')); }
    catch (e) { if (e.code !== 'ENOENT') throw e; cache = {}; }
    return cache;
  }
  async function save() {
    await fsp.mkdir(path.dirname(file), { recursive: true });
    const tmp = `${file}.tmp`;
    await fsp.writeFile(tmp, JSON.stringify(cache));
    await fsp.rename(tmp, file);
  }
  // Serialize writes so concurrent requests never interleave a read-modify-write.
  const locked = fn => (chain = chain.then(fn, fn));
  return {
    kind: 'file',
    create: item => locked(async () => { const db = await load(); if (db[item.worldId]) throw new Error('exists'); db[item.worldId] = item; await save(); return clean(item); }),
    get: async worldId => clean((await load())[worldId]),
    listByOwner: async uid => Object.values(await load()).filter(w => w.ownerUserId === uid)
      .sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || '')).map(clean),
    update: (worldId, fields) => locked(async () => {
      const db = await load(); if (!db[worldId]) throw new Error('missing');
      db[worldId] = { ...db[worldId], ...fields, updatedAt: new Date().toISOString() }; await save(); return clean(db[worldId]);
    }),
    remove: worldId => locked(async () => { const db = await load(); delete db[worldId]; await save(); }),
  };
}

function createDb(env = process.env) {
  return (env.WORLD_DB || 'dynamo') === 'file' ? fileDb(env) : dynamoDb(env);
}

module.exports = { createDb };
