/* ===========================================================================
   The invariant that makes the whole security argument true.

   The README claims this service "imports nothing private": no database, no
   hypervisor, no identity secret. That claim is only worth something if
   something checks it, because the failure mode is quiet — someone adds a
   convenience import to answer "how many machines do I have?", and a public
   LLM endpoint suddenly has a path to the control plane.

   So: read every source file this container ships and fail on anything that
   would open such a path.
   =========================================================================== */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

/* Everything COPY'd in the Dockerfile. tools/ is included: it runs inside the
   container too (chat-probe), so it is as much a surface as the route. */
const SHIPPED = ['server.js', 'lib', 'routes', 'tools'];

function jsFiles(rel) {
  const abs = path.join(ROOT, rel);
  if (statSync(abs).isFile()) return abs.endsWith('.js') || abs.endsWith('.mjs') ? [abs] : [];
  return readdirSync(abs).flatMap((f) => jsFiles(path.join(rel, f)));
}

/* Module names that would give this process reach it must not have. */
const FORBIDDEN_MODULES = [
  'pg', 'postgres', 'mysql', 'mysql2', 'sqlite', 'better-sqlite3', 'mongodb', 'redis', 'ioredis',
  '@supabase/supabase-js', 'supabase',
  'proxmox', 'node-ssh', 'ssh2',
  'jose', 'jsonwebtoken', 'passport', 'bcrypt', 'argon2',
  'aws-sdk', '@aws-sdk/client-s3', 'stripe'
];

/* Env vars that only exist for the private side of the platform. Reading one
   here would mean this container is being trusted with a secret. */
const FORBIDDEN_ENV = [
  'SUPABASE_SERVICE_ROLE', 'SUPABASE_SERVICE_KEY', 'SUPABASE_URL', 'SUPABASE_ANON',
  'DATABASE_URL', 'POSTGRES_PASSWORD', 'PROXMOX_PASSWORD', 'PROXMOX_USER',
  'NODE_CRED_ENC_KEY', 'JWT_SECRET', 'SECRET_KEY'
];

const files = SHIPPED.flatMap(jsFiles);

test('the service ships some source to check', () => {
  assert.ok(files.length >= 4, `expected several shipped files, found ${files.length}`);
});

test('no import reaches a database, a hypervisor or an auth library', () => {
  const offenders = [];
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    // Strip comments: this very file names the modules it forbids, and so does
    // the route's header. Only real import/require statements count.
    const code = src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    for (const mod of FORBIDDEN_MODULES) {
      const re = new RegExp(`(from|require\\s*\\()\\s*['"\`]${mod.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(/[^'"\`]*)?['"\`]`);
      if (re.test(code)) offenders.push(`${path.relative(ROOT, f)} → ${mod}`);
    }
  }
  assert.deepEqual(offenders, [], 'private dependency imported into the public chat service');
});

test('no private environment variable is read', () => {
  const offenders = [];
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    for (const key of FORBIDDEN_ENV) {
      if (new RegExp(`process\\.env\\.${key}\\b|process\\.env\\[['"\`]${key}['"\`]\\]`).test(code)) {
        offenders.push(`${path.relative(ROOT, f)} → ${key}`);
      }
    }
  }
  assert.deepEqual(offenders, [], 'private env var read by the public chat service');
});

test('package.json declares no private dependency', () => {
  const pkg = JSON.parse(readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  const deps = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies });
  const bad = deps.filter((d) => FORBIDDEN_MODULES.includes(d));
  assert.deepEqual(bad, [], 'private dependency declared in package.json');
});

test('the knowledge base is the only file the service reads', () => {
  // readFileSync anywhere outside lib/chat-kb.js (which reads the KB) and
  // tools/ (build-time helpers) would be a second, unreviewed data source.
  const offenders = [];
  for (const f of files) {
    const rel = path.relative(ROOT, f).replace(/\\/g, '/');
    if (rel === 'lib/chat-kb.js' || rel.startsWith('tools/')) continue;
    const code = readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');
    if (/readFileSync|readFile\(|createReadStream/.test(code)) offenders.push(rel);
  }
  assert.deepEqual(offenders, [], 'unexpected file read outside the knowledge base');
});
