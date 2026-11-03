/**
 * worldStore.js — where a world's files live: maps, edits, bible, lore, history.
 *
 * Two backends behind one interface, chosen by WORLD_STORE:
 *   local  files under DATA_DIR (default ./data) — development, single server
 *   s3     objects in WORLD_BUCKET              — production
 *
 * Keys are always built by the server (worlds/<uuid>/<fixed name>), never
 * taken from a request, so a client cannot read or write outside its world.
 */
const fs   = require('fs');
const fsp  = require('fs/promises');
const path = require('path');

const KEY_RE = /^[a-z0-9][a-z0-9/_.-]{0,200}$/;

function checkKey(key) {
  if (!KEY_RE.test(key) || key.includes('..')) throw new Error(`invalid store key: ${key}`);
  return key;
}

function localStore(root) {
  const full = key => path.join(root, checkKey(key));
  return {
    kind: 'local',
    async put(key, body) {
      const p = full(key);
      await fsp.mkdir(path.dirname(p), { recursive: true });
      const tmp = `${p}.${process.pid}.${Date.now()}.tmp`;
      await fsp.writeFile(tmp, body);
      await fsp.rename(tmp, p);                       // atomic replace
    },
    async get(key) {
      try { return await fsp.readFile(full(key)); }
      catch (e) { if (e.code === 'ENOENT') return null; throw e; }
    },
    async putFile(key, file) { await this.put(key, await fsp.readFile(file)); },
    async getToFile(key, file) {
      const body = await this.get(key);
      if (body === null) return false;
      await fsp.writeFile(file, body);
      return true;
    },
    async del(prefix) {
      await fsp.rm(full(prefix), { recursive: true, force: true });
    },
  };
}

function s3Store(bucket, region) {
  // Loaded only when S3 is used, so local development needs no AWS setup.
  const { S3Client, PutObjectCommand, GetObjectCommand, ListObjectsV2Command,
          DeleteObjectsCommand } = require('@aws-sdk/client-s3');
  const s3 = new S3Client({ region });
  return {
    kind: 's3',
    async put(key, body) {
      await s3.send(new PutObjectCommand({ Bucket: bucket, Key: checkKey(key), Body: body }));
    },
    async get(key) {
      try {
        const r = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: checkKey(key) }));
        return Buffer.from(await r.Body.transformToByteArray());
      } catch (e) {
        if (e.name === 'NoSuchKey' || e.$metadata?.httpStatusCode === 404) return null;
        throw e;
      }
    },
    async putFile(key, file) { await this.put(key, fs.createReadStream(file)); },
    async getToFile(key, file) {
      const body = await this.get(key);
      if (body === null) return false;
      await fsp.writeFile(file, body);
      return true;
    },
    async del(prefix) {
      let token;
      do {
        const list = await s3.send(new ListObjectsV2Command({ Bucket: bucket, Prefix: checkKey(prefix), ContinuationToken: token }));
        const objs = (list.Contents || []).map(o => ({ Key: o.Key }));
        if (objs.length) await s3.send(new DeleteObjectsCommand({ Bucket: bucket, Delete: { Objects: objs } }));
        token = list.IsTruncated ? list.NextContinuationToken : undefined;
      } while (token);
    },
  };
}

function createStore(env = process.env) {
  if ((env.WORLD_STORE || 'local') === 's3') {
    if (!env.WORLD_BUCKET) throw new Error('WORLD_STORE=s3 needs WORLD_BUCKET');
    return s3Store(env.WORLD_BUCKET, env.AWS_REGION || 'us-east-2');
  }
  return localStore(path.resolve(env.DATA_DIR || path.join(__dirname, '..', 'data')));
}

module.exports = { createStore, checkKey };
